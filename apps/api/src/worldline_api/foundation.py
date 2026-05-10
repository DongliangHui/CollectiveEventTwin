from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from .audit import write_audit
from . import models

DEFAULT_TENANT_ID = "tenant-xian-social-v1"
BOOTSTRAP_ADMIN_USERNAME = "admin"
BOOTSTRAP_ADMIN_PASSWORD = "admin12345"

PERMISSIONS = {
    "auth:read": "Read authenticated user and permission context.",
    "user:write": "Create, disable, and update users.",
    "role:write": "Create and update roles and permissions.",
    "audit:read": "Read immutable audit logs.",
    "review:write": "Create and update review records.",
    "review:approve": "Approve review waivers.",
    "workflow:run": "Start and inspect workflow runs.",
    "ops:read": "Read operational health and queues.",
    "config:publish": "Publish versioned product configuration.",
    "data_source:read": "Read data source governance and raw record state.",
    "data_source:write": "Create data sources, collection jobs, imports, and raw labels.",
    "data_source:raw_original": "Read original raw record payload text after explicit permission and audit.",
    "city:read": "Read city situation, map, event, source health, media, and timeline views.",
    "city:write": "Update city map state and create topics from city events.",
    "topic:read": "Read topic situation, source, spread, emotion, and candidate mainline views.",
    "topic:write": "Create and update topics and persisted topic situation snapshots.",
    "signal:read": "Read extracted signals, workbench views, signal details, and signal packages.",
    "signal:write": "Run signal extraction and modify signal packages.",
    "evidence:read": "Read evidence candidates, evidence review views, media links, and risk factors.",
    "evidence:write": "Generate evidence candidates, process media, redact evidence, and create risk factors.",
    "evidence:review": "Review evidence status and confirm or reject risk factors.",
    "mainline:read": "Read mainline builder views, versions, world states, graph nodes, and stakeholders.",
    "mainline:write": "Create and edit mainlines, run quality checks, generate world states, graphs, and stakeholders.",
    "stakeholder:review": "Review stakeholders before Agent Profile generation.",
    "worldline:read": "Read worldline simulations, agent profiles, LLM calls, and council views.",
    "worldline:write": "Create worldline runs, interventions, agent profiles, and council sessions.",
    "agent:review": "Review Agent Profile and Council Result readiness gates.",
    "report:read": "Read report drafts, claims, exports, and task closure state.",
    "report:write": "Create, edit, submit, publish, and export evidence-backed reports.",
    "task:read": "Read report-linked operational tasks.",
    "task:write": "Create and update report-linked operational tasks.",
    "memory:read": "Read retrospective memory, knowledge items, and case library state.",
    "memory:write": "Create and publish retrospective knowledge after review.",
    "case_library:read": "Search and inspect approved case library entries.",
    "case_library:write": "Apply approved case library suggestions with audit.",
    "config:read": "Read data source, taxonomy, model, agent, and prompt configuration versions.",
    "config:write": "Create configuration versions and run regression checks.",
}

REVIEW_TEMPLATES = [
    {
        "id": "TPL-API-V1",
        "name": "API Contract Freeze Review",
        "object_type": "api",
        "checklist": [
            "OpenAPI path has envelope response.",
            "DTO fields match persisted database objects.",
            "Error codes and trace_id are present.",
            "Audit-affecting actions are declared.",
        ],
    },
    {
        "id": "TPL-DB-MIGRATION-V1",
        "name": "Database Migration Review",
        "object_type": "config_version",
        "checklist": [
            "Migration order is append-only.",
            "Rollback or forward-fix strategy is explicit.",
            "Audit and traceability columns are preserved.",
        ],
    },
    {
        "id": "TPL-FRONTEND-PAGE-V1",
        "name": "Frontend Page State Review",
        "object_type": "frontend_page",
        "checklist": [
            "Page uses real FastAPI data.",
            "Loading, empty, error, degraded, and no_permission states exist.",
            "Every business action calls a backend API.",
        ],
    },
    {
        "id": "TPL-ALGORITHM-OUTPUT-V1",
        "name": "Algorithm Output Evidence Review",
        "object_type": "algorithm_output",
        "checklist": [
            "Inputs are persisted and traceable.",
            "Evidence references are attached to every fact judgement.",
            "Synthetic input is labelled synthetic end to end.",
        ],
    },
    {
        "id": "TPL-AGENT-PROFILE-V1",
        "name": "Agent Profile Evidence and Guardrail Review",
        "object_type": "agent_profile",
        "checklist": [
            "Stakeholder was reviewed before profile creation.",
            "Profile files are evidence-bounded and versioned.",
            "No unsupported factual or personal claims are present.",
        ],
    },
    {
        "id": "TPL-COUNCIL-RESULT-V1",
        "name": "Council Result Guardrail Review",
        "object_type": "council_result",
        "checklist": [
            "Council output schema is valid.",
            "Every judgement cites evidence or is blocked.",
            "Probability deltas and blocked claims are persisted.",
        ],
    },
    {
        "id": "TPL-REPORT-V1",
        "name": "Report Evidence and Publication Review",
        "object_type": "report",
        "checklist": [
            "Every factual claim has persisted evidence references.",
            "Report version, Council result, Worldline Run, and Mainline refs are locked.",
            "Exports and downstream tasks are traceable and audit-logged.",
        ],
    },
    {
        "id": "TPL-RETROSPECTIVE-V1",
        "name": "Retrospective Memory Publication Review",
        "object_type": "retrospective",
        "checklist": [
            "Knowledge items are derived from a published report.",
            "Every durable lesson preserves report and evidence source refs.",
            "Approved memory is separated from production configuration until explicit config release.",
        ],
    },
    {
        "id": "TPL-CONFIG-VERSION-V1",
        "name": "Configuration Release Review",
        "object_type": "config_version",
        "checklist": [
            "Regression run passed against approved case library entries.",
            "Impact scope and rollback path are explicit.",
            "Published configuration does not overwrite previous release records.",
        ],
    },
]

