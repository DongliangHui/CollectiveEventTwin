from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import city as city_service
from . import models, schemas
from .audit import write_audit
from .foundation import api_error


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_topics(session: Session, actor: models.User, city_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 50) -> list[dict]:
    statement = select(models.Topic).order_by(models.Topic.heat_score.desc(), models.Topic.updated_at.desc())
    if city_id:
        statement = statement.where(models.Topic.city_id == city_id)
    if status:
        statement = statement.where(models.Topic.status == status)
    rows = session.execute(statement.offset(max(page - 1, 0) * page_size).limit(page_size)).scalars()
    return [serialize_topic_with_counts(session, row) for row in rows]


def create_topic(session: Session, request: schemas.TopicCreate, actor: models.User, trace_id: str) -> dict:
    city = city_service.ensure_city(session, request.city_id, actor, trace_id)
    source_event = _source_city_event(session, request.created_from)
    topic = models.Topic(
        id=_id("TOP"),
        tenant_id=actor.tenant_id,
        city_id=city.id,
        title=request.title,
        status="candidate",
        heat_score=source_event.heat_score if source_event else 0,
        created_from_type=request.created_from.object_type if request.created_from else None,
        created_from_id=request.created_from.object_id if request.created_from else None,
        payload=request.payload | {
            "evidence_refs": source_event.evidence_refs if source_event else [],
            "synthetic": bool(source_event.payload.get("synthetic")) if source_event else False,
        },
    )
    session.add(topic)
    session.flush()
    if source_event is not None:
        before = city_service.serialize_city_event(source_event)
        source_event.topic_id = topic.id
        source_event.status = "topic_created"
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="city_event",
                from_object_id=source_event.id,
                to_object_type="topic",
                to_object_id=topic.id,
                relation="created_topic",
                is_synthetic=bool(source_event.payload.get("synthetic")),
                payload={"evidence_refs": source_event.evidence_refs},
            )
        )
    else:
        before = {}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="topic.create",
        object_type="topic",
        object_id=topic.id,
        reason=request.reason,
        before=before,
        after=serialize_topic(topic),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_topic(topic)


