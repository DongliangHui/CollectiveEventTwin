from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import foundation, models, schemas
from .audit import write_audit
from .foundation import api_error

ALGORITHM_VERSION = "s7a-report-task-closure-v1"
REPORT_REVIEW_TEMPLATE_ID = "TPL-REPORT-V1"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_reports(session: Session, topic_id: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.Report).order_by(models.Report.updated_at.desc())
    if topic_id:
        statement = statement.where(models.Report.topic_id == topic_id)
    if status:
        statement = statement.where(models.Report.status == status)
    return [serialize_report(row) for row in session.execute(statement).scalars()]


def create_report_draft(session: Session, request: schemas.ReportCreate, actor: models.User, trace_id: str) -> dict:
    topic, result, run, world_state, mainline = _resolve_context(session, request.topic_id, request.council_result_id)
    evidence_refs = _dedupe_refs(
        list(result.evidence_refs or [])
        + list(run.payload.get("evidence_refs", []))
        + list(mainline.payload.get("evidence_refs", []))
    )
    if not evidence_refs:
        raise api_error(409, "REPORT_EVIDENCE_REFS_REQUIRED", "Report draft requires evidence references.")

    evidence_rows = _evidence_rows(session, evidence_refs)
    sections = _build_sections(topic, result, run, world_state, mainline, evidence_rows)
    synthetic = bool(mainline.payload.get("synthetic") or world_state.payload.get("synthetic") or run.payload.get("synthetic"))
    report = models.Report(
        id=_id("RPT"),
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        topic_id=topic.id,
        title=f"{topic.title} - evidence brief",
        human_confirmed=False,
        status="draft",
        current_version=1,
        payload=jsonable_encoder(
            {
                "algorithm_version": ALGORITHM_VERSION,
                "topic_id": topic.id,
                "mainline_id": mainline.id,
                "world_state_id": world_state.id,
                "worldline_run_id": run.id,
                "council_result_id": result.id,
                "reason": request.reason,
                "input_refs": [
                    {"object_type": "topic", "object_id": topic.id},
                    {"object_type": "mainline", "object_id": mainline.id, "object_version": mainline.payload.get("version", "v1")},
                    {"object_type": "world_state", "object_id": world_state.id, "object_version": world_state.payload.get("version", "v1")},
                    {"object_type": "worldline_run", "object_id": run.id, "object_version": f"v{run.version}"},
                    {"object_type": "council_result", "object_id": result.id, "object_version": "v1"},
                ],
                "evidence_refs": evidence_refs,
                "claim_validation": {"passed": True, "checked_at": utcnow().isoformat(), "invalid_claim_ids": []},
                "synthetic_watermark": synthetic,
                "draft_summary": result.summary,
                "blocked_claims": result.payload.get("blocked_claims", []),
            }
        ),
    )
    session.add(report)
    session.flush()

    version = _save_version(session, actor, report, sections, {"action": "create_report_draft"})
    claims = _build_claims(topic, result, run, world_state, mainline, evidence_refs)
    invalid = []
    for position, claim in enumerate(claims, start=1):
        validation_status = "valid" if _claim_evidence_valid(session, claim["evidence_refs"]) else "invalid"
        claim_row = models.ReportClaim(
            id=_id("RC"),
            tenant_id=actor.tenant_id,
            report_id=report.id,
            report_version_id=version.id,
            position=position,
            claim_type=claim["claim_type"],
            statement=claim["statement"],
            status="candidate",
            validation_status=validation_status,
            source_object_type=claim["source_object_type"],
            source_object_id=claim["source_object_id"],
            evidence_refs=jsonable_encoder(claim["evidence_refs"]),
            payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, "input_refs": claim["input_refs"]}),
        )
        session.add(claim_row)
        if validation_status != "valid":
            invalid.append(claim_row.id)
    if invalid:
        report.status = "claim_validation_failed"
        report.payload = jsonable_encoder(report.payload | {"claim_validation": {"passed": False, "checked_at": utcnow().isoformat(), "invalid_claim_ids": invalid}})

    _create_auto_tasks(session, actor, report, result, evidence_refs, trace_id)
    _workflow_run(session, actor, report.case_id, "report_draft_generation", f"report:{report.id}", trace_id, {"report_id": report.id, "claim_count": len(claims), "evidence_refs": evidence_refs})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=report.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="report_draft.create",
        object_type="report",
        object_id=report.id,
        object_version="v1",
        reason=request.reason,
        after=serialize_report(report),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_report(report)


