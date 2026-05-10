from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .audit import write_audit
from .foundation import DEFAULT_TENANT_ID, api_error

XIAN_CITY_ID = "xian"
XIAN_CENTER = [108.9398, 34.3416]


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_cities(session: Session, actor: models.User, trace_id: str) -> list[dict]:
    ensure_city(session, XIAN_CITY_ID, actor, trace_id)
    session.commit()
    rows = session.execute(select(models.City).order_by(models.City.id)).scalars()
    return [serialize_city(row) for row in rows]


def city_overview(session: Session, city_id: str, actor: models.User, trace_id: str) -> dict:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    events = _events(session, city_id)
    sources = _source_rows(session)
    health = _source_health_rows(session)
    map_state = _map_state_for_user(session, city_id, actor.id)
    session.commit()

    page_state = "empty" if not events else "degraded" if any(item["status"] in {"degraded", "unhealthy", "blocked"} for item in health) else "ready"
    metrics = _overview_metrics(events, sources)
    legacy_sections = [
        {"id": "map", "title": "City event radar", "kind": "map", "items": [_legacy_signal(event) for event in events]},
        {"id": "layers", "title": "Layer controls", "kind": "chips", "items": ["hot", "rising", "media", "follow"]},
        {"id": "hot", "title": "Current event ranking", "kind": "signals", "items": [_legacy_signal(event) for event in events]},
        {"id": "source-status", "title": "Source health", "kind": "sources", "items": sources},
    ]
    legacy_page_view = {
        "case_id": "xian-city",
        "page": "city",
        "title": "Xi'an City Situation",
        "subtitle": "Synthetic-labelled Xi'an social issue monitoring from PostgreSQL raw records",
        "nav": _nav("CASE-CAMPUS-001"),
        "metrics": metrics,
        "sections": legacy_sections,
        "actions": [],
        "raw": {"city": serialize_city(city), "map_state": serialize_map_state(map_state) if map_state else None},
    }
    return _page_view_model(
        city=city,
        page_state=page_state,
        actor=actor,
        trace_id=trace_id,
        primary_data={
            "city": serialize_city(city),
            "events": [serialize_city_event(event) for event in events],
            "metrics": metrics,
            "sections": legacy_sections,
            "source_health": health,
            "map_state": serialize_map_state(map_state) if map_state else None,
            "legacy_page_view": legacy_page_view,
        },
        degraded_sources=[item for item in health if item["status"] in {"degraded", "unhealthy", "blocked"}],
    )


def city_map_layers(session: Session, city_id: str, actor: models.User, trace_id: str) -> list[dict]:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    events = _events(session, city_id)
    session.commit()
    point_features = [_map_feature(event, index) for index, event in enumerate(events)]
    heat_features = [
        {
            "id": f"heat-{event.id}",
            "coordinates": _event_coordinates(event),
            "weight": round(event.heat_score / 100, 4),
            "risk_score": event.risk_score,
            "evidence_refs": event.evidence_refs,
        }
        for event in events
    ]
    return [
        {"id": "xian-base-map", "layer_type": "map", "features": [{"config": {"center": XIAN_CENTER, "zoom": 10.8}}]},
        {"id": "xian-event-points", "layer_type": "point", "features": point_features},
        {"id": "xian-heat", "layer_type": "heat", "features": heat_features},
    ]


def update_city_map_state(session: Session, city_id: str, request: schemas.CityMapStateWrite, actor: models.User, trace_id: str) -> dict:
    city = ensure_city(session, city_id, actor, trace_id)
    state = _map_state_for_user(session, city.id, actor.id)
    before = serialize_map_state(state) if state else None
    if state is None:
        state = models.CityMapState(
            id=_id("CMS"),
            tenant_id=actor.tenant_id,
            city_id=city.id,
            user_id=actor.id,
            layer_mode=request.layer_mode,
            filters=request.filters,
            version=1,
            payload={"source": "s3a_city_page"},
        )
        session.add(state)
    else:
        state.layer_mode = request.layer_mode
        state.filters = request.filters
        state.version += 1
    session.flush()
    after = serialize_map_state(state)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="city.map_state_update",
        object_type="city_map_state",
        object_id=state.id,
        object_version=str(state.version),
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return after


def list_city_events(session: Session, city_id: str, actor: models.User, trace_id: str, limit: int = 50, status: str | None = None) -> list[dict]:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    events = _events(session, city_id, limit=limit, status=status)
    session.commit()
    return [serialize_city_event(event) for event in events]


