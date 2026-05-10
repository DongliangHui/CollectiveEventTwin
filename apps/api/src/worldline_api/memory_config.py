from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import foundation, models, schemas
from .audit import write_audit
from .foundation import api_error
from .reports import serialize_report, serialize_report_claim, serialize_task

ALGORITHM_VERSION = "s7b-memory-library-config-v1"
RETROSPECTIVE_TEMPLATE_ID = "TPL-RETROSPECTIVE-V1"
CONFIG_TEMPLATE_ID = "TPL-CONFIG-VERSION-V1"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_retrospective(session: Session, request: schemas.RetrospectiveCreate, actor: models.User, trace_id: str) -> dict:
    report = _report_or_404(session, request.report_id)
    if report.status not in {"published", "exported"} or not report.human_confirmed:
        raise api_error(409, "RETROSPECTIVE_SOURCE_REPORT_NOT_PUBLISHED", "Retrospective requires a published report.")
    source_refs = _dedupe_refs(
        [{"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"}]
        + list(report.payload.get("evidence_refs", []))
    )
    retrospective = models.Retrospective(
        id=_id("RET"),
        tenant_id=actor.tenant_id,
        report_id=report.id,
        case_id=report.case_id,
        status="draft",
        version=1,
        summary=f"Retrospective memory draft for {report.title}",
        source_refs=jsonable_encoder(source_refs),
        payload=jsonable_encoder(
            {
                "algorithm_version": ALGORITHM_VERSION,
                "reason": request.reason,
                "knowledge_item_ids": [],
                "case_library_entry_ids": [],
                "synthetic_watermark": bool(report.payload.get("synthetic_watermark")),
                "input_refs": [{"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"}],
            }
        ),
    )
    session.add(retrospective)
    session.flush()

    items = _derive_knowledge_items(session, report, retrospective, actor)
    retrospective.payload = jsonable_encoder(retrospective.payload | {"knowledge_item_ids": [item.id for item in items]})
    _workflow_run(session, actor, report.case_id, "retrospective_memory_draft", f"retrospective:{retrospective.id}", trace_id, {"retrospective_id": retrospective.id, "knowledge_item_ids": [item.id for item in items]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=report.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="retrospective.create",
        object_type="retrospective",
        object_id=retrospective.id,
        object_version="v1",
        reason=request.reason,
        after=serialize_retrospective(retrospective),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_retrospective(retrospective)


def create_knowledge_item(session: Session, request: schemas.KnowledgeItemCreate, actor: models.User, trace_id: str) -> dict:
    retrospective = _retrospective_or_404(session, request.retrospective_id)
    if retrospective.status not in {"draft", "review_failed"}:
        raise api_error(409, "RETROSPECTIVE_LOCKED", "Knowledge items can only be added before retrospective approval.")
    report = _report_or_404(session, retrospective.report_id)
    source_refs = request.source_refs or [{"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"}]
    if not _source_refs_valid(source_refs):
        raise api_error(422, "KNOWLEDGE_SOURCE_REFS_REQUIRED", "Knowledge item requires source refs.")
    item = models.KnowledgeItem(
        id=_id("KI"),
        tenant_id=actor.tenant_id,
        retrospective_id=retrospective.id,
        report_id=report.id,
        case_id=report.case_id,
        status="draft",
        content=request.content,
        source_refs=jsonable_encoder(source_refs),
        payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, "manual": True, "reason": request.reason}),
    )
    session.add(item)
    retrospective.payload = jsonable_encoder(retrospective.payload | {"knowledge_item_ids": list(retrospective.payload.get("knowledge_item_ids", [])) + [item.id]})
    write_audit(session, tenant_id=actor.tenant_id, case_id=report.case_id, actor=actor.username, actor_id=actor.id, action="knowledge_item.create", object_type="knowledge_item", object_id=item.id, object_version="v1", reason=request.reason, after=serialize_knowledge_item(item), trace_id=trace_id)
    session.commit()
    return serialize_knowledge_item(item)


