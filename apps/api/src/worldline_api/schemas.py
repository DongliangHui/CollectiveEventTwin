from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CaseOut(ORMModel):
    id: str
    slug: str
    title: str
    scenario_type: str
    status: str
    payload: dict[str, Any]


class SourceRecordOut(ORMModel):
    id: str
    case_id: str
    source_id: str
    source_name: str
    access_mode: str
    status: str
    trust: float
    accepted: bool
    blocked_reason: str | None
    payload: dict[str, Any]


class SignalOut(ORMModel):
    id: str
    case_id: str
    topic_id: str | None = None
    mainline_id: str | None
    title: str
    summary: str
    priority: str
    region_id: str
    status: str
    scores: dict[str, Any]
    payload: dict[str, Any]


class EvidenceOut(ORMModel):
    id: str
    case_id: str
    signal_id: str | None
    title: str
    excerpt: str
    masked_excerpt: str
    source: str
    credibility: str
    status: str
    sensitivity: str
    payload: dict[str, Any]


class RiskFactorOut(ORMModel):
    id: str
    case_id: str
    name: str
    category: str
    confidence: float
    status: str
    payload: dict[str, Any]


class MainlineOut(ORMModel):
    id: str
    case_id: str
    title: str
    confidence: float
    status: str
    payload: dict[str, Any]


class WorldStateOut(ORMModel):
    id: str
    case_id: str
    title: str
    status: str
    payload: dict[str, Any]


class WorldlineNodeOut(ORMModel):
    id: str
    case_id: str
    title: str
    branch: str
    probability: int
    risk: int
    status: str
    payload: dict[str, Any]


class CouncilSessionOut(ORMModel):
    id: str
    case_id: str
    node_id: str
    hypothesis: str
    status: str
    payload: dict[str, Any]


class ReportOut(ORMModel):
    id: str
    case_id: str
    title: str
    human_confirmed: bool
    status: str
    payload: dict[str, Any]


class TaskOut(ORMModel):
    id: str
    case_id: str
    title: str
    owner: str
    due_label: str
    status: str
    payload: dict[str, Any]


class WorkflowRunOut(ORMModel):
    id: str
    case_id: str
    workflow_name: str
    workflow_id: str
    status: str
    payload: dict[str, Any]


class AuditLogOut(ORMModel):
    id: str
    case_id: str
    actor: str
    action: str
    object_type: str
    object_id: str
    reason: str | None
    payload: dict[str, Any]
    created_at: datetime


class SearchResultOut(BaseModel):
    object_type: str
    object_id: str
    case_id: str
    title: str
    summary: str
    score: float


class EvidenceUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed_fact|needs_review|rumor|opinion|emotion|propagation|rejected)$")
    reason: str | None = None
    actor: str = "analyst"


class RiskFactorUpdate(BaseModel):
    status: str = Field(pattern="^(suggested|confirmed|rejected)$")
    reason: str | None = None
    actor: str = "analyst"


class TaskUpdate(BaseModel):
    status: str = Field(pattern="^(suggested|in_progress|completed|overdue|blocked)$")
    reason: str | None = None
    actor: str = "operator"


class ReportConfirm(BaseModel):
    actor: str = "reviewer"
    reason: str = "human_confirmed_for_p0"


class SeedRequest(BaseModel):
    fixture: str = "all"


class WorkflowStartRequest(BaseModel):
    case_id: str
    target_id: str | None = None


class RunCreate(BaseModel):
    object_type: str = Field(min_length=2, max_length=80)
    object_id: str = Field(min_length=2, max_length=160)
    input_scope: dict[str, Any] = Field(default_factory=dict)
    actor_id: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class RoleUpdate(BaseModel):
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    permission_codes: list[str] | None = None
    payload: dict[str, Any] | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=200)
    role_ids: list[str] = Field(default_factory=list)
    status: str = Field(default="active", pattern="^(active|disabled)$")
    payload: dict[str, Any] = Field(default_factory=dict)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    role_ids: list[str] | None = None
    payload: dict[str, Any] | None = None


