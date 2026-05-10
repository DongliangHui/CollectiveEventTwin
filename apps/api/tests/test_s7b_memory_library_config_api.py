from __future__ import annotations

from test_s7a_reports_tasks_api import _applied_council_result, _pass_existing_review, client
from test_s6_worldline_agent_council_api import _headers


def _published_report(headers: dict[str, str]) -> tuple[str, str, str]:
    topic_id, _worldline_run_id, council_result_id = _applied_council_result(headers)
    report = client.post(
        "/api/v1/reports",
        headers=headers,
        json={"topic_id": topic_id, "council_result_id": council_result_id, "reason": "S7B source report"},
    )
    assert report.status_code == 201, report.text
    report_id = report.json()["data"]["id"]
    review = client.post(f"/api/v1/reports/{report_id}/submit-review", headers=headers)
    assert review.status_code == 201, review.text
    _pass_existing_review(headers, review.json()["data"]["review_id"])
    published = client.post(f"/api/v1/reports/{report_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    exported = client.post(
        f"/api/v1/reports/{report_id}/exports",
        headers=headers,
        json={"format": "markdown", "reason": "S7B source export"},
    )
    assert exported.status_code == 201, exported.text
    return report_id, published.json()["data"]["case_id"], topic_id


def _pass_review(headers: dict[str, str], review_id: str, finding: str) -> None:
    updated = client.patch(
        f"/api/v1/reviews/{review_id}",
        headers=headers,
        json={"status": "pass", "findings": [finding], "blockers": []},
    )
    assert updated.status_code == 200, updated.text
    gate = client.post(f"/api/v1/reviews/{review_id}/gate-check", headers=headers)
    assert gate.status_code == 200, gate.text
    assert gate.json()["data"]["passed"] is True