NAVIGATION_ITEMS = [
    {
        "id": "foundation.users",
        "label": "Users",
        "path": "/admin?tab=users",
        "section": "foundation",
        "order": 10,
        "required_permission": "user:write",
        "button_ids": ["users.create", "users.update_roles", "users.update_status"],
    },
    {
        "id": "foundation.roles",
        "label": "Roles",
        "path": "/admin?tab=roles",
        "section": "foundation",
        "order": 20,
        "required_permission": "role:write",
        "button_ids": ["roles.create", "roles.update"],
    },
    {
        "id": "foundation.audit",
        "label": "Audit",
        "path": "/admin?tab=audit",
        "section": "foundation",
        "order": 30,
        "required_permission": "audit:read",
        "button_ids": ["audit.view_detail"],
    },
    {
        "id": "foundation.reviews",
        "label": "Reviews",
        "path": "/admin?tab=reviews",
        "section": "foundation",
        "order": 40,
        "required_permission": "review:write",
        "button_ids": ["review.create", "review.retest", "review.checklist_version", "review.waive"],
    },
    {
        "id": "foundation.ops",
        "label": "Ops",
        "path": "/admin?tab=ops",
        "section": "foundation",
        "order": 50,
        "required_permission": "ops:read",
        "button_ids": ["ops.refresh", "ops.metrics_capture"],
    },
]

BUTTON_PERMISSION_STATES = {
    "users.create": ("Create user", "user:write"),
    "users.update_roles": ("Update roles", "user:write"),
    "users.update_status": ("Update status", "user:write"),
    "roles.create": ("Create role", "role:write"),
    "roles.update": ("Update role", "role:write"),
    "audit.view_detail": ("View audit detail", "audit:read"),
    "review.create": ("Create review gate", "review:write"),
    "review.retest": ("Retest review gate", "review:write"),
    "review.checklist_version": ("Create checklist version", "review:write"),
    "review.waive": ("Waive review", "review:approve"),
    "ops.refresh": ("Refresh ops status", "ops:read"),
    "ops.metrics_capture": ("Capture metrics", "ops:read"),
}


def utcnow() -> datetime:
    return datetime.utcnow()


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, digest = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return hmac.compare_digest(candidate, digest)


def api_error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details or {}},
    )


def ensure_foundation_seed(session: Session) -> None:
    tenant = session.get(models.Tenant, DEFAULT_TENANT_ID)
    if tenant is None:
        session.add(
            models.Tenant(
                id=DEFAULT_TENANT_ID,
                name="西安第一阶段社会议题生产租户",
                status="active",
                payload={"scope": "s1_foundation", "synthetic": False},
            )
        )

    for code, description in PERMISSIONS.items():
        permission_id = f"PERM-{code.replace(':', '-').upper()}"
        if session.get(models.Permission, permission_id) is None:
            session.add(models.Permission(id=permission_id, code=code, description=description, payload={}))
    session.flush()

    admin_role = session.get(models.Role, "ROLE-SYSTEM-ADMIN")
    if admin_role is None:
        admin_role = models.Role(
            id="ROLE-SYSTEM-ADMIN",
            tenant_id=DEFAULT_TENANT_ID,
            name="system_admin",
            description="Full S1 production administration role.",
            status="active",
            payload={"builtin": True},
        )
        session.add(admin_role)
    session.flush()

    existing_permission_ids = set(
        session.execute(
            select(models.RolePermission.permission_id).where(models.RolePermission.role_id == admin_role.id)
        ).scalars()
    )
    for permission in session.execute(select(models.Permission)).scalars():
        if permission.id not in existing_permission_ids:
            session.add(models.RolePermission(role_id=admin_role.id, permission_id=permission.id))

    admin_user = session.execute(select(models.User).where(models.User.username == BOOTSTRAP_ADMIN_USERNAME)).scalar_one_or_none()
    if admin_user is None:
        admin_user = models.User(
            id="USR-BOOTSTRAP-ADMIN",
            tenant_id=DEFAULT_TENANT_ID,
            username=BOOTSTRAP_ADMIN_USERNAME,
            display_name="System Administrator",
            password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            status="active",
            failed_attempts=0,
            payload={"bootstrap": True},
        )
        session.add(admin_user)
        session.flush()
    if session.get(models.UserRole, {"user_id": admin_user.id, "role_id": admin_role.id}) is None:
        session.add(models.UserRole(user_id=admin_user.id, role_id=admin_role.id))

    for template in REVIEW_TEMPLATES:
        if session.get(models.ReviewTemplate, template["id"]) is None:
            session.add(
                models.ReviewTemplate(
                    id=template["id"],
                    name=template["name"],
                    object_type=template["object_type"],
                    status="active",
                    payload={"version": "1.0", "checklist": template["checklist"]},
                )
            )

    session.commit()