def get_report(session: Session, report_id: str) -> dict:
    return serialize_report(_report_or_404(session, report_id))


def update_report(session: Session, report_id: str, request: schemas.ReportPatch, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, report_id)
    before = serialize_report(report)
    if report.status in {"published", "exported", "archived"}:
        raise api_error(409, "REPORT_LOCKED", "Published or exported report requires a new draft version.")
    if request.title is not None:
        report.title = request.title
    report.current_version += 1
    sections = request.sections if request.sections is not None else _latest_sections(session, report.id)
    report.payload = jsonable_encoder(report.payload | {"last_edit_reason": request.reason, "claim_validation": _validate_report_claims(session, report.id)})
    if not report.payload["claim_validation"]["passed"]:
        report.status = "claim_validation_failed"
    elif report.status == "claim_validation_failed":
        report.status = "draft"
    _save_version(session, actor, report, sections, {"action": "update_report", "before": before, "reason": request.reason})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=report.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="report.update",
        object_type="report",
        object_id=report.id,
        object_version=f"v{report.current_version}",
        reason=request.reason,
        before=before,
        after=serialize_report(report),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_report(report)


def brief_view(session: Session, report_id: str, actor: models.User) -> dict:
    report = _report_or_404(session, report_id)
    claims = _claims_for_report(session, report.id)
    versions = _versions_for_report(session, report.id)
    exports = _exports_for_report(session, report.id)
    tasks = _tasks_for_report(session, report.id)
    evidence = _evidence_rows(session, report.payload.get("evidence_refs", []))
    review = session.get(models.Review, report.review_id) if report.review_id else None
    page = _legacy_brief_page(report, claims, tasks, exports)
    return {
        "page_state": "ready" if claims else "empty",
        "permissions": {"report:read": True, "report:write": True, "task:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "reports/report_versions/report_claims/report_exports/tasks/task_events"},
        "degraded_sources": [] if report.payload.get("claim_validation", {}).get("passed") else [{"code": "REPORT_CLAIM_VALIDATION_FAILED", "message": "One or more report claims lack valid evidence refs."}],
        "audit_context": {"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"},
        "primary_data": {
            "report": serialize_report(report),
            "versions": [serialize_report_version(row) for row in versions],
            "claims": [serialize_report_claim(row) for row in claims],
            "evidence": [_serialize_evidence(row) for row in evidence],
            "exports": [serialize_report_export(row) for row in exports],
            "tasks": [serialize_task(row) for row in tasks],
            "review": foundation.serialize_review(review) if review else None,
            "legacy_page_view": page,
        },
        "actions": [
            {"id": "submit-review", "label": "Submit report review", "method": "POST", "href": f"/api/v1/reports/{report.id}/submit-review", "enabled": report.status in {"draft", "review_returned"}},
            {"id": "publish-report", "label": "Publish report", "method": "POST", "href": f"/api/v1/reports/{report.id}/publish", "enabled": report.status in {"submitted_review", "approved"}},
            {"id": "export-report", "label": "Export report", "method": "POST", "href": f"/api/v1/reports/{report.id}/exports", "enabled": report.status in {"published", "exported"}},
        ],
    }


def submit_report_review(session: Session, report_id: str, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, report_id)
    validation = _validate_report_claims(session, report.id)
    if not validation["passed"]:
        report.status = "claim_validation_failed"
        report.payload = jsonable_encoder(report.payload | {"claim_validation": validation})
        session.commit()
        raise api_error(409, "REPORT_CLAIM_VALIDATION_FAILED", "Report claims must all have valid evidence refs before review.", validation)
    review = foundation.create_review(
        session,
        schemas.ReviewCreate(
            object_type="report",
            object_id=report.id,
            object_version=f"v{report.current_version}",
            template_id=REPORT_REVIEW_TEMPLATE_ID,
            payload={"claim_count": len(_claims_for_report(session, report.id)), "evidence_refs": report.payload.get("evidence_refs", [])},
        ),
        actor,
        trace_id,
    )
    report.review_id = review["review_id"]
    report.status = "submitted_review"
    report.payload = jsonable_encoder(report.payload | {"review_id": report.review_id, "submitted_at": utcnow().isoformat(), "claim_validation": validation})
    _workflow_run(session, actor, report.case_id, "report_review_submission", f"report-review:{report.id}", trace_id, {"report_id": report.id, "review_id": report.review_id})
    write_audit(session, tenant_id=actor.tenant_id, case_id=report.case_id, actor=actor.username, actor_id=actor.id, action="report_review.submit", object_type="report", object_id=report.id, object_version=f"v{report.current_version}", after=serialize_report(report), trace_id=trace_id)
    session.commit()
    return review


def publish_report(session: Session, report_id: str, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, report_id)
    if not report.review_id or not _has_passed_review(session, report.review_id):
        raise api_error(409, "REPORT_REVIEW_NOT_PASSED", "Report review gate must pass before publication.")
    validation = _validate_report_claims(session, report.id)
    if not validation["passed"]:
        raise api_error(409, "REPORT_CLAIM_VALIDATION_FAILED", "Report claims must remain evidence-valid before publication.", validation)
    before = serialize_report(report)
    report.status = "published"
    report.human_confirmed = True
    report.published_at = utcnow()
    report.payload = jsonable_encoder(report.payload | {"published_at": report.published_at.isoformat(), "claim_validation": validation})
    _save_version(session, actor, report, _latest_sections(session, report.id), {"action": "publish_report", "review_id": report.review_id})
    _workflow_run(session, actor, report.case_id, "report_publication", f"report-publish:{report.id}", trace_id, {"report_id": report.id, "review_id": report.review_id})
    write_audit(session, tenant_id=actor.tenant_id, case_id=report.case_id, actor=actor.username, actor_id=actor.id, action="report.publish", object_type="report", object_id=report.id, object_version=f"v{report.current_version}", before=before, after=serialize_report(report), trace_id=trace_id)
    session.commit()
    return serialize_report(report)


def export_report(session: Session, report_id: str, request: schemas.ReportExportCreate, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, report_id)
    if report.status not in {"published", "exported"}:
        raise api_error(409, "REPORT_NOT_PUBLISHED", "Report must be published before export.")
    claims = [serialize_report_claim(row) for row in _claims_for_report(session, report.id)]
    tasks = [serialize_task(row) for row in _tasks_for_report(session, report.id)]
    content = _export_content(report, claims, tasks, request.format)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    watermark = "synthetic" if report.payload.get("synthetic_watermark") else "production"
    export = models.ReportExport(
        id=_id("RPE"),
        tenant_id=actor.tenant_id,
        report_id=report.id,
        format=request.format,
        status="completed",
        file_uri=f"postgresql://report_exports/{report.id}/{content_hash[:16]}.{request.format}",
        watermark=watermark,
        content_hash=content_hash,
        payload=jsonable_encoder({"content": content, "reason": request.reason, "claim_count": len(claims), "task_count": len(tasks)}),
    )
    session.add(export)
    report.status = "exported"
    report.exported_at = utcnow()
    report.payload = jsonable_encoder(report.payload | {"latest_export_id": export.id, "exported_at": report.exported_at.isoformat()})
    _workflow_run(session, actor, report.case_id, "report_export", f"report-export:{export.id}", trace_id, {"report_id": report.id, "export_id": export.id, "format": request.format})
    write_audit(session, tenant_id=actor.tenant_id, case_id=report.case_id, actor=actor.username, actor_id=actor.id, action="report_export.create", object_type="report_export", object_id=export.id, object_version=f"v{report.current_version}", reason=request.reason, after=serialize_report_export(export), trace_id=trace_id)
    session.commit()
    return serialize_report_export(export)


def list_tasks(session: Session, report_id: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.Task).order_by(models.Task.updated_at.desc())
    if report_id:
        statement = statement.where(models.Task.report_id == report_id)
    if status:
        statement = statement.where(models.Task.status == status)
    return [serialize_task(row) for row in session.execute(statement).scalars()]


def create_task(session: Session, request: schemas.TaskCreate, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, request.report_id) if request.report_id else None
    case_id = request.case_id or (report.case_id if report else None)
    if case_id is None:
        raise api_error(422, "TASK_REPORT_OR_CASE_REQUIRED", "Task creation requires report_id or case_id.")
    evidence_refs = request.evidence_refs or (report.payload.get("evidence_refs", []) if report else [])
    if report is not None and not evidence_refs:
        raise api_error(409, "TASK_EVIDENCE_REFS_REQUIRED", "Report-linked tasks require evidence refs.")
    task = models.Task(
        id=_id("TSK"),
        tenant_id=actor.tenant_id,
        case_id=case_id,
        report_id=report.id if report else None,
        title=request.title,
        owner=request.owner,
        due_label=request.due_label,
        due_at=request.due_at,
        status=request.status,
        version=1,
        evidence_refs=jsonable_encoder(evidence_refs),
        payload=jsonable_encoder({"reason": request.reason, **request.payload, "input_refs": [{"object_type": "report", "object_id": report.id}] if report else [{"object_type": "case", "object_id": case_id}]}),
    )
    session.add(task)
    _task_event(session, actor, task, "task.create", None, task.status, request.reason, trace_id)
    write_audit(session, tenant_id=actor.tenant_id, case_id=case_id, actor=actor.username, actor_id=actor.id, action="task.create", object_type="task", object_id=task.id, object_version="v1", reason=request.reason, after=serialize_task(task), trace_id=trace_id)
    session.commit()
    return serialize_task(task)


def update_task_status(session: Session, task_id: str, request: schemas.TaskUpdate, actor: models.User, trace_id: str) -> dict:
    task = _task_or_404(session, task_id)
    before = serialize_task(task)
    old = task.status
    task.status = request.status
    task.version += 1
    task.payload = jsonable_encoder(task.payload | {"last_status_reason": request.reason})
    _task_event(session, actor, task, "task.status_update", old, task.status, request.reason, trace_id)
    write_audit(session, tenant_id=actor.tenant_id, case_id=task.case_id, actor=actor.username, actor_id=actor.id, action="task.status_update", object_type="task", object_id=task.id, object_version=f"v{task.version}", reason=request.reason, before=before, after=serialize_task(task), trace_id=trace_id)
    session.commit()
    return serialize_task(task)


def serialize_report(report: models.Report) -> dict:
    return {"id": report.id, "tenant_id": report.tenant_id, "case_id": report.case_id, "topic_id": report.topic_id, "title": report.title, "human_confirmed": report.human_confirmed, "status": report.status, "version": f"v{report.current_version}", "current_version": report.current_version, "review_id": report.review_id, "published_at": report.published_at, "exported_at": report.exported_at, "synthetic_watermark": bool(report.payload.get("synthetic_watermark")), "payload": report.payload, "created_at": report.created_at, "updated_at": report.updated_at}


def serialize_report_version(row: models.ReportVersion) -> dict:
    return {"id": row.id, "report_id": row.report_id, "version": f"v{row.version}", "version_number": row.version, "status": row.status, "sections": row.sections, "diff": row.diff, "payload": row.payload, "created_at": row.created_at}


def serialize_report_claim(row: models.ReportClaim) -> dict:
    return {"id": row.id, "report_id": row.report_id, "report_version_id": row.report_version_id, "position": row.position, "claim_type": row.claim_type, "statement": row.statement, "status": row.status, "validation_status": row.validation_status, "source_object_type": row.source_object_type, "source_object_id": row.source_object_id, "evidence_refs": row.evidence_refs, "payload": row.payload, "created_at": row.created_at}


def serialize_report_export(row: models.ReportExport) -> dict:
    return {"id": row.id, "report_id": row.report_id, "format": row.format, "status": row.status, "file_uri": row.file_uri, "watermark": row.watermark, "content_hash": row.content_hash, "payload": row.payload, "created_at": row.created_at}


def serialize_task(row: models.Task) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "case_id": row.case_id, "report_id": row.report_id, "title": row.title, "owner": row.owner, "due_label": row.due_label, "due_at": row.due_at, "status": row.status, "version": f"v{row.version}", "evidence_refs": row.evidence_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def _resolve_context(session: Session, topic_id: str, council_result_id: str | None) -> tuple[models.Topic, models.CouncilResult, models.WorldlineRun, models.WorldState, models.Mainline]:
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic does not exist.")
    result = _council_result_or_404(session, council_result_id) if council_result_id else _latest_applied_council_for_topic(session, topic.id)
    if result is None:
        raise api_error(404, "COUNCIL_RESULT_NOT_FOUND", "No applied Council Result exists for this topic.")
    if result.status != "pass" or result.payload.get("applied") is not True:
        raise api_error(409, "REPORT_COUNCIL_RESULT_NOT_APPLIED", "Report can only use a reviewed and applied Council Result.")
    run = session.get(models.WorldlineRun, result.worldline_run_id)
    if run is None:
        raise api_error(404, "WORLDLINE_RUN_NOT_FOUND", "Worldline Run does not exist.")
    world_state = session.get(models.WorldState, run.world_state_id)
    if world_state is None:
        raise api_error(404, "WORLD_STATE_NOT_FOUND", "World State does not exist.")
    mainline = session.get(models.Mainline, world_state.payload.get("mainline_id"))
    if mainline is None:
        raise api_error(404, "MAINLINE_NOT_FOUND", "Mainline does not exist.")
    if mainline.payload.get("topic_id") != topic.id:
        raise api_error(409, "REPORT_TOPIC_MISMATCH", "Council Result does not belong to the requested topic.")
    return topic, result, run, world_state, mainline


def _latest_applied_council_for_topic(session: Session, topic_id: str) -> models.CouncilResult | None:
    results = session.execute(select(models.CouncilResult).where(models.CouncilResult.status == "pass").order_by(models.CouncilResult.updated_at.desc())).scalars()
    for result in results:
        try:
            _, resolved, _, _, _ = _resolve_context(session, topic_id, result.id)
        except Exception:
            continue
        return resolved
    return None


def _build_sections(topic: models.Topic, result: models.CouncilResult, run: models.WorldlineRun, world_state: models.WorldState, mainline: models.Mainline, evidence_rows: list[models.Evidence]) -> list[dict]:
    return [
        {"id": "summary", "title": "Executive summary", "body": result.summary, "source_refs": [{"object_type": "council_result", "object_id": result.id}]},
        {"id": "topic", "title": "Topic situation", "body": topic.title, "source_refs": [{"object_type": "topic", "object_id": topic.id}]},
        {"id": "mainline", "title": "Mainline result", "body": mainline.title, "source_refs": [{"object_type": "mainline", "object_id": mainline.id, "object_version": mainline.payload.get("version", "v1")}]},
        {"id": "worldline", "title": "Worldline projection", "body": f"Worldline Run {run.id} reached {run.status}.", "source_refs": [{"object_type": "worldline_run", "object_id": run.id, "object_version": f"v{run.version}"}]},
        {"id": "evidence", "title": "Evidence chain", "body": f"{len(evidence_rows)} persisted evidence records support this brief.", "source_refs": [{"object_type": "evidence", "object_id": row.id} for row in evidence_rows]},
        {"id": "uncertainty", "title": "Uncertainty", "body": "; ".join(result.payload.get("information_gaps", [])) or "No extra information gaps recorded.", "source_refs": [{"object_type": "world_state", "object_id": world_state.id}]},
    ]


def _build_claims(topic: models.Topic, result: models.CouncilResult, run: models.WorldlineRun, world_state: models.WorldState, mainline: models.Mainline, evidence_refs: list[dict]) -> list[dict]:
    return [
        {"claim_type": "topic_summary", "statement": f"Topic {topic.title} is the report scope.", "source_object_type": "topic", "source_object_id": topic.id, "evidence_refs": evidence_refs, "input_refs": [{"object_type": "topic", "object_id": topic.id}]},
        {"claim_type": "mainline_result", "statement": f"Confirmed mainline: {mainline.title}.", "source_object_type": "mainline", "source_object_id": mainline.id, "evidence_refs": evidence_refs, "input_refs": [{"object_type": "mainline", "object_id": mainline.id}]},
        {"claim_type": "worldline_projection", "statement": f"Worldline Run {run.id} is version v{run.version} and status {run.status}.", "source_object_type": "worldline_run", "source_object_id": run.id, "evidence_refs": evidence_refs, "input_refs": [{"object_type": "worldline_run", "object_id": run.id}]},
        {"claim_type": "council_result", "statement": result.summary, "source_object_type": "council_result", "source_object_id": result.id, "evidence_refs": evidence_refs, "input_refs": [{"object_type": "council_result", "object_id": result.id}]},
        {"claim_type": "world_state_lock", "statement": f"World State {world_state.id} locks the S5 mainline input for this report.", "source_object_type": "world_state", "source_object_id": world_state.id, "evidence_refs": evidence_refs, "input_refs": [{"object_type": "world_state", "object_id": world_state.id}]},
    ]


def _create_auto_tasks(session: Session, actor: models.User, report: models.Report, result: models.CouncilResult, evidence_refs: list[dict], trace_id: str) -> None:
    gaps = result.payload.get("information_gaps", []) or ["Verify follow-up observation window."]
    for position, gap in enumerate(gaps, start=1):
        task = models.Task(
            id=_id("TSK"),
            tenant_id=actor.tenant_id,
            case_id=report.case_id,
            report_id=report.id,
            title=f"Follow up: {gap}",
            owner="operator",
            due_label="24h",
            status="suggested",
            version=1,
            evidence_refs=jsonable_encoder(evidence_refs),
            payload=jsonable_encoder({"auto_generated": True, "source": "report_information_gap", "position": position, "input_refs": [{"object_type": "report", "object_id": report.id}]}),
        )
        session.add(task)
        _task_event(session, actor, task, "task.create", None, task.status, "Auto-generated from report uncertainty.", trace_id)


def _save_version(session: Session, actor: models.User, report: models.Report, sections: list[dict], diff: dict) -> models.ReportVersion:
    version = models.ReportVersion(
        id=_id("RPV"),
        tenant_id=actor.tenant_id,
        report_id=report.id,
        version=report.current_version,
        status=report.status,
        sections=jsonable_encoder(sections),
        diff=jsonable_encoder(diff),
        payload={"algorithm_version": ALGORITHM_VERSION},
    )
    session.add(version)
    session.flush()
    return version


def _validate_report_claims(session: Session, report_id: str) -> dict:
    invalid = [claim.id for claim in _claims_for_report(session, report_id) if not _claim_evidence_valid(session, claim.evidence_refs)]
    return {"passed": not invalid, "checked_at": utcnow().isoformat(), "invalid_claim_ids": invalid}


def _claim_evidence_valid(session: Session, evidence_refs: list[dict]) -> bool:
    ids = [ref.get("object_id") for ref in evidence_refs if ref.get("object_type") == "evidence" and ref.get("object_id")]
    if not ids:
        return False
    count = session.execute(select(models.Evidence).where(models.Evidence.id.in_(ids))).scalars().all()
    return len({row.id for row in count}) == len(set(ids))


def _report_or_404(session: Session, report_id: str | None) -> models.Report:
    row = session.get(models.Report, report_id)
    if row is None:
        raise api_error(404, "REPORT_NOT_FOUND", "Report does not exist.")
    return row


def _task_or_404(session: Session, task_id: str) -> models.Task:
    row = session.get(models.Task, task_id)
    if row is None:
        raise api_error(404, "TASK_NOT_FOUND", "Task does not exist.")
    return row


def _council_result_or_404(session: Session, council_result_id: str | None) -> models.CouncilResult:
    row = session.get(models.CouncilResult, council_result_id)
    if row is None:
        raise api_error(404, "COUNCIL_RESULT_NOT_FOUND", "Council Result does not exist.")
    return row


def _has_passed_review(session: Session, review_id: str) -> bool:
    review = session.get(models.Review, review_id)
    return review is not None and foundation.review_gate_check(session, review.id)["passed"] is True


def _claims_for_report(session: Session, report_id: str) -> list[models.ReportClaim]:
    return list(session.execute(select(models.ReportClaim).where(models.ReportClaim.report_id == report_id).order_by(models.ReportClaim.position)).scalars())


def _versions_for_report(session: Session, report_id: str) -> list[models.ReportVersion]:
    return list(session.execute(select(models.ReportVersion).where(models.ReportVersion.report_id == report_id).order_by(models.ReportVersion.version)).scalars())


def _exports_for_report(session: Session, report_id: str) -> list[models.ReportExport]:
    return list(session.execute(select(models.ReportExport).where(models.ReportExport.report_id == report_id).order_by(models.ReportExport.created_at.desc())).scalars())


def _tasks_for_report(session: Session, report_id: str) -> list[models.Task]:
    return list(session.execute(select(models.Task).where(models.Task.report_id == report_id).order_by(models.Task.created_at)).scalars())


def _latest_sections(session: Session, report_id: str) -> list[dict]:
    version = session.execute(select(models.ReportVersion).where(models.ReportVersion.report_id == report_id).order_by(models.ReportVersion.version.desc())).scalars().first()
    return list(version.sections) if version else []


def _evidence_rows(session: Session, evidence_refs: list[dict]) -> list[models.Evidence]:
    ids = [ref.get("object_id") for ref in evidence_refs if ref.get("object_type") == "evidence" and ref.get("object_id")]
    if not ids:
        return []
    rows = session.execute(select(models.Evidence).where(models.Evidence.id.in_(ids))).scalars().all()
    by_id = {row.id: row for row in rows}
    return [by_id[row_id] for row_id in ids if row_id in by_id]


def _dedupe_refs(refs: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for ref in refs:
        key = (ref.get("object_type"), ref.get("object_id"), ref.get("object_version"))
        if ref.get("object_type") and ref.get("object_id") and key not in seen:
            seen.add(key)
            out.append(ref)
    return out


def _task_event(session: Session, actor: models.User, task: models.Task, event_type: str, from_status: str | None, to_status: str | None, reason: str | None, trace_id: str) -> None:
    session.add(models.TaskEvent(id=_id("TSE"), tenant_id=actor.tenant_id, task_id=task.id, event_type=event_type, from_status=from_status, to_status=to_status, actor_id=actor.id, reason=reason, payload={"trace_id": trace_id}))


def _workflow_run(session: Session, actor: models.User, case_id: str, workflow_type: str, workflow_id: str, trace_id: str, payload: dict) -> None:
    session.add(models.WorkflowRun(id=_id("WFR"), case_id=case_id, tenant_id=actor.tenant_id, workflow_name=workflow_type, workflow_id=workflow_id, status="completed", started_by=actor.id, trace_id=trace_id, payload=jsonable_encoder(payload | {"algorithm_version": ALGORITHM_VERSION})))


def _serialize_evidence(row: models.Evidence) -> dict:
    return {"id": row.id, "signal_id": row.signal_id, "title": row.title, "status": row.status, "credibility": row.credibility, "source": row.source, "masked_excerpt": row.masked_excerpt, "payload": row.payload}


def _legacy_brief_page(report: models.Report, claims: list[models.ReportClaim], tasks: list[models.Task], exports: list[models.ReportExport]) -> dict:
    return {
        "id": report.id,
        "case_id": report.case_id,
        "page": "brief",
        "title": report.title,
        "status": report.status,
        "nav": [],
        "hero": {"title": report.title, "subtitle": report.payload.get("draft_summary", ""), "status": report.status},
        "metrics": [
            {"label": "Claims", "value": len(claims), "tone": "green"},
            {"label": "Tasks", "value": len(tasks), "tone": "red"},
            {"label": "Exports", "value": len(exports), "tone": "blue"},
        ],
        "sections": [
            {"id": "claims", "title": "Report claims", "kind": "records", "items": [serialize_report_claim(row) for row in claims]},
            {"id": "actions", "title": "Suggested tasks", "kind": "tasks", "items": [serialize_task(row) for row in tasks]},
            {"id": "exports", "title": "Exports", "kind": "records", "items": [serialize_report_export(row) for row in exports]},
        ],
    }


def _export_content(report: models.Report, claims: list[dict], tasks: list[dict], export_format: str) -> str:
    payload = {"report": serialize_report(report), "claims": claims, "tasks": tasks}
    if export_format == "json":
        return json.dumps(jsonable_encoder(payload), ensure_ascii=False, sort_keys=True)
    lines = [f"# {report.title}", "", f"Status: {report.status}", f"Version: v{report.current_version}", ""]
    lines.append("## Claims")
    for claim in claims:
        lines.append(f"- {claim['statement']} [{len(claim['evidence_refs'])} evidence refs]")
    lines.extend(["", "## Tasks"])
    for task in tasks:
        lines.append(f"- {task['title']} ({task['status']})")
    return "\n".join(lines)
