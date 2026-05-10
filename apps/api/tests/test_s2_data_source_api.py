from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import time
import zipfile
import zlib
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from uuid import uuid4

os.environ["WORLDLINE_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["WORLDLINE_AUTO_CREATE_TABLES"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from worldline_api.database import engine
from worldline_api import adapters, data_sources
from worldline_api import foundation
from worldline_api.foundation import BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_ADMIN_USERNAME
from worldline_api.main import app
from worldline_api import models
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


def _unique_name(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def _compliance_payload(reason: str = "S2 compliance tags saved") -> dict:
    return {
        "authorization_scope": "public_sector_notice",
        "authorization_basis": "Xi'an first-phase public notice synthetic adapter; no private-domain data.",
        "retention_days": 180,
        "data_classification": "public",
        "pii_policy": "masked",
        "synthetic_allowed": True,
        "reason": reason,
    }


def _complete_collection_run_for_test(run_id: str) -> None:
    with Session(engine) as db:
        run = db.get(models.CollectionRun, run_id)
        assert run is not None
        run.status = "completed"
        run.record_count = max(run.record_count, 1)
        run.payload = {**(run.payload or {}), "test_completion": True}
        workflow_run_id = (run.payload or {}).get("workflow_run_id")
        if workflow_run_id:
            workflow = db.get(models.WorkflowRun, workflow_run_id)
            if workflow is not None:
                workflow.status = "completed"
                workflow.payload = {**(workflow.payload or {}), "test_completion": True}
        health = db.execute(select(models.SourceHealth).where(models.SourceHealth.data_source_id == run.data_source_id)).scalar_one_or_none()
        if health is not None:
            health.status = "healthy"
            health.last_run_id = run.id
            health.success_count += 1
            health.last_error_code = None
            health.payload = {**(health.payload or {}), "last_success": {"collection_run_id": run.id}}
        db.commit()


def test_s2_data_source_policy_collection_and_synthetic_raw_chain() -> None:
    headers = _headers()

    types = client.get("/api/v1/data-source-types", headers=headers)
    assert types.status_code == 200
    assert {item["source_type"] for item in types.json()["data"]} >= {"synthetic", "public_web", "official_api", "media"}

    blocked_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": "Blocked private scrape", "source_type": "public_web", "policy": {"access_mode": "cookie_pool"}},
    )
    assert blocked_source.status_code == 200, blocked_source.text
    blocked = blocked_source.json()["data"]
    assert blocked["status"] == "blocked"

    policy = client.post(f"/api/v1/data-sources/{blocked['data_source_id']}/policy-check", headers=headers)
    assert policy.status_code == 200
    assert policy.json()["data"]["allowed"] is False

    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": blocked["data_source_id"], "name": "Blocked run should not collect"},
    )
    assert job.status_code == 200
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200
    assert run.json()["data"]["status"] == "failed"
    assert run.json()["data"]["error_code"] == "SOURCE_POLICY_BLOCKED"

    synthetic = client.post("/api/v1/synthetic-scenarios/xian-social-issues", headers=headers)
    assert synthetic.status_code == 200, synthetic.text
    payload = synthetic.json()["data"]
    assert payload["collection_run"]["status"] == "completed"
    assert payload["collection_run"]["record_count"] == 6
    assert all(item["is_synthetic"] is True for item in payload["raw_records"])

    raw_records = client.get("/api/v1/raw-records", headers=headers)
    assert raw_records.status_code == 200
    first = raw_records.json()["data"][0]
    assert first["city_id"] == "xian"
    assert first["payload"]["source_flags"]["synthetic"] is True

    detail = client.get(f"/api/v1/raw-records/{first['raw_record_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["masked_text"]

    label = client.post(
        f"/api/v1/raw-records/{first['raw_record_id']}/labels",
        headers=headers,
        json={"label": "xian_social_issue_seed", "reason": "S2 synthetic chain validation"},
    )
    assert label.status_code == 200

    lineage = client.get("/api/v1/lineage", params={"object_type": "raw_record", "object_id": first["raw_record_id"]}, headers=headers)
    assert lineage.status_code == 200
    assert any(edge["is_synthetic"] is True for edge in lineage.json()["data"])

    health = client.get("/api/v1/data-sources/health-view", headers=headers)
    assert health.status_code == 200
    assert health.json()["data"]["page_state"] == "ready"

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    actions = {entry["action"] for entry in audit}
    assert {"data_source.create", "data_source.policy_check", "collection_job.create", "synthetic_xian_samples.generate", "raw_record.label"}.issubset(actions)


def test_s2_public_web_registry_validation_and_crawl_policy_contract() -> None:
    headers = _headers()

    types = client.get("/api/v1/data-source-types", headers=headers)
    assert types.status_code == 200
    assert {item["source_type"] for item in types.json()["data"]} >= {
        "public_web",
        "official_api",
        "rss",
        "file_upload",
        "webhook",
        "manual",
        "db_import",
        "object_storage",
    }

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": "S2 public web validation source",
            "source_type": "public_web",
            "policy": {"access_mode": "public_web", "base_url": "synthetic://xian/public-notice"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()["data"]

    validation = client.post(
        f"/api/v1/data-sources/{source['data_source_id']}/validate-url",
        headers=headers,
        json={"url": "synthetic://xian/public-notice"},
    )
    assert validation.status_code == 200, validation.text
    validation_data = validation.json()["data"]
    assert validation_data["reachable"] is True
    assert validation_data["status_code"] == 200
    assert validation_data["is_synthetic"] is True

    bad_validation = client.post(
        f"/api/v1/data-sources/{source['data_source_id']}/validate-url",
        headers=headers,
        json={"url": "file:///etc/passwd"},
    )
    assert bad_validation.status_code == 422

    crawl_policy = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/crawl-policy",
        headers=headers,
        json={"start_url": "synthetic://xian/public-notice", "max_depth": 2, "respect_robots": True, "rate_limit_per_minute": 30},
    )
    assert crawl_policy.status_code == 200, crawl_policy.text
    saved = crawl_policy.json()["data"]
    assert saved["policy"]["crawl_policy"]["start_url"] == "synthetic://xian/public-notice"
    assert saved["policy"]["crawl_policy"]["max_depth"] == 2
    assert saved["policy"]["policy_result"]["allowed"] is True

    refreshed = client.get("/api/v1/data-sources", headers=headers)
    assert refreshed.status_code == 200
    stored = next(item for item in refreshed.json()["data"] if item["data_source_id"] == source["data_source_id"])
    assert stored["policy"]["url_validation"]["reachable"] is True
    assert stored["policy"]["crawl_policy"]["rate_limit_per_minute"] == 30

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    actions = {entry["action"] for entry in audit}
    assert {"data_source.validate_url", "data_source.crawl_policy.update"}.issubset(actions)


def test_s2_data_source_list_filters_pagination_and_duplicate_conflict() -> None:
    headers = _headers()
    prefix = _unique_name("S2 filtered source")
    created = []
    for source_type, policy in [
        ("public_web", {"access_mode": "public_web"}),
        ("synthetic", {"access_mode": "test_fixture"}),
        ("official_api", {}),
    ]:
        response = client.post(
            "/api/v1/data-sources",
            headers=headers,
            json={"name": f"{prefix} {source_type}", "source_type": source_type, "policy": policy},
        )
        assert response.status_code == 200, response.text
        created.append(response.json()["data"])
    assert created[2]["status"] == "blocked"

    duplicate = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} public_web", "source_type": "public_web", "policy": {"access_mode": "public_web"}},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DATA_SOURCE_DUPLICATE"

    public_web = client.get("/api/v1/data-sources", headers=headers, params={"source_type": "public_web", "page": 1, "page_size": 50})
    assert public_web.status_code == 200
    assert all(item["source_type"] == "public_web" for item in public_web.json()["data"])
    assert public_web.json()["meta"]["pagination"]["total"] >= 1

    blocked = client.get("/api/v1/data-sources", headers=headers, params={"status": "blocked", "page": 1, "page_size": 10})
    assert blocked.status_code == 200
    assert any(item["data_source_id"] == created[2]["data_source_id"] for item in blocked.json()["data"])
    assert all(item["status"] == "blocked" for item in blocked.json()["data"])

    first_page = client.get("/api/v1/data-sources", headers=headers, params={"page": 1, "page_size": 1})
    second_page = client.get("/api/v1/data-sources", headers=headers, params={"page": 2, "page_size": 1})
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["meta"]["pagination"]["page_size"] == 1
    assert first_page.json()["data"][0]["data_source_id"] != second_page.json()["data"][0]["data_source_id"]

    invalid = client.get("/api/v1/data-sources", headers=headers, params={"status": "deleted"})
    assert invalid.status_code == 422


def test_s2_official_api_auth_connection_and_pagination_contract() -> None:
    headers = _headers()
    prefix = _unique_name("S2 official API")

    insecure = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} insecure", "source_type": "official_api", "policy": {"base_url": "http://api.example.invalid"}},
    )
    assert insecure.status_code == 422
    assert insecure.json()["error"]["code"] == "OFFICIAL_API_HTTPS_REQUIRED"

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} synthetic",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()["data"]
    assert source["status"] == "blocked"
    assert source["is_synthetic"] is True
    assert source["policy"]["policy_result"]["reason"] == "official_api_key_missing"

    plaintext_auth = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/xian-official", "api_key": "plain-secret-value"},
    )
    assert plaintext_auth.status_code == 422

    auth = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/xian-official", "header_name": "X-API-Key"},
    )
    assert auth.status_code == 200, auth.text
    authed_source = auth.json()["data"]
    assert authed_source["status"] == "active"
    assert authed_source["policy"]["auth"]["secret_ref"] == "vault://s2/xian-official"
    assert "plain-secret-value" not in json.dumps(authed_source, ensure_ascii=False)

    connection = client.post(
        f"/api/v1/data-sources/{source['data_source_id']}/test-connection",
        headers=headers,
        json={"sample_path": "/xian/issues", "expected_status": 200},
    )
    assert connection.status_code == 200, connection.text
    connection_data = connection.json()["data"]
    assert connection_data["status"] == "ok"
    assert connection_data["status_code"] == 200
    assert connection_data["is_synthetic"] is True
    assert connection_data["classification"] == "ok"
    assert connection_data["sample_metadata"]["sample_path"] == "/xian/issues"

    missing_next_path = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/pagination",
        headers=headers,
        json={"strategy": "next_url", "dry_run": True},
    )
    assert missing_next_path.status_code == 422
    assert missing_next_path.json()["error"]["code"] == "PAGINATION_NEXT_URL_PATH_MISSING"

    pagination = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/pagination",
        headers=headers,
        json={"strategy": "page", "page_param": "page", "page_size_param": "limit", "max_pages": 3, "dry_run": True},
    )
    assert pagination.status_code == 200, pagination.text
    paginated_source = pagination.json()["data"]
    assert paginated_source["policy"]["pagination"]["strategy"] == "page"
    assert paginated_source["policy"]["pagination_dry_run"]["page_count"] == 3
    assert paginated_source["policy"]["pagination_dry_run"]["status"] == "ok"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "plain-secret-value" not in audit_payload
    assert "data_source.auth.update" in audit_payload
    assert "data_source.connection_test" in audit_payload
    assert "data_source.pagination.update" in audit_payload


def test_s2_official_api_fetch_activity_paginates_json_and_classifies_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 official API fetch")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    auth = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/fetch-official", "header_name": "X-API-Key"},
    )
    assert auth.status_code == 200, auth.text
    pagination = client.put(
        f"/api/v1/data-sources/{source_id}/pagination",
        headers=headers,
        json={"strategy": "page", "page_param": "page", "page_size_param": "limit", "max_pages": 100, "dry_run": True},
    )
    assert pagination.status_code == 200, pagination.text

    fetched = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "西安官方接口分页拉取",
            "source_uri": "synthetic://xian/official-api/issues",
            "payload": {"page_size": 1},
        },
    )
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["import_run"]["status"] == "completed"
    assert data["collection_run"]["status"] == "completed"
    assert data["collection_run"]["record_count"] == 100
    assert len(data["raw_records"]) == 100
    assert data["import_run"]["payload"]["official_api_activity"]["activity_name"] == "fetch_official_api_page"
    assert data["import_run"]["payload"]["official_api_activity"]["page_count"] == 100
    assert data["raw_records"][0]["payload"]["official_api_activity"]["activity_name"] == "fetch_official_api_page"
    assert data["raw_records"][0]["payload"]["page_number"] == 1
    run_id = data["collection_run"]["collection_run_id"]
    workflow_run_id = data["collection_run"]["payload"]["workflow_run_id"]

    with Session(engine) as db:
        payloads = [
            item
            for item in db.execute(
                select(models.RawRecordPayload)
                .join(models.RawRecord, models.RawRecordPayload.raw_record_id == models.RawRecord.id)
                .where(models.RawRecord.collection_run_id == run_id)
            ).scalars()
        ]
        assert len(payloads) == 100
        assert all(item.payload["activity_name"] == "fetch_official_api_page" for item in payloads)
        assert "\"synthetic\"" in payloads[0].content_text
        events = [
            event.event_type
            for event in db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars()
        ]
        assert "fetch_official_api_page_started" in events
        assert "fetch_official_api_page_completed" in events
        workflow_events = [
            event.event_type
            for event in db.execute(select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow_run_id)).scalars()
        ]
        assert "activity_started" in workflow_events
        assert "activity_completed" in workflow_events

    steps = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    step_by_key = {item["step_key"]: item for item in steps.json()["data"]["steps"]}
    assert step_by_key["fetch"]["status"] == "completed"
    assert step_by_key["store"]["status"] == "completed"

    failure_cases = [
        ("unauthorized", "synthetic://xian/official-api/401", "OFFICIAL_API_UNAUTHORIZED", False),
        ("rate limited", "synthetic://xian/official-api/429", "OFFICIAL_API_RATE_LIMITED", True),
        ("upstream", "synthetic://xian/official-api/500", "OFFICIAL_API_UPSTREAM_ERROR", True),
    ]
    for title, uri, code, retryable in failure_cases:
        failed = client.post(
            "/api/v1/imports/official-api",
            headers=headers,
            json={"data_source_id": source_id, "title": f"Official API {title}", "source_uri": uri},
        )
        assert failed.status_code == 200, failed.text
        failed_data = failed.json()["data"]
        assert failed_data["import_run"]["status"] == "failed"
        assert failed_data["import_run"]["error_code"] == code
        assert failed_data["collection_run"]["status"] == "failed"
        assert failed_data["raw_records"] == []
        assert failed_data["import_run"]["payload"]["official_api_activity"]["activity_name"] == "fetch_official_api_page"
        assert failed_data["import_run"]["payload"]["official_api_activity"]["retryable"] is retryable

    retry_queue = client.get("/api/v1/ops/retry-queue", headers=headers)
    assert retry_queue.status_code == 200, retry_queue.text
    retry_error_codes = {item["payload"].get("error_code") for item in retry_queue.json()["data"] if item["target_type"] == "import_run"}
    assert {"OFFICIAL_API_RATE_LIMITED", "OFFICIAL_API_UPSTREAM_ERROR"}.issubset(retry_error_codes)


def test_s2_retry_policy_exponential_backoff_and_permanent_error_no_retry() -> None:
    headers = _headers()
    prefix = _unique_name("S2 retry backoff")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "secret_ref": "vault://s2/retry-backoff",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
                "retry_policy": {"max_attempts": 3, "initial_delay_seconds": 5, "multiplier": 2, "max_delay_seconds": 30, "jitter_seconds": 0},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    transient_runs = []
    for _ in range(2):
        failed = client.post(
            "/api/v1/imports/official-api",
            headers=headers,
            json={"data_source_id": source_id, "title": "retryable 429", "source_uri": "synthetic://xian/official-api/429"},
        )
        assert failed.status_code == 200, failed.text
        transient_runs.append(failed.json()["data"])

    permanent = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={"data_source_id": source_id, "title": "permanent 401", "source_uri": "synthetic://xian/official-api/401"},
    )
    assert permanent.status_code == 200, permanent.text
    permanent_data = permanent.json()["data"]
    assert permanent_data["import_run"]["error_code"] == "OFFICIAL_API_UNAUTHORIZED"
    assert permanent_data["import_run"]["payload"]["retry_policy"]["classification"] == "permanent"
    assert permanent_data["import_run"]["payload"]["retry_policy"]["scheduled"] is False

    with Session(engine) as db:
        retry_rows = [
            row
            for row in db.execute(select(models.OpsRetryQueue).where(models.OpsRetryQueue.target_type == "import_run")).scalars()
            if row.payload.get("data_source_id") == source_id and row.payload.get("error_code") == "OFFICIAL_API_RATE_LIMITED"
        ]
        retry_rows.sort(key=lambda row: row.attempts)
        assert [row.attempts for row in retry_rows] == [1, 2]
        assert [row.payload["retry_policy"]["next_delay_seconds"] for row in retry_rows] == [5, 10]
        assert all(row.status == "pending" and row.next_run_at is not None for row in retry_rows)
        assert all(row.payload["retry_policy"]["classification"] == "transient" for row in retry_rows)
        assert all(row.payload["retry_policy"]["max_attempts"] == 3 for row in retry_rows)

        transient_import_ids = [item["import_run"]["import_run_id"] for item in transient_runs]
        persisted_imports = [db.get(models.ImportRun, import_id) for import_id in transient_import_ids]
        assert [item.payload["retry_policy"]["attempt"] for item in persisted_imports if item is not None] == [1, 2]
        transient_collection_ids = [item["collection_run"]["collection_run_id"] for item in transient_runs]
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id.in_(transient_collection_ids))).scalars())
        assert sum(1 for event in events if event.event_type == "retry_backoff_scheduled") == 2

        permanent_import_id = permanent_data["import_run"]["import_run_id"]
        permanent_retry = db.execute(select(models.OpsRetryQueue).where(models.OpsRetryQueue.target_id == permanent_import_id)).scalar_one_or_none()
        assert permanent_retry is None
        permanent_import = db.get(models.ImportRun, permanent_import_id)
        assert permanent_import is not None
        assert permanent_import.payload["retry_policy"]["classification"] == "permanent"
        permanent_events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == permanent_data["collection_run"]["collection_run_id"])).scalars())
        assert any(event.event_type == "retry_not_scheduled" and event.payload["classification"] == "permanent" for event in permanent_events)

    retry_queue = client.get("/api/v1/ops/retry-queue", headers=headers)
    assert retry_queue.status_code == 200, retry_queue.text
    queue_items = [item for item in retry_queue.json()["data"] if item["payload"].get("data_source_id") == source_id and item["payload"].get("error_code") == "OFFICIAL_API_RATE_LIMITED"]
    assert [item["attempts"] for item in sorted(queue_items, key=lambda item: item["attempts"])] == [1, 2]
    assert all(item["payload"]["retry_policy"]["backoff_strategy"] == "exponential" for item in queue_items)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "import.official_api.failed" in audit_payload
    assert "OFFICIAL_API_RATE_LIMITED" in audit_payload
    assert "OFFICIAL_API_UNAUTHORIZED" in audit_payload


def test_s2_dead_letter_queue_persists_failed_payload_and_is_idempotent() -> None:
    headers = _headers()
    prefix = _unique_name("S2 dead letter")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "secret_ref": "vault://s2/dead-letter",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
                "retry_policy": {"max_attempts": 3, "initial_delay_seconds": 5, "multiplier": 2, "max_delay_seconds": 30, "jitter_seconds": 0},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    failed = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={"data_source_id": source_id, "title": "dead letter permanent 401", "source_uri": "synthetic://xian/official-api/401"},
    )
    assert failed.status_code == 200, failed.text
    failed_data = failed.json()["data"]
    import_run_id = failed_data["import_run"]["import_run_id"]
    collection_run_id = failed_data["collection_run"]["collection_run_id"]

    dead_letters = client.get("/api/v1/dead-letters", headers=headers, params={"data_source_id": source_id})
    assert dead_letters.status_code == 200, dead_letters.text
    rows = dead_letters.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["target_type"] == "import_run"
    assert row["target_id"] == import_run_id
    assert row["collection_run_id"] == collection_run_id
    assert row["data_source_id"] == source_id
    assert row["error_code"] == "OFFICIAL_API_UNAUTHORIZED"
    assert row["retryable"] is False
    assert row["classification"] == "permanent"
    assert row["status"] == "open"
    assert row["payload"]["failure_payload"]["source_uri"] == "synthetic://xian/official-api/401"
    assert row["payload"]["retry_policy"]["scheduled"] is False

    with Session(engine) as db:
        source = db.get(models.DataSource, source_id)
        run = db.get(models.CollectionRun, collection_run_id)
        import_run = db.get(models.ImportRun, import_run_id)
        assert source is not None and run is not None and import_run is not None
        before_count = db.execute(select(func.count()).select_from(models.OpsErrorQueue).where(models.OpsErrorQueue.source == "dead_letter")).scalar_one()
        first = data_sources._record_dead_letter(
            db,
            run,
            import_run,
            source,
            "OFFICIAL_API_UNAUTHORIZED",
            "Official API returned 401 Unauthorized.",
            failed_data["import_run"]["payload"]["retry_policy"],
        )
        second = data_sources._record_dead_letter(
            db,
            run,
            import_run,
            source,
            "OFFICIAL_API_UNAUTHORIZED",
            "Official API returned 401 Unauthorized.",
            failed_data["import_run"]["payload"]["retry_policy"],
        )
        db.commit()
        after_count = db.execute(select(func.count()).select_from(models.OpsErrorQueue).where(models.OpsErrorQueue.source == "dead_letter")).scalar_one()
        assert first.id == second.id
        assert after_count == before_count

    filtered = client.get("/api/v1/dead-letters", headers=headers, params={"status": "open", "error_code": "OFFICIAL_API_UNAUTHORIZED", "page_size": 10})
    assert filtered.status_code == 200, filtered.text
    assert any(item["target_id"] == import_run_id for item in filtered.json()["data"])
    assert filtered.json()["meta"]["pagination"]["total"] >= 1

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "dead_letter.create" in audit_payload
    assert "OFFICIAL_API_UNAUTHORIZED" in audit_payload


def test_s2_dead_letter_replay_continues_from_failure_and_is_idempotent() -> None:
    headers = _headers()
    prefix = _unique_name("S2 dead letter replay")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "secret_ref": "vault://s2/dead-letter-replay",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
                "pagination": {"strategy": "page", "page_param": "page", "page_size_param": "limit", "max_pages": 1},
                "retry_policy": {"max_attempts": 3, "initial_delay_seconds": 5, "multiplier": 2, "max_delay_seconds": 30, "jitter_seconds": 0},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    failed = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={"data_source_id": source_id, "title": "dead letter replay 401", "source_uri": "synthetic://xian/official-api/401", "payload": {"page_size": 2}},
    )
    assert failed.status_code == 200, failed.text
    failed_import_id = failed.json()["data"]["import_run"]["import_run_id"]
    dead_letters = client.get("/api/v1/dead-letters", headers=headers, params={"data_source_id": source_id, "error_code": "OFFICIAL_API_UNAUTHORIZED"})
    assert dead_letters.status_code == 200, dead_letters.text
    dead_letter_id = dead_letters.json()["data"][0]["dead_letter_id"]

    replay = client.post(
        f"/api/v1/dead-letters/{dead_letter_id}/replay",
        headers=headers,
        json={"source_uri": "synthetic://xian/official-api/issues", "reason": "AT-080 replay with corrected official API source URI."},
    )
    assert replay.status_code == 200, replay.text
    replay_data = replay.json()["data"]
    assert replay_data["dead_letter"]["status"] == "resolved"
    assert replay_data["replay"]["status"] == "completed"
    assert replay_data["replay"]["dead_letter_id"] == dead_letter_id
    assert replay_data["replay"]["original_import_run_id"] == failed_import_id
    assert replay_data["replay_result"]["import_run"]["status"] == "completed"
    assert replay_data["replay_result"]["import_run"]["record_count"] == 2
    assert replay_data["replay_result"]["import_run"]["payload"]["dead_letter_replay"]["dead_letter_id"] == dead_letter_id
    replay_import_id = replay_data["replay"]["replay_import_run_id"]
    replay_collection_id = replay_data["replay"]["replay_collection_run_id"]

    with Session(engine) as db:
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one()
        assert raw_count == 2
        row = db.get(models.OpsErrorQueue, dead_letter_id)
        assert row is not None
        assert row.status == "resolved"
        assert row.payload["replay"]["replay_import_run_id"] == replay_import_id
        run = db.get(models.CollectionRun, replay_collection_id)
        import_run = db.get(models.ImportRun, replay_import_id)
        assert run is not None and import_run is not None
        assert run.payload["dead_letter_replay"]["replay_from_step"] == "fetch"
        assert import_run.payload["dead_letter_replay"]["source_uri"] == "synthetic://xian/official-api/issues"
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == replay_collection_id)).scalars())
        assert any(event.event_type == "dead_letter_replay_completed" for event in events)

    replay_again = client.post(
        f"/api/v1/dead-letters/{dead_letter_id}/replay",
        headers=headers,
        json={"source_uri": "synthetic://xian/official-api/issues", "reason": "AT-080 idempotent replay."},
    )
    assert replay_again.status_code == 200, replay_again.text
    assert replay_again.json()["data"]["replay"]["status"] == "already_completed"
    assert replay_again.json()["data"]["replay"]["replay_import_run_id"] == replay_import_id
    with Session(engine) as db:
        raw_count_after = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one()
        assert raw_count_after == 2

    resolved = client.get("/api/v1/dead-letters", headers=headers, params={"status": "resolved", "data_source_id": source_id})
    assert resolved.status_code == 200, resolved.text
    assert any(item["dead_letter_id"] == dead_letter_id for item in resolved.json()["data"])

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "dead_letter.replay.completed" in audit_payload


def test_s2_dead_letter_replay_rejects_incompatible_source_version() -> None:
    headers = _headers()
    prefix = _unique_name("S2 dead letter replay version")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "secret_ref": "vault://s2/dead-letter-replay-v1",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
                "pagination": {"strategy": "page", "page_param": "page", "page_size_param": "limit", "max_pages": 1},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-080 replay version compliance v1"))
    assert compliance.status_code == 200, compliance.text
    v1 = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-080 publish v1"})
    assert v1.status_code == 200, v1.text

    failed = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={"data_source_id": source_id, "title": "dead letter replay version 401", "source_uri": "synthetic://xian/official-api/401"},
    )
    assert failed.status_code == 200, failed.text
    dead_letters = client.get("/api/v1/dead-letters", headers=headers, params={"data_source_id": source_id, "error_code": "OFFICIAL_API_UNAUTHORIZED"})
    assert dead_letters.status_code == 200, dead_letters.text
    dead_letter = dead_letters.json()["data"][0]
    assert dead_letter["payload"]["source_version"]["data_source_version"] == 1

    auth = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/dead-letter-replay-v2", "header_name": "X-API-Key", "reason": "AT-080 mutate source config before replay"},
    )
    assert auth.status_code == 200, auth.text
    v2 = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-080 publish v2"})
    assert v2.status_code == 200, v2.text
    assert v2.json()["data"]["config_hash"] != v1.json()["data"]["config_hash"]

    replay = client.post(
        f"/api/v1/dead-letters/{dead_letter['dead_letter_id']}/replay",
        headers=headers,
        json={"source_uri": "synthetic://xian/official-api/issues", "reason": "AT-080 replay stale version"},
    )
    assert replay.status_code == 409, replay.text
    assert replay.json()["error"]["code"] == "DATA_SOURCE_VERSION_INCOMPATIBLE"


def test_s2_raw_record_repository_batch_persists_source_run_hash_uri_metadata_and_scope_guards() -> None:
    headers = _headers()
    prefix = _unique_name("S2 raw repository")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} repository job", "payload": {"repository_probe": True}},
    )
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    collection_run_id = run.json()["data"]["collection_run_id"]

    first_content = "Xi'an raw repository content with contact 13800138000 for masking."
    first_hash = hashlib.sha256(first_content.encode("utf-8")).hexdigest()
    missing_run = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={"data_source_id": source_id, "records": [{"title": "Missing run", "content": "no run"}]},
    )
    assert missing_run.status_code == 422
    assert missing_run.json()["error"]["code"] == "RAW_RECORD_RUN_REQUIRED"

    stored = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": collection_run_id,
            "complete_run": True,
            "response_limit": 2,
            "records": [
                {
                    "title": "Repository item one",
                    "content": first_content,
                    "content_hash": first_hash,
                    "raw_uri": "synthetic://xian/raw-repository/one",
                    "metadata": {"district": "beilin", "source_file": "repo-one.json"},
                    "external_id": "repo-one",
                    "city_id": "xian",
                    "is_synthetic": True,
                    "payload": {"topic_hint": "pension_queue"},
                },
                {
                    "title": "Repository item two",
                    "content": "Xi'an raw repository second content.",
                    "raw_uri": "synthetic://xian/raw-repository/two",
                    "metadata": {"district": "yanta", "source_file": "repo-two.json"},
                    "external_id": "repo-two",
                    "city_id": "xian",
                    "is_synthetic": True,
                },
            ],
            "reason": "AT-081 raw repository acceptance",
        },
    )
    assert stored.status_code == 201, stored.text
    data = stored.json()["data"]
    assert data["status"] == "stored"
    assert data["repository"]["activity_name"] == "raw_record_repository_store"
    assert data["repository"]["stored_count"] == 2
    assert data["repository"]["raw_uri_count"] == 2
    assert data["repository"]["metadata_count"] == 2
    assert data["collection_run"]["status"] == "completed"
    assert data["collection_run"]["record_count"] == 2
    assert len(data["raw_records"]) == 2
    first = data["raw_records"][0]
    assert first["data_source_id"] == source_id
    assert first["collection_run_id"] == collection_run_id
    assert first["content_hash"] == first_hash
    assert first["payload"]["raw_uri"] == "synthetic://xian/raw-repository/one"
    assert first["payload"]["metadata"]["source_file"] == "repo-one.json"
    assert first["payload"]["external_id"] == "repo-one"

    with Session(engine) as db:
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.collection_run_id == collection_run_id)).scalar_one()
        assert raw_count == 2
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == first["raw_record_id"])).scalar_one()
        assert "raw repository content" in payload.content_text
        assert "13800138000" not in payload.masked_text
        assert payload.payload["raw_uri"] == "synthetic://xian/raw-repository/one"
        assert payload.payload["metadata"]["district"] == "beilin"
        edges = list(
            db.execute(
                select(models.LineageEdge).where(
                    models.LineageEdge.to_object_type == "raw_record",
                    models.LineageEdge.to_object_id == first["raw_record_id"],
                )
            ).scalars()
        )
        assert {edge.from_object_type for edge in edges} >= {"data_source", "collection_run"}
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == collection_run_id)).scalars())
        assert any(event.event_type == "raw_record_repository_batch_stored" and event.payload["stored_count"] == 2 for event in events)

    other_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} other source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert other_source.status_code == 200, other_source.text
    mismatch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": other_source.json()["data"]["data_source_id"],
            "collection_run_id": collection_run_id,
            "records": [{"title": "Wrong source", "content": "wrong source"}],
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "RAW_RECORD_RUN_SOURCE_MISMATCH"

    synthetic_job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} synthetic repository job", "payload": {"repository_probe": "synthetic_count"}},
    )
    assert synthetic_job.status_code == 200, synthetic_job.text
    synthetic_run = client.post(f"/api/v1/collection-jobs/{synthetic_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert synthetic_run.status_code == 200, synthetic_run.text
    synthetic = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": synthetic_run.json()["data"]["collection_run_id"],
            "synthetic_count": 25,
            "response_limit": 3,
            "reason": "AT-081 synthetic bulk path",
            "payload": {"batch_probe": True},
        },
    )
    assert synthetic.status_code == 201, synthetic.text
    assert synthetic.json()["data"]["repository"]["stored_count"] == 25
    assert synthetic.json()["data"]["repository"]["supports_million_record_batch"] is True
    assert len(synthetic.json()["data"]["raw_records"]) == 3

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "raw_record.repository.batch_create" in audit_payload


def test_s2_raw_hash_repository_idempotency_dedupe_and_conflict_stats() -> None:
    headers = _headers()
    prefix = _unique_name("S2 raw hash")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    def new_run(label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"raw_hash_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    content = "Xi'an raw hash idempotent content"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    external_id = f"petition-row-{uuid4().hex[:8]}"
    first_run_id = new_run("first")
    first = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": first_run_id,
            "complete_run": True,
            "records": [{"title": "Raw hash first", "content": content, "content_hash": content_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-082 first write",
        },
    )
    assert first.status_code == 201, first.text
    first_data = first.json()["data"]
    assert first_data["repository"]["stored_count"] == 1
    assert first_data["repository"]["duplicate_count"] == 0
    assert first_data["repository"]["conflict_count"] == 0
    first_raw_id = first_data["raw_records"][0]["raw_record_id"]

    duplicate_run_id = new_run("duplicate")
    duplicate = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": duplicate_run_id,
            "complete_run": True,
            "records": [{"title": "Raw hash duplicate", "content": content, "content_hash": content_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-082 duplicate write",
        },
    )
    assert duplicate.status_code == 201, duplicate.text
    duplicate_repo = duplicate.json()["data"]["repository"]
    assert duplicate_repo["status"] == "deduped"
    assert duplicate_repo["stored_count"] == 0
    assert duplicate_repo["duplicate_count"] == 1
    assert duplicate_repo["conflict_count"] == 0
    assert duplicate_repo["dedupe_hit_rate"] == 1.0
    assert duplicate_repo["duplicate_refs"][0]["existing_raw_record_id"] == first_raw_id
    with Session(engine) as db:
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one()
        assert raw_count == 1
        duplicate_events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == duplicate_run_id)).scalars())
        assert any(event.event_type == "raw_record_repository_dedupe_skipped" and event.payload["duplicate_count"] == 1 for event in duplicate_events)

    conflict_content = "Xi'an raw hash conflict content with the same external id."
    conflict_hash = hashlib.sha256(conflict_content.encode("utf-8")).hexdigest()
    conflict_run_id = new_run("conflict")
    conflict = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": conflict_run_id,
            "complete_run": True,
            "records": [{"title": "Raw hash conflict", "content": conflict_content, "content_hash": conflict_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-082 conflict write",
        },
    )
    assert conflict.status_code == 201, conflict.text
    conflict_repo = conflict.json()["data"]["repository"]
    assert conflict_repo["status"] == "conflict"
    assert conflict_repo["stored_count"] == 0
    assert conflict_repo["duplicate_count"] == 0
    assert conflict_repo["conflict_count"] == 1
    assert conflict_repo["conflict_refs"][0]["existing_raw_record_id"] == first_raw_id
    assert conflict_repo["conflict_refs"][0]["incoming_content_hash"] == conflict_hash
    with Session(engine) as db:
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one()
        assert raw_count == 1
        conflict_events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == conflict_run_id)).scalars())
        assert any(event.event_type == "raw_record_repository_hash_conflict" and event.payload["conflict_count"] == 1 for event in conflict_events)
        conflict_errors = list(db.execute(select(models.OpsErrorQueue).where(models.OpsErrorQueue.source == "raw_hash_conflict")).scalars())
        assert any(item.payload.get("external_id") == external_id and item.payload.get("existing_raw_record_id") == first_raw_id for item in conflict_errors)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "raw_record.repository.hash_conflict" in audit_payload


def test_s2_collection_run_metrics_counts_dedupe_failure_and_consistency() -> None:
    headers = _headers()
    prefix = _unique_name("S2 run metrics")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    def new_run(label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"metrics_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    content = "Xi'an collection run metrics source content"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    external_id = f"metrics-row-{uuid4().hex[:8]}"
    first_run_id = new_run("first")
    first = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": first_run_id,
            "complete_run": True,
            "records": [{"title": "Metrics first", "content": content, "content_hash": content_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-084 metrics first write",
        },
    )
    assert first.status_code == 201, first.text

    duplicate_run_id = new_run("duplicate")
    duplicate = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": duplicate_run_id,
            "complete_run": True,
            "records": [{"title": "Metrics duplicate", "content": content, "content_hash": content_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-084 metrics duplicate write",
        },
    )
    assert duplicate.status_code == 201, duplicate.text

    conflict_content = "Xi'an collection run metrics conflict content"
    conflict_hash = hashlib.sha256(conflict_content.encode("utf-8")).hexdigest()
    conflict_run_id = new_run("conflict")
    conflict = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": conflict_run_id,
            "complete_run": True,
            "records": [{"title": "Metrics conflict", "content": conflict_content, "content_hash": conflict_hash, "external_id": external_id, "is_synthetic": True}],
            "reason": "AT-084 metrics conflict write",
        },
    )
    assert conflict.status_code == 201, conflict.text

    first_metrics = client.get(f"/api/v1/collection-runs/{first_run_id}/metrics", headers=headers)
    assert first_metrics.status_code == 200, first_metrics.text
    first_data = first_metrics.json()["data"]
    assert first_data["metrics"]["fetched_count"] == 1
    assert first_data["metrics"]["parsed_count"] == 1
    assert first_data["metrics"]["stored_count"] == 1
    assert first_data["metrics"]["failed_count"] == 0
    assert first_data["metrics"]["deduped_count"] == 0
    assert first_data["consistency"]["status"] == "consistent"
    assert first_data["consistency"]["db_raw_record_count"] == 1
    assert first_data["snapshot"]["metric_scope"] == f"collection_run:{first_run_id}"

    duplicate_metrics = client.get(f"/api/v1/collection-runs/{duplicate_run_id}/metrics", headers=headers)
    assert duplicate_metrics.status_code == 200, duplicate_metrics.text
    duplicate_data = duplicate_metrics.json()["data"]
    assert duplicate_data["metrics"]["fetched_count"] == 1
    assert duplicate_data["metrics"]["stored_count"] == 0
    assert duplicate_data["metrics"]["deduped_count"] == 1
    assert duplicate_data["metrics"]["failed_count"] == 0
    assert duplicate_data["consistency"]["status"] == "consistent"

    conflict_metrics = client.get(f"/api/v1/collection-runs/{conflict_run_id}/metrics", headers=headers)
    assert conflict_metrics.status_code == 200, conflict_metrics.text
    conflict_data = conflict_metrics.json()["data"]
    assert conflict_data["metrics"]["fetched_count"] == 1
    assert conflict_data["metrics"]["stored_count"] == 0
    assert conflict_data["metrics"]["failed_count"] == 1
    assert conflict_data["metrics"]["conflict_count"] == 1
    assert conflict_data["consistency"]["status"] == "consistent"

    multi_run_id = new_run("multi-batch")
    for index in range(2):
        multi_content = f"Xi'an collection run metrics multi-batch content {index} {uuid4().hex}"
        multi = client.post(
            "/api/v1/raw-records/batches",
            headers=headers,
            json={
                "data_source_id": source_id,
                "collection_run_id": multi_run_id,
                "complete_run": index == 1,
                "records": [
                    {
                        "title": f"Metrics multi batch {index}",
                        "content": multi_content,
                        "content_hash": hashlib.sha256(multi_content.encode("utf-8")).hexdigest(),
                        "external_id": f"metrics-multi-{index}-{uuid4().hex[:8]}",
                        "is_synthetic": True,
                    }
                ],
                "reason": f"AT-084 metrics multi-batch write {index}",
            },
        )
        assert multi.status_code == 201, multi.text

    multi_metrics = client.get(f"/api/v1/collection-runs/{multi_run_id}/metrics", headers=headers)
    assert multi_metrics.status_code == 200, multi_metrics.text
    multi_data = multi_metrics.json()["data"]
    assert multi_data["metrics"]["fetched_count"] == 2
    assert multi_data["metrics"]["parsed_count"] == 2
    assert multi_data["metrics"]["stored_count"] == 2
    assert multi_data["metrics"]["raw_record_count"] == 2
    assert multi_data["metrics"]["payload_count"] == 2
    assert multi_data["consistency"]["db_raw_record_count"] == 2
    assert multi_data["consistency"]["status"] == "consistent"

    with Session(engine) as db:
        snapshots = list(db.execute(select(models.MetricsSnapshot).where(models.MetricsSnapshot.metric_scope == f"collection_run:{first_run_id}")).scalars())
        assert snapshots
        corrupted = db.get(models.CollectionRun, first_run_id)
        assert corrupted is not None
        corrupted.record_count = 99
        db.commit()

    inconsistent = client.get(f"/api/v1/collection-runs/{first_run_id}/metrics", headers=headers)
    assert inconsistent.status_code == 409
    assert inconsistent.json()["error"]["code"] == "COLLECTION_RUN_METRICS_INCONSISTENT"

    missing = client.get(f"/api/v1/collection-runs/CRUN-{uuid4().hex[:20]}/metrics", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.metrics.read" in audit_payload


def test_s2_cleaning_run_metrics_track_clean_extract_failures_and_consistency() -> None:
    headers = _headers()
    prefix = _unique_name("AT115 cleaning metrics")
    source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "public_web", "policy": {"access_mode": "public_web", "source_trust": {"score": 0.8}}},
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    collection_run_id = run.json()["data"]["collection_run_id"]
    batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": collection_run_id,
            "complete_run": True,
            "records": [
                {
                    "title": "AT-115 clean run metric row",
                    "content": "Xi'an pension service queue metric row with enough content for cleaning and extraction.",
                    "city_id": "xian",
                    "occurred_at": "2026-05-09T10:00:00Z",
                    "is_synthetic": True,
                    "external_id": f"{prefix}-raw",
                }
            ],
            "reason": "AT-115 cleaning run metrics seed",
        },
    )
    assert batch.status_code == 201, batch.text
    raw_id = batch.json()["data"]["raw_records"][0]["raw_record_id"]

    normalization = client.post(
        "/api/v1/normalization-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "normalize_text-at115-v1", "response_limit": 10},
    )
    assert normalization.status_code == 200, normalization.text
    normalization_run_id = normalization.json()["data"]["normalization_run_id"]
    extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "s4a-signal-extraction-at115-v1", "limit": 5},
    )
    assert extraction.status_code == 201, extraction.text

    metrics = client.get(f"/api/v1/cleaning-runs/{collection_run_id}/metrics", headers=headers)
    assert metrics.status_code == 200, metrics.text
    data = metrics.json()["data"]
    assert data["cleaning_run_id"] == collection_run_id
    assert data["collection_run_id"] == collection_run_id
    assert data["metrics"]["parsed_count"] == 1
    assert data["metrics"]["cleaned_count"] == 1
    assert data["metrics"]["extracted_count"] == 1
    assert data["metrics"]["failed_count"] == 0
    assert data["metrics"]["normalization_output_count"] == 1
    assert data["metrics"]["signal_count"] == 1
    assert data["consistency"]["status"] == "consistent"
    assert {check["code"] for check in data["consistency"]["checks"]} >= {
        "cleaned_count_matches_normalization_outputs",
        "extracted_count_matches_signal_lineage",
    }
    assert data["snapshot"]["metric_scope"] == f"cleaning_run:{collection_run_id}"
    assert data["page_state"] == "ready"

    compatibility = client.get(f"/api/v1/collection-runs/{collection_run_id}/metrics", headers=headers)
    assert compatibility.status_code == 200, compatibility.text
    assert compatibility.json()["data"]["metrics"]["cleaned_count"] == 1
    assert compatibility.json()["data"]["metrics"]["extracted_count"] == 1

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at115_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not cleaning run metrics.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at115.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-115 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get(f"/api/v1/cleaning-runs/{collection_run_id}/metrics", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    missing = client.get(f"/api/v1/cleaning-runs/CRUN-{uuid4().hex[:20]}/metrics", headers=headers)
    assert missing.status_code == 404

    with Session(engine) as db:
        run_row = db.get(models.NormalizationRun, normalization_run_id)
        assert run_row is not None
        run_row.output_count = 99
        db.commit()

    inconsistent = client.get(f"/api/v1/cleaning-runs/{collection_run_id}/metrics", headers=headers)
    assert inconsistent.status_code == 409
    assert inconsistent.json()["error"]["code"] == "CLEANING_RUN_METRICS_INCONSISTENT"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "cleaning_run.metrics.read" in audit_payload


def test_s2_html_main_content_parser_extracts_body_and_marks_empty_parse_failed() -> None:
    headers = _headers()
    prefix = _unique_name("S2 HTML parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} public web", "source_type": "public_web", "policy": {"access_mode": "public_web", "base_url": "synthetic://xian/public-web"}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    html = """
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <title>西安养老保险办理进度公告</title>
        <meta property="article:published_time" content="2026-05-09T08:30:00Z">
      </head>
      <body>
        <nav>导航噪声不应进入正文</nav>
        <article>
          <h1>西安养老保险办理进度公告</h1>
          <p>正文第一段：居民关注养老保险补缴情形和窗口排队进度。</p>
          <p>正文第二段：现场咨询电话 13800138000 需要脱敏。</p>
        </article>
        <script>window.noise = true;</script>
      </body>
    </html>
    """
    imported = client.post(
        "/api/v1/imports/public-web",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "HTML parser import",
            "content": html,
            "source_uri": "synthetic://xian/public-web/html-parser",
            "is_synthetic": True,
            "payload": {"at": "AT-085"},
        },
    )
    assert imported.status_code == 200, imported.text
    raw_id = imported.json()["data"]["raw_records"][0]["raw_record_id"]

    parsed = client.post(
        "/api/v1/parser-runs/html-main-content",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "parse_html_main_content-test-v1", "payload": {"at": "AT-085"}},
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_html_main_content"
    assert data["parser"]["parsed_count"] == 1
    assert data["parser"]["failed_count"] == 0
    output = data["outputs"][0]
    assert output["normalized_title"] == "西安养老保险办理进度公告"
    assert "正文第一段" in output["normalized_text"]
    assert "导航噪声" not in output["normalized_text"]
    assert "13800138000" not in output["normalized_text"]
    assert "[MASKED]" in output["normalized_text"]
    assert output["payload"]["parser_status"] == "parsed"
    assert output["payload"]["published_at"] == "2026-05-09T08:30:00Z"
    assert output["payload"]["source_uri"] == "synthetic://xian/public-web/html-parser"

    empty = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": imported.json()["data"]["collection_run"]["collection_run_id"],
            "records": [{"title": "Empty HTML", "content": "<html><head><title>Empty</title></head><body><script>noise()</script></body></html>", "external_id": f"empty-html-{uuid4().hex[:8]}", "is_synthetic": True}],
            "reason": "AT-085 empty HTML parse failure",
        },
    )
    assert empty.status_code == 201, empty.text
    empty_raw_id = empty.json()["data"]["raw_records"][0]["raw_record_id"]
    empty_parsed = client.post(
        "/api/v1/parser-runs/html-main-content",
        headers=headers,
        json={"raw_record_ids": [empty_raw_id], "rule_version": "parse_html_main_content-test-v1"},
    )
    assert empty_parsed.status_code == 201, empty_parsed.text
    empty_data = empty_parsed.json()["data"]
    assert empty_data["parser"]["parsed_count"] == 0
    assert empty_data["parser"]["failed_count"] == 1
    assert empty_data["outputs"][0]["payload"]["parser_status"] == "parse_failed"
    assert empty_data["outputs"][0]["payload"]["error_code"] == "HTML_MAIN_CONTENT_EMPTY"

    foreign_tenant_id = f"TEN-{uuid4().hex[:12]}"
    foreign_source_id = f"DS-{uuid4().hex[:20]}"
    foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
    foreign_run_id = f"CRUN-{uuid4().hex[:20]}"
    foreign_raw_id = f"RAW-{uuid4().hex[:20]}"
    with Session(engine) as db:
        db.add(models.Tenant(id=foreign_tenant_id, name="Foreign parser tenant", status="active", payload={}))
        db.flush()
        db.add(models.DataSource(id=foreign_source_id, tenant_id=foreign_tenant_id, name="Foreign parser source", source_type="public_web", status="active", is_synthetic=True, policy={}, payload={}))
        db.flush()
        db.add(models.CollectionJob(id=foreign_job_id, tenant_id=foreign_tenant_id, data_source_id=foreign_source_id, name="Foreign parser job", status="active", schedule=None, payload={}))
        db.flush()
        db.add(models.CollectionRun(id=foreign_run_id, collection_job_id=foreign_job_id, data_source_id=foreign_source_id, status="completed", record_count=1, trace_id="at085-foreign", payload={}))
        db.flush()
        db.add(
            models.RawRecord(
                id=foreign_raw_id,
                tenant_id=foreign_tenant_id,
                data_source_id=foreign_source_id,
                collection_run_id=foreign_run_id,
                source_type="public_web",
                title="Foreign parser raw",
                content_hash="sha256:foreign-parser",
                status="collected",
                is_synthetic=True,
                city_id="xian",
                occurred_at=datetime.utcnow(),
                payload={"source_uri": "synthetic://foreign/parser"},
            )
        )
        db.add(models.RawRecordPayload(id=f"RAWP-{uuid4().hex[:20]}", raw_record_id=foreign_raw_id, content_text="<article><p>foreign body</p></article>", masked_text="<article><p>foreign body</p></article>", payload={}))
        db.commit()

    foreign_parse = client.post(
        "/api/v1/parser-runs/html-main-content",
        headers=headers,
        json={"raw_record_ids": [foreign_raw_id], "rule_version": "parse_html_main_content-tenant-scope-v1"},
    )
    assert foreign_parse.status_code == 201, foreign_parse.text
    foreign_data = foreign_parse.json()["data"]
    assert foreign_data["status"] == "failed"
    assert foreign_data["error_code"] == "RAW_RECORD_SCOPE_EMPTY"
    assert foreign_data["outputs"] == []
    with Session(engine) as db:
        assert db.execute(select(func.count()).select_from(models.RawRecordNormalization).where(models.RawRecordNormalization.raw_record_id == foreign_raw_id)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(models.LineageEdge).where(models.LineageEdge.from_object_id == foreign_raw_id, models.LineageEdge.to_object_type == "raw_record_normalization")).scalar_one() == 0

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_html_main_content")).scalars())
        assert any(item.object_id == data["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == output["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.html_main_content.completed" in audit_payload


def test_s2_json_by_mapping_parser_extracts_fields_and_marks_mapping_error() -> None:
    headers = _headers()
    prefix = _unique_name("S2 JSON parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    run_id = run.json()["data"]["collection_run_id"]
    parsed_payload = {"headline": "西安窗口办理进度更新", "detail": {"body": "JSON 正文：居民关注养老保险办理进度，联系电话 13800138000。"}, "published": "2026-05-09T11:00:00Z", "source": {"district": "yanta"}}
    missing_payload = {"headline": "缺字段记录", "published": "2026-05-09T12:00:00Z"}
    batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run_id,
            "complete_run": True,
            "records": [
                {"title": "JSON mapping parsed", "content": json.dumps(parsed_payload, ensure_ascii=False), "external_id": f"json-map-{uuid4().hex[:8]}", "is_synthetic": True, "source_type": "official_api"},
                {"title": "JSON mapping missing", "content": json.dumps(missing_payload, ensure_ascii=False), "external_id": f"json-map-missing-{uuid4().hex[:8]}", "is_synthetic": True, "source_type": "official_api"},
            ],
            "reason": "AT-086 JSON mapping parser input",
        },
    )
    assert batch.status_code == 201, batch.text
    raw_ids = [item["raw_record_id"] for item in batch.json()["data"]["raw_records"]]

    mapped = client.post(
        "/api/v1/parser-runs/json-by-mapping",
        headers=headers,
        json={
            "raw_record_ids": raw_ids,
            "rule_version": "parse_json_by_mapping-test-v1",
            "payload": {"mapping": {"title": "$.headline", "body": "$.detail.body", "published_at": "$.published"}},
        },
    )
    assert mapped.status_code == 201, mapped.text
    data = mapped.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_json_by_mapping"
    assert data["parser"]["mapping"] == {"title": "$.headline", "body": "$.detail.body", "published_at": "$.published"}
    assert data["parser"]["parsed_count"] == 1
    assert data["parser"]["failed_count"] == 1
    parsed_output = next(item for item in data["outputs"] if item["payload"]["parser_status"] == "parsed")
    failed_output = next(item for item in data["outputs"] if item["payload"]["parser_status"] == "mapping_error")
    assert parsed_output["normalized_title"] == "西安窗口办理进度更新"
    assert "JSON 正文" in parsed_output["normalized_text"]
    assert "13800138000" not in parsed_output["normalized_text"]
    assert "[MASKED]" in parsed_output["normalized_text"]
    assert parsed_output["payload"]["published_at"] == "2026-05-09T11:00:00Z"
    assert parsed_output["payload"]["mapping"]["body"] == "$.detail.body"
    assert failed_output["payload"]["error_code"] == "JSON_MAPPING_FIELD_MISSING"
    assert failed_output["payload"]["missing_fields"] == ["body"]

    invalid = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run_id,
            "records": [{"title": "Invalid JSON", "content": "{not-json", "external_id": f"json-invalid-{uuid4().hex[:8]}", "is_synthetic": True, "source_type": "official_api"}],
            "reason": "AT-086 invalid JSON parser input",
        },
    )
    assert invalid.status_code == 201, invalid.text
    invalid_raw_id = invalid.json()["data"]["raw_records"][0]["raw_record_id"]
    invalid_mapped = client.post(
        "/api/v1/parser-runs/json-by-mapping",
        headers=headers,
        json={"raw_record_ids": [invalid_raw_id], "rule_version": "parse_json_by_mapping-test-v1", "payload": {"mapping": {"title": "$.headline", "body": "$.detail.body"}}},
    )
    assert invalid_mapped.status_code == 201, invalid_mapped.text
    assert invalid_mapped.json()["data"]["outputs"][0]["payload"]["parser_status"] == "mapping_error"
    assert invalid_mapped.json()["data"]["outputs"][0]["payload"]["error_code"] == "JSON_MAPPING_INVALID"

    omitted_required_mapping = client.post(
        "/api/v1/parser-runs/json-by-mapping",
        headers=headers,
        json={"raw_record_ids": [raw_ids[0]], "rule_version": "parse_json_by_mapping-test-v1", "payload": {"mapping": {"title": "$.headline"}}},
    )
    assert omitted_required_mapping.status_code == 201, omitted_required_mapping.text
    omitted_output = omitted_required_mapping.json()["data"]["outputs"][0]
    assert omitted_output["payload"]["parser_status"] == "mapping_error"
    assert omitted_output["payload"]["error_code"] == "JSON_MAPPING_FIELD_MISSING"
    assert omitted_output["payload"]["missing_fields"] == ["body"]

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_json_by_mapping")).scalars())
        assert any(item.object_id == data["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == parsed_output["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.json_by_mapping.completed" in audit_payload


def test_s2_csv_file_parser_imports_rows_and_marks_file_errors() -> None:
    headers = _headers()
    prefix = _unique_name("S2 CSV parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["csv"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 20,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    def upload_and_import(file_name: str, body: bytes) -> str:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"data_source_id": source_id, "title": file_name, "is_synthetic": "true"},
            files={"file": (file_name, body, "text/csv")},
        )
        assert uploaded.status_code == 201, uploaded.text
        imported = client.post(
            f"/api/v1/collection-jobs/{job_id}/file-runs",
            headers=headers,
            json={"file_object_id": uploaded.json()["data"]["file_object"]["file_object_id"], "title": file_name, "city_id": "xian"},
        )
        assert imported.status_code == 201, imported.text
        return imported.json()["data"]["raw_records"][0]["raw_record_id"]

    csv_raw_id = upload_and_import(
        "xian-notices.csv",
        "title,content,published_at\nCSV 第一行,居民关注养老保险办理，联系电话 13800138000,2026-05-09T12:00:00Z\nCSV 第二行,社区回访进展稳定,2026-05-09T12:05:00Z\n".encode("utf-8"),
    )
    parsed = client.post(
        "/api/v1/parser-runs/csv-file",
        headers=headers,
        json={
            "raw_record_ids": [csv_raw_id],
            "rule_version": "parse_csv_file-test-v1",
            "response_limit": 5,
            "payload": {"mapping": {"title": "title", "body": "content", "published_at": "published_at"}},
        },
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_csv_file"
    assert data["parser"]["parsed_count"] == 2
    assert data["parser"]["failed_count"] == 0
    assert data["parser"]["row_count"] == 2
    assert data["parser"]["response_count"] == 2
    assert data["outputs"][0]["payload"]["parser_status"] == "parsed"
    assert data["outputs"][0]["payload"]["row_number"] == 2
    assert data["outputs"][0]["normalized_title"] == "CSV 第一行"
    assert "13800138000" not in data["outputs"][0]["normalized_text"]
    assert "[MASKED]" in data["outputs"][0]["normalized_text"]
    assert "13800138000" not in data["outputs"][0]["payload"]["columns"]["content"]
    assert "[MASKED]" in data["outputs"][0]["payload"]["columns"]["content"]
    assert data["outputs"][0]["payload"]["published_at"] == "2026-05-09T12:00:00Z"

    missing_raw_id = upload_and_import("xian-missing-column.csv", "title,published_at\nCSV 缺内容,2026-05-09T12:10:00Z\n".encode("utf-8"))
    missing = client.post(
        "/api/v1/parser-runs/csv-file",
        headers=headers,
        json={"raw_record_ids": [missing_raw_id], "rule_version": "parse_csv_file-test-v1", "payload": {"mapping": {"title": "title", "body": "content"}}},
    )
    assert missing.status_code == 201, missing.text
    assert missing.json()["data"]["status"] == "failed"
    assert missing.json()["data"]["error_code"] == "CSV_COLUMNS_MISSING"
    assert missing.json()["data"]["parser"]["missing_columns"] == ["content"]
    assert missing.json()["data"]["outputs"] == []

    invalid_raw_id = upload_and_import("xian-invalid-encoding.csv", b"title,content\nCSV bad,\xff\xfe")
    invalid = client.post(
        "/api/v1/parser-runs/csv-file",
        headers=headers,
        json={"raw_record_ids": [invalid_raw_id], "rule_version": "parse_csv_file-test-v1"},
    )
    assert invalid.status_code == 201, invalid.text
    assert invalid.json()["data"]["status"] == "failed"
    assert invalid.json()["data"]["error_code"] == "CSV_ENCODING_ERROR"
    assert invalid.json()["data"]["outputs"] == []

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_csv_file")).scalars())
        assert any(item.object_id == data["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == data["outputs"][0]["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)
        assert any(item.from_object_type == "raw_record" and item.from_object_id == csv_raw_id for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.csv_file.completed" in audit_payload
    assert "parser.csv_file.failed" in audit_payload


def _xlsx_bytes(
    rows: list[list[str]],
    *,
    sheet_name: str = "Sheet1",
    merged_ref: str | None = None,
    formula_cell: tuple[str, str, str] | None = None,
) -> bytes:
    def column_name(index: int) -> str:
        name = ""
        value = index
        while value:
            value, remainder = divmod(value - 1, 26)
            name = chr(65 + remainder) + name
        return name

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{column_name(column_index)}{row_index}"
            if formula_cell and formula_cell[0] == cell_ref:
                cells.append(f'<c r="{cell_ref}"><f>{formula_cell[1]}</f><v>{formula_cell[2]}</v></c>')
            else:
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    merge_xml = f'<mergeCells count="1"><mergeCell ref="{merged_ref}"/></mergeCells>' if merged_ref else ""
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>{merge_xml}</worksheet>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def test_s2_xlsx_file_parser_imports_range_and_marks_sheet_errors() -> None:
    headers = _headers()
    prefix = _unique_name("S2 XLSX parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["xlsx"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 20,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    def upload_and_import(file_name: str, body: bytes) -> str:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"data_source_id": source_id, "title": file_name, "is_synthetic": "true"},
            files={"file": (file_name, body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert uploaded.status_code == 201, uploaded.text
        imported = client.post(
            f"/api/v1/collection-jobs/{job_id}/file-runs",
            headers=headers,
            json={"file_object_id": uploaded.json()["data"]["file_object"]["file_object_id"], "title": file_name, "city_id": "xian"},
        )
        assert imported.status_code == 201, imported.text
        return imported.json()["data"]["raw_records"][0]["raw_record_id"]

    xlsx_raw_id = upload_and_import(
        "xian-notices.xlsx",
        _xlsx_bytes(
            [
                ["title", "content", "published_at"],
                ["XLSX first row", "Xi'an pension insurance queue phone 13800138000", "2026-05-09T14:00:00Z"],
                ["XLSX second row", "Xi'an community visit stable", "2026-05-09T14:05:00Z"],
            ],
            sheet_name="Sheet1",
        ),
    )
    parsed = client.post(
        "/api/v1/parser-runs/xlsx-file",
        headers=headers,
        json={
            "raw_record_ids": [xlsx_raw_id],
            "rule_version": "parse_xlsx_file-test-v1",
            "response_limit": 5,
            "payload": {"sheet": "Sheet1", "range": "A1:C3", "mapping": {"title": "title", "body": "content", "published_at": "published_at"}},
        },
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_xlsx_file"
    assert data["parser"]["sheet_name"] == "Sheet1"
    assert data["parser"]["cell_range"] == "A1:C3"
    assert data["parser"]["row_count"] == 2
    assert data["parser"]["parsed_count"] == 2
    assert data["outputs"][0]["payload"]["parser_status"] == "parsed"
    assert data["outputs"][0]["payload"]["row_number"] == 2
    assert data["outputs"][0]["normalized_title"] == "XLSX first row"
    assert "13800138000" not in data["outputs"][0]["normalized_text"]
    assert "[MASKED]" in data["outputs"][0]["normalized_text"]
    assert "13800138000" not in data["outputs"][0]["payload"]["columns"]["content"]
    assert "[MASKED]" in data["outputs"][0]["payload"]["columns"]["content"]
    assert data["outputs"][0]["payload"]["published_at"] == "2026-05-09T14:00:00Z"

    missing_sheet = client.post(
        "/api/v1/parser-runs/xlsx-file",
        headers=headers,
        json={"raw_record_ids": [xlsx_raw_id], "rule_version": "parse_xlsx_file-test-v1", "payload": {"sheet": "Missing", "range": "A1:C3"}},
    )
    assert missing_sheet.status_code == 201, missing_sheet.text
    assert missing_sheet.json()["data"]["status"] == "failed"
    assert missing_sheet.json()["data"]["error_code"] == "XLSX_SHEET_NOT_FOUND"
    assert missing_sheet.json()["data"]["outputs"] == []

    merged_raw_id = upload_and_import("xian-merged.xlsx", _xlsx_bytes([["title", "content"], ["Merged", "Merged body"]], merged_ref="A2:B2"))
    merged = client.post(
        "/api/v1/parser-runs/xlsx-file",
        headers=headers,
        json={"raw_record_ids": [merged_raw_id], "rule_version": "parse_xlsx_file-test-v1", "payload": {"range": "A1:B2"}},
    )
    assert merged.status_code == 201, merged.text
    assert merged.json()["data"]["status"] == "failed"
    assert merged.json()["data"]["error_code"] == "XLSX_MERGED_CELLS_UNSUPPORTED"

    formula_raw_id = upload_and_import(
        "xian-formula.xlsx",
        _xlsx_bytes([["title", "content"], ["Formula row", "cached body"]], formula_cell=("B2", "CONCAT(\"cached\",\" body\")", "cached body")),
    )
    formula = client.post(
        "/api/v1/parser-runs/xlsx-file",
        headers=headers,
        json={"raw_record_ids": [formula_raw_id], "rule_version": "parse_xlsx_file-test-v1", "payload": {"range": "A1:B2"}},
    )
    assert formula.status_code == 201, formula.text
    assert formula.json()["data"]["status"] == "failed"
    assert formula.json()["data"]["error_code"] == "XLSX_FORMULA_UNSUPPORTED"

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_xlsx_file")).scalars())
        assert any(item.object_id == data["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == data["outputs"][0]["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)
        assert any(item.from_object_type == "raw_record" and item.from_object_id == xlsx_raw_id for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.xlsx_file.completed" in audit_payload
    assert "parser.xlsx_file.failed" in audit_payload


def _pdf_bytes(pages: list[str]) -> bytes:
    streams: list[bytes] = []
    for text in pages:
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("utf-8")
        streams.append(b"BT /F1 12 Tf 72 720 Td (" + escaped + b") Tj ET")
    return _pdf_bytes_from_content_streams(streams)


def _pdf_bytes_from_content_streams(streams: list[bytes]) -> bytes:
    objects: list[bytes] = []

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    page_ids: list[int] = []
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for stream in streams:
        compressed = zlib.compress(stream)
        content_id = add_object(b"<< /Length " + str(len(compressed)).encode("ascii") + b" /Filter /FlateDecode >>\nstream\n" + compressed + b"\nendstream")
        page_id = add_object(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 "
            + str(font_id).encode("ascii")
            + b" 0 R >> >> /Contents "
            + str(content_id).encode("ascii")
            + b" 0 R >>"
        )
        page_ids.append(page_id)
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + b" ".join(str(item).encode("ascii") + b" 0 R" for item in page_ids) + b"] /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(str(index).encode("ascii") + b" 0 obj\n" + body + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n")
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(b"trailer\n<< /Size " + str(len(objects) + 1).encode("ascii") + b" /Root " + str(catalog_id).encode("ascii") + b" 0 R >>\nstartxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n")
    return b"".join(chunks)


def _scanned_pdf_bytes(page_count: int = 1) -> bytes:
    objects: list[bytes] = []

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    page_ids: list[int] = []
    for _ in range(page_count):
        content_id = add_object(b"<< /Length 0 >>\nstream\n\nendstream")
        page_id = add_object(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents " + str(content_id).encode("ascii") + b" 0 R >>")
        page_ids.append(page_id)
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + b" ".join(str(item).encode("ascii") + b" 0 R" for item in page_ids) + b"] /Count " + str(page_count).encode("ascii") + b" >>"
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(str(index).encode("ascii") + b" 0 obj\n" + body + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(b"trailer\n<< /Size " + str(len(objects) + 1).encode("ascii") + b" /Root " + str(catalog_id).encode("ascii") + b" 0 R >>\nstartxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n")
    return b"".join(chunks)


def _docx_xml_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _docx_paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{_docx_xml_text(text)}</w:t></w:r></w:p>"


def _docx_bytes(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    body = "".join(_docx_paragraph_xml(item) for item in paragraphs)
    if table:
        rows = []
        for row in table:
            cells = "".join(f"<w:tc>{_docx_paragraph_xml(cell)}</w:tc>" for cell in row)
            rows.append(f"<w:tr>{cells}</w:tr>")
        body += f"<w:tbl>{''.join(rows)}</w:tbl>"
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr /></w:body>"
        "</w:document>"
    ).encode("utf-8")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    ).encode("utf-8")
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _encrypted_docx_bytes() -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1encrypted-docx-placeholder"


def test_s2_pdf_text_parser_extracts_pages_and_marks_ocr_required() -> None:
    headers = _headers()
    prefix = _unique_name("S2 PDF parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["pdf"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 20,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    def upload_and_import(file_name: str, body: bytes) -> str:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"data_source_id": source_id, "title": file_name, "is_synthetic": "true"},
            files={"file": (file_name, body, "application/pdf")},
        )
        assert uploaded.status_code == 201, uploaded.text
        upload_payload = uploaded.json()["data"]["file_object"]["payload"]
        assert upload_payload["content_preview_base64"] is None
        assert upload_payload["content_preview_inlined"] is False
        assert upload_payload["content_preview_redacted"] is True
        imported = client.post(
            f"/api/v1/collection-jobs/{job_id}/file-runs",
            headers=headers,
            json={"file_object_id": uploaded.json()["data"]["file_object"]["file_object_id"], "title": file_name, "city_id": "xian"},
        )
        assert imported.status_code == 201, imported.text
        return imported.json()["data"]["raw_records"][0]["raw_record_id"]

    pdf_raw_id = upload_and_import(
        "xian-notice.pdf",
        _pdf_bytes(["PDF page one Xi'an pension insurance phone 13800138000", "PDF page two community visit stable"]),
    )
    parsed = client.post(
        "/api/v1/parser-runs/pdf-text",
        headers=headers,
        json={"raw_record_ids": [pdf_raw_id], "rule_version": "parse_pdf_text-test-v1", "response_limit": 5, "payload": {"title_prefix": "PDF extracted page"}},
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_pdf_text"
    assert data["parser"]["page_count"] == 2
    assert data["parser"]["parsed_count"] == 2
    assert data["parser"]["ocr_required_count"] == 0
    assert data["outputs"][0]["payload"]["parser_status"] == "parsed"
    assert data["outputs"][0]["payload"]["page_number"] == 1
    assert data["outputs"][0]["normalized_title"] == "PDF extracted page 1"
    assert "13800138000" not in data["outputs"][0]["normalized_text"]
    assert "[MASKED]" in data["outputs"][0]["normalized_text"]

    scanned_raw_id = upload_and_import("xian-scanned.pdf", _scanned_pdf_bytes(1))
    scanned = client.post(
        "/api/v1/parser-runs/pdf-text",
        headers=headers,
        json={"raw_record_ids": [scanned_raw_id], "rule_version": "parse_pdf_text-test-v1"},
    )
    assert scanned.status_code == 201, scanned.text
    assert scanned.json()["data"]["status"] == "completed"
    assert scanned.json()["data"]["parser"]["ocr_required_count"] == 1
    assert scanned.json()["data"]["outputs"][0]["payload"]["parser_status"] == "ocr_required"
    assert scanned.json()["data"]["outputs"][0]["payload"]["error_code"] == "PDF_OCR_REQUIRED"

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_pdf_text")).scalars())
        parser_run = next(item for item in algorithm_runs if item.object_id == data["normalization_run_id"] and item.status == "completed")
        assert len(parser_run.output_refs) == data["parser"]["page_count"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == data["outputs"][0]["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)
        assert any(item.from_object_type == "raw_record" and item.from_object_id == pdf_raw_id for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.pdf_text.completed" in audit_payload
    assert b64encode(b"%PDF-").decode("ascii") not in audit_payload


def test_s2_pdf_text_parser_handles_tj_arrays_and_escaped_literals() -> None:
    parsed = data_sources.parse_pdf_text(
        _pdf_bytes_from_content_streams([b"BT /F1 12 Tf 72 720 Td [(PDF escaped \\(notice\\) and ) 10 (array-safe phone 13800138000)] TJ ET"])
    )
    assert parsed["status"] == "parsed"
    assert parsed["page_count"] == 1
    assert parsed["pages"][0]["status"] == "parsed"
    assert "PDF escaped" in parsed["pages"][0]["text"]
    assert "(notice)" in parsed["pages"][0]["text"]
    assert "13800138000" in parsed["pages"][0]["text"]


def test_s2_docx_text_parser_extracts_paragraphs_tables_and_rejects_encrypted() -> None:
    headers = _headers()
    prefix = _unique_name("S2 DOCX parser")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["docx"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 20,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    def upload_and_import(file_name: str, body: bytes) -> str:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=headers,
            data={"data_source_id": source_id, "title": file_name, "is_synthetic": "true"},
            files={"file": (file_name, body, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert uploaded.status_code == 201, uploaded.text
        imported = client.post(
            f"/api/v1/collection-jobs/{job_id}/file-runs",
            headers=headers,
            json={"file_object_id": uploaded.json()["data"]["file_object"]["file_object_id"], "title": file_name, "city_id": "xian"},
        )
        assert imported.status_code == 201, imported.text
        return imported.json()["data"]["raw_records"][0]["raw_record_id"]

    docx_raw_id = upload_and_import(
        "xian-brief.docx",
        _docx_bytes(
            ["DOCX paragraph one Xi'an pension insurance phone 13800138000", "DOCX paragraph two community visit stable"],
            table=[["stakeholder", "position"], ["居民代表", "要求公开沟通时间表"]],
        ),
    )
    parsed = client.post(
        "/api/v1/parser-runs/docx-text",
        headers=headers,
        json={"raw_record_ids": [docx_raw_id], "rule_version": "parse_docx_text-test-v1", "response_limit": 10, "payload": {"title_prefix": "DOCX extracted block"}},
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_docx_text"
    assert data["parser"]["paragraph_count"] == 2
    assert data["parser"]["table_count"] == 1
    assert data["parser"]["table_cell_count"] == 4
    assert data["parser"]["block_count"] == 6
    assert data["outputs"][0]["payload"]["parser_status"] == "parsed"
    assert data["outputs"][0]["payload"]["block_type"] == "paragraph"
    assert data["outputs"][0]["normalized_title"] == "DOCX extracted block 1"
    assert "13800138000" not in data["outputs"][0]["normalized_text"]
    assert "[MASKED]" in data["outputs"][0]["normalized_text"]
    assert any(item["payload"]["block_type"] == "table_cell" and "居民代表" in item["normalized_text"] for item in data["outputs"])

    encrypted_raw_id = upload_and_import("xian-encrypted.docx", _encrypted_docx_bytes())
    encrypted = client.post(
        "/api/v1/parser-runs/docx-text",
        headers=headers,
        json={"raw_record_ids": [encrypted_raw_id], "rule_version": "parse_docx_text-test-v1"},
    )
    assert encrypted.status_code == 201, encrypted.text
    assert encrypted.json()["data"]["status"] == "failed"
    assert encrypted.json()["data"]["error_code"] == "DOCX_ENCRYPTED_UNSUPPORTED"
    assert encrypted.json()["data"]["outputs"] == []

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_docx_text")).scalars())
        parser_run = next(item for item in algorithm_runs if item.object_id == data["normalization_run_id"] and item.status == "completed")
        assert len(parser_run.output_refs) == data["parser"]["block_count"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == data["outputs"][0]["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)
        assert any(item.from_object_type == "raw_record" and item.from_object_id == docx_raw_id for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.docx_text.completed" in audit_payload
    assert "parser.docx_text.failed" in audit_payload


def test_s2_rss_source_creation_and_inspect_contract() -> None:
    headers = _headers()
    prefix = _unique_name("S2 RSS")

    invalid = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} invalid", "source_type": "rss", "policy": {"feed_url": "synthetic://xian/not-rss"}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "RSS_FEED_INVALID"

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} synthetic feed",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-social-issues"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()["data"]
    assert source["status"] == "active"
    assert source["is_synthetic"] is True
    assert source["policy"]["feed_url"] == "synthetic://xian/rss-social-issues"

    inspect = client.post(f"/api/v1/data-sources/{source['data_source_id']}/rss/inspect", headers=headers)
    assert inspect.status_code == 200, inspect.text
    metadata = inspect.json()["data"]
    assert metadata["title"] == "Xi'an Social Issues Synthetic RSS"
    assert metadata["item_count"] == 3
    assert metadata["latest_time"]
    assert metadata["is_synthetic"] is True

    refreshed = client.get("/api/v1/data-sources", headers=headers, params={"source_type": "rss", "page_size": 50})
    assert refreshed.status_code == 200
    stored = next(item for item in refreshed.json()["data"] if item["data_source_id"] == source["data_source_id"])
    assert stored["policy"]["rss_inspection"]["item_count"] == 3

    empty_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} empty feed",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-empty"},
        },
    )
    assert empty_source.status_code == 200, empty_source.text
    empty_inspect = client.post(f"/api/v1/data-sources/{empty_source.json()['data']['data_source_id']}/rss/inspect", headers=headers)
    assert empty_inspect.status_code == 422
    assert empty_inspect.json()["error"]["code"] == "RSS_FEED_EMPTY"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.rss.inspect" in audit_payload


def test_s2_rss_fetch_items_activity_writes_new_items_and_skips_duplicate_guid() -> None:
    headers = _headers()
    prefix = _unique_name("S2 RSS fetch")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-social-issues"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    fetched = client.post(
        "/api/v1/imports/rss",
        headers=headers,
        json={"data_source_id": source_id, "title": "RSS item fetch", "source_uri": "synthetic://xian/rss-social-issues"},
    )
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["import_run"]["status"] == "completed"
    assert data["collection_run"]["status"] == "completed"
    assert data["collection_run"]["record_count"] == 3
    assert len(data["raw_records"]) == 3
    activity = data["import_run"]["payload"]["rss_activity"]
    assert activity["activity_name"] == "fetch_rss_items"
    assert activity["item_count"] == 3
    assert activity["new_record_count"] == 3
    assert activity["duplicate_count"] == 0
    assert activity["is_synthetic"] is True
    assert data["raw_records"][0]["payload"]["rss_activity"]["activity_name"] == "fetch_rss_items"
    assert data["raw_records"][0]["payload"]["guid"]
    run_id = data["collection_run"]["collection_run_id"]
    workflow_run_id = data["collection_run"]["payload"]["workflow_run_id"]

    with Session(engine) as db:
        records = list(db.execute(select(models.RawRecord).where(models.RawRecord.data_source_id == source_id, models.RawRecord.source_type == "rss")).scalars())
        assert len(records) == 3
        assert all(record.dedupe_key for record in records)
        assert all(record.rss_guid_key for record in records)
        assert all(record.rss_link_key for record in records)
        assert any(index["name"] == "ux_raw_records_source_type_dedupe_key" and index["unique"] for index in inspect(engine).get_indexes("raw_records"))
        assert any(index["name"] == "ux_raw_records_rss_guid_key" and index["unique"] for index in inspect(engine).get_indexes("raw_records"))
        assert any(index["name"] == "ux_raw_records_rss_link_key" and index["unique"] for index in inspect(engine).get_indexes("raw_records"))
        payloads = [
            item
            for item in db.execute(
                select(models.RawRecordPayload)
                .join(models.RawRecord, models.RawRecordPayload.raw_record_id == models.RawRecord.id)
                .where(models.RawRecord.collection_run_id == run_id)
            ).scalars()
        ]
        assert len(payloads) == 3
        assert all(item.payload["activity_name"] == "fetch_rss_items" for item in payloads)
        assert "synthetic RSS item" in payloads[0].content_text
        events = [
            event.event_type
            for event in db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars()
        ]
        assert "fetch_rss_items_started" in events
        assert "fetch_rss_items_completed" in events
        workflow_events = [
            event.event_type
            for event in db.execute(select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow_run_id)).scalars()
        ]
        assert "activity_started" in workflow_events
        assert "activity_completed" in workflow_events

    steps = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    step_by_key = {item["step_key"]: item for item in steps.json()["data"]["steps"]}
    assert step_by_key["fetch"]["status"] == "completed"
    assert step_by_key["store"]["status"] == "completed"

    duplicate = client.post(
        "/api/v1/imports/rss",
        headers=headers,
        json={"data_source_id": source_id, "title": "RSS duplicate fetch", "source_uri": "synthetic://xian/rss-social-issues"},
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_data = duplicate.json()["data"]
    assert duplicate_data["import_run"]["status"] == "completed"
    assert duplicate_data["collection_run"]["record_count"] == 0
    assert duplicate_data["raw_records"] == []
    assert duplicate_data["import_run"]["payload"]["rss_activity"]["duplicate_count"] == 3

    same_link_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} same link source",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-same-link?items=3"},
        },
    )
    assert same_link_source.status_code == 200, same_link_source.text
    same_link = client.post(
        "/api/v1/imports/rss",
        headers=headers,
        json={"data_source_id": same_link_source.json()["data"]["data_source_id"], "title": "RSS same-link fetch"},
    )
    assert same_link.status_code == 200, same_link.text
    same_link_data = same_link.json()["data"]
    assert same_link_data["collection_run"]["record_count"] == 1
    assert len(same_link_data["raw_records"]) == 1
    assert same_link_data["import_run"]["payload"]["rss_activity"]["item_count"] == 3
    assert same_link_data["import_run"]["payload"]["rss_activity"]["duplicate_count"] == 2

    with Session(engine) as db:
        total_records = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id, models.RawRecord.source_type == "rss")).scalar_one()
        assert total_records == 3

    empty_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} empty source",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-empty"},
        },
    )
    assert empty_source.status_code == 200, empty_source.text
    failed = client.post(
        "/api/v1/imports/rss",
        headers=headers,
        json={"data_source_id": empty_source.json()["data"]["data_source_id"], "title": "RSS empty fetch"},
    )
    assert failed.status_code == 200, failed.text
    failed_data = failed.json()["data"]
    assert failed_data["import_run"]["status"] == "failed"
    assert failed_data["import_run"]["error_code"] == "RSS_FEED_EMPTY"
    assert failed_data["collection_run"]["status"] == "failed"
    assert failed_data["raw_records"] == []

    failure_cases = [
        ("invalid", "synthetic://xian/not-rss", "RSS_FEED_INVALID", False),
        ("unreachable", "synthetic://xian/rss-unreachable", "RSS_FEED_UNREACHABLE", True),
        ("timeout", "synthetic://xian/rss-timeout", "RSS_FEED_TIMEOUT", True),
        ("rate limited", "synthetic://xian/rss-429", "RSS_FEED_RATE_LIMITED", True),
        ("upstream", "synthetic://xian/rss-500", "RSS_FEED_UPSTREAM_ERROR", True),
    ]
    for title, uri, code, retryable in failure_cases:
        failure = client.post(
            "/api/v1/imports/rss",
            headers=headers,
            json={"data_source_id": source_id, "title": f"RSS {title} fetch", "source_uri": uri},
        )
        assert failure.status_code == 200, failure.text
        failure_data = failure.json()["data"]
        assert failure_data["import_run"]["status"] == "failed"
        assert failure_data["import_run"]["error_code"] == code
        assert failure_data["collection_run"]["status"] == "failed"
        assert failure_data["raw_records"] == []
        assert failure_data["import_run"]["payload"]["rss_activity"]["activity_name"] == "fetch_rss_items"
        assert failure_data["import_run"]["payload"]["rss_activity"]["retryable"] is retryable

    retry_queue = client.get("/api/v1/ops/retry-queue", headers=headers)
    assert retry_queue.status_code == 200, retry_queue.text
    retry_error_codes = {item["payload"].get("error_code") for item in retry_queue.json()["data"] if item["target_type"] == "import_run"}
    assert {"RSS_FEED_UNREACHABLE", "RSS_FEED_TIMEOUT", "RSS_FEED_RATE_LIMITED", "RSS_FEED_UPSTREAM_ERROR"}.issubset(retry_error_codes)


def test_s2_rss_item_parser_extracts_fields_uses_link_hash_and_skips_duplicates() -> None:
    headers = _headers()
    prefix = _unique_name("S2 RSS parser")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "rss",
            "policy": {"access_mode": "public_web", "feed_url": "synthetic://xian/rss-social-issues"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    fetched = client.post(
        "/api/v1/imports/rss",
        headers=headers,
        json={"data_source_id": source_id, "title": "RSS parser fetch", "source_uri": "synthetic://xian/rss-social-issues"},
    )
    assert fetched.status_code == 200, fetched.text
    fetched_data = fetched.json()["data"]
    raw_ids = [item["raw_record_id"] for item in fetched_data["raw_records"]]
    assert len(raw_ids) == 3

    parsed = client.post(
        "/api/v1/parser-runs/rss-item",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "parse_rss_item-test-v1", "response_limit": 3, "payload": {"at": "AT-091"}},
    )
    assert parsed.status_code == 201, parsed.text
    data = parsed.json()["data"]
    assert data["status"] == "completed"
    assert data["parser"]["activity_name"] == "parse_rss_item"
    assert data["parser"]["item_count"] == 3
    assert data["parser"]["parsed_count"] == 3
    assert data["parser"]["failed_count"] == 0
    assert data["parser"]["duplicate_count"] == 0
    assert data["parser"]["response_count"] == 3
    first = data["outputs"][0]
    assert first["payload"]["parser_status"] == "parsed"
    assert first["payload"]["guid"].startswith("xian-rss-")
    assert first["payload"]["identity_source"] == "guid"
    assert first["payload"]["rss_item_key"].startswith("guid:")
    assert first["payload"]["link"].startswith("https://synthetic.local/xian/rss/")
    assert first["payload"]["published_at"].startswith("2026-05-09T08:")
    assert first["payload"]["summary"]

    missing_guid_payload = {
        "title": "RSS missing guid",
        "link": f"https://synthetic.local/xian/rss/no-guid-{uuid4().hex[:8]}",
        "summary": "Missing guid item includes phone 13800138000 and must be masked.",
        "published_at": "Sat, 09 May 2026 09:15:00 GMT",
        "synthetic": True,
    }
    missing_guid = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": fetched_data["collection_run"]["collection_run_id"],
            "records": [
                {
                    "title": "RSS missing guid raw",
                    "content": json.dumps(missing_guid_payload, ensure_ascii=False),
                    "external_id": f"rss-missing-guid-{uuid4().hex[:8]}",
                    "is_synthetic": True,
                    "source_type": "rss",
                }
            ],
            "reason": "AT-091 missing guid parser input",
        },
    )
    assert missing_guid.status_code == 201, missing_guid.text
    missing_guid_raw_id = missing_guid.json()["data"]["raw_records"][0]["raw_record_id"]

    parsed_missing_guid = client.post(
        "/api/v1/parser-runs/rss-item",
        headers=headers,
        json={"raw_record_ids": [missing_guid_raw_id], "rule_version": "parse_rss_item-test-v1", "payload": {"at": "AT-091"}},
    )
    assert parsed_missing_guid.status_code == 201, parsed_missing_guid.text
    missing_output = parsed_missing_guid.json()["data"]["outputs"][0]
    expected_link_hash = "sha256:" + hashlib.sha256(missing_guid_payload["link"].encode("utf-8")).hexdigest()
    assert missing_output["payload"]["guid"] is None
    assert missing_output["payload"]["identity_source"] == "link_hash"
    assert missing_output["payload"]["link_hash"] == expected_link_hash
    assert missing_output["payload"]["rss_item_key"] == f"link:{expected_link_hash}"
    assert missing_output["payload"]["published_at"] == "2026-05-09T09:15:00Z"
    assert "13800138000" not in missing_output["normalized_text"]
    assert "[MASKED]" in missing_output["normalized_text"]

    duplicate_parse = client.post(
        "/api/v1/parser-runs/rss-item",
        headers=headers,
        json={"raw_record_ids": [missing_guid_raw_id], "rule_version": "parse_rss_item-test-v1"},
    )
    assert duplicate_parse.status_code == 201, duplicate_parse.text
    duplicate_data = duplicate_parse.json()["data"]
    assert duplicate_data["status"] == "completed"
    assert duplicate_data["output_count"] == 0
    assert duplicate_data["outputs"] == []
    assert duplicate_data["parser"]["duplicate_count"] == 1

    invalid = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": fetched_data["collection_run"]["collection_run_id"],
            "records": [
                {
                    "title": "RSS invalid raw",
                    "content": json.dumps({"title": "RSS missing link", "summary": "no link", "published_at": "2026-05-09T10:00:00Z"}, ensure_ascii=False),
                    "external_id": f"rss-invalid-{uuid4().hex[:8]}",
                    "is_synthetic": True,
                    "source_type": "rss",
                }
            ],
            "reason": "AT-091 invalid RSS parser input",
        },
    )
    assert invalid.status_code == 201, invalid.text
    invalid_raw_id = invalid.json()["data"]["raw_records"][0]["raw_record_id"]
    invalid_parsed = client.post(
        "/api/v1/parser-runs/rss-item",
        headers=headers,
        json={"raw_record_ids": [invalid_raw_id], "rule_version": "parse_rss_item-test-v1"},
    )
    assert invalid_parsed.status_code == 201, invalid_parsed.text
    invalid_output = invalid_parsed.json()["data"]["outputs"][0]
    assert invalid_output["payload"]["parser_status"] == "parse_error"
    assert invalid_output["payload"]["error_code"] == "RSS_ITEM_REQUIRED_FIELD_MISSING"
    assert invalid_output["payload"]["missing_fields"] == ["link"]

    with Session(engine) as db:
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "parse_rss_item")).scalars())
        assert any(item.object_id == data["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == first["normalization_output_id"])).scalars())
        assert any(item.from_object_type == "algorithm_run" for item in lineages)
        assert any(item.from_object_type == "raw_record" and item.from_object_id in raw_ids for item in lineages)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "parser.rss_item.completed" in audit_payload


def test_s2_file_upload_source_policy_contract() -> None:
    headers = _headers()
    prefix = _unique_name("S2 file upload")

    invalid = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} invalid",
            "source_type": "file_upload",
            "policy": {"allowed_file_types": ["csv", "exe"], "schema": {"columns": ["title", "content"]}},
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "FILE_UPLOAD_TYPE_NOT_ALLOWED"

    missing_schema = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} missing schema", "source_type": "file_upload", "policy": {"allowed_file_types": ["csv"]}},
    )
    assert missing_schema.status_code == 422
    assert missing_schema.json()["error"]["code"] == "FILE_UPLOAD_SCHEMA_REQUIRED"

    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["csv", "json", "pdf"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 50,
            },
        },
    )
    assert created.status_code == 200, created.text
    source = created.json()["data"]
    assert source["status"] == "active"
    assert source["policy"]["allowed_file_types"] == ["csv", "json", "pdf"]
    assert source["policy"]["schema"]["required_fields"] == ["title", "content"]
    assert source["policy"]["max_file_size_mb"] == 50
    assert source["policy"]["policy_result"]["allowed"] is True

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.create" in audit_payload
    assert "FILE_UPLOAD_TYPE_NOT_ALLOWED" not in audit_payload


def test_s2_file_upload_receive_persists_file_object_and_classifies_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 upload receive")

    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["csv", "json", "pdf", "docx", "xlsx"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 1,
            },
        },
    )
    assert created.status_code == 200, created.text
    source = created.json()["data"]
    source_id = source["data_source_id"]

    body = b"{\"title\":\"Xi'an upload\",\"content\":\"synthetic but backend persisted\"}"
    uploaded = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"data_source_id": source_id, "title": "Xi'an source upload", "is_synthetic": "true"},
        files={"file": ("xian-upload.json", body, "application/json")},
    )
    assert uploaded.status_code == 201, uploaded.text
    data = uploaded.json()["data"]
    assert data["upload"]["status"] == "stored"
    assert data["upload"]["recoverable"] is True
    assert data["upload"]["scan"]["status"] == "passed"
    assert data["file_object"]["file_name"] == "xian-upload.json"
    assert data["file_object"]["mime_type"] == "application/json"
    assert data["file_object"]["byte_size"] == len(body)
    assert data["file_object"]["payload"]["storage_mode"] == "local_object_store"
    assert Path(data["file_object"]["payload"]["object_store_uri"]).exists()
    assert data["file_object"]["payload"]["source_flags"]["synthetic"] is True

    with Session(engine) as db:
        file_object = db.get(models.FileObject, data["file_object"]["file_object_id"])
        assert file_object is not None
        assert file_object.status == "stored"
        assert file_object.object_type == "data_source"
        assert file_object.object_id == source_id
        assert file_object.owner_user_id is not None
        assert file_object.checksum.startswith("sha256:")
        assert file_object.payload["scan_status"] == "passed"
        assert Path(file_object.payload["object_store_uri"]).read_bytes() == body
        assert file_object.payload["upload"]["title"] == "Xi'an source upload"
        edges = list(
            db.execute(
                select(models.LineageEdge).where(
                    models.LineageEdge.to_object_type == "file_object",
                    models.LineageEdge.to_object_id == file_object.id,
                )
            ).scalars()
        )
        assert any(edge.from_object_type == "data_source" and edge.from_object_id == source_id for edge in edges)

    disallowed = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"data_source_id": source_id, "title": "disallowed"},
        files={"file": ("payload.exe", b"not allowed", "application/octet-stream")},
    )
    assert disallowed.status_code == 415
    assert disallowed.json()["error"]["code"] == "FILE_UPLOAD_TYPE_NOT_ALLOWED"

    oversize = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"data_source_id": source_id, "title": "oversize"},
        files={"file": ("large.json", b"x" * (1024 * 1024 + 1), "application/json")},
    )
    assert oversize.status_code == 413
    assert oversize.json()["error"]["code"] == "FILE_UPLOAD_TOO_LARGE"
    assert oversize.json()["error"]["details"]["recoverable"] is True

    virus = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"data_source_id": source_id, "title": "virus marker"},
        files={"file": ("eicar.csv", b"X5O!P%@AP EICAR-STANDARD-ANTIVIRUS-TEST-FILE", "text/csv")},
    )
    assert virus.status_code == 422
    assert virus.json()["error"]["code"] == "FILE_UPLOAD_VIRUS_DETECTED"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "file_upload.received" in audit_payload
    assert "file_upload.rejected" in audit_payload
    assert "FILE_UPLOAD_VIRUS_DETECTED" in audit_payload


def test_s2_file_upload_binding_creates_file_import_run_and_raw_record() -> None:
    headers = _headers()
    prefix = _unique_name("S2 file run")
    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": ["json"],
                "schema": {"required_fields": ["title", "content"], "city_id": "xian"},
                "max_file_size_mb": 1,
            },
        },
    )
    assert created.status_code == 200, created.text
    source_id = created.json()["data"]["data_source_id"]
    body = b'{"title":"Bound upload","content":"file run binding through object store","synthetic":true}'
    uploaded = client.post(
        "/api/v1/uploads",
        headers=headers,
        data={"data_source_id": source_id, "title": "Bound upload", "is_synthetic": "true"},
        files={"file": ("bound-upload.json", body, "application/json")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_object_id = uploaded.json()["data"]["file_object"]["file_object_id"]
    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"job_kind": "file_upload"}},
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    imported = client.post(
        f"/api/v1/collection-jobs/{job_id}/file-runs",
        headers=headers,
        json={"file_object_id": file_object_id, "title": "Import uploaded file", "city_id": "xian"},
    )
    assert imported.status_code == 201, imported.text
    data = imported.json()["data"]
    assert data["file_object"]["file_object_id"] == file_object_id
    assert data["collection_run"]["status"] == "completed"
    assert data["import_run"]["status"] == "completed"
    assert data["import_run"]["import_type"] == "file_upload"
    assert data["raw_records"][0]["payload"]["file_object_ref"]["file_object_id"] == file_object_id
    assert data["raw_records"][0]["payload"]["source_flags"]["synthetic"] is True
    run_id = data["collection_run"]["collection_run_id"]
    raw_record_id = data["raw_records"][0]["raw_record_id"]

    with Session(engine) as db:
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert "file run binding through object store" in payload.content_text
        edges = list(
            db.execute(
                select(models.LineageEdge).where(
                    models.LineageEdge.to_object_type == "raw_record",
                    models.LineageEdge.to_object_id == raw_record_id,
                )
            ).scalars()
        )
        assert any(edge.from_object_type == "file_object" and edge.from_object_id == file_object_id for edge in edges)
        assert any(edge.from_object_type == "collection_run" and edge.from_object_id == run_id for edge in edges)

        other_tenant = models.Tenant(id=f"tenant-other-{uuid4().hex[:8]}", name="Other tenant", status="active", payload={})
        db.add(other_tenant)
        db.flush()
        foreign_file = models.FileObject(
            id=f"FILE-{uuid4().hex[:20]}",
            tenant_id=other_tenant.id,
            object_type="data_source",
            object_id=source_id,
            storage_key="uploads/other/foreign.json",
            file_name="foreign.json",
            mime_type="application/json",
            byte_size=2,
            checksum="sha256:foreign",
            status="stored",
            access_policy={"scope": "tenant"},
            source_refs=[{"object_type": "data_source", "object_id": source_id}],
            payload={"storage_mode": "local_object_store", "object_store_uri": "missing://foreign"},
        )
        db.add(foreign_file)
        db.commit()
        foreign_file_id = foreign_file.id

    forbidden = client.post(
        f"/api/v1/collection-jobs/{job_id}/file-runs",
        headers=headers,
        json={"file_object_id": foreign_file_id, "title": "foreign"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FILE_OBJECT_TENANT_MISMATCH"

    steps = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    step_by_key = {item["step_key"]: item for item in steps.json()["data"]["steps"]}
    assert step_by_key["fetch"]["status"] == "completed"
    assert step_by_key["store"]["status"] == "completed"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "file_upload.file_run.completed" in audit_payload
    assert file_object_id in audit_payload


def test_s2_webhook_source_signature_replay_and_payload_chain() -> None:
    headers = _headers()
    prefix = _unique_name("S2 webhook")

    plaintext = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} plaintext", "source_type": "webhook", "policy": {"secret": "plain-secret"}},
    )
    assert plaintext.status_code == 422
    assert plaintext.json()["error"]["code"] == "WEBHOOK_SECRET_PLAINTEXT_NOT_ALLOWED"

    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "webhook",
            "policy": {"source_key": f"wh-{uuid4().hex[:10]}", "schema": {"required_fields": ["request_id", "title", "content", "city_id"]}},
        },
    )
    assert created.status_code == 200, created.text
    source = created.json()["data"]
    webhook = source["policy"]["webhook"]
    secret = source["webhook_secret_once"]
    assert source["status"] == "active"
    assert webhook["endpoint_path"] == f"/api/v1/webhooks/{webhook['source_key']}"
    assert webhook["secret_ref"].startswith("generated://webhooks/")
    assert "secret_hash" in webhook
    assert secret not in json.dumps(source["policy"], ensure_ascii=False)

    body = json.dumps(
        {
            "request_id": "delivery-001",
            "title": "Webhook Xi'an source payload",
            "content": "synthetic webhook content for Xi'an public service issue.",
            "city_id": "xian",
            "is_synthetic": True,
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    received = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": timestamp,
            "x-cet-delivery-id": "delivery-001",
            "x-cet-signature": signature,
        },
    )
    assert received.status_code == 200, received.text
    received_data = received.json()["data"]
    assert received_data["status"] == "received"
    assert received_data["raw_record"]["is_synthetic"] is True
    assert received_data["collection_run"]["record_count"] == 1

    replay = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": timestamp,
            "x-cet-delivery-id": "delivery-001",
            "x-cet-signature": signature,
        },
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "WEBHOOK_REPLAY_DETECTED"

    duplicate_request_body = json.dumps(
        {
            "request_id": "delivery-001",
            "title": "Webhook duplicate request id",
            "content": "same request id must not write another raw record.",
            "city_id": "xian",
            "is_synthetic": True,
        },
        separators=(",", ":"),
    ).encode()
    duplicate_timestamp = str(int(time.time()))
    duplicate_signature = "sha256=" + hmac.new(secret.encode(), duplicate_timestamp.encode() + b"." + duplicate_request_body, hashlib.sha256).hexdigest()
    duplicate_request = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=duplicate_request_body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": duplicate_timestamp,
            "x-cet-delivery-id": "delivery-002",
            "x-cet-signature": duplicate_signature,
        },
    )
    assert duplicate_request.status_code == 409
    assert duplicate_request.json()["error"]["code"] == "WEBHOOK_REQUEST_ID_DUPLICATE"

    missing_required_body = json.dumps(
        {
            "request_id": "delivery-004",
            "title": "Webhook schema miss",
            "city_id": "xian",
            "is_synthetic": True,
        },
        separators=(",", ":"),
    ).encode()
    schema_timestamp = str(int(time.time()))
    schema_signature = "sha256=" + hmac.new(secret.encode(), schema_timestamp.encode() + b"." + missing_required_body, hashlib.sha256).hexdigest()
    schema_error = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=missing_required_body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": schema_timestamp,
            "x-cet-delivery-id": "delivery-004",
            "x-cet-signature": schema_signature,
        },
    )
    assert schema_error.status_code == 422
    assert schema_error.json()["error"]["code"] == "WEBHOOK_SCHEMA_INVALID"
    assert schema_error.json()["error"]["details"]["missing_fields"] == ["content"]

    bad = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": str(int(time.time())),
            "x-cet-delivery-id": "delivery-002",
            "x-cet-signature": "sha256=bad",
        },
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"

    old_timestamp = str(int(time.time()) - 1000)
    old_signature = "sha256=" + hmac.new(secret.encode(), old_timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    expired = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=body,
        headers={
            "content-type": "application/json",
            "x-cet-timestamp": old_timestamp,
            "x-cet-delivery-id": "delivery-003",
            "x-cet-signature": old_signature,
        },
    )
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "WEBHOOK_TIMESTAMP_EXPIRED"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert secret not in audit_payload
    assert "webhook.payload.received" in audit_payload

    lineage = client.get("/api/v1/lineage", params={"object_type": "raw_record", "object_id": received_data["raw_record"]["raw_record_id"]}, headers=headers)
    assert lineage.status_code == 200
    assert any(edge["from_object_type"] == "data_source" for edge in lineage.json()["data"])

    with Session(engine) as db:
        record = db.get(models.RawRecord, received_data["raw_record"]["raw_record_id"])
        assert record is not None
        assert record.dedupe_key == "webhook-request:delivery-001"
        assert record.webhook_delivery_key == "webhook-delivery:delivery-001"


def test_s2_webhook_source_key_global_uniqueness_and_delivery_idempotency() -> None:
    headers = _headers()
    source_key = f"wh-global-{uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"webhook global {source_key}", "source_type": "webhook", "policy": {"source_key": source_key}},
    )
    assert created.status_code == 200, created.text

    with Session(engine) as db:
        other_tenant = models.Tenant(id=f"tenant-webhook-{uuid4().hex[:8]}", name="Webhook other tenant", status="active", payload={})
        db.add(other_tenant)
        username = f"webhook.admin.{uuid4().hex[:8]}"
        user = models.User(id=f"USER-{uuid4().hex[:12]}", tenant_id=other_tenant.id, username=username, display_name="Webhook other admin", password_hash=foundation.hash_password("StrongPass123!"), status="active")
        db.add(user)
        db.commit()
        duplicate_request = type("RequestShape", (), {"name": f"webhook duplicate {source_key}", "source_type": "webhook", "policy": {"source_key": source_key}, "payload": {}})()
        try:
            data_sources.create_data_source(db, duplicate_request, user, f"trc-{uuid4().hex[:12]}")
            raise AssertionError("Duplicate webhook source_key should be rejected globally.")
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 409
            assert exc.detail["code"] == "WEBHOOK_SOURCE_KEY_DUPLICATE"

    webhook = created.json()["data"]["policy"]["webhook"]
    secret = created.json()["data"]["webhook_secret_once"]
    first_payload = json.dumps({"request_id": "req-a", "title": "first", "content": "first delivery", "city_id": "xian"}, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + first_payload, hashlib.sha256).hexdigest()
    first = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=first_payload,
        headers={"content-type": "application/json", "x-cet-timestamp": timestamp, "x-cet-delivery-id": "same-delivery", "x-cet-signature": signature},
    )
    assert first.status_code == 200, first.text
    second_payload = json.dumps({"request_id": "req-b", "title": "second", "content": "same delivery id", "city_id": "xian"}, separators=(",", ":")).encode()
    second_timestamp = str(int(time.time()))
    second_signature = "sha256=" + hmac.new(secret.encode(), second_timestamp.encode() + b"." + second_payload, hashlib.sha256).hexdigest()
    second = client.post(
        f"/api/v1/webhooks/{webhook['source_key']}",
        content=second_payload,
        headers={"content-type": "application/json", "x-cet-timestamp": second_timestamp, "x-cet-delivery-id": "same-delivery", "x-cet-signature": second_signature},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WEBHOOK_REPLAY_DETECTED"


def test_s2_manual_source_creation_requires_authorized_role_and_audit() -> None:
    headers = _headers()
    prefix = _unique_name("S2 manual")

    role_response = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": f"{prefix} audit only", "description": "Cannot create data sources.", "permission_codes": ["audit:read"]},
    )
    assert role_response.status_code == 200, role_response.text
    username = f"manual.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "display_name": "Manual Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"}

    forbidden = client.post(
        "/api/v1/data-sources",
        headers=viewer_headers,
        json={"name": f"{prefix} forbidden", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"]}}},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    created = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} valid", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert created.status_code == 200, created.text
    source = created.json()["data"]
    assert source["status"] == "active"
    assert source["policy"]["entry_schema"]["required_fields"] == ["title", "content"]
    assert source["policy"]["policy_result"]["access_mode"] == "manual_upload"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.create" in audit_payload
    assert source["data_source_id"] in audit_payload


def test_s2_manual_record_create_persists_raw_payload_lineage_and_audit() -> None:
    headers = _headers()
    prefix = _unique_name("S2 manual record")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    missing = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={"data_source_id": source_id, "title": "Manual missing content", "city_id": "xian"},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "MANUAL_RECORD_SCHEMA_INVALID"
    assert missing.json()["error"]["details"]["missing_fields"] == ["content"]

    bad_policy_source_id = f"DS-{uuid4().hex[:20]}"
    with Session(engine) as db:
        db.add(
            models.DataSource(
                id=bad_policy_source_id,
                tenant_id=foundation.DEFAULT_TENANT_ID,
                name=f"{prefix} legacy bad manual source",
                source_type="manual",
                status="active",
                is_synthetic=True,
                policy={"entry_schema": {"city_id": "xian"}},
                payload={},
            )
        )
        db.add(models.SourceHealth(id=f"SH-{uuid4().hex[:20]}", data_source_id=bad_policy_source_id, status="healthy", payload={"synthetic": True}))
        db.commit()
    bad_policy = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={"data_source_id": bad_policy_source_id, "title": "Bad policy", "content": "Bad policy content", "city_id": "xian"},
    )
    assert bad_policy.status_code == 422
    assert bad_policy.json()["error"]["code"] == "MANUAL_RECORD_SCHEMA_INVALID"
    assert bad_policy.json()["error"]["details"]["policy_error"] == "required_fields_required"

    created = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "Manual pension queue report",
            "content": "Resident manually entered a Xi'an pension insurance queue update. Contact Li 13800138000 should be masked.",
            "city_id": "xian",
            "source_uri": "synthetic://xian/manual-record-test",
            "is_synthetic": True,
            "payload": {"district": "beilin", "channel": "manual_entry"},
            "reason": "AT-074 manual entry acceptance",
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["status"] == "created"
    assert data["raw_record"]["source_type"] == "manual"
    assert data["raw_record"]["status"] == "collected"
    assert data["raw_record"]["is_synthetic"] is True
    assert data["collection_run"]["status"] == "completed"
    assert data["collection_run"]["record_count"] == 1
    raw_record_id = data["raw_record"]["raw_record_id"]
    run_id = data["collection_run"]["collection_run_id"]

    with Session(engine) as db:
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert "pension insurance queue update" in payload.content_text
        assert "13800138000" not in payload.masked_text
        assert "[MASKED]" in payload.masked_text
        edges = list(
            db.execute(
                select(models.LineageEdge).where(
                    models.LineageEdge.to_object_type == "raw_record",
                    models.LineageEdge.to_object_id == raw_record_id,
                )
            ).scalars()
        )
        assert any(edge.from_object_type == "data_source" and edge.from_object_id == source_id for edge in edges)
        assert any(edge.from_object_type == "collection_run" and edge.from_object_id == run_id for edge in edges)
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars())
        assert any(event.event_type == "manual_record_created" and event.status == "completed" for event in events)

    role_response = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": f"{prefix} audit only", "description": "Cannot create manual records.", "permission_codes": ["audit:read"]},
    )
    assert role_response.status_code == 200, role_response.text
    username = f"manual.record.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "display_name": "Manual Record Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.post(
        "/api/v1/manual-records",
        headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"},
        json={"data_source_id": source_id, "title": "Forbidden", "content": "Forbidden", "city_id": "xian"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "manual_record.create" in audit_payload
    assert raw_record_id in audit_payload


def test_s2_manual_record_schema_validator_requires_time_location_and_creates_clean_draft() -> None:
    headers = _headers()
    prefix = _unique_name("S2 manual validator")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "manual",
            "policy": {"entry_schema": {"required_fields": ["title", "content", "time", "location"], "city_id": "xian"}},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    invalid = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={"data_source_id": source_id, "content": "Manual validator missing title time and location.", "city_id": None},
    )
    assert invalid.status_code == 422
    error = invalid.json()["error"]
    assert error["code"] == "MANUAL_RECORD_SCHEMA_INVALID"
    assert error["details"]["validator"] == "validate_manual_record"
    assert error["details"]["missing_fields"] == ["title", "time", "location"]
    assert "title" in error["message"] and "time" in error["message"] and "location" in error["message"]
    with Session(engine) as db:
        assert db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one() == 0

    omitted_location = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "Manual validator omitted location",
            "content": "Manual validator has title, content, and time but no location.",
            "occurred_at": "2026-05-09T09:30:00Z",
        },
    )
    assert omitted_location.status_code == 422
    assert omitted_location.json()["error"]["details"]["missing_fields"] == ["location"]
    with Session(engine) as db:
        assert db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one() == 0

    valid = client.post(
        "/api/v1/manual-records",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "Manual schema validated queue report",
            "content": "Manual schema validator accepts this Xi'an queue note with contact 13800138000 masked in clean draft.",
            "city_id": "xian",
            "occurred_at": "2026-05-09T09:30:00Z",
            "source_uri": "synthetic://xian/manual-validator",
            "is_synthetic": True,
            "payload": {"location": "碑林区政务服务大厅", "district": "beilin"},
            "reason": "AT-092 manual schema validation",
        },
    )
    assert valid.status_code == 201, valid.text
    data = valid.json()["data"]
    assert data["validation"]["status"] == "valid"
    assert data["validation"]["validator"] == "validate_manual_record"
    assert data["validation"]["required_fields"] == ["title", "content", "time", "location"]
    assert data["validation"]["location"] == "碑林区政务服务大厅"
    assert data["raw_record"]["status"] == "collected"
    assert data["clean_draft"]["payload"]["activity_name"] == "validate_manual_record"
    assert data["clean_draft"]["payload"]["clean_record_status"] == "draft"
    assert "13800138000" not in data["clean_draft"]["normalized_text"]
    assert "[MASKED]" in data["clean_draft"]["normalized_text"]
    raw_record_id = data["raw_record"]["raw_record_id"]
    clean_draft_id = data["clean_draft"]["normalization_output_id"]

    with Session(engine) as db:
        raw_record = db.get(models.RawRecord, raw_record_id)
        assert raw_record is not None
        assert raw_record.payload["manual_validation"]["status"] == "valid"
        assert raw_record.payload["manual_validation"]["location"] == "碑林区政务服务大厅"
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert payload.payload["manual_validation"]["validator"] == "validate_manual_record"
        clean_draft = db.get(models.RawRecordNormalization, clean_draft_id)
        assert clean_draft is not None
        assert clean_draft.payload["clean_record_status"] == "draft"
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == clean_draft_id)).scalars())
        assert any(edge.from_object_type == "raw_record" and edge.relation == "manual_record_validated_into_clean_draft" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        algorithm_runs = list(db.execute(select(models.AlgorithmRun).where(models.AlgorithmRun.algorithm_name == "validate_manual_record")).scalars())
        assert any(item.object_id == data["validator_run"]["normalization_run_id"] and item.status == "completed" for item in algorithm_runs)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "manual_record.validation_failed" in audit_payload
    assert "manual_record.create" in audit_payload
    assert clean_draft_id in audit_payload


def test_s2_normalize_text_cleaner_strips_html_controls_marks_empty_and_writes_algorithm_lineage() -> None:
    headers = _headers()
    prefix = _unique_name("S2 normalize text")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual_upload"},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} repository job", "payload": {"normalize_text_probe": True}},
    )
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    collection_run_id = run_response.json()["data"]["collection_run_id"]
    batch_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": collection_run_id,
            "complete_run": True,
            "response_limit": 2,
            "records": [
                {
                    "title": "Normalize HTML control source",
                    "content": "<article> Xi'an&nbsp;Pension\tQueue <br> update \u0007 13800138000 </article>",
                    "raw_uri": "synthetic://xian/normalize-text/valid",
                    "is_synthetic": True,
                },
                {
                    "title": "Blank after cleaning",
                    "content": "<div>\u0007 \n\t</div>",
                    "raw_uri": "synthetic://xian/normalize-text/blank",
                    "is_synthetic": True,
                },
            ],
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    raw_ids = [item["raw_record_id"] for item in batch_response.json()["data"]["raw_records"]]

    normalization = client.post(
        "/api/v1/normalization-runs",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "normalize_text-test-v1", "response_limit": 10},
    )
    assert normalization.status_code == 200, normalization.text
    data = normalization.json()["data"]
    assert data["status"] == "completed"
    assert data["output_count"] == 2
    assert data["cleaner"]["activity_name"] == "normalize_text"
    assert data["cleaner"]["valid_count"] == 1
    assert data["cleaner"]["invalid_count"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "normalize_text"
    assert data["algorithm_run"]["status"] == "completed"
    assert len(data["algorithm_run"]["output_refs"]) == 2
    outputs_by_raw = {item["raw_record_id"]: item for item in data["outputs"]}
    valid_output = outputs_by_raw[raw_ids[0]]
    invalid_output = outputs_by_raw[raw_ids[1]]
    assert "<" not in valid_output["normalized_text"]
    assert "xi'an pension queue update" in valid_output["normalized_text"]
    assert "13800138000" not in valid_output["normalized_text"]
    assert "[masked]" in valid_output["normalized_text"]
    assert valid_output["payload"]["cleaner_status"] == "valid"
    assert valid_output["payload"]["html_tag_count"] >= 2
    assert valid_output["payload"]["control_char_count"] >= 1
    assert invalid_output["normalized_text"] == ""
    assert invalid_output["payload"]["cleaner_status"] == "invalid"
    assert invalid_output["payload"]["error_code"] == "NORMALIZE_TEXT_EMPTY"

    with Session(engine) as db:
        clean_id = valid_output["normalization_output_id"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == clean_id)).scalars())
        assert any(edge.from_object_type == "raw_record" and edge.relation == "text_normalized_into" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, raw_ids[0])
        assert raw_record is not None
        assert raw_record.payload["normalize_text"]["status"] == "valid"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "cleaner.normalize_text.completed" in audit_payload
    assert data["algorithm_run"]["algorithm_run_id"] in audit_payload


def test_s2_normalize_datetime_cleaner_parses_formats_and_marks_review_required() -> None:
    headers = _headers()
    prefix = _unique_name("S2 normalize datetime")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual_upload"},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} repository job", "payload": {"normalize_datetime_probe": True}},
    )
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    collection_run_id = run_response.json()["data"]["collection_run_id"]
    batch_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": collection_run_id,
            "complete_run": True,
            "response_limit": 3,
            "records": [
                {
                    "title": "Slash offset time",
                    "content": "Xi'an public service note happened at 2026/05/09 17:30 +0800.",
                    "raw_uri": "synthetic://xian/normalize-datetime/slash-offset",
                    "is_synthetic": True,
                },
                {
                    "title": "Payload ISO time",
                    "content": "Time field is supplied through payload metadata.",
                    "raw_uri": "synthetic://xian/normalize-datetime/payload-iso",
                    "is_synthetic": True,
                    "payload": {"published_at": "2026-05-09T09:15:00Z"},
                },
                {
                    "title": "Review required time",
                    "content": "Xi'an public service note has no parseable datetime.",
                    "raw_uri": "synthetic://xian/normalize-datetime/review",
                    "is_synthetic": True,
                },
            ],
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    raw_ids = [item["raw_record_id"] for item in batch_response.json()["data"]["raw_records"]]

    normalization = client.post(
        "/api/v1/normalization-runs/datetime",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "normalize_datetime-test-v1", "response_limit": 10},
    )
    assert normalization.status_code == 201, normalization.text
    data = normalization.json()["data"]
    assert data["status"] == "completed"
    assert data["output_count"] == 3
    assert data["cleaner"]["activity_name"] == "normalize_datetime"
    assert data["cleaner"]["normalized_count"] == 2
    assert data["cleaner"]["review_required_count"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "normalize_datetime"
    assert data["algorithm_run"]["metrics"]["per_item_ms"] < 10
    outputs_by_raw = {item["raw_record_id"]: item for item in data["outputs"]}
    slash_output = outputs_by_raw[raw_ids[0]]
    iso_output = outputs_by_raw[raw_ids[1]]
    review_output = outputs_by_raw[raw_ids[2]]
    assert slash_output["payload"]["cleaner_status"] == "normalized"
    assert slash_output["payload"]["normalized_datetime_utc"] == "2026-05-09T09:30:00Z"
    assert slash_output["payload"]["original_timezone"] == "+08:00"
    assert iso_output["payload"]["normalized_datetime_utc"] == "2026-05-09T09:15:00Z"
    assert iso_output["payload"]["original_timezone"] == "Z"
    assert iso_output["payload"]["source_field"] == "payload.published_at"
    assert review_output["payload"]["cleaner_status"] == "review_required"
    assert review_output["payload"]["error_code"] == "DATETIME_PARSE_REVIEW_REQUIRED"

    with Session(engine) as db:
        clean_id = slash_output["normalization_output_id"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == clean_id)).scalars())
        assert any(edge.from_object_type == "raw_record" and edge.relation == "datetime_normalized_into" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, raw_ids[0])
        assert raw_record is not None
        assert raw_record.payload["normalize_datetime"]["status"] == "normalized"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "cleaner.normalize_datetime.completed" in audit_payload
    assert data["algorithm_run"]["algorithm_run_id"] in audit_payload


def test_s2_normalize_location_cleaner_extracts_city_district_address_and_marks_candidates() -> None:
    headers = _headers()
    prefix = _unique_name("S2 normalize location")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual_upload"},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} repository job", "payload": {"normalize_location_probe": True}},
    )
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    collection_run_id = run_response.json()["data"]["collection_run_id"]
    batch_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": collection_run_id,
            "complete_run": True,
            "response_limit": 3,
            "records": [
                {
                    "title": "Beilin service hall",
                    "content": "西安市碑林区政务服务大厅养老保险窗口排队反馈。",
                    "raw_uri": "synthetic://xian/normalize-location/beilin",
                    "is_synthetic": True,
                },
                {
                    "title": "Payload location",
                    "content": "Location supplied through metadata.",
                    "raw_uri": "synthetic://xian/normalize-location/payload",
                    "is_synthetic": True,
                    "payload": {"city": "西安", "district": "雁塔区", "address": "小寨东路办事大厅"},
                },
                {
                    "title": "Ambiguous districts",
                    "content": "雁塔区和碑林区均有群众反馈，需要人工确认主地点。",
                    "raw_uri": "synthetic://xian/normalize-location/candidates",
                    "is_synthetic": True,
                },
            ],
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    raw_ids = [item["raw_record_id"] for item in batch_response.json()["data"]["raw_records"]]

    normalization = client.post(
        "/api/v1/normalization-runs/location",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "normalize_location-test-v1", "response_limit": 10},
    )
    assert normalization.status_code == 201, normalization.text
    data = normalization.json()["data"]
    assert data["status"] == "completed"
    assert data["cleaner"]["activity_name"] == "normalize_location"
    assert data["cleaner"]["normalized_count"] == 2
    assert data["cleaner"]["candidate_count"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "normalize_location"
    outputs_by_raw = {item["raw_record_id"]: item for item in data["outputs"]}
    beilin_output = outputs_by_raw[raw_ids[0]]
    payload_output = outputs_by_raw[raw_ids[1]]
    candidate_output = outputs_by_raw[raw_ids[2]]
    assert beilin_output["payload"]["cleaner_status"] == "normalized"
    assert beilin_output["payload"]["city_id"] == "xian"
    assert beilin_output["payload"]["district"] == "碑林区"
    assert beilin_output["payload"]["address"] == "西安市碑林区政务服务大厅"
    assert payload_output["payload"]["source_field"] == "payload"
    assert payload_output["payload"]["district"] == "雁塔区"
    assert payload_output["payload"]["address"] == "小寨东路办事大厅"
    assert candidate_output["payload"]["cleaner_status"] == "candidate"
    assert candidate_output["payload"]["error_code"] == "LOCATION_AMBIGUOUS_CANDIDATES"
    assert {item["district"] for item in candidate_output["payload"]["candidates"]} >= {"雁塔区", "碑林区"}

    with Session(engine) as db:
        clean_id = beilin_output["normalization_output_id"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == clean_id)).scalars())
        assert any(edge.from_object_type == "raw_record" and edge.relation == "location_normalized_into" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, raw_ids[0])
        assert raw_record is not None
        assert raw_record.payload["normalize_location"]["status"] == "normalized"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "cleaner.normalize_location.completed" in audit_payload
    assert data["algorithm_run"]["algorithm_run_id"] in audit_payload


def test_s2_assign_source_trust_uses_config_and_defaults_with_warning() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source trust")
    trusted_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} configured source",
            "source_type": "manual_upload",
            "policy": {"source_trust": {"score": 0.87, "version": "trust-policy-test-v1", "reason": "official local notice"}},
        },
    )
    assert trusted_source_response.status_code == 200, trusted_source_response.text
    default_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} default source", "source_type": "manual_upload"},
    )
    assert default_source_response.status_code == 200, default_source_response.text
    trusted_source_id = trusted_source_response.json()["data"]["data_source_id"]
    default_source_id = default_source_response.json()["data"]["data_source_id"]

    def create_raw(source_id: str, label: str) -> str:
        job_response = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label} job", "payload": {"assign_source_trust_probe": True}},
        )
        assert job_response.status_code == 200, job_response.text
        run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run_response.status_code == 200, run_response.text
        batch_response = client.post(
            "/api/v1/raw-records/batches",
            headers=headers,
            json={
                "data_source_id": source_id,
                "collection_run_id": run_response.json()["data"]["collection_run_id"],
                "complete_run": True,
                "response_limit": 1,
                "records": [
                    {
                        "title": f"{label} trust record",
                        "content": "Xi'an first-stage public service trust assignment sample.",
                        "raw_uri": f"synthetic://xian/source-trust/{label}/{uuid4().hex}",
                        "is_synthetic": True,
                    }
                ],
            },
        )
        assert batch_response.status_code == 201, batch_response.text
        return batch_response.json()["data"]["raw_records"][0]["raw_record_id"]

    trusted_raw_id = create_raw(trusted_source_id, "configured")
    default_raw_id = create_raw(default_source_id, "defaulted")
    response = client.post(
        "/api/v1/normalization-runs/source-trust",
        headers=headers,
        json={"raw_record_ids": [trusted_raw_id, default_raw_id], "rule_version": "assign_source_trust-test-v1", "response_limit": 10},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["cleaner"]["activity_name"] == "assign_source_trust"
    assert data["cleaner"]["assigned_count"] == 1
    assert data["cleaner"]["defaulted_count"] == 1
    assert data["cleaner"]["warning_count"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "assign_source_trust"
    outputs_by_raw = {item["raw_record_id"]: item for item in data["outputs"]}
    configured_output = outputs_by_raw[trusted_raw_id]
    default_output = outputs_by_raw[default_raw_id]
    assert configured_output["payload"]["cleaner_status"] == "assigned"
    assert configured_output["payload"]["trust_score"] == 0.87
    assert configured_output["payload"]["trust_band"] == "high"
    assert configured_output["payload"]["trust_source"] == "policy.source_trust.score"
    assert configured_output["payload"]["source_policy_ref"]["policy_version"] == "trust-policy-test-v1"
    assert default_output["payload"]["cleaner_status"] == "defaulted"
    assert default_output["payload"]["trust_score"] == 0.62
    assert default_output["payload"]["trust_band"] == "medium"
    assert default_output["payload"]["warnings"][0]["code"] == "SOURCE_TRUST_DEFAULTED"

    with Session(engine) as db:
        output_id = configured_output["normalization_output_id"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == output_id)).scalars())
        assert any(edge.from_object_type == "raw_record" and edge.relation == "source_trust_assigned_into" for edge in lineages)
        assert any(edge.from_object_type == "data_source" and edge.relation == "source_trust_used_for" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, trusted_raw_id)
        assert raw_record is not None
        assert raw_record.payload["assign_source_trust"]["trust_score"] == 0.87

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "cleaner.assign_source_trust.completed" in audit_payload
    assert data["algorithm_run"]["algorithm_run_id"] in audit_payload


def test_s2_detect_sensitive_fields_marks_phone_id_email_without_leaking_raw_values() -> None:
    headers = _headers()
    prefix = _unique_name("S2 sensitive detector")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual_upload"},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"detect_sensitive_fields_probe": True}},
    )
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    raw_content = "Contact phone 13800138000, id 610112199001011234, email resident@example.org, minor name: Zhang and class 7-3."
    clean_content = "Xi'an public service notice without personal identifiers."
    batch_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run_response.json()["data"]["collection_run_id"],
            "complete_run": True,
            "response_limit": 2,
            "records": [
                {"title": "Sensitive detector record", "content": raw_content, "raw_uri": f"synthetic://xian/sensitive-detector/{uuid4().hex}", "is_synthetic": True},
                {"title": "Clean detector record", "content": clean_content, "raw_uri": f"synthetic://xian/sensitive-detector/{uuid4().hex}", "is_synthetic": True},
            ],
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    raw_ids = [item["raw_record_id"] for item in batch_response.json()["data"]["raw_records"]]

    detection = client.post(
        "/api/v1/detector-runs/sensitive-fields",
        headers=headers,
        json={
            "raw_record_ids": raw_ids,
            "rule_version": "detect_sensitive_fields-test-v1",
            "response_limit": 10,
            "payload": {
                "operator_note": "callback 13800138000 and resident@example.org must be redacted in run payload",
                "nested": {"resident@example.org": 13800138000, "case_id": "610112199001011234"},
            },
        },
    )
    assert detection.status_code == 201, detection.text
    data = detection.json()["data"]
    assert data["status"] == "completed"
    assert data["detector"]["activity_name"] == "detect_sensitive_fields"
    assert data["detector"]["detected_record_count"] == 1
    assert data["detector"]["clean_record_count"] == 1
    assert data["detector"]["sensitive_count"] == 5
    assert data["detector"]["type_counts"]["phone"] == 1
    assert data["detector"]["type_counts"]["id_card"] == 1
    assert data["detector"]["type_counts"]["email"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "detect_sensitive_fields"
    outputs_by_raw = {item["raw_record_id"]: item for item in data["outputs"]}
    sensitive_output = outputs_by_raw[raw_ids[0]]
    clean_output = outputs_by_raw[raw_ids[1]]
    sensitive_payload = sensitive_output["payload"]
    assert sensitive_payload["detector_status"] == "detected"
    assert sensitive_payload["risk_level"] == "sensitive"
    assert set(sensitive_payload["field_types"]) >= {"phone", "id_card", "email", "minor_name", "class_ref"}
    assert all(field["redacted_value"] == "[MASKED]" for field in sensitive_payload["fields"])
    assert "13800138000" not in sensitive_output["normalized_text"]
    serialized_response = json.dumps(data, ensure_ascii=False)
    assert "13800138000" not in serialized_response
    assert "610112199001011234" not in serialized_response
    assert "resident@example.org" not in serialized_response
    assert "Zhang" not in serialized_response
    assert "class 7-3" not in serialized_response
    assert data["payload"]["operator_note"] == "callback [MASKED] and [MASKED] must be redacted in run payload"
    assert data["payload"]["nested"]["[MASKED]"] == "[MASKED]"
    assert data["payload"]["nested"]["case_id"] == "[MASKED]"
    assert data["algorithm_run"]["payload"]["request_payload"]["operator_note"] == "callback [MASKED] and [MASKED] must be redacted in run payload"
    assert "[MASKED]" in sensitive_payload["redacted_preview"]
    assert clean_output["payload"]["detector_status"] == "clean"
    assert clean_output["payload"]["sensitive_count"] == 0

    with Session(engine) as db:
        output_id = sensitive_output["normalization_output_id"]
        persisted_run = db.get(models.NormalizationRun, data["normalization_run_id"])
        persisted_algorithm = db.get(models.AlgorithmRun, data["algorithm_run"]["algorithm_run_id"])
        persisted_outputs = list(db.execute(select(models.RawRecordNormalization).where(models.RawRecordNormalization.normalization_run_id == data["normalization_run_id"])).scalars())
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == output_id)).scalars())
        audits = list(
            db.execute(
                select(models.AuditLog).where(
                    models.AuditLog.action == "detector.detect_sensitive_fields.completed",
                    models.AuditLog.object_id == data["normalization_run_id"],
                )
            ).scalars()
        )
        assert persisted_run is not None
        assert persisted_algorithm is not None
        assert audits
        assert any(edge.from_object_type == "raw_record" and edge.relation == "sensitive_fields_detected_into" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, raw_ids[0])
        assert raw_record is not None
        assert raw_record.payload["detect_sensitive_fields"]["sensitive_count"] == 5
        persisted_surface = json.dumps(
            {
                "normalization_run_payload": persisted_run.payload,
                "algorithm_run": {
                    "payload": persisted_algorithm.payload,
                    "output": persisted_algorithm.output,
                    "metrics": persisted_algorithm.metrics,
                    "input_refs": persisted_algorithm.input_refs,
                    "output_refs": persisted_algorithm.output_refs,
                },
                "outputs": [
                    {"normalized_title": item.normalized_title, "normalized_text": item.normalized_text, "payload": item.payload}
                    for item in persisted_outputs
                ],
                "lineage_payloads": [edge.payload for edge in lineages],
                "audit_payloads": [
                    {
                        "action": item.action,
                        "object_type": item.object_type,
                        "object_id": item.object_id,
                        "reason": item.reason,
                        "before": item.before,
                        "after": item.after,
                        "diff": item.diff,
                        "payload": item.payload,
                    }
                    for item in audits
                ],
            },
            ensure_ascii=False,
        )
        assert "13800138000" not in persisted_surface
        assert "610112199001011234" not in persisted_surface
        assert "resident@example.org" not in persisted_surface
        assert "Zhang" not in persisted_surface
        assert "class 7-3" not in persisted_surface

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "detector.detect_sensitive_fields.completed" in audit_payload
    assert data["algorithm_run"]["algorithm_run_id"] in audit_payload


def test_s2_redact_sensitive_fields_defaults_display_export_to_masked_and_gates_original() -> None:
    headers = _headers()
    prefix = _unique_name("S2 redact sensitive")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "manual",
            "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}},
            "is_synthetic": True,
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"redact_sensitive_fields_probe": True}},
    )
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    raw_content = "Contact phone 13800138000, id 610112199001011234, email resident@example.org, minor name: Zhang and class 7-3."
    batch_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run_response.json()["data"]["collection_run_id"],
            "complete_run": True,
            "response_limit": 1,
            "payload": {"batch_note": "resident@example.org and class 7-3 should not leak from raw record metadata"},
            "records": [
                {
                    "title": "Sensitive redaction record",
                    "content": raw_content,
                    "raw_uri": f"synthetic://xian/sensitive-redaction/resident@example.org/class 7-3/{uuid4().hex}",
                    "external_id": f"resident@example.org-13800138000-610112199001011234-class 7-3-{uuid4().hex}",
                    "dedupe_key": f"resident@example.org-13800138000-610112199001011234-class 7-3-{uuid4().hex}",
                    "metadata": {"uri_owner": "resident@example.org", "class_ref": "class 7-3", "phone": "13800138000"},
                    "is_synthetic": True,
                    "payload": {"record_note": "phone 13800138000 and id 610112199001011234 must be redacted in default metadata"},
                }
            ],
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    assert "13800138000" not in json.dumps(batch_response.json()["data"]["raw_records"], ensure_ascii=False)
    assert "resident@example.org" not in json.dumps(batch_response.json()["data"]["raw_records"], ensure_ascii=False)
    raw_record_id = batch_response.json()["data"]["raw_records"][0]["raw_record_id"]

    redaction = client.post(
        "/api/v1/redaction-runs/sensitive-fields",
        headers=headers,
        json={
            "raw_record_ids": [raw_record_id],
            "rule_version": "redact_sensitive_fields-test-v1",
            "response_limit": 10,
            "payload": {
                "operator_note": "export 13800138000, resident@example.org, class 7-3 and 610112199001011234 as masked only",
                "nested": {"resident@example.org": 13800138000, "case_id": "610112199001011234"},
            },
        },
    )
    assert redaction.status_code == 201, redaction.text
    data = redaction.json()["data"]
    assert data["status"] == "completed"
    assert data["cleaner"]["activity_name"] == "redact_sensitive_fields"
    assert data["cleaner"]["redacted_record_count"] == 1
    assert data["cleaner"]["sensitive_count"] == 5
    assert data["cleaner"]["type_counts"]["phone"] == 1
    assert data["algorithm_run"]["algorithm_name"] == "redact_sensitive_fields"
    output = data["outputs"][0]
    output_payload = output["payload"]
    assert output_payload["cleaner_status"] == "redacted"
    assert output_payload["default_display"] == "redacted"
    assert output_payload["original_access_required_permission"] == "data_source:raw_original"
    assert output_payload["display_text"] == output_payload["export_text"] == output["normalized_text"]
    assert set(output_payload["field_types"]) >= {"phone", "id_card", "email", "minor_name", "class_ref"}
    serialized_response = json.dumps(data, ensure_ascii=False)
    for raw_value in ("13800138000", "610112199001011234", "resident@example.org", "Zhang", "class 7-3"):
        assert raw_value not in serialized_response
    assert data["payload"]["operator_note"] == "export [MASKED], [MASKED], [MASKED] and [MASKED] as masked only"
    assert data["payload"]["nested"]["[MASKED]"] == "[MASKED]"
    assert data["payload"]["nested"]["case_id"] == "[MASKED]"

    default_detail = client.get(f"/api/v1/raw-records/{raw_record_id}", headers=headers)
    assert default_detail.status_code == 200, default_detail.text
    default_data = default_detail.json()["data"]
    assert default_data["access_mode"] == "redacted"
    assert default_data["content_redacted"] is True
    assert default_data["default_display"] == "masked_text"
    assert default_data["content"] == default_data["masked_text"]
    default_surface = json.dumps(default_data, ensure_ascii=False)
    for raw_value in ("13800138000", "610112199001011234", "resident@example.org", "Zhang", "class 7-3"):
        assert raw_value not in default_surface

    export = client.get(f"/api/v1/raw-records/{raw_record_id}/redacted-export", headers=headers)
    assert export.status_code == 200, export.text
    export_data = export.json()["data"]
    assert export_data["access_mode"] == "redacted_export"
    assert export_data["content_redacted"] is True
    assert export_data["content"] == default_data["masked_text"]
    export_surface = json.dumps(export_data, ensure_ascii=False)
    for raw_value in ("13800138000", "610112199001011234", "resident@example.org", "Zhang", "class 7-3"):
        assert raw_value not in export_surface

    role_response = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": f"{prefix} read only", "description": "Can inspect redacted raw records only.", "permission_codes": ["data_source:read"]},
    )
    assert role_response.status_code == 200, role_response.text
    username = f"raw.redacted.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "display_name": "Raw Redacted Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"}
    viewer_detail = client.get(f"/api/v1/raw-records/{raw_record_id}", headers=viewer_headers)
    assert viewer_detail.status_code == 200, viewer_detail.text
    assert viewer_detail.json()["data"]["access_mode"] == "redacted"
    forbidden_original = client.get(f"/api/v1/raw-records/{raw_record_id}/original", headers=viewer_headers)
    assert forbidden_original.status_code == 403
    assert forbidden_original.json()["error"]["code"] == "FORBIDDEN"

    original = client.get(f"/api/v1/raw-records/{raw_record_id}/original", headers=headers)
    assert original.status_code == 200, original.text
    original_data = original.json()["data"]
    assert original_data["access_mode"] == "original"
    assert original_data["content_redacted"] is False
    assert "13800138000" in original_data["content"]

    with Session(engine) as db:
        persisted_run = db.get(models.NormalizationRun, data["normalization_run_id"])
        persisted_algorithm = db.get(models.AlgorithmRun, data["algorithm_run"]["algorithm_run_id"])
        persisted_outputs = list(db.execute(select(models.RawRecordNormalization).where(models.RawRecordNormalization.normalization_run_id == data["normalization_run_id"])).scalars())
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == output["normalization_output_id"])).scalars())
        raw_record_lineages = list(
            db.execute(
                select(models.LineageEdge).where(
                    models.LineageEdge.to_object_type == "raw_record",
                    models.LineageEdge.to_object_id == raw_record_id,
                )
            ).scalars()
        )
        audits = list(
            db.execute(
                select(models.AuditLog).where(
                    models.AuditLog.action.in_(
                        [
                            "cleaner.redact_sensitive_fields.completed",
                            "raw_record.redacted_exported",
                            "raw_record.original_viewed",
                        ]
                    )
                )
            ).scalars()
        )
        assert persisted_run is not None
        assert persisted_algorithm is not None
        assert persisted_outputs
        assert any(edge.from_object_type == "raw_record" and edge.relation == "sensitive_fields_redacted_into" for edge in lineages)
        assert any(edge.from_object_type == "algorithm_run" and edge.relation == "generated" for edge in lineages)
        raw_record = db.get(models.RawRecord, raw_record_id)
        raw_payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert raw_record is not None
        assert raw_record.dedupe_key is not None
        assert raw_record.dedupe_key.startswith("raw-hash:")
        for raw_value in ("13800138000", "610112199001011234", "resident@example.org", "Zhang", "class 7-3"):
            assert raw_value not in raw_record.dedupe_key
        assert raw_record.payload["redact_sensitive_fields"]["sensitive_count"] == 5
        persisted_surface = json.dumps(
            {
                "raw_record_payload": raw_record.payload,
                "raw_payload_metadata": raw_payload.payload,
                "normalization_run_payload": persisted_run.payload,
                "algorithm_run": {
                    "payload": persisted_algorithm.payload,
                    "output": persisted_algorithm.output,
                    "metrics": persisted_algorithm.metrics,
                    "input_refs": persisted_algorithm.input_refs,
                    "output_refs": persisted_algorithm.output_refs,
                },
                "outputs": [
                    {"normalized_title": item.normalized_title, "normalized_text": item.normalized_text, "payload": item.payload}
                    for item in persisted_outputs
                ],
                "lineage_payloads": [edge.payload for edge in lineages],
                "raw_record_lineage_payloads": [edge.payload for edge in raw_record_lineages],
                "audit_payloads": [
                    {
                        "action": item.action,
                        "object_type": item.object_type,
                        "object_id": item.object_id,
                        "reason": item.reason,
                        "before": item.before,
                        "after": item.after,
                        "diff": item.diff,
                        "payload": item.payload,
                    }
                    for item in audits
                ],
            },
            ensure_ascii=False,
        )
        for raw_value in ("13800138000", "610112199001011234", "resident@example.org", "Zhang", "class 7-3"):
            assert raw_value not in persisted_surface
        assert any(item.action == "raw_record.original_viewed" and item.object_id == raw_record_id for item in audits)


def test_s2_dedupe_by_hash_and_external_id_marks_duplicate_of_and_keeps_source_boundary() -> None:
    headers = _headers()
    prefix = _unique_name("S2 rule dedupe")

    def create_manual_source(label: str) -> str:
        response = client.post(
            "/api/v1/data-sources",
            headers=headers,
            json={"name": f"{prefix} {label}", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["data_source_id"]

    def create_collection_run(source_id: str, label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"dedupe_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    source_id = create_manual_source("source A")
    other_source_id = create_manual_source("source B")
    shared_content = "Xi'an public-service petition duplicate body for AT-099 rule dedupe."
    same_source_batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": create_collection_run(source_id, "same source"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {"title": "AT-099 same source kept candidate", "content": shared_content, "is_synthetic": True},
                {"title": "AT-099 same source duplicate candidate", "content": shared_content, "is_synthetic": True},
                {
                    "title": "AT-099 same external kept candidate",
                    "content": "Xi'an AT-099 external identity kept body.",
                    "external_id": "external-case-at-099-001",
                    "dedupe_key": f"external-case-at-099-001-left-{uuid4().hex}",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-099 same external duplicate candidate",
                    "content": "Xi'an AT-099 external identity changed body.",
                    "external_id": "external-case-at-099-001",
                    "dedupe_key": f"external-case-at-099-001-right-{uuid4().hex}",
                    "is_synthetic": True,
                },
            ],
            "reason": "AT-099 same-source duplicate seed",
        },
    )
    assert same_source_batch.status_code == 201, same_source_batch.text
    same_source_ids = [item["raw_record_id"] for item in same_source_batch.json()["data"]["raw_records"]]
    assert len(same_source_ids) == 4
    same_hash_ids = same_source_ids[:2]
    same_external_ids = same_source_ids[2:]

    cross_source_batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": other_source_id,
            "collection_run_id": create_collection_run(other_source_id, "cross source"),
            "complete_run": True,
            "response_limit": 10,
            "records": [{"title": "AT-099 cross source same hash candidate", "content": shared_content, "is_synthetic": True}],
            "reason": "AT-099 cross-source non-merge seed",
        },
    )
    assert cross_source_batch.status_code == 201, cross_source_batch.text
    cross_source_id = cross_source_batch.json()["data"]["raw_records"][0]["raw_record_id"]

    dedupe = client.post(
        "/api/v1/deduplication-runs",
        headers=headers,
        json={
            "raw_record_ids": same_source_ids + [cross_source_id],
            "rule_version": "dedupe_by_hash_and_external_id-test-v1",
            "response_limit": 10,
            "payload": {"source": "test_s2_dedupe_by_hash_and_external_id"},
        },
    )
    assert dedupe.status_code == 200, dedupe.text
    data = dedupe.json()["data"]
    deduper = data["deduper"]
    assert data["status"] == "completed"
    assert deduper["activity_name"] == "dedupe_by_hash_and_external_id"
    assert deduper["duplicate_group_count"] == 2
    assert deduper["duplicate_record_count"] == 2
    assert deduper["cross_source_candidate_count"] == 3
    assert len(data["groups"]) == 2
    hash_group = next(group for group in data["groups"] if set([group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]]) == set(same_hash_ids))
    external_group = next(group for group in data["groups"] if set([group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]]) == set(same_external_ids))
    assert cross_source_id not in hash_group["duplicate_raw_record_ids"]
    assert cross_source_id not in external_group["duplicate_raw_record_ids"]
    assert hash_group["payload"]["source_boundary"] == "same_data_source_only"
    assert external_group["payload"]["source_boundary"] == "same_data_source_only"
    assert "same_data_source_and_content_hash" in hash_group["payload"]["match_rules"]
    assert "same_data_source_and_external_id" in external_group["payload"]["match_rules"]
    assert hash_group["payload"]["duplicate_of"][hash_group["duplicate_raw_record_ids"][0]] == hash_group["kept_raw_record_id"]
    assert external_group["payload"]["duplicate_of"][external_group["duplicate_raw_record_ids"][0]] == external_group["kept_raw_record_id"]

    with Session(engine) as db:
        run = db.get(models.DeduplicationRun, data["deduplication_run_id"])
        assert run is not None
        assert run.payload["algorithm_name"] == "dedupe_by_hash_and_external_id"
        algorithm_run = db.execute(
            select(models.AlgorithmRun).where(
                models.AlgorithmRun.object_type == "deduplication_run",
                models.AlgorithmRun.object_id == data["deduplication_run_id"],
                models.AlgorithmRun.algorithm_name == "dedupe_by_hash_and_external_id",
            )
        ).scalar_one()
        assert algorithm_run.status == "completed"
        assert len(algorithm_run.input_refs) == 5
        assert algorithm_run.output["duplicate_record_count"] == 2
        assert algorithm_run.output["cross_source_candidate_count"] == 3
        cross_source_record = db.get(models.RawRecord, cross_source_id)
        assert cross_source_record is not None
        for group in (hash_group, external_group):
            duplicate_record = db.get(models.RawRecord, group["duplicate_raw_record_ids"][0])
            kept_record = db.get(models.RawRecord, group["kept_raw_record_id"])
            assert duplicate_record is not None and kept_record is not None
            assert duplicate_record.payload["duplicate_of"] == kept_record.id
            assert duplicate_record.payload["dedupe_by_hash_and_external_id"]["duplicate_of"] == kept_record.id
            assert kept_record.payload["dedupe_by_hash_and_external_id"]["status"] == "kept"
        assert "duplicate_of" not in cross_source_record.payload
        assert "dedupe_by_hash_and_external_id" not in cross_source_record.payload
        edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.payload["run_id"].as_string() == data["deduplication_run_id"])).scalars())
        assert sum(1 for edge in edges if edge.relation == "deduplicated_into") == 2
        assert any(edge.from_object_type == "algorithm_run" and edge.to_object_type == "raw_record_dedup_group" for edge in edges)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "dedupe.dedupe_by_hash_and_external_id.completed" in audit_payload


def test_s2_semantic_dedupe_records_creates_candidate_groups_and_partial_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 semantic dedupe")

    def create_manual_source(label: str) -> str:
        response = client.post(
            "/api/v1/data-sources",
            headers=headers,
            json={"name": f"{prefix} {label}", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["data_source_id"]

    def create_collection_run(source_id: str, label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"semantic_dedupe_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    source_a = create_manual_source("source A")
    source_b = create_manual_source("source B")
    batch_a = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_a,
            "collection_run_id": create_collection_run(source_a, "source a records"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {
                    "title": "AT-100 碑林区居民咨询拆迁补偿公示时间",
                    "content": "西安碑林区城中村改造居民持续询问拆迁补偿方案、公示时间和安置进度。",
                    "external_id": f"semantic-a-{uuid4().hex}",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-100 曲江市场食品抽检复核",
                    "content": "曲江市场监管部门发布食品抽检复核安排，与拆迁补偿议题无关。",
                    "external_id": f"semantic-unrelated-{uuid4().hex}",
                    "is_synthetic": True,
                },
            ],
            "reason": "AT-100 semantic candidate seed A",
        },
    )
    assert batch_a.status_code == 201, batch_a.text
    source_a_ids = [item["raw_record_id"] for item in batch_a.json()["data"]["raw_records"]]

    batch_b = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_b,
            "collection_run_id": create_collection_run(source_b, "source b records"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {
                    "title": "AT-100 碑林居民询问城改补偿进度",
                    "content": "碑林居民关注城中村改造补偿公示是否延期，并要求说明安置时间表。",
                    "external_id": f"semantic-b-{uuid4().hex}",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-100 semantic embedding failure row",
                    "content": "这条记录模拟向量服务失败，不能阻断其它候选组生成。",
                    "external_id": f"semantic-fail-{uuid4().hex}",
                    "is_synthetic": True,
                    "payload": {"semantic_embedding": {"force_error": True, "reason": "AT-100 partial failure regression"}},
                },
            ],
            "reason": "AT-100 semantic candidate seed B",
        },
    )
    assert batch_b.status_code == 201, batch_b.text
    source_b_ids = [item["raw_record_id"] for item in batch_b.json()["data"]["raw_records"]]
    similar_ids = {source_a_ids[0], source_b_ids[0]}
    failure_id = source_b_ids[1]

    semantic = client.post(
        "/api/v1/deduplication-runs/semantic",
        headers=headers,
        json={
            "raw_record_ids": source_a_ids + source_b_ids,
            "rule_version": "semantic_dedupe_records-test-v1",
            "response_limit": 10,
            "payload": {"source": "test_s2_semantic_dedupe_records", "similarity_threshold": 0.34},
        },
    )
    assert semantic.status_code == 200, semantic.text
    data = semantic.json()["data"]
    semantic_deduper = data["semantic_deduper"]
    assert data["status"] == "partial"
    assert semantic_deduper["activity_name"] == "semantic_dedupe_records"
    assert semantic_deduper["candidate_group_count"] == 1
    assert semantic_deduper["candidate_record_count"] == 2
    assert semantic_deduper["embedding_failed_count"] == 1
    assert semantic_deduper["embedding_provider"] == "synthetic_deterministic_shingle"
    assert semantic_deduper["synthetic_embedding"] is True
    assert len(data["groups"]) == 1
    group = data["groups"][0]
    assert {group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]} == similar_ids
    assert group["payload"]["activity_name"] == "semantic_dedupe_records"
    assert group["payload"]["candidate_only"] is True
    assert group["payload"]["review_required"] is True
    assert group["payload"]["merge_state"] == "candidate_pending_review"
    assert group["payload"]["match_rule"] == "semantic_similarity"
    assert group["payload"]["similarity_threshold"] == 0.34
    assert group["payload"]["source_boundary"] == "cross_source_allowed_candidate_only"
    assert group["payload"]["min_similarity"] >= 0.34
    assert data["embedding_errors"][0]["raw_record_id"] == failure_id
    assert data["embedding_errors"][0]["error_code"] == "SEMANTIC_EMBEDDING_FORCED_FAILURE"

    with Session(engine) as db:
        run = db.get(models.DeduplicationRun, data["deduplication_run_id"])
        assert run is not None
        assert run.status == "partial"
        assert run.payload["algorithm_name"] == "semantic_dedupe_records"
        assert run.payload["embedding_failed_count"] == 1
        algorithm_run = db.execute(
            select(models.AlgorithmRun).where(
                models.AlgorithmRun.object_type == "deduplication_run",
                models.AlgorithmRun.object_id == data["deduplication_run_id"],
                models.AlgorithmRun.algorithm_name == "semantic_dedupe_records",
            )
        ).scalar_one()
        assert algorithm_run.status == "partial"
        assert algorithm_run.output["candidate_group_count"] == 1
        assert algorithm_run.metrics["embedding_failed_count"] == 1
        assert len(algorithm_run.output_refs) == 1
        for raw_id in source_a_ids + source_b_ids:
            record = db.get(models.RawRecord, raw_id)
            assert record is not None
            assert "duplicate_of" not in record.payload
        for raw_id in similar_ids:
            record = db.get(models.RawRecord, raw_id)
            assert record is not None
            assert record.payload["semantic_dedupe_records"]["status"] == "candidate"
            assert record.payload["semantic_dedupe_records"]["dedup_group_id"] == group["dedup_group_id"]
        failure_record = db.get(models.RawRecord, failure_id)
        assert failure_record is not None
        assert failure_record.payload["semantic_dedupe_records"]["status"] == "embedding_failed"
        edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.payload["run_id"].as_string() == data["deduplication_run_id"])).scalars())
        assert sum(1 for edge in edges if edge.relation == "semantic_candidate_member") == 2
        assert any(edge.from_object_type == "algorithm_run" and edge.to_object_type == "raw_record_dedup_group" for edge in edges)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "dedupe.semantic_dedupe_records.partial" in audit_payload


def test_s2_dedupe_candidate_decision_confirms_and_splits_with_lineage() -> None:
    headers = _headers()
    prefix = _unique_name("S2 dedupe decision")

    def create_manual_source(label: str) -> str:
        response = client.post(
            "/api/v1/data-sources",
            headers=headers,
            json={"name": f"{prefix} {label}", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["data_source_id"]

    def create_collection_run(source_id: str, label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"dedupe_decision_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    source_a = create_manual_source("source A")
    source_b = create_manual_source("source B")
    batch_a = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_a,
            "collection_run_id": create_collection_run(source_a, "source a"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {"title": "AT-101 confirm left", "content": "beilin demolition compensation public notice relocation timetable residents ask schedule community settlement disclosure", "is_synthetic": True},
                {"title": "AT-101 split left", "content": "qujiang food safety inspection sample laboratory retest supplier market supervision notice", "is_synthetic": True},
            ],
            "reason": "AT-101 candidate decision seed A",
        },
    )
    assert batch_a.status_code == 201, batch_a.text
    batch_b = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_b,
            "collection_run_id": create_collection_run(source_b, "source b"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {"title": "AT-101 confirm right", "content": "beilin residents ask demolition compensation disclosure schedule and relocation settlement public timetable", "is_synthetic": True},
                {"title": "AT-101 split right", "content": "qujiang food inspection laboratory retest market vendor notice and supervision sample", "is_synthetic": True},
            ],
            "reason": "AT-101 candidate decision seed B",
        },
    )
    assert batch_b.status_code == 201, batch_b.text
    source_a_ids = [item["raw_record_id"] for item in batch_a.json()["data"]["raw_records"]]
    source_b_ids = [item["raw_record_id"] for item in batch_b.json()["data"]["raw_records"]]
    confirm_ids = {source_a_ids[0], source_b_ids[0]}
    split_ids = {source_a_ids[1], source_b_ids[1]}

    semantic = client.post(
        "/api/v1/deduplication-runs/semantic",
        headers=headers,
        json={
            "raw_record_ids": source_a_ids + source_b_ids,
            "rule_version": "semantic_dedupe_records-at101-v1",
            "response_limit": 10,
            "payload": {"source": "test_s2_dedupe_candidate_decision", "similarity_threshold": 0.5},
        },
    )
    assert semantic.status_code == 200, semantic.text
    semantic_data = semantic.json()["data"]
    assert semantic_data["semantic_deduper"]["candidate_group_count"] == 2
    confirm_group = next(group for group in semantic_data["groups"] if {group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]} == confirm_ids)
    split_group = next(group for group in semantic_data["groups"] if {group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]} == split_ids)

    confirm_raw_id = confirm_group["duplicate_raw_record_ids"][0]
    confirm = client.post(
        f"/api/v1/clean-records/{confirm_raw_id}/dedupe-decision",
        headers=headers,
        json={"decision": "confirm_duplicate", "dedup_group_id": confirm_group["dedup_group_id"], "reason": "AT-101 confirmed candidate after human review"},
    )
    assert confirm.status_code == 200, confirm.text
    confirm_data = confirm.json()["data"]
    assert confirm_data["decision"]["status"] == "confirmed_duplicate"
    assert confirm_data["decision"]["duplicate_of_raw_record_id"] == confirm_group["kept_raw_record_id"]
    assert confirm_data["group"]["payload"]["merge_state"] == "confirmed_duplicate"
    assert confirm_data["duplicate_raw_record_ids"] == confirm_group["duplicate_raw_record_ids"]

    repeated = client.post(
        f"/api/v1/clean-records/{confirm_raw_id}/dedupe-decision",
        headers=headers,
        json={"decision": "confirm_duplicate", "dedup_group_id": confirm_group["dedup_group_id"], "reason": "AT-101 duplicate submit"},
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "DEDUPE_DECISION_ALREADY_APPLIED"

    split_raw_id = split_group["duplicate_raw_record_ids"][0]
    split = client.post(
        f"/api/v1/clean-records/{split_raw_id}/dedupe-decision",
        headers=headers,
        json={"decision": "split_candidate", "dedup_group_id": split_group["dedup_group_id"], "reason": "AT-101 split after human review"},
    )
    assert split.status_code == 200, split.text
    split_data = split.json()["data"]
    assert split_data["decision"]["status"] == "split_candidate"
    assert split_data["group"]["payload"]["merge_state"] == "split_candidate"

    with Session(engine) as db:
        confirmed_duplicate = db.get(models.RawRecord, confirm_raw_id)
        kept = db.get(models.RawRecord, confirm_group["kept_raw_record_id"])
        assert confirmed_duplicate is not None and kept is not None
        assert confirmed_duplicate.payload["duplicate_of"] == kept.id
        assert confirmed_duplicate.payload["dedupe_decision"]["status"] == "confirmed_duplicate"
        assert confirmed_duplicate.payload["semantic_dedupe_records"]["status"] == "confirmed_duplicate"
        assert kept.payload["dedupe_decision"]["status"] == "kept"
        for raw_id in split_ids:
            split_record = db.get(models.RawRecord, raw_id)
            assert split_record is not None
            assert "duplicate_of" not in split_record.payload
            assert split_record.payload["dedupe_decision"]["status"] == "split_candidate"
            assert split_record.payload["semantic_dedupe_records"]["status"] == "split_candidate"
        confirm_edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.payload["dedupe_decision_id"].as_string() == confirm_data["decision"]["dedupe_decision_id"])).scalars())
        split_edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.payload["dedupe_decision_id"].as_string() == split_data["decision"]["dedupe_decision_id"])).scalars())
        assert any(edge.relation == "deduplicated_into" and edge.from_object_id == confirm_raw_id and edge.to_object_id == kept.id for edge in confirm_edges)
        assert sum(1 for edge in split_edges if edge.relation == "dedupe_candidate_split") == 2

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "dedupe.candidate.confirmed" in audit_payload
    assert "dedupe.candidate.split" in audit_payload


def test_s2_clean_records_list_filters_status_source_time_and_permission() -> None:
    headers = _headers()
    prefix = _unique_name("S2 clean list")

    def create_manual_source(label: str) -> str:
        response = client.post(
            "/api/v1/data-sources",
            headers=headers,
            json={"name": f"{prefix} {label}", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["data_source_id"]

    def create_collection_run(source_id: str, label: str) -> str:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"clean_record_list_probe": label}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        return run.json()["data"]["collection_run_id"]

    source_a = create_manual_source("source A")
    source_b = create_manual_source("source B")
    batch_a = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_a,
            "collection_run_id": create_collection_run(source_a, "source a"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {
                    "title": "AT-110 confirm left",
                    "content": "beilin demolition compensation public notice relocation timetable residents ask schedule community settlement disclosure",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-110 candidate left",
                    "content": "xian pension service queue update residents ask window guidance insurance explanation follow up notice",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-110 cleaned only",
                    "content": "xian transit reroute notice asks for accessible alternative stops and public update cadence",
                    "is_synthetic": True,
                },
            ],
            "reason": "AT-110 clean record list seed A",
        },
    )
    assert batch_a.status_code == 201, batch_a.text
    batch_b = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_b,
            "collection_run_id": create_collection_run(source_b, "source b"),
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {
                    "title": "AT-110 confirm right",
                    "content": "beilin residents ask demolition compensation disclosure schedule and relocation settlement public timetable",
                    "is_synthetic": True,
                },
                {
                    "title": "AT-110 candidate right",
                    "content": "xian pension insurance service queue residents request guidance window follow up policy explanation notice",
                    "is_synthetic": True,
                },
            ],
            "reason": "AT-110 clean record list seed B",
        },
    )
    assert batch_b.status_code == 201, batch_b.text
    source_a_ids = [item["raw_record_id"] for item in batch_a.json()["data"]["raw_records"]]
    source_b_ids = [item["raw_record_id"] for item in batch_b.json()["data"]["raw_records"]]
    raw_ids = source_a_ids + source_b_ids

    normalization = client.post(
        "/api/v1/normalization-runs",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "normalize_text-at110-v1", "response_limit": 10, "payload": {"source": "test_s2_clean_records_list"}},
    )
    assert normalization.status_code == 200, normalization.text
    assert normalization.json()["data"]["status"] == "completed"

    semantic = client.post(
        "/api/v1/deduplication-runs/semantic",
        headers=headers,
        json={
            "raw_record_ids": raw_ids,
            "rule_version": "semantic_dedupe_records-at110-v1",
            "response_limit": 10,
            "payload": {"source": "test_s2_clean_records_list", "similarity_threshold": 0.5},
        },
    )
    assert semantic.status_code == 200, semantic.text
    groups = semantic.json()["data"]["groups"]
    assert len(groups) >= 2
    confirm_group = next(group for group in groups if {group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]} == {source_a_ids[0], source_b_ids[0]})
    candidate_group = next(group for group in groups if {group["kept_raw_record_id"], *group["duplicate_raw_record_ids"]} == {source_a_ids[1], source_b_ids[1]})

    confirm_raw_id = confirm_group["duplicate_raw_record_ids"][0]
    confirmed = client.post(
        f"/api/v1/clean-records/{confirm_raw_id}/dedupe-decision",
        headers=headers,
        json={"decision": "confirm_duplicate", "dedup_group_id": confirm_group["dedup_group_id"], "reason": "AT-110 list status seed"},
    )
    assert confirmed.status_code == 200, confirmed.text

    page = client.get("/api/v1/clean-records", headers=headers, params={"data_source_id": source_a, "page": 1, "page_size": 10})
    assert page.status_code == 200, page.text
    payload = page.json()
    assert payload["meta"]["page_state"] == "ready"
    assert payload["meta"]["filters"]["data_source_id"] == source_a
    assert payload["meta"]["pagination"]["page"] == 1
    assert payload["meta"]["pagination"]["page_size"] == 10
    assert payload["meta"]["status_counts_scope"] == "page"
    assert {item["data_source_id"] for item in payload["data"]} == {source_a}
    assert all(item["masked_text_preview"] for item in payload["data"])
    assert all(item["content_redacted"] is True for item in payload["data"])
    assert any(item["clean_status"] == "dedupe_candidate" for item in payload["data"])
    assert any(item["clean_status"] in {"cleaned", "kept"} for item in payload["data"])

    candidate_page = client.get(
        "/api/v1/clean-records",
        headers=headers,
        params={"status": "dedupe_candidate", "data_source_id": source_a, "page_size": 10},
    )
    assert candidate_page.status_code == 200, candidate_page.text
    assert {item["raw_record_id"] for item in candidate_page.json()["data"]} == {source_a_ids[1]}
    assert candidate_page.json()["data"][0]["dedupe_group_id"] == candidate_group["dedup_group_id"]

    duplicate_page = client.get(
        "/api/v1/clean-records",
        headers=headers,
        params={"status": "confirmed_duplicate", "page_size": 10},
    )
    assert duplicate_page.status_code == 200, duplicate_page.text
    duplicate_ids = {item["raw_record_id"] for item in duplicate_page.json()["data"]}
    assert confirm_raw_id in duplicate_ids
    duplicate_item = next(item for item in duplicate_page.json()["data"] if item["raw_record_id"] == confirm_raw_id)
    assert duplicate_item["duplicate_of_raw_record_id"] == confirm_group["kept_raw_record_id"]

    time_page = client.get(
        "/api/v1/clean-records",
        headers=headers,
        params={"data_source_id": source_a, "created_from": "2000-01-01T00:00:00Z", "created_to": "2100-01-01T00:00:00Z", "page_size": 10},
    )
    assert time_page.status_code == 200, time_page.text
    assert {item["raw_record_id"] for item in time_page.json()["data"]} >= set(source_a_ids)

    invalid_status = client.get("/api/v1/clean-records", headers=headers, params={"status": "made_up"})
    assert invalid_status.status_code == 422
    assert invalid_status.json()["error"]["code"] == "CLEAN_RECORD_STATUS_INVALID"
    invalid_date = client.get("/api/v1/clean-records", headers=headers, params={"created_from": "not-a-date"})
    assert invalid_date.status_code == 422
    assert invalid_date.json()["error"]["code"] == "CLEAN_RECORD_CREATED_FROM_INVALID"

    assert all("normalized_text" not in (item.get("normalization") or {}) for item in page.json()["data"])
    assert any((item.get("normalization") or {}).get("normalized_text_preview") for item in page.json()["data"])

    foreign_tenant_id = f"tenant-at110-{uuid4().hex[:8]}"
    foreign_source_id = f"DS-{uuid4().hex[:20]}"
    foreign_raw_id = f"RAW-{uuid4().hex[:20]}"
    foreign_username = f"at110.foreign.{uuid4().hex[:8]}"
    with Session(engine) as db:
        read_permission = db.execute(select(models.Permission).where(models.Permission.code == "data_source:read")).scalar_one()
        foreign_role_id = f"ROLE-{uuid4().hex[:20]}"
        foreign_user_id = f"USR-{uuid4().hex[:20]}"
        foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
        foreign_run_id = f"CRUN-{uuid4().hex[:20]}"
        db.add(models.Tenant(id=foreign_tenant_id, name="AT-110 Foreign Tenant", status="active", payload={}))
        db.flush()
        db.add(models.Role(id=foreign_role_id, tenant_id=foreign_tenant_id, name=f"at110_foreign_reader_{uuid4().hex[:6]}", status="active", payload={}))
        db.add(models.User(id=foreign_user_id, tenant_id=foreign_tenant_id, username=foreign_username, display_name="AT-110 Foreign Reader", password_hash=foundation.hash_password("StrongPass123!"), status="active", payload={}))
        db.add(models.DataSource(id=foreign_source_id, tenant_id=foreign_tenant_id, name="AT-110 foreign source", source_type="manual", status="active", is_synthetic=True, policy={}, payload={}))
        db.flush()
        db.add(models.RolePermission(role_id=foreign_role_id, permission_id=read_permission.id))
        db.add(models.UserRole(user_id=foreign_user_id, role_id=foreign_role_id))
        db.add(models.CollectionJob(id=foreign_job_id, tenant_id=foreign_tenant_id, data_source_id=foreign_source_id, created_by_id=foreign_user_id, name="AT-110 foreign job", status="active", payload={}))
        db.flush()
        db.add(models.CollectionRun(id=foreign_run_id, collection_job_id=foreign_job_id, data_source_id=foreign_source_id, status="completed", record_count=1, trace_id="at110-foreign", payload={}))
        db.flush()
        db.add(models.RawRecord(id=foreign_raw_id, tenant_id=foreign_tenant_id, data_source_id=foreign_source_id, collection_run_id=foreign_run_id, source_type="manual", title="AT-110 foreign raw", content_hash=_unique_name("foreign-hash"), status="collected", is_synthetic=True, city_id="xian", payload={"foreign_tenant_probe": True}))
        db.flush()
        db.add(models.RawRecordPayload(id=f"RAWP-{uuid4().hex[:20]}", raw_record_id=foreign_raw_id, content_text="foreign tenant raw content", masked_text="foreign tenant raw content", payload={}))
        db.commit()

    foreign_source_lookup = client.get("/api/v1/clean-records", headers=headers, params={"data_source_id": foreign_source_id})
    assert foreign_source_lookup.status_code == 403
    assert foreign_source_lookup.json()["error"]["code"] == "FORBIDDEN"

    foreign_login = client.post("/api/v1/auth/login", json={"username": foreign_username, "password": "StrongPass123!"})
    assert foreign_login.status_code == 200, foreign_login.text
    foreign_headers = {"Authorization": f"Bearer {foreign_login.json()['data']['access_token']}"}
    foreign_raw_records = client.get("/api/v1/raw-records", headers=foreign_headers)
    assert foreign_raw_records.status_code == 200, foreign_raw_records.text
    assert foreign_raw_id in {item["raw_record_id"] for item in foreign_raw_records.json()["data"]}
    assert {item["tenant_id"] for item in foreign_raw_records.json()["data"]} == {foreign_tenant_id}

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at110_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not clean records.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at110.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-110 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/clean-records", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "clean_record.list" in audit_payload


def test_s2_clean_record_detail_raw_clean_extraction_lineage_and_permission() -> None:
    headers = _headers()
    prefix = _unique_name("S2 clean detail")
    source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["data"]["data_source_id"]
    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"clean_record_detail_probe": True}},
    )
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run.json()["data"]["collection_run_id"],
            "complete_run": True,
            "response_limit": 5,
            "records": [
                {
                    "title": "AT-111 clean detail pension queue",
                    "content": "xian pension service queue asks for guidance and callback phone 13800138000 with public notice evidence.",
                    "is_synthetic": True,
                }
            ],
            "reason": "AT-111 clean detail seed",
        },
    )
    assert batch.status_code == 201, batch.text
    raw_id = batch.json()["data"]["raw_records"][0]["raw_record_id"]

    normalization = client.post(
        "/api/v1/normalization-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "normalize_text-at111-v1", "response_limit": 5, "payload": {"source": "test_s2_clean_record_detail"}},
    )
    assert normalization.status_code == 200, normalization.text
    quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "data_quality-at111-v1", "response_limit": 5, "payload": {"source": "test_s2_clean_record_detail"}},
    )
    assert quality.status_code == 200, quality.text
    extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "limit": 5, "rule_version": "s4a-signal-extract-at111-v1", "payload": {"source": "test_s2_clean_record_detail"}},
    )
    assert extraction.status_code == 201, extraction.text
    assert extraction.json()["data"]["payload"]["output_count"] >= 1

    detail = client.get(f"/api/v1/clean-records/{raw_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    data = payload["data"]
    assert payload["meta"]["page_state"] == "ready"
    assert data["clean_record_id"] == raw_id
    assert data["raw"]["access_mode"] == "redacted"
    assert data["raw"]["content_redacted"] is True
    assert "13800138000" not in json.dumps(data, ensure_ascii=False)
    assert "[MASKED]" in data["raw"]["masked_text"]
    assert data["clean"]["latest_normalization"]["normalized_text"]
    assert data["clean"]["latest_normalization"]["normalized_text_preview"]
    assert "13800138000" not in data["clean"]["latest_normalization"]["normalized_text"]
    assert data["quality"]["issue_count"] >= 1
    assert any(issue["issue_type"] == "sensitive_masked" for issue in data["quality"]["issues"])
    assert data["extractions"]["signal_count"] >= 1
    assert data["extractions"]["signals"][0]["payload"]["evidence_refs"]
    assert data["lineage"]["edge_count"] >= 2
    relations = {edge["relation"] for edge in data["lineage"]["edges"]}
    assert {"text_normalized_into", "extracted_signal"}.issubset(relations)
    assert data["access"]["original_access_required_permission"] == "data_source:raw_original"

    missing = client.get("/api/v1/clean-records/RAW-missing", headers=headers)
    assert missing.status_code == 404

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at111_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not clean detail.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at111.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-111 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get(f"/api/v1/clean-records/{raw_id}", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "clean_record.detail_viewed" in audit_payload


def test_s2_clean_record_status_update_affects_extraction_and_report_lock() -> None:
    headers = _headers()
    prefix = _unique_name("S2 clean status")
    source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}}},
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["data"]["data_source_id"]
    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"clean_record_status_probe": True}},
    )
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": run.json()["data"]["collection_run_id"],
            "complete_run": True,
            "response_limit": 5,
            "records": [
                {"title": "AT-112 valid clean record", "content": "xian transit reroute notice asks for accessible alternative stops", "is_synthetic": True},
                {"title": "AT-112 invalid clean record", "content": "xian pension queue duplicate invalid note should not feed signal extraction", "is_synthetic": True},
                {"title": "AT-112 report-chain clean record", "content": "xian service evidence chain should lock invalid status once it enters a report", "is_synthetic": True},
            ],
            "reason": "AT-112 clean status seed",
        },
    )
    assert batch.status_code == 201, batch.text
    valid_id, invalid_id, report_chain_id = [item["raw_record_id"] for item in batch.json()["data"]["raw_records"]]
    normalization = client.post(
        "/api/v1/normalization-runs",
        headers=headers,
        json={"raw_record_ids": [valid_id, invalid_id, report_chain_id], "rule_version": "normalize_text-at112-v1", "response_limit": 5, "payload": {"source": "test_s2_clean_record_status_update"}},
    )
    assert normalization.status_code == 200, normalization.text

    valid = client.patch(
        f"/api/v1/clean-records/{valid_id}/status",
        headers=headers,
        json={"status": "valid", "reason": "AT-112 accepted for downstream signal generation."},
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["data"]["clean_record"]["clean_status"] == "valid"
    assert valid.json()["data"]["downstream_effect"]["signal_generation_allowed"] is True

    review = client.patch(
        f"/api/v1/clean-records/{valid_id}/status",
        headers=headers,
        json={"status": "review_required", "reason": "AT-112 needs source-owner review."},
    )
    assert review.status_code == 200, review.text
    assert review.json()["data"]["status_transition"]["previous_status"] == "valid"
    assert review.json()["data"]["clean_record"]["clean_status"] == "review_required"
    assert review.json()["data"]["downstream_effect"]["signal_generation_allowed"] is False

    invalid = client.patch(
        f"/api/v1/clean-records/{invalid_id}/status",
        headers=headers,
        json={"status": "invalid", "reason": "AT-112 invalid data should be skipped."},
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["data"]["clean_record"]["clean_status"] == "invalid"
    assert invalid.json()["data"]["downstream_effect"]["signal_generation_allowed"] is False

    invalid_detail = client.get(f"/api/v1/clean-records/{invalid_id}", headers=headers)
    assert invalid_detail.status_code == 200, invalid_detail.text
    assert invalid_detail.json()["data"]["clean_record"]["clean_status"] == "invalid"
    assert invalid_detail.json()["data"]["clean_record"]["payload"]["clean_record_status"]["reason"] == "AT-112 invalid data should be skipped."

    invalid_extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"raw_record_ids": [invalid_id], "limit": 5, "rule_version": "s4a-signal-extract-at112-v1", "payload": {"source": "test_s2_clean_record_status_update"}},
    )
    assert invalid_extraction.status_code == 201, invalid_extraction.text
    assert invalid_extraction.json()["data"]["status"] == "failed"
    assert invalid_extraction.json()["data"]["payload"]["error_code"] == "RAW_RECORD_SCOPE_EMPTY"

    report_chain_valid = client.patch(
        f"/api/v1/clean-records/{report_chain_id}/status",
        headers=headers,
        json={"status": "valid", "reason": "AT-112 report-chain record is valid before report use."},
    )
    assert report_chain_valid.status_code == 200, report_chain_valid.text
    chain_extraction = client.post(
        "/api/v1/extraction-runs",
        headers=headers,
        json={"raw_record_ids": [report_chain_id], "limit": 5, "rule_version": "s4a-signal-extract-at112-report-chain-v1", "payload": {"source": "test_s2_clean_record_status_update"}},
    )
    assert chain_extraction.status_code == 201, chain_extraction.text
    assert chain_extraction.json()["data"]["status"] == "completed"
    signal_id = chain_extraction.json()["data"]["payload"]["sample_outputs"][0]["id"]
    evidence_response = client.post(
        "/api/v1/evidence-candidates",
        headers=headers,
        json={"signal_ids": [signal_id], "rule_version": "s4b-evidence-at112-report-chain-v1", "payload": {"source": "test_s2_clean_record_status_update"}},
    )
    assert evidence_response.status_code == 201, evidence_response.text
    evidence_id = evidence_response.json()["data"]["evidence"][0]["id"]
    evidence_ref = {"object_type": "evidence", "object_id": evidence_id}
    with Session(engine) as db:
        case = models.Case(id=f"CASE-{uuid4().hex[:20]}", slug=f"at112-{uuid4().hex[:8]}", title="AT-112 report lock", scenario_type="test", status="active", payload={})
        db.add(case)
        db.flush()
        report = models.Report(id=f"RPT-{uuid4().hex[:20]}", tenant_id=foundation.DEFAULT_TENANT_ID, case_id=case.id, title="AT-112 locked report", human_confirmed=False, status="draft", payload={"evidence_refs": [evidence_ref], "input_refs": [{"object_type": "evidence", "object_id": evidence_id}]})
        db.add(report)
        db.flush()
        db.add(
            models.ReportClaim(
                id=f"RCL-{uuid4().hex[:20]}",
                tenant_id=foundation.DEFAULT_TENANT_ID,
                report_id=report.id,
                report_version_id=None,
                position=1,
                claim_type="raw_record_lock",
                statement="AT-112 raw record has entered a report.",
                status="draft",
                validation_status="valid",
                source_object_type="evidence",
                source_object_id=evidence_id,
                evidence_refs=[evidence_ref],
                payload={},
            )
        )
        db.add(
            models.Task(
                id=f"TASK-{uuid4().hex[:20]}",
                tenant_id=foundation.DEFAULT_TENANT_ID,
                case_id=case.id,
                report_id=report.id,
                title="AT-112 report-chain task",
                owner="qa",
                due_label="2h",
                status="suggested",
                evidence_refs=[evidence_ref],
                payload={"source": "AT-112 report-chain fixture"},
            )
        )
        db.commit()

    locked = client.patch(
        f"/api/v1/clean-records/{report_chain_id}/status",
        headers=headers,
        json={"status": "invalid", "reason": "AT-112 cannot invalidate once used in report."},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "CLEAN_RECORD_REPORT_LOCKED"

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at112_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not change clean status.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at112.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-112 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.patch(
        f"/api/v1/clean-records/{invalid_id}/status",
        headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"},
        json={"status": "valid", "reason": "AT-112 forbidden update"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "clean_record.status_updated" in audit_payload


def test_s2_score_clean_record_quality_outputs_dimensions_and_clean_scores() -> None:
    headers = _headers()
    prefix = _unique_name("AT113 quality score")

    high_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} high",
            "source_type": "manual",
            "policy": {"entry_schema": {"required_fields": ["title", "content"], "city_id": "xian"}, "source_trust": {"score": 0.95, "version": "at113-high"}},
        },
    )
    low_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} low", "source_type": "public_web", "policy": {"access_mode": "public_web", "source_trust": {"score": 0.25, "version": "at113-low"}}},
    )
    assert high_source.status_code == 200, high_source.text
    assert low_source.status_code == 200, low_source.text

    raw_ids: list[str] = []
    for source, records in [
        (
            high_source.json()["data"],
            [
                {
                    "title": "AT-113 complete pension service quality record",
                    "content": "Xi'an pension service synthetic notice has city, fresh timestamp, clear public source, and enough detail for downstream extraction.",
                    "city_id": "xian",
                    "occurred_at": datetime.utcnow().isoformat() + "Z",
                    "is_synthetic": True,
                    "external_id": f"{prefix}-high",
                }
            ],
        ),
        (
            low_source.json()["data"],
            [
                {
                    "title": "x",
                    "content": "Call 13800138000",
                    "city_id": None,
                    "occurred_at": "2024-01-01T00:00:00Z",
                    "is_synthetic": True,
                    "external_id": f"{prefix}-low",
                }
            ],
        ),
    ]:
        job = client.post(
            "/api/v1/collection-jobs",
            headers=headers,
            json={"data_source_id": source["data_source_id"], "name": f"{prefix} job {source['data_source_id']}"},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        batch = client.post(
            "/api/v1/raw-records/batches",
            headers=headers,
            json={
                "data_source_id": source["data_source_id"],
                "collection_run_id": run.json()["data"]["collection_run_id"],
                "complete_run": True,
                "response_limit": 10,
                "records": records,
                "reason": "AT-113 quality score seed",
            },
        )
        assert batch.status_code == 201, batch.text
        raw_ids.extend(item["raw_record_id"] for item in batch.json()["data"]["raw_records"])

    quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "score_clean_record_quality-at113-v1", "response_limit": 10},
    )
    assert quality.status_code == 200, quality.text
    quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": raw_ids, "rule_version": "score_clean_record_quality-at113-v2", "response_limit": 10},
    )
    assert quality.status_code == 200, quality.text
    payload = quality.json()["data"]
    assert payload["status"] == "completed"
    assert payload["quality_scorer"]["activity_name"] == "score_clean_record_quality"
    assert payload["quality_scorer"]["score_count"] == 2
    assert 0 <= payload["quality_scorer"]["average_overall"] <= 1
    assert payload["algorithm_run"]["algorithm_name"] == "score_clean_record_quality"
    assert payload["algorithm_run"]["status"] == "completed"
    assert payload["algorithm_run"]["metrics"]["input_count"] == 2

    scores = {item["raw_record_id"]: item for item in payload["scores"]}
    high_id, low_id = raw_ids
    for item in scores.values():
        assert set(item["scores"]) >= {"completeness", "freshness", "trust", "overall"}
        assert all(0 <= value <= 1 for value in item["scores"].values())
    assert scores[high_id]["scores"]["overall"] > scores[low_id]["scores"]["overall"]
    assert scores[high_id]["scores"]["completeness"] > scores[low_id]["scores"]["completeness"]
    assert scores[high_id]["scores"]["freshness"] > scores[low_id]["scores"]["freshness"]
    assert scores[high_id]["scores"]["trust"] > scores[low_id]["scores"]["trust"]
    assert "missing_city" in scores[low_id]["issue_types"]
    assert "short_title" in scores[low_id]["issue_types"]
    assert "sensitive_masked" in scores[low_id]["issue_types"]

    with Session(engine) as db:
        run = db.get(models.DataQualityRun, payload["data_quality_run_id"])
        assert run is not None
        assert run.payload["algorithm_name"] == "score_clean_record_quality"
        assert run.payload["score_summary"]["score_count"] == 2
        algorithm_run = db.execute(
            select(models.AlgorithmRun).where(
                models.AlgorithmRun.object_type == "data_quality_run",
                models.AlgorithmRun.object_id == run.id,
                models.AlgorithmRun.algorithm_name == "score_clean_record_quality",
            )
        ).scalar_one()
        assert algorithm_run.output["score_summary"]["score_count"] == 2
        low_record = db.get(models.RawRecord, low_id)
        assert low_record is not None
        assert low_record.payload["score_clean_record_quality"]["scores"]["overall"] == scores[low_id]["scores"]["overall"]
        historical_low_issue_count = db.execute(
            select(func.count()).select_from(models.RawRecordQualityIssue).where(models.RawRecordQualityIssue.raw_record_id == low_id)
        ).scalar_one()
        assert historical_low_issue_count > scores[low_id]["issue_count"]
        oversized_scope = data_sources._scoped_raw_records(
            db,
            [low_id] + [f"RAW-at113-missing-{index}" for index in range(70000)] + [high_id],
            100000,
            foundation.DEFAULT_TENANT_ID,
        )
        assert {record.id for record in oversized_scope} == {high_id, low_id}

        other_tenant_id = f"tenant-at113-{uuid4().hex[:8]}"
        other_quality_run_id = f"QRUN-{uuid4().hex[:20]}"
        db.add(models.Tenant(id=other_tenant_id, name="AT-113 other tenant", status="active", payload={}))
        db.flush()
        db.add(
            models.DataQualityRun(
                id=other_quality_run_id,
                tenant_id=other_tenant_id,
                status="completed",
                input_count=1,
                issue_count=0,
                rule_version="score_clean_record_quality-foreign-v1",
                payload={"algorithm_name": "score_clean_record_quality", "tenant_isolation_probe": True},
            )
        )
        db.commit()

    clean_list = client.get("/api/v1/clean-records", headers=headers, params={"data_source_id": high_source.json()["data"]["data_source_id"], "page_size": 5})
    assert clean_list.status_code == 200, clean_list.text
    listed = next(item for item in clean_list.json()["data"] if item["raw_record_id"] == high_id)
    assert listed["quality_score"] == scores[high_id]["scores"]["overall"]
    assert listed["quality_scores"]["trust"] == scores[high_id]["scores"]["trust"]
    assert listed["quality_issue_count"] == scores[high_id]["issue_count"]

    detail = client.get(f"/api/v1/clean-records/{low_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["clean_record"]["quality_score"] == scores[low_id]["scores"]["overall"]
    assert detail_data["clean_record"]["quality_issue_count"] == scores[low_id]["issue_count"]
    assert detail_data["quality"]["issue_count"] == scores[low_id]["issue_count"]
    assert len(detail_data["quality"]["issues"]) == scores[low_id]["issue_count"]
    assert detail_data["quality"]["score"]["overall"] == scores[low_id]["scores"]["overall"]
    assert detail_data["quality"]["score_dimensions"]["completeness"] == scores[low_id]["scores"]["completeness"]

    quality_runs = client.get("/api/v1/data-quality-runs", headers=headers)
    assert quality_runs.status_code == 200, quality_runs.text
    assert all(item["tenant_id"] == foundation.DEFAULT_TENANT_ID for item in quality_runs.json()["data"])
    assert all(item["payload"].get("tenant_isolation_probe") is not True for item in quality_runs.json()["data"])

    empty_quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": ["RAW-at113-missing"], "rule_version": "score_clean_record_quality-at113-empty", "response_limit": 10},
    )
    assert empty_quality.status_code == 200, empty_quality.text
    empty_scorer = empty_quality.json()["data"]["quality_scorer"]
    assert empty_scorer["score_count"] == 0
    assert empty_scorer["issue_count"] == 0
    assert empty_scorer["average_overall"] == 0
    assert empty_scorer["average_completeness"] == 0
    assert empty_scorer["average_freshness"] == 0
    assert empty_scorer["average_trust"] == 0
    assert empty_scorer["band_counts"] == {}

    lineage = client.get("/api/v1/lineage", headers=headers, params={"object_type": "raw_record", "object_id": low_id})
    assert lineage.status_code == 200, lineage.text
    assert any(edge["from_object_type"] == "algorithm_run" and edge["relation"] == "scored_quality" for edge in lineage.json()["data"])

    audit = client.get("/api/v1/audit-logs", headers=headers).json()["data"]
    assert any(entry["action"] == "data_quality.score_clean_record_quality.completed" for entry in audit)


def test_s2_data_quality_issue_list_filters_permissions_and_tenant_scope() -> None:
    headers = _headers()
    prefix = _unique_name("AT114 quality issues")
    source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} low", "source_type": "public_web", "policy": {"access_mode": "public_web", "source_trust": {"score": 0.2, "version": "at114-low"}}},
    )
    assert source.status_code == 200, source.text
    source_data = source.json()["data"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_data["data_source_id"], "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    batch = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_data["data_source_id"],
            "collection_run_id": run.json()["data"]["collection_run_id"],
            "complete_run": True,
            "response_limit": 10,
            "records": [
                {
                    "title": "x 13800138000",
                    "content": "Call 13800138000",
                    "city_id": None,
                    "occurred_at": "2024-01-01T00:00:00Z",
                    "is_synthetic": True,
                    "external_id": f"{prefix}-low",
                }
            ],
            "reason": "AT-114 quality issue list seed",
        },
    )
    assert batch.status_code == 201, batch.text
    raw_id = batch.json()["data"]["raw_records"][0]["raw_record_id"]
    quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": [raw_id], "rule_version": "score_clean_record_quality-at114-v1", "response_limit": 10},
    )
    assert quality.status_code == 200, quality.text
    quality_run_id = quality.json()["data"]["data_quality_run_id"]

    with Session(engine) as db:
        db.add(
            models.RawRecordQualityIssue(
                id=f"QISS-{uuid4().hex[:20]}",
                tenant_id=foundation.DEFAULT_TENANT_ID,
                data_quality_run_id=quality_run_id,
                raw_record_id=raw_id,
                issue_type="parse_failed",
                severity="error",
                message="Parser failed to extract a main content body.",
                payload={"parser": "parse_html_main_content", "error_code": "HTML_BODY_EMPTY"},
            )
        )

        other_tenant_id = f"tenant-at114-{uuid4().hex[:8]}"
        other_source_id = f"DS-{uuid4().hex[:20]}"
        other_user_id = f"USR-{uuid4().hex[:20]}"
        other_job_id = f"CJOB-{uuid4().hex[:20]}"
        other_run_id = f"CRUN-{uuid4().hex[:20]}"
        other_raw_id = f"RAW-{uuid4().hex[:20]}"
        other_quality_run_id = f"QRUN-{uuid4().hex[:20]}"
        db.add(models.Tenant(id=other_tenant_id, name="AT-114 other tenant", status="active", payload={}))
        db.flush()
        db.add(models.User(id=other_user_id, tenant_id=other_tenant_id, username=f"at114.foreign.{uuid4().hex[:8]}", display_name="AT-114 foreign", password_hash=foundation.hash_password("StrongPass123!"), status="active", payload={}))
        db.add(models.DataSource(id=other_source_id, tenant_id=other_tenant_id, name="AT-114 foreign source", source_type="manual", status="active", is_synthetic=True, policy={}, payload={}))
        db.flush()
        db.add(models.CollectionJob(id=other_job_id, tenant_id=other_tenant_id, data_source_id=other_source_id, created_by_id=other_user_id, name="AT-114 foreign job", status="active", payload={}))
        db.flush()
        db.add(models.CollectionRun(id=other_run_id, collection_job_id=other_job_id, data_source_id=other_source_id, status="completed", record_count=1, trace_id="at114-foreign", payload={}))
        db.add(models.RawRecord(id=other_raw_id, tenant_id=other_tenant_id, data_source_id=other_source_id, collection_run_id=other_run_id, source_type="manual", title="AT-114 foreign raw", content_hash=_unique_name("foreign-hash"), status="collected", is_synthetic=True, city_id="xian", payload={"foreign_tenant_probe": True}))
        db.add(models.DataQualityRun(id=other_quality_run_id, tenant_id=other_tenant_id, status="completed", input_count=1, issue_count=1, rule_version="score_clean_record_quality-foreign-at114", payload={"foreign_tenant_probe": True}))
        db.flush()
        db.add(models.RawRecordQualityIssue(id=f"QISS-{uuid4().hex[:20]}", tenant_id=other_tenant_id, data_quality_run_id=other_quality_run_id, raw_record_id=other_raw_id, issue_type="missing_city", severity="warning", message="Foreign issue must not leak.", payload={"foreign_tenant_probe": True}))
        db.commit()

    page = client.get("/api/v1/data-quality/issues", headers=headers, params={"data_quality_run_id": quality_run_id, "page_size": 20})
    assert page.status_code == 200, page.text
    payload = page.json()
    issue_types = {item["issue_type"] for item in payload["data"]}
    assert {"missing_city", "low_source_trust", "parse_failed"} <= issue_types
    assert all(item["tenant_id"] == foundation.DEFAULT_TENANT_ID for item in payload["data"])
    assert all(item["data_quality_run"]["data_quality_run_id"] == quality_run_id for item in payload["data"])
    assert all(item["raw_record"]["raw_record_id"] == raw_id for item in payload["data"])
    assert all(item["raw_record"]["data_source_id"] == source_data["data_source_id"] for item in payload["data"])
    assert all(any(ref["object_type"] == "raw_record" and ref["object_id"] == raw_id for ref in item["evidence_refs"]) for item in payload["data"])
    assert all(any(ref["object_type"] == "data_quality_run" and ref["object_id"] == quality_run_id for ref in item["evidence_refs"]) for item in payload["data"])
    assert payload["meta"]["pagination"]["total"] >= 6
    assert payload["meta"]["page_state"] == "ready"
    assert payload["meta"]["summary"]["issue_type_counts"]["parse_failed"] == 1
    assert "13800138000" not in json.dumps(payload, ensure_ascii=False)
    assert "foreign_tenant_probe" not in json.dumps(payload, ensure_ascii=False)

    missing_city = client.get("/api/v1/data-quality/issues", headers=headers, params={"issue_type": "missing_city", "page_size": 20})
    assert missing_city.status_code == 200, missing_city.text
    assert missing_city.json()["data"]
    assert all(item["issue_type"] == "missing_city" for item in missing_city.json()["data"])

    parse_failed = client.get("/api/v1/data-quality/issues", headers=headers, params={"issue_type": "parse_failed", "severity": "error", "page_size": 20})
    assert parse_failed.status_code == 200, parse_failed.text
    assert any(item["raw_record"]["raw_record_id"] == raw_id for item in parse_failed.json()["data"])
    assert all(item["severity"] == "error" for item in parse_failed.json()["data"])

    source_filtered = client.get("/api/v1/data-quality/issues", headers=headers, params={"data_source_id": source_data["data_source_id"], "source_type": "public_web", "page_size": 20})
    assert source_filtered.status_code == 200, source_filtered.text
    assert source_filtered.json()["data"]
    assert all(item["raw_record"]["data_source_id"] == source_data["data_source_id"] for item in source_filtered.json()["data"])

    invalid_date = client.get("/api/v1/data-quality/issues", headers=headers, params={"created_from": "not-a-date"})
    assert invalid_date.status_code == 422
    assert invalid_date.json()["error"]["code"] == "DATA_QUALITY_ISSUE_CREATED_FROM_INVALID"

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at114_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not quality issues.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at114.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-114 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/data-quality/issues", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_quality.issue_list_viewed" in audit_payload


def test_s2_db_import_and_object_storage_secure_source_contract() -> None:
    headers = _headers()
    prefix = _unique_name("S2 external storage")

    db_plaintext = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} db plaintext",
            "source_type": "db_import",
            "policy": {"connection_ref": "synthetic://db/xian", "password": "plain-db-password"},
        },
    )
    assert db_plaintext.status_code == 422
    assert db_plaintext.json()["error"]["code"] == "DB_IMPORT_PLAINTEXT_SECRET_NOT_ALLOWED"

    db_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} db valid",
            "source_type": "db_import",
            "policy": {
                "connection_ref": "synthetic://db/xian-social-issues",
                "secret_ref": "vault://s2/db-import",
                "engine": "postgresql",
                "is_synthetic": True,
            },
        },
    )
    assert db_source_response.status_code == 200, db_source_response.text
    db_source = db_source_response.json()["data"]
    assert db_source["status"] == "active"
    assert db_source["policy"]["secret_ref"] == "vault://s2/db-import"
    assert "plain-db-password" not in json.dumps(db_source, ensure_ascii=False)

    db_connection = client.post(
        f"/api/v1/data-sources/{db_source['data_source_id']}/test-connection",
        headers=headers,
        json={"sample_path": "public_petition_rows", "expected_status": 200},
    )
    assert db_connection.status_code == 200, db_connection.text
    assert db_connection.json()["data"]["status"] == "ok"
    assert db_connection.json()["data"]["is_synthetic"] is True
    assert db_connection.json()["data"]["sample_metadata"]["row_count"] == 100

    object_plaintext = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} object plaintext",
            "source_type": "object_storage",
            "policy": {"bucket": "xian-evidence", "secret_key": "plain-object-secret"},
        },
    )
    assert object_plaintext.status_code == 422
    assert object_plaintext.json()["error"]["code"] == "OBJECT_STORAGE_PLAINTEXT_SECRET_NOT_ALLOWED"

    object_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} object valid",
            "source_type": "object_storage",
            "policy": {
                "bucket": "xian-evidence",
                "prefix": "synthetic/public-service/",
                "secret_ref": "vault://s2/object-storage",
                "is_synthetic": True,
            },
        },
    )
    assert object_source_response.status_code == 200, object_source_response.text
    object_source = object_source_response.json()["data"]
    assert object_source["status"] == "active"
    assert object_source["policy"]["secret_ref"] == "vault://s2/object-storage"

    object_list = client.post(
        f"/api/v1/data-sources/{object_source['data_source_id']}/object-storage/list",
        headers=headers,
        json={"max_keys": 1000},
    )
    assert object_list.status_code == 200, object_list.text
    object_data = object_list.json()["data"]
    assert object_data["status"] == "ok"
    assert object_data["key_count"] == 1000
    assert object_data["is_synthetic"] is True

    denied_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} object denied",
            "source_type": "object_storage",
            "policy": {
                "bucket": "xian-denied",
                "prefix": "synthetic/denied/",
                "secret_ref": "vault://s2/object-storage-denied",
                "permission_mode": "deny",
                "is_synthetic": True,
            },
        },
    )
    assert denied_source_response.status_code == 200, denied_source_response.text
    denied_list = client.post(
        f"/api/v1/data-sources/{denied_source_response.json()['data']['data_source_id']}/object-storage/list",
        headers=headers,
        json={"max_keys": 10},
    )
    assert denied_list.status_code == 403
    assert denied_list.json()["error"]["code"] == "OBJECT_STORAGE_BUCKET_FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "plain-db-password" not in audit_payload
    assert "plain-object-secret" not in audit_payload
    assert "data_source.connection_test" in audit_payload
    assert "data_source.object_storage.list" in audit_payload


def test_s2_db_import_table_scan_persists_cursor_raw_records_and_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 db table scan")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "db_import",
            "policy": {
                "connection_ref": "synthetic://db/xian-social-issues",
                "secret_ref": "vault://s2/db-import",
                "engine": "postgresql",
                "is_synthetic": True,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    scanned = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": source_id, "table_name": "public_petition_rows", "cursor_field": "id", "limit": 5, "city_id": "xian"},
    )
    assert scanned.status_code == 200, scanned.text
    data = scanned.json()["data"]
    activity = data["import_run"]["payload"]["db_import_activity"]
    assert data["import_run"]["status"] == "completed"
    assert data["import_run"]["import_type"] == "db_import"
    assert data["collection_run"]["record_count"] == 5
    assert activity["activity_name"] == "scan_db_import_table"
    assert activity["row_count"] == 5
    assert activity["next_cursor"] == 5
    assert activity["is_synthetic"] is True
    assert len(data["raw_records"]) == 5
    assert all(record["source_type"] == "db_import" and record["is_synthetic"] for record in data["raw_records"])
    raw_record_id = data["raw_records"][0]["raw_record_id"]
    run_id = data["collection_run"]["collection_run_id"]
    import_run_id = data["import_run"]["import_run_id"]

    with Session(engine) as db:
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert "public_petition_rows" in payload.content_text
        assert "13800138000" not in payload.masked_text
        assert "[MASKED]" in payload.masked_text
        edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == raw_record_id)).scalars())
        assert any(edge.from_object_type == "data_source" and edge.from_object_id == source_id for edge in edges)
        assert any(edge.from_object_type == "collection_run" and edge.from_object_id == run_id for edge in edges)
        assert any(edge.from_object_type == "import_run" and edge.from_object_id == import_run_id for edge in edges)
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars())
        assert any(event.event_type == "scan_db_import_table_started" and event.status == "running" for event in events)
        assert any(event.event_type == "scan_db_import_table_completed" and event.status == "completed" for event in events)
        refreshed_source = db.get(models.DataSource, source_id)
        assert refreshed_source is not None
        assert refreshed_source.policy["db_import_cursor"]["public_petition_rows"]["id"] == 5

    second = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": source_id, "table_name": "public_petition_rows", "cursor_field": "id", "limit": 3, "city_id": "xian"},
    )
    assert second.status_code == 200, second.text
    second_activity = second.json()["data"]["import_run"]["payload"]["db_import_activity"]
    assert second_activity["start_cursor"] == 5
    assert second_activity["next_cursor"] == 8
    assert second.json()["data"]["raw_records"][0]["payload"]["external_id"] == "public_petition_rows:6"

    failed_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} connection failed",
            "source_type": "db_import",
            "policy": {
                "connection_ref": "synthetic://db/unavailable",
                "secret_ref": "vault://s2/db-import-failed",
                "engine": "postgresql",
                "connection_mode": "fail",
                "is_synthetic": True,
            },
        },
    )
    assert failed_source_response.status_code == 200, failed_source_response.text
    failed = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": failed_source_response.json()["data"]["data_source_id"], "table_name": "public_petition_rows", "limit": 5},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["data"]["import_run"]["status"] == "failed"
    assert failed.json()["data"]["import_run"]["error_code"] == "DB_IMPORT_CONNECTION_FAILED"

    denied_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} permission denied",
            "source_type": "db_import",
            "policy": {
                "connection_ref": "synthetic://db/denied",
                "secret_ref": "vault://s2/db-import-denied",
                "engine": "postgresql",
                "permission_mode": "deny",
                "is_synthetic": True,
            },
        },
    )
    assert denied_source_response.status_code == 200, denied_source_response.text
    denied = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": denied_source_response.json()["data"]["data_source_id"], "table_name": "public_petition_rows", "limit": 5},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "DB_IMPORT_PERMISSION_DENIED"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "db_import.scan.completed" in audit_payload
    assert "db_import.scan.failed" in audit_payload


def test_s2_db_import_cursor_state_service_failure_guard_and_resume() -> None:
    headers = _headers()
    prefix = _unique_name("S2 cursor state")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "db_import",
            "policy": {
                "connection_ref": "synthetic://db/xian-social-issues",
                "secret_ref": "vault://s2/db-import",
                "engine": "postgresql",
                "is_synthetic": True,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    empty_state = client.get(f"/api/v1/data-sources/{source_id}/cursor-state", headers=headers)
    assert empty_state.status_code == 200, empty_state.text
    assert empty_state.json()["data"]["page_state"] == "empty"
    assert empty_state.json()["data"]["cursor_count"] == 0

    first = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": source_id, "table_name": "public_petition_rows", "cursor_field": "id", "limit": 4, "city_id": "xian"},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    first_activity = first_data["import_run"]["payload"]["db_import_activity"]
    assert first_activity["start_cursor"] == 0
    assert first_activity["next_cursor"] == 4

    cursor_state = client.get(f"/api/v1/data-sources/{source_id}/cursor-state", headers=headers)
    assert cursor_state.status_code == 200, cursor_state.text
    state_data = cursor_state.json()["data"]
    assert state_data["page_state"] == "ready"
    assert state_data["cursor_count"] == 1
    assert state_data["cursor_state"]["public_petition_rows"]["id"] == 4
    assert state_data["last_db_import_scan"]["next_cursor"] == 4
    assert state_data["last_db_import_scan"]["collection_run_id"] == first_data["collection_run"]["collection_run_id"]
    assert state_data["last_db_import_scan"]["import_run_id"] == first_data["import_run"]["import_run_id"]
    assert state_data["failure_guard"]["failed_runs_do_not_advance_cursor"] is True
    assert state_data["cursors"][0]["table_key"] == "public_petition_rows"
    assert state_data["cursors"][0]["cursor_field"] == "id"
    assert state_data["cursors"][0]["current_value"] == 4

    current_source = client.get("/api/v1/data-sources", headers=headers, params={"source_type": "db_import", "page_size": 100})
    assert current_source.status_code == 200, current_source.text
    source_record = next(item for item in current_source.json()["data"] if item["data_source_id"] == source_id)
    failing_policy = dict(source_record["policy"])
    failing_policy["connection_ref"] = "synthetic://db/unavailable"
    failing_policy["connection_mode"] = "fail"
    patched_failure = client.patch(
        f"/api/v1/data-sources/{source_id}",
        headers=headers,
        json={"name": source_record["name"], "source_type": "db_import", "policy": failing_policy, "payload": source_record["payload"]},
    )
    assert patched_failure.status_code == 200, patched_failure.text

    failed = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": source_id, "table_name": "public_petition_rows", "cursor_field": "id", "limit": 9, "city_id": "xian"},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["data"]["import_run"]["status"] == "failed"
    assert failed.json()["data"]["import_run"]["error_code"] == "DB_IMPORT_CONNECTION_FAILED"

    after_failure = client.get(f"/api/v1/data-sources/{source_id}/cursor-state", headers=headers)
    assert after_failure.status_code == 200, after_failure.text
    assert after_failure.json()["data"]["cursor_state"]["public_petition_rows"]["id"] == 4

    resumed_policy = dict(failing_policy)
    resumed_policy["connection_ref"] = "synthetic://db/xian-social-issues"
    resumed_policy.pop("connection_mode", None)
    patched_resume = client.patch(
        f"/api/v1/data-sources/{source_id}",
        headers=headers,
        json={"name": source_record["name"], "source_type": "db_import", "policy": resumed_policy, "payload": source_record["payload"]},
    )
    assert patched_resume.status_code == 200, patched_resume.text

    resumed = client.post(
        "/api/v1/imports/db-import",
        headers=headers,
        json={"data_source_id": source_id, "table_name": "public_petition_rows", "cursor_field": "id", "limit": 2, "city_id": "xian"},
    )
    assert resumed.status_code == 200, resumed.text
    resumed_activity = resumed.json()["data"]["import_run"]["payload"]["db_import_activity"]
    assert resumed_activity["start_cursor"] == 4
    assert resumed_activity["next_cursor"] == 6

    resumed_state = client.get(f"/api/v1/data-sources/{source_id}/cursor-state", headers=headers)
    assert resumed_state.status_code == 200, resumed_state.text
    assert resumed_state.json()["data"]["cursor_state"]["public_petition_rows"]["id"] == 6
    assert resumed_state.json()["data"]["cursors"][0]["current_value"] == 6

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.cursor_state.read" in audit_payload
    assert "db_import.scan.failed" in audit_payload


def test_s2_object_storage_prefix_scan_creates_raw_records_file_objects_and_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 object scan")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "object_storage",
            "policy": {
                "bucket": "xian-evidence",
                "prefix": "synthetic/public-service",
                "secret_ref": "vault://s2/object-storage",
                "is_synthetic": True,
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    scanned = client.post(
        "/api/v1/imports/object-storage",
        headers=headers,
        json={"data_source_id": source_id, "prefix": "synthetic/public-service", "limit": 5, "response_limit": 5, "city_id": "xian"},
    )
    assert scanned.status_code == 200, scanned.text
    data = scanned.json()["data"]
    activity = data["import_run"]["payload"]["object_storage_activity"]
    assert data["import_run"]["status"] == "completed"
    assert data["import_run"]["import_type"] == "object_storage"
    assert data["collection_run"]["record_count"] == 5
    assert activity["activity_name"] == "scan_object_storage_prefix"
    assert activity["key_count"] == 5
    assert activity["new_record_count"] == 5
    assert activity["missing_count"] == 0
    assert len(data["raw_records"]) == 5
    assert len(data["file_objects"]) == 5
    assert all(record["source_type"] == "object_storage" and record["is_synthetic"] for record in data["raw_records"])
    raw_record_id = data["raw_records"][0]["raw_record_id"]
    file_object_id = data["file_objects"][0]["file_object_id"]
    run_id = data["collection_run"]["collection_run_id"]
    import_run_id = data["import_run"]["import_run_id"]

    with Session(engine) as db:
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert "synthetic/public-service" in payload.content_text
        assert "13800138000" not in payload.masked_text
        assert "[MASKED]" in payload.masked_text
        file_object = db.get(models.FileObject, file_object_id)
        assert file_object is not None
        assert file_object.status == "stored"
        assert file_object.object_type == "data_source"
        assert file_object.object_id == source_id
        assert file_object.payload["activity_name"] == "scan_object_storage_prefix"
        assert file_object.payload["storage_mode"] == "external_object_storage_reference"
        assert file_object.payload["source_flags"]["synthetic"] is True
        edges = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == raw_record_id)).scalars())
        assert any(edge.from_object_type == "file_object" and edge.from_object_id == file_object_id for edge in edges)
        assert any(edge.from_object_type == "data_source" and edge.from_object_id == source_id for edge in edges)
        assert any(edge.from_object_type == "collection_run" and edge.from_object_id == run_id for edge in edges)
        assert any(edge.from_object_type == "import_run" and edge.from_object_id == import_run_id for edge in edges)
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars())
        assert any(event.event_type == "scan_object_storage_prefix_started" and event.status == "running" for event in events)
        assert any(event.event_type == "scan_object_storage_prefix_completed" and event.status == "completed" for event in events)
        refreshed_source = db.get(models.DataSource, source_id)
        assert refreshed_source is not None
        assert refreshed_source.policy["last_object_storage_scan"]["new_record_count"] == 5

    repeated = client.post(
        "/api/v1/imports/object-storage",
        headers=headers,
        json={"data_source_id": source_id, "prefix": "synthetic/public-service", "limit": 3, "response_limit": 3, "city_id": "xian"},
    )
    assert repeated.status_code == 200, repeated.text
    repeated_activity = repeated.json()["data"]["import_run"]["payload"]["object_storage_activity"]
    assert repeated_activity["new_record_count"] == 0
    assert repeated_activity["skipped_existing_count"] == 3
    assert repeated.json()["data"]["raw_records"] == []

    missing_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} missing source",
            "source_type": "object_storage",
            "policy": {
                "bucket": "xian-evidence",
                "prefix": "synthetic/missing",
                "secret_ref": "vault://s2/object-storage-missing",
                "is_synthetic": True,
                "missing_key_every": 2,
            },
        },
    )
    assert missing_source_response.status_code == 200, missing_source_response.text
    partial = client.post(
        "/api/v1/imports/object-storage",
        headers=headers,
        json={"data_source_id": missing_source_response.json()["data"]["data_source_id"], "prefix": "synthetic/missing", "limit": 5},
    )
    assert partial.status_code == 200, partial.text
    partial_activity = partial.json()["data"]["import_run"]["payload"]["object_storage_activity"]
    assert partial_activity["classification"] == "partial_missing"
    assert partial_activity["missing_count"] == 2
    assert partial_activity["new_record_count"] == 3

    denied_source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} denied source",
            "source_type": "object_storage",
            "policy": {
                "bucket": "xian-denied",
                "prefix": "synthetic/denied",
                "secret_ref": "vault://s2/object-storage-denied",
                "permission_mode": "deny",
                "is_synthetic": True,
            },
        },
    )
    assert denied_source_response.status_code == 200, denied_source_response.text
    denied = client.post(
        "/api/v1/imports/object-storage",
        headers=headers,
        json={"data_source_id": denied_source_response.json()["data"]["data_source_id"], "prefix": "synthetic/denied", "limit": 5},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "OBJECT_STORAGE_BUCKET_FORBIDDEN"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "object_storage.scan.completed" in audit_payload
    assert "object_storage.scan.failed" in audit_payload


def test_s2_data_source_version_publish_requires_connection_and_versions_new_collection() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source version")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()["data"]

    auth = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/versioned-official", "header_name": "X-API-Key"},
    )
    assert auth.status_code == 200, auth.text

    premature_publish = client.post(f"/api/v1/data-sources/{source['data_source_id']}/versions/publish", headers=headers)
    assert premature_publish.status_code == 409
    assert premature_publish.json()["error"]["code"] == "DATA_SOURCE_CONNECTION_TEST_REQUIRED"

    connection = client.post(
        f"/api/v1/data-sources/{source['data_source_id']}/test-connection",
        headers=headers,
        json={"sample_path": "/xian/issues", "expected_status": 200},
    )
    assert connection.status_code == 200, connection.text
    assert connection.json()["data"]["status"] == "ok"

    compliance = client.put(
        f"/api/v1/data-sources/{source['data_source_id']}/compliance",
        headers=headers,
        json=_compliance_payload("AT-049 publish after successful synthetic connection test"),
    )
    assert compliance.status_code == 200, compliance.text

    publish = client.post(
        f"/api/v1/data-sources/{source['data_source_id']}/versions/publish",
        headers=headers,
        json={"reason": "AT-049 publish after successful synthetic connection test"},
    )
    assert publish.status_code == 200, publish.text
    version = publish.json()["data"]
    assert version["version"] == 1
    assert version["status"] == "published"
    assert version["data_source_id"] == source["data_source_id"]
    assert version["policy_snapshot"]["last_connection_test"]["status"] == "ok"
    assert version["config_hash"].startswith("sha256:")

    refreshed = client.get("/api/v1/data-sources", headers=headers, params={"source_type": "official_api", "page_size": 50})
    assert refreshed.status_code == 200
    stored = next(item for item in refreshed.json()["data"] if item["data_source_id"] == source["data_source_id"])
    assert stored["policy"]["published_version"]["version"] == 1
    assert stored["policy"]["config_status"] == "published"

    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source["data_source_id"], "name": f"{prefix} collection"},
    )
    assert job.status_code == 200, job.text
    assert job.json()["data"]["payload"]["data_source_version"] == 1
    assert job.json()["data"]["payload"]["data_source_version_id"] == version["data_source_version_id"]

    run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["payload"]["data_source_version"] == 1
    assert run.json()["data"]["payload"]["data_source_config_hash"] == version["config_hash"]

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.version.publish" in audit_payload


def test_s2_data_source_compliance_tags_gate_version_publish() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source compliance")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    auth = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/compliance-official", "header_name": "X-API-Key"},
    )
    assert auth.status_code == 200, auth.text

    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text

    missing_compliance = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-053 publish without compliance"})
    assert missing_compliance.status_code == 409
    assert missing_compliance.json()["error"]["code"] == "DATA_SOURCE_COMPLIANCE_REQUIRED"

    missing_basis = client.put(
        f"/api/v1/data-sources/{source_id}/compliance",
        headers=headers,
        json={"authorization_scope": "public_sector_notice", "retention_days": 180, "data_classification": "public"},
    )
    assert missing_basis.status_code == 422
    assert missing_basis.json()["error"]["code"] == "DATA_SOURCE_COMPLIANCE_BASIS_REQUIRED"

    compliance = client.put(
        f"/api/v1/data-sources/{source_id}/compliance",
        headers=headers,
        json=_compliance_payload("AT-053 compliance tags saved before publication."),
    )
    assert compliance.status_code == 200, compliance.text
    stored = compliance.json()["data"]
    assert stored["policy"]["compliance"]["authorization_scope"] == "public_sector_notice"
    assert stored["policy"]["compliance"]["authorization_basis"].startswith("Xi'an first-phase")
    assert stored["policy"]["policy_result"]["allowed"] is True
    assert stored["policy"]["policy_result"]["compliance_ready"] is True

    publish = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-053 publish after compliance"})
    assert publish.status_code == 200, publish.text
    assert publish.json()["data"]["policy_snapshot"]["compliance"]["retention_days"] == 180

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.compliance.update" in audit_payload
    assert "AT-053 compliance tags saved before publication" in audit_payload


def test_s2_adapter_registry_registers_required_source_adapters() -> None:
    headers = _headers()
    registry = adapters.build_adapter_registry()
    expected = {"public_web", "official_api", "rss", "file_upload", "media", "manual", "db_import", "object_storage"}
    assert expected.issubset(set(registry))
    for source_type in expected:
        adapter = registry[source_type]
        assert adapter.source_type == source_type
        assert adapter.status == "registered"
        assert adapter.capabilities
        for method in adapters.REQUIRED_ADAPTER_METHODS:
            assert callable(adapter.handlers.get(method))

    broken = adapters.AdapterDefinition(
        source_type="broken",
        label="Broken",
        capabilities={"input": [], "outputs": [], "supports_synthetic": True},
        handlers={
            "discover": lambda *_args, **_kwargs: None,
            "fetch": lambda *_args, **_kwargs: None,
            "parse": lambda *_args, **_kwargs: None,
        },
    )
    try:
        adapters.AdapterRegistry([broken])
    except ValueError as error:
        assert "normalize" in str(error)
    else:
        raise AssertionError("broken adapter without required methods should fail registry startup")

    response = client.get("/api/v1/adapters/capabilities", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert expected.issubset({item["source_type"] for item in rows})
    official = next(item for item in rows if item["source_type"] == "official_api")
    assert official["status"] == "registered"
    assert set(official["required_methods"]) == set(adapters.REQUIRED_ADAPTER_METHODS)
    assert official["contract_status"] == "passed"
    assert all(official["method_status"].values())
    assert "pagination" in official["capabilities"]["input"]
    unknown = client.get("/api/v1/adapters/capabilities", headers=headers, params={"source_type": "unknown_adapter"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "ADAPTER_NOT_FOUND"


def test_s2_channel_adapter_contract_validation_reports_startup_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/adapter-contract", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["service"] == "validate_channel_adapter_contract"
    assert data["status"] == "passed"
    assert data["required_methods"] == list(adapters.REQUIRED_ADAPTER_METHODS)
    assert data["adapter_count"] == 9
    assert data["checked_channel_count"] == 11
    assert data["failure_count"] == 0
    assert data["degraded_channel_count"] == 1

    adapter_contracts = {item["source_type"]: item for item in data["adapters"]}
    assert set(adapter_contracts) == {"public_web", "official_api", "rss", "file_upload", "media", "live_segment", "manual", "db_import", "object_storage"}
    for contract in adapter_contracts.values():
        assert contract["status"] == "passed"
        assert set(contract["method_status"]) == set(adapters.REQUIRED_ADAPTER_METHODS)
        assert all(contract["method_status"].values())
        assert contract["missing_methods"] == []

    channel_contracts = {item["channel"]: item for item in data["channels"]}
    assert channel_contracts["web_page"]["contract_status"] == "passed"
    assert channel_contracts["web_page"]["method_status"]["discover"] is True
    assert channel_contracts["livestream"]["adapter_registered"] is True
    assert channel_contracts["livestream"]["contract_status"] == "passed"
    assert channel_contracts["webhook"]["contract_status"] == "degraded"
    assert channel_contracts["image_file"]["adapter_registered"] is True
    assert channel_contracts["image_file"]["contract_status"] == "passed"
    assert channel_contracts["video_file"]["adapter_registered"] is True
    assert channel_contracts["video_file"]["contract_status"] == "passed"
    assert channel_contracts["audio_file"]["adapter_registered"] is True
    assert channel_contracts["audio_file"]["contract_status"] == "passed"

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at294_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not adapter contracts.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at294.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-294 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/adapter-contract", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.adapter_contract_validated" in audit_payload


def test_s2_collection_channel_registry_lists_required_channels_and_warnings() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    channels = {item["channel"]: item for item in data}
    assert set(channels) == {
        "web_page",
        "official_api",
        "rss",
        "document_file",
        "image_file",
        "video_file",
        "livestream",
        "audio_file",
        "webhook",
        "database",
        "object_storage",
    }
    assert channels["web_page"]["source_type"] == "public_web"
    assert channels["web_page"]["status"] == "available"
    assert channels["web_page"]["adapter_registered"] is True
    assert channels["database"]["source_type"] == "db_import"
    assert channels["object_storage"]["requires_external_key"] is True
    assert channels["livestream"]["status"] == "available"
    assert channels["livestream"]["adapter_registered"] is True
    assert channels["audio_file"]["status"] == "available"
    assert channels["audio_file"]["adapter_registered"] is True
    assert response.json()["meta"]["summary"]["total"] == 11
    assert response.json()["meta"]["summary"]["warning_count"] >= 1

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at293_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not channel registry.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at293.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-293 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.registry_read" in audit_payload


def test_s2_web_page_channel_schema_returns_crawl_policy_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/web_page/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "web_page"
    assert data["source_type"] == "public_web"
    assert data["adapter_source_type"] == "public_web"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"start_url", "max_depth", "respect_robots", "rate_limit_per_minute"}
    schema = data["json_schema"]
    assert schema["required"] == data["required_fields"]
    properties = schema["properties"]
    assert properties["start_url"]["format"] == "uri"
    assert properties["start_url"]["x-accepted-schemes"] == ["https", "http", "synthetic"]
    assert properties["max_depth"]["minimum"] == 0
    assert properties["max_depth"]["maximum"] == 5
    assert properties["respect_robots"]["default"] is True
    assert properties["rate_limit_per_minute"]["minimum"] == 1
    assert properties["rate_limit_per_minute"]["maximum"] == 120
    assert data["validation"]["policy_endpoint"] == "PUT /api/v1/data-sources/{data_source_id}/crawl-policy"
    assert data["validation"]["discovery_endpoint"] == "POST /api/v1/data-sources/{data_source_id}/public-web/discover-links"
    assert "cookie_pool" in data["validation"]["forbidden_access_modes"]
    assert {"discover_public_web_links", "fetch_public_web_page"}.issubset(set(data["workflow_refs"]))

    unsupported = client.get("/api/v1/collection-channels/rss/schema", headers=headers)
    assert unsupported.status_code == 404
    assert unsupported.json()["error"]["code"] == "CHANNEL_SCHEMA_NOT_FOUND"

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at295_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not web page schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at295.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-295 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/web_page/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload


def test_s2_official_api_channel_schema_bans_plain_secret_fields() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/official_api/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "official_api"
    assert data["source_type"] == "official_api"
    assert data["adapter_source_type"] == "official_api"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"base_url", "auth_type", "secret_ref", "sample_path", "pagination_strategy", "max_pages"}
    properties = data["json_schema"]["properties"]
    assert properties["base_url"]["format"] == "uri"
    assert properties["base_url"]["x-accepted-schemes"] == ["https", "http", "synthetic"]
    assert set(properties["auth_type"]["enum"]) == {"api_key", "oauth", "basic", "bearer"}
    assert properties["secret_ref"]["x-secret-handling"] == "reference_only"
    assert properties["secret_ref"]["x-plaintext-secret-allowed"] is False
    assert {"api_key", "secret", "token", "password"}.isdisjoint(set(properties))
    assert properties["pagination_strategy"]["enum"] == ["page", "cursor", "next_url"]
    assert properties["max_pages"]["minimum"] == 1
    assert properties["max_pages"]["maximum"] == 100
    assert data["validation"]["auth_endpoint"] == "PUT /api/v1/data-sources/{data_source_id}/auth"
    assert data["validation"]["connection_test_endpoint"] == "POST /api/v1/data-sources/{data_source_id}/test-connection"
    assert data["validation"]["pagination_endpoint"] == "PUT /api/v1/data-sources/{data_source_id}/pagination"
    assert data["validation"]["fetch_endpoint"] == "POST /api/v1/imports/official-api"
    assert data["validation"]["plain_secret_fields_allowed"] is False
    assert data["validation"]["forbidden_plain_secret_fields"] == ["api_key", "secret", "token", "password"]
    assert data["workflow_refs"] == ["fetch_official_api_page"]

    prefix = _unique_name("AT296 official schema")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": prefix, "source_type": "official_api", "policy": {"access_mode": "official_api", "base_url": "synthetic://xian/official-api"}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    plaintext_auth = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/at296-official", "api_key": "plain-secret-value"},
    )
    assert plaintext_auth.status_code == 422
    assert "plain-secret-value" not in plaintext_auth.text

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at296_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not official schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at296.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-296 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/official_api/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload
    assert "plain-secret-value" not in audit_payload


def test_s2_document_file_channel_schema_returns_allowed_types_and_mapping_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/document_file/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "document_file"
    assert data["source_type"] == "file_upload"
    assert data["adapter_source_type"] == "file_upload"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"allowed_file_types", "schema_mapping", "max_file_size_mb"}
    properties = data["json_schema"]["properties"]
    allowed_types = properties["allowed_file_types"]["items"]["enum"]
    assert allowed_types == ["csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"]
    assert {"exe", "js", "html", "zip", "bat", "cmd", "ps1", "sh"}.isdisjoint(set(allowed_types))
    assert properties["allowed_file_types"]["uniqueItems"] is True
    assert properties["schema_mapping"]["required"] == ["title_field", "content_field", "city_id"]
    assert properties["schema_mapping"]["properties"]["city_id"]["default"] == "xian"
    assert properties["max_file_size_mb"]["minimum"] == 1
    assert properties["max_file_size_mb"]["maximum"] == 100
    assert data["validation"]["create_source_endpoint"] == "POST /api/v1/data-sources"
    assert data["validation"]["upload_endpoint"] == "POST /api/v1/uploads"
    assert data["validation"]["file_run_endpoint"] == "POST /api/v1/collection-jobs/{collection_job_id}/file-runs"
    assert data["validation"]["forbidden_file_types"] == ["exe", "js", "html", "zip", "bat", "cmd", "ps1", "sh"]
    assert data["validation"]["signature_scan_required"] is True
    assert data["validation"]["schema_required"] is True
    assert data["workflow_refs"] == ["import_uploaded_file"]

    prefix = _unique_name("AT297 document schema")
    blocked_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} blocked", "source_type": "file_upload", "policy": {"allowed_file_types": ["csv", "exe"], "schema": {"title_field": "title", "content_field": "content", "city_id": "xian"}}},
    )
    assert blocked_source.status_code == 422
    assert blocked_source.json()["error"]["code"] == "FILE_UPLOAD_TYPE_NOT_ALLOWED"

    valid_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "file_upload",
            "policy": {
                "allowed_file_types": allowed_types,
                "schema": {"title_field": "title", "content_field": "content", "city_id": "xian"},
                "max_file_size_mb": properties["max_file_size_mb"]["default"],
            },
        },
    )
    assert valid_source.status_code == 200, valid_source.text
    valid_data = valid_source.json()["data"]
    assert valid_data["source_type"] == "file_upload"
    assert valid_data["policy"]["allowed_file_types"] == allowed_types
    assert valid_data["policy"]["schema"]["city_id"] == "xian"
    assert valid_data["policy"]["max_file_size_mb"] == 50

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at297_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not document schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at297.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-297 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/document_file/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload


def test_s2_image_file_channel_schema_returns_processing_and_redaction_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/image_file/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "image_file"
    assert data["source_type"] == "media"
    assert data["adapter_source_type"] == "media"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"allowed_formats", "ocr_policy", "vlm_policy", "redaction_policy"}
    properties = data["json_schema"]["properties"]
    allowed_formats = properties["allowed_formats"]["items"]["enum"]
    assert allowed_formats == ["jpg", "jpeg", "png", "webp", "tiff", "heic"]
    assert {"exe", "zip", "svg", "html"}.isdisjoint(set(allowed_formats))
    assert properties["ocr_policy"]["properties"]["engine"]["default"] == "synthetic_ocr"
    assert properties["vlm_policy"]["properties"]["provider"]["default"] == "synthetic_deterministic_caption"
    assert properties["vlm_policy"]["properties"]["evidence_mode"]["enum"] == ["candidate_only"]
    assert properties["redaction_policy"]["properties"]["enabled"]["default"] is True
    assert properties["redaction_policy"]["properties"]["strategy"]["default"] == "mask_faces_and_text"
    assert data["validation"]["create_source_endpoint"] == "POST /api/v1/data-sources"
    assert data["validation"]["import_endpoint"] == "POST /api/v1/imports/media"
    assert data["validation"]["media_processing_endpoint"] == "POST /api/v1/media-processing-runs"
    assert data["validation"]["redaction_required"] is True
    assert data["validation"]["redaction_disabled_warning"]["code"] == "IMAGE_REDACTION_DISABLED_RISK"
    assert set(data["workflow_refs"]) == {"import_media_file", "process_image_media", "redact_image_media"}

    prefix = _unique_name("AT298 image schema")
    blocked_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} blocked", "source_type": "media", "policy": {"allowed_formats": ["png", "exe"]}},
    )
    assert blocked_source.status_code == 422
    assert blocked_source.json()["error"]["code"] == "MEDIA_FORMAT_NOT_ALLOWED"

    warning_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} warning",
            "source_type": "media",
            "policy": {
                "allowed_formats": ["png", "jpg"],
                "ocr_policy": {"enabled": True, "engine": "synthetic_ocr", "languages": ["zh-CN"], "store_text": True},
                "vlm_policy": {"enabled": True, "provider": "synthetic_deterministic_caption", "evidence_mode": "candidate_only"},
                "redaction_policy": {"enabled": False, "strategy": "mask_sensitive_text", "minors_policy": "review_required"},
                "max_file_size_mb": 20,
            },
        },
    )
    assert warning_source.status_code == 200, warning_source.text
    warning_policy = warning_source.json()["data"]["policy"]
    assert warning_policy["warnings"][0]["code"] == "IMAGE_REDACTION_DISABLED_RISK"

    valid_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "media",
            "policy": {
                "allowed_formats": properties["allowed_formats"]["default"],
                "ocr_policy": properties["ocr_policy"]["properties"] | {"enabled": True, "engine": "synthetic_ocr", "languages": ["zh-CN", "en"], "store_text": True},
                "vlm_policy": {"enabled": True, "provider": "synthetic_deterministic_caption", "evidence_mode": "candidate_only"},
                "redaction_policy": {"enabled": True, "strategy": "mask_faces_and_text", "minors_policy": "always_mask"},
                "max_file_size_mb": properties["max_file_size_mb"]["default"],
            },
        },
    )
    assert valid_source.status_code == 200, valid_source.text
    source_id = valid_source.json()["data"]["data_source_id"]
    assert valid_source.json()["data"]["policy"]["allowed_formats"] == ["jpg", "jpeg", "png", "webp"]
    assert valid_source.json()["data"]["policy"]["redaction_policy"]["enabled"] is True

    imported = client.post(
        "/api/v1/imports/media",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": f"{prefix} imported image 13800138000 minor name: Zhang",
            "content": "synthetic image text with phone 13800138000 and minor name: Zhang",
            "source_uri": "synthetic://xian/image-file/at298.png",
            "media_type": "image",
            "media_uri": "synthetic://xian/image-file/at298.png",
            "is_synthetic": True,
        },
    )
    assert imported.status_code == 200, imported.text
    imported_data = imported.json()["data"]
    assert imported_data["import_run"]["status"] == "completed"
    assert imported_data["collection_run"]["status"] == "completed"
    raw_record_id = imported_data["raw_records"][0]["raw_record_id"]

    with Session(engine) as db:
        media_asset = db.execute(select(models.MediaAsset).where(models.MediaAsset.raw_record_id == raw_record_id)).scalar_one()
        assert media_asset.media_type == "image"
        assert media_asset.payload["channel"] == "image_file"
        media_run = db.execute(select(models.MediaProcessingRun).where(models.MediaProcessingRun.media_asset_id == media_asset.id)).scalar_one()
        assert media_run.status == "completed"
        assert media_run.output["ocr"]["engine"] == "synthetic_ocr"
        assert media_run.output["vlm"]["provider"] == "synthetic_deterministic_caption"
        assert media_run.output["vlm"]["evidence_mode"] == "candidate_only"
        assert media_run.output["redaction"]["enabled"] is True
        assert "13800138000" not in json.dumps(media_run.output, ensure_ascii=False)
        assert "minor name" not in json.dumps(media_run.output, ensure_ascii=False).lower()
        assert media_run.output["blocked_claims"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == media_asset.id)).scalars())
        assert any(item.from_object_type == "raw_record" and item.from_object_id == raw_record_id for item in lineages)

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at298_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not image schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at298.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-298 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/image_file/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload
    assert "import.media.completed" in audit_payload


def test_s2_video_file_channel_schema_returns_keyframe_asr_ocr_vlm_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/video_file/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "video_file"
    assert data["source_type"] == "media"
    assert data["adapter_source_type"] == "media"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"allowed_formats", "keyframe_policy", "asr_policy", "ocr_policy", "vlm_policy", "large_video_policy"}
    properties = data["json_schema"]["properties"]
    allowed_formats = properties["allowed_formats"]["items"]["enum"]
    assert allowed_formats == ["mp4", "mov", "webm", "mkv"]
    assert {"exe", "zip", "html"}.isdisjoint(set(allowed_formats))
    assert properties["keyframe_policy"]["properties"]["strategy"]["default"] == "interval_seconds"
    assert properties["asr_policy"]["properties"]["engine"]["default"] == "synthetic_asr"
    assert properties["ocr_policy"]["properties"]["engine"]["default"] == "synthetic_ocr"
    assert properties["ocr_policy"]["properties"]["keyframe_only"]["default"] is True
    assert properties["vlm_policy"]["properties"]["provider"]["default"] == "synthetic_deterministic_caption"
    assert properties["vlm_policy"]["properties"]["evidence_mode"]["enum"] == ["candidate_only"]
    assert properties["large_video_policy"]["properties"]["threshold_mb"]["default"] == 512
    assert properties["large_video_policy"]["properties"]["oversize_action"]["default"] == "defer_chunked_processing"
    assert data["validation"]["create_source_endpoint"] == "POST /api/v1/data-sources"
    assert data["validation"]["import_endpoint"] == "POST /api/v1/imports/media"
    assert data["validation"]["media_processing_endpoint"] == "POST /api/v1/media-processing-runs"
    assert data["validation"]["large_video_policy_required"] is True
    assert data["validation"]["large_video_policy_missing_code"] == "VIDEO_LARGE_POLICY_REQUIRED"
    assert set(data["workflow_refs"]) == {"import_media_file", "extract_video_keyframes", "transcribe_video_asr", "process_video_ocr", "process_video_vlm"}

    defaults = {item["name"]: item.get("default") for item in data["ui_schema"]["fields"]}
    prefix = _unique_name("AT299 video schema")
    missing_large_policy = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} missing large policy",
            "source_type": "media",
            "policy": {
                "media_kind": "video_file",
                "allowed_formats": ["mp4"],
                "keyframe_policy": defaults["keyframe_policy"],
                "asr_policy": defaults["asr_policy"],
                "ocr_policy": defaults["ocr_policy"],
                "vlm_policy": defaults["vlm_policy"],
            },
        },
    )
    assert missing_large_policy.status_code == 422
    assert missing_large_policy.json()["error"]["code"] == "VIDEO_LARGE_POLICY_REQUIRED"

    blocked_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} blocked",
            "source_type": "media",
            "policy": {
                "media_kind": "video_file",
                "allowed_formats": ["mp4", "exe"],
                "large_video_policy": defaults["large_video_policy"],
            },
        },
    )
    assert blocked_source.status_code == 422
    assert blocked_source.json()["error"]["code"] == "VIDEO_FORMAT_NOT_ALLOWED"

    valid_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "media",
            "policy": {
                "media_kind": "video_file",
                "allowed_formats": defaults["allowed_formats"],
                "keyframe_policy": defaults["keyframe_policy"],
                "asr_policy": defaults["asr_policy"],
                "ocr_policy": defaults["ocr_policy"],
                "vlm_policy": defaults["vlm_policy"],
                "large_video_policy": defaults["large_video_policy"],
                "redaction_policy": defaults["redaction_policy"],
                "max_file_size_mb": defaults["max_file_size_mb"],
            },
        },
    )
    assert valid_source.status_code == 200, valid_source.text
    source_data = valid_source.json()["data"]
    source_id = source_data["data_source_id"]
    assert source_data["policy"]["media_kind"] == "video_file"
    assert source_data["policy"]["media_types"] == ["video"]
    assert source_data["policy"]["allowed_formats"] == ["mp4", "mov", "webm"]
    assert source_data["policy"]["large_video_policy"]["oversize_action"] == "defer_chunked_processing"

    imported = client.post(
        "/api/v1/imports/media",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": f"{prefix} imported video 13800138000 minor name: Zhang",
            "content": "synthetic video transcript with phone 13800138000 and minor name: Zhang",
            "source_uri": "synthetic://xian/video-file/at299.mp4",
            "media_type": "video",
            "media_uri": "synthetic://xian/video-file/at299.mp4",
            "is_synthetic": True,
        },
    )
    assert imported.status_code == 200, imported.text
    imported_data = imported.json()["data"]
    assert imported_data["import_run"]["status"] == "completed"
    assert imported_data["collection_run"]["status"] == "completed"
    raw_record_id = imported_data["raw_records"][0]["raw_record_id"]

    with Session(engine) as db:
        media_asset = db.execute(select(models.MediaAsset).where(models.MediaAsset.raw_record_id == raw_record_id)).scalar_one()
        assert media_asset.media_type == "video"
        assert media_asset.payload["channel"] == "video_file"
        media_run = db.execute(select(models.MediaProcessingRun).where(models.MediaProcessingRun.media_asset_id == media_asset.id)).scalar_one()
        assert media_run.status == "completed"
        assert media_run.processor == "s2_import_video_media_processor_v1"
        assert media_run.output["keyframes"]["strategy"] == "interval_seconds"
        assert media_run.output["keyframes"]["frames"]
        assert media_run.output["asr"]["engine"] == "synthetic_asr"
        assert media_run.output["ocr"]["engine"] == "synthetic_ocr"
        assert media_run.output["ocr"]["keyframe_only"] is True
        assert media_run.output["vlm"]["provider"] == "synthetic_deterministic_caption"
        assert media_run.output["vlm"]["evidence_mode"] == "candidate_only"
        assert media_run.output["large_video_policy"]["threshold_mb"] == 512
        assert "13800138000" not in json.dumps(media_run.output, ensure_ascii=False)
        assert "minor name" not in json.dumps(media_run.output, ensure_ascii=False).lower()
        assert media_run.output["blocked_claims"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == media_asset.id)).scalars())
        assert any(item.from_object_type == "raw_record" and item.from_object_id == raw_record_id for item in lineages)

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at299_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not video schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at299.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-299 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/video_file/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload
    assert "import.media.completed" in audit_payload


def test_s2_livestream_channel_schema_returns_segment_buffer_retention_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/livestream/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "livestream"
    assert data["source_type"] == "live_segment"
    assert data["adapter_source_type"] == "live_segment"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"stream_url", "stream_protocol", "segment_policy", "buffer_policy", "retention_policy"}
    properties = data["json_schema"]["properties"]
    assert properties["stream_url"]["x-accepted-schemes"] == ["https", "http", "rtmp", "synthetic"]
    assert properties["stream_protocol"]["enum"] == ["hls", "dash", "rtmp", "synthetic"]
    assert properties["segment_policy"]["properties"]["segment_seconds"]["default"] == 10
    assert properties["buffer_policy"]["properties"]["buffer_seconds"]["default"] == 60
    assert properties["retention_policy"]["properties"]["retention_days"]["default"] == 7
    assert data["validation"]["create_source_endpoint"] == "POST /api/v1/data-sources"
    assert data["validation"]["import_endpoint"] == "POST /api/v1/imports/media"
    assert data["validation"]["media_processing_endpoint"] == "POST /api/v1/live-segment-runs"
    assert data["validation"]["retention_policy_required"] is True
    assert data["validation"]["retention_policy_missing_code"] == "LIVE_RETENTION_POLICY_REQUIRED"
    assert set(data["workflow_refs"]) == {"ingest_livestream_segments", "buffer_livestream_window", "process_live_segment"}

    defaults = {item["name"]: item.get("default") for item in data["ui_schema"]["fields"]}
    prefix = _unique_name("AT300 live schema")
    missing_retention = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} missing retention",
            "source_type": "live_segment",
            "policy": {
                "stream_url": defaults["stream_url"],
                "stream_protocol": defaults["stream_protocol"],
                "segment_policy": defaults["segment_policy"],
                "buffer_policy": defaults["buffer_policy"],
            },
        },
    )
    assert missing_retention.status_code == 422
    assert missing_retention.json()["error"]["code"] == "LIVE_RETENTION_POLICY_REQUIRED"

    invalid_protocol = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} invalid protocol",
            "source_type": "live_segment",
            "policy": {
                "stream_url": defaults["stream_url"],
                "stream_protocol": "ftp",
                "retention_policy": defaults["retention_policy"],
            },
        },
    )
    assert invalid_protocol.status_code == 422
    assert invalid_protocol.json()["error"]["code"] == "LIVE_STREAM_PROTOCOL_UNSUPPORTED"

    valid_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "live_segment",
            "policy": {
                "stream_url": defaults["stream_url"],
                "stream_protocol": defaults["stream_protocol"],
                "segment_policy": defaults["segment_policy"],
                "buffer_policy": defaults["buffer_policy"],
                "retention_policy": defaults["retention_policy"],
                "redaction_policy": defaults["redaction_policy"],
            },
        },
    )
    assert valid_source.status_code == 200, valid_source.text
    source_data = valid_source.json()["data"]
    source_id = source_data["data_source_id"]
    assert source_data["source_type"] == "live_segment"
    assert source_data["policy"]["stream_protocol"] == "synthetic"
    assert source_data["policy"]["retention_policy"]["retention_days"] == 7

    imported = client.post(
        "/api/v1/imports/media",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": f"{prefix} segment 13800138000",
            "content": "synthetic livestream segment transcript with phone 13800138000",
            "source_uri": defaults["stream_url"],
            "media_type": "live_segment",
            "media_uri": f"{defaults['stream_url']}/segment-001.ts",
            "is_synthetic": True,
        },
    )
    assert imported.status_code == 200, imported.text
    imported_data = imported.json()["data"]
    assert imported_data["import_run"]["status"] == "completed"
    assert imported_data["collection_run"]["status"] == "completed"
    raw_record_id = imported_data["raw_records"][0]["raw_record_id"]

    with Session(engine) as db:
        media_asset = db.execute(select(models.MediaAsset).where(models.MediaAsset.raw_record_id == raw_record_id)).scalar_one()
        assert media_asset.media_type == "live_segment"
        assert media_asset.payload["channel"] == "livestream"
        media_run = db.execute(select(models.MediaProcessingRun).where(models.MediaProcessingRun.media_asset_id == media_asset.id)).scalar_one()
        assert media_run.status == "completed"
        assert media_run.processor == "s2_import_live_segment_processor_v1"
        assert media_run.output["live_segment"]["stream_protocol"] == "synthetic"
        assert media_run.output["live_segment"]["segment_policy"]["segment_seconds"] == 10
        assert media_run.output["live_segment"]["buffer_policy"]["buffer_seconds"] == 60
        assert media_run.output["live_segment"]["retention_policy"]["retention_days"] == 7
        assert media_run.output["live_segment"]["segments"]
        assert "13800138000" not in json.dumps(media_run.output, ensure_ascii=False)
        assert media_run.output["blocked_claims"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == media_asset.id)).scalars())
        assert any(item.from_object_type == "raw_record" and item.from_object_id == raw_record_id for item in lineages)

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at300_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not livestream schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at300.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-300 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/livestream/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload
    assert "import.media.completed" in audit_payload


def test_s2_audio_file_channel_schema_returns_asr_segmentation_language_contract() -> None:
    headers = _headers()
    response = client.get("/api/v1/collection-channels/audio_file/schema", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["channel"] == "audio_file"
    assert data["source_type"] == "media"
    assert data["adapter_source_type"] == "media"
    assert data["adapter_registered"] is True
    assert data["adapter_contract_status"] == "passed"
    assert data["status"] == "ready"
    assert data["schema_kind"] == "json_schema"
    assert set(data["required_fields"]) == {"allowed_formats", "asr_policy", "segmentation_policy", "language_policy"}
    properties = data["json_schema"]["properties"]
    allowed_formats = properties["allowed_formats"]["items"]["enum"]
    assert allowed_formats == ["mp3", "wav", "m4a", "aac", "flac"]
    assert {"exe", "zip", "html"}.isdisjoint(set(allowed_formats))
    assert properties["asr_policy"]["properties"]["engine"]["default"] == "synthetic_asr"
    assert properties["segmentation_policy"]["properties"]["mode"]["default"] == "fixed_window"
    assert properties["segmentation_policy"]["properties"]["segment_seconds"]["default"] == 30
    assert properties["language_policy"]["properties"]["primary_language"]["default"] == "zh-CN"
    assert properties["language_policy"]["properties"]["allowed_languages"]["items"]["enum"] == ["zh-CN", "en"]
    assert data["validation"]["create_source_endpoint"] == "POST /api/v1/data-sources"
    assert data["validation"]["import_endpoint"] == "POST /api/v1/imports/media"
    assert data["validation"]["unsupported_language_code"] == "AUDIO_LANGUAGE_UNSUPPORTED"
    assert data["validation"]["supported_languages"] == ["zh-CN", "en"]
    assert set(data["workflow_refs"]) == {"import_media_file", "segment_audio_file", "transcribe_audio_asr"}

    defaults = {item["name"]: item.get("default") for item in data["ui_schema"]["fields"]}
    prefix = _unique_name("AT301 audio schema")
    unsupported_language = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} unsupported language",
            "source_type": "media",
            "policy": {
                "media_kind": "audio_file",
                "allowed_formats": defaults["allowed_formats"],
                "asr_policy": defaults["asr_policy"],
                "segmentation_policy": defaults["segmentation_policy"],
                "language_policy": {"primary_language": "fr", "allowed_languages": ["fr"], "fallback_language": "fr"},
            },
        },
    )
    assert unsupported_language.status_code == 422
    assert unsupported_language.json()["error"]["code"] == "AUDIO_LANGUAGE_UNSUPPORTED"

    invalid_format = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} invalid format",
            "source_type": "media",
            "policy": {
                "media_kind": "audio_file",
                "allowed_formats": ["mp3", "exe"],
                "language_policy": defaults["language_policy"],
            },
        },
    )
    assert invalid_format.status_code == 422
    assert invalid_format.json()["error"]["code"] == "AUDIO_FORMAT_NOT_ALLOWED"

    valid_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} valid",
            "source_type": "media",
            "policy": {
                "media_kind": "audio_file",
                "allowed_formats": defaults["allowed_formats"],
                "asr_policy": defaults["asr_policy"],
                "segmentation_policy": defaults["segmentation_policy"],
                "language_policy": defaults["language_policy"],
                "redaction_policy": defaults["redaction_policy"],
                "max_file_size_mb": defaults["max_file_size_mb"],
            },
        },
    )
    assert valid_source.status_code == 200, valid_source.text
    source_data = valid_source.json()["data"]
    source_id = source_data["data_source_id"]
    assert source_data["policy"]["media_kind"] == "audio_file"
    assert source_data["policy"]["media_types"] == ["audio"]
    assert source_data["policy"]["language_policy"]["primary_language"] == "zh-CN"

    imported = client.post(
        "/api/v1/imports/media",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": f"{prefix} audio 13800138000",
            "content": "synthetic audio transcript with phone 13800138000",
            "source_uri": "synthetic://xian/audio-file/at301.mp3",
            "media_type": "audio",
            "media_uri": "synthetic://xian/audio-file/at301.mp3",
            "is_synthetic": True,
        },
    )
    assert imported.status_code == 200, imported.text
    imported_data = imported.json()["data"]
    assert imported_data["import_run"]["status"] == "completed"
    assert imported_data["collection_run"]["status"] == "completed"
    raw_record_id = imported_data["raw_records"][0]["raw_record_id"]

    with Session(engine) as db:
        media_asset = db.execute(select(models.MediaAsset).where(models.MediaAsset.raw_record_id == raw_record_id)).scalar_one()
        assert media_asset.media_type == "audio"
        assert media_asset.payload["channel"] == "audio_file"
        media_run = db.execute(select(models.MediaProcessingRun).where(models.MediaProcessingRun.media_asset_id == media_asset.id)).scalar_one()
        assert media_run.status == "completed"
        assert media_run.processor == "s2_import_audio_media_processor_v1"
        assert media_run.output["asr"]["engine"] == "synthetic_asr"
        assert media_run.output["asr"]["language"] == "zh-CN"
        assert media_run.output["audio"]["segmentation_policy"]["segment_seconds"] == 30
        assert media_run.output["audio"]["language_policy"]["allowed_languages"] == ["zh-CN", "en"]
        assert media_run.output["audio"]["segments"]
        assert "13800138000" not in json.dumps(media_run.output, ensure_ascii=False)
        assert media_run.output["blocked_claims"]
        lineages = list(db.execute(select(models.LineageEdge).where(models.LineageEdge.to_object_id == media_asset.id)).scalars())
        assert any(item.from_object_type == "raw_record" and item.from_object_id == raw_record_id for item in lineages)

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at301_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not audio schema.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at301.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-301 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/audio_file/schema", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.schema_read" in audit_payload
    assert "import.media.completed" in audit_payload


def test_s2_channel_error_code_mapping_returns_readable_channel_errors_and_unknown_warning() -> None:
    headers = _headers()
    response = client.get(
        "/api/v1/collection-channels/error-codes",
        headers=headers,
        params={"channel": "audio_file", "error_code": "AUDIO_LANGUAGE_UNSUPPORTED"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["service"] == "map_channel_error_codes"
    assert data["status"] == "ready"
    assert data["requested"] == {"channel": "audio_file", "error_code": "AUDIO_LANGUAGE_UNSUPPORTED"}
    assert data["summary"]["channel_count"] >= 11
    assert data["summary"]["mapping_count"] >= 1
    assert data["summary"]["unknown_count"] == 0
    assert data["warnings"] == []
    assert len(data["results"]) == 1
    audio_mapping = data["results"][0]
    assert audio_mapping["channel"] == "audio_file"
    assert audio_mapping["error_code"] == "AUDIO_LANGUAGE_UNSUPPORTED"
    assert audio_mapping["known"] is True
    assert audio_mapping["classification"] == "validation"
    assert audio_mapping["severity"] == "warning"
    assert audio_mapping["retryable"] is False
    assert "Audio language" in audio_mapping["label"]
    assert audio_mapping["run_detail_hint"]
    assert audio_mapping["source"] == "map_channel_error_codes"

    official_policy = client.get(
        "/api/v1/collection-channels/error-codes",
        headers=headers,
        params={"channel": "official_api", "error_code": "official_api_key_missing"},
    )
    assert official_policy.status_code == 200, official_policy.text
    official_mapping = official_policy.json()["data"]["results"][0]
    assert official_mapping["known"] is True
    assert official_mapping["classification"] == "auth"
    assert official_mapping["severity"] == "error"
    assert "secret_ref" in official_mapping["remediation"]

    all_response = client.get("/api/v1/collection-channels/error-codes", headers=headers)
    assert all_response.status_code == 200, all_response.text
    all_data = all_response.json()["data"]
    channels = {item["channel"]: item for item in all_data["channels"]}
    assert {"web_page", "official_api", "rss", "document_file", "image_file", "video_file", "livestream", "audio_file", "webhook", "database", "object_storage"}.issubset(set(channels))
    assert any(item["error_code"] == "OFFICIAL_API_RATE_LIMITED" for item in channels["official_api"]["mappings"])
    assert any(item["error_code"] == "VIDEO_LARGE_POLICY_REQUIRED" for item in channels["video_file"]["mappings"])
    assert channels["audio_file"]["fallback"]["classification"] == "unknown"
    assert channels["audio_file"]["fallback"]["warning_code"] == "CHANNEL_ERROR_CODE_UNMAPPED"

    unknown = client.get(
        "/api/v1/collection-channels/error-codes",
        headers=headers,
        params={"channel": "livestream", "error_code": "LIVE_VENDOR_EDGE_FAILURE"},
    )
    assert unknown.status_code == 200, unknown.text
    unknown_data = unknown.json()["data"]
    assert unknown_data["summary"]["unknown_count"] == 1
    assert unknown_data["warnings"][0]["code"] == "CHANNEL_ERROR_CODE_UNMAPPED"
    assert unknown_data["results"][0]["known"] is False
    assert unknown_data["results"][0]["classification"] == "unknown"
    assert unknown_data["results"][0]["severity"] == "warning"
    assert unknown_data["results"][0]["run_detail_hint"].startswith("Unmapped livestream error")

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at302_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not channel error codes.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at302.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-302 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/error-codes", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.error_codes_mapped" in audit_payload
    assert "AUDIO_LANGUAGE_UNSUPPORTED" in audit_payload
    assert "CHANNEL_ERROR_CODE_UNMAPPED" in audit_payload


def test_s2_once_collection_job_requires_published_source_and_persists_scope() -> None:
    headers = _headers()
    prefix = _unique_name("S2 once collection")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    unpublished = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={
            "data_source_id": source_id,
            "name": f"{prefix} unpublished once",
            "schedule": "once",
            "payload": {"query": {"district": "雁塔区", "topic": "public service"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}},
        },
    )
    assert unpublished.status_code == 409
    assert unpublished.json()["error"]["code"] == "DATA_SOURCE_UNPUBLISHED"

    auth = client.put(f"/api/v1/data-sources/{source_id}/auth", headers=headers, json={"auth_type": "api_key", "secret_ref": "vault://s2/once-official", "header_name": "X-API-Key"})
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-056 once job compliance"))
    assert compliance.status_code == 200, compliance.text
    version = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-056 once job publish"})
    assert version.status_code == 200, version.text
    version_data = version.json()["data"]

    missing_query = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} missing query", "schedule": "once", "payload": {"window": {"from": "2026-05-01", "to": "2026-05-09"}}},
    )
    assert missing_query.status_code == 422
    assert missing_query.json()["error"]["code"] == "COLLECTION_JOB_QUERY_REQUIRED"

    missing_window = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} missing window", "schedule": "once", "payload": {"query": {"district": "雁塔区"}}},
    )
    assert missing_window.status_code == 422
    assert missing_window.json()["error"]["code"] == "COLLECTION_JOB_WINDOW_REQUIRED"

    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={
            "data_source_id": source_id,
            "name": f"{prefix} once job",
            "schedule": "once",
            "payload": {
                "query": {"district": "雁塔区", "topic": "public service"},
                "window": {"from": "2026-05-01", "to": "2026-05-09"},
            },
        },
    )
    assert job.status_code == 200, job.text
    job_data = job.json()["data"]
    assert job_data["schedule"] == "once"
    assert job_data["status"] == "active"
    assert job_data["payload"]["job_kind"] == "once"
    assert job_data["payload"]["query"]["district"] == "雁塔区"
    assert job_data["payload"]["window"]["to"] == "2026-05-09"
    assert job_data["payload"]["data_source_version"] == version_data["version"]
    assert job_data["payload"]["data_source_version_id"] == version_data["data_source_version_id"]
    assert job_data["payload"]["data_source_config_hash"] == version_data["config_hash"]

    disabled = client.patch(f"/api/v1/data-sources/{source_id}/status", headers=headers, json={"status": "disabled", "reason": "AT-056 disabled source gate"})
    assert disabled.status_code == 200, disabled.text
    disabled_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} disabled once", "schedule": "once", "payload": {"query": {}, "window": {}}})
    assert disabled_job.status_code == 409
    assert disabled_job.json()["error"]["code"] == "DATA_SOURCE_DISABLED"


def test_s2_cron_collection_job_validates_frequency_and_registers_schedule() -> None:
    headers = _headers()
    prefix = _unique_name("S2 cron collection")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    payload = {"query": {"district": "yanta", "topic": "public service"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}}

    invalid_cron = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} invalid cron", "schedule": "cron:* * *", "payload": payload},
    )
    assert invalid_cron.status_code == 422
    assert invalid_cron.json()["error"]["code"] == "COLLECTION_CRON_INVALID"

    too_frequent = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} too frequent", "schedule": "cron:* * * * *", "payload": payload},
    )
    assert too_frequent.status_code == 422
    assert too_frequent.json()["error"]["code"] == "COLLECTION_CRON_TOO_FREQUENT"

    wraparound_too_frequent = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} wraparound frequent", "schedule": "cron:0,59 * * * *", "payload": payload},
    )
    assert wraparound_too_frequent.status_code == 422
    assert wraparound_too_frequent.json()["error"]["code"] == "COLLECTION_CRON_TOO_FREQUENT"

    unpublished = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} unpublished cron", "schedule": "cron:*/15 * * * *", "payload": payload},
    )
    assert unpublished.status_code == 409
    assert unpublished.json()["error"]["code"] == "DATA_SOURCE_UNPUBLISHED"

    auth = client.put(f"/api/v1/data-sources/{source_id}/auth", headers=headers, json={"auth_type": "api_key", "secret_ref": "vault://s2/cron-official", "header_name": "X-API-Key"})
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-057 cron job compliance"))
    assert compliance.status_code == 200, compliance.text
    version = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-057 cron job publish"})
    assert version.status_code == 200, version.text
    version_data = version.json()["data"]

    missing_query = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} missing query", "schedule": "cron:*/15 * * * *", "payload": {"window": payload["window"]}},
    )
    assert missing_query.status_code == 422
    assert missing_query.json()["error"]["code"] == "COLLECTION_JOB_QUERY_REQUIRED"

    missing_window = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} missing window", "schedule": "cron:*/15 * * * *", "payload": {"query": payload["query"]}},
    )
    assert missing_window.status_code == 422
    assert missing_window.json()["error"]["code"] == "COLLECTION_JOB_WINDOW_REQUIRED"

    started_at = time.perf_counter()
    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} cron job", "schedule": "cron:*/15 * * * *", "payload": payload},
    )
    elapsed = time.perf_counter() - started_at
    assert job.status_code == 200, job.text
    assert elapsed < 1.0
    job_data = job.json()["data"]
    job_payload = job_data["payload"]
    assert job_data["schedule"] == "cron:*/15 * * * *"
    assert job_data["status"] == "active"
    assert job_payload["job_kind"] == "cron"
    assert job_payload["cron_expression"] == "*/15 * * * *"
    assert job_payload["query"]["district"] == "yanta"
    assert job_payload["window"]["to"] == "2026-05-09"
    assert job_payload["data_source_version"] == version_data["version"]
    assert job_payload["data_source_version_id"] == version_data["data_source_version_id"]
    registration = job_payload["scheduler_registration"]
    assert registration["status"] == "registered"
    assert registration["scheduler"] == "in_process_schedule_registry_v1"
    assert registration["interval_minutes"] == 15
    assert registration["registered_at"]
    assert registration["trace_id"] == job.json()["trace_id"]


def test_s2_collection_job_list_filters_pagination_and_tenant_scope() -> None:
    headers = _headers()
    prefix = _unique_name("S2 job list")
    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    admin_id = me.json()["data"]["user_id"]

    active_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} active source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}},
    )
    assert active_source.status_code == 200, active_source.text
    active_source_id = active_source.json()["data"]["data_source_id"]
    blocked_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} blocked source", "source_type": "public_web", "policy": {"access_mode": "cookie_pool"}},
    )
    assert blocked_source.status_code == 200, blocked_source.text
    blocked_source_id = blocked_source.json()["data"]["data_source_id"]

    created_ids = []
    for index in range(3):
        response = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": active_source_id, "name": f"{prefix} active job {index}"})
        assert response.status_code == 200, response.text
        created_ids.append(response.json()["data"]["collection_job_id"])
        assert response.json()["data"]["created_by_id"] == admin_id
    blocked_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": blocked_source_id, "name": f"{prefix} blocked job"})
    assert blocked_job.status_code == 200, blocked_job.text
    blocked_job_id = blocked_job.json()["data"]["collection_job_id"]

    other_tenant_id = f"tenant-{uuid4().hex[:8]}"
    foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
    foreign_source_id = f"DS-{uuid4().hex[:20]}"
    with Session(engine) as db:
        db.add(models.Tenant(id=other_tenant_id, name="Foreign tenant", status="active", payload={}))
        db.commit()
        db.add(models.User(id=f"USR-{uuid4().hex[:20]}", tenant_id=other_tenant_id, username=f"foreign-{uuid4().hex[:8]}", display_name="Foreign User", password_hash="unused", status="active", payload={}))
        db.add(models.DataSource(id=foreign_source_id, tenant_id=other_tenant_id, name=f"{prefix} foreign source", source_type="synthetic", status="active", is_synthetic=True, policy={}, payload={}))
        db.commit()
        db.add(
            models.CollectionJob(
                id=foreign_job_id,
                tenant_id=other_tenant_id,
                data_source_id=foreign_source_id,
                name=f"{prefix} foreign job",
                status="active",
                schedule=None,
                created_by_id=None,
                payload={},
            )
        )
        db.commit()

    page_one = client.get("/api/v1/collection-jobs", headers=headers, params={"data_source_id": active_source_id, "page": 1, "page_size": 2})
    assert page_one.status_code == 200, page_one.text
    page_one_payload = page_one.json()
    assert len(page_one_payload["data"]) == 2
    assert page_one_payload["meta"]["pagination"] == {"page": 1, "page_size": 2, "total": 3}
    assert {item["data_source_id"] for item in page_one_payload["data"]} == {active_source_id}
    assert all(item["tenant_id"] == me.json()["data"]["tenant_id"] for item in page_one_payload["data"])
    assert foreign_job_id not in {item["collection_job_id"] for item in page_one_payload["data"]}

    page_two = client.get("/api/v1/collection-jobs", headers=headers, params={"data_source_id": active_source_id, "page": 2, "page_size": 2})
    assert page_two.status_code == 200, page_two.text
    assert len(page_two.json()["data"]) == 1

    active_filter = client.get("/api/v1/collection-jobs", headers=headers, params={"status": "active", "data_source_id": active_source_id})
    assert active_filter.status_code == 200, active_filter.text
    assert {item["collection_job_id"] for item in active_filter.json()["data"]} == set(created_ids)

    blocked_filter = client.get("/api/v1/collection-jobs", headers=headers, params={"status": "blocked", "data_source_id": blocked_source_id})
    assert blocked_filter.status_code == 200, blocked_filter.text
    assert [item["collection_job_id"] for item in blocked_filter.json()["data"]] == [blocked_job_id]

    creator_filter = client.get("/api/v1/collection-jobs", headers=headers, params={"created_by_id": admin_id, "data_source_id": active_source_id})
    assert creator_filter.status_code == 200, creator_filter.text
    assert creator_filter.json()["meta"]["pagination"]["total"] == 3
    assert all(item["created_by_id"] == admin_id for item in creator_filter.json()["data"])

    invalid_status = client.get("/api/v1/collection-jobs", headers=headers, params={"status": "not-a-status"})
    assert invalid_status.status_code == 422
    assert invalid_status.json()["error"]["code"] == "COLLECTION_JOB_STATUS_INVALID"


def test_s2_collection_job_detail_returns_config_version_and_recent_runs() -> None:
    headers = _headers()
    prefix = _unique_name("S2 job detail")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    auth = client.put(f"/api/v1/data-sources/{source_id}/auth", headers=headers, json={"auth_type": "api_key", "secret_ref": "vault://s2/detail-official", "header_name": "X-API-Key"})
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-059 job detail compliance"))
    assert compliance.status_code == 200, compliance.text
    version = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-059 job detail publish"})
    assert version.status_code == 200, version.text

    job = client.post(
        "/api/v1/collection-jobs",
        headers=headers,
        json={
            "data_source_id": source_id,
            "name": f"{prefix} cron job",
            "schedule": "cron:*/15 * * * *",
            "payload": {"query": {"district": "yanta"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}},
        },
    )
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    first_run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert first_run.status_code == 200, first_run.text
    _complete_collection_run_for_test(first_run.json()["data"]["collection_run_id"])
    second_run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert second_run.status_code == 200, second_run.text
    _complete_collection_run_for_test(second_run.json()["data"]["collection_run_id"])

    detail = client.get(f"/api/v1/collection-jobs/{job_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["collection_job_id"] == job_id
    assert detail_data["source"]["data_source_id"] == source_id
    assert detail_data["config"]["schedule"] == "cron:*/15 * * * *"
    assert detail_data["config"]["query"]["district"] == "yanta"
    assert detail_data["version_pin"]["data_source_version_id"] == version.json()["data"]["data_source_version_id"]
    assert detail_data["latest_runs"][0]["collection_run_id"] == second_run.json()["data"]["collection_run_id"]
    assert detail_data["latest_runs"][1]["collection_run_id"] == first_run.json()["data"]["collection_run_id"]
    assert detail_data["run_summary"]["total_runs"] == 2
    assert detail_data["run_summary"]["success_count"] == 2
    assert detail_data["page_state"] == "ready"

    missing = client.get("/api/v1/collection-jobs/CJOB-not-found", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    other_tenant_id = f"tenant-{uuid4().hex[:8]}"
    foreign_source_id = f"DS-{uuid4().hex[:20]}"
    foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
    with Session(engine) as db:
        db.add(models.Tenant(id=other_tenant_id, name="Foreign tenant detail", status="active", payload={}))
        db.commit()
        db.add(models.DataSource(id=foreign_source_id, tenant_id=other_tenant_id, name=f"{prefix} foreign source", source_type="synthetic", status="active", is_synthetic=True, policy={}, payload={}))
        db.commit()
        db.add(models.CollectionJob(id=foreign_job_id, tenant_id=other_tenant_id, data_source_id=foreign_source_id, name=f"{prefix} foreign job", status="active", schedule=None, payload={}))
        db.commit()
    foreign_detail = client.get(f"/api/v1/collection-jobs/{foreign_job_id}", headers=headers)
    assert foreign_detail.status_code == 404
    assert foreign_detail.json()["error"]["code"] == "NOT_FOUND"


def test_s2_collection_rate_limit_delays_runs_and_exposes_stats() -> None:
    headers = _headers()
    prefix = _unique_name("S2 rate limit")
    lock_sql = str(data_sources._rate_limit_lock_statement("DS-lock-test").compile(dialect=postgresql.dialect())).upper()
    assert "FOR UPDATE" in lock_sql

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "synthetic",
            "policy": {
                "access_mode": "test_fixture",
                "is_synthetic": True,
                "rate_limit": {"max_runs": 1, "window_seconds": 60, "delay_seconds": 60},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    first_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} first"})
    second_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} second"})
    assert first_job.status_code == 200, first_job.text
    assert second_job.status_code == 200, second_job.text

    first = client.post(f"/api/v1/collection-jobs/{first_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "pending"
    assert first.json()["data"]["payload"]["rate_limit"]["allowed"] is True

    delayed = client.post(f"/api/v1/collection-jobs/{second_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert delayed.status_code == 200, delayed.text
    delayed_data = delayed.json()["data"]
    assert delayed_data["status"] == "delayed"
    assert delayed_data["error_code"] == "SOURCE_RATE_LIMITED"
    assert delayed_data["payload"]["rate_limit"]["allowed"] is False
    assert delayed_data["payload"]["rate_limit"]["next_allowed_at"]
    delayed_run_id = delayed_data["collection_run_id"]

    stats = client.get(f"/api/v1/data-sources/{source_id}/rate-limit", headers=headers)
    assert stats.status_code == 200, stats.text
    stats_data = stats.json()["data"]
    assert stats_data["status"] == "limited"
    assert stats_data["config"]["max_runs"] == 1
    assert stats_data["state"]["used"] == 1
    assert stats_data["state"]["delayed_count"] == 1
    assert stats_data["state"]["last_delayed_run_id"] == delayed_run_id

    delayed_runs = client.get("/api/v1/collection-runs", headers=headers, params={"status": "delayed", "data_source_id": source_id})
    assert delayed_runs.status_code == 200, delayed_runs.text
    assert [item["collection_run_id"] for item in delayed_runs.json()["data"]] == [delayed_run_id]

    with Session(engine) as db:
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == delayed_run_id)).scalars())
        assert any(event.event_type == "rate_limit_delayed" and event.status == "delayed" for event in events)
        retry = db.execute(
            select(models.OpsRetryQueue).where(
                models.OpsRetryQueue.target_type == "collection_run",
                models.OpsRetryQueue.target_id == delayed_run_id,
            )
        ).scalar_one()
        assert retry.status == "delayed"
        assert retry.payload["error_code"] == "SOURCE_RATE_LIMITED"
        policy_rows = list(db.execute(select(models.SourcePolicy).where(models.SourcePolicy.data_source_id == source_id)).scalars())
        assert any(row.status == "rate_limited" and row.payload["rate_limit"]["collection_run_id"] == delayed_run_id for row in policy_rows)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.delayed" in audit_payload
    assert "SOURCE_RATE_LIMITED" in audit_payload

    invalid_policy_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} invalid policy",
            "source_type": "synthetic",
            "policy": {
                "access_mode": "test_fixture",
                "rate_limit": {"max_runs": 2, "window_seconds": 60, "scope": "tenant", "mode": "token_bucket"},
            },
        },
    )
    assert invalid_policy_source.status_code == 200, invalid_policy_source.text
    invalid_stats = client.get(f"/api/v1/data-sources/{invalid_policy_source.json()['data']['data_source_id']}/rate-limit", headers=headers)
    assert invalid_stats.status_code == 200, invalid_stats.text
    assert invalid_stats.json()["data"]["config"]["scope"] == "data_source"
    assert invalid_stats.json()["data"]["config"]["mode"] == "sliding_window"


def test_s2_channel_rate_limit_delays_only_the_limited_channel() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel rate limit")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "synthetic",
            "policy": {
                "access_mode": "test_fixture",
                "is_synthetic": True,
                "channel_rate_limits": {
                    "web_page": {"max_runs": 1, "window_seconds": 60, "delay_seconds": 60},
                    "rss": {"max_runs": 1, "window_seconds": 60, "delay_seconds": 60},
                },
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    web_first = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} web first", "payload": {"collection_channel": "web_page"}})
    web_second = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} web second", "payload": {"collection_channel": "web_page"}})
    rss_first = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} rss first", "payload": {"collection_channel": "rss"}})
    assert web_first.status_code == 200, web_first.text
    assert web_second.status_code == 200, web_second.text
    assert rss_first.status_code == 200, rss_first.text

    first = client.post(f"/api/v1/collection-jobs/{web_first.json()['data']['collection_job_id']}/runs", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "pending"
    assert first.json()["data"]["payload"]["rate_limit"]["channel"] == "web_page"
    assert first.json()["data"]["payload"]["rate_limit"]["config"]["scope"] == "channel"

    delayed = client.post(f"/api/v1/collection-jobs/{web_second.json()['data']['collection_job_id']}/runs", headers=headers)
    assert delayed.status_code == 200, delayed.text
    delayed_data = delayed.json()["data"]
    assert delayed_data["status"] == "delayed"
    assert delayed_data["error_code"] == "CHANNEL_RATE_LIMITED"
    assert delayed_data["payload"]["rate_limit"]["channel"] == "web_page"
    assert delayed_data["payload"]["rate_limit"]["allowed"] is False

    rss = client.post(f"/api/v1/collection-jobs/{rss_first.json()['data']['collection_job_id']}/runs", headers=headers)
    assert rss.status_code == 200, rss.text
    rss_data = rss.json()["data"]
    assert rss_data["status"] == "pending"
    assert rss_data["payload"]["rate_limit"]["channel"] == "rss"
    assert rss_data["payload"]["rate_limit"]["allowed"] is True

    web_stats = client.get(f"/api/v1/data-sources/{source_id}/rate-limit", headers=headers, params={"channel": "web_page"})
    rss_stats = client.get(f"/api/v1/data-sources/{source_id}/rate-limit", headers=headers, params={"channel": "rss"})
    assert web_stats.status_code == 200, web_stats.text
    assert rss_stats.status_code == 200, rss_stats.text
    web_stats_data = web_stats.json()["data"]
    rss_stats_data = rss_stats.json()["data"]
    assert web_stats_data["channel"] == "web_page"
    assert web_stats_data["status"] == "limited"
    assert web_stats_data["state"]["used"] == 1
    assert web_stats_data["state"]["delayed_count"] == 1
    assert rss_stats_data["channel"] == "rss"
    assert rss_stats_data["status"] == "limited"
    assert rss_stats_data["state"]["used"] == 1
    assert rss_stats_data["state"]["delayed_count"] == 0
    assert web_stats_data["channel_states"]["web_page"]["delayed_count"] == 1
    assert web_stats_data["channel_states"]["rss"]["used"] == 1

    with Session(engine) as db:
        source = db.get(models.DataSource, source_id)
        assert source is not None
        channel_state = source.policy["channel_rate_limit_state"]
        assert channel_state["web_page"]["used"] == 1
        assert channel_state["web_page"]["last_delayed_run_id"] == delayed_data["collection_run_id"]
        assert channel_state["rss"]["used"] == 1
        assert "last_delayed_run_id" not in channel_state["rss"]
        retry = db.execute(select(models.OpsRetryQueue).where(models.OpsRetryQueue.target_id == delayed_data["collection_run_id"])).scalar_one()
        assert retry.payload["error_code"] == "CHANNEL_RATE_LIMITED"
        assert retry.payload["rate_limit"]["channel"] == "web_page"
        policy_rows = list(db.execute(select(models.SourcePolicy).where(models.SourcePolicy.data_source_id == source_id)).scalars())
        assert any(row.reason == "CHANNEL_RATE_LIMITED" and row.payload["rate_limit"]["channel"] == "web_page" for row in policy_rows)

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.delayed" in audit_payload
    assert "CHANNEL_RATE_LIMITED" in audit_payload


def test_s2_channel_rate_limit_preserves_source_level_cap_and_filters_evidence() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel source cap")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "synthetic",
            "policy": {
                "access_mode": "test_fixture",
                "is_synthetic": True,
                "rate_limit": {"max_runs": 1, "window_seconds": 60, "delay_seconds": 60},
                "channel_rate_limits": {
                    "web_page": {"max_runs": 5, "window_seconds": 60, "delay_seconds": 60},
                    "rss": {"max_runs": 5, "window_seconds": 60, "delay_seconds": 60},
                },
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    web_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} web", "payload": {"collection_channel": "web_page"}})
    rss_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} rss", "payload": {"collection_channel": "rss"}})
    assert web_job.status_code == 200, web_job.text
    assert rss_job.status_code == 200, rss_job.text

    web_run = client.post(f"/api/v1/collection-jobs/{web_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert web_run.status_code == 200, web_run.text
    assert web_run.json()["data"]["status"] == "pending"
    assert web_run.json()["data"]["payload"]["rate_limit"]["channel"] == "web_page"
    assert web_run.json()["data"]["payload"]["rate_limit"]["source_rate_limit"]["config"]["scope"] == "data_source"

    rss_run = client.post(f"/api/v1/collection-jobs/{rss_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert rss_run.status_code == 200, rss_run.text
    rss_data = rss_run.json()["data"]
    assert rss_data["status"] == "delayed"
    assert rss_data["error_code"] == "SOURCE_RATE_LIMITED"
    assert rss_data["payload"]["rate_limit"]["config"]["scope"] == "data_source"
    assert rss_data["payload"]["rate_limit"]["channel_context"] == "rss"

    rss_stats = client.get(f"/api/v1/data-sources/{source_id}/rate-limit", headers=headers, params={"channel": "rss"})
    assert rss_stats.status_code == 200, rss_stats.text
    rss_stats_data = rss_stats.json()["data"]
    assert rss_stats_data["channel"] == "rss"
    assert rss_stats_data["state"]["delayed_count"] == 0
    assert rss_stats_data["recent_delayed_runs"] == []
    assert rss_stats_data.get("source_policy") is None

    source_stats = client.get(f"/api/v1/data-sources/{source_id}/rate-limit", headers=headers)
    assert source_stats.status_code == 200, source_stats.text
    assert source_stats.json()["data"]["state"]["delayed_count"] == 1


def test_s2_channel_replay_from_checkpoint_schedules_resume_without_duplicate_raw() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel replay")
    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "web_page"}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"collection_channel": "web_page"}})
    assert job_response.status_code == 200, job_response.text
    job_id = job_response.json()["data"]["collection_job_id"]
    run_response = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    original_run_id = run_response.json()["data"]["collection_run_id"]
    raw_response = client.post(
        "/api/v1/raw-records/batches",
        headers=headers,
        json={
            "data_source_id": source_id,
            "collection_run_id": original_run_id,
            "records": [{"title": f"{prefix} raw", "content": "AT-304 checkpoint raw content", "external_id": "at304-checkpoint-1", "is_synthetic": True}],
            "response_limit": 5,
            "reason": "AT-304 seed raw before failed checkpoint replay.",
        },
    )
    assert raw_response.status_code == 201, raw_response.text
    raw_id = raw_response.json()["data"]["raw_records"][0]["raw_record_id"]
    checkpoint = {
        "checkpoint_id": f"chk-{uuid4().hex[:12]}",
        "channel": "web_page",
        "resume_from_step": "fetch",
        "last_raw_record_id": raw_id,
        "last_raw_content_hash": raw_response.json()["data"]["raw_records"][0]["content_hash"],
        "raw_record_count": 1,
    }
    with Session(engine) as db:
        original = db.get(models.CollectionRun, original_run_id)
        assert original is not None
        original.status = "failed"
        original.error_code = "PUBLIC_WEB_TIMEOUT"
        original.error_message = "Synthetic checkpoint failure."
        original.payload = {**(original.payload or {}), "collection_channel": "web_page", "channel_checkpoint": checkpoint, "workflow_status": "failed"}
        db.commit()

    replay = client.post(
        f"/api/v1/collection-runs/{original_run_id}/channel-replay",
        headers=headers,
        json={"reason": "AT-304 replay from channel checkpoint."},
    )
    assert replay.status_code == 200, replay.text
    data = replay.json()["data"]
    assert data["status"] == "pending"
    assert data["payload"]["replay_strategy"] == "channel_checkpoint"
    assert data["payload"]["replay_of"] == original_run_id
    assert data["payload"]["collection_channel"] == "web_page"
    assert data["payload"]["channel_checkpoint"]["checkpoint_id"] == checkpoint["checkpoint_id"]
    assert data["payload"]["raw_replay_guard"]["skip_existing_raw"] is True
    assert data["payload"]["raw_replay_guard"]["last_raw_record_id"] == raw_id

    with Session(engine) as db:
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.data_source_id == source_id)).scalar_one()
        assert raw_count == 1
        replay_run = db.get(models.CollectionRun, data["collection_run_id"])
        assert replay_run is not None
        workflow_id = replay_run.payload["workflow_run_id"]
        workflow = db.get(models.WorkflowRun, workflow_id)
        assert workflow is not None
        events = list(db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == replay_run.id)).scalars())
        assert any(event.event_type == "channel_replay_scheduled" and event.payload["checkpoint_id"] == checkpoint["checkpoint_id"] for event in events)
        original = db.get(models.CollectionRun, original_run_id)
        assert original.payload["last_channel_replay_run_id"] == replay_run.id
        assert original.payload["last_channel_replay_status"] == "pending"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.channel_replay" in audit_payload
    assert checkpoint["checkpoint_id"] in audit_payload


def test_s2_channel_replay_missing_checkpoint_returns_409() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel replay missing")
    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job_response = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job", "payload": {"collection_channel": "web_page"}})
    assert job_response.status_code == 200, job_response.text
    run_response = client.post(f"/api/v1/collection-jobs/{job_response.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_response.status_code == 200, run_response.text
    run_id = run_response.json()["data"]["collection_run_id"]
    with Session(engine) as db:
        run = db.get(models.CollectionRun, run_id)
        assert run is not None
        run.status = "failed"
        run.error_code = "PUBLIC_WEB_TIMEOUT"
        run.payload = {**(run.payload or {}), "collection_channel": "web_page", "workflow_status": "failed"}
        db.commit()

    replay = client.post(f"/api/v1/collection-runs/{run_id}/channel-replay", headers=headers, json={"reason": "missing checkpoint"})
    assert replay.status_code == 409, replay.text
    assert replay.json()["error"]["code"] == "CHANNEL_CHECKPOINT_MISSING"


def test_s2_channel_quality_metrics_returns_channel_specific_metrics_and_404() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel quality metrics")
    web_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} web", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "web_page"}},
    )
    rss_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} rss", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "rss"}},
    )
    no_job_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} object storage no job", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "object_storage"}},
    )
    assert web_source.status_code == 200, web_source.text
    assert rss_source.status_code == 200, rss_source.text
    assert no_job_source.status_code == 200, no_job_source.text
    web_source_id = web_source.json()["data"]["data_source_id"]
    rss_source_id = rss_source.json()["data"]["data_source_id"]

    def seed_run(source_id: str, channel: str, label: str, content: str) -> tuple[str, str]:
        job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} {label}", "payload": {"collection_channel": channel}})
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
        assert run.status_code == 200, run.text
        run_id = run.json()["data"]["collection_run_id"]
        raw = client.post(
            "/api/v1/raw-records/batches",
            headers=headers,
            json={
                "data_source_id": source_id,
                "collection_run_id": run_id,
                "complete_run": True,
                "records": [{"title": f"{label} title", "content": content, "external_id": f"{label}-{uuid4().hex[:8]}", "is_synthetic": True}],
                "response_limit": 5,
                "reason": f"AT-305 seed {label}",
            },
        )
        assert raw.status_code == 201, raw.text
        return run_id, raw.json()["data"]["raw_records"][0]["raw_record_id"]

    web_run_id, web_raw_id = seed_run(web_source_id, "web_page", "web", "Long enough web content for quality metrics in Xi'an.")
    rss_run_id, rss_raw_id = seed_run(rss_source_id, "rss", "rss", "Short")
    quality = client.post(
        "/api/v1/data-quality-runs",
        headers=headers,
        json={"raw_record_ids": [web_raw_id, rss_raw_id], "rule_version": "score_clean_record_quality-at305", "response_limit": 10},
    )
    assert quality.status_code == 200, quality.text

    web_metrics = client.get("/api/v1/collection-channels/web_page/quality-metrics", headers=headers)
    assert web_metrics.status_code == 200, web_metrics.text
    data = web_metrics.json()["data"]
    assert data["channel"] == "web_page"
    assert data["summary"]["run_count"] >= 1
    assert data["summary"]["raw_record_count"] >= 1
    assert data["summary"]["quality_issue_count"] >= 0
    assert data["summary"]["lineage_edge_count"] >= 1
    assert data["summary"]["p95_latency_ms"] < 500
    assert any(run["collection_run_id"] == web_run_id for run in data["runs"])
    assert next(run for run in data["runs"] if run["collection_run_id"] == web_run_id)["status"] == "completed"
    assert data["page_state"] in {"ready", "degraded"}
    assert data["metrics_source"] == "postgresql"

    rss_metrics = client.get("/api/v1/collection-channels/rss/quality-metrics", headers=headers)
    assert rss_metrics.status_code == 200, rss_metrics.text
    rss_data = rss_metrics.json()["data"]
    assert rss_data["channel"] == "rss"
    assert rss_data["summary"]["run_count"] >= 1
    assert any(run["collection_run_id"] == rss_run_id for run in rss_data["runs"])
    assert all(run["collection_run_id"] != web_run_id for run in rss_data["runs"])

    missing = client.get("/api/v1/collection-channels/nope/quality-metrics", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CHANNEL_NOT_FOUND"

    other_audit_id = f"AUDIT-other-at305-{uuid4().hex[:8]}"
    with Session(engine) as db:
        db.merge(models.Tenant(id="tenant-at305-other", name="AT305 other tenant", status="active", payload={}))
        db.commit()
        db.add(
            models.AuditLog(
                id=other_audit_id,
                tenant_id="tenant-at305-other",
                actor="other-admin",
                action="collection_channel.quality_metrics_read",
                object_type="collection_channel",
                object_id="web_page",
                before={},
                after={"channel": "web_page", "summary": {"run_count": 999}},
                diff={},
                payload={},
            )
        )
        db.commit()

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.quality_metrics_read" in audit_payload
    assert "web_page" in audit_payload
    assert other_audit_id not in audit_payload
    other_detail = client.get(f"/api/v1/audit-logs/{other_audit_id}", headers=headers)
    assert other_detail.status_code == 404


def test_s2_channel_maintenance_dashboard_returns_cost_metrics_and_alerts() -> None:
    headers = _headers()
    prefix = _unique_name("S2 channel maintenance")
    web_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} web", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "web_page"}},
    )
    rss_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} rss", "source_type": "synthetic", "policy": {"access_mode": "test_fixture", "is_synthetic": True, "channel": "rss"}},
    )
    assert web_source.status_code == 200, web_source.text
    assert rss_source.status_code == 200, rss_source.text
    web_source_id = web_source.json()["data"]["data_source_id"]
    rss_source_id = rss_source.json()["data"]["data_source_id"]

    web_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": web_source_id, "name": f"{prefix} web", "payload": {"collection_channel": "web_page"}})
    rss_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": rss_source_id, "name": f"{prefix} rss", "payload": {"collection_channel": "rss"}})
    assert web_job.status_code == 200, web_job.text
    assert rss_job.status_code == 200, rss_job.text
    web_run = client.post(f"/api/v1/collection-jobs/{web_job.json()['data']['collection_job_id']}/runs", headers=headers)
    rss_run = client.post(f"/api/v1/collection-jobs/{rss_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert web_run.status_code == 200, web_run.text
    assert rss_run.status_code == 200, rss_run.text
    web_run_id = web_run.json()["data"]["collection_run_id"]
    rss_run_id = rss_run.json()["data"]["collection_run_id"]
    _complete_collection_run_for_test(web_run_id)
    with Session(engine) as db:
        rss_row = db.get(models.CollectionRun, rss_run_id)
        assert rss_row is not None
        rss_row.status = "failed"
        rss_row.error_code = "RSS_FEED_RATE_LIMITED"
        rss_row.error_message = "Synthetic RSS maintenance failure."
        rss_row.payload = {**(rss_row.payload or {}), "workflow_status": "failed", "collection_channel": "rss"}
        db.add(
            models.DataSourceVersion(
                id=f"DSV-at306-{uuid4().hex[:8]}",
                tenant_id=foundation.DEFAULT_TENANT_ID,
                data_source_id=web_source_id,
                version=7,
                status="published",
                config_hash="at306-web-config-hash",
                policy_snapshot={"channel": "web_page", "access_mode": "test_fixture"},
                payload={"reason": "AT-306 test published config"},
                published_by_id=None,
                published_at=datetime.utcnow(),
            )
        )
        db.commit()

    response = client.get("/api/v1/collection-channels/maintenance", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["tenant_id"] == foundation.DEFAULT_TENANT_ID
    assert data["metrics_source"] == "postgresql"
    assert data["summary"]["channel_count"] == 11
    assert data["summary"]["p95_latency_ms"] < 1000
    assert data["metrics_snapshot_id"]
    channels = {row["channel"]: row for row in data["channels"]}
    assert channels["web_page"]["run_count"] >= 1
    assert channels["web_page"]["completed_run_count"] >= 1
    assert channels["web_page"]["failure_rate"] >= 0
    assert channels["web_page"]["config_version"]["latest_version"] >= 7
    assert channels["web_page"]["code_version"]["version"]
    assert channels["web_page"]["test_coverage"]["api_test"] == "test_s2_channel_maintenance_dashboard_returns_cost_metrics_and_alerts"
    assert channels["rss"]["failed_run_count"] >= 1
    assert channels["rss"]["failure_rate"] > 0
    assert any(item["error_code"] == "RSS_FEED_RATE_LIMITED" for item in channels["rss"]["top_error_codes"])
    assert any(warning["code"] == "CONFIG_VERSION_MISSING" for warning in channels["rss"]["warnings"])
    assert any(warning["code"] == "CHANNEL_MAINTENANCE_METRICS_MISSING" for row in channels.values() for warning in row["warnings"])
    assert data["page_state"] in {"ready", "degraded"}

    role_response = client.post(
        "/api/v1/roles",
        json={"name": f"at306_audit_only_{uuid4().hex[:8]}", "description": "Can inspect audit but not channel maintenance.", "permission_codes": ["audit:read"]},
        headers=headers,
    )
    assert role_response.status_code == 200, role_response.text
    username = f"at306.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        json={"username": username, "display_name": "AT-306 Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
        headers=headers,
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    forbidden = client.get("/api/v1/collection-channels/maintenance", headers={"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"})
    assert forbidden.status_code == 403

    with Session(engine) as db:
        snapshot = db.get(models.MetricsSnapshot, data["metrics_snapshot_id"])
        assert snapshot is not None
        assert snapshot.tenant_id == foundation.DEFAULT_TENANT_ID
        assert snapshot.metric_scope == "collection_channels:maintenance"
        assert snapshot.payload["summary"]["channel_count"] == 11
    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_channel.maintenance_read" in audit_payload


def test_s2_start_collection_run_creates_pending_workflow_and_blocks_existing_running_run() -> None:
    headers = _headers()
    prefix = _unique_name("S2 start run")

    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run.status_code == 200, run.text
    run_data = run.json()["data"]
    assert run_data["status"] == "pending"
    assert run_data["record_count"] == 0
    assert run_data["payload"]["workflow_name"] == "CollectSourceRunWorkflow"
    assert run_data["payload"]["workflow_status"] == "pending"
    assert run_data["payload"]["manual_start"] is True
    assert run_data["payload"]["started_by"]
    workflow_run_id = run_data["payload"]["workflow_run_id"]

    with Session(engine) as db:
        persisted_run = db.get(models.CollectionRun, run_data["collection_run_id"])
        assert persisted_run is not None
        assert persisted_run.status == "pending"
        workflow = db.get(models.WorkflowRun, workflow_run_id)
        assert workflow is not None
        assert workflow.workflow_name == "CollectSourceRunWorkflow"
        assert workflow.status == "pending"
        assert workflow.payload["collection_run_id"] == run_data["collection_run_id"]
        assert workflow.payload["collection_job_id"] == job_id

    blocked = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "COLLECTION_RUN_ALREADY_RUNNING"

    detail = client.get(f"/api/v1/collection-jobs/{job_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["run_summary"]["running_count"] == 1
    assert detail.json()["data"]["latest_runs"][0]["collection_run_id"] == run_data["collection_run_id"]


def test_s2_pause_collection_job_preserves_running_run_and_blocks_new_runs() -> None:
    headers = _headers()
    prefix = _unique_name("S2 pause job")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    auth = client.put(f"/api/v1/data-sources/{source_id}/auth", headers=headers, json={"auth_type": "api_key", "secret_ref": "vault://s2/pause-official", "header_name": "X-API-Key"})
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-061 pause job compliance"))
    assert compliance.status_code == 200, compliance.text
    version = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-061 pause job publish"})
    assert version.status_code == 200, version.text
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job", "schedule": "cron:*/15 * * * *", "payload": {"query": {"district": "yanta"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}}})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run.status_code == 200, run.text
    run_id = run.json()["data"]["collection_run_id"]

    pause = client.post(f"/api/v1/collection-jobs/{job_id}/pause", headers=headers, json={"reason": "AT-061 pause collection job"})
    assert pause.status_code == 200, pause.text
    paused_data = pause.json()["data"]
    assert paused_data["status"] == "paused"
    assert paused_data["payload"]["pause"]["reason"] == "AT-061 pause collection job"
    assert paused_data["payload"]["pause"]["active_run_ids"] == [run_id]

    with Session(engine) as db:
        persisted_run = db.get(models.CollectionRun, run_id)
        assert persisted_run is not None
        assert persisted_run.status == "pending"
        persisted_job = db.get(models.CollectionJob, job_id)
        assert persisted_job is not None
        assert persisted_job.status == "paused"

    blocked_while_pending = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert blocked_while_pending.status_code == 409
    assert blocked_while_pending.json()["error"]["code"] == "COLLECTION_JOB_PAUSED"

    _complete_collection_run_for_test(run_id)
    blocked_after_completion = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert blocked_after_completion.status_code == 409
    assert blocked_after_completion.json()["error"]["code"] == "COLLECTION_JOB_PAUSED"

    detail = client.get(f"/api/v1/collection-jobs/{job_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_data = detail.json()["data"]
    assert detail_data["status"] == "paused"
    assert detail_data["run_summary"]["total_runs"] == 1
    assert detail_data["latest_runs"][0]["collection_run_id"] == run_id

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_job.pause" in audit_payload
    assert "AT-061 pause collection job" in audit_payload


def test_s2_resume_collection_job_requires_active_source_and_allows_next_run() -> None:
    headers = _headers()
    prefix = _unique_name("S2 resume job")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    auth = client.put(f"/api/v1/data-sources/{source_id}/auth", headers=headers, json={"auth_type": "api_key", "secret_ref": "vault://s2/resume-official", "header_name": "X-API-Key"})
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-062 resume job compliance"))
    assert compliance.status_code == 200, compliance.text
    version = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "AT-062 resume job publish"})
    assert version.status_code == 200, version.text
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job", "schedule": "cron:*/15 * * * *", "payload": {"query": {"district": "yanta"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}}})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]

    pause = client.post(f"/api/v1/collection-jobs/{job_id}/pause", headers=headers, json={"reason": "AT-062 pause before resume"})
    assert pause.status_code == 200, pause.text

    disabled = client.patch(f"/api/v1/data-sources/{source_id}/status", headers=headers, json={"status": "disabled", "reason": "AT-062 disabled source gate"})
    assert disabled.status_code == 200, disabled.text
    blocked_resume = client.post(f"/api/v1/collection-jobs/{job_id}/resume", headers=headers, json={"reason": "AT-062 blocked resume"})
    assert blocked_resume.status_code == 409
    assert blocked_resume.json()["error"]["code"] == "DATA_SOURCE_DISABLED"

    reenabled = client.patch(f"/api/v1/data-sources/{source_id}/status", headers=headers, json={"status": "active", "reason": "AT-062 re-enable source"})
    assert reenabled.status_code == 200, reenabled.text
    resumed = client.post(f"/api/v1/collection-jobs/{job_id}/resume", headers=headers, json={"reason": "AT-062 resume collection job"})
    assert resumed.status_code == 200, resumed.text
    resumed_data = resumed.json()["data"]
    assert resumed_data["status"] == "active"
    assert resumed_data["payload"]["resume"]["reason"] == "AT-062 resume collection job"
    assert resumed_data["payload"]["resume"]["previous_status"] == "paused"
    assert resumed_data["payload"]["operational_state"]["status"] == "active"

    run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["status"] == "pending"
    assert run.json()["data"]["payload"]["workflow_status"] == "pending"

    with Session(engine) as db:
        persisted_job = db.get(models.CollectionJob, job_id)
        assert persisted_job is not None
        assert persisted_job.status == "active"
        assert persisted_job.payload["resume"]["reason"] == "AT-062 resume collection job"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_job.resume" in audit_payload
    assert "AT-062 resume collection job" in audit_payload


def test_s2_cancel_collection_run_transitions_and_rejects_terminal_runs() -> None:
    headers = _headers()
    prefix = _unique_name("S2 cancel run")

    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run.status_code == 200, run.text
    run_id = run.json()["data"]["collection_run_id"]
    workflow_run_id = run.json()["data"]["payload"]["workflow_run_id"]

    canceled = client.post(f"/api/v1/collection-runs/{run_id}/cancel", headers=headers)
    assert canceled.status_code == 200, canceled.text
    canceled_data = canceled.json()["data"]
    assert canceled_data["status"] == "canceled"
    assert canceled_data["payload"]["cancel"]["requested_by"]
    assert canceled_data["payload"]["cancel"]["transition"] == "pending->cancelling->canceled"
    assert canceled_data["payload"]["workflow_status"] == "canceled"

    with Session(engine) as db:
        persisted_run = db.get(models.CollectionRun, run_id)
        assert persisted_run is not None
        assert persisted_run.status == "canceled"
        workflow = db.get(models.WorkflowRun, workflow_run_id)
        assert workflow is not None
        assert workflow.status == "canceled"
        event_types = {
            event.event_type
            for event in db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars()
        }
        assert {"cancel_requested", "cancel_completed"} <= event_types
        workflow_event_types = {
            event.event_type
            for event in db.execute(select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow_run_id)).scalars()
        }
        assert {"cancel_requested", "cancel_completed"} <= workflow_event_types

    blocked_terminal = client.post(f"/api/v1/collection-runs/{run_id}/cancel", headers=headers)
    assert blocked_terminal.status_code == 409
    assert blocked_terminal.json()["error"]["code"] == "COLLECTION_RUN_TERMINAL"

    rerun = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert rerun.status_code == 200, rerun.text
    _complete_collection_run_for_test(rerun.json()["data"]["collection_run_id"])
    blocked_completed = client.post(f"/api/v1/collection-runs/{rerun.json()['data']['collection_run_id']}/cancel", headers=headers)
    assert blocked_completed.status_code == 409
    assert blocked_completed.json()["error"]["code"] == "COLLECTION_RUN_TERMINAL"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.cancel" in audit_payload


def test_s2_retry_failed_collection_run_creates_pending_retry_without_duplicate_raw_records() -> None:
    headers = _headers()
    prefix = _unique_name("S2 retry run")

    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    failed = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert failed.status_code == 200, failed.text
    failed_run_id = failed.json()["data"]["collection_run_id"]
    failed_workflow_id = failed.json()["data"]["payload"]["workflow_run_id"]
    with Session(engine) as db:
        run = db.get(models.CollectionRun, failed_run_id)
        assert run is not None
        run.status = "failed"
        run.error_code = "SYNTHETIC_TRANSIENT_FAILURE"
        run.error_message = "Synthetic transient failure for retry test."
        run.payload = {**(run.payload or {}), "input_snapshot": {"query": {"district": "yanta"}, "window": {"from": "2026-05-01", "to": "2026-05-09"}}}
        workflow = db.get(models.WorkflowRun, failed_workflow_id)
        assert workflow is not None
        workflow.status = "failed"
        db.commit()

    retry = client.post(f"/api/v1/collection-runs/{failed_run_id}/retry", headers=headers)
    assert retry.status_code == 200, retry.text
    retry_data = retry.json()["data"]
    assert retry_data["status"] == "pending"
    assert retry_data["record_count"] == 0
    assert retry_data["payload"]["retry_of"] == failed_run_id
    assert retry_data["payload"]["retry_attempt"] == 1
    assert retry_data["payload"]["workflow_name"] == "CollectSourceRunWorkflow"
    assert retry_data["payload"]["workflow_status"] == "pending"
    assert retry_data["payload"]["input_snapshot"]["query"]["district"] == "yanta"

    with Session(engine) as db:
        retry_run = db.get(models.CollectionRun, retry_data["collection_run_id"])
        assert retry_run is not None
        assert retry_run.status == "pending"
        workflow = db.get(models.WorkflowRun, retry_data["payload"]["workflow_run_id"])
        assert workflow is not None
        assert workflow.status == "pending"
        assert workflow.payload["retry_of"] == failed_run_id
        raw_count = db.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.collection_run_id == retry_data["collection_run_id"])).scalar_one()
        assert raw_count == 0
        original = db.get(models.CollectionRun, failed_run_id)
        assert original is not None
        assert original.payload["last_retry_run_id"] == retry_data["collection_run_id"]

    retry_again = client.post(f"/api/v1/collection-runs/{failed_run_id}/retry", headers=headers)
    assert retry_again.status_code == 409
    assert retry_again.json()["error"]["code"] == "COLLECTION_RETRY_ALREADY_ACTIVE"

    _complete_collection_run_for_test(retry_data["collection_run_id"])
    completed_retry = client.post(f"/api/v1/collection-runs/{retry_data['collection_run_id']}/retry", headers=headers)
    assert completed_retry.status_code == 409
    assert completed_retry.json()["error"]["code"] == "COLLECTION_RUN_NOT_RETRYABLE"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "collection_run.retry" in audit_payload


def test_s2_collection_run_list_filters_pagination_and_tenant_scope() -> None:
    headers = _headers()
    prefix = _unique_name("S2 run list")

    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    other_source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} other source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert other_source_response.status_code == 200, other_source_response.text
    other_source_id = other_source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    other_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": other_source_id, "name": f"{prefix} other job"})
    assert other_job.status_code == 200, other_job.text

    statuses = ["failed", "completed", "pending", "canceled"]
    run_ids: list[str] = []
    with Session(engine) as db:
        for index, status in enumerate(statuses):
            run_id = f"CRUN-{uuid4().hex[:20]}"
            db.add(
                models.CollectionRun(
                    id=run_id,
                    collection_job_id=job_id,
                    data_source_id=source_id,
                    status=status,
                    record_count=index,
                    created_at=datetime(2026, 5, 9, 8 + index, 0, 0),
                    trace_id=f"at065-{index}",
                    payload={"index": index},
                )
            )
            run_ids.append(run_id)
        db.add(
            models.CollectionRun(
                id=f"CRUN-{uuid4().hex[:20]}",
                collection_job_id=other_job.json()["data"]["collection_job_id"],
                data_source_id=other_source_id,
                status="failed",
                record_count=0,
                created_at=datetime(2026, 5, 9, 12, 0, 0),
                trace_id="at065-other-source",
                payload={},
            )
        )
        other_tenant_id = f"tenant-{uuid4().hex[:8]}"
        foreign_source_id = f"DS-{uuid4().hex[:20]}"
        foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
        db.add(models.Tenant(id=other_tenant_id, name="Foreign tenant run list", status="active", payload={}))
        db.commit()
        db.add(models.DataSource(id=foreign_source_id, tenant_id=other_tenant_id, name=f"{prefix} foreign source", source_type="synthetic", status="active", is_synthetic=True, policy={}, payload={}))
        db.commit()
        db.add(models.CollectionJob(id=foreign_job_id, tenant_id=other_tenant_id, data_source_id=foreign_source_id, name=f"{prefix} foreign job", status="active", schedule=None, payload={}))
        db.add(models.CollectionRun(id=f"CRUN-{uuid4().hex[:20]}", collection_job_id=foreign_job_id, data_source_id=foreign_source_id, status="failed", record_count=0, created_at=datetime(2026, 5, 9, 13, 0, 0), trace_id="at065-foreign", payload={}))
        db.commit()

    page_one = client.get("/api/v1/collection-runs", headers=headers, params={"data_source_id": source_id, "page": 1, "page_size": 2})
    assert page_one.status_code == 200, page_one.text
    assert page_one.json()["meta"]["pagination"]["total"] == 4
    assert len(page_one.json()["data"]) == 2
    assert page_one.json()["data"][0]["status"] == "canceled"

    failed_filter = client.get("/api/v1/collection-runs", headers=headers, params={"status": "failed", "data_source_id": source_id})
    assert failed_filter.status_code == 200, failed_filter.text
    assert [item["collection_run_id"] for item in failed_filter.json()["data"]] == [run_ids[0]]

    job_filter = client.get("/api/v1/collection-runs", headers=headers, params={"collection_job_id": job_id})
    assert job_filter.status_code == 200, job_filter.text
    assert job_filter.json()["meta"]["pagination"]["total"] == 4

    time_filter = client.get("/api/v1/collection-runs", headers=headers, params={"data_source_id": source_id, "created_from": "2026-05-09T09:00:00", "created_to": "2026-05-09T10:30:00"})
    assert time_filter.status_code == 200, time_filter.text
    assert [item["status"] for item in time_filter.json()["data"]] == ["pending", "completed"]

    invalid_status = client.get("/api/v1/collection-runs", headers=headers, params={"status": "not-a-status"})
    assert invalid_status.status_code == 422
    assert invalid_status.json()["error"]["code"] == "COLLECTION_RUN_STATUS_INVALID"

    invalid_time = client.get("/api/v1/collection-runs", headers=headers, params={"created_from": "not-a-date"})
    assert invalid_time.status_code == 422
    assert invalid_time.json()["error"]["code"] == "COLLECTION_RUN_CREATED_FROM_INVALID"

    foreign_lookup = client.get("/api/v1/collection-runs", headers=headers, params={"collection_job_id": foreign_job_id})
    assert foreign_lookup.status_code == 200, foreign_lookup.text
    assert foreign_lookup.json()["meta"]["pagination"]["total"] == 0


def test_s2_collection_run_steps_show_stage_statuses_and_tenant_scope() -> None:
    headers = _headers()
    prefix = _unique_name("S2 run steps")

    source_response = client.post("/api/v1/data-sources", headers=headers, json={"name": f"{prefix} source", "source_type": "synthetic", "policy": {"access_mode": "test_fixture"}})
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run.status_code == 200, run.text
    run_id = run.json()["data"]["collection_run_id"]
    workflow_run_id = run.json()["data"]["payload"]["workflow_run_id"]

    with Session(engine) as db:
        persisted = db.get(models.CollectionRun, run_id)
        assert persisted is not None
        persisted.status = "running"
        persisted.payload = {**(persisted.payload or {}), "workflow_status": "running"}
        workflow = db.get(models.WorkflowRun, workflow_run_id)
        assert workflow is not None
        workflow.status = "running"
        for step_key, event_type, status in [
            ("fetch", "fetch_completed", "completed"),
            ("parse", "parse_completed", "completed"),
            ("store", "store_started", "running"),
        ]:
            db.add(
                models.CollectionRunEvent(
                    id=f"CREV-{uuid4().hex[:20]}",
                    collection_run_id=run_id,
                    event_type=event_type,
                    status=status,
                    payload={"step_key": step_key, "stage": step_key, "trace_id": persisted.trace_id},
                )
            )
        db.add(models.WorkflowRunEvent(id=f"WFRE-{uuid4().hex[:20]}", workflow_run_id=workflow_run_id, event_type="activity_started", status="running", payload={"step_key": "store", "collection_run_id": run_id}))

        other_tenant_id = f"tenant-{uuid4().hex[:8]}"
        foreign_source_id = f"DS-{uuid4().hex[:20]}"
        foreign_job_id = f"CJOB-{uuid4().hex[:20]}"
        foreign_run_id = f"CRUN-{uuid4().hex[:20]}"
        db.add(models.Tenant(id=other_tenant_id, name="Foreign tenant run steps", status="active", payload={}))
        db.commit()
        db.add(models.DataSource(id=foreign_source_id, tenant_id=other_tenant_id, name=f"{prefix} foreign source", source_type="synthetic", status="active", is_synthetic=True, policy={}, payload={}))
        db.commit()
        db.add(models.CollectionJob(id=foreign_job_id, tenant_id=other_tenant_id, data_source_id=foreign_source_id, name=f"{prefix} foreign job", status="active", schedule=None, payload={}))
        db.add(models.CollectionRun(id=foreign_run_id, collection_job_id=foreign_job_id, data_source_id=foreign_source_id, status="running", record_count=0, trace_id="at066-foreign", payload={}))
        db.commit()

    steps = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    data = steps.json()["data"]
    assert data["collection_run_id"] == run_id
    assert data["workflow_run_id"] == workflow_run_id
    assert data["page_state"] == "ready"
    assert data["raw_record_count"] == 0
    step_by_key = {item["step_key"]: item for item in data["steps"]}
    assert list(step_by_key) == ["fetch", "parse", "store", "clean", "extract"]
    assert step_by_key["fetch"]["status"] == "completed"
    assert step_by_key["parse"]["status"] == "completed"
    assert step_by_key["store"]["status"] == "running"
    assert step_by_key["clean"]["status"] == "pending"
    assert step_by_key["extract"]["status"] == "pending"
    assert step_by_key["store"]["event_refs"]
    assert data["events"][0]["source"] in {"collection_run_event", "workflow_run_event"}

    missing = client.get(f"/api/v1/collection-runs/CRUN-{uuid4().hex[:20]}/steps", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    foreign = client.get(f"/api/v1/collection-runs/{foreign_run_id}/steps", headers=headers)
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "NOT_FOUND"

    role_response = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"name": f"{prefix} audit only", "description": "Cannot inspect collection run steps.", "permission_codes": ["audit:read"]},
    )
    assert role_response.status_code == 200, role_response.text
    username = f"run.steps.viewer.{uuid4().hex[:8]}"
    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": username, "display_name": "Run Steps Viewer", "password": "StrongPass123!", "role_ids": [role_response.json()["data"]["role_id"]]},
    )
    assert user_response.status_code == 200, user_response.text
    viewer_login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert viewer_login.status_code == 200, viewer_login.text
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['data']['access_token']}"}
    forbidden = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=viewer_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def test_s2_data_source_version_rollback_creates_new_version_and_preserves_running_runs() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source rollback")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} official",
            "source_type": "official_api",
            "policy": {
                "access_mode": "official_api",
                "base_url": "synthetic://xian/official-api",
                "method": "GET",
                "schema": {"records_path": "$.items", "id_path": "$.id"},
            },
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    auth = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/rollback-official-v1", "header_name": "X-API-Key"},
    )
    assert auth.status_code == 200, auth.text
    connection = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues", "expected_status": 200})
    assert connection.status_code == 200, connection.text
    compliance = client.put(f"/api/v1/data-sources/{source_id}/compliance", headers=headers, json=_compliance_payload("AT-050 rollback compliance before v1"))
    assert compliance.status_code == 200, compliance.text
    v1 = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "publish v1"})
    assert v1.status_code == 200, v1.text

    auth_v2 = client.put(
        f"/api/v1/data-sources/{source_id}/auth",
        headers=headers,
        json={"auth_type": "api_key", "secret_ref": "vault://s2/rollback-official-v2", "header_name": "X-API-Key"},
    )
    assert auth_v2.status_code == 200, auth_v2.text
    connection_v2 = client.post(f"/api/v1/data-sources/{source_id}/test-connection", headers=headers, json={"sample_path": "/xian/issues/v2", "expected_status": 200})
    assert connection_v2.status_code == 200, connection_v2.text
    v2 = client.post(f"/api/v1/data-sources/{source_id}/versions/publish", headers=headers, json={"reason": "publish v2"})
    assert v2.status_code == 200, v2.text
    assert v2.json()["data"]["version"] == 2

    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} existing job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    run_before = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_before.status_code == 200, run_before.text
    assert run_before.json()["data"]["payload"]["data_source_version"] == 2
    _complete_collection_run_for_test(run_before.json()["data"]["collection_run_id"])

    rollback = client.post(
        f"/api/v1/data-sources/{source_id}/versions/1/rollback",
        headers=headers,
        json={"reason": "AT-050 rollback to v1 after v2 issue"},
    )
    assert rollback.status_code == 200, rollback.text
    rollback_data = rollback.json()["data"]
    assert rollback_data["version"] == 3
    assert rollback_data["status"] == "published"
    assert rollback_data["payload"]["rollback_from_version"] == 2
    assert rollback_data["payload"]["rollback_to_version"] == 1
    assert rollback_data["policy_snapshot"]["secret_ref"] == "vault://s2/rollback-official-v1"

    refreshed = client.get("/api/v1/data-sources", headers=headers, params={"source_type": "official_api", "page_size": 50})
    stored = next(item for item in refreshed.json()["data"] if item["data_source_id"] == source_id)
    assert stored["policy"]["published_version"]["version"] == 3
    assert stored["policy"]["rollback"]["from_version"] == 2
    assert stored["policy"]["rollback"]["to_version"] == 1

    patched_job = client.patch(
        f"/api/v1/collection-jobs/{job_id}",
        headers=headers,
        json={"data_source_id": source_id, "name": f"{prefix} existing job renamed", "payload": {"client_note": "preserve server version pin"}},
    )
    assert patched_job.status_code == 200, patched_job.text
    assert patched_job.json()["data"]["payload"]["client_note"] == "preserve server version pin"
    assert patched_job.json()["data"]["payload"]["data_source_version"] == 2
    assert patched_job.json()["data"]["payload"]["data_source_version_id"] == v2.json()["data"]["data_source_version_id"]

    run_after = client.post(f"/api/v1/collection-jobs/{job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert run_after.status_code == 200, run_after.text
    assert run_after.json()["data"]["payload"]["data_source_version"] == 2

    new_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} after rollback"})
    assert new_job.status_code == 200, new_job.text
    assert new_job.json()["data"]["payload"]["data_source_version"] == 3

    missing = client.post(f"/api/v1/data-sources/{source_id}/versions/99/rollback", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DATA_SOURCE_VERSION_NOT_FOUND"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.version.rollback" in audit_payload
    assert "rollback_from_version" in audit_payload
    assert "rollback_to_version" in audit_payload


def test_s2_data_source_disable_blocks_new_collection_without_mutating_existing_run() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source disable")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"]}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]
    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} existing job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    run_before = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run_before.status_code == 200, run_before.text
    assert run_before.json()["data"]["status"] == "pending"
    run_id = run_before.json()["data"]["collection_run_id"]
    running_run_id = f"CRUN-RUNNING-{uuid4().hex[:12]}"
    with Session(engine) as session:
        session.add(
            models.CollectionRun(
                id=running_run_id,
                collection_job_id=job_id,
                data_source_id=source_id,
                status="running",
                record_count=0,
                trace_id="at051-running-boundary",
                payload={"test_marker": "at051_running_run_not_force_killed"},
            )
        )
        session.commit()

    disabled = client.patch(
        f"/api/v1/data-sources/{source_id}/status",
        headers=headers,
        json={"status": "disabled", "reason": "AT-051 disable source for collection safety"},
    )
    assert disabled.status_code == 200, disabled.text
    disabled_data = disabled.json()["data"]
    assert disabled_data["status"] == "disabled"
    assert disabled_data["policy"]["operational_state"]["status"] == "disabled"
    assert disabled_data["policy"]["operational_state"]["reason"] == "AT-051 disable source for collection safety"

    existing_run = client.get(f"/api/v1/collection-runs/{run_id}", headers=headers)
    assert existing_run.status_code == 200, existing_run.text
    assert existing_run.json()["data"]["status"] == "pending"
    running_after_disable = client.get(f"/api/v1/collection-runs/{running_run_id}", headers=headers)
    assert running_after_disable.status_code == 200, running_after_disable.text
    assert running_after_disable.json()["data"]["status"] == "running"

    blocked_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} blocked new job"})
    assert blocked_job.status_code == 409
    assert blocked_job.json()["error"]["code"] == "DATA_SOURCE_DISABLED"

    run_after_disable = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert run_after_disable.status_code == 409
    assert run_after_disable.json()["error"]["code"] == "DATA_SOURCE_DISABLED"

    reenabled = client.patch(
        f"/api/v1/data-sources/{source_id}/status",
        headers=headers,
        json={"status": "active", "reason": "AT-051 re-enable after validation"},
    )
    assert reenabled.status_code == 200, reenabled.text
    assert reenabled.json()["data"]["status"] == "active"

    new_job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} reenabled job"})
    assert new_job.status_code == 200, new_job.text
    rerun = client.post(f"/api/v1/collection-jobs/{new_job.json()['data']['collection_job_id']}/runs", headers=headers)
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["data"]["status"] == "pending"

    audit_payload = json.dumps(client.get("/api/v1/audit-logs", headers=headers).json()["data"], ensure_ascii=False)
    assert "data_source.status.update" in audit_payload
    assert "AT-051 disable source for collection safety" in audit_payload


def test_s2_data_source_health_detail_unknown_degraded_and_recovered_states() -> None:
    headers = _headers()
    prefix = _unique_name("S2 source health")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={"name": f"{prefix} manual", "source_type": "manual", "policy": {"entry_schema": {"required_fields": ["title", "content"]}}},
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    initial = client.get(f"/api/v1/data-sources/{source_id}/health", headers=headers)
    assert initial.status_code == 200, initial.text
    initial_data = initial.json()["data"]
    assert initial_data["status"] == "unknown"
    assert initial_data["last_success"] is None
    assert initial_data["last_failure"] is None
    assert initial_data["error_rate"] == 0
    assert initial_data["recent_runs"] == []

    job = client.post("/api/v1/collection-jobs", headers=headers, json={"data_source_id": source_id, "name": f"{prefix} job"})
    assert job.status_code == 200, job.text
    job_id = job.json()["data"]["collection_job_id"]
    first_run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert first_run.status_code == 200, first_run.text
    _complete_collection_run_for_test(first_run.json()["data"]["collection_run_id"])

    disabled = client.patch(f"/api/v1/data-sources/{source_id}/status", headers=headers, json={"status": "disabled", "reason": "AT-052 degraded source health"})
    assert disabled.status_code == 200, disabled.text
    blocked_run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert blocked_run.status_code == 409
    assert blocked_run.json()["error"]["code"] == "DATA_SOURCE_DISABLED"

    degraded = client.get(f"/api/v1/data-sources/{source_id}/health", headers=headers)
    assert degraded.status_code == 200, degraded.text
    degraded_data = degraded.json()["data"]
    assert degraded_data["status"] == "disabled"
    assert degraded_data["last_success"]["collection_run_id"] == first_run.json()["data"]["collection_run_id"]
    assert degraded_data["last_failure"]["error_code"] == "DATA_SOURCE_DISABLED"
    assert degraded_data["failure_count"] >= 1
    assert degraded_data["error_rate"] > 0
    assert degraded_data["source"]["status"] == "disabled"
    assert degraded_data["recent_runs"][0]["collection_run_id"] == degraded_data["last_failure"]["collection_run_id"]

    reenabled = client.patch(f"/api/v1/data-sources/{source_id}/status", headers=headers, json={"status": "active", "reason": "AT-052 recover source health"})
    assert reenabled.status_code == 200, reenabled.text
    second_run = client.post(f"/api/v1/collection-jobs/{job_id}/runs", headers=headers)
    assert second_run.status_code == 200, second_run.text
    _complete_collection_run_for_test(second_run.json()["data"]["collection_run_id"])

    recovered = client.get(f"/api/v1/data-sources/{source_id}/health", headers=headers)
    assert recovered.status_code == 200, recovered.text
    recovered_data = recovered.json()["data"]
    assert recovered_data["status"] == "healthy"
    assert recovered_data["last_success"]["collection_run_id"] == second_run.json()["data"]["collection_run_id"]
    assert recovered_data["recent_runs"][0]["collection_run_id"] == second_run.json()["data"]["collection_run_id"]
    assert recovered_data["success_count"] >= 2
    assert recovered_data["last_failure"]["error_code"] == "DATA_SOURCE_DISABLED"
    assert recovered_data["page_state"] in {"ready", "degraded"}


def test_s2_import_normalization_dedup_quality_and_retry_chain() -> None:
    headers = _headers()

    manual_source = client.post("/api/v1/data-sources", headers=headers, json={"name": "Manual import source", "source_type": "manual_upload"})
    public_source = client.post("/api/v1/data-sources", headers=headers, json={"name": "Public web import source", "source_type": "public_web", "policy": {"access_mode": "public_web"}})
    media_source = client.post("/api/v1/data-sources", headers=headers, json={"name": "Media import source", "source_type": "media"})
    official_source = client.post("/api/v1/data-sources", headers=headers, json={"name": "Official API without key", "source_type": "official_api"})
    for response in [manual_source, public_source, media_source, official_source]:
        assert response.status_code == 200, response.text
    assert official_source.json()["data"]["status"] == "blocked"

    duplicate_content = "synthetic import duplicate content. minor name: Zhang needs masking."
    file_import = client.post(
        "/api/v1/imports/files",
        headers=headers,
        json={
            "data_source_id": manual_source.json()["data"]["data_source_id"],
            "title": "Manual file import",
            "content": duplicate_content,
            "source_uri": "synthetic://imports/file-001.txt",
            "is_synthetic": True,
        },
    )
    public_import = client.post(
        "/api/v1/imports/public-web",
        headers=headers,
        json={
            "data_source_id": public_source.json()["data"]["data_source_id"],
            "title": "Public web import",
            "content": duplicate_content,
            "source_uri": "https://example.invalid/xian-public-web",
            "is_synthetic": True,
        },
    )
    media_import = client.post(
        "/api/v1/imports/media",
        headers=headers,
        json={
            "data_source_id": media_source.json()["data"]["data_source_id"],
            "title": "Media import",
            "content": "synthetic media import transcript for Xi'an public service issue.",
            "source_uri": "synthetic://imports/media-001.png",
            "media_type": "image",
            "media_uri": "synthetic://imports/media-001.png",
            "is_synthetic": True,
        },
    )
    official_import = client.post(
        "/api/v1/imports/official-api",
        headers=headers,
        json={
            "data_source_id": official_source.json()["data"]["data_source_id"],
            "title": "Official import should fail",
            "source_uri": "official://xian/no-key",
        },
    )
    for response in [file_import, public_import, media_import, official_import]:
        assert response.status_code == 200, response.text
    assert file_import.json()["data"]["import_run"]["status"] == "completed"
    assert public_import.json()["data"]["import_run"]["status"] == "completed"
    assert media_import.json()["data"]["raw_records"][0]["payload"]["synthetic"] is True
    assert official_import.json()["data"]["import_run"]["status"] == "failed"
    assert official_import.json()["data"]["import_run"]["error_code"] == "official_api_key_missing"

    imported_raw_ids = [
        file_import.json()["data"]["raw_records"][0]["raw_record_id"],
        public_import.json()["data"]["raw_records"][0]["raw_record_id"],
        media_import.json()["data"]["raw_records"][0]["raw_record_id"],
    ]
    normalization = client.post("/api/v1/normalization-runs", headers=headers, json={"raw_record_ids": imported_raw_ids, "rule_version": "s2-test-normalize-v1"})
    assert normalization.status_code == 200, normalization.text
    assert normalization.json()["data"]["status"] == "completed"
    assert normalization.json()["data"]["output_count"] == 3

    dedup = client.post("/api/v1/deduplication-runs", headers=headers, json={"raw_record_ids": imported_raw_ids, "rule_version": "s2-test-dedup-v1"})
    assert dedup.status_code == 200, dedup.text
    assert dedup.json()["data"]["status"] == "completed"
    assert dedup.json()["data"]["duplicate_group_count"] == 0
    assert dedup.json()["data"]["deduper"]["cross_source_candidate_count"] == 2

    quality = client.post("/api/v1/data-quality-runs", headers=headers, json={"raw_record_ids": imported_raw_ids, "rule_version": "s2-test-quality-v1"})
    assert quality.status_code == 200, quality.text
    assert quality.json()["data"]["status"] == "completed"
    assert any(issue["issue_type"] == "sensitive_masked" for issue in quality.json()["data"]["issues"])

    import_runs = client.get("/api/v1/import-runs", headers=headers)
    assert import_runs.status_code == 200
    assert {run["status"] for run in import_runs.json()["data"]} >= {"completed", "failed"}

    metrics = client.get("/api/v1/ops/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data"]["import_runs"] >= 4
    assert metrics.json()["data"]["normalization_runs"] >= 1
    assert metrics.json()["data"]["deduplication_runs"] >= 1
    assert metrics.json()["data"]["data_quality_runs"] >= 1

    retry = client.get("/api/v1/ops/retry-queue", headers=headers)
    assert retry.status_code == 200
    assert any(item["target_type"] == "import_run" for item in retry.json()["data"])


def test_s2_public_web_fetch_activity_writes_html_object_and_classifies_failures() -> None:
    headers = _headers()
    prefix = _unique_name("S2 public web fetch")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "public_web",
            "policy": {"access_mode": "public_web", "base_url": "synthetic://xian/public-web"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    fetched = client.post(
        "/api/v1/imports/public-web",
        headers=headers,
        json={
            "data_source_id": source_id,
            "title": "西安社区公告页面",
            "source_uri": "synthetic://xian/public-web/community-notice-001",
        },
    )
    assert fetched.status_code == 200, fetched.text
    data = fetched.json()["data"]
    assert data["import_run"]["status"] == "completed"
    assert data["collection_run"]["status"] == "completed"
    assert data["import_run"]["payload"]["fetch_activity"]["activity_name"] == "fetch_public_web_page"
    assert data["import_run"]["payload"]["fetch_activity"]["classification"] == "html"
    assert data["raw_records"][0]["payload"]["fetch_activity"]["activity_name"] == "fetch_public_web_page"
    assert data["raw_records"][0]["payload"]["content_type"].startswith("text/html")
    assert data["raw_records"][0]["payload"]["source_flags"]["synthetic"] is True
    raw_record_id = data["raw_records"][0]["raw_record_id"]
    run_id = data["collection_run"]["collection_run_id"]
    workflow_run_id = data["collection_run"]["payload"]["workflow_run_id"]

    with Session(engine) as db:
        payload = db.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == raw_record_id)).scalar_one()
        assert "<html" in payload.content_text.lower()
        assert "西安" in payload.content_text
        assert payload.payload["activity_name"] == "fetch_public_web_page"
        file_object = db.execute(select(models.FileObject).where(models.FileObject.object_type == "raw_record", models.FileObject.object_id == raw_record_id)).scalar_one()
        assert file_object.mime_type.startswith("text/html")
        assert file_object.status == "stored"
        assert file_object.payload["storage_mode"] == "raw_record_payload"
        events = [
            event.event_type
            for event in db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars()
        ]
        assert "fetch_public_web_page_started" in events
        assert "fetch_public_web_page_completed" in events
        workflow_events = [
            event.event_type
            for event in db.execute(select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow_run_id)).scalars()
        ]
        assert "activity_started" in workflow_events
        assert "activity_completed" in workflow_events

    steps = client.get(f"/api/v1/collection-runs/{run_id}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    step_by_key = {item["step_key"]: item for item in steps.json()["data"]["steps"]}
    assert step_by_key["fetch"]["status"] == "completed"
    assert step_by_key["store"]["status"] == "completed"

    failure_cases = [
        ("timeout", "synthetic://xian/public-web/timeout", "PUBLIC_WEB_TIMEOUT"),
        ("forbidden", "synthetic://xian/public-web/forbidden", "PUBLIC_WEB_FORBIDDEN"),
        ("non-html", "synthetic://xian/public-web/non-html", "PUBLIC_WEB_NON_HTML"),
    ]
    for title, uri, code in failure_cases:
        failed = client.post(
            "/api/v1/imports/public-web",
            headers=headers,
            json={"data_source_id": source_id, "title": f"Public web {title}", "source_uri": uri},
        )
        assert failed.status_code == 200, failed.text
        failed_data = failed.json()["data"]
        assert failed_data["import_run"]["status"] == "failed"
        assert failed_data["import_run"]["error_code"] == code
        assert failed_data["collection_run"]["status"] == "failed"
        assert failed_data["raw_records"] == []
        assert failed_data["import_run"]["payload"]["fetch_activity"]["activity_name"] == "fetch_public_web_page"
        assert failed_data["import_run"]["payload"]["fetch_activity"]["error_code"] == code


def test_s2_public_web_link_discovery_generates_pending_urls_and_records_robots(monkeypatch) -> None:
    headers = _headers()
    prefix = _unique_name("S2 public web discovery")

    source_response = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} source",
            "source_type": "public_web",
            "policy": {"access_mode": "public_web", "base_url": "synthetic://xian/public-web"},
        },
    )
    assert source_response.status_code == 200, source_response.text
    source_id = source_response.json()["data"]["data_source_id"]

    crawl_policy = client.put(
        f"/api/v1/data-sources/{source_id}/crawl-policy",
        headers=headers,
        json={"start_url": "synthetic://xian/public-web/discovery-seed", "max_depth": 2, "respect_robots": True, "rate_limit_per_minute": 30},
    )
    assert crawl_policy.status_code == 200, crawl_policy.text

    discovery = client.post(
        f"/api/v1/data-sources/{source_id}/public-web/discover-links",
        headers=headers,
        json={"limit": 75, "reason": "AT-068 link discovery"},
    )
    assert discovery.status_code == 200, discovery.text
    data = discovery.json()["data"]
    assert data["activity"]["activity_name"] == "discover_public_web_links"
    assert data["activity"]["status"] == "completed"
    assert data["activity"]["discovered_count"] == 75
    assert data["collection_run"]["status"] == "completed"
    assert data["collection_run"]["record_count"] == 75
    assert data["collection_run"]["payload"]["activity_name"] == "discover_public_web_links"
    assert data["pending_urls"][0]["url"] == "synthetic://xian/public-web/discovery-seed"
    assert {item["depth"] for item in data["pending_urls"]} == {0, 1, 2}
    assert all(item["status"] == "pending" for item in data["pending_urls"])
    run_id = data["collection_run"]["collection_run_id"]
    workflow_run_id = data["collection_run"]["payload"]["workflow_run_id"]

    with Session(engine) as db:
        run = db.get(models.CollectionRun, run_id)
        assert run is not None
        assert len(run.payload["pending_urls"]) == 75
        events = [
            event.event_type
            for event in db.execute(select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run_id)).scalars()
        ]
        assert "discover_public_web_links_started" in events
        assert "discover_public_web_links_completed" in events
        workflow_events = [
            event.event_type
            for event in db.execute(select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow_run_id)).scalars()
        ]
        assert "activity_started" in workflow_events
        assert "activity_completed" in workflow_events
        policy = next(
            item
            for item in db.execute(select(models.SourcePolicy).where(models.SourcePolicy.data_source_id == source_id)).scalars()
            if "link_discovery" in (item.payload or {})
        )
        assert policy is not None
        assert policy.payload["link_discovery"]["activity_name"] == "discover_public_web_links"
        assert len(policy.payload["link_discovery"]["pending_urls"]) == 75

    robots = client.post(
        f"/api/v1/data-sources/{source_id}/public-web/discover-links",
        headers=headers,
        json={"start_url": "synthetic://xian/public-web/robots-deny", "max_depth": 2, "limit": 10, "respect_robots": True},
    )
    assert robots.status_code == 200, robots.text
    robots_data = robots.json()["data"]
    assert robots_data["activity"]["status"] == "completed"
    assert robots_data["activity"]["discovered_count"] == 0
    assert robots_data["activity"]["skipped_count"] == 1
    assert robots_data["pending_urls"] == []
    assert robots_data["skipped_urls"][0]["reason"] == "ROBOTS_DISALLOWED"

    live_source = client.post(
        "/api/v1/data-sources",
        headers=headers,
        json={
            "name": f"{prefix} live source",
            "source_type": "public_web",
            "policy": {"access_mode": "public_web", "base_url": "https://example.test"},
        },
    )
    assert live_source.status_code == 200, live_source.text
    live_source_id = live_source.json()["data"]["data_source_id"]

    def fake_fetch_public_web_page(_source, _request):
        return {
            "ok": True,
            "activity_name": "fetch_public_web_page",
            "classification": "html",
            "source_uri": "https://example.test/seed",
            "content_type": "text/html; charset=utf-8",
            "http_status_code": 200,
            "latency_ms": 1,
            "byte_size": 128,
            "content_hash": "sha256:test",
            "content": "<html><body><a href=\"/open-notice\">open</a><a href=\"/robots-deny-secret\">deny</a></body></html>",
            "is_synthetic": False,
            "truncated": False,
            "error_code": None,
            "error_message": None,
            "retryable": False,
        }

    monkeypatch.setattr(data_sources, "_fetch_public_web_page", fake_fetch_public_web_page)
    child_robots = client.post(
        f"/api/v1/data-sources/{live_source_id}/public-web/discover-links",
        headers=headers,
        json={"start_url": "https://example.test/seed", "max_depth": 1, "limit": 10, "respect_robots": True},
    )
    assert child_robots.status_code == 200, child_robots.text
    child_data = child_robots.json()["data"]
    assert {item["url"] for item in child_data["pending_urls"]} == {"https://example.test/seed", "https://example.test/open-notice"}
    assert child_data["activity"]["discovered_count"] == 2
    assert child_data["activity"]["skipped_count"] == 1
    assert child_data["skipped_urls"][0]["url"] == "https://example.test/robots-deny-secret"
    assert child_data["skipped_urls"][0]["reason"] == "ROBOTS_DISALLOWED"