def get_retrospective_memory_view(session: Session, retrospective_id: str, actor: models.User) -> dict:
    retrospective = _retrospective_or_404(session, retrospective_id)
    report = _report_or_404(session, retrospective.report_id)
    items = _knowledge_items_for_retrospective(session, retrospective.id)
    entries = _library_entries_for_retrospective(session, retrospective.id)
    review = session.get(models.Review, retrospective.review_id) if retrospective.review_id else None
    page_state = "ready"
    degraded = []
    if not items:
        page_state = "empty"
    if retrospective.status == "review_failed":
        page_state = "degraded"
        degraded.append({"code": "RETROSPECTIVE_REVIEW_FAILED", "message": "Retrospective review must pass before memory publication."})
    legacy_page = _memory_page(retrospective, report, items, entries)
    return {
        "page_state": page_state,
        "permissions": {"memory:read": True, "memory:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "retrospectives/knowledge_items/case_library_entries/reviews"},
        "degraded_sources": degraded,
        "audit_context": {"object_type": "retrospective", "object_id": retrospective.id, "object_version": f"v{retrospective.version}"},
        "primary_data": {
            "retrospective": serialize_retrospective(retrospective),
            "report": serialize_report(report),
            "knowledge_items": [serialize_knowledge_item(item) for item in items],
            "case_library_entries": [serialize_case_library_entry(entry) for entry in entries],
            "review": foundation.serialize_review(review) if review else None,
            "legacy_page_view": legacy_page,
        },
        "actions": [
            {"id": "submit-review", "label": "Submit memory review", "method": "POST", "href": f"/api/v1/retrospectives/{retrospective.id}/submit-review", "enabled": retrospective.status in {"draft", "review_failed"}},
            {"id": "publish-memory", "label": "Publish to case library", "method": "POST", "href": f"/api/v1/retrospectives/{retrospective.id}/publish", "enabled": retrospective.status in {"submitted_review", "approved"}},
        ],
    }


def submit_retrospective_review(session: Session, retrospective_id: str, actor: models.User, trace_id: str) -> dict:
    retrospective = _retrospective_or_404(session, retrospective_id)
    items = _knowledge_items_for_retrospective(session, retrospective.id)
    if not items:
        raise api_error(409, "RETROSPECTIVE_KNOWLEDGE_REQUIRED", "Retrospective requires at least one knowledge item.")
    if any(not _source_refs_valid(item.source_refs) for item in items):
        raise api_error(409, "RETROSPECTIVE_SOURCE_REFS_REQUIRED", "All knowledge items require source refs.")
    review = foundation.create_review(
        session,
        schemas.ReviewCreate(
            object_type="retrospective",
            object_id=retrospective.id,
            object_version=f"v{retrospective.version}",
            template_id=RETROSPECTIVE_TEMPLATE_ID,
            payload={"knowledge_item_ids": [item.id for item in items], "source_refs": retrospective.source_refs},
        ),
        actor,
        trace_id,
    )
    retrospective.review_id = review["review_id"]
    retrospective.status = "submitted_review"
    retrospective.payload = jsonable_encoder(retrospective.payload | {"review_id": retrospective.review_id, "submitted_at": utcnow().isoformat()})
    _workflow_run(session, actor, retrospective.case_id, "retrospective_review_submission", f"retrospective-review:{retrospective.id}", trace_id, {"retrospective_id": retrospective.id, "review_id": retrospective.review_id})
    write_audit(session, tenant_id=actor.tenant_id, case_id=retrospective.case_id, actor=actor.username, actor_id=actor.id, action="retrospective_review.submit", object_type="retrospective", object_id=retrospective.id, object_version=f"v{retrospective.version}", after=serialize_retrospective(retrospective), trace_id=trace_id)
    session.commit()
    return review


def publish_retrospective(session: Session, retrospective_id: str, actor: models.User, trace_id: str) -> dict:
    retrospective = _retrospective_or_404(session, retrospective_id)
    if not retrospective.review_id or not _has_passed_review(session, retrospective.review_id):
        raise api_error(409, "RETROSPECTIVE_REVIEW_NOT_PASSED", "Retrospective review gate must pass before memory publication.")
    before = serialize_retrospective(retrospective)
    entries = []
    for item in _knowledge_items_for_retrospective(session, retrospective.id):
        item.status = "published"
        existing = session.execute(select(models.CaseLibraryEntry).where(models.CaseLibraryEntry.knowledge_item_id == item.id)).scalar_one_or_none()
        if existing is not None:
            entries.append(existing)
            continue
        entry = models.CaseLibraryEntry(
            id=_id("CLE"),
            tenant_id=actor.tenant_id,
            case_id=retrospective.case_id,
            retrospective_id=retrospective.id,
            knowledge_item_id=item.id,
            title=_entry_title(item.content),
            status="active",
            tags=jsonable_encoder(_tags_for_item(item)),
            source_refs=jsonable_encoder(item.source_refs),
            payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, "retrospective_id": retrospective.id, "knowledge_item_id": item.id}),
        )
        session.add(entry)
        entries.append(entry)
    retrospective.status = "published"
    retrospective.version += 1
    retrospective.payload = jsonable_encoder(retrospective.payload | {"published_at": utcnow().isoformat(), "case_library_entry_ids": [entry.id for entry in entries]})
    _workflow_run(session, actor, retrospective.case_id, "case_library_publication", f"case-library:{retrospective.id}", trace_id, {"retrospective_id": retrospective.id, "case_library_entry_ids": [entry.id for entry in entries]})
    write_audit(session, tenant_id=actor.tenant_id, case_id=retrospective.case_id, actor=actor.username, actor_id=actor.id, action="retrospective.publish", object_type="retrospective", object_id=retrospective.id, object_version=f"v{retrospective.version}", before=before, after=serialize_retrospective(retrospective), trace_id=trace_id)
    session.commit()
    return serialize_retrospective(retrospective)


