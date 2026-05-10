from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import city as city_service
from . import models, schemas
from .audit import write_audit
from .foundation import DEFAULT_TENANT_ID, api_error

DEFAULT_CASE_ID = "CASE-CAMPUS-001"
ALGORITHM_VERSION = "s4a-signal-extraction-v1"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_extraction_run(session: Session, request: schemas.ExtractionRunCreate, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_none(session, request.topic_id)
    if request.topic_id and topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")

    records = _select_raw_records(session, request, topic)
    case = _ensure_case(session, topic)
    run = models.WorkflowRun(
        id=_id("WRUN"),
        case_id=case.id,
        tenant_id=actor.tenant_id,
        workflow_name="signal_extraction_run",
        workflow_id=f"signal-extraction:{request.rule_version}",
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload={
            "topic_id": topic.id if topic else None,
            "raw_record_ids": [record.id for record in records],
            "input_count": len(records),
            "output_count": 0,
            "algorithm_version": ALGORITHM_VERSION,
            "rule_version": request.rule_version,
            "errors": [],
            "sample_outputs": [],
            "synthetic_count": len([record for record in records if record.is_synthetic]),
        },
    )
    session.add(run)
    session.flush()

    if not records:
        run.status = "failed"
        run.payload = jsonable_encoder(run.payload | {
            "error_code": "RAW_RECORD_SCOPE_EMPTY",
            "error_message": "No raw records matched signal extraction scope.",
        })
        session.add(
            models.OpsErrorQueue(
                id=_id("ERRQ"),
                source="signal_extraction_run",
                severity="warning",
                status="open",
                message="No raw records matched signal extraction scope.",
                payload={"workflow_run_id": run.id, "topic_id": request.topic_id, "error_code": "RAW_RECORD_SCOPE_EMPTY"},
            )
        )
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="signal.extraction_run.failed",
            object_type="workflow_run",
            object_id=run.id,
            after=serialize_workflow_run(run),
            trace_id=trace_id,
        )
        session.commit()
        return serialize_workflow_run(run)

    outputs: list[models.Signal] = []
    for record in records:
        signal = _upsert_signal_from_raw_record(session, case, topic, record, run.id)
        outputs.append(signal)

    run.status = "completed"
    run.payload = jsonable_encoder(run.payload | {
        "output_count": len(outputs),
        "sample_outputs": [serialize_signal(signal) for signal in outputs[:8]],
        "dedup_explanation": "Signals are keyed by topic/raw_record deterministic hash; repeated extraction updates the same signal id.",
        "aggregation_rule": "One candidate signal per selected raw record, grouped later by package/mainline stages.",
    })
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="signal.extraction_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        after=serialize_workflow_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_workflow_run(run)


