from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from .models import AuditLog


def write_audit(
    session: Session,
    *,
    case_id: str,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    reason: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    audit = AuditLog(
        id=f"AUD-{uuid4().hex[:20]}",
        case_id=case_id,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        payload=payload or {},
    )
    session.add(audit)
    return audit