def case_library_view(session: Session, actor: models.User, q: str | None = None, status: str | None = None) -> dict:
    entries = list_case_library_entries(session, q=q, status=status)
    applications = list(session.execute(select(models.CaseLibraryApplication).order_by(models.CaseLibraryApplication.updated_at.desc()).limit(20)).scalars())
    page_state = "ready" if entries else "empty"
    return {
        "page_state": page_state,
        "permissions": {"case_library:read": True, "case_library:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "case_library_entries/case_library_applications/knowledge_items"},
        "degraded_sources": [],
        "audit_context": {"object_type": "case_library", "object_id": "global", "object_version": ALGORITHM_VERSION},
        "primary_data": {
            "entries": entries,
            "applications": [serialize_case_library_application(row) for row in applications],
            "legacy_page_view": _library_page(entries),
        },
        "actions": [{"id": "apply-entry", "label": "Apply case suggestion", "method": "POST", "href": "/api/v1/case-library-entries/{id}/apply", "enabled": bool(entries)}],
    }


def list_case_library_entries(session: Session, q: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.CaseLibraryEntry).order_by(models.CaseLibraryEntry.updated_at.desc())
    if status:
        statement = statement.where(models.CaseLibraryEntry.status == status)
    if q:
        pattern = f"%{q.lower()}%"
        statement = statement.where(or_(func.lower(models.CaseLibraryEntry.title).like(pattern), func.lower(models.CaseLibraryEntry.payload.cast(models.String)).like(pattern)))
    return [serialize_case_library_entry(row) for row in session.execute(statement).scalars()]


def get_case_library_entry(session: Session, entry_id: str) -> dict:
    return serialize_case_library_entry(_case_library_entry_or_404(session, entry_id))


def apply_case_library_entry(session: Session, entry_id: str, request: schemas.CaseLibraryApplyCreate, actor: models.User, trace_id: str) -> dict:
    entry = _case_library_entry_or_404(session, entry_id)
    if entry.status != "active":
        raise api_error(409, "CASE_LIBRARY_ENTRY_NOT_ACTIVE", "Only active case library entries can be applied.")
    if session.get(models.Case, request.case_id) is None:
        raise api_error(404, "CASE_NOT_FOUND", "Case does not exist.")
    conflict = _application_conflict(session, entry.id, request.case_id, request.object_type, request.object_id)
    application = models.CaseLibraryApplication(
        id=_id("CLA"),
        tenant_id=actor.tenant_id,
        case_id=request.case_id,
        case_library_entry_id=entry.id,
        target_object_type=request.object_type,
        target_object_id=request.object_id,
        status="blocked_conflict" if conflict["has_conflict"] else "applied",
        conflict_summary=jsonable_encoder(conflict),
        source_refs=jsonable_encoder(entry.source_refs),
        payload=jsonable_encoder({"reason": request.reason, **request.payload, "entry_title": entry.title}),
    )
    session.add(application)
    _workflow_run(session, actor, request.case_id, "case_library_application", f"case-library-apply:{application.id}", trace_id, {"application_id": application.id, "entry_id": entry.id, "status": application.status})
    write_audit(session, tenant_id=actor.tenant_id, case_id=request.case_id, actor=actor.username, actor_id=actor.id, action="case_library.apply", object_type="case_library_application", object_id=application.id, object_version="v1", reason=request.reason, after=serialize_case_library_application(application), trace_id=trace_id)
    session.commit()
    return {"status": application.status, "object_type": "case_library_entry", "object_id": entry.id, "payload": serialize_case_library_application(application)}


def config_admin_view(session: Session, actor: models.User) -> dict:
    versions = [serialize_config_version(row) for row in session.execute(select(models.ConfigVersion).order_by(models.ConfigVersion.updated_at.desc()).limit(50)).scalars()]
    releases = [serialize_config_release(row) for row in session.execute(select(models.ConfigRelease).order_by(models.ConfigRelease.updated_at.desc()).limit(20)).scalars()]
    page_state = "ready" if versions else "empty"
    degraded = [{"code": "CONFIG_REGRESSION_FAILED", "message": "One or more config versions failed regression."} for item in versions if item["status"] == "regression_failed"]
    return {
        "page_state": page_state,
        "permissions": {"config:read": True, "config:write": True, "config:publish": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "config_versions/config_releases/workflow_runs/reviews"},
        "degraded_sources": degraded,
        "audit_context": {"object_type": "config_admin", "object_id": "global", "object_version": ALGORITHM_VERSION},
        "primary_data": {"versions": versions, "releases": releases, "legacy_page_view": _config_page(versions, releases)},
        "actions": [
            {"id": "create-version", "label": "Create config version", "method": "POST", "href": "/api/v1/config/versions", "enabled": True},
            {"id": "run-regression", "label": "Run regression", "method": "POST", "href": "/api/v1/config/versions/{id}/regression-runs", "enabled": bool(versions)},
            {"id": "publish-config", "label": "Publish config", "method": "POST", "href": "/api/v1/config/versions/{id}/publish", "enabled": bool(versions)},
        ],
    }


def list_config_versions(session: Session, config_type: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.ConfigVersion).order_by(models.ConfigVersion.updated_at.desc())
    if config_type:
        statement = statement.where(models.ConfigVersion.config_type == config_type)
    if status:
        statement = statement.where(models.ConfigVersion.status == status)
    return [serialize_config_version(row) for row in session.execute(statement).scalars()]


def create_config_version(session: Session, request: schemas.ConfigVersionCreate, actor: models.User, trace_id: str) -> dict:
    source_refs = request.payload.get("source_refs", []) if isinstance(request.payload, dict) else []
    version = _next_config_version(session, request.config_type)
    impact_scope = _impact_scope(request.config_type, source_refs)
    row = models.ConfigVersion(
        id=_id("CFG"),
        tenant_id=actor.tenant_id,
        config_type=request.config_type,
        version=version,
        status="draft",
        input_refs=jsonable_encoder(source_refs),
        impact_scope=jsonable_encoder(impact_scope),
        payload=jsonable_encoder({"reason": request.reason, **request.payload, "algorithm_version": ALGORITHM_VERSION}),
    )
    session.add(row)
    _workflow_run(session, actor, _config_case_id(session), "config_version_draft", f"config:{row.id}", trace_id, {"config_version_id": row.id, "config_type": request.config_type, "version": version})
    write_audit(session, tenant_id=actor.tenant_id, case_id=None, actor=actor.username, actor_id=actor.id, action="config_version.create", object_type="config_version", object_id=row.id, object_version=version, reason=request.reason, after=serialize_config_version(row), trace_id=trace_id)
    session.commit()
    return serialize_config_version(row)


def run_config_regression(session: Session, config_version_id: str, actor: models.User, trace_id: str) -> dict:
    version = _config_version_or_404(session, config_version_id)
    before = serialize_config_version(version)
    active_entries = session.execute(select(models.CaseLibraryEntry).where(models.CaseLibraryEntry.status == "active")).scalars().all()
    forced_failure = bool(version.payload.get("regression", {}).get("force_fail"))
    passed = bool(active_entries) and not forced_failure
    version.status = "approval_pending" if passed else "regression_failed"
    case_id = active_entries[0].case_id if active_entries else _config_case_id(session)
    run = _workflow_run(
        session,
        actor,
        case_id,
        "config_regression",
        f"config-regression:{version.id}:{version.version}",
        trace_id,
        {"config_version_id": version.id, "case_library_entry_ids": [entry.id for entry in active_entries], "passed": passed},
    )
    version.regression_workflow_run_id = run.id
    version.payload = jsonable_encoder(version.payload | {"regression_result": {"passed": passed, "checked_at": utcnow().isoformat(), "case_library_entry_count": len(active_entries)}})
    write_audit(session, tenant_id=actor.tenant_id, case_id=case_id, actor=actor.username, actor_id=actor.id, action="config_regression.run", object_type="config_version", object_id=version.id, object_version=version.version, before=before, after=serialize_config_version(version), trace_id=trace_id)
    session.commit()
    return serialize_workflow_run(run)


def submit_config_approval(session: Session, config_version_id: str, request: schemas.ConfigApprovalRequest, actor: models.User, trace_id: str) -> dict:
    version = _config_version_or_404(session, config_version_id)
    if not version.payload.get("regression_result", {}).get("passed"):
        raise api_error(409, "CONFIG_REGRESSION_REQUIRED", "Config approval requires a passed regression run.")
    review = foundation.create_review(
        session,
        schemas.ReviewCreate(
            object_type="config_version",
            object_id=version.id,
            object_version=version.version,
            template_id=CONFIG_TEMPLATE_ID,
            payload={"config_type": version.config_type, "impact_scope": version.impact_scope, "regression_workflow_run_id": version.regression_workflow_run_id, "reason": request.reason},
        ),
        actor,
        trace_id,
    )
    version.review_id = review["review_id"]
    version.status = "approval_pending"
    version.payload = jsonable_encoder(version.payload | {"approval_submitted_at": utcnow().isoformat(), "review_id": version.review_id})
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="config_review.submit", object_type="config_version", object_id=version.id, object_version=version.version, reason=request.reason, after=serialize_config_version(version), trace_id=trace_id)
    session.commit()
    return review