class UserRolesUpdate(BaseModel):
    role_ids: list[str] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=1000)


class UserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|disabled|locked)$")
    reason: str | None = Field(default=None, max_length=1000)


class ReviewCreate(BaseModel):
    object_type: str = Field(min_length=2, max_length=80)
    object_id: str = Field(min_length=2, max_length=200)
    object_version: str = Field(min_length=1, max_length=80)
    template_id: str = Field(min_length=2, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewUpdate(BaseModel):
    status: str = Field(pattern="^(pending|pass|fail|waived)$")
    findings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    reason: str | None = None


class ReviewWaiveRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=8, max_length=2000)
    risk: str = Field(min_length=4, max_length=2000)
    expires_at: datetime


class ReviewGateCreate(BaseModel):
    task_id: str | None = Field(default=None, max_length=160)
    object_type: str = Field(default="task", min_length=2, max_length=80)
    object_id: str | None = Field(default=None, max_length=200)
    object_version: str = Field(default="1.0.0", min_length=1, max_length=80)
    template_id: str = Field(default="TPL-API-V1", min_length=2, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewGateRetestRequest(BaseModel):
    status: str = Field(pattern="^(pending|pass|fail|waived)$")
    findings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewChecklistVersionCreate(BaseModel):
    object_type: str = Field(min_length=2, max_length=80)
    version: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    checklist: list[str] = Field(min_length=1)
    status: str = Field(default="active", pattern="^(active|disabled)$")
    template_id: str | None = Field(default=None, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


class ButtonPermissionState(BaseModel):
    button_id: str
    label: str
    required_permission: str
    visible: bool
    enabled: bool
    disabled_reason: str | None = None


class NavigationItem(BaseModel):
    id: str
    label: str
    path: str
    section: str
    order: int
    required_permission: str
    visible: bool
    enabled: bool
    disabled_reason: str | None = None
    button_states: list[ButtonPermissionState] = Field(default_factory=list)


class PageSurfaceContract(BaseModel):
    surface_id: str
    route: str
    owner: str
    title: str
    required_permissions: list[str] = Field(default_factory=list)
    api_operations: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class PageViewState(BaseModel):
    surface_id: str
    state: str
    trigger: str
    expected_api_calls: list[str] = Field(default_factory=list)
    expected_ui_assertions: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class BrowserVerificationRecord(BaseModel):
    verification_id: str
    surface_id: str
    route: str
    viewport: str
    status: str
    network_assertions: list[dict[str, Any]] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
    screenshot_uri: str | None = None
    recorded_at: datetime | None = None


class BusinessFlowEdge(BaseModel):
    from_state: str
    to_state: str
    trigger: str
    api_operation: str | None = None
    guard: str | None = None


class BusinessStateMachine(BaseModel):
    state_machine_id: str
    object_type: str
    states: list[str]
    initial_state: str
    terminal_states: list[str] = Field(default_factory=list)
    edges: list[BusinessFlowEdge] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    decision_id: str
    label: str
    actor: str
    input_refs: list[dict[str, Any]] = Field(default_factory=list)
    allowed_outcomes: list[str] = Field(default_factory=list)
    audit_required: bool = True


class WriteBackPoint(BaseModel):
    write_back_id: str
    label: str
    api_operation: str
    object_type: str
    required_permission: str
    audit_action: str


class BusinessQualityGate(BaseModel):
    gate_id: str
    label: str
    stage: str
    required_evidence: list[str] = Field(default_factory=list)
    blocking: bool = True


class BusinessCapabilityContract(BaseModel):
    capability_id: str
    label: str
    surface_ids: list[str] = Field(default_factory=list)
    state_machine_ids: list[str] = Field(default_factory=list)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    write_back_points: list[WriteBackPoint] = Field(default_factory=list)
    quality_gates: list[BusinessQualityGate] = Field(default_factory=list)


class ATTraceabilityRow(BaseModel):
    at_id: str
    title: str
    stage: str
    api_operation: str
    db_objects: list[str] = Field(default_factory=list)
    surface_id: str | None = None
    test_id: str | None = None
    review_gate_id: str | None = None
    status: str = "pending"


class ReviewGateRecord(BaseModel):
    review_gate_id: str
    review_id: str
    task_id: str | None = None
    object_type: str
    object_id: str
    object_version: str
    template_id: str
    status: str
    reviewer_id: str | None = None
    findings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    persistence_backend: str = "reviews"
    created_at: datetime | None = None
    completed_at: datetime | None = None


class ReviewChecklistVersion(BaseModel):
    review_checklist_version_id: str
    template_id: str
    object_type: str
    version: str
    name: str
    checklist: list[str]
    status: str
    persistence_backend: str = "review_templates"
    created_at: datetime | None = None


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    source_type: str = Field(pattern="^(synthetic|manual_upload|manual|public_web|official_api|rss|file_upload|webhook|db_import|object_storage|media|live_segment)$")
    policy: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class DataSourceUrlValidationRequest(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class DataSourceCrawlPolicyUpdate(BaseModel):
    start_url: str = Field(min_length=8, max_length=500)
    max_depth: int = Field(default=1, ge=0, le=5)
    respect_robots: bool = True
    rate_limit_per_minute: int = Field(default=30, ge=1, le=120)
    allowed_domains: list[str] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=500)


class PublicWebLinkDiscoveryRequest(BaseModel):
    start_url: str | None = Field(default=None, min_length=8, max_length=500)
    max_depth: int | None = Field(default=None, ge=0, le=5)
    limit: int = Field(default=1000, ge=1, le=5000)
    respect_robots: bool | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=500)


class DataSourceAuthUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auth_type: str = Field(pattern="^(api_key|oauth|basic|bearer)$")
    secret_ref: str = Field(min_length=6, max_length=500)
    header_name: str | None = Field(default=None, max_length=120)
    token_url: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class DataSourceConnectionTestRequest(BaseModel):
    sample_path: str | None = Field(default=None, max_length=500)
    expected_status: int = Field(default=200, ge=100, le=599)


class DataSourcePaginationUpdate(BaseModel):
    strategy: str = Field(pattern="^(page|cursor|next_url)$")
    page_param: str | None = Field(default="page", max_length=120)
    page_size_param: str | None = Field(default="page_size", max_length=120)
    cursor_param: str | None = Field(default="cursor", max_length=120)
    next_url_path: str | None = Field(default=None, max_length=500)
    max_pages: int = Field(default=3, ge=1, le=100)
    dry_run: bool = False
    reason: str | None = Field(default=None, max_length=500)


class ObjectStorageListRequest(BaseModel):
    max_keys: int = Field(default=1000, ge=1, le=1000)
    prefix: str | None = Field(default=None, max_length=500)


class DataSourceVersionPublishRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DataSourceVersionRollbackRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class DataSourceComplianceUpdate(BaseModel):
    authorization_scope: str | None = Field(default=None, max_length=160)
    authorization_basis: str | None = Field(default=None, max_length=1000)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    data_classification: str | None = Field(default=None, pattern="^(public|internal|restricted|sensitive)$")
    pii_policy: str = Field(default="masked", pattern="^(none|masked|redacted)$")
    synthetic_allowed: bool = False
    reason: str | None = Field(default=None, max_length=500)


class DataSourceStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")
    reason: str = Field(min_length=2, max_length=500)


class CollectionJobCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=200)
    schedule: str | None = Field(default=None, description="None for legacy compatibility, once, or cron:<five-field-expression>.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Scheduled jobs require query and window objects; cron jobs also receive scheduler_registration metadata.")