def get_topic(session: Session, topic_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    return serialize_topic_with_counts(session, topic) | {"lineage": _lineage_for_topic(session, topic)}


def update_topic(session: Session, topic_id: str, request: schemas.TopicPatch, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    before = serialize_topic(topic)
    if request.title is not None:
        topic.title = request.title
    if request.status is not None:
        topic.status = request.status
    if request.payload is not None:
        topic.payload = topic.payload | request.payload
    after = serialize_topic(topic)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="topic.update",
        object_type="topic",
        object_id=topic.id,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return after


def situation_view(session: Session, topic_id: str, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    snapshot = jsonable_encoder(compute_situation_snapshot(session, topic))
    before_snapshot = topic.payload.get("situation_snapshot", {})
    topic.payload = topic.payload | {"situation_snapshot": snapshot}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="topic.situation_snapshot_update",
        object_type="topic",
        object_id=topic.id,
        before=before_snapshot,
        after=snapshot,
        trace_id=trace_id,
    )
    session.commit()
    legacy = _legacy_topic_page(topic, snapshot)
    return {
        "page_state": "empty" if not snapshot["events"] else "ready",
        "permissions": {"topic:read": True, "topic:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "topics/city_events/raw_records", "snapshot_version": snapshot["version"]},
        "degraded_sources": snapshot["degraded_sources"],
        "audit_context": {"object_type": "topic", "object_id": topic.id, "object_version": snapshot["version"], "actor_id": actor.id},
        "primary_data": snapshot | {"legacy_page_view": legacy},
        "actions": [
            {"id": "update-topic", "label": "Update topic status", "method": "PATCH", "href": f"/api/v1/topics/{topic.id}", "enabled": True},
            {"id": "enter-mainline", "label": "Enter mainline modeling", "method": "GET", "href": f"/api/v1/topics/{topic.id}/candidate-mainlines", "enabled": bool(snapshot["candidate_mainlines"])},
        ],
    }


def source_breakdown(session: Session, topic_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    return compute_situation_snapshot(session, topic)["source_breakdown"]


def spread_paths(session: Session, topic_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    return {"paths": compute_situation_snapshot(session, topic)["spread_paths"]}


def emotion_stance(session: Session, topic_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    return compute_situation_snapshot(session, topic)["emotion_stance"]


def candidate_mainlines(session: Session, topic_id: str) -> dict:
    topic = _topic_or_404(session, topic_id)
    return {"candidate_mainlines": compute_situation_snapshot(session, topic)["candidate_mainlines"]}


def compute_situation_snapshot(session: Session, topic: models.Topic) -> dict:
    events = _related_events(session, topic)
    source_breakdown_data = _source_breakdown(events)
    spread = _spread_paths(events)
    emotion = _emotion_stance(events)
    candidates = _candidate_mainlines(topic, events)
    evidence_refs = _dedupe_refs([ref for event in events for ref in event.evidence_refs])
    return {
        "version": "s3b-topic-situation-v1",
        "topic": serialize_topic(topic),
        "events": [city_service.serialize_city_event(event) for event in events],
        "source_breakdown": source_breakdown_data,
        "spread_paths": spread,
        "emotion_stance": emotion,
        "candidate_mainlines": candidates,
        "evidence_refs": evidence_refs,
        "degraded_sources": [],
        "generated_at": utcnow(),
    }


def serialize_topic(topic: models.Topic) -> dict:
    return city_service.serialize_topic(topic)


def serialize_topic_with_counts(session: Session, topic: models.Topic) -> dict:
    related = _related_events(session, topic)
    return serialize_topic(topic) | {
        "event_count": len(related),
        "evidence_ref_count": len(_dedupe_refs([ref for event in related for ref in event.evidence_refs])),
    }


def _source_city_event(session: Session, ref: schemas.EntityRef | None) -> models.CityEvent | None:
    if ref is None:
        return None
    if ref.object_type != "city_event":
        raise api_error(400, "INVALID_TOPIC_SOURCE", "Topic created_from must reference a city_event.")
    event = session.get(models.CityEvent, ref.object_id)
    if event is None:
        raise api_error(404, "CITY_EVENT_NOT_FOUND", "City event not found.")
    return event


def _topic_or_404(session: Session, topic_id: str) -> models.Topic:
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    return topic


def _related_events(session: Session, topic: models.Topic) -> list[models.CityEvent]:
    linked = list(
        session.execute(
            select(models.CityEvent)
            .where(models.CityEvent.topic_id == topic.id)
            .order_by(models.CityEvent.heat_score.desc(), models.CityEvent.created_at.desc())
        ).scalars()
    )
    if linked:
        event_type = linked[0].event_type
        related = list(
            session.execute(
                select(models.CityEvent)
                .where(models.CityEvent.city_id == topic.city_id, models.CityEvent.event_type == event_type)
                .order_by(models.CityEvent.heat_score.desc(), models.CityEvent.created_at.desc())
                .limit(30)
            ).scalars()
        )
        by_id = {event.id: event for event in related + linked}
        return sorted(by_id.values(), key=lambda event: (event.heat_score, event.created_at), reverse=True)
    return list(
        session.execute(
            select(models.CityEvent)
            .where(models.CityEvent.city_id == topic.city_id)
            .order_by(models.CityEvent.heat_score.desc(), models.CityEvent.created_at.desc())
            .limit(20)
        ).scalars()
    )


def _source_breakdown(events: list[models.CityEvent]) -> dict:
    by_type = Counter(event.event_type for event in events)
    by_source = Counter(str(event.payload.get("source_type", "unknown")) for event in events)
    return {
        "total": len(events),
        "by_event_type": [{"label": key, "count": value} for key, value in by_type.most_common()],
        "by_source_type": [{"label": key, "count": value} for key, value in by_source.most_common()],
        "media_count": len([event for event in events if event.event_type == "media" or event.payload.get("media_asset_id")]),
        "synthetic_count": len([event for event in events if event.payload.get("synthetic")]),
    }


def _spread_paths(events: list[models.CityEvent]) -> list[dict]:
    source_counts = Counter(str(event.payload.get("source_type", "unknown")) for event in events)
    paths = []
    for index, (source, count) in enumerate(source_counts.most_common()):
        refs = _dedupe_refs([ref for event in events if event.payload.get("source_type") == source for ref in event.evidence_refs])
        paths.append(
            {
                "id": f"SPREAD-{index + 1}",
                "nodes": [source, "city_event", "topic"],
                "count": count,
                "weight": round(count / max(len(events), 1), 4),
                "evidence_refs": refs[:8],
            }
        )
    return paths


def _emotion_stance(events: list[models.CityEvent]) -> dict:
    high_risk = len([event for event in events if event.risk_score >= 70])
    medium = len([event for event in events if 55 <= event.risk_score < 70])
    low = max(len(events) - high_risk - medium, 0)
    total = max(len(events), 1)
    samples = [
        {
            "city_event_id": event.id,
            "stance": _stance_for_event(event),
            "summary": event.summary,
            "evidence_refs": event.evidence_refs,
        }
        for event in events[:8]
    ]
    return {
        "sentiment": [
            {"label": "negative_or_urgent", "value": round(high_risk / total, 4)},
            {"label": "watching", "value": round(medium / total, 4)},
            {"label": "neutral_or_low", "value": round(low / total, 4)},
        ],
        "stance_samples": samples,
    }


def _candidate_mainlines(topic: models.Topic, events: list[models.CityEvent]) -> list[dict]:
    if not events:
        return []
    top = sorted(events, key=lambda event: (event.risk_score, event.heat_score), reverse=True)[:3]
    candidates = []
    for index, event in enumerate(top):
        probability = min(0.92, 0.48 + event.risk_score / 220 + event.heat_score / 360 - index * 0.04)
        candidates.append(
            {
                "id": f"CML-{topic.id}-{index + 1}",
                "topic_id": topic.id,
                "title": f"{topic.title} / {event.event_type} path",
                "probability": round(probability, 4),
                "evidence_refs": event.evidence_refs,
                "evidence_gaps": _evidence_gaps(event),
                "input_event_ids": [event.id],
                "status": "candidate",
            }
        )
    return candidates


def _stance_for_event(event: models.CityEvent) -> str:
    if event.risk_score >= 72:
        return "requests_response_or_clarification"
    if event.event_type == "media":
        return "asks_for_context_and_redaction"
    if event.event_type == "public_service":
        return "asks_for_process_and_timeline"
    return "observes_and_compares_sources"


def _evidence_gaps(event: models.CityEvent) -> list[str]:
    gaps = ["official_response_window", "independent_evidence_review"]
    if event.event_type == "media":
        gaps.append("media_redaction_and_original_context")
    if event.risk_score >= 70:
        gaps.append("offline_impact_confirmation")
    return gaps


def _dedupe_refs(refs: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for ref in refs:
        key = (ref.get("object_type"), ref.get("object_id"), ref.get("object_version"))
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _lineage_for_topic(session: Session, topic: models.Topic) -> list[dict]:
    rows = session.execute(
        select(models.LineageEdge).where(
            ((models.LineageEdge.from_object_type == "topic") & (models.LineageEdge.from_object_id == topic.id))
            | ((models.LineageEdge.to_object_type == "topic") & (models.LineageEdge.to_object_id == topic.id))
        )
    ).scalars()
    return [
        {
            "lineage_edge_id": row.id,
            "from_object_type": row.from_object_type,
            "from_object_id": row.from_object_id,
            "to_object_type": row.to_object_type,
            "to_object_id": row.to_object_id,
            "relation": row.relation,
            "is_synthetic": row.is_synthetic,
            "payload": row.payload,
        }
        for row in rows
    ]


def _legacy_topic_page(topic: models.Topic, snapshot: dict) -> dict:
    metrics = [
        {"label": "Topic heat", "value": round(topic.heat_score, 2), "tone": "red"},
        {"label": "Related events", "value": len(snapshot["events"]), "tone": "blue"},
        {"label": "Evidence refs", "value": len(snapshot["evidence_refs"]), "tone": "green"},
        {"label": "Media count", "value": snapshot["source_breakdown"]["media_count"], "tone": "violet"},
    ]
    return {
        "case_id": "xian-topic",
        "page": "risk",
        "title": "Topic Situation",
        "subtitle": topic.title,
        "nav": _nav("CASE-CAMPUS-001"),
        "metrics": metrics,
        "sections": [
            {"id": "sources", "title": "Topic source breakdown", "kind": "sources", "items": snapshot["source_breakdown"]["by_source_type"]},
            {"id": "phase", "title": "Topic spread phase", "kind": "timeline", "items": [path["nodes"] for path in snapshot["spread_paths"]]},
            {"id": "sentiment", "title": "Emotion and stance", "kind": "sentiment", "items": snapshot["emotion_stance"]["sentiment"]},
            {"id": "candidates", "title": "Candidate mainlines", "kind": "mainlines", "items": snapshot["candidate_mainlines"]},
            {"id": "review", "title": "Evidence references", "kind": "signals", "items": snapshot["events"]},
        ],
        "actions": [{"id": "enter-mainline", "label": "Enter mainline modeling", "to_page": "mainline"}],
        "raw": snapshot,
    }


def _nav(case_id: str) -> list[dict]:
    pages = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]
    return [{"page": page, "label": page, "path": f"/cases/{case_id}/{page}"} for page in pages]
