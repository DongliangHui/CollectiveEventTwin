from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import adapters, city, data_sources, evidence, foundation, mainline as mainline_service, memory_config as memory_config_service, models, reports as report_service, schemas, services, signals, topic, worldline as worldline_service
from .config import settings
from .database import engine, get_session
from .audit import write_audit
from .search import search_adapter
from .workflow_runtime import execute_p0_workflow

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="CollectiveEventTwin P0 API", version="0.1.0")
WEBHOOK_EXECUTOR = ThreadPoolExecutor(max_workers=100, thread_name_prefix="cet-webhook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_trace_id(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or f"trc-{uuid4().hex[:24]}"
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        error = exc.detail
    else:
        error = {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}
    return JSONResponse(status_code=exc.status_code, content={"error": error, "meta": {}, "trace_id": _trace_id(request)})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in jsonable_encoder(exc.errors()):
        if isinstance(error, dict):
            sanitized = {key: value for key, value in error.items() if key != "input"}
            errors.append(sanitized)
        else:
            errors.append(error)
    payload = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "details": {"errors": errors},
        },
        "meta": {},
        "trace_id": _trace_id(request),
    }
    return JSONResponse(status_code=422, content=payload)


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", f"trc-{uuid4().hex[:24]}")


def _envelope(request: Request, data, meta: dict | None = None) -> dict:
    return {"data": data, "meta": meta or {}, "trace_id": _trace_id(request)}


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def current_user_dependency(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> models.User:
    return foundation.current_user_from_token(session, _bearer_token(authorization))


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_tables:
        models.Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "collective-event-twin-api"}