def permission_codes_for_user(session: Session, user_id: str) -> list[str]:
    return sorted(
        set(
            session.execute(
                select(models.Permission.code)
                .join(models.RolePermission, models.RolePermission.permission_id == models.Permission.id)
                .join(models.UserRole, models.UserRole.role_id == models.RolePermission.role_id)
                .where(models.UserRole.user_id == user_id)
            ).scalars()
        )
    )


def roles_for_user(session: Session, user_id: str) -> list[dict]:
    roles = session.execute(
        select(models.Role)
        .join(models.UserRole, models.UserRole.role_id == models.Role.id)
        .where(models.UserRole.user_id == user_id)
        .order_by(models.Role.name)
    ).scalars()
    return [{"role_id": role.id, "name": role.name, "status": role.status} for role in roles]


def serialize_user(session: Session, user: models.User) -> dict:
    return {
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "username": user.username,
        "display_name": user.display_name,
        "status": user.status,
        "roles": roles_for_user(session, user.id),
        "permissions": permission_codes_for_user(session, user.id),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def button_permission_states(session: Session, user: models.User) -> list[dict]:
    permission_codes = set(permission_codes_for_user(session, user.id))
    states = []
    for button_id, (label, required_permission) in sorted(BUTTON_PERMISSION_STATES.items()):
        enabled = required_permission in permission_codes
        states.append(
            {
                "button_id": button_id,
                "label": label,
                "required_permission": required_permission,
                "visible": enabled,
                "enabled": enabled,
                "disabled_reason": None if enabled else f"missing_permission:{required_permission}",
            }
        )
    return states


def current_permissions(session: Session, user: models.User) -> dict:
    return {
        "permissions": permission_codes_for_user(session, user.id),
        "button_states": button_permission_states(session, user),
    }


def navigation_for_user(session: Session, user: models.User) -> dict:
    all_button_states = button_permission_states(session, user)
    button_by_id = {state["button_id"]: state for state in all_button_states}
    permission_codes = set(permission_codes_for_user(session, user.id))
    items = []
    for item in NAVIGATION_ITEMS:
        enabled = item["required_permission"] in permission_codes
        items.append(
            {
                "id": item["id"],
                "label": item["label"],
                "path": item["path"],
                "section": item["section"],
                "order": item["order"],
                "required_permission": item["required_permission"],
                "visible": enabled,
                "enabled": enabled,
                "disabled_reason": None if enabled else f"missing_permission:{item['required_permission']}",
                "button_states": [button_by_id[button_id] for button_id in item["button_ids"]],
            }
        )
    return {"items": items, "button_states": all_button_states}


def require_permission(session: Session, user: models.User, permission_code: str) -> None:
    if permission_code not in permission_codes_for_user(session, user.id):
        raise api_error(403, "FORBIDDEN", f"Missing permission: {permission_code}")


def login(
    session: Session,
    *,
    username: str,
    password: str,
    trace_id: str,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    ensure_foundation_seed(session)
    user = session.execute(select(models.User).where(models.User.username == username)).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_attempts += 1
        write_audit(
            session,
            tenant_id=user.tenant_id if user else DEFAULT_TENANT_ID,
            actor=username,
            action="auth.login_failed",
            object_type="auth",
            object_id=username,
            reason="invalid_credentials",
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.commit()
        raise api_error(401, "UNAUTHENTICATED", "Invalid username or password.")

    if user.status != "active":
        write_audit(
            session,
            tenant_id=user.tenant_id,
            actor=user.username,
            actor_id=user.id,
            action="auth.login_blocked",
            object_type="user",
            object_id=user.id,
            reason=f"user_status:{user.status}",
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.commit()
        raise api_error(403, "FORBIDDEN", "User account is not active.")

    access_token = f"cet_at_{secrets.token_urlsafe(32)}"
    refresh_token = f"cet_rt_{secrets.token_urlsafe(32)}"
    auth_session = models.AuthSession(
        id=_id("SES"),
        tenant_id=user.tenant_id,
        user_id=user.id,
        access_token_hash=_hash_secret(access_token),
        refresh_token_hash=_hash_secret(refresh_token),
        status="active",
        expires_at=utcnow() + timedelta(hours=8),
        payload={"issued_for": "s1_foundation", "trace_id": trace_id},
    )
    user.failed_attempts = 0
    session.add(auth_session)
    write_audit(
        session,
        tenant_id=user.tenant_id,
        actor=user.username,
        actor_id=user.id,
        action="auth.login_success",
        object_type="session",
        object_id=auth_session.id,
        trace_id=trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": auth_session.expires_at,
        "user": serialize_user(session, user),
    }


def current_user_from_token(session: Session, token: str | None) -> models.User:
    ensure_foundation_seed(session)
    if not token:
        raise api_error(401, "UNAUTHENTICATED", "Bearer token is required.")
    auth_session = session.execute(
        select(models.AuthSession).where(
            models.AuthSession.access_token_hash == _hash_secret(token),
            models.AuthSession.status == "active",
        )
    ).scalar_one_or_none()
    if auth_session is None:
        raise api_error(401, "UNAUTHENTICATED", "Session is invalid.")
    if _naive_utc(auth_session.expires_at) <= utcnow():
        auth_session.status = "expired"
        session.commit()
        raise api_error(401, "UNAUTHENTICATED", "Session has expired.")
    user = session.get(models.User, auth_session.user_id)
    if user is None or user.status != "active":
        raise api_error(403, "FORBIDDEN", "User account is not active.")
    return user


def refresh_session(session: Session, refresh_token: str, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    auth_session = session.execute(
        select(models.AuthSession).where(
            models.AuthSession.refresh_token_hash == _hash_secret(refresh_token),
            models.AuthSession.status == "active",
        )
    ).scalar_one_or_none()
    if auth_session is None or _naive_utc(auth_session.expires_at) <= utcnow():
        raise api_error(401, "UNAUTHENTICATED", "Refresh token is invalid.")
    user = session.get(models.User, auth_session.user_id)
    if user is None or user.status != "active":
        raise api_error(403, "FORBIDDEN", "User account is not active.")
    access_token = f"cet_at_{secrets.token_urlsafe(32)}"
    new_refresh_token = f"cet_rt_{secrets.token_urlsafe(32)}"
    auth_session.access_token_hash = _hash_secret(access_token)
    auth_session.refresh_token_hash = _hash_secret(new_refresh_token)
    auth_session.expires_at = utcnow() + timedelta(hours=8)
    write_audit(
        session,
        tenant_id=user.tenant_id,
        actor=user.username,
        actor_id=user.id,
        action="auth.refresh",
        object_type="session",
        object_id=auth_session.id,
        trace_id=trace_id,
    )
    session.commit()
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_at": auth_session.expires_at,
        "user": serialize_user(session, user),
    }


def logout(session: Session, token: str | None, user: models.User, trace_id: str) -> dict:
    if token:
        auth_session = session.execute(
            select(models.AuthSession).where(models.AuthSession.access_token_hash == _hash_secret(token))
        ).scalar_one_or_none()
        if auth_session is not None:
            auth_session.status = "revoked"
            write_audit(
                session,
                tenant_id=user.tenant_id,
                actor=user.username,
                actor_id=user.id,
                action="auth.logout",
                object_type="session",
                object_id=auth_session.id,
                trace_id=trace_id,
            )
            session.commit()
    return {"logged_out": True}


def serialize_role(session: Session, role: models.Role) -> dict:
    permission_codes = sorted(
        session.execute(
            select(models.Permission.code)
            .join(models.RolePermission, models.RolePermission.permission_id == models.Permission.id)
            .where(models.RolePermission.role_id == role.id)
        ).scalars()
    )
    return {
        "role_id": role.id,
        "tenant_id": role.tenant_id,
        "name": role.name,
        "description": role.description,
        "status": role.status,
        "permission_codes": permission_codes,
        "payload": role.payload,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


def list_roles(session: Session) -> list[dict]:
    ensure_foundation_seed(session)
    return [serialize_role(session, role) for role in session.execute(select(models.Role).order_by(models.Role.name)).scalars()]


def create_role(session: Session, request, actor: models.User, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    role = models.Role(
        id=_id("ROLE"),
        tenant_id=actor.tenant_id,
        name=request.name,
        description=request.description,
        status="active",
        payload=request.payload,
    )
    session.add(role)
    session.flush()
    _replace_role_permissions(session, role.id, request.permission_codes)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="role.create",
        object_type="role",
        object_id=role.id,
        after=serialize_role(session, role),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_role(session, role)


def update_role(session: Session, role_id: str, request, actor: models.User, trace_id: str) -> dict:
    role = session.get(models.Role, role_id)
    if role is None:
        raise api_error(404, "NOT_FOUND", "Role does not exist.")
    before = serialize_role(session, role)
    if request.description is not None:
        role.description = request.description
    if request.status is not None:
        role.status = request.status
    if request.payload is not None:
        role.payload = request.payload
    if request.permission_codes is not None:
        _replace_role_permissions(session, role.id, request.permission_codes)
    after = serialize_role(session, role)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="role.update",
        object_type="role",
        object_id=role.id,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_role(session, role)


def _replace_role_permissions(session: Session, role_id: str, permission_codes: list[str]) -> None:
    permissions = list(session.execute(select(models.Permission).where(models.Permission.code.in_(permission_codes))).scalars())
    found_codes = {permission.code for permission in permissions}
    missing = sorted(set(permission_codes) - found_codes)
    if missing:
        raise api_error(400, "VALIDATION_ERROR", "Unknown permission codes.", {"missing": missing})
    session.query(models.RolePermission).filter(models.RolePermission.role_id == role_id).delete()
    for permission in permissions:
        session.add(models.RolePermission(role_id=role_id, permission_id=permission.id))


def list_users(session: Session) -> list[dict]:
    ensure_foundation_seed(session)
    return [serialize_user(session, user) for user in session.execute(select(models.User).order_by(models.User.username)).scalars()]


def create_user(session: Session, request, actor: models.User, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    existing = session.execute(select(models.User).where(models.User.username == request.username)).scalar_one_or_none()
    if existing is not None:
        raise api_error(409, "CONFLICT", "Username already exists.")
    user = models.User(
        id=_id("USR"),
        tenant_id=actor.tenant_id,
        username=request.username,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
        status=request.status,
        failed_attempts=0,
        payload=request.payload,
    )
    session.add(user)
    session.flush()
    _replace_user_roles(session, user.id, request.role_ids)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="user.create",
        object_type="user",
        object_id=user.id,
        after=serialize_user(session, user),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_user(session, user)


def update_user(session: Session, user_id: str, request, actor: models.User, trace_id: str) -> dict:
    user = session.get(models.User, user_id)
    if user is None:
        raise api_error(404, "NOT_FOUND", "User does not exist.")
    before = serialize_user(session, user)
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.status is not None:
        user.status = request.status
    if request.payload is not None:
        user.payload = request.payload
    if request.role_ids is not None:
        _replace_user_roles(session, user.id, request.role_ids)
    after = serialize_user(session, user)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="user.update",
        object_type="user",
        object_id=user.id,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_user(session, user)


def update_user_roles(session: Session, user_id: str, request, actor: models.User, trace_id: str) -> dict:
    user = session.get(models.User, user_id)
    if user is None:
        raise api_error(404, "NOT_FOUND", "User does not exist.")
    before = serialize_user(session, user)
    _replace_user_roles(session, user.id, request.role_ids)
    session.flush()
    after = serialize_user(session, user)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="user.roles_update",
        object_type="user",
        object_id=user.id,
        reason=request.reason,
        before=before,
        after=after,
        diff={
            "role_ids": {
                "before": [role["role_id"] for role in before["roles"]],
                "after": [role["role_id"] for role in after["roles"]],
            }
        },
        trace_id=trace_id,
    )
    session.commit()
    return serialize_user(session, user)


def update_user_status(session: Session, user_id: str, request, actor: models.User, trace_id: str) -> dict:
    user = session.get(models.User, user_id)
    if user is None:
        raise api_error(404, "NOT_FOUND", "User does not exist.")
    before = serialize_user(session, user)
    user.status = request.status
    after = serialize_user(session, user)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="user.status_update",
        object_type="user",
        object_id=user.id,
        reason=request.reason,
        before=before,
        after=after,
        diff={"status": {"before": before["status"], "after": after["status"]}},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_user(session, user)


def _replace_user_roles(session: Session, user_id: str, role_ids: list[str]) -> None:
    roles = list(session.execute(select(models.Role).where(models.Role.id.in_(role_ids))).scalars())
    found_ids = {role.id for role in roles}
    missing = sorted(set(role_ids) - found_ids)
    if missing:
        raise api_error(400, "VALIDATION_ERROR", "Unknown role ids.", {"missing": missing})
    session.query(models.UserRole).filter(models.UserRole.user_id == user_id).delete()
    for role in roles:
        session.add(models.UserRole(user_id=user_id, role_id=role.id))


def list_audit_logs(
    session: Session,
    tenant_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    limit: int | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
) -> list[dict]:
    ensure_foundation_seed(session)
    effective_limit = limit or page_size
    statement = select(models.AuditLog).order_by(models.AuditLog.created_at.desc())
    if tenant_id:
        statement = statement.where(or_(models.AuditLog.tenant_id == tenant_id, models.AuditLog.tenant_id.is_(None)))
    if object_type:
        statement = statement.where(models.AuditLog.object_type == object_type)
    if object_id:
        statement = statement.where(models.AuditLog.object_id == object_id)
    if actor_id:
        statement = statement.where(models.AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(models.AuditLog.action == action)
    statement = statement.offset(max(page - 1, 0) * effective_limit).limit(effective_limit)
    rows = session.execute(statement).scalars()
    return [serialize_audit(row) for row in rows]


def get_audit_log(session: Session, audit_id: str, tenant_id: str | None = None) -> dict:
    audit = session.get(models.AuditLog, audit_id)
    if audit is None:
        raise api_error(404, "NOT_FOUND", "Audit log does not exist.")
    if tenant_id and audit.tenant_id not in {tenant_id, None}:
        raise api_error(404, "NOT_FOUND", "Audit log does not exist.")
    return serialize_audit(audit)


def serialize_audit(audit: models.AuditLog) -> dict:
    return {
        "audit_id": audit.id,
        "tenant_id": audit.tenant_id,
        "case_id": audit.case_id,
        "actor_id": audit.actor_id,
        "actor": audit.actor,
        "action": audit.action,
        "object_type": audit.object_type,
        "object_id": audit.object_id,
        "object_version": audit.object_version,
        "reason": audit.reason,
        "trace_id": audit.trace_id,
        "ip": audit.ip_address,
        "user_agent": audit.user_agent,
        "before": audit.before,
        "after": audit.after,
        "diff": audit.diff,
        "payload": audit.payload,
        "created_at": audit.created_at,
    }


def list_review_templates(session: Session, object_type: str | None = None) -> list[dict]:
    ensure_foundation_seed(session)
    statement = select(models.ReviewTemplate).order_by(models.ReviewTemplate.object_type, models.ReviewTemplate.id)
    if object_type:
        statement = statement.where(models.ReviewTemplate.object_type == object_type)
    return [serialize_review_template(template) for template in session.execute(statement).scalars()]


def serialize_review_template(template: models.ReviewTemplate) -> dict:
    return {
        "id": template.id,
        "object_type": template.object_type,
        "version": template.payload.get("version", "1.0"),
        "name": template.name,
        "checklist": template.payload.get("checklist", []),
        "status": template.status,
    }


def create_review(session: Session, request, actor: models.User, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    template = session.get(models.ReviewTemplate, request.template_id)
    if template is None:
        raise api_error(404, "NOT_FOUND", "Review template does not exist.")
    review = models.Review(
        id=_id("REV"),
        tenant_id=actor.tenant_id,
        template_id=template.id,
        object_type=request.object_type,
        object_id=request.object_id,
        object_version=request.object_version,
        status="pending",
        reviewer_id=None,
        blocker_count=0,
        payload={"findings": [], "blockers": [], "request": request.payload},
    )
    session.add(review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review.create",
        object_type="review",
        object_id=review.id,
        object_version=review.object_version,
        after=serialize_review(review),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_review(review)


def list_reviews(session: Session, status: str | None = None, object_type: str | None = None) -> list[dict]:
    ensure_foundation_seed(session)
    statement = select(models.Review).order_by(models.Review.created_at.desc())
    if status:
        statement = statement.where(models.Review.status == status)
    if object_type:
        statement = statement.where(models.Review.object_type == object_type)
    return [serialize_review(review) for review in session.execute(statement).scalars()]


def get_review(session: Session, review_id: str) -> models.Review:
    review = session.get(models.Review, review_id)
    if review is None:
        raise api_error(404, "NOT_FOUND", "Review does not exist.")
    return review


def update_review(session: Session, review_id: str, request, actor: models.User, trace_id: str) -> dict:
    review = get_review(session, review_id)
    before = serialize_review(review)
    review.status = request.status
    review.reviewer_id = actor.id
    review.blocker_count = len(request.blockers)
    review.payload = {**review.payload, "findings": request.findings, "blockers": request.blockers, "reason": request.reason}
    session.add(
        models.ReviewResult(
            id=_id("REVR"),
            review_id=review.id,
            reviewer_id=actor.id,
            status=request.status,
            findings=request.findings,
            blockers=request.blockers,
            reason=request.reason,
            payload={"trace_id": trace_id},
        )
    )
    after = serialize_review(review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review.update",
        object_type="review",
        object_id=review.id,
        object_version=review.object_version,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_review(review)


def waive_review(session: Session, review_id: str, request, actor: models.User, trace_id: str) -> dict:
    review = get_review(session, review_id)
    before = serialize_review(review)
    review.status = "waived"
    review.reviewer_id = actor.id
    review.waived_until = _naive_utc(request.expires_at)
    review.waiver_reason = request.reason
    review.payload = {**review.payload, "waiver": {"approved_by": request.approved_by, "risk": request.risk}}
    session.add(
        models.ReviewResult(
            id=_id("REVR"),
            review_id=review.id,
            reviewer_id=actor.id,
            status="waived",
            findings=["waiver_recorded"],
            blockers=[],
            reason=request.reason,
            payload={"approved_by": request.approved_by, "risk": request.risk, "expires_at": _naive_utc(request.expires_at).isoformat()},
        )
    )
    after = serialize_review(review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review.waive",
        object_type="review",
        object_id=review.id,
        object_version=review.object_version,
        before=before,
        after=after,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_review(review)


def review_gate_check(session: Session, review_id: str) -> dict:
    review = get_review(session, review_id)
    blockers = [] if review.status == "waived" else list(review.payload.get("blockers", []))
    if review.status == "pending":
        blockers.append("review_pending")
    if review.status == "fail" and review.blocker_count == 0:
        blockers.append("review_failed")
    if review.status == "waived" and review.waived_until is not None and _naive_utc(review.waived_until) <= utcnow():
        blockers.append("waiver_expired")
    return {"passed": review.status in {"pass", "waived"} and not blockers, "blockers": blockers}


def serialize_review(review: models.Review) -> dict:
    return {
        "review_id": review.id,
        "tenant_id": review.tenant_id,
        "object_type": review.object_type,
        "object_id": review.object_id,
        "object_version": review.object_version,
        "template_id": review.template_id,
        "status": review.status,
        "reviewer_id": review.reviewer_id,
        "findings": review.payload.get("findings", []),
        "blockers": review.payload.get("blockers", []),
        "waiver_reason": review.waiver_reason,
        "waived_until": review.waived_until,
        "payload": review.payload,
        "created_at": review.created_at,
        "completed_at": review.updated_at if review.status in {"pass", "fail", "waived"} else None,
    }


def serialize_review_gate(review: models.Review) -> dict:
    review_data = serialize_review(review)
    request_payload = review.payload.get("request", {})
    task_id = review.payload.get("task_id") or request_payload.get("task_id")
    if task_id is None and review.object_type == "task":
        task_id = review.object_id
    return {
        "review_gate_id": review.id,
        "review_id": review.id,
        "task_id": task_id,
        "object_type": review.object_type,
        "object_id": review.object_id,
        "object_version": review.object_version,
        "template_id": review.template_id,
        "status": review.status,
        "reviewer_id": review.reviewer_id,
        "findings": review_data["findings"],
        "blockers": review_data["blockers"],
        "waiver_reason": review.waiver_reason,
        "waived_until": review.waived_until,
        "payload": review.payload,
        "persistence_backend": "reviews",
        "alias_of": "/api/v1/reviews",
        "created_at": review.created_at,
        "completed_at": review_data["completed_at"],
    }


def create_review_gate(session: Session, request, actor: models.User, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    object_id = request.object_id or request.task_id
    if object_id is None:
        raise api_error(400, "VALIDATION_ERROR", "Review gate requires object_id or task_id.")
    template = session.get(models.ReviewTemplate, request.template_id)
    if template is None:
        raise api_error(404, "NOT_FOUND", "Review template does not exist.")
    review = models.Review(
        id=_id("REV"),
        tenant_id=actor.tenant_id,
        template_id=template.id,
        object_type=request.object_type,
        object_id=object_id,
        object_version=request.object_version,
        status="pending",
        reviewer_id=None,
        blocker_count=0,
        payload={
            "findings": [],
            "blockers": [],
            "request": request.payload,
            "task_id": request.task_id,
            "alias": "review_gate",
            "persistence_backend": "reviews",
        },
    )
    session.add(review)
    session.flush()
    after = serialize_review_gate(review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review_gate.create",
        object_type="review_gate",
        object_id=review.id,
        object_version=review.object_version,
        after=after,
        trace_id=trace_id,
        payload={"alias_of": "/api/v1/reviews", "persistence_backend": "reviews"},
    )
    session.commit()
    return serialize_review_gate(review)


def list_review_gates_for_task(session: Session, task_id: str) -> list[dict]:
    ensure_foundation_seed(session)
    reviews = session.execute(
        select(models.Review)
        .where(models.Review.object_type == "task", models.Review.object_id == task_id)
        .order_by(models.Review.created_at.desc())
    ).scalars()
    return [serialize_review_gate(review) for review in reviews]


def retest_review_gate(session: Session, review_gate_id: str, request, actor: models.User, trace_id: str) -> dict:
    review = get_review(session, review_gate_id)
    before = serialize_review_gate(review)
    review.status = request.status
    review.reviewer_id = actor.id
    review.blocker_count = len(request.blockers)
    review.payload = {
        **review.payload,
        "findings": request.findings,
        "blockers": request.blockers,
        "reason": request.reason,
        "retest_payload": request.payload,
        "alias": "review_gate",
        "persistence_backend": "reviews",
    }
    session.add(
        models.ReviewResult(
            id=_id("REVR"),
            review_id=review.id,
            reviewer_id=actor.id,
            status=request.status,
            findings=request.findings,
            blockers=request.blockers,
            reason=request.reason,
            payload={"trace_id": trace_id, "alias": "review_gate.retest", **request.payload},
        )
    )
    session.flush()
    after = serialize_review_gate(review)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review_gate.retest",
        object_type="review_gate",
        object_id=review.id,
        object_version=review.object_version,
        reason=request.reason,
        before=before,
        after=after,
        trace_id=trace_id,
        payload={"alias_of": "/api/v1/reviews/{review_id}", "persistence_backend": "reviews"},
    )
    session.commit()
    return serialize_review_gate(review)


def _template_id_for_checklist(object_type: str, version: str) -> str:
    object_slug = "".join(character if character.isalnum() else "-" for character in object_type).strip("-").upper()
    version_slug = "".join(character if character.isalnum() else "-" for character in version).strip("-").upper()
    return f"TPL-{object_slug}-{version_slug}"


def serialize_review_checklist_version(template: models.ReviewTemplate) -> dict:
    return {
        "review_checklist_version_id": template.id,
        "template_id": template.id,
        "object_type": template.object_type,
        "version": template.payload.get("version", "1.0"),
        "name": template.name,
        "checklist": template.payload.get("checklist", []),
        "status": template.status,
        "payload": template.payload,
        "persistence_backend": "review_templates",
        "alias_of": "/api/v1/review-templates",
        "created_at": template.created_at,
    }


def create_review_checklist_version(session: Session, request, actor: models.User, trace_id: str) -> dict:
    ensure_foundation_seed(session)
    template_id = request.template_id or _template_id_for_checklist(request.object_type, request.version)
    if session.get(models.ReviewTemplate, template_id) is not None:
        raise api_error(409, "CONFLICT", "Review checklist version already exists.")
    template = models.ReviewTemplate(
        id=template_id,
        name=request.name,
        object_type=request.object_type,
        status=request.status,
        payload={
            **request.payload,
            "version": request.version,
            "checklist": request.checklist,
            "alias": "review_checklist_version",
            "persistence_backend": "review_templates",
        },
    )
    session.add(template)
    session.flush()
    after = serialize_review_checklist_version(template)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="review_checklist_version.create",
        object_type="review_checklist_version",
        object_id=template.id,
        object_version=request.version,
        after=after,
        trace_id=trace_id,
        payload={"alias_of": "/api/v1/review-templates", "persistence_backend": "review_templates"},
    )
    session.commit()
    return serialize_review_checklist_version(template)


def release_review_gates_summary(session: Session) -> dict:
    ensure_foundation_seed(session)
    reviews = list(session.execute(select(models.Review).order_by(models.Review.created_at.desc())).scalars())
    counts_by_status = {"pending": 0, "pass": 0, "fail": 0, "waived": 0}
    blocking_gate_ids = []
    gates = []
    for review in reviews:
        counts_by_status[review.status] = counts_by_status.get(review.status, 0) + 1
        if review.status in {"pending", "fail"} or review.blocker_count > 0:
            blocking_gate_ids.append(review.id)
        gates.append(serialize_review_gate(review))
    return {
        "persistence_backend": "reviews",
        "alias_of": "/api/v1/reviews",
        "total": len(reviews),
        "counts_by_status": counts_by_status,
        "blocking_gate_ids": blocking_gate_ids,
        "gates": gates,
        "generated_at": utcnow(),
    }


def ops_api_health() -> dict:
    return {
        "component": "api",
        "status": "ok",
        "version": "s1-foundation",
        "checked_at": utcnow(),
        "source": "runtime",
    }


def ops_db_health(session: Session) -> dict:
    started = time.perf_counter()
    value = session.execute(text("select 1")).scalar_one()
    return {
        "component": "db",
        "status": "ok" if value == 1 else "degraded",
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "checked_at": utcnow(),
        "source": "database",
    }


def ops_workers_health(session: Session) -> list[dict]:
    retry_backlog = session.execute(
        select(func.count()).select_from(models.OpsRetryQueue).where(models.OpsRetryQueue.status.in_(["pending", "retrying"]))
    ).scalar_one()
    error_backlog = session.execute(
        select(func.count()).select_from(models.OpsErrorQueue).where(models.OpsErrorQueue.status == "open")
    ).scalar_one()
    return [
        {
            "worker_id": "local-fastapi-worker",
            "status": "online",
            "backlog_count": int(retry_backlog or 0),
            "last_seen_at": utcnow(),
            "source": "runtime",
        },
        {
            "worker_id": "ops-error-queue",
            "status": "online" if not error_backlog else "degraded",
            "backlog_count": int(error_backlog or 0),
            "last_seen_at": utcnow(),
            "source": "database",
        },
    ]


def ops_health_summary(session: Session) -> dict:
    api = ops_api_health()
    db = ops_db_health(session)
    workers = ops_workers_health(session)
    worker_degraded = any(worker["status"] != "online" for worker in workers)
    status = "degraded" if api["status"] != "ok" or db["status"] != "ok" or worker_degraded else "ok"
    return {
        "status": status,
        "api": api,
        "db": db,
        "workers": workers,
        "checked_at": utcnow(),
    }


def ops_workflow_runs(session: Session, limit: int = 20, object_type: str | None = None, object_id: str | None = None) -> list[dict]:
    statement = select(models.WorkflowRun).order_by(models.WorkflowRun.updated_at.desc()).limit(limit)
    if object_type and object_type != "case":
        return []
    if object_id:
        statement = statement.where(models.WorkflowRun.case_id == object_id)
    runs = session.execute(statement).scalars()
    return [
        {
            "workflow_run_id": run.id,
            "workflow_type": run.workflow_name,
            "workflow_id": run.workflow_id,
            "object_type": "case",
            "object_id": run.case_id,
            "input_hash": run.payload.get("input_hash", "not_recorded_p0_legacy"),
            "status": run.status,
            "attempt": run.payload.get("attempt", 1),
            "trace_id": run.trace_id or run.payload.get("trace_id", "legacy-no-trace"),
            "payload": run.payload,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        }
        for run in runs
    ]


def ops_error_queue(session: Session, limit: int = 50) -> list[dict]:
    rows = session.execute(select(models.OpsErrorQueue).order_by(models.OpsErrorQueue.created_at.desc()).limit(limit)).scalars()
    return [
        {
            "error_id": row.id,
            "source": row.source,
            "severity": row.severity,
            "status": row.status,
            "message": row.message,
            "payload": row.payload,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


def ops_retry_queue(session: Session, limit: int = 50) -> list[dict]:
    rows = session.execute(select(models.OpsRetryQueue).order_by(models.OpsRetryQueue.created_at.desc()).limit(limit)).scalars()
    return [
        {
            "retry_id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "status": row.status,
            "attempts": row.attempts,
            "next_run_at": row.next_run_at,
            "payload": row.payload,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


def ops_metrics(session: Session, actor: models.User | None, trace_id: str) -> dict:
    payload = {
        "users": session.execute(select(func.count()).select_from(models.User)).scalar_one(),
        "roles": session.execute(select(func.count()).select_from(models.Role)).scalar_one(),
        "audit_logs": session.execute(select(func.count()).select_from(models.AuditLog)).scalar_one(),
        "reviews": session.execute(select(func.count()).select_from(models.Review)).scalar_one(),
        "open_errors": session.execute(
            select(func.count()).select_from(models.OpsErrorQueue).where(models.OpsErrorQueue.status == "open")
        ).scalar_one(),
        "queued_retries": session.execute(
            select(func.count()).select_from(models.OpsRetryQueue).where(models.OpsRetryQueue.status.in_(["pending", "retrying"]))
        ).scalar_one(),
        "data_sources": session.execute(select(func.count()).select_from(models.DataSource)).scalar_one(),
        "collection_runs": session.execute(select(func.count()).select_from(models.CollectionRun)).scalar_one(),
        "import_runs": session.execute(select(func.count()).select_from(models.ImportRun)).scalar_one(),
        "normalization_runs": session.execute(select(func.count()).select_from(models.NormalizationRun)).scalar_one(),
        "deduplication_runs": session.execute(select(func.count()).select_from(models.DeduplicationRun)).scalar_one(),
        "data_quality_runs": session.execute(select(func.count()).select_from(models.DataQualityRun)).scalar_one(),
        "raw_records": session.execute(select(func.count()).select_from(models.RawRecord)).scalar_one(),
        "cities": session.execute(select(func.count()).select_from(models.City)).scalar_one(),
        "city_events": session.execute(select(func.count()).select_from(models.CityEvent)).scalar_one(),
        "topics": session.execute(select(func.count()).select_from(models.Topic)).scalar_one(),
        "signal_packages": session.execute(select(func.count()).select_from(models.SignalPackage)).scalar_one(),
        "captured_at": utcnow().isoformat(),
    }
    snapshot = models.MetricsSnapshot(id=_id("MET"), metric_scope="s1_foundation", payload=payload)
    session.add(snapshot)
    if actor is not None:
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="ops.metrics_capture",
            object_type="metrics_snapshot",
            object_id=snapshot.id,
            after=payload,
            trace_id=trace_id,
        )
    session.commit()
    return {"snapshot_id": snapshot.id, **payload}
