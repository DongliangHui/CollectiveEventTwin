from __future__ import annotations

import os

os.environ["WORLDLINE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["WORLDLINE_AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient

from worldline_api.database import engine
from worldline_api.main import app
from worldline_api.models import Base
from worldline_api.policy import mask_sensitive_text, source_allowed

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_campus_golden_path_reaches_confirmed_report_and_audit_trail() -> None:
    assert client.post("/api/v1/admin/seed", json={"fixture": "all"}).status_code == 200
    assert client.post("/api/v1/admin/seed", json={"fixture": "all"}).status_code == 200

    cases = client.get("/api/v1/cases").json()
    assert {case["id"] for case in cases} == {"CASE-CAMPUS-001", "CASE-COMMUNITY-WATER-001"}
    search_results = client.get("/api/v1/search", params={"q": "Campus"}).json()
    assert any(item["case_id"] == "CASE-CAMPUS-001" for item in search_results)

    bundle = client.get("/api/v1/cases/CASE-CAMPUS-001").json()
    assert bundle["case"]["slug"] == "campus-death-high-intensity"
    assert len(bundle["signals"]) == 42
    assert len(bundle["source_records"]) == 38
    assert len(bundle["evidence"]) == 68
    assert len(bundle["risk_factors"]) == 23
    assert {node["branch"] for node in bundle["worldline_nodes"]} >= {"root", "A", "B", "C", "D"}

    blocked = [source for source in bundle["source_records"] if source["id"] == "SRC-BLOCKED-001"][0]
    assert blocked["accepted"] is False
    assert blocked["blocked_reason"] == "source_not_allowed_for_p0"

    minor_evidence = [item for item in bundle["evidence"] if item["id"] == "EVD-017"][0]
    assert "[MASKED]" in minor_evidence["masked_excerpt"]
    assert "Zhang" not in minor_evidence["masked_excerpt"]
    assert bundle["report"]["payload"]["formal_conclusion"] == ""

    updated_evidence = client.patch(
        "/api/v1/evidence/EVD-017",
        json={"status": "confirmed_fact", "actor": "analyst", "reason": "privacy sample reviewed"},
    )
    assert updated_evidence.status_code == 200
    assert updated_evidence.json()["status"] == "confirmed_fact"

    updated_factor = client.patch(
        "/api/v1/risk-factors/RF-CAMPUS-PRIVACY",
        json={"status": "confirmed", "actor": "analyst", "reason": "linked evidence reviewed"},
    )
    assert updated_factor.status_code == 200
    assert updated_factor.json()["status"] == "confirmed"

    mainline = client.post("/api/v1/mainlines/ML-001/confirm")
    assert mainline.status_code == 200
    assert mainline.json()["status"] == "confirmed"

    council = client.post("/api/v1/worldline-nodes/NODE-C3/run-council")
    assert council.status_code == 200
    council_payload = council.json()["payload"]
    assert council_payload["schema_version"] == "p0.agent_council.v1"
    assert {agent["role"] for agent in council_payload["agents"]} == {
        "education-and-local-authority",
        "family-community",
        "local-media",
        "local-street-office",
        "platform-safety",
        "public-observers",
        "school",
    }
    for agent in council_payload["agents"]:
        assert set(agent) == {
            "role",
            "stance",
            "reaction",
            "support_point_delta",
            "branch_probability_delta",
            "evidence_refs",
            "uncertainty",
            "blocked_claims",
        }
        assert agent["evidence_refs"]

    applied = client.post("/api/v1/council-sessions/COUNCIL-001/apply")
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"

    confirmed_report = client.post(
        "/api/v1/reports/REPORT-001/confirm",
        json={"actor": "reviewer", "reason": "human confirmed for P0 golden path"},
    )
    assert confirmed_report.status_code == 200
    report_payload = confirmed_report.json()["payload"]
    assert confirmed_report.json()["human_confirmed"] is True
    assert report_payload["formal_conclusion"] == report_payload["draft_summary"]

    task = client.patch(
        "/api/v1/tasks/TASK-002",
        json={"status": "in_progress", "actor": "operator", "reason": "evidence team started"},
    )
    assert task.status_code == 200
    assert task.json()["status"] == "in_progress"

    audit = client.get("/api/v1/cases/CASE-CAMPUS-001/audit").json()
    actions = [entry["action"] for entry in audit]
    assert actions.count("source_rejected") == 1
    assert "evidence_status_updated" in actions
    assert "risk_factor_status_updated" in actions
    assert "mainline_confirmed" in actions
    assert "council_generated" in actions
    assert "council_applied" in actions
    assert "report_confirmed" in actions
    assert "task_status_updated" in actions


def test_p0_page_apis_and_actions_are_db_driven_and_audited() -> None:
    assert client.post("/api/v1/admin/seed", json={"fixture": "all"}).status_code == 200

    pages = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]
    for page in pages:
        response = client.get(f"/api/v1/cases/CASE-CAMPUS-001/pages/{page}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["page"] == page
        assert payload["sections"]
        assert payload["raw"]["counts"]["signals"] == 42
        assert payload["raw"]["counts"]["evidence"] == 68
        assert payload["raw"]["counts"]["mainlines"] == 7

    assert client.get("/api/v1/cases/CASE-CAMPUS-001/pages/not-a-page").status_code == 404

    updated_signal = client.patch(
        "/api/v1/signals/SIG-AUX-001",
        json={"status": "confirmed", "priority": "P0", "actor": "analyst", "reason": "signal reviewed"},
    )
    assert updated_signal.status_code == 200
    assert updated_signal.json()["status"] == "confirmed"

    draft = client.post(
        "/api/v1/mainlines/ML-001/draft-signals",
        json={"signal_id": "SIG-AUX-002", "action": "add", "actor": "analyst"},
    )
    assert draft.status_code == 200
    assert "SIG-AUX-002" in draft.json()["payload"]["draft_signals"]

    similar = client.get("/api/v1/signals/SIG-AUX-001/similar").json()
    assert similar
    assert all(item["id"] != "SIG-AUX-001" for item in similar)

    created_mainline = client.post(
        "/api/v1/mainlines",
        json={"case_id": "CASE-CAMPUS-001", "title": "人工补充主线", "confidence": 0.62, "status": "draft"},
    )
    assert created_mainline.status_code == 200
    mainline_id = created_mainline.json()["id"]
    patched_mainline = client.patch(
        f"/api/v1/mainlines/{mainline_id}",
        json={"payload": {"support_points": ["补充支点"]}, "reason": "manual edit"},
    )
    assert patched_mainline.status_code == 200
    assert "补充支点" in patched_mainline.json()["payload"]["support_points"]

    council = client.post("/api/v1/worldline-nodes/NODE-C3/run-council").json()
    pressure = client.post(
        f"/api/v1/council-sessions/{council['id']}/pressure-tests",
        json={"hypothesis": "如果 2 小时内发布证据清单会怎样？", "actor": "analyst"},
    )
    assert pressure.status_code == 200
    assert pressure.json()["payload"]["pressure_tests"]

    new_task = client.post(
        "/api/v1/tasks",
        json={"case_id": "CASE-CAMPUS-001", "title": "补充家属沟通纪要", "owner": "family-liaison", "due_label": "2h"},
    )
    assert new_task.status_code == 200

    memory = client.post("/api/v1/case-memories/CASE-CAMPUS-001/actions", json={"action": "confirm_ingest", "actor": "analyst"})
    assert memory.status_code == 200
    assert memory.json()["status"] == "ingested"

    library = client.post(
        "/api/v1/library/apply",
        json={"case_id": "CASE-CAMPUS-001", "object_type": "Pattern", "object_id": "PATTERN-FACT-GAP"},
    )
    assert library.status_code == 200
    assert library.json()["status"] == "applied"

    config = client.post(
        "/api/v1/config/versions/v2.4.2/actions",
        json={"case_id": "CASE-CAMPUS-001", "action": "run_regression", "actor": "admin"},
    )
    assert config.status_code == 200
    assert config.json()["status"] == "regression_passed"

    audit = client.get("/api/v1/cases/CASE-CAMPUS-001/audit").json()
    actions = {entry["action"] for entry in audit}
    assert {
        "signal_updated",
        "mainline_draft_signal_updated",
        "mainline_created",
        "mainline_updated",
        "pressure_test_run",
        "task_created",
        "case_memory_confirm_ingest",
        "library_item_applied",
        "config_run_regression",
    }.issubset(actions)


def test_non_campus_smoke_path_is_not_campus_hardcoded() -> None:
    assert client.post("/api/v1/admin/seed", json={"fixture": "community"}).status_code == 200

    bundle = client.get("/api/v1/cases/CASE-COMMUNITY-WATER-001").json()
    combined_text = " ".join(
        [bundle["case"]["title"], bundle["report"]["title"], bundle["report"]["payload"]["draft_summary"]]
        + [signal["title"] for signal in bundle["signals"]]
    ).lower()
    assert "campus" not in combined_text
    assert "water" in combined_text

    for page in ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]:
        page_payload = client.get(f"/api/v1/cases/CASE-COMMUNITY-WATER-001/pages/{page}").json()
        assert page_payload["sections"]
        assert "青澜中学" not in str(page_payload)

    council = client.post("/api/v1/worldline-nodes/NODE-WATER-C1/run-council")
    assert council.status_code == 200
    agents = council.json()["payload"]["agents"]
    residents = [agent for agent in agents if agent["role"] == "residents"][0]
    assert residents["blocked_claims"] == ["unsupported claim: assigning individual blame without confirmed evidence"]


def test_compliance_policy_masks_sensitive_text_and_blocks_unauthorized_sources() -> None:
    assert source_allowed("public_web", "active") == (True, None)
    assert source_allowed("private_chat", "active") == (False, "source_not_allowed_for_p0")
    assert source_allowed("manual_upload", "inactive") == (False, "source_inactive")

    masked = mask_sensitive_text("minor name: Zhang, class 7-3, phone 13900000000")
    assert "Zhang" not in masked
    assert "7-3" not in masked
    assert "13900000000" not in masked