def publish_config_version(session: Session, config_version_id: str, actor: models.User, trace_id: str) -> dict:
    version = _config_version_or_404(session, config_version_id)
    if not version.payload.get("regression_result", {}).get("passed"):
        raise api_error(409, "CONFIG_REGRESSION_REQUIRED", "Config publication requires a passed regression run.")
    if not version.review_id or not _has_passed_review(session, version.review_id):
        raise api_error(409, "CONFIG_REVIEW_NOT_PASSED", "Config review gate must pass before publication.")
    before = serialize_config_version(version)
    version.status = "published"
    release = models.ConfigRelease(
        id=_id("CFR"),
        tenant_id=actor.tenant_id,
        config_version_id=version.id,
        status="rollback_available",
        impact_scope=jsonable_encoder(version.impact_scope),
        payload=jsonable_encoder({"published_at": utcnow().isoformat(), "config_type": version.config_type, "version": version.version, "review_id": version.review_id}),
    )
    session.add(release)
    _workflow_run(session, actor, _config_case_id(session), "config_release_publication", f"config-release:{release.id}", trace_id, {"config_version_id": version.id, "config_release_id": release.id})
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="config_version.publish", object_type="config_release", object_id=release.id, object_version=version.version, before=before, after=serialize_config_release(release), trace_id=trace_id)
    session.commit()
    return serialize_config_release(release)


