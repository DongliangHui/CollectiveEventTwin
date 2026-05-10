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


def _topic(headers: dict[str, str]) -> str:
    synthetic = client.post("/api/v1/synthetic-scenarios/xian-social-issues", headers=headers)
    assert synthetic.status_code == 200, synthetic.text
    events = client.get("/api/v1/cities/xian/events", headers=headers)
    assert events.status_code == 200, events.text
    first_event = events.json()["data"][0]
    created = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "city_id": "xian",
            "title": "S4A signal extraction topic",
            "created_from": {"object_type": "city_event", "object_id": first_event["id"]},
            "reason": "S4A signal API validation",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


def test_s4a_signal_extraction_search_detail_and_package_flow() -> None:
    headers = _headers()
    topic_id = _topic(headers)

    extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"topic_id": topic_id, "limit": 20, "rule_version": "s4a-signal-extract-test-v1"},
    )
    assert extraction.status_code == 201, extraction.text
    run = extraction.json()["data"]
    assert run["status"] == "completed"
    assert run["payload"]["input_count"] >= 1
    assert run["payload"]["output_count"] >= 1
    assert run["payload"]["sample_outputs"][0]["payload"]["evidence_refs"]

    workbench = client.get(f"/api/v1/topics/{topic_id}/signal-workbench-view", headers=headers)
    assert workbench.status_code == 200, workbench.text
    primary = workbench.json()["data"]["primary_data"]
    assert primary["signals"]
    assert primary["extraction_runs"][0]["workflow_run_id"] == run["workflow_run_id"]
    assert primary["lineage_summary"]["signal_count"] >= 1

    first_signal = primary["signals"][0]
    listed = client.get("/api/v1/signals", headers=headers, params={"topic_id": topic_id, "q": first_signal["title"][:4]})
    assert listed.status_code == 200
    assert any(item["id"] == first_signal["id"] for item in listed.json()["data"])

    detail = client.get(f"/api/v1/signals/{first_signal['id']}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["payload"]["input_refs"]
    assert detail_data["lineage"]

    package = client.post(
        "/api/v1/signal-packages",
        headers=headers,
        json={"topic_id": topic_id, "name": "S4A draft signal package", "rule_version": "s4a-package-test-v1"},
    )
    assert package.status_code == 201, package.text
    package_id = package.json()["data"]["signal_package_id"]

    added = client.post(
        f"/api/v1/signal-packages/{package_id}/items",
        headers=headers,
        json={"signal_id": first_signal["id"], "rank": 1, "reason": "S4A add signal validation"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["data"]["items"][0]["signal"]["id"] == first_signal["id"]

    removed = client.delete(f"/api/v1/signal-packages/{package_id}/items", headers=headers, params={"signal_id": first_signal["id"]})
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["items"] == []

    audit = []
    for action in ["signal.extraction_run.completed", "signal_package.create", "signal_package.item.add", "signal_package.item.remove"]:
        audit.extend(client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 50}).json()["data"])
    actions = {entry["action"] for entry in audit}
    assert {"signal.extraction_run.completed", "signal_package.create", "signal_package.item.add", "signal_package.item.remove"}.issubset(actions)


def test_s4a_signal_api_reports_invalid_scope_and_missing_objects() -> None:
    headers = _headers()

    missing_topic = client.post("/api/v1/extraction-runs", headers=headers, json={"topic_id": "TOP-missing", "limit": 5})
    assert missing_topic.status_code == 404
    assert missing_topic.json()["error"]["code"] == "TOPIC_NOT_FOUND"

    invalid_scope = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"raw_record_ids": ["RAW-missing"], "limit": 5, "rule_version": "s4a-invalid-scope-v1"},
    )
    assert invalid_scope.status_code == 201
    assert invalid_scope.json()["data"]["status"] == "failed"
    assert invalid_scope.json()["data"]["payload"]["error_code"] == "RAW_RECORD_SCOPE_EMPTY"

    missing_signal = client.get("/api/v1/signals/SIG-missing", headers=headers)
    assert missing_signal.status_code == 404
    assert missing_signal.json()["error"]["code"] == "SIGNAL_NOT_FOUND"