def get_workbench_view(session: Session, topic_id: str, actor: models.User) -> dict:
    topic = _topic_or_404(session, topic_id)
    signals = list_signals(session, topic_id=topic_id, page_size=100)
    packages = [serialize_signal_package(session, package) for package in _packages_for_topic(session, topic_id)]
    runs = _extraction_runs_for_topic(session, topic_id)
    lineage_edges = _lineage_for_topic_signals(session, [signal["id"] for signal in signals])
    latest_run = runs[0] if runs else None
    primary = {
        "topic": city_service.serialize_topic(topic),
        "signals": signals,
        "signal_packages": packages,
        "extraction_runs": runs,
        "lineage": lineage_edges[:100],
        "lineage_summary": {
            "signal_count": len(signals),
            "package_count": len(packages),
            "lineage_edge_count": len(lineage_edges),
            "raw_record_ref_count": len({edge["from_object_id"] for edge in lineage_edges if edge["from_object_type"] == "raw_record"}),
        },
        "latest_run_status": latest_run["status"] if latest_run else "not_started",
        "algorithm_version": ALGORITHM_VERSION,
        "legacy_page_view": _legacy_signal_page(topic, signals, packages, runs, lineage_edges),
    }
    return {
        "page_state": "empty" if not signals else "ready",
        "permissions": {"signal:read": True, "signal:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "signals/lineage/workflow_runs", "algorithm_version": ALGORITHM_VERSION},
        "degraded_sources": [] if signals else [{"code": "NO_SIGNALS", "message": "No signal extraction run has produced signals for this topic."}],
        "audit_context": {"object_type": "topic", "object_id": topic.id, "object_version": ALGORITHM_VERSION, "actor_id": actor.id},
        "primary_data": primary,
        "actions": [
            {"id": "run-signal-extraction", "label": "Run signal extraction", "method": "POST", "href": "/api/v1/extraction-runs", "enabled": True},
            {"id": "create-signal-package", "label": "Create signal package", "method": "POST", "href": "/api/v1/signal-packages", "enabled": bool(signals)},
        ],
    }


def list_signals(
    session: Session,
    topic_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[dict]:
    statement = select(models.Signal).order_by(models.Signal.updated_at.desc())
    if topic_id:
        statement = statement.where(models.Signal.topic_id == topic_id)
    if status:
        statement = statement.where(models.Signal.status == status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(models.Signal.title.ilike(pattern), models.Signal.summary.ilike(pattern)))
    rows = session.execute(statement.offset(max(page - 1, 0) * page_size).limit(page_size)).scalars()
    return [serialize_signal(row) for row in rows]


def get_signal(session: Session, signal_id: str) -> dict:
    signal = _signal_or_404(session, signal_id)
    return serialize_signal(signal) | {"lineage": _lineage_for_signal(session, signal.id)}


def create_signal_package(session: Session, request: schemas.SignalPackageCreate, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_404(session, request.topic_id)
    package = models.SignalPackage(
        id=_id("SPKG"),
        tenant_id=actor.tenant_id,
        topic_id=topic.id,
        name=request.name,
        status="draft",
        rule_version=request.rule_version,
        payload=request.payload | {"algorithm_version": ALGORITHM_VERSION},
    )
    session.add(package)
    session.flush()
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="signal_package.create",
        object_type="signal_package",
        object_id=package.id,
        reason=request.reason,
        after=serialize_signal_package(session, package),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_signal_package(session, package)


def get_signal_package(session: Session, signal_package_id: str) -> dict:
    return serialize_signal_package(session, _package_or_404(session, signal_package_id))


def add_signal_package_item(session: Session, signal_package_id: str, request: schemas.SignalPackageItemWrite, actor: models.User, trace_id: str) -> dict:
    package = _package_or_404(session, signal_package_id)
    signal = _signal_or_404(session, request.signal_id)
    if signal.topic_id != package.topic_id:
        raise api_error(409, "SIGNAL_TOPIC_MISMATCH", "Signal does not belong to this signal package topic.")
    existing = session.execute(
        select(models.SignalPackageItem).where(
            models.SignalPackageItem.signal_package_id == package.id,
            models.SignalPackageItem.signal_id == signal.id,
        )
    ).scalar_one_or_none()
    before = serialize_signal_package(session, package)
    if existing is None:
        session.add(
            models.SignalPackageItem(
                id=_id("SPITEM"),
                signal_package_id=package.id,
                signal_id=signal.id,
                rank=request.rank,
                payload=request.payload | {"reason": request.reason},
            )
        )
    else:
        existing.rank = request.rank
        existing.payload = existing.payload | request.payload | {"reason": request.reason}
    session.flush()
    after = serialize_signal_package(session, package)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="signal_package.item.add",
        object_type="signal_package",
        object_id=package.id,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_signal_package(session, package)


def remove_signal_package_item(session: Session, signal_package_id: str, signal_id: str, actor: models.User, trace_id: str) -> dict:
    package = _package_or_404(session, signal_package_id)
    _signal_or_404(session, signal_id)
    before = serialize_signal_package(session, package)
    item = session.execute(
        select(models.SignalPackageItem).where(
            models.SignalPackageItem.signal_package_id == package.id,
            models.SignalPackageItem.signal_id == signal_id,
        )
    ).scalar_one_or_none()
    if item is not None:
        session.delete(item)
        session.flush()
    after = serialize_signal_package(session, package)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="signal_package.item.remove",
        object_type="signal_package",
        object_id=package.id,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_signal_package(session, package)


def serialize_workflow_run(run: models.WorkflowRun) -> dict:
    return {
        "workflow_run_id": run.id,
        "id": run.id,
        "case_id": run.case_id,
        "tenant_id": run.tenant_id,
        "workflow_name": run.workflow_name,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "started_by": run.started_by,
        "trace_id": run.trace_id,
        "payload": jsonable_encoder(run.payload),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def serialize_signal(signal: models.Signal) -> dict:
    return {
        "id": signal.id,
        "case_id": signal.case_id,
        "topic_id": signal.topic_id,
        "mainline_id": signal.mainline_id,
        "title": signal.title,
        "summary": signal.summary,
        "priority": signal.priority,
        "region_id": signal.region_id,
        "status": signal.status,
        "scores": signal.scores,
        "payload": signal.payload,
        "created_at": signal.created_at,
        "updated_at": signal.updated_at,
    }


def serialize_signal_package(session: Session, package: models.SignalPackage) -> dict:
    items = list(
        session.execute(
            select(models.SignalPackageItem)
            .where(models.SignalPackageItem.signal_package_id == package.id)
            .order_by(models.SignalPackageItem.rank, models.SignalPackageItem.created_at)
        ).scalars()
    )
    return {
        "signal_package_id": package.id,
        "id": package.id,
        "tenant_id": package.tenant_id,
        "topic_id": package.topic_id,
        "name": package.name,
        "status": package.status,
        "rule_version": package.rule_version,
        "payload": package.payload,
        "items": [
            {
                "signal_package_item_id": item.id,
                "signal_id": item.signal_id,
                "rank": item.rank,
                "payload": item.payload,
                "created_at": item.created_at,
                "signal": serialize_signal(session.get(models.Signal, item.signal_id)),
            }
            for item in items
            if session.get(models.Signal, item.signal_id) is not None
        ],
        "created_at": package.created_at,
        "updated_at": package.updated_at,
    }


def _select_raw_records(session: Session, request: schemas.ExtractionRunCreate, topic: models.Topic | None) -> list[models.RawRecord]:
    if request.raw_record_ids:
        records = list(
            session.execute(
                select(models.RawRecord)
                .where(models.RawRecord.id.in_(request.raw_record_ids))
                .order_by(models.RawRecord.created_at.desc())
                .limit(request.limit)
            ).scalars()
        )
        return [record for record in records if _raw_record_signal_generation_allowed(record)]
    if topic is not None:
        events = list(
            session.execute(
                select(models.CityEvent)
                .where(models.CityEvent.city_id == topic.city_id)
                .order_by(models.CityEvent.heat_score.desc(), models.CityEvent.created_at.desc())
                .limit(request.limit)
            ).scalars()
        )
        raw_ids = [event.raw_record_id for event in events if event.raw_record_id]
        if raw_ids:
            records = list(
                session.execute(
                    select(models.RawRecord)
                    .where(models.RawRecord.id.in_(raw_ids))
                    .order_by(models.RawRecord.created_at.desc())
                    .limit(request.limit)
                ).scalars()
            )
            return [record for record in records if _raw_record_signal_generation_allowed(record)]
        statement = select(models.RawRecord).where(models.RawRecord.city_id == topic.city_id).order_by(models.RawRecord.created_at.desc()).limit(request.limit)
        return [record for record in session.execute(statement).scalars() if _raw_record_signal_generation_allowed(record)]
    statement = select(models.RawRecord).order_by(models.RawRecord.created_at.desc()).limit(request.limit)
    return [record for record in session.execute(statement).scalars() if _raw_record_signal_generation_allowed(record)]


def _raw_record_signal_generation_allowed(record: models.RawRecord) -> bool:
    payload = record.payload if isinstance(record.payload, dict) else {}
    clean_status = payload.get("clean_record_status") if isinstance(payload.get("clean_record_status"), dict) else {}
    return clean_status.get("status") not in {"invalid", "review_required"}


def _upsert_signal_from_raw_record(
    session: Session,
    case: models.Case,
    topic: models.Topic | None,
    record: models.RawRecord,
    run_id: str,
) -> models.Signal:
    payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
    content = payload.masked_text if payload else record.title
    evidence_refs = [_raw_evidence_ref(record)]
    signal_id = _signal_id(topic.id if topic else "untopic", record.id)
    scores = _scores_for(record, content)
    signal_payload = {
        "algorithm_version": ALGORITHM_VERSION,
        "extraction_run_id": run_id,
        "input_refs": evidence_refs,
        "evidence_refs": evidence_refs,
        "sentiment": _sentiment_for(content, scores),
        "appeal_tags": _appeal_tags(record, content),
        "spread_features": _spread_features(record, content),
        "locality": {"city_id": record.city_id, "local_share": scores["localShare"], "basis": "raw_record.city_id and Xi'an source scope"},
        "credibility_inputs": {"source_type": record.source_type, "synthetic": record.is_synthetic, "source_trust": scores["sourceTrust"]},
        "dedup_key": record.content_hash,
        "synthetic": record.is_synthetic,
        "blocked_claims": ["extracted signal is a candidate interpretation and not a factual finding until evidence review"],
    }
    signal = session.get(models.Signal, signal_id)
    if signal is None:
        signal = models.Signal(
            id=signal_id,
            case_id=case.id,
            topic_id=topic.id if topic else None,
            mainline_id=None,
            title=record.title,
            summary=_summary(content),
            priority=_priority(scores),
            region_id=record.city_id or "unknown",
            status="candidate",
            scores=scores,
            payload=signal_payload,
        )
        session.add(signal)
        session.flush()
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="raw_record",
                from_object_id=record.id,
                to_object_type="signal",
                to_object_id=signal.id,
                relation="extracted_signal",
                is_synthetic=record.is_synthetic,
                payload={"workflow_run_id": run_id, "algorithm_version": ALGORITHM_VERSION, "evidence_refs": evidence_refs},
            )
        )
    else:
        signal.case_id = case.id
        signal.topic_id = topic.id if topic else signal.topic_id
        signal.title = record.title
        signal.summary = _summary(content)
        signal.priority = _priority(scores)
        signal.region_id = record.city_id or signal.region_id
        signal.scores = scores
        signal.payload = signal.payload | signal_payload
    return signal


def _ensure_case(session: Session, topic: models.Topic | None) -> models.Case:
    case = session.get(models.Case, DEFAULT_CASE_ID)
    if case is not None:
        return case
    case = models.Case(
        id=DEFAULT_CASE_ID,
        slug="xian-social-signal-workbench",
        title="Xi'an Social Signal Workbench",
        scenario_type="xian_social_issue_signal_extraction",
        status="active",
        payload={
            "source": "s4a_signal_extraction",
            "city_id": topic.city_id if topic else "xian",
            "synthetic": bool(topic.payload.get("synthetic")) if topic else False,
            "evidence_refs": topic.payload.get("evidence_refs", []) if topic else [],
        },
    )
    session.add(case)
    session.flush()
    return case


def _topic_or_none(session: Session, topic_id: str | None) -> models.Topic | None:
    return session.get(models.Topic, topic_id) if topic_id else None


def _topic_or_404(session: Session, topic_id: str) -> models.Topic:
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    return topic


def _signal_or_404(session: Session, signal_id: str) -> models.Signal:
    signal = session.get(models.Signal, signal_id)
    if signal is None:
        raise api_error(404, "SIGNAL_NOT_FOUND", "Signal not found.")
    return signal


def _package_or_404(session: Session, signal_package_id: str) -> models.SignalPackage:
    package = session.get(models.SignalPackage, signal_package_id)
    if package is None:
        raise api_error(404, "SIGNAL_PACKAGE_NOT_FOUND", "Signal package not found.")
    return package


def _packages_for_topic(session: Session, topic_id: str) -> list[models.SignalPackage]:
    return list(
        session.execute(
            select(models.SignalPackage).where(models.SignalPackage.topic_id == topic_id).order_by(models.SignalPackage.updated_at.desc())
        ).scalars()
    )


def _extraction_runs_for_topic(session: Session, topic_id: str, limit: int = 20) -> list[dict]:
    rows = session.execute(
        select(models.WorkflowRun)
        .where(models.WorkflowRun.workflow_name == "signal_extraction_run")
        .order_by(models.WorkflowRun.updated_at.desc())
        .limit(limit)
    ).scalars()
    return [serialize_workflow_run(row) for row in rows if row.payload.get("topic_id") == topic_id]


def _lineage_for_signal(session: Session, signal_id: str) -> list[dict]:
    rows = session.execute(
        select(models.LineageEdge)
        .where(
            ((models.LineageEdge.from_object_type == "signal") & (models.LineageEdge.from_object_id == signal_id))
            | ((models.LineageEdge.to_object_type == "signal") & (models.LineageEdge.to_object_id == signal_id))
        )
        .order_by(models.LineageEdge.created_at.desc())
    ).scalars()
    return [_serialize_lineage(row) for row in rows]


def _lineage_for_topic_signals(session: Session, signal_ids: list[str]) -> list[dict]:
    if not signal_ids:
        return []
    rows = session.execute(
        select(models.LineageEdge)
        .where(
            ((models.LineageEdge.from_object_type == "signal") & (models.LineageEdge.from_object_id.in_(signal_ids)))
            | ((models.LineageEdge.to_object_type == "signal") & (models.LineageEdge.to_object_id.in_(signal_ids)))
        )
        .order_by(models.LineageEdge.created_at.desc())
    ).scalars()
    return [_serialize_lineage(row) for row in rows]


def _serialize_lineage(edge: models.LineageEdge) -> dict:
    return {
        "lineage_edge_id": edge.id,
        "from_object_type": edge.from_object_type,
        "from_object_id": edge.from_object_id,
        "to_object_type": edge.to_object_type,
        "to_object_id": edge.to_object_id,
        "relation": edge.relation,
        "is_synthetic": edge.is_synthetic,
        "payload": edge.payload,
        "created_at": edge.created_at,
    }


def _legacy_signal_page(topic: models.Topic, signal_rows: list[dict], packages: list[dict], runs: list[dict], lineage: list[dict]) -> dict:
    return {
        "case_id": DEFAULT_CASE_ID,
        "page": "data",
        "title": "Data / Signal Workbench",
        "subtitle": topic.title,
        "nav": _nav(DEFAULT_CASE_ID),
        "metrics": [
            {"label": "Candidate signals", "value": len(signal_rows), "tone": "blue"},
            {"label": "Signal packages", "value": len(packages), "tone": "green"},
            {"label": "Extraction runs", "value": len(runs), "tone": "amber"},
            {"label": "Lineage edges", "value": len(lineage), "tone": "violet"},
        ],
        "sections": [
            {"id": "signals", "title": "Signal search results", "kind": "signal-table", "items": signal_rows},
            {"id": "packages", "title": "Signal packages", "kind": "packages", "items": packages},
            {"id": "runs", "title": "Extraction runs", "kind": "timeline", "items": [run["workflow_run_id"] + ":" + run["status"] for run in runs]},
            {"id": "lineage", "title": "Input lineage", "kind": "chips", "items": [edge["from_object_id"] + " -> " + edge["to_object_id"] for edge in lineage[:30]]},
        ],
        "actions": [{"id": "enter-evidence", "label": "Enter evidence review", "to_page": "evidence"}],
        "raw": {"topic_id": topic.id, "algorithm_version": ALGORITHM_VERSION},
    }


def _nav(case_id: str) -> list[dict]:
    pages = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]
    return [{"page": page, "label": page, "path": f"/cases/{case_id}/{page}"} for page in pages]


def _signal_id(topic_id: str, raw_record_id: str) -> str:
    digest = hashlib.sha256(f"{topic_id}:{raw_record_id}:{ALGORITHM_VERSION}".encode("utf-8")).hexdigest()[:20]
    return f"SIG-{digest}"


def _raw_evidence_ref(record: models.RawRecord) -> dict:
    return {
        "object_type": "raw_record",
        "object_id": record.id,
        "object_version": record.content_hash,
        "confidence": 0.78 if record.is_synthetic else 0.66,
        "synthetic": record.is_synthetic,
    }


def _scores_for(record: models.RawRecord, content: str) -> dict:
    seed = int(hashlib.sha256(f"{record.id}:{record.content_hash}".encode("utf-8")).hexdigest()[:8], 16)
    urgent = _contains(content, ["question", "request", "asks", "争议", "咨询", "反馈", "热线", "投诉"])
    media_boost = 7 if record.source_type in {"media", "live_segment"} or record.payload.get("media_type") else 0
    online_heat = min(98.0, 48 + seed % 34 + media_boost + (5 if urgent else 0))
    mainline_risk = min(96.0, 40 + (seed // 19) % 36 + (6 if "minor" in content.lower() else 0) + (4 if urgent else 0))
    source_trust = 0.78 if record.is_synthetic else 0.64
    cross_support = 0.12 if record.payload.get("tags") else 0.04
    credibility = min(0.94, source_trust + cross_support)
    return {
        "onlineHeat": round(online_heat, 2),
        "mainlineRisk": round(mainline_risk, 2),
        "sentimentConfidence": round(min(0.95, 0.55 + mainline_risk / 220), 4),
        "appealConfidence": round(0.72 if urgent else 0.58, 4),
        "spreadSpeed": round(min(0.96, 0.42 + online_heat / 180 + media_boost / 100), 4),
        "localShare": 0.92 if record.city_id == "xian" else 0.45,
        "sourceTrust": source_trust,
        "credibility": round(credibility, 4),
    }


def _priority(scores: dict) -> str:
    if scores["mainlineRisk"] >= 76 or scores["onlineHeat"] >= 84:
        return "P0"
    if scores["mainlineRisk"] >= 62:
        return "P1"
    if scores["onlineHeat"] >= 60:
        return "P2"
    return "P3"


def _sentiment_for(content: str, scores: dict) -> dict:
    if scores["mainlineRisk"] >= 72:
        label = "negative_or_urgent"
    elif _contains(content, ["ask", "request", "咨询", "反馈"]):
        label = "requesting_clarification"
    else:
        label = "watching"
    return {"label": label, "confidence": scores["sentimentConfidence"]}


def _appeal_tags(record: models.RawRecord, content: str) -> list[dict]:
    tags = []
    if _contains(content, ["timeline", "time", "窗口", "时间", "排队"]):
        tags.append("timeline_or_response_window")
    if _contains(content, ["ledger", "fee", "basis", "compensation", "charge", "account"]):
        tags.append("explanation_or_ledger")
    if _contains(content, ["minor", "school", "学生", "学校"]):
        tags.append("minor_or_school_safety")
    if not tags:
        tags = [str(item) for item in record.payload.get("tags", [])[:3]] or ["general_public_service"]
    return [{"tag": tag, "confidence": 0.74, "evidence_refs": [_raw_evidence_ref(record)]} for tag in tags[:4]]


def _spread_features(record: models.RawRecord, content: str) -> dict:
    channel = str(record.payload.get("channel") or record.payload.get("import_type") or record.source_type)
    tokens = len(re.findall(r"\w+", content))
    return {
        "source_type": record.source_type,
        "channel": channel,
        "token_count": tokens,
        "path": [channel, "raw_record", "signal"],
        "confidence": 0.71 if record.is_synthetic else 0.58,
    }


def _summary(content: str) -> str:
    cleaned = re.sub(r"\s+", " ", content).strip()
    return cleaned[:260] if cleaned else "Signal extracted from raw record."


def _contains(content: str, words: list[str]) -> bool:
    lower = content.lower()
    return any(word.lower() in lower for word in words)
