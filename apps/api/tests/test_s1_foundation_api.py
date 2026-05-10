from __future__ import annotations

import os

os.environ["WORLDLINE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["WORLDLINE_AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient

from worldline_api.database import engine
from worldline_api.foundation import BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_ADMIN_USERNAME
from worldline_api.main import app
from worldline_api.models import Base

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _login(username: str = BOOTSTRAP_ADMIN_USERNAME, password: str = BOOTSTRAP_ADMIN_PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["trace_id"]
    assert payload["data"]["access_token"].startswith("cet_at_")
    return payload["data"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_s1_login_permissions_and_audit_are_backend_persisted() -> None:
    unauthenticated = client.get("/api/v1/auth/me")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "UNAUTHENTICATED"
    canonical_unauthenticated = client.get("/api/v1/me")
    assert canonical_unauthenticated.status_code == 401
    assert canonical_unauthenticated.json()["error"]["code"] == "UNAUTHENTICATED"

    login = _login()
    headers = _headers(login["access_token"])

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["username"] == BOOTSTRAP_ADMIN_USERNAME
    canonical_me = client.get("/api/v1/me", headers=headers)
    assert canonical_me.status_code == 200
    assert canonical_me.json()["data"]["user_id"] == me.json()["data"]["user_id"]

    permissions = client.get("/api/v1/auth/permissions", headers=headers)
    assert permissions.status_code == 200
    assert {"audit:read", "review:write", "ops:read", "user:write"}.issubset(
        set(permissions.json()["data"]["permissions"])
    )
    canonical_permissions = client.get("/api/v1/me/permissions", headers=headers)
    assert canonical_permissions.status_code == 200
    permission_data = canonical_permissions.json()["data"]
    assert set(permission_data["permissions"]) == set(permissions.json()["data"]["permissions"])
    assert any(
        state["button_id"] == "review.waive" and state["enabled"] is True
        for state in permission_data["button_states"]
    )

    navigation = client.get("/api/v1/me/navigation", headers=headers)
    assert navigation.status_code == 200
    navigation_data = navigation.json()["data"]
    nav_ids = {item["id"] for item in navigation_data["items"]}
    assert {"foundation.users", "foundation.audit", "foundation.reviews", "foundation.ops"}.issubset(nav_ids)
    assert any(
        state["button_id"] == "ops.refresh" and state["required_permission"] == "ops:read" and state["enabled"] is True
        for state in navigation_data["button_states"]
    )

    failed = client.post("/api/v1/auth/login", json={"username": BOOTSTRAP_ADMIN_USERNAME, "password": "wrong"})
    assert failed.status_code == 401
    assert failed.json()["error"]["code"] == "UNAUTHENTICATED"

    audit = client.get("/api/v1/audit-logs", headers=headers)
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()["data"]]
    assert "auth.login_success" in actions
    assert "auth.login_failed" in actions
    assert all(entry["trace_id"] for entry in audit.json()["data"] if entry["action"].startswith("auth."))


def test_s1_role_user_lifecycle_is_authorized_and_audited() -> None:
    admin = _login()
    headers = _headers(admin["access_token"])

    role_response = client.post(
        "/api/v1/roles",
        json={
            "name": "audit_viewer",
            "description": "Can inspect persisted audit logs.",
            "permission_codes": ["audit:read"],
        },
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    role = role_response.json()["data"]
    assert role["permission_codes"] == ["audit:read"]

    username = "audit.viewer.s1"
    user_response = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "display_name": "Audit Viewer",
            "password": "StrongPass123!",
            "role_ids": [role["role_id"]],
        },
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    user = user_response.json()["data"]
    assert user["roles"][0]["role_id"] == role["role_id"]

    duplicate = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "display_name": "Duplicate",
            "password": "StrongPass123!",
            "role_ids": [role["role_id"]],
        },
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    viewer = _login(username, "StrongPass123!")
    forbidden = client.get("/api/v1/ops/health/api", headers=_headers(viewer["access_token"]))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    disabled = client.patch(f"/api/v1/users/{user['user_id']}", json={"status": "disabled"}, headers=headers)
    assert disabled.status_code == 200
    blocked_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert blocked_login.status_code == 403

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    assert {"role.create", "user.create", "user.update"}.issubset({entry["action"] for entry in audit})


def test_s1_user_role_status_aliases_are_authorized_and_audited_with_detail() -> None:
    admin = _login()
    headers = _headers(admin["access_token"])

    audit_role_response = client.post(
        "/api/v1/roles",
        json={
            "name": "s1_alias_audit_viewer",
            "description": "Can inspect audit logs but cannot administer users.",
            "permission_codes": ["audit:read"],
        },
        headers=headers,
    )
    assert audit_role_response.status_code == 200, audit_role_response.text
    audit_role = audit_role_response.json()["data"]

    ops_role_response = client.post(
        "/api/v1/roles",
        json={
            "name": "s1_alias_ops_viewer",
            "description": "Can inspect ops state.",
            "permission_codes": ["ops:read"],
        },
        headers=headers,
    )
    assert ops_role_response.status_code == 200, ops_role_response.text
    ops_role = ops_role_response.json()["data"]

    username = "s1.alias.user"
    user_response = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "display_name": "S1 Alias User",
            "password": "StrongPass123!",
            "role_ids": [audit_role["role_id"]],
        },
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    user = user_response.json()["data"]

    viewer = _login(username, "StrongPass123!")
    forbidden = client.patch(
        f"/api/v1/users/{user['user_id']}/status",
        json={"status": "disabled", "reason": "viewer should not mutate users"},
        headers=_headers(viewer["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    role_alias = client.patch(
        f"/api/v1/users/{user['user_id']}/roles",
        json={"role_ids": [ops_role["role_id"]], "reason": "S1 role alias readiness test"},
        headers=headers,
    )
    assert role_alias.status_code == 200, role_alias.text
    assert [role["role_id"] for role in role_alias.json()["data"]["roles"]] == [ops_role["role_id"]]

    status_alias = client.patch(
        f"/api/v1/users/{user['user_id']}/status",
        json={"status": "disabled", "reason": "S1 status alias readiness test"},
        headers=headers,
    )
    assert status_alias.status_code == 200, status_alias.text
    assert status_alias.json()["data"]["status"] == "disabled"

    audit_rows = client.get(
        "/api/v1/audit-logs",
        params={"object_type": "user", "object_id": user["user_id"]},
        headers=headers,
    ).json()["data"]
    alias_actions = {entry["action"]: entry for entry in audit_rows}
    assert {"user.roles_update", "user.status_update"}.issubset(alias_actions)

    detail = client.get(f"/api/v1/audit-logs/{alias_actions['user.status_update']['audit_id']}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["reason"] == "S1 status alias readiness test"
    assert detail_data["before"]["status"] == "active"
    assert detail_data["after"]["status"] == "disabled"


def test_s1_review_gate_waiver_and_ops_health_are_persisted() -> None:
    admin = _login()
    headers = _headers(admin["access_token"])

    templates = client.get("/api/v1/review-templates", params={"object_type": "api"}, headers=headers)
    assert templates.status_code == 200
    assert templates.json()["data"][0]["id"] == "TPL-API-V1"

    created = client.post(
        "/api/v1/reviews",
        json={
            "object_type": "api",
            "object_id": "packages/contracts/openapi/v1.0.yaml",
            "object_version": "1.0.0",
            "template_id": "TPL-API-V1",
            "payload": {"source": "s1_foundation_test"},
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    review = created.json()["data"]
    assert review["status"] == "pending"

    pending_gate = client.post(f"/api/v1/reviews/{review['review_id']}/gate-check", headers=headers)
    assert pending_gate.status_code == 200
    assert pending_gate.json()["data"] == {"passed": False, "blockers": ["review_pending"]}

    failed = client.patch(
        f"/api/v1/reviews/{review['review_id']}",
        json={"status": "fail", "findings": ["trace propagation missing"], "blockers": ["missing trace propagation"]},
        headers=headers,
    )
    assert failed.status_code == 200
    assert failed.json()["data"]["blockers"] == ["missing trace propagation"]

    failed_gate = client.post(f"/api/v1/reviews/{review['review_id']}/gate-check", headers=headers)
    assert failed_gate.json()["data"]["passed"] is False
    assert failed_gate.json()["data"]["blockers"] == ["missing trace propagation"]

    waived = client.post(
        f"/api/v1/reviews/{review['review_id']}/waive",
        json={
            "approved_by": "system_admin",
            "reason": "Temporary S1 bootstrap waiver with audit trail.",
            "risk": "No production traffic; contract is still captured in review payload.",
            "expires_at": "2030-01-01T00:00:00",
        },
        headers=headers,
    )
    assert waived.status_code == 200
    assert waived.json()["data"]["status"] == "waived"

    waived_gate = client.post(f"/api/v1/reviews/{review['review_id']}/gate-check", headers=headers)
    assert waived_gate.json()["data"] == {"passed": True, "blockers": []}

    for path in [
        "/api/v1/ops/health/api",
        "/api/v1/ops/health/db",
        "/api/v1/ops/workers",
        "/api/v1/workflow-runs",
        "/api/v1/ops/error-queue",
        "/api/v1/ops/retry-queue",
        "/api/v1/ops/metrics",
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["trace_id"]
        assert "data" in response.json()

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    assert {"review.create", "review.update", "review.waive", "ops.metrics_capture"}.issubset(
        {entry["action"] for entry in audit}
    )


def test_s1_review_gate_aliases_and_ops_canonical_paths_use_existing_persistence() -> None:
    admin = _login()
    headers = _headers(admin["access_token"])

    checklist = client.post(
        "/api/v1/review-checklists/versions",
        json={
            "object_type": "api",
            "version": "s1-alias-test-v1",
            "name": "S1 Alias API Checklist",
            "checklist": ["Alias endpoints are present.", "Existing /reviews behavior is preserved."],
        },
        headers=headers,
    )
    assert checklist.status_code == 200, checklist.text
    checklist_data = checklist.json()["data"]
    assert checklist_data["persistence_backend"] == "review_templates"

    task_id = "TASK-S1-OPENAPI-003"
    created = client.post(
        "/api/v1/review-gates",
        json={
            "task_id": task_id,
            "object_version": "1.0.0",
            "template_id": checklist_data["template_id"],
            "payload": {"source": "s1_alias_test"},
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    gate = created.json()["data"]
    assert gate["review_gate_id"] == gate["review_id"]
    assert gate["task_id"] == task_id
    assert gate["persistence_backend"] == "reviews"

    existing_review_detail = client.get(f"/api/v1/reviews/{gate['review_id']}", headers=headers)
    assert existing_review_detail.status_code == 200
    assert existing_review_detail.json()["data"]["object_id"] == task_id

    by_task = client.get(f"/api/v1/tasks/{task_id}/review-gates", headers=headers)
    assert by_task.status_code == 200
    assert [record["review_gate_id"] for record in by_task.json()["data"]] == [gate["review_gate_id"]]

    retested = client.post(
        f"/api/v1/review-gates/{gate['review_gate_id']}/retest",
        json={"status": "pass", "findings": ["alias behavior verified"], "blockers": [], "reason": "S1 retest"},
        headers=headers,
    )
    assert retested.status_code == 200, retested.text
    assert retested.json()["data"]["status"] == "pass"

    summary = client.get("/api/v1/release/review-gates-summary", headers=headers)
    assert summary.status_code == 200
    summary_data = summary.json()["data"]
    assert summary_data["persistence_backend"] == "reviews"
    assert summary_data["counts_by_status"]["pass"] >= 1

    for path in [
        "/api/v1/ops/api-health",
        "/api/v1/ops/health/api",
        "/api/v1/ops/db-health",
        "/api/v1/ops/health/db",
        "/api/v1/ops/health",
        "/api/v1/ops/workers",
        "/api/v1/ops/health/workers",
    ]:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["trace_id"]
        assert "data" in response.json()

    ops_summary = client.get("/api/v1/ops/health", headers=headers).json()["data"]
    assert ops_summary["api"]["component"] == "api"
    assert ops_summary["db"]["component"] == "db"
    assert len(ops_summary["workers"]) >= 1

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    assert {"review_gate.create", "review_gate.retest", "review_checklist_version.create"}.issubset(
        {entry["action"] for entry in audit}
    )