def city_event_rankings(session: Session, city_id: str, actor: models.User, trace_id: str, rank_mode: str = "heat", limit: int = 20) -> list[dict]:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    events = _events(session, city_id, limit=200)
    if rank_mode == "risk":
        events = sorted(events, key=lambda event: (event.risk_score, event.heat_score), reverse=True)
    elif rank_mode == "freshness":
        events = sorted(events, key=lambda event: event.occurred_at or event.created_at, reverse=True)
    elif rank_mode == "media":
        events = sorted(events, key=lambda event: (bool(event.payload.get("media_asset_id")), event.heat_score), reverse=True)
    else:
        events = sorted(events, key=lambda event: event.heat_score, reverse=True)
    session.commit()
    return [serialize_city_event(event) for event in events[:limit]]


def city_source_health_view(session: Session, city_id: str, actor: models.User, trace_id: str) -> dict:
    city = ensure_city(session, city_id, actor, trace_id)
    health = _source_health_rows(session)
    sources = _source_rows(session)
    page_state = "empty" if not sources else "degraded" if any(row["status"] in {"degraded", "unhealthy", "blocked"} for row in health) else "ready"
    session.commit()
    return _page_view_model(
        city=city,
        page_state=page_state,
        actor=actor,
        trace_id=trace_id,
        primary_data={"city": serialize_city(city), "sources": sources, "source_health": health},
        degraded_sources=[item for item in health if item["status"] in {"degraded", "unhealthy", "blocked"}],
    )


def city_media_evidence(session: Session, city_id: str, actor: models.User, trace_id: str, limit: int = 50) -> list[dict]:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    statement = (
        select(models.MediaAsset, models.RawRecord)
        .join(models.RawRecord, models.RawRecord.id == models.MediaAsset.raw_record_id)
        .where(models.RawRecord.city_id == city_id)
        .order_by(models.MediaAsset.created_at.desc())
        .limit(limit)
    )
    rows = session.execute(statement).all()
    session.commit()
    return [_serialize_media_asset(asset, record) for asset, record in rows]


def city_timeline(session: Session, city_id: str, actor: models.User, trace_id: str, limit: int = 50) -> list[dict]:
    city = ensure_city(session, city_id, actor, trace_id)
    sync_city_events_from_raw_records(session, city, actor, trace_id)
    rows = _events(session, city_id, limit=limit)
    session.commit()
    return [
        {
            "id": f"TL-{event.id}",
            "city_event_id": event.id,
            "occurred_at": event.occurred_at or event.created_at,
            "title": event.title,
            "status": event.status,
            "heat_score": event.heat_score,
            "evidence_refs": event.evidence_refs,
            "synthetic": bool(event.payload.get("synthetic")),
        }
        for event in rows
    ]


def get_city_event(session: Session, city_event_id: str, actor: models.User, trace_id: str) -> dict:
    event = session.get(models.CityEvent, city_event_id)
    if event is None:
        raise api_error(404, "CITY_EVENT_NOT_FOUND", "City event not found.")
    return serialize_city_event(event) | {"lineage": _lineage_for_event(session, event)}


def create_topic_from_city_event(session: Session, city_event_id: str, actor: models.User, trace_id: str) -> dict:
    event = session.get(models.CityEvent, city_event_id)
    if event is None:
        raise api_error(404, "CITY_EVENT_NOT_FOUND", "City event not found.")
    existing = session.get(models.Topic, event.topic_id) if event.topic_id else None
    if existing is not None:
        return serialize_topic(existing)

    topic = models.Topic(
        id=_id("TOP"),
        tenant_id=actor.tenant_id,
        city_id=event.city_id,
        title=event.title,
        status="candidate",
        heat_score=event.heat_score,
        created_from_type="city_event",
        created_from_id=event.id,
        payload={"evidence_refs": event.evidence_refs, "synthetic": bool(event.payload.get("synthetic"))},
    )
    session.add(topic)
    session.flush()
    before = serialize_city_event(event)
    event.topic_id = topic.id
    event.status = "topic_created"
    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="city_event",
            from_object_id=event.id,
            to_object_type="topic",
            to_object_id=topic.id,
            relation="created_topic",
            is_synthetic=bool(event.payload.get("synthetic")),
            payload={"evidence_refs": event.evidence_refs},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="city_event.create_topic",
        object_type="topic",
        object_id=topic.id,
        before=before,
        after={"topic": serialize_topic(topic), "city_event": serialize_city_event(event)},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_topic(topic)