class CollectionJobControl(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ChannelReplayRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class RawRecordLabelCreate(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    reason: str | None = None


class DedupeDecisionCreate(BaseModel):
    decision: str = Field(pattern="^(confirm_duplicate|split_candidate)$")
    dedup_group_id: str | None = Field(default=None, min_length=2, max_length=120)
    duplicate_of_raw_record_id: str | None = Field(default=None, min_length=2, max_length=120)
    reason: str = Field(min_length=2, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class RawRecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=20000)
    content_hash: str | None = Field(default=None, max_length=120)
    raw_uri: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_id: str | None = Field(default=None, max_length=240)
    dedupe_key: str | None = Field(default=None, max_length=240)
    source_type: str | None = Field(default=None, pattern="^(synthetic|manual_upload|manual|public_web|official_api|rss|file_upload|webhook|db_import|object_storage|media|live_segment)$")
    status: str = Field(default="collected", pattern="^(collected|pending|failed|quarantined)$")
    city_id: str | None = Field(default="xian", max_length=80)
    occurred_at: datetime | None = None
    is_synthetic: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RawRecordBatchCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    collection_run_id: str | None = Field(default=None, max_length=120)
    records: list[RawRecordCreate] = Field(default_factory=list, max_length=10000)
    synthetic_count: int = Field(default=0, ge=0, le=1000000)
    response_limit: int = Field(default=100, ge=0, le=1000)
    complete_run: bool = False
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class CollectionRunMetricCounts(BaseModel):
    fetched_count: int = Field(ge=0)
    parsed_count: int = Field(ge=0)
    stored_count: int = Field(ge=0)
    cleaned_count: int = Field(ge=0)
    extracted_count: int = Field(ge=0)
    raw_record_count: int = Field(ge=0)
    payload_count: int = Field(ge=0)
    normalization_output_count: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    lineage_edge_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    cleaning_failed_count: int = Field(ge=0)
    extraction_failed_count: int = Field(ge=0)
    deduped_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    quality_issue_count: int = Field(ge=0)
    source: str
    dedupe_hit_rate: float = Field(ge=0)


class CollectionRunMetricCheck(BaseModel):
    code: str
    passed: bool
    expected: int
    actual: int
    critical: bool
    message: str


class CollectionRunMetricConsistency(BaseModel):
    status: str = Field(pattern="^(consistent|inconsistent)$")
    db_raw_record_count: int = Field(ge=0)
    raw_record_payload_count: int = Field(ge=0)
    lineage_edge_count: int = Field(ge=0)
    checks: list[CollectionRunMetricCheck] = Field(default_factory=list)


class CollectionRunMetricsView(BaseModel):
    cleaning_run_id: str
    collection_run_id: str
    collection_job_id: str
    data_source_id: str
    source_type: str | None = None
    status: str
    workflow_status: str | None = None
    trace_id: str | None = None
    metrics: CollectionRunMetricCounts
    consistency: CollectionRunMetricConsistency
    import_runs: list[dict[str, Any]] = Field(default_factory=list)
    event_count: int = Field(ge=0)
    snapshot: dict[str, Any]
    page_state: str = Field(pattern="^ready$")


class ImportRunCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=240)
    content: str | None = Field(default=None, max_length=20000)
    source_uri: str | None = Field(default=None, max_length=500)
    city_id: str | None = Field(default="xian", max_length=80)
    is_synthetic: bool = False
    media_type: str | None = Field(default=None, pattern="^(image|video|audio|live_segment)$")
    media_uri: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class DeadLetterReplayRequest(BaseModel):
    source_uri: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=240)
    content: str | None = Field(default=None, max_length=20000)
    city_id: str | None = Field(default="xian", max_length=80)
    is_synthetic: bool | None = None
    media_type: str | None = Field(default=None, pattern="^(image|video|audio|live_segment)$")
    media_uri: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class DbImportScanCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    table_name: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    schema_name: str | None = Field(default=None, max_length=160, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    cursor_field: str = Field(default="id", min_length=1, max_length=120, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    cursor_value: int | None = Field(default=None, ge=0)
    limit: int = Field(default=1000, ge=1, le=100000)
    response_limit: int = Field(default=100, ge=0, le=1000)
    city_id: str | None = Field(default="xian", max_length=80)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class DataSourceCursorRecord(BaseModel):
    cursor_scope: str = "db_import"
    table_key: str
    table_name: str
    schema_name: str | None = None
    cursor_field: str
    current_value: int | str
    storage_path: str
    last_scan: dict[str, Any] | None = None


class DataSourceCursorFailureGuard(BaseModel):
    failed_runs_do_not_advance_cursor: bool = True
    persisted_after_success_only: bool = True
    storage_path: str = "data_sources.policy.db_import_cursor"


class DataSourceCursorState(BaseModel):
    data_source_id: str
    source_type: str
    status: str
    cursor_scope: str = "db_import"
    cursor_state: dict[str, Any] = Field(default_factory=dict)
    cursor_count: int
    cursors: list[DataSourceCursorRecord] = Field(default_factory=list)
    last_db_import_scan: dict[str, Any] | None = None
    failure_guard: DataSourceCursorFailureGuard
    page_state: str = Field(pattern="^(empty|ready)$")
    source: dict[str, Any]


class ObjectStorageScanCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    prefix: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=1000, ge=1, le=10000)
    response_limit: int = Field(default=100, ge=0, le=1000)
    city_id: str | None = Field(default="xian", max_length=80)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class FileObjectOut(BaseModel):
    file_object_id: str
    tenant_id: str
    storage_key: str
    file_name: str
    mime_type: str
    byte_size: int
    checksum: str | None = None
    status: str
    access_policy: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class FileUploadResult(BaseModel):
    upload: dict[str, Any]
    file_object: FileObjectOut
    data_source: dict[str, Any]


class FileRunCreate(BaseModel):
    file_object_id: str = Field(min_length=2, max_length=120)
    title: str | None = Field(default=None, max_length=240)
    city_id: str | None = Field(default="xian", max_length=80)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class ManualRecordCreate(BaseModel):
    data_source_id: str = Field(min_length=2, max_length=120)
    title: str | None = Field(default=None, max_length=240)
    content: str | None = Field(default=None, max_length=20000)
    city_id: str | None = Field(default="xian", max_length=80)
    location: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None
    source_uri: str | None = Field(default=None, max_length=500)
    is_synthetic: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class RawRecordScope(BaseModel):
    raw_record_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=100000)
    response_limit: int = Field(default=100, ge=0, le=1000)
    rule_version: str = Field(default="s2-rules-v1.0", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class CleanRecordStatusUpdate(BaseModel):
    status: str = Field(pattern="^(valid|invalid|review_required)$")
    reason: str = Field(min_length=2, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class CityMapStateWrite(BaseModel):
    layer_mode: str = Field(pattern="^(map|satellite|heat)$")
    filters: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class EntityRef(BaseModel):
    object_type: str = Field(min_length=2, max_length=80)
    object_id: str = Field(min_length=2, max_length=120)
    object_version: str | None = Field(default=None, max_length=160)


class TopicCreate(BaseModel):
    city_id: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=240)
    created_from: EntityRef | None = None
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class TopicPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    status: str | None = Field(default=None, pattern="^(candidate|observing|active|merged|archived|converted_to_mainline)$")
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] | None = None