def rollback_config_release(session: Session, config_release_id: str, request: schemas.ConfigRollbackRequest, actor: models.User, trace_id: str) -> dict:
    release = _config_release_or_404(session, config_release_id)
    version = _config_version_or_404(session, release.config_version_id)
    before = serialize_config_release(release)
    release.status = "rolled_back"
    release.impact_scope = jsonable_encoder(
        release.impact_scope
        | {
            "rollback_from_release_id": release.id,
            "rollback_reason": request.reason,
            "affected_objects": release.impact_scope.get("affected_objects", []),
            "requires_revalidation": ["topic_situation", "mainline", "worldline", "report", "retrospective"],
        }
    )
    version.status = "rolled_back"
    _workflow_run(session, actor, _config_case_id(session), "config_release_rollback", f"config-rollback:{release.id}", trace_id, {"config_release_id": release.id, "config_version_id": version.id, "impact_scope": release.impact_scope})
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="config_release.rollback", object_type="config_release", object_id=release.id, object_version=version.version, reason=request.reason, before=before, after=serialize_config_release(release), trace_id=trace_id)
    session.commit()
    return serialize_config_release(release)


def serialize_retrospective(row: models.Retrospective) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "report_id": row.report_id, "case_id": row.case_id, "status": row.status, "version": f"v{row.version}", "review_id": row.review_id, "summary": row.summary, "source_refs": row.source_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_knowledge_item(row: models.KnowledgeItem) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "retrospective_id": row.retrospective_id, "report_id": row.report_id, "case_id": row.case_id, "status": row.status, "content": row.content, "source_refs": row.source_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_case_library_entry(row: models.CaseLibraryEntry) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "case_id": row.case_id, "retrospective_id": row.retrospective_id, "knowledge_item_id": row.knowledge_item_id, "title": row.title, "status": row.status, "tags": row.tags, "source_refs": row.source_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_case_library_application(row: models.CaseLibraryApplication) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "case_id": row.case_id, "case_library_entry_id": row.case_library_entry_id, "target_object_type": row.target_object_type, "target_object_id": row.target_object_id, "status": row.status, "conflict_summary": row.conflict_summary, "source_refs": row.source_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at, "application_id": row.id}