def ensure_city(session: Session, city_id: str, actor: models.User | None = None, trace_id: str | None = None) -> models.City:
    city = session.get(models.City, city_id)
    if city is not None:
        return city
    tenant_id = actor.tenant_id if actor else DEFAULT_TENANT_ID
    city = models.City(
        id=city_id,
        tenant_id=tenant_id,
        name="Xi'an",
        region_code="CN-SN-XA",
        status="active",
        payload={"center": XIAN_CENTER, "synthetic_allowed": True, "scope": "s3a_city_page"},
    )
    session.add(city)
    session.flush()
    if actor is not None:
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="city.ensure",
            object_type="city",
            object_id=city.id,
            after=serialize_city(city),
            trace_id=trace_id,
        )
    return city


def sync_city_events_from_raw_records(session: Session, city: models.City, actor: models.User, trace_id: str) -> None:
    records = list(
        session.execute(
            select(models.RawRecord)
            .where(models.RawRecord.city_id == city.id)
            .order_by(models.RawRecord.created_at.asc(), models.RawRecord.id.asc())
            .limit(500)
        ).scalars()
    )
    existing_raw_ids = set(
        session.execute(
            select(models.CityEvent.raw_record_id).where(models.CityEvent.city_id == city.id, models.CityEvent.raw_record_id.is_not(None))
        ).scalars()
    )
    for index, record in enumerate(records):
        if record.id in existing_raw_ids:
            continue
        event = _city_event_from_raw_record(city, record, index)
        session.add(event)
        session.flush()
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="raw_record",
                from_object_id=record.id,
                to_object_type="city_event",
                to_object_id=event.id,
                relation="derived_city_event",
                is_synthetic=record.is_synthetic,
                payload={"source_type": record.source_type, "evidence_refs": event.evidence_refs},
            )
        )
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="city_event.derive_from_raw_record",
            object_type="city_event",
            object_id=event.id,
            after=serialize_city_event(event),
            trace_id=trace_id,
        )


def serialize_city(city: models.City) -> dict:
    return {"id": city.id, "name": city.name, "region_code": city.region_code, "status": city.status, "payload": city.payload}


