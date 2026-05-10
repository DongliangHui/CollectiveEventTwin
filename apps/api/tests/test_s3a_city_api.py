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


def test_s3a_city_page_map_event_topic_and_evidence_chain() -> None:
    headers = _headers()

    seed = client.post("/api/v1/synthetic-scenarios/xian-social-issues", headers=headers)
    assert seed.status_code == 200, seed.text

    cities = client.get("/api/v1/cities", headers=headers)
    assert cities.status_code == 200, cities.text
    assert any(city["id"] == "xian" for city in cities.json()["data"])

    overview = client.get("/api/v1/cities/xian/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    overview_data = overview.json()["data"]
    assert overview_data["page_state"] in {"ready", "degraded"}
    events = overview_data["primary_data"]["events"]
    assert len(events) >= 6
    assert all(event["evidence_refs"] for event in events)
    synthetic_flags = [event["payload"]["source_flags"]["synthetic"] for event in events]
    assert all(isinstance(flag, bool) for flag in synthetic_flags)
    assert sum(1 for flag in synthetic_flags if flag) >= 6

    layers = client.get("/api/v1/cities/xian/map-layers", headers=headers)
    assert layers.status_code == 200, layers.text
    layer_types = {layer["layer_type"] for layer in layers.json()["data"]}
    assert {"map", "point", "heat"}.issubset(layer_types)

    state = client.patch(
        "/api/v1/cities/xian/map-state",
        headers=headers,
        json={"layer_mode": "satellite", "filters": {"map_filter": "hot", "event_types": ["media"]}, "reason": "S3A test state"},
    )
    assert state.status_code == 200, state.text
    assert state.json()["data"]["layer_mode"] == "satellite"
    assert state.json()["data"]["version"] == 1

    event_rows = client.get("/api/v1/cities/xian/events", headers=headers)
    assert event_rows.status_code == 200
    first_event = event_rows.json()["data"][0]

    rankings = client.get("/api/v1/cities/xian/events/rankings", params={"rank_mode": "risk"}, headers=headers)
    assert rankings.status_code == 200
    ranked = rankings.json()["data"]
    assert ranked[0]["risk_score"] >= ranked[-1]["risk_score"]

    detail = client.get(f"/api/v1/city-events/{first_event['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert any(edge["relation"] == "derived_city_event" for edge in detail.json()["data"]["lineage"])

    topic = client.post(f"/api/v1/city-events/{first_event['id']}/create-topic", headers=headers)
    assert topic.status_code == 201, topic.text
    assert topic.json()["data"]["created_from"]["object_id"] == first_event["id"]

    updated_detail = client.get(f"/api/v1/city-events/{first_event['id']}", headers=headers)
    assert updated_detail.status_code == 200
    assert updated_detail.json()["data"]["topic_id"] == topic.json()["data"]["id"]

    source_health = client.get("/api/v1/cities/xian/source-health-view", headers=headers)
    assert source_health.status_code == 200
    assert source_health.json()["data"]["primary_data"]["source_health"]

    media = client.get("/api/v1/cities/xian/media-evidence", headers=headers)
    assert media.status_code == 200
    assert any(item["is_redacted"] is True for item in media.json()["data"])

    timeline = client.get("/api/v1/cities/xian/timeline", headers=headers)
    assert timeline.status_code == 200
    assert len(timeline.json()["data"]) >= len(events)

    metrics = client.get("/api/v1/ops/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data"]["city_events"] >= len(events)
    assert metrics.json()["data"]["topics"] >= 1

    audit = []
    for action in ["city.map_state_update", "city_event.create_topic", "city_event.derive_from_raw_record"]:
        audit.extend(client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 50}).json()["data"])
    actions = {entry["action"] for entry in audit}
    assert {"city.map_state_update", "city_event.create_topic", "city_event.derive_from_raw_record"}.issubset(actions)
