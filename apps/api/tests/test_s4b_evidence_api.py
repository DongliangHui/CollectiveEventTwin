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


def _topic_with_signal(headers: dict[str, str]) -> tuple[str, str]:
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
            "title": "S4B evidence review topic",
            "created_from": {"object_type": "city_event", "object_id": first_event["id"]},
            "reason": "S4B evidence API validation",
        },
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["data"]["id"]
    extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"topic_id": topic_id, "limit": 20, "rule_version": "s4b-evidence-test-signal-v1"},
    )
    assert extraction.status_code == 201, extraction.text
    workbench = client.get(f"/api/v1/topics/{topic_id}/signal-workbench-view", headers=headers)
    assert workbench.status_code == 200, workbench.text
    first_signal = workbench.json()["data"]["primary_data"]["signals"][0]
    return topic_id, first_signal["id"]


def test_s4b_evidence_candidate_review_media_risk_and_conflict_flow() -> None:
    headers = _headers()
    topic_id, signal_id = _topic_with_signal(headers)

    candidates = client.post(
        "/api/v1/evidence-candidates",
        headers=headers,
        json={"topic_id": topic_id, "signal_ids": [signal_id], "limit": 5, "rule_version": "s4b-evidence-candidate-test-v1"},
    )
    assert candidates.status_code == 201, candidates.text
    payload = candidates.json()["data"]
    assert payload["run"]["status"] == "completed"
    evidence = payload["evidence"][0]
    review = payload["reviews"][0]
    evidence_id = evidence["id"]
    review_id = review["evidence_review_id"]
    assert evidence["status"] == "candidate"
    assert evidence["payload"]["input_refs"]
    assert evidence["payload"]["evidence_refs"]
    assert evidence["payload"]["blocked_claims"]

    listed = client.get("/api/v1/evidence", headers=headers, params={"topic_id": topic_id, "status": "candidate"})
    assert listed.status_code == 200
    assert any(item["id"] == evidence_id for item in listed.json()["data"])

    detail = client.get(f"/api/v1/evidence/{evidence_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["review"]["evidence_review_id"] == review_id
    assert detail.json()["data"]["lineage"]

    attachment = client.post(
        f"/api/v1/evidence/{evidence_id}/attachments",
        headers=headers,
        json={
            "media_type": "video",
            "uri": "synthetic://s4b/evidence-video-001.mp4",
            "content": "synthetic attachment transcript mentions minor name Zhang and must stay masked.",
            "is_synthetic": True,
            "payload": {"source": "s4b_test"},
        },
    )
    assert attachment.status_code == 201, attachment.text
    media = attachment.json()["data"]["media_asset"]
    assert attachment.json()["data"]["link"]["evidence_id"] == evidence_id

    media_run = client.post(
        "/api/v1/media-processing-runs",
        headers=headers,
        json={"media_asset_id": media["id"], "processor": "asr", "evidence_id": evidence_id, "rule_version": "s4b-media-test-v1"},
    )
    assert media_run.status_code == 201, media_run.text
    assert media_run.json()["data"]["output"]["blocked_claims"]

    link = client.post(
        "/api/v1/evidence-media-links",
        headers=headers,
        json={"evidence_id": evidence_id, "media_asset_id": media["id"], "relation": "supporting_clip", "payload": {"dedupe": True}},
    )
    assert link.status_code == 201, link.text
    assert link.json()["data"]["media_asset_id"] == media["id"]

    redaction = client.post(
        "/api/v1/redaction-runs",
        headers=headers,
        json={"object_type": "evidence", "object_id": evidence_id, "input_scope": {"fields": ["excerpt", "masked_excerpt"]}, "actor_id": "USR-BOOTSTRAP-ADMIN"},
    )
    assert redaction.status_code == 201, redaction.text
    assert redaction.json()["data"]["payload"]["redaction_applied"] is True

    reviewed = client.patch(
        f"/api/v1/evidence-reviews/{review_id}",
        headers=headers,
        json={"status": "confirmed", "reason": "S4B review confirms this is usable as evidence material, not a final public fact."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["status"] == "confirmed"
    assert reviewed.json()["data"]["evidence"]["status"] == "confirmed_fact"

    review_view = client.get(f"/api/v1/evidence-reviews/{review_id}/review-view", headers=headers)
    assert review_view.status_code == 200, review_view.text
    primary = review_view.json()["data"]["primary_data"]
    assert primary["evidence"]["id"] == evidence_id
    assert primary["media_links"]
    assert primary["legacy_page_view"]["page"] == "evidence"

    risk_run = client.post(
        "/api/v1/risk-factor-runs",
        headers=headers,
        json={"topic_id": topic_id, "evidence_ids": [evidence_id], "rule_version": "s4b-risk-factor-test-v1"},
    )
    assert risk_run.status_code == 201, risk_run.text
    risk_factor = risk_run.json()["data"]["risk_factors"][0]
    assert risk_factor["payload"]["evidence_refs"][0]["object_id"] == evidence_id

    risk_list = client.get("/api/v1/risk-factors", headers=headers, params={"topic_id": topic_id, "status": "suggested"})
    assert risk_list.status_code == 200
    assert any(item["id"] == risk_factor["id"] for item in risk_list.json()["data"])

    risk_patch = client.patch(
        f"/api/v1/risk-factors/{risk_factor['id']}",
        headers=headers,
        json={"status": "confirmed", "reason": "S4B risk factor confirmation"},
    )
    assert risk_patch.status_code == 200
    assert risk_patch.json()["data"]["status"] == "confirmed"

    adjustment = client.post(
        f"/api/v1/risk-factors/{risk_factor['id']}/confidence-adjustments",
        headers=headers,
        json={"delta": 0.04, "reason": "Confirmed evidence material raises confidence.", "input_refs": [{"object_type": "evidence", "object_id": evidence_id}]},
    )
    assert adjustment.status_code == 201, adjustment.text
    assert adjustment.json()["data"]["confidence"] > risk_factor["confidence"]

    conflict = client.post(
        "/api/v1/conflict-detection-runs",
        headers=headers,
        json={"topic_id": topic_id, "evidence_ids": [evidence_id], "rule_version": "s4b-conflict-test-v1"},
    )
    assert conflict.status_code == 201, conflict.text
    assert conflict.json()["data"]["run"]["status"] == "completed"
    assert conflict.json()["data"]["conflicts"][0]["evidence_refs"][0]["object_id"] == evidence_id

    audit = []
    for action in [
        "evidence_candidate.create",
        "evidence_review.update",
        "evidence_attachment.create",
        "media_processing_run.create",
        "redaction_run.completed",
        "risk_factor_run.completed",
        "conflict_detection_run.completed",
    ]:
        audit.extend(client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 50}).json()["data"])
    assert {
        "evidence_candidate.create",
        "evidence_review.update",
        "evidence_attachment.create",
        "media_processing_run.create",
        "redaction_run.completed",
        "risk_factor_run.completed",
        "conflict_detection_run.completed",
    }.issubset({entry["action"] for entry in audit})


def test_s4b_evidence_api_reports_missing_objects_and_invalid_review_state() -> None:
    headers = _headers()

    missing_topic = client.post("/api/v1/evidence-candidates", headers=headers, json={"topic_id": "TOP-missing", "limit": 5})
    assert missing_topic.status_code == 404
    assert missing_topic.json()["error"]["code"] == "TOPIC_NOT_FOUND"

    missing_evidence = client.get("/api/v1/evidence/EVD-missing", headers=headers)
    assert missing_evidence.status_code == 404
    assert missing_evidence.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"

    missing_review = client.patch("/api/v1/evidence-reviews/ER-missing", headers=headers, json={"status": "confirmed", "reason": "missing"})
    assert missing_review.status_code == 404
    assert missing_review.json()["error"]["code"] == "EVIDENCE_REVIEW_NOT_FOUND"

    missing_media = client.post(
        "/api/v1/media-processing-runs",
        headers=headers,
        json={"media_asset_id": "MED-missing", "processor": "ocr", "rule_version": "s4b-negative-test-v1"},
    )
    assert missing_media.status_code == 404
    assert missing_media.json()["error"]["code"] == "MEDIA_ASSET_NOT_FOUND"

    invalid_state = client.patch(
        "/api/v1/evidence-reviews/ER-missing",
        headers=headers,
        json={"status": "not_a_state", "reason": "invalid state"},
    )
    assert invalid_state.status_code == 422