def serialize_config_version(row: models.ConfigVersion) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "config_type": row.config_type, "version": row.version, "status": row.status, "review_id": row.review_id, "regression_workflow_run_id": row.regression_workflow_run_id, "parent_version_id": row.parent_version_id, "input_refs": row.input_refs, "impact_scope": row.impact_scope, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_config_release(row: models.ConfigRelease) -> dict:
    return {"id": row.id, "tenant_id": row.tenant_id, "config_version_id": row.config_version_id, "status": row.status, "impact_scope": row.impact_scope, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_workflow_run(row: models.WorkflowRun) -> dict:
    return {"id": row.id, "case_id": row.case_id, "tenant_id": row.tenant_id, "workflow_name": row.workflow_name, "workflow_id": row.workflow_id, "status": row.status, "started_by": row.started_by, "trace_id": row.trace_id, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def _derive_knowledge_items(session: Session, report: models.Report, retrospective: models.Retrospective, actor: models.User) -> list[models.KnowledgeItem]:
    items = []
    claims = list(session.execute(select(models.ReportClaim).where(models.ReportClaim.report_id == report.id).order_by(models.ReportClaim.position)).scalars())
    tasks = list(session.execute(select(models.Task).where(models.Task.report_id == report.id).order_by(models.Task.created_at)).scalars())
    for claim in claims[:3]:
        item = models.KnowledgeItem(
            id=_id("KI"),
            tenant_id=actor.tenant_id,
            retrospective_id=retrospective.id,
            report_id=report.id,
            case_id=report.case_id,
            status="draft",
            content=f"Evidence-backed claim pattern: {claim.statement}",
            source_refs=jsonable_encoder(_dedupe_refs([{"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"}, {"object_type": "report_claim", "object_id": claim.id}] + list(claim.evidence_refs))),
            payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, "source": "report_claim", "claim": serialize_report_claim(claim)}),
        )
        session.add(item)
        items.append(item)
    for task in tasks[:3]:
        item = models.KnowledgeItem(
            id=_id("KI"),
            tenant_id=actor.tenant_id,
            retrospective_id=retrospective.id,
            report_id=report.id,
            case_id=report.case_id,
            status="draft",
            content=f"Information gap follow-up pattern: {task.title}",
            source_refs=jsonable_encoder(_dedupe_refs([{"object_type": "report", "object_id": report.id, "object_version": f"v{report.current_version}"}, {"object_type": "task", "object_id": task.id}] + list(task.evidence_refs))),
            payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, "source": "task", "task": serialize_task(task)}),
        )
        session.add(item)
        items.append(item)
    if not items:
        raise api_error(409, "RETROSPECTIVE_INPUTS_REQUIRED", "Published report has no claims or tasks for memory extraction.")
    session.flush()
    return items


