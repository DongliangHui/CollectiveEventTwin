from __future__ import annotations

import os

os.environ["WORLDLINE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["WORLDLINE_AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import event

from worldline_api.database import engine
from worldline_api.foundation import BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_ADMIN_USERNAME
from worldline_api.main import app
from worldline_api.models import Base


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _headers() -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"username": BOOTSTRAP_ADMIN_USERNAME, "password": BOOTSTRAP_ADMIN_PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


def _s5_world_state_and_stakeholder(headers: dict[str, str]) -> tuple[str, str, str]:
    synthetic = client.post("/api/v1/synthetic-scenarios/xian-social-issues", headers=headers)
    assert synthetic.status_code == 200, synthetic.text
    events = client.get("/api/v1/cities/xian/events", headers=headers)
    first_event = events.json()["data"][0]
    topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "city_id": "xian",
            "title": "S6 worldline council topic",
            "created_from": {"object_type": "city_event", "object_id": first_event["id"]},
            "reason": "S6 worldline API validation",
        },
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["data"]["id"]
    extraction = client.post("/api/v1/extraction-runs", headers=headers, json={"topic_id": topic_id, "limit": 20, "rule_version": "s6-signal-v1"})
    assert extraction.status_code == 201, extraction.text
    workbench = client.get(f"/api/v1/topics/{topic_id}/signal-workbench-view", headers=headers)
    signals = workbench.json()["data"]["primary_data"]["signals"][:2]
    signal_ids = [signal["id"] for signal in signals]
    package = client.post(
        "/api/v1/signal-packages",
        headers=headers,
        json={"topic_id": topic_id, "name": "S6 worldline signal package", "rule_version": "s6-package-v1", "reason": "S6 package validation"},
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["data"]["signal_package_id"]
    for rank, signal_id in enumerate(signal_ids, start=1):
        added = client.post(f"/api/v1/signal-packages/{package_id}/items", headers=headers, json={"signal_id": signal_id, "rank": rank, "reason": "S6 package item"})
        assert added.status_code == 201, added.text
    candidates = client.post("/api/v1/evidence-candidates", headers=headers, json={"topic_id": topic_id, "signal_ids": signal_ids, "limit": 5, "rule_version": "s6-evidence-v1"})
    assert candidates.status_code == 201, candidates.text
    review_id = candidates.json()["data"]["reviews"][0]["evidence_review_id"]
    confirmed_evidence = client.patch(f"/api/v1/evidence-reviews/{review_id}", headers=headers, json={"status": "confirmed", "reason": "S6 requires confirmed evidence."})
    assert confirmed_evidence.status_code == 200, confirmed_evidence.text
    mainline = client.post(
        "/api/v1/mainlines",
        headers=headers,
        json={"topic_id": topic_id, "signal_package_id": package_id, "title": "S6 evidence-backed mainline", "reason": "S6 mainline validation"},
    )
    assert mainline.status_code == 201, mainline.text
    mainline_id = mainline.json()["data"]["id"]
    quality = client.post(f"/api/v1/mainlines/{mainline_id}/quality-check", headers=headers)
    assert quality.status_code == 200, quality.text
    confirmed = client.post(f"/api/v1/mainlines/{mainline_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    world_state = client.post("/api/v1/world-states", headers=headers, json={"mainline_id": mainline_id, "reason": "S6 world state lock"})
    assert world_state.status_code == 201, world_state.text
    world_state_id = world_state.json()["data"]["id"]
    graph = client.post("/api/v1/case-graph-runs", headers=headers, json={"mainline_id": mainline_id, "world_state_id": world_state_id, "rule_version": "s6-case-graph-v1"})
    assert graph.status_code == 201, graph.text
    stakeholders = client.post("/api/v1/stakeholder-runs", headers=headers, json={"mainline_id": mainline_id, "world_state_id": world_state_id, "rule_version": "s6-stakeholder-v1"})
    assert stakeholders.status_code == 201, stakeholders.text
    stakeholder_id = stakeholders.json()["data"]["stakeholders"][0]["id"]
    reviewed = client.patch(
        f"/api/v1/stakeholders/{stakeholder_id}/review",
        headers=headers,
        json={"decision": "pass", "reason": "S6 profile input reviewed."},
    )
    assert reviewed.status_code == 200, reviewed.text
    return world_state_id, stakeholder_id, topic_id


def _pass_review(headers: dict[str, str], object_type: str, object_id: str, object_version: str, template_id: str) -> str:
    created = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"object_type": object_type, "object_id": object_id, "object_version": object_version, "template_id": template_id, "payload": {"source": "s6_test"}},
    )
    assert created.status_code == 200, created.text
    review_id = created.json()["data"]["review_id"]
    updated = client.patch(f"/api/v1/reviews/{review_id}", headers=headers, json={"status": "pass", "findings": ["S6 review pass"], "blockers": []})
    assert updated.status_code == 200, updated.text
    gate = client.post(f"/api/v1/reviews/{review_id}/gate-check", headers=headers)
    assert gate.status_code == 200, gate.text
    assert gate.json()["data"]["passed"] is True
    return review_id