def test_s7b_retrospective_case_library_and_config_release_flow() -> None:
    headers = _headers()
    report_id, case_id, _topic_id = _published_report(headers)

    retrospective = client.post(
        "/api/v1/retrospectives",
        headers=headers,
        json={"report_id": report_id, "reason": "S7B retrospective from published report"},
    )
    assert retrospective.status_code == 201, retrospective.text
    retrospective_data = retrospective.json()["data"]
    retrospective_id = retrospective_data["id"]
    assert retrospective_data["status"] == "draft"
    assert retrospective_data["payload"]["knowledge_item_ids"]
    assert all(ref["object_id"] == report_id for ref in retrospective_data["source_refs"] if ref["object_type"] == "report")

    memory_view = client.get(f"/api/v1/retrospectives/{retrospective_id}/memory-view", headers=headers)
    assert memory_view.status_code == 200, memory_view.text
    memory_primary = memory_view.json()["data"]["primary_data"]
    assert memory_primary["retrospective"]["id"] == retrospective_id
    assert memory_primary["knowledge_items"]
    assert all(item["source_refs"] for item in memory_primary["knowledge_items"])

    blocked_publish = client.post(f"/api/v1/retrospectives/{retrospective_id}/publish", headers=headers)
    assert blocked_publish.status_code == 409
    assert blocked_publish.json()["error"]["code"] == "RETROSPECTIVE_REVIEW_NOT_PASSED"

    review = client.post(f"/api/v1/retrospectives/{retrospective_id}/submit-review", headers=headers)
    assert review.status_code == 201, review.text
    _pass_review(headers, review.json()["data"]["review_id"], "S7B retrospective memory pass")
    published = client.post(f"/api/v1/retrospectives/{retrospective_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "published"
    library_entry_ids = published.json()["data"]["payload"]["case_library_entry_ids"]
    assert library_entry_ids

    library_view = client.get("/api/v1/cases/library-view", headers=headers, params={"q": "information gap"})
    assert library_view.status_code == 200, library_view.text
    library_primary = library_view.json()["data"]["primary_data"]
    assert any(entry["id"] in library_entry_ids for entry in library_primary["entries"])

    entries = client.get("/api/v1/case-library-entries", headers=headers, params={"q": "information gap"})
    assert entries.status_code == 200, entries.text
    entry_id = entries.json()["data"][0]["id"]
    detail = client.get(f"/api/v1/case-library-entries/{entry_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["source_refs"]

    applied = client.post(
        f"/api/v1/case-library-entries/{entry_id}/apply",
        headers=headers,
        json={"case_id": case_id, "object_type": "report", "object_id": report_id, "reason": "S7B apply memory suggestion"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["status"] == "applied"
    assert applied.json()["data"]["payload"]["application_id"].startswith("CLA-")

    config_version = client.post(
        "/api/v1/config/versions",
        headers=headers,
        json={
            "config_type": "model",
            "payload": {
                "name": "xian-social-risk-model",
                "parameters": {"breakout_threshold": 0.61, "noise_discount": 0.64},
                "source_refs": [{"object_type": "case_library_entry", "object_id": entry_id}],
            },
            "reason": "S7B model parameter calibration",
        },
    )
    assert config_version.status_code == 201, config_version.text
    config_id = config_version.json()["data"]["id"]
    assert config_version.json()["data"]["status"] == "draft"

    premature_publish = client.post(f"/api/v1/config/versions/{config_id}/publish", headers=headers)
    assert premature_publish.status_code == 409
    assert premature_publish.json()["error"]["code"] == "CONFIG_REGRESSION_REQUIRED"

    regression = client.post(f"/api/v1/config/versions/{config_id}/regression-runs", headers=headers)
    assert regression.status_code == 201, regression.text
    assert regression.json()["data"]["status"] == "completed"

    approval = client.post(f"/api/v1/config/versions/{config_id}/submit-approval", headers=headers)
    assert approval.status_code == 201, approval.text
    pending_publish = client.post(f"/api/v1/config/versions/{config_id}/publish", headers=headers)
    assert pending_publish.status_code == 409
    assert pending_publish.json()["error"]["code"] == "CONFIG_REVIEW_NOT_PASSED"
    _pass_review(headers, approval.json()["data"]["review_id"], "S7B config regression and approval pass")

    release = client.post(f"/api/v1/config/versions/{config_id}/publish", headers=headers)
    assert release.status_code == 200, release.text
    release_data = release.json()["data"]
    assert release_data["status"] == "rollback_available"
    assert release_data["impact_scope"]["source_refs"][0]["object_id"] == entry_id

    admin_view = client.get("/api/v1/config/admin-view", headers=headers)
    assert admin_view.status_code == 200, admin_view.text
    admin_primary = admin_view.json()["data"]["primary_data"]
    assert any(item["id"] == config_id for item in admin_primary["versions"])
    assert any(item["id"] == release_data["id"] for item in admin_primary["releases"])

    rollback = client.post(f"/api/v1/config/releases/{release_data['id']}/rollback", headers=headers)
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["data"]["status"] == "rolled_back"
    assert rollback.json()["data"]["impact_scope"]["rollback_from_release_id"] == release_data["id"]

    expected_audit = {
        "retrospective.create",
        "retrospective_review.submit",
        "retrospective.publish",
        "case_library.apply",
        "config_version.create",
        "config_regression.run",
        "config_review.submit",
        "config_version.publish",
        "config_release.rollback",
    }
    observed = set()
    for action in expected_audit:
        audit = client.get("/api/v1/audit-logs", headers=headers, params={"action": action, "limit": 100})
        assert audit.status_code == 200
        if audit.json()["data"]:
            observed.add(action)
    assert expected_audit.issubset(observed)


def test_s7b_memory_library_config_controlled_errors() -> None:
    headers = _headers()
    missing_report = client.post("/api/v1/retrospectives", headers=headers, json={"report_id": "RPT-s7b-missing"})
    assert missing_report.status_code == 404
    assert missing_report.json()["error"]["code"] == "REPORT_NOT_FOUND"

    missing_memory = client.get("/api/v1/retrospectives/RET-s7b-missing/memory-view", headers=headers)
    assert missing_memory.status_code == 404
    assert missing_memory.json()["error"]["code"] == "RETROSPECTIVE_NOT_FOUND"

    missing_library = client.get("/api/v1/case-library-entries/CLE-s7b-missing", headers=headers)
    assert missing_library.status_code == 404
    assert missing_library.json()["error"]["code"] == "CASE_LIBRARY_ENTRY_NOT_FOUND"

    missing_config = client.post("/api/v1/config/versions/CFG-s7b-missing/regression-runs", headers=headers)
    assert missing_config.status_code == 404
    assert missing_config.json()["error"]["code"] == "CONFIG_VERSION_NOT_FOUND"
