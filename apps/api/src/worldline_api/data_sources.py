from __future__ import annotations

import hashlib
import hmac
import csv
import io
import json
import posixpath
import re
import secrets
import socket
import time
import email.utils
import zipfile
import zlib
from importlib import import_module
import html as html_lib
import xml.etree.ElementTree as ElementTree
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .audit import write_audit
from . import adapters, models
from .config import settings
from .foundation import DEFAULT_TENANT_ID
from .policy import mask_sensitive_text, source_allowed

DATA_SOURCE_TYPES = [
    {"source_type": "synthetic", "label": "Synthetic", "requires_external_key": False},
    {"source_type": "manual", "label": "Manual entry", "requires_external_key": False},
    {"source_type": "manual_upload", "label": "Manual upload", "requires_external_key": False},
    {"source_type": "file_upload", "label": "File upload", "requires_external_key": False},
    {"source_type": "public_web", "label": "Public web", "requires_external_key": False},
    {"source_type": "official_api", "label": "Official API", "requires_external_key": True},
    {"source_type": "rss", "label": "RSS feed", "requires_external_key": False},
    {"source_type": "webhook", "label": "Webhook", "requires_external_key": False},
    {"source_type": "db_import", "label": "Database import", "requires_external_key": True},
    {"source_type": "object_storage", "label": "Object storage", "requires_external_key": True},
    {"source_type": "media", "label": "Image/video media", "requires_external_key": False},
    {"source_type": "live_segment", "label": "Live segment", "requires_external_key": False},
]

CLEAN_RECORD_MANUAL_STATUSES = {"valid", "invalid", "review_required"}
CLEAN_RECORD_SIGNAL_BLOCKING_STATUSES = {"invalid", "review_required"}

_WEBHOOK_SECRET_CACHE: dict[str, str] = {}
_WEBHOOK_SOURCE_CACHE: dict[str, str] = {}
MIN_COLLECTION_CRON_INTERVAL_MINUTES = 5
COLLECTION_RUN_STEPS = [
    {"step_key": "fetch", "label": "Fetch", "description": "Acquire source payload or scheduled work item."},
    {"step_key": "parse", "label": "Parse", "description": "Parse source payload into normalized candidate records."},
    {"step_key": "store", "label": "Store", "description": "Persist raw records, payloads, lineage, and run metadata."},
    {"step_key": "clean", "label": "Clean", "description": "Run normalization, deduplication, and quality checks."},
    {"step_key": "extract", "label": "Extract", "description": "Extract downstream signals, evidence refs, and business objects."},
]
COLLECTION_RUN_STEP_INDEX = {step["step_key"]: index for index, step in enumerate(COLLECTION_RUN_STEPS)}
COLLECTION_WORKFLOW_CASE_ID = "CASE-S2-COLLECTION"
PUBLIC_WEB_FETCH_ACTIVITY_NAME = "fetch_public_web_page"
PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME = "discover_public_web_links"
OFFICIAL_API_FETCH_ACTIVITY_NAME = "fetch_official_api_page"
RSS_FETCH_ACTIVITY_NAME = "fetch_rss_items"
DB_IMPORT_SCAN_ACTIVITY_NAME = "scan_db_import_table"
OBJECT_STORAGE_SCAN_ACTIVITY_NAME = "scan_object_storage_prefix"
RAW_RECORD_REPOSITORY_ACTIVITY_NAME = "raw_record_repository_store"
HTML_MAIN_CONTENT_PARSER_NAME = "parse_html_main_content"
HTML_MAIN_CONTENT_PARSER_VERSION = "parse_html_main_content-v1.0"
JSON_BY_MAPPING_PARSER_NAME = "parse_json_by_mapping"
JSON_BY_MAPPING_PARSER_VERSION = "parse_json_by_mapping-v1.0"
RSS_ITEM_PARSER_NAME = "parse_rss_item"
RSS_ITEM_PARSER_VERSION = "parse_rss_item-v1.0"
CSV_FILE_PARSER_NAME = "parse_csv_file"
CSV_FILE_PARSER_VERSION = "parse_csv_file-v1.0"
XLSX_FILE_PARSER_NAME = "parse_xlsx_file"
XLSX_FILE_PARSER_VERSION = "parse_xlsx_file-v1.0"
PDF_TEXT_PARSER_NAME = "parse_pdf_text"
PDF_TEXT_PARSER_VERSION = "parse_pdf_text-v1.0"
DOCX_TEXT_PARSER_NAME = "parse_docx_text"
DOCX_TEXT_PARSER_VERSION = "parse_docx_text-v1.0"
MANUAL_RECORD_VALIDATOR_NAME = "validate_manual_record"
MANUAL_RECORD_VALIDATOR_VERSION = "validate_manual_record-v1.0"
NORMALIZE_TEXT_CLEANER_NAME = "normalize_text"
NORMALIZE_TEXT_CLEANER_VERSION = "normalize_text-v1.0"
NORMALIZE_DATETIME_CLEANER_NAME = "normalize_datetime"
NORMALIZE_DATETIME_CLEANER_VERSION = "normalize_datetime-v1.0"
NORMALIZE_LOCATION_CLEANER_NAME = "normalize_location"
NORMALIZE_LOCATION_CLEANER_VERSION = "normalize_location-v1.0"
ASSIGN_SOURCE_TRUST_CLEANER_NAME = "assign_source_trust"
ASSIGN_SOURCE_TRUST_CLEANER_VERSION = "assign_source_trust-v1.0"
DETECT_SENSITIVE_FIELDS_NAME = "detect_sensitive_fields"
DETECT_SENSITIVE_FIELDS_VERSION = "detect_sensitive_fields-v1.0"
REDACT_SENSITIVE_FIELDS_NAME = "redact_sensitive_fields"
REDACT_SENSITIVE_FIELDS_VERSION = "redact_sensitive_fields-v1.0"
DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME = "dedupe_by_hash_and_external_id"
DEDUPE_BY_HASH_AND_EXTERNAL_ID_VERSION = "dedupe_by_hash_and_external_id-v1.0"
SEMANTIC_DEDUPE_RECORDS_NAME = "semantic_dedupe_records"
SEMANTIC_DEDUPE_RECORDS_VERSION = "semantic_dedupe_records-v1.0"
SCORE_CLEAN_RECORD_QUALITY_NAME = "score_clean_record_quality"
SCORE_CLEAN_RECORD_QUALITY_VERSION = "score_clean_record_quality-v1.0"
SQL_IN_CHUNK_SIZE = 10000
SEMANTIC_DEDUPE_PROVIDER = "synthetic_deterministic_shingle"
PUBLIC_WEB_FETCH_TIMEOUT_SECONDS = 8
PUBLIC_WEB_FETCH_MAX_BYTES = 1_000_000
RSS_FETCH_MAX_BYTES = 5_000_000
FILE_UPLOAD_INLINE_MAX_BYTES = 1_000_000
FILE_UPLOAD_VIRUS_SIGNATURES = (
    b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE",
    b"X5O!P%@AP",
)
FILE_UPLOAD_MIME_TYPES = {
    "csv": "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
SOURCE_TRUST_DEFAULTS = {
    "official_api": 0.86,
    "db_import": 0.8,
    "object_storage": 0.78,
    "webhook": 0.74,
    "rss": 0.72,
    "public_web": 0.7,
    "live_segment": 0.68,
    "file_upload": 0.66,
    "media": 0.64,
    "manual_upload": 0.62,
    "manual": 0.62,
    "synthetic": 0.5,
}
SOURCE_TRUST_FALLBACK = 0.55
SENSITIVE_DETECTOR_PATTERNS = [
    ("minor_name", re.compile(r"minor name:?\s*[A-Za-z\u4e00-\u9fff]{1,12}", re.IGNORECASE), "restricted"),
    ("class_ref", re.compile(r"\bclass\s*\d+[-\w]*\b", re.IGNORECASE), "restricted"),
    ("phone", re.compile(r"\b1[3-9]\d{9}\b"), "restricted"),
    ("id_card", re.compile(r"\b\d{17}[\dXx]\b"), "sensitive"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "restricted"),
]


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def _hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_access_mode(source_type: str) -> str:
    return {
        "synthetic": "test_fixture",
        "manual": "manual_upload",
        "manual_upload": "manual_upload",
        "file_upload": "manual_upload",
        "public_web": "public_web",
        "official_api": "official_api",
        "rss": "public_web",
        "webhook": "authorized_export",
        "db_import": "authorized_export",
        "object_storage": "authorized_export",
        "media": "authorized_export",
        "live_segment": "authorized_export",
    }[source_type]


def _api_error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})


def evaluate_policy(source_type: str, policy: dict, status: str = "active") -> dict:
    access_mode = str(policy.get("access_mode") or _default_access_mode(source_type))
    auth = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
    compliance_state = _compliance_state(policy)
    if source_type == "official_api" and not (policy.get("api_key_ref") or policy.get("secret_ref") or auth.get("secret_ref")):
        return {"allowed": False, "reason": "official_api_key_missing", "access_mode": access_mode, **compliance_state}
    if source_type in {"db_import", "object_storage"} and not policy.get("secret_ref"):
        return {"allowed": False, "reason": f"{source_type}_secret_ref_missing", "access_mode": access_mode, **compliance_state}
    allowed, reason = source_allowed(access_mode, status)
    return {"allowed": allowed, "reason": reason, "access_mode": access_mode, **compliance_state}


def create_data_source(session: Session, request, actor: models.User, trace_id: str) -> dict:
    duplicate = session.execute(
        select(models.DataSource).where(models.DataSource.tenant_id == actor.tenant_id, models.DataSource.name == request.name)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise _api_error(409, "DATA_SOURCE_DUPLICATE", "A data source with this name already exists in the tenant.")
    if request.source_type == "official_api":
        _validate_official_api_policy(request.policy)
    if request.source_type == "rss":
        _validate_rss_policy(request.policy)
    if request.source_type == "file_upload":
        _validate_file_upload_policy(request.policy)
    if request.source_type == "media":
        _validate_media_policy(request.policy)
    if request.source_type == "live_segment":
        _validate_live_segment_policy(request.policy)
    if request.source_type == "manual":
        _validate_manual_source_policy(request.policy)
    webhook_secret_once = None
    if request.source_type == "webhook":
        webhook_secret_once = _prepare_webhook_policy(session, actor.tenant_id, request.policy)
    if request.source_type == "db_import":
        _validate_db_import_policy(request.policy)
    if request.source_type == "object_storage":
        _validate_object_storage_policy(request.policy)
    policy_result = evaluate_policy(request.source_type, request.policy)
    source = models.DataSource(
        id=_id("DS"),
        tenant_id=actor.tenant_id,
        name=request.name,
        source_type=request.source_type,
        status="active" if policy_result["allowed"] else "blocked",
        is_synthetic=request.source_type == "synthetic" or _policy_is_synthetic(request.policy),
        policy={**request.policy, "policy_result": policy_result},
        payload=request.payload,
    )
    session.add(source)
    session.flush()
    if request.source_type == "webhook":
        webhook = _webhook_policy(source)
        source_key = webhook.get("source_key")
        if isinstance(source_key, str) and source_key:
            _WEBHOOK_SOURCE_CACHE[source_key] = source.id
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload=policy_result,
        )
    )
    session.add(
        models.SourceHealth(
            id=_id("SH"),
            data_source_id=source.id,
            status="healthy" if policy_result["allowed"] else "blocked",
            payload={"synthetic": source.is_synthetic},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.create",
        object_type="data_source",
        object_id=source.id,
        after=serialize_data_source(source),
        trace_id=trace_id,
    )
    session.commit()
    result = serialize_data_source(source)
    if webhook_secret_once:
        result["webhook_secret_once"] = webhook_secret_once
    return result


def list_data_sources(
    session: Session,
    tenant_id: str,
    source_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], dict]:
    allowed_statuses = {"draft", "active", "disabled", "paused", "blocked", "archived"}
    if status and status not in allowed_statuses:
        raise _api_error(422, "DATA_SOURCE_STATUS_INVALID", "Unsupported data source status filter.")
    if source_type and source_type not in {item["source_type"] for item in DATA_SOURCE_TYPES}:
        raise _api_error(422, "DATA_SOURCE_TYPE_INVALID", "Unsupported data source type filter.")
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [models.DataSource.tenant_id == tenant_id]
    if source_type:
        filters.append(models.DataSource.source_type == source_type)
    if status:
        filters.append(models.DataSource.status == status)
    total = session.execute(select(func.count()).select_from(models.DataSource).where(*filters)).scalar_one()
    rows = session.execute(
        select(models.DataSource)
        .where(*filters)
        .order_by(models.DataSource.created_at.desc(), models.DataSource.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    meta = {"pagination": {"page": page, "page_size": page_size, "total": total}}
    return [serialize_data_source(row) for row in rows], meta


def get_data_source(session: Session, data_source_id: str) -> models.DataSource:
    source = session.get(models.DataSource, data_source_id)
    if source is None:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    return source


def update_data_source(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    before = serialize_data_source(source)
    policy = request.config if hasattr(request, "config") else request.policy
    payload = request.config if hasattr(request, "config") else request.payload
    if request.source_type == "official_api":
        _validate_official_api_policy(policy)
    if request.source_type == "rss":
        _validate_rss_policy(policy)
    if request.source_type == "file_upload":
        _validate_file_upload_policy(policy)
    if request.source_type == "media":
        _validate_media_policy(policy)
    if request.source_type == "live_segment":
        _validate_live_segment_policy(policy)
    if request.source_type == "webhook":
        _prepare_webhook_policy(session, source.tenant_id, policy, existing_source_id=source.id)
    if request.source_type == "db_import":
        _validate_db_import_policy(policy)
    if request.source_type == "object_storage":
        _validate_object_storage_policy(policy)
    policy_result = evaluate_policy(request.source_type, policy)
    source.name = request.name
    source.source_type = request.source_type
    source.status = "active" if policy_result["allowed"] else "blocked"
    source.is_synthetic = request.source_type == "synthetic" or _policy_is_synthetic(policy)
    source.policy = {**policy, "policy_result": policy_result}
    source.payload = payload
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload=policy_result,
        )
    )
    _update_health(session, source.id, None, success=policy_result["allowed"], error_code=policy_result["reason"])
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def policy_check(session: Session, data_source_id: str, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    result = evaluate_policy(source.source_type, source.policy, source.status)
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if result["allowed"] else "block",
            reason=result["reason"],
            payload=result,
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.policy_check",
        object_type="data_source",
        object_id=source.id,
        after=result,
        trace_id=trace_id,
    )
    session.commit()
    return result


def validate_source_url(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    result = _validate_url(request.url)
    before = serialize_data_source(source)
    policy = dict(source.policy or {})
    policy["url_validation"] = result
    source.policy = policy
    _update_health(session, source.id, None, success=result["reachable"], error_code=result.get("error_code"))
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if result["reachable"] else "needs_review",
            reason=result.get("error_code"),
            payload={"url_validation": result},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.validate_url",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after={"url_validation": result},
        trace_id=trace_id,
    )
    session.commit()
    return result


def update_crawl_policy(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.source_type not in {"public_web", "rss"}:
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_CRAWL_POLICY", "Crawl policy is only valid for public_web and rss sources.")
    validation = _validate_url(request.start_url, network=False)
    if not validation["reachable"]:
        raise _api_error(422, validation.get("error_code") or "URL_NOT_REACHABLE", "Crawl policy start_url is not acceptable.")
    before = serialize_data_source(source)
    crawl_policy = {
        "start_url": request.start_url,
        "max_depth": request.max_depth,
        "respect_robots": request.respect_robots,
        "rate_limit_per_minute": request.rate_limit_per_minute,
        "allowed_domains": request.allowed_domains,
    }
    policy = dict(source.policy or {})
    policy["crawl_policy"] = crawl_policy
    policy["url_validation"] = validation
    policy_result = evaluate_policy(source.source_type, policy, "active")
    policy["policy_result"] = policy_result
    source.policy = policy
    source.status = "active" if policy_result["allowed"] else "blocked"
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload={"crawl_policy": crawl_policy, "policy_result": policy_result, "reason": request.reason},
        )
    )
    _update_health(session, source.id, None, success=policy_result["allowed"], error_code=policy_result["reason"])
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.crawl_policy.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def discover_public_web_links(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.source_type != "public_web":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_LINK_DISCOVERY", "Public web link discovery is only valid for public_web data sources.")
    policy = dict(source.policy or {})
    crawl_policy = policy.get("crawl_policy") if isinstance(policy.get("crawl_policy"), dict) else {}
    start_url = request.start_url or crawl_policy.get("start_url") or policy.get("base_url")
    if not isinstance(start_url, str) or not start_url.strip():
        raise _api_error(422, "PUBLIC_WEB_START_URL_REQUIRED", "Public web link discovery requires start_url or a saved crawl policy.")
    max_depth = request.max_depth if request.max_depth is not None else int(crawl_policy.get("max_depth") or 1)
    respect_robots = request.respect_robots if request.respect_robots is not None else bool(crawl_policy.get("respect_robots", True))
    allowed_domains = request.allowed_domains or list(crawl_policy.get("allowed_domains") or [])
    policy_result = evaluate_policy(source.source_type, policy, source.status)

    _ensure_collection_workflow_case(session)
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        name="public_web link discovery",
        status="active" if policy_result["allowed"] else "blocked",
        schedule=None,
        payload={"activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "start_url": start_url, "max_depth": max_depth, "limit": request.limit},
    )
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"DiscoverPublicWebLinksWorkflow-{run_id}"
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="running",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload={
            "activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME,
            "workflow_run_id": workflow_run_id,
            "workflow_name": "DiscoverPublicWebLinksWorkflow",
            "workflow_id": workflow_id,
            "workflow_status": "running",
            "start_url": start_url,
            "max_depth": max_depth,
            "respect_robots": respect_robots,
            "limit": request.limit,
        },
    )
    workflow = models.WorkflowRun(
        id=workflow_run_id,
        case_id=COLLECTION_WORKFLOW_CASE_ID,
        tenant_id=actor.tenant_id,
        workflow_name="DiscoverPublicWebLinksWorkflow",
        workflow_id=workflow_id,
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload={
            "collection_run_id": run.id,
            "data_source_id": source.id,
            "activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME,
            "input_hash": _hash(json.dumps({"data_source_id": source.id, "start_url": start_url, "max_depth": max_depth, "limit": request.limit}, sort_keys=True, ensure_ascii=True)),
        },
    )
    session.add(job)
    session.add(run)
    session.add(workflow)
    started_payload = {"activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "start_url": start_url, "max_depth": max_depth, "limit": request.limit, "step_key": "fetch"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="discover_public_web_links_started", status="running", payload=started_payload, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=started_payload | {"collection_run_id": run.id}, created_at=_now()))
    session.flush()

    if not policy_result["allowed"]:
        code = policy_result["reason"] or "SOURCE_POLICY_BLOCKED"
        message = "Source policy blocks public web link discovery."
        run.status = "failed"
        run.error_code = code
        run.error_message = message
        workflow.status = "failed"
        workflow.payload = {**(workflow.payload or {}), "error_code": code}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="discover_public_web_links_failed", status="failed", payload={"activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "error_code": code, "step_key": "fetch"}, created_at=_now()))
        session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload={"collection_run_id": run.id, "activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "error_code": code, "step_key": "fetch"}, created_at=_now()))
        _update_health(session, source.id, run.id, success=False, error_code=code)
        session.commit()
        return {"data_source": serialize_data_source(source), "collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "activity": {"activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "status": "failed", "error_code": code, "discovered_count": 0, "skipped_count": 0}, "pending_urls": [], "skipped_urls": []}

    result = _discover_public_web_links(source, start_url, max_depth, request.limit, respect_robots, allowed_domains)
    pending_urls = result["pending_urls"]
    skipped_urls = result["skipped_urls"]
    activity = {
        "activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME,
        "status": "completed",
        "start_url": start_url,
        "max_depth": max_depth,
        "limit": request.limit,
        "respect_robots": respect_robots,
        "allowed_domains": allowed_domains,
        "is_synthetic": result["is_synthetic"],
        "discovered_count": len(pending_urls),
        "skipped_count": len(skipped_urls),
        "latency_ms": result["latency_ms"],
    }
    run.status = "completed"
    run.record_count = len(pending_urls)
    run.payload = {**(run.payload or {}), "workflow_status": "completed", "pending_urls": pending_urls, "skipped_urls": skipped_urls, "activity": activity}
    workflow.status = "completed"
    workflow.payload = {**(workflow.payload or {}), "activity": activity, "pending_url_count": len(pending_urls), "skipped_url_count": len(skipped_urls)}
    if skipped_urls:
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="robots_disallowed", status="completed", payload={"activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME, "skipped_urls": skipped_urls, "step_key": "fetch"}, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="discover_public_web_links_completed", status="completed", payload=activity | {"step_key": "fetch"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
    policy["last_link_discovery"] = {
        "collection_run_id": run.id,
        "activity_name": PUBLIC_WEB_LINK_DISCOVERY_ACTIVITY_NAME,
        "discovered_count": len(pending_urls),
        "skipped_count": len(skipped_urls),
        "sample_pending_urls": pending_urls[:10],
        "sample_skipped_urls": skipped_urls[:10],
    }
    source.policy = policy
    flag_modified(source, "policy")
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow",
            reason=None,
            payload={"link_discovery": activity | {"pending_urls": pending_urls, "skipped_urls": skipped_urls}},
        )
    )
    _update_health(session, source.id, run.id, success=True, count=len(pending_urls))
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.public_web_links.discovered",
        object_type="collection_run",
        object_id=run.id,
        after={"data_source_id": source.id, "activity": activity},
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return {
        "data_source": serialize_data_source(source),
        "collection_job": serialize_collection_job(job),
        "collection_run": serialize_collection_run(run),
        "activity": activity,
        "pending_urls": pending_urls,
        "skipped_urls": skipped_urls,
    }


def update_source_auth(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = _official_api_source(session, data_source_id)
    before = serialize_data_source(source)
    policy = dict(source.policy or {})
    auth = {
        "auth_type": request.auth_type,
        "secret_ref": request.secret_ref,
        "header_name": request.header_name,
        "token_url": request.token_url,
    }
    policy["auth"] = {key: value for key, value in auth.items() if value is not None}
    policy["secret_ref"] = request.secret_ref
    policy_result = evaluate_policy(source.source_type, policy, "active")
    policy["policy_result"] = policy_result
    source.policy = policy
    source.status = "active" if policy_result["allowed"] else "blocked"
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload={"auth": policy["auth"], "policy_result": policy_result},
        )
    )
    _update_health(session, source.id, None, success=policy_result["allowed"], error_code=policy_result["reason"])
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.auth.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def test_official_api_connection(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.source_type not in {"official_api", "db_import", "object_storage"}:
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_CONNECTION_TEST", "Connection tests are valid for official_api, db_import, and object_storage data sources.")
    policy = dict(source.policy or {})
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    if not policy_result["allowed"]:
        result = {
            "status": "failed",
            "classification": policy_result["reason"] or "source_policy_blocked",
            "status_code": None,
            "latency_ms": 0,
            "is_synthetic": source.is_synthetic,
            "sample_metadata": {"sample_path": request.sample_path, "expected_status": request.expected_status},
        }
    else:
        _validate_official_api_policy(policy)
        if source.source_type == "db_import":
            result = _synthetic_db_connection_result(policy, request)
        elif source.source_type == "object_storage":
            result = _synthetic_object_connection_result(policy, request)
        else:
            base_url = _official_api_base_url(policy)
            if base_url and urlparse(base_url).scheme == "synthetic":
                result = {
                    "status": "ok",
                    "classification": "ok",
                    "status_code": request.expected_status,
                    "latency_ms": 1,
                    "is_synthetic": True,
                    "sample_metadata": {
                        "base_url": base_url,
                        "sample_path": request.sample_path,
                        "sample_record_count": 3,
                        "adapter": "synthetic_official_api",
                    },
                }
            else:
                validation = _validate_url(_compose_test_url(base_url, request.sample_path), network=True)
                classification = _classify_connection(validation.get("status_code"), validation.get("reachable", False))
                result = {
                    "status": "ok" if classification == "ok" else "failed",
                    "classification": classification,
                    "status_code": validation.get("status_code"),
                    "latency_ms": validation.get("latency_ms", 0),
                    "is_synthetic": False,
                    "sample_metadata": {
                        "base_url": base_url,
                        "sample_path": request.sample_path,
                        "content_type": validation.get("content_type"),
                        "validation_mode": validation.get("validation_mode"),
                        "error_code": validation.get("error_code"),
                    },
                }
    before = serialize_data_source(source)
    policy["last_connection_test"] = result
    source.policy = policy
    _update_health(session, source.id, None, success=result["status"] == "ok", error_code=result["classification"])
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if result["status"] == "ok" else "needs_review",
            reason=result["classification"],
            payload={"connection_test": result},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.connection_test",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after={"connection_test": result},
        trace_id=trace_id,
    )
    session.commit()
    return result


def update_pagination_policy(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = _official_api_source(session, data_source_id)
    if request.strategy == "next_url" and not request.next_url_path:
        raise _api_error(422, "PAGINATION_NEXT_URL_PATH_MISSING", "next_url pagination requires next_url_path.")
    before = serialize_data_source(source)
    pagination = {
        "strategy": request.strategy,
        "page_param": request.page_param,
        "page_size_param": request.page_size_param,
        "cursor_param": request.cursor_param,
        "next_url_path": request.next_url_path,
        "max_pages": request.max_pages,
    }
    policy = dict(source.policy or {})
    policy["pagination"] = {key: value for key, value in pagination.items() if value is not None}
    if request.dry_run:
        policy["pagination_dry_run"] = {
            "status": "ok",
            "strategy": request.strategy,
            "page_count": request.max_pages,
            "is_synthetic": source.is_synthetic or _policy_is_synthetic(policy),
            "duration_ms": min(request.max_pages * 5, 250),
        }
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    policy["policy_result"] = policy_result
    source.policy = policy
    source.status = "active" if policy_result["allowed"] else "blocked"
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload={"pagination": policy["pagination"], "pagination_dry_run": policy.get("pagination_dry_run")},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.pagination.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def inspect_rss_feed(session: Session, data_source_id: str, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.source_type != "rss":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_RSS", "RSS inspect is only valid for rss data sources.")
    before = serialize_data_source(source)
    policy = dict(source.policy or {})
    metadata = _inspect_rss_feed(policy, network=True)
    policy["rss_inspection"] = metadata
    policy_result = evaluate_policy(source.source_type, policy, "active")
    policy["policy_result"] = policy_result
    source.policy = policy
    source.status = "active" if policy_result["allowed"] else "blocked"
    source.is_synthetic = source.is_synthetic or metadata["is_synthetic"]
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason=policy_result["reason"],
            payload={"rss_inspection": metadata},
        )
    )
    _update_health(session, source.id, None, success=True, error_code=None)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.rss.inspect",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after={"rss_inspection": metadata},
        trace_id=trace_id,
    )
    session.commit()
    return metadata


def receive_webhook_payload(
    session: Session,
    source_key: str,
    raw_body: bytes,
    headers: dict[str, str | None],
    trace_id: str,
) -> dict:
    source = _webhook_source_by_key(session, source_key)
    webhook = _webhook_policy(source)
    delivery_id = headers.get("x-cet-delivery-id")
    timestamp = headers.get("x-cet-timestamp")
    signature = headers.get("x-cet-signature")
    if not delivery_id:
        raise _api_error(401, "WEBHOOK_DELIVERY_ID_REQUIRED", "Webhook delivery id is required.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled webhook sources cannot receive payloads.")
    _verify_webhook_timestamp(timestamp, webhook.get("accepted_window_seconds", 300))
    _verify_webhook_signature(source_key, timestamp or "", raw_body, signature)
    if _webhook_delivery_exists(session, source.id, delivery_id):
        raise _api_error(409, "WEBHOOK_REPLAY_DETECTED", "Webhook delivery was already processed.")
    payload = _parse_webhook_payload(raw_body)
    _validate_webhook_payload_schema(source.policy or {}, payload)
    request_id = str(payload.get("request_id") or "").strip()
    dedupe_key = _webhook_request_dedupe_key(request_id, delivery_id)
    existing_request = session.execute(
        select(models.RawRecord).where(models.RawRecord.data_source_id == source.id, models.RawRecord.source_type == "webhook", models.RawRecord.dedupe_key == dedupe_key).limit(1)
    ).scalar_one_or_none()
    if existing_request is not None:
        raise _api_error(409, "WEBHOOK_REQUEST_ID_DUPLICATE", "Webhook request_id was already processed.")
    content = str(payload.get("content") or payload.get("text") or raw_body.decode("utf-8", errors="replace"))
    title = str(payload.get("title") or f"Webhook delivery {delivery_id}")[:240]
    is_synthetic = bool(payload.get("is_synthetic") or payload.get("synthetic") or source.is_synthetic)
    delivery_key = _webhook_delivery_key(delivery_id)
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        name=f"webhook delivery {delivery_id}",
        status="completed",
        schedule=None,
        payload={"source_key": source_key, "delivery_id": delivery_id},
    )
    session.add(job)
    session.flush()
    run = models.CollectionRun(
        id=_id("CRUN"),
        collection_job_id=job.id,
        data_source_id=source.id,
        status="completed",
        record_count=1,
        created_at=_now(),
        trace_id=trace_id,
        payload={"source_key": source_key, "delivery_id": delivery_id},
    )
    session.add(run)
    session.flush()
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type=source.source_type,
        title=title,
        content_hash=_hash(content),
        dedupe_key=dedupe_key,
        webhook_delivery_key=delivery_key,
        status="collected",
        is_synthetic=is_synthetic,
        city_id=str(payload.get("city_id") or "xian"),
        occurred_at=datetime.utcnow(),
        payload={
            "delivery_id": delivery_id,
            "source_key": source_key,
            "request_id": request_id or None,
            "dedupe_key": dedupe_key,
            "webhook_delivery_key": delivery_key,
            "synthetic": is_synthetic,
            "source_flags": {"synthetic": is_synthetic, "import_type": "webhook"},
            "payload": payload,
        },
    )
    session.add(record)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        conflict_code = "WEBHOOK_REPLAY_DETECTED" if _webhook_delivery_exists(session, source.id, delivery_id) else "WEBHOOK_REQUEST_ID_DUPLICATE"
        message = "Webhook delivery was already processed." if conflict_code == "WEBHOOK_REPLAY_DETECTED" else "Webhook request_id was already processed."
        raise _api_error(409, conflict_code, message) from exc
    session.add(models.RawRecordPayload(id=_id("RAWP"), raw_record_id=record.id, content_text=content, masked_text=mask_sensitive_text(content), payload={"delivery_id": delivery_id, "synthetic": is_synthetic}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="webhook_received_from", is_synthetic=is_synthetic, payload={"delivery_id": delivery_id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"delivery_id": delivery_id}))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="webhook_received", status="completed", payload={"delivery_id": delivery_id, "record_count": 1, "step_key": "store"}))
    write_audit(
        session,
        tenant_id=source.tenant_id,
        actor="webhook",
        actor_id=None,
        action="webhook.payload.received",
        object_type="raw_record",
        object_id=record.id,
        after={"data_source_id": source.id, "delivery_id": delivery_id, "request_id": request_id or None, "raw_record_id": record.id, "synthetic": is_synthetic},
        trace_id=trace_id,
    )
    session.commit()
    return {
        "status": "received",
        "delivery_id": delivery_id,
        "data_source_id": source.id,
        "collection_run": serialize_collection_run(run),
        "raw_record": serialize_raw_record(record),
    }


def list_object_storage_keys(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.source_type != "object_storage":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_OBJECT_STORAGE", "Object storage list is only valid for object_storage data sources.")
    policy = dict(source.policy or {})
    _validate_object_storage_policy(policy)
    if policy.get("permission_mode") == "deny":
        _update_health(session, source.id, None, success=False, error_code="OBJECT_STORAGE_BUCKET_FORBIDDEN")
        session.commit()
        raise _api_error(403, "OBJECT_STORAGE_BUCKET_FORBIDDEN", "Object storage bucket permissions deny listing keys.")
    max_keys = request.max_keys
    prefix = request.prefix if request.prefix is not None else str(policy.get("prefix") or "")
    keys = [f"{prefix.rstrip('/')}/synthetic-object-{index:04d}.json".lstrip("/") for index in range(max_keys)]
    result = {
        "status": "ok",
        "bucket": policy["bucket"],
        "prefix": prefix,
        "key_count": len(keys),
        "keys": keys,
        "is_synthetic": bool(policy.get("is_synthetic") or source.is_synthetic),
        "latency_ms": min(max_keys, 1000),
    }
    before = serialize_data_source(source)
    policy["last_object_storage_list"] = {key: value for key, value in result.items() if key != "keys"} | {"sample_keys": keys[:5]}
    source.policy = policy
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow",
            reason="ok",
            payload={"object_storage_list": policy["last_object_storage_list"]},
        )
    )
    _update_health(session, source.id, None, success=True, count=len(keys), error_code=None)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.object_storage.list",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=policy["last_object_storage_list"],
        trace_id=trace_id,
    )
    session.commit()
    return result


def scan_object_storage_prefix(session: Session, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, request.data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.source_type != "object_storage":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_OBJECT_STORAGE_SCAN", "Object storage scans require an object_storage data source.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot start object storage scans.")
    policy = dict(source.policy or {})
    _validate_object_storage_policy(policy)

    job, run, import_run, workflow = _create_object_storage_scan_ledgers(session, source, request, actor, trace_id)
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    if source.status != "active" or not policy_result["allowed"]:
        code = policy_result["reason"] or "DATA_SOURCE_POLICY_BLOCKED"
        _fail_object_storage_scan(session, source, run, import_run, workflow, code, "Source policy blocks object storage scans.", retryable=False)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="object_storage.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "file_objects": [], "raw_records": []}

    if policy.get("permission_mode") == "deny":
        _fail_object_storage_scan(session, source, run, import_run, workflow, "OBJECT_STORAGE_BUCKET_FORBIDDEN", "Object storage bucket permissions deny scanning keys.", retryable=False)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="object_storage.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), reason=getattr(request, "reason", None), trace_id=trace_id)
        session.commit()
        raise _api_error(403, "OBJECT_STORAGE_BUCKET_FORBIDDEN", "Object storage bucket permissions deny scanning keys.")

    scan_prefix = request.prefix if request.prefix is not None else str(policy.get("prefix") or "")
    started = time.perf_counter()
    is_synthetic = bool(source.is_synthetic or policy.get("is_synthetic") or str(scan_prefix).startswith("synthetic/") or str(scan_prefix).startswith("synthetic://"))
    started_payload = {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "bucket": policy.get("bucket"), "prefix": scan_prefix, "limit": request.limit, "step_key": "fetch"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_object_storage_prefix_started", status="running", payload=started_payload, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=started_payload | {"collection_run_id": run.id}, created_at=_now()))

    keys = _object_storage_scan_keys(policy, scan_prefix, request.limit)
    missing_keys = _object_storage_missing_keys(policy, keys)
    present_keys = [key for key in keys if key not in missing_keys]
    existing_dedupe_keys = _existing_object_storage_dedupe_keys(session, source.id, policy["bucket"], present_keys)
    new_keys = [key for key in present_keys if _object_storage_dedupe_key(source.id, policy["bucket"], key) not in existing_dedupe_keys]
    skipped_existing_count = len(present_keys) - len(new_keys)

    response = _bulk_insert_object_storage_records(session, source, run, import_run, request, policy, scan_prefix, new_keys, is_synthetic)
    new_record_count = len(new_keys)
    missing_count = len(missing_keys)
    key_count = len(keys)
    if key_count and missing_count == key_count:
        _fail_object_storage_scan(session, source, run, import_run, workflow, "OBJECT_STORAGE_FILE_MISSING", "All listed object storage files disappeared before fetch.", retryable=True)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="object_storage.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), reason=getattr(request, "reason", None), trace_id=trace_id)
        session.commit()
        return {"collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "file_objects": [], "raw_records": []}

    latency_ms = int((time.perf_counter() - started) * 1000)
    classification = "partial_missing" if missing_count else "files"
    activity = {
        "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME,
        "classification": classification,
        "bucket": policy.get("bucket"),
        "prefix": scan_prefix,
        "key_count": key_count,
        "new_record_count": new_record_count,
        "raw_record_count": new_record_count,
        "file_object_count": new_record_count,
        "skipped_existing_count": skipped_existing_count,
        "missing_count": missing_count,
        "missing_keys_sample": missing_keys[:10],
        "response_record_count": len(response["raw_records"]),
        "is_synthetic": is_synthetic,
        "latency_ms": latency_ms,
        "retryable": False,
    }
    run.status = "completed"
    run.record_count = new_record_count
    run.payload = {**(run.payload or {}), "workflow_status": "completed", "object_storage_activity": activity}
    workflow.status = "completed"
    workflow.payload = {**(workflow.payload or {}), "status": "completed", "object_storage_activity": activity, "raw_record_count": new_record_count}
    import_run.status = "completed"
    import_run.record_count = new_record_count
    import_run.is_synthetic = is_synthetic
    import_run.payload = {**(import_run.payload or {}), "object_storage_activity": activity}
    policy["last_object_storage_scan"] = {
        "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME,
        "bucket": policy.get("bucket"),
        "prefix": scan_prefix,
        "key_count": key_count,
        "new_record_count": new_record_count,
        "skipped_existing_count": skipped_existing_count,
        "missing_count": missing_count,
        "latency_ms": latency_ms,
        "is_synthetic": is_synthetic,
    }
    source.policy = policy
    flag_modified(source, "policy")
    if missing_count:
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_object_storage_prefix_missing", status="warning", payload=activity | {"step_key": "fetch"}, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_object_storage_prefix_completed", status="completed", payload=activity | {"step_key": "store"}, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": "object_storage", "record_count": new_record_count, "missing_count": missing_count, "step_key": "store"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=activity | {"collection_run_id": run.id, "step_key": "store"}, created_at=_now()))
    session.add(models.SourcePolicy(id=_id("SPOL"), data_source_id=source.id, status="allow", reason=classification, payload={"object_storage_scan": activity}))
    _update_health(session, source.id, run.id, success=True, count=new_record_count)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="object_storage.scan.completed",
        object_type="import_run",
        object_id=import_run.id,
        after={"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "object_storage_activity": activity},
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return {
        "collection_job": serialize_collection_job(job),
        "collection_run": serialize_collection_run(run),
        "import_run": serialize_import_run(import_run),
        "file_objects": response["file_objects"],
        "raw_records": response["raw_records"],
    }


def scan_db_import_table(session: Session, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, request.data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.source_type != "db_import":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_DB_IMPORT_SCAN", "DB import scans require a db_import data source.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot start DB import scans.")
    policy = dict(source.policy or {})
    _validate_db_import_policy(policy)

    job, run, import_run, workflow = _create_db_import_scan_ledgers(session, source, request, actor, trace_id)
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    if source.status != "active" or not policy_result["allowed"]:
        code = policy_result["reason"] or "DATA_SOURCE_POLICY_BLOCKED"
        _fail_db_import_scan(session, source, run, import_run, workflow, code, "Source policy blocks DB import scans.", retryable=False)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="db_import.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "raw_records": []}

    if policy.get("permission_mode") == "deny":
        _fail_db_import_scan(session, source, run, import_run, workflow, "DB_IMPORT_PERMISSION_DENIED", "DB import credentials do not have table scan permission.", retryable=False)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="db_import.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), reason=getattr(request, "reason", None), trace_id=trace_id)
        session.commit()
        raise _api_error(403, "DB_IMPORT_PERMISSION_DENIED", "DB import credentials do not have table scan permission.")

    if policy.get("connection_mode") == "fail" or str(policy.get("connection_ref") or "").endswith("/unavailable"):
        _fail_db_import_scan(session, source, run, import_run, workflow, "DB_IMPORT_CONNECTION_FAILED", "DB import connection failed during table scan.", retryable=True)
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="db_import.scan.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), reason=getattr(request, "reason", None), trace_id=trace_id)
        session.commit()
        return {"collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "raw_records": []}

    table_key = _db_import_table_key(request)
    start_cursor = _db_import_start_cursor(policy, table_key, request)
    started = time.perf_counter()
    is_synthetic = bool(source.is_synthetic or policy.get("is_synthetic") or str(policy.get("connection_ref") or "").startswith("synthetic://"))
    started_payload = {"activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME, "table_name": request.table_name, "schema_name": request.schema_name, "cursor_field": request.cursor_field, "start_cursor": start_cursor, "limit": request.limit, "step_key": "fetch"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_db_import_table_started", status="running", payload=started_payload, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=started_payload | {"collection_run_id": run.id}, created_at=_now()))

    response_records = _bulk_insert_db_import_records(session, source, run, import_run, request, start_cursor, is_synthetic)
    row_count = request.limit
    next_cursor = start_cursor + row_count
    latency_ms = int((time.perf_counter() - started) * 1000)
    activity = {
        "activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME,
        "classification": "rows",
        "engine": policy.get("engine"),
        "connection_ref": policy.get("connection_ref"),
        "table_name": request.table_name,
        "schema_name": request.schema_name,
        "cursor_field": request.cursor_field,
        "start_cursor": start_cursor,
        "next_cursor": next_cursor,
        "row_count": row_count,
        "raw_record_count": row_count,
        "response_record_count": len(response_records),
        "is_synthetic": is_synthetic,
        "latency_ms": latency_ms,
        "retryable": False,
        "collection_job_id": job.id,
        "collection_run_id": run.id,
        "import_run_id": import_run.id,
        "workflow_run_id": workflow.id,
    }
    run.status = "completed"
    run.record_count = row_count
    run.payload = {**(run.payload or {}), "workflow_status": "completed", "db_import_activity": activity}
    workflow.status = "completed"
    workflow.payload = {**(workflow.payload or {}), "status": "completed", "db_import_activity": activity, "raw_record_count": row_count}
    import_run.status = "completed"
    import_run.record_count = row_count
    import_run.is_synthetic = is_synthetic
    import_run.payload = {**(import_run.payload or {}), "db_import_activity": activity}
    _update_db_import_cursor(policy, table_key, request.cursor_field, next_cursor, activity)
    source.policy = policy
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_db_import_table_completed", status="completed", payload=activity | {"step_key": "store"}, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": "db_import", "record_count": row_count, "step_key": "store"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=activity | {"collection_run_id": run.id, "step_key": "store"}, created_at=_now()))
    session.add(models.SourcePolicy(id=_id("SPOL"), data_source_id=source.id, status="allow", reason="ok", payload={"db_import_scan": activity}))
    _update_health(session, source.id, run.id, success=True, count=row_count)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="db_import.scan.completed",
        object_type="import_run",
        object_id=import_run.id,
        after={"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "db_import_activity": activity},
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return {"collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "raw_records": response_records}


def receive_file_upload(
    session: Session,
    data_source_id: str,
    file_name: str,
    mime_type: str | None,
    content: bytes,
    actor: models.User,
    trace_id: str,
    title: str | None = None,
    is_synthetic: bool = False,
    source_uri: str | None = None,
) -> dict:
    source = get_data_source(session, data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.source_type != "file_upload":
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            "SOURCE_TYPE_UNSUPPORTED_FOR_UPLOAD",
            "Uploads are only valid for file_upload data sources.",
            file_name=file_name,
            status_code=422,
        )

    policy = dict(source.policy or {})
    _validate_file_upload_policy(policy)
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    if not policy_result["allowed"]:
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            policy_result.get("reason") or "SOURCE_POLICY_BLOCKED",
            "Source policy blocks file upload.",
            file_name=file_name,
            status_code=409,
        )

    safe_name = _safe_file_name(file_name)
    extension = _file_extension(safe_name)
    allowed_extensions = set(policy.get("allowed_file_types") or [])
    if extension not in allowed_extensions:
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            "FILE_UPLOAD_TYPE_NOT_ALLOWED",
            f"File extension .{extension or 'unknown'} is not allowed for this source.",
            file_name=safe_name,
            status_code=415,
            details={"allowed_file_types": sorted(allowed_extensions), "extension": extension},
        )

    byte_size = len(content)
    max_file_size_mb = int(policy.get("max_file_size_mb") or 50)
    max_bytes = max_file_size_mb * 1024 * 1024
    if byte_size > max_bytes:
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            "FILE_UPLOAD_TOO_LARGE",
            f"File exceeds the configured {max_file_size_mb}MB limit.",
            file_name=safe_name,
            status_code=413,
            details={"byte_size": byte_size, "max_bytes": max_bytes, "max_file_size_mb": max_file_size_mb, "recoverable": True},
        )

    scan = _scan_file_upload(content)
    if scan["status"] != "passed":
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            "FILE_UPLOAD_VIRUS_DETECTED",
            "File upload was rejected by the local virus signature scan.",
            file_name=safe_name,
            status_code=422,
            details=scan,
        )

    checksum = _hash_bytes(content)
    effective_mime_type = _normalize_upload_mime_type(extension, mime_type)
    synthetic = bool(is_synthetic or source.is_synthetic or policy.get("is_synthetic"))
    file_object_id = _id("FILE")
    storage_key = f"uploads/{source.tenant_id}/{source.id}/{file_object_id}/{safe_name}"
    try:
        object_store_uri = _write_upload_object(storage_key, content)
    except OSError as error:
        _reject_file_upload(
            session,
            source,
            actor,
            trace_id,
            "FILE_UPLOAD_STORAGE_FAILED",
            f"File upload could not be written to local object storage: {error}",
            file_name=safe_name,
            status_code=507,
            details={"recoverable": True, "storage_key": storage_key},
        )
    payload = {
        "storage_mode": "local_object_store",
        "object_store_uri": object_store_uri,
        "upload": {
            "title": title or safe_name,
            "source_uri": source_uri or f"upload://{source.id}/{safe_name}",
            "extension": extension,
            "trace_id": trace_id,
            "max_file_size_mb": max_file_size_mb,
            "recoverable": True,
        },
        "scan_status": scan["status"],
        "scan": scan,
        "content_hash": checksum,
        "content_preview": {
            "mode": "redacted",
            "reason": "raw upload bytes are stored only in object storage; reversible inline previews are not persisted or audited",
            "byte_size": byte_size,
            "checksum": checksum,
        },
        "content_preview_base64": None,
        "content_preview_inlined": False,
        "content_preview_redacted": True,
        "source_flags": {"synthetic": synthetic, "import_type": "file_upload"},
        "schema": policy.get("schema"),
    }
    file_object = models.FileObject(
        id=file_object_id,
        tenant_id=source.tenant_id,
        owner_user_id=actor.id,
        object_type="data_source",
        object_id=source.id,
        storage_key=storage_key,
        file_name=safe_name,
        mime_type=effective_mime_type,
        byte_size=byte_size,
        checksum=checksum,
        status="stored",
        access_policy={"scope": "tenant", "tenant_id": source.tenant_id, "synthetic": synthetic},
        source_refs=[{"object_type": "data_source", "object_id": source.id}],
        payload=payload,
    )
    session.add(file_object)
    session.flush()
    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="data_source",
            from_object_id=source.id,
            to_object_type="file_object",
            to_object_id=file_object.id,
            relation="uploaded_file_object",
            is_synthetic=synthetic,
            payload={"trace_id": trace_id, "file_name": safe_name, "checksum": checksum},
        )
    )
    before = serialize_data_source(source)
    policy["last_file_upload"] = {
        "file_object_id": file_object.id,
        "file_name": safe_name,
        "byte_size": byte_size,
        "mime_type": effective_mime_type,
        "checksum": checksum,
        "scan_status": scan["status"],
        "uploaded_at": _now().isoformat(),
    }
    source.policy = policy
    flag_modified(source, "policy")
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow",
            reason="file_upload_received",
            payload={"file_upload": policy["last_file_upload"]},
        )
    )
    _update_health(session, source.id, None, success=True, count=1)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="file_upload.received",
        object_type="file_object",
        object_id=file_object.id,
        before=before,
        after=serialize_file_object(file_object),
        trace_id=trace_id,
    )
    session.commit()
    return {
        "upload": {
            "upload_id": file_object.id,
            "status": "stored",
            "data_source_id": source.id,
            "storage_key": file_object.storage_key,
            "byte_size": byte_size,
            "checksum": checksum,
            "recoverable": True,
            "max_file_size_mb": max_file_size_mb,
            "scan": scan,
        },
        "file_object": serialize_file_object(file_object),
        "data_source": serialize_data_source(source),
    }


def publish_data_source_version(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    policy = dict(source.policy or {})
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    if not policy_result["allowed"]:
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Data source policy must allow collection before publishing a version.")
    last_connection_test = policy.get("last_connection_test") if isinstance(policy.get("last_connection_test"), dict) else {}
    if last_connection_test.get("status") != "ok":
        raise _api_error(409, "DATA_SOURCE_CONNECTION_TEST_REQUIRED", "Data source must have a successful connection test before publishing.")
    if not policy_result["compliance_ready"]:
        raise _api_error(409, "DATA_SOURCE_COMPLIANCE_REQUIRED", "Data source must have authorization basis and compliance tags before publishing.")

    before = serialize_data_source(source)
    next_version = (session.execute(select(func.max(models.DataSourceVersion.version)).where(models.DataSourceVersion.data_source_id == source.id)).scalar_one() or 0) + 1
    for published in session.execute(
        select(models.DataSourceVersion).where(models.DataSourceVersion.data_source_id == source.id, models.DataSourceVersion.status == "published")
    ).scalars():
        published.status = "superseded"

    policy_snapshot = _source_policy_snapshot(source)
    config_hash = _config_hash({"source_type": source.source_type, "policy": policy_snapshot, "payload": source.payload})
    version = models.DataSourceVersion(
        id=_id("DSV"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        version=next_version,
        status="published",
        config_hash=config_hash,
        policy_snapshot=policy_snapshot,
        payload={"reason": getattr(request, "reason", None), "trace_id": trace_id, "published_from_status": source.status},
        published_by_id=actor.id,
        published_at=datetime.utcnow(),
    )
    session.add(version)
    session.flush()

    policy["config_status"] = "published"
    policy["published_version"] = _published_version_pointer(version)
    source.policy = policy
    flag_modified(source, "policy")
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="published",
            reason="version_published",
            payload={"published_version": _published_version_pointer(version), "reason": getattr(request, "reason", None)},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.version.publish",
        object_type="data_source_version",
        object_id=version.id,
        before=before,
        after=serialize_data_source_version(version),
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source_version(version)


def update_data_source_compliance(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    before = serialize_data_source(source)
    compliance = _normalize_compliance_update(request)
    compliance["updated_by"] = actor.username
    compliance["updated_at"] = _now().isoformat()
    compliance["trace_id"] = trace_id
    policy = dict(source.policy or {})
    policy["compliance"] = compliance
    collection_controls = dict(policy.get("collection_controls") or {})
    collection_controls.update(
        {
            "compliance_ready": True,
            "authorization_scope": compliance["authorization_scope"],
            "retention_days": compliance["retention_days"],
            "data_classification": compliance["data_classification"],
            "pii_policy": compliance["pii_policy"],
        }
    )
    policy["collection_controls"] = collection_controls
    policy_result = evaluate_policy(source.source_type, policy, source.status)
    policy["policy_result"] = policy_result
    source.policy = policy
    flag_modified(source, "policy")
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="allow" if policy_result["allowed"] else "block",
            reason="compliance_updated",
            payload={"compliance": compliance, "policy_result": policy_result, "reason": request.reason},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.compliance.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def rollback_data_source_version(session: Session, data_source_id: str, version_number: int, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    target = session.execute(
        select(models.DataSourceVersion).where(models.DataSourceVersion.data_source_id == source.id, models.DataSourceVersion.version == version_number)
    ).scalar_one_or_none()
    if target is None:
        raise _api_error(404, "DATA_SOURCE_VERSION_NOT_FOUND", "Data source version does not exist.")
    current = session.execute(
        select(models.DataSourceVersion)
        .where(models.DataSourceVersion.data_source_id == source.id, models.DataSourceVersion.status == "published")
        .order_by(models.DataSourceVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if current is None:
        raise _api_error(409, "DATA_SOURCE_VERSION_PUBLISHED_REQUIRED", "Data source rollback requires an active published version.")
    if current.version == target.version:
        raise _api_error(409, "DATA_SOURCE_VERSION_ALREADY_ACTIVE", "Target data source version is already the active published version.")

    before = {"source": serialize_data_source(source), "from_version": serialize_data_source_version(current), "to_version": serialize_data_source_version(target)}
    current.status = "superseded"
    next_version = (session.execute(select(func.max(models.DataSourceVersion.version)).where(models.DataSourceVersion.data_source_id == source.id)).scalar_one() or 0) + 1
    rollback_payload = {
        "reason": getattr(request, "reason", None),
        "trace_id": trace_id,
        "rollback_from_version": current.version,
        "rollback_from_version_id": current.id,
        "rollback_to_version": target.version,
        "rollback_to_version_id": target.id,
        "rollback_strategy": "append_only_snapshot",
    }
    rollback_version = models.DataSourceVersion(
        id=_id("DSV"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        version=next_version,
        status="published",
        config_hash=target.config_hash,
        policy_snapshot=dict(target.policy_snapshot or {}),
        payload=rollback_payload,
        published_by_id=actor.id,
        published_at=datetime.utcnow(),
    )
    session.add(rollback_version)
    session.flush()

    policy = dict(source.policy or {})
    policy.update(dict(target.policy_snapshot or {}))
    policy["config_status"] = "published"
    policy["published_version"] = _published_version_pointer(rollback_version)
    policy["rollback"] = {
        "from_version": current.version,
        "from_version_id": current.id,
        "to_version": target.version,
        "to_version_id": target.id,
        "rollback_version": rollback_version.version,
        "rollback_version_id": rollback_version.id,
        "reason": getattr(request, "reason", None),
    }
    source.policy = policy
    source.is_synthetic = bool(policy.get("is_synthetic") or source.is_synthetic)
    policy_result = evaluate_policy(source.source_type, policy, "active")
    policy["policy_result"] = policy_result
    source.status = "active" if policy_result["allowed"] else "blocked"
    flag_modified(source, "policy")
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="published",
            reason="version_rollback",
            payload={"rollback": policy["rollback"], "policy_result": policy_result},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.version.rollback",
        object_type="data_source_version",
        object_id=rollback_version.id,
        before=before,
        after=serialize_data_source_version(rollback_version),
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source_version(rollback_version)


def update_data_source_status(session: Session, data_source_id: str, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    before = serialize_data_source(source)
    policy = dict(source.policy or {})
    policy["operational_state"] = {"status": request.status, "reason": request.reason, "updated_by": actor.username, "trace_id": trace_id}
    if request.status == "disabled":
        source.status = "disabled"
        policy_result = evaluate_policy(source.source_type, policy, "disabled")
        policy["policy_result"] = policy_result
        health_status = "disabled"
        source_policy_status = "disabled"
    else:
        policy_result = evaluate_policy(source.source_type, policy, "active")
        policy["policy_result"] = policy_result
        source.status = "active" if policy_result["allowed"] else "blocked"
        health_status = "healthy" if policy_result["allowed"] else "blocked"
        source_policy_status = "allow" if policy_result["allowed"] else "block"
    source.policy = policy
    flag_modified(source, "policy")
    _set_health_status(session, source.id, health_status, policy_result.get("reason"))
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status=source_policy_status,
            reason=request.reason,
            payload={"operational_state": policy["operational_state"], "policy_result": policy_result},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.status.update",
        object_type="data_source",
        object_id=source.id,
        before=before,
        after=serialize_data_source(source),
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_data_source(source)


def create_collection_job(session: Session, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, request.data_source_id)
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot create new collection jobs.")
    schedule = _normalize_collection_schedule(request.schedule)
    payload = dict(request.payload or {})
    if schedule is not None:
        if not isinstance(payload.get("query"), dict):
            raise _api_error(422, "COLLECTION_JOB_QUERY_REQUIRED", "Scheduled collection jobs require a query object.")
        if not isinstance(payload.get("window"), dict):
            raise _api_error(422, "COLLECTION_JOB_WINDOW_REQUIRED", "Scheduled collection jobs require a window object.")
    version_payload = _collection_version_payload(source)
    if schedule is not None and not version_payload.get("data_source_version_id"):
        raise _api_error(409, "DATA_SOURCE_UNPUBLISHED", "Collection jobs require a published data source version.")
    if schedule is not None and source.status != "active":
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Only active data sources can create scheduled collection jobs.")
    if schedule is not None:
        payload.update(_collection_schedule_payload(schedule, trace_id))
    payload.update(version_payload)
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        created_by_id=actor.id,
        name=request.name,
        status="active" if source.status == "active" else "blocked",
        schedule=schedule,
        payload=payload,
    )
    session.add(job)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_job.create",
        object_type="collection_job",
        object_id=job.id,
        after=serialize_collection_job(job),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_job(job)


def list_collection_jobs(
    session: Session,
    tenant_id: str,
    status: str | None = None,
    data_source_id: str | None = None,
    created_by_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], dict]:
    allowed_statuses = {"draft", "active", "blocked", "paused", "archived", "completed"}
    if status and status not in allowed_statuses:
        raise _api_error(422, "COLLECTION_JOB_STATUS_INVALID", "Unsupported collection job status filter.")
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [models.CollectionJob.tenant_id == tenant_id]
    if status:
        filters.append(models.CollectionJob.status == status)
    if data_source_id:
        filters.append(models.CollectionJob.data_source_id == data_source_id)
    if created_by_id:
        filters.append(models.CollectionJob.created_by_id == created_by_id)
    total = session.execute(select(func.count()).select_from(models.CollectionJob).where(*filters)).scalar_one()
    rows = session.execute(
        select(models.CollectionJob)
        .where(*filters)
        .order_by(models.CollectionJob.created_at.desc(), models.CollectionJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    meta = {"pagination": {"page": page, "page_size": page_size, "total": total}}
    return [serialize_collection_job(row) for row in rows], meta


def get_collection_job(session: Session, collection_job_id: str, tenant_id: str | None = None) -> dict:
    job = session.get(models.CollectionJob, collection_job_id)
    if job is None or (tenant_id is not None and job.tenant_id != tenant_id):
        raise _api_error(404, "NOT_FOUND", "Collection job does not exist.")
    return serialize_collection_job_detail(session, job)


def _get_actor_collection_job(session: Session, collection_job_id: str, actor: models.User) -> models.CollectionJob:
    job = session.get(models.CollectionJob, collection_job_id)
    if job is None or job.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Collection job does not exist.")
    return job


def update_collection_job(session: Session, collection_job_id: str, request, actor: models.User, trace_id: str) -> dict:
    job = session.get(models.CollectionJob, collection_job_id)
    if job is None:
        raise _api_error(404, "NOT_FOUND", "Collection job does not exist.")
    source = get_data_source(session, request.data_source_id)
    before = serialize_collection_job(job)
    protected_version_payload = _collection_version_payload(source, job.payload)
    next_payload = dict(request.payload or {})
    next_payload.update({key: value for key, value in protected_version_payload.items() if value is not None})
    job.data_source_id = source.id
    job.name = request.name
    job.status = "active" if source.status == "active" else "blocked"
    job.schedule = request.schedule
    job.payload = next_payload
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_job.update",
        object_type="collection_job",
        object_id=job.id,
        before=before,
        after=serialize_collection_job(job),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_job(job)


def pause_collection_job(session: Session, collection_job_id: str, request, actor: models.User, trace_id: str) -> dict:
    job = _get_actor_collection_job(session, collection_job_id, actor)
    if job.status in {"archived", "completed"}:
        raise _api_error(409, "COLLECTION_JOB_NOT_PAUSABLE", "Archived or completed collection jobs cannot be paused.")
    before = serialize_collection_job_detail(session, job)
    active_runs = list(
        session.execute(
            select(models.CollectionRun)
            .where(models.CollectionRun.collection_job_id == job.id, models.CollectionRun.status.in_(["pending", "running", "retrying"]))
            .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
        ).scalars()
    )
    reason = getattr(request, "reason", None) if request is not None else None
    payload = dict(job.payload or {})
    pause_state = {
        "status": "paused",
        "reason": reason,
        "updated_by": actor.id,
        "updated_by_username": actor.username,
        "trace_id": trace_id,
        "paused_at": _now().isoformat(),
        "active_run_ids": [run.id for run in active_runs],
        "active_run_count": len(active_runs),
        "running_run_policy": "preserve_existing_runs",
    }
    payload["pause"] = pause_state
    payload["operational_state"] = pause_state
    job.status = "paused"
    job.payload = payload
    for run in active_runs:
        session.add(
            models.CollectionRunEvent(
                id=_id("CREV"),
                collection_run_id=run.id,
                event_type="job_paused",
                status=run.status,
                payload={"collection_job_id": job.id, "trace_id": trace_id, "reason": reason, "run_interrupted": False},
            )
        )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_job.pause",
        object_type="collection_job",
        object_id=job.id,
        before=before,
        after=serialize_collection_job_detail(session, job),
        reason=reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_job(job)


def resume_collection_job(session: Session, collection_job_id: str, request, actor: models.User, trace_id: str) -> dict:
    job = _get_actor_collection_job(session, collection_job_id, actor)
    source = get_data_source(session, job.data_source_id)
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot resume collection jobs.")
    if source.status != "active":
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Only active data sources can resume collection jobs.")
    previous_status = job.status
    if previous_status in {"archived", "completed"}:
        raise _api_error(409, "COLLECTION_JOB_NOT_RESUMABLE", "Archived or completed collection jobs cannot be resumed.")
    before = serialize_collection_job_detail(session, job)
    reason = getattr(request, "reason", None) if request is not None else None
    payload = dict(job.payload or {})
    resume_state = {
        "status": "active",
        "previous_status": previous_status,
        "reason": reason,
        "updated_by": actor.id,
        "updated_by_username": actor.username,
        "trace_id": trace_id,
        "resumed_at": _now().isoformat(),
        "scheduler_state": "scheduled" if job.schedule else "manual_ready",
    }
    payload["resume"] = resume_state
    payload["operational_state"] = resume_state
    job.status = "active"
    job.payload = payload
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_job.resume",
        object_type="collection_job",
        object_id=job.id,
        before=before,
        after=serialize_collection_job_detail(session, job),
        reason=reason,
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_job(job)


def _coerce_positive_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(parsed, 0)


def _parse_rate_limit_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


COLLECTION_CHANNEL_ALIASES = {
    "public_web": "web_page",
    "web": "web_page",
    "web_page": "web_page",
    "official_api": "official_api",
    "api": "official_api",
    "rss": "rss",
    "file_upload": "document_file",
    "manual_upload": "document_file",
    "document": "document_file",
    "document_file": "document_file",
    "image": "image_file",
    "image_file": "image_file",
    "video": "video_file",
    "video_file": "video_file",
    "audio": "audio_file",
    "audio_file": "audio_file",
    "live_segment": "livestream",
    "livestream": "livestream",
    "webhook": "webhook",
    "db_import": "database",
    "database": "database",
    "object_storage": "object_storage",
    "synthetic": "synthetic",
}


def _normalize_collection_channel(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return COLLECTION_CHANNEL_ALIASES.get(value.strip().lower())


def _collection_job_channel(source: models.DataSource, job_payload: dict | None = None) -> str | None:
    payload = job_payload if isinstance(job_payload, dict) else {}
    policy = source.policy if isinstance(source.policy, dict) else {}
    for container in (payload, policy):
        for key in ("collection_channel", "channel"):
            channel = _normalize_collection_channel(container.get(key))
            if channel and channel != "synthetic":
                return channel
    if source.source_type == "media":
        media_kind = _normalize_collection_channel(policy.get("media_kind"))
        if media_kind:
            return media_kind
        media_types = policy.get("media_types")
        if isinstance(media_types, list):
            for item in media_types:
                media_channel = _normalize_collection_channel(item)
                if media_channel in {"image_file", "video_file", "audio_file"}:
                    return media_channel
        return "image_file"
    channel = _normalize_collection_channel(source.source_type)
    return None if channel == "synthetic" else channel


def _rate_limit_config_from_mapping(configured: dict | None, scope: str, fallbacks: list[object] | None = None) -> dict | None:
    configured = configured if isinstance(configured, dict) else {}
    fallback_values = fallbacks or []
    max_runs = _coerce_positive_int(
        configured.get("max_runs")
        or configured.get("max_runs_per_window")
        or configured.get("rate_limit_per_minute")
        or next((item for item in fallback_values if item is not None), None)
    )
    if max_runs <= 0:
        return None
    window_seconds = _coerce_positive_int(configured.get("window_seconds") or configured.get("window") or 60, 60)
    delay_seconds = _coerce_positive_int(configured.get("delay_seconds") or window_seconds, window_seconds)
    mode = str(configured.get("mode") or "sliding_window")
    requested_scope = str(configured.get("scope") or scope)
    return {
        "enabled": True,
        "max_runs": max_runs,
        "window_seconds": max(window_seconds, 1),
        "delay_seconds": max(delay_seconds, 1),
        "scope": requested_scope if requested_scope == scope else scope,
        "mode": mode if mode == "sliding_window" else "sliding_window",
    }


def _source_rate_limit_config(policy: dict | None) -> dict | None:
    if not isinstance(policy, dict):
        return None
    configured = policy.get("rate_limit") if isinstance(policy.get("rate_limit"), dict) else {}
    crawl_policy = policy.get("crawl_policy") if isinstance(policy.get("crawl_policy"), dict) else {}
    return _rate_limit_config_from_mapping(configured, "data_source", [policy.get("rate_limit_per_minute"), crawl_policy.get("rate_limit_per_minute")])


def _channel_rate_limit_config(policy: dict | None, channel: str | None) -> dict | None:
    if not isinstance(policy, dict) or not channel:
        return None
    limits = policy.get("channel_rate_limits") if isinstance(policy.get("channel_rate_limits"), dict) else {}
    configured = limits.get(channel)
    config = _rate_limit_config_from_mapping(configured if isinstance(configured, dict) else None, "channel")
    if config is not None:
        config["channel"] = channel
    return config


def _rate_limit_lock_statement(source_id: str):
    return select(models.DataSource).where(models.DataSource.id == source_id).with_for_update().execution_options(populate_existing=True)


def _rate_limit_state_view(state: dict, config: dict, now: datetime | None = None) -> dict:
    now = now or _now()
    started_at = _parse_rate_limit_datetime(state.get("window_started_at")) or now
    window_ends_at = started_at + timedelta(seconds=config["window_seconds"])
    expired = now >= window_ends_at
    used = 0 if expired else _coerce_positive_int(state.get("used"))
    remaining = max(config["max_runs"] - used, 0)
    next_allowed_at = state.get("next_allowed_at")
    if used >= config["max_runs"]:
        next_allowed_at = next_allowed_at or window_ends_at.isoformat()
    return {
        "enabled": True,
        "used": used,
        "remaining": remaining,
        "window_started_at": None if expired else started_at.isoformat(),
        "window_ends_at": None if expired else window_ends_at.isoformat(),
        "next_allowed_at": next_allowed_at if used >= config["max_runs"] else None,
        "delayed_count": _coerce_positive_int(state.get("delayed_count")),
        "last_allowed_at": state.get("last_allowed_at"),
        "last_limited_at": state.get("last_limited_at"),
        "last_delayed_at": state.get("last_delayed_at"),
        "last_delayed_run_id": state.get("last_delayed_run_id"),
    }


def _advance_rate_limit_state(state: dict, config: dict, now: datetime) -> tuple[dict, bool, int]:
    state = dict(state)
    started_at = _parse_rate_limit_datetime(state.get("window_started_at"))
    if started_at is None or now >= started_at + timedelta(seconds=config["window_seconds"]):
        state = {"window_started_at": now.isoformat(), "used": 0, "delayed_count": _coerce_positive_int(state.get("delayed_count"))}
        started_at = now
    window_ends_at = started_at + timedelta(seconds=config["window_seconds"])
    used = _coerce_positive_int(state.get("used"))
    allowed = used < config["max_runs"]
    if allowed:
        used += 1
        state.update(
            {
                "status": "available" if used < config["max_runs"] else "limited",
                "used": used,
                "remaining": max(config["max_runs"] - used, 0),
                "window_ends_at": window_ends_at.isoformat(),
                "last_allowed_at": now.isoformat(),
                "next_allowed_at": window_ends_at.isoformat() if used >= config["max_runs"] else None,
            }
        )
    else:
        next_allowed_at = max(window_ends_at, now + timedelta(seconds=config["delay_seconds"]))
        state.update(
            {
                "status": "limited",
                "used": used,
                "remaining": 0,
                "window_ends_at": window_ends_at.isoformat(),
                "next_allowed_at": next_allowed_at.isoformat(),
                "last_limited_at": now.isoformat(),
                "delayed_count": _coerce_positive_int(state.get("delayed_count")) + 1,
            }
        )
    return state, allowed, used


def _rate_limit_result(
    source: models.DataSource,
    config: dict,
    state: dict,
    now: datetime,
    allowed: bool,
    used: int,
    actor: models.User,
    trace_id: str,
    collection_job_id: str,
    purpose: str,
    channel: str | None = None,
) -> dict:
    result = {
        "allowed": allowed,
        "status": "allowed" if allowed else "limited",
        "config": config,
        "state": _rate_limit_state_view(state, config, now),
        "source_id": source.id,
        "collection_job_id": collection_job_id,
        "actor_id": actor.id,
        "trace_id": trace_id,
        "purpose": purpose,
        "remaining": max(config["max_runs"] - used, 0),
        "next_allowed_at": state.get("next_allowed_at"),
        "evaluated_at": now.isoformat(),
    }
    if channel:
        result["channel"] = channel
    return result


def _evaluate_source_rate_limit(
    session: Session,
    source: models.DataSource,
    actor: models.User,
    trace_id: str,
    collection_job_id: str,
    purpose: str,
) -> dict | None:
    policy = dict(source.policy or {})
    config = _source_rate_limit_config(policy)
    if config is None:
        return None
    locked_source = session.execute(_rate_limit_lock_statement(source.id)).scalar_one_or_none()
    if locked_source is None:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    source = locked_source
    policy = dict(source.policy or {})
    config = _source_rate_limit_config(policy)
    if config is None:
        return None
    now = _now()
    state = dict(policy.get("rate_limit_state") if isinstance(policy.get("rate_limit_state"), dict) else {})
    started_at = _parse_rate_limit_datetime(state.get("window_started_at"))
    if started_at is None or now >= started_at + timedelta(seconds=config["window_seconds"]):
        state = {"window_started_at": now.isoformat(), "used": 0, "delayed_count": _coerce_positive_int(state.get("delayed_count"))}
        started_at = now
    window_ends_at = started_at + timedelta(seconds=config["window_seconds"])
    used = _coerce_positive_int(state.get("used"))
    allowed = used < config["max_runs"]
    if allowed:
        used += 1
        state.update(
            {
                "status": "available" if used < config["max_runs"] else "limited",
                "used": used,
                "remaining": max(config["max_runs"] - used, 0),
                "window_ends_at": window_ends_at.isoformat(),
                "last_allowed_at": now.isoformat(),
                "next_allowed_at": window_ends_at.isoformat() if used >= config["max_runs"] else None,
            }
        )
    else:
        next_allowed_at = max(window_ends_at, now + timedelta(seconds=config["delay_seconds"]))
        state.update(
            {
                "status": "limited",
                "used": used,
                "remaining": 0,
                "window_ends_at": window_ends_at.isoformat(),
                "next_allowed_at": next_allowed_at.isoformat(),
                "last_limited_at": now.isoformat(),
                "delayed_count": _coerce_positive_int(state.get("delayed_count")) + 1,
            }
        )
    policy["rate_limit_state"] = state
    source.policy = policy
    flag_modified(source, "policy")
    session.add(source)
    return {
        "allowed": allowed,
        "status": "allowed" if allowed else "limited",
        "config": config,
        "state": _rate_limit_state_view(state, config, now),
        "source_id": source.id,
        "collection_job_id": collection_job_id,
        "actor_id": actor.id,
        "trace_id": trace_id,
        "purpose": purpose,
        "remaining": max(config["max_runs"] - used, 0),
        "next_allowed_at": state.get("next_allowed_at"),
        "evaluated_at": now.isoformat(),
    }


def apply_channel_rate_limit(
    session: Session,
    source: models.DataSource,
    channel: str | None,
    actor: models.User,
    trace_id: str,
    collection_job_id: str,
    purpose: str,
) -> dict | None:
    channel = _normalize_collection_channel(channel)
    if not channel:
        return None
    locked_source = session.execute(_rate_limit_lock_statement(source.id)).scalar_one_or_none()
    if locked_source is None:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    source = locked_source
    policy = dict(source.policy or {})
    channel_config = _channel_rate_limit_config(policy, channel)
    if channel_config is None:
        return None
    now = _now()
    states = dict(policy.get("channel_rate_limit_state") if isinstance(policy.get("channel_rate_limit_state"), dict) else {})
    channel_state = dict(states.get(channel) if isinstance(states.get(channel), dict) else {})
    channel_state, channel_allowed, channel_used = _advance_rate_limit_state(channel_state, channel_config, now)
    channel_result = _rate_limit_result(source, channel_config, channel_state, now, channel_allowed, channel_used, actor, trace_id, collection_job_id, purpose, channel)
    if not channel_allowed:
        states[channel] = channel_state
        policy["channel_rate_limit_state"] = states
        source.policy = policy
        flag_modified(source, "policy")
        session.add(source)
        return channel_result

    source_config = _source_rate_limit_config(policy)
    if source_config is not None:
        source_state = dict(policy.get("rate_limit_state") if isinstance(policy.get("rate_limit_state"), dict) else {})
        source_state, source_allowed, source_used = _advance_rate_limit_state(source_state, source_config, now)
        source_result = _rate_limit_result(source, source_config, source_state, now, source_allowed, source_used, actor, trace_id, collection_job_id, purpose)
        if not source_allowed:
            source_result["channel_context"] = channel
            policy["rate_limit_state"] = source_state
            source.policy = policy
            flag_modified(source, "policy")
            session.add(source)
            return source_result
        policy["rate_limit_state"] = source_state
        channel_result["source_rate_limit"] = source_result

    states[channel] = channel_state
    policy["channel_rate_limit_state"] = states
    source.policy = policy
    flag_modified(source, "policy")
    session.add(source)
    return channel_result


def _create_delayed_collection_run(
    session: Session,
    job: models.CollectionJob,
    source: models.DataSource,
    actor: models.User,
    trace_id: str,
    rate_limit: dict,
    extra_payload: dict | None = None,
) -> models.CollectionRun:
    run_id = _id("CRUN")
    now = _now()
    next_allowed_at = _parse_rate_limit_datetime(rate_limit.get("next_allowed_at"))
    channel = _normalize_collection_channel(rate_limit.get("channel"))
    rate_limit_code = "CHANNEL_RATE_LIMITED" if channel else "SOURCE_RATE_LIMITED"
    delayed_payload = {
        "manual_start": True,
        "workflow_status": "delayed",
        "delay_reason": rate_limit_code,
        "rate_limit": {**rate_limit, "collection_run_id": run_id},
        "started_by": actor.id,
    }
    delayed_payload.update(_collection_version_payload(source, job.payload))
    if extra_payload:
        delayed_payload.update(extra_payload)
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="delayed",
        record_count=0,
        error_code=rate_limit_code,
        error_message="Channel rate limit exceeded; collection run delayed." if channel else "Source rate limit exceeded; collection run delayed.",
        created_at=now,
        trace_id=trace_id,
        payload=delayed_payload,
    )
    session.add(run)
    policy = dict(source.policy or {})
    if channel:
        states = dict(policy.get("channel_rate_limit_state") if isinstance(policy.get("channel_rate_limit_state"), dict) else {})
        state = dict(states.get(channel) if isinstance(states.get(channel), dict) else {})
    else:
        state = dict(policy.get("rate_limit_state") if isinstance(policy.get("rate_limit_state"), dict) else {})
    state.update({"last_delayed_run_id": run.id, "last_delayed_at": now.isoformat()})
    if channel:
        states[channel] = state
        policy["channel_rate_limit_state"] = states
    else:
        policy["rate_limit_state"] = state
    source.policy = policy
    flag_modified(source, "policy")
    session.add(source)
    delayed_payload["rate_limit"]["state"] = _rate_limit_state_view(state, rate_limit["config"], now)
    delayed_payload["rate_limit"]["state"]["last_delayed_run_id"] = run.id
    session.add(
        models.CollectionRunEvent(
            id=_id("CREV"),
            collection_run_id=run.id,
            event_type="rate_limit_delayed",
            status="delayed",
            payload={"rate_limit": delayed_payload["rate_limit"], "next_allowed_at": rate_limit.get("next_allowed_at")},
        )
    )
    session.add(
        models.OpsRetryQueue(
            id=_id("RETQ"),
            target_type="collection_run",
            target_id=run.id,
            status="delayed",
            attempts=0,
            next_run_at=next_allowed_at,
            payload={"error_code": rate_limit_code, "data_source_id": source.id, "collection_job_id": job.id, "rate_limit": delayed_payload["rate_limit"]},
        )
    )
    session.add(
        models.SourcePolicy(
            id=_id("SPOL"),
            data_source_id=source.id,
            status="rate_limited",
            reason=rate_limit_code,
            payload={"rate_limit": delayed_payload["rate_limit"]},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_run.delayed",
        object_type="collection_run",
        object_id=run.id,
        after=serialize_collection_run(run),
        trace_id=trace_id,
    )
    return run


def start_collection_run(session: Session, job_id: str, actor: models.User, trace_id: str) -> dict:
    job = _get_actor_collection_job(session, job_id, actor)
    if job.status == "paused":
        raise _api_error(409, "COLLECTION_JOB_PAUSED", "Paused collection jobs cannot start new collection runs.")
    source = get_data_source(session, job.data_source_id)
    if source.status == "disabled":
        run = _create_failed_run(session, job, source, trace_id, "DATA_SOURCE_DISABLED", "Disabled data sources cannot start new collection runs.")
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="blocked", status="failed", payload={"reason": "DATA_SOURCE_DISABLED"}))
        _update_health(session, source.id, run.id, success=False, error_code="DATA_SOURCE_DISABLED")
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="collection_run.blocked",
            object_type="collection_run",
            object_id=run.id,
            after=serialize_collection_run(run),
            trace_id=trace_id,
        )
        session.commit()
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot start new collection runs.")
    if source.status != "active":
        run = _create_failed_run(session, job, source, trace_id, "SOURCE_POLICY_BLOCKED", "Source policy blocks collection.")
        _update_health(session, source.id, run.id, success=False, error_code="SOURCE_POLICY_BLOCKED")
        session.commit()
        return serialize_collection_run(run)
    active_run = session.execute(
        select(models.CollectionRun)
        .where(models.CollectionRun.collection_job_id == job.id, models.CollectionRun.status.in_(["pending", "running", "retrying"]))
        .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
    ).scalar_one_or_none()
    if active_run is not None:
        raise _api_error(409, "COLLECTION_RUN_ALREADY_RUNNING", "A collection run is already pending or running for this job.")
    collection_channel = _collection_job_channel(source, job.payload)
    rate_limit = apply_channel_rate_limit(session, source, collection_channel, actor, trace_id, job.id, "collection_run.start")
    if rate_limit is None:
        rate_limit = _evaluate_source_rate_limit(session, source, actor, trace_id, job.id, "collection_run.start")
    if rate_limit is not None and not rate_limit["allowed"]:
        delayed_run = _create_delayed_collection_run(session, job, source, actor, trace_id, rate_limit)
        session.commit()
        return serialize_collection_run(delayed_run)
    run_payload = {"manual_start": True}
    run_payload.update(_collection_version_payload(source, job.payload))
    if rate_limit is not None:
        run_payload["rate_limit"] = rate_limit
    _ensure_collection_workflow_case(session)
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"CollectSourceRunWorkflow-{run_id}"
    run_payload.update(
        {
            "workflow_run_id": workflow_run_id,
            "workflow_name": "CollectSourceRunWorkflow",
            "workflow_id": workflow_id,
            "workflow_status": "pending",
            "started_by": actor.id,
        }
    )
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="pending",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload=run_payload,
    )
    session.add(run)
    session.add(
        models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="CollectSourceRunWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={
                "collection_job_id": job.id,
                "collection_run_id": run.id,
                "data_source_id": source.id,
                "input_hash": _hash(json.dumps({"job_id": job.id, "source_id": source.id, "payload": job.payload}, sort_keys=True, ensure_ascii=True)),
                "attempt": 1,
            },
        )
    )
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="workflow_scheduled", status="pending", payload={"workflow_run_id": workflow_run_id}))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow_run_id, event_type="scheduled", status="pending", payload={"collection_run_id": run.id}))
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="collection_run.start", object_type="collection_run", object_id=run.id, trace_id=trace_id)
    session.commit()
    return serialize_collection_run(run)


def start_file_upload_run(session: Session, collection_job_id: str, request, actor: models.User, trace_id: str) -> dict:
    job = _get_actor_collection_job(session, collection_job_id, actor)
    if job.status == "paused":
        raise _api_error(409, "COLLECTION_JOB_PAUSED", "Paused collection jobs cannot start file import runs.")
    source = get_data_source(session, job.data_source_id)
    if source.source_type != "file_upload":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_FILE_RUN", "File import runs require a file_upload data source.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot start file import runs.")
    policy_result = evaluate_policy(source.source_type, source.policy or {}, source.status)
    if source.status != "active" or not policy_result["allowed"]:
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Source policy blocks file import runs.")

    file_object = session.get(models.FileObject, request.file_object_id)
    if file_object is None:
        raise _api_error(404, "FILE_OBJECT_NOT_FOUND", "Uploaded file object does not exist.")
    if file_object.tenant_id != actor.tenant_id:
        raise _api_error(403, "FILE_OBJECT_TENANT_MISMATCH", "Uploaded file object belongs to another tenant.")
    if file_object.object_type != "data_source" or file_object.object_id != source.id:
        raise _api_error(403, "FILE_OBJECT_SOURCE_MISMATCH", "Uploaded file object is not linked to this collection job data source.")
    if file_object.status != "stored":
        raise _api_error(409, "FILE_OBJECT_NOT_STORED", "Only stored file objects can start file import runs.")

    content_bytes = _read_upload_object(file_object)
    content_text = _file_object_text(file_object, content_bytes)
    source_flags = (file_object.payload or {}).get("source_flags")
    synthetic = bool((source_flags if isinstance(source_flags, dict) else {}).get("synthetic") or source.is_synthetic)
    title = (request.title or (file_object.payload or {}).get("upload", {}).get("title") or file_object.file_name)[:240]
    _ensure_collection_workflow_case(session)
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"FileUploadImportWorkflow-{run_id}"
    run_payload = {
        "import_type": "file_upload",
        "file_object_id": file_object.id,
        "file_name": file_object.file_name,
        "storage_key": file_object.storage_key,
        "workflow_run_id": workflow_run_id,
        "workflow_name": "FileUploadImportWorkflow",
        "workflow_id": workflow_id,
        "workflow_status": "running",
        "started_by": actor.id,
    }
    run_payload.update(_collection_version_payload(source, job.payload))
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="running",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload=run_payload,
    )
    workflow = models.WorkflowRun(
        id=workflow_run_id,
        case_id=COLLECTION_WORKFLOW_CASE_ID,
        tenant_id=actor.tenant_id,
        workflow_name="FileUploadImportWorkflow",
        workflow_id=workflow_id,
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload={
            "collection_job_id": job.id,
            "collection_run_id": run.id,
            "data_source_id": source.id,
            "file_object_id": file_object.id,
            "input_hash": _hash(json.dumps({"job_id": job.id, "file_object_id": file_object.id, "checksum": file_object.checksum}, sort_keys=True, ensure_ascii=True)),
        },
    )
    import_run = models.ImportRun(
        id=_id("IMPR"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        import_type="file_upload",
        status="running",
        is_synthetic=synthetic,
        trace_id=trace_id,
        payload={"file_object_id": file_object.id, "file_name": file_object.file_name, "checksum": file_object.checksum, "payload": request.payload},
    )
    session.add(run)
    session.add(workflow)
    session.add(import_run)
    session.flush()
    started_payload = {"activity_name": "import_uploaded_file", "file_object_id": file_object.id, "step_key": "fetch"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="file_upload_import_started", status="running", payload=started_payload, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=started_payload | {"collection_run_id": run.id}, created_at=_now()))

    record = _create_file_upload_raw_record(session, source, run, import_run, file_object, title, content_text, synthetic, request.city_id, request.payload)
    fetched_payload = {"activity_name": "import_uploaded_file", "file_object_id": file_object.id, "byte_size": file_object.byte_size, "step_key": "fetch"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="file_upload_object_read", status="completed", payload=fetched_payload, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_progress", status="completed", payload=fetched_payload | {"collection_run_id": run.id}, created_at=_now()))
    run.status = "completed"
    run.record_count = 1
    run.payload = {**(run.payload or {}), "workflow_status": "completed", "raw_record_id": record.id, "file_import_activity": {"activity_name": "import_uploaded_file", "status": "completed", "file_object_id": file_object.id, "raw_record_id": record.id, "byte_size": file_object.byte_size}}
    workflow.status = "completed"
    workflow.payload = {**(workflow.payload or {}), "status": "completed", "raw_record_id": record.id, "file_import_activity": run.payload["file_import_activity"]}
    import_run.status = "completed"
    import_run.record_count = 1
    import_run.payload = {**(import_run.payload or {}), "raw_record_id": record.id, "file_import_activity": run.payload["file_import_activity"]}
    completed_payload = run.payload["file_import_activity"] | {"step_key": "store"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="file_upload_import_completed", status="completed", payload=completed_payload, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": "file_upload", "record_count": 1, "step_key": "store"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=completed_payload | {"collection_run_id": run.id}, created_at=_now()))
    _update_health(session, source.id, run.id, success=True, count=1)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="file_upload.file_run.completed",
        object_type="collection_run",
        object_id=run.id,
        after={"collection_run": serialize_collection_run(run), "import_run": serialize_import_run(import_run), "file_object_id": file_object.id, "raw_record_id": record.id},
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return {
        "collection_job": serialize_collection_job(job),
        "collection_run": serialize_collection_run(run),
        "import_run": serialize_import_run(import_run),
        "file_object": serialize_file_object(file_object),
        "raw_records": [serialize_raw_record(record)],
    }


def _ensure_collection_workflow_case(session: Session) -> None:
    if session.get(models.Case, COLLECTION_WORKFLOW_CASE_ID) is not None:
        return
    session.add(
        models.Case(
            id=COLLECTION_WORKFLOW_CASE_ID,
            slug="s2-collection-workflows",
            title="S2 Collection Workflow Ledger",
            scenario_type="xian_social_issue",
            status="active",
            payload={"system": True, "purpose": "collection workflow tracking"},
        )
    )


def _get_tenant_collection_run(session: Session, collection_run_id: str, tenant_id: str | None = None) -> models.CollectionRun:
    statement = select(models.CollectionRun).join(models.CollectionJob, models.CollectionRun.collection_job_id == models.CollectionJob.id).where(models.CollectionRun.id == collection_run_id)
    if tenant_id is not None:
        statement = statement.where(models.CollectionJob.tenant_id == tenant_id)
    run = session.execute(statement).scalar_one_or_none()
    if run is None:
        raise _api_error(404, "NOT_FOUND", "Collection run does not exist.")
    return run


def get_collection_run(session: Session, collection_run_id: str, tenant_id: str | None = None) -> dict:
    run = _get_tenant_collection_run(session, collection_run_id, tenant_id)
    return serialize_collection_run(run)


def _collection_step_key(event_type: str, payload: dict) -> str | None:
    for candidate in (payload.get("step_key"), payload.get("stage")):
        if isinstance(candidate, str) and candidate in COLLECTION_RUN_STEP_INDEX:
            return candidate
    for step_key in COLLECTION_RUN_STEP_INDEX:
        if event_type == step_key or event_type.startswith(f"{step_key}_"):
            return step_key
    if event_type in {"workflow_scheduled", "scheduled", "activity_started", "rate_limit_delayed", "blocked", "import_failed"}:
        return "fetch"
    if event_type in {"webhook_received", "records_created", "import_completed"}:
        return "store"
    return None


def _collection_step_status(event_type: str, status: str) -> str:
    if status in {"pending", "running", "retrying", "delayed", "cancelling", "failed", "completed", "canceled"}:
        return status
    if event_type.endswith("_completed") or event_type in {"records_created", "import_completed", "webhook_received"}:
        return "completed"
    if event_type.endswith("_started") or event_type == "activity_started":
        return "running"
    if event_type.endswith("_failed") or event_type in {"blocked", "import_failed"}:
        return "failed"
    return "pending"


def _serialize_run_step_event(source: str, event) -> dict:
    payload = event.payload or {}
    return {
        "event_id": event.id,
        "source": source,
        "event_type": event.event_type,
        "status": event.status,
        "step_key": _collection_step_key(event.event_type, payload),
        "payload": payload,
        "created_at": event.created_at,
    }


def _new_collection_step(definition: dict) -> dict:
    return {
        "step_key": definition["step_key"],
        "label": definition["label"],
        "description": definition["description"],
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "event_count": 0,
        "event_refs": [],
        "payload": {},
    }


def _mark_collection_step(step: dict, status: str, event: dict | None = None) -> None:
    rank = {"pending": 0, "running": 1, "retrying": 1, "delayed": 1, "cancelling": 1, "completed": 2, "failed": 3, "canceled": 3}
    if rank.get(status, 0) < rank.get(step["status"], 0):
        return
    step["status"] = status
    event_time = event.get("created_at") if event else None
    if status in {"running", "retrying", "delayed", "cancelling"} and step["started_at"] is None:
        step["started_at"] = event_time
    if status in {"completed", "failed", "canceled"}:
        step["completed_at"] = event_time
    if event:
        step["event_count"] += 1
        step["event_refs"].append({"source": event["source"], "event_id": event["event_id"], "event_type": event["event_type"]})
        step["payload"] = {"last_event_type": event["event_type"], "last_event_status": event["status"], "last_event_source": event["source"]}


def get_collection_run_steps(session: Session, collection_run_id: str, tenant_id: str) -> dict:
    run = _get_tenant_collection_run(session, collection_run_id, tenant_id)
    job = session.get(models.CollectionJob, run.collection_job_id)
    workflow_run_id = (run.payload or {}).get("workflow_run_id")
    workflow = session.get(models.WorkflowRun, workflow_run_id) if isinstance(workflow_run_id, str) else None
    collection_events = [
        _serialize_run_step_event("collection_run_event", event)
        for event in session.execute(
            select(models.CollectionRunEvent).where(models.CollectionRunEvent.collection_run_id == run.id).order_by(models.CollectionRunEvent.created_at.asc(), models.CollectionRunEvent.id.asc())
        ).scalars()
    ]
    workflow_events = []
    if workflow is not None:
        workflow_events = [
            _serialize_run_step_event("workflow_run_event", event)
            for event in session.execute(
                select(models.WorkflowRunEvent).where(models.WorkflowRunEvent.workflow_run_id == workflow.id).order_by(models.WorkflowRunEvent.created_at.asc(), models.WorkflowRunEvent.id.asc())
            ).scalars()
        ]
    raw_record_count = session.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.collection_run_id == run.id)).scalar_one()
    steps = [_new_collection_step(definition) for definition in COLLECTION_RUN_STEPS]
    by_key = {step["step_key"]: step for step in steps}
    events = sorted(collection_events + workflow_events, key=lambda item: (item["created_at"] or datetime.min, item["event_id"]))
    for event in events:
        step_key = event.get("step_key")
        if step_key not in by_key:
            continue
        _mark_collection_step(by_key[step_key], _collection_step_status(event["event_type"], event["status"]), event)

    highest_completed = max((COLLECTION_RUN_STEP_INDEX[step["step_key"]] for step in steps if step["status"] == "completed"), default=-1)
    if raw_record_count or run.record_count:
        highest_completed = max(highest_completed, COLLECTION_RUN_STEP_INDEX["store"])
    if run.status == "completed":
        highest_completed = len(steps) - 1
    for index in range(highest_completed + 1):
        if steps[index]["status"] == "pending":
            _mark_collection_step(steps[index], "completed")

    if run.status in {"running", "retrying"} and not any(step["status"] in {"running", "retrying"} for step in steps):
        for step in steps:
            if step["status"] == "pending":
                _mark_collection_step(step, run.status)
                break
    if run.status in {"failed", "canceled", "cancelling"}:
        terminal_status = "canceled" if run.status == "canceled" else run.status
        for step in steps:
            if step["status"] == "pending":
                _mark_collection_step(step, terminal_status)
                break

    return {
        "collection_run_id": run.id,
        "collection_job_id": run.collection_job_id,
        "data_source_id": run.data_source_id,
        "collection_job_status": job.status if job else None,
        "status": run.status,
        "workflow_run_id": workflow.id if workflow is not None else workflow_run_id,
        "workflow_status": workflow.status if workflow is not None else (run.payload or {}).get("workflow_status"),
        "raw_record_count": raw_record_count,
        "record_count": run.record_count,
        "trace_id": run.trace_id,
        "page_state": "ready",
        "steps": steps,
        "events": list(reversed(events)),
    }


def get_collection_run_metrics(session: Session, collection_run_id: str, actor: models.User, trace_id: str) -> dict:
    return _get_collection_run_metrics(
        session,
        collection_run_id,
        actor,
        trace_id,
        metric_scope_prefix="collection_run",
        audit_action="collection_run.metrics.read",
        inconsistent_action="collection_run.metrics.inconsistent",
        inconsistency_code="COLLECTION_RUN_METRICS_INCONSISTENT",
        inconsistency_message="Collection run metrics do not match persisted database records.",
    )


def get_cleaning_run_metrics(session: Session, cleaning_run_id: str, actor: models.User, trace_id: str) -> dict:
    return _get_collection_run_metrics(
        session,
        cleaning_run_id,
        actor,
        trace_id,
        metric_scope_prefix="cleaning_run",
        audit_action="cleaning_run.metrics.read",
        inconsistent_action="cleaning_run.metrics.inconsistent",
        inconsistency_code="CLEANING_RUN_METRICS_INCONSISTENT",
        inconsistency_message="Cleaning run metrics do not match persisted database records.",
    )


def _get_collection_run_metrics(
    session: Session,
    collection_run_id: str,
    actor: models.User,
    trace_id: str,
    *,
    metric_scope_prefix: str,
    audit_action: str,
    inconsistent_action: str,
    inconsistency_code: str,
    inconsistency_message: str,
) -> dict:
    run = _get_tenant_collection_run(session, collection_run_id, actor.tenant_id)
    job = session.get(models.CollectionJob, run.collection_job_id)
    source = session.get(models.DataSource, run.data_source_id)
    raw_record_count = session.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.collection_run_id == run.id)).scalar_one()
    payload_count = session.execute(
        select(func.count())
        .select_from(models.RawRecordPayload)
        .join(models.RawRecord, models.RawRecordPayload.raw_record_id == models.RawRecord.id)
        .where(models.RawRecord.collection_run_id == run.id)
    ).scalar_one()
    raw_ids = select(models.RawRecord.id).where(models.RawRecord.collection_run_id == run.id)
    lineage_edge_count = session.execute(
        select(func.count())
        .select_from(models.LineageEdge)
        .where(models.LineageEdge.to_object_type == "raw_record", models.LineageEdge.to_object_id.in_(raw_ids))
    ).scalar_one()
    cleaning_stats = _collection_run_cleaning_stats(session, raw_ids)
    quality_issue_count = session.execute(
        select(func.count())
        .select_from(models.RawRecordQualityIssue)
        .join(models.RawRecord, models.RawRecordQualityIssue.raw_record_id == models.RawRecord.id)
        .where(models.RawRecord.collection_run_id == run.id)
    ).scalar_one()
    import_runs = list(
        session.execute(
            select(models.ImportRun)
            .where(models.ImportRun.collection_run_id == run.id)
            .order_by(models.ImportRun.created_at.asc(), models.ImportRun.id.asc())
        ).scalars()
    )
    events = list(
        session.execute(
            select(models.CollectionRunEvent)
            .where(models.CollectionRunEvent.collection_run_id == run.id)
            .order_by(models.CollectionRunEvent.created_at.asc(), models.CollectionRunEvent.id.asc())
        ).scalars()
    )
    metrics = _collection_run_metric_counts(run, import_runs, events, raw_record_count, quality_issue_count)
    metrics["payload_count"] = payload_count
    metrics["lineage_edge_count"] = lineage_edge_count
    metrics.update(cleaning_stats["metrics"])
    metrics["failed_count"] = metrics.get("failed_count", 0) + cleaning_stats["metrics"]["cleaning_failed_count"] + cleaning_stats["metrics"]["extraction_failed_count"]
    consistency = _collection_run_metric_consistency(run, metrics, raw_record_count, payload_count, lineage_edge_count, cleaning_stats["checks"])
    result = {
        "cleaning_run_id": run.id,
        "collection_run_id": run.id,
        "collection_job_id": run.collection_job_id,
        "data_source_id": run.data_source_id,
        "source_type": source.source_type if source is not None else None,
        "status": run.status,
        "workflow_status": (run.payload or {}).get("workflow_status"),
        "trace_id": run.trace_id,
        "metrics": metrics,
        "consistency": consistency,
        "import_runs": [serialize_import_run(item) for item in import_runs],
        "event_count": len(events),
        "page_state": "ready",
    }
    metric_scope = f"{metric_scope_prefix}:{run.id}"
    snapshot = models.MetricsSnapshot(
        id=_id("MSNP"),
        metric_scope=metric_scope,
        payload={
            "collection_run_id": run.id,
            "metrics": metrics,
            "consistency": consistency,
            "trace_id": trace_id,
            "source_type": result["source_type"],
        },
        captured_at=_now(),
    )
    session.add(snapshot)
    if consistency["status"] != "consistent":
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action=inconsistent_action,
            object_type="collection_run",
            object_id=run.id,
            after={"metrics": metrics, "consistency": consistency, "metrics_snapshot_id": snapshot.id},
            trace_id=trace_id,
        )
        session.commit()
        raise _api_error(
            409,
            inconsistency_code,
            inconsistency_message,
            {"metrics": metrics, "consistency": consistency, "metrics_snapshot_id": snapshot.id},
        )
    result["snapshot"] = {"metrics_snapshot_id": snapshot.id, "metric_scope": metric_scope, "captured_at": snapshot.captured_at}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action=audit_action,
        object_type="collection_run",
        object_id=run.id,
        after={"metrics": metrics, "consistency": consistency, "metrics_snapshot_id": snapshot.id},
        trace_id=trace_id,
    )
    session.commit()
    return result


def _collection_run_cleaning_stats(session: Session, raw_ids) -> dict:
    normalization_output_count = session.execute(
        select(func.count())
        .select_from(models.RawRecordNormalization)
        .where(models.RawRecordNormalization.raw_record_id.in_(raw_ids))
    ).scalar_one()
    cleaned_count = session.execute(
        select(func.count(func.distinct(models.RawRecordNormalization.raw_record_id)))
        .select_from(models.RawRecordNormalization)
        .where(models.RawRecordNormalization.raw_record_id.in_(raw_ids))
    ).scalar_one()
    invalid_normalization_count = session.execute(
        select(func.count())
        .select_from(models.RawRecordNormalization)
        .where(
            models.RawRecordNormalization.raw_record_id.in_(raw_ids),
            models.RawRecordNormalization.payload["cleaner_status"].as_string() == "invalid",
        )
    ).scalar_one()
    signal_count = session.execute(
        select(func.count(func.distinct(models.LineageEdge.to_object_id)))
        .select_from(models.LineageEdge)
        .where(
            models.LineageEdge.from_object_type == "raw_record",
            models.LineageEdge.from_object_id.in_(raw_ids),
            models.LineageEdge.to_object_type == "signal",
            models.LineageEdge.relation == "extracted_signal",
        )
    ).scalar_one()
    extracted_count = session.execute(
        select(func.count(func.distinct(models.LineageEdge.from_object_id)))
        .select_from(models.LineageEdge)
        .where(
            models.LineageEdge.from_object_type == "raw_record",
            models.LineageEdge.from_object_id.in_(raw_ids),
            models.LineageEdge.to_object_type == "signal",
            models.LineageEdge.relation == "extracted_signal",
        )
    ).scalar_one()
    normalization_run_ids = [
        row[0]
        for row in session.execute(
            select(models.RawRecordNormalization.normalization_run_id)
            .where(models.RawRecordNormalization.raw_record_id.in_(raw_ids))
            .distinct()
        )
        if row[0]
    ]
    normalization_run_checks: list[dict] = []
    if normalization_run_ids:
        actual_counts = {
            row[0]: int(row[1])
            for row in session.execute(
                select(models.RawRecordNormalization.normalization_run_id, func.count())
                .where(models.RawRecordNormalization.normalization_run_id.in_(normalization_run_ids))
                .group_by(models.RawRecordNormalization.normalization_run_id)
            )
        }
        runs = list(
            session.execute(
                select(models.NormalizationRun).where(models.NormalizationRun.id.in_(normalization_run_ids))
            ).scalars()
        )
        for run in runs:
            actual = actual_counts.get(run.id, 0)
            normalization_run_checks.append(
                _metric_check(f"normalization_run_output_count_matches_rows:{run.id}", run.output_count, actual, critical=True)
            )
    checks = [
        {
            "code": "cleaned_count_matches_normalization_outputs",
            "passed": cleaned_count <= normalization_output_count,
            "expected": cleaned_count,
            "actual": normalization_output_count,
            "critical": True,
            "message": "Each cleaned record has at least one persisted normalization output." if cleaned_count <= normalization_output_count else "Cleaned count exceeds persisted normalization outputs.",
        },
        {
            "code": "extracted_count_matches_signal_lineage",
            "passed": extracted_count <= signal_count,
            "expected": extracted_count,
            "actual": signal_count,
            "critical": True,
            "message": "Each extracted record has at least one raw-to-signal lineage edge." if extracted_count <= signal_count else "Extracted count exceeds persisted signal lineage.",
        },
        *normalization_run_checks,
    ]
    return {
        "metrics": {
            "cleaned_count": int(cleaned_count or 0),
            "extracted_count": int(extracted_count or 0),
            "normalization_output_count": int(normalization_output_count or 0),
            "signal_count": int(signal_count or 0),
            "cleaning_failed_count": int(invalid_normalization_count or 0),
            "extraction_failed_count": 0,
        },
        "checks": checks,
    }


def _collection_run_metric_counts(run: models.CollectionRun, import_runs: list[models.ImportRun], events: list[models.CollectionRunEvent], raw_record_count: int, quality_issue_count: int) -> dict:
    repository = (run.payload or {}).get("raw_record_repository")
    repository_activities = _collection_run_metric_repository_activities(events)
    if repository_activities or isinstance(repository, dict):
        activities = repository_activities or [repository]
        stored_count = sum(_metric_int(activity.get("stored_count")) for activity in activities)
        deduped_count = sum(_metric_int(activity.get("duplicate_count")) for activity in activities)
        conflict_count = sum(_metric_int(activity.get("conflict_count")) for activity in activities)
        attempted_count = stored_count + deduped_count + conflict_count
        return {
            "fetched_count": attempted_count,
            "parsed_count": attempted_count,
            "stored_count": stored_count,
            "raw_record_count": raw_record_count,
            "payload_count": raw_record_count,
            "lineage_edge_count": 0,
            "failed_count": conflict_count,
            "deduped_count": deduped_count,
            "conflict_count": conflict_count,
            "quality_issue_count": quality_issue_count,
            "source": "raw_record_repository_events" if repository_activities else "raw_record_repository",
            "dedupe_hit_rate": round(deduped_count / max(stored_count + deduped_count, 1), 4),
        }

    activities = _collection_run_metric_activities(import_runs, events)
    fetched_count = 0
    parsed_count = 0
    stored_count = raw_record_count
    failed_count = 0
    deduped_count = 0
    conflict_count = 0
    for activity in activities:
        duplicates = _metric_int(activity.get("duplicate_count") or activity.get("skipped_existing_count"))
        conflicts = _metric_int(activity.get("conflict_count"))
        missing = _metric_int(activity.get("missing_count"))
        activity_stored = _metric_int(activity.get("new_record_count") or activity.get("raw_record_count") or activity.get("record_count"))
        attempted = max(
            _metric_int(activity.get("row_count")),
            _metric_int(activity.get("key_count")),
            _metric_int(activity.get("record_count")) + duplicates + conflicts + missing,
            activity_stored + duplicates + conflicts + missing,
        )
        fetched_count += attempted
        parsed_count += max(0, attempted - missing)
        deduped_count += duplicates
        conflict_count += conflicts
        failed_count += conflicts + missing
        if activity.get("error_code"):
            failed_count += max(1, attempted or 1)
    if not activities:
        fetched_count = raw_record_count
        parsed_count = raw_record_count
    if run.status == "failed" and failed_count == 0:
        failed_count = 1
    return {
        "fetched_count": fetched_count,
        "parsed_count": parsed_count,
        "stored_count": stored_count,
        "raw_record_count": raw_record_count,
        "payload_count": raw_record_count,
        "lineage_edge_count": 0,
        "failed_count": failed_count,
        "deduped_count": deduped_count,
        "conflict_count": conflict_count,
        "quality_issue_count": quality_issue_count,
        "source": "import_activity" if activities else "database_counts",
        "dedupe_hit_rate": round(deduped_count / max(stored_count + deduped_count, 1), 4),
    }


def _collection_run_metric_repository_activities(events: list[models.CollectionRunEvent]) -> list[dict]:
    activities: list[dict] = []
    for event in events:
        if event.event_type != "raw_record_repository_batch_stored":
            continue
        payload = event.payload if isinstance(event.payload, dict) else {}
        if payload.get("activity_name") == RAW_RECORD_REPOSITORY_ACTIVITY_NAME:
            activities.append(payload)
    return activities


def _collection_run_metric_activities(import_runs: list[models.ImportRun], events: list[models.CollectionRunEvent]) -> list[dict]:
    activities: list[dict] = []
    for import_run in import_runs:
        payload = import_run.payload if isinstance(import_run.payload, dict) else {}
        for value in payload.values():
            if isinstance(value, dict) and (value.get("activity_name") or value.get("raw_record_count") is not None or value.get("error_code")):
                activities.append(value)
    if activities:
        return activities
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if payload.get("activity_name") or payload.get("record_count") is not None or payload.get("error_code"):
            activities.append(payload)
    return activities


def _collection_run_metric_consistency(run: models.CollectionRun, metrics: dict, raw_record_count: int, payload_count: int, lineage_edge_count: int, extra_checks: list[dict] | None = None) -> dict:
    checks = [
        _metric_check("run_record_count_matches_raw_records", run.record_count, raw_record_count, critical=True),
        _metric_check("stored_count_matches_raw_records", metrics.get("stored_count"), raw_record_count, critical=True),
        _metric_check("payload_count_matches_raw_records", raw_record_count, payload_count, critical=raw_record_count > 0),
    ]
    if raw_record_count:
        checks.append({"code": "lineage_edges_present", "passed": lineage_edge_count >= raw_record_count, "expected": raw_record_count, "actual": lineage_edge_count, "critical": False, "message": "At least one lineage edge should exist for each raw record."})
    checks.extend(extra_checks or [])
    failed_critical = [item for item in checks if item["critical"] and not item["passed"]]
    return {
        "status": "inconsistent" if failed_critical else "consistent",
        "db_raw_record_count": raw_record_count,
        "raw_record_payload_count": payload_count,
        "lineage_edge_count": lineage_edge_count,
        "checks": checks,
    }


def _metric_check(code: str, expected, actual: int, critical: bool) -> dict:
    expected_int = _metric_int(expected)
    return {
        "code": code,
        "passed": expected_int == actual,
        "expected": expected_int,
        "actual": actual,
        "critical": critical,
        "message": "Metric matches persisted database records." if expected_int == actual else "Metric does not match persisted database records.",
    }


def _metric_int(value) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_optional_datetime(value: str | None, code: str) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    except ValueError as exc:
        raise _api_error(422, code, "Datetime filter must be ISO-8601.") from exc


def list_collection_runs(
    session: Session,
    tenant_id: str,
    status: str | None = None,
    data_source_id: str | None = None,
    collection_job_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], dict]:
    allowed_statuses = {"pending", "running", "retrying", "delayed", "cancelling", "failed", "completed", "canceled"}
    if status and status not in allowed_statuses:
        raise _api_error(422, "COLLECTION_RUN_STATUS_INVALID", "Unsupported collection run status filter.")
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [models.CollectionJob.tenant_id == tenant_id]
    if status:
        filters.append(models.CollectionRun.status == status)
    if data_source_id:
        filters.append(models.CollectionRun.data_source_id == data_source_id)
    if collection_job_id:
        filters.append(models.CollectionRun.collection_job_id == collection_job_id)
    from_dt = _parse_optional_datetime(created_from, "COLLECTION_RUN_CREATED_FROM_INVALID")
    to_dt = _parse_optional_datetime(created_to, "COLLECTION_RUN_CREATED_TO_INVALID")
    if from_dt is not None:
        filters.append(models.CollectionRun.created_at >= from_dt)
    if to_dt is not None:
        filters.append(models.CollectionRun.created_at <= to_dt)
    base = select(models.CollectionRun).join(models.CollectionJob, models.CollectionRun.collection_job_id == models.CollectionJob.id).where(*filters)
    total = session.execute(select(func.count()).select_from(models.CollectionRun).join(models.CollectionJob, models.CollectionRun.collection_job_id == models.CollectionJob.id).where(*filters)).scalar_one()
    rows = session.execute(
        base.order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    meta = {"pagination": {"page": page, "page_size": page_size, "total": total}, "filters": {"status": status, "data_source_id": data_source_id, "collection_job_id": collection_job_id, "created_from": created_from, "created_to": created_to}}
    return [serialize_collection_run(row) for row in rows], meta


def cancel_collection_run(session: Session, collection_run_id: str, actor: models.User, trace_id: str) -> dict:
    run = session.get(models.CollectionRun, collection_run_id)
    if run is None:
        raise _api_error(404, "NOT_FOUND", "Collection run does not exist.")
    if run.status not in {"pending", "running", "retrying", "delayed", "cancelling"}:
        raise _api_error(409, "COLLECTION_RUN_TERMINAL", "Terminal collection runs cannot be canceled.")
    before = serialize_collection_run(run)
    payload = dict(run.payload or {})
    previous_status = run.status
    workflow_run_id = payload.get("workflow_run_id")
    cancel_payload = {
        "requested_by": actor.id,
        "requested_by_username": actor.username,
        "requested_at": _now().isoformat(),
        "trace_id": trace_id,
        "previous_status": previous_status,
        "transition": f"{previous_status}->cancelling->canceled",
        "worker_stop": "local_stop_confirmed",
    }
    run.status = "cancelling"
    payload["cancel"] = cancel_payload
    payload["workflow_status"] = "cancelling"
    run.payload = payload
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="cancel_requested", status=run.status, payload={"actor": actor.username}))
    if workflow_run_id:
        workflow = session.get(models.WorkflowRun, workflow_run_id)
        if workflow is not None:
            workflow.status = "cancelling"
            workflow.payload = {**(workflow.payload or {}), "cancel": cancel_payload}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="cancel_requested", status="cancelling", payload={"collection_run_id": run.id, "trace_id": trace_id}))
    run.status = "canceled"
    payload["cancel"] = {**cancel_payload, "completed_at": _now().isoformat()}
    payload["workflow_status"] = "canceled"
    run.payload = payload
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="cancel_completed", status=run.status, payload={"actor": actor.username, "worker_stop": "local_stop_confirmed"}))
    if workflow_run_id:
        workflow = session.get(models.WorkflowRun, workflow_run_id)
        if workflow is not None:
            workflow.status = "canceled"
            workflow.payload = {**(workflow.payload or {}), "cancel": payload["cancel"]}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="cancel_completed", status="canceled", payload={"collection_run_id": run.id, "trace_id": trace_id}))
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_run.cancel",
        object_type="collection_run",
        object_id=run.id,
        before=before,
        after=serialize_collection_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_run(run)


def retry_collection_run(session: Session, collection_run_id: str, actor: models.User, trace_id: str) -> dict:
    original = session.get(models.CollectionRun, collection_run_id)
    if original is None:
        raise _api_error(404, "NOT_FOUND", "Collection run does not exist.")
    if original.status not in {"failed", "canceled"}:
        raise _api_error(409, "COLLECTION_RUN_NOT_RETRYABLE", "Only failed or canceled collection runs can be retried.")
    job = session.get(models.CollectionJob, original.collection_job_id)
    if job is None:
        raise _api_error(404, "NOT_FOUND", "Collection job does not exist.")
    source = get_data_source(session, original.data_source_id)
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot retry collection runs.")
    if source.status != "active":
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Only active data sources can retry collection runs.")
    if job.status == "paused":
        raise _api_error(409, "COLLECTION_JOB_PAUSED", "Paused collection jobs cannot retry collection runs.")
    active_retry = session.execute(
        select(models.CollectionRun).where(
            models.CollectionRun.collection_job_id == job.id,
            models.CollectionRun.status.in_(["pending", "running", "retrying", "cancelling"]),
            models.CollectionRun.payload["retry_of"].as_string() == original.id,
        )
    ).scalar_one_or_none()
    if active_retry is not None:
        raise _api_error(409, "COLLECTION_RETRY_ALREADY_ACTIVE", "A retry run is already pending or running for this collection run.")
    retry_attempt = int((original.payload or {}).get("retry_count") or 0) + 1
    input_snapshot = (original.payload or {}).get("input_snapshot") or {
        "collection_job_id": job.id,
        "data_source_id": source.id,
        "job_payload": job.payload,
        "original_run_payload": original.payload,
    }
    retry_payload = {
        "retry_of": original.id,
        "retry_attempt": retry_attempt,
        "retry_reason": original.error_code,
        "input_snapshot": input_snapshot,
    }
    retry_payload.update(_collection_version_payload(source, job.payload))
    collection_channel = _collection_job_channel(source, job.payload)
    rate_limit = apply_channel_rate_limit(session, source, collection_channel, actor, trace_id, job.id, "collection_run.retry")
    if rate_limit is None:
        rate_limit = _evaluate_source_rate_limit(session, source, actor, trace_id, job.id, "collection_run.retry")
    if rate_limit is not None and not rate_limit["allowed"]:
        delayed_run = _create_delayed_collection_run(session, job, source, actor, trace_id, rate_limit, {**retry_payload, "retry_delayed": True})
        original_payload = dict(original.payload or {})
        original_payload["last_retry_run_id"] = delayed_run.id
        original_payload["retry_count"] = retry_attempt
        original_payload["last_retry_status"] = "delayed"
        original.payload = original_payload
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="collection_run.retry_delayed",
            object_type="collection_run",
            object_id=original.id,
            after={"retry_run": serialize_collection_run(delayed_run)},
            trace_id=trace_id,
        )
        session.commit()
        return serialize_collection_run(delayed_run)
    if rate_limit is not None:
        retry_payload["rate_limit"] = rate_limit
    _ensure_collection_workflow_case(session)
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"CollectSourceRunWorkflow-{run_id}"
    retry_payload.update(
        {
            "workflow_run_id": workflow_run_id,
            "workflow_name": "CollectSourceRunWorkflow",
            "workflow_id": workflow_id,
            "workflow_status": "pending",
            "started_by": actor.id,
        }
    )
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="pending",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload=retry_payload,
    )
    session.add(run)
    input_hash = _hash(json.dumps({"retry_of": original.id, "input_snapshot": input_snapshot, "attempt": retry_attempt}, sort_keys=True, ensure_ascii=True))
    session.add(
        models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="CollectSourceRunWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={"collection_job_id": job.id, "collection_run_id": run.id, "data_source_id": source.id, "retry_of": original.id, "input_hash": input_hash, "attempt": retry_attempt},
        )
    )
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="retry_scheduled", status="pending", payload={"retry_of": original.id, "workflow_run_id": workflow_run_id}))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow_run_id, event_type="scheduled", status="pending", payload={"collection_run_id": run.id, "retry_of": original.id}))
    retry_payload = dict(original.payload or {})
    retry_payload["last_retry_run_id"] = run.id
    retry_payload["retry_count"] = retry_attempt
    original.payload = retry_payload
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_run.retry",
        object_type="collection_run",
        object_id=original.id,
        after={"retry_run": serialize_collection_run(run)},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_run(run)


def _channel_checkpoint_for_run(run: models.CollectionRun, channel: str | None) -> dict | None:
    payload = run.payload if isinstance(run.payload, dict) else {}
    checkpoints = payload.get("channel_checkpoints") if isinstance(payload.get("channel_checkpoints"), dict) else {}
    if channel and isinstance(checkpoints.get(channel), dict):
        checkpoint = dict(checkpoints[channel])
    else:
        checkpoint = dict(payload.get("channel_checkpoint") if isinstance(payload.get("channel_checkpoint"), dict) else {})
    checkpoint_channel = _normalize_collection_channel(checkpoint.get("channel"))
    if checkpoint and channel and checkpoint_channel and checkpoint_channel != channel:
        raise _api_error(409, "CHANNEL_CHECKPOINT_MISMATCH", "Collection run checkpoint belongs to a different channel.")
    if not checkpoint:
        return None
    has_resume_boundary = any(checkpoint.get(key) for key in ("checkpoint_id", "cursor", "last_raw_record_id", "last_raw_content_hash", "offset", "resume_from_step"))
    if not has_resume_boundary:
        return None
    if channel:
        checkpoint["channel"] = channel
    checkpoint.setdefault("checkpoint_id", _id("CHK"))
    checkpoint.setdefault("resume_from_step", "fetch")
    return checkpoint


def _checkpoint_raw_replay_guard(session: Session, original: models.CollectionRun, checkpoint: dict) -> dict:
    raw_count = session.execute(select(func.count()).select_from(models.RawRecord).where(models.RawRecord.collection_run_id == original.id)).scalar_one()
    return {
        "skip_existing_raw": True,
        "existing_raw_record_count": int(raw_count or 0),
        "last_raw_record_id": checkpoint.get("last_raw_record_id"),
        "last_raw_content_hash": checkpoint.get("last_raw_content_hash"),
        "dedupe_required": True,
    }


def replay_channel_run_from_checkpoint(session: Session, collection_run_id: str, request, actor: models.User, trace_id: str) -> dict:
    original = session.get(models.CollectionRun, collection_run_id)
    if original is None:
        raise _api_error(404, "NOT_FOUND", "Collection run does not exist.")
    if original.status not in {"failed", "canceled"}:
        raise _api_error(409, "COLLECTION_RUN_NOT_REPLAYABLE", "Only failed or canceled collection runs can be replayed from a checkpoint.")
    job = session.get(models.CollectionJob, original.collection_job_id)
    if job is None:
        raise _api_error(404, "NOT_FOUND", "Collection job does not exist.")
    source = get_data_source(session, original.data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled data sources cannot replay collection runs.")
    if source.status != "active":
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Only active data sources can replay collection runs.")
    if job.status == "paused":
        raise _api_error(409, "COLLECTION_JOB_PAUSED", "Paused collection jobs cannot replay collection runs.")
    channel = _collection_job_channel(source, job.payload) or _normalize_collection_channel((original.payload or {}).get("collection_channel"))
    checkpoint = _channel_checkpoint_for_run(original, channel)
    if checkpoint is None:
        raise _api_error(409, "CHANNEL_CHECKPOINT_MISSING", "Channel replay requires a persisted checkpoint on the failed run.")
    active_replay = session.execute(
        select(models.CollectionRun).where(
            models.CollectionRun.collection_job_id == job.id,
            models.CollectionRun.status.in_(["pending", "running", "retrying", "delayed", "cancelling"]),
            models.CollectionRun.payload["replay_of"].as_string() == original.id,
        )
    ).scalar_one_or_none()
    if active_replay is not None:
        raise _api_error(409, "CHANNEL_REPLAY_ALREADY_ACTIVE", "A checkpoint replay is already active for this collection run.")
    raw_guard = _checkpoint_raw_replay_guard(session, original, checkpoint)
    replay_attempt = int((original.payload or {}).get("channel_replay_count") or 0) + 1
    input_snapshot = {
        "collection_job_id": job.id,
        "data_source_id": source.id,
        "job_payload": job.payload,
        "original_run_payload": original.payload,
        "checkpoint": checkpoint,
    }
    _ensure_collection_workflow_case(session)
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"ReplayChannelRunFromCheckpointWorkflow-{run_id}"
    replay_payload = {
        "replay_of": original.id,
        "replay_attempt": replay_attempt,
        "replay_strategy": "channel_checkpoint",
        "collection_channel": channel,
        "channel_checkpoint": checkpoint,
        "resume_from_step": checkpoint.get("resume_from_step", "fetch"),
        "raw_replay_guard": raw_guard,
        "input_snapshot": input_snapshot,
        "workflow_run_id": workflow_run_id,
        "workflow_name": "ReplayChannelRunFromCheckpointWorkflow",
        "workflow_id": workflow_id,
        "workflow_status": "pending",
        "started_by": actor.id,
        "request_payload": getattr(request, "payload", {}) or {},
    }
    replay_payload.update(_collection_version_payload(source, job.payload))
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="pending",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload=replay_payload,
    )
    input_hash = _hash(json.dumps({"replay_of": original.id, "checkpoint": checkpoint, "attempt": replay_attempt}, sort_keys=True, ensure_ascii=True))
    session.add(run)
    session.add(
        models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="ReplayChannelRunFromCheckpointWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={
                "collection_job_id": job.id,
                "collection_run_id": run.id,
                "data_source_id": source.id,
                "replay_of": original.id,
                "collection_channel": channel,
                "checkpoint_id": checkpoint.get("checkpoint_id"),
                "input_hash": input_hash,
            },
        )
    )
    event_payload = {
        "replay_of": original.id,
        "collection_channel": channel,
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "resume_from_step": replay_payload["resume_from_step"],
        "raw_replay_guard": raw_guard,
        "workflow_run_id": workflow_run_id,
    }
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="channel_replay_scheduled", status="pending", payload=event_payload))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow_run_id, event_type="scheduled", status="pending", payload=event_payload | {"collection_run_id": run.id}))
    original_payload = dict(original.payload or {})
    original_payload["last_channel_replay_run_id"] = run.id
    original_payload["last_channel_replay_status"] = "pending"
    original_payload["channel_replay_count"] = replay_attempt
    original.payload = original_payload
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_run.channel_replay",
        object_type="collection_run",
        object_id=original.id,
        after={"replay_run": serialize_collection_run(run), "checkpoint": checkpoint, "raw_replay_guard": raw_guard},
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_collection_run(run)


def generate_xian_synthetic_samples(session: Session, actor: models.User, trace_id: str) -> dict:
    source = session.get(models.DataSource, "DS-XIAN-SYNTHETIC-SOCIAL-V1")
    if source is None:
        source = models.DataSource(
            id="DS-XIAN-SYNTHETIC-SOCIAL-V1",
            tenant_id=DEFAULT_TENANT_ID,
            name="西安第一阶段社会议题合成源",
            source_type="synthetic",
            status="active",
            is_synthetic=True,
            policy={"access_mode": "test_fixture", "policy_result": {"allowed": True, "reason": None}},
            payload={"city_id": "xian", "synthetic": True},
        )
        session.add(source)
        session.flush()
        session.add(models.SourceHealth(id="SH-XIAN-SYNTHETIC-SOCIAL-V1", data_source_id=source.id, status="healthy", payload={"synthetic": True}))
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        name="合成西安社会议题采集任务",
        status="active",
        schedule=None,
        payload={"synthetic": True},
    )
    run = models.CollectionRun(
        id=_id("CRUN"),
        collection_job_id=job.id,
        data_source_id=source.id,
        status="completed",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload={"generator": "xian_social_issues_v1", "synthetic": True},
    )
    session.add(job)
    session.add(run)
    records = []
    for sample in _xian_samples():
        record = _create_raw_record(session, source, run, sample)
        records.append(record)
    run.record_count = len(records)
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="records_created", status="completed", payload={"record_count": len(records)}))
    _update_health(session, source.id, run.id, success=True, count=len(records))
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="synthetic_xian_samples.generate",
        object_type="collection_run",
        object_id=run.id,
        after={"record_count": len(records), "synthetic": True},
        trace_id=trace_id,
    )
    session.commit()
    return {"data_source": serialize_data_source(source), "collection_job": serialize_collection_job(job), "collection_run": serialize_collection_run(run), "raw_records": [serialize_raw_record(item) for item in records]}


def run_import(session: Session, request, actor: models.User, trace_id: str, import_type: str) -> dict:
    source = get_data_source(session, request.data_source_id)
    run_id = _id("CRUN")
    run_payload = {"import_type": import_type}
    workflow: models.WorkflowRun | None = None
    activity_name: str | None = None
    if import_type == "public_web":
        activity_name = PUBLIC_WEB_FETCH_ACTIVITY_NAME
        _ensure_collection_workflow_case(session)
        workflow_run_id = _id("WFR")
        workflow_id = f"FetchPublicWebPageWorkflow-{run_id}"
        run_payload.update(
            {
                "workflow_run_id": workflow_run_id,
                "workflow_name": "FetchPublicWebPageWorkflow",
                "workflow_id": workflow_id,
                "workflow_status": "pending",
                "activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME,
                "started_by": actor.id,
            }
        )
        workflow = models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="FetchPublicWebPageWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={
                "collection_run_id": run_id,
                "data_source_id": source.id,
                "source_uri": request.source_uri,
                "activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME,
                "input_hash": _hash(json.dumps({"data_source_id": source.id, "source_uri": request.source_uri, "title": request.title, "payload": request.payload}, sort_keys=True, ensure_ascii=True)),
            },
        )
    elif import_type == "official_api":
        activity_name = OFFICIAL_API_FETCH_ACTIVITY_NAME
        _ensure_collection_workflow_case(session)
        workflow_run_id = _id("WFR")
        workflow_id = f"FetchOfficialApiPageWorkflow-{run_id}"
        run_payload.update(
            {
                "workflow_run_id": workflow_run_id,
                "workflow_name": "FetchOfficialApiPageWorkflow",
                "workflow_id": workflow_id,
                "workflow_status": "pending",
                "activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME,
                "started_by": actor.id,
            }
        )
        workflow = models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="FetchOfficialApiPageWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={
                "collection_run_id": run_id,
                "data_source_id": source.id,
                "source_uri": request.source_uri,
                "activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME,
                "input_hash": _hash(json.dumps({"data_source_id": source.id, "source_uri": request.source_uri, "title": request.title, "payload": request.payload}, sort_keys=True, ensure_ascii=True)),
            },
        )
    elif import_type == "rss":
        activity_name = RSS_FETCH_ACTIVITY_NAME
        _ensure_collection_workflow_case(session)
        workflow_run_id = _id("WFR")
        workflow_id = f"FetchRssItemsWorkflow-{run_id}"
        run_payload.update(
            {
                "workflow_run_id": workflow_run_id,
                "workflow_name": "FetchRssItemsWorkflow",
                "workflow_id": workflow_id,
                "workflow_status": "pending",
                "activity_name": RSS_FETCH_ACTIVITY_NAME,
                "started_by": actor.id,
            }
        )
        workflow = models.WorkflowRun(
            id=workflow_run_id,
            case_id=COLLECTION_WORKFLOW_CASE_ID,
            tenant_id=actor.tenant_id,
            workflow_name="FetchRssItemsWorkflow",
            workflow_id=workflow_id,
            status="pending",
            started_by=actor.id,
            trace_id=trace_id,
            payload={
                "collection_run_id": run_id,
                "data_source_id": source.id,
                "feed_url": request.source_uri or _rss_feed_url(source.policy or {}),
                "activity_name": RSS_FETCH_ACTIVITY_NAME,
                "input_hash": _hash(json.dumps({"data_source_id": source.id, "source_uri": request.source_uri, "title": request.title, "payload": request.payload}, sort_keys=True, ensure_ascii=True)),
            },
        )
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        name=f"{import_type} import",
        status="active" if source.status == "active" else "blocked",
        schedule=None,
        payload={"import_type": import_type},
    )
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="running",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload=run_payload,
    )
    import_run = models.ImportRun(
        id=_id("IMPR"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        import_type=import_type,
        status="running",
        is_synthetic=bool(request.is_synthetic or source.is_synthetic),
        trace_id=trace_id,
        payload={"source_uri": request.source_uri, "payload": request.payload},
    )
    session.add(job)
    session.flush()
    session.add(run)
    session.add(import_run)
    if workflow is not None:
        session.add(workflow)
        session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="scheduled", status="pending", payload={"collection_run_id": run.id, "activity_name": activity_name, "step_key": "fetch"}, created_at=_now()))
    session.flush()

    policy_result = evaluate_policy(source.source_type, source.policy, source.status)
    if not policy_result["allowed"]:
        _fail_import(session, run, import_run, source, policy_result["reason"] or "SOURCE_POLICY_BLOCKED", "Source policy blocks import.", retryable=source.source_type == "official_api", actor=actor, trace_id=trace_id)
        if workflow is not None:
            workflow.status = "failed"
            workflow.payload = {**(workflow.payload or {}), "error_code": policy_result["reason"] or "SOURCE_POLICY_BLOCKED"}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="blocked", status="failed", payload={"collection_run_id": run.id, "activity_name": activity_name, "error_code": policy_result["reason"] or "SOURCE_POLICY_BLOCKED", "step_key": "fetch"}, created_at=_now()))
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.blocked", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": []}

    content = request.content
    is_synthetic = bool(request.is_synthetic or source.is_synthetic)
    fetch_result = None
    if import_type == "public_web":
        fetch_started = {"activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME, "source_uri": request.source_uri, "step_key": "fetch"}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_public_web_page_started", status="running", payload=fetch_started, created_at=_now()))
        if workflow is not None:
            workflow.status = "running"
            workflow.payload = {**(workflow.payload or {}), "started_at": _now().isoformat()}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=fetch_started, created_at=_now()))
        fetch_result = _fetch_public_web_page(source, request)
        fetch_activity = _public_web_fetch_activity_payload(fetch_result)
        is_synthetic = bool(is_synthetic or fetch_result["is_synthetic"])
        run.payload = {**(run.payload or {}), "workflow_status": "running", "fetch_activity": fetch_activity}
        import_run.payload = {**(import_run.payload or {}), "fetch_activity": fetch_activity}
        import_run.is_synthetic = is_synthetic
        if not fetch_result["ok"]:
            _fail_import(session, run, import_run, source, fetch_result["error_code"], fetch_result["error_message"], retryable=bool(fetch_result.get("retryable")), actor=actor, trace_id=trace_id)
            session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_public_web_page_failed", status="failed", payload=fetch_activity | {"step_key": "fetch"}, created_at=_now()))
            run.payload = {**(run.payload or {}), "workflow_status": "failed", "fetch_activity": fetch_activity}
            if workflow is not None:
                workflow.status = "failed"
                workflow.payload = {**(workflow.payload or {}), "status": "failed", "fetch_activity": fetch_activity, "error_code": fetch_result["error_code"]}
                session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload=fetch_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
            write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
            session.commit()
            return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": []}
        content = fetch_result["content"]
    if import_type == "official_api":
        official_started = {"activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME, "source_uri": request.source_uri, "step_key": "fetch"}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_official_api_page_started", status="running", payload=official_started, created_at=_now()))
        if workflow is not None:
            workflow.status = "running"
            workflow.payload = {**(workflow.payload or {}), "started_at": _now().isoformat()}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=official_started, created_at=_now()))
        official_result = _fetch_official_api_pages(source, request)
        official_activity = _official_api_activity_payload(official_result)
        is_synthetic = bool(is_synthetic or official_result["is_synthetic"])
        run.payload = {**(run.payload or {}), "workflow_status": "running", "official_api_activity": official_activity}
        import_run.payload = {**(import_run.payload or {}), "official_api_activity": official_activity}
        import_run.is_synthetic = is_synthetic
        if not official_result["ok"]:
            _fail_import(session, run, import_run, source, official_result["error_code"], official_result["error_message"], retryable=bool(official_result.get("retryable")), actor=actor, trace_id=trace_id)
            session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_official_api_page_failed", status="failed", payload=official_activity | {"step_key": "fetch"}, created_at=_now()))
            run.payload = {**(run.payload or {}), "workflow_status": "failed", "official_api_activity": official_activity}
            if workflow is not None:
                workflow.status = "failed"
                workflow.payload = {**(workflow.payload or {}), "status": "failed", "official_api_activity": official_activity, "error_code": official_result["error_code"]}
                session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload=official_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
            write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
            session.commit()
            return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": []}
        records = []
        for item in official_result["records"]:
            records.append(_create_official_api_raw_record(session, source, run, import_run, request, item, official_activity, is_synthetic))
        run.status = "completed"
        run.record_count = len(records)
        import_run.status = "completed"
        import_run.record_count = len(records)
        official_activity = official_activity | {"raw_record_count": len(records)}
        run.payload = {**(run.payload or {}), "workflow_status": "completed", "official_api_activity": official_activity}
        import_run.payload = {**(import_run.payload or {}), "official_api_activity": official_activity}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_official_api_page_completed", status="completed", payload=official_activity | {"step_key": "fetch"}, created_at=_now()))
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": import_type, "record_count": len(records)}))
        if workflow is not None:
            workflow.status = "completed"
            workflow.payload = {**(workflow.payload or {}), "status": "completed", "official_api_activity": official_activity, "raw_record_count": len(records)}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=official_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
        _update_health(session, source.id, run.id, success=True, count=len(records))
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.completed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": [serialize_raw_record(record) for record in records]}
    if import_type == "rss":
        rss_started = {"activity_name": RSS_FETCH_ACTIVITY_NAME, "feed_url": request.source_uri or _rss_feed_url(source.policy or {}), "step_key": "fetch"}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_rss_items_started", status="running", payload=rss_started, created_at=_now()))
        if workflow is not None:
            workflow.status = "running"
            workflow.payload = {**(workflow.payload or {}), "started_at": _now().isoformat()}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_started", status="running", payload=rss_started, created_at=_now()))
        rss_result = _fetch_rss_items(source, request)
        rss_activity = _rss_fetch_activity_payload(rss_result)
        is_synthetic = bool(is_synthetic or rss_result["is_synthetic"])
        run.payload = {**(run.payload or {}), "workflow_status": "running", "rss_activity": rss_activity}
        import_run.payload = {**(import_run.payload or {}), "rss_activity": rss_activity}
        import_run.is_synthetic = is_synthetic
        if not rss_result["ok"]:
            _fail_import(session, run, import_run, source, rss_result["error_code"], rss_result["error_message"], retryable=bool(rss_result.get("retryable")), actor=actor, trace_id=trace_id)
            session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_rss_items_failed", status="failed", payload=rss_activity | {"step_key": "fetch"}, created_at=_now()))
            run.payload = {**(run.payload or {}), "workflow_status": "failed", "rss_activity": rss_activity}
            if workflow is not None:
                workflow.status = "failed"
                workflow.payload = {**(workflow.payload or {}), "status": "failed", "rss_activity": rss_activity, "error_code": rss_result["error_code"]}
                session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload=rss_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
            write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
            session.commit()
            return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": []}
        existing_keys = _existing_rss_item_keys(session, source.id)
        seen_keys: set[str] = set()
        records = []
        duplicate_count = 0
        for item in rss_result["items"]:
            item_identity = _rss_item_identity(item)
            item_keys = set(item_identity["keys"])
            if item_keys & existing_keys or item_keys & seen_keys:
                duplicate_count += 1
                continue
            seen_keys.update(item_keys)
            try:
                with session.begin_nested():
                    records.append(_create_rss_raw_record(session, source, run, import_run, item, rss_activity, is_synthetic, item_identity))
            except IntegrityError:
                duplicate_count += 1
                existing_keys.update(item_keys)
        run.status = "completed"
        run.record_count = len(records)
        import_run.status = "completed"
        import_run.record_count = len(records)
        rss_activity = rss_activity | {"new_record_count": len(records), "duplicate_count": duplicate_count, "raw_record_count": len(records)}
        run.payload = {**(run.payload or {}), "workflow_status": "completed", "rss_activity": rss_activity}
        import_run.payload = {**(import_run.payload or {}), "rss_activity": rss_activity}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_rss_items_completed", status="completed", payload=rss_activity | {"step_key": "fetch"}, created_at=_now()))
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": import_type, "record_count": len(records), "duplicate_count": duplicate_count}))
        if workflow is not None:
            workflow.status = "completed"
            workflow.payload = {**(workflow.payload or {}), "status": "completed", "rss_activity": rss_activity, "raw_record_count": len(records)}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=rss_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
        _update_health(session, source.id, run.id, success=True, count=len(records))
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.completed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": [serialize_raw_record(record) for record in records]}
    if not content and is_synthetic:
        content = f"synthetic import payload for {import_type}: {request.title} from {request.source_uri or source.name}"
    if not content:
        _fail_import(session, run, import_run, source, "IMPORT_CONTENT_MISSING", "Import content is required unless the request is explicitly synthetic.", retryable=False, actor=actor, trace_id=trace_id)
        if workflow is not None:
            workflow.status = "failed"
            workflow.payload = {**(workflow.payload or {}), "error_code": "IMPORT_CONTENT_MISSING"}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload={"collection_run_id": run.id, "error_code": "IMPORT_CONTENT_MISSING", "activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME, "step_key": "fetch"}, created_at=_now()))
        write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.failed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
        session.commit()
        return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": []}

    record = _create_import_raw_record(session, source, run, import_run, request, import_type, content, is_synthetic, fetch_result)
    run.status = "completed"
    run.record_count = 1
    import_run.status = "completed"
    import_run.record_count = 1
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_completed", status="completed", payload={"import_type": import_type, "record_count": 1}))
    if import_type == "public_web" and fetch_result is not None:
        fetch_activity = _public_web_fetch_activity_payload(fetch_result) | {"raw_record_id": record.id}
        run.payload = {**(run.payload or {}), "workflow_status": "completed", "fetch_activity": fetch_activity}
        import_run.payload = {**(import_run.payload or {}), "fetch_activity": fetch_activity, "raw_record_id": record.id}
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="fetch_public_web_page_completed", status="completed", payload=fetch_activity | {"step_key": "fetch"}, created_at=_now()))
        if workflow is not None:
            workflow.status = "completed"
            workflow.payload = {**(workflow.payload or {}), "status": "completed", "fetch_activity": fetch_activity, "raw_record_id": record.id}
            session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=fetch_activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))
    _update_health(session, source.id, run.id, success=True, count=1)
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action=f"import.{import_type}.completed", object_type="import_run", object_id=import_run.id, after=serialize_import_run(import_run), trace_id=trace_id)
    session.commit()
    return {"import_run": serialize_import_run(import_run), "collection_run": serialize_collection_run(run), "raw_records": [serialize_raw_record(record)]}


def list_import_runs(session: Session, limit: int = 50) -> list[dict]:
    rows = session.execute(select(models.ImportRun).order_by(models.ImportRun.created_at.desc()).limit(limit)).scalars()
    return [serialize_import_run(row) for row in rows]


def list_dead_letters(
    session: Session,
    tenant_id: str,
    status: str | None = None,
    data_source_id: str | None = None,
    error_code: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], dict]:
    rows = list(
        session.execute(
            select(models.OpsErrorQueue)
            .where(models.OpsErrorQueue.source == "dead_letter")
            .order_by(models.OpsErrorQueue.created_at.desc(), models.OpsErrorQueue.id.desc())
        ).scalars()
    )
    serialized = []
    for row in rows:
        payload = row.payload or {}
        if payload.get("tenant_id") != tenant_id:
            continue
        item = serialize_dead_letter(row)
        if status and item["status"] != status:
            continue
        if data_source_id and item["data_source_id"] != data_source_id:
            continue
        if error_code and item["error_code"] != error_code:
            continue
        serialized.append(item)
    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 100))
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return serialized[start:end], {"pagination": {"page": safe_page, "page_size": safe_page_size, "total": len(serialized)}}


def replay_dead_letter(session: Session, dead_letter_id: str, request, actor: models.User, trace_id: str) -> dict:
    row = session.get(models.OpsErrorQueue, dead_letter_id)
    if row is None or row.source != "dead_letter":
        raise _api_error(404, "DEAD_LETTER_NOT_FOUND", "Dead letter does not exist.")
    payload = dict(row.payload or {})
    if payload.get("tenant_id") != actor.tenant_id:
        raise _api_error(403, "FORBIDDEN", "Dead letter belongs to another tenant.")
    if payload.get("target_type") != "import_run":
        raise _api_error(422, "DEAD_LETTER_TARGET_UNSUPPORTED", "Only import_run dead letters can be replayed.")

    replay_state = payload.get("replay") if isinstance(payload.get("replay"), dict) else {}
    if row.status == "resolved" and replay_state.get("status") == "completed":
        no_op = dict(replay_state)
        no_op["status"] = "already_completed"
        return {"dead_letter": serialize_dead_letter(row), "replay": no_op, "replay_result": _dead_letter_replay_result(session, replay_state)}

    source = session.get(models.DataSource, payload.get("data_source_id"))
    if source is None:
        raise _api_error(404, "DATA_SOURCE_NOT_FOUND", "Dead letter source no longer exists.")
    stored_version = payload.get("source_version") if isinstance(payload.get("source_version"), dict) else {}
    current_version = _collection_version_payload(source)
    if stored_version.get("data_source_config_hash") and stored_version.get("data_source_config_hash") != current_version.get("data_source_config_hash"):
        raise _api_error(
            409,
            "DATA_SOURCE_VERSION_INCOMPATIBLE",
            "Dead letter replay requires the same data source version/config hash that produced the failed payload.",
            {"dead_letter_source_version": stored_version, "current_source_version": current_version},
        )

    original_import = session.get(models.ImportRun, payload.get("import_run_id") or payload.get("target_id"))
    import_type = original_import.import_type if original_import is not None else str(payload.get("source_type") or source.source_type)
    if import_type == "official_api":
        import_type = "official_api"
    if import_type not in {"public_web", "official_api", "rss", "media", "file"}:
        raise _api_error(422, "DEAD_LETTER_IMPORT_TYPE_UNSUPPORTED", "Dead letter replay only supports import-backed failures.")

    failure_payload = dict(payload.get("failure_payload") or {})
    request_payload = dict(failure_payload.get("payload") or {})
    request_payload.update(dict(getattr(request, "payload", None) or {}))
    replay_input = {
        "dead_letter_id": row.id,
        "original_import_run_id": payload.get("import_run_id") or payload.get("target_id"),
        "original_collection_run_id": payload.get("collection_run_id"),
        "source_version": stored_version or current_version,
        "replay_from_step": _dead_letter_replay_step(payload),
        "reason": getattr(request, "reason", None),
    }
    request_payload["dead_letter_replay"] = replay_input
    replay_request = SimpleNamespace(
        data_source_id=source.id,
        title=str(getattr(request, "title", None) or failure_payload.get("title") or f"Dead letter replay {row.id}")[:240],
        content=getattr(request, "content", None) or failure_payload.get("content"),
        source_uri=getattr(request, "source_uri", None) or failure_payload.get("source_uri"),
        city_id=getattr(request, "city_id", None) or failure_payload.get("city_id") or "xian",
        is_synthetic=bool(failure_payload.get("is_synthetic") or failure_payload.get("synthetic") or payload.get("synthetic")),
        media_type=getattr(request, "media_type", None) or failure_payload.get("media_type"),
        media_uri=getattr(request, "media_uri", None) or failure_payload.get("media_uri"),
        payload=request_payload,
    )
    result = run_import(session, replay_request, actor, trace_id, import_type)

    replay_import_id = result["import_run"]["import_run_id"]
    replay_collection_id = result["collection_run"]["collection_run_id"]
    replay_import = session.get(models.ImportRun, replay_import_id)
    replay_run = session.get(models.CollectionRun, replay_collection_id)
    replay_status = result["import_run"]["status"]
    replay_meta = {
        **replay_input,
        "status": replay_status,
        "source_uri": replay_request.source_uri,
        "replay_import_run_id": replay_import_id,
        "replay_collection_run_id": replay_collection_id,
        "record_count": result["import_run"].get("record_count", 0),
        "trace_id": trace_id,
        "replayed_at": _now().isoformat(),
    }
    if replay_import is not None:
        replay_import.payload = {**(replay_import.payload or {}), "dead_letter_replay": replay_meta}
    if replay_run is not None:
        replay_run.payload = {**(replay_run.payload or {}), "dead_letter_replay": replay_meta}
        session.add(
            models.CollectionRunEvent(
                id=_id("CREV"),
                collection_run_id=replay_run.id,
                event_type="dead_letter_replay_completed" if replay_status == "completed" else "dead_letter_replay_failed",
                status=replay_status,
                payload=replay_meta,
            )
        )
    payload["replay"] = replay_meta
    history = list(payload.get("replay_history") or [])
    history.append(replay_meta)
    payload["replay_history"] = history[-10:]
    row.payload = payload
    row.status = "resolved" if replay_status == "completed" else "open"
    action = "dead_letter.replay.completed" if replay_status == "completed" else "dead_letter.replay.failed"
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action=action,
        object_type="dead_letter",
        object_id=row.id,
        after={"dead_letter": serialize_dead_letter(row), "replay": replay_meta},
        reason=getattr(request, "reason", None),
        trace_id=trace_id,
    )
    session.commit()
    return {"dead_letter": serialize_dead_letter(row), "replay": replay_meta, "replay_result": _dead_letter_replay_result(session, replay_meta)}


def _dead_letter_replay_step(payload: dict) -> str:
    failure_payload = payload.get("failure_payload") if isinstance(payload.get("failure_payload"), dict) else {}
    for key in ("official_api_activity", "fetch_activity", "rss_activity"):
        activity = failure_payload.get(key)
        if isinstance(activity, dict) and activity.get("activity_name"):
            return "fetch"
    return "import"


def _dead_letter_replay_result(session: Session, replay_state: dict) -> dict:
    import_run = session.get(models.ImportRun, replay_state.get("replay_import_run_id"))
    collection_run = session.get(models.CollectionRun, replay_state.get("replay_collection_run_id"))
    raw_records = []
    if collection_run is not None:
        raw_records = list(session.execute(select(models.RawRecord).where(models.RawRecord.collection_run_id == collection_run.id).order_by(models.RawRecord.created_at.asc(), models.RawRecord.id.asc())).scalars())
    return {
        "import_run": serialize_import_run(import_run) if import_run is not None else None,
        "collection_run": serialize_collection_run(collection_run) if collection_run is not None else None,
        "raw_records": [serialize_raw_record(record) for record in raw_records],
    }


def create_manual_record(session: Session, request, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, request.data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.source_type != "manual":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_MANUAL_RECORD", "Manual records require a manual data source.")
    if source.status == "disabled":
        raise _api_error(409, "DATA_SOURCE_DISABLED", "Disabled manual sources cannot receive records.")
    policy_result = evaluate_policy(source.source_type, source.policy or {}, source.status)
    if source.status != "active" or not policy_result["allowed"]:
        raise _api_error(409, "DATA_SOURCE_POLICY_BLOCKED", "Source policy blocks manual record creation.")
    validation = validate_manual_record(source.policy or {}, request)
    if validation["status"] != "valid":
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="manual_record.validation_failed",
            object_type="data_source",
            object_id=source.id,
            after={"validation": validation, "data_source_id": source.id},
            reason=request.reason,
            trace_id=trace_id,
        )
        session.commit()
        fields = validation.get("missing_fields") or validation.get("invalid_fields") or []
        suffix = f": {', '.join(fields)}" if fields else "."
        raise _api_error(422, "MANUAL_RECORD_SCHEMA_INVALID", f"Manual record schema validation failed{suffix}", validation)

    title = str(validation["fields"]["title"])[:240]
    content = str(validation["fields"].get("content") or request.content or request.payload.get("content") or "")
    is_synthetic = bool(request.is_synthetic or source.is_synthetic)
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        created_by_id=actor.id,
        name=f"manual record {title[:80]}",
        status="completed",
        schedule=None,
        payload={"source_type": "manual", "manual_entry": {"actor_id": actor.id, "reason": request.reason}},
    )
    session.add(job)
    session.flush()
    run = models.CollectionRun(
        id=_id("CRUN"),
        collection_job_id=job.id,
        data_source_id=source.id,
        status="completed",
        record_count=1,
        created_at=_now(),
        trace_id=trace_id,
        payload={"source_type": "manual", "manual_entry": {"actor_id": actor.id, "reason": request.reason}, "workflow_status": "completed"},
    )
    session.add(run)
    session.flush()
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type="manual",
        title=title,
        content_hash=_hash(content),
        status="collected",
        is_synthetic=is_synthetic,
        city_id=validation["fields"].get("city_id") or request.city_id or (source.policy or {}).get("entry_schema", {}).get("city_id") or "xian",
        occurred_at=_manual_record_occurred_datetime(request) or request.occurred_at or datetime.utcnow(),
        payload={
            "manual_entry": {"actor_id": actor.id, "actor": actor.username, "reason": request.reason},
            "manual_validation": validation,
            "source_flags": {"synthetic": is_synthetic, "import_type": "manual"},
            "source_uri": request.source_uri,
            "synthetic": is_synthetic,
            "payload": request.payload,
            "location": validation.get("location"),
        },
    )
    session.add(record)
    session.flush()
    session.add(models.RawRecordPayload(id=_id("RAWP"), raw_record_id=record.id, content_text=content, masked_text=mask_sensitive_text(content), payload={"manual_entry": True, "synthetic": is_synthetic, "actor_id": actor.id, "manual_validation": validation}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="manual_entered_from", is_synthetic=is_synthetic, payload={"collection_run_id": run.id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"entry_mode": "manual"}))
    validator_run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=source.tenant_id,
        status="completed",
        input_count=1,
        output_count=1,
        rule_version=MANUAL_RECORD_VALIDATOR_VERSION,
        trace_id=trace_id,
        payload={"activity_name": MANUAL_RECORD_VALIDATOR_NAME, "validator": MANUAL_RECORD_VALIDATOR_NAME, "validation": validation},
    )
    session.add(validator_run)
    session.flush()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=source.tenant_id,
        object_type="normalization_run",
        object_id=validator_run.id,
        algorithm_name=MANUAL_RECORD_VALIDATOR_NAME,
        algorithm_version=MANUAL_RECORD_VALIDATOR_VERSION,
        status="completed",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": is_synthetic}],
        output_refs=[],
        output={},
        metrics={"input_count": 1, "valid_count": 1, "missing_count": 0},
        trace_id=trace_id,
        started_at=_now(),
        completed_at=_now(),
        payload={"activity_name": MANUAL_RECORD_VALIDATOR_NAME, "validation": validation},
    )
    session.add(algorithm_run)
    session.flush()
    clean_draft = models.RawRecordNormalization(
        id=_id("RNORM"),
        normalization_run_id=validator_run.id,
        raw_record_id=record.id,
        normalized_title=mask_sensitive_text(title)[:240],
        normalized_text=mask_sensitive_text(content),
        language="zh-CN" if re.search(r"[\u4e00-\u9fff]", title + content) else "en",
        region_id=record.city_id,
        payload={
            "activity_name": MANUAL_RECORD_VALIDATOR_NAME,
            "validator_status": "valid",
            "clean_record_status": "draft",
            "required_fields": validation["required_fields"],
            "location": validation.get("location"),
            "occurred_at": validation.get("occurred_at"),
            "source_raw_record_id": record.id,
            "source_type": record.source_type,
            "synthetic": is_synthetic,
        },
    )
    session.add(clean_draft)
    session.flush()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": clean_draft.id, "object_version": MANUAL_RECORD_VALIDATOR_VERSION}]
    algorithm_run.output = {"normalization_run_id": validator_run.id, "clean_draft_id": clean_draft.id, "validation_status": "valid"}
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=clean_draft.id, relation="manual_record_validated_into_clean_draft", is_synthetic=is_synthetic, payload={"normalization_run_id": validator_run.id, "algorithm_run_id": algorithm_run.id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=clean_draft.id, relation="generated", is_synthetic=is_synthetic, payload={"algorithm_name": MANUAL_RECORD_VALIDATOR_NAME}))
    record.payload = {**(record.payload or {}), "clean_draft": {"normalization_run_id": validator_run.id, "normalization_output_id": clean_draft.id, "status": "draft"}}
    flag_modified(record, "payload")
    event_payload = {"record_count": 1, "raw_record_id": record.id, "actor_id": actor.id, "step_key": "store"}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="manual_record_created", status="completed", payload=event_payload, created_at=_now()))
    _update_health(session, source.id, run.id, success=True, count=1, error_code=None)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="manual_record.create",
        object_type="raw_record",
        object_id=record.id,
        after={"raw_record": serialize_raw_record(record), "collection_run": serialize_collection_run(run), "data_source_id": source.id, "validation": validation, "clean_draft": serialize_normalization_output(clean_draft), "algorithm_run_id": algorithm_run.id},
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return {
        "status": "created",
        "data_source": serialize_data_source(source),
        "collection_job": serialize_collection_job(job),
        "collection_run": serialize_collection_run(run),
        "raw_record": serialize_raw_record(record),
        "validation": validation,
        "validator_run": serialize_normalization_run(validator_run),
        "algorithm_run": serialize_algorithm_run(algorithm_run),
        "clean_draft": serialize_normalization_output(clean_draft),
    }


def run_normalization(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    rule_version = request.rule_version or NORMALIZE_TEXT_CLEANER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": NORMALIZE_TEXT_CLEANER_NAME, "cleaner": NORMALIZE_TEXT_CLEANER_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=NORMALIZE_TEXT_CLEANER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": NORMALIZE_TEXT_CLEANER_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched normalization scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched normalization scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "cleaner": {"activity_name": NORMALIZE_TEXT_CLEANER_NAME, "valid_count": 0, "invalid_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    outputs = []
    valid_count = 0
    invalid_count = 0
    for record in records:
        payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        source_text = payload.masked_text if payload else record.title
        clean = normalize_text(source_text)
        title_clean = normalize_text(record.title)
        status = clean["status"]
        if status == "valid":
            valid_count += 1
        else:
            invalid_count += 1
        text = clean["normalized_text"]
        normalized_title = title_clean["normalized_text"][:240] or record.title[:240]
        cleaner_payload = {
            "activity_name": NORMALIZE_TEXT_CLEANER_NAME,
            "cleaner_status": status,
            "cleaner_version": rule_version,
            "raw_length": clean["raw_length"],
            "normalized_length": clean["normalized_length"],
            "html_tag_count": clean["html_tag_count"],
            "control_char_count": clean["control_char_count"],
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": payload.id if payload is not None else None,
        }
        if status != "valid":
            cleaner_payload.update({"error_code": clean["error_code"], "error_message": clean["error_message"]})
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=normalized_title,
            normalized_text=text,
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + text) else "en",
            region_id=record.city_id,
            payload=cleaner_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {**(record.payload or {}), NORMALIZE_TEXT_CLEANER_NAME: {"status": status, "normalization_output_id": output.id, "normalization_run_id": run.id}}
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="text_normalized_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "cleaner_status": status}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": NORMALIZE_TEXT_CLEANER_NAME}))
    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "valid_count": valid_count, "invalid_count": invalid_count}
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "valid_count": valid_count, "invalid_count": invalid_count, "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": int((_now() - started_at).total_seconds() * 1000), "input_count": len(records), "valid_count": valid_count, "invalid_count": invalid_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="cleaner.normalize_text.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "cleaner": {"valid_count": valid_count, "invalid_count": invalid_count}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "cleaner": {
            "activity_name": NORMALIZE_TEXT_CLEANER_NAME,
            "algorithm_version": rule_version,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_datetime_normalization(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    rule_version = request.rule_version or NORMALIZE_DATETIME_CLEANER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": NORMALIZE_DATETIME_CLEANER_NAME, "cleaner": NORMALIZE_DATETIME_CLEANER_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=NORMALIZE_DATETIME_CLEANER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": NORMALIZE_DATETIME_CLEANER_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched datetime normalization scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched datetime normalization scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "cleaner": {"activity_name": NORMALIZE_DATETIME_CLEANER_NAME, "normalized_count": 0, "review_required_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    outputs = []
    normalized_count = 0
    review_required_count = 0
    default_timezone = str(payload.get("default_timezone") or "+08:00")
    for record in records:
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        normalized = normalize_datetime(record, raw_payload, default_timezone=default_timezone)
        status = normalized["status"]
        if status == "normalized":
            normalized_count += 1
        else:
            review_required_count += 1
        masked_text = raw_payload.masked_text if raw_payload is not None else record.title
        cleaner_payload = {
            "activity_name": NORMALIZE_DATETIME_CLEANER_NAME,
            "cleaner_status": status,
            "cleaner_version": rule_version,
            "raw_datetime": normalized.get("raw_datetime"),
            "normalized_datetime_utc": normalized.get("normalized_datetime_utc"),
            "original_timezone": normalized.get("original_timezone"),
            "source_field": normalized.get("source_field"),
            "parse_format": normalized.get("parse_format"),
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
        }
        if status != "normalized":
            cleaner_payload.update({"error_code": normalized["error_code"], "error_message": normalized["error_message"]})
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=mask_sensitive_text(record.title)[:240],
            normalized_text=mask_sensitive_text(masked_text),
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", record.title + masked_text) else "en",
            region_id=record.city_id,
            payload=cleaner_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {**(record.payload or {}), NORMALIZE_DATETIME_CLEANER_NAME: {"status": status, "normalization_output_id": output.id, "normalization_run_id": run.id, "normalized_datetime_utc": normalized.get("normalized_datetime_utc")}}
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="datetime_normalized_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "cleaner_status": status}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": NORMALIZE_DATETIME_CLEANER_NAME}))
    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "normalized_count": normalized_count, "review_required_count": review_required_count}
    elapsed_ms = max(0, int((_now() - started_at).total_seconds() * 1000))
    per_item_ms = elapsed_ms / max(len(records), 1)
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "normalized_count": normalized_count, "review_required_count": review_required_count, "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": elapsed_ms, "per_item_ms": per_item_ms, "input_count": len(records), "normalized_count": normalized_count, "review_required_count": review_required_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="cleaner.normalize_datetime.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "cleaner": {"normalized_count": normalized_count, "review_required_count": review_required_count}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "cleaner": {
            "activity_name": NORMALIZE_DATETIME_CLEANER_NAME,
            "algorithm_version": rule_version,
            "normalized_count": normalized_count,
            "review_required_count": review_required_count,
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_location_normalization(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    rule_version = request.rule_version or NORMALIZE_LOCATION_CLEANER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": NORMALIZE_LOCATION_CLEANER_NAME, "cleaner": NORMALIZE_LOCATION_CLEANER_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=NORMALIZE_LOCATION_CLEANER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": NORMALIZE_LOCATION_CLEANER_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched location normalization scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched location normalization scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "cleaner": {"activity_name": NORMALIZE_LOCATION_CLEANER_NAME, "normalized_count": 0, "candidate_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    outputs = []
    normalized_count = 0
    candidate_count = 0
    missing_count = 0
    for record in records:
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        normalized = normalize_location(record, raw_payload)
        status = normalized["status"]
        if status == "normalized":
            normalized_count += 1
        elif status == "candidate":
            candidate_count += 1
        else:
            missing_count += 1
        masked_text = raw_payload.masked_text if raw_payload is not None else record.title
        cleaner_payload = {
            "activity_name": NORMALIZE_LOCATION_CLEANER_NAME,
            "cleaner_status": status,
            "cleaner_version": rule_version,
            "city_id": normalized.get("city_id"),
            "city": normalized.get("city"),
            "district": normalized.get("district"),
            "address": normalized.get("address"),
            "source_field": normalized.get("source_field"),
            "candidates": normalized.get("candidates", []),
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
        }
        if status != "normalized":
            cleaner_payload.update({"error_code": normalized["error_code"], "error_message": normalized["error_message"]})
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=mask_sensitive_text(record.title)[:240],
            normalized_text=mask_sensitive_text(masked_text),
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", record.title + masked_text) else "en",
            region_id=normalized.get("city_id") or record.city_id,
            payload=cleaner_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {**(record.payload or {}), NORMALIZE_LOCATION_CLEANER_NAME: {"status": status, "normalization_output_id": output.id, "normalization_run_id": run.id, "city_id": normalized.get("city_id"), "district": normalized.get("district")}}
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="location_normalized_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "cleaner_status": status}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": NORMALIZE_LOCATION_CLEANER_NAME}))
    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "normalized_count": normalized_count, "candidate_count": candidate_count, "missing_count": missing_count}
    elapsed_ms = max(0, int((_now() - started_at).total_seconds() * 1000))
    per_item_ms = elapsed_ms / max(len(records), 1)
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "normalized_count": normalized_count, "candidate_count": candidate_count, "missing_count": missing_count, "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": elapsed_ms, "per_item_ms": per_item_ms, "input_count": len(records), "normalized_count": normalized_count, "candidate_count": candidate_count, "missing_count": missing_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="cleaner.normalize_location.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "cleaner": {"normalized_count": normalized_count, "candidate_count": candidate_count, "missing_count": missing_count}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "cleaner": {
            "activity_name": NORMALIZE_LOCATION_CLEANER_NAME,
            "algorithm_version": rule_version,
            "normalized_count": normalized_count,
            "candidate_count": candidate_count,
            "missing_count": missing_count,
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_source_trust_assignment(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    rule_version = request.rule_version or ASSIGN_SOURCE_TRUST_CLEANER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME, "cleaner": ASSIGN_SOURCE_TRUST_CLEANER_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=ASSIGN_SOURCE_TRUST_CLEANER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched source trust assignment scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched source trust assignment scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "cleaner": {"activity_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME, "assigned_count": 0, "defaulted_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    record_ids = [record.id for record in records]
    source_ids = sorted({record.data_source_id for record in records})
    payloads = _raw_record_payloads_by_id(session, record_ids)
    sources = {
        item.id: item
        for item in session.execute(select(models.DataSource).where(models.DataSource.tenant_id == actor.tenant_id, models.DataSource.id.in_(source_ids))).scalars()
    }
    outputs = []
    assigned_count = 0
    defaulted_count = 0
    warning_count = 0
    for record in records:
        raw_payload = payloads.get(record.id)
        source = sources.get(record.data_source_id)
        assignment = assign_source_trust(record, source)
        if assignment["status"] == "assigned":
            assigned_count += 1
        else:
            defaulted_count += 1
        warning_count += len(assignment["warnings"])
        masked_text = raw_payload.masked_text if raw_payload is not None else record.title
        cleaner_payload = {
            "activity_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME,
            "cleaner_status": assignment["status"],
            "cleaner_version": rule_version,
            "trust_score": assignment["trust_score"],
            "trust_band": assignment["trust_band"],
            "trust_source": assignment["trust_source"],
            "source_id": record.data_source_id,
            "source_type": assignment["source_type"],
            "source_name": assignment["source_name"],
            "warnings": assignment["warnings"],
            "source_policy_ref": assignment["source_policy_ref"],
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
        }
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=mask_sensitive_text(record.title)[:240],
            normalized_text=mask_sensitive_text(masked_text),
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", record.title + masked_text) else "en",
            region_id=record.city_id,
            payload=cleaner_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {
            **(record.payload or {}),
            ASSIGN_SOURCE_TRUST_CLEANER_NAME: {
                "status": assignment["status"],
                "normalization_output_id": output.id,
                "normalization_run_id": run.id,
                "trust_score": assignment["trust_score"],
                "trust_source": assignment["trust_source"],
                "warnings": assignment["warnings"],
            },
        }
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="source_trust_assigned_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "trust_score": assignment["trust_score"]}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=record.data_source_id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="source_trust_used_for", is_synthetic=record.is_synthetic, payload={"trust_source": assignment["trust_source"], "defaulted": assignment["status"] == "defaulted"}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME}))

    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "assigned_count": assigned_count, "defaulted_count": defaulted_count, "warning_count": warning_count}
    elapsed_ms = max(0, int((_now() - started_at).total_seconds() * 1000))
    per_item_ms = elapsed_ms / max(len(records), 1)
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "assigned_count": assigned_count, "defaulted_count": defaulted_count, "warning_count": warning_count, "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": elapsed_ms, "per_item_ms": per_item_ms, "input_count": len(records), "assigned_count": assigned_count, "defaulted_count": defaulted_count, "warning_count": warning_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="cleaner.assign_source_trust.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "cleaner": {"assigned_count": assigned_count, "defaulted_count": defaulted_count, "warning_count": warning_count}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "cleaner": {
            "activity_name": ASSIGN_SOURCE_TRUST_CLEANER_NAME,
            "algorithm_version": rule_version,
            "assigned_count": assigned_count,
            "defaulted_count": defaulted_count,
            "warning_count": warning_count,
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
            "per_item_ms": per_item_ms,
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_sensitive_field_detection(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = _redact_sensitive_payload(request.payload or {})
    rule_version = request.rule_version or DETECT_SENSITIVE_FIELDS_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": DETECT_SENSITIVE_FIELDS_NAME, "detector": DETECT_SENSITIVE_FIELDS_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=DETECT_SENSITIVE_FIELDS_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": DETECT_SENSITIVE_FIELDS_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched sensitive-field detection scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched sensitive-field detection scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "detector": {"activity_name": DETECT_SENSITIVE_FIELDS_NAME, "detected_record_count": 0, "sensitive_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    record_ids = [record.id for record in records]
    payloads = {
        item.raw_record_id: item
        for item in session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id.in_(record_ids))).scalars()
    }
    outputs = []
    detected_record_count = 0
    clean_record_count = 0
    sensitive_count = 0
    type_counts: dict[str, int] = defaultdict(int)
    for record in records:
        raw_payload = payloads.get(record.id)
        detection = detect_sensitive_fields(record, raw_payload)
        field_count = len(detection["fields"])
        if field_count:
            detected_record_count += 1
        else:
            clean_record_count += 1
        sensitive_count += field_count
        for field in detection["fields"]:
            type_counts[field["field_type"]] += 1
        masked_text = detection["redacted_preview"]
        detector_payload = {
            "activity_name": DETECT_SENSITIVE_FIELDS_NAME,
            "detector_status": "detected" if field_count else "clean",
            "detector_version": rule_version,
            "sensitive_count": field_count,
            "field_types": sorted({field["field_type"] for field in detection["fields"]}),
            "fields": detection["fields"],
            "risk_level": detection["risk_level"],
            "redacted_preview": masked_text[:500],
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
            "input_ref": {"object_type": "raw_record_payload", "object_id": raw_payload.id if raw_payload is not None else None, "text_source": "raw_record_payload.masked_text"},
        }
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=mask_sensitive_text(record.title)[:240],
            normalized_text=masked_text,
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", record.title + masked_text) else "en",
            region_id=record.city_id,
            payload=detector_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {
            **(record.payload or {}),
            DETECT_SENSITIVE_FIELDS_NAME: {
                "status": detector_payload["detector_status"],
                "normalization_output_id": output.id,
                "normalization_run_id": run.id,
                "sensitive_count": field_count,
                "field_types": detector_payload["field_types"],
                "risk_level": detection["risk_level"],
            },
        }
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="sensitive_fields_detected_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "sensitive_count": field_count}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": DETECT_SENSITIVE_FIELDS_NAME}))

    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "detected_record_count": detected_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts)}
    elapsed_ms = max(0, int((_now() - started_at).total_seconds() * 1000))
    per_item_ms = elapsed_ms / max(len(records), 1)
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "detected_record_count": detected_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts), "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": elapsed_ms, "per_item_ms": per_item_ms, "input_count": len(records), "detected_record_count": detected_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="detector.detect_sensitive_fields.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "detector": {"detected_record_count": detected_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts)}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "detector": {
            "activity_name": DETECT_SENSITIVE_FIELDS_NAME,
            "algorithm_version": rule_version,
            "detected_record_count": detected_record_count,
            "clean_record_count": clean_record_count,
            "sensitive_count": sensitive_count,
            "type_counts": dict(type_counts),
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
            "per_item_ms": per_item_ms,
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_sensitive_field_redaction(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = _redact_sensitive_payload(request.payload or {})
    rule_version = request.rule_version or REDACT_SENSITIVE_FIELDS_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": REDACT_SENSITIVE_FIELDS_NAME, "cleaner": REDACT_SENSITIVE_FIELDS_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=REDACT_SENSITIVE_FIELDS_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": REDACT_SENSITIVE_FIELDS_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched sensitive-field redaction scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched sensitive-field redaction scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "cleaner": {"activity_name": REDACT_SENSITIVE_FIELDS_NAME, "redacted_record_count": 0, "sensitive_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    record_ids = [record.id for record in records]
    payloads = {
        item.raw_record_id: item
        for item in session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id.in_(record_ids))).scalars()
    }
    outputs = []
    redacted_record_count = 0
    clean_record_count = 0
    sensitive_count = 0
    type_counts: dict[str, int] = defaultdict(int)
    for record in records:
        raw_payload = payloads.get(record.id)
        detection = detect_sensitive_fields(record, raw_payload)
        field_count = len(detection["fields"])
        if field_count:
            redacted_record_count += 1
        else:
            clean_record_count += 1
        sensitive_count += field_count
        for field in detection["fields"]:
            type_counts[field["field_type"]] += 1
        redacted_text = detection["redacted_preview"]
        cleaner_payload = {
            "activity_name": REDACT_SENSITIVE_FIELDS_NAME,
            "cleaner_status": "redacted" if field_count else "clean",
            "cleaner_version": rule_version,
            "sensitive_count": field_count,
            "field_types": sorted({field["field_type"] for field in detection["fields"]}),
            "fields": detection["fields"],
            "risk_level": detection["risk_level"],
            "redacted_text": redacted_text[:500],
            "display_text": redacted_text,
            "export_text": redacted_text,
            "default_display": "redacted",
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
            "input_ref": {"object_type": "raw_record_payload", "object_id": raw_payload.id if raw_payload is not None else None, "text_source": "raw_record_payload.content_text"},
            "original_access_required_permission": "data_source:raw_original",
        }
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=mask_sensitive_text(record.title)[:240],
            normalized_text=redacted_text,
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", record.title + redacted_text) else "en",
            region_id=record.city_id,
            payload=cleaner_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {
            **(record.payload or {}),
            REDACT_SENSITIVE_FIELDS_NAME: {
                "status": cleaner_payload["cleaner_status"],
                "normalization_output_id": output.id,
                "normalization_run_id": run.id,
                "sensitive_count": field_count,
                "field_types": cleaner_payload["field_types"],
                "risk_level": detection["risk_level"],
                "default_display": "redacted",
                "original_access_required_permission": "data_source:raw_original",
            },
        }
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="sensitive_fields_redacted_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "sensitive_count": field_count, "default_display": "redacted"}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": REDACT_SENSITIVE_FIELDS_NAME}))

    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "redacted_record_count": redacted_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts), "default_display": "redacted"}
    elapsed_ms = max(0, int((_now() - started_at).total_seconds() * 1000))
    per_item_ms = elapsed_ms / max(len(records), 1)
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "redacted_record_count": redacted_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts), "output_count": len(outputs), "default_display": "redacted"}
    algorithm_run.metrics = {"latency_ms": elapsed_ms, "per_item_ms": per_item_ms, "input_count": len(records), "redacted_record_count": redacted_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="cleaner.redact_sensitive_fields.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "cleaner": {"redacted_record_count": redacted_record_count, "clean_record_count": clean_record_count, "sensitive_count": sensitive_count, "type_counts": dict(type_counts), "default_display": "redacted"}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs[:response_limit]],
        "cleaner": {
            "activity_name": REDACT_SENSITIVE_FIELDS_NAME,
            "algorithm_version": rule_version,
            "redacted_record_count": redacted_record_count,
            "clean_record_count": clean_record_count,
            "sensitive_count": sensitive_count,
            "type_counts": dict(type_counts),
            "output_count": len(outputs),
            "response_count": min(len(outputs), response_limit),
            "per_item_ms": per_item_ms,
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_html_main_content_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    rule_version = request.rule_version or HTML_MAIN_CONTENT_PARSER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": HTML_MAIN_CONTENT_PARSER_NAME, "parser": HTML_MAIN_CONTENT_PARSER_NAME},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=HTML_MAIN_CONTENT_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": HTML_MAIN_CONTENT_PARSER_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched HTML parser scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched HTML parser scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {"outputs": [], "parser": {"activity_name": HTML_MAIN_CONTENT_PARSER_NAME, "parsed_count": 0, "failed_count": 0}, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    outputs = []
    parsed_count = 0
    failed_count = 0
    for record in records:
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        raw_html = raw_payload.content_text if raw_payload is not None else ""
        parsed = parse_html_main_content(raw_html)
        parser_status = parsed["status"]
        if parser_status == "parsed":
            parsed_count += 1
        else:
            failed_count += 1
        normalized_text = mask_sensitive_text(parsed.get("body") or "")
        normalized_title = mask_sensitive_text(parsed.get("title") or record.title)[:240]
        parser_payload = {
            "activity_name": HTML_MAIN_CONTENT_PARSER_NAME,
            "parser_status": parser_status,
            "parser_version": rule_version,
            "published_at": parsed.get("published_at"),
            "source_uri": (record.payload or {}).get("source_uri"),
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "body_length": len(parsed.get("body") or ""),
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
        }
        if parser_status != "parsed":
            parser_payload.update({"error_code": parsed.get("error_code") or "HTML_MAIN_CONTENT_EMPTY", "error_message": parsed.get("error_message") or "HTML main content is empty."})
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=normalized_title,
            normalized_text=normalized_text,
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
            region_id=record.city_id,
            payload=parser_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {**(record.payload or {}), HTML_MAIN_CONTENT_PARSER_NAME: {"status": parser_status, "normalization_output_id": output.id, "normalization_run_id": run.id, "published_at": parsed.get("published_at")}}
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="html_main_content_parsed_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": HTML_MAIN_CONTENT_PARSER_NAME}))

    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "parsed_count": parsed_count, "failed_count": failed_count}
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "parsed_count": parsed_count, "failed_count": failed_count, "output_count": len(outputs)}
    algorithm_run.metrics = {"latency_ms": int((_now() - started_at).total_seconds() * 1000), "input_count": len(records), "parsed_count": parsed_count, "failed_count": failed_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.html_main_content.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"parsed_count": parsed_count, "failed_count": failed_count}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs],
        "parser": {
            "activity_name": HTML_MAIN_CONTENT_PARSER_NAME,
            "algorithm_version": rule_version,
            "parsed_count": parsed_count,
            "failed_count": failed_count,
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_json_by_mapping_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else payload.get("field_mapping")
    mapping = mapping if isinstance(mapping, dict) else {}
    if not mapping:
        mapping = {"title": "$.title", "body": "$.summary", "published_at": "$.published_at"}
    mapping = {str(key): str(value) for key, value in mapping.items() if value is not None}
    rule_version = request.rule_version or JSON_BY_MAPPING_PARSER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": JSON_BY_MAPPING_PARSER_NAME, "parser": JSON_BY_MAPPING_PARSER_NAME, "mapping": mapping},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=JSON_BY_MAPPING_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": JSON_BY_MAPPING_PARSER_NAME, "mapping": mapping},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched JSON parser scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched JSON parser scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_normalization_run(run) | {
            "outputs": [],
            "parser": {"activity_name": JSON_BY_MAPPING_PARSER_NAME, "algorithm_version": rule_version, "parsed_count": 0, "failed_count": 0, "mapping": mapping},
            "algorithm_run": serialize_algorithm_run(algorithm_run),
        }

    outputs = []
    parsed_count = 0
    failed_count = 0
    for record in records:
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        raw_text = raw_payload.content_text if raw_payload is not None else ""
        parsed = parse_json_by_mapping(raw_text, mapping)
        parser_status = parsed["status"]
        if parser_status == "parsed":
            parsed_count += 1
        else:
            failed_count += 1
        normalized_title = mask_sensitive_text(str(parsed.get("title") or record.title))[:240]
        normalized_text = mask_sensitive_text(str(parsed.get("body") or ""))
        parser_payload = {
            "activity_name": JSON_BY_MAPPING_PARSER_NAME,
            "parser_status": parser_status,
            "parser_version": rule_version,
            "mapping": mapping,
            "published_at": parsed.get("published_at"),
            "source_uri": (record.payload or {}).get("source_uri"),
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
            "mapped_fields": parsed.get("mapped_fields", {}),
        }
        if parser_status != "parsed":
            parser_payload.update({"error_code": parsed.get("error_code"), "error_message": parsed.get("error_message"), "missing_fields": parsed.get("missing_fields", [])})
        output = models.RawRecordNormalization(
            id=_id("RNORM"),
            normalization_run_id=run.id,
            raw_record_id=record.id,
            normalized_title=normalized_title,
            normalized_text=normalized_text,
            language="zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
            region_id=record.city_id,
            payload=parser_payload,
        )
        outputs.append(output)
        session.add(output)
        record.payload = {**(record.payload or {}), JSON_BY_MAPPING_PARSER_NAME: {"status": parser_status, "normalization_output_id": output.id, "normalization_run_id": run.id, "published_at": parsed.get("published_at")}}
        flag_modified(record, "payload")
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="json_mapping_parsed_into", is_synthetic=record.is_synthetic, payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status}))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="algorithm_run", from_object_id=algorithm_run.id, to_object_type="raw_record_normalization", to_object_id=output.id, relation="generated", is_synthetic=record.is_synthetic, payload={"algorithm_name": JSON_BY_MAPPING_PARSER_NAME}))

    run.status = "completed"
    run.output_count = len(outputs)
    run.payload = {**(run.payload or {}), "parsed_count": parsed_count, "failed_count": failed_count}
    algorithm_run.status = "completed"
    algorithm_run.completed_at = _now()
    algorithm_run.output_refs = [{"object_type": "raw_record_normalization", "object_id": output.id, "object_version": rule_version} for output in outputs]
    algorithm_run.output = {"normalization_run_id": run.id, "parsed_count": parsed_count, "failed_count": failed_count, "output_count": len(outputs), "mapping": mapping}
    algorithm_run.metrics = {"latency_ms": int((_now() - started_at).total_seconds() * 1000), "input_count": len(records), "parsed_count": parsed_count, "failed_count": failed_count}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.json_by_mapping.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"parsed_count": parsed_count, "failed_count": failed_count, "mapping": mapping}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": [serialize_normalization_output(item) for item in outputs],
        "parser": {
            "activity_name": JSON_BY_MAPPING_PARSER_NAME,
            "algorithm_version": rule_version,
            "parsed_count": parsed_count,
            "failed_count": failed_count,
            "mapping": mapping,
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_rss_item_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    response_limit = min(max(int(getattr(request, "response_limit", 100) or 0), 0), 1000)
    rule_version = request.rule_version or RSS_ITEM_PARSER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": RSS_ITEM_PARSER_NAME, "parser": RSS_ITEM_PARSER_NAME, "response_limit": response_limit},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=RSS_ITEM_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": RSS_ITEM_PARSER_NAME, "response_limit": response_limit},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        return _finish_rss_item_parser_failure(session, run, algorithm_run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched RSS item parser scope.", trace_id, actor, response_limit)

    existing_keys = _existing_rss_parser_item_keys(session, {record.data_source_id for record in records})
    seen_keys: set[str] = set()
    item_count = 0
    parsed_count = 0
    failed_count = 0
    duplicate_count = 0
    output_count = 0
    preview_outputs: list[dict] = []
    output_refs: list[dict] = []
    normalization_rows: list[dict] = []
    lineage_rows: list[dict] = []

    def flush_rows() -> None:
        nonlocal normalization_rows, lineage_rows
        if normalization_rows:
            session.execute(models.RawRecordNormalization.__table__.insert(), normalization_rows)
            normalization_rows = []
        if lineage_rows:
            session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
            lineage_rows = []

    for record in records:
        item_count += 1
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        raw_text = raw_payload.content_text if raw_payload is not None else ""
        parsed = parse_rss_item(raw_text, record.payload if isinstance(record.payload, dict) else {})
        if record.source_type != "rss":
            parsed = {
                "status": "parse_error",
                "error_code": "RSS_ITEM_SOURCE_TYPE_UNSUPPORTED",
                "error_message": "RSS item parser only accepts raw records with source_type=rss.",
                "missing_fields": [],
                "title": record.title,
                "summary": "",
            }
        parser_status = str(parsed["status"])
        rss_item_key = str(parsed.get("rss_item_key") or "")
        if parser_status == "parsed" and rss_item_key and (rss_item_key in existing_keys or rss_item_key in seen_keys):
            duplicate_count += 1
            record.payload = {
                **(record.payload or {}),
                RSS_ITEM_PARSER_NAME: {
                    "status": "duplicate_skipped",
                    "normalization_run_id": run.id,
                    "rss_item_key": rss_item_key,
                    "identity_source": parsed.get("identity_source"),
                },
            }
            flag_modified(record, "payload")
            continue
        if parser_status == "parsed":
            parsed_count += 1
            if rss_item_key:
                seen_keys.add(rss_item_key)
        else:
            failed_count += 1

        output_id = _id("RNORM")
        normalized_title = mask_sensitive_text(str(parsed.get("title") or record.title))[:240]
        normalized_text = mask_sensitive_text(str(parsed.get("summary") or ""))
        parser_payload = {
            "activity_name": RSS_ITEM_PARSER_NAME,
            "parser_status": parser_status,
            "parser_version": rule_version,
            "title": normalized_title,
            "link": parsed.get("link"),
            "summary": normalized_text,
            "published_at": parsed.get("published_at"),
            "raw_published_at": parsed.get("raw_published_at"),
            "guid": parsed.get("guid"),
            "link_hash": parsed.get("link_hash"),
            "rss_item_key": parsed.get("rss_item_key"),
            "identity_source": parsed.get("identity_source"),
            "feed_url": parsed.get("feed_url") or (record.payload or {}).get("feed_url"),
            "source_uri": parsed.get("source_uri") or parsed.get("link") or (record.payload or {}).get("source_uri"),
            "input_format": parsed.get("input_format"),
            "source_raw_record_id": record.id,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
            "source_type": record.source_type,
            "synthetic": record.is_synthetic,
        }
        if parser_status != "parsed":
            parser_payload.update(
                {
                    "error_code": parsed.get("error_code"),
                    "error_message": parsed.get("error_message"),
                    "missing_fields": parsed.get("missing_fields", []),
                }
            )
        normalization_row = {
            "id": output_id,
            "normalization_run_id": run.id,
            "raw_record_id": record.id,
            "normalized_title": normalized_title,
            "normalized_text": normalized_text,
            "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
            "region_id": record.city_id,
            "payload": parser_payload,
        }
        normalization_rows.append(normalization_row)
        lineage_rows.append(
            {
                "id": _id("LIN"),
                "from_object_type": "raw_record",
                "from_object_id": record.id,
                "to_object_type": "raw_record_normalization",
                "to_object_id": output_id,
                "relation": "rss_item_parsed_into",
                "is_synthetic": record.is_synthetic,
                "payload": {"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status, "rss_item_key": parsed.get("rss_item_key")},
            }
        )
        lineage_rows.append(
            {
                "id": _id("LIN"),
                "from_object_type": "algorithm_run",
                "from_object_id": algorithm_run.id,
                "to_object_type": "raw_record_normalization",
                "to_object_id": output_id,
                "relation": "generated",
                "is_synthetic": record.is_synthetic,
                "payload": {"algorithm_name": RSS_ITEM_PARSER_NAME, "rss_item_key": parsed.get("rss_item_key")},
            }
        )
        output_count += 1
        output_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
        if len(preview_outputs) < response_limit:
            preview_outputs.append(
                {
                    "normalization_output_id": output_id,
                    "normalization_run_id": run.id,
                    "raw_record_id": record.id,
                    "normalized_title": normalized_title,
                    "normalized_text": normalized_text,
                    "language": normalization_row["language"],
                    "region_id": record.city_id,
                    "payload": parser_payload,
                    "created_at": None,
                }
            )
        record.payload = {
            **(record.payload or {}),
            RSS_ITEM_PARSER_NAME: {
                "status": parser_status,
                "normalization_run_id": run.id,
                "normalization_output_id": output_id,
                "rss_item_key": parsed.get("rss_item_key"),
                "identity_source": parsed.get("identity_source"),
                "published_at": parsed.get("published_at"),
            },
        }
        flag_modified(record, "payload")
        if len(normalization_rows) >= 5000:
            flush_rows()

    flush_rows()
    completed_at = _now()
    run.status = "completed"
    run.output_count = output_count
    run.payload = {
        **(run.payload or {}),
        "item_count": item_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "duplicate_count": duplicate_count,
        "response_count": len(preview_outputs),
    }
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {
        "normalization_run_id": run.id,
        "item_count": item_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "duplicate_count": duplicate_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
    }
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - started_at).total_seconds() * 1000),
        "input_count": len(records),
        "item_count": item_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "duplicate_count": duplicate_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
    }
    parser_summary = {
        "activity_name": RSS_ITEM_PARSER_NAME,
        "algorithm_version": rule_version,
        "item_count": item_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "duplicate_count": duplicate_count,
        "response_count": len(preview_outputs),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.rss_item.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": preview_outputs, "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def _finish_rss_item_parser_failure(
    session: Session,
    run: models.NormalizationRun,
    algorithm_run: models.AlgorithmRun,
    code: str,
    message: str,
    trace_id: str,
    actor: models.User,
    response_limit: int,
) -> dict:
    _fail_processing_run(session, run, code, message)
    completed_at = _now()
    run.output_count = 0
    run.payload = {**(run.payload or {}), "item_count": 0, "parsed_count": 0, "failed_count": 0, "duplicate_count": 0, "response_count": 0}
    algorithm_run.status = "failed"
    algorithm_run.error_code = code
    algorithm_run.error_message = message
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = []
    algorithm_run.output = {"normalization_run_id": run.id, "item_count": 0, "parsed_count": 0, "failed_count": 0, "duplicate_count": 0, "output_count": 0, "response_count": 0}
    algorithm_run.metrics = {"latency_ms": int((completed_at - (algorithm_run.started_at or completed_at)).total_seconds() * 1000), "input_count": run.input_count, "output_count": 0, "response_limit": response_limit}
    parser_summary = {"activity_name": RSS_ITEM_PARSER_NAME, "algorithm_version": run.rule_version, "item_count": 0, "parsed_count": 0, "failed_count": 0, "duplicate_count": 0, "response_count": 0}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.rss_item.failed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": [], "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def _existing_rss_parser_item_keys(session: Session, source_ids: set[str]) -> set[str]:
    if not source_ids:
        return set()
    rows = session.execute(
        select(models.RawRecordNormalization.payload)
        .join(models.RawRecord, models.RawRecordNormalization.raw_record_id == models.RawRecord.id)
        .where(models.RawRecord.data_source_id.in_(sorted(source_ids)))
    ).all()
    keys: set[str] = set()
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        if payload.get("activity_name") != RSS_ITEM_PARSER_NAME or payload.get("parser_status") != "parsed":
            continue
        key = str(payload.get("rss_item_key") or "").strip()
        if key:
            keys.add(key)
    return keys


def run_csv_file_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    mapping = _csv_file_mapping(payload)
    response_limit = min(max(int(getattr(request, "response_limit", 100) or 0), 0), 1000)
    rule_version = request.rule_version or CSV_FILE_PARSER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": CSV_FILE_PARSER_NAME, "parser": CSV_FILE_PARSER_NAME, "mapping": mapping, "response_limit": response_limit},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=CSV_FILE_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": CSV_FILE_PARSER_NAME, "mapping": mapping, "response_limit": response_limit},
    )
    session.add(algorithm_run)
    session.flush()

    if not records:
        return _finish_csv_file_parser_failure(
            session,
            run,
            algorithm_run,
            "RAW_RECORD_SCOPE_EMPTY",
            "No raw records matched CSV parser scope.",
            trace_id,
            actor,
            mapping,
            response_limit,
        )

    parsed_files: list[dict] = []
    total_row_count = 0
    for record in records:
        raw_payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
        raw_text = raw_payload.content_text if raw_payload is not None else ""
        parsed = parse_csv_file(raw_text, mapping)
        file_ref = (record.payload or {}).get("file_object_ref") if isinstance(record.payload, dict) else {}
        file_summary = {
            "raw_record_id": record.id,
            "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
            "file_object_id": file_ref.get("file_object_id") if isinstance(file_ref, dict) else None,
            "file_name": file_ref.get("file_name") if isinstance(file_ref, dict) else None,
            "row_count": parsed.get("row_count", 0),
            "status": parsed["status"],
        }
        if parsed["status"] != "parsed":
            return _finish_csv_file_parser_failure(
                session,
                run,
                algorithm_run,
                parsed.get("error_code") or "CSV_PARSE_FAILED",
                parsed.get("error_message") or "CSV parser failed.",
                trace_id,
                actor,
                mapping,
                response_limit,
                missing_columns=parsed.get("missing_columns", []),
                row_count=total_row_count + int(parsed.get("row_count") or 0),
                file_summaries=parsed_files + [file_summary | {"missing_columns": parsed.get("missing_columns", [])}],
            )
        total_row_count += int(parsed.get("row_count") or 0)
        parsed_files.append({"record": record, "raw_payload": raw_payload, "file_ref": file_ref if isinstance(file_ref, dict) else {}, "parsed": parsed, "summary": file_summary})

    parsed_count = 0
    failed_count = 0
    output_count = 0
    preview_outputs: list[dict] = []
    preview_refs: list[dict] = []
    output_refs: list[dict] = []
    normalization_rows: list[dict] = []
    lineage_rows: list[dict] = []

    def flush_rows() -> None:
        nonlocal normalization_rows, lineage_rows
        if normalization_rows:
            session.execute(models.RawRecordNormalization.__table__.insert(), normalization_rows)
            normalization_rows = []
        if lineage_rows:
            session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
            lineage_rows = []

    for parsed_file in parsed_files:
        record: models.RawRecord = parsed_file["record"]
        raw_payload = parsed_file["raw_payload"]
        file_ref = parsed_file["file_ref"]
        for row in parsed_file["parsed"]["rows"]:
            output_id = _id("RNORM")
            row_title = str(row.get("title") or record.title)
            row_body = str(row.get("body") or "")
            normalized_title = mask_sensitive_text(row_title)[:240]
            normalized_text = mask_sensitive_text(row_body)
            parser_status = row["status"]
            if parser_status == "parsed":
                parsed_count += 1
            else:
                failed_count += 1
            masked_columns = {str(key): mask_sensitive_text(str(value)) for key, value in (row.get("columns") or {}).items()}
            parser_payload = {
                "activity_name": CSV_FILE_PARSER_NAME,
                "parser_status": parser_status,
                "parser_version": rule_version,
                "mapping": mapping,
                "row_number": row["row_number"],
                "source_raw_record_id": record.id,
                "source_file_object_id": file_ref.get("file_object_id"),
                "file_name": file_ref.get("file_name"),
                "raw_record_payload_id": raw_payload.id if raw_payload is not None else None,
                "published_at": row.get("published_at"),
                "columns": masked_columns,
                "source_type": record.source_type,
                "synthetic": record.is_synthetic,
            }
            if parser_status != "parsed":
                parser_payload.update({"error_code": row.get("error_code"), "error_message": row.get("error_message"), "missing_fields": row.get("missing_fields", [])})
            normalization_row = {
                "id": output_id,
                "normalization_run_id": run.id,
                "raw_record_id": record.id,
                "normalized_title": normalized_title,
                "normalized_text": normalized_text,
                "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
                "region_id": record.city_id,
                "payload": parser_payload,
            }
            normalization_rows.append(normalization_row)
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "raw_record",
                    "from_object_id": record.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "csv_row_parsed_into",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status, "row_number": row["row_number"]},
                }
            )
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "algorithm_run",
                    "from_object_id": algorithm_run.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "generated",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"algorithm_name": CSV_FILE_PARSER_NAME, "row_number": row["row_number"]},
                }
            )
            output_count += 1
            output_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(preview_outputs) < response_limit:
                preview_outputs.append(
                    {
                        "normalization_output_id": output_id,
                        "normalization_run_id": run.id,
                        "raw_record_id": record.id,
                        "normalized_title": normalized_title,
                        "normalized_text": normalized_text,
                        "language": normalization_row["language"],
                        "region_id": record.city_id,
                        "payload": parser_payload,
                        "created_at": None,
                    }
                )
                preview_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(normalization_rows) >= 5000:
                flush_rows()

        record.payload = {
            **(record.payload or {}),
            CSV_FILE_PARSER_NAME: {
                "status": "completed",
                "normalization_run_id": run.id,
                "row_count": parsed_file["parsed"].get("row_count", 0),
                "parsed_count": parsed_file["parsed"].get("parsed_count", 0),
                "failed_count": parsed_file["parsed"].get("failed_count", 0),
                "mapping": mapping,
            },
        }
        flag_modified(record, "payload")

    flush_rows()
    completed_at = _now()
    run.status = "completed"
    run.output_count = output_count
    run.payload = {
        **(run.payload or {}),
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "response_count": len(preview_outputs),
        "file_count": len(parsed_files),
    }
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {
        "normalization_run_id": run.id,
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
        "mapping": mapping,
    }
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - started_at).total_seconds() * 1000),
        "input_count": len(records),
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.csv_file.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"row_count": total_row_count, "parsed_count": parsed_count, "failed_count": failed_count, "mapping": mapping}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": preview_outputs,
        "parser": {
            "activity_name": CSV_FILE_PARSER_NAME,
            "algorithm_version": rule_version,
            "row_count": total_row_count,
            "parsed_count": parsed_count,
            "failed_count": failed_count,
            "response_count": len(preview_outputs),
            "mapping": mapping,
            "files": [item["summary"] for item in parsed_files],
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def _finish_csv_file_parser_failure(
    session: Session,
    run: models.NormalizationRun,
    algorithm_run: models.AlgorithmRun,
    code: str,
    message: str,
    trace_id: str,
    actor: models.User,
    mapping: dict[str, str],
    response_limit: int,
    missing_columns: list[str] | None = None,
    row_count: int = 0,
    file_summaries: list[dict] | None = None,
) -> dict:
    _fail_processing_run(session, run, code, message)
    completed_at = _now()
    run.output_count = 0
    run.payload = {
        **(run.payload or {}),
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "response_count": 0,
        "missing_columns": missing_columns or [],
    }
    algorithm_run.status = "failed"
    algorithm_run.error_code = code
    algorithm_run.error_message = message
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = []
    algorithm_run.output = {
        "normalization_run_id": run.id,
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "output_count": 0,
        "response_count": 0,
        "mapping": mapping,
        "missing_columns": missing_columns or [],
    }
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - (algorithm_run.started_at or completed_at)).total_seconds() * 1000),
        "input_count": run.input_count,
        "row_count": row_count,
        "output_count": 0,
        "response_limit": response_limit,
    }
    parser_summary = {
        "activity_name": CSV_FILE_PARSER_NAME,
        "algorithm_version": run.rule_version,
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "response_count": 0,
        "mapping": mapping,
        "missing_columns": missing_columns or [],
        "files": file_summaries or [],
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.csv_file.failed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": [], "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def run_xlsx_file_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    mapping = _xlsx_file_mapping(payload)
    requested_sheet = str(payload.get("sheet") or payload.get("sheet_name") or "").strip() or None
    requested_range = str(payload.get("range") or payload.get("cell_range") or "").strip() or None
    response_limit = min(max(int(getattr(request, "response_limit", 100) or 0), 0), 1000)
    rule_version = request.rule_version or XLSX_FILE_PARSER_VERSION
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload
        | {
            "activity_name": XLSX_FILE_PARSER_NAME,
            "parser": XLSX_FILE_PARSER_NAME,
            "mapping": mapping,
            "sheet_name": requested_sheet,
            "cell_range": requested_range,
            "response_limit": response_limit,
        },
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=XLSX_FILE_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": XLSX_FILE_PARSER_NAME, "mapping": mapping, "sheet_name": requested_sheet, "cell_range": requested_range, "response_limit": response_limit},
    )
    session.add(algorithm_run)
    session.flush()

    if not records:
        return _finish_xlsx_file_parser_failure(session, run, algorithm_run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched XLSX parser scope.", trace_id, actor, mapping, response_limit)

    parsed_files: list[dict] = []
    total_row_count = 0
    for record in records:
        file_ref = (record.payload or {}).get("file_object_ref") if isinstance(record.payload, dict) else {}
        file_object_id = file_ref.get("file_object_id") if isinstance(file_ref, dict) else None
        file_object = session.get(models.FileObject, file_object_id) if file_object_id else None
        if file_object is None or file_object.tenant_id != actor.tenant_id:
            return _finish_xlsx_file_parser_failure(
                session,
                run,
                algorithm_run,
                "XLSX_FILE_OBJECT_NOT_FOUND",
                "XLSX parser requires a stored file object linked from the raw record.",
                trace_id,
                actor,
                mapping,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object_id, "status": "file_error"}],
            )
        if _file_extension(file_object.file_name) != "xlsx":
            return _finish_xlsx_file_parser_failure(
                session,
                run,
                algorithm_run,
                "XLSX_FILE_TYPE_UNSUPPORTED",
                "XLSX parser can only parse .xlsx uploaded file objects.",
                trace_id,
                actor,
                mapping,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object.id, "file_name": file_object.file_name, "status": "file_error"}],
            )
        parsed = parse_xlsx_file(_read_upload_object(file_object), mapping, sheet_name=requested_sheet, cell_range=requested_range)
        file_summary = {
            "raw_record_id": record.id,
            "file_object_id": file_object.id,
            "file_name": file_object.file_name,
            "sheet_name": parsed.get("sheet_name") or requested_sheet,
            "cell_range": parsed.get("cell_range") or requested_range,
            "row_count": parsed.get("row_count", 0),
            "status": parsed["status"],
        }
        if parsed["status"] != "parsed":
            return _finish_xlsx_file_parser_failure(
                session,
                run,
                algorithm_run,
                parsed.get("error_code") or "XLSX_PARSE_FAILED",
                parsed.get("error_message") or "XLSX parser failed.",
                trace_id,
                actor,
                mapping,
                response_limit,
                missing_columns=parsed.get("missing_columns", []),
                row_count=total_row_count + int(parsed.get("row_count") or 0),
                sheet_name=parsed.get("sheet_name") or requested_sheet,
                cell_range=parsed.get("cell_range") or requested_range,
                file_summaries=parsed_files + [file_summary | {"missing_columns": parsed.get("missing_columns", []), "error_ref": parsed.get("error_ref")}],
            )
        total_row_count += int(parsed.get("row_count") or 0)
        parsed_files.append({"record": record, "file_object": file_object, "file_ref": file_ref if isinstance(file_ref, dict) else {}, "parsed": parsed, "summary": file_summary})

    parsed_count = 0
    failed_count = 0
    output_count = 0
    preview_outputs: list[dict] = []
    preview_refs: list[dict] = []
    output_refs: list[dict] = []
    normalization_rows: list[dict] = []
    lineage_rows: list[dict] = []

    def flush_rows() -> None:
        nonlocal normalization_rows, lineage_rows
        if normalization_rows:
            session.execute(models.RawRecordNormalization.__table__.insert(), normalization_rows)
            normalization_rows = []
        if lineage_rows:
            session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
            lineage_rows = []

    for parsed_file in parsed_files:
        record: models.RawRecord = parsed_file["record"]
        file_object: models.FileObject = parsed_file["file_object"]
        parsed = parsed_file["parsed"]
        for row in parsed["rows"]:
            output_id = _id("RNORM")
            row_title = str(row.get("title") or record.title)
            row_body = str(row.get("body") or "")
            normalized_title = mask_sensitive_text(row_title)[:240]
            normalized_text = mask_sensitive_text(row_body)
            parser_status = row["status"]
            if parser_status == "parsed":
                parsed_count += 1
            else:
                failed_count += 1
            masked_columns = {str(key): mask_sensitive_text(str(value)) for key, value in (row.get("columns") or {}).items()}
            parser_payload = {
                "activity_name": XLSX_FILE_PARSER_NAME,
                "parser_status": parser_status,
                "parser_version": rule_version,
                "mapping": mapping,
                "row_number": row["row_number"],
                "sheet_name": parsed["sheet_name"],
                "cell_range": parsed.get("cell_range"),
                "source_raw_record_id": record.id,
                "source_file_object_id": file_object.id,
                "file_name": file_object.file_name,
                "published_at": row.get("published_at"),
                "columns": masked_columns,
                "source_type": record.source_type,
                "synthetic": record.is_synthetic,
            }
            if parser_status != "parsed":
                parser_payload.update({"error_code": row.get("error_code"), "error_message": row.get("error_message"), "missing_fields": row.get("missing_fields", [])})
            normalization_row = {
                "id": output_id,
                "normalization_run_id": run.id,
                "raw_record_id": record.id,
                "normalized_title": normalized_title,
                "normalized_text": normalized_text,
                "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
                "region_id": record.city_id,
                "payload": parser_payload,
            }
            normalization_rows.append(normalization_row)
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "raw_record",
                    "from_object_id": record.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "xlsx_row_parsed_into",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status, "row_number": row["row_number"], "sheet_name": parsed["sheet_name"]},
                }
            )
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "algorithm_run",
                    "from_object_id": algorithm_run.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "generated",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"algorithm_name": XLSX_FILE_PARSER_NAME, "row_number": row["row_number"], "sheet_name": parsed["sheet_name"]},
                }
            )
            output_count += 1
            output_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(preview_outputs) < response_limit:
                preview_outputs.append(
                    {
                        "normalization_output_id": output_id,
                        "normalization_run_id": run.id,
                        "raw_record_id": record.id,
                        "normalized_title": normalized_title,
                        "normalized_text": normalized_text,
                        "language": normalization_row["language"],
                        "region_id": record.city_id,
                        "payload": parser_payload,
                        "created_at": None,
                    }
                )
                preview_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(normalization_rows) >= 5000:
                flush_rows()

        record.payload = {
            **(record.payload or {}),
            XLSX_FILE_PARSER_NAME: {
                "status": "completed",
                "normalization_run_id": run.id,
                "row_count": parsed.get("row_count", 0),
                "parsed_count": parsed.get("parsed_count", 0),
                "failed_count": parsed.get("failed_count", 0),
                "sheet_name": parsed.get("sheet_name"),
                "cell_range": parsed.get("cell_range"),
                "mapping": mapping,
            },
        }
        flag_modified(record, "payload")

    flush_rows()
    completed_at = _now()
    sheet_name = parsed_files[0]["parsed"].get("sheet_name") if parsed_files else requested_sheet
    cell_range = parsed_files[0]["parsed"].get("cell_range") if parsed_files else requested_range
    run.status = "completed"
    run.output_count = output_count
    run.payload = {
        **(run.payload or {}),
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "response_count": len(preview_outputs),
        "file_count": len(parsed_files),
    }
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {
        "normalization_run_id": run.id,
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
        "mapping": mapping,
    }
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - started_at).total_seconds() * 1000),
        "input_count": len(records),
        "row_count": total_row_count,
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "output_count": output_count,
        "response_count": len(preview_outputs),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.xlsx_file.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"row_count": total_row_count, "parsed_count": parsed_count, "failed_count": failed_count, "mapping": mapping, "sheet_name": sheet_name, "cell_range": cell_range}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": preview_outputs,
        "parser": {
            "activity_name": XLSX_FILE_PARSER_NAME,
            "algorithm_version": rule_version,
            "sheet_name": sheet_name,
            "cell_range": cell_range,
            "row_count": total_row_count,
            "parsed_count": parsed_count,
            "failed_count": failed_count,
            "response_count": len(preview_outputs),
            "mapping": mapping,
            "files": [item["summary"] for item in parsed_files],
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def _finish_xlsx_file_parser_failure(
    session: Session,
    run: models.NormalizationRun,
    algorithm_run: models.AlgorithmRun,
    code: str,
    message: str,
    trace_id: str,
    actor: models.User,
    mapping: dict[str, str],
    response_limit: int,
    missing_columns: list[str] | None = None,
    row_count: int = 0,
    sheet_name: str | None = None,
    cell_range: str | None = None,
    file_summaries: list[dict] | None = None,
) -> dict:
    _fail_processing_run(session, run, code, message)
    completed_at = _now()
    run.output_count = 0
    run.payload = {
        **(run.payload or {}),
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "response_count": 0,
        "missing_columns": missing_columns or [],
    }
    algorithm_run.status = "failed"
    algorithm_run.error_code = code
    algorithm_run.error_message = message
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = []
    algorithm_run.output = {
        "normalization_run_id": run.id,
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "output_count": 0,
        "response_count": 0,
        "mapping": mapping,
        "missing_columns": missing_columns or [],
    }
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - (algorithm_run.started_at or completed_at)).total_seconds() * 1000),
        "input_count": run.input_count,
        "row_count": row_count,
        "output_count": 0,
        "response_limit": response_limit,
    }
    parser_summary = {
        "activity_name": XLSX_FILE_PARSER_NAME,
        "algorithm_version": run.rule_version,
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": row_count,
        "parsed_count": 0,
        "failed_count": 0,
        "response_count": 0,
        "mapping": mapping,
        "missing_columns": missing_columns or [],
        "files": file_summaries or [],
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.xlsx_file.failed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": [], "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def run_pdf_text_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    response_limit = min(max(int(getattr(request, "response_limit", 100) or 0), 0), 1000)
    rule_version = request.rule_version or PDF_TEXT_PARSER_VERSION
    title_prefix = str(payload.get("title_prefix") or "PDF page").strip() or "PDF page"
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": PDF_TEXT_PARSER_NAME, "parser": PDF_TEXT_PARSER_NAME, "response_limit": response_limit, "title_prefix": title_prefix},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=PDF_TEXT_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": PDF_TEXT_PARSER_NAME, "response_limit": response_limit},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        return _finish_pdf_text_parser_failure(session, run, algorithm_run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched PDF parser scope.", trace_id, actor, response_limit)

    parsed_files: list[dict] = []
    total_page_count = 0
    for record in records:
        file_ref = (record.payload or {}).get("file_object_ref") if isinstance(record.payload, dict) else {}
        file_object_id = file_ref.get("file_object_id") if isinstance(file_ref, dict) else None
        file_object = session.get(models.FileObject, file_object_id) if file_object_id else None
        if file_object is None or file_object.tenant_id != actor.tenant_id:
            return _finish_pdf_text_parser_failure(
                session,
                run,
                algorithm_run,
                "PDF_FILE_OBJECT_NOT_FOUND",
                "PDF parser requires a stored file object linked from the raw record.",
                trace_id,
                actor,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object_id, "status": "file_error"}],
            )
        if _file_extension(file_object.file_name) != "pdf":
            return _finish_pdf_text_parser_failure(
                session,
                run,
                algorithm_run,
                "PDF_FILE_TYPE_UNSUPPORTED",
                "PDF parser can only parse .pdf uploaded file objects.",
                trace_id,
                actor,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object.id, "file_name": file_object.file_name, "status": "file_error"}],
            )
        parsed = parse_pdf_text(_read_upload_object(file_object))
        file_summary = {"raw_record_id": record.id, "file_object_id": file_object.id, "file_name": file_object.file_name, "page_count": parsed.get("page_count", 0), "status": parsed["status"], "parser_engine": parsed.get("parser_engine") or "builtin_pdf_stream"}
        if parsed["status"] != "parsed":
            return _finish_pdf_text_parser_failure(
                session,
                run,
                algorithm_run,
                parsed.get("error_code") or "PDF_PARSE_FAILED",
                parsed.get("error_message") or "PDF parser failed.",
                trace_id,
                actor,
                response_limit,
                page_count=total_page_count + int(parsed.get("page_count") or 0),
                file_summaries=parsed_files + [file_summary],
            )
        total_page_count += int(parsed.get("page_count") or 0)
        parsed_files.append({"record": record, "file_object": file_object, "parsed": parsed, "summary": file_summary})

    parsed_count = 0
    ocr_required_count = 0
    output_count = 0
    preview_outputs: list[dict] = []
    preview_refs: list[dict] = []
    output_refs: list[dict] = []
    normalization_rows: list[dict] = []
    lineage_rows: list[dict] = []

    def flush_rows() -> None:
        nonlocal normalization_rows, lineage_rows
        if normalization_rows:
            session.execute(models.RawRecordNormalization.__table__.insert(), normalization_rows)
            normalization_rows = []
        if lineage_rows:
            session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
            lineage_rows = []

    for parsed_file in parsed_files:
        record: models.RawRecord = parsed_file["record"]
        file_object: models.FileObject = parsed_file["file_object"]
        for page in parsed_file["parsed"]["pages"]:
            output_id = _id("RNORM")
            parser_status = page["status"]
            if parser_status == "parsed":
                parsed_count += 1
            else:
                ocr_required_count += 1
            page_number = int(page["page_number"])
            page_text = str(page.get("text") or "")
            normalized_title = mask_sensitive_text(f"{title_prefix} {page_number}")[:240]
            normalized_text = mask_sensitive_text(page_text)
            parser_payload = {
                "activity_name": PDF_TEXT_PARSER_NAME,
                "parser_status": parser_status,
                "parser_version": rule_version,
                "page_number": page_number,
                "source_raw_record_id": record.id,
                "source_file_object_id": file_object.id,
                "file_name": file_object.file_name,
                "text_length": len(page_text),
                "parser_engine": page.get("engine") or parsed_file["parsed"].get("parser_engine") or "builtin_pdf_stream",
                "source_type": record.source_type,
                "synthetic": record.is_synthetic,
            }
            if parser_status != "parsed":
                parser_payload.update({"error_code": page.get("error_code") or "PDF_OCR_REQUIRED", "error_message": page.get("error_message") or "PDF page contains no extractable text; OCR is required."})
            normalization_row = {
                "id": output_id,
                "normalization_run_id": run.id,
                "raw_record_id": record.id,
                "normalized_title": normalized_title,
                "normalized_text": normalized_text,
                "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
                "region_id": record.city_id,
                "payload": parser_payload,
            }
            normalization_rows.append(normalization_row)
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "raw_record",
                    "from_object_id": record.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "pdf_page_parsed_into",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"run_id": run.id, "algorithm_run_id": algorithm_run.id, "parser_status": parser_status, "page_number": page_number},
                }
            )
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "algorithm_run",
                    "from_object_id": algorithm_run.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "generated",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"algorithm_name": PDF_TEXT_PARSER_NAME, "page_number": page_number},
                }
            )
            output_count += 1
            output_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(preview_outputs) < response_limit:
                preview_outputs.append(
                    {
                        "normalization_output_id": output_id,
                        "normalization_run_id": run.id,
                        "raw_record_id": record.id,
                        "normalized_title": normalized_title,
                        "normalized_text": normalized_text,
                        "language": normalization_row["language"],
                        "region_id": record.city_id,
                        "payload": parser_payload,
                        "created_at": None,
                    }
                )
                preview_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(normalization_rows) >= 5000:
                flush_rows()

        record.payload = {
            **(record.payload or {}),
            PDF_TEXT_PARSER_NAME: {
                "status": "completed",
                "normalization_run_id": run.id,
                "page_count": parsed_file["parsed"].get("page_count", 0),
                "parsed_count": parsed_file["parsed"].get("parsed_count", 0),
                "ocr_required_count": parsed_file["parsed"].get("ocr_required_count", 0),
            },
        }
        flag_modified(record, "payload")

    flush_rows()
    completed_at = _now()
    run.status = "completed"
    run.output_count = output_count
    parser_engine = parsed_files[0]["parsed"].get("parser_engine") if parsed_files else None
    run.payload = {**(run.payload or {}), "page_count": total_page_count, "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "response_count": len(preview_outputs), "file_count": len(parsed_files), "parser_engine": parser_engine or "builtin_pdf_stream"}
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {"normalization_run_id": run.id, "page_count": total_page_count, "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "output_count": output_count, "response_count": len(preview_outputs), "parser_engine": parser_engine or "builtin_pdf_stream"}
    algorithm_run.metrics = {"latency_ms": int((completed_at - started_at).total_seconds() * 1000), "input_count": len(records), "page_count": total_page_count, "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "output_count": output_count, "response_count": len(preview_outputs)}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.pdf_text.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"page_count": total_page_count, "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "parser_engine": parser_engine or "builtin_pdf_stream"}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": preview_outputs,
        "parser": {
            "activity_name": PDF_TEXT_PARSER_NAME,
            "algorithm_version": rule_version,
            "page_count": total_page_count,
            "parsed_count": parsed_count,
            "ocr_required_count": ocr_required_count,
            "response_count": len(preview_outputs),
            "parser_engine": parser_engine or "builtin_pdf_stream",
            "files": [item["summary"] for item in parsed_files],
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def _finish_pdf_text_parser_failure(
    session: Session,
    run: models.NormalizationRun,
    algorithm_run: models.AlgorithmRun,
    code: str,
    message: str,
    trace_id: str,
    actor: models.User,
    response_limit: int,
    page_count: int = 0,
    file_summaries: list[dict] | None = None,
) -> dict:
    _fail_processing_run(session, run, code, message)
    completed_at = _now()
    run.output_count = 0
    run.payload = {**(run.payload or {}), "page_count": page_count, "parsed_count": 0, "ocr_required_count": 0, "response_count": 0}
    algorithm_run.status = "failed"
    algorithm_run.error_code = code
    algorithm_run.error_message = message
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = []
    algorithm_run.output = {"normalization_run_id": run.id, "page_count": page_count, "parsed_count": 0, "ocr_required_count": 0, "output_count": 0, "response_count": 0}
    algorithm_run.metrics = {"latency_ms": int((completed_at - (algorithm_run.started_at or completed_at)).total_seconds() * 1000), "input_count": run.input_count, "page_count": page_count, "output_count": 0, "response_limit": response_limit}
    parser_summary = {"activity_name": PDF_TEXT_PARSER_NAME, "algorithm_version": run.rule_version, "page_count": page_count, "parsed_count": 0, "ocr_required_count": 0, "response_count": 0, "files": file_summaries or []}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.pdf_text.failed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": [], "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def run_docx_text_parser(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    payload = dict(request.payload or {})
    response_limit = min(max(int(getattr(request, "response_limit", 100) or 0), 0), 1000)
    rule_version = request.rule_version or DOCX_TEXT_PARSER_VERSION
    title_prefix = str(payload.get("title_prefix") or "DOCX block").strip() or "DOCX block"
    run = models.NormalizationRun(
        id=_id("NRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        output_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=payload | {"activity_name": DOCX_TEXT_PARSER_NAME, "parser": DOCX_TEXT_PARSER_NAME, "response_limit": response_limit, "title_prefix": title_prefix},
    )
    session.add(run)
    session.flush()
    started_at = _now()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="normalization_run",
        object_id=run.id,
        algorithm_name=DOCX_TEXT_PARSER_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": payload, "activity_name": DOCX_TEXT_PARSER_NAME, "response_limit": response_limit},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        return _finish_docx_text_parser_failure(session, run, algorithm_run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched DOCX parser scope.", trace_id, actor, response_limit)

    parsed_files: list[dict] = []
    total_block_count = 0
    total_paragraph_count = 0
    total_table_count = 0
    total_table_cell_count = 0
    for record in records:
        file_ref = (record.payload or {}).get("file_object_ref") if isinstance(record.payload, dict) else {}
        file_object_id = file_ref.get("file_object_id") if isinstance(file_ref, dict) else None
        file_object = session.get(models.FileObject, file_object_id) if file_object_id else None
        if file_object is None or file_object.tenant_id != actor.tenant_id:
            return _finish_docx_text_parser_failure(
                session,
                run,
                algorithm_run,
                "DOCX_FILE_OBJECT_NOT_FOUND",
                "DOCX parser requires a stored file object linked from the raw record.",
                trace_id,
                actor,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object_id, "status": "file_error"}],
            )
        if _file_extension(file_object.file_name) != "docx":
            return _finish_docx_text_parser_failure(
                session,
                run,
                algorithm_run,
                "DOCX_FILE_TYPE_UNSUPPORTED",
                "DOCX parser can only parse .docx uploaded file objects.",
                trace_id,
                actor,
                response_limit,
                file_summaries=[{"raw_record_id": record.id, "file_object_id": file_object.id, "file_name": file_object.file_name, "status": "file_error"}],
            )
        parsed = parse_docx_text(_read_upload_object(file_object))
        file_summary = {
            "raw_record_id": record.id,
            "file_object_id": file_object.id,
            "file_name": file_object.file_name,
            "block_count": parsed.get("block_count", 0),
            "paragraph_count": parsed.get("paragraph_count", 0),
            "table_count": parsed.get("table_count", 0),
            "table_cell_count": parsed.get("table_cell_count", 0),
            "status": parsed["status"],
            "parser_engine": parsed.get("parser_engine") or "ooxml_zip_xml",
        }
        if parsed["status"] != "parsed":
            return _finish_docx_text_parser_failure(
                session,
                run,
                algorithm_run,
                parsed.get("error_code") or "DOCX_PARSE_FAILED",
                parsed.get("error_message") or "DOCX parser failed.",
                trace_id,
                actor,
                response_limit,
                block_count=total_block_count + int(parsed.get("block_count") or 0),
                paragraph_count=total_paragraph_count + int(parsed.get("paragraph_count") or 0),
                table_count=total_table_count + int(parsed.get("table_count") or 0),
                table_cell_count=total_table_cell_count + int(parsed.get("table_cell_count") or 0),
                file_summaries=parsed_files + [file_summary],
            )
        total_block_count += int(parsed.get("block_count") or 0)
        total_paragraph_count += int(parsed.get("paragraph_count") or 0)
        total_table_count += int(parsed.get("table_count") or 0)
        total_table_cell_count += int(parsed.get("table_cell_count") or 0)
        parsed_files.append({"record": record, "file_object": file_object, "parsed": parsed, "summary": file_summary})

    output_count = 0
    preview_outputs: list[dict] = []
    output_refs: list[dict] = []
    normalization_rows: list[dict] = []
    lineage_rows: list[dict] = []

    def flush_rows() -> None:
        nonlocal normalization_rows, lineage_rows
        if normalization_rows:
            session.execute(models.RawRecordNormalization.__table__.insert(), normalization_rows)
            normalization_rows = []
        if lineage_rows:
            session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
            lineage_rows = []

    for parsed_file in parsed_files:
        record: models.RawRecord = parsed_file["record"]
        file_object: models.FileObject = parsed_file["file_object"]
        parsed = parsed_file["parsed"]
        for block in parsed["blocks"]:
            output_id = _id("RNORM")
            block_number = int(block["block_number"])
            block_text = str(block.get("text") or "")
            normalized_title = mask_sensitive_text(f"{title_prefix} {block_number}")[:240]
            normalized_text = mask_sensitive_text(block_text)
            parser_payload = {
                "activity_name": DOCX_TEXT_PARSER_NAME,
                "parser_status": "parsed",
                "parser_version": rule_version,
                "block_number": block_number,
                "block_type": block.get("block_type"),
                "source_raw_record_id": record.id,
                "source_file_object_id": file_object.id,
                "file_name": file_object.file_name,
                "text_length": len(block_text),
                "parser_engine": parsed.get("parser_engine") or "ooxml_zip_xml",
                "source_type": record.source_type,
                "synthetic": record.is_synthetic,
            }
            for key in ("paragraph_number", "table_number", "row_number", "column_number"):
                if block.get(key) is not None:
                    parser_payload[key] = block.get(key)
            normalization_row = {
                "id": output_id,
                "normalization_run_id": run.id,
                "raw_record_id": record.id,
                "normalized_title": normalized_title,
                "normalized_text": normalized_text,
                "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized_title + normalized_text) else "en",
                "region_id": record.city_id,
                "payload": parser_payload,
            }
            normalization_rows.append(normalization_row)
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "raw_record",
                    "from_object_id": record.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "docx_block_parsed_into",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"run_id": run.id, "algorithm_run_id": algorithm_run.id, "block_number": block_number, "block_type": block.get("block_type")},
                }
            )
            lineage_rows.append(
                {
                    "id": _id("LIN"),
                    "from_object_type": "algorithm_run",
                    "from_object_id": algorithm_run.id,
                    "to_object_type": "raw_record_normalization",
                    "to_object_id": output_id,
                    "relation": "generated",
                    "is_synthetic": record.is_synthetic,
                    "payload": {"algorithm_name": DOCX_TEXT_PARSER_NAME, "block_number": block_number, "block_type": block.get("block_type")},
                }
            )
            output_count += 1
            output_refs.append({"object_type": "raw_record_normalization", "object_id": output_id, "object_version": rule_version})
            if len(preview_outputs) < response_limit:
                preview_outputs.append(
                    {
                        "normalization_output_id": output_id,
                        "normalization_run_id": run.id,
                        "raw_record_id": record.id,
                        "normalized_title": normalized_title,
                        "normalized_text": normalized_text,
                        "language": normalization_row["language"],
                        "region_id": record.city_id,
                        "payload": parser_payload,
                        "created_at": None,
                    }
                )
            if len(normalization_rows) >= 5000:
                flush_rows()

        record.payload = {
            **(record.payload or {}),
            DOCX_TEXT_PARSER_NAME: {
                "status": "completed",
                "normalization_run_id": run.id,
                "block_count": parsed.get("block_count", 0),
                "paragraph_count": parsed.get("paragraph_count", 0),
                "table_count": parsed.get("table_count", 0),
                "table_cell_count": parsed.get("table_cell_count", 0),
            },
        }
        flag_modified(record, "payload")

    flush_rows()
    completed_at = _now()
    parser_engine = parsed_files[0]["parsed"].get("parser_engine") if parsed_files else "ooxml_zip_xml"
    run.status = "completed"
    run.output_count = output_count
    run.payload = {
        **(run.payload or {}),
        "block_count": total_block_count,
        "paragraph_count": total_paragraph_count,
        "table_count": total_table_count,
        "table_cell_count": total_table_cell_count,
        "response_count": len(preview_outputs),
        "file_count": len(parsed_files),
        "parser_engine": parser_engine or "ooxml_zip_xml",
    }
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {"normalization_run_id": run.id, "block_count": total_block_count, "paragraph_count": total_paragraph_count, "table_count": total_table_count, "table_cell_count": total_table_cell_count, "output_count": output_count, "response_count": len(preview_outputs), "parser_engine": parser_engine or "ooxml_zip_xml"}
    algorithm_run.metrics = {"latency_ms": int((completed_at - started_at).total_seconds() * 1000), "input_count": len(records), "block_count": total_block_count, "paragraph_count": total_paragraph_count, "table_count": total_table_count, "table_cell_count": total_table_cell_count, "output_count": output_count, "response_count": len(preview_outputs)}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.docx_text.completed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": {"block_count": total_block_count, "paragraph_count": total_paragraph_count, "table_count": total_table_count, "table_cell_count": total_table_cell_count, "parser_engine": parser_engine or "ooxml_zip_xml"}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {
        "outputs": preview_outputs,
        "parser": {
            "activity_name": DOCX_TEXT_PARSER_NAME,
            "algorithm_version": rule_version,
            "block_count": total_block_count,
            "paragraph_count": total_paragraph_count,
            "table_count": total_table_count,
            "table_cell_count": total_table_cell_count,
            "response_count": len(preview_outputs),
            "parser_engine": parser_engine or "ooxml_zip_xml",
            "files": [item["summary"] for item in parsed_files],
        },
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def _finish_docx_text_parser_failure(
    session: Session,
    run: models.NormalizationRun,
    algorithm_run: models.AlgorithmRun,
    code: str,
    message: str,
    trace_id: str,
    actor: models.User,
    response_limit: int,
    block_count: int = 0,
    paragraph_count: int = 0,
    table_count: int = 0,
    table_cell_count: int = 0,
    file_summaries: list[dict] | None = None,
) -> dict:
    _fail_processing_run(session, run, code, message)
    completed_at = _now()
    run.output_count = 0
    run.payload = {**(run.payload or {}), "block_count": block_count, "paragraph_count": paragraph_count, "table_count": table_count, "table_cell_count": table_cell_count, "response_count": 0}
    algorithm_run.status = "failed"
    algorithm_run.error_code = code
    algorithm_run.error_message = message
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = []
    algorithm_run.output = {"normalization_run_id": run.id, "block_count": block_count, "paragraph_count": paragraph_count, "table_count": table_count, "table_cell_count": table_cell_count, "output_count": 0, "response_count": 0}
    algorithm_run.metrics = {"latency_ms": int((completed_at - (algorithm_run.started_at or completed_at)).total_seconds() * 1000), "input_count": run.input_count, "block_count": block_count, "output_count": 0, "response_limit": response_limit}
    parser_summary = {"activity_name": DOCX_TEXT_PARSER_NAME, "algorithm_version": run.rule_version, "block_count": block_count, "paragraph_count": paragraph_count, "table_count": table_count, "table_cell_count": table_cell_count, "response_count": 0, "files": file_summaries or []}
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="parser.docx_text.failed",
        object_type="normalization_run",
        object_id=run.id,
        after={"normalization_run": serialize_normalization_run(run), "parser": parser_summary, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_normalization_run(run) | {"outputs": [], "parser": parser_summary, "algorithm_run": serialize_algorithm_run(algorithm_run)}


def run_deduplication(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    request_payload = dict(request.payload or {})
    rule_version = request.rule_version or DEDUPE_BY_HASH_AND_EXTERNAL_ID_VERSION
    started_at = _now()
    run = models.DeduplicationRun(
        id=_id("DRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        duplicate_group_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=request_payload | {"activity_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME, "algorithm_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME},
    )
    session.add(run)
    session.flush()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="deduplication_run",
        object_id=run.id,
        algorithm_name=DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "data_source_id": record.data_source_id, "source_type": record.source_type, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": request_payload, "activity_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched deduplication scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched deduplication scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_deduplication_run(run) | {
            "groups": [],
            "deduper": {"activity_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME, "duplicate_group_count": 0, "duplicate_record_count": 0, "cross_source_candidate_count": 0},
            "algorithm_run": serialize_algorithm_run(algorithm_run),
        }

    parent = {record.id: record.id for record in records}

    def find(raw_record_id: str) -> str:
        root = raw_record_id
        while parent[root] != root:
            root = parent[root]
        while parent[raw_record_id] != raw_record_id:
            next_id = parent[raw_record_id]
            parent[raw_record_id] = root
            raw_record_id = next_id
        return root

    def union(left_id: str, right_id: str) -> None:
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    scoped_keys: dict[tuple[str, str, str, str], list[models.RawRecord]] = defaultdict(list)
    global_keys: dict[tuple[str, str], dict[str, list[models.RawRecord]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        source_scope = (record.data_source_id, record.source_type)
        for key_type, key_value in _rule_dedupe_record_keys(record):
            scoped_keys[source_scope + (key_type, key_value)].append(record)
            global_keys[(key_type, key_value)][record.data_source_id].append(record)
    for key_records in scoped_keys.values():
        if len(key_records) < 2:
            continue
        kept = key_records[0]
        for record in key_records[1:]:
            union(kept.id, record.id)
    cross_source_candidates: list[dict] = []
    for (key_type, key_value), by_source in global_keys.items():
        if len(by_source) < 2:
            continue
        seen_candidate_ids: set[str] = set()
        for source_records in by_source.values():
            for record in source_records:
                if record.id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(record.id)
                cross_source_candidates.append(
                    {
                        "raw_record_id": record.id,
                        "data_source_id": record.data_source_id,
                        "source_type": record.source_type,
                        "key_type": key_type,
                        "key_hash": _hash(key_value),
                        "source_count": len(by_source),
                        "record_count": sum(len(items) for items in by_source.values()),
                        "reason": f"same_{key_type}_exists_in_other_data_source_but_rule_does_not_merge_cross_source",
                    }
                )
    component_records: dict[str, list[models.RawRecord]] = defaultdict(list)
    for record in records:
        component_records[find(record.id)].append(record)
    groups = []
    duplicate_record_count = 0
    for members in component_records.values():
        if len(members) < 2:
            continue
        data_source_id = members[0].data_source_id
        source_type = members[0].source_type
        match_rules = _rule_dedupe_match_rules(members)
        kept = sorted(members, key=lambda item: (item.created_at.isoformat() if item.created_at else "", item.id))[0]
        duplicates = [item.id for item in members if item.id != kept.id]
        duplicate_of = {duplicate_id: kept.id for duplicate_id in duplicates}
        group = models.RawRecordDedupGroup(
            id=_id("DGRP"),
            deduplication_run_id=run.id,
            group_key=f"dedupe-rule:{data_source_id}:{hashlib.sha256('|'.join(sorted(item.id for item in members)).encode('utf-8')).hexdigest()}"[:160],
            kept_raw_record_id=kept.id,
            duplicate_raw_record_ids=duplicates,
            explanation="same external identity or content_hash within the same data_source and source_type; cross-source matches are candidates only",
            payload={
                "activity_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME,
                "algorithm_version": rule_version,
                "match_rule": match_rules[0],
                "match_rules": match_rules,
                "source_boundary": "same_data_source_only",
                "data_source_id": data_source_id,
                "source_type": source_type,
                "member_count": len(members),
                "duplicate_count": len(duplicates),
                "duplicate_of": duplicate_of,
            },
        )
        groups.append(group)
        session.add(group)
        kept.payload = {
            **(kept.payload or {}),
            DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME: {
                "status": "kept",
                "deduplication_run_id": run.id,
                "dedup_group_id": group.id,
                "duplicate_count": len(duplicates),
                "match_rule": match_rules[0],
                "match_rules": match_rules,
                "source_boundary": "same_data_source_only",
            },
        }
        flag_modified(kept, "payload")
        duplicate_record_count += len(duplicates)
        for duplicate in [item for item in members if item.id != kept.id]:
            dedupe_state = {
                "status": "duplicate",
                "duplicate_of": kept.id,
                "deduplication_run_id": run.id,
                "dedup_group_id": group.id,
                "match_rule": match_rules[0],
                "match_rules": match_rules,
                "source_boundary": "same_data_source_only",
            }
            duplicate.payload = {**(duplicate.payload or {}), "duplicate_of": kept.id, DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME: dedupe_state}
            flag_modified(duplicate, "payload")
            session.add(
                models.LineageEdge(
                    id=_id("LIN"),
                    from_object_type="raw_record",
                    from_object_id=duplicate.id,
                    to_object_type="raw_record",
                    to_object_id=kept.id,
                    relation="deduplicated_into",
                    is_synthetic=duplicate.is_synthetic,
                    payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "group_id": group.id, "match_rule": match_rules[0], "match_rules": match_rules},
                )
            )
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="algorithm_run",
                from_object_id=algorithm_run.id,
                to_object_type="raw_record_dedup_group",
                to_object_id=group.id,
                relation="generated",
                is_synthetic=kept.is_synthetic,
                payload={"run_id": run.id, "algorithm_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME, "match_rule": match_rules[0], "match_rules": match_rules},
            )
        )
    run.status = "completed"
    run.duplicate_group_count = len(groups)
    completed_at = _now()
    deduper = {
        "activity_name": DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME,
        "algorithm_version": rule_version,
        "match_rule": "same_data_source_external_id_or_content_hash",
        "match_rules": ["same_data_source_and_external_id", "same_data_source_and_content_hash"],
        "source_boundary": "same_data_source_only",
        "input_count": len(records),
        "duplicate_group_count": len(groups),
        "duplicate_record_count": duplicate_record_count,
        "cross_source_candidate_count": len(cross_source_candidates),
        "response_group_count": min(len(groups), getattr(request, "response_limit", 100)),
        "cross_source_candidates": cross_source_candidates[:50],
    }
    run.payload = {**(run.payload or {}), **{key: value for key, value in deduper.items() if key != "cross_source_candidates"}, "cross_source_candidates": cross_source_candidates[:50]}
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = [{"object_type": "raw_record_dedup_group", "object_id": group.id, "object_version": rule_version} for group in groups]
    algorithm_run.output = {key: value for key, value in deduper.items() if key != "cross_source_candidates"} | {"cross_source_candidates": cross_source_candidates[:50]}
    algorithm_run.metrics = {
        "latency_ms": int((completed_at - started_at).total_seconds() * 1000),
        "input_count": len(records),
        "duplicate_group_count": len(groups),
        "duplicate_record_count": duplicate_record_count,
        "cross_source_candidate_count": len(cross_source_candidates),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="dedupe.dedupe_by_hash_and_external_id.completed",
        object_type="deduplication_run",
        object_id=run.id,
        after={"deduplication_run": serialize_deduplication_run(run), "deduper": {key: value for key, value in deduper.items() if key != "cross_source_candidates"}, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_deduplication_run(run) | {
        "groups": [serialize_dedup_group(item) for item in groups[:response_limit]],
        "deduper": deduper | {"response_group_count": min(len(groups), response_limit)},
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def run_semantic_deduplication(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    request_payload = _redact_sensitive_payload(dict(request.payload or {}))
    rule_version = request.rule_version or SEMANTIC_DEDUPE_RECORDS_VERSION
    threshold = _semantic_similarity_threshold(request_payload)
    started_at = _now()
    run = models.DeduplicationRun(
        id=_id("DRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        duplicate_group_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=request_payload
        | {
            "activity_name": SEMANTIC_DEDUPE_RECORDS_NAME,
            "algorithm_name": SEMANTIC_DEDUPE_RECORDS_NAME,
            "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
            "synthetic_embedding": True,
            "similarity_threshold": threshold,
        },
    )
    session.add(run)
    session.flush()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="deduplication_run",
        object_id=run.id,
        algorithm_name=SEMANTIC_DEDUPE_RECORDS_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[{"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "data_source_id": record.data_source_id, "source_type": record.source_type, "synthetic": record.is_synthetic} for record in records],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": request_payload, "activity_name": SEMANTIC_DEDUPE_RECORDS_NAME, "embedding_provider": SEMANTIC_DEDUPE_PROVIDER, "synthetic_embedding": True},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched semantic deduplication scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched semantic deduplication scope."
        algorithm_run.completed_at = _now()
        session.commit()
        return serialize_deduplication_run(run) | {
            "groups": [],
            "embedding_errors": [],
            "semantic_deduper": {
                "activity_name": SEMANTIC_DEDUPE_RECORDS_NAME,
                "algorithm_version": rule_version,
                "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
                "synthetic_embedding": True,
                "similarity_threshold": threshold,
                "status": "failed",
                "input_count": 0,
                "embedded_count": 0,
                "candidate_pair_count": 0,
                "candidate_group_count": 0,
                "candidate_record_count": 0,
                "embedding_failed_count": 0,
                "response_group_count": 0,
                "candidate_only": True,
                "review_required": True,
                "merge_state": "candidate_pending_review",
            },
            "algorithm_run": serialize_algorithm_run(algorithm_run),
        }

    record_ids = [record.id for record in records]
    payloads = {
        item.raw_record_id: item
        for item in session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id.in_(record_ids))).scalars()
    }
    embeddings: dict[str, dict] = {}
    embedding_errors: list[dict] = []
    for record in records:
        embedding = _semantic_record_embedding(record, payloads.get(record.id))
        if embedding["status"] != "embedded":
            error = {
                "raw_record_id": record.id,
                "error_code": embedding["error_code"],
                "error_message": embedding["error_message"],
                "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
            }
            embedding_errors.append(error)
            record.payload = {
                **(record.payload or {}),
                SEMANTIC_DEDUPE_RECORDS_NAME: {
                    "status": "embedding_failed",
                    "deduplication_run_id": run.id,
                    "error_code": embedding["error_code"],
                    "error_message": embedding["error_message"],
                    "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
                    "synthetic_embedding": True,
                },
            }
            flag_modified(record, "payload")
            continue
        embeddings[record.id] = embedding

    candidate_pairs = _semantic_candidate_pairs(embeddings, threshold)
    parent = {raw_id: raw_id for raw_id in embeddings}

    def find(raw_record_id: str) -> str:
        root = raw_record_id
        while parent[root] != root:
            root = parent[root]
        while parent[raw_record_id] != raw_record_id:
            next_id = parent[raw_record_id]
            parent[raw_record_id] = root
            raw_record_id = next_id
        return root

    def union(left_id: str, right_id: str) -> None:
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    pair_scores: dict[tuple[str, str], float] = {}
    for left_id, right_id, score in candidate_pairs:
        union(left_id, right_id)
        pair_scores[tuple(sorted((left_id, right_id)))] = score

    by_id = {record.id: record for record in records}
    components: dict[str, list[models.RawRecord]] = defaultdict(list)
    for raw_id in embeddings:
        components[find(raw_id)].append(by_id[raw_id])

    groups: list[models.RawRecordDedupGroup] = []
    candidate_record_ids: set[str] = set()
    for members in components.values():
        if len(members) < 2:
            continue
        ordered_members = sorted(members, key=lambda item: (item.created_at.isoformat() if item.created_at else "", item.id))
        representative = ordered_members[0]
        candidate_ids = [item.id for item in ordered_members[1:]]
        scores = [
            pair_scores[tuple(sorted((left.id, right.id)))]
            for left_index, left in enumerate(ordered_members)
            for right in ordered_members[left_index + 1 :]
            if tuple(sorted((left.id, right.id))) in pair_scores
        ]
        min_similarity = min(scores) if scores else threshold
        max_similarity = max(scores) if scores else threshold
        avg_similarity = round(sum(scores) / max(len(scores), 1), 4)
        group = models.RawRecordDedupGroup(
            id=_id("DGRP"),
            deduplication_run_id=run.id,
            group_key=f"semantic:{hashlib.sha256('|'.join(sorted(item.id for item in ordered_members)).encode('utf-8')).hexdigest()}"[:160],
            kept_raw_record_id=representative.id,
            duplicate_raw_record_ids=candidate_ids,
            explanation="semantic similarity candidate group; candidate only until AT-101 manual dedupe decision",
            payload={
                "activity_name": SEMANTIC_DEDUPE_RECORDS_NAME,
                "algorithm_version": rule_version,
                "match_rule": "semantic_similarity",
                "candidate_only": True,
                "review_required": True,
                "merge_state": "candidate_pending_review",
                "source_boundary": "cross_source_allowed_candidate_only",
                "similarity_threshold": threshold,
                "min_similarity": round(min_similarity, 4),
                "max_similarity": round(max_similarity, 4),
                "avg_similarity": avg_similarity,
                "member_count": len(ordered_members),
                "candidate_count": len(candidate_ids),
                "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
                "synthetic_embedding": True,
                "members": [
                    {
                        "raw_record_id": item.id,
                        "data_source_id": item.data_source_id,
                        "source_type": item.source_type,
                        "token_count": len(embeddings[item.id]["tokens"]),
                    }
                    for item in ordered_members
                ],
            },
        )
        groups.append(group)
        session.add(group)
        for member in ordered_members:
            candidate_record_ids.add(member.id)
            member.payload = {
                **(member.payload or {}),
                SEMANTIC_DEDUPE_RECORDS_NAME: {
                    "status": "candidate",
                    "deduplication_run_id": run.id,
                    "dedup_group_id": group.id,
                    "candidate_only": True,
                    "review_required": True,
                    "merge_state": "candidate_pending_review",
                    "similarity_threshold": threshold,
                    "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
                    "synthetic_embedding": True,
                },
            }
            flag_modified(member, "payload")
            session.add(
                models.LineageEdge(
                    id=_id("LIN"),
                    from_object_type="raw_record",
                    from_object_id=member.id,
                    to_object_type="raw_record_dedup_group",
                    to_object_id=group.id,
                    relation="semantic_candidate_member",
                    is_synthetic=member.is_synthetic,
                    payload={"run_id": run.id, "algorithm_run_id": algorithm_run.id, "match_rule": "semantic_similarity", "candidate_only": True, "similarity_threshold": threshold},
                )
            )
        session.add(
            models.LineageEdge(
                id=_id("LIN"),
                from_object_type="algorithm_run",
                from_object_id=algorithm_run.id,
                to_object_type="raw_record_dedup_group",
                to_object_id=group.id,
                relation="generated",
                is_synthetic=any(item.is_synthetic for item in ordered_members),
                payload={"run_id": run.id, "algorithm_name": SEMANTIC_DEDUPE_RECORDS_NAME, "match_rule": "semantic_similarity", "candidate_only": True},
            )
        )

    status = "partial" if embedding_errors else "completed"
    run.status = status
    run.duplicate_group_count = len(groups)
    completed_at = _now()
    elapsed_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
    semantic_deduper = {
        "activity_name": SEMANTIC_DEDUPE_RECORDS_NAME,
        "algorithm_version": rule_version,
        "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
        "synthetic_embedding": True,
        "similarity_threshold": threshold,
        "status": status,
        "input_count": len(records),
        "embedded_count": len(embeddings),
        "embedding_failed_count": len(embedding_errors),
        "candidate_pair_count": len(candidate_pairs),
        "candidate_group_count": len(groups),
        "candidate_record_count": len(candidate_record_ids),
        "response_group_count": min(len(groups), getattr(request, "response_limit", 100)),
        "candidate_only": True,
        "review_required": True,
        "merge_state": "candidate_pending_review",
    }
    run.payload = {**(run.payload or {}), **semantic_deduper, "embedding_errors": embedding_errors[:50]}
    algorithm_run.status = status
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = [{"object_type": "raw_record_dedup_group", "object_id": group.id, "object_version": rule_version} for group in groups]
    algorithm_run.output = semantic_deduper | {"embedding_errors": embedding_errors[:50]}
    algorithm_run.metrics = {
        "latency_ms": elapsed_ms,
        "input_count": len(records),
        "embedded_count": len(embeddings),
        "embedding_failed_count": len(embedding_errors),
        "candidate_pair_count": len(candidate_pairs),
        "candidate_group_count": len(groups),
        "candidate_record_count": len(candidate_record_ids),
        "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
        "synthetic_embedding": True,
    }
    action_status = "partial" if status == "partial" else "completed"
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action=f"dedupe.semantic_dedupe_records.{action_status}",
        object_type="deduplication_run",
        object_id=run.id,
        after={"deduplication_run": serialize_deduplication_run(run), "semantic_deduper": semantic_deduper, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_deduplication_run(run) | {
        "groups": [serialize_dedup_group(item) for item in groups[:response_limit]],
        "embedding_errors": embedding_errors[:50],
        "semantic_deduper": semantic_deduper | {"response_group_count": min(len(groups), response_limit)},
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def _semantic_similarity_threshold(payload: dict) -> float:
    raw_value = payload.get("similarity_threshold", 0.42)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = 0.42
    return round(min(max(value, 0.05), 0.95), 4)


def _semantic_record_embedding(record: models.RawRecord, raw_payload: models.RawRecordPayload | None) -> dict:
    record_payload = record.payload if isinstance(record.payload, dict) else {}
    semantic_config = record_payload.get("semantic_embedding") if isinstance(record_payload.get("semantic_embedding"), dict) else {}
    if semantic_config.get("force_error") is True:
        return {
            "status": "failed",
            "error_code": "SEMANTIC_EMBEDDING_FORCED_FAILURE",
            "error_message": str(semantic_config.get("reason") or "Semantic embedding was forced to fail for this record."),
        }
    source_text = f"{record.title or ''} {_raw_record_masked_text(record, raw_payload)}"
    normalized = normalize_text(source_text)["normalized_text"]
    tokens = _semantic_shingle_tokens(normalized)
    if len(tokens) < 4:
        return {
            "status": "failed",
            "error_code": "SEMANTIC_TEXT_EMPTY",
            "error_message": "Raw record has insufficient embeddable text after masking and normalization.",
        }
    return {
        "status": "embedded",
        "raw_record_id": record.id,
        "embedding_provider": SEMANTIC_DEDUPE_PROVIDER,
        "synthetic_embedding": True,
        "tokens": tokens,
        "token_count": len(tokens),
        "text_hash": _hash(normalized),
    }


def _semantic_shingle_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for word in re.findall(r"[a-z0-9]{2,}", text.lower()):
        tokens.add(f"w:{word}")
    cjk_segments = re.findall(r"[\u4e00-\u9fff]+", text)
    for segment in cjk_segments:
        for char in segment:
            tokens.add(f"c1:{char}")
        for width in (2, 3):
            if len(segment) < width:
                continue
            for index in range(0, len(segment) - width + 1):
                tokens.add(f"c{width}:{segment[index:index + width]}")
    return tokens


def _semantic_candidate_pairs(embeddings: dict[str, dict], threshold: float) -> list[tuple[str, str, float]]:
    token_index: dict[str, list[str]] = defaultdict(list)
    for raw_id, embedding in embeddings.items():
        for token in embedding["tokens"]:
            token_index[token].append(raw_id)
    pair_hits: dict[tuple[str, str], int] = defaultdict(int)
    for raw_ids in token_index.values():
        if len(raw_ids) < 2 or len(raw_ids) > 500:
            continue
        sorted_ids = sorted(raw_ids)
        for left_index, left_id in enumerate(sorted_ids):
            for right_id in sorted_ids[left_index + 1 :]:
                pair_hits[(left_id, right_id)] += 1
    pairs = []
    for (left_id, right_id), _hit_count in pair_hits.items():
        score = _semantic_similarity(embeddings[left_id]["tokens"], embeddings[right_id]["tokens"])
        if score >= threshold:
            pairs.append((left_id, right_id, score))
    pairs.sort(key=lambda item: (-item[2], item[0], item[1]))
    return pairs


def _semantic_similarity(left_tokens: set[str], right_tokens: set[str]) -> float:
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    if intersection <= 0:
        return 0.0
    union = len(left_tokens | right_tokens)
    jaccard = intersection / max(union, 1)
    cosine = intersection / max((len(left_tokens) * len(right_tokens)) ** 0.5, 1.0)
    overlap = intersection / max(min(len(left_tokens), len(right_tokens)), 1)
    return round(max(jaccard, cosine, overlap * 0.82), 4)


def _rule_dedupe_record_keys(record: models.RawRecord) -> list[tuple[str, str]]:
    keys = [("content_hash", record.content_hash)]
    payload = record.payload if isinstance(record.payload, dict) else {}
    external_id = payload.get("external_id")
    if not isinstance(external_id, str):
        repository = payload.get("repository")
        if isinstance(repository, dict):
            external_id = repository.get("external_id")
    if isinstance(external_id, str) and external_id.strip() and "[MASKED]" not in external_id:
        keys.append(("external_id", external_id.strip()))
    if isinstance(record.dedupe_key, str) and record.dedupe_key.strip():
        keys.append(("dedupe_key", record.dedupe_key.strip()))
    return keys


def _rule_dedupe_match_rules(records: list[models.RawRecord]) -> list[str]:
    repeated: set[str] = set()
    values: dict[tuple[str, str], int] = defaultdict(int)
    for record in records:
        for key_type, key_value in _rule_dedupe_record_keys(record):
            values[(key_type, key_value)] += 1
    for (key_type, _key_value), count in values.items():
        if count < 2:
            continue
        if key_type in {"external_id", "dedupe_key"}:
            repeated.add("same_data_source_and_external_id")
        if key_type == "content_hash":
            repeated.add("same_data_source_and_content_hash")
    ordered = [rule for rule in ["same_data_source_and_external_id", "same_data_source_and_content_hash"] if rule in repeated]
    return ordered or ["same_data_source_and_content_hash"]


def run_data_quality(session: Session, request, actor: models.User, trace_id: str) -> dict:
    records = _scoped_raw_records(session, request.raw_record_ids, request.limit, actor.tenant_id)
    request_payload = _redact_sensitive_payload(dict(request.payload or {}))
    rule_version = request.rule_version or SCORE_CLEAN_RECORD_QUALITY_VERSION
    started_at = _now()
    run = models.DataQualityRun(
        id=_id("QRUN"),
        tenant_id=actor.tenant_id,
        status="running",
        input_count=len(records),
        issue_count=0,
        rule_version=rule_version,
        trace_id=trace_id,
        payload=request_payload | {"activity_name": SCORE_CLEAN_RECORD_QUALITY_NAME, "algorithm_name": SCORE_CLEAN_RECORD_QUALITY_NAME},
    )
    session.add(run)
    session.flush()
    algorithm_run = models.AlgorithmRun(
        id=_id("ALGO"),
        tenant_id=actor.tenant_id,
        object_type="data_quality_run",
        object_id=run.id,
        algorithm_name=SCORE_CLEAN_RECORD_QUALITY_NAME,
        algorithm_version=rule_version,
        status="running",
        input_refs=[
            {
                "object_type": "raw_record",
                "object_id": record.id,
                "object_version": record.content_hash,
                "data_source_id": record.data_source_id,
                "source_type": record.source_type,
                "synthetic": record.is_synthetic,
            }
            for record in records
        ],
        output_refs=[],
        output={},
        metrics={},
        trace_id=trace_id,
        started_at=started_at,
        payload={"request_payload": request_payload, "activity_name": SCORE_CLEAN_RECORD_QUALITY_NAME},
    )
    session.add(algorithm_run)
    session.flush()
    if not records:
        _fail_processing_run(session, run, "RAW_RECORD_SCOPE_EMPTY", "No raw records matched quality scope.")
        algorithm_run.status = "failed"
        algorithm_run.error_code = "RAW_RECORD_SCOPE_EMPTY"
        algorithm_run.error_message = "No raw records matched quality scope."
        algorithm_run.completed_at = _now()
        algorithm_run.metrics = {"latency_ms": 0, "input_count": 0, "score_count": 0}
        session.commit()
        empty_scorer = {
            "activity_name": SCORE_CLEAN_RECORD_QUALITY_NAME,
            "algorithm_version": rule_version,
            "score_count": 0,
            "issue_count": 0,
            "average_overall": 0,
            "average_completeness": 0,
            "average_freshness": 0,
            "average_trust": 0,
            "band_counts": {},
            "response_count": 0,
        }
        return serialize_quality_run(run) | {"issues": [], "scores": [], "quality_scorer": empty_scorer, "algorithm_run": serialize_algorithm_run(algorithm_run)}

    record_ids = [record.id for record in records]
    source_ids = sorted({record.data_source_id for record in records})
    payloads = _raw_record_payloads_by_id(session, record_ids)
    sources = {
        item.id: item
        for item in session.execute(select(models.DataSource).where(models.DataSource.tenant_id == actor.tenant_id, models.DataSource.id.in_(source_ids))).scalars()
    }

    issues: list[models.RawRecordQualityIssue] = []
    score_results: list[dict] = []
    output_refs: list[dict] = []
    lineage_rows: list[dict] = []
    for record in records:
        raw_payload = payloads.get(record.id)
        source = sources.get(record.data_source_id)
        result = score_clean_record_quality(record, raw_payload, source, run.id, algorithm_run.id, rule_version)
        score_results.append(result)
        output_refs.append({"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash, "quality_score": result["scores"]["overall"]})
        for issue in result["issues"]:
            issues.append(
                _quality_issue(
                    run.id,
                    actor.tenant_id,
                    record.id,
                    issue["issue_type"],
                    issue["severity"],
                    issue["message"],
                    payload=issue["payload"],
                )
            )
        record.payload = {**(record.payload or {}), SCORE_CLEAN_RECORD_QUALITY_NAME: result["score_state"]}
        flag_modified(record, "payload")
        lineage_rows.append(
            {
                "id": _id("LIN"),
                "from_object_type": "algorithm_run",
                "from_object_id": algorithm_run.id,
                "to_object_type": "raw_record",
                "to_object_id": record.id,
                "relation": "scored_quality",
                "is_synthetic": record.is_synthetic,
                "payload": {
                    "algorithm_name": SCORE_CLEAN_RECORD_QUALITY_NAME,
                    "data_quality_run_id": run.id,
                    "overall": result["scores"]["overall"],
                    "quality_band": result["quality_band"],
                },
            }
        )

    for issue in issues:
        session.add(issue)
    if lineage_rows:
        session.execute(models.LineageEdge.__table__.insert(), lineage_rows)

    completed_at = _now()
    latency_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
    score_summary = _quality_score_summary(score_results)
    run.status = "completed"
    run.issue_count = len(issues)
    run.payload = {
        **(run.payload or {}),
        "score_summary": score_summary,
        "score_count": len(score_results),
        "issue_type_counts": _quality_issue_type_counts(score_results),
        "response_count": min(len(score_results), getattr(request, "response_limit", 100)),
    }
    algorithm_run.status = "completed"
    algorithm_run.completed_at = completed_at
    algorithm_run.output_refs = output_refs
    algorithm_run.output = {
        "data_quality_run_id": run.id,
        "score_summary": score_summary,
        "issue_count": len(issues),
        "score_count": len(score_results),
    }
    algorithm_run.metrics = {
        "latency_ms": latency_ms,
        "per_item_ms": round(latency_ms / max(len(records), 1), 4),
        "input_count": len(records),
        "score_count": len(score_results),
        "issue_count": len(issues),
    }
    quality_scorer = {
        "activity_name": SCORE_CLEAN_RECORD_QUALITY_NAME,
        "algorithm_version": rule_version,
        "score_count": len(score_results),
        "issue_count": len(issues),
        "average_overall": score_summary["average_overall"],
        "average_completeness": score_summary["average_completeness"],
        "average_freshness": score_summary["average_freshness"],
        "average_trust": score_summary["average_trust"],
        "band_counts": score_summary["band_counts"],
        "response_count": min(len(score_results), getattr(request, "response_limit", 100)),
        "latency_ms": latency_ms,
        "per_item_ms": algorithm_run.metrics["per_item_ms"],
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_quality.score_clean_record_quality.completed",
        object_type="data_quality_run",
        object_id=run.id,
        after={"data_quality_run": serialize_quality_run(run), "quality_scorer": quality_scorer, "algorithm_run_id": algorithm_run.id},
        trace_id=trace_id,
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_quality.run.completed",
        object_type="data_quality_run",
        object_id=run.id,
        after=serialize_quality_run(run),
        trace_id=trace_id,
    )
    session.commit()
    response_limit = getattr(request, "response_limit", 100)
    return serialize_quality_run(run) | {
        "issues": [serialize_quality_issue(item) for item in issues[:response_limit]],
        "scores": [_serialize_quality_score_result(item) for item in score_results[:response_limit]],
        "quality_scorer": quality_scorer,
        "algorithm_run": serialize_algorithm_run(algorithm_run),
    }


def list_processing_runs(session: Session, run_type: str, limit: int = 50, tenant_id: str | None = None) -> list[dict]:
    if run_type == "normalization":
        rows = session.execute(select(models.NormalizationRun).order_by(models.NormalizationRun.created_at.desc()).limit(limit)).scalars()
        return [serialize_normalization_run(row) for row in rows]
    if run_type == "deduplication":
        rows = session.execute(select(models.DeduplicationRun).order_by(models.DeduplicationRun.created_at.desc()).limit(limit)).scalars()
        return [serialize_deduplication_run(row) for row in rows]
    if run_type == "quality":
        statement = select(models.DataQualityRun).order_by(models.DataQualityRun.created_at.desc()).limit(limit)
        if tenant_id:
            statement = statement.where(models.DataQualityRun.tenant_id == tenant_id)
        rows = session.execute(statement).scalars()
        return [serialize_quality_run(row) for row in rows]
    raise _api_error(400, "INVALID_RUN_TYPE", "Unknown processing run type.")


def list_quality_issues(
    session: Session,
    actor: models.User,
    issue_type: str | None = None,
    severity: str | None = None,
    data_quality_run_id: str | None = None,
    raw_record_id: str | None = None,
    data_source_id: str | None = None,
    source_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    trace_id: str | None = None,
) -> tuple[list[dict], dict]:
    allowed_severities = {"info", "warning", "error", "critical"}
    if severity and severity not in allowed_severities:
        raise _api_error(422, "DATA_QUALITY_ISSUE_SEVERITY_INVALID", "Unsupported quality issue severity filter.")
    if source_type and source_type not in {item["source_type"] for item in DATA_SOURCE_TYPES}:
        raise _api_error(422, "DATA_QUALITY_ISSUE_SOURCE_TYPE_INVALID", "Unsupported quality issue source type filter.")
    if data_quality_run_id:
        run = session.get(models.DataQualityRun, data_quality_run_id)
        if run is None:
            raise _api_error(404, "NOT_FOUND", "Data quality run does not exist.")
        if run.tenant_id != actor.tenant_id:
            raise _api_error(403, "FORBIDDEN", "Data quality run belongs to another tenant.")
    if raw_record_id:
        record = session.get(models.RawRecord, raw_record_id)
        if record is None:
            raise _api_error(404, "NOT_FOUND", "Raw record does not exist.")
        if record.tenant_id != actor.tenant_id:
            raise _api_error(403, "FORBIDDEN", "Raw record belongs to another tenant.")
    if data_source_id:
        source = session.get(models.DataSource, data_source_id)
        if source is None:
            raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
        if source.tenant_id != actor.tenant_id:
            raise _api_error(403, "FORBIDDEN", "Data source belongs to another tenant.")

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    from_dt = _parse_optional_datetime(created_from, "DATA_QUALITY_ISSUE_CREATED_FROM_INVALID")
    to_dt = _parse_optional_datetime(created_to, "DATA_QUALITY_ISSUE_CREATED_TO_INVALID")
    issue_filters = [models.RawRecordQualityIssue.tenant_id == actor.tenant_id]
    raw_filters = [models.RawRecord.tenant_id == actor.tenant_id]
    if issue_type:
        issue_filters.append(models.RawRecordQualityIssue.issue_type == issue_type)
    if severity:
        issue_filters.append(models.RawRecordQualityIssue.severity == severity)
    if data_quality_run_id:
        issue_filters.append(models.RawRecordQualityIssue.data_quality_run_id == data_quality_run_id)
    if raw_record_id:
        issue_filters.append(models.RawRecordQualityIssue.raw_record_id == raw_record_id)
    if data_source_id:
        raw_filters.append(models.RawRecord.data_source_id == data_source_id)
    if source_type:
        raw_filters.append(models.RawRecord.source_type == source_type)
    if from_dt is not None:
        issue_filters.append(models.RawRecordQualityIssue.created_at >= from_dt)
    if to_dt is not None:
        issue_filters.append(models.RawRecordQualityIssue.created_at <= to_dt)

    def issue_select(*columns):
        statement = select(*columns).select_from(models.RawRecordQualityIssue)
        if data_source_id or source_type:
            statement = statement.join(models.RawRecord, models.RawRecordQualityIssue.raw_record_id == models.RawRecord.id).where(*raw_filters)
        return statement.where(*issue_filters)

    total = session.execute(
        issue_select(func.count())
    ).scalar_one()
    issue_statement = (
        issue_select(models.RawRecordQualityIssue)
        .order_by(models.RawRecordQualityIssue.created_at.desc(), models.RawRecordQualityIssue.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    issues = list(
        session.execute(issue_statement).scalars()
    )
    issue_type_counts = dict(
        session.execute(
            issue_select(models.RawRecordQualityIssue.issue_type, func.count(models.RawRecordQualityIssue.id))
            .group_by(models.RawRecordQualityIssue.issue_type)
        ).all()
    )
    severity_counts = dict(
        session.execute(
            issue_select(models.RawRecordQualityIssue.severity, func.count(models.RawRecordQualityIssue.id))
            .group_by(models.RawRecordQualityIssue.severity)
        ).all()
    )
    raw_ids = sorted({issue.raw_record_id for issue in issues})
    run_ids = sorted({issue.data_quality_run_id for issue in issues})
    records = {
        item.id: item
        for item in session.execute(select(models.RawRecord).where(models.RawRecord.tenant_id == actor.tenant_id, models.RawRecord.id.in_(raw_ids))).scalars()
    } if raw_ids else {}
    runs = {
        item.id: item
        for item in session.execute(select(models.DataQualityRun).where(models.DataQualityRun.tenant_id == actor.tenant_id, models.DataQualityRun.id.in_(run_ids))).scalars()
    } if run_ids else {}
    items = [
        serialize_data_quality_issue_list_item(issue, records[issue.raw_record_id], runs[issue.data_quality_run_id])
        for issue in issues
        if issue.raw_record_id in records and issue.data_quality_run_id in runs
    ]
    filters_payload = {
        "issue_type": issue_type,
        "severity": severity,
        "data_quality_run_id": data_quality_run_id,
        "raw_record_id": raw_record_id,
        "data_source_id": data_source_id,
        "source_type": source_type,
        "created_from": created_from,
        "created_to": created_to,
    }
    pagination = {"page": page, "page_size": page_size, "total": total}
    meta = {
        "pagination": pagination,
        "filters": filters_payload,
        "page_state": "ready" if items else "empty",
        "summary": {
            "returned_count": len(items),
            "total": total,
            "issue_type_counts": issue_type_counts,
            "severity_counts": severity_counts,
            "source": "postgresql",
        },
        "required_permission": "data_source:read",
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_quality.issue_list_viewed",
        object_type="data_quality_issue",
        object_id="list",
        after={"filters": filters_payload, "pagination": pagination, "returned_count": len(items)},
        trace_id=trace_id,
    )
    session.commit()
    return items, meta


def _create_raw_record(session: Session, source: models.DataSource, run: models.CollectionRun, sample: dict) -> models.RawRecord:
    content_hash = _hash(sample["content"])
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type=sample["source_type"],
        title=sample["title"],
        content_hash=content_hash,
        status="collected",
        is_synthetic=True,
        city_id="xian",
        occurred_at=datetime.utcnow(),
        payload={k: v for k, v in sample.items() if k != "content"} | {"synthetic": True, "source_flags": {"synthetic": True}},
    )
    session.add(record)
    session.flush()
    session.add(models.RawRecordPayload(id=_id("RAWP"), raw_record_id=record.id, content_text=sample["content"], masked_text=mask_sensitive_text(sample["content"]), payload={"synthetic": True}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="collected_from", is_synthetic=True, payload={}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=True, payload={}))
    if sample.get("media_type"):
        asset = models.MediaAsset(id=_id("MED"), raw_record_id=record.id, media_type=sample["media_type"], uri=sample["media_uri"], status="processed", is_synthetic=True, payload={"synthetic": True})
        session.add(asset)
        session.flush()
        session.add(models.MediaProcessingRun(id=_id("MPR"), media_asset_id=asset.id, processor="synthetic_media_processor_v1", status="completed", output={"text": mask_sensitive_text(sample["content"]), "blocked_claims": ["media output is not a fact until evidence review"]}, trace_id=run.trace_id))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="media_asset", to_object_id=asset.id, relation="has_media", is_synthetic=True, payload={}))
    return record


def _fetch_failure(code: str, message: str, source_uri: str | None, retryable: bool, **payload) -> dict:
    return {
        "ok": False,
        "activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME,
        "classification": payload.pop("classification", "failed"),
        "source_uri": source_uri,
        "content_type": payload.pop("content_type", None),
        "http_status_code": payload.pop("http_status_code", None),
        "latency_ms": payload.pop("latency_ms", 0),
        "byte_size": payload.pop("byte_size", 0),
        "content_hash": None,
        "content": None,
        "is_synthetic": bool(payload.pop("is_synthetic", False)),
        "error_code": code,
        "error_message": message,
        "retryable": retryable,
        **payload,
    }


def _fetch_success(content: str, source_uri: str | None, content_type: str, status_code: int | None, latency_ms: int, is_synthetic: bool, truncated: bool = False) -> dict:
    return {
        "ok": True,
        "activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME,
        "classification": "html",
        "source_uri": source_uri,
        "content_type": content_type,
        "http_status_code": status_code,
        "latency_ms": latency_ms,
        "byte_size": len(content.encode("utf-8")),
        "content_hash": _hash(content),
        "content": content,
        "is_synthetic": is_synthetic,
        "truncated": truncated,
        "error_code": None,
        "error_message": None,
        "retryable": False,
    }


def _public_web_fetch_activity_payload(fetch_result: dict) -> dict:
    return {key: value for key, value in fetch_result.items() if key != "content"}


def _is_html_payload(content_type: str | None, raw_body: bytes) -> bool:
    normalized = (content_type or "").lower()
    if "text/html" in normalized or "application/xhtml+xml" in normalized:
        return True
    sample = raw_body[:512].decode("utf-8", errors="replace").strip().lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html")


def _decode_html(raw_body: bytes, content_type: str | None) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type or "", re.IGNORECASE)
    encoding = charset_match.group(1) if charset_match else "utf-8"
    try:
        return raw_body.decode(encoding, errors="replace")
    except LookupError:
        return raw_body.decode("utf-8", errors="replace")


def _synthetic_public_web_html(source_uri: str | None, title: str, request_payload: dict) -> str:
    body = str(request_payload.get("body") or request_payload.get("synthetic_body") or "西安社区公告更新：居民关注补偿进度、公开说明和后续沟通窗口。")
    district = str(request_payload.get("district") or "雁塔区")
    return (
        "<!doctype html><html lang=\"zh-CN\"><head>"
        f"<meta charset=\"utf-8\"><title>{title}</title></head><body>"
        f"<article data-source-uri=\"{source_uri or 'synthetic://xian/public-web'}\" data-synthetic=\"true\">"
        f"<h1>{title}</h1><p>地区：{district}</p><p>{body}</p>"
        "<p>synthetic=true; generated by fetch_public_web_page for a public_web collection run.</p>"
        "</article></body></html>"
    )


def _fetch_synthetic_public_web_page(source_uri: str | None, request) -> dict:
    started = time.perf_counter()
    normalized_uri = (source_uri or "").lower()
    if request.content is not None and request.is_synthetic:
        return _fetch_success(request.content, source_uri, "text/html; charset=utf-8", 200, int((time.perf_counter() - started) * 1000), True)
    if "timeout" in normalized_uri:
        return _fetch_failure("PUBLIC_WEB_TIMEOUT", "Public web page fetch timed out.", source_uri, retryable=True, classification="timeout", latency_ms=PUBLIC_WEB_FETCH_TIMEOUT_SECONDS * 1000, is_synthetic=True)
    if "forbidden" in normalized_uri or "403" in normalized_uri:
        return _fetch_failure("PUBLIC_WEB_FORBIDDEN", "Public web page returned 403 Forbidden.", source_uri, retryable=False, classification="forbidden", http_status_code=403, latency_ms=int((time.perf_counter() - started) * 1000), is_synthetic=True)
    if "non-html" in normalized_uri or "json" in normalized_uri:
        return _fetch_failure("PUBLIC_WEB_NON_HTML", "Public web page response is not HTML.", source_uri, retryable=False, classification="non_html", content_type="application/json", http_status_code=200, latency_ms=int((time.perf_counter() - started) * 1000), is_synthetic=True, byte_size=22)
    content = _synthetic_public_web_html(source_uri, request.title, request.payload or {})
    return _fetch_success(content, source_uri, "text/html; charset=utf-8", 200, int((time.perf_counter() - started) * 1000), True)


def _fetch_public_web_page(source: models.DataSource, request) -> dict:
    source_uri = request.source_uri or str((source.policy or {}).get("start_url") or (source.policy or {}).get("base_url") or "")
    if not source_uri:
        return _fetch_failure("PUBLIC_WEB_SOURCE_URI_REQUIRED", "Public web fetch requires source_uri or source policy URL.", source_uri, retryable=False)
    parsed = urlparse(source_uri)
    is_synthetic = bool(request.is_synthetic or source.is_synthetic or parsed.scheme == "synthetic" or (source.policy or {}).get("is_synthetic"))
    if is_synthetic:
        return _fetch_synthetic_public_web_page(source_uri, request)
    if parsed.scheme not in {"http", "https"}:
        return _fetch_failure("PUBLIC_WEB_SOURCE_URI_INVALID", "Public web fetch supports http and https URLs, or synthetic:// for labeled synthetic sources.", source_uri, retryable=False)

    started = time.perf_counter()
    try:
        url_request = UrlRequest(
            source_uri,
            method="GET",
            headers={
                "User-Agent": "CollectiveEventTwin-PublicWebFetcher/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(url_request, timeout=PUBLIC_WEB_FETCH_TIMEOUT_SECONDS) as response:
            raw_body = response.read(PUBLIC_WEB_FETCH_MAX_BYTES + 1)
            truncated = len(raw_body) > PUBLIC_WEB_FETCH_MAX_BYTES
            raw_body = raw_body[:PUBLIC_WEB_FETCH_MAX_BYTES]
            content_type = response.headers.get("content-type")
            latency_ms = int((time.perf_counter() - started) * 1000)
            if not _is_html_payload(content_type, raw_body):
                return _fetch_failure("PUBLIC_WEB_NON_HTML", "Public web page response is not HTML.", source_uri, retryable=False, classification="non_html", content_type=content_type, http_status_code=response.status, latency_ms=latency_ms, byte_size=len(raw_body))
            return _fetch_success(_decode_html(raw_body, content_type), source_uri, content_type or "text/html", response.status, latency_ms, False, truncated)
    except HTTPError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        content_type = error.headers.get("content-type") if error.headers else None
        if error.code == 403:
            return _fetch_failure("PUBLIC_WEB_FORBIDDEN", "Public web page returned 403 Forbidden.", source_uri, retryable=False, classification="forbidden", content_type=content_type, http_status_code=403, latency_ms=latency_ms)
        return _fetch_failure("PUBLIC_WEB_HTTP_ERROR", f"Public web page returned HTTP {error.code}.", source_uri, retryable=error.code >= 500, classification="http_error", content_type=content_type, http_status_code=error.code, latency_ms=latency_ms)
    except (TimeoutError, socket.timeout):
        return _fetch_failure("PUBLIC_WEB_TIMEOUT", "Public web page fetch timed out.", source_uri, retryable=True, classification="timeout", latency_ms=int((time.perf_counter() - started) * 1000))
    except URLError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        reason = getattr(error, "reason", error)
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
            return _fetch_failure("PUBLIC_WEB_TIMEOUT", "Public web page fetch timed out.", source_uri, retryable=True, classification="timeout", latency_ms=latency_ms)
        return _fetch_failure("PUBLIC_WEB_UNREACHABLE", f"Public web page is unreachable: {reason}", source_uri, retryable=True, classification="unreachable", latency_ms=latency_ms)


def _official_api_failure(code: str, message: str, source_uri: str | None, retryable: bool, **payload) -> dict:
    return {
        "ok": False,
        "activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME,
        "classification": payload.pop("classification", "failed"),
        "source_uri": source_uri,
        "page_count": payload.pop("page_count", 0),
        "record_count": 0,
        "status_code": payload.pop("status_code", None),
        "latency_ms": payload.pop("latency_ms", 0),
        "is_synthetic": bool(payload.pop("is_synthetic", False)),
        "records": [],
        "pages": payload.pop("pages", []),
        "error_code": code,
        "error_message": message,
        "retryable": retryable,
        **payload,
    }


def _official_api_success(source_uri: str | None, records: list[dict], pages: list[dict], latency_ms: int, is_synthetic: bool) -> dict:
    return {
        "ok": True,
        "activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME,
        "classification": "json",
        "source_uri": source_uri,
        "page_count": len(pages),
        "record_count": len(records),
        "status_code": 200,
        "latency_ms": latency_ms,
        "is_synthetic": is_synthetic,
        "records": records,
        "pages": pages,
        "error_code": None,
        "error_message": None,
        "retryable": False,
    }


def _official_api_activity_payload(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "records"}


def _official_api_request_uri(source: models.DataSource, request) -> str | None:
    value = request.source_uri or _official_api_base_url(source.policy or {})
    if isinstance(value, str) and value:
        return value
    return _official_api_base_url(source.policy or {})


def _synthetic_official_api_pages(source_uri: str | None, request, pagination: dict) -> dict:
    started = time.perf_counter()
    normalized = (source_uri or "").lower()
    if "401" in normalized or "unauthorized" in normalized:
        return _official_api_failure("OFFICIAL_API_UNAUTHORIZED", "Official API returned 401 Unauthorized.", source_uri, retryable=False, classification="unauthorized", status_code=401, is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "429" in normalized or "rate-limit" in normalized or "rate_limited" in normalized:
        return _official_api_failure("OFFICIAL_API_RATE_LIMITED", "Official API returned 429 Too Many Requests.", source_uri, retryable=True, classification="rate_limited", status_code=429, is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "500" in normalized or "5xx" in normalized or "upstream" in normalized:
        return _official_api_failure("OFFICIAL_API_UPSTREAM_ERROR", "Official API returned an upstream 5xx error.", source_uri, retryable=True, classification="upstream_error", status_code=500, is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))

    max_pages = int(pagination.get("max_pages") or 1)
    page_size = int((request.payload or {}).get("page_size") or pagination.get("page_size") or 3)
    pages = []
    records = []
    for page_number in range(1, max_pages + 1):
        page_records = []
        for item_index in range(1, page_size + 1):
            external_id = f"xian-official-p{page_number:03d}-{item_index:03d}"
            item = {
                "id": external_id,
                "title": f"西安官方接口事项 {page_number}-{item_index}",
                "summary": "synthetic official API record for Xi'an public issue collection.",
                "city_id": "xian",
                "district": "雁塔区" if page_number % 2 else "莲湖区",
                "source_uri": source_uri,
                "page_number": page_number,
                "item_index": item_index,
                "synthetic": True,
            }
            page_records.append(item)
            records.append({"page_number": page_number, "item_index": item_index, "page_uri": f"{source_uri}?page={page_number}", "item": item})
        pages.append({"page_number": page_number, "status_code": 200, "record_count": len(page_records), "next_page": page_number + 1 if page_number < max_pages else None, "is_synthetic": True})
    return _official_api_success(source_uri, records, pages, int((time.perf_counter() - started) * 1000), True)


def _json_path_items(payload: dict, records_path: str | None) -> list[dict]:
    if not records_path or records_path == "$":
        return payload if isinstance(payload, list) else [payload]
    if records_path.startswith("$."):
        current = payload
        for part in records_path[2:].split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return []
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
        if isinstance(current, dict):
            return [current]
    return []


def _append_query_param(url: str, params: dict[str, object]) -> str:
    connector = "&" if "?" in url else "?"
    return url + connector + urlencode({key: value for key, value in params.items() if value is not None})


def _fetch_official_api_pages(source: models.DataSource, request) -> dict:
    source_uri = _official_api_request_uri(source, request)
    if not source_uri:
        return _official_api_failure("OFFICIAL_API_SOURCE_URI_REQUIRED", "Official API fetch requires source_uri or source base_url.", source_uri, retryable=False)
    policy = source.policy or {}
    _validate_official_api_policy(policy)
    pagination = policy.get("pagination") if isinstance(policy.get("pagination"), dict) else {}
    parsed = urlparse(source_uri)
    is_synthetic = bool(request.is_synthetic or source.is_synthetic or parsed.scheme == "synthetic" or _policy_is_synthetic(policy))
    if is_synthetic:
        return _synthetic_official_api_pages(source_uri, request, pagination)
    if parsed.scheme not in {"https"}:
        return _official_api_failure("OFFICIAL_API_HTTPS_REQUIRED", "Official API fetch supports https URLs, or synthetic:// for labeled synthetic sources.", source_uri, retryable=False)

    started = time.perf_counter()
    max_pages = int(pagination.get("max_pages") or 1)
    page_param = str(pagination.get("page_param") or "page")
    page_size_param = str(pagination.get("page_size_param") or "limit")
    page_size = int((request.payload or {}).get("page_size") or 100)
    schema = policy.get("schema") if isinstance(policy.get("schema"), dict) else {}
    records_path = str(schema.get("records_path") or "$.items")
    pages = []
    records = []
    for page_number in range(1, max_pages + 1):
        page_url = _append_query_param(source_uri, {page_param: page_number, page_size_param: page_size})
        url_request = UrlRequest(page_url, method=str(policy.get("method") or "GET"), headers={"Accept": "application/json", "User-Agent": "CollectiveEventTwin-OfficialApiFetcher/1.0", "X-CET-Secret-Ref": str(policy.get("secret_ref") or "")})
        try:
            with urlopen(url_request, timeout=PUBLIC_WEB_FETCH_TIMEOUT_SECONDS) as response:
                raw = response.read(PUBLIC_WEB_FETCH_MAX_BYTES)
                page_payload = json.loads(raw.decode("utf-8"))
                page_items = _json_path_items(page_payload, records_path)
                pages.append({"page_number": page_number, "status_code": response.status, "record_count": len(page_items), "page_uri": page_url, "is_synthetic": False})
                for item_index, item in enumerate(page_items, start=1):
                    records.append({"page_number": page_number, "item_index": item_index, "page_uri": page_url, "item": item})
                if not page_items:
                    break
        except HTTPError as error:
            latency_ms = int((time.perf_counter() - started) * 1000)
            if error.code == 401:
                return _official_api_failure("OFFICIAL_API_UNAUTHORIZED", "Official API returned 401 Unauthorized.", source_uri, retryable=False, classification="unauthorized", status_code=401, latency_ms=latency_ms)
            if error.code == 429:
                return _official_api_failure("OFFICIAL_API_RATE_LIMITED", "Official API returned 429 Too Many Requests.", source_uri, retryable=True, classification="rate_limited", status_code=429, latency_ms=latency_ms)
            if error.code >= 500:
                return _official_api_failure("OFFICIAL_API_UPSTREAM_ERROR", f"Official API returned HTTP {error.code}.", source_uri, retryable=True, classification="upstream_error", status_code=error.code, latency_ms=latency_ms)
            return _official_api_failure("OFFICIAL_API_HTTP_ERROR", f"Official API returned HTTP {error.code}.", source_uri, retryable=False, classification="http_error", status_code=error.code, latency_ms=latency_ms)
        except (TimeoutError, socket.timeout):
            return _official_api_failure("OFFICIAL_API_TIMEOUT", "Official API request timed out.", source_uri, retryable=True, classification="timeout", latency_ms=int((time.perf_counter() - started) * 1000))
        except (URLError, json.JSONDecodeError) as error:
            return _official_api_failure("OFFICIAL_API_UNREACHABLE", f"Official API fetch failed: {error}", source_uri, retryable=True, classification="unreachable", latency_ms=int((time.perf_counter() - started) * 1000))
    return _official_api_success(source_uri, records, pages, int((time.perf_counter() - started) * 1000), False)


def _domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain.lower() or host.endswith(f".{domain.lower()}") for domain in allowed_domains)


def _resolve_link(base_url: str, href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https", "synthetic"}:
        return href
    base = base_url.rstrip("/")
    if href.startswith("/"):
        parsed_base = urlparse(base_url)
        if parsed_base.scheme == "synthetic":
            return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        return f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
    return f"{base}/{href}"


def _robots_disallowed(url: str, respect_robots: bool) -> bool:
    if not respect_robots:
        return False
    normalized = url.lower()
    return "robots-deny" in normalized or "robots-disallow" in normalized or "disallow-all" in normalized


def _synthetic_public_web_links(start_url: str, max_depth: int, limit: int) -> list[dict]:
    links = []
    normalized_start = start_url.rstrip("/")
    for index in range(limit):
        if index == 0:
            url = normalized_start
            parent_url = None
            depth = 0
        else:
            depth = 1 + ((index - 1) % max_depth) if max_depth > 0 else 0
            url = f"{normalized_start}/d{depth}/link-{index:04d}"
            parent_url = normalized_start if depth <= 1 else f"{normalized_start}/d{depth - 1}/link-{max(index - 1, 1):04d}"
        links.append({"url": url, "depth": depth, "parent_url": parent_url, "status": "pending", "is_synthetic": True})
    return links


def _extract_html_links(base_url: str, html: str, max_depth: int, limit: int, allowed_domains: list[str], respect_robots: bool) -> dict:
    links = [{"url": base_url, "depth": 0, "parent_url": None, "status": "pending", "is_synthetic": False}]
    skipped = []
    seen = {base_url}
    if max_depth == 0:
        return {"pending_urls": links[:limit], "skipped_urls": skipped}
    for match in re.finditer(r"<a\s+[^>]*href=[\"']([^\"']+)[\"']", html, re.IGNORECASE):
        if len(links) >= limit:
            break
        resolved = _resolve_link(base_url, match.group(1))
        if not resolved or resolved in seen or not _domain_allowed(resolved, allowed_domains):
            continue
        seen.add(resolved)
        if _robots_disallowed(resolved, respect_robots):
            skipped.append({"url": resolved, "depth": 1, "parent_url": base_url, "status": "skipped", "reason": "ROBOTS_DISALLOWED", "is_synthetic": False})
            continue
        links.append({"url": resolved, "depth": 1, "parent_url": base_url, "status": "pending", "is_synthetic": False})
    return {"pending_urls": links, "skipped_urls": skipped}


def _discover_public_web_links(source: models.DataSource, start_url: str, max_depth: int, limit: int, respect_robots: bool, allowed_domains: list[str]) -> dict:
    started = time.perf_counter()
    is_synthetic = bool(source.is_synthetic or start_url.startswith("synthetic://") or (source.policy or {}).get("is_synthetic"))
    if _robots_disallowed(start_url, respect_robots):
        return {
            "pending_urls": [],
            "skipped_urls": [{"url": start_url, "depth": 0, "reason": "ROBOTS_DISALLOWED", "is_synthetic": is_synthetic}],
            "is_synthetic": is_synthetic,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    if is_synthetic:
        return {
            "pending_urls": _synthetic_public_web_links(start_url, max_depth, limit),
            "skipped_urls": [],
            "is_synthetic": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    class RequestShape:
        title = "Public web discovery seed"
        source_uri = start_url
        content = None
        is_synthetic = False
        payload = {}

    fetched = _fetch_public_web_page(source, RequestShape())
    if not fetched["ok"]:
        return {
            "pending_urls": [],
            "skipped_urls": [{"url": start_url, "depth": 0, "reason": fetched["error_code"], "message": fetched["error_message"], "is_synthetic": False}],
            "is_synthetic": False,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    extracted = _extract_html_links(start_url, fetched["content"] or "", max_depth, limit, allowed_domains, respect_robots)
    return {
        "pending_urls": extracted["pending_urls"],
        "skipped_urls": extracted["skipped_urls"],
        "is_synthetic": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _create_import_raw_record(session: Session, source: models.DataSource, run: models.CollectionRun, import_run: models.ImportRun, request, import_type: str, content: str, is_synthetic: bool, fetch_result: dict | None = None) -> models.RawRecord:
    fetch_activity = _public_web_fetch_activity_payload(fetch_result) if fetch_result else None
    record_payload = {
        "import_type": import_type,
        "source_uri": request.source_uri,
        "synthetic": is_synthetic,
        "source_flags": {"synthetic": is_synthetic, "import_type": import_type},
        "request_payload": request.payload,
    }
    if fetch_activity:
        record_payload.update(
            {
                "fetch_activity": fetch_activity,
                "content_type": fetch_result.get("content_type"),
                "http_status_code": fetch_result.get("http_status_code"),
                "byte_size": fetch_result.get("byte_size"),
            }
        )
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type=source.source_type,
        title=request.title,
        content_hash=_hash(content),
        status="collected",
        is_synthetic=is_synthetic,
        city_id=request.city_id,
        occurred_at=datetime.utcnow(),
        payload=record_payload,
    )
    session.add(record)
    session.flush()
    raw_payload = {"import_run_id": import_run.id, "synthetic": is_synthetic}
    if fetch_activity:
        raw_payload.update({"activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME, "content_type": fetch_result.get("content_type"), "content_hash": fetch_result.get("content_hash")})
    session.add(models.RawRecordPayload(id=_id("RAWP"), raw_record_id=record.id, content_text=content, masked_text=mask_sensitive_text(content), payload=raw_payload))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="imported_from", is_synthetic=is_synthetic, payload={"import_type": import_type}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="import_run", from_object_id=import_run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={}))
    if fetch_activity:
        file_object = models.FileObject(
            id=_id("FILE"),
            tenant_id=source.tenant_id,
            owner_user_id=None,
            object_type="raw_record",
            object_id=record.id,
            storage_key=f"raw-records/{record.id}/original.html",
            file_name=f"{record.id}.html",
            mime_type=str(fetch_result.get("content_type") or "text/html"),
            byte_size=int(fetch_result.get("byte_size") or len(content.encode("utf-8"))),
            checksum=str(fetch_result.get("content_hash") or _hash(content)),
            status="stored",
            access_policy={"scope": "tenant", "synthetic": is_synthetic},
            source_refs=[
                {"object_type": "data_source", "object_id": source.id},
                {"object_type": "collection_run", "object_id": run.id},
                {"object_type": "import_run", "object_id": import_run.id},
            ],
            payload={"activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME, "source_uri": request.source_uri, "storage_mode": "raw_record_payload", "content_hash": fetch_result.get("content_hash")},
        )
        session.add(file_object)
        session.flush()
        record.payload = {**(record.payload or {}), "object_ref": {"file_object_id": file_object.id, "storage_key": file_object.storage_key, "mime_type": file_object.mime_type}}
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="file_object", to_object_id=file_object.id, relation="has_raw_html_object", is_synthetic=is_synthetic, payload={"activity_name": PUBLIC_WEB_FETCH_ACTIVITY_NAME}))
    if request.media_type and request.media_uri:
        media_policy = source.policy or {}
        ocr_policy = media_policy.get("ocr_policy") if isinstance(media_policy.get("ocr_policy"), dict) else {}
        vlm_policy = media_policy.get("vlm_policy") if isinstance(media_policy.get("vlm_policy"), dict) else {}
        redaction_policy = media_policy.get("redaction_policy") if isinstance(media_policy.get("redaction_policy"), dict) else {}
        keyframe_policy = media_policy.get("keyframe_policy") if isinstance(media_policy.get("keyframe_policy"), dict) else {}
        asr_policy = media_policy.get("asr_policy") if isinstance(media_policy.get("asr_policy"), dict) else {}
        large_video_policy = media_policy.get("large_video_policy") if isinstance(media_policy.get("large_video_policy"), dict) else {}
        segment_policy = media_policy.get("segment_policy") if isinstance(media_policy.get("segment_policy"), dict) else {}
        buffer_policy = media_policy.get("buffer_policy") if isinstance(media_policy.get("buffer_policy"), dict) else {}
        retention_policy = media_policy.get("retention_policy") if isinstance(media_policy.get("retention_policy"), dict) else {}
        segmentation_policy = media_policy.get("segmentation_policy") if isinstance(media_policy.get("segmentation_policy"), dict) else {}
        language_policy = media_policy.get("language_policy") if isinstance(media_policy.get("language_policy"), dict) else {}
        masked_text = mask_sensitive_text(content)
        media_channel = "livestream" if request.media_type == "live_segment" else "audio_file" if request.media_type == "audio" else "video_file" if request.media_type == "video" else "image_file" if request.media_type == "image" else request.media_type
        asset = models.MediaAsset(
            id=_id("MED"),
            raw_record_id=record.id,
            media_type=request.media_type,
            uri=request.media_uri,
            status="processed",
            is_synthetic=is_synthetic,
            payload={"source_uri": request.source_uri, "synthetic": is_synthetic, "channel": media_channel, "redaction_policy": redaction_policy},
        )
        session.add(asset)
        session.flush()
        caption_kind = "livestream segment" if request.media_type == "live_segment" else "audio" if request.media_type == "audio" else "video" if request.media_type == "video" else "image"
        keyframe_interval = int(keyframe_policy.get("interval_seconds", 10) or 10)
        max_keyframes = int(keyframe_policy.get("max_keyframes", 3) or 3)
        keyframe_count = max(1, min(3, max_keyframes))
        media_output = {
            "text": masked_text,
            "ocr": {"enabled": bool(ocr_policy.get("enabled", True)), "engine": ocr_policy.get("engine", "synthetic_ocr"), "text": masked_text if bool(ocr_policy.get("store_text", True)) else "", "languages": ocr_policy.get("languages", ["zh-CN", "en"])},
            "vlm": {
                "enabled": bool(vlm_policy.get("enabled", True)),
                "provider": vlm_policy.get("provider", "synthetic_deterministic_caption"),
                "caption": f"candidate {caption_kind} context for {mask_sensitive_text(record.title)}",
                "evidence_mode": vlm_policy.get("evidence_mode", "candidate_only"),
            },
            "redaction": {"enabled": bool(redaction_policy.get("enabled", True)), "strategy": redaction_policy.get("strategy", "mask_faces_and_text"), "text_redacted": masked_text != content},
            "blocked_claims": ["media output is not a factual finding until evidence review"],
            "synthetic": is_synthetic,
        }
        if request.media_type == "video":
            media_output.update(
                {
                    "keyframes": {
                        "strategy": keyframe_policy.get("strategy", "interval_seconds"),
                        "interval_seconds": keyframe_interval,
                        "max_keyframes": max_keyframes,
                        "frames": [
                            {"index": index + 1, "timestamp_seconds": index * keyframe_interval, "status": "synthetic_candidate"}
                            for index in range(keyframe_count)
                        ],
                    },
                    "asr": {"enabled": bool(asr_policy.get("enabled", True)), "engine": asr_policy.get("engine", "synthetic_asr"), "text": masked_text if bool(asr_policy.get("store_text", True)) else "", "languages": asr_policy.get("languages", ["zh-CN", "en"])},
                    "ocr": {
                        **media_output["ocr"],
                        "keyframe_only": bool(ocr_policy.get("keyframe_only", True)),
                    },
                    "large_video_policy": large_video_policy,
                }
            )
        if request.media_type == "live_segment":
            segment_seconds = int(segment_policy.get("segment_seconds", 10) or 10)
            max_segments = int(segment_policy.get("max_segments_per_run", 1) or 1)
            segment_count = max(1, min(3, max_segments))
            media_output.update(
                {
                    "live_segment": {
                        "stream_url": media_policy.get("stream_url") or request.source_uri,
                        "stream_protocol": media_policy.get("stream_protocol", "synthetic"),
                        "segment_policy": segment_policy,
                        "buffer_policy": buffer_policy,
                        "retention_policy": retention_policy,
                        "segments": [
                            {"index": index + 1, "start_second": index * segment_seconds, "duration_seconds": segment_seconds, "status": "synthetic_candidate"}
                            for index in range(segment_count)
                        ],
                    }
                }
            )
        if request.media_type == "audio":
            segment_seconds = int(segmentation_policy.get("segment_seconds", 30) or 30)
            overlap_seconds = int(segmentation_policy.get("overlap_seconds", 0) or 0)
            media_output.update(
                {
                    "asr": {"enabled": bool(asr_policy.get("enabled", True)), "engine": asr_policy.get("engine", "synthetic_asr"), "text": masked_text if bool(asr_policy.get("store_text", True)) else "", "language": language_policy.get("primary_language", "zh-CN")},
                    "audio": {
                        "segmentation_policy": segmentation_policy,
                        "language_policy": language_policy,
                        "segments": [
                            {"index": index + 1, "start_second": index * max(1, segment_seconds - overlap_seconds), "duration_seconds": segment_seconds, "status": "synthetic_candidate"}
                            for index in range(3)
                        ],
                    },
                }
            )
        processor_name = "s2_import_live_segment_processor_v1" if request.media_type == "live_segment" else "s2_import_audio_media_processor_v1" if request.media_type == "audio" else "s2_import_video_media_processor_v1" if request.media_type == "video" else "s2_import_media_processor_v1"
        session.add(models.MediaProcessingRun(id=_id("MPR"), media_asset_id=asset.id, processor=processor_name, status="completed", output=media_output, trace_id=run.trace_id))
        session.add(models.LineageEdge(id=_id("LIN"), from_object_type="raw_record", from_object_id=record.id, to_object_type="media_asset", to_object_id=asset.id, relation="has_media", is_synthetic=is_synthetic, payload={"import_type": import_type}))
    return record


def _create_file_upload_raw_record(
    session: Session,
    source: models.DataSource,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    file_object: models.FileObject,
    title: str,
    content_text: str,
    is_synthetic: bool,
    city_id: str | None,
    request_payload: dict | None,
) -> models.RawRecord:
    file_ref = {
        "file_object_id": file_object.id,
        "storage_key": file_object.storage_key,
        "file_name": file_object.file_name,
        "mime_type": file_object.mime_type,
        "byte_size": file_object.byte_size,
        "checksum": file_object.checksum,
    }
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type="file_upload",
        title=title,
        content_hash=file_object.checksum or _hash(content_text),
        status="collected",
        is_synthetic=is_synthetic,
        city_id=city_id or "xian",
        occurred_at=datetime.utcnow(),
        payload={
            "import_type": "file_upload",
            "file_object_ref": file_ref,
            "source_flags": {"synthetic": is_synthetic, "import_type": "file_upload"},
            "synthetic": is_synthetic,
            "request_payload": request_payload or {},
            "import_run_id": import_run.id,
            "collection_run_id": run.id,
        },
    )
    session.add(record)
    session.flush()
    session.add(
        models.RawRecordPayload(
            id=_id("RAWP"),
            raw_record_id=record.id,
            content_text=content_text,
            masked_text=mask_sensitive_text(content_text),
            payload={"import_run_id": import_run.id, "synthetic": is_synthetic, "file_object_id": file_object.id, "checksum": file_object.checksum},
        )
    )
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="file_object", from_object_id=file_object.id, to_object_type="raw_record", to_object_id=record.id, relation="file_imported_as_raw_record", is_synthetic=is_synthetic, payload={"import_run_id": import_run.id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="file_imported_from", is_synthetic=is_synthetic, payload={"file_object_id": file_object.id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="import_run", from_object_id=import_run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"file_object_id": file_object.id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"file_object_id": file_object.id}))
    return record


def _create_official_api_raw_record(session: Session, source: models.DataSource, run: models.CollectionRun, import_run: models.ImportRun, request, fetched_item: dict, activity: dict, is_synthetic: bool) -> models.RawRecord:
    item = fetched_item["item"]
    content = json.dumps(item, ensure_ascii=False, sort_keys=True)
    title = str(item.get("title") or item.get("name") or f"{request.title} p{fetched_item['page_number']} #{fetched_item['item_index']}")[:240]
    external_id = str(item.get("id") or item.get("external_id") or _hash(content))
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type=source.source_type,
        title=title,
        content_hash=_hash(content),
        status="collected",
        is_synthetic=is_synthetic,
        city_id=str(item.get("city_id") or request.city_id or "xian"),
        occurred_at=datetime.utcnow(),
        payload={
            "import_type": "official_api",
            "source_uri": request.source_uri,
            "page_uri": fetched_item.get("page_uri"),
            "page_number": fetched_item["page_number"],
            "item_index": fetched_item["item_index"],
            "external_id": external_id,
            "content_type": "application/json",
            "synthetic": is_synthetic,
            "source_flags": {"synthetic": is_synthetic, "import_type": "official_api"},
            "request_payload": request.payload,
            "official_api_activity": activity,
        },
    )
    session.add(record)
    session.flush()
    session.add(
        models.RawRecordPayload(
            id=_id("RAWP"),
            raw_record_id=record.id,
            content_text=content,
            masked_text=mask_sensitive_text(content),
            payload={"import_run_id": import_run.id, "synthetic": is_synthetic, "activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME, "page_number": fetched_item["page_number"], "external_id": external_id},
        )
    )
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="official_api_fetched_from", is_synthetic=is_synthetic, payload={"page_number": fetched_item["page_number"], "external_id": external_id}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="import_run", from_object_id=import_run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"activity_name": OFFICIAL_API_FETCH_ACTIVITY_NAME}))
    return record


def _dead_letter_id(target_type: str, target_id: str) -> str:
    digest = hashlib.sha256(f"{target_type}:{target_id}".encode("utf-8")).hexdigest()[:24]
    return f"DLQ-{digest}"


def _record_dead_letter(
    session: Session,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    source: models.DataSource,
    code: str,
    message: str,
    retry_policy: dict,
    actor: models.User | None = None,
    trace_id: str | None = None,
) -> models.OpsErrorQueue:
    dead_letter_id = _dead_letter_id("import_run", import_run.id)
    existing = session.get(models.OpsErrorQueue, dead_letter_id)
    if existing is not None:
        return existing

    failure_payload = dict(import_run.payload or {})
    retry_state = dict(retry_policy or {})
    classification = str(retry_state.get("classification") or ("transient" if retry_state.get("retryable") else "permanent"))
    payload = {
        "dead_letter_id": dead_letter_id,
        "tenant_id": source.tenant_id,
        "target_type": "import_run",
        "target_id": import_run.id,
        "import_run_id": import_run.id,
        "collection_run_id": run.id,
        "data_source_id": source.id,
        "source_type": source.source_type,
        "error_code": code,
        "error_message": message,
        "retryable": bool(retry_state.get("retryable")),
        "classification": classification,
        "failure_payload": failure_payload,
        "retry_policy": retry_state,
        "source_version": _collection_version_payload(source),
        "collection_run": {"status": run.status, "error_code": run.error_code, "trace_id": run.trace_id},
        "created_from": "import_failure",
        "synthetic": bool(import_run.is_synthetic or source.is_synthetic or failure_payload.get("is_synthetic") or failure_payload.get("synthetic")),
    }
    row = models.OpsErrorQueue(
        id=dead_letter_id,
        source="dead_letter",
        severity="warning" if classification == "permanent" else "error",
        status="open",
        message=message,
        payload=payload,
    )
    session.add(row)
    session.add(
        models.CollectionRunEvent(
            id=_id("CREV"),
            collection_run_id=run.id,
            event_type="dead_letter_created",
            status="open",
            payload={"dead_letter_id": dead_letter_id, "target_type": "import_run", "target_id": import_run.id, "error_code": code, "classification": classification},
        )
    )
    if actor is not None:
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="dead_letter.create",
            object_type="dead_letter",
            object_id=dead_letter_id,
            after=serialize_dead_letter(row),
            trace_id=trace_id or run.trace_id,
        )
    return row


def _fail_import(session: Session, run: models.CollectionRun, import_run: models.ImportRun, source: models.DataSource, code: str, message: str, retryable: bool, actor: models.User | None = None, trace_id: str | None = None) -> None:
    run.status = "failed"
    run.error_code = code
    run.error_message = message
    import_run.status = "failed"
    import_run.error_code = code
    import_run.error_message = message
    job = session.get(models.CollectionJob, run.collection_job_id)
    channel = _collection_job_channel(source, job.payload if job is not None else None)
    checkpoint = {
        "checkpoint_id": _id("CHK"),
        "channel": channel,
        "resume_from_step": "fetch",
        "failed_step": "fetch",
        "collection_run_id": run.id,
        "import_run_id": import_run.id,
        "error_code": code,
        "retryable": retryable,
        "created_at": _now().isoformat(),
    }
    run.payload = {
        **(run.payload or {}),
        "collection_channel": channel,
        "channel_checkpoint": checkpoint,
        "workflow_status": "failed",
    }
    import_run.payload = {**(import_run.payload or {}), "channel_checkpoint": checkpoint}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="import_failed", status="failed", payload={"error_code": code, "message": message}))
    session.add(models.OpsErrorQueue(id=_id("ERRQ"), source="import_run", severity="warning", status="open", message=message, payload={"import_run_id": import_run.id, "collection_run_id": run.id, "data_source_id": source.id, "error_code": code}))
    retry_state = _apply_retry_policy(session, run, import_run, source, code, message, retryable)
    _record_dead_letter(session, run, import_run, source, code, message, retry_state, actor=actor, trace_id=trace_id)
    _update_health(session, source.id, run.id, success=False, error_code=code)


def _fail_processing_run(session: Session, run, code: str, message: str) -> None:
    run.status = "failed"
    run.error_code = code
    run.error_message = message
    session.add(models.OpsErrorQueue(id=_id("ERRQ"), source=run.__tablename__, severity="warning", status="open", message=message, payload={"run_id": run.id, "error_code": code}))


def _policy_is_synthetic(policy: dict | None) -> bool:
    if not policy:
        return False
    if policy.get("is_synthetic") is True:
        return True
    for key in ("base_url", "start_url", "source_uri", "feed_url"):
        value = policy.get(key)
        if isinstance(value, str) and value.startswith("synthetic://"):
            return True
    crawl_policy = policy.get("crawl_policy")
    if isinstance(crawl_policy, dict):
        start_url = crawl_policy.get("start_url")
        if isinstance(start_url, str) and start_url.startswith("synthetic://"):
            return True
    return False


def _compliance_state(policy: dict | None) -> dict:
    compliance = policy.get("compliance") if isinstance(policy, dict) else None
    if not isinstance(compliance, dict):
        return {"compliance_ready": False, "compliance_missing_fields": ["authorization_scope", "authorization_basis", "retention_days", "data_classification"]}
    missing = []
    if not str(compliance.get("authorization_scope") or "").strip():
        missing.append("authorization_scope")
    if len(str(compliance.get("authorization_basis") or "").strip()) < 8:
        missing.append("authorization_basis")
    retention_days = compliance.get("retention_days")
    if not isinstance(retention_days, int) or retention_days < 1:
        missing.append("retention_days")
    if str(compliance.get("data_classification") or "") not in {"public", "internal", "restricted", "sensitive"}:
        missing.append("data_classification")
    return {"compliance_ready": not missing, "compliance_missing_fields": missing}


def _normalize_compliance_update(request) -> dict:
    authorization_scope = str(request.authorization_scope or "").strip()
    authorization_basis = str(request.authorization_basis or "").strip()
    data_classification = str(request.data_classification or "").strip()
    if not authorization_scope:
        raise _api_error(422, "DATA_SOURCE_COMPLIANCE_SCOPE_REQUIRED", "Data source compliance requires an authorization scope.")
    if len(authorization_basis) < 8:
        raise _api_error(422, "DATA_SOURCE_COMPLIANCE_BASIS_REQUIRED", "Data source compliance requires an authorization basis before publication.")
    if request.retention_days is None or request.retention_days < 1:
        raise _api_error(422, "DATA_SOURCE_COMPLIANCE_RETENTION_REQUIRED", "Data source compliance requires a positive retention period.")
    if data_classification not in {"public", "internal", "restricted", "sensitive"}:
        raise _api_error(422, "DATA_SOURCE_COMPLIANCE_CLASSIFICATION_REQUIRED", "Data source compliance requires a valid data classification.")
    return {
        "authorization_scope": authorization_scope,
        "authorization_basis": authorization_basis,
        "retention_days": request.retention_days,
        "data_classification": data_classification,
        "pii_policy": request.pii_policy,
        "synthetic_allowed": request.synthetic_allowed,
    }


def _official_api_base_url(policy: dict) -> str | None:
    value = policy.get("base_url")
    if isinstance(value, str) and value:
        return value
    connection = policy.get("connection")
    if isinstance(connection, dict):
        base_url = connection.get("base_url")
        if isinstance(base_url, str) and base_url:
            return base_url
    return None


def _validate_official_api_policy(policy: dict) -> None:
    base_url = _official_api_base_url(policy)
    if not base_url:
        return
    parsed = urlparse(base_url)
    if parsed.scheme == "synthetic":
        return
    if parsed.scheme != "https" or not parsed.netloc:
        raise _api_error(422, "OFFICIAL_API_HTTPS_REQUIRED", "Official API base_url must use https or an explicit synthetic:// adapter.")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("127.") or host.endswith(".local"):
        raise _api_error(422, "URL_HOST_NOT_ALLOWED", "Private or local official API base URLs are not allowed.")


def _official_api_source(session: Session, data_source_id: str) -> models.DataSource:
    source = get_data_source(session, data_source_id)
    if source.source_type != "official_api":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_OFFICIAL_API", "This action is only valid for official_api data sources.")
    return source


def _classify_connection(status_code: int | None, reachable: bool) -> str:
    if status_code in {401}:
        return "auth_failed"
    if status_code in {403}:
        return "forbidden"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and status_code >= 500:
        return "upstream_error"
    if not reachable:
        return "unreachable"
    if status_code is not None and status_code >= 400:
        return "client_error"
    return "ok"


def _compose_test_url(base_url: str | None, sample_path: str | None) -> str:
    if not base_url:
        raise _api_error(422, "OFFICIAL_API_BASE_URL_MISSING", "Official API connection tests require base_url.")
    if not sample_path:
        return base_url
    if sample_path.startswith(("http://", "https://", "synthetic://")):
        return sample_path
    return base_url.rstrip("/") + "/" + sample_path.lstrip("/")


def _rss_feed_url(policy: dict) -> str | None:
    value = policy.get("feed_url") or policy.get("base_url") or policy.get("url")
    return value if isinstance(value, str) and value else None


def _validate_rss_policy(policy: dict) -> None:
    feed_url = _rss_feed_url(policy)
    if not feed_url:
        raise _api_error(422, "RSS_FEED_URL_MISSING", "RSS sources require feed_url.")
    parsed = urlparse(feed_url)
    if parsed.scheme == "synthetic":
        if "not-rss" in parsed.path.lower() or "not-rss" in parsed.netloc.lower():
            raise _api_error(422, "RSS_FEED_INVALID", "RSS feed URL does not point to an RSS or Atom feed.")
        return
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _api_error(422, "URL_SCHEME_NOT_ALLOWED", "RSS feed URLs must use http, https, or an explicit synthetic:// adapter.")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("127.") or host.endswith(".local"):
        raise _api_error(422, "URL_HOST_NOT_ALLOWED", "Private or local RSS URLs are not allowed.")


def _inspect_rss_feed(policy: dict, network: bool) -> dict:
    feed_url = _rss_feed_url(policy)
    _validate_rss_policy(policy)
    assert feed_url is not None
    parsed = urlparse(feed_url)
    started = time.perf_counter()
    if parsed.scheme == "synthetic":
        metadata = _synthetic_rss_metadata(feed_url)
    else:
        if not network:
            return {
                "feed_url": feed_url,
                "title": None,
                "item_count": None,
                "latest_time": None,
                "is_synthetic": False,
                "latency_ms": 0,
                "inspect_mode": "syntax_only",
            }
        try:
            request = UrlRequest(feed_url, method="GET", headers={"User-Agent": "CollectiveEventTwin-RssInspector/1.0"})
            with urlopen(request, timeout=5) as response:
                content_type = response.headers.get("content-type") or ""
                payload = response.read(1_000_000)
        except HTTPError as error:
            raise _api_error(422, f"RSS_HTTP_{error.code}", "RSS feed request returned an HTTP error.") from error
        except URLError as error:
            raise _api_error(422, "RSS_FEED_UNREACHABLE", f"RSS feed is unreachable: {error.reason}") from error
        metadata = _parse_rss_xml(feed_url, payload, content_type)
    if metadata["item_count"] == 0:
        raise _api_error(422, "RSS_FEED_EMPTY", "RSS feed contains no items.")
    metadata["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return metadata


def _rss_fetch_failure(code: str, message: str, feed_url: str | None, retryable: bool, **payload) -> dict:
    return {
        "ok": False,
        "activity_name": RSS_FETCH_ACTIVITY_NAME,
        "classification": payload.pop("classification", "failed"),
        "feed_url": feed_url,
        "item_count": 0,
        "new_record_count": 0,
        "duplicate_count": 0,
        "status_code": payload.pop("status_code", None),
        "latency_ms": payload.pop("latency_ms", 0),
        "is_synthetic": bool(payload.pop("is_synthetic", False)),
        "items": [],
        "error_code": code,
        "error_message": message,
        "retryable": retryable,
        **payload,
    }


def _rss_fetch_success(feed_url: str, title: str | None, items: list[dict], latency_ms: int, is_synthetic: bool, status_code: int | None = 200) -> dict:
    return {
        "ok": True,
        "activity_name": RSS_FETCH_ACTIVITY_NAME,
        "classification": "rss_items",
        "feed_url": feed_url,
        "title": title,
        "item_count": len(items),
        "new_record_count": 0,
        "duplicate_count": 0,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "is_synthetic": is_synthetic,
        "items": items,
        "error_code": None,
        "error_message": None,
        "retryable": False,
    }


def _rss_fetch_activity_payload(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "items"}


def _synthetic_rss_item_count(feed_url: str) -> int:
    parsed = urlparse(feed_url)
    params = parse_qs(parsed.query)
    raw_count = params.get("items", ["3"])[0]
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        count = 3
    return min(max(count, 0), 10_000)


def _synthetic_rss_items(feed_url: str) -> dict:
    started = time.perf_counter()
    lowered = feed_url.lower()
    if "not-rss" in lowered or ("rss" not in lowered and "feed" not in lowered):
        return _rss_fetch_failure("RSS_FEED_INVALID", "Synthetic RSS adapter name must identify an RSS or feed source.", feed_url, retryable=False, classification="invalid", is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "timeout" in lowered:
        return _rss_fetch_failure("RSS_FEED_TIMEOUT", "RSS feed request timed out.", feed_url, retryable=True, classification="timeout", is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "unreachable" in lowered:
        return _rss_fetch_failure("RSS_FEED_UNREACHABLE", "RSS feed is unreachable.", feed_url, retryable=True, classification="unreachable", is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "429" in lowered or "rate-limit" in lowered or "rate_limited" in lowered:
        return _rss_fetch_failure("RSS_FEED_RATE_LIMITED", "RSS feed returned 429 Too Many Requests.", feed_url, retryable=True, classification="rate_limited", status_code=429, is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "500" in lowered or "upstream" in lowered:
        return _rss_fetch_failure("RSS_FEED_UPSTREAM_ERROR", "RSS feed returned an upstream error.", feed_url, retryable=True, classification="upstream_error", status_code=500, is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    if "empty" in lowered:
        return _rss_fetch_failure("RSS_FEED_EMPTY", "RSS feed contains no items.", feed_url, retryable=False, classification="empty", is_synthetic=True, latency_ms=int((time.perf_counter() - started) * 1000))
    count = _synthetic_rss_item_count(feed_url)
    items = []
    base_titles = [
        "Xi'an public notice response cadence",
        "Xi'an community queue guidance",
        "Xi'an transit reroute comments",
    ]
    for index in range(1, count + 1):
        title = base_titles[(index - 1) % len(base_titles)] if count <= 3 else f"Xi'an synthetic RSS item {index:05d}"
        published_at = f"2026-05-09T08:{(30 + index) % 60:02d}:00Z"
        guid = f"xian-rss-{index:05d}"
        link = "https://synthetic.local/xian/rss/shared-link" if "same-link" in lowered else f"https://synthetic.local/xian/rss/{guid}"
        items.append(
            {
                "guid": guid,
                "title": title,
                "link": link,
                "summary": f"synthetic RSS item {index} for Xi'an public issue collection.",
                "published_at": published_at,
                "feed_url": feed_url,
                "source_uri": feed_url,
                "synthetic": True,
            }
        )
    return _rss_fetch_success(feed_url, "Xi'an Social Issues Synthetic RSS", items, int((time.perf_counter() - started) * 1000), True)


def _fetch_rss_items(source: models.DataSource, request) -> dict:
    feed_url = request.source_uri or _rss_feed_url(source.policy or {})
    if not feed_url:
        return _rss_fetch_failure("RSS_FEED_URL_MISSING", "RSS fetch requires source_uri or source feed_url.", feed_url, retryable=False)
    policy = {**(source.policy or {}), "feed_url": feed_url}
    parsed = urlparse(feed_url)
    try:
        _validate_rss_policy(policy)
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        code = str(detail.get("code") or "RSS_FEED_INVALID")
        message = str(detail.get("message") or "RSS feed policy is invalid.")
        return _rss_fetch_failure(code, message, feed_url, retryable=False, classification="invalid", is_synthetic=parsed.scheme == "synthetic")
    if parsed.scheme == "synthetic":
        return _synthetic_rss_items(feed_url)
    started = time.perf_counter()
    try:
        url_request = UrlRequest(feed_url, method="GET", headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml", "User-Agent": "CollectiveEventTwin-RssFetcher/1.0"})
        with urlopen(url_request, timeout=PUBLIC_WEB_FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type") or ""
            payload = response.read(RSS_FETCH_MAX_BYTES)
            title, items = _rss_items_from_xml(feed_url, payload, content_type)
            if not items:
                return _rss_fetch_failure("RSS_FEED_EMPTY", "RSS feed contains no items.", feed_url, retryable=False, classification="empty", status_code=response.status, latency_ms=int((time.perf_counter() - started) * 1000))
            return _rss_fetch_success(feed_url, title, items, int((time.perf_counter() - started) * 1000), False, status_code=response.status)
    except HTTPError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        if error.code == 429:
            return _rss_fetch_failure("RSS_FEED_RATE_LIMITED", "RSS feed returned 429 Too Many Requests.", feed_url, retryable=True, classification="rate_limited", status_code=429, latency_ms=latency_ms)
        if error.code >= 500:
            return _rss_fetch_failure("RSS_FEED_UPSTREAM_ERROR", f"RSS feed returned HTTP {error.code}.", feed_url, retryable=True, classification="upstream_error", status_code=error.code, latency_ms=latency_ms)
        return _rss_fetch_failure(f"RSS_HTTP_{error.code}", "RSS feed request returned an HTTP error.", feed_url, retryable=False, classification="http_error", status_code=error.code, latency_ms=latency_ms)
    except (TimeoutError, socket.timeout):
        return _rss_fetch_failure("RSS_FEED_TIMEOUT", "RSS feed request timed out.", feed_url, retryable=True, classification="timeout", latency_ms=int((time.perf_counter() - started) * 1000))
    except URLError as error:
        return _rss_fetch_failure("RSS_FEED_UNREACHABLE", f"RSS feed is unreachable: {getattr(error, 'reason', error)}", feed_url, retryable=True, classification="unreachable", latency_ms=int((time.perf_counter() - started) * 1000))
    except ElementTree.ParseError:
        return _rss_fetch_failure("RSS_FEED_INVALID", "RSS feed body is not valid XML.", feed_url, retryable=False, classification="invalid", latency_ms=int((time.perf_counter() - started) * 1000))


def _rss_items_from_xml(feed_url: str, payload: bytes, content_type: str) -> tuple[str | None, list[dict]]:
    root = ElementTree.fromstring(payload)
    tag = _strip_xml_namespace(root.tag).lower()
    if tag not in {"rss", "feed"}:
        raise ElementTree.ParseError("RSS feed body is not RSS or Atom.")
    if tag == "rss":
        channel = root.find("channel")
        title = _xml_text(channel, "title") if channel is not None else None
        elements = list(channel.findall("item")) if channel is not None else []
        items = [_rss_item_from_xml(feed_url, element, index, atom=False, content_type=content_type) for index, element in enumerate(elements, start=1)]
        return title, items
    title = _xml_text(root, "title")
    elements = [element for element in root if _strip_xml_namespace(element.tag).lower() == "entry"]
    items = [_rss_item_from_xml(feed_url, element, index, atom=True, content_type=content_type) for index, element in enumerate(elements, start=1)]
    return title, items


def _rss_item_from_xml(feed_url: str, element, index: int, atom: bool, content_type: str) -> dict:
    title = _xml_text(element, "title") or f"RSS item {index}"
    link = _xml_link(element)
    guid = _xml_text(element, "id") if atom else (_xml_text(element, "guid") or link)
    published_at = _xml_text(element, "updated") or _xml_text(element, "published") if atom else (_xml_text(element, "pubDate") or _xml_text(element, "updated"))
    summary = _xml_text(element, "summary") or _xml_text(element, "description") or _xml_text(element, "content") or _xml_text(element, "encoded") or title
    return {
        "guid": guid or _hash(f"{feed_url}:{title}:{published_at or index}"),
        "title": title,
        "link": link,
        "summary": summary,
        "published_at": published_at,
        "feed_url": feed_url,
        "source_uri": link or feed_url,
        "content_type": content_type,
        "synthetic": False,
    }


def _xml_link(element) -> str | None:
    if element is None:
        return None
    for child in list(element):
        if _strip_xml_namespace(child.tag).lower() == "link":
            href = child.attrib.get("href")
            if href:
                return href
            text = child.text.strip() if child.text else ""
            return text or None
    return None


def _rss_item_identity(item: dict) -> dict:
    guid = str(item.get("guid") or "").strip()
    link = str(item.get("link") or "").strip()
    guid_key = f"guid:{guid}" if guid else None
    link_key = f"link:{_hash(link)}" if link else None
    fallback_key = f"content:{_hash(json.dumps(item, sort_keys=True, ensure_ascii=True))}" if not guid_key and not link_key else None
    return {
        "dedupe_key": guid_key or link_key or fallback_key,
        "guid_key": guid_key,
        "link_key": link_key,
        "keys": [key for key in (guid_key, link_key, fallback_key) if key],
    }


def _rss_item_key(item: dict) -> str:
    identity = _rss_item_identity(item)
    return str(identity["dedupe_key"])


def _rss_item_keys(item: dict) -> set[str]:
    return set(_rss_item_identity(item)["keys"])


def _rss_guid_key(guid: str | None) -> str | None:
    value = str(guid or "").strip()
    if value:
        return f"guid:{value}"
    return None


def _rss_link_key(link: str | None) -> str | None:
    value = str(link or "").strip()
    if value:
        return f"link:{_hash(value)}"
    return None


def _existing_rss_item_keys(session: Session, source_id: str) -> set[str]:
    keys: set[str] = set()
    rows = session.execute(select(models.RawRecord.dedupe_key, models.RawRecord.rss_guid_key, models.RawRecord.rss_link_key, models.RawRecord.payload).where(models.RawRecord.data_source_id == source_id, models.RawRecord.source_type == "rss")).all()
    for dedupe_key, rss_guid_key, rss_link_key, payload in rows:
        if dedupe_key:
            keys.add(dedupe_key)
        if rss_guid_key:
            keys.add(rss_guid_key)
        if rss_link_key:
            keys.add(rss_link_key)
        if not isinstance(payload, dict):
            continue
        guid = str(payload.get("guid") or "").strip()
        if guid:
            keys.add(f"guid:{guid}")
        link_hash = str(payload.get("link_hash") or "").strip()
        if link_hash:
            keys.add(f"link:{link_hash}")
    return keys


def _rss_occurred_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _create_rss_raw_record(session: Session, source: models.DataSource, run: models.CollectionRun, import_run: models.ImportRun, item: dict, activity: dict, is_synthetic: bool, identity: dict) -> models.RawRecord:
    title = str(item.get("title") or "RSS item")[:240]
    summary = str(item.get("summary") or title)
    link = str(item.get("link") or item.get("source_uri") or activity.get("feed_url") or "")
    guid = str(item.get("guid") or _hash(f"{activity.get('feed_url')}:{title}:{link}"))
    content = json.dumps({"title": title, "summary": summary, "link": link, "guid": guid, "published_at": item.get("published_at"), "synthetic": is_synthetic}, ensure_ascii=False, sort_keys=True)
    link_hash = _hash(link) if link else None
    dedupe_key = str(identity["dedupe_key"])
    guid_key = identity.get("guid_key") or _rss_guid_key(guid)
    link_key = identity.get("link_key") or _rss_link_key(link)
    record = models.RawRecord(
        id=_id("RAW"),
        tenant_id=source.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        source_type="rss",
        title=title,
        content_hash=_hash(content),
        dedupe_key=dedupe_key,
        rss_guid_key=guid_key,
        rss_link_key=link_key,
        status="collected",
        is_synthetic=is_synthetic,
        city_id="xian",
        occurred_at=_rss_occurred_at(str(item.get("published_at") or "")) or _now(),
        payload={
            "rss_activity": activity,
            "feed_url": activity.get("feed_url"),
            "guid": guid,
            "link": link,
            "link_hash": link_hash,
            "dedupe_key": dedupe_key,
            "rss_guid_key": guid_key,
            "rss_link_key": link_key,
            "published_at": item.get("published_at"),
            "source_uri": item.get("source_uri") or link or activity.get("feed_url"),
            "source_flags": {"synthetic": is_synthetic},
            "synthetic": is_synthetic,
            "import_run_id": import_run.id,
            "collection_run_id": run.id,
        },
    )
    session.add(record)
    session.flush()
    session.add(
        models.RawRecordPayload(
            id=_id("RAWP"),
            raw_record_id=record.id,
            content_text=content,
            masked_text=mask_sensitive_text(content),
            payload={"import_run_id": import_run.id, "synthetic": is_synthetic, "activity_name": RSS_FETCH_ACTIVITY_NAME, "guid": guid, "feed_url": activity.get("feed_url")},
        )
    )
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="data_source", from_object_id=source.id, to_object_type="raw_record", to_object_id=record.id, relation="rss_fetched_from", is_synthetic=is_synthetic, payload={"guid": guid, "feed_url": activity.get("feed_url")}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="import_run", from_object_id=import_run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"activity_name": RSS_FETCH_ACTIVITY_NAME, "guid": guid}))
    session.add(models.LineageEdge(id=_id("LIN"), from_object_type="collection_run", from_object_id=run.id, to_object_type="raw_record", to_object_id=record.id, relation="created", is_synthetic=is_synthetic, payload={"activity_name": RSS_FETCH_ACTIVITY_NAME, "guid": guid}))
    return record


def _synthetic_rss_metadata(feed_url: str) -> dict:
    lowered = feed_url.lower()
    if "empty" in lowered:
        return {
            "feed_url": feed_url,
            "title": "Xi'an Empty Synthetic RSS",
            "item_count": 0,
            "latest_time": None,
            "is_synthetic": True,
            "inspect_mode": "synthetic_adapter",
        }
    if "rss" not in lowered and "feed" not in lowered:
        raise _api_error(422, "RSS_FEED_INVALID", "Synthetic RSS adapter name must identify an RSS or feed source.")
    return {
        "feed_url": feed_url,
        "title": "Xi'an Social Issues Synthetic RSS",
        "item_count": 3,
        "latest_time": "2026-05-09T08:30:00Z",
        "is_synthetic": True,
        "inspect_mode": "synthetic_adapter",
        "sample_items": [
            {"title": "Xi'an public notice response cadence", "published_at": "2026-05-09T08:30:00Z"},
            {"title": "Xi'an community queue guidance", "published_at": "2026-05-09T08:10:00Z"},
            {"title": "Xi'an transit reroute comments", "published_at": "2026-05-09T07:40:00Z"},
        ],
    }


def _parse_rss_xml(feed_url: str, payload: bytes, content_type: str) -> dict:
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise _api_error(422, "RSS_FEED_INVALID", "RSS feed body is not valid XML.") from error
    tag = _strip_xml_namespace(root.tag).lower()
    if tag not in {"rss", "feed"}:
        raise _api_error(422, "RSS_FEED_INVALID", "RSS feed body is not RSS or Atom.")
    if tag == "rss":
        channel = root.find("channel")
        title = _xml_text(channel, "title") if channel is not None else None
        items = list(channel.findall("item")) if channel is not None else []
        latest_time = _latest_time([_xml_text(item, "pubDate") or _xml_text(item, "updated") for item in items])
    else:
        title = _xml_text(root, "title")
        items = [element for element in root if _strip_xml_namespace(element.tag).lower() == "entry"]
        latest_time = _latest_time([_xml_text(item, "updated") or _xml_text(item, "published") for item in items])
    return {
        "feed_url": feed_url,
        "title": title,
        "item_count": len(items),
        "latest_time": latest_time,
        "content_type": content_type,
        "is_synthetic": False,
        "inspect_mode": "http_get",
    }


def _strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_text(element, child_name: str) -> str | None:
    if element is None:
        return None
    for child in list(element):
        if _strip_xml_namespace(child.tag).lower() == child_name.lower():
            text = child.text.strip() if child.text else ""
            return text or None
    return None


def _latest_time(values: list[str | None]) -> str | None:
    parsed: list[datetime] = []
    for value in values:
        if not value:
            continue
        try:
            parsed.append(email.utils.parsedate_to_datetime(value).replace(tzinfo=None))
            continue
        except (TypeError, ValueError):
            pass
        try:
            parsed.append(datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None))
        except ValueError:
            continue
    if not parsed:
        return None
    return max(parsed).isoformat() + "Z"


def _validate_file_upload_policy(policy: dict) -> None:
    allowed_file_types = policy.get("allowed_file_types")
    if not isinstance(allowed_file_types, list) or not allowed_file_types:
        raise _api_error(422, "FILE_UPLOAD_TYPES_REQUIRED", "file_upload sources require allowed_file_types.")
    allowed_extensions = {"csv", "json", "jsonl", "txt", "pdf", "docx", "xlsx"}
    normalized: list[str] = []
    for item in allowed_file_types:
        if not isinstance(item, str):
            raise _api_error(422, "FILE_UPLOAD_TYPE_NOT_ALLOWED", "File type entries must be strings.")
        extension = item.lower().lstrip(".")
        if extension not in allowed_extensions:
            raise _api_error(422, "FILE_UPLOAD_TYPE_NOT_ALLOWED", f"File type {extension} is not allowed.")
        normalized.append(extension)
    schema = policy.get("schema")
    if not isinstance(schema, dict) or not schema:
        raise _api_error(422, "FILE_UPLOAD_SCHEMA_REQUIRED", "file_upload sources require an import schema.")
    max_file_size = policy.get("max_file_size_mb", 50)
    if not isinstance(max_file_size, int) or max_file_size < 1 or max_file_size > 100:
        raise _api_error(422, "FILE_UPLOAD_SIZE_LIMIT_INVALID", "max_file_size_mb must be between 1 and 100.")
    policy["allowed_file_types"] = normalized
    policy["max_file_size_mb"] = max_file_size


def _validate_media_policy(policy: dict) -> None:
    media_types = policy.get("media_types")
    media_kind = str(policy.get("media_kind") or policy.get("channel") or "").strip()
    if not media_kind:
        if isinstance(media_types, list) and "audio" in media_types:
            media_kind = "audio_file"
        elif isinstance(media_types, list) and "video" in media_types:
            media_kind = "video_file"
        elif any(key in policy for key in ("segmentation_policy", "language_policy")):
            media_kind = "audio_file"
        elif any(key in policy for key in ("keyframe_policy", "asr_policy", "large_video_policy")):
            media_kind = "video_file"
        else:
            media_kind = "image_file"

    if media_kind in {"video", "video_file"}:
        _validate_video_media_policy(policy)
        return
    if media_kind in {"audio", "audio_file"}:
        _validate_audio_media_policy(policy)
        return
    if media_kind not in {"image", "image_file", "media"}:
        raise _api_error(422, "MEDIA_KIND_UNSUPPORTED", "Media policy supports image_file and video_file channels.")
    _validate_image_media_policy(policy)


def _validate_image_media_policy(policy: dict) -> None:
    allowed_formats = policy.get("allowed_formats") or ["jpg", "jpeg", "png", "webp"]
    if not isinstance(allowed_formats, list) or not allowed_formats:
        raise _api_error(422, "MEDIA_FORMATS_REQUIRED", "media sources require allowed_formats.")
    allowed_extensions = {"jpg", "jpeg", "png", "webp", "tiff", "heic"}
    normalized: list[str] = []
    for item in allowed_formats:
        if not isinstance(item, str):
            raise _api_error(422, "MEDIA_FORMAT_NOT_ALLOWED", "Media format entries must be strings.")
        extension = item.lower().lstrip(".")
        if extension not in allowed_extensions:
            raise _api_error(422, "MEDIA_FORMAT_NOT_ALLOWED", f"Media format {extension} is not allowed.")
        if extension not in normalized:
            normalized.append(extension)

    ocr_policy = policy.get("ocr_policy") if isinstance(policy.get("ocr_policy"), dict) else {}
    ocr_engine = str(ocr_policy.get("engine") or "synthetic_ocr")
    if ocr_engine not in {"synthetic_ocr", "tesseract", "external_ocr"}:
        raise _api_error(422, "MEDIA_OCR_ENGINE_UNSUPPORTED", "Unsupported image OCR engine.")
    ocr_languages = ocr_policy.get("languages") or ["zh-CN", "en"]
    if not isinstance(ocr_languages, list) or not all(isinstance(item, str) and item in {"zh-CN", "en"} for item in ocr_languages):
        raise _api_error(422, "MEDIA_OCR_LANGUAGES_UNSUPPORTED", "Image OCR languages must be zh-CN and/or en.")

    vlm_policy = policy.get("vlm_policy") if isinstance(policy.get("vlm_policy"), dict) else {}
    vlm_provider = str(vlm_policy.get("provider") or "synthetic_deterministic_caption")
    if vlm_provider not in {"synthetic_deterministic_caption", "external_vlm", "disabled"}:
        raise _api_error(422, "MEDIA_VLM_PROVIDER_UNSUPPORTED", "Unsupported image VLM provider.")
    evidence_mode = str(vlm_policy.get("evidence_mode") or "candidate_only")
    if evidence_mode != "candidate_only":
        raise _api_error(422, "MEDIA_VLM_EVIDENCE_MODE_UNSUPPORTED", "Image VLM outputs must remain candidate_only.")

    redaction_policy = policy.get("redaction_policy") if isinstance(policy.get("redaction_policy"), dict) else {}
    redaction_strategy = str(redaction_policy.get("strategy") or "mask_faces_and_text")
    if redaction_strategy not in {"mask_faces_and_text", "mask_sensitive_text", "blur_faces"}:
        raise _api_error(422, "MEDIA_REDACTION_STRATEGY_UNSUPPORTED", "Unsupported image redaction strategy.")
    minors_policy = str(redaction_policy.get("minors_policy") or "always_mask")
    if minors_policy not in {"always_mask", "review_required"}:
        raise _api_error(422, "MEDIA_REDACTION_MINORS_POLICY_UNSUPPORTED", "Unsupported minors redaction policy.")

    max_file_size = policy.get("max_file_size_mb", 20)
    if not isinstance(max_file_size, int) or max_file_size < 1 or max_file_size > 50:
        raise _api_error(422, "MEDIA_SIZE_LIMIT_INVALID", "max_file_size_mb must be between 1 and 50.")

    redaction_enabled = bool(redaction_policy.get("enabled", True))
    warnings = [item for item in policy.get("warnings", []) if isinstance(item, dict)]
    warnings = [item for item in warnings if item.get("code") != "IMAGE_REDACTION_DISABLED_RISK"]
    if not redaction_enabled:
        warnings.append({"code": "IMAGE_REDACTION_DISABLED_RISK", "severity": "warning", "message": "Image sources without redaction must be treated as elevated privacy risk."})

    policy["media_kind"] = "image_file"
    policy["media_types"] = ["image"]
    policy["allowed_formats"] = normalized
    policy["ocr_policy"] = {"enabled": bool(ocr_policy.get("enabled", True)), "engine": ocr_engine, "languages": ocr_languages, "store_text": bool(ocr_policy.get("store_text", True))}
    policy["vlm_policy"] = {"enabled": bool(vlm_policy.get("enabled", True)), "provider": vlm_provider, "evidence_mode": evidence_mode}
    policy["redaction_policy"] = {"enabled": redaction_enabled, "strategy": redaction_strategy, "minors_policy": minors_policy}
    policy["max_file_size_mb"] = max_file_size
    policy["warnings"] = warnings


def _validate_video_media_policy(policy: dict) -> None:
    allowed_formats = policy.get("allowed_formats") or ["mp4", "mov", "webm"]
    if not isinstance(allowed_formats, list) or not allowed_formats:
        raise _api_error(422, "VIDEO_FORMATS_REQUIRED", "video_file media sources require allowed_formats.")
    allowed_extensions = {"mp4", "mov", "webm", "mkv"}
    normalized: list[str] = []
    for item in allowed_formats:
        if not isinstance(item, str):
            raise _api_error(422, "VIDEO_FORMAT_NOT_ALLOWED", "Video format entries must be strings.")
        extension = item.lower().lstrip(".")
        if extension not in allowed_extensions:
            raise _api_error(422, "VIDEO_FORMAT_NOT_ALLOWED", f"Video format {extension} is not allowed.")
        if extension not in normalized:
            normalized.append(extension)

    keyframe_policy = policy.get("keyframe_policy") if isinstance(policy.get("keyframe_policy"), dict) else {}
    keyframe_strategy = str(keyframe_policy.get("strategy") or "interval_seconds")
    if keyframe_strategy not in {"interval_seconds", "scene_change"}:
        raise _api_error(422, "VIDEO_KEYFRAME_STRATEGY_UNSUPPORTED", "Unsupported video keyframe strategy.")
    interval_seconds = keyframe_policy.get("interval_seconds", 10)
    if not isinstance(interval_seconds, int) or interval_seconds < 1 or interval_seconds > 300:
        raise _api_error(422, "VIDEO_KEYFRAME_INTERVAL_INVALID", "Video keyframe interval must be between 1 and 300 seconds.")
    scene_threshold = keyframe_policy.get("scene_threshold", 0.35)
    if not isinstance(scene_threshold, (int, float)) or scene_threshold < 0 or scene_threshold > 1:
        raise _api_error(422, "VIDEO_SCENE_THRESHOLD_INVALID", "Video scene threshold must be between 0 and 1.")
    max_keyframes = keyframe_policy.get("max_keyframes", 120)
    if not isinstance(max_keyframes, int) or max_keyframes < 1 or max_keyframes > 1000:
        raise _api_error(422, "VIDEO_MAX_KEYFRAMES_INVALID", "Video max_keyframes must be between 1 and 1000.")

    asr_policy = policy.get("asr_policy") if isinstance(policy.get("asr_policy"), dict) else {}
    asr_engine = str(asr_policy.get("engine") or "synthetic_asr")
    if asr_engine not in {"synthetic_asr", "whisper", "external_asr"}:
        raise _api_error(422, "VIDEO_ASR_ENGINE_UNSUPPORTED", "Unsupported video ASR engine.")
    asr_languages = asr_policy.get("languages") or ["zh-CN", "en"]
    if not isinstance(asr_languages, list) or not all(isinstance(item, str) and item in {"zh-CN", "en"} for item in asr_languages):
        raise _api_error(422, "VIDEO_ASR_LANGUAGES_UNSUPPORTED", "Video ASR languages must be zh-CN and/or en.")

    ocr_policy = policy.get("ocr_policy") if isinstance(policy.get("ocr_policy"), dict) else {}
    ocr_engine = str(ocr_policy.get("engine") or "synthetic_ocr")
    if ocr_engine not in {"synthetic_ocr", "tesseract", "external_ocr"}:
        raise _api_error(422, "VIDEO_OCR_ENGINE_UNSUPPORTED", "Unsupported video OCR engine.")
    ocr_languages = ocr_policy.get("languages") or ["zh-CN", "en"]
    if not isinstance(ocr_languages, list) or not all(isinstance(item, str) and item in {"zh-CN", "en"} for item in ocr_languages):
        raise _api_error(422, "VIDEO_OCR_LANGUAGES_UNSUPPORTED", "Video OCR languages must be zh-CN and/or en.")

    vlm_policy = policy.get("vlm_policy") if isinstance(policy.get("vlm_policy"), dict) else {}
    vlm_provider = str(vlm_policy.get("provider") or "synthetic_deterministic_caption")
    if vlm_provider not in {"synthetic_deterministic_caption", "external_vlm", "disabled"}:
        raise _api_error(422, "VIDEO_VLM_PROVIDER_UNSUPPORTED", "Unsupported video VLM provider.")
    evidence_mode = str(vlm_policy.get("evidence_mode") or "candidate_only")
    if evidence_mode != "candidate_only":
        raise _api_error(422, "VIDEO_VLM_EVIDENCE_MODE_UNSUPPORTED", "Video VLM outputs must remain candidate_only.")

    large_video_policy = policy.get("large_video_policy")
    if not isinstance(large_video_policy, dict):
        raise _api_error(422, "VIDEO_LARGE_POLICY_REQUIRED", "video_file sources require large_video_policy before ingesting large or long videos.")
    threshold_mb = large_video_policy.get("threshold_mb", 512)
    if not isinstance(threshold_mb, int) or threshold_mb < 50 or threshold_mb > 2048:
        raise _api_error(422, "VIDEO_LARGE_THRESHOLD_INVALID", "large_video_policy.threshold_mb must be between 50 and 2048.")
    oversize_action = str(large_video_policy.get("oversize_action") or "defer_chunked_processing")
    if oversize_action not in {"reject", "defer_chunked_processing", "require_manual_review"}:
        raise _api_error(422, "VIDEO_LARGE_ACTION_UNSUPPORTED", "Unsupported large-video oversize action.")
    max_duration_seconds = large_video_policy.get("max_duration_seconds", 7200)
    if not isinstance(max_duration_seconds, int) or max_duration_seconds < 1 or max_duration_seconds > 21600:
        raise _api_error(422, "VIDEO_DURATION_LIMIT_INVALID", "large_video_policy.max_duration_seconds must be between 1 and 21600.")

    redaction_policy = policy.get("redaction_policy") if isinstance(policy.get("redaction_policy"), dict) else {}
    redaction_strategy = str(redaction_policy.get("strategy") or "mask_faces_and_text")
    if redaction_strategy not in {"mask_faces_and_text", "mask_sensitive_text", "blur_faces"}:
        raise _api_error(422, "VIDEO_REDACTION_STRATEGY_UNSUPPORTED", "Unsupported video redaction strategy.")
    minors_policy = str(redaction_policy.get("minors_policy") or "always_mask")
    if minors_policy not in {"always_mask", "review_required"}:
        raise _api_error(422, "VIDEO_REDACTION_MINORS_POLICY_UNSUPPORTED", "Unsupported video minors redaction policy.")

    max_file_size = policy.get("max_file_size_mb", 512)
    if not isinstance(max_file_size, int) or max_file_size < 1 or max_file_size > 2048:
        raise _api_error(422, "VIDEO_SIZE_LIMIT_INVALID", "max_file_size_mb must be between 1 and 2048.")

    redaction_enabled = bool(redaction_policy.get("enabled", True))
    warnings = [item for item in policy.get("warnings", []) if isinstance(item, dict)]
    warnings = [item for item in warnings if item.get("code") != "VIDEO_REDACTION_DISABLED_RISK"]
    if not redaction_enabled:
        warnings.append({"code": "VIDEO_REDACTION_DISABLED_RISK", "severity": "warning", "message": "Video sources without redaction must be treated as elevated privacy risk."})

    policy["media_kind"] = "video_file"
    policy["media_types"] = ["video"]
    policy["allowed_formats"] = normalized
    policy["keyframe_policy"] = {"strategy": keyframe_strategy, "interval_seconds": interval_seconds, "scene_threshold": float(scene_threshold), "max_keyframes": max_keyframes}
    policy["asr_policy"] = {"enabled": bool(asr_policy.get("enabled", True)), "engine": asr_engine, "languages": asr_languages, "store_text": bool(asr_policy.get("store_text", True))}
    policy["ocr_policy"] = {"enabled": bool(ocr_policy.get("enabled", True)), "engine": ocr_engine, "languages": ocr_languages, "store_text": bool(ocr_policy.get("store_text", True)), "keyframe_only": bool(ocr_policy.get("keyframe_only", True))}
    policy["vlm_policy"] = {"enabled": bool(vlm_policy.get("enabled", True)), "provider": vlm_provider, "evidence_mode": evidence_mode}
    policy["large_video_policy"] = {"threshold_mb": threshold_mb, "oversize_action": oversize_action, "max_duration_seconds": max_duration_seconds}
    policy["redaction_policy"] = {"enabled": redaction_enabled, "strategy": redaction_strategy, "minors_policy": minors_policy}
    policy["max_file_size_mb"] = max_file_size
    policy["warnings"] = warnings


def _validate_audio_media_policy(policy: dict) -> None:
    allowed_formats = policy.get("allowed_formats") or ["mp3", "wav", "m4a"]
    if not isinstance(allowed_formats, list) or not allowed_formats:
        raise _api_error(422, "AUDIO_FORMATS_REQUIRED", "audio_file media sources require allowed_formats.")
    allowed_extensions = {"mp3", "wav", "m4a", "aac", "flac"}
    normalized: list[str] = []
    for item in allowed_formats:
        if not isinstance(item, str):
            raise _api_error(422, "AUDIO_FORMAT_NOT_ALLOWED", "Audio format entries must be strings.")
        extension = item.lower().lstrip(".")
        if extension not in allowed_extensions:
            raise _api_error(422, "AUDIO_FORMAT_NOT_ALLOWED", f"Audio format {extension} is not allowed.")
        if extension not in normalized:
            normalized.append(extension)

    asr_policy = policy.get("asr_policy") if isinstance(policy.get("asr_policy"), dict) else {}
    asr_engine = str(asr_policy.get("engine") or "synthetic_asr")
    if asr_engine not in {"synthetic_asr", "whisper", "external_asr"}:
        raise _api_error(422, "AUDIO_ASR_ENGINE_UNSUPPORTED", "Unsupported audio ASR engine.")

    segmentation_policy = policy.get("segmentation_policy") if isinstance(policy.get("segmentation_policy"), dict) else {}
    segmentation_mode = str(segmentation_policy.get("mode") or "fixed_window")
    if segmentation_mode not in {"fixed_window", "voice_activity"}:
        raise _api_error(422, "AUDIO_SEGMENTATION_MODE_UNSUPPORTED", "Unsupported audio segmentation mode.")
    segment_seconds = segmentation_policy.get("segment_seconds", 30)
    if not isinstance(segment_seconds, int) or segment_seconds < 5 or segment_seconds > 600:
        raise _api_error(422, "AUDIO_SEGMENT_SECONDS_INVALID", "segmentation_policy.segment_seconds must be between 5 and 600.")
    overlap_seconds = segmentation_policy.get("overlap_seconds", 2)
    if not isinstance(overlap_seconds, int) or overlap_seconds < 0 or overlap_seconds > 30:
        raise _api_error(422, "AUDIO_OVERLAP_SECONDS_INVALID", "segmentation_policy.overlap_seconds must be between 0 and 30.")
    if overlap_seconds >= segment_seconds:
        raise _api_error(422, "AUDIO_OVERLAP_SECONDS_INVALID", "segmentation overlap must be shorter than each segment.")

    language_policy = policy.get("language_policy") if isinstance(policy.get("language_policy"), dict) else {}
    supported_languages = {"zh-CN", "en"}
    primary_language = str(language_policy.get("primary_language") or "zh-CN")
    fallback_language = str(language_policy.get("fallback_language") or "zh-CN")
    allowed_languages = language_policy.get("allowed_languages") or ["zh-CN", "en"]
    if primary_language not in supported_languages or fallback_language not in supported_languages:
        raise _api_error(422, "AUDIO_LANGUAGE_UNSUPPORTED", "Audio language policy supports zh-CN and en only.")
    if not isinstance(allowed_languages, list) or not allowed_languages or not all(isinstance(item, str) and item in supported_languages for item in allowed_languages):
        raise _api_error(422, "AUDIO_LANGUAGE_UNSUPPORTED", "Audio allowed_languages must contain zh-CN and/or en.")
    if primary_language not in allowed_languages:
        raise _api_error(422, "AUDIO_LANGUAGE_UNSUPPORTED", "primary_language must be included in allowed_languages.")

    redaction_policy = policy.get("redaction_policy") if isinstance(policy.get("redaction_policy"), dict) else {}
    redaction_strategy = str(redaction_policy.get("strategy") or "mask_sensitive_text")
    if redaction_strategy != "mask_sensitive_text":
        raise _api_error(422, "AUDIO_REDACTION_STRATEGY_UNSUPPORTED", "Audio redaction uses mask_sensitive_text.")

    max_file_size = policy.get("max_file_size_mb", 100)
    if not isinstance(max_file_size, int) or max_file_size < 1 or max_file_size > 512:
        raise _api_error(422, "AUDIO_SIZE_LIMIT_INVALID", "max_file_size_mb must be between 1 and 512.")

    policy["media_kind"] = "audio_file"
    policy["media_types"] = ["audio"]
    policy["allowed_formats"] = normalized
    policy["asr_policy"] = {"enabled": bool(asr_policy.get("enabled", True)), "engine": asr_engine, "store_text": bool(asr_policy.get("store_text", True))}
    policy["segmentation_policy"] = {"mode": segmentation_mode, "segment_seconds": segment_seconds, "overlap_seconds": overlap_seconds}
    policy["language_policy"] = {"primary_language": primary_language, "allowed_languages": allowed_languages, "fallback_language": fallback_language}
    policy["redaction_policy"] = {"enabled": bool(redaction_policy.get("enabled", True)), "strategy": redaction_strategy}
    policy["max_file_size_mb"] = max_file_size
    policy["warnings"] = [item for item in policy.get("warnings", []) if isinstance(item, dict)]


def _validate_live_segment_policy(policy: dict) -> None:
    stream_url = str(policy.get("stream_url") or "").strip()
    if not stream_url:
        raise _api_error(422, "LIVE_STREAM_URL_REQUIRED", "livestream sources require stream_url.")
    parsed = urlparse(stream_url)
    if parsed.scheme not in {"https", "http", "rtmp", "synthetic"}:
        raise _api_error(422, "LIVE_STREAM_URL_SCHEME_UNSUPPORTED", "Livestream stream_url must use https, http, rtmp, or synthetic.")

    stream_protocol = str(policy.get("stream_protocol") or ("synthetic" if parsed.scheme == "synthetic" else "")).strip()
    if stream_protocol not in {"hls", "dash", "rtmp", "synthetic"}:
        raise _api_error(422, "LIVE_STREAM_PROTOCOL_UNSUPPORTED", "Livestream protocol must be hls, dash, rtmp, or synthetic.")
    if stream_protocol == "rtmp" and parsed.scheme != "rtmp":
        raise _api_error(422, "LIVE_STREAM_PROTOCOL_URL_MISMATCH", "RTMP livestream protocol requires an rtmp:// stream URL.")
    if stream_protocol in {"hls", "dash"} and parsed.scheme not in {"https", "http", "synthetic"}:
        raise _api_error(422, "LIVE_STREAM_PROTOCOL_URL_MISMATCH", "HLS/DASH livestream protocol requires http(s) or synthetic URL.")

    segment_policy = policy.get("segment_policy") if isinstance(policy.get("segment_policy"), dict) else {}
    segment_seconds = segment_policy.get("segment_seconds", 10)
    if not isinstance(segment_seconds, int) or segment_seconds < 2 or segment_seconds > 60:
        raise _api_error(422, "LIVE_SEGMENT_SECONDS_INVALID", "segment_policy.segment_seconds must be between 2 and 60.")
    max_segments = segment_policy.get("max_segments_per_run", 12)
    if not isinstance(max_segments, int) or max_segments < 1 or max_segments > 1000:
        raise _api_error(422, "LIVE_MAX_SEGMENTS_INVALID", "segment_policy.max_segments_per_run must be between 1 and 1000.")
    dedupe_window = segment_policy.get("dedupe_window_seconds", 120)
    if not isinstance(dedupe_window, int) or dedupe_window < 10 or dedupe_window > 3600:
        raise _api_error(422, "LIVE_DEDUPE_WINDOW_INVALID", "segment_policy.dedupe_window_seconds must be between 10 and 3600.")

    buffer_policy = policy.get("buffer_policy") if isinstance(policy.get("buffer_policy"), dict) else {}
    buffer_seconds = buffer_policy.get("buffer_seconds", 60)
    if not isinstance(buffer_seconds, int) or buffer_seconds < 5 or buffer_seconds > 600:
        raise _api_error(422, "LIVE_BUFFER_SECONDS_INVALID", "buffer_policy.buffer_seconds must be between 5 and 600.")
    late_arrival_seconds = buffer_policy.get("late_arrival_seconds", 30)
    if not isinstance(late_arrival_seconds, int) or late_arrival_seconds < 0 or late_arrival_seconds > 600:
        raise _api_error(422, "LIVE_LATE_ARRIVAL_INVALID", "buffer_policy.late_arrival_seconds must be between 0 and 600.")
    gap_strategy = str(buffer_policy.get("gap_strategy") or "mark_gap")
    if gap_strategy not in {"mark_gap", "retry_once", "skip_with_audit"}:
        raise _api_error(422, "LIVE_GAP_STRATEGY_UNSUPPORTED", "Unsupported livestream gap strategy.")

    retention_policy = policy.get("retention_policy")
    if not isinstance(retention_policy, dict):
        raise _api_error(422, "LIVE_RETENTION_POLICY_REQUIRED", "livestream sources require retention_policy.")
    retention_days = retention_policy.get("retention_days")
    if not isinstance(retention_days, int) or retention_days < 1 or retention_days > 30:
        raise _api_error(422, "LIVE_RETENTION_DAYS_INVALID", "retention_policy.retention_days must be between 1 and 30.")
    purge_strategy = str(retention_policy.get("purge_strategy") or "delete_raw_keep_metadata")
    if purge_strategy not in {"delete_raw_keep_metadata", "delete_all_after_review"}:
        raise _api_error(422, "LIVE_PURGE_STRATEGY_UNSUPPORTED", "Unsupported livestream purge strategy.")

    redaction_policy = policy.get("redaction_policy") if isinstance(policy.get("redaction_policy"), dict) else {}
    redaction_strategy = str(redaction_policy.get("strategy") or "mask_faces_and_text")
    if redaction_strategy not in {"mask_faces_and_text", "mask_sensitive_text", "blur_faces"}:
        raise _api_error(422, "LIVE_REDACTION_STRATEGY_UNSUPPORTED", "Unsupported livestream redaction strategy.")

    policy["stream_url"] = stream_url
    policy["stream_protocol"] = stream_protocol
    policy["segment_policy"] = {"segment_seconds": segment_seconds, "max_segments_per_run": max_segments, "dedupe_window_seconds": dedupe_window}
    policy["buffer_policy"] = {"buffer_seconds": buffer_seconds, "late_arrival_seconds": late_arrival_seconds, "gap_strategy": gap_strategy}
    policy["retention_policy"] = {"retention_days": retention_days, "retain_original_segments": bool(retention_policy.get("retain_original_segments", False)), "purge_strategy": purge_strategy}
    policy["redaction_policy"] = {"enabled": bool(redaction_policy.get("enabled", True)), "strategy": redaction_strategy}
    policy["is_synthetic"] = bool(policy.get("is_synthetic", parsed.scheme == "synthetic"))


def _validate_manual_source_policy(policy: dict) -> None:
    schema = policy.get("entry_schema")
    if not isinstance(schema, dict):
        raise _api_error(422, "MANUAL_ENTRY_SCHEMA_REQUIRED", "manual sources require entry_schema.")
    required_fields = schema.get("required_fields")
    if not isinstance(required_fields, list) or not required_fields:
        raise _api_error(422, "MANUAL_ENTRY_REQUIRED_FIELDS_REQUIRED", "manual entry_schema requires required_fields.")
    normalized: list[str] = []
    allowed_fields = {"title", "content", "time", "location"}
    for field in required_fields:
        if not isinstance(field, str) or not field.strip():
            raise _api_error(422, "MANUAL_ENTRY_REQUIRED_FIELD_INVALID", "manual required_fields entries must be non-empty strings.")
        name = _manual_record_field_name(field)
        if name not in allowed_fields:
            raise _api_error(422, "MANUAL_ENTRY_REQUIRED_FIELD_INVALID", f"manual required field {name} is not allowed.")
        if name not in normalized:
            normalized.append(name)
    city_id = schema.get("city_id") or "xian"
    if not isinstance(city_id, str) or not city_id.strip():
        raise _api_error(422, "MANUAL_ENTRY_CITY_INVALID", "manual entry_schema city_id must be a non-empty string.")
    policy["entry_schema"] = {**schema, "required_fields": normalized, "city_id": city_id.strip()}


def _manual_record_field_name(field: str) -> str:
    name = str(field).strip().lower()
    aliases = {
        "occurred_at": "time",
        "published_at": "time",
        "timestamp": "time",
        "city_id": "location",
        "district": "location",
        "address": "location",
    }
    return aliases.get(name, name)


def validate_manual_record(policy: dict, request) -> dict:
    schema = policy.get("entry_schema")
    if not isinstance(schema, dict):
        raise _api_error(
            422,
            "MANUAL_RECORD_SCHEMA_INVALID",
            "Manual data source entry_schema is missing.",
            {"missing_fields": ["entry_schema"], "policy_error": "entry_schema_required"},
        )
    required_fields = schema.get("required_fields")
    if not isinstance(required_fields, list) or not required_fields:
        raise _api_error(
            422,
            "MANUAL_RECORD_SCHEMA_INVALID",
            "Manual data source entry_schema.required_fields is missing.",
            {"missing_fields": ["entry_schema.required_fields"], "policy_error": "required_fields_required"},
        )
    required = []
    for field in required_fields:
        name = _manual_record_field_name(str(field))
        if name not in required:
            required.append(name)
    payload = request.payload if isinstance(request.payload, dict) else {}
    title = _manual_record_text(request.title or payload.get("title"))
    content = _manual_record_text(request.content or payload.get("content"))
    time_text, occurred_at = _manual_record_time(request, payload)
    location = _manual_record_location(request, payload, schema)
    values = {
        "title": title,
        "content": content,
        "time": time_text,
        "location": location,
    }
    missing = [field for field in required if not values.get(field)]
    invalid_fields = ["time"] if time_text and occurred_at is None else []
    status = "valid" if not missing and not invalid_fields else "invalid"
    return {
        "validator": MANUAL_RECORD_VALIDATOR_NAME,
        "status": status,
        "required_fields": required,
        "missing_fields": missing,
        "invalid_fields": invalid_fields,
        "field_errors": {field: "required" for field in missing} | {field: "invalid" for field in invalid_fields},
        "fields": {
            "title": title,
            "content": content,
            "time": time_text,
            "location": location,
            "city_id": request.city_id or payload.get("city_id") or schema.get("city_id") or "xian",
        },
        "occurred_at": _manual_record_datetime_iso(occurred_at),
        "location": location,
    }


def _validate_manual_record_payload(policy: dict, request) -> None:
    validation = validate_manual_record(policy, request)
    if validation["status"] != "valid":
        fields = validation.get("missing_fields") or validation.get("invalid_fields") or []
        suffix = f": {', '.join(fields)}" if fields else "."
        raise _api_error(422, "MANUAL_RECORD_SCHEMA_INVALID", f"Manual record schema validation failed{suffix}", validation)


def _manual_record_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _manual_record_time(request, payload: dict) -> tuple[str | None, datetime | None]:
    if request.occurred_at is not None:
        return _manual_record_datetime_iso(request.occurred_at), request.occurred_at if request.occurred_at.tzinfo is not None else request.occurred_at.replace(tzinfo=timezone.utc)
    for key in ("occurred_at", "time", "published_at", "timestamp"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        parsed = _rss_occurred_at(text)
        return text, parsed
    return None, None


def _manual_record_occurred_datetime(request) -> datetime | None:
    payload = request.payload if isinstance(request.payload, dict) else {}
    return _manual_record_time(request, payload)[1]


def _manual_record_datetime_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _manual_record_location(request, payload: dict, schema: dict) -> str | None:
    request_city_id = request.city_id if "city_id" in getattr(request, "model_fields_set", set()) else None
    for value in (getattr(request, "location", None), payload.get("location"), payload.get("address"), payload.get("district"), request_city_id, payload.get("city_id")):
        text = _manual_record_text(value)
        if text:
            return text
    return None


def _safe_file_name(file_name: str | None) -> str:
    raw = (file_name or "upload.bin").replace("\\", "/").split("/")[-1].strip()
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw)[:240].strip(" .")
    return safe or "upload.bin"


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", 1)[-1].lower()


def _normalize_upload_mime_type(extension: str, mime_type: str | None) -> str:
    candidate = (mime_type or "").split(";", 1)[0].strip().lower()
    if candidate and candidate != "application/octet-stream":
        return candidate
    return FILE_UPLOAD_MIME_TYPES.get(extension, "application/octet-stream")


def _scan_file_upload(content: bytes) -> dict:
    for signature in FILE_UPLOAD_VIRUS_SIGNATURES:
        if signature in content:
            return {
                "status": "failed",
                "engine": "local_signature_scan_v1",
                "signature": signature.decode("ascii", errors="replace"),
                "checked_bytes": len(content),
            }
    return {"status": "passed", "engine": "local_signature_scan_v1", "checked_bytes": len(content)}


def _write_upload_object(storage_key: str, content: bytes) -> str:
    base_path = Path(settings.object_store_path)
    target = base_path.joinpath(*storage_key.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return str(target)


def _read_upload_object(file_object: models.FileObject) -> bytes:
    payload = file_object.payload or {}
    object_store_uri = payload.get("object_store_uri")
    if not isinstance(object_store_uri, str) or not object_store_uri:
        raise _api_error(409, "FILE_OBJECT_STORAGE_URI_MISSING", "File object does not contain an object-store URI.")
    object_path = Path(object_store_uri)
    if not object_path.exists():
        raise _api_error(409, "FILE_OBJECT_STORAGE_MISSING", "File object bytes are missing from object storage.")
    return object_path.read_bytes()


def _file_object_text(file_object: models.FileObject, content: bytes) -> str:
    extension = _file_extension(file_object.file_name)
    if extension in {"csv", "json", "jsonl", "txt"} or file_object.mime_type.startswith("text/") or file_object.mime_type == "application/json":
        return content.decode("utf-8", errors="replace")
    return (
        f"Binary file object {file_object.file_name} stored at {file_object.storage_key}; "
        f"mime_type={file_object.mime_type}; byte_size={file_object.byte_size}; checksum={file_object.checksum}."
    )


def _reject_file_upload(
    session: Session,
    source: models.DataSource,
    actor: models.User,
    trace_id: str,
    code: str,
    message: str,
    file_name: str | None,
    status_code: int,
    details: dict | None = None,
) -> None:
    rejection = {
        "data_source_id": source.id,
        "file_name": _safe_file_name(file_name),
        "error_code": code,
        "message": message,
        "recoverable": bool((details or {}).get("recoverable") or code in {"FILE_UPLOAD_TOO_LARGE"}),
        "details": details or {},
    }
    session.add(
        models.OpsErrorQueue(
            id=_id("ERRQ"),
            source="file_upload",
            severity="warning",
            status="open",
            message=message,
            payload=rejection,
        )
    )
    _update_health(session, source.id, None, success=False, error_code=code)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="file_upload.rejected",
        object_type="data_source",
        object_id=source.id,
        after=rejection,
        trace_id=trace_id,
    )
    session.commit()
    raise _api_error(status_code, code, message, rejection)


def _validate_db_import_policy(policy: dict) -> None:
    for key in ("password", "plain_password", "connection_string", "dsn"):
        if key in policy:
            raise _api_error(422, "DB_IMPORT_PLAINTEXT_SECRET_NOT_ALLOWED", "db_import sources must store credentials only as secret_ref.")
    connection_ref = policy.get("connection_ref")
    if not isinstance(connection_ref, str) or not connection_ref:
        raise _api_error(422, "DB_IMPORT_CONNECTION_REF_REQUIRED", "db_import sources require connection_ref.")
    secret_ref = policy.get("secret_ref")
    if not isinstance(secret_ref, str) or not secret_ref:
        raise _api_error(422, "DB_IMPORT_SECRET_REF_REQUIRED", "db_import sources require secret_ref.")
    engine = policy.get("engine", "postgresql")
    if engine not in {"postgresql", "mysql", "sqlite", "mssql"}:
        raise _api_error(422, "DB_IMPORT_ENGINE_UNSUPPORTED", "Unsupported db_import engine.")
    policy["engine"] = engine


def _validate_object_storage_policy(policy: dict) -> None:
    for key in ("access_key", "secret_key", "access_token", "token", "password"):
        if key in policy:
            raise _api_error(422, "OBJECT_STORAGE_PLAINTEXT_SECRET_NOT_ALLOWED", "object_storage sources must store credentials only as secret_ref.")
    bucket = policy.get("bucket")
    if not isinstance(bucket, str) or not bucket:
        raise _api_error(422, "OBJECT_STORAGE_BUCKET_REQUIRED", "object_storage sources require bucket.")
    secret_ref = policy.get("secret_ref")
    if not isinstance(secret_ref, str) or not secret_ref:
        raise _api_error(422, "OBJECT_STORAGE_SECRET_REF_REQUIRED", "object_storage sources require secret_ref.")
    prefix = policy.get("prefix", "")
    if not isinstance(prefix, str):
        raise _api_error(422, "OBJECT_STORAGE_PREFIX_INVALID", "object_storage prefix must be a string.")
    policy["prefix"] = prefix


def _synthetic_db_connection_result(policy: dict, request) -> dict:
    connection_ref = str(policy.get("connection_ref") or "")
    return {
        "status": "ok",
        "classification": "ok",
        "status_code": request.expected_status,
        "latency_ms": 1,
        "is_synthetic": bool(policy.get("is_synthetic") or connection_ref.startswith("synthetic://")),
        "sample_metadata": {
            "connection_ref": connection_ref,
            "engine": policy.get("engine"),
            "sample_path": request.sample_path,
            "row_count": 100,
            "adapter": "synthetic_db_import",
        },
    }


def _create_object_storage_scan_ledgers(session: Session, source: models.DataSource, request, actor: models.User, trace_id: str) -> tuple[models.CollectionJob, models.CollectionRun, models.ImportRun, models.WorkflowRun]:
    _ensure_collection_workflow_case(session)
    scan_prefix = request.prefix if request.prefix is not None else str((source.policy or {}).get("prefix") or "")
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"ScanObjectStoragePrefixWorkflow-{run_id}"
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        created_by_id=actor.id,
        name=f"object storage scan {scan_prefix or '/'}",
        status="active" if source.status == "active" else "blocked",
        schedule=None,
        payload={"job_kind": "object_storage_scan", "prefix": scan_prefix, "limit": request.limit},
    )
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="running",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload={
            "import_type": "object_storage",
            "workflow_run_id": workflow_run_id,
            "workflow_name": "ScanObjectStoragePrefixWorkflow",
            "workflow_id": workflow_id,
            "workflow_status": "running",
            "prefix": scan_prefix,
            "started_by": actor.id,
        },
    )
    workflow = models.WorkflowRun(
        id=workflow_run_id,
        case_id=COLLECTION_WORKFLOW_CASE_ID,
        tenant_id=actor.tenant_id,
        workflow_name="ScanObjectStoragePrefixWorkflow",
        workflow_id=workflow_id,
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload={
            "collection_job_id": job.id,
            "collection_run_id": run.id,
            "data_source_id": source.id,
            "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME,
            "input_hash": _hash(json.dumps({"source_id": source.id, "prefix": scan_prefix, "limit": request.limit, "payload": request.payload}, sort_keys=True, ensure_ascii=True)),
        },
    )
    import_run = models.ImportRun(
        id=_id("IMPR"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        import_type="object_storage",
        status="running",
        is_synthetic=bool(source.is_synthetic),
        trace_id=trace_id,
        payload={"prefix": scan_prefix, "payload": request.payload},
    )
    session.add(job)
    session.flush()
    session.add(run)
    session.add(workflow)
    session.add(import_run)
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="scheduled", status="pending", payload={"collection_run_id": run.id, "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "step_key": "fetch"}, created_at=_now()))
    session.flush()
    return job, run, import_run, workflow


def _fail_object_storage_scan(
    session: Session,
    source: models.DataSource,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    workflow: models.WorkflowRun,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    activity = {
        "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME,
        "classification": code,
        "key_count": 0,
        "new_record_count": 0,
        "raw_record_count": 0,
        "file_object_count": 0,
        "missing_count": 0,
        "is_synthetic": bool(source.is_synthetic),
        "error_code": code,
        "error_message": message,
        "retryable": retryable,
    }
    _fail_import(session, run, import_run, source, code, message, retryable=retryable)
    run.payload = {**(run.payload or {}), "workflow_status": "failed", "object_storage_activity": activity}
    import_run.payload = {**(import_run.payload or {}), "object_storage_activity": activity}
    workflow.status = "failed"
    workflow.payload = {**(workflow.payload or {}), "status": "failed", "object_storage_activity": activity, "error_code": code}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_object_storage_prefix_failed", status="failed", payload=activity | {"step_key": "fetch"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload=activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))


def _object_storage_scan_keys(policy: dict, prefix: str, limit: int) -> list[str]:
    configured = policy.get("object_keys")
    if isinstance(configured, list):
        keys = [str(key) for key in configured if isinstance(key, str) and (not prefix or str(key).startswith(prefix))]
        return keys[:limit]
    normalized_prefix = prefix.rstrip("/")
    return [f"{normalized_prefix}/synthetic-object-{index:04d}.json".lstrip("/") for index in range(limit)]


def _object_storage_missing_keys(policy: dict, keys: list[str]) -> list[str]:
    configured = policy.get("missing_keys")
    missing = {str(key) for key in configured if isinstance(key, str)} if isinstance(configured, list) else set()
    every = int(policy.get("missing_key_every") or 0)
    for index, key in enumerate(keys, start=1):
        if every > 0 and index % every == 0:
            missing.add(key)
    return [key for key in keys if key in missing]


def _object_storage_dedupe_key(source_id: str, bucket: str, key: str) -> str:
    return f"object-storage:{source_id}:{bucket}:{key}"[:240]


def _existing_object_storage_dedupe_keys(session: Session, source_id: str, bucket: str, keys: list[str]) -> set[str]:
    dedupe_keys = [_object_storage_dedupe_key(source_id, bucket, key) for key in keys]
    existing: set[str] = set()
    for index in range(0, len(dedupe_keys), 500):
        chunk = dedupe_keys[index : index + 500]
        if not chunk:
            continue
        rows = session.execute(
            select(models.RawRecord.dedupe_key).where(
                models.RawRecord.data_source_id == source_id,
                models.RawRecord.source_type == "object_storage",
                models.RawRecord.dedupe_key.in_(chunk),
            )
        )
        existing.update(str(row[0]) for row in rows if row[0])
    return existing


def _bulk_insert_object_storage_records(
    session: Session,
    source: models.DataSource,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    request,
    policy: dict,
    scan_prefix: str,
    keys: list[str],
    is_synthetic: bool,
) -> dict:
    response_records: list[dict] = []
    response_files: list[dict] = []
    file_rows: list[dict] = []
    raw_rows: list[dict] = []
    payload_rows: list[dict] = []
    lineage_rows: list[dict] = []
    now = datetime.utcnow()
    bucket = str(policy["bucket"])
    for index, key in enumerate(keys, start=1):
        file_id = _id("FILE")
        raw_id = _id("RAW")
        file_name = Path(key).name or f"object-{index}.json"
        content = _synthetic_object_storage_content(bucket, key, request.city_id or "xian", is_synthetic)
        content_bytes = content.encode("utf-8")
        checksum = _hash_bytes(content_bytes)
        file_payload = {
            "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME,
            "storage_mode": "external_object_storage_reference",
            "bucket": bucket,
            "key": key,
            "prefix": scan_prefix,
            "object_uri": f"object-storage://{bucket}/{key}",
            "content_hash": checksum,
            "scan_status": "referenced",
            "source_flags": {"synthetic": is_synthetic, "import_type": "object_storage"},
            "payload": request.payload,
        }
        file_row = {
            "id": file_id,
            "tenant_id": source.tenant_id,
            "owner_user_id": None,
            "object_type": "data_source",
            "object_id": source.id,
            "storage_key": key,
            "file_name": file_name,
            "mime_type": "application/json",
            "byte_size": len(content_bytes),
            "checksum": checksum,
            "status": "stored",
            "version": 1,
            "access_policy": {"scope": "tenant", "tenant_id": source.tenant_id, "synthetic": is_synthetic, "bucket": bucket},
            "source_refs": [{"object_type": "data_source", "object_id": source.id}, {"object_type": "object_storage_key", "object_id": key}],
            "payload": file_payload,
        }
        raw_payload = {
            "import_type": "object_storage",
            "object_storage_activity": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "bucket": bucket, "prefix": scan_prefix},
            "file_object_ref": {"file_object_id": file_id, "storage_key": key, "bucket": bucket, "checksum": checksum},
            "external_id": key,
            "bucket": bucket,
            "key": key,
            "content_type": "application/json",
            "synthetic": is_synthetic,
            "source_flags": {"synthetic": is_synthetic, "import_type": "object_storage"},
            "payload": request.payload,
        }
        raw_row = {
            "id": raw_id,
            "tenant_id": source.tenant_id,
            "data_source_id": source.id,
            "collection_run_id": run.id,
            "source_type": "object_storage",
            "title": f"Object storage file {file_name}"[:240],
            "content_hash": checksum,
            "dedupe_key": _object_storage_dedupe_key(source.id, bucket, key),
            "status": "collected",
            "is_synthetic": is_synthetic,
            "city_id": request.city_id or "xian",
            "occurred_at": now,
            "payload": raw_payload,
        }
        file_rows.append(file_row)
        raw_rows.append(raw_row)
        payload_rows.append(
            {
                "id": _id("RAWP"),
                "raw_record_id": raw_id,
                "content_text": content,
                "masked_text": mask_sensitive_text(content),
                "payload": {"import_run_id": import_run.id, "synthetic": is_synthetic, "activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "file_object_id": file_id, "bucket": bucket, "key": key},
            }
        )
        lineage_rows.extend(
            [
                {"id": _id("LIN"), "from_object_type": "data_source", "from_object_id": source.id, "to_object_type": "file_object", "to_object_id": file_id, "relation": "object_storage_scanned_from", "is_synthetic": is_synthetic, "payload": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "bucket": bucket, "key": key}},
                {"id": _id("LIN"), "from_object_type": "file_object", "from_object_id": file_id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "object_storage_file_as_raw_record", "is_synthetic": is_synthetic, "payload": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "bucket": bucket, "key": key}},
                {"id": _id("LIN"), "from_object_type": "data_source", "from_object_id": source.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "object_storage_scanned_from", "is_synthetic": is_synthetic, "payload": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "bucket": bucket, "key": key}},
                {"id": _id("LIN"), "from_object_type": "import_run", "from_object_id": import_run.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "created", "is_synthetic": is_synthetic, "payload": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "file_object_id": file_id}},
                {"id": _id("LIN"), "from_object_type": "collection_run", "from_object_id": run.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "created", "is_synthetic": is_synthetic, "payload": {"activity_name": OBJECT_STORAGE_SCAN_ACTIVITY_NAME, "file_object_id": file_id}},
            ]
        )
        if len(response_records) < request.response_limit:
            response_records.append(_serialize_bulk_raw_record(raw_row))
            response_files.append(_serialize_bulk_file_object(file_row))
        if len(raw_rows) >= 5000:
            _flush_object_storage_record_batch(session, file_rows, raw_rows, payload_rows, lineage_rows)
            file_rows, raw_rows, payload_rows, lineage_rows = [], [], [], []
    if raw_rows:
        _flush_object_storage_record_batch(session, file_rows, raw_rows, payload_rows, lineage_rows)
    return {"raw_records": response_records, "file_objects": response_files}


def _flush_object_storage_record_batch(session: Session, file_rows: list[dict], raw_rows: list[dict], payload_rows: list[dict], lineage_rows: list[dict]) -> None:
    if file_rows:
        session.execute(models.FileObject.__table__.insert(), file_rows)
    if raw_rows:
        session.execute(models.RawRecord.__table__.insert(), raw_rows)
    if payload_rows:
        session.execute(models.RawRecordPayload.__table__.insert(), payload_rows)
    if lineage_rows:
        session.execute(models.LineageEdge.__table__.insert(), lineage_rows)


def _synthetic_object_storage_content(bucket: str, key: str, city_id: str, is_synthetic: bool) -> str:
    return json.dumps(
        {
            "bucket": bucket,
            "key": key,
            "city_id": city_id,
            "title": f"Xi'an object storage evidence {Path(key).name}",
            "content": f"synthetic object storage file {key}: Xi'an public service evidence with contact 13800138000.",
            "synthetic": is_synthetic,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _serialize_bulk_file_object(row: dict) -> dict:
    return {
        "file_object_id": row["id"],
        "tenant_id": row["tenant_id"],
        "case_id": row.get("case_id"),
        "owner_user_id": row.get("owner_user_id"),
        "task_id": row.get("task_id"),
        "review_id": row.get("review_id"),
        "media_asset_id": row.get("media_asset_id"),
        "object_type": row.get("object_type"),
        "object_id": row.get("object_id"),
        "storage_key": row["storage_key"],
        "file_name": row["file_name"],
        "mime_type": row["mime_type"],
        "byte_size": row["byte_size"],
        "checksum": row.get("checksum"),
        "status": row["status"],
        "version": row.get("version") or 1,
        "access_policy": row["access_policy"],
        "source_refs": row["source_refs"],
        "review_gate_record_id": row.get("review_gate_record_id"),
        "payload": row["payload"],
        "created_at": None,
        "updated_at": None,
    }


def _create_db_import_scan_ledgers(session: Session, source: models.DataSource, request, actor: models.User, trace_id: str) -> tuple[models.CollectionJob, models.CollectionRun, models.ImportRun, models.WorkflowRun]:
    _ensure_collection_workflow_case(session)
    table_key = _db_import_table_key(request)
    run_id = _id("CRUN")
    workflow_run_id = _id("WFR")
    workflow_id = f"DbImportScanWorkflow-{run_id}"
    job = models.CollectionJob(
        id=_id("CJOB"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        created_by_id=actor.id,
        name=f"db import scan {table_key}",
        status="active" if source.status == "active" else "blocked",
        schedule=None,
        payload={"job_kind": "db_import_scan", "table_name": request.table_name, "schema_name": request.schema_name, "cursor_field": request.cursor_field},
    )
    run = models.CollectionRun(
        id=run_id,
        collection_job_id=job.id,
        data_source_id=source.id,
        status="running",
        record_count=0,
        created_at=_now(),
        trace_id=trace_id,
        payload={
            "import_type": "db_import",
            "workflow_run_id": workflow_run_id,
            "workflow_name": "DbImportScanWorkflow",
            "workflow_id": workflow_id,
            "workflow_status": "running",
            "table_name": request.table_name,
            "schema_name": request.schema_name,
            "cursor_field": request.cursor_field,
            "started_by": actor.id,
        },
    )
    workflow = models.WorkflowRun(
        id=workflow_run_id,
        case_id=COLLECTION_WORKFLOW_CASE_ID,
        tenant_id=actor.tenant_id,
        workflow_name="DbImportScanWorkflow",
        workflow_id=workflow_id,
        status="running",
        started_by=actor.id,
        trace_id=trace_id,
        payload={
            "collection_job_id": job.id,
            "collection_run_id": run.id,
            "data_source_id": source.id,
            "activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME,
            "input_hash": _hash(
                json.dumps(
                    {
                        "source_id": source.id,
                        "table_name": request.table_name,
                        "schema_name": request.schema_name,
                        "cursor_field": request.cursor_field,
                        "cursor_value": request.cursor_value,
                        "limit": request.limit,
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                )
            ),
        },
    )
    import_run = models.ImportRun(
        id=_id("IMPR"),
        tenant_id=actor.tenant_id,
        data_source_id=source.id,
        collection_run_id=run.id,
        import_type="db_import",
        status="running",
        is_synthetic=bool(source.is_synthetic),
        trace_id=trace_id,
        payload={"table_name": request.table_name, "schema_name": request.schema_name, "cursor_field": request.cursor_field, "payload": request.payload},
    )
    session.add(job)
    session.flush()
    session.add(run)
    session.add(workflow)
    session.add(import_run)
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="scheduled", status="pending", payload={"collection_run_id": run.id, "activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME, "step_key": "fetch"}, created_at=_now()))
    session.flush()
    return job, run, import_run, workflow


def _fail_db_import_scan(
    session: Session,
    source: models.DataSource,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    workflow: models.WorkflowRun,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    activity = {
        "activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME,
        "classification": code,
        "row_count": 0,
        "raw_record_count": 0,
        "is_synthetic": bool(source.is_synthetic),
        "error_code": code,
        "error_message": message,
        "retryable": retryable,
    }
    _fail_import(session, run, import_run, source, code, message, retryable=retryable)
    run.payload = {**(run.payload or {}), "workflow_status": "failed", "db_import_activity": activity}
    import_run.payload = {**(import_run.payload or {}), "db_import_activity": activity}
    workflow.status = "failed"
    workflow.payload = {**(workflow.payload or {}), "status": "failed", "db_import_activity": activity, "error_code": code}
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="scan_db_import_table_failed", status="failed", payload=activity | {"step_key": "fetch"}, created_at=_now()))
    session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_failed", status="failed", payload=activity | {"collection_run_id": run.id, "step_key": "fetch"}, created_at=_now()))


def _db_import_table_key(request) -> str:
    return f"{request.schema_name}.{request.table_name}" if request.schema_name else request.table_name


def _db_import_start_cursor(policy: dict, table_key: str, request) -> int:
    if request.cursor_value is not None:
        return int(request.cursor_value)
    cursor_state = policy.get("db_import_cursor") if isinstance(policy.get("db_import_cursor"), dict) else {}
    table_state = cursor_state.get(table_key) if isinstance(cursor_state.get(table_key), dict) else {}
    return int(table_state.get(request.cursor_field) or 0)


def _update_db_import_cursor(policy: dict, table_key: str, cursor_field: str, next_cursor: int, activity: dict) -> None:
    cursor_state = dict(policy.get("db_import_cursor") or {}) if isinstance(policy.get("db_import_cursor"), dict) else {}
    table_state = dict(cursor_state.get(table_key) or {}) if isinstance(cursor_state.get(table_key), dict) else {}
    table_state[cursor_field] = next_cursor
    cursor_state[table_key] = table_state
    policy["db_import_cursor"] = cursor_state
    policy["last_db_import_scan"] = {
        "activity_name": activity["activity_name"],
        "table_name": activity["table_name"],
        "schema_name": activity["schema_name"],
        "table_key": table_key,
        "cursor_field": activity["cursor_field"],
        "start_cursor": activity["start_cursor"],
        "next_cursor": activity["next_cursor"],
        "row_count": activity["row_count"],
        "latency_ms": activity["latency_ms"],
        "is_synthetic": activity["is_synthetic"],
        "collection_job_id": activity.get("collection_job_id"),
        "collection_run_id": activity.get("collection_run_id"),
        "import_run_id": activity.get("import_run_id"),
        "workflow_run_id": activity.get("workflow_run_id"),
    }


def _bulk_insert_db_import_records(session: Session, source: models.DataSource, run: models.CollectionRun, import_run: models.ImportRun, request, start_cursor: int, is_synthetic: bool) -> list[dict]:
    response_records: list[dict] = []
    batch_size = 5000
    raw_rows: list[dict] = []
    payload_rows: list[dict] = []
    lineage_rows: list[dict] = []
    now = datetime.utcnow()
    table_key = _db_import_table_key(request)
    for index in range(1, request.limit + 1):
        cursor_value = start_cursor + index
        row = _synthetic_db_import_row(request, table_key, cursor_value)
        raw_id = _id("RAW")
        row_content = json.dumps({"table": table_key, "row": row}, ensure_ascii=False, sort_keys=True)
        row_hash = _hash(row_content)
        record_payload = {
            "import_type": "db_import",
            "db_import_activity": {"activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME, "table_name": request.table_name, "schema_name": request.schema_name},
            "table_name": request.table_name,
            "schema_name": request.schema_name,
            "cursor_field": request.cursor_field,
            "cursor_value": cursor_value,
            "external_id": row["external_id"],
            "content_type": "application/json",
            "synthetic": is_synthetic,
            "source_flags": {"synthetic": is_synthetic, "import_type": "db_import"},
            "request_payload": request.payload,
            "row": row,
        }
        raw_row = {
            "id": raw_id,
            "tenant_id": source.tenant_id,
            "data_source_id": source.id,
            "collection_run_id": run.id,
            "source_type": "db_import",
            "title": str(row.get("title") or f"{table_key} row {cursor_value}")[:240],
            "content_hash": row_hash,
            "dedupe_key": f"db-import:{source.id}:{table_key}:{request.cursor_field}:{cursor_value}"[:240],
            "status": "collected",
            "is_synthetic": is_synthetic,
            "city_id": str(row.get("city_id") or request.city_id or "xian"),
            "occurred_at": now,
            "payload": record_payload,
        }
        raw_rows.append(raw_row)
        payload_rows.append(
            {
                "id": _id("RAWP"),
                "raw_record_id": raw_id,
                "content_text": row_content,
                "masked_text": mask_sensitive_text(row_content),
                "payload": {"import_run_id": import_run.id, "synthetic": is_synthetic, "activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME, "cursor_value": cursor_value, "external_id": row["external_id"]},
            }
        )
        lineage_rows.extend(
            [
                {"id": _id("LIN"), "from_object_type": "data_source", "from_object_id": source.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "db_import_scanned_from", "is_synthetic": is_synthetic, "payload": {"activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME, "table_name": request.table_name, "cursor_value": cursor_value}},
                {"id": _id("LIN"), "from_object_type": "import_run", "from_object_id": import_run.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "created", "is_synthetic": is_synthetic, "payload": {"activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME}},
                {"id": _id("LIN"), "from_object_type": "collection_run", "from_object_id": run.id, "to_object_type": "raw_record", "to_object_id": raw_id, "relation": "created", "is_synthetic": is_synthetic, "payload": {"activity_name": DB_IMPORT_SCAN_ACTIVITY_NAME}},
            ]
        )
        if len(response_records) < request.response_limit:
            response_records.append(_serialize_bulk_raw_record(raw_row))
        if len(raw_rows) >= batch_size:
            _flush_db_import_record_batch(session, raw_rows, payload_rows, lineage_rows)
            raw_rows, payload_rows, lineage_rows = [], [], []
    if raw_rows:
        _flush_db_import_record_batch(session, raw_rows, payload_rows, lineage_rows)
    return response_records


def _flush_db_import_record_batch(session: Session, raw_rows: list[dict], payload_rows: list[dict], lineage_rows: list[dict]) -> None:
    session.execute(models.RawRecord.__table__.insert(), raw_rows)
    session.execute(models.RawRecordPayload.__table__.insert(), payload_rows)
    session.execute(models.LineageEdge.__table__.insert(), lineage_rows)


def _synthetic_db_import_row(request, table_key: str, cursor_value: int) -> dict:
    return {
        "id": cursor_value,
        "external_id": f"{table_key}:{cursor_value}",
        "title": f"Xi'an public service DB row {cursor_value}",
        "content": f"synthetic db import row {cursor_value} from {table_key}: Xi'an pension insurance queue update with contact 13800138000.",
        "city_id": request.city_id or "xian",
        "district": "beilin" if cursor_value % 2 else "yanta",
        "channel": "db_import",
        "updated_cursor": cursor_value,
        "is_synthetic": True,
    }


def _serialize_bulk_raw_record(row: dict) -> dict:
    return {
        "raw_record_id": row["id"],
        "tenant_id": row["tenant_id"],
        "data_source_id": row["data_source_id"],
        "collection_run_id": row["collection_run_id"],
        "source_type": row["source_type"],
        "title": mask_sensitive_text(row["title"]),
        "content_hash": row["content_hash"],
        "status": row["status"],
        "is_synthetic": row["is_synthetic"],
        "city_id": row["city_id"],
        "occurred_at": row["occurred_at"],
        "payload": _redact_sensitive_payload(row["payload"]),
        "created_at": None,
    }


def _synthetic_object_connection_result(policy: dict, request) -> dict:
    if policy.get("permission_mode") == "deny":
        return {
            "status": "failed",
            "classification": "forbidden",
            "status_code": 403,
            "latency_ms": 1,
            "is_synthetic": bool(policy.get("is_synthetic")),
            "sample_metadata": {"bucket": policy.get("bucket"), "prefix": policy.get("prefix"), "sample_path": request.sample_path},
        }
    return {
        "status": "ok",
        "classification": "ok",
        "status_code": request.expected_status,
        "latency_ms": 1,
        "is_synthetic": bool(policy.get("is_synthetic")),
        "sample_metadata": {
            "bucket": policy.get("bucket"),
            "prefix": policy.get("prefix"),
            "sample_path": request.sample_path,
            "key_count": 1000,
            "adapter": "synthetic_object_storage",
        },
    }


def _prepare_webhook_policy(session: Session, tenant_id: str, policy: dict, existing_source_id: str | None = None) -> str | None:
    for key in ("secret", "webhook_secret", "signing_secret"):
        if key in policy:
            raise _api_error(422, "WEBHOOK_SECRET_PLAINTEXT_NOT_ALLOWED", "Webhook signing secrets cannot be supplied or stored as plaintext policy.")
    existing_webhook = policy.get("webhook") if isinstance(policy.get("webhook"), dict) else {}
    source_key = str(policy.get("source_key") or existing_webhook.get("source_key") or f"wh-{uuid4().hex[:20]}")
    _ensure_unique_webhook_key(session, tenant_id, source_key, existing_source_id)
    secret_once = secrets.token_urlsafe(32)
    secret_hash = _hash(secret_once)
    received_delivery_ids = list(existing_webhook.get("received_delivery_ids") or [])
    webhook = {
        "source_key": source_key,
        "endpoint_path": f"/api/v1/webhooks/{source_key}",
        "secret_ref": f"generated://webhooks/{source_key}/v1",
        "secret_hash": secret_hash,
        "signature_header": "x-cet-signature",
        "timestamp_header": "x-cet-timestamp",
        "delivery_id_header": "x-cet-delivery-id",
        "signature_version": 1,
        "accepted_window_seconds": int(policy.get("accepted_window_seconds") or existing_webhook.get("accepted_window_seconds") or 300),
        "received_delivery_ids": received_delivery_ids[:20],
        "idempotency_store": "raw_records.webhook_delivery_key",
    }
    policy.pop("source_key", None)
    policy["webhook"] = webhook
    policy["secret_ref"] = webhook["secret_ref"]
    _WEBHOOK_SECRET_CACHE[source_key] = secret_once
    return secret_once


def _ensure_unique_webhook_key(session: Session, tenant_id: str, source_key: str, existing_source_id: str | None) -> None:
    rows = session.execute(select(models.DataSource).where(models.DataSource.source_type == "webhook")).scalars()
    for row in rows:
        if existing_source_id and row.id == existing_source_id:
            continue
        webhook = _webhook_policy(row)
        if webhook.get("source_key") == source_key:
            raise _api_error(409, "WEBHOOK_SOURCE_KEY_DUPLICATE", "Webhook source_key already exists.")


def _webhook_source_by_key(session: Session, source_key: str) -> models.DataSource:
    cached_source_id = _WEBHOOK_SOURCE_CACHE.get(source_key)
    if cached_source_id:
        cached = session.get(models.DataSource, cached_source_id)
        if cached is not None and _webhook_policy(cached).get("source_key") == source_key:
            return cached
        _WEBHOOK_SOURCE_CACHE.pop(source_key, None)
    rows = session.execute(select(models.DataSource).where(models.DataSource.source_type == "webhook")).scalars()
    for source in rows:
        if _webhook_policy(source).get("source_key") == source_key:
            _WEBHOOK_SOURCE_CACHE[source_key] = source.id
            return source
    raise _api_error(404, "WEBHOOK_SOURCE_NOT_FOUND", "Webhook source does not exist.")


def _webhook_policy(source: models.DataSource) -> dict:
    policy = source.policy or {}
    webhook = policy.get("webhook")
    return webhook if isinstance(webhook, dict) else {}


def _verify_webhook_timestamp(timestamp: str | None, accepted_window_seconds: int) -> None:
    try:
        value = int(timestamp or "")
    except ValueError as error:
        raise _api_error(401, "WEBHOOK_TIMESTAMP_INVALID", "Webhook timestamp must be a unix timestamp.") from error
    if abs(int(time.time()) - value) > accepted_window_seconds:
        raise _api_error(401, "WEBHOOK_TIMESTAMP_EXPIRED", "Webhook timestamp is outside the accepted window.")


def _verify_webhook_signature(source_key: str, timestamp: str, raw_body: bytes, signature: str | None) -> None:
    secret = _WEBHOOK_SECRET_CACHE.get(source_key)
    if not secret:
        raise _api_error(503, "WEBHOOK_SECRET_UNAVAILABLE", "Webhook signing secret is unavailable in the local secret manager.")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + raw_body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise _api_error(401, "WEBHOOK_SIGNATURE_INVALID", "Webhook signature verification failed.")


def _parse_webhook_payload(raw_body: bytes) -> dict:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _api_error(422, "WEBHOOK_PAYLOAD_INVALID", "Webhook payload must be valid JSON.") from error
    if not isinstance(parsed, dict):
        raise _api_error(422, "WEBHOOK_PAYLOAD_INVALID", "Webhook payload must be a JSON object.")
    return parsed


def _validate_webhook_payload_schema(policy: dict, payload: dict) -> None:
    schema = policy.get("schema") if isinstance(policy.get("schema"), dict) else {}
    required_fields = schema.get("required_fields") if isinstance(schema.get("required_fields"), list) else []
    missing = [str(field) for field in required_fields if not str(field) or payload.get(str(field)) in (None, "")]
    if missing:
        raise _api_error(422, "WEBHOOK_SCHEMA_INVALID", "Webhook payload is missing required fields.", {"missing_fields": missing})


def _webhook_request_dedupe_key(request_id: str, delivery_id: str) -> str:
    value = request_id.strip() or delivery_id.strip()
    prefix = "request" if request_id.strip() else "delivery"
    return f"webhook-{prefix}:{value}"[:240]


def _webhook_delivery_key(delivery_id: str) -> str:
    return f"webhook-delivery:{delivery_id.strip()}"[:240]


def _webhook_delivery_exists(session: Session, source_id: str, delivery_id: str) -> bool:
    existing = session.execute(
        select(models.RawRecord)
        .where(
            models.RawRecord.data_source_id == source_id,
            models.RawRecord.source_type == "webhook",
            models.RawRecord.webhook_delivery_key == _webhook_delivery_key(delivery_id),
        )
        .limit(1)
    ).scalar_one_or_none()
    return existing is not None


def _validate_url(url: str, network: bool = True) -> dict:
    parsed = urlparse(url)
    if parsed.scheme == "synthetic":
        return {
            "url": url,
            "reachable": True,
            "status_code": 200,
            "content_type": "text/html",
            "latency_ms": 1,
            "is_synthetic": True,
            "validation_mode": "synthetic_adapter",
        }
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _api_error(422, "URL_SCHEME_NOT_ALLOWED", "Only http, https, and synthetic source URLs are allowed.")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("127.") or host.endswith(".local"):
        raise _api_error(422, "URL_HOST_NOT_ALLOWED", "Private or local source URLs are not allowed.")
    if not network:
        return {
            "url": url,
            "reachable": True,
            "status_code": None,
            "content_type": None,
            "latency_ms": 0,
            "is_synthetic": False,
            "validation_mode": "syntax_and_policy_only",
        }
    started = time.perf_counter()
    try:
        request = UrlRequest(url, method="HEAD", headers={"User-Agent": "CollectiveEventTwin-SourceValidator/1.0"})
        with urlopen(request, timeout=5) as response:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "url": url,
                "reachable": True,
                "status_code": response.status,
                "content_type": response.headers.get("content-type"),
                "latency_ms": latency_ms,
                "is_synthetic": False,
                "validation_mode": "http_head",
            }
    except HTTPError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "url": url,
            "reachable": error.code < 500,
            "status_code": error.code,
            "content_type": error.headers.get("content-type"),
            "latency_ms": latency_ms,
            "is_synthetic": False,
            "validation_mode": "http_head",
            "error_code": f"HTTP_{error.code}",
        }
    except URLError as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "url": url,
            "reachable": False,
            "status_code": None,
            "content_type": None,
            "latency_ms": latency_ms,
            "is_synthetic": False,
            "validation_mode": "http_head",
            "error_code": "URL_UNREACHABLE",
            "error_message": str(error.reason),
        }


def _scoped_raw_records(session: Session, raw_record_ids: list[str], limit: int, tenant_id: str | None = None) -> list[models.RawRecord]:
    statement = select(models.RawRecord).order_by(models.RawRecord.created_at.desc()).limit(limit)
    if tenant_id:
        statement = statement.where(models.RawRecord.tenant_id == tenant_id)
    if raw_record_ids:
        records: list[models.RawRecord] = []
        for offset in range(0, len(raw_record_ids), SQL_IN_CHUNK_SIZE):
            chunk = raw_record_ids[offset : offset + SQL_IN_CHUNK_SIZE]
            if not chunk:
                continue
            chunk_statement = select(models.RawRecord).where(models.RawRecord.id.in_(chunk))
            if tenant_id:
                chunk_statement = chunk_statement.where(models.RawRecord.tenant_id == tenant_id)
            records.extend(session.execute(chunk_statement).scalars())
        records.sort(key=lambda record: record.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return records[:limit]
    return list(session.execute(statement).scalars())


def normalize_text(value: str | None) -> dict:
    raw = "" if value is None else str(value)
    html_tag_count = len(re.findall(r"<[^>]+>", raw))
    control_char_count = len(re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", raw))
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    without_controls = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", without_tags)
    normalized = re.sub(r"\s+", " ", html_lib.unescape(without_controls).strip()).lower()
    status = "valid" if normalized else "invalid"
    result = {
        "status": status,
        "normalized_text": normalized,
        "raw_length": len(raw),
        "normalized_length": len(normalized),
        "html_tag_count": html_tag_count,
        "control_char_count": control_char_count,
    }
    if status != "valid":
        result.update({"error_code": "NORMALIZE_TEXT_EMPTY", "error_message": "Text is empty after HTML, control character, and whitespace normalization."})
    return result


def _normalize_text(value: str) -> str:
    return normalize_text(value)["normalized_text"]


def normalize_datetime(record: models.RawRecord, raw_payload: models.RawRecordPayload | None, default_timezone: str = "+08:00") -> dict:
    for source_field, value in _datetime_candidate_values(record, raw_payload):
        parsed = _parse_datetime_value(value, default_timezone)
        if parsed is None:
            continue
        dt, original_timezone, parse_format = parsed
        return {
            "status": "normalized",
            "raw_datetime": str(value).strip(),
            "normalized_datetime_utc": _manual_record_datetime_iso(dt),
            "original_timezone": original_timezone,
            "source_field": source_field,
            "parse_format": parse_format,
        }
    return {
        "status": "review_required",
        "raw_datetime": None,
        "normalized_datetime_utc": None,
        "original_timezone": None,
        "source_field": None,
        "parse_format": None,
        "error_code": "DATETIME_PARSE_REVIEW_REQUIRED",
        "error_message": "No parseable datetime was found; manual review is required.",
    }


LOCATION_CITY_ALIASES = {"xian": ("xian", "西安"), "西安": ("xian", "西安"), "西安市": ("xian", "西安")}
LOCATION_DISTRICTS = {
    "雁塔": "雁塔区",
    "雁塔区": "雁塔区",
    "yanta": "雁塔区",
    "碑林": "碑林区",
    "碑林区": "碑林区",
    "beilin": "碑林区",
    "新城": "新城区",
    "新城区": "新城区",
    "莲湖": "莲湖区",
    "莲湖区": "莲湖区",
    "长安": "长安区",
    "长安区": "长安区",
    "未央": "未央区",
    "未央区": "未央区",
    "灞桥": "灞桥区",
    "灞桥区": "灞桥区",
}


def normalize_location(record: models.RawRecord, raw_payload: models.RawRecordPayload | None) -> dict:
    payload_result = _location_from_payload(record.payload if isinstance(record.payload, dict) else {})
    if payload_result is not None:
        return payload_result
    raw_payload_result = _location_from_payload(raw_payload.payload if raw_payload is not None and isinstance(raw_payload.payload, dict) else {}, source_prefix="raw_payload.payload")
    if raw_payload_result is not None:
        return raw_payload_result
    text = raw_payload.content_text if raw_payload is not None else ""
    return _location_from_text(text)


def _location_from_payload(payload: dict, source_prefix: str = "payload") -> dict | None:
    city_id, city = _normalize_city(payload.get("city_id") or payload.get("city") or payload.get("city_name") or payload.get("region_id"))
    district = _normalize_district(payload.get("district") or payload.get("district_name"))
    address = _location_text(payload.get("address") or payload.get("location"))
    if not (city_id or district or address):
        return None
    if not city_id and (district or address):
        city_id, city = "xian", "西安"
    if not district and address:
        district = _district_from_text(address)
    return {
        "status": "normalized",
        "city_id": city_id or "xian",
        "city": city or "西安",
        "district": district,
        "address": address,
        "source_field": source_prefix,
        "candidates": [],
    }


def _location_from_text(text: str | None) -> dict:
    raw = _location_text(text)
    if not raw:
        return _location_missing()
    districts = []
    for key, district in LOCATION_DISTRICTS.items():
        if key and key in raw and district not in districts:
            districts.append(district)
    if len(districts) > 1:
        return {
            "status": "candidate",
            "city_id": "xian",
            "city": "西安",
            "district": None,
            "address": None,
            "source_field": "raw_payload.content_text",
            "candidates": [{"city_id": "xian", "city": "西安", "district": district, "address": _address_from_text(raw, district)} for district in districts],
            "error_code": "LOCATION_AMBIGUOUS_CANDIDATES",
            "error_message": "Multiple location candidates were found; manual review is required.",
        }
    district = districts[0] if districts else None
    city_id, city = _normalize_city("xian" if district or "西安" in raw or "西安市" in raw else None)
    if not city_id:
        return _location_missing()
    return {
        "status": "normalized",
        "city_id": city_id,
        "city": city,
        "district": district,
        "address": _address_from_text(raw, district),
        "source_field": "raw_payload.content_text",
        "candidates": [],
    }


def _location_missing() -> dict:
    return {
        "status": "candidate",
        "city_id": None,
        "city": None,
        "district": None,
        "address": None,
        "source_field": None,
        "candidates": [],
        "error_code": "LOCATION_REVIEW_REQUIRED",
        "error_message": "No normalized location could be extracted; manual review is required.",
    }


def _normalize_city(value: object | None) -> tuple[str | None, str | None]:
    text = _location_text(value)
    if not text:
        return None, None
    lowered = text.lower()
    for key, result in LOCATION_CITY_ALIASES.items():
        if key.lower() == lowered or key in text:
            return result
    return None, None


def _normalize_district(value: object | None) -> str | None:
    text = _location_text(value)
    if not text:
        return None
    lowered = text.lower()
    for key, district in LOCATION_DISTRICTS.items():
        if key.lower() == lowered or key in text:
            return district
    return None


def _district_from_text(text: str) -> str | None:
    districts = [district for key, district in LOCATION_DISTRICTS.items() if key in text]
    return districts[0] if districts else None


def _address_from_text(text: str, district: str | None) -> str | None:
    if not text:
        return None
    district_index = text.find(district) if district else -1
    if district_index >= 0:
        city_prefix = "西安市" if "西安" in text[: district_index + len(district)] else ""
        segment = text[district_index : district_index + 40]
        suffix_match = re.search(r".*?(?:政务服务大厅|办事大厅|服务大厅|大厅|服务中心|中心|医院|学校|小区|路|街|站|窗口)", segment)
        if suffix_match:
            phrase = suffix_match.group(0).strip()
        else:
            end_match = re.search(r"[，。,.；;]", segment)
            end = end_match.start() if end_match else min(len(segment), 24)
            phrase = segment[:end].strip()
        return (city_prefix + phrase).strip() or None
    match = re.search(r"(西安市?[^，。,.；;]{0,40})", text)
    return match.group(1).strip() if match else None


def _location_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", "", str(value)).strip()
    return text or None


def assign_source_trust(record: models.RawRecord, source: models.DataSource | None) -> dict:
    source_type = source.source_type if source is not None else record.source_type
    source_name = source.name if source is not None else None
    policy = source.policy if source is not None and isinstance(source.policy, dict) else {}
    payload = source.payload if source is not None and isinstance(source.payload, dict) else {}
    candidates = [
        ("policy.source_trust.score", (policy.get("source_trust") or {}).get("score") if isinstance(policy.get("source_trust"), dict) else None),
        ("policy.source_trust", policy.get("source_trust") if not isinstance(policy.get("source_trust"), dict) else None),
        ("policy.trust_score", policy.get("trust_score")),
        ("policy.trust", policy.get("trust")),
        ("payload.source_trust.score", (payload.get("source_trust") or {}).get("score") if isinstance(payload.get("source_trust"), dict) else None),
        ("payload.source_trust", payload.get("source_trust") if not isinstance(payload.get("source_trust"), dict) else None),
        ("payload.trust_score", payload.get("trust_score")),
    ]
    warnings: list[dict] = []
    for field, value in candidates:
        score = _trust_score(value)
        if score is None:
            if value is not None:
                warnings.append({"code": "SOURCE_TRUST_INVALID", "message": f"Trust value at {field} is outside 0..1 and was ignored.", "source_field": field})
            continue
        return {
            "status": "assigned",
            "trust_score": score,
            "trust_band": _trust_band(score),
            "trust_source": field,
            "source_type": source_type,
            "source_name": source_name,
            "warnings": warnings,
            "source_policy_ref": _source_trust_policy_ref(policy, payload),
        }
    default_score = round(float(SOURCE_TRUST_DEFAULTS.get(source_type or "", SOURCE_TRUST_FALLBACK)), 4)
    warnings.append(
        {
            "code": "SOURCE_TRUST_DEFAULTED",
            "message": "No source trust configuration was found; deterministic source_type default was applied.",
            "source_type": source_type,
        }
    )
    return {
        "status": "defaulted",
        "trust_score": default_score,
        "trust_band": _trust_band(default_score),
        "trust_source": f"default.source_type.{source_type or 'unknown'}",
        "source_type": source_type,
        "source_name": source_name,
        "warnings": warnings,
        "source_policy_ref": _source_trust_policy_ref(policy, payload),
    }


def _trust_score(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0 or score > 1:
        return None
    return round(score, 4)


def _trust_band(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    if score >= 0.4:
        return "low"
    return "very_low"


def _source_trust_policy_ref(policy: dict, payload: dict) -> dict:
    source_trust = policy.get("source_trust") if isinstance(policy.get("source_trust"), dict) else {}
    payload_trust = payload.get("source_trust") if isinstance(payload.get("source_trust"), dict) else {}
    return {
        "policy_version": source_trust.get("version") or policy.get("source_trust_version"),
        "payload_version": payload_trust.get("version"),
        "has_policy_score": _trust_score(source_trust.get("score") if source_trust else policy.get("trust_score") or policy.get("trust")) is not None,
    }


def detect_sensitive_fields(record: models.RawRecord, raw_payload: models.RawRecordPayload | None) -> dict:
    original_text = raw_payload.content_text if raw_payload is not None else record.title
    masked_text = mask_sensitive_text(original_text)
    fields = []
    for field_type, pattern, severity in SENSITIVE_DETECTOR_PATTERNS:
        for match in pattern.finditer(original_text):
            fields.append(
                {
                    "field_type": field_type,
                    "severity": severity,
                    "start": match.start(),
                    "end": match.end(),
                    "length": match.end() - match.start(),
                    "redacted_value": "[MASKED]",
                    "source_field": "raw_record_payload.content_text" if raw_payload is not None else "raw_record.title",
                }
            )
    fields.sort(key=lambda item: (item["start"], item["field_type"]))
    if any(field["severity"] == "sensitive" for field in fields):
        risk_level = "sensitive"
    elif fields:
        risk_level = "restricted"
    else:
        risk_level = "none"
    return {"fields": fields, "redacted_preview": masked_text, "risk_level": risk_level}


def _redact_sensitive_payload(value):
    if isinstance(value, dict):
        return {mask_sensitive_text(str(key)): _redact_sensitive_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_sensitive_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_sensitive_payload(item) for item in value]
    if isinstance(value, str):
        return mask_sensitive_text(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value)
        return "[MASKED]" if mask_sensitive_text(text) != text else value
    return value


def _datetime_candidate_values(record: models.RawRecord, raw_payload: models.RawRecordPayload | None):
    seen: set[str] = set()

    def emit(source_field: str, value: object | None):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in seen:
            return None
        seen.add(text)
        return (source_field, text)

    for container_name, container in (("payload", record.payload), ("raw_payload.payload", raw_payload.payload if raw_payload is not None else None)):
        if not isinstance(container, dict):
            continue
        for key in ("occurred_at", "published_at", "time", "timestamp", "datetime", "date"):
            candidate = emit(f"{container_name}.{key}", container.get(key))
            if candidate is not None:
                yield candidate
    text = raw_payload.content_text if raw_payload is not None else ""
    for candidate_text in _datetime_candidates_from_text(text):
        candidate = emit("raw_payload.content_text", candidate_text)
        if candidate is not None:
            yield candidate


def _datetime_candidates_from_text(text: str | None) -> list[str]:
    if not text:
        return []
    candidates = re.findall(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}[T\s]\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:Z|[+-]\d{2}:?\d{2}))?\b", text)
    candidates.extend(re.findall(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", text))
    return candidates


def _parse_datetime_value(value: object, default_timezone: str = "+08:00") -> tuple[datetime, str, str] | None:
    text = str(value).strip()
    if not text:
        return None
    tz = _timezone_from_label(default_timezone)
    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text.replace("/", "-").replace("Z", "+00:00"))
    try:
        parsed = datetime.fromisoformat(normalized)
        parse_format = "iso8601"
    except ValueError:
        parsed = None
        parse_format = ""
    if parsed is None:
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                parse_format = fmt
                break
            except ValueError:
                continue
    if parsed is None:
        try:
            parsed = email.utils.parsedate_to_datetime(text)
            parse_format = "rfc2822"
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed, _timezone_label(parsed), parse_format


def _timezone_from_label(value: str) -> timezone:
    text = (value or "+08:00").strip()
    if text.upper() in {"Z", "UTC", "+00:00", "+0000"}:
        return timezone.utc
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", text)
    if match:
        sign = -1 if match.group(1) == "-" else 1
        return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3))))
    return timezone(timedelta(hours=8))


def _timezone_label(value: datetime) -> str:
    offset = value.utcoffset() or timedelta(0)
    if offset == timedelta(0):
        return "Z"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "-" if total_minutes < 0 else "+"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _html_text(value: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(value).strip())


class _HtmlMainContentParser(HTMLParser):
    ignored_tags = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "canvas"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.skip_depth = 0
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.article_parts: list[str] = []
        self.main_parts: list[str] = []
        self.body_parts: list[str] = []
        self.published_at: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        self.stack.append(tag)
        if tag in self.ignored_tags:
            self.skip_depth += 1
        if tag == "meta":
            attr_map = {str(key).lower(): str(value) for key, value in attrs if value is not None}
            key = (attr_map.get("property") or attr_map.get("name") or "").lower()
            if key in {"article:published_time", "published_time", "datepublished", "publishdate", "dc.date", "date"}:
                self.published_at = attr_map.get("content") or self.published_at
        if tag == "time":
            attr_map = {str(key).lower(): str(value) for key, value in attrs if value is not None}
            self.published_at = attr_map.get("datetime") or self.published_at

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags and self.skip_depth > 0:
            self.skip_depth -= 1
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        text = _html_text(data)
        if not text:
            return
        if self.stack and self.stack[-1] == "title":
            self.title_parts.append(text)
            return
        if self.skip_depth:
            return
        if "h1" in self.stack:
            self.h1_parts.append(text)
        if "article" in self.stack:
            self.article_parts.append(text)
        elif "main" in self.stack:
            self.main_parts.append(text)
        elif "body" in self.stack:
            self.body_parts.append(text)


def parse_html_main_content(raw_html: str) -> dict:
    parser = _HtmlMainContentParser()
    parser.feed(raw_html or "")
    parser.close()
    title = _html_text(" ".join(parser.h1_parts or parser.title_parts))
    body = _html_text(" ".join(parser.article_parts or parser.main_parts or parser.body_parts))
    if title and body.startswith(title):
        body = _html_text(body[len(title) :])
    if not body:
        return {
            "status": "parse_failed",
            "error_code": "HTML_MAIN_CONTENT_EMPTY",
            "error_message": "HTML main content is empty.",
            "title": title,
            "body": "",
            "published_at": parser.published_at,
        }
    return {
        "status": "parsed",
        "title": title,
        "body": body,
        "published_at": parser.published_at,
    }


def parse_csv_file(raw_text: str, mapping: dict[str, str]) -> dict:
    if "\ufffd" in (raw_text or ""):
        return {
            "status": "file_error",
            "error_code": "CSV_ENCODING_ERROR",
            "error_message": "CSV file must be valid UTF-8 without replacement characters.",
            "missing_columns": [],
            "row_count": 0,
            "rows": [],
        }
    reader = csv.DictReader(io.StringIO(raw_text or ""))
    headers = [str(field or "").strip() for field in (reader.fieldnames or []) if str(field or "").strip()]
    if not headers:
        return {
            "status": "file_error",
            "error_code": "CSV_COLUMNS_MISSING",
            "error_message": "CSV file must contain a header row.",
            "missing_columns": sorted({mapping.get("title") or "title", mapping.get("body") or "body"}),
            "row_count": 0,
            "rows": [],
        }
    required_columns = [mapping.get(field, field) for field in ("title", "body")]
    missing_columns = [str(column) for column in required_columns if not column or str(column) not in headers]
    if missing_columns:
        return {
            "status": "file_error",
            "error_code": "CSV_COLUMNS_MISSING",
            "error_message": "CSV file is missing required mapped columns.",
            "missing_columns": missing_columns,
            "row_count": 0,
            "rows": [],
        }

    rows: list[dict] = []
    parsed_count = 0
    failed_count = 0
    for row_number, source_row in enumerate(reader, start=2):
        columns = {str(key): str(value or "").strip() for key, value in (source_row or {}).items() if key is not None}
        title = columns.get(mapping["title"], "")
        body = columns.get(mapping["body"], "")
        published_at = columns.get(mapping["published_at"], "") if mapping.get("published_at") else None
        missing_fields = [field for field, value in (("title", title), ("body", body)) if not value]
        if missing_fields:
            failed_count += 1
            rows.append(
                {
                    "status": "parse_error",
                    "error_code": "CSV_ROW_REQUIRED_FIELD_MISSING",
                    "error_message": "CSV row is missing required mapped fields.",
                    "missing_fields": missing_fields,
                    "row_number": row_number,
                    "title": title,
                    "body": body,
                    "published_at": published_at or None,
                    "columns": columns,
                }
            )
            continue
        parsed_count += 1
        rows.append(
            {
                "status": "parsed",
                "row_number": row_number,
                "title": title,
                "body": body,
                "published_at": published_at or None,
                "columns": columns,
            }
        )
    return {
        "status": "parsed",
        "row_count": len(rows),
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "headers": headers,
        "rows": rows,
    }


def _csv_file_mapping(payload: dict) -> dict[str, str]:
    mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else payload.get("field_mapping")
    mapping = mapping if isinstance(mapping, dict) else {}
    if not mapping:
        mapping = {"title": "title", "body": "content", "published_at": "published_at"}
    normalized = {str(key): str(value).strip() for key, value in mapping.items() if value is not None and str(value).strip()}
    for field in ("title", "body"):
        normalized.setdefault(field, field)
    return normalized


def parse_xlsx_file(content: bytes, mapping: dict[str, str], sheet_name: str | None = None, cell_range: str | None = None) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            shared_strings = _xlsx_shared_strings(workbook)
            sheets = _xlsx_sheet_paths(workbook)
            if not sheets:
                return _xlsx_file_error("XLSX_SHEET_NOT_FOUND", "XLSX workbook does not contain worksheets.", sheet_name=sheet_name, cell_range=cell_range)
            selected = sheet_name or sheets[0]["name"]
            sheet = next((item for item in sheets if item["name"] == selected), None)
            if sheet is None:
                return _xlsx_file_error("XLSX_SHEET_NOT_FOUND", "Requested XLSX sheet does not exist.", sheet_name=selected, cell_range=cell_range)
            bounds = _xlsx_parse_range(cell_range)
            if bounds is None and cell_range:
                return _xlsx_file_error("XLSX_RANGE_INVALID", "XLSX range must use A1 or A1:C10 notation.", sheet_name=selected, cell_range=cell_range)
            sheet_xml = workbook.read(sheet["path"])
            return _parse_xlsx_sheet(sheet_xml, shared_strings, mapping, selected, cell_range, bounds)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        return _xlsx_file_error("XLSX_FILE_INVALID", f"XLSX workbook could not be parsed: {error}", sheet_name=sheet_name, cell_range=cell_range)


def _xlsx_file_mapping(payload: dict) -> dict[str, str]:
    mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else payload.get("field_mapping")
    mapping = mapping if isinstance(mapping, dict) else {}
    if not mapping:
        mapping = {"title": "title", "body": "content", "published_at": "published_at"}
    normalized = {str(key): str(value).strip() for key, value in mapping.items() if value is not None and str(value).strip()}
    for field in ("title", "body"):
        normalized.setdefault(field, field)
    return normalized


def _xlsx_file_error(code: str, message: str, sheet_name: str | None = None, cell_range: str | None = None, **extra) -> dict:
    return {
        "status": "file_error",
        "error_code": code,
        "error_message": message,
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "missing_columns": extra.get("missing_columns", []),
        "error_ref": extra.get("error_ref"),
        "row_count": int(extra.get("row_count") or 0),
        "rows": [],
    }


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.iter():
        if _strip_xml_namespace(item.tag) != "si":
            continue
        text_parts = [node.text or "" for node in item.iter() if _strip_xml_namespace(node.tag) == "t"]
        values.append("".join(text_parts))
    return values


def _xlsx_sheet_paths(workbook: zipfile.ZipFile) -> list[dict]:
    workbook_root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rels = {rel.attrib.get("Id"): rel.attrib.get("Target") for rel in rels_root if rel.attrib.get("Id") and rel.attrib.get("Target")}
    sheets: list[dict] = []
    for element in workbook_root.iter():
        if _strip_xml_namespace(element.tag) != "sheet":
            continue
        rel_id = next((value for key, value in element.attrib.items() if key.endswith("}id") or key == "id"), None)
        target = rels.get(rel_id or "")
        if not target:
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = posixpath.normpath(target)
        else:
            path = posixpath.normpath(posixpath.join("xl", target))
        sheets.append({"name": str(element.attrib.get("name") or f"Sheet{len(sheets) + 1}"), "path": path})
    return sheets


def _parse_xlsx_sheet(
    sheet_xml: bytes,
    shared_strings: list[str],
    mapping: dict[str, str],
    sheet_name: str,
    cell_range: str | None,
    bounds: tuple[int, int, int | None, int | None] | None,
) -> dict:
    root = ElementTree.fromstring(sheet_xml)
    min_col, min_row, max_col, max_row = bounds or (1, 1, None, None)
    for merge_cell in root.iter():
        if _strip_xml_namespace(merge_cell.tag) != "mergeCell":
            continue
        merge_ref = str(merge_cell.attrib.get("ref") or "")
        merge_bounds = _xlsx_parse_range(merge_ref)
        if merge_bounds and _xlsx_ranges_intersect((min_col, min_row, max_col, max_row), merge_bounds):
            return _xlsx_file_error(
                "XLSX_MERGED_CELLS_UNSUPPORTED",
                "XLSX parser does not accept merged cells inside the selected range.",
                sheet_name=sheet_name,
                cell_range=cell_range,
                error_ref=merge_ref,
            )

    row_cells: dict[int, dict[int, str]] = defaultdict(dict)
    formula_ref: str | None = None
    for cell in root.iter():
        if _strip_xml_namespace(cell.tag) != "c":
            continue
        ref = str(cell.attrib.get("r") or "")
        coordinate = _xlsx_cell_coordinate(ref)
        if coordinate is None:
            continue
        column_index, row_index = coordinate
        if column_index < min_col or row_index < min_row:
            continue
        if max_col is not None and column_index > max_col:
            continue
        if max_row is not None and row_index > max_row:
            continue
        if any(_strip_xml_namespace(child.tag) == "f" for child in cell):
            formula_ref = ref
            break
        row_cells[row_index][column_index] = _xlsx_cell_value(cell, shared_strings)
    if formula_ref:
        return _xlsx_file_error(
            "XLSX_FORMULA_UNSUPPORTED",
            "XLSX parser requires resolved literal values and does not evaluate formulas.",
            sheet_name=sheet_name,
            cell_range=cell_range,
            error_ref=formula_ref,
        )

    header_row = row_cells.get(min_row, {})
    headers_by_col = {column: value.strip() for column, value in header_row.items() if value.strip()}
    required_columns = [mapping.get(field, field) for field in ("title", "body")]
    missing_columns = [str(column) for column in required_columns if not column or str(column) not in set(headers_by_col.values())]
    if missing_columns:
        return _xlsx_file_error(
            "XLSX_COLUMNS_MISSING",
            "XLSX sheet is missing required mapped columns.",
            sheet_name=sheet_name,
            cell_range=cell_range,
            missing_columns=missing_columns,
        )

    field_columns: dict[str, int] = {}
    for field, header in mapping.items():
        for column, value in headers_by_col.items():
            if value == header:
                field_columns[field] = column
                break

    rows: list[dict] = []
    parsed_count = 0
    failed_count = 0
    selected_row_numbers = [row for row in sorted(row_cells) if row > min_row and (max_row is None or row <= max_row)]
    for row_number in selected_row_numbers:
        source_row = row_cells.get(row_number, {})
        columns = {header: source_row.get(column, "").strip() for column, header in headers_by_col.items()}
        if not any(columns.values()):
            continue
        title = source_row.get(field_columns.get("title", -1), "").strip()
        body = source_row.get(field_columns.get("body", -1), "").strip()
        published_at = source_row.get(field_columns.get("published_at", -1), "").strip() if "published_at" in field_columns else None
        missing_fields = [field for field, value in (("title", title), ("body", body)) if not value]
        if missing_fields:
            failed_count += 1
            rows.append(
                {
                    "status": "parse_error",
                    "error_code": "XLSX_ROW_REQUIRED_FIELD_MISSING",
                    "error_message": "XLSX row is missing required mapped fields.",
                    "missing_fields": missing_fields,
                    "row_number": row_number,
                    "title": title,
                    "body": body,
                    "published_at": published_at or None,
                    "columns": columns,
                }
            )
            continue
        parsed_count += 1
        rows.append({"status": "parsed", "row_number": row_number, "title": title, "body": body, "published_at": published_at or None, "columns": columns})

    return {
        "status": "parsed",
        "sheet_name": sheet_name,
        "cell_range": cell_range,
        "row_count": len(rows),
        "parsed_count": parsed_count,
        "failed_count": failed_count,
        "headers": list(headers_by_col.values()),
        "rows": rows,
    }


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter() if _strip_xml_namespace(node.tag) == "t").strip()
    value_node = next((child for child in cell if _strip_xml_namespace(child.tag) == "v"), None)
    raw_value = (value_node.text or "").strip() if value_node is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)].strip()
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "true" if raw_value == "1" else "false"
    return raw_value


def _xlsx_parse_range(value: str | None) -> tuple[int, int, int | None, int | None] | None:
    if not value:
        return (1, 1, None, None)
    parts = value.split(":")
    if len(parts) == 1:
        start = _xlsx_cell_coordinate(parts[0])
        if start is None:
            return None
        return (start[0], start[1], start[0], start[1])
    if len(parts) != 2:
        return None
    start = _xlsx_cell_coordinate(parts[0])
    end = _xlsx_cell_coordinate(parts[1])
    if start is None or end is None:
        return None
    return (min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1]))


def _xlsx_cell_coordinate(ref: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", ref.strip())
    if not match:
        return None
    column = 0
    for char in match.group(1).upper():
        column = column * 26 + (ord(char) - 64)
    return column, int(match.group(2))


def _xlsx_ranges_intersect(left: tuple[int, int, int | None, int | None], right: tuple[int, int, int | None, int | None]) -> bool:
    left_min_col, left_min_row, left_max_col, left_max_row = left
    right_min_col, right_min_row, right_max_col, right_max_row = right
    left_max_col = left_max_col or 16384
    left_max_row = left_max_row or 1048576
    right_max_col = right_max_col or 16384
    right_max_row = right_max_row or 1048576
    return not (left_max_col < right_min_col or right_max_col < left_min_col or left_max_row < right_min_row or right_max_row < left_min_row)


def parse_docx_text(content: bytes) -> dict:
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return {"status": "file_error", "error_code": "DOCX_ENCRYPTED_UNSUPPORTED", "error_message": "Encrypted or legacy Office containers are not supported by the DOCX text parser.", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "EncryptedPackage" in names:
                return {"status": "file_error", "error_code": "DOCX_ENCRYPTED_UNSUPPORTED", "error_message": "Encrypted DOCX packages are not supported by the DOCX text parser.", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}
            if "word/document.xml" not in names:
                return {"status": "file_error", "error_code": "DOCX_DOCUMENT_XML_MISSING", "error_message": "DOCX package does not contain word/document.xml.", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}
            document_xml = archive.read("word/document.xml")
    except zipfile.BadZipFile:
        return {"status": "file_error", "error_code": "DOCX_FILE_INVALID", "error_message": "DOCX file is not a valid ZIP package.", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}
    except OSError as error:
        return {"status": "file_error", "error_code": "DOCX_FILE_INVALID", "error_message": f"DOCX file could not be read: {error}", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as error:
        return {"status": "file_error", "error_code": "DOCX_XML_INVALID", "error_message": f"DOCX document XML is invalid: {error}", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    body = root.find(f".//{namespace}body")
    if body is None:
        return {"status": "file_error", "error_code": "DOCX_BODY_MISSING", "error_message": "DOCX document body is missing.", "block_count": 0, "paragraph_count": 0, "table_count": 0, "table_cell_count": 0, "blocks": []}

    blocks: list[dict] = []
    paragraph_count = 0
    table_count = 0
    table_cell_count = 0
    for child in list(body):
        tag = _xml_local_name(child.tag)
        if tag == "p":
            paragraph_count += 1
            text = _docx_paragraph_text(child)
            if text:
                blocks.append({"block_number": len(blocks) + 1, "block_type": "paragraph", "paragraph_number": paragraph_count, "text": text})
        elif tag == "tbl":
            table_count += 1
            for row_number, row in enumerate(child.findall(f"{namespace}tr"), start=1):
                for column_number, cell in enumerate(row.findall(f"{namespace}tc"), start=1):
                    paragraph_texts = [_docx_paragraph_text(paragraph) for paragraph in cell.findall(f"{namespace}p")]
                    text = _html_text(" ".join(item for item in paragraph_texts if item))
                    if text:
                        table_cell_count += 1
                        blocks.append(
                            {
                                "block_number": len(blocks) + 1,
                                "block_type": "table_cell",
                                "table_number": table_count,
                                "row_number": row_number,
                                "column_number": column_number,
                                "text": text,
                            }
                        )
    if not blocks:
        return {"status": "file_error", "error_code": "DOCX_TEXT_EMPTY", "error_message": "DOCX document contains no extractable paragraph or table text.", "block_count": 0, "paragraph_count": paragraph_count, "table_count": table_count, "table_cell_count": table_cell_count, "parser_engine": "ooxml_zip_xml", "blocks": []}
    return {"status": "parsed", "block_count": len(blocks), "paragraph_count": paragraph_count, "table_count": table_count, "table_cell_count": table_cell_count, "parser_engine": "ooxml_zip_xml", "blocks": blocks}


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        tag = _xml_local_name(node.tag)
        if tag == "t" and node.text:
            parts.append(node.text)
        elif tag == "tab":
            parts.append("\t")
        elif tag in {"br", "cr"}:
            parts.append("\n")
    return _html_text("".join(parts))


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_pdf_text(content: bytes) -> dict:
    if not content.startswith(b"%PDF-"):
        return {"status": "file_error", "error_code": "PDF_FILE_INVALID", "error_message": "PDF file header is missing.", "page_count": 0, "pages": []}
    engine_result = _parse_pdf_text_with_pypdf(content)
    if engine_result is not None:
        return engine_result
    objects = _pdf_objects(content)
    page_object_ids = _pdf_page_object_ids(objects)
    if not page_object_ids:
        return {"status": "file_error", "error_code": "PDF_PAGE_TREE_EMPTY", "error_message": "PDF contains no page objects.", "page_count": 0, "pages": []}
    pages: list[dict] = []
    parsed_count = 0
    ocr_required_count = 0
    for page_number, page_object_id in enumerate(page_object_ids, start=1):
        page_body = objects.get(page_object_id, b"")
        content_refs = _pdf_content_refs(page_body)
        text_parts: list[str] = []
        for content_ref in content_refs:
            stream = _pdf_stream_bytes(objects.get(content_ref, b""))
            if stream:
                text_parts.extend(_pdf_text_from_stream(stream))
        text = _html_text(" ".join(text_parts))
        if text:
            parsed_count += 1
            pages.append({"status": "parsed", "page_number": page_number, "text": text})
        else:
            ocr_required_count += 1
            pages.append({"status": "ocr_required", "page_number": page_number, "text": "", "error_code": "PDF_OCR_REQUIRED", "error_message": "PDF page contains no extractable text; OCR is required."})
    return {"status": "parsed", "page_count": len(pages), "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "pages": pages}


def _parse_pdf_text_with_pypdf(content: bytes) -> dict | None:
    try:
        pdf_reader = import_module("pypdf").PdfReader
    except (ImportError, AttributeError):
        return None
    try:
        reader = pdf_reader(io.BytesIO(content))
        pages: list[dict] = []
        parsed_count = 0
        ocr_required_count = 0
        for page_number, page in enumerate(reader.pages, start=1):
            raw_text = page.extract_text() or ""
            text = _html_text(raw_text)
            if text:
                parsed_count += 1
                pages.append({"status": "parsed", "page_number": page_number, "text": text, "engine": "pypdf"})
            else:
                ocr_required_count += 1
                pages.append({"status": "ocr_required", "page_number": page_number, "text": "", "error_code": "PDF_OCR_REQUIRED", "error_message": "PDF page contains no extractable text; OCR is required.", "engine": "pypdf"})
        return {"status": "parsed", "page_count": len(pages), "parsed_count": parsed_count, "ocr_required_count": ocr_required_count, "parser_engine": "pypdf", "pages": pages}
    except Exception as error:
        return {"status": "file_error", "error_code": "PDF_ENGINE_PARSE_FAILED", "error_message": f"pypdf could not parse the PDF: {error}", "page_count": 0, "parser_engine": "pypdf", "pages": []}


def _pdf_objects(content: bytes) -> dict[int, bytes]:
    objects: dict[int, bytes] = {}
    for match in re.finditer(rb"(?m)(\d+)\s+0\s+obj\s*(.*?)\s*endobj", content, re.DOTALL):
        objects[int(match.group(1))] = match.group(2)
    return objects


def _pdf_page_object_ids(objects: dict[int, bytes]) -> list[int]:
    page_ids = [object_id for object_id, body in objects.items() if re.search(rb"/Type\s*/Page\b", body)]
    return sorted(page_ids)


def _pdf_content_refs(page_body: bytes) -> list[int]:
    refs: list[int] = []
    contents = re.search(rb"/Contents\s*(\[[^\]]+\]|\d+\s+0\s+R)", page_body, re.DOTALL)
    if not contents:
        return refs
    for ref in re.finditer(rb"(\d+)\s+0\s+R", contents.group(1)):
        refs.append(int(ref.group(1)))
    return refs


def _pdf_stream_bytes(object_body: bytes) -> bytes:
    match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", object_body, re.DOTALL)
    if not match:
        return b""
    stream = match.group(1)
    if b"/FlateDecode" in object_body:
        try:
            return zlib.decompress(stream)
        except zlib.error:
            return b""
    return stream


def _pdf_text_from_stream(stream: bytes) -> list[str]:
    text: list[str] = []
    for literal in _pdf_literals_before_operator(stream, b"Tj"):
        text.append(_pdf_literal_string(literal))
    for literal in _pdf_literals_before_operator(stream, b"'"):
        text.append(_pdf_literal_string(literal))
    for literal in _pdf_literals_before_operator(stream, b'"'):
        text.append(_pdf_literal_string(literal))
    for array in re.finditer(rb"\[(.*?)\]\s*TJ", stream, re.DOTALL):
        parts = _pdf_literal_tokens(array.group(1))
        if parts:
            text.append("".join(_pdf_literal_string(part) for part in parts))
    return [item for item in text if item.strip()]


def _pdf_literals_before_operator(stream: bytes, operator: bytes) -> list[bytes]:
    literals: list[bytes] = []
    pattern = re.compile(rb"\s" + re.escape(operator) + rb"(?=\s|$)")
    for match in pattern.finditer(stream):
        prefix = stream[: match.start()].rstrip()
        literal = _pdf_last_literal_token(prefix)
        if literal:
            literals.append(literal)
    return literals


def _pdf_last_literal_token(value: bytes) -> bytes | None:
    tokens = _pdf_literal_tokens(value)
    return tokens[-1] if tokens else None


def _pdf_literal_tokens(value: bytes) -> list[bytes]:
    tokens: list[bytes] = []
    index = 0
    while index < len(value):
        if value[index] != ord("("):
            index += 1
            continue
        start = index
        index += 1
        depth = 1
        while index < len(value) and depth > 0:
            char = value[index]
            if char == 92:
                index += 2
                continue
            if char == ord("("):
                depth += 1
            elif char == ord(")"):
                depth -= 1
            index += 1
        if depth == 0:
            tokens.append(value[start:index])
    return tokens


def _pdf_literal_string(token: bytes) -> str:
    if token.startswith(b"(") and token.endswith(b")"):
        token = token[1:-1]
    result = bytearray()
    index = 0
    while index < len(token):
        value = token[index]
        if value != 92:
            result.append(value)
            index += 1
            continue
        index += 1
        if index >= len(token):
            break
        escaped = token[index]
        mapping = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
        if escaped in mapping:
            result.append(mapping[escaped])
            index += 1
            continue
        if 48 <= escaped <= 55:
            octal = bytes([escaped])
            index += 1
            for _ in range(2):
                if index < len(token) and 48 <= token[index] <= 55:
                    octal += bytes([token[index]])
                    index += 1
                else:
                    break
            result.append(int(octal, 8))
            continue
        result.append(escaped)
        index += 1
    return result.decode("utf-8", errors="replace")


def parse_rss_item(raw_text: str, record_payload: dict | None = None) -> dict:
    payload, input_format, error = _rss_item_payload_from_text(raw_text)
    if error is not None:
        return error
    payload = payload or {}
    record_payload = record_payload or {}

    title = _rss_payload_text(payload, "title")
    link = _rss_payload_text(payload, "link", "url", "source_uri")
    summary = _rss_payload_text(payload, "summary", "description", "content", "body") or title
    raw_published_at = _rss_payload_text(payload, "published_at", "published", "pubDate", "updated", "time")
    guid = _rss_payload_text(payload, "guid", "id")
    feed_url = _rss_payload_text(payload, "feed_url") or _rss_payload_text(record_payload, "feed_url")
    source_uri = _rss_payload_text(payload, "source_uri") or link or feed_url

    missing_fields = [field for field, value in (("title", title), ("link", link)) if not value]
    if missing_fields:
        return {
            "status": "parse_error",
            "error_code": "RSS_ITEM_REQUIRED_FIELD_MISSING",
            "error_message": "RSS item is missing required title or link.",
            "missing_fields": missing_fields,
            "title": title,
            "link": link,
            "summary": summary,
            "raw_published_at": raw_published_at,
            "guid": guid,
            "feed_url": feed_url,
            "source_uri": source_uri,
            "input_format": input_format,
        }

    published_at = None
    if raw_published_at:
        published_at = _rss_timestamp_iso(raw_published_at)
        if published_at is None:
            return {
                "status": "parse_error",
                "error_code": "RSS_ITEM_TIME_INVALID",
                "error_message": "RSS item published time could not be parsed.",
                "missing_fields": [],
                "title": title,
                "link": link,
                "summary": summary,
                "raw_published_at": raw_published_at,
                "guid": guid,
                "feed_url": feed_url,
                "source_uri": source_uri,
                "input_format": input_format,
            }

    link_hash = _hash(link)
    identity_source = "guid" if guid else "link_hash"
    rss_item_key = f"guid:{guid}" if guid else f"link:{link_hash}"
    return {
        "status": "parsed",
        "title": title,
        "link": link,
        "summary": summary or title,
        "published_at": published_at,
        "raw_published_at": raw_published_at,
        "guid": guid,
        "link_hash": link_hash,
        "rss_item_key": rss_item_key,
        "identity_source": identity_source,
        "feed_url": feed_url,
        "source_uri": source_uri,
        "input_format": input_format,
        "missing_fields": [],
    }


def _rss_item_payload_from_text(raw_text: str) -> tuple[dict | None, str | None, dict | None]:
    text = (raw_text or "").strip()
    if not text:
        return None, None, {"status": "parse_error", "error_code": "RSS_ITEM_CONTENT_EMPTY", "error_message": "RSS raw record payload is empty.", "missing_fields": [], "input_format": None}
    if text[0] in "[{":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            return None, "json", {"status": "parse_error", "error_code": "RSS_ITEM_JSON_INVALID", "error_message": f"RSS item JSON is invalid: {error.msg}", "missing_fields": [], "input_format": "json"}
        if isinstance(payload, dict):
            return payload, "json", None
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            return payload[0], "json", None
        return None, "json", {"status": "parse_error", "error_code": "RSS_ITEM_JSON_INVALID", "error_message": "RSS item JSON root must be an object or single-item object array.", "missing_fields": [], "input_format": "json"}
    if text.startswith("<"):
        try:
            root = ElementTree.fromstring(text.encode("utf-8"))
        except ElementTree.ParseError as error:
            return None, "xml", {"status": "parse_error", "error_code": "RSS_ITEM_XML_INVALID", "error_message": f"RSS item XML is invalid: {error}", "missing_fields": [], "input_format": "xml"}
        element = _rss_item_element_from_xml(root)
        if element is None:
            return None, "xml", {"status": "parse_error", "error_code": "RSS_ITEM_XML_INVALID", "error_message": "RSS item XML does not contain an item or entry element.", "missing_fields": [], "input_format": "xml"}
        atom = _strip_xml_namespace(element.tag).lower() == "entry"
        payload = {
            "title": _xml_text(element, "title"),
            "link": _xml_link(element),
            "guid": _xml_text(element, "id") if atom else _xml_text(element, "guid"),
            "published_at": (_xml_text(element, "updated") or _xml_text(element, "published")) if atom else (_xml_text(element, "pubDate") or _xml_text(element, "updated")),
            "summary": _xml_text(element, "summary") or _xml_text(element, "description") or _xml_text(element, "content") or _xml_text(element, "encoded"),
        }
        return payload, "xml", None
    return None, "text", {"status": "parse_error", "error_code": "RSS_ITEM_FORMAT_UNSUPPORTED", "error_message": "RSS item parser expects JSON or XML raw payload.", "missing_fields": [], "input_format": "text"}


def _rss_item_element_from_xml(root: ElementTree.Element) -> ElementTree.Element | None:
    tag = _strip_xml_namespace(root.tag).lower()
    if tag in {"item", "entry"}:
        return root
    if tag == "rss":
        channel = root.find("channel")
        if channel is None:
            return None
        return next((child for child in list(channel) if _strip_xml_namespace(child.tag).lower() == "item"), None)
    if tag == "feed":
        return next((child for child in list(root) if _strip_xml_namespace(child.tag).lower() == "entry"), None)
    return None


def _rss_payload_text(payload: dict | None, *keys: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None or isinstance(value, (dict, list)):
            continue
        text = _html_text(str(value))
        if text:
            return text
    return None


def _rss_timestamp_iso(value: str) -> str | None:
    parsed = _rss_occurred_at(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_json_by_mapping(raw_text: str, mapping: dict[str, str]) -> dict:
    try:
        payload = json.loads(raw_text or "")
    except json.JSONDecodeError as error:
        return {
            "status": "mapping_error",
            "error_code": "JSON_MAPPING_INVALID",
            "error_message": f"Raw record content is not valid JSON: {error.msg}",
            "missing_fields": [],
            "mapped_fields": {},
        }
    if not isinstance(payload, dict):
        return {
            "status": "mapping_error",
            "error_code": "JSON_MAPPING_INVALID",
            "error_message": "Raw record JSON root must be an object.",
            "missing_fields": [],
            "mapped_fields": {},
        }
    mapped_fields: dict[str, object] = {}
    missing_fields: list[str] = []
    for field, path in mapping.items():
        found, value = _json_mapping_path_value(payload, path)
        if not found or value in (None, ""):
            if field in {"title", "body"}:
                missing_fields.append(field)
            continue
        mapped_fields[field] = value
    for field in ("title", "body"):
        if field not in mapped_fields and field not in missing_fields:
            missing_fields.append(field)
    if missing_fields:
        return {
            "status": "mapping_error",
            "error_code": "JSON_MAPPING_FIELD_MISSING",
            "error_message": "Required JSON mapping fields are missing.",
            "missing_fields": missing_fields,
            "mapped_fields": mapped_fields,
            "title": mapped_fields.get("title"),
            "body": mapped_fields.get("body"),
            "published_at": mapped_fields.get("published_at"),
        }
    return {
        "status": "parsed",
        "title": mapped_fields.get("title"),
        "body": mapped_fields.get("body"),
        "published_at": mapped_fields.get("published_at"),
        "mapped_fields": mapped_fields,
    }


def _json_mapping_path_value(payload: object, path: str) -> tuple[bool, object | None]:
    if path == "$":
        return True, payload
    if not path.startswith("$."):
        return False, None
    current: object = payload
    for part in path[2:].split("."):
        if "[" in part and part.endswith("]"):
            name, index_text = part[:-1].split("[", 1)
            if name:
                if not isinstance(current, dict) or name not in current:
                    return False, None
                current = current[name]
            try:
                index = int(index_text)
            except ValueError:
                return False, None
            if not isinstance(current, list) or index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def score_clean_record_quality(
    record: models.RawRecord,
    raw_payload: models.RawRecordPayload | None,
    source: models.DataSource | None,
    run_id: str,
    algorithm_run_id: str,
    rule_version: str,
) -> dict:
    issues: list[dict] = []
    completeness = 1.0
    title = (record.title or "").strip()
    content_text = (raw_payload.content_text if raw_payload is not None else title).strip()

    def add_issue(issue_type: str, severity: str, message: str, dimension: str, penalty: float = 0.0, payload: dict | None = None) -> None:
        nonlocal completeness
        if dimension == "completeness" and penalty:
            completeness -= penalty
        issues.append(
            {
                "issue_type": issue_type,
                "severity": severity,
                "message": message,
                "payload": _redact_sensitive_payload(
                    {
                        "dimension": dimension,
                        "penalty": round(float(penalty), 4),
                        "algorithm_name": SCORE_CLEAN_RECORD_QUALITY_NAME,
                        "algorithm_version": rule_version,
                    }
                    | dict(payload or {})
                ),
            }
        )

    if not record.city_id:
        add_issue("missing_city", "warning", "Raw record has no city_id.", "completeness", 0.25)
    if len(title) < 4:
        add_issue("short_title", "warning", "Raw record title is too short for downstream extraction.", "completeness", 0.15, {"title_length": len(title)})
    if len(content_text) < 20:
        add_issue("short_content", "warning", "Raw record content is too short for reliable evidence extraction.", "completeness", 0.15, {"content_length": len(content_text)})
    if raw_payload is None:
        add_issue("missing_raw_payload", "warning", "Raw record has no persisted payload body.", "completeness", 0.1)
    elif raw_payload.content_text != raw_payload.masked_text:
        add_issue("sensitive_masked", "info", "Sensitive text was masked for display.", "privacy", 0.0)
    if not record.occurred_at:
        add_issue("missing_occurred_at", "warning", "Raw record has no occurred_at timestamp.", "completeness", 0.1)

    completeness = _clamp_quality_score(completeness)
    freshness, freshness_payload = _quality_freshness_score(record.occurred_at)
    if freshness_payload.get("status") == "stale":
        add_issue("stale_occurred_at", "warning", "Raw record occurred_at is stale for first-phase monitoring.", "freshness", 0.0, freshness_payload)
    if freshness_payload.get("status") == "missing":
        freshness = min(freshness, 0.4)
    trust_assignment = assign_source_trust(record, source)
    trust = _clamp_quality_score(float(trust_assignment["trust_score"]))
    if trust < 0.4:
        add_issue(
            "low_source_trust",
            "warning",
            "Source trust is below the reliable evidence threshold.",
            "trust",
            0.0,
            {"trust_score": trust, "trust_source": trust_assignment["trust_source"], "source_type": trust_assignment["source_type"]},
        )
    overall = _clamp_quality_score((completeness * 0.45) + (freshness * 0.25) + (trust * 0.30))
    scores = {
        "completeness": completeness,
        "freshness": freshness,
        "trust": trust,
        "overall": overall,
    }
    quality_band = _quality_band(overall)
    score_state = {
        "status": "completed",
        "data_quality_run_id": run_id,
        "algorithm_run_id": algorithm_run_id,
        "algorithm_name": SCORE_CLEAN_RECORD_QUALITY_NAME,
        "algorithm_version": rule_version,
        "scores": scores,
        "quality_band": quality_band,
        "issue_types": [issue["issue_type"] for issue in issues],
        "issue_count": len(issues),
        "trust": {
            "trust_source": trust_assignment["trust_source"],
            "trust_band": trust_assignment["trust_band"],
            "trust_score": trust,
            "source_policy_ref": trust_assignment["source_policy_ref"],
        },
        "freshness": freshness_payload,
        "input_refs": [
            {"object_type": "raw_record", "object_id": record.id, "object_version": record.content_hash},
            {"object_type": "data_source", "object_id": record.data_source_id},
        ],
        "scored_at": _now().isoformat(),
        "synthetic": record.is_synthetic,
    }
    return {
        "raw_record_id": record.id,
        "data_source_id": record.data_source_id,
        "source_type": record.source_type,
        "scores": scores,
        "quality_band": quality_band,
        "issue_types": score_state["issue_types"],
        "issue_count": len(issues),
        "issues": issues,
        "score_state": score_state,
    }


def _quality_freshness_score(occurred_at: datetime | None) -> tuple[float, dict]:
    if occurred_at is None:
        return 0.4, {"status": "missing", "age_days": None}
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    age_days = max(0, int((_now() - occurred_at.astimezone(timezone.utc)).total_seconds() // 86400))
    if age_days <= 30:
        score = 1.0
        status = "fresh"
    elif age_days <= 90:
        score = 0.85
        status = "recent"
    elif age_days <= 180:
        score = 0.7
        status = "aging"
    elif age_days <= 365:
        score = 0.5
        status = "old"
    elif age_days <= 730:
        score = 0.3
        status = "stale"
    else:
        score = 0.2
        status = "stale"
    return score, {"status": status, "age_days": age_days}


def _quality_band(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.7:
        return "usable"
    if score >= 0.5:
        return "review"
    return "blocked"


def _clamp_quality_score(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _quality_score_summary(results: list[dict]) -> dict:
    if not results:
        return {
            "score_count": 0,
            "average_overall": 0,
            "average_completeness": 0,
            "average_freshness": 0,
            "average_trust": 0,
            "min_overall": 0,
            "max_overall": 0,
            "band_counts": {},
        }
    band_counts: dict[str, int] = {}
    for result in results:
        band = result["quality_band"]
        band_counts[band] = band_counts.get(band, 0) + 1
    count = len(results)
    overall_scores = [float(result["scores"]["overall"]) for result in results]
    return {
        "score_count": count,
        "average_overall": round(sum(overall_scores) / count, 4),
        "average_completeness": round(sum(float(result["scores"]["completeness"]) for result in results) / count, 4),
        "average_freshness": round(sum(float(result["scores"]["freshness"]) for result in results) / count, 4),
        "average_trust": round(sum(float(result["scores"]["trust"]) for result in results) / count, 4),
        "min_overall": round(min(overall_scores), 4),
        "max_overall": round(max(overall_scores), 4),
        "band_counts": band_counts,
    }


def _quality_issue_type_counts(results: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for result in results:
        for issue_type in result.get("issue_types", []):
            counts[issue_type] = counts.get(issue_type, 0) + 1
    return counts


def _raw_record_payloads_by_id(session: Session, record_ids: list[str], chunk_size: int = SQL_IN_CHUNK_SIZE) -> dict[str, models.RawRecordPayload]:
    payloads: dict[str, models.RawRecordPayload] = {}
    for offset in range(0, len(record_ids), chunk_size):
        chunk = record_ids[offset : offset + chunk_size]
        if not chunk:
            continue
        for item in session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id.in_(chunk))).scalars():
            payloads[item.raw_record_id] = item
    return payloads


def _serialize_quality_score_result(result: dict) -> dict:
    return {
        "raw_record_id": result["raw_record_id"],
        "data_source_id": result["data_source_id"],
        "source_type": result["source_type"],
        "scores": result["scores"],
        "quality_score": result["scores"]["overall"],
        "quality_band": result["quality_band"],
        "issue_types": result["issue_types"],
        "issue_count": result["issue_count"],
    }


def _quality_issue(run_id: str, tenant_id: str, raw_record_id: str, issue_type: str, severity: str, message: str, payload: dict | None = None) -> models.RawRecordQualityIssue:
    return models.RawRecordQualityIssue(id=_id("QISS"), tenant_id=tenant_id, data_quality_run_id=run_id, raw_record_id=raw_record_id, issue_type=issue_type, severity=severity, message=message, payload=_redact_sensitive_payload(payload or {}))


def _create_failed_run(session: Session, job: models.CollectionJob, source: models.DataSource, trace_id: str, code: str, message: str) -> models.CollectionRun:
    run = models.CollectionRun(
        id=_id("CRUN"),
        collection_job_id=job.id,
        data_source_id=source.id,
        status="failed",
        record_count=0,
        error_code=code,
        error_message=message,
        created_at=_now(),
        trace_id=trace_id,
        payload={},
    )
    session.add(run)
    session.add(models.OpsErrorQueue(id=_id("ERRQ"), source="collection_run", severity="warning", status="open", message=message, payload={"collection_run_id": run.id, "error_code": code}))
    return run


def _retry_policy_config(policy: dict | None) -> dict:
    configured = policy.get("retry_policy") if isinstance(policy, dict) and isinstance(policy.get("retry_policy"), dict) else {}
    max_attempts = _coerce_positive_int(configured.get("max_attempts"), 3) or 3
    initial_delay_seconds = _coerce_positive_int(configured.get("initial_delay_seconds") or configured.get("base_delay_seconds"), 60) or 60
    multiplier_raw = configured.get("multiplier", 2)
    try:
        multiplier = float(multiplier_raw)
    except (TypeError, ValueError):
        multiplier = 2.0
    if multiplier < 1:
        multiplier = 1.0
    max_delay_seconds = _coerce_positive_int(configured.get("max_delay_seconds"), 3600) or 3600
    jitter_seconds = _coerce_positive_int(configured.get("jitter_seconds"), 0)
    return {
        "enabled": bool(configured.get("enabled", True)),
        "backoff_strategy": "exponential",
        "max_attempts": max_attempts,
        "initial_delay_seconds": max(initial_delay_seconds, 1),
        "multiplier": multiplier,
        "max_delay_seconds": max(max_delay_seconds, 1),
        "jitter_seconds": jitter_seconds,
    }


def _retry_attempt_for_source_error(session: Session, source_id: str, error_code: str) -> int:
    rows = session.execute(select(models.OpsRetryQueue).where(models.OpsRetryQueue.target_type == "import_run")).scalars()
    attempts = [
        row.attempts
        for row in rows
        if (row.payload or {}).get("data_source_id") == source_id and (row.payload or {}).get("error_code") == error_code
    ]
    return (max(attempts) if attempts else 0) + 1


def _retry_delay_seconds(config: dict, attempt: int, key: str) -> int:
    base_delay = int(config["initial_delay_seconds"] * (float(config["multiplier"]) ** max(attempt - 1, 0)))
    delay = min(base_delay, int(config["max_delay_seconds"]))
    jitter = int(config.get("jitter_seconds") or 0)
    if jitter > 0:
        delay += int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % (jitter + 1)
    return max(delay, 1)


def _apply_retry_policy(
    session: Session,
    run: models.CollectionRun,
    import_run: models.ImportRun,
    source: models.DataSource,
    code: str,
    message: str,
    retryable: bool,
) -> dict:
    config = _retry_policy_config(source.policy or {})
    classification = "transient" if retryable and config["enabled"] else "permanent"
    attempt = _retry_attempt_for_source_error(session, source.id, code) if classification == "transient" else 0
    scheduled = classification == "transient" and attempt <= int(config["max_attempts"])
    next_delay_seconds = _retry_delay_seconds(config, attempt, import_run.id) if scheduled else None
    now = _now()
    next_run_at = now + timedelta(seconds=next_delay_seconds or 0) if scheduled else None
    retry_state = {
        **config,
        "classification": classification,
        "retryable": bool(retryable),
        "scheduled": scheduled,
        "attempt": attempt,
        "next_delay_seconds": next_delay_seconds,
        "next_run_at": next_run_at.isoformat() if next_run_at else None,
        "error_code": code,
        "message": message,
        "data_source_id": source.id,
        "collection_run_id": run.id,
        "import_run_id": import_run.id,
    }
    run.payload = {**(run.payload or {}), "retry_policy": retry_state}
    import_run.payload = {**(import_run.payload or {}), "retry_policy": retry_state}
    if scheduled:
        session.add(
            models.OpsRetryQueue(
                id=_id("RETQ"),
                target_type="import_run",
                target_id=import_run.id,
                status="pending",
                attempts=attempt,
                next_run_at=next_run_at,
                payload={"error_code": code, "data_source_id": source.id, "collection_run_id": run.id, "import_run_id": import_run.id, "retry_policy": retry_state},
            )
        )
        session.add(
            models.CollectionRunEvent(
                id=_id("CREV"),
                collection_run_id=run.id,
                event_type="retry_backoff_scheduled",
                status="pending",
                payload=retry_state,
            )
        )
    else:
        session.add(
            models.CollectionRunEvent(
                id=_id("CREV"),
                collection_run_id=run.id,
                event_type="retry_not_scheduled",
                status="failed",
                payload=retry_state,
            )
        )
    return retry_state


def _update_health(session: Session, source_id: str, run_id: str, success: bool, count: int = 0, error_code: str | None = None) -> None:
    health = session.execute(select(models.SourceHealth).where(models.SourceHealth.data_source_id == source_id)).scalar_one_or_none()
    if health is None:
        health = models.SourceHealth(id=_id("SH"), data_source_id=source_id, status="unknown", payload={})
        session.add(health)
    health.last_run_id = run_id
    if success:
        health.status = "healthy"
        health.success_count += count
    else:
        health.status = "degraded"
        health.failure_count += 1
        health.last_error_code = error_code


def _set_health_status(session: Session, source_id: str, status: str, error_code: str | None = None) -> None:
    health = session.execute(select(models.SourceHealth).where(models.SourceHealth.data_source_id == source_id)).scalar_one_or_none()
    if health is None:
        health = models.SourceHealth(id=_id("SH"), data_source_id=source_id, status=status, payload={})
        session.add(health)
    health.status = status
    health.last_error_code = error_code


def list_source_health(session: Session) -> list[dict]:
    rows = session.execute(select(models.SourceHealth).order_by(models.SourceHealth.updated_at.desc())).scalars()
    return [serialize_source_health(row) for row in rows]


def get_data_source_health(session: Session, data_source_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    health = session.execute(select(models.SourceHealth).where(models.SourceHealth.data_source_id == source.id)).scalar_one_or_none()
    recent_runs = list(
        session.execute(
            select(models.CollectionRun)
            .where(models.CollectionRun.data_source_id == source.id)
            .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
            .limit(10)
        ).scalars()
    )
    success_runs = [run for run in recent_runs if run.status == "completed"]
    failure_runs = [run for run in recent_runs if run.status in {"failed", "canceled"}]
    runs_by_id = {run.id: run for run in recent_runs}
    last_health_run = runs_by_id.get(health.last_run_id) if health is not None and health.last_run_id else None
    last_success_run = last_health_run if last_health_run is not None and last_health_run.status == "completed" else (success_runs[0] if success_runs else None)
    last_failure_run = last_health_run if last_health_run is not None and last_health_run.status in {"failed", "canceled"} else (failure_runs[0] if failure_runs else None)
    total_runs = len(success_runs) + len(failure_runs)
    failure_count = health.failure_count if health is not None else len(failure_runs)
    success_count = health.success_count if health is not None else len(success_runs)
    error_rate = round((len(failure_runs) / total_runs), 4) if total_runs else 0
    if not recent_runs:
        status = "unknown"
    elif source.status == "disabled":
        status = "disabled"
    elif health is not None:
        status = health.status
    elif failure_runs:
        status = "degraded"
    else:
        status = "healthy"
    page_state = "empty" if not recent_runs else ("degraded" if status in {"degraded", "disabled", "blocked", "unhealthy"} or failure_count else "ready")
    policy = source.policy or {}
    return {
        "data_source_id": source.id,
        "source_health_id": health.id if health is not None else None,
        "status": status,
        "source": serialize_data_source(source),
        "policy_result": evaluate_policy(source.source_type, policy, source.status),
        "operational_state": policy.get("operational_state") if isinstance(policy.get("operational_state"), dict) else None,
        "last_success": serialize_collection_run(last_success_run) if last_success_run is not None else None,
        "last_failure": serialize_collection_run(last_failure_run) if last_failure_run is not None else None,
        "error_rate": error_rate,
        "success_count": success_count,
        "failure_count": failure_count,
        "last_error_code": health.last_error_code if health is not None else (failure_runs[0].error_code if failure_runs else None),
        "last_run_id": health.last_run_id if health is not None else (recent_runs[0].id if recent_runs else None),
        "recent_runs": [serialize_collection_run(run) for run in recent_runs],
        "page_state": page_state,
        "payload": health.payload if health is not None else {},
    }


def get_data_source_cursor_state(session: Session, data_source_id: str, actor: models.User, trace_id: str) -> dict:
    source = get_data_source(session, data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    if source.source_type != "db_import":
        raise _api_error(422, "SOURCE_TYPE_UNSUPPORTED_FOR_CURSOR_STATE", "Cursor state is currently supported for db_import data sources.")
    policy = source.policy or {}
    cursor_state = policy.get("db_import_cursor") if isinstance(policy.get("db_import_cursor"), dict) else {}
    last_scan = policy.get("last_db_import_scan") if isinstance(policy.get("last_db_import_scan"), dict) else None
    cursors: list[dict] = []
    for table_key in sorted(cursor_state):
        table_state = cursor_state.get(table_key)
        if not isinstance(table_state, dict):
            continue
        for cursor_field in sorted(table_state):
            raw_value = table_state.get(cursor_field)
            try:
                current_value = int(raw_value)
            except (TypeError, ValueError):
                current_value = raw_value
            scan_for_cursor = (
                last_scan
                if last_scan is not None
                and last_scan.get("table_key") == table_key
                and last_scan.get("cursor_field") == cursor_field
                else None
            )
            cursors.append(
                {
                    "cursor_scope": "db_import",
                    "table_key": table_key,
                    "table_name": (scan_for_cursor or {}).get("table_name") or table_key.split(".")[-1],
                    "schema_name": (scan_for_cursor or {}).get("schema_name"),
                    "cursor_field": cursor_field,
                    "current_value": current_value,
                    "storage_path": f"data_sources.policy.db_import_cursor.{table_key}.{cursor_field}",
                    "last_scan": scan_for_cursor,
                }
            )
    result = {
        "data_source_id": source.id,
        "source_type": source.source_type,
        "status": source.status,
        "cursor_scope": "db_import",
        "cursor_state": cursor_state,
        "cursor_count": len(cursors),
        "cursors": cursors,
        "last_db_import_scan": last_scan,
        "failure_guard": {
            "failed_runs_do_not_advance_cursor": True,
            "persisted_after_success_only": True,
            "storage_path": "data_sources.policy.db_import_cursor",
        },
        "page_state": "ready" if cursors else "empty",
        "source": serialize_data_source(source),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="data_source.cursor_state.read",
        object_type="data_source",
        object_id=source.id,
        after={"cursor_count": len(cursors), "last_db_import_scan": last_scan, "failure_guard": result["failure_guard"]},
        trace_id=trace_id,
    )
    session.commit()
    return result


def get_data_source_rate_limit(session: Session, data_source_id: str, actor: models.User, channel: str | None = None) -> dict:
    source = get_data_source(session, data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    policy = source.policy or {}
    requested_channel = _normalize_collection_channel(channel)
    config = _source_rate_limit_config(policy)
    delayed_run_candidates = list(
        session.execute(
            select(models.CollectionRun)
            .where(models.CollectionRun.data_source_id == source.id, models.CollectionRun.status == "delayed")
            .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
            .limit(50)
        ).scalars()
    )
    delayed_runs = [
        run
        for run in delayed_run_candidates
        if requested_channel is None or _normalize_collection_channel(((run.payload or {}).get("rate_limit") or {}).get("channel")) == requested_channel
    ][:10]
    now = _now()
    channel_states: dict[str, dict] = {}
    limits = policy.get("channel_rate_limits") if isinstance(policy.get("channel_rate_limits"), dict) else {}
    raw_states = policy.get("channel_rate_limit_state") if isinstance(policy.get("channel_rate_limit_state"), dict) else {}
    for raw_channel in limits:
        normalized_channel = _normalize_collection_channel(raw_channel)
        if not normalized_channel or normalized_channel in channel_states:
            continue
        channel_config = _channel_rate_limit_config(policy, normalized_channel)
        if channel_config is None:
            continue
        channel_state = raw_states.get(normalized_channel) if isinstance(raw_states.get(normalized_channel), dict) else {}
        channel_states[normalized_channel] = _rate_limit_state_view(channel_state, channel_config, now)
    source_policy_candidates = list(
        session.execute(
            select(models.SourcePolicy)
            .where(models.SourcePolicy.data_source_id == source.id)
            .order_by(models.SourcePolicy.created_at.desc(), models.SourcePolicy.id.desc())
            .limit(50)
        ).scalars()
    )

    def latest_policy_for(channel_name: str | None = None) -> models.SourcePolicy | None:
        for row in source_policy_candidates:
            rate_limit = (row.payload or {}).get("rate_limit") if isinstance(row.payload, dict) else None
            row_channel = _normalize_collection_channel(rate_limit.get("channel")) if isinstance(rate_limit, dict) else None
            if channel_name is None or row_channel == channel_name:
                return row
        return None

    if requested_channel and requested_channel in channel_states:
        channel_config = _channel_rate_limit_config(policy, requested_channel)
        state = channel_states[requested_channel]
        status = "limited" if state["used"] >= channel_config["max_runs"] and state["next_allowed_at"] else "available"
        latest_policy = latest_policy_for(requested_channel)
        return {
            "data_source_id": source.id,
            "channel": requested_channel,
            "status": status,
            "config": channel_config,
            "state": {**state, "delayed_count": max(state["delayed_count"], len(delayed_runs))},
            "channel_states": channel_states,
            "recent_delayed_runs": [serialize_collection_run(run) for run in delayed_runs],
            "source_policy": None
            if latest_policy is None
            else {"source_policy_id": latest_policy.id, "status": latest_policy.status, "reason": latest_policy.reason, "payload": latest_policy.payload},
            "page_state": "degraded" if status == "limited" else "ready",
        }
    if config is None and channel_states:
        delayed_count = sum(_coerce_positive_int(state.get("delayed_count")) for state in channel_states.values())
        limited = any(state.get("next_allowed_at") and _coerce_positive_int(state.get("remaining")) == 0 for state in channel_states.values())
        return {
            "data_source_id": source.id,
            "channel": None,
            "status": "limited" if limited else "available",
            "config": None,
            "state": {
                "enabled": True,
                "used": sum(_coerce_positive_int(state.get("used")) for state in channel_states.values()),
                "remaining": sum(_coerce_positive_int(state.get("remaining")) for state in channel_states.values()),
                "delayed_count": max(delayed_count, len(delayed_runs)),
                "next_allowed_at": min((state["next_allowed_at"] for state in channel_states.values() if state.get("next_allowed_at")), default=None),
            },
            "channel_states": channel_states,
            "recent_delayed_runs": [serialize_collection_run(run) for run in delayed_runs],
            "page_state": "degraded" if limited else "ready",
        }
    if config is None:
        return {
            "data_source_id": source.id,
            "channel": requested_channel,
            "status": "unconfigured",
            "config": None,
            "state": {"enabled": False, "used": 0, "remaining": None, "delayed_count": len(delayed_runs)},
            "channel_states": channel_states,
            "recent_delayed_runs": [serialize_collection_run(run) for run in delayed_runs],
            "page_state": "empty",
        }
    state = _rate_limit_state_view(policy.get("rate_limit_state") if isinstance(policy.get("rate_limit_state"), dict) else {}, config, now)
    status = "limited" if state["used"] >= config["max_runs"] and state["next_allowed_at"] else "available"
    latest_policy = latest_policy_for()
    return {
        "data_source_id": source.id,
        "channel": requested_channel,
        "status": status,
        "config": config,
        "state": {**state, "delayed_count": max(state["delayed_count"], len(delayed_runs))},
        "channel_states": channel_states,
        "recent_delayed_runs": [serialize_collection_run(run) for run in delayed_runs],
        "source_policy": None
        if latest_policy is None
        else {"source_policy_id": latest_policy.id, "status": latest_policy.status, "reason": latest_policy.reason, "payload": latest_policy.payload},
        "page_state": "degraded" if status == "limited" else "ready",
    }


def get_collection_channel_quality_metrics(session: Session, channel: str, actor: models.User, trace_id: str) -> dict:
    requested_channel = _normalize_collection_channel(channel)
    if requested_channel not in {
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
    }:
        raise _api_error(404, "CHANNEL_NOT_FOUND", "Collection channel does not exist.")
    started_at = time.perf_counter()
    sources = list(session.execute(select(models.DataSource).where(models.DataSource.tenant_id == actor.tenant_id)).scalars())
    channel_source_ids = [source.id for source in sources if _collection_job_channel(source, {}) == requested_channel]
    aliases = [alias for alias, canonical in COLLECTION_CHANNEL_ALIASES.items() if canonical == requested_channel] + [requested_channel]
    channel_job_filters = [
        models.CollectionJob.payload["collection_channel"].as_string().in_(aliases),
        models.CollectionJob.payload["channel"].as_string().in_(aliases),
    ]
    if channel_source_ids:
        channel_job_filters.append(models.CollectionJob.data_source_id.in_(channel_source_ids))
    channel_job_ids = list(
        session.execute(
            select(models.CollectionJob.id).where(models.CollectionJob.tenant_id == actor.tenant_id, or_(*channel_job_filters))
        ).scalars()
    )
    run_ids = (
        list(session.execute(select(models.CollectionRun.id).where(models.CollectionRun.collection_job_id.in_(channel_job_ids))).scalars())
        if channel_job_ids
        else []
    )
    status_rows = (
        list(
            session.execute(
                select(models.CollectionRun.status, func.count())
                .where(models.CollectionRun.id.in_(run_ids))
                .group_by(models.CollectionRun.status)
            )
        )
        if run_ids
        else []
    )
    run_rows = (
        list(
            session.execute(
                select(
                    models.CollectionRun.id,
                    models.CollectionRun.collection_job_id,
                    models.CollectionRun.data_source_id,
                    models.CollectionRun.status,
                    models.CollectionRun.error_code,
                    models.CollectionRun.record_count,
                    models.CollectionRun.payload,
                    models.CollectionRun.created_at,
                )
                .where(models.CollectionRun.id.in_(run_ids))
                .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
                .limit(20)
            )
        )
        if run_ids
        else []
    )
    raw_record_count = (
        session.execute(
            select(func.count()).select_from(models.RawRecord).where(models.RawRecord.tenant_id == actor.tenant_id, models.RawRecord.collection_run_id.in_(run_ids))
        ).scalar_one()
        if run_ids
        else 0
    )
    issue_rows = (
        list(
            session.execute(
                select(models.RawRecordQualityIssue.issue_type, models.RawRecordQualityIssue.severity, func.count())
                .join(models.RawRecord, models.RawRecord.id == models.RawRecordQualityIssue.raw_record_id)
                .where(
                    models.RawRecord.tenant_id == actor.tenant_id,
                    models.RawRecord.collection_run_id.in_(run_ids),
                    models.RawRecordQualityIssue.tenant_id == actor.tenant_id,
                )
                .group_by(models.RawRecordQualityIssue.issue_type, models.RawRecordQualityIssue.severity)
            )
        )
        if run_ids
        else []
    )
    lineage_count = (
        session.execute(
            select(func.count())
            .select_from(models.LineageEdge)
            .join(models.RawRecord, models.RawRecord.id == models.LineageEdge.to_object_id)
            .where(
                models.LineageEdge.to_object_type == "raw_record",
                models.RawRecord.tenant_id == actor.tenant_id,
                models.RawRecord.collection_run_id.in_(run_ids),
            )
        ).scalar_one()
        if run_ids
        else 0
    )
    events = list(
        session.execute(select(models.CollectionRunEvent.payload).where(models.CollectionRunEvent.collection_run_id.in_(run_ids))).scalars()
    ) if run_ids else []
    status_counts = {status: int(count or 0) for status, count in status_rows}
    run_count = sum(status_counts.values())
    delayed_count = status_counts.get("delayed", 0)
    failed_count = status_counts.get("failed", 0)
    completed_count = status_counts.get("completed", 0)
    deduped_count = 0
    conflict_count = 0
    for payload in events:
        payload = payload if isinstance(payload, dict) else {}
        deduped_count += _metric_int(payload.get("duplicate_count") or payload.get("skipped_existing_count"))
        conflict_count += _metric_int(payload.get("conflict_count"))
    severity_counts: dict[str, int] = {}
    issue_type_counts: dict[str, int] = {}
    quality_issue_count = 0
    for issue_type, severity, count in issue_rows:
        issue_count = int(count or 0)
        quality_issue_count += issue_count
        severity_counts[severity] = severity_counts.get(severity, 0) + issue_count
        issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + issue_count
    serialized_run_rows = [
        {
            "collection_run_id": run_id,
            "collection_job_id": collection_job_id,
            "data_source_id": data_source_id,
            "status": status,
            "error_code": error_code,
            "record_count": record_count,
            "workflow_status": (payload or {}).get("workflow_status") if isinstance(payload, dict) else None,
            "created_at": created_at,
        }
        for run_id, collection_job_id, data_source_id, status, error_code, record_count, payload, created_at in run_rows
    ]
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    summary = {
        "run_count": run_count,
        "completed_run_count": completed_count,
        "failed_run_count": failed_count,
        "delayed_run_count": delayed_count,
        "raw_record_count": int(raw_record_count or 0),
        "quality_issue_count": quality_issue_count,
        "lineage_edge_count": int(lineage_count or 0),
        "deduped_count": deduped_count,
        "conflict_count": conflict_count,
        "issue_type_counts": issue_type_counts,
        "severity_counts": severity_counts,
        "p95_latency_ms": latency_ms,
    }
    page_state = "empty" if not run_count else ("degraded" if failed_count or quality_issue_count else "ready")
    result = {
        "channel": requested_channel,
        "metrics_source": "postgresql",
        "summary": summary,
        "runs": serialized_run_rows,
        "page_state": page_state,
        "generated_at": _now().isoformat(),
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_channel.quality_metrics_read",
        object_type="collection_channel",
        object_id=requested_channel,
        after={"channel": requested_channel, "summary": summary},
        trace_id=trace_id,
    )
    session.commit()
    return result


def get_collection_channel_maintenance(session: Session, actor: models.User, trace_id: str) -> dict:
    started_at = time.perf_counter()
    registry_rows = adapters.collection_channel_registry(DATA_SOURCE_TYPES)
    sources = list(session.execute(select(models.DataSource).where(models.DataSource.tenant_id == actor.tenant_id)).scalars())
    source_ids_by_channel: dict[str, list[str]] = {row["channel"]: [] for row in registry_rows}
    for source in sources:
        channel = _collection_job_channel(source, {})
        if channel in source_ids_by_channel:
            source_ids_by_channel[channel].append(source.id)

    channels: list[dict] = []
    warning_total = 0
    high_failure_count = 0
    missing_metrics_count = 0
    ready_count = 0
    degraded_count = 0
    empty_count = 0
    total_sources = 0
    total_jobs = 0
    total_runs = 0
    total_failed_runs = 0
    total_delayed_runs = 0

    for row in registry_rows:
        channel = row["channel"]
        source_ids = source_ids_by_channel.get(channel, [])
        aliases = [alias for alias, canonical in COLLECTION_CHANNEL_ALIASES.items() if canonical == channel] + [channel]
        job_filters = [
            models.CollectionJob.payload["collection_channel"].as_string().in_(aliases),
            models.CollectionJob.payload["channel"].as_string().in_(aliases),
        ]
        if source_ids:
            job_filters.append(models.CollectionJob.data_source_id.in_(source_ids))
        channel_job_rows = list(
            session.execute(
                select(models.CollectionJob.id, models.CollectionJob.data_source_id).where(models.CollectionJob.tenant_id == actor.tenant_id, or_(*job_filters))
            )
        )
        channel_job_ids = [job_id for job_id, _data_source_id in channel_job_rows]
        job_source_ids = {data_source_id for _job_id, data_source_id in channel_job_rows if data_source_id in source_ids}
        source_without_job_count = len(set(source_ids) - job_source_ids)
        status_rows = (
            list(
                session.execute(
                    select(models.CollectionRun.status, func.count())
                    .where(models.CollectionRun.collection_job_id.in_(channel_job_ids))
                    .group_by(models.CollectionRun.status)
                )
            )
            if channel_job_ids
            else []
        )
        error_rows = (
            list(
                session.execute(
                    select(models.CollectionRun.error_code, func.count())
                    .where(models.CollectionRun.collection_job_id.in_(channel_job_ids), models.CollectionRun.error_code.is_not(None))
                    .group_by(models.CollectionRun.error_code)
                    .order_by(func.count().desc(), models.CollectionRun.error_code.asc())
                    .limit(5)
                )
            )
            if channel_job_ids
            else []
        )
        run_job_ids = (
            set(session.execute(select(models.CollectionRun.collection_job_id).where(models.CollectionRun.collection_job_id.in_(channel_job_ids)).distinct()).scalars())
            if channel_job_ids
            else set()
        )
        job_without_run_count = len(set(channel_job_ids) - run_job_ids)
        last_run_at = (
            session.execute(select(func.max(models.CollectionRun.created_at)).where(models.CollectionRun.collection_job_id.in_(channel_job_ids))).scalar_one()
            if channel_job_ids
            else None
        )
        config_rows = (
            list(
                session.execute(
                    select(func.count(), func.max(models.DataSourceVersion.version), func.max(models.DataSourceVersion.published_at))
                    .where(models.DataSourceVersion.tenant_id == actor.tenant_id, models.DataSourceVersion.data_source_id.in_(source_ids), models.DataSourceVersion.status == "published")
                )
            )
            if source_ids
            else [(0, None, None)]
        )
        published_config_count, latest_config_version, latest_published_at = config_rows[0]
        published_config_count = int(published_config_count or 0)
        source_count = len(source_ids)
        active_source_count = sum(1 for source in sources if source.id in source_ids and source.status == "active")
        job_count = len(channel_job_ids)
        status_counts = {status: int(count or 0) for status, count in status_rows}
        run_count = sum(status_counts.values())
        completed_count = status_counts.get("completed", 0)
        failed_count = status_counts.get("failed", 0)
        delayed_count = status_counts.get("delayed", 0)
        failure_rate = round(failed_count / run_count, 4) if run_count else 0.0
        warnings: list[dict] = []
        if source_count == 0 or job_count == 0 or run_count == 0 or source_without_job_count or job_without_run_count:
            warnings.append(
                {
                    "code": "CHANNEL_MAINTENANCE_METRICS_MISSING",
                    "message": "Channel has no complete source/job/run maintenance evidence yet.",
                    "details": {
                        "source_count": source_count,
                        "job_count": job_count,
                        "run_count": run_count,
                        "source_without_job_count": source_without_job_count,
                        "job_without_run_count": job_without_run_count,
                    },
                }
            )
        if source_count > published_config_count:
            warnings.append(
                {
                    "code": "CONFIG_VERSION_MISSING",
                    "message": "One or more channel sources have no published configuration version.",
                    "details": {"source_count": source_count, "published_config_count": published_config_count},
                }
            )
        if run_count >= 3 and failure_rate >= 0.25:
            warnings.append(
                {
                    "code": "HIGH_FAILURE_RATE",
                    "message": "Channel failure rate exceeds the S2 maintenance threshold.",
                    "details": {"failure_rate": failure_rate, "failed_run_count": failed_count, "run_count": run_count},
                }
            )
        for registry_warning in row.get("warnings") or []:
            warnings.append(
                {
                    "code": registry_warning.get("code", "CHANNEL_REGISTRY_WARNING"),
                    "message": registry_warning.get("message", "Channel registry warning."),
                    "details": {"registry_status": row.get("status")},
                }
            )
        try:
            schema = adapters.get_collection_channel_schema(channel)
            code_version = {
                "source": "collection_channel_schema",
                "version": schema["version"],
                "adapter_source_type": schema["adapter_source_type"],
                "schema_status": schema["status"],
            }
        except KeyError:
            code_version = {
                "source": "adapter_registry",
                "version": f"{row['adapter_source_type']}:required_methods_v1",
                "adapter_source_type": row["adapter_source_type"],
                "schema_status": "not_registered",
            }
        status = "empty" if not run_count else ("degraded" if warnings else "ready")
        if status == "ready":
            ready_count += 1
        elif status == "degraded":
            degraded_count += 1
        else:
            empty_count += 1
        if failure_rate >= 0.25 and run_count:
            high_failure_count += 1
        if any(warning["code"] == "CHANNEL_MAINTENANCE_METRICS_MISSING" for warning in warnings):
            missing_metrics_count += 1
        warning_total += len(warnings)
        total_sources += source_count
        total_jobs += job_count
        total_runs += run_count
        total_failed_runs += failed_count
        total_delayed_runs += delayed_count
        channels.append(
            {
                "channel": channel,
                "label": row["label"],
                "status": status,
                "source_count": source_count,
                "active_source_count": active_source_count,
                "job_count": job_count,
                "run_count": run_count,
                "completed_run_count": completed_count,
                "failed_run_count": failed_count,
                "delayed_run_count": delayed_count,
                "failure_rate": failure_rate,
                "maintenance_cost_score": failed_count * 10 + delayed_count * 3 + len(warnings) * 5,
                "top_error_codes": [{"error_code": error_code, "count": int(count or 0)} for error_code, count in error_rows],
                "code_version": code_version,
                "config_version": {
                    "published_config_count": published_config_count,
                    "latest_version": latest_config_version,
                    "latest_published_at": latest_published_at.isoformat() if latest_published_at else None,
                },
                "test_coverage": {
                    "status": "instrumented",
                    "api_test": "test_s2_channel_maintenance_dashboard_returns_cost_metrics_and_alerts",
                    "browser_smoke": "s2-source-306-channel-maintenance-dashboard",
                    "third_party_review": "required_before_freeze",
                },
                "warnings": warnings,
                "last_run_at": last_run_at.isoformat() if last_run_at else None,
            }
        )

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    summary = {
        "channel_count": len(channels),
        "ready_channel_count": ready_count,
        "degraded_channel_count": degraded_count,
        "empty_channel_count": empty_count,
        "warning_count": warning_total,
        "high_failure_channel_count": high_failure_count,
        "missing_metrics_channel_count": missing_metrics_count,
        "source_count": total_sources,
        "job_count": total_jobs,
        "run_count": total_runs,
        "failed_run_count": total_failed_runs,
        "delayed_run_count": total_delayed_runs,
        "p95_latency_ms": latency_ms,
    }
    page_state = "empty" if not total_runs else ("degraded" if warning_total else "ready")
    result = {
        "tenant_id": actor.tenant_id,
        "metrics_source": "postgresql",
        "summary": summary,
        "channels": channels,
        "page_state": page_state,
        "generated_at": _now().isoformat(),
    }
    snapshot = models.MetricsSnapshot(id=_id("MSNP"), tenant_id=actor.tenant_id, metric_scope="collection_channels:maintenance", payload={}, captured_at=_now())
    session.add(snapshot)
    session.flush()
    result["metrics_snapshot_id"] = snapshot.id
    snapshot.payload = result
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="collection_channel.maintenance_read",
        object_type="collection_channel_maintenance",
        object_id="collection-channels/maintenance",
        after={"summary": summary, "metrics_snapshot_id": snapshot.id},
        trace_id=trace_id,
    )
    session.commit()
    return result


def list_raw_records(session: Session, actor: models.User, limit: int = 50) -> list[dict]:
    safe_limit = min(max(limit, 1), 100)
    rows = session.execute(
        select(models.RawRecord)
        .where(models.RawRecord.tenant_id == actor.tenant_id)
        .order_by(models.RawRecord.created_at.desc(), models.RawRecord.id.desc())
        .limit(safe_limit)
    ).scalars()
    return [serialize_raw_record(row) for row in rows]


def list_clean_records(
    session: Session,
    actor: models.User,
    status: str | None = None,
    data_source_id: str | None = None,
    source_type: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    trace_id: str | None = None,
) -> tuple[list[dict], dict]:
    allowed_statuses = {
        "raw",
        "cleaned",
        "collected",
        "pending",
        "failed",
        "quarantined",
        "dedupe_candidate",
        "confirmed_duplicate",
        "duplicate",
        "kept",
        "split_candidate",
        "embedding_failed",
        "valid",
        "invalid",
        "review_required",
    }
    if status and status not in allowed_statuses:
        raise _api_error(422, "CLEAN_RECORD_STATUS_INVALID", "Unsupported clean record status filter.")
    if source_type and source_type not in {item["source_type"] for item in DATA_SOURCE_TYPES}:
        raise _api_error(422, "CLEAN_RECORD_SOURCE_TYPE_INVALID", "Unsupported clean record source type filter.")
    if data_source_id:
        source = session.get(models.DataSource, data_source_id)
        if source is None:
            raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
        if source.tenant_id != actor.tenant_id:
            raise _api_error(403, "FORBIDDEN", "Data source belongs to another tenant.")

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    from_dt = _parse_optional_datetime(created_from, "CLEAN_RECORD_CREATED_FROM_INVALID")
    to_dt = _parse_optional_datetime(created_to, "CLEAN_RECORD_CREATED_TO_INVALID")
    filters = [models.RawRecord.tenant_id == actor.tenant_id]
    if data_source_id:
        filters.append(models.RawRecord.data_source_id == data_source_id)
    if source_type:
        filters.append(models.RawRecord.source_type == source_type)
    if from_dt is not None:
        filters.append(models.RawRecord.created_at >= from_dt)
    if to_dt is not None:
        filters.append(models.RawRecord.created_at <= to_dt)
    if status:
        filters.append(_clean_record_status_filter(status))

    total = session.execute(select(func.count()).select_from(models.RawRecord).where(*filters)).scalar_one()
    records = list(
        session.execute(
            select(models.RawRecord)
            .where(*filters)
            .order_by(models.RawRecord.created_at.desc(), models.RawRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    raw_ids = [record.id for record in records]
    payloads = {
        item.raw_record_id: item
        for item in session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id.in_(raw_ids))).scalars()
    } if raw_ids else {}
    normalizations: dict[str, models.RawRecordNormalization] = {}
    if raw_ids:
        for item in session.execute(
            select(models.RawRecordNormalization)
            .where(models.RawRecordNormalization.raw_record_id.in_(raw_ids))
            .order_by(models.RawRecordNormalization.created_at.desc(), models.RawRecordNormalization.id.desc())
        ).scalars():
            normalizations.setdefault(item.raw_record_id, item)
    quality_counts = dict(
        session.execute(
            select(models.RawRecordQualityIssue.raw_record_id, func.count(models.RawRecordQualityIssue.id))
            .where(models.RawRecordQualityIssue.raw_record_id.in_(raw_ids))
            .group_by(models.RawRecordQualityIssue.raw_record_id)
        ).all()
    ) if raw_ids else {}
    items = [
        serialize_clean_record(record, payloads.get(record.id), normalizations.get(record.id), int(quality_counts.get(record.id, 0)))
        for record in records
    ]
    status_counts: dict[str, int] = {}
    for item in items:
        clean_status = str(item["clean_status"])
        status_counts[clean_status] = status_counts.get(clean_status, 0) + 1
    filters_payload = {
        "status": status,
        "data_source_id": data_source_id,
        "source_type": source_type,
        "created_from": created_from,
        "created_to": created_to,
    }
    pagination = {"page": page, "page_size": page_size, "total": total}
    meta = {
        "pagination": pagination,
        "filters": filters_payload,
        "page_state": "ready" if items else "empty",
        "status_counts": status_counts,
        "status_counts_scope": "page",
        "summary": {"returned_count": len(items), "total": total, "content_redacted": True, "source": "postgresql"},
        "required_permission": "data_source:read",
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="clean_record.list",
        object_type="clean_record",
        object_id="list",
        after={"filters": filters_payload, "pagination": pagination, "returned_count": len(items)},
        trace_id=trace_id,
    )
    session.commit()
    return items, meta


def get_clean_record_detail(session: Session, clean_record_id: str, actor: models.User, trace_id: str) -> dict:
    record, raw_payload = _raw_record_with_payload(session, clean_record_id, actor)
    normalizations = list(
        session.execute(
            select(models.RawRecordNormalization)
            .where(models.RawRecordNormalization.raw_record_id == record.id)
            .order_by(models.RawRecordNormalization.created_at.desc(), models.RawRecordNormalization.id.desc())
        ).scalars()
    )
    latest_normalization = normalizations[0] if normalizations else None
    quality_state = (record.payload or {}).get(SCORE_CLEAN_RECORD_QUALITY_NAME) if isinstance((record.payload or {}).get(SCORE_CLEAN_RECORD_QUALITY_NAME), dict) else {}
    current_quality_run_id = quality_state.get("data_quality_run_id") if isinstance(quality_state.get("data_quality_run_id"), str) else None
    quality_statement = select(models.RawRecordQualityIssue).where(models.RawRecordQualityIssue.raw_record_id == record.id)
    if current_quality_run_id:
        quality_statement = quality_statement.where(models.RawRecordQualityIssue.data_quality_run_id == current_quality_run_id)
    quality_issues = list(
        session.execute(
            quality_statement.order_by(models.RawRecordQualityIssue.created_at.desc(), models.RawRecordQualityIssue.id.desc())
        ).scalars()
    )
    object_refs = [("raw_record", record.id)]
    object_refs.extend(("raw_record_normalization", item.id) for item in normalizations)
    object_refs.extend(("normalization_run", item.normalization_run_id) for item in normalizations)
    lineage_filters = [
        ((models.LineageEdge.from_object_type == object_type) & (models.LineageEdge.from_object_id == object_id))
        | ((models.LineageEdge.to_object_type == object_type) & (models.LineageEdge.to_object_id == object_id))
        for object_type, object_id in object_refs
        if object_id
    ]
    lineage_edges = list(
        session.execute(
            select(models.LineageEdge)
            .where(or_(*lineage_filters))
            .order_by(models.LineageEdge.created_at.desc(), models.LineageEdge.id.desc())
            .limit(100)
        ).scalars()
    ) if lineage_filters else []
    signal_ids = {
        edge.to_object_id
        for edge in lineage_edges
        if edge.from_object_type == "raw_record" and edge.from_object_id == record.id and edge.to_object_type == "signal"
    } | {
        edge.from_object_id
        for edge in lineage_edges
        if edge.to_object_type == "raw_record" and edge.to_object_id == record.id and edge.from_object_type == "signal"
    }
    signals = list(session.execute(select(models.Signal).where(models.Signal.id.in_(signal_ids))).scalars()) if signal_ids else []
    clean_record = serialize_clean_record(record, raw_payload, latest_normalization, len(quality_issues))
    raw_detail = _serialize_raw_record_redacted_detail(record, raw_payload)
    lineage_payload = [serialize_lineage(edge) for edge in lineage_edges]
    detail = {
        "clean_record_id": record.id,
        "raw_record_id": record.id,
        "clean_record": clean_record,
        "raw": raw_detail,
        "clean": {
            "status": clean_record["clean_status"],
            "latest_normalization": serialize_normalization_detail(latest_normalization) if latest_normalization else None,
            "normalization_history": [serialize_normalization_detail(item) for item in normalizations[:20]],
            "normalization_count": len(normalizations),
            "dedupe_state": clean_record["dedupe_state"],
        },
        "quality": {
            "issue_count": len(quality_issues),
            "issues": [serialize_quality_issue(item) for item in quality_issues[:50]],
            "score": clean_record.get("quality_scores"),
            "score_dimensions": clean_record.get("quality_scores"),
            "quality_score": clean_record.get("quality_score"),
            "quality_band": clean_record.get("quality_band"),
            "quality_scored_at": clean_record.get("quality_scored_at"),
        },
        "extractions": {
            "signal_count": len(signals),
            "signals": [serialize_clean_record_signal(item) for item in signals],
        },
        "lineage": {
            "edge_count": len(lineage_payload),
            "edges": lineage_payload,
        },
        "access": {
            "content_redacted": True,
            "access_mode": "redacted",
            "default_display": "masked_text",
            "required_permission": "data_source:read",
            "original_available": raw_payload is not None,
            "original_access_path": f"/api/v1/raw-records/{record.id}/original" if raw_payload is not None else None,
            "redacted_export_path": f"/api/v1/raw-records/{record.id}/redacted-export",
            "original_access_required_permission": "data_source:raw_original",
        },
        "page_state": "ready",
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="clean_record.detail_viewed",
        object_type="clean_record",
        object_id=record.id,
        after={
            "raw_record_id": record.id,
            "normalization_count": len(normalizations),
            "quality_issue_count": len(quality_issues),
            "lineage_edge_count": len(lineage_payload),
            "signal_count": len(signals),
            "content_redacted": True,
        },
        trace_id=trace_id,
    )
    session.commit()
    return detail


def update_clean_record_status(session: Session, clean_record_id: str, request, actor: models.User, trace_id: str) -> dict:
    record, raw_payload = _raw_record_with_payload(session, clean_record_id, actor)
    latest_normalization = session.execute(
        select(models.RawRecordNormalization)
        .where(models.RawRecordNormalization.raw_record_id == record.id)
        .order_by(models.RawRecordNormalization.created_at.desc(), models.RawRecordNormalization.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    quality_issue_count = session.execute(
        select(func.count()).select_from(models.RawRecordQualityIssue).where(models.RawRecordQualityIssue.raw_record_id == record.id)
    ).scalar_one()
    previous_payload = dict(record.payload or {})
    previous_mark = previous_payload.get("clean_record_status") if isinstance(previous_payload.get("clean_record_status"), dict) else {}
    previous_status = _derive_clean_record_status(record, latest_normalization, _clean_record_dedupe_state(record))
    if request.status == "invalid":
        report_refs = _clean_record_report_references(session, record.id, actor.tenant_id)
        if report_refs:
            raise _api_error(
                409,
                "CLEAN_RECORD_REPORT_LOCKED",
                "Clean record has entered a report and cannot be marked invalid.",
                {"raw_record_id": record.id, "report_refs": report_refs[:10]},
            )
    version = int(previous_mark.get("version") or 0) + 1
    changed_at = _now().isoformat()
    status_mark = {
        "status": request.status,
        "previous_status": previous_status,
        "reason": request.reason,
        "changed_by_id": actor.id,
        "changed_by": actor.username,
        "changed_at": changed_at,
        "version": version,
        "payload": _redact_sensitive_payload(dict(request.payload or {})),
        "blocks_downstream_signal_generation": request.status in CLEAN_RECORD_SIGNAL_BLOCKING_STATUSES,
        "affects_downstream_signal_generation": True,
    }
    record.payload = previous_payload | {"clean_record_status": status_mark}
    flag_modified(record, "payload")
    clean_record = serialize_clean_record(record, raw_payload, latest_normalization, int(quality_issue_count))
    transition = {
        "from_status": previous_status,
        "to_status": request.status,
        "previous_status": previous_status,
        "status": request.status,
        "version": version,
        "changed_at": changed_at,
        "reason": request.reason,
    }
    downstream = {
        "signal_generation_allowed": request.status not in CLEAN_RECORD_SIGNAL_BLOCKING_STATUSES,
        "blocked_reason": "clean_record_status_blocks_signal_generation" if request.status in CLEAN_RECORD_SIGNAL_BLOCKING_STATUSES else None,
        "applies_to": ["signal_extraction_run"],
    }
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="clean_record.status_updated",
        object_type="clean_record",
        object_id=record.id,
        before={"clean_record_status": previous_mark, "derived_status": previous_status},
        after={"clean_record_status": status_mark, "downstream_effect": downstream},
        diff=transition,
        trace_id=trace_id,
    )
    session.commit()
    return {
        "clean_record": clean_record,
        "status_transition": transition,
        "downstream_effect": downstream,
        "report_lock": {"checked": request.status == "invalid", "locked": False},
    }


def get_raw_record(session: Session, raw_record_id: str, actor: models.User | None = None) -> dict:
    record, payload = _raw_record_with_payload(session, raw_record_id, actor)
    return _serialize_raw_record_redacted_detail(record, payload)


def get_raw_record_original(session: Session, raw_record_id: str, actor: models.User, trace_id: str) -> dict:
    record, payload = _raw_record_with_payload(session, raw_record_id, actor)
    masked_text = _raw_record_masked_text(record, payload)
    content_text = payload.content_text if payload is not None else record.title
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="raw_record.original_viewed",
        object_type="raw_record",
        object_id=record.id,
        after={"raw_record_id": record.id, "access_mode": "original", "content_hash": record.content_hash, "content_redacted": False},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_raw_record(record) | {
        "content": content_text,
        "masked_text": masked_text,
        "content_redacted": False,
        "access_mode": "original",
        "default_display": "original",
        "required_permission": "data_source:raw_original",
    }


def export_raw_record_redacted(session: Session, raw_record_id: str, actor: models.User, trace_id: str) -> dict:
    record, payload = _raw_record_with_payload(session, raw_record_id, actor)
    masked_text = _raw_record_masked_text(record, payload)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="raw_record.redacted_exported",
        object_type="raw_record",
        object_id=record.id,
        after={"raw_record_id": record.id, "access_mode": "redacted_export", "content_hash": record.content_hash, "content_redacted": True},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_raw_record(record) | {
        "content": masked_text,
        "masked_text": masked_text,
        "content_redacted": True,
        "access_mode": "redacted_export",
        "format": "text/plain",
        "file_name": f"{record.id}-redacted.txt",
        "default_display": "masked_text",
        "required_permission": "data_source:read",
        "original_access_required_permission": "data_source:raw_original",
    }


def _raw_record_with_payload(session: Session, raw_record_id: str, actor: models.User | None = None) -> tuple[models.RawRecord, models.RawRecordPayload | None]:
    record = session.get(models.RawRecord, raw_record_id)
    if record is None or (actor is not None and record.tenant_id != actor.tenant_id):
        raise _api_error(404, "NOT_FOUND", "Raw record does not exist.")
    payload = session.execute(select(models.RawRecordPayload).where(models.RawRecordPayload.raw_record_id == record.id)).scalar_one_or_none()
    return record, payload


def _raw_record_masked_text(record: models.RawRecord, payload: models.RawRecordPayload | None) -> str:
    if payload is None:
        return mask_sensitive_text(record.title)
    return payload.masked_text or mask_sensitive_text(payload.content_text or record.title)


def _clean_record_report_references(session: Session, raw_record_id: str, tenant_id: str) -> list[dict]:
    references: list[dict] = []
    seen: set[tuple[str, str]] = set()
    signal_ids = _signal_ids_for_raw_record(session, raw_record_id)
    evidence_ids = _evidence_ids_for_raw_record(session, raw_record_id, signal_ids)
    object_ids = {raw_record_id, *signal_ids, *evidence_ids}
    object_refs = {("raw_record", raw_record_id)} | {("signal", signal_id) for signal_id in signal_ids} | {("evidence", evidence_id) for evidence_id in evidence_ids}

    def add_reference(reference: dict) -> None:
        key = (str(reference.get("object_type")), str(reference.get("object_id")))
        if key not in seen:
            seen.add(key)
            references.append(reference)

    claims = list(session.execute(select(models.ReportClaim).where(models.ReportClaim.tenant_id == tenant_id)).scalars())
    for claim in claims:
        if (
            (claim.source_object_type, claim.source_object_id) in object_refs
            or claim.source_object_id in object_ids
            or _json_contains_any(claim.evidence_refs, object_ids)
            or _json_contains_any(claim.payload, object_ids)
        ):
            add_reference({"object_type": "report_claim", "object_id": claim.id, "report_id": claim.report_id})
    reports = list(session.execute(select(models.Report).where(or_(models.Report.tenant_id == tenant_id, models.Report.tenant_id.is_(None)))).scalars())
    for report in reports:
        if _json_contains_any(report.payload, object_ids):
            add_reference({"object_type": "report", "object_id": report.id})
    versions = list(session.execute(select(models.ReportVersion).where(models.ReportVersion.tenant_id == tenant_id)).scalars())
    for version in versions:
        if _json_contains_any(version.sections, object_ids) or _json_contains_any(version.diff, object_ids) or _json_contains_any(version.payload, object_ids):
            add_reference({"object_type": "report_version", "object_id": version.id, "report_id": version.report_id})
    tasks = list(session.execute(select(models.Task).where(or_(models.Task.tenant_id == tenant_id, models.Task.tenant_id.is_(None)))).scalars())
    for task in tasks:
        if _json_contains_any(task.evidence_refs, object_ids) or _json_contains_any(task.payload, object_ids):
            add_reference({"object_type": "task", "object_id": task.id, "report_id": task.report_id})
    return references


def _signal_ids_for_raw_record(session: Session, raw_record_id: str) -> set[str]:
    signal_ids = set(
        session.execute(
            select(models.LineageEdge.to_object_id).where(
                models.LineageEdge.from_object_type == "raw_record",
                models.LineageEdge.from_object_id == raw_record_id,
                models.LineageEdge.to_object_type == "signal",
            )
        ).scalars()
    )
    for signal in session.execute(select(models.Signal)).scalars():
        if _json_contains_any(signal.payload, {raw_record_id}):
            signal_ids.add(signal.id)
    return signal_ids


def _evidence_ids_for_raw_record(session: Session, raw_record_id: str, signal_ids: set[str]) -> set[str]:
    evidence_ids: set[str] = set()
    if signal_ids:
        evidence_ids.update(
            session.execute(
                select(models.Evidence.id).where(models.Evidence.signal_id.in_(signal_ids))
            ).scalars()
        )
        evidence_ids.update(
            session.execute(
                select(models.LineageEdge.to_object_id).where(
                    models.LineageEdge.from_object_type == "signal",
                    models.LineageEdge.from_object_id.in_(signal_ids),
                    models.LineageEdge.to_object_type == "evidence",
                )
            ).scalars()
        )
    tokens = {raw_record_id, *signal_ids}
    for evidence in session.execute(select(models.Evidence)).scalars():
        if evidence.signal_id in signal_ids or _json_contains_any(evidence.payload, tokens):
            evidence_ids.add(evidence.id)
    return evidence_ids


def _json_contains_any(value, tokens: set[str]) -> bool:
    if not tokens:
        return False
    try:
        encoded = json.dumps(value or {}, ensure_ascii=False, default=str)
    except TypeError:
        encoded = str(value)
    return any(token in encoded for token in tokens)


def create_raw_record_batch(session: Session, request, actor: models.User, trace_id: str) -> dict:
    if not getattr(request, "collection_run_id", None):
        raise _api_error(422, "RAW_RECORD_RUN_REQUIRED", "Raw record repository writes require collection_run_id.")
    source = get_data_source(session, request.data_source_id)
    if source.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Data source does not exist.")
    run = session.get(models.CollectionRun, request.collection_run_id)
    if run is None:
        raise _api_error(404, "RAW_RECORD_RUN_NOT_FOUND", "Collection run does not exist.")
    if run.data_source_id != source.id:
        raise _api_error(422, "RAW_RECORD_RUN_SOURCE_MISMATCH", "Collection run belongs to a different data source.")
    if len(request.records) + request.synthetic_count <= 0:
        raise _api_error(422, "RAW_RECORD_BATCH_EMPTY", "Raw record repository batch must contain records or synthetic_count.")

    started_at = time.perf_counter()
    stored_count = 0
    raw_uri_count = 0
    metadata_count = 0
    response_records: list[dict] = []
    raw_rows: list[dict] = []
    payload_rows: list[dict] = []
    lineage_rows: list[dict] = []
    now = _now()
    batch_size = 5000
    duplicate_count = 0
    conflict_count = 0
    duplicate_refs: list[dict] = []
    conflict_refs: list[dict] = []
    pending_by_dedupe: dict[tuple[str, str], dict] = {}

    def flush() -> None:
        if not raw_rows:
            return
        session.execute(models.RawRecord.__table__.insert(), raw_rows)
        session.execute(models.RawRecordPayload.__table__.insert(), payload_rows)
        session.execute(models.LineageEdge.__table__.insert(), lineage_rows)
        raw_rows.clear()
        payload_rows.clear()
        lineage_rows.clear()

    try:
        for spec in _raw_record_repository_specs(request, source):
            raw_id = _id("RAW")
            source_type = spec["source_type"] or source.source_type
            is_synthetic = bool(source.is_synthetic if spec["is_synthetic"] is None else spec["is_synthetic"])
            content = spec["content"]
            raw_uri = spec["raw_uri"]
            metadata = spec["metadata"]
            content_hash = spec["content_hash"] or _hash(content)
            dedupe_key = (
                _raw_hash_dedupe_key(source.id, f"dedupe_key:{spec['dedupe_key']}")
                if spec["dedupe_key"]
                else (_raw_hash_dedupe_key(source.id, f"external_id:{spec['external_id']}") if spec["external_id"] else None)
            )
            redacted_external_id = mask_sensitive_text(spec["external_id"]) if isinstance(spec["external_id"], str) else spec["external_id"]
            if dedupe_key:
                existing_ref = pending_by_dedupe.get((source_type, dedupe_key))
                existing = None
                if existing_ref is None:
                    existing = session.execute(
                        select(models.RawRecord)
                        .where(models.RawRecord.data_source_id == source.id, models.RawRecord.source_type == source_type, models.RawRecord.dedupe_key == dedupe_key)
                        .limit(1)
                    ).scalar_one_or_none()
                    if existing is not None:
                        existing_ref = {"raw_record_id": existing.id, "content_hash": existing.content_hash, "dedupe_key": existing.dedupe_key}
                if existing_ref is not None:
                    if existing_ref["content_hash"] == content_hash:
                        duplicate_count += 1
                        duplicate_refs.append(
                            {
                                "external_id": redacted_external_id,
                                "dedupe_key": dedupe_key,
                                "incoming_content_hash": content_hash,
                                "existing_content_hash": existing_ref["content_hash"],
                                "existing_raw_record_id": existing_ref["raw_record_id"],
                            }
                        )
                        continue
                    conflict_count += 1
                    conflict = {
                        "external_id": redacted_external_id,
                        "dedupe_key": dedupe_key,
                        "incoming_content_hash": content_hash,
                        "existing_content_hash": existing_ref["content_hash"],
                        "existing_raw_record_id": existing_ref["raw_record_id"],
                        "collection_run_id": run.id,
                        "data_source_id": source.id,
                    }
                    conflict_refs.append(conflict)
                    session.add(
                        models.OpsErrorQueue(
                            id=_id("ERRQ"),
                            source="raw_hash_conflict",
                            severity="warning",
                            status="open",
                            message="Raw record hash conflict for the same source external id.",
                            payload=conflict | {"trace_id": trace_id},
                        )
                    )
                    continue
            stored_count += 1
            if raw_uri:
                raw_uri_count += 1
            if metadata:
                metadata_count += 1
            redacted_raw_uri = mask_sensitive_text(raw_uri) if isinstance(raw_uri, str) else raw_uri
            redacted_metadata = _redact_sensitive_payload(metadata)
            repository_ref = {
                "activity_name": RAW_RECORD_REPOSITORY_ACTIVITY_NAME,
                "batch_index": stored_count,
                "trace_id": trace_id,
                "raw_uri": redacted_raw_uri,
                "metadata": redacted_metadata,
                "external_id": redacted_external_id,
            }
            record_payload = {
                **_redact_sensitive_payload(spec["payload"]),
                "repository": repository_ref,
                "raw_uri": redacted_raw_uri,
                "metadata": redacted_metadata,
                "external_id": redacted_external_id,
                "source_flags": {"synthetic": is_synthetic, "import_type": source_type},
                "batch_payload": _redact_sensitive_payload(request.payload or {}),
            }
            raw_row = {
                "id": raw_id,
                "tenant_id": source.tenant_id,
                "data_source_id": source.id,
                "collection_run_id": run.id,
                "source_type": source_type,
                "title": spec["title"][:240],
                "content_hash": content_hash,
                "dedupe_key": dedupe_key,
                "rss_guid_key": None,
                "rss_link_key": None,
                "webhook_delivery_key": None,
                "status": spec["status"],
                "is_synthetic": is_synthetic,
                "city_id": spec["city_id"],
                "occurred_at": spec["occurred_at"] or now,
                "payload": record_payload,
            }
            raw_rows.append(raw_row)
            if dedupe_key:
                pending_by_dedupe[(source_type, dedupe_key)] = {"raw_record_id": raw_id, "content_hash": content_hash, "dedupe_key": dedupe_key}
            payload_rows.append(
                {
                        "id": _id("RAWP"),
                        "raw_record_id": raw_id,
                        "content_text": content,
                        "masked_text": mask_sensitive_text(content),
                        "payload": {
                            "activity_name": RAW_RECORD_REPOSITORY_ACTIVITY_NAME,
                            "raw_uri": redacted_raw_uri,
                            "metadata": redacted_metadata,
                            "external_id": redacted_external_id,
                            "synthetic": is_synthetic,
                        },
                }
            )
            lineage_rows.extend(
                [
                    {
                        "id": _id("LIN"),
                        "from_object_type": "data_source",
                        "from_object_id": source.id,
                        "to_object_type": "raw_record",
                        "to_object_id": raw_id,
                        "relation": "raw_repository_source",
                        "is_synthetic": is_synthetic,
                        "payload": {"activity_name": RAW_RECORD_REPOSITORY_ACTIVITY_NAME, "raw_uri": redacted_raw_uri, "external_id": redacted_external_id},
                    },
                    {
                        "id": _id("LIN"),
                        "from_object_type": "collection_run",
                        "from_object_id": run.id,
                        "to_object_type": "raw_record",
                        "to_object_id": raw_id,
                        "relation": "raw_repository_batch",
                        "is_synthetic": is_synthetic,
                        "payload": {"activity_name": RAW_RECORD_REPOSITORY_ACTIVITY_NAME, "batch_index": stored_count},
                    },
                ]
            )
            if len(response_records) < request.response_limit:
                response_records.append(_serialize_bulk_raw_record(raw_row))
            if len(raw_rows) >= batch_size:
                flush()
        flush()
    except IntegrityError as exc:
        session.rollback()
        raise _api_error(409, "RAW_RECORD_DEDUPE_CONFLICT", "Raw record repository write conflicts with an existing dedupe key.") from exc

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    repository = {
        "activity_name": RAW_RECORD_REPOSITORY_ACTIVITY_NAME,
        "status": _raw_record_repository_status(stored_count, duplicate_count, conflict_count),
        "stored_count": stored_count,
        "duplicate_count": duplicate_count,
        "conflict_count": conflict_count,
        "dedupe_hit_rate": round(duplicate_count / max(stored_count + duplicate_count, 1), 4),
        "duplicate_refs": duplicate_refs[:50],
        "conflict_refs": conflict_refs[:50],
        "response_record_count": len(response_records),
        "raw_uri_count": raw_uri_count,
        "metadata_count": metadata_count,
        "batch_size": batch_size,
        "supports_million_record_batch": True,
        "latency_ms": latency_ms,
        "source_type": source.source_type,
        "trace_id": trace_id,
    }
    run.record_count = max(0, run.record_count or 0) + stored_count
    run.payload = {**(run.payload or {}), "raw_record_repository": repository, "workflow_status": "completed" if request.complete_run else (run.payload or {}).get("workflow_status", "pending")}
    if request.complete_run:
        run.status = "completed"
        workflow_id = (run.payload or {}).get("workflow_run_id")
        if isinstance(workflow_id, str):
            workflow = session.get(models.WorkflowRun, workflow_id)
            if workflow is not None:
                workflow.status = "completed"
                workflow.payload = {**(workflow.payload or {}), "status": "completed", "raw_record_repository": repository}
                session.add(models.WorkflowRunEvent(id=_id("WFRE"), workflow_run_id=workflow.id, event_type="activity_completed", status="completed", payload=repository | {"collection_run_id": run.id, "step_key": "store"}, created_at=_now()))
    session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="raw_record_repository_batch_stored", status="completed", payload=repository | {"step_key": "store"}, created_at=_now()))
    if duplicate_count:
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="raw_record_repository_dedupe_skipped", status="completed", payload=repository | {"step_key": "store"}, created_at=_now()))
    if conflict_count:
        session.add(models.CollectionRunEvent(id=_id("CREV"), collection_run_id=run.id, event_type="raw_record_repository_hash_conflict", status="conflict", payload=repository | {"step_key": "store"}, created_at=_now()))
    _update_health(session, source.id, run.id, success=True, count=stored_count, error_code=None)
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action="raw_record.repository.batch_create",
        object_type="collection_run",
        object_id=run.id,
        after={"repository": repository, "collection_run": serialize_collection_run(run), "sample_raw_record_ids": [item["raw_record_id"] for item in response_records[:20]]},
        reason=request.reason,
        trace_id=trace_id,
    )
    if conflict_count:
        write_audit(
            session,
            tenant_id=actor.tenant_id,
            actor=actor.username,
            actor_id=actor.id,
            action="raw_record.repository.hash_conflict",
            object_type="collection_run",
            object_id=run.id,
            after={"repository": repository, "conflicts": conflict_refs[:50]},
            reason=request.reason,
            trace_id=trace_id,
        )
    session.commit()
    return {"status": "stored", "repository": repository, "data_source": serialize_data_source(source), "collection_run": serialize_collection_run(run), "raw_records": response_records}


def _raw_record_repository_status(stored_count: int, duplicate_count: int, conflict_count: int) -> str:
    if conflict_count and stored_count:
        return "partial_conflict"
    if conflict_count:
        return "conflict"
    if duplicate_count and not stored_count:
        return "deduped"
    return "stored"


def _raw_hash_dedupe_key(source_id: str, external_id: str) -> str:
    return f"raw-hash:{source_id}:{hashlib.sha256(external_id.encode('utf-8')).hexdigest()}"[:240]


def _raw_record_repository_specs(request, source: models.DataSource):
    for record in request.records:
        yield {
            "title": record.title,
            "content": record.content,
            "content_hash": record.content_hash,
            "raw_uri": record.raw_uri,
            "metadata": dict(record.metadata or {}),
            "external_id": record.external_id,
            "dedupe_key": record.dedupe_key,
            "source_type": record.source_type,
            "status": record.status,
            "city_id": record.city_id,
            "occurred_at": record.occurred_at,
            "is_synthetic": record.is_synthetic,
            "payload": dict(record.payload or {}),
        }
    for index in range(1, request.synthetic_count + 1):
        content = f"synthetic raw repository row {index}: Xi'an first-phase public service evidence with contact 13800138000."
        yield {
            "title": f"Raw repository synthetic row {index}",
            "content": content,
            "content_hash": _hash(content),
            "raw_uri": f"synthetic://xian/raw-repository/{source.id}/{index}",
            "metadata": {"generator": "raw_record_repository", "sequence": index, "city_id": "xian"},
            "external_id": f"raw-repository:{source.id}:{index}",
            "dedupe_key": None,
            "source_type": source.source_type,
            "status": "collected",
            "city_id": "xian",
            "occurred_at": None,
            "is_synthetic": True,
            "payload": {"synthetic_repository_probe": True},
        }


def add_raw_record_label(session: Session, raw_record_id: str, request, actor: models.User, trace_id: str) -> dict:
    record = session.get(models.RawRecord, raw_record_id)
    if record is None:
        raise _api_error(404, "NOT_FOUND", "Raw record does not exist.")
    label = models.RawRecordLabel(id=_id("RLBL"), raw_record_id=record.id, label=request.label, actor_id=actor.id, reason=request.reason)
    session.add(label)
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="raw_record.label", object_type="raw_record", object_id=record.id, after={"label": request.label}, trace_id=trace_id)
    session.commit()
    return {"label_id": label.id, "raw_record_id": record.id, "label": label.label, "reason": label.reason}


def apply_dedupe_decision(session: Session, clean_record_id: str, request, actor: models.User, trace_id: str) -> dict:
    record = session.get(models.RawRecord, clean_record_id)
    if record is None or record.tenant_id != actor.tenant_id:
        raise _api_error(404, "NOT_FOUND", "Clean record does not exist.")
    group = _resolve_dedupe_decision_group(session, clean_record_id, request.dedup_group_id, actor.tenant_id)
    payload = dict(group.payload or {})
    existing_decision = payload.get("dedupe_decision") if isinstance(payload.get("dedupe_decision"), dict) else None
    if existing_decision and existing_decision.get("status") in {"confirmed_duplicate", "split_candidate"}:
        raise _api_error(409, "DEDUPE_DECISION_ALREADY_APPLIED", "This dedupe candidate already has a final decision.", {"dedup_group_id": group.id, "status": existing_decision.get("status")})
    if payload.get("candidate_only") is not True:
        raise _api_error(409, "DEDUPE_GROUP_NOT_CANDIDATE", "Only candidate dedupe groups can be confirmed or split manually.", {"dedup_group_id": group.id})

    members = _dedupe_group_member_records(session, group, actor.tenant_id)
    if clean_record_id not in {member.id for member in members}:
        raise _api_error(422, "DEDUPE_DECISION_RECORD_NOT_IN_GROUP", "The clean record is not a member of the dedupe candidate group.", {"dedup_group_id": group.id})

    decision_id = _id("DDEC")
    decided_at = _now().isoformat()
    request_payload = _redact_sensitive_payload(dict(request.payload or {}))
    if request.decision == "confirm_duplicate":
        kept_id = request.duplicate_of_raw_record_id or group.kept_raw_record_id
        if kept_id not in {member.id for member in members}:
            raise _api_error(422, "DEDUPE_DECISION_KEEP_RECORD_NOT_IN_GROUP", "duplicate_of_raw_record_id must be a member of the dedupe candidate group.", {"dedup_group_id": group.id})
        kept_record = next(member for member in members if member.id == kept_id)
        duplicate_records = [member for member in members if member.id != kept_id]
        duplicate_ids = [member.id for member in duplicate_records]
        group.kept_raw_record_id = kept_id
        group.duplicate_raw_record_ids = duplicate_ids
        decision = {
            "dedupe_decision_id": decision_id,
            "status": "confirmed_duplicate",
            "decision": "confirm_duplicate",
            "dedup_group_id": group.id,
            "clean_record_id": clean_record_id,
            "duplicate_of_raw_record_id": kept_id,
            "duplicate_raw_record_ids": duplicate_ids,
            "decided_by_id": actor.id,
            "decided_by": actor.username,
            "decided_at": decided_at,
            "reason": request.reason,
            "payload": request_payload,
        }
        group.payload = {
            **payload,
            "candidate_only": False,
            "review_required": False,
            "merge_state": "confirmed_duplicate",
            "dedupe_decision": decision,
            "confirmed_duplicate_of": {duplicate.id: kept_id for duplicate in duplicate_records},
        }
        flag_modified(group, "payload")
        flag_modified(group, "duplicate_raw_record_ids")
        kept_record.payload = {
            **(kept_record.payload or {}),
            "dedupe_decision": {
                "status": "kept",
                "dedupe_decision_id": decision_id,
                "dedup_group_id": group.id,
                "confirmed_duplicate_count": len(duplicate_records),
                "decided_at": decided_at,
            },
            SEMANTIC_DEDUPE_RECORDS_NAME: {
                **((kept_record.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME) if isinstance((kept_record.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME), dict) else {}),
                "status": "kept",
                "merge_state": "confirmed_duplicate",
                "dedupe_decision_id": decision_id,
                "review_required": False,
            },
        }
        flag_modified(kept_record, "payload")
        for duplicate in duplicate_records:
            semantic_state = (duplicate.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME) if isinstance((duplicate.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME), dict) else {}
            duplicate.payload = {
                **(duplicate.payload or {}),
                "duplicate_of": kept_id,
                "dedupe_decision": {
                    "status": "confirmed_duplicate",
                    "dedupe_decision_id": decision_id,
                    "dedup_group_id": group.id,
                    "duplicate_of": kept_id,
                    "decided_at": decided_at,
                },
                SEMANTIC_DEDUPE_RECORDS_NAME: {
                    **semantic_state,
                    "status": "confirmed_duplicate",
                    "duplicate_of": kept_id,
                    "merge_state": "confirmed_duplicate",
                    "dedupe_decision_id": decision_id,
                    "review_required": False,
                },
            }
            flag_modified(duplicate, "payload")
            session.add(
                models.LineageEdge(
                    id=_id("LIN"),
                    from_object_type="raw_record",
                    from_object_id=duplicate.id,
                    to_object_type="raw_record",
                    to_object_id=kept_id,
                    relation="deduplicated_into",
                    is_synthetic=duplicate.is_synthetic,
                    payload={"dedupe_decision_id": decision_id, "dedup_group_id": group.id, "decision": "confirm_duplicate", "reason": request.reason},
                )
            )
        action = "dedupe.candidate.confirmed"
    else:
        decision = {
            "dedupe_decision_id": decision_id,
            "status": "split_candidate",
            "decision": "split_candidate",
            "dedup_group_id": group.id,
            "clean_record_id": clean_record_id,
            "duplicate_of_raw_record_id": None,
            "duplicate_raw_record_ids": [],
            "decided_by_id": actor.id,
            "decided_by": actor.username,
            "decided_at": decided_at,
            "reason": request.reason,
            "payload": request_payload,
        }
        group.payload = {
            **payload,
            "candidate_only": False,
            "review_required": False,
            "merge_state": "split_candidate",
            "dedupe_decision": decision,
            "confirmed_duplicate_of": {},
        }
        flag_modified(group, "payload")
        for member in members:
            semantic_state = (member.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME) if isinstance((member.payload or {}).get(SEMANTIC_DEDUPE_RECORDS_NAME), dict) else {}
            member.payload = {
                **(member.payload or {}),
                "dedupe_decision": {
                    "status": "split_candidate",
                    "dedupe_decision_id": decision_id,
                    "dedup_group_id": group.id,
                    "decided_at": decided_at,
                },
                SEMANTIC_DEDUPE_RECORDS_NAME: {
                    **semantic_state,
                    "status": "split_candidate",
                    "merge_state": "split_candidate",
                    "dedupe_decision_id": decision_id,
                    "review_required": False,
                },
            }
            member.payload.pop("duplicate_of", None)
            flag_modified(member, "payload")
            session.add(
                models.LineageEdge(
                    id=_id("LIN"),
                    from_object_type="raw_record",
                    from_object_id=member.id,
                    to_object_type="raw_record_dedup_group",
                    to_object_id=group.id,
                    relation="dedupe_candidate_split",
                    is_synthetic=member.is_synthetic,
                    payload={"dedupe_decision_id": decision_id, "dedup_group_id": group.id, "decision": "split_candidate", "reason": request.reason},
                )
            )
        duplicate_ids = []
        kept_id = group.kept_raw_record_id
        action = "dedupe.candidate.split"

    session.add(
        models.LineageEdge(
            id=_id("LIN"),
            from_object_type="raw_record",
            from_object_id=clean_record_id,
            to_object_type="raw_record_dedup_group",
            to_object_id=group.id,
            relation="dedupe_decision_applied",
            is_synthetic=record.is_synthetic,
            payload={"dedupe_decision_id": decision_id, "dedup_group_id": group.id, "decision": request.decision},
        )
    )
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        actor=actor.username,
        actor_id=actor.id,
        action=action,
        object_type="raw_record_dedup_group",
        object_id=group.id,
        after={"dedupe_decision": decision, "group": serialize_dedup_group(group)},
        reason=request.reason,
        trace_id=trace_id,
    )
    session.commit()
    return {
        "clean_record_id": clean_record_id,
        "decision": decision,
        "dedupe_decision": decision,
        "dedup_group_id": group.id,
        "kept_raw_record_id": kept_id,
        "duplicate_raw_record_ids": duplicate_ids,
        "group": serialize_dedup_group(group),
        "raw_records": [serialize_raw_record(member) for member in _dedupe_group_member_records(session, group, actor.tenant_id)],
    }


def _resolve_dedupe_decision_group(session: Session, raw_record_id: str, dedup_group_id: str | None, tenant_id: str) -> models.RawRecordDedupGroup:
    statement = (
        select(models.RawRecordDedupGroup, models.DeduplicationRun)
        .join(models.DeduplicationRun, models.RawRecordDedupGroup.deduplication_run_id == models.DeduplicationRun.id)
        .where(models.DeduplicationRun.tenant_id == tenant_id)
        .order_by(models.RawRecordDedupGroup.created_at.desc())
        .limit(200)
    )
    if dedup_group_id:
        statement = statement.where(models.RawRecordDedupGroup.id == dedup_group_id)
    for group, _run in session.execute(statement).all():
        member_ids = {group.kept_raw_record_id, *list(group.duplicate_raw_record_ids or [])}
        if raw_record_id in member_ids:
            return group
    raise _api_error(404, "DEDUPE_CANDIDATE_NOT_FOUND", "Dedupe candidate group does not exist for this clean record.", {"dedup_group_id": dedup_group_id})


def _dedupe_group_member_records(session: Session, group: models.RawRecordDedupGroup, tenant_id: str) -> list[models.RawRecord]:
    member_ids = [group.kept_raw_record_id, *list(group.duplicate_raw_record_ids or [])]
    rows = list(session.execute(select(models.RawRecord).where(models.RawRecord.id.in_(member_ids), models.RawRecord.tenant_id == tenant_id)).scalars())
    by_id = {row.id: row for row in rows}
    return [by_id[raw_id] for raw_id in member_ids if raw_id in by_id]


def lineage(session: Session, object_type: str | None = None, object_id: str | None = None, actor: models.User | None = None) -> list[dict]:
    if actor is not None:
        if not object_type or not object_id:
            return []
        _require_lineage_object_visible(session, object_type, object_id, actor)
    statement = select(models.LineageEdge).order_by(models.LineageEdge.created_at.desc())
    if object_type and object_id:
        statement = statement.where(
            ((models.LineageEdge.from_object_type == object_type) & (models.LineageEdge.from_object_id == object_id))
            | ((models.LineageEdge.to_object_type == object_type) & (models.LineageEdge.to_object_id == object_id))
        )
    return [serialize_lineage(row) for row in session.execute(statement).scalars()]


def _require_lineage_object_visible(session: Session, object_type: str, object_id: str, actor: models.User) -> None:
    if object_type == "raw_record":
        row = session.get(models.RawRecord, object_id)
        if row is not None and row.tenant_id == actor.tenant_id:
            return
        raise _api_error(404, "NOT_FOUND", "Lineage object does not exist.")
    if object_type == "data_source":
        row = session.get(models.DataSource, object_id)
        if row is not None and row.tenant_id == actor.tenant_id:
            return
        raise _api_error(404, "NOT_FOUND", "Lineage object does not exist.")
    if object_type == "collection_run":
        row = session.get(models.CollectionRun, object_id)
        if row is not None:
            source = session.get(models.DataSource, row.data_source_id)
            if source is not None and source.tenant_id == actor.tenant_id:
                return
        raise _api_error(404, "NOT_FOUND", "Lineage object does not exist.")
    if object_type in {"import_run", "normalization_run", "deduplication_run", "data_quality_run", "algorithm_run"}:
        model_by_type = {
            "import_run": models.ImportRun,
            "normalization_run": models.NormalizationRun,
            "deduplication_run": models.DeduplicationRun,
            "data_quality_run": models.DataQualityRun,
            "algorithm_run": models.AlgorithmRun,
        }
        row = session.get(model_by_type[object_type], object_id)
        if row is not None and getattr(row, "tenant_id", None) == actor.tenant_id:
            return
        raise _api_error(404, "NOT_FOUND", "Lineage object does not exist.")
    if object_type == "raw_record_normalization":
        row = session.get(models.RawRecordNormalization, object_id)
        if row is not None:
            raw = session.get(models.RawRecord, row.raw_record_id)
            if raw is not None and raw.tenant_id == actor.tenant_id:
                return
        raise _api_error(404, "NOT_FOUND", "Lineage object does not exist.")


def _source_policy_snapshot(source: models.DataSource) -> dict:
    policy = dict(source.policy or {})
    for governance_key in ("published_version", "config_status", "rollback"):
        policy.pop(governance_key, None)
    policy["source_name"] = source.name
    policy["source_type"] = source.source_type
    policy["is_synthetic"] = source.is_synthetic
    return policy


def _config_hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return _hash(canonical)


def _published_version_pointer(version: models.DataSourceVersion) -> dict:
    return {
        "data_source_version_id": version.id,
        "version": version.version,
        "status": version.status,
        "config_hash": version.config_hash,
        "published_at": version.published_at.isoformat() if version.published_at else None,
    }


def _collection_version_payload(source: models.DataSource, job_payload: dict | None = None) -> dict:
    published = None
    if isinstance(job_payload, dict) and job_payload.get("data_source_version_id"):
        return {
            "data_source_version_id": job_payload.get("data_source_version_id"),
            "data_source_version": job_payload.get("data_source_version"),
            "data_source_config_hash": job_payload.get("data_source_config_hash"),
        }
    policy = source.policy or {}
    if isinstance(policy.get("published_version"), dict):
        published = policy["published_version"]
    if not published:
        return {}
    return {
        "data_source_version_id": published.get("data_source_version_id"),
        "data_source_version": published.get("version"),
        "data_source_config_hash": published.get("config_hash"),
    }


def _normalize_collection_schedule(schedule: str | None) -> str | None:
    if schedule is None:
        return None
    value = schedule.strip()
    if value == "once":
        return value
    if value.startswith("cron:"):
        expression = value.removeprefix("cron:").strip()
        parts = expression.split()
        if len(parts) != 5:
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron schedules must include five fields.")
        if any(not re.fullmatch(r"[\d*/,\-]+", part) for part in parts):
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron schedules contain unsupported characters.")
        interval = _cron_interval_minutes(expression)
        if interval < MIN_COLLECTION_CRON_INTERVAL_MINUTES:
            raise _api_error(422, "COLLECTION_CRON_TOO_FREQUENT", f"Cron schedules cannot run more often than every {MIN_COLLECTION_CRON_INTERVAL_MINUTES} minutes.")
        return f"cron:{expression}"
    raise _api_error(422, "COLLECTION_SCHEDULE_INVALID", "Collection job schedule must be once or cron:<expr>.")


def _collection_schedule_payload(schedule: str, trace_id: str) -> dict:
    if schedule == "once":
        return {"job_kind": "once"}
    expression = schedule.removeprefix("cron:").strip()
    return {
        "job_kind": "cron",
        "cron_expression": expression,
        "scheduler_registration": {
            "status": "registered",
            "scheduler": "in_process_schedule_registry_v1",
            "registered_at": _now().isoformat(),
            "trace_id": trace_id,
            "interval_minutes": _cron_interval_minutes(expression),
        },
    }


def _cron_interval_minutes(expression: str) -> int:
    minute, hour, *_ = expression.split()
    minute_interval = _cron_field_interval_minutes(minute, 1, 60)
    if minute_interval is not None:
        return minute_interval
    hour_interval = _cron_field_interval_minutes(hour, 60, 24)
    if hour_interval is not None:
        return hour_interval
    return 24 * 60


def _cron_field_interval_minutes(field: str, unit_minutes: int, modulus: int) -> int | None:
    if field == "*":
        return unit_minutes
    step = re.fullmatch(r"\*/(\d+)", field)
    if step:
        value = int(step.group(1))
        if value <= 0:
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron step must be greater than zero.")
        return value * unit_minutes
    numbers = [int(item) for item in field.split(",") if item.isdigit()]
    if len(numbers) >= 2:
        numbers = sorted(set(numbers))
        if numbers[0] < 0 or numbers[-1] >= modulus:
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron field value is out of range.")
        diffs = [b - a for a, b in zip(numbers, numbers[1:]) if b > a]
        wrap_diff = (modulus - numbers[-1]) + numbers[0]
        if wrap_diff > 0:
            diffs.append(wrap_diff)
        return min(diffs) * unit_minutes if diffs else None
    if re.fullmatch(r"\d+", field):
        value = int(field)
        if value >= modulus:
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron field value is out of range.")
        return None
    range_match = re.fullmatch(r"(\d+)-(\d+)", field)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start >= modulus or end >= modulus or start > end:
            raise _api_error(422, "COLLECTION_CRON_INVALID", "Cron field range is invalid.")
        return unit_minutes
    return None


def serialize_file_object(file_object: models.FileObject) -> dict:
    return {
        "file_object_id": file_object.id,
        "tenant_id": file_object.tenant_id,
        "case_id": file_object.case_id,
        "owner_user_id": file_object.owner_user_id,
        "task_id": file_object.task_id,
        "review_id": file_object.review_id,
        "media_asset_id": file_object.media_asset_id,
        "object_type": file_object.object_type,
        "object_id": file_object.object_id,
        "storage_key": file_object.storage_key,
        "file_name": file_object.file_name,
        "mime_type": file_object.mime_type,
        "byte_size": file_object.byte_size,
        "checksum": file_object.checksum,
        "status": file_object.status,
        "version": file_object.version,
        "access_policy": file_object.access_policy,
        "source_refs": file_object.source_refs,
        "review_gate_record_id": file_object.review_gate_record_id,
        "payload": file_object.payload,
        "created_at": file_object.created_at,
        "updated_at": file_object.updated_at,
    }


def serialize_data_source(source: models.DataSource) -> dict:
    return {"data_source_id": source.id, "tenant_id": source.tenant_id, "name": source.name, "source_type": source.source_type, "status": source.status, "is_synthetic": source.is_synthetic, "policy": source.policy, "payload": source.payload, "created_at": source.created_at}


def serialize_data_source_version(version: models.DataSourceVersion) -> dict:
    return {
        "data_source_version_id": version.id,
        "tenant_id": version.tenant_id,
        "data_source_id": version.data_source_id,
        "version": version.version,
        "status": version.status,
        "config_hash": version.config_hash,
        "policy_snapshot": version.policy_snapshot,
        "payload": version.payload,
        "published_by_id": version.published_by_id,
        "published_at": version.published_at,
        "created_at": version.created_at,
        "updated_at": version.updated_at,
    }


def serialize_collection_job(job: models.CollectionJob) -> dict:
    return {
        "collection_job_id": job.id,
        "tenant_id": job.tenant_id,
        "data_source_id": job.data_source_id,
        "created_by_id": job.created_by_id,
        "name": job.name,
        "status": job.status,
        "schedule": job.schedule,
        "payload": job.payload,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def serialize_collection_job_detail(session: Session, job: models.CollectionJob) -> dict:
    data = serialize_collection_job(job)
    source = session.get(models.DataSource, job.data_source_id)
    runs = list(
        session.execute(
            select(models.CollectionRun)
            .where(models.CollectionRun.collection_job_id == job.id)
            .order_by(models.CollectionRun.created_at.desc(), models.CollectionRun.id.desc())
            .limit(10)
        ).scalars()
    )
    version_pin = _collection_version_payload(source, job.payload) if source is not None else {}
    data.update(
        {
            "source": serialize_data_source(source) if source is not None else None,
            "config": {
                "schedule": job.schedule,
                "query": (job.payload or {}).get("query"),
                "window": (job.payload or {}).get("window"),
                "job_kind": (job.payload or {}).get("job_kind"),
                "cron_expression": (job.payload or {}).get("cron_expression"),
                "scheduler_registration": (job.payload or {}).get("scheduler_registration"),
            },
            "version_pin": version_pin,
            "latest_runs": [serialize_collection_run(run) for run in runs],
            "run_summary": {
                "total_runs": len(runs),
                "success_count": sum(1 for run in runs if run.status == "completed"),
                "failure_count": sum(1 for run in runs if run.status == "failed"),
                "running_count": sum(1 for run in runs if run.status in {"pending", "running", "retrying"}),
                "latest_status": runs[0].status if runs else None,
            },
            "page_state": "ready" if runs else "empty",
        }
    )
    return data


def serialize_collection_run(run: models.CollectionRun) -> dict:
    return {
        "collection_run_id": run.id,
        "collection_job_id": run.collection_job_id,
        "data_source_id": run.data_source_id,
        "status": run.status,
        "record_count": run.record_count,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "trace_id": run.trace_id,
        "payload": run.payload,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def serialize_source_health(health: models.SourceHealth) -> dict:
    return {"source_health_id": health.id, "data_source_id": health.data_source_id, "status": health.status, "last_run_id": health.last_run_id, "success_count": health.success_count, "failure_count": health.failure_count, "last_error_code": health.last_error_code, "payload": health.payload}


def _serialize_raw_record_redacted_detail(record: models.RawRecord, payload: models.RawRecordPayload | None) -> dict:
    masked_text = _raw_record_masked_text(record, payload)
    return serialize_raw_record(record) | {
        "content": masked_text,
        "masked_text": masked_text,
        "content_redacted": True,
        "access_mode": "redacted",
        "default_display": "masked_text",
        "original_available": payload is not None,
        "original_access_path": f"/api/v1/raw-records/{record.id}/original" if payload is not None else None,
        "redacted_export_path": f"/api/v1/raw-records/{record.id}/redacted-export",
        "required_permission": "data_source:read",
        "original_access_required_permission": "data_source:raw_original",
    }


def _clean_record_status_filter(status: str):
    manual_status = models.RawRecord.payload["clean_record_status"]["status"].as_string()
    semantic_status = models.RawRecord.payload[SEMANTIC_DEDUPE_RECORDS_NAME]["status"].as_string()
    decision_status = models.RawRecord.payload["dedupe_decision"]["status"].as_string()
    rule_status = models.RawRecord.payload[DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME]["status"].as_string()
    duplicate_of = models.RawRecord.payload["duplicate_of"].as_string()
    normalization_exists = exists().where(models.RawRecordNormalization.raw_record_id == models.RawRecord.id)
    dedupe_state_exists = or_(
        semantic_status.is_not(None),
        decision_status.is_not(None),
        rule_status.is_not(None),
        duplicate_of.is_not(None),
        manual_status.is_not(None),
    )
    if status in CLEAN_RECORD_MANUAL_STATUSES:
        return manual_status == status
    if status == "dedupe_candidate":
        return semantic_status == "candidate"
    if status == "confirmed_duplicate":
        return or_(decision_status == "confirmed_duplicate", semantic_status == "confirmed_duplicate")
    if status == "duplicate":
        return rule_status == "duplicate"
    if status == "kept":
        return or_(decision_status == "kept", semantic_status == "kept", rule_status == "kept")
    if status == "split_candidate":
        return or_(decision_status == "split_candidate", semantic_status == "split_candidate")
    if status == "embedding_failed":
        return semantic_status == "embedding_failed"
    if status == "cleaned":
        return normalization_exists & ~dedupe_state_exists
    if status == "raw":
        return ~normalization_exists & ~dedupe_state_exists
    return models.RawRecord.status == status


def _clean_record_dedupe_state(record: models.RawRecord) -> dict:
    payload = record.payload or {}
    semantic = payload.get(SEMANTIC_DEDUPE_RECORDS_NAME) if isinstance(payload.get(SEMANTIC_DEDUPE_RECORDS_NAME), dict) else {}
    decision = payload.get("dedupe_decision") if isinstance(payload.get("dedupe_decision"), dict) else {}
    rule = payload.get(DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME) if isinstance(payload.get(DEDUPE_BY_HASH_AND_EXTERNAL_ID_NAME), dict) else {}
    status = decision.get("status") or semantic.get("status") or rule.get("status")
    dedup_group_id = decision.get("dedup_group_id") or semantic.get("dedup_group_id") or rule.get("dedup_group_id")
    duplicate_of = decision.get("duplicate_of") or decision.get("duplicate_of_raw_record_id") or semantic.get("duplicate_of") or rule.get("duplicate_of") or payload.get("duplicate_of")
    return {
        "status": status,
        "dedup_group_id": dedup_group_id,
        "dedupe_decision_id": decision.get("dedupe_decision_id") or semantic.get("dedupe_decision_id"),
        "duplicate_of_raw_record_id": duplicate_of,
        "merge_state": decision.get("merge_state") or semantic.get("merge_state"),
        "candidate_only": semantic.get("candidate_only"),
        "review_required": semantic.get("review_required"),
        "source_boundary": semantic.get("source_boundary") or rule.get("source_boundary"),
        "match_rule": semantic.get("match_rule") or rule.get("match_rule"),
    }


def _derive_clean_record_status(record: models.RawRecord, normalization: models.RawRecordNormalization | None, dedupe_state: dict) -> str:
    payload = record.payload or {}
    manual = payload.get("clean_record_status") if isinstance(payload.get("clean_record_status"), dict) else {}
    manual_status = manual.get("status")
    if isinstance(manual_status, str) and manual_status in CLEAN_RECORD_MANUAL_STATUSES:
        return manual_status
    dedupe_status = dedupe_state.get("status")
    if dedupe_status == "candidate":
        return "dedupe_candidate"
    if dedupe_status in {"confirmed_duplicate", "duplicate", "kept", "split_candidate", "embedding_failed"}:
        return str(dedupe_status)
    if normalization is not None:
        normalization_status = (normalization.payload or {}).get("clean_record_status")
        if isinstance(normalization_status, str) and normalization_status:
            return normalization_status
        return "cleaned"
    if record.status == "collected":
        return "raw"
    return record.status


def _preview(value: str, limit: int = 240) -> str:
    collapsed = re.sub(r"\s+", " ", value or "").strip()
    return collapsed[:limit]


def serialize_raw_record(record: models.RawRecord) -> dict:
    return {"raw_record_id": record.id, "tenant_id": record.tenant_id, "data_source_id": record.data_source_id, "collection_run_id": record.collection_run_id, "source_type": record.source_type, "title": mask_sensitive_text(record.title), "content_hash": record.content_hash, "status": record.status, "is_synthetic": record.is_synthetic, "city_id": record.city_id, "occurred_at": record.occurred_at, "payload": _redact_sensitive_payload(record.payload or {})}


def serialize_clean_record(
    record: models.RawRecord,
    raw_payload: models.RawRecordPayload | None,
    normalization: models.RawRecordNormalization | None,
    quality_issue_count: int = 0,
) -> dict:
    payload = record.payload or {}
    dedupe_state = _clean_record_dedupe_state(record)
    clean_status = _derive_clean_record_status(record, normalization, dedupe_state)
    masked_text = _raw_record_masked_text(record, raw_payload)
    normalized_text = normalization.normalized_text if normalization is not None else None
    normalized_title = normalization.normalized_title if normalization is not None else None
    quality_state = payload.get(SCORE_CLEAN_RECORD_QUALITY_NAME) if isinstance(payload.get(SCORE_CLEAN_RECORD_QUALITY_NAME), dict) else {}
    quality_scores = quality_state.get("scores") if isinstance(quality_state.get("scores"), dict) else None
    quality_score = quality_scores.get("overall") if isinstance(quality_scores, dict) else None
    current_quality_issue_count = int(quality_state["issue_count"]) if isinstance(quality_state.get("issue_count"), (int, float)) else quality_issue_count
    return {
        "clean_record_id": record.id,
        "raw_record_id": record.id,
        "normalization_output_id": normalization.id if normalization is not None else None,
        "normalization_run_id": normalization.normalization_run_id if normalization is not None else None,
        "tenant_id": record.tenant_id,
        "data_source_id": record.data_source_id,
        "collection_run_id": record.collection_run_id,
        "source_type": record.source_type,
        "title": mask_sensitive_text(normalized_title or record.title),
        "raw_title": mask_sensitive_text(record.title),
        "content_hash": record.content_hash,
        "status": clean_status,
        "clean_status": clean_status,
        "raw_status": record.status,
        "is_synthetic": record.is_synthetic,
        "city_id": record.city_id,
        "occurred_at": record.occurred_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "cleaned_at": normalization.created_at if normalization is not None else None,
        "normalized_text_preview": _preview(mask_sensitive_text(normalized_text or "")),
        "masked_text_preview": _preview(masked_text),
        "content_redacted": True,
        "access_mode": "redacted",
        "default_display": "masked_text",
        "original_available": raw_payload is not None,
        "original_access_path": f"/api/v1/raw-records/{record.id}/original" if raw_payload is not None else None,
        "redacted_export_path": f"/api/v1/raw-records/{record.id}/redacted-export",
        "required_permission": "data_source:read",
        "original_access_required_permission": "data_source:raw_original",
        "dedupe_group_id": dedupe_state.get("dedup_group_id"),
        "dedupe_decision_id": dedupe_state.get("dedupe_decision_id"),
        "duplicate_of_raw_record_id": dedupe_state.get("duplicate_of_raw_record_id"),
        "merge_state": dedupe_state.get("merge_state"),
        "candidate_only": dedupe_state.get("candidate_only"),
        "review_required": dedupe_state.get("review_required"),
        "quality_issue_count": current_quality_issue_count,
        "quality_score": quality_score,
        "quality_scores": quality_scores,
        "quality_band": quality_state.get("quality_band"),
        "quality_scored_at": quality_state.get("scored_at"),
        "dedupe_state": _redact_sensitive_payload(dedupe_state),
        "normalization": None if normalization is None else serialize_normalization_summary(normalization),
        "payload": _redact_sensitive_payload(payload),
    }


def serialize_lineage(edge: models.LineageEdge) -> dict:
    return {"lineage_edge_id": edge.id, "from_object_type": edge.from_object_type, "from_object_id": edge.from_object_id, "to_object_type": edge.to_object_type, "to_object_id": edge.to_object_id, "relation": edge.relation, "is_synthetic": edge.is_synthetic, "payload": _redact_sensitive_payload(edge.payload or {})}


def serialize_import_run(run: models.ImportRun) -> dict:
    return {"import_run_id": run.id, "tenant_id": run.tenant_id, "data_source_id": run.data_source_id, "collection_run_id": run.collection_run_id, "import_type": run.import_type, "status": run.status, "record_count": run.record_count, "error_code": run.error_code, "error_message": run.error_message, "is_synthetic": run.is_synthetic, "trace_id": run.trace_id, "payload": run.payload, "created_at": run.created_at, "updated_at": run.updated_at}


def serialize_algorithm_run(run: models.AlgorithmRun) -> dict:
    return {
        "algorithm_run_id": run.id,
        "tenant_id": run.tenant_id,
        "case_id": run.case_id,
        "workflow_run_id": run.workflow_run_id,
        "object_type": run.object_type,
        "object_id": run.object_id,
        "algorithm_name": run.algorithm_name,
        "algorithm_version": run.algorithm_version,
        "status": run.status,
        "input_refs": run.input_refs,
        "output_refs": run.output_refs,
        "output": run.output,
        "metrics": run.metrics,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "trace_id": run.trace_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "payload": run.payload,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def serialize_dead_letter(row: models.OpsErrorQueue) -> dict:
    payload = row.payload or {}
    retry_policy = payload.get("retry_policy") if isinstance(payload.get("retry_policy"), dict) else {}
    return {
        "dead_letter_id": row.id,
        "target_type": payload.get("target_type") or "import_run",
        "target_id": payload.get("target_id") or payload.get("import_run_id"),
        "import_run_id": payload.get("import_run_id") or payload.get("target_id"),
        "collection_run_id": payload.get("collection_run_id"),
        "data_source_id": payload.get("data_source_id"),
        "source_type": payload.get("source_type"),
        "error_code": payload.get("error_code"),
        "error_message": payload.get("error_message") or row.message,
        "retryable": bool(payload.get("retryable") or retry_policy.get("retryable")),
        "classification": payload.get("classification") or retry_policy.get("classification") or "unknown",
        "status": row.status,
        "severity": row.severity,
        "payload": payload,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_normalization_run(run: models.NormalizationRun) -> dict:
    return {"normalization_run_id": run.id, "tenant_id": run.tenant_id, "status": run.status, "input_count": run.input_count, "output_count": run.output_count, "rule_version": run.rule_version, "error_code": run.error_code, "error_message": run.error_message, "trace_id": run.trace_id, "payload": run.payload, "created_at": run.created_at, "updated_at": run.updated_at}


def serialize_normalization_output(output: models.RawRecordNormalization) -> dict:
    return {"normalization_output_id": output.id, "normalization_run_id": output.normalization_run_id, "raw_record_id": output.raw_record_id, "normalized_title": output.normalized_title, "normalized_text": output.normalized_text, "language": output.language, "region_id": output.region_id, "payload": output.payload, "created_at": output.created_at}


def serialize_normalization_summary(output: models.RawRecordNormalization) -> dict:
    return {
        "normalization_output_id": output.id,
        "normalization_run_id": output.normalization_run_id,
        "raw_record_id": output.raw_record_id,
        "normalized_title": mask_sensitive_text(output.normalized_title),
        "normalized_text_preview": _preview(mask_sensitive_text(output.normalized_text)),
        "language": output.language,
        "region_id": output.region_id,
        "payload": _redact_sensitive_payload(output.payload or {}),
        "created_at": output.created_at,
    }


def serialize_normalization_detail(output: models.RawRecordNormalization) -> dict:
    return {
        "normalization_output_id": output.id,
        "normalization_run_id": output.normalization_run_id,
        "raw_record_id": output.raw_record_id,
        "normalized_title": mask_sensitive_text(output.normalized_title),
        "normalized_text": mask_sensitive_text(output.normalized_text),
        "normalized_text_preview": _preview(mask_sensitive_text(output.normalized_text)),
        "language": output.language,
        "region_id": output.region_id,
        "payload": _redact_sensitive_payload(output.payload or {}),
        "created_at": output.created_at,
        "content_redacted": True,
    }


def serialize_clean_record_signal(signal: models.Signal) -> dict:
    return {
        "signal_id": signal.id,
        "case_id": signal.case_id,
        "topic_id": signal.topic_id,
        "mainline_id": signal.mainline_id,
        "title": mask_sensitive_text(signal.title),
        "summary": mask_sensitive_text(signal.summary),
        "priority": signal.priority,
        "region_id": signal.region_id,
        "status": signal.status,
        "scores": signal.scores,
        "payload": _redact_sensitive_payload(signal.payload or {}),
        "created_at": signal.created_at,
        "updated_at": signal.updated_at,
    }


def serialize_deduplication_run(run: models.DeduplicationRun) -> dict:
    return {"deduplication_run_id": run.id, "tenant_id": run.tenant_id, "status": run.status, "input_count": run.input_count, "duplicate_group_count": run.duplicate_group_count, "rule_version": run.rule_version, "error_code": run.error_code, "error_message": run.error_message, "trace_id": run.trace_id, "payload": run.payload, "created_at": run.created_at, "updated_at": run.updated_at}


def serialize_dedup_group(group: models.RawRecordDedupGroup) -> dict:
    return {"dedup_group_id": group.id, "deduplication_run_id": group.deduplication_run_id, "group_key": group.group_key, "kept_raw_record_id": group.kept_raw_record_id, "duplicate_raw_record_ids": group.duplicate_raw_record_ids, "explanation": group.explanation, "payload": group.payload, "created_at": group.created_at}


def serialize_quality_run(run: models.DataQualityRun) -> dict:
    return {"data_quality_run_id": run.id, "tenant_id": run.tenant_id, "status": run.status, "input_count": run.input_count, "issue_count": run.issue_count, "rule_version": run.rule_version, "error_code": run.error_code, "error_message": run.error_message, "trace_id": run.trace_id, "payload": run.payload, "created_at": run.created_at, "updated_at": run.updated_at}


def serialize_quality_issue(issue: models.RawRecordQualityIssue) -> dict:
    return {"quality_issue_id": issue.id, "data_quality_run_id": issue.data_quality_run_id, "raw_record_id": issue.raw_record_id, "issue_type": issue.issue_type, "severity": issue.severity, "message": issue.message, "payload": issue.payload, "created_at": issue.created_at}


def serialize_data_quality_issue_list_item(issue: models.RawRecordQualityIssue, record: models.RawRecord, run: models.DataQualityRun) -> dict:
    quality_state = (record.payload or {}).get(SCORE_CLEAN_RECORD_QUALITY_NAME) if isinstance((record.payload or {}).get(SCORE_CLEAN_RECORD_QUALITY_NAME), dict) else {}
    scores = quality_state.get("scores") if quality_state.get("data_quality_run_id") == issue.data_quality_run_id and isinstance(quality_state.get("scores"), dict) else None
    return {
        "quality_issue_id": issue.id,
        "tenant_id": run.tenant_id,
        "data_quality_run_id": issue.data_quality_run_id,
        "raw_record_id": issue.raw_record_id,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "message": issue.message,
        "payload": _redact_sensitive_payload(issue.payload or {}),
        "created_at": issue.created_at,
        "data_quality_run": {
            "data_quality_run_id": run.id,
            "status": run.status,
            "rule_version": run.rule_version,
            "trace_id": run.trace_id,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        },
        "raw_record": {
            "raw_record_id": record.id,
            "data_source_id": record.data_source_id,
            "collection_run_id": record.collection_run_id,
            "source_type": record.source_type,
            "title": mask_sensitive_text(record.title),
            "status": record.status,
            "city_id": record.city_id,
            "is_synthetic": record.is_synthetic,
            "content_hash": record.content_hash,
        },
        "score": scores,
        "quality_score": scores.get("overall") if isinstance(scores, dict) else None,
        "quality_band": quality_state.get("quality_band") if quality_state.get("data_quality_run_id") == issue.data_quality_run_id else None,
        "evidence_refs": [
            {"object_type": "data_quality_run", "object_id": issue.data_quality_run_id, "object_version": run.rule_version},
            {"object_type": "raw_record", "object_id": issue.raw_record_id, "object_version": record.content_hash},
            {"object_type": "data_source", "object_id": record.data_source_id},
        ],
    }


def _xian_samples() -> list[dict]:
    return [
        {"source_type": "synthetic", "title": "西安城中村改造补偿咨询升温", "district": "雁塔区", "channel": "public_web", "content": "synthetic sample: residents ask about relocation compensation timeline and public notice clarity in Xi'an.", "tags": ["demolition", "compensation"]},
        {"source_type": "synthetic", "title": "养老保险补缴窗口排队反馈", "district": "碑林区", "channel": "manual_upload", "content": "synthetic sample: pension insurance petition discussion asks for queue guidance, policy explanation, and next update time.", "tags": ["pension", "petition"]},
        {"source_type": "synthetic", "title": "小区物业费争议短视频片段", "district": "未央区", "channel": "media", "content": "synthetic media sample: video transcript says owners question fee basis and request public ledger. minor name: Zhang appears in comment and must be masked.", "tags": ["property", "media"], "media_type": "video", "media_uri": "synthetic://xian/property-fee-video-001.mp4"},
        {"source_type": "synthetic", "title": "医院收费解释窗口热线摘要", "district": "莲湖区", "channel": "official_api", "content": "synthetic sample: hotline summary asks hospital billing desk to clarify invoice category and complaint path.", "tags": ["medical", "billing"]},
        {"source_type": "synthetic", "title": "学校周边通行安全图片反馈", "district": "新城区", "channel": "media", "content": "synthetic media sample: image note describes school commute congestion and asks for crossing guard schedule.", "tags": ["school", "traffic"], "media_type": "image", "media_uri": "synthetic://xian/school-traffic-image-001.png"},
        {"source_type": "synthetic", "title": "公交临时绕行通知评论聚集", "district": "长安区", "channel": "public_web", "content": "synthetic sample: bus reroute notice comments focus on alternative stops, accessibility, and update cadence.", "tags": ["transit", "public_service"]},
    ]
