from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from .models import AuditLog


def write_audit(
    session: Session,
    *,
    case_id: str | None = None,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    tenant_id: str | None = None,
    actor_id: str | None = None,
    object_version: str | None = None,
    reason: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    diff: dict | None = None,
    trace_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    audit = AuditLog(
        id=f"AUD-{uuid4().hex[:20]}",
        tenant_id=tenant_id,
        case_id=case_id,
        actor_id=actor_id,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_version=object_version,
        reason=reason,
        before=jsonable_encoder(before or {}),
        after=jsonable_encoder(after or {}),
        diff=jsonable_encoder(diff or {}),
        trace_id=trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
        payload=jsonable_encoder(payload or {}),
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit)
    return audit