def test_s6_worldline_profile_council_and_guardrail_flow() -> None:
    headers = _headers()
    world_state_id, stakeholder_id, topic_id = _s5_world_state_and_stakeholder(headers)

    run = client.post("/api/v1/worldline-runs", headers=headers, json={"world_state_id": world_state_id, "options": {"horizon_hours": 72}})
    assert run.status_code == 201, run.text
    worldline = run.json()["data"]
    worldline_run_id = worldline["id"]
    assert worldline["status"] == "completed"
    assert worldline["payload"]["status_history"] == ["pending", "running", "completed"]
    assert len(worldline["payload"]["node_ids"]) == 4

    detail = client.get(f"/api/v1/worldline-runs/{worldline_run_id}", headers=headers)
    assert detail.status_code == 200
    simulation = client.get(f"/api/v1/worldline-runs/{worldline_run_id}/simulation-view", headers=headers)
    assert simulation.status_code == 200, simulation.text
    primary = simulation.json()["data"]["primary_data"]
    selected_node_id = primary["nodes"][0]["id"]
    assert primary["run"]["id"] == worldline_run_id
    assert primary["nodes"][0]["evidence_refs"]

    intervention = client.post(
        f"/api/v1/worldline-runs/{worldline_run_id}/interventions",
        headers=headers,
        json={"action": "publish_evidence_window", "reason": "S6 intervention validation", "constraints": {"must_preserve_evidence_refs": True}},
    )
    assert intervention.status_code == 201, intervention.text
    assert intervention.json()["data"]["version"] == "v2"

    providers = client.get("/api/v1/llm-providers", headers=headers)
    assert providers.status_code == 200
    assert providers.json()["data"][0]["status"] == "active"
    assert client.get("/api/v1/prompt-templates", headers=headers).status_code == 200
    assert client.get("/api/v1/agent-templates", headers=headers).status_code == 200

    profile = client.post("/api/v1/agent-profiles", headers=headers, json={"stakeholder_id": stakeholder_id, "worldline_run_id": worldline_run_id})
    assert profile.status_code == 201, profile.text
    profile_id = profile.json()["data"]["id"]
    assert profile.json()["data"]["status"] == "draft"

    premature_council = client.post(
        "/api/v1/council-sessions",
        headers=headers,
        json={"worldline_run_id": worldline_run_id, "selected_node_id": selected_node_id, "agent_profile_ids": [profile_id], "hypothesis": "premature"},
    )
    assert premature_council.status_code == 409
    assert premature_council.json()["error"]["code"] == "AGENT_PROFILE_REVIEW_NOT_PASSED"

    files = client.post(
        f"/api/v1/agent-profiles/{profile_id}/files",
        headers=headers,
        json={"user_md": "# User\nReviewed stakeholder context.", "soul_md": "# Soul\nEvidence-bounded stance.", "agent_md": "# Agent\nGuardrailed response policy.", "reason": "S6 profile files"},
    )
    assert files.status_code == 201, files.text
    assert files.json()["data"]["status"] == "checking"
    profile_review_id = _pass_review(headers, "agent_profile", profile_id, "v1", "TPL-AGENT-PROFILE-V1")
    ready = client.get(f"/api/v1/agent-profiles/{profile_id}", headers=headers)
    assert ready.status_code == 200
    assert ready.json()["data"]["status"] == "ready"

    council = client.post(
        "/api/v1/council-sessions",
        headers=headers,
        json={"worldline_run_id": worldline_run_id, "selected_node_id": selected_node_id, "agent_profile_ids": [profile_id], "hypothesis": "Evidence window delay may increase offline pressure."},
    )
    assert council.status_code == 201, council.text
    council_id = council.json()["data"]["id"]
    assert council.json()["data"]["status"] == "created"
    council_view = client.get(f"/api/v1/council-sessions/{council_id}/council-view", headers=headers)
    assert council_view.status_code == 200
    assert council_view.json()["data"]["primary_data"]["session"]["id"] == council_id

    council_run = client.post(f"/api/v1/council-sessions/{council_id}/run", headers=headers)
    assert council_run.status_code == 200, council_run.text
    session_payload = council_run.json()["data"]["payload"]
    council_result_id = session_payload["result_id"]
    assert council_run.json()["data"]["status"] == "completed"
    assert session_payload["schema_valid"] is True
    assert session_payload["blocked_claims"]

    llm_calls = client.get("/api/v1/llm-calls", headers=headers, params={"object_id": council_id})
    assert llm_calls.status_code == 200
    assert llm_calls.json()["data"][0]["input_refs"]

    blocked_apply = client.post(f"/api/v1/council-results/{council_result_id}/apply", headers=headers)
    assert blocked_apply.status_code == 409
    assert blocked_apply.json()["error"]["code"] == "COUNCIL_REVIEW_NOT_PASSED"

    council_review_id = _pass_review(headers, "council_result", council_result_id, "v1", "TPL-COUNCIL-RESULT-V1")
    applied = client.post(f"/api/v1/council-results/{council_result_id}/apply", headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["status"] == "pass"
    assert applied.json()["data"]["payload"]["applied"] is True

    audit_actions = {
        "worldline_run.completed",
        "worldline_intervention.create",
        "agent_profile.create",
        "agent_profile.files_write",
        "council_session.create",
        "llm_call.completed",
        "council_result.create",
        "council_result.apply",
    }
    observed = set()
    for action in audit_actions:
        audit = client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 100})
        assert audit.status_code == 200
        if audit.json()["data"]:
            observed.add(action)
    assert audit_actions.issubset(observed)
    assert profile_review_id
    assert council_review_id


def test_s6_missing_objects_return_controlled_errors() -> None:
    headers = _headers()
    missing_run = client.get("/api/v1/worldline-runs/WLR-s6-missing", headers=headers)
    assert missing_run.status_code == 404
    assert missing_run.json()["error"]["code"] == "WORLDLINE_RUN_NOT_FOUND"

    missing_world_state = client.post("/api/v1/worldline-runs", headers=headers, json={"world_state_id": "WS-s6-missing"})
    assert missing_world_state.status_code == 404
    assert missing_world_state.json()["error"]["code"] == "WORLD_STATE_NOT_FOUND"

    missing_profile = client.get("/api/v1/agent-profiles/AP-s6-missing", headers=headers)
    assert missing_profile.status_code == 404
    assert missing_profile.json()["error"]["code"] == "AGENT_PROFILE_NOT_FOUND"

    missing_council = client.get("/api/v1/council-sessions/CS-s6-missing/council-view", headers=headers)
    assert missing_council.status_code == 404
    assert missing_council.json()["error"]["code"] == "COUNCIL_SESSION_NOT_FOUND"
