from __future__ import annotations

from test_s6_worldline_agent_council_api import _headers, _pass_review, _s5_world_state_and_stakeholder, client


def _pass_existing_review(headers: dict[str, str], review_id: str) -> None:
    updated = client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=headers,
        json={"status": "pass", "findings": ["S7A report review pass"], "blockers": []},
    )
    assert updated.status_code == 200, updated.text
    gate = client.post(f"/api/v1/reviews/{review_id}/gate-check", headers=headers)
    assert gate.status_code == 200, gate.text
    assert gate.json()["data"]["passed"] is True


def _applied_council_result(headers: dict[str, str]) -> tuple[str, str, str]:
    world_state_id, stakeholder_id, topic_id = _s5_world_state_and_stakeholder(headers)
    run = client.post("/api/v1/worldline-runs", headers=headers, json={"world_state_id": world_state_id, "options": {"horizon_hours": 72}})
    assert run.status_code == 201, run.text
    worldline_run_id = run.json()["data"]["id"]
    simulation = client.get(f"/api/v1/worldline-runs/{worldline_run_id}/simulation-view", headers=headers)
    assert simulation.status_code == 200, simulation.text
    selected_node_id = simulation.json()["data"]["primary_data"]["nodes"][0]["id"]

    profile = client.post("/api/v1/agent-profiles", headers=headers, json={"stakeholder_id": stakeholder_id, "worldline_run_id": worldline_run_id})
    assert profile.status_code == 201, profile.text
    profile_id = profile.json()["data"]["id"]
    files = client.post(
        f"/api/v1/agent-profiles/{profile_id}/files",
        headers=headers,
        json={"user_md": "# User\nS7A profile input.", "soul_md": "# Soul\nEvidence bounded.", "agent_md": "# Agent\nGuardrailed.", "reason": "S7A report test"},
    )
    assert files.status_code == 201, files.text
    _pass_review(headers, "agent_profile", profile_id, "v1", "TPL-AGENT-PROFILE-V1")

    council = client.post(
        "/api/v1/council-sessions",
        headers=headers,
        json={"worldline_run_id": worldline_run_id, "selected_node_id": selected_node_id, "agent_profile_ids": [profile_id], "hypothesis": "S7A report source council."},
    )
    assert council.status_code == 201, council.text
    council_id = council.json()["data"]["id"]
    council_run = client.post(f"/api/v1/council-sessions/{council_id}/run", headers=headers)
    assert council_run.status_code == 200, council_run.text
    result_id = council_run.json()["data"]["payload"]["result_id"]
    _pass_review(headers, "council_result", result_id, "v1", "TPL-COUNCIL-RESULT-V1")
    applied = client.post(f"/api/v1/council-results/{result_id}/apply", headers=headers)
    assert applied.status_code == 200, applied.text
    return topic_id, worldline_run_id, result_id


def test_s7a_report_review_publish_export_and_task_closure_flow() -> None:
    headers = _headers()
    topic_id, _worldline_run_id, council_result_id = _applied_council_result(headers)

    report = client.post("/api/v1/reports", headers=headers, json={"topic_id": topic_id, "council_result_id": council_result_id, "reason": "S7A report draft"})
    assert report.status_code == 201, report.text
    report_data = report.json()["data"]
    report_id = report_data["id"]
    assert report_data["status"] == "draft"
    assert report_data["topic_id"] == topic_id
    assert report_data["payload"]["claim_validation"]["passed"] is True
    assert report_data["payload"]["evidence_refs"]

    detail = client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert detail.status_code == 200
    listed = client.get("/api/v1/reports", headers=headers, params={"topic_id": topic_id})
    assert listed.status_code == 200
    assert any(item["id"] == report_id for item in listed.json()["data"])

    brief = client.get(f"/api/v1/reports/{report_id}/brief-view", headers=headers)
    assert brief.status_code == 200, brief.text
    primary = brief.json()["data"]["primary_data"]
    assert primary["claims"]
    assert all(claim["validation_status"] == "valid" for claim in primary["claims"])
    assert all(claim["evidence_refs"] for claim in primary["claims"])
    assert primary["tasks"]

    review = client.post(f"/api/v1/reports/{report_id}/submit-review", headers=headers)
    assert review.status_code == 201, review.text
    review_id = review.json()["data"]["review_id"]
    blocked_publish = client.post(f"/api/v1/reports/{report_id}/publish", headers=headers)
    assert blocked_publish.status_code == 409
    assert blocked_publish.json()["error"]["code"] == "REPORT_REVIEW_NOT_PASSED"

    _pass_existing_review(headers, review_id)
    published = client.post(f"/api/v1/reports/{report_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["human_confirmed"] is True

    exported = client.post(f"/api/v1/reports/{report_id}/exports", headers=headers, json={"format": "markdown", "reason": "S7A export"})
    assert exported.status_code == 201, exported.text
    assert exported.json()["data"]["status"] == "completed"
    assert exported.json()["data"]["file_uri"].startswith("postgresql://report_exports/")

    tasks = client.get("/api/v1/tasks", headers=headers, params={"report_id": report_id})
    assert tasks.status_code == 200, tasks.text
    first_task = tasks.json()["data"][0]
    assert first_task["evidence_refs"]
    updated = client.patch(f"/api/v1/tasks/{first_task['id']}", headers=headers, json={"status": "in_progress", "reason": "S7A task started"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["status"] == "in_progress"

    audit_actions = {
        "report_draft.create",
        "report_review.submit",
        "report.publish",
        "report_export.create",
        "task.status_update",
    }
    observed = set()
    for action in audit_actions:
        audit = client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 100})
        assert audit.status_code == 200
        if audit.json()["data"]:
            observed.add(action)
    assert audit_actions.issubset(observed)


def test_s7a_report_and_task_controlled_errors() -> None:
    headers = _headers()
    missing_topic = client.post("/api/v1/reports", headers=headers, json={"topic_id": "TOPIC-s7a-missing", "reason": "negative"})
    assert missing_topic.status_code == 404
    assert missing_topic.json()["error"]["code"] == "TOPIC_NOT_FOUND"

    missing_council = client.post("/api/v1/reports", headers=headers, json={"topic_id": "topic-xian-s7a", "council_result_id": "CR-s7a-missing"})
    assert missing_council.status_code in {404, 409}

    missing_report = client.get("/api/v1/reports/RPT-s7a-missing", headers=headers)
    assert missing_report.status_code == 404
    assert missing_report.json()["error"]["code"] == "REPORT_NOT_FOUND"

    missing_task = client.patch("/api/v1/tasks/TSK-s7a-missing", headers=headers, json={"status": "completed", "reason": "negative"})
    assert missing_task.status_code == 404
    assert missing_task.json()["error"]["code"] == "TASK_NOT_FOUND"
