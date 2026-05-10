from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import city as city_service
from . import models, schemas
from .audit import write_audit
from .foundation import api_error
from .policy import mask_sensitive_text

ALGORITHM_VERSION = "s4b-evidence-review-v1"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_evidence_candidates(session: Session, request: schemas.EvidenceCandidateCreate, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_none(session, request.topic_id)
    if request.topic_id and topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    signals = _select_signals(session, request, topic)
    if request.signal_ids and len(signals) != len(set(request.signal_ids)):
        raise api_error(404, "SIGNAL_NOT_FOUND", "One or more signals were not found.")
    case = _case_for_signals(session, signals)
    run = _workflow_run(
        actor,
        case.id,
        "evidence_candidate_generation",
        f"evidence-candidates:{request.rule_version}",
        trace_id,
        {
            "topic_id": topic.id if topic else None,
            "signal_ids": [signal.id for signal in signals],
            "input_count": len(signals),
            "output_count": 0,
            "algorithm_version": ALGORITHM_VERSION,
            "rule_version": request.rule_version,
            "errors": [],
        },
    )
    session.add(run)
    session.flush()

    if not signals:
        run.status = "failed"
        run.payload = run.payload | {"error_code": "SIGNAL_SCOPE_EMPTY", "error_message": "No signals matched evidence candidate scope."}
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            case_id=case.id,
            actor=actor.username,
            actor_id=actor.id,
            action="evidence_candidate.failed",
            object_type="workflow_run",
            object_id=run.id,
            after=serialize_workflow_run(run),
            trace_id=trace_id,
        )
        session.commit()
        return {"run": serialize_workflow_run(run), "evidence": [], "reviews": []}

    evidence_rows: list[models.Evidence] = []
    review_rows: list[models.EvidenceReview] = []
    for signal in signals:
        evidence = _upsert_evidence_from_signal(session, signal, topic, run.id)
        review = _ensure_evidence_review(session, evidence, signal, topic, actor)
        evidence_rows.append(evidence)
        review_rows.append(review)

    run.status = "completed"
    run.payload = jsonable_encoder(run.payload | {"output_count": len(evidence_rows), "evidence_ids": [row.id for row in evidence_rows]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=case.id,
        actor=actor.username,
        actor_id=actor.id,
        action="evidence_candidate.create",
        object_type="workflow_run",
        object_id=run.id,
        after=serialize_workflow_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return {
        "run": serialize_workflow_run(run),
        "evidence": [serialize_evidence(row) for row in evidence_rows],
        "reviews": [serialize_evidence_review(session, row) for row in review_rows],
    }


def list_evidence(session: Session, topic_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 50) -> list[dict]:
    statement = select(models.Evidence).order_by(models.Evidence.updated_at.desc())
    if status:
        statement = statement.where(models.Evidence.status == status)
    rows = list(session.execute(statement.offset(max(page - 1, 0) * page_size).limit(page_size)).scalars())
    if topic_id:
        rows = [row for row in rows if row.payload.get("topic_id") == topic_id]
    return [serialize_evidence(row) for row in rows]


def get_evidence_detail(session: Session, evidence_id: str) -> dict:
    evidence = _evidence_or_404(session, evidence_id)
    return serialize_evidence(evidence) | {
        "review": _review_for_evidence(session, evidence.id, serialized=True),
        "media_links": media_links_for_evidence(session, evidence.id),
        "media_processing_runs": _media_runs_for_evidence(session, evidence.id),
        "lineage": _lineage_for_evidence(session, evidence.id),
    }


def update_evidence_review(session: Session, review_id: str, request: schemas.EvidenceReviewPatch, actor: models.User, trace_id: str) -> dict:
    review = _review_or_404(session, review_id)
    evidence = _evidence_or_404(session, review.evidence_id)
    before = serialize_evidence_review(session, review)
    status_map = {
        "confirmed": "confirmed_fact",
        "rejected": "rejected",
        "probability_reference_only": "probability_reference_only",
        "needs_review": "needs_review",
    }
    review.status = request.status
    review.decision = request.status
    review.reviewer_id = actor.id
    review.payload = jsonable_encoder(review.payload | {"reason": request.reason, "payload": request.payload, "reviewed_at": utcnow()})
    evidence.status = status_map[request.status]
    evidence.payload = jsonable_encoder(evidence.payload | {"review_status": request.status, "review_reason": request.reason, "reviewed_by": actor.id})
    after = serialize_evidence_review(session, review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=review.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="evidence_review.update",
        object_type="evidence_review",
        object_id=review.id,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_evidence_review(session, review) | {"evidence": serialize_evidence(evidence)}


def create_evidence_attachment(session: Session, evidence_id: str, request: schemas.EvidenceAttachmentCreate, actor: models.User, trace_id: str) -> dict:
    evidence = _evidence_or_404(session, evidence_id)
    raw_record_id = _raw_record_id_for_evidence(evidence)
    if raw_record_id is None:
        raise api_error(409, "RAW_RECORD_REF_REQUIRED", "Evidence attachment requires a raw_record input reference.")
    media = models.MediaAsset(
        id=_id("MED"),
        raw_record_id=raw_record_id,
        media_type=request.media_type,
        uri=request.uri,
        status="uploaded",
        is_synthetic=request.is_synthetic or bool(evidence.payload.get("synthetic")),
        payload=jsonable_encoder(request.payload | {"content": request.content, "masked_text": mask_sensitive_text(request.content), "evidence_id": evidence.id}),
    )
    session.add(media)
    session.flush()
    link = _upsert_media_link(session, evidence, media, "attachment", actor.tenant_id, request.payload)
    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="media_asset",
            from_object_id=media.id,
            to_object_type="evidence",
            to_object_id=evidence.id,
            relation="attached_media",
            is_synthetic=media.is_synthetic,
            payload={"trace_id": trace_id, "evidence_refs": evidence.payload.get("evidence_refs", [])},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=evidence.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="evidence_attachment.create",
        object_type="evidence",
        object_id=evidence.id,
        after={"media_asset": serialize_media_asset(media), "link": serialize_media_link(link)},
        trace_id=trace_id,
    )
    session.commit()
    return {"media_asset": serialize_media_asset(media), "link": serialize_media_link(link)}


def create_media_processing_run(session: Session, request: schemas.MediaProcessingRunCreate, actor: models.User, trace_id: str) -> dict:
    media = _media_or_404(session, request.media_asset_id)
    evidence = _evidence_or_404(session, request.evidence_id) if request.evidence_id else _evidence_for_media(session, media.id)
    output = _media_output(media, evidence, request.processor, request.rule_version)
    run = models.MediaProcessingRun(
        id=_id("MPR"),
        media_asset_id=media.id,
        processor=f"{request.processor}:{request.rule_version}",
        status="completed",
        output=jsonable_encoder(output),
        trace_id=trace_id,
    )
    media.status = "processed"
    media.payload = jsonable_encoder(media.payload | {"latest_processor": request.processor, "latest_processing_run_id": run.id})
    session.add(run)
    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="media_asset",
            from_object_id=media.id,
            to_object_type="media_processing_run",
            to_object_id=run.id,
            relation=request.processor,
            is_synthetic=media.is_synthetic,
            payload={"evidence_id": evidence.id if evidence else None, "blocked_claims": output["blocked_claims"]},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=evidence.case_id if evidence else None,
        actor=actor.username,
        actor_id=actor.id,
        action="media_processing_run.create",
        object_type="media_processing_run",
        object_id=run.id,
        after=serialize_media_processing_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_media_processing_run(run)


def create_evidence_media_link(session: Session, request: schemas.EvidenceMediaLinkWrite, actor: models.User, trace_id: str) -> dict:
    evidence = _evidence_or_404(session, request.evidence_id)
    media = _media_or_404(session, request.media_asset_id)
    link = _upsert_media_link(session, evidence, media, request.relation, actor.tenant_id, request.payload)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=evidence.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="evidence_media_link.create",
        object_type="evidence_media_link",
        object_id=link.id,
        after=serialize_media_link(link),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_media_link(link)


def create_redaction_run(session: Session, request: schemas.RunCreate, actor: models.User, trace_id: str) -> dict:
    if request.object_type != "evidence":
        raise api_error(422, "UNSUPPORTED_REDACTION_OBJECT", "Only evidence redaction is supported in S4B.")
    evidence = _evidence_or_404(session, request.object_id)
    before = serialize_evidence(evidence)
    evidence.masked_excerpt = mask_sensitive_text(evidence.excerpt)
    evidence.payload = jsonable_encoder(evidence.payload | {"redaction_applied": True, "redaction_scope": request.input_scope, "redaction_version": ALGORITHM_VERSION})
    run = _workflow_run(
        actor,
        evidence.case_id,
        "evidence_redaction_run",
        f"redaction:{ALGORITHM_VERSION}",
        trace_id,
        {
            "object_type": request.object_type,
            "object_id": request.object_id,
            "input_scope": request.input_scope,
            "redaction_applied": True,
            "algorithm_version": ALGORITHM_VERSION,
        },
    )
    run.status = "completed"
    session.add(run)
    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="evidence",
            from_object_id=evidence.id,
            to_object_type="workflow_run",
            to_object_id=run.id,
            relation="redacted",
            is_synthetic=bool(evidence.payload.get("synthetic")),
            payload={"masked": True},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=evidence.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="redaction_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        before=before,
        after=serialize_evidence(evidence),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_workflow_run(run)


def review_view(session: Session, review_id: str, actor: models.User) -> dict:
    review = _review_or_404(session, review_id)
    evidence = _evidence_or_404(session, review.evidence_id)
    media_links = media_links_for_evidence(session, evidence.id)
    risk_factors = list_risk_factors(session, topic_id=review.topic_id, page_size=50)
    media_runs = _media_runs_for_evidence(session, evidence.id)
    conflicts = evidence.payload.get("conflicts", [])
    primary = {
        "review": serialize_evidence_review(session, review),
        "evidence": serialize_evidence(evidence),
        "media_links": media_links,
        "media_processing_runs": media_runs,
        "risk_factors": risk_factors,
        "conflicts": conflicts,
        "lineage": _lineage_for_evidence(session, evidence.id),
        "legacy_page_view": _legacy_evidence_page(evidence, review, media_links, media_runs, risk_factors, conflicts),
    }
    return {
        "page_state": "ready",
        "permissions": {"evidence:read": True, "evidence:review": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "evidence/evidence_reviews/media/risk_factors"},
        "degraded_sources": [],
        "audit_context": {"object_type": "evidence_review", "object_id": review.id, "object_version": ALGORITHM_VERSION, "actor_id": actor.id},
        "primary_data": primary,
        "actions": [
            {"id": "confirm-evidence", "label": "Confirm evidence material", "method": "PATCH", "href": f"/api/v1/evidence-reviews/{review.id}", "enabled": True},
            {"id": "run-risk-factor", "label": "Generate risk factors", "method": "POST", "href": "/api/v1/risk-factor-runs", "enabled": evidence.status == "confirmed_fact"},
        ],
    }


def create_risk_factor_run(session: Session, request: schemas.RiskFactorRunCreate, actor: models.User, trace_id: str) -> dict:
    evidence_rows = _select_evidence_for_risk(session, request)
    if request.topic_id and _topic_or_none(session, request.topic_id) is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    case = _case_for_evidence(evidence_rows)
    run = _workflow_run(
        actor,
        case.id,
        "risk_factor_generation",
        f"risk-factors:{request.rule_version}",
        trace_id,
        {"topic_id": request.topic_id, "evidence_ids": [row.id for row in evidence_rows], "input_count": len(evidence_rows), "output_count": 0, "algorithm_version": ALGORITHM_VERSION},
    )
    session.add(run)
    session.flush()
    factors = [_upsert_risk_factor_from_evidence(session, evidence, request.rule_version, run.id) for evidence in evidence_rows]
    run.status = "completed"
    run.payload = jsonable_encoder(run.payload | {"output_count": len(factors), "risk_factor_ids": [factor.id for factor in factors]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=case.id,
        actor=actor.username,
        actor_id=actor.id,
        action="risk_factor_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        after=serialize_workflow_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return {"run": serialize_workflow_run(run), "risk_factors": [serialize_risk_factor(row) for row in factors]}


def list_risk_factors(session: Session, topic_id: str | None = None, status: str | None = None, category: str | None = None, page: int = 1, page_size: int = 50) -> list[dict]:
    statement = select(models.RiskFactor).order_by(models.RiskFactor.updated_at.desc())
    if status:
        statement = statement.where(models.RiskFactor.status == status)
    if category:
        statement = statement.where(models.RiskFactor.category == category)
    rows = list(session.execute(statement.offset(max(page - 1, 0) * page_size).limit(page_size)).scalars())
    if topic_id:
        rows = [row for row in rows if row.payload.get("topic_id") == topic_id]
    return [serialize_risk_factor(row) for row in rows]


def update_risk_factor(session: Session, risk_factor_id: str, request: schemas.RiskFactorUpdate, actor: models.User, trace_id: str) -> dict:
    factor = _risk_factor_or_404(session, risk_factor_id)
    before = serialize_risk_factor(factor)
    factor.status = request.status
    factor.payload = jsonable_encoder(factor.payload | {"status_reason": request.reason, "status_actor": actor.id})
    after = serialize_risk_factor(factor)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=factor.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="risk_factor.update",
        object_type="risk_factor",
        object_id=factor.id,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_risk_factor(factor)


def adjust_risk_factor_confidence(session: Session, risk_factor_id: str, request: schemas.RiskFactorConfidenceAdjustment, actor: models.User, trace_id: str) -> dict:
    factor = _risk_factor_or_404(session, risk_factor_id)
    before = serialize_risk_factor(factor)
    factor.confidence = max(0.0, min(1.0, factor.confidence + request.delta))
    adjustments = list(factor.payload.get("confidence_adjustments", []))
    adjustments.append({"delta": request.delta, "reason": request.reason, "input_refs": request.input_refs, "actor_id": actor.id, "trace_id": trace_id})
    factor.payload = jsonable_encoder(factor.payload | {"confidence_adjustments": adjustments})
    after = serialize_risk_factor(factor)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=factor.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="risk_factor.confidence_adjust",
        object_type="risk_factor",
        object_id=factor.id,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_risk_factor(factor)


def create_conflict_detection_run(session: Session, request: schemas.ConflictDetectionRunCreate, actor: models.User, trace_id: str) -> dict:
    evidence_rows = _select_evidence_for_risk(session, schemas.RiskFactorRunCreate(topic_id=request.topic_id, evidence_ids=request.evidence_ids, rule_version=request.rule_version, payload=request.payload))
    if request.topic_id and _topic_or_none(session, request.topic_id) is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    case = _case_for_evidence(evidence_rows)
    conflicts = [_conflict_for_evidence(evidence) for evidence in evidence_rows] or [{"severity": "none", "message": "No evidence available for conflict detection.", "evidence_refs": []}]
    run = _workflow_run(
        actor,
        case.id,
        "conflict_detection_run",
        f"conflict-detection:{request.rule_version}",
        trace_id,
        {"topic_id": request.topic_id, "evidence_ids": [row.id for row in evidence_rows], "conflicts": conflicts, "algorithm_version": ALGORITHM_VERSION},
    )
    run.status = "completed"
    session.add(run)
    for evidence in evidence_rows:
        evidence.payload = jsonable_encoder(evidence.payload | {"conflicts": conflicts, "conflict_detection_run_id": run.id})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=case.id,
        actor=actor.username,
        actor_id=actor.id,
        action="conflict_detection_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        after=serialize_workflow_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return {"run": serialize_workflow_run(run), "conflicts": conflicts}


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


def serialize_evidence(evidence: models.Evidence) -> dict:
    return {
        "id": evidence.id,
        "case_id": evidence.case_id,
        "signal_id": evidence.signal_id,
        "title": evidence.title,
        "excerpt": evidence.excerpt,
        "masked_excerpt": evidence.masked_excerpt,
        "source": evidence.source,
        "credibility": evidence.credibility,
        "status": evidence.status,
        "sensitivity": evidence.sensitivity,
        "payload": evidence.payload,
        "created_at": evidence.created_at,
        "updated_at": evidence.updated_at,
    }


def serialize_evidence_review(session: Session, review: models.EvidenceReview) -> dict:
    return {
        "evidence_review_id": review.id,
        "id": review.id,
        "tenant_id": review.tenant_id,
        "case_id": review.case_id,
        "topic_id": review.topic_id,
        "evidence_id": review.evidence_id,
        "signal_id": review.signal_id,
        "status": review.status,
        "reviewer_id": review.reviewer_id,
        "decision": review.decision,
        "payload": review.payload,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def serialize_media_asset(media: models.MediaAsset) -> dict:
    return {
        "id": media.id,
        "media_asset_id": media.id,
        "raw_record_id": media.raw_record_id,
        "media_type": media.media_type,
        "uri": media.uri,
        "status": media.status,
        "is_synthetic": media.is_synthetic,
        "payload": media.payload,
        "created_at": media.created_at,
        "updated_at": media.updated_at,
    }


def serialize_media_processing_run(run: models.MediaProcessingRun) -> dict:
    return {
        "media_processing_run_id": run.id,
        "id": run.id,
        "media_asset_id": run.media_asset_id,
        "processor": run.processor,
        "status": run.status,
        "output": run.output,
        "trace_id": run.trace_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def serialize_media_link(link: models.EvidenceMediaLink) -> dict:
    return {
        "evidence_media_link_id": link.id,
        "id": link.id,
        "tenant_id": link.tenant_id,
        "evidence_id": link.evidence_id,
        "media_asset_id": link.media_asset_id,
        "relation": link.relation,
        "status": link.status,
        "payload": link.payload,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def serialize_risk_factor(factor: models.RiskFactor) -> dict:
    return {
        "id": factor.id,
        "case_id": factor.case_id,
        "name": factor.name,
        "category": factor.category,
        "confidence": factor.confidence,
        "status": factor.status,
        "payload": factor.payload,
        "created_at": factor.created_at,
        "updated_at": factor.updated_at,
    }


def media_links_for_evidence(session: Session, evidence_id: str) -> list[dict]:
    rows = session.execute(
        select(models.EvidenceMediaLink).where(models.EvidenceMediaLink.evidence_id == evidence_id).order_by(models.EvidenceMediaLink.created_at.desc())
    ).scalars()
    return [serialize_media_link(row) | {"media_asset": serialize_media_asset(session.get(models.MediaAsset, row.media_asset_id))} for row in rows if session.get(models.MediaAsset, row.media_asset_id)]


def _workflow_run(actor: models.User, case_id: str, name: str, workflow_id: str, trace_id: str, payload: dict) -> models.WorkflowRun:
    return models.WorkflowRun(
        id=_id("WRUN"),
        case_id=case_id,
        tenant_id=actor.tenant_id,
        workflow_name=name,
        workflow_id=workflow_id,
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload=jsonable_encoder(payload),
    )


def _upsert_evidence_from_signal(session: Session, signal: models.Signal, topic: models.Topic | None, run_id: str) -> models.Evidence:
    evidence_id = _stable_id("EVD", signal.id, ALGORITHM_VERSION)
    evidence_refs = _evidence_refs_for_signal(signal)
    excerpt = signal.summary or signal.title
    payload = {
        "topic_id": signal.topic_id or (topic.id if topic else None),
        "input_refs": [{"object_type": "signal", "object_id": signal.id, "object_version": signal.payload.get("algorithm_version", "unknown")}],
        "evidence_refs": evidence_refs,
        "source_refs": signal.payload.get("input_refs", []),
        "algorithm_version": ALGORITHM_VERSION,
        "candidate_run_id": run_id,
        "synthetic": bool(signal.payload.get("synthetic")),
        "blocked_claims": ["candidate evidence is review material and not a reportable fact until confirmed"],
    }
    evidence = session.get(models.Evidence, evidence_id)
    if evidence is None:
        evidence = models.Evidence(
            id=evidence_id,
            case_id=signal.case_id,
            signal_id=signal.id,
            title=f"Evidence candidate: {signal.title}",
            excerpt=excerpt,
            masked_excerpt=mask_sensitive_text(excerpt),
            source="signal_extraction",
            credibility=_credibility_label(signal),
            status="candidate",
            sensitivity="normal" if not _sensitive_signal(signal) else "sensitive_person_minor",
            payload=payload,
        )
        session.add(evidence)
        session.flush()
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="signal",
                from_object_id=signal.id,
                to_object_type="evidence",
                to_object_id=evidence.id,
                relation="generated_evidence_candidate",
                is_synthetic=bool(signal.payload.get("synthetic")),
                payload={"workflow_run_id": run_id, "evidence_refs": evidence_refs, "algorithm_version": ALGORITHM_VERSION},
            )
        )
    else:
        evidence.title = f"Evidence candidate: {signal.title}"
        evidence.excerpt = excerpt
        evidence.masked_excerpt = mask_sensitive_text(excerpt)
        evidence.payload = jsonable_encoder(evidence.payload | payload)
    return evidence


def _ensure_evidence_review(session: Session, evidence: models.Evidence, signal: models.Signal, topic: models.Topic | None, actor: models.User) -> models.EvidenceReview:
    existing = session.execute(select(models.EvidenceReview).where(models.EvidenceReview.evidence_id == evidence.id)).scalar_one_or_none()
    if existing is not None:
        return existing
    review = models.EvidenceReview(
        id=_stable_id("ER", evidence.id, ALGORITHM_VERSION),
        tenant_id=actor.tenant_id,
        case_id=evidence.case_id,
        topic_id=signal.topic_id or (topic.id if topic else None),
        evidence_id=evidence.id,
        signal_id=signal.id,
        status="pending",
        reviewer_id=None,
        decision=None,
        payload={"algorithm_version": ALGORITHM_VERSION, "blocked_claims": evidence.payload.get("blocked_claims", [])},
    )
    session.add(review)
    session.flush()
    return review


def _upsert_media_link(session: Session, evidence: models.Evidence, media: models.MediaAsset, relation: str, tenant_id: str, payload: dict) -> models.EvidenceMediaLink:
    existing = session.execute(
        select(models.EvidenceMediaLink).where(
            models.EvidenceMediaLink.evidence_id == evidence.id,
            models.EvidenceMediaLink.media_asset_id == media.id,
            models.EvidenceMediaLink.relation == relation,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.status = "linked"
        existing.payload = jsonable_encoder(existing.payload | payload)
        return existing
    link = models.EvidenceMediaLink(
        id=_id("EML"),
        tenant_id=tenant_id,
        evidence_id=evidence.id,
        media_asset_id=media.id,
        relation=relation,
        status="linked",
        payload=jsonable_encoder(payload | {"synthetic": media.is_synthetic}),
    )
    session.add(link)
    session.flush()
    return link


def _upsert_risk_factor_from_evidence(session: Session, evidence: models.Evidence, rule_version: str, run_id: str) -> models.RiskFactor:
    factor_id = _stable_id("RF", evidence.id, rule_version)
    category = _risk_category(evidence)
    evidence_ref = {"object_type": "evidence", "object_id": evidence.id, "object_version": evidence.payload.get("algorithm_version", ALGORITHM_VERSION)}
    payload = {
        "topic_id": evidence.payload.get("topic_id"),
        "evidence_refs": [evidence_ref],
        "input_refs": evidence.payload.get("input_refs", []),
        "algorithm_version": rule_version,
        "risk_factor_run_id": run_id,
        "synthetic": bool(evidence.payload.get("synthetic")),
        "blocked_claims": ["risk factor is explainable model output and requires later mainline validation"],
    }
    factor = session.get(models.RiskFactor, factor_id)
    if factor is None:
        factor = models.RiskFactor(
            id=factor_id,
            case_id=evidence.case_id,
            name=_risk_name(evidence, category),
            category=category,
            confidence=_risk_confidence(evidence),
            status="suggested",
            payload=payload,
        )
        session.add(factor)
        session.flush()
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="evidence",
                from_object_id=evidence.id,
                to_object_type="risk_factor",
                to_object_id=factor.id,
                relation="supports_risk_factor",
                is_synthetic=bool(evidence.payload.get("synthetic")),
                payload={"workflow_run_id": run_id, "evidence_refs": [evidence_ref]},
            )
        )
    else:
        factor.payload = jsonable_encoder(factor.payload | payload)
    return factor


def _select_signals(session: Session, request: schemas.EvidenceCandidateCreate, topic: models.Topic | None) -> list[models.Signal]:
    statement = select(models.Signal).order_by(models.Signal.updated_at.desc()).limit(request.limit)
    if request.signal_ids:
        statement = select(models.Signal).where(models.Signal.id.in_(request.signal_ids)).order_by(models.Signal.updated_at.desc()).limit(request.limit)
    elif topic is not None:
        statement = statement.where(models.Signal.topic_id == topic.id)
    return list(session.execute(statement).scalars())


def _select_evidence_for_risk(session: Session, request: schemas.RiskFactorRunCreate) -> list[models.Evidence]:
    statement = select(models.Evidence).order_by(models.Evidence.updated_at.desc())
    if request.evidence_ids:
        statement = statement.where(models.Evidence.id.in_(request.evidence_ids))
    rows = list(session.execute(statement.limit(100)).scalars())
    if request.topic_id:
        rows = [row for row in rows if row.payload.get("topic_id") == request.topic_id]
    return rows


def _case_for_signals(session: Session, signals: list[models.Signal]) -> models.Case:
    if signals:
        case = session.get(models.Case, signals[0].case_id)
        if case is not None:
            return case
    case = session.get(models.Case, "CASE-CAMPUS-001")
    if case is None:
        raise api_error(404, "CASE_NOT_FOUND", "Default case not found.")
    return case


def _case_for_evidence(evidence_rows: list[models.Evidence]) -> models.Case:
    if not evidence_rows:
        raise api_error(409, "EVIDENCE_SCOPE_EMPTY", "No evidence matched the requested scope.")
    case = evidence_rows[0].case_id
    return evidence_rows[0] and evidence_rows[0]._sa_instance_state.session.get(models.Case, case)


def _topic_or_none(session: Session, topic_id: str | None) -> models.Topic | None:
    return session.get(models.Topic, topic_id) if topic_id else None


def _evidence_or_404(session: Session, evidence_id: str) -> models.Evidence:
    evidence = session.get(models.Evidence, evidence_id)
    if evidence is None:
        raise api_error(404, "EVIDENCE_NOT_FOUND", "Evidence not found.")
    return evidence


def _review_or_404(session: Session, review_id: str) -> models.EvidenceReview:
    review = session.get(models.EvidenceReview, review_id)
    if review is None:
        raise api_error(404, "EVIDENCE_REVIEW_NOT_FOUND", "Evidence review not found.")
    return review


def _media_or_404(session: Session, media_asset_id: str) -> models.MediaAsset:
    media = session.get(models.MediaAsset, media_asset_id)
    if media is None:
        raise api_error(404, "MEDIA_ASSET_NOT_FOUND", "Media asset not found.")
    return media


def _risk_factor_or_404(session: Session, risk_factor_id: str) -> models.RiskFactor:
    factor = session.get(models.RiskFactor, risk_factor_id)
    if factor is None:
        raise api_error(404, "RISK_FACTOR_NOT_FOUND", "Risk factor not found.")
    return factor


def _review_for_evidence(session: Session, evidence_id: str, serialized: bool = False):
    review = session.execute(select(models.EvidenceReview).where(models.EvidenceReview.evidence_id == evidence_id)).scalar_one_or_none()
    if serialized:
        return serialize_evidence_review(session, review) if review else None
    return review


def _evidence_for_media(session: Session, media_asset_id: str) -> models.Evidence | None:
    link = session.execute(select(models.EvidenceMediaLink).where(models.EvidenceMediaLink.media_asset_id == media_asset_id)).scalar_one_or_none()
    return session.get(models.Evidence, link.evidence_id) if link else None


def _media_runs_for_evidence(session: Session, evidence_id: str) -> list[dict]:
    links = session.execute(select(models.EvidenceMediaLink).where(models.EvidenceMediaLink.evidence_id == evidence_id)).scalars()
    media_ids = [link.media_asset_id for link in links]
    if not media_ids:
        return []
    rows = session.execute(select(models.MediaProcessingRun).where(models.MediaProcessingRun.media_asset_id.in_(media_ids)).order_by(models.MediaProcessingRun.created_at.desc())).scalars()
    return [serialize_media_processing_run(row) for row in rows]


def _lineage_for_evidence(session: Session, evidence_id: str) -> list[dict]:
    rows = session.execute(
        select(models.LineageEdge)
        .where(
            ((models.LineageEdge.from_object_type == "evidence") & (models.LineageEdge.from_object_id == evidence_id))
            | ((models.LineageEdge.to_object_type == "evidence") & (models.LineageEdge.to_object_id == evidence_id))
        )
        .order_by(models.LineageEdge.created_at.desc())
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
            "created_at": row.created_at,
        }
        for row in rows
    ]


def _raw_record_id_for_evidence(evidence: models.Evidence) -> str | None:
    refs = list(evidence.payload.get("evidence_refs", [])) + list(evidence.payload.get("source_refs", []))
    for ref in refs:
        if isinstance(ref, dict) and ref.get("object_type") == "raw_record":
            return str(ref.get("object_id"))
    return None


def _evidence_refs_for_signal(signal: models.Signal) -> list[dict]:
    refs = list(signal.payload.get("evidence_refs", []))
    refs.append({"object_type": "signal", "object_id": signal.id, "object_version": signal.payload.get("algorithm_version", "unknown"), "confidence": signal.scores.get("credibility", 0.6), "synthetic": bool(signal.payload.get("synthetic"))})
    return refs


def _media_output(media: models.MediaAsset, evidence: models.Evidence | None, processor: str, rule_version: str) -> dict:
    content = str(media.payload.get("content") or media.payload.get("masked_text") or evidence.masked_excerpt if evidence else media.uri)
    text = mask_sensitive_text(content)
    output = {
        "processor": processor,
        "rule_version": rule_version,
        "text": text,
        "confidence": 0.82 if media.is_synthetic else 0.62,
        "frame_refs": [],
        "timecodes": [],
        "synthetic": media.is_synthetic,
        "blocked_claims": ["media processing output is not a factual finding until evidence review"],
    }
    if processor in {"frame_extract", "video_ocr", "segment_detect", "live_segment"}:
        output["frame_refs"] = [{"frame_id": f"{media.id}-frame-001", "timecode_ms": 1200, "confidence": output["confidence"]}]
    if processor in {"asr", "segment_detect", "live_segment"}:
        output["timecodes"] = [{"start_ms": 0, "end_ms": 4200, "confidence": output["confidence"]}]
    return output


def _conflict_for_evidence(evidence: models.Evidence) -> dict:
    evidence_ref = {"object_type": "evidence", "object_id": evidence.id, "object_version": evidence.payload.get("algorithm_version", ALGORITHM_VERSION)}
    return {
        "severity": "low" if evidence.status == "confirmed_fact" else "medium",
        "message": "Evidence material requires source-context check before it can support a report fact.",
        "evidence_refs": [evidence_ref],
        "blocked_claims": evidence.payload.get("blocked_claims", []),
    }


def _legacy_evidence_page(evidence: models.Evidence, review: models.EvidenceReview, media_links: list[dict], media_runs: list[dict], risk_factors: list[dict], conflicts: list[dict]) -> dict:
    case_id = evidence.case_id
    return {
        "case_id": case_id,
        "page": "evidence",
        "title": "Evidence Review Workbench",
        "subtitle": evidence.title,
        "nav": _nav(case_id),
        "metrics": [
            {"label": "Review status", "value": review.status, "tone": "blue"},
            {"label": "Media links", "value": len(media_links), "tone": "violet"},
            {"label": "Processing runs", "value": len(media_runs), "tone": "amber"},
            {"label": "Risk factors", "value": len(risk_factors), "tone": "green"},
        ],
        "sections": [
            {"id": "evidence", "title": "Evidence material", "kind": "evidence", "items": [serialize_evidence(evidence)]},
            {"id": "media", "title": "Linked media", "kind": "sources", "items": media_links},
            {"id": "processing", "title": "Media processing runs", "kind": "timeline", "items": [run["media_processing_run_id"] + ":" + run["status"] for run in media_runs]},
            {"id": "risk-factors", "title": "Risk factors", "kind": "signals", "items": risk_factors},
            {"id": "conflicts", "title": "Conflict prompts", "kind": "chips", "items": [item["message"] for item in conflicts]},
        ],
        "actions": [{"id": "enter-mainline", "label": "Enter mainline modeling", "to_page": "mainline"}],
        "raw": {"evidence_review_id": review.id, "evidence_id": evidence.id, "topic_id": review.topic_id, "source": "postgresql"},
    }


def _nav(case_id: str) -> list[dict]:
    pages = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]
    return [{"page": page, "label": page, "path": f"/cases/{case_id}/{page}"} for page in pages]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _credibility_label(signal: models.Signal) -> str:
    credibility = signal.scores.get("credibility", 0.6)
    if credibility >= 0.82:
        return "high"
    if credibility >= 0.68:
        return "medium"
    return "low"


def _sensitive_signal(signal: models.Signal) -> bool:
    title_summary = f"{signal.title} {signal.summary}".lower()
    return "minor" in title_summary or "zhang" in title_summary or "student" in title_summary


def _risk_category(evidence: models.Evidence) -> str:
    text = f"{evidence.title} {evidence.excerpt}".lower()
    if "minor" in text or "student" in text:
        return "privacy"
    if "timeline" in text or "window" in text:
        return "response_gap"
    if "ledger" in text or "fee" in text or "compensation" in text:
        return "responsibility"
    return "trust_risk"


def _risk_name(evidence: models.Evidence, category: str) -> str:
    labels = {
        "privacy": "Sensitive-person privacy exposure",
        "response_gap": "Response-window credibility gap",
        "responsibility": "Responsibility explanation gap",
        "trust_risk": "Evidence-backed trust risk",
    }
    return labels.get(category, "Evidence-backed risk factor")


def _risk_confidence(evidence: models.Evidence) -> float:
    base = 0.66 if evidence.status == "confirmed_fact" else 0.54
    if evidence.credibility == "high":
        base += 0.12
    if evidence.payload.get("synthetic"):
        base -= 0.04
    return round(max(0.1, min(0.95, base)), 4)
