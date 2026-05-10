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


def _topic_signal_package_and_evidence(headers: dict[str, str]) -> tuple[str, str, list[str], str, str]:
    synthetic = client.post("/api/v1/synthetic-scenarios/xian-social-issues", headers=headers)
    assert synthetic.status_code == 200, synthetic.text
    events = client.get("/api/v1/cities/xian/events", headers=headers)
    assert events.status_code == 200, events.text
    first_event = events.json()["data"][0]
    topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "city_id": "xian",
            "title": "S5 mainline modeling topic",
            "created_from": {"object_type": "city_event", "object_id": first_event["id"]},
            "reason": "S5 mainline API validation",
        },
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["data"]["id"]
    extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"topic_id": topic_id, "limit": 20, "rule_version": "s5-mainline-signal-v1"},
    )
    assert extraction.status_code == 201, extraction.text
    workbench = client.get(f"/api/v1/topics/{topic_id}/signal-workbench-view", headers=headers)
    assert workbench.status_code == 200, workbench.text
    signals = workbench.json()["data"]["primary_data"]["signals"][:2]
    assert signals
    signal_ids = [signal["id"] for signal in signals]
    package = client.post(
        "/api/v1/signal-packages",
        headers=headers,
        json={
            "topic_id": topic_id,
            "name": "S5 mainline input package",
            "rule_version": "s5-mainline-package-v1",
            "reason": "S5 package validation",
        },
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["data"]["signal_package_id"]
    for rank, signal_id in enumerate(signal_ids, start=1):
        added = client.post(
            f"/api/v1/signal-packages/{package_id}/items",
            headers=headers,
            json={"signal_id": signal_id, "rank": rank, "reason": "S5 package validation"},
        )
        assert added.status_code == 201, added.text
    candidates = client.post(
        "/api/v1/evidence-candidates",
        headers=headers,
        json={"topic_id": topic_id, "signal_ids": signal_ids, "limit": 5, "rule_version": "s5-mainline-evidence-v1"},
    )
    assert candidates.status_code == 201, candidates.text
    evidence = candidates.json()["data"]["evidence"][0]
    review = candidates.json()["data"]["reviews"][0]
    confirmed = client.patch(
        f"/api/v1/evidence-reviews/{review['evidence_review_id']}",
        headers=headers,
        json={"status": "confirmed", "reason": "S5 mainline requires confirmed evidence material."},
    )
    assert confirmed.status_code == 200, confirmed.text
    return topic_id, package_id, signal_ids, evidence["id"], review["evidence_review_id"]


def test_s5_mainline_world_state_graph_and_stakeholder_flow() -> None:
    headers = _headers()
    topic_id, package_id, signal_ids, evidence_id, _review_id = _topic_signal_package_and_evidence(headers)

    created = client.post(
        "/api/v1/mainlines",
        headers=headers,
        json={
            "topic_id": topic_id,
            "signal_package_id": package_id,
            "title": "S5 evidence-backed mainline",
            "reason": "Generate mainline draft from signal package and confirmed evidence.",
        },
    )
    assert created.status_code == 201, created.text
    mainline = created.json()["data"]
    mainline_id = mainline["id"]
    assert mainline["payload"]["topic_id"] == topic_id
    assert mainline["payload"]["signal_package_id"] == package_id
    assert mainline["payload"]["evidence_refs"][0]["object_id"] == evidence_id
    assert mainline["payload"]["version"] == "v1"
    assert mainline["status"] == "draft"

    detail = client.get(f"/api/v1/mainlines/{mainline_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["id"] == mainline_id

    listed = client.get("/api/v1/mainlines", headers=headers, params={"topic_id": topic_id})
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == mainline_id for item in listed.json()["data"])

    builder = client.get(f"/api/v1/mainlines/{mainline_id}/builder-view", headers=headers)
    assert builder.status_code == 200, builder.text
    primary = builder.json()["data"]["primary_data"]
    node = primary["nodes"][0]
    assert primary["mainline"]["id"] == mainline_id
    assert primary["quality_gate"]["status"] == "not_run"
    assert node["evidence_refs"]

    conflict = client.patch(
        f"/api/v1/mainline-nodes/{node['id']}",
        headers=headers,
        json={"expected_version": node["version"] - 1, "title": "stale edit", "reason": "force conflict"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MAINLINE_NODE_VERSION_CONFLICT"

    node_update = client.patch(
        f"/api/v1/mainline-nodes/{node['id']}",
        headers=headers,
        json={"expected_version": node["version"], "title": "Reviewed main narrative node", "reason": "S5 node edit"},
    )
    assert node_update.status_code == 200, node_update.text
    assert node_update.json()["data"]["version"] == node["version"] + 1

    if len(signal_ids) > 1:
        signal_update = client.post(
            f"/api/v1/mainlines/{mainline_id}/signals",
            headers=headers,
            json={"signal_id": signal_ids[1], "action": "remove", "reason": "S5 signal version validation"},
        )
        assert signal_update.status_code == 200, signal_update.text
        assert signal_update.json()["data"]["payload"]["version"] == "v3"

    blocked_confirm = client.post(f"/api/v1/mainlines/{mainline_id}/confirm", headers=headers)
    assert blocked_confirm.status_code == 409
    assert blocked_confirm.json()["error"]["code"] == "MAINLINE_QUALITY_NOT_PASSED"

    quality = client.post(f"/api/v1/mainlines/{mainline_id}/quality-check", headers=headers)
    assert quality.status_code == 200, quality.text
    assert quality.json()["data"]["passed"] is True
    assert quality.json()["data"]["mainline"]["status"] == "pending_confirmation"

    confirmed = client.post(f"/api/v1/mainlines/{mainline_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "confirmed"

    world_state = client.post(
        "/api/v1/world-states",
        headers=headers,
        json={"mainline_id": mainline_id, "reason": "S5 world state lock"},
    )
    assert world_state.status_code == 201, world_state.text
    world_state_id = world_state.json()["data"]["id"]
    assert world_state.json()["data"]["payload"]["mainline_version"] == confirmed.json()["data"]["payload"]["version"]
    assert world_state.json()["data"]["payload"]["evidence_refs"]

    world_state_detail = client.get(f"/api/v1/world-states/{world_state_id}", headers=headers)
    assert world_state_detail.status_code == 200
    assert world_state_detail.json()["data"]["id"] == world_state_id

    graph = client.post(
        "/api/v1/case-graph-runs",
        headers=headers,
        json={"mainline_id": mainline_id, "world_state_id": world_state_id, "rule_version": "s5-case-graph-test-v1"},
    )
    assert graph.status_code == 201, graph.text
    assert graph.json()["data"]["nodes"][0]["evidence_refs"]

    stakeholder_run = client.post(
        "/api/v1/stakeholder-runs",
        headers=headers,
        json={"mainline_id": mainline_id, "world_state_id": world_state_id, "rule_version": "s5-stakeholder-test-v1"},
    )
    assert stakeholder_run.status_code == 201, stakeholder_run.text
    stakeholder = stakeholder_run.json()["data"]["stakeholders"][0]
    assert stakeholder["status"] == "candidate"
    assert stakeholder["evidence_refs"]

    stakeholder_list = client.get("/api/v1/stakeholders", headers=headers, params={"topic_id": topic_id})
    assert stakeholder_list.status_code == 200
    assert any(item["id"] == stakeholder["id"] for item in stakeholder_list.json()["data"])

    reviewed = client.patch(
        f"/api/v1/stakeholders/{stakeholder['id']}/review",
        headers=headers,
        json={"decision": "pass", "reason": "Stakeholder is evidence-backed and can enter S6 profile generation."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "reviewed"
    assert reviewed.json()["data"]["reviewer_id"] == "USR-BOOTSTRAP-ADMIN"

    audit_actions = {
        "mainline_draft.create",
        "mainline_node.update",
        "mainline_signal.update",
        "mainline_quality_check.completed",
        "mainline.confirm",
        "world_state.create",
        "case_graph_run.completed",
        "stakeholder_run.completed",
        "stakeholder.review",
    }
    observed = set()
    for action in audit_actions:
        audit = client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 50})
        assert audit.status_code == 200
        if audit.json()["data"]:
            observed.add(action)
    assert audit_actions.issubset(observed)


def test_s5_mainline_reports_missing_objects_and_state_conflicts() -> None:
    headers = _headers()

    missing_mainline = client.get("/api/v1/mainlines/ML-s5-missing", headers=headers)
    assert missing_mainline.status_code == 404
    assert missing_mainline.json()["error"]["code"] == "MAINLINE_NOT_FOUND"

    missing_world_state = client.get("/api/v1/world-states/WS-s5-missing", headers=headers)
    assert missing_world_state.status_code == 404
    assert missing_world_state.json()["error"]["code"] == "WORLD_STATE_NOT_FOUND"

    missing_node = client.patch(
        "/api/v1/mainline-nodes/MLN-s5-missing",
        headers=headers,
        json={"expected_version": 1, "title": "missing", "reason": "missing"},
    )
    assert missing_node.status_code == 404
    assert missing_node.json()["error"]["code"] == "MAINLINE_NODE_NOT_FOUND"

    missing_stakeholder = client.patch(
        "/api/v1/stakeholders/STK-s5-missing/review",
        headers=headers,
        json={"decision": "pass", "reason": "missing stakeholder"},
    )
    assert missing_stakeholder.status_code == 404
    assert missing_stakeholder.json()["error"]["code"] == "STAKEHOLDER_NOT_FOUND"