def serialize_city_event(event: models.CityEvent) -> dict:
    return {
        "id": event.id,
        "city_id": event.city_id,
        "topic_id": event.topic_id,
        "raw_record_id": event.raw_record_id,
        "title": event.title,
        "summary": event.summary,
        "status": event.status,
        "event_type": event.event_type,
        "heat_score": event.heat_score,
        "risk_score": event.risk_score,
        "evidence_refs": event.evidence_refs,
        "occurred_at": event.occurred_at,
        "payload": event.payload,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def serialize_map_state(state: models.CityMapState) -> dict:
    return {
        "map_state_id": state.id,
        "tenant_id": state.tenant_id,
        "city_id": state.city_id,
        "user_id": state.user_id,
        "layer_mode": state.layer_mode,
        "filters": state.filters,
        "version": state.version,
        "payload": state.payload,
        "updated_at": state.updated_at,
    }


def serialize_topic(topic: models.Topic) -> dict:
    return {
        "id": topic.id,
        "tenant_id": topic.tenant_id,
        "city_id": topic.city_id,
        "title": topic.title,
        "status": topic.status,
        "heat_score": topic.heat_score,
        "created_from": {"object_type": topic.created_from_type, "object_id": topic.created_from_id} if topic.created_from_type and topic.created_from_id else None,
        "payload": topic.payload,
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }


def _city_event_from_raw_record(city: models.City, record: models.RawRecord, index: int) -> models.CityEvent:
    score_seed = int(hashlib.sha256(f"{record.id}:{record.content_hash}".encode("utf-8")).hexdigest()[:8], 16)
    media_boost = 8 if record.source_type in {"media", "live_segment"} or record.payload.get("media_type") else 0
    heat = min(98.0, 52.0 + (score_seed % 34) + media_boost)
    risk = min(96.0, 42.0 + ((score_seed // 37) % 32) + (6 if "minor" in str(record.payload).lower() else 0))
    coordinates = _coordinates_for_record(record, index)
    evidence_refs = [
        {
            "object_type": "raw_record",
            "object_id": record.id,
            "object_version": record.content_hash,
            "excerpt_hash": record.content_hash[:16],
            "confidence": 0.78 if record.is_synthetic else 0.66,
        }
    ]
    return models.CityEvent(
        id=_id("CEV"),
        tenant_id=record.tenant_id,
        city_id=city.id,
        topic_id=None,
        raw_record_id=record.id,
        title=record.title,
        summary=_summary_for_record(record),
        status="candidate",
        event_type=_event_type_for_record(record),
        heat_score=round(heat, 2),
        risk_score=round(risk, 2),
        evidence_refs=evidence_refs,
        occurred_at=record.occurred_at or record.created_at,
        payload={
            "synthetic": record.is_synthetic,
            "source_flags": record.payload.get("source_flags", {"synthetic": record.is_synthetic}),
            "data_source_id": record.data_source_id,
            "collection_run_id": record.collection_run_id,
            "source_type": record.source_type,
            "coordinates": coordinates,
            "district": record.payload.get("district", "xian"),
            "tags": record.payload.get("tags", []),
            "media_asset_id": _media_asset_id_for_record(record),
        },
    )


def _summary_for_record(record: models.RawRecord) -> str:
    payload = session_payload_text(record)
    if payload:
        return payload[:240]
    return f"Derived from raw record {record.id}; source_type={record.source_type}; synthetic={record.is_synthetic}."


def session_payload_text(record: models.RawRecord) -> str:
    value = record.payload.get("request_payload", {}).get("summary") if isinstance(record.payload.get("request_payload"), dict) else None
    if isinstance(value, str) and value:
        return value
    source_uri = record.payload.get("source_uri")
    if source_uri:
        return f"Collected from {source_uri}; no fact judgement is made without evidence review."
    return ""


def _event_type_for_record(record: models.RawRecord) -> str:
    tags = {str(tag).lower() for tag in record.payload.get("tags", [])}
    if record.source_type in {"media", "live_segment"} or {"media", "video", "image"} & tags:
        return "media"
    if {"traffic", "transit", "school"} & tags:
        return "mobility"
    if {"medical", "billing", "pension"} & tags:
        return "public_service"
    if {"property", "demolition", "compensation"} & tags:
        return "city_management"
    return "social_life"


def _coordinates_for_record(record: models.RawRecord, index: int) -> list[float]:
    if isinstance(record.payload.get("coordinates"), list) and len(record.payload["coordinates"]) == 2:
        return [float(record.payload["coordinates"][0]), float(record.payload["coordinates"][1])]
    seed = int(hashlib.sha256(f"{record.id}:{index}".encode("utf-8")).hexdigest()[:8], 16)
    lon = XIAN_CENTER[0] + (((seed % 700) - 350) / 10000)
    lat = XIAN_CENTER[1] + ((((seed // 700) % 600) - 300) / 10000)
    return [round(lon, 6), round(lat, 6)]


def _media_asset_id_for_record(record: models.RawRecord) -> str | None:
    if record.source_type not in {"media", "live_segment"} and not record.payload.get("media_type"):
        return None
    digest = hashlib.sha256(record.id.encode("utf-8")).hexdigest()[:12]
    return f"media-ref-{digest}"


def _events(session: Session, city_id: str, limit: int = 50, status: str | None = None) -> list[models.CityEvent]:
    statement = select(models.CityEvent).where(models.CityEvent.city_id == city_id)
    if status:
        statement = statement.where(models.CityEvent.status == status)
    statement = statement.order_by(models.CityEvent.heat_score.desc(), models.CityEvent.created_at.desc()).limit(limit)
    return list(session.execute(statement).scalars())


def _map_state_for_user(session: Session, city_id: str, user_id: str) -> models.CityMapState | None:
    return session.execute(
        select(models.CityMapState).where(models.CityMapState.city_id == city_id, models.CityMapState.user_id == user_id)
    ).scalar_one_or_none()


def _source_rows(session: Session) -> list[dict]:
    rows = list(session.execute(select(models.DataSource).order_by(models.DataSource.created_at.desc()).limit(50)).scalars())
    health_by_source = {
        item.data_source_id: item
        for item in session.execute(select(models.SourceHealth)).scalars()
    }
    return [
        {
            "id": source.id,
            "name": source.name,
            "source_id": source.id,
            "source_name": source.name,
            "access_mode": source.policy.get("access_mode", source.source_type),
            "source_type": source.source_type,
            "status": source.status,
            "trust": round(0.82 if source.status == "active" else 0.42, 2),
            "accepted": source.status == "active" and health_by_source.get(source.id, None) is not None,
            "blocked_reason": health_by_source[source.id].last_error_code if source.id in health_by_source else None,
            "payload": source.payload | {"synthetic": source.is_synthetic},
        }
        for source in rows
    ]


def _source_health_rows(session: Session) -> list[dict]:
    rows = list(session.execute(select(models.SourceHealth).order_by(models.SourceHealth.updated_at.desc()).limit(50)).scalars())
    return [
        {
            "id": row.id,
            "data_source_id": row.data_source_id,
            "status": row.status if row.status in {"healthy", "degraded", "unhealthy", "blocked"} else "degraded",
            "last_success_at": row.updated_at if row.success_count else None,
            "last_failure_at": row.updated_at if row.failure_count else None,
            "run_counters": {"success": row.success_count, "failure": row.failure_count, "last_run_id": row.last_run_id},
            "last_error_code": row.last_error_code,
            "payload": row.payload,
        }
        for row in rows
    ]


def _overview_metrics(events: list[models.CityEvent], sources: list[dict]) -> list[dict]:
    max_heat = max([event.heat_score for event in events] or [0])
    media_count = len([event for event in events if event.event_type == "media" or event.payload.get("media_asset_id")])
    return [
        {"label": "Event total", "value": len(events), "tone": "blue"},
        {"label": "New events", "value": len([event for event in events if event.status == "candidate"]), "tone": "green"},
        {"label": "Max heat", "value": round(max_heat, 2), "tone": "red"},
        {"label": "Media records", "value": media_count, "tone": "violet"},
        {"label": "Source count", "value": len(sources), "tone": "amber"},
    ]


def _legacy_signal(event: models.CityEvent) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "summary": event.summary,
        "priority": "P0" if event.risk_score >= 80 else "P1" if event.risk_score >= 64 else "P2",
        "region_id": event.payload.get("district", event.city_id),
        "status": event.status,
        "scores": {"onlineHeat": event.heat_score, "mainlineRisk": event.risk_score},
        "tags": event.payload.get("tags", []),
        "payload": event.payload | {"evidence_refs": event.evidence_refs, "topic_id": event.topic_id},
    }


def _map_feature(event: models.CityEvent, index: int) -> dict:
    return {
        "type": "Feature",
        "id": event.id,
        "geometry": {"type": "Point", "coordinates": _event_coordinates(event)},
        "properties": {
            "featureId": event.id,
            "regionId": event.payload.get("district", event.city_id),
            "featureType": event.event_type,
            "title": event.title,
            "displayTitle": event.title,
            "summary": event.summary,
            "mainlineId": event.topic_id,
            "riskScore": event.risk_score,
            "onlineHeat": event.heat_score,
            "confidence": min(0.98, 0.62 + index * 0.015),
            "eventCount": 1,
            "evidenceRefs": event.evidence_refs,
            "synthetic": bool(event.payload.get("synthetic")),
        },
    }


def _event_coordinates(event: models.CityEvent) -> list[float]:
    coordinates = event.payload.get("coordinates", XIAN_CENTER)
    return [float(coordinates[0]), float(coordinates[1])] if isinstance(coordinates, list) and len(coordinates) == 2 else XIAN_CENTER


def _serialize_media_asset(asset: models.MediaAsset, record: models.RawRecord) -> dict:
    return {
        "id": asset.id,
        "media_type": asset.media_type if asset.media_type != "live_segment" else "live_segment",
        "status": "completed" if asset.status in {"processed", "completed"} else asset.status,
        "is_redacted": True,
        "source_record_id": record.id,
        "storage_uri": asset.uri,
        "payload": asset.payload | {"raw_record_id": record.id, "synthetic": asset.is_synthetic},
    }


def _lineage_for_event(session: Session, event: models.CityEvent) -> list[dict]:
    rows = session.execute(
        select(models.LineageEdge).where(
            ((models.LineageEdge.from_object_type == "city_event") & (models.LineageEdge.from_object_id == event.id))
            | ((models.LineageEdge.to_object_type == "city_event") & (models.LineageEdge.to_object_id == event.id))
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


def _page_view_model(
    *,
    city: models.City,
    page_state: str,
    actor: models.User,
    trace_id: str,
    primary_data: dict,
    degraded_sources: list[dict],
) -> dict:
    return {
        "page_state": page_state,
        "permissions": {"city:read": True, "city:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {
            "source": "postgresql",
            "derived_from": "raw_records",
            "synthetic_allowed": bool(city.payload.get("synthetic_allowed")),
        },
        "degraded_sources": degraded_sources,
        "audit_context": {"object_type": "city", "object_id": city.id, "object_version": "s3a-v1", "actor_id": actor.id},
        "primary_data": primary_data,
        "actions": [
            {"id": "update-map-state", "label": "Update map state", "method": "PATCH", "href": f"/api/v1/cities/{city.id}/map-state", "enabled": True},
            {"id": "create-topic-from-event", "label": "Create topic from city event", "method": "POST", "href": "/api/v1/city-events/{city_event_id}/create-topic", "enabled": True},
        ],
        "trace_id": trace_id,
    }


def _nav(case_id: str) -> list[dict]:
    pages = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]
    return [{"page": page, "label": page, "path": f"/cases/{case_id}/{page}"} for page in pages]
