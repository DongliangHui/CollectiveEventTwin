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


def test_s3b_topic_situation_source_spread_emotion_and_candidates() -> None:
    headers = _headers()
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
            "title": "Xi'an topic situation test",
            "created_from": {"object_type": "city_event", "object_id": first_event["id"]},
            "reason": "S3B topic API validation",
        },
    )
    assert created.status_code == 201, created.text
    topic_id = created.json()["data"]["id"]

    topics = client.get("/api/v1/topics", headers=headers, params={"city_id": "xian"})
    assert topics.status_code == 200
    assert any(item["id"] == topic_id for item in topics.json()["data"])

    detail = client.get(f"/api/v1/topics/{topic_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["lineage"]

    view = client.get(f"/api/v1/topics/{topic_id}/situation-view", headers=headers)
    assert view.status_code == 200, view.text
    data = view.json()["data"]
    assert data["page_state"] == "ready"
    snapshot = data["primary_data"]
    assert snapshot["events"]
    assert snapshot["evidence_refs"]
    assert snapshot["candidate_mainlines"]
    assert all(item["evidence_refs"] for item in snapshot["candidate_mainlines"])

    source = client.get(f"/api/v1/topics/{topic_id}/source-breakdown", headers=headers)
    spread = client.get(f"/api/v1/topics/{topic_id}/spread-paths", headers=headers)
    emotion = client.get(f"/api/v1/topics/{topic_id}/emotion-stance", headers=headers)
    candidates = client.get(f"/api/v1/topics/{topic_id}/candidate-mainlines", headers=headers)
    for response in [source, spread, emotion, candidates]:
        assert response.status_code == 200, response.text
    assert source.json()["data"]["total"] >= 1
    assert spread.json()["data"]["paths"][0]["evidence_refs"]
    assert emotion.json()["data"]["stance_samples"][0]["evidence_refs"]
    assert candidates.json()["data"]["candidate_mainlines"][0]["evidence_refs"]

    patched = client.patch(f"/api/v1/topics/{topic_id}", headers=headers, json={"status": "observing", "reason": "S3B state transition"})
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "observing"

    audit = client.get("/api/v1/audit-logs", headers=headers, params={"object_type": "topic", "object_id": topic_id, "limit": 200}).json()["data"]
    actions = {entry["action"] for entry in audit}
    assert {"topic.create", "topic.update", "topic.situation_snapshot_update"}.issubset(actions)


def test_s3b_topic_api_rejects_invalid_sources_and_missing_topics() -> None:
    headers = _headers()

    invalid_source = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "city_id": "xian",
            "title": "Invalid topic source",
            "created_from": {"object_type": "raw_record", "object_id": "RAW-missing"},
            "reason": "S3B invalid source validation",
        },
    )
    assert invalid_source.status_code == 400
    assert invalid_source.json()["error"]["code"] == "INVALID_TOPIC_SOURCE"

    missing_view = client.get("/api/v1/topics/TOP-does-not-exist/situation-view", headers=headers)
    assert missing_view.status_code == 404
    assert missing_view.json()["error"]["code"] == "TOPIC_NOT_FOUND"

    unauthorized = client.get("/api/v1/topics")
    assert unauthorized.status_code in {401, 403}