def _memory_page(retrospective: models.Retrospective, report: models.Report, items: list[models.KnowledgeItem], entries: list[models.CaseLibraryEntry]) -> dict:
    return {
        "id": retrospective.id,
        "case_id": retrospective.case_id,
        "page": "memory",
        "title": f"Memory retrospective - {report.title}",
        "status": retrospective.status,
        "nav": [],
        "hero": {"title": retrospective.summary, "subtitle": report.title, "status": retrospective.status},
        "metrics": [
            {"label": "Knowledge items", "value": len(items), "tone": "green"},
            {"label": "Library entries", "value": len(entries), "tone": "blue"},
            {"label": "Review", "value": retrospective.status, "tone": "amber"},
        ],
        "sections": [
            {"id": "knowledge", "title": "Retrospective knowledge", "kind": "records", "items": [serialize_knowledge_item(item) for item in items]},
            {"id": "library", "title": "Published case library entries", "kind": "records", "items": [serialize_case_library_entry(entry) for entry in entries]},
        ],
    }


def _library_page(entries: list[dict]) -> dict:
    return {
        "id": "case-library",
        "case_id": "global",
        "page": "library",
        "title": "Case library",
        "status": "ready" if entries else "empty",
        "nav": [],
        "hero": {"title": "Case library", "subtitle": "Approved retrospective knowledge only.", "status": "ready" if entries else "empty"},
        "metrics": [{"label": "Entries", "value": len(entries), "tone": "blue"}],
        "sections": [{"id": "apply", "title": "Applicable case memory", "kind": "records", "items": entries}],
    }


def _config_page(versions: list[dict], releases: list[dict]) -> dict:
    return {
        "id": "config-admin",
        "case_id": "global",
        "page": "config",
        "title": "Configuration center",
        "status": "ready" if versions else "empty",
        "nav": [],
        "hero": {"title": "Data source and model configuration", "subtitle": "Versioned, regression-tested, review-gated.", "status": "ready" if versions else "empty"},
        "metrics": [
            {"label": "Versions", "value": len(versions), "tone": "violet"},
            {"label": "Releases", "value": len(releases), "tone": "green"},
        ],
        "sections": [
            {"id": "changes", "title": "Config versions", "kind": "records", "items": versions},
            {"id": "releases", "title": "Releases and rollback", "kind": "records", "items": releases},
        ],
    }


def _retrospective_or_404(session: Session, retrospective_id: str) -> models.Retrospective:
    row = session.get(models.Retrospective, retrospective_id)
    if row is None:
        raise api_error(404, "RETROSPECTIVE_NOT_FOUND", "Retrospective does not exist.")
    return row


def _report_or_404(session: Session, report_id: str | None) -> models.Report:
    row = session.get(models.Report, report_id)
    if row is None:
        raise api_error(404, "REPORT_NOT_FOUND", "Report does not exist.")
    return row


def _case_library_entry_or_404(session: Session, entry_id: str) -> models.CaseLibraryEntry:
    row = session.get(models.CaseLibraryEntry, entry_id)
    if row is None:
        raise api_error(404, "CASE_LIBRARY_ENTRY_NOT_FOUND", "Case library entry does not exist.")
    return row


def _config_version_or_404(session: Session, config_version_id: str) -> models.ConfigVersion:
    row = session.get(models.ConfigVersion, config_version_id)
    if row is None:
        raise api_error(404, "CONFIG_VERSION_NOT_FOUND", "Config version does not exist.")
    return row