class ExtractionRunCreate(BaseModel):
    topic_id: str | None = Field(default=None, max_length=120)
    raw_record_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=500)
    rule_version: str = Field(default="s4a-signal-extraction-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class SignalPackageCreate(BaseModel):
    topic_id: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=200)
    rule_version: str = Field(default="s4a-signal-package-v1", min_length=2, max_length=80)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class SignalPackageItemWrite(BaseModel):
    signal_id: str = Field(min_length=2, max_length=100)
    rank: int = Field(default=0, ge=0)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceCandidateCreate(BaseModel):
    topic_id: str | None = Field(default=None, max_length=120)
    signal_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=200)
    rule_version: str = Field(default="s4b-evidence-candidate-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceReviewPatch(BaseModel):
    status: str = Field(pattern="^(confirmed|rejected|probability_reference_only|needs_review)$")
    reason: str = Field(min_length=2, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceAttachmentCreate(BaseModel):
    media_type: str = Field(pattern="^(image|video|audio|live_segment)$")
    uri: str = Field(min_length=2, max_length=500)
    content: str = Field(default="", max_length=20000)
    is_synthetic: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class MediaProcessingRunCreate(BaseModel):
    media_asset_id: str = Field(min_length=2, max_length=120)
    processor: str = Field(pattern="^(ocr|asr|frame_extract|video_ocr|scene_detect|segment_detect|live_segment|redaction)$")
    evidence_id: str | None = Field(default=None, max_length=120)
    rule_version: str = Field(default="s4b-media-processing-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceMediaLinkWrite(BaseModel):
    evidence_id: str = Field(min_length=2, max_length=120)
    media_asset_id: str = Field(min_length=2, max_length=120)
    relation: str = Field(default="supporting_media", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class RiskFactorRunCreate(BaseModel):
    topic_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list)
    rule_version: str = Field(default="s4b-risk-factor-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class RiskFactorConfidenceAdjustment(BaseModel):
    delta: float = Field(ge=-1, le=1)
    reason: str = Field(min_length=2, max_length=1000)
    input_refs: list[dict[str, Any]] = Field(default_factory=list)


class ConflictDetectionRunCreate(BaseModel):
    topic_id: str | None = Field(default=None, max_length=120)
    evidence_ids: list[str] = Field(default_factory=list)
    rule_version: str = Field(default="s4b-conflict-detection-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class CouncilAgentOutput(BaseModel):
    role: str
    stance: str
    reaction: str
    support_point_delta: dict[str, float]
    branch_probability_delta: dict[str, float]
    evidence_refs: list[str]
    uncertainty: str
    blocked_claims: list[str]


class ClosedLoopOut(BaseModel):
    case: CaseOut
    source_records: list[SourceRecordOut]
    signals: list[SignalOut]
    evidence: list[EvidenceOut]
    risk_factors: list[RiskFactorOut]
    mainline: MainlineOut | None
    world_state: WorldStateOut | None
    worldline_nodes: list[WorldlineNodeOut]
    council_sessions: list[CouncilSessionOut]
    report: ReportOut | None
    tasks: list[TaskOut]
    workflow_runs: list[WorkflowRunOut]
    audit: list[AuditLogOut]


class PageViewOut(BaseModel):
    case_id: str
    page: str
    title: str
    subtitle: str | None = None
    nav: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    raw: dict[str, Any] = {}


class SignalUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(selected_for_mainline|confirmed|needs_review|noise|excluded)$")
    priority: str | None = Field(default=None, pattern="^(P0|P1|P2|P3)$")
    reason: str | None = None
    actor: str = "analyst"


class DraftSignalRequest(BaseModel):
    signal_id: str
    action: str = Field(pattern="^(add|remove)$")
    actor: str = "analyst"
    reason: str | None = None


class MainlineCreate(BaseModel):
    case_id: str | None = None
    topic_id: str | None = None
    signal_package_id: str | None = None
    title: str
    confidence: float = 0.6
    status: str = "draft"
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "analyst"


class MainlinePatch(BaseModel):
    title: str | None = None
    confidence: float | None = None
    status: str | None = None
    payload: dict[str, Any] | None = None
    actor: str = "analyst"
    reason: str | None = None


class MainlineNodePatch(BaseModel):
    expected_version: int = Field(ge=0)
    title: str | None = Field(default=None, min_length=2, max_length=240)
    body: str | None = Field(default=None, min_length=2, max_length=4000)
    status: str | None = Field(default=None, pattern="^(draft|confirmed|evidence_gap|archived)$")
    reason: str = Field(min_length=2, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class MainlineSignalWrite(BaseModel):
    signal_id: str = Field(min_length=2, max_length=120)
    action: str = Field(pattern="^(add|remove)$")
    reason: str = Field(min_length=2, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorldStateCreate(BaseModel):
    mainline_id: str = Field(min_length=2, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class CaseGraphRunCreate(BaseModel):
    mainline_id: str = Field(min_length=2, max_length=120)
    world_state_id: str | None = Field(default=None, max_length=120)
    rule_version: str = Field(default="s5-case-graph-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class StakeholderRunCreate(BaseModel):
    mainline_id: str = Field(min_length=2, max_length=120)
    world_state_id: str | None = Field(default=None, max_length=120)
    rule_version: str = Field(default="s5-stakeholder-v1", min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class StakeholderReviewPatch(BaseModel):
    decision: str = Field(pattern="^(pass|fail|waive)$")
    reason: str = Field(min_length=2, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorldlineRunCreate(BaseModel):
    world_state_id: str = Field(min_length=2, max_length=120)
    options: dict[str, Any] = Field(default_factory=dict)


class WorldlineInterventionCreate(BaseModel):
    action: str = Field(min_length=2, max_length=160)
    reason: str = Field(min_length=2, max_length=1000)
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentProfileCreate(BaseModel):
    stakeholder_id: str = Field(min_length=2, max_length=120)
    worldline_run_id: str = Field(min_length=2, max_length=120)


class AgentProfileFilesWrite(BaseModel):
    user_md: str = Field(min_length=2, max_length=20000)
    soul_md: str = Field(min_length=2, max_length=20000)
    agent_md: str = Field(min_length=2, max_length=20000)
    reason: str | None = Field(default=None, max_length=1000)


class CouncilSessionCreate(BaseModel):
    worldline_run_id: str = Field(min_length=2, max_length=120)
    selected_node_id: str = Field(min_length=2, max_length=120)
    agent_profile_ids: list[str] = Field(min_length=1)
    hypothesis: str | None = Field(default=None, max_length=2000)


class ReportCreate(BaseModel):
    topic_id: str = Field(min_length=2, max_length=120)
    council_result_id: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)


class ReportPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    sections: list[dict[str, Any]] | None = None
    reason: str | None = Field(default=None, max_length=1000)


class ReportExportCreate(BaseModel):
    format: str = Field(default="markdown", pattern="^(markdown|json)$")
    reason: str | None = Field(default=None, max_length=1000)


class RetrospectiveCreate(BaseModel):
    report_id: str = Field(min_length=2, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)


class KnowledgeItemCreate(BaseModel):
    retrospective_id: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=2, max_length=5000)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = Field(default=None, max_length=1000)


class CaseLibraryApplyCreate(BaseModel):
    case_id: str = Field(min_length=2, max_length=120)
    object_type: str = Field(min_length=2, max_length=80)
    object_id: str = Field(min_length=2, max_length=120)
    reason: str | None = Field(default=None, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionCreate(BaseModel):
    config_type: str = Field(pattern="^(data_source|taxonomy|model|agent|prompt)$")
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=1000)


class ConfigApprovalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ConfigRollbackRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class PressureTestRequest(BaseModel):
    hypothesis: str
    actor: str = "analyst"


class TaskCreate(BaseModel):
    case_id: str | None = None
    report_id: str | None = None
    title: str
    owner: str
    due_label: str = "2h"
    due_at: datetime | None = None
    status: str = Field(default="suggested", pattern="^(suggested|in_progress|completed|overdue|blocked)$")
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "operator"


class CaseMemoryActionRequest(BaseModel):
    action: str = Field(pattern="^(save_draft|submit_review|confirm_ingest)$")
    actor: str = "analyst"
    payload: dict[str, Any] = {}


class LibraryApplyRequest(BaseModel):
    case_id: str
    object_type: str
    object_id: str
    actor: str = "analyst"
    reason: str | None = None
    payload: dict[str, Any] = {}


class ConfigVersionActionRequest(BaseModel):
    case_id: str
    action: str = Field(pattern="^(run_regression|submit_approval|publish)$")
    actor: str = "admin"
    payload: dict[str, Any] = {}


class GenericActionOut(BaseModel):
    status: str
    object_type: str
    object_id: str
    payload: dict[str, Any] = {}