@app.post("/api/v1/auth/login")
def auth_login(request_body: schemas.LoginRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    return _envelope(
        request,
        foundation.login(
            session,
            username=request_body.username,
            password=request_body.password,
            trace_id=_trace_id(request),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )


@app.post("/api/v1/auth/refresh")
def auth_refresh(request_body: schemas.RefreshRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    return _envelope(request, foundation.refresh_session(session, request_body.refresh_token, _trace_id(request)))


@app.post("/api/v1/auth/logout")
def auth_logout(
    request: Request,
    authorization: str | None = Header(default=None),
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    return _envelope(request, foundation.logout(session, _bearer_token(authorization), current_user, _trace_id(request)))


@app.get("/api/v1/me")
@app.get("/api/v1/auth/me")
def auth_me(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    return _envelope(request, foundation.serialize_user(session, current_user))


@app.get("/api/v1/me/navigation")
def me_navigation(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    return _envelope(request, foundation.navigation_for_user(session, current_user))


@app.get("/api/v1/me/permissions")
def me_permissions(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    return _envelope(request, foundation.current_permissions(session, current_user))


@app.get("/api/v1/auth/permissions")
def auth_permissions(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    return _envelope(request, {"permissions": foundation.permission_codes_for_user(session, current_user.id)})


@app.get("/api/v1/users")
def list_users(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "user:write")
    return _envelope(request, foundation.list_users(session))


@app.post("/api/v1/users")
def create_user(
    request_body: schemas.UserCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "user:write")
    return _envelope(request, foundation.create_user(session, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/users/{user_id}")
def update_user(
    user_id: str,
    request_body: schemas.UserUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "user:write")
    return _envelope(request, foundation.update_user(session, user_id, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/users/{user_id}/roles")
def update_user_roles(
    user_id: str,
    request_body: schemas.UserRolesUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "user:write")
    return _envelope(request, foundation.update_user_roles(session, user_id, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/users/{user_id}/status")
def update_user_status(
    user_id: str,
    request_body: schemas.UserStatusUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "user:write")
    return _envelope(request, foundation.update_user_status(session, user_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/roles")
def list_roles(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "role:write")
    return _envelope(request, foundation.list_roles(session))


@app.post("/api/v1/roles")
def create_role(
    request_body: schemas.RoleCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "role:write")
    return _envelope(request, foundation.create_role(session, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/roles/{role_id}")
def update_role(
    role_id: str,
    request_body: schemas.RoleUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "role:write")
    return _envelope(request, foundation.update_role(session, role_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/audit-logs")
def list_audit_logs(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    limit: int | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "audit:read")
    return _envelope(
        request,
        foundation.list_audit_logs(
            session,
            tenant_id=current_user.tenant_id,
            page=page,
            page_size=page_size,
            limit=limit,
            object_type=object_type,
            object_id=object_id,
            actor_id=actor_id,
            action=action,
        ),
    )


@app.get("/api/v1/audit-logs/{audit_id}")
def get_audit_log(
    audit_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "audit:read")
    return _envelope(request, foundation.get_audit_log(session, audit_id, tenant_id=current_user.tenant_id))


@app.get("/api/v1/review-templates")
def list_review_templates(
    request: Request,
    object_type: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.list_review_templates(session, object_type))


@app.get("/api/v1/reviews")
def list_reviews(
    request: Request,
    status: str | None = None,
    object_type: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.list_reviews(session, status, object_type))


@app.post("/api/v1/reviews")
def create_review(
    request_body: schemas.ReviewCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.create_review(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/reviews/{review_id}")
def get_review(
    review_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.serialize_review(foundation.get_review(session, review_id)))


@app.patch("/api/v1/reviews/{review_id}")
def update_review(
    review_id: str,
    request_body: schemas.ReviewUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.update_review(session, review_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/reviews/{review_id}/gate-check")
def review_gate_check(
    review_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.review_gate_check(session, review_id))


@app.post("/api/v1/reviews/{review_id}/waive")
def waive_review(
    review_id: str,
    request_body: schemas.ReviewWaiveRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:approve")
    return _envelope(request, foundation.waive_review(session, review_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/review-gates")
def create_review_gate(
    request_body: schemas.ReviewGateCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.create_review_gate(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/tasks/{task_id}/review-gates")
def list_task_review_gates(
    task_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.list_review_gates_for_task(session, task_id))


@app.post("/api/v1/review-gates/{review_gate_id}/retest")
def retest_review_gate(
    review_gate_id: str,
    request_body: schemas.ReviewGateRetestRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.retest_review_gate(session, review_gate_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/review-checklists/versions")
def create_review_checklist_version(
    request_body: schemas.ReviewChecklistVersionCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.create_review_checklist_version(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/release/review-gates-summary")
def release_review_gates_summary(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "review:write")
    return _envelope(request, foundation.release_review_gates_summary(session))


@app.get("/api/v1/ops/health")
def ops_health(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_health_summary(session))


@app.get("/api/v1/ops/api-health")
@app.get("/api/v1/ops/health/api")
def ops_api_health(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_api_health())


@app.get("/api/v1/ops/db-health")
@app.get("/api/v1/ops/health/db")
def ops_db_health(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_db_health(session))


@app.get("/api/v1/ops/workers")
@app.get("/api/v1/ops/health/workers")
def ops_workers_health(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_workers_health(session))


@app.get("/api/v1/ops/workflow-runs")
def ops_workflow_runs(
    request: Request,
    limit: int = 20,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_workflow_runs(session, limit))


@app.get("/api/v1/workflow-runs")
def list_workflow_runs(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    object_type: str | None = None,
    object_id: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    limit = max(1, min(page_size, 100))
    return _envelope(
        request,
        foundation.ops_workflow_runs(session, limit=limit, object_type=object_type, object_id=object_id),
        {"page": page, "page_size": limit},
    )


@app.get("/api/v1/ops/error-queue")
def ops_error_queue(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_error_queue(session, limit))


@app.get("/api/v1/ops/retry-queue")
def ops_retry_queue(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_retry_queue(session, limit))


@app.get("/api/v1/dead-letters")
def list_dead_letters(
    request: Request,
    status: str | None = None,
    data_source_id: str | None = None,
    error_code: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    rows, meta = data_sources.list_dead_letters(session, current_user.tenant_id, status=status, data_source_id=data_source_id, error_code=error_code, page=page, page_size=page_size)
    return _envelope(request, rows, meta)


@app.post("/api/v1/dead-letters/{dead_letter_id}/replay")
def replay_dead_letter(
    dead_letter_id: str,
    request_body: schemas.DeadLetterReplayRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.replay_dead_letter(session, dead_letter_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/ops/metrics")
def ops_metrics(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "ops:read")
    return _envelope(request, foundation.ops_metrics(session, current_user, _trace_id(request)))


@app.get("/api/v1/data-source-types")
def list_data_source_types(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.DATA_SOURCE_TYPES)


@app.get("/api/v1/adapters/capabilities")
def list_adapter_capabilities(
    request: Request,
    source_type: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    if source_type:
        try:
            return _envelope(request, [adapters.serialize_adapter(adapters.ADAPTER_REGISTRY[source_type])])
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "ADAPTER_NOT_FOUND", "message": "Adapter is not registered.", "details": {"source_type": source_type}})
    return _envelope(request, adapters.ADAPTER_REGISTRY.to_list())


@app.get("/api/v1/collection-channels")
def list_collection_channels(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    rows = adapters.collection_channel_registry(data_sources.DATA_SOURCE_TYPES)
    warning_count = sum(1 for row in rows if row["warnings"])
    trace_id = _trace_id(request)
    write_audit(
        session,
        tenant_id=current_user.tenant_id,
        actor=current_user.username,
        actor_id=current_user.id,
        action="collection_channel.registry_read",
        object_type="collection_channel_registry",
        object_id="collection-channels",
        after={"total": len(rows), "warning_count": warning_count, "channels": [row["channel"] for row in rows]},
        trace_id=trace_id,
    )
    session.commit()
    return _envelope(request, rows, {"summary": {"total": len(rows), "warning_count": warning_count, "source": "backend_registry"}})


@app.get("/api/v1/collection-channels/adapter-contract")
def validate_collection_channel_adapter_contract(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    result = adapters.validate_channel_adapter_contract(data_source_types=data_sources.DATA_SOURCE_TYPES)
    trace_id = _trace_id(request)
    write_audit(
        session,
        tenant_id=current_user.tenant_id,
        actor=current_user.username,
        actor_id=current_user.id,
        action="collection_channel.adapter_contract_validated",
        object_type="collection_channel_adapter_contract",
        object_id=result["service"],
        after={
            "status": result["status"],
            "adapter_count": result["adapter_count"],
            "checked_channel_count": result["checked_channel_count"],
            "failure_count": result["failure_count"],
            "degraded_channel_count": result["degraded_channel_count"],
        },
        trace_id=trace_id,
    )
    session.commit()
    return _envelope(request, result)


@app.get("/api/v1/collection-channels/error-codes")
def map_collection_channel_error_codes(
    request: Request,
    channel: str | None = None,
    error_code: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    result = adapters.map_channel_error_codes(channel=channel, error_code=error_code)
    trace_id = _trace_id(request)
    write_audit(
        session,
        tenant_id=current_user.tenant_id,
        actor=current_user.username,
        actor_id=current_user.id,
        action="collection_channel.error_codes_mapped",
        object_type="collection_channel_error_codes",
        object_id=result["service"],
        after={
            "requested": result["requested"],
            "status": result["status"],
            "mapping_count": result["summary"]["mapping_count"],
            "registered_mapping_count": result["summary"]["registered_mapping_count"],
            "unknown_count": result["summary"]["unknown_count"],
            "warnings": result["warnings"],
        },
        trace_id=trace_id,
    )
    session.commit()
    return _envelope(request, result)


@app.get("/api/v1/collection-channels/maintenance")
def get_collection_channel_maintenance(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_channel_maintenance(session, current_user, _trace_id(request)))


@app.get("/api/v1/collection-channels/{channel}/schema")
def get_collection_channel_schema(
    channel: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    try:
        schema = adapters.get_collection_channel_schema(channel)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "CHANNEL_SCHEMA_NOT_FOUND", "message": "Collection channel schema is not registered.", "details": {"channel": channel}})
    trace_id = _trace_id(request)
    write_audit(
        session,
        tenant_id=current_user.tenant_id,
        actor=current_user.username,
        actor_id=current_user.id,
        action="collection_channel.schema_read",
        object_type="collection_channel_schema",
        object_id=channel,
        after={"channel": channel, "version": schema["version"], "required_fields": schema["required_fields"]},
        trace_id=trace_id,
    )
    session.commit()
    return _envelope(request, schema)


@app.get("/api/v1/data-sources")
def list_data_sources(
    request: Request,
    source_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    rows, meta = data_sources.list_data_sources(session, current_user.tenant_id, source_type=source_type, status=status, page=page, page_size=page_size)
    return _envelope(request, rows, meta)


@app.post("/api/v1/data-sources")
def create_data_source(
    request_body: schemas.DataSourceCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.create_data_source(session, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/data-sources/{data_source_id}")
def update_data_source(
    data_source_id: str,
    request_body: schemas.DataSourceCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_data_source(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/policy-check")
def check_data_source_policy(
    data_source_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.policy_check(session, data_source_id, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/validate-url")
def validate_data_source_url(
    data_source_id: str,
    request_body: schemas.DataSourceUrlValidationRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.validate_source_url(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.put("/api/v1/data-sources/{data_source_id}/crawl-policy")
def update_data_source_crawl_policy(
    data_source_id: str,
    request_body: schemas.DataSourceCrawlPolicyUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_crawl_policy(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/public-web/discover-links")
def discover_public_web_links(
    data_source_id: str,
    request_body: schemas.PublicWebLinkDiscoveryRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.discover_public_web_links(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.put("/api/v1/data-sources/{data_source_id}/auth")
def update_data_source_auth(
    data_source_id: str,
    request_body: schemas.DataSourceAuthUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_source_auth(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/test-connection")
def test_data_source_connection(
    data_source_id: str,
    request_body: schemas.DataSourceConnectionTestRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.test_official_api_connection(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/object-storage/list")
def list_data_source_object_storage_keys(
    data_source_id: str,
    request_body: schemas.ObjectStorageListRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.list_object_storage_keys(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/versions/publish")
def publish_data_source_version(
    data_source_id: str,
    request: Request,
    request_body: schemas.DataSourceVersionPublishRequest | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.publish_data_source_version(session, data_source_id, request_body or schemas.DataSourceVersionPublishRequest(), current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/versions/{version}/rollback")
def rollback_data_source_version(
    data_source_id: str,
    version: int,
    request: Request,
    request_body: schemas.DataSourceVersionRollbackRequest | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.rollback_data_source_version(session, data_source_id, version, request_body or schemas.DataSourceVersionRollbackRequest(), current_user, _trace_id(request)))


@app.patch("/api/v1/data-sources/{data_source_id}/status")
def update_data_source_status(
    data_source_id: str,
    request_body: schemas.DataSourceStatusUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_data_source_status(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.put("/api/v1/data-sources/{data_source_id}/compliance")
def update_data_source_compliance(
    data_source_id: str,
    request_body: schemas.DataSourceComplianceUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_data_source_compliance(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.put("/api/v1/data-sources/{data_source_id}/pagination")
def update_data_source_pagination(
    data_source_id: str,
    request_body: schemas.DataSourcePaginationUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_pagination_policy(session, data_source_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/data-sources/{data_source_id}/rss/inspect")
def inspect_data_source_rss_feed(
    data_source_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.inspect_rss_feed(session, data_source_id, current_user, _trace_id(request)))


@app.post("/api/v1/webhooks/{source_key}")
async def receive_webhook_payload(
    source_key: str,
    request: Request,
    x_cet_timestamp: str | None = Header(default=None),
    x_cet_delivery_id: str | None = Header(default=None),
    x_cet_signature: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    raw_body = await request.body()
    result = await asyncio.get_running_loop().run_in_executor(
        WEBHOOK_EXECUTOR,
        partial(
            data_sources.receive_webhook_payload,
            session,
            source_key,
            raw_body,
            {
                "x-cet-timestamp": x_cet_timestamp,
                "x-cet-delivery-id": x_cet_delivery_id,
                "x-cet-signature": x_cet_signature,
            },
            _trace_id(request),
        ),
    )
    return _envelope(request, result)


@app.get("/api/v1/source-health")
def list_source_health(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_source_health(session))


@app.get("/api/v1/data-sources/health-view")
def data_sources_health_view(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    health = data_sources.list_source_health(session)
    return _envelope(request, {"page_state": "ready" if health else "empty", "sources": health})


@app.get("/api/v1/data-sources/{data_source_id}/health")
def get_data_source_health(
    data_source_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_data_source_health(session, data_source_id))


@app.get("/api/v1/data-sources/{data_source_id}/cursor-state")
def get_data_source_cursor_state(
    data_source_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_data_source_cursor_state(session, data_source_id, current_user, _trace_id(request)))


@app.get("/api/v1/data-sources/{data_source_id}/rate-limit")
def get_data_source_rate_limit(
    data_source_id: str,
    request: Request,
    channel: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_data_source_rate_limit(session, data_source_id, current_user, channel))


@app.get("/api/v1/collection-channels/{channel}/quality-metrics")
def get_collection_channel_quality_metrics(
    channel: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_channel_quality_metrics(session, channel, current_user, _trace_id(request)))


@app.get("/api/v1/collection-jobs")
def list_collection_jobs(
    request: Request,
    status: str | None = None,
    data_source_id: str | None = None,
    created_by_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    data, meta = data_sources.list_collection_jobs(
        session,
        tenant_id=current_user.tenant_id,
        status=status,
        data_source_id=data_source_id,
        created_by_id=created_by_id,
        page=page,
        page_size=page_size,
    )
    return _envelope(request, data, meta)


@app.post("/api/v1/collection-jobs")
def create_collection_job(
    request_body: schemas.CollectionJobCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.create_collection_job(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/collection-jobs/{collection_job_id}")
def get_collection_job(
    collection_job_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_job(session, collection_job_id, current_user.tenant_id))


@app.patch("/api/v1/collection-jobs/{collection_job_id}")
def update_collection_job(
    collection_job_id: str,
    request_body: schemas.CollectionJobCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_collection_job(session, collection_job_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/collection-jobs/{collection_job_id}/pause")
def pause_collection_job(
    collection_job_id: str,
    request: Request,
    request_body: schemas.CollectionJobControl | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.pause_collection_job(session, collection_job_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/collection-jobs/{collection_job_id}/resume")
def resume_collection_job(
    collection_job_id: str,
    request: Request,
    request_body: schemas.CollectionJobControl | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.resume_collection_job(session, collection_job_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/collection-jobs/{collection_job_id}/runs")
def start_collection_run(
    collection_job_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.start_collection_run(session, collection_job_id, current_user, _trace_id(request)))


@app.post("/api/v1/collection-jobs/{collection_job_id}/file-runs", status_code=201)
def start_file_upload_run(
    collection_job_id: str,
    request_body: schemas.FileRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.start_file_upload_run(session, collection_job_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/collection-runs/{collection_run_id}")
def get_collection_run(
    collection_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_run(session, collection_run_id, current_user.tenant_id))


@app.get("/api/v1/collection-runs/{collection_run_id}/steps")
def get_collection_run_steps(
    collection_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_run_steps(session, collection_run_id, current_user.tenant_id))


@app.get("/api/v1/collection-runs/{collection_run_id}/metrics")
def get_collection_run_metrics(
    collection_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_collection_run_metrics(session, collection_run_id, current_user, _trace_id(request)))


@app.get("/api/v1/cleaning-runs/{cleaning_run_id}/metrics")
def get_cleaning_run_metrics(
    cleaning_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_cleaning_run_metrics(session, cleaning_run_id, current_user, _trace_id(request)))


@app.get("/api/v1/collection-runs")
def list_collection_runs(
    request: Request,
    status: str | None = None,
    data_source_id: str | None = None,
    collection_job_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    data, meta = data_sources.list_collection_runs(
        session,
        tenant_id=current_user.tenant_id,
        status=status,
        data_source_id=data_source_id,
        collection_job_id=collection_job_id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return _envelope(request, data, meta)


@app.post("/api/v1/collection-runs/{collection_run_id}/cancel")
def cancel_collection_run(
    collection_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.cancel_collection_run(session, collection_run_id, current_user, _trace_id(request)))


@app.post("/api/v1/collection-runs/{collection_run_id}/retry")
def retry_collection_run(
    collection_run_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.retry_collection_run(session, collection_run_id, current_user, _trace_id(request)))


@app.post("/api/v1/collection-runs/{collection_run_id}/channel-replay")
def replay_collection_run_from_checkpoint(
    collection_run_id: str,
    request_body: schemas.ChannelReplayRequest,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.replay_channel_run_from_checkpoint(session, collection_run_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/synthetic-scenarios/xian-social-issues")
def generate_xian_synthetic_samples(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.generate_xian_synthetic_samples(session, current_user, _trace_id(request)))


@app.get("/api/v1/import-runs")
def list_import_runs(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_import_runs(session, limit))


@app.post("/api/v1/manual-records", status_code=201)
def create_manual_record(
    request_body: schemas.ManualRecordCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.create_manual_record(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/imports/files")
def import_file(
    request_body: schemas.ImportRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_import(session, request_body, current_user, _trace_id(request), "file"))


@app.post("/api/v1/imports/db-import")
def scan_db_import_table(
    request_body: schemas.DbImportScanCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.scan_db_import_table(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/imports/object-storage")
def scan_object_storage_prefix(
    request_body: schemas.ObjectStorageScanCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.scan_object_storage_prefix(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/uploads", status_code=201)
async def upload_file(
    request: Request,
    data_source_id: str = Form(...),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    is_synthetic: bool = Form(default=False),
    source_uri: str | None = Form(default=None),
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    content = await file.read()
    try:
        result = data_sources.receive_file_upload(
            session,
            data_source_id=data_source_id,
            file_name=file.filename or "upload.bin",
            mime_type=file.content_type,
            content=content,
            actor=current_user,
            trace_id=_trace_id(request),
            title=title,
            is_synthetic=is_synthetic,
            source_uri=source_uri,
        )
    finally:
        await file.close()
    return _envelope(request, result)


@app.post("/api/v1/imports/public-web")
def import_public_web(
    request_body: schemas.ImportRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_import(session, request_body, current_user, _trace_id(request), "public_web"))


@app.post("/api/v1/imports/official-api")
def import_official_api(
    request_body: schemas.ImportRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_import(session, request_body, current_user, _trace_id(request), "official_api"))


@app.post("/api/v1/imports/rss")
def import_rss(
    request_body: schemas.ImportRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_import(session, request_body, current_user, _trace_id(request), "rss"))


@app.post("/api/v1/imports/media")
def import_media(
    request_body: schemas.ImportRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_import(session, request_body, current_user, _trace_id(request), "media"))


@app.get("/api/v1/raw-records")
def list_raw_records(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_raw_records(session, current_user, limit))


@app.post("/api/v1/raw-records/batches", status_code=201)
def create_raw_record_batch(
    request_body: schemas.RawRecordBatchCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.create_raw_record_batch(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/raw-records/{raw_record_id}")
def get_raw_record(
    raw_record_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.get_raw_record(session, raw_record_id, current_user))


@app.get("/api/v1/raw-records/{raw_record_id}/redacted-export")
def export_raw_record_redacted(
    raw_record_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.export_raw_record_redacted(session, raw_record_id, current_user, _trace_id(request)))


@app.get("/api/v1/raw-records/{raw_record_id}/original")
def get_raw_record_original(
    raw_record_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:raw_original")
    return _envelope(request, data_sources.get_raw_record_original(session, raw_record_id, current_user, _trace_id(request)))


@app.post("/api/v1/raw-records/{raw_record_id}/labels")
def add_raw_record_label(
    raw_record_id: str,
    request_body: schemas.RawRecordLabelCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.add_raw_record_label(session, raw_record_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/clean-records")
def list_clean_records(
    request: Request,
    status: str | None = None,
    data_source_id: str | None = None,
    source_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    rows, meta = data_sources.list_clean_records(
        session,
        current_user,
        status=status,
        data_source_id=data_source_id,
        source_type=source_type,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
        trace_id=_trace_id(request),
    )
    return _envelope(request, rows, meta)


@app.get("/api/v1/clean-records/{clean_record_id}")
def get_clean_record_detail(
    clean_record_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(
        request,
        data_sources.get_clean_record_detail(session, clean_record_id, current_user, _trace_id(request)),
        {"page_state": "ready", "required_permission": "data_source:read", "source": "postgresql"},
    )


@app.patch("/api/v1/clean-records/{clean_record_id}/status")
def update_clean_record_status(
    clean_record_id: str,
    request_body: schemas.CleanRecordStatusUpdate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.update_clean_record_status(session, clean_record_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/clean-records/{clean_record_id}/dedupe-decision")
def create_clean_record_dedupe_decision(
    clean_record_id: str,
    request_body: schemas.DedupeDecisionCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.apply_dedupe_decision(session, clean_record_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/normalization-runs")
def list_normalization_runs(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_processing_runs(session, "normalization", limit))


@app.post("/api/v1/normalization-runs")
def create_normalization_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_normalization(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/normalization-runs/datetime", status_code=201)
def create_datetime_normalization_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_datetime_normalization(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/normalization-runs/location", status_code=201)
def create_location_normalization_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_location_normalization(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/normalization-runs/source-trust", status_code=201)
def create_source_trust_assignment_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_source_trust_assignment(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/detector-runs/sensitive-fields", status_code=201)
def create_sensitive_fields_detector_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_sensitive_field_detection(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/redaction-runs/sensitive-fields", status_code=201)
def create_sensitive_fields_redaction_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_sensitive_field_redaction(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/html-main-content", status_code=201)
def create_html_main_content_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_html_main_content_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/json-by-mapping", status_code=201)
def create_json_by_mapping_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_json_by_mapping_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/rss-item", status_code=201)
def create_rss_item_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_rss_item_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/csv-file", status_code=201)
def create_csv_file_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_csv_file_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/xlsx-file", status_code=201)
def create_xlsx_file_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_xlsx_file_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/pdf-text", status_code=201)
def create_pdf_text_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_pdf_text_parser(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/parser-runs/docx-text", status_code=201)
def create_docx_text_parser_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_docx_text_parser(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/deduplication-runs")
def list_deduplication_runs(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_processing_runs(session, "deduplication", limit))


@app.post("/api/v1/deduplication-runs")
def create_deduplication_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_deduplication(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/deduplication-runs/semantic")
def create_semantic_deduplication_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_semantic_deduplication(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/data-quality-runs")
def list_data_quality_runs(
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.list_processing_runs(session, "quality", limit, tenant_id=current_user.tenant_id))


@app.post("/api/v1/data-quality-runs")
def create_data_quality_run(
    request_body: schemas.RawRecordScope,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:write")
    return _envelope(request, data_sources.run_data_quality(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/data-quality/issues")
def list_data_quality_issues(
    request: Request,
    issue_type: str | None = None,
    severity: str | None = None,
    data_quality_run_id: str | None = None,
    raw_record_id: str | None = None,
    data_source_id: str | None = None,
    source_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    rows, meta = data_sources.list_quality_issues(
        session,
        current_user,
        issue_type=issue_type,
        severity=severity,
        data_quality_run_id=data_quality_run_id,
        raw_record_id=raw_record_id,
        data_source_id=data_source_id,
        source_type=source_type,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
        trace_id=_trace_id(request),
    )
    return _envelope(request, rows, meta)


@app.get("/api/v1/lineage")
def get_lineage(
    request: Request,
    object_type: str | None = None,
    object_id: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "data_source:read")
    return _envelope(request, data_sources.lineage(session, object_type, object_id, current_user))


@app.get("/api/v1/cities")
def list_cities(
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.list_cities(session, current_user, _trace_id(request)))


@app.get("/api/v1/cities/{city_id}/overview")
def get_city_overview(
    city_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_overview(session, city_id, current_user, _trace_id(request)))


@app.get("/api/v1/cities/{city_id}/map-layers")
def get_city_map_layers(
    city_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_map_layers(session, city_id, current_user, _trace_id(request)))


@app.patch("/api/v1/cities/{city_id}/map-state")
def patch_city_map_state(
    city_id: str,
    request_body: schemas.CityMapStateWrite,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:write")
    return _envelope(request, city.update_city_map_state(session, city_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/cities/{city_id}/events")
def list_city_events(
    city_id: str,
    request: Request,
    status: str | None = None,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.list_city_events(session, city_id, current_user, _trace_id(request), limit=limit, status=status))


@app.get("/api/v1/cities/{city_id}/events/rankings")
def list_city_event_rankings(
    city_id: str,
    request: Request,
    rank_mode: str = "heat",
    limit: int = 20,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_event_rankings(session, city_id, current_user, _trace_id(request), rank_mode=rank_mode, limit=limit))


@app.get("/api/v1/cities/{city_id}/source-health-view")
def get_city_source_health_view(
    city_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_source_health_view(session, city_id, current_user, _trace_id(request)))


@app.get("/api/v1/cities/{city_id}/media-evidence")
def list_city_media_evidence(
    city_id: str,
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_media_evidence(session, city_id, current_user, _trace_id(request), limit=limit))


@app.get("/api/v1/cities/{city_id}/timeline")
def get_city_timeline(
    city_id: str,
    request: Request,
    limit: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.city_timeline(session, city_id, current_user, _trace_id(request), limit=limit))


@app.get("/api/v1/city-events/{city_event_id}")
def get_city_event(
    city_event_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:read")
    return _envelope(request, city.get_city_event(session, city_event_id, current_user, _trace_id(request)))


@app.post("/api/v1/city-events/{city_event_id}/create-topic", status_code=201)
def create_topic_from_city_event(
    city_event_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "city:write")
    return _envelope(request, city.create_topic_from_city_event(session, city_event_id, current_user, _trace_id(request)))


@app.get("/api/v1/topics")
def list_topics(
    request: Request,
    city_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.list_topics(session, current_user, city_id=city_id, status=status, page=page, page_size=page_size))


@app.post("/api/v1/topics", status_code=201)
def create_topic(
    request_body: schemas.TopicCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:write")
    return _envelope(request, topic.create_topic(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/topics/{topic_id}")
def get_topic(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.get_topic(session, topic_id))


@app.patch("/api/v1/topics/{topic_id}")
def update_topic(
    topic_id: str,
    request_body: schemas.TopicPatch,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:write")
    return _envelope(request, topic.update_topic(session, topic_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/topics/{topic_id}/situation-view")
def get_topic_situation_view(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.situation_view(session, topic_id, current_user, _trace_id(request)))


@app.get("/api/v1/topics/{topic_id}/source-breakdown")
def get_topic_source_breakdown(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.source_breakdown(session, topic_id))


@app.get("/api/v1/topics/{topic_id}/spread-paths")
def get_topic_spread_paths(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.spread_paths(session, topic_id))


@app.get("/api/v1/topics/{topic_id}/emotion-stance")
def get_topic_emotion_stance(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.emotion_stance(session, topic_id))


@app.get("/api/v1/topics/{topic_id}/candidate-mainlines")
def get_topic_candidate_mainlines(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "topic:read")
    return _envelope(request, topic.candidate_mainlines(session, topic_id))


@app.post("/api/v1/extraction-runs", status_code=201)
def create_extraction_run(
    request_body: schemas.ExtractionRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:write")
    return _envelope(request, signals.create_extraction_run(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/topics/{topic_id}/signal-workbench-view")
def get_signal_workbench_view(
    topic_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:read")
    return _envelope(request, signals.get_workbench_view(session, topic_id, current_user))


@app.get("/api/v1/signals")
def list_signals(
    request: Request,
    topic_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:read")
    return _envelope(request, signals.list_signals(session, topic_id=topic_id, status=status, q=q, page=page, page_size=page_size))


@app.get("/api/v1/signals/{signal_id}")
def get_signal(
    signal_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:read")
    return _envelope(request, signals.get_signal(session, signal_id))


@app.post("/api/v1/signal-packages", status_code=201)
def create_signal_package(
    request_body: schemas.SignalPackageCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:write")
    return _envelope(request, signals.create_signal_package(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/signal-packages/{signal_package_id}")
def get_signal_package(
    signal_package_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:read")
    return _envelope(request, signals.get_signal_package(session, signal_package_id))


@app.post("/api/v1/signal-packages/{signal_package_id}/items", status_code=201)
def add_signal_package_item(
    signal_package_id: str,
    request_body: schemas.SignalPackageItemWrite,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:write")
    return _envelope(request, signals.add_signal_package_item(session, signal_package_id, request_body, current_user, _trace_id(request)))


@app.delete("/api/v1/signal-packages/{signal_package_id}/items")
def remove_signal_package_item(
    signal_package_id: str,
    signal_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "signal:write")
    return _envelope(request, signals.remove_signal_package_item(session, signal_package_id, signal_id, current_user, _trace_id(request)))


@app.post("/api/v1/evidence-candidates", status_code=201)
def create_evidence_candidates(
    request_body: schemas.EvidenceCandidateCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_evidence_candidates(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/evidence")
def list_evidence(
    request: Request,
    topic_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:read")
    return _envelope(request, evidence.list_evidence(session, topic_id=topic_id, status=status, page=page, page_size=page_size))


@app.get("/api/v1/evidence/{evidence_id}")
def get_evidence(
    evidence_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:read")
    return _envelope(request, evidence.get_evidence_detail(session, evidence_id))


@app.post("/api/v1/evidence/{evidence_id}/attachments", status_code=201)
def create_evidence_attachment(
    evidence_id: str,
    request_body: schemas.EvidenceAttachmentCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_evidence_attachment(session, evidence_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/evidence-reviews/{evidence_review_id}/review-view")
def get_evidence_review_view(
    evidence_review_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:read")
    return _envelope(request, evidence.review_view(session, evidence_review_id, current_user))


@app.patch("/api/v1/evidence-reviews/{evidence_review_id}")
def update_evidence_review(
    evidence_review_id: str,
    request_body: schemas.EvidenceReviewPatch,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:review")
    return _envelope(request, evidence.update_evidence_review(session, evidence_review_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/evidence-media-links", status_code=201)
def create_evidence_media_link(
    request_body: schemas.EvidenceMediaLinkWrite,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_evidence_media_link(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/media-processing-runs", status_code=201)
def create_media_processing_run(
    request_body: schemas.MediaProcessingRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_media_processing_run(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/media-segment-runs", status_code=201)
def create_media_segment_run(
    request_body: schemas.MediaProcessingRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    request_body.processor = "segment_detect"
    return _envelope(request, evidence.create_media_processing_run(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/live-segment-runs", status_code=201)
def create_live_segment_run(
    request_body: schemas.MediaProcessingRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    request_body.processor = "live_segment"
    return _envelope(request, evidence.create_media_processing_run(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/redaction-runs", status_code=201)
def create_redaction_run(
    request_body: schemas.RunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_redaction_run(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/risk-factor-runs", status_code=201)
def create_risk_factor_run(
    request_body: schemas.RiskFactorRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_risk_factor_run(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/risk-factors")
def list_risk_factors(
    request: Request,
    topic_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:read")
    return _envelope(request, evidence.list_risk_factors(session, topic_id=topic_id, status=status, category=category, page=page, page_size=page_size))


@app.patch("/api/v1/risk-factors/{risk_factor_id}")
def update_risk_factor(
    risk_factor_id: str,
    request_body: schemas.RiskFactorUpdate,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    token = _bearer_token(authorization)
    if token is None:
        factor = services.update_factor_status(session, risk_factor_id, request_body.status, request_body.actor, request_body.reason)
        return schemas.RiskFactorOut.model_validate(factor).model_dump()
    current_user = foundation.current_user_from_token(session, token)
    foundation.require_permission(session, current_user, "evidence:review")
    return _envelope(request, evidence.update_risk_factor(session, risk_factor_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/risk-factors/{risk_factor_id}/confidence-adjustments", status_code=201)
def adjust_risk_factor_confidence(
    risk_factor_id: str,
    request_body: schemas.RiskFactorConfidenceAdjustment,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:review")
    return _envelope(request, evidence.adjust_risk_factor_confidence(session, risk_factor_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/conflict-detection-runs", status_code=201)
def create_conflict_detection_run(
    request_body: schemas.ConflictDetectionRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "evidence:write")
    return _envelope(request, evidence.create_conflict_detection_run(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/mainlines")
def list_mainlines(
    request: Request,
    case_id: str | None = None,
    topic_id: str | None = None,
    status: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:read")
    return _envelope(request, mainline_service.list_mainlines(session, case_id=case_id, topic_id=topic_id, status=status))


@app.get("/api/v1/mainlines/{mainline_id}")
def get_mainline(
    mainline_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:read")
    return _envelope(request, mainline_service.get_mainline(session, mainline_id))


@app.get("/api/v1/mainlines/{mainline_id}/builder-view")
def get_mainline_builder_view(
    mainline_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:read")
    return _envelope(request, mainline_service.builder_view(session, mainline_id, current_user))


@app.patch("/api/v1/mainline-nodes/{mainline_node_id}")
def patch_mainline_node(
    mainline_node_id: str,
    request_body: schemas.MainlineNodePatch,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.update_mainline_node(session, mainline_node_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/mainlines/{mainline_id}/signals")
def update_mainline_signal(
    mainline_id: str,
    request_body: schemas.MainlineSignalWrite,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.update_mainline_signal(session, mainline_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/mainlines/{mainline_id}/quality-check")
def run_mainline_quality_check(
    mainline_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.run_quality_check(session, mainline_id, current_user, _trace_id(request)))


@app.post("/api/v1/world-states", status_code=201)
def create_world_state(
    request_body: schemas.WorldStateCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.create_world_state(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/world-states/{world_state_id}")
def get_world_state(
    world_state_id: str,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:read")
    return _envelope(request, mainline_service.get_world_state(session, world_state_id))


@app.post("/api/v1/case-graph-runs", status_code=201)
def create_case_graph_run(
    request_body: schemas.CaseGraphRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.create_case_graph_run(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/stakeholder-runs", status_code=201)
def create_stakeholder_run(
    request_body: schemas.StakeholderRunCreate,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:write")
    return _envelope(request, mainline_service.create_stakeholder_run(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/stakeholders")
def list_stakeholders(
    request: Request,
    topic_id: str | None = None,
    mainline_id: str | None = None,
    status: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "mainline:read")
    return _envelope(request, mainline_service.list_stakeholders(session, topic_id=topic_id, mainline_id=mainline_id, status=status))


@app.patch("/api/v1/stakeholders/{stakeholder_id}/review")
def review_stakeholder(
    stakeholder_id: str,
    request_body: schemas.StakeholderReviewPatch,
    request: Request,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "stakeholder:review")
    return _envelope(request, mainline_service.review_stakeholder(session, stakeholder_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/worldline-runs", status_code=201)
def create_worldline_run(request_body: schemas.WorldlineRunCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.create_worldline_run(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/worldline-runs/{worldline_run_id}")
def get_worldline_run(worldline_run_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.get_worldline_run(session, worldline_run_id))


@app.get("/api/v1/worldline-runs/{worldline_run_id}/simulation-view")
def get_worldline_simulation_view(worldline_run_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.simulation_view(session, worldline_run_id, current_user))


@app.post("/api/v1/worldline-runs/{worldline_run_id}/interventions", status_code=201)
def add_worldline_intervention(worldline_run_id: str, request_body: schemas.WorldlineInterventionCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.add_worldline_intervention(session, worldline_run_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/llm-providers")
def list_llm_providers(request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.list_llm_providers(session, current_user))


@app.get("/api/v1/llm-calls")
def list_llm_calls(request: Request, object_id: str | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.list_llm_calls(session, object_id=object_id))


@app.get("/api/v1/prompt-templates")
def list_prompt_templates(request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.list_prompt_templates(session, current_user))


@app.post("/api/v1/prompt-templates", status_code=201)
def create_prompt_template(request_body: dict, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.create_prompt_template(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/agent-templates")
def list_agent_templates(request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.list_agent_templates(session, current_user))


@app.post("/api/v1/agent-profiles", status_code=201)
def create_agent_profile(request_body: schemas.AgentProfileCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.create_agent_profile(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/agent-profiles/{agent_profile_id}")
def get_agent_profile(agent_profile_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.get_agent_profile(session, agent_profile_id))


@app.post("/api/v1/agent-profiles/{agent_profile_id}/files", status_code=201)
def create_agent_profile_files(agent_profile_id: str, request_body: schemas.AgentProfileFilesWrite, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.create_agent_profile_files(session, agent_profile_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/council-sessions", status_code=201)
def create_council_session(request_body: schemas.CouncilSessionCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.create_council_session(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/council-sessions/{council_session_id}/council-view")
def get_council_view(council_session_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:read")
    return _envelope(request, worldline_service.council_view(session, council_session_id, current_user))


@app.post("/api/v1/council-sessions/{council_session_id}/run")
def run_council_session(council_session_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.run_council(session, council_session_id, current_user, _trace_id(request)))


@app.post("/api/v1/council-results/{council_result_id}/apply")
def apply_council_result(council_result_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "worldline:write")
    return _envelope(request, worldline_service.apply_council_result(session, council_result_id, current_user, _trace_id(request)))


@app.get("/api/v1/reports")
def list_reports(
    request: Request,
    topic_id: str | None = None,
    status: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "report:read")
    return _envelope(request, report_service.list_reports(session, topic_id=topic_id, status=status))


@app.post("/api/v1/reports", status_code=201)
def create_report_draft(request_body: schemas.ReportCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:write")
    return _envelope(request, report_service.create_report_draft(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/reports/{report_id}")
def get_report(report_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:read")
    return _envelope(request, report_service.get_report(session, report_id))


@app.patch("/api/v1/reports/{report_id}")
def update_report(report_id: str, request_body: schemas.ReportPatch, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:write")
    return _envelope(request, report_service.update_report(session, report_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/reports/{report_id}/brief-view")
def get_report_brief_view(report_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:read")
    return _envelope(request, report_service.brief_view(session, report_id, current_user))


@app.post("/api/v1/reports/{report_id}/submit-review", status_code=201)
def submit_report_review(report_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:write")
    return _envelope(request, report_service.submit_report_review(session, report_id, current_user, _trace_id(request)))


@app.post("/api/v1/reports/{report_id}/publish")
def publish_report(report_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:write")
    return _envelope(request, report_service.publish_report(session, report_id, current_user, _trace_id(request)))


@app.post("/api/v1/reports/{report_id}/exports", status_code=201)
def export_report(report_id: str, request_body: schemas.ReportExportCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "report:write")
    return _envelope(request, report_service.export_report(session, report_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/tasks")
def list_tasks(
    request: Request,
    report_id: str | None = None,
    status: str | None = None,
    current_user: models.User = Depends(current_user_dependency),
    session: Session = Depends(get_session),
) -> dict:
    foundation.require_permission(session, current_user, "task:read")
    return _envelope(request, report_service.list_tasks(session, report_id=report_id, status=status))


@app.post("/api/v1/tasks", status_code=201)
def create_task(
    request_body: schemas.TaskCreate,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    token = _bearer_token(authorization)
    if token is None:
        if request_body.case_id is None:
            raise HTTPException(status_code=422, detail="case_id is required for legacy task creation.")
        task = services.create_task(session, request_body.case_id, request_body.title, request_body.owner, request_body.due_label, request_body.status, request_body.payload, request_body.actor)
        return JSONResponse(status_code=200, content=jsonable_encoder(schemas.TaskOut.model_validate(task).model_dump()))
    current_user = foundation.current_user_from_token(session, token)
    foundation.require_permission(session, current_user, "task:write")
    return _envelope(request, report_service.create_task(session, request_body, current_user, _trace_id(request)))


@app.patch("/api/v1/tasks/{task_id}")
def update_task(
    task_id: str,
    request_body: schemas.TaskUpdate,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    token = _bearer_token(authorization)
    if token is None:
        task = services.update_task_status(session, task_id, request_body.status, request_body.actor, request_body.reason)
        return schemas.TaskOut.model_validate(task).model_dump()
    current_user = foundation.current_user_from_token(session, token)
    foundation.require_permission(session, current_user, "task:write")
    return _envelope(request, report_service.update_task_status(session, task_id, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/retrospectives", status_code=201)
def create_retrospective(request_body: schemas.RetrospectiveCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "memory:write")
    return _envelope(request, memory_config_service.create_retrospective(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/retrospectives/{retrospective_id}/memory-view")
def get_retrospective_memory_view(retrospective_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "memory:read")
    return _envelope(request, memory_config_service.get_retrospective_memory_view(session, retrospective_id, current_user))


@app.post("/api/v1/retrospectives/{retrospective_id}/submit-review", status_code=201)
def submit_retrospective_review(retrospective_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "memory:write")
    return _envelope(request, memory_config_service.submit_retrospective_review(session, retrospective_id, current_user, _trace_id(request)))


@app.post("/api/v1/retrospectives/{retrospective_id}/publish")
def publish_retrospective(retrospective_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "memory:write")
    return _envelope(request, memory_config_service.publish_retrospective(session, retrospective_id, current_user, _trace_id(request)))


@app.post("/api/v1/knowledge-items", status_code=201)
def create_knowledge_item(request_body: schemas.KnowledgeItemCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "memory:write")
    return _envelope(request, memory_config_service.create_knowledge_item(session, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/cases/library-view")
def get_case_library_view(request: Request, q: str | None = None, status: str | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "case_library:read")
    return _envelope(request, memory_config_service.case_library_view(session, current_user, q=q, status=status))


@app.get("/api/v1/case-library-entries")
def list_case_library_entries(request: Request, q: str | None = None, status: str | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "case_library:read")
    return _envelope(request, memory_config_service.list_case_library_entries(session, q=q, status=status))


@app.get("/api/v1/case-library-entries/{case_library_entry_id}")
def get_case_library_entry(case_library_entry_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "case_library:read")
    return _envelope(request, memory_config_service.get_case_library_entry(session, case_library_entry_id))


@app.post("/api/v1/case-library-entries/{case_library_entry_id}/apply")
def apply_case_library_entry(case_library_entry_id: str, request_body: schemas.CaseLibraryApplyCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "case_library:write")
    return _envelope(request, memory_config_service.apply_case_library_entry(session, case_library_entry_id, request_body, current_user, _trace_id(request)))


@app.get("/api/v1/config/admin-view")
def get_config_admin_view(request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:read")
    return _envelope(request, memory_config_service.config_admin_view(session, current_user))


@app.get("/api/v1/config/versions")
def list_config_versions(request: Request, config_type: str | None = None, status: str | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:read")
    return _envelope(request, memory_config_service.list_config_versions(session, config_type=config_type, status=status))


@app.post("/api/v1/config/versions", status_code=201)
def create_config_version(request_body: schemas.ConfigVersionCreate, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:write")
    return _envelope(request, memory_config_service.create_config_version(session, request_body, current_user, _trace_id(request)))


@app.post("/api/v1/config/versions/{config_version_id}/regression-runs", status_code=201)
def run_config_regression(config_version_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:write")
    return _envelope(request, memory_config_service.run_config_regression(session, config_version_id, current_user, _trace_id(request)))


@app.post("/api/v1/config/versions/{config_version_id}/submit-approval", status_code=201)
def submit_config_approval(config_version_id: str, request: Request, request_body: schemas.ConfigApprovalRequest | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:write")
    return _envelope(request, memory_config_service.submit_config_approval(session, config_version_id, request_body or schemas.ConfigApprovalRequest(), current_user, _trace_id(request)))


@app.post("/api/v1/config/versions/{config_version_id}/publish")
def publish_config_version(config_version_id: str, request: Request, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:publish")
    return _envelope(request, memory_config_service.publish_config_version(session, config_version_id, current_user, _trace_id(request)))


@app.post("/api/v1/config/releases/{config_release_id}/rollback")
def rollback_config_release(config_release_id: str, request: Request, request_body: schemas.ConfigRollbackRequest | None = None, current_user: models.User = Depends(current_user_dependency), session: Session = Depends(get_session)) -> dict:
    foundation.require_permission(session, current_user, "config:publish")
    return _envelope(request, memory_config_service.rollback_config_release(session, config_release_id, request_body or schemas.ConfigRollbackRequest(), current_user, _trace_id(request)))


@app.post("/api/v1/admin/seed")
def seed(request: schemas.SeedRequest, session: Session = Depends(get_session)) -> dict[str, int]:
    return services.seed_p0(session, request.fixture)


@app.get("/api/v1/cases", response_model=list[schemas.CaseOut])
def cases(session: Session = Depends(get_session)):
    return services.list_cases(session)


@app.get("/api/v1/search", response_model=list[schemas.SearchResultOut])
def search(q: str, limit: int = 20, session: Session = Depends(get_session)):
    return search_adapter.search(session, q, limit)


@app.get("/api/v1/cases/{case_id}", response_model=schemas.ClosedLoopOut)
def case_bundle(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)


@app.get("/api/v1/cases/{case_id}/pages/{page}", response_model=schemas.PageViewOut)
def case_page(case_id: str, page: str, session: Session = Depends(get_session)):
    return services.get_page_view(session, case_id, page)


@app.get("/api/v1/cases/{case_id}/signals", response_model=list[schemas.SignalOut])
def case_signals(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["signals"]


@app.get("/api/v1/cases/{case_id}/sources", response_model=list[schemas.SourceRecordOut])
def case_sources(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["source_records"]


@app.get("/api/v1/cases/{case_id}/evidence", response_model=list[schemas.EvidenceOut])
def case_evidence(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["evidence"]


@app.get("/api/v1/cases/{case_id}/risk-factors", response_model=list[schemas.RiskFactorOut])
def case_risk_factors(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["risk_factors"]


@app.get("/api/v1/cases/{case_id}/mainline", response_model=schemas.MainlineOut | None)
def case_mainline(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["mainline"]


@app.get("/api/v1/cases/{case_id}/worldline", response_model=list[schemas.WorldlineNodeOut])
def case_worldline(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["worldline_nodes"]


@app.get("/api/v1/cases/{case_id}/report", response_model=schemas.ReportOut | None)
def case_report(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["report"]


@app.get("/api/v1/cases/{case_id}/audit", response_model=list[schemas.AuditLogOut])
def case_audit(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["audit"]


@app.get("/api/v1/cases/{case_id}/workflow-runs", response_model=list[schemas.WorkflowRunOut])
def case_workflow_runs(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["workflow_runs"]


@app.get("/api/v1/map-layers/{case_id}")
def case_map_layers(case_id: str, session: Session = Depends(get_session)):
    return services.map_layers(session, case_id)


@app.patch("/api/v1/evidence/{evidence_id}", response_model=schemas.EvidenceOut)
def update_evidence(evidence_id: str, update: schemas.EvidenceUpdate, session: Session = Depends(get_session)):
    return services.update_evidence_status(session, evidence_id, update.status, update.actor, update.reason)


@app.patch("/api/v1/signals/{signal_id}", response_model=schemas.SignalOut)
def update_signal(signal_id: str, update: schemas.SignalUpdate, session: Session = Depends(get_session)):
    return services.update_signal(session, signal_id, update.status, update.priority, update.actor, update.reason)


@app.get("/api/v1/signals/{signal_id}/similar", response_model=list[schemas.SignalOut])
def similar_signals(signal_id: str, limit: int = 6, session: Session = Depends(get_session)):
    return services.similar_signals(session, signal_id, limit)


@app.patch("/api/v1/risk-factors/{factor_id}", response_model=schemas.RiskFactorOut)
def update_factor(factor_id: str, update: schemas.RiskFactorUpdate, session: Session = Depends(get_session)):
    return services.update_factor_status(session, factor_id, update.status, update.actor, update.reason)


@app.post("/api/v1/mainlines")
def create_mainline(
    request_body: schemas.MainlineCreate,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _bearer_token(authorization)
    if token:
        current_user = foundation.current_user_from_token(session, token)
        foundation.require_permission(session, current_user, "mainline:write")
        data = mainline_service.create_mainline_draft(session, request_body, current_user, _trace_id(request))
        return JSONResponse(status_code=201, content=jsonable_encoder(_envelope(request, data)))
    if not request_body.case_id:
        raise HTTPException(status_code=422, detail="case_id is required for legacy mainline creation.")
    return services.create_mainline(session, request_body.case_id, request_body.title, request_body.confidence, request_body.status, request_body.payload, request_body.actor)


@app.patch("/api/v1/mainlines/{mainline_id}")
def update_mainline(
    mainline_id: str,
    request_body: schemas.MainlinePatch,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _bearer_token(authorization)
    if token:
        current_user = foundation.current_user_from_token(session, token)
        foundation.require_permission(session, current_user, "mainline:write")
        updated = services.update_mainline(session, mainline_id, request_body.title, request_body.confidence, request_body.status, request_body.payload, current_user.username, request_body.reason)
        return _envelope(request, mainline_service.serialize_mainline(updated))
    return services.update_mainline(session, mainline_id, request_body.title, request_body.confidence, request_body.status, request_body.payload, request_body.actor, request_body.reason)


@app.post("/api/v1/mainlines/{mainline_id}/draft-signals", response_model=schemas.MainlineOut)
def update_mainline_draft_signal(mainline_id: str, request: schemas.DraftSignalRequest, session: Session = Depends(get_session)):
    return services.update_mainline_draft_signal(session, mainline_id, request.signal_id, request.action, request.actor, request.reason)


@app.post("/api/v1/mainlines/{mainline_id}/confirm")
def confirm_mainline(
    mainline_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _bearer_token(authorization)
    if token:
        current_user = foundation.current_user_from_token(session, token)
        foundation.require_permission(session, current_user, "mainline:write")
        return _envelope(request, mainline_service.confirm_mainline(session, mainline_id, current_user, _trace_id(request)))
    return services.confirm_mainline(session, mainline_id)


@app.post("/api/v1/worldline-nodes/{node_id}/run-council", response_model=schemas.CouncilSessionOut)
def run_council(node_id: str, session: Session = Depends(get_session)):
    return services.run_council(session, node_id)


@app.post("/api/v1/council-sessions/{session_id}/apply", response_model=schemas.CouncilSessionOut)
def apply_council(session_id: str, session: Session = Depends(get_session)):
    return services.apply_council(session, session_id)


@app.post("/api/v1/council-sessions/{session_id}/pressure-tests", response_model=schemas.CouncilSessionOut)
def run_pressure_test(session_id: str, request: schemas.PressureTestRequest, session: Session = Depends(get_session)):
    return services.run_pressure_test(session, session_id, request.hypothesis, request.actor)


@app.post("/api/v1/reports/{report_id}/confirm", response_model=schemas.ReportOut)
def confirm_report(report_id: str, request: schemas.ReportConfirm, session: Session = Depends(get_session)):
    return services.confirm_report(session, report_id, request.actor, request.reason)


@app.post("/api/v1/tasks", response_model=schemas.TaskOut)
def create_task(request: schemas.TaskCreate, session: Session = Depends(get_session)):
    return services.create_task(session, request.case_id, request.title, request.owner, request.due_label, request.status, request.payload, request.actor)


@app.patch("/api/v1/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: str, update: schemas.TaskUpdate, session: Session = Depends(get_session)):
    return services.update_task_status(session, task_id, update.status, update.actor, update.reason)


@app.post("/api/v1/case-memories/{case_id}/actions", response_model=schemas.GenericActionOut)
def run_case_memory_action(case_id: str, request: schemas.CaseMemoryActionRequest, session: Session = Depends(get_session)):
    return services.run_case_memory_action(session, case_id, request.action, request.actor, request.payload)


@app.post("/api/v1/library/apply", response_model=schemas.GenericActionOut)
def apply_library_item(request: schemas.LibraryApplyRequest, session: Session = Depends(get_session)):
    return services.apply_library_item(session, request.case_id, request.object_type, request.object_id, request.actor, request.payload)


@app.post("/api/v1/config/versions/{version_id}/actions", response_model=schemas.GenericActionOut)
def run_config_version_action(version_id: str, request: schemas.ConfigVersionActionRequest, session: Session = Depends(get_session)):
    return services.run_config_version_action(session, version_id, request.case_id, request.action, request.actor, request.payload)


@app.post("/api/v1/workflows/{workflow_name}/start", response_model=schemas.WorkflowRunOut)
async def start_workflow(workflow_name: str, request: schemas.WorkflowStartRequest, session: Session = Depends(get_session)):
    try:
        workflow_id, result = await execute_p0_workflow(workflow_name, case_id=request.case_id, target_id=request.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return services.record_workflow_execution(
        session,
        case_id=request.case_id,
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        status="completed",
        payload={"result": result, "target_id": request.target_id},
    )