def _config_release_or_404(session: Session, config_release_id: str) -> models.ConfigRelease:
    row = session.get(models.ConfigRelease, config_release_id)
    if row is None:
        raise api_error(404, "CONFIG_RELEASE_NOT_FOUND", "Config release does not exist.")
    return row


def _knowledge_items_for_retrospective(session: Session, retrospective_id: str) -> list[models.KnowledgeItem]:
    return list(session.execute(select(models.KnowledgeItem).where(models.KnowledgeItem.retrospective_id == retrospective_id).order_by(models.KnowledgeItem.created_at)).scalars())


def _library_entries_for_retrospective(session: Session, retrospective_id: str) -> list[models.CaseLibraryEntry]:
    return list(session.execute(select(models.CaseLibraryEntry).where(models.CaseLibraryEntry.retrospective_id == retrospective_id).order_by(models.CaseLibraryEntry.created_at)).scalars())


def _has_passed_review(session: Session, review_id: str) -> bool:
    review = session.get(models.Review, review_id)
    return review is not None and foundation.review_gate_check(session, review.id)["passed"] is True


def _source_refs_valid(source_refs: list[dict]) -> bool:
    return bool(source_refs) and all(ref.get("object_type") and ref.get("object_id") for ref in source_refs)


def _entry_title(content: str) -> str:
    return content[:116] + ("..." if len(content) > 116 else "")


def _tags_for_item(item: models.KnowledgeItem) -> list[str]:
    tags = ["retrospective", item.payload.get("source", "knowledge")]
    if "information gap" in item.content.lower():
        tags.append("information_gap")
    return tags


def _application_conflict(session: Session, entry_id: str, case_id: str, object_type: str, object_id: str) -> dict:
    existing = session.execute(
        select(models.CaseLibraryApplication).where(
            models.CaseLibraryApplication.case_library_entry_id == entry_id,
            models.CaseLibraryApplication.case_id == case_id,
            models.CaseLibraryApplication.target_object_type == object_type,
            models.CaseLibraryApplication.target_object_id == object_id,
            models.CaseLibraryApplication.status == "applied",
        )
    ).scalar_one_or_none()
    return {"has_conflict": existing is not None, "existing_application_id": existing.id if existing else None}


def _next_config_version(session: Session, config_type: str) -> str:
    count = session.execute(select(func.count(models.ConfigVersion.id)).where(models.ConfigVersion.config_type == config_type)).scalar_one()
    return f"{config_type}-v{int(count) + 1}.0"


def _impact_scope(config_type: str, source_refs: list[dict]) -> dict:
    affected = {
        "data_source": ["collection_runs", "raw_records", "source_health", "city_overview"],
        "taxonomy": ["topics", "signals", "evidence", "case_library"],
        "model": ["topic_situation", "mainline", "worldline", "report", "retrospective"],
        "agent": ["agent_profiles", "council_sessions", "worldline_runs"],
        "prompt": ["llm_calls", "council_results", "reports"],
    }[config_type]
    return {"config_type": config_type, "affected_objects": affected, "source_refs": source_refs, "rollback_available": True}


def _config_case_id(session: Session) -> str:
    case_id = session.execute(select(models.Case.id).order_by(models.Case.created_at.desc())).scalars().first()
    return case_id or "CASE-CAMPUS-001"


def _workflow_run(session: Session, actor: models.User, case_id: str, workflow_type: str, workflow_id: str, trace_id: str, payload: dict) -> models.WorkflowRun:
    run = models.WorkflowRun(id=_id("WFR"), case_id=case_id, tenant_id=actor.tenant_id, workflow_name=workflow_type, workflow_id=workflow_id, status="completed", started_by=actor.id, trace_id=trace_id, payload=jsonable_encoder(payload | {"algorithm_version": ALGORITHM_VERSION}))
    session.add(run)
    session.flush()
    return run


def _dedupe_refs(refs: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for ref in refs:
        key = (ref.get("object_type"), ref.get("object_id"), ref.get("object_version"))
        if ref.get("object_type") and ref.get("object_id") and key not in seen:
            seen.add(key)
            out.append(ref)
    return out
