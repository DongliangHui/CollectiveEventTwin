export type JsonMap = Record<string, unknown>;

export type CaseOut = {
  id: string;
  slug: string;
  title: string;
  scenario_type: string;
  status: string;
  payload: JsonMap;
};

export type SourceRecord = {
  id: string;
  case_id: string;
  source_id: string;
  source_name: string;
  access_mode: string;
  status: string;
  trust: number;
  accepted: boolean;
  blocked_reason: string | null;
  payload: JsonMap;
};

export type Signal = {
  id: string;
  case_id: string;
  topic_id?: string | null;
  mainline_id: string | null;
  title: string;
  summary: string;
  priority: string;
  region_id: string;
  status: string;
  scores: Record<string, number>;
  payload: JsonMap;
};

export type Evidence = {
  id: string;
  case_id: string;
  signal_id: string | null;
  title: string;
  excerpt: string;
  masked_excerpt: string;
  source: string;
  credibility: string;
  status: string;
  sensitivity: string;
  payload: JsonMap;
};

export type RiskFactor = {
  id: string;
  case_id: string;
  name: string;
  category: string;
  confidence: number;
  status: string;
  payload: { evidence_refs?: string[]; trigger_reason?: string };
};

export type Mainline = {
  id: string;
  case_id: string;
  topic_id?: string | null;
  title: string;
  confidence: number;
  status: string;
  version?: string;
  evidence_gap_count?: number;
  payload: JsonMap & { signals?: string[]; signal_ids?: string[]; support_points?: string[]; evidence_gaps?: string[] };
};

export type WorldState = {
  id: string;
  case_id: string;
  mainline_id?: string | null;
  title: string;
  status: string;
  version?: string;
  payload: JsonMap;
};

export type WorldlineNode = {
  id: string;
  case_id: string;
  title: string;
  branch: string;
  probability: number;
  risk: number;
  status: string;
  payload: { needsCouncil?: boolean; support_point_state?: string[] };
};

export type CouncilAgent = {
  role: string;
  stance: string;
  reaction: string;
  support_point_delta: Record<string, number>;
  branch_probability_delta: Record<string, number>;
  evidence_refs: string[];
  uncertainty: string;
  blocked_claims: string[];
};

export type CouncilSession = {
  id: string;
  case_id: string;
  node_id: string;
  hypothesis: string;
  status: string;
  payload: {
    agents?: CouncilAgent[];
    summary?: string;
    branch_changes?: Array<Record<string, unknown>>;
    schema_version?: string;
  };
};

export type Report = {
  id: string;
  case_id: string;
  topic_id?: string | null;
  title: string;
  human_confirmed: boolean;
  status: string;
  version?: string;
  review_id?: string | null;
  synthetic_watermark?: boolean;
  payload: JsonMap & { draft_summary?: string; formal_conclusion?: string; compliance_note?: string; council_result_id?: string; evidence_refs?: JsonMap[] };
};

export type Task = {
  id: string;
  case_id: string;
  report_id?: string | null;
  title: string;
  owner: string;
  due_label: string;
  due_at?: string | null;
  status: string;
  evidence_refs?: JsonMap[];
  payload: JsonMap;
};

export type Retrospective = {
  id: string;
  report_id: string;
  case_id: string;
  status: string;
  version?: string;
  review_id?: string | null;
  summary: string;
  source_refs: JsonMap[];
  payload: JsonMap;
};

export type KnowledgeItem = {
  id: string;
  retrospective_id: string;
  report_id: string;
  case_id: string;
  status: string;
  content: string;
  source_refs: JsonMap[];
  payload: JsonMap;
};

export type CaseLibraryEntry = {
  id: string;
  case_id: string;
  retrospective_id: string;
  knowledge_item_id: string;
  title: string;
  status: string;
  tags: string[];
  source_refs: JsonMap[];
  payload: JsonMap;
};

export type ConfigVersion = {
  id: string;
  config_type: string;
  version: string;
  status: string;
  review_id?: string | null;
  regression_workflow_run_id?: string | null;
  input_refs: JsonMap[];
  impact_scope: JsonMap;
  payload: JsonMap;
};

export type ConfigRelease = {
  id: string;
  config_version_id: string;
  status: string;
  impact_scope: JsonMap;
  payload: JsonMap;
};

export type WorkflowRun = {
  workflow_run_id?: string;
  id: string;
  case_id: string;
  workflow_name: string;
  workflow_id: string;
  status: string;
  payload: JsonMap;
};

export type AuditLog = {
  id: string;
  case_id: string;
  actor: string;
  action: string;
  object_type: string;
  object_id: string;
  reason: string | null;
  payload: JsonMap;
  created_at: string;
};

export type MapFeature = {
  type: "Feature";
  id: string;
  geometry: { type: "Point"; coordinates: number[] };
  properties: {
    featureId: string;
    regionId: string;
    featureType: string;
    title: string;
    summary: string;
    mainlineId: string | null;
    riskScore: number;
    confidence: number;
  };
};

export type MapLayers = {
  caseId: string;
  eventPoints: { type: "FeatureCollection"; features: MapFeature[] };
  riskAreas: { type: "FeatureCollection"; features: MapFeature[] };
  config: { center: number[]; zoom: number };
};

export type CaseBundle = {
  case: CaseOut;
  source_records: SourceRecord[];
  signals: Signal[];
  evidence: Evidence[];
  risk_factors: RiskFactor[];
  mainline: Mainline | null;
  world_state: WorldState | null;
  worldline_nodes: WorldlineNode[];
  council_sessions: CouncilSession[];
  report: Report | null;
  tasks: Task[];
  workflow_runs: WorkflowRun[];
  audit: AuditLog[];
};

export type ProductPageName =
  | "city"
  | "risk"
  | "data"
  | "evidence"
  | "mainline"
  | "worldline"
  | "council"
  | "brief"
  | "memory"
  | "library"
  | "config";

export type PageMetric = {
  label: string;
  value: string | number;
  tone?: string;
  helper?: string;
};

export type PageSection = {
  id: string;
  title: string;
  kind: string;
  items?: unknown[];
  meta?: unknown;
};

export type PageAction = {
  id: string;
  label: string;
  to_page?: ProductPageName;
  object_id?: string | null;
};

export type PageView = {
  case_id: string;
  page: ProductPageName;
  title: string;
  subtitle: string | null;
  nav: Array<{ page: ProductPageName; label: string; path: string }>;
  metrics: PageMetric[];
  sections: PageSection[];
  actions: PageAction[];
  raw: JsonMap;
};

export type ApiEnvelope<T> = {
  data: T;
  meta: JsonMap;
  trace_id: string;
};

export type AuthRole = {
  role_id: string;
  name: string;
  status: string;
};

export type AuthUser = {
  user_id: string;
  tenant_id: string;
  username: string;
  display_name: string;
  status: string;
  roles: AuthRole[];
  permissions: string[];
};

export type AuthTokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

export type PermissionButtonState = {
  button_id: string;
  label: string;
  required_permission: string;
  visible: boolean;
  enabled: boolean;
  disabled_reason: string | null;
};

export type CurrentPermissionResponse = {
  permissions: string[];
  button_states: PermissionButtonState[];
};

export type NavigationItem = {
  id: string;
  label: string;
  path: string;
  section: string;
  order: number;
  required_permission: string;
  visible: boolean;
  enabled: boolean;
  disabled_reason: string | null;
  button_states: PermissionButtonState[];
};

export type NavigationResponse = {
  items: NavigationItem[];
  button_states: PermissionButtonState[];
};

export type RoleRecord = {
  role_id: string;
  name: string;
  description: string | null;
  status: string;
  permission_codes: string[];
};

export type S1AuditLog = {
  audit_id: string;
  tenant_id: string | null;
  case_id: string | null;
  actor_id: string | null;
  actor: string;
  action: string;
  object_type: string;
  object_id: string;
  object_version: string | null;
  reason: string | null;
  trace_id: string | null;
  created_at: string;
};

export type ReviewTemplate = {
  id: string;
  object_type: string;
  version: string;
  name: string;
  checklist: string[];
  status: string;
};

export type ReviewRecord = {
  review_id: string;
  object_type: string;
  object_id: string;
  object_version: string;
  template_id: string;
  status: "pending" | "pass" | "fail" | "waived";
  reviewer_id: string | null;
  findings: string[];
  blockers: string[];
  waiver_reason: string | null;
  created_at: string;
  completed_at: string | null;
};

export type GateCheck = {
  passed: boolean;
  blockers: string[];
};

export type OpsHealth = {
  component?: string;
  status: string;
  checked_at?: string;
  latency_ms?: number;
  source?: string;
};

export type OpsWorker = {
  worker_id: string;
  status: string;
  backlog_count: number;
  last_seen_at: string | null;
  source: string;
};

export type DataSourceRecord = {
  data_source_id: string;
  name: string;
  source_type: string;
  status: string;
  is_synthetic: boolean;
  policy: JsonMap;
  payload: JsonMap;
  webhook_secret_once?: string;
};

export type DataSourceUrlValidation = {
  url: string;
  reachable: boolean;
  status_code: number | null;
  content_type: string | null;
  latency_ms: number;
  is_synthetic: boolean;
  validation_mode: string;
  error_code?: string | null;
  error_message?: string | null;
};

export type DataSourceConnectionTest = {
  status: string;
  classification: string;
  status_code: number | null;
  latency_ms: number;
  is_synthetic: boolean;
  sample_metadata: JsonMap;
};

export type DataSourceCursorState = {
  data_source_id: string;
  source_type: string;
  status: string;
  cursor_scope: string;
  cursor_state: JsonMap;
  cursor_count: number;
  cursors: Array<{
    cursor_scope: string;
    table_key: string;
    table_name: string;
    schema_name?: string | null;
    cursor_field: string;
    current_value: number | string;
    storage_path: string;
    last_scan?: JsonMap | null;
  }>;
  last_db_import_scan?: JsonMap | null;
  failure_guard: JsonMap;
  page_state: "empty" | "ready";
  source: DataSourceRecord;
};

export type PublicWebLinkDiscovery = {
  data_source: DataSourceRecord;
  collection_job: CollectionJobRecord;
  collection_run: CollectionRunRecord;
  activity: JsonMap & {
    activity_name?: string;
    status?: string;
    discovered_count?: number;
    skipped_count?: number;
  };
  pending_urls: Array<JsonMap & { url?: string; depth?: number; status?: string }>;
  skipped_urls: Array<JsonMap & { url?: string; reason?: string }>;
};

export type AdapterCapability = {
  source_type: string;
  label: string;
  status: string;
  capabilities: { input?: string[]; outputs?: string[]; supports_synthetic?: boolean };
  required_methods: string[];
};

export type CollectionChannel = {
  channel: string;
  label: string;
  source_type: string;
  adapter_source_type: string;
  status: "available" | "degraded" | "not_configured";
  configured: boolean;
  adapter_registered: boolean;
  requires_external_key: boolean;
  capabilities: JsonMap;
  synthetic_supported: boolean;
  schema_path: string;
  quality_metrics_path: string;
  warnings: JsonMap[];
};

export type ChannelAdapterContractValidation = {
  service: string;
  status: "passed" | "failed";
  required_methods: string[];
  adapter_count: number;
  checked_channel_count: number;
  failure_count: number;
  degraded_channel_count: number;
  adapters: Array<{
    source_type: string;
    label: string;
    status: "passed" | "failed";
    required_methods: string[];
    method_status: Record<string, boolean>;
    missing_methods: string[];
    capabilities: JsonMap;
    synthetic_supported: boolean;
    channel_refs: string[];
  }>;
  channels: Array<{
    channel: string;
    source_type: string;
    adapter_source_type: string;
    adapter_registered: boolean;
    contract_status: "passed" | "failed" | "degraded" | "not_configured";
    required_methods: string[];
    method_status: Record<string, boolean>;
    missing_methods: string[];
    warnings: JsonMap[];
  }>;
};

export type CollectionChannelSchema = {
  channel: string;
  label: string;
  source_type: string;
  adapter_source_type: string;
  version: string;
  status: "ready" | "degraded" | "not_configured";
  schema_kind: string;
  required_fields: string[];
  json_schema: JsonMap;
  ui_schema: JsonMap;
  validation: JsonMap;
  workflow_refs: string[];
  warnings: JsonMap[];
  adapter_registered: boolean;
  adapter_contract_status: string;
};

export type ChannelErrorMapping = {
  channel: string;
  error_code: string;
  known: boolean;
  label: string;
  classification: string;
  severity: "info" | "warning" | "error" | "critical";
  retryable: boolean;
  remediation: string;
  run_detail_hint: string;
  source: string;
};

export type ChannelErrorCodeMap = {
  service: string;
  version: string;
  status: "ready" | "degraded";
  requested: { channel?: string | null; error_code?: string | null };
  summary: {
    channel_count: number;
    returned_channel_count: number;
    mapping_count: number;
    registered_mapping_count: number;
    unknown_count: number;
    warning_count: number;
  };
  channels: Array<{
    channel: string;
    label: string;
    source_type?: string;
    adapter_source_type?: string;
    mapping_count: number;
    mappings: ChannelErrorMapping[];
    fallback: {
      classification: "unknown";
      severity: "warning";
      retryable: false;
      warning_code: "CHANNEL_ERROR_CODE_UNMAPPED";
    };
  }>;
  results: ChannelErrorMapping[];
  warnings: JsonMap[];
};

export type DataSourceVersion = {
  data_source_version_id: string;
  tenant_id: string;
  data_source_id: string;
  version: number;
  status: string;
  config_hash: string;
  policy_snapshot: JsonMap;
  payload: JsonMap;
  published_by_id: string | null;
  published_at: string | null;
};

export type CollectionJobRecord = {
  collection_job_id: string;
  tenant_id: string;
  data_source_id: string;
  created_by_id: string | null;
  name: string;
  status: string;
  schedule: string | null;
  payload: JsonMap;
  created_at: string;
  updated_at: string;
};

export type CollectionJobDetail = CollectionJobRecord & {
  source: DataSourceRecord | null;
  config: JsonMap;
  version_pin: JsonMap;
  latest_runs: JsonMap[];
  run_summary: JsonMap;
  page_state: string;
};

export type CollectionRunRecord = {
  collection_run_id: string;
  collection_job_id: string;
  data_source_id: string;
  status: string;
  record_count: number;
  error_code: string | null;
  error_message: string | null;
  trace_id: string | null;
  payload: JsonMap;
  created_at: string;
  updated_at: string;
};

export type CollectionRunStepRecord = {
  step_key: "fetch" | "parse" | "store" | "clean" | "extract";
  label: string;
  description: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  event_count: number;
  event_refs: JsonMap[];
  payload: JsonMap;
};

export type CollectionRunStepsView = {
  collection_run_id: string;
  collection_job_id: string;
  data_source_id: string;
  status: string;
  workflow_run_id: string | null;
  workflow_status: string | null;
  raw_record_count: number;
  record_count: number;
  trace_id: string | null;
  page_state: string;
  steps: CollectionRunStepRecord[];
  events: JsonMap[];
};

export type CollectionRunMetricsView = {
  cleaning_run_id: string;
  collection_run_id: string;
  collection_job_id: string;
  data_source_id: string;
  source_type: string | null;
  status: string;
  workflow_status: string | null;
  trace_id: string | null;
  metrics: {
    fetched_count: number;
    parsed_count: number;
    stored_count: number;
    cleaned_count: number;
    extracted_count: number;
    raw_record_count: number;
    payload_count: number;
    normalization_output_count: number;
    signal_count: number;
    lineage_edge_count: number;
    failed_count: number;
    cleaning_failed_count: number;
    extraction_failed_count: number;
    deduped_count: number;
    conflict_count: number;
    quality_issue_count: number;
    source: string;
    dedupe_hit_rate: number;
  };
  consistency: {
    status: "consistent" | "inconsistent";
    db_raw_record_count: number;
    raw_record_payload_count: number;
    lineage_edge_count: number;
    checks: JsonMap[];
  };
  import_runs: JsonMap[];
  event_count: number;
  snapshot: JsonMap;
  page_state: "ready";
};

export type DataSourceHealthDetail = {
  data_source_id: string;
  source_health_id: string | null;
  status: string;
  source: DataSourceRecord;
  policy_result: JsonMap;
  operational_state: JsonMap | null;
  last_success: JsonMap | null;
  last_failure: JsonMap | null;
  error_rate: number;
  success_count: number;
  failure_count: number;
  last_error_code: string | null;
  last_run_id: string | null;
  recent_runs: JsonMap[];
  page_state: string;
  payload: JsonMap;
};

export type DataSourceRateLimitStatus = {
  data_source_id: string;
  channel?: string | null;
  status: "unconfigured" | "available" | "limited";
  config: JsonMap | null;
  state: JsonMap & {
    enabled?: boolean;
    used?: number;
    remaining?: number | null;
    delayed_count?: number;
    next_allowed_at?: string | null;
    last_delayed_run_id?: string | null;
  };
  channel_states?: Record<string, JsonMap>;
  recent_delayed_runs: CollectionRunRecord[];
  source_policy?: JsonMap | null;
  page_state: string;
};

export type CollectionChannelQualityMetrics = {
  channel: string;
  metrics_source: string;
  summary: JsonMap & {
    run_count?: number;
    completed_run_count?: number;
    failed_run_count?: number;
    delayed_run_count?: number;
    raw_record_count?: number;
    quality_issue_count?: number;
    lineage_edge_count?: number;
    deduped_count?: number;
    conflict_count?: number;
    p95_latency_ms?: number;
  };
  runs: JsonMap[];
  page_state: string;
  generated_at: string;
};

export type CollectionChannelMaintenance = {
  tenant_id: string;
  metrics_source: string;
  summary: JsonMap & {
    channel_count?: number;
    ready_channel_count?: number;
    degraded_channel_count?: number;
    empty_channel_count?: number;
    warning_count?: number;
    high_failure_channel_count?: number;
    missing_metrics_channel_count?: number;
    run_count?: number;
    failed_run_count?: number;
    delayed_run_count?: number;
    p95_latency_ms?: number;
  };
  channels: JsonMap[];
  page_state: string;
  generated_at: string;
  metrics_snapshot_id: string;
};

export type DataSourceRssInspection = {
  feed_url: string;
  title: string | null;
  item_count: number;
  latest_time: string | null;
  latency_ms: number;
  is_synthetic: boolean;
  inspect_mode: string;
  sample_items?: JsonMap[];
};

export type RawRecord = {
  raw_record_id: string;
  data_source_id: string;
  collection_run_id: string;
  source_type: string;
  title: string;
  content_hash: string;
  status: string;
  is_synthetic: boolean;
  city_id: string | null;
  payload: JsonMap;
};

export type CleanRecord = RawRecord & {
  clean_record_id: string;
  normalization_output_id?: string | null;
  normalization_run_id?: string | null;
  raw_title?: string;
  clean_status: string;
  raw_status: string;
  created_at?: string;
  updated_at?: string;
  cleaned_at?: string | null;
  normalized_text_preview?: string;
  masked_text_preview: string;
  content_redacted: boolean;
  access_mode: "redacted";
  default_display: "masked_text";
  original_available: boolean;
  original_access_path?: string | null;
  redacted_export_path?: string | null;
  required_permission: string;
  original_access_required_permission: string;
  dedupe_group_id?: string | null;
  dedupe_decision_id?: string | null;
  duplicate_of_raw_record_id?: string | null;
  merge_state?: string | null;
  candidate_only?: boolean | null;
  review_required?: boolean | null;
  quality_issue_count: number;
  quality_score?: number | null;
  quality_scores?: JsonMap | null;
  quality_band?: string | null;
  quality_scored_at?: string | null;
  dedupe_state: JsonMap;
  normalization?: JsonMap | null;
};

export type CleanRecordDetail = {
  clean_record_id: string;
  raw_record_id: string;
  clean_record: CleanRecord;
  raw: RawRecord & JsonMap;
  clean: JsonMap & {
    status?: string;
    latest_normalization?: JsonMap | null;
    normalization_history?: JsonMap[];
    normalization_count?: number;
    dedupe_state?: JsonMap;
  };
  quality: JsonMap & {
    issue_count?: number;
    issues?: JsonMap[];
  };
  extractions: JsonMap & {
    signal_count?: number;
    signals?: JsonMap[];
  };
  lineage: JsonMap & {
    edge_count?: number;
    edges?: JsonMap[];
  };
  access: JsonMap;
  page_state: string;
};

export type CleanRecordListParams = {
  status?: string;
  dataSourceId?: string;
  sourceType?: string;
  createdFrom?: string;
  createdTo?: string;
  page?: number;
  pageSize?: number;
};

export type CleanRecordStatusUpdateResult = {
  clean_record: CleanRecord;
  status_transition: JsonMap;
  downstream_effect: JsonMap & { signal_generation_allowed?: boolean; blocked_reason?: string | null };
  report_lock: JsonMap;
};

export type DataQualityIssue = {
  quality_issue_id: string;
  tenant_id: string;
  data_quality_run_id: string;
  raw_record_id: string;
  issue_type: string;
  severity: string;
  message: string;
  payload: JsonMap;
  created_at?: string;
  data_quality_run: JsonMap & { data_quality_run_id?: string; status?: string; rule_version?: string };
  raw_record: JsonMap & {
    raw_record_id?: string;
    data_source_id?: string;
    source_type?: string;
    title?: string;
    status?: string;
    city_id?: string | null;
    is_synthetic?: boolean;
  };
  score?: JsonMap | null;
  quality_score?: number | null;
  quality_band?: string | null;
  evidence_refs: JsonMap[];
};

export type DataQualityIssueListParams = {
  issueType?: string;
  severity?: string;
  dataQualityRunId?: string;
  rawRecordId?: string;
  dataSourceId?: string;
  sourceType?: string;
  createdFrom?: string;
  createdTo?: string;
  page?: number;
  pageSize?: number;
};

export type S2RunRecord = JsonMap & {
  status?: string;
  import_type?: string;
  record_count?: number;
  input_count?: number;
  output_count?: number;
  duplicate_group_count?: number;
  issue_count?: number;
  quality_scorer?: JsonMap;
  error_code?: string | null;
};

export type PageViewModel = {
  page_state: "loading" | "ready" | "empty" | "error" | "degraded" | "no_permission";
  permissions: JsonMap;
  refresh_at: string;
  data_freshness: JsonMap;
  degraded_sources: JsonMap[];
  audit_context: JsonMap;
  primary_data: JsonMap;
  actions: Array<{ id: string; label: string; method: string; href: string; enabled: boolean; disabled_reason?: string | null }>;
};

export type CityRecord = {
  id: string;
  name: string;
  region_code?: string;
  status?: string;
  payload?: JsonMap;
};

export type CityEventRecord = {
  id: string;
  city_id: string;
  topic_id: string | null;
  raw_record_id?: string | null;
  title: string;
  summary?: string;
  status: string;
  event_type?: string;
  heat_score: number;
  risk_score?: number;
  evidence_refs: JsonMap[];
  payload: JsonMap;
};

export type CityMapLayer = {
  id: string;
  layer_type: "map" | "satellite" | "heat" | "point" | "cluster";
  features: JsonMap[];
};

export type CityMapStateWrite = {
  layer_mode: "map" | "satellite" | "heat";
  filters?: JsonMap;
  reason?: string;
};

export type EntityRef = {
  object_type: string;
  object_id: string;
  object_version?: string | null;
};

export type TopicRecord = {
  id: string;
  tenant_id: string;
  city_id: string;
  title: string;
  status: string;
  heat_score: number;
  created_from: EntityRef | null;
  payload: JsonMap;
  created_at: string;
  updated_at: string;
  event_count?: number;
  evidence_ref_count?: number;
};

export type TopicCreateInput = {
  city_id: string;
  title: string;
  created_from?: EntityRef | null;
  reason?: string;
  payload?: JsonMap;
};

export type TopicPatchInput = {
  title?: string;
  status?: "candidate" | "observing" | "active" | "merged" | "archived" | "converted_to_mainline";
  reason?: string;
  payload?: JsonMap;
};

export type ExtractionRunInput = {
  topic_id?: string | null;
  raw_record_ids?: string[];
  limit?: number;
  rule_version?: string;
  payload?: JsonMap;
};

export type SignalPackageRecord = {
  signal_package_id: string;
  id: string;
  topic_id: string;
  name: string;
  status: string;
  rule_version: string;
  payload: JsonMap;
  items: Array<JsonMap & { signal_id?: string; signal?: Signal }>;
};

export type SignalPackageCreateInput = {
  topic_id: string;
  name: string;
  rule_version?: string;
  reason?: string;
  payload?: JsonMap;
};

export type SignalPackageItemInput = {
  signal_id: string;
  rank?: number;
  reason?: string;
  payload?: JsonMap;
};

export type EvidenceCandidateInput = {
  topic_id?: string | null;
  signal_ids?: string[];
  limit?: number;
  rule_version?: string;
  payload?: JsonMap;
};

export type EvidenceReviewPatchInput = {
  status: "confirmed" | "rejected" | "probability_reference_only" | "needs_review";
  reason: string;
  payload?: JsonMap;
};

export type EvidenceAttachmentInput = {
  media_type: "image" | "video" | "audio" | "live_segment";
  uri: string;
  content?: string;
  is_synthetic?: boolean;
  payload?: JsonMap;
};

export type MediaProcessingRunInput = {
  media_asset_id: string;
  processor: "ocr" | "asr" | "frame_extract" | "video_ocr" | "scene_detect" | "segment_detect" | "live_segment" | "redaction";
  evidence_id?: string | null;
  rule_version?: string;
  payload?: JsonMap;
};

export type RiskFactorRunInput = {
  topic_id?: string | null;
  evidence_ids?: string[];
  rule_version?: string;
  payload?: JsonMap;
};

export type ConflictDetectionRunInput = {
  topic_id?: string | null;
  evidence_ids?: string[];
  rule_version?: string;
  payload?: JsonMap;
};

export type MainlineCreateInput = {
  topic_id: string;
  signal_package_id: string;
  title: string;
  reason?: string;
  payload?: JsonMap;
};

export type MainlineNodePatchInput = {
  expected_version: number;
  title?: string;
  body?: string;
  status?: "draft" | "confirmed" | "evidence_gap" | "archived";
  reason: string;
  payload?: JsonMap;
};

export type MainlineSignalInput = {
  signal_id: string;
  action: "add" | "remove";
  reason: string;
  payload?: JsonMap;
};

export type WorldStateCreateInput = {
  mainline_id: string;
  reason?: string;
  payload?: JsonMap;
};

export type CaseGraphRunInput = {
  mainline_id: string;
  world_state_id?: string | null;
  rule_version?: string;
  payload?: JsonMap;
};

export type StakeholderRunInput = {
  mainline_id: string;
  world_state_id?: string | null;
  rule_version?: string;
  payload?: JsonMap;
};

export type StakeholderReviewInput = {
  decision: "pass" | "fail" | "waive";
  reason: string;
  payload?: JsonMap;
};

export type WorldlineRunCreateInput = {
  world_state_id: string;
  options?: JsonMap;
};

export type WorldlineInterventionInput = {
  action: string;
  reason: string;
  constraints?: JsonMap;
};

export type AgentProfileCreateInput = {
  stakeholder_id: string;
  worldline_run_id: string;
};

export type AgentProfileFilesInput = {
  user_md: string;
  soul_md: string;
  agent_md: string;
  reason?: string;
};

export type CouncilSessionCreateInput = {
  worldline_run_id: string;
  selected_node_id: string;
  agent_profile_ids: string[];
  hypothesis?: string;
};

export type ReportCreateInput = {
  topic_id: string;
  council_result_id?: string | null;
  reason?: string;
};

export type ReportPatchInput = {
  title?: string;
  sections?: JsonMap[];
  reason?: string;
};

export type ReportExportInput = {
  format?: "markdown" | "json";
  reason?: string;
};

export type ConfigVersionCreateInput = {
  config_type: "data_source" | "taxonomy" | "model" | "agent" | "prompt";
  payload: JsonMap;
  reason?: string;
};

export type FileUploadRunInput = {
  title?: string;
  cityId?: string;
  reason?: string;
  payload?: JsonMap;
};

export type ManualRecordInput = {
  title?: string;
  content?: string;
  cityId?: string | null;
  location?: string;
  occurredAt?: string;
  sourceUri?: string;
  isSynthetic?: boolean;
  payload?: JsonMap;
  reason?: string;
};

export type RawRecordRepositoryRecordInput = {
  title: string;
  content: string;
  contentHash?: string;
  rawUri?: string;
  metadata?: JsonMap;
  externalId?: string;
  dedupeKey?: string;
  sourceType?: string;
  status?: string;
  cityId?: string;
  occurredAt?: string;
  isSynthetic?: boolean;
  payload?: JsonMap;
};

export type RawRecordBatchInput = {
  dataSourceId: string;
  collectionRunId?: string;
  records?: RawRecordRepositoryRecordInput[];
  syntheticCount?: number;
  responseLimit?: number;
  completeRun?: boolean;
  reason?: string;
  payload?: JsonMap;
};

export type DbImportScanInput = {
  tableName: string;
  schemaName?: string;
  cursorField?: string;
  cursorValue?: number;
  limit?: number;
  responseLimit?: number;
  cityId?: string;
  reason?: string;
  payload?: JsonMap;
};

export type ObjectStorageScanInput = {
  prefix?: string;
  limit?: number;
  responseLimit?: number;
  cityId?: string;
  reason?: string;
  payload?: JsonMap;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_STORAGE_KEY = "cet_access_token";

export function setAuthToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;
  if (!isFormData) headers.set("Content-Type", "application/json");
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    const detail = await response.text();
    try {
      const payload = JSON.parse(detail) as { error?: { code?: string; message?: string } };
      if (payload.error?.code) {
        throw new Error(`${payload.error.code}: ${payload.error.message ?? response.statusText}`);
      }
    } catch (error) {
      if (error instanceof Error && error.message.includes(":")) throw error;
    }
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return (await response.json()) as T;
}

async function hmacSha256(secret: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return Array.from(new Uint8Array(signature)).map((value) => value.toString(16).padStart(2, "0")).join("");
}

function objectValue(value: unknown): JsonMap {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonMap) : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function stringField(value: unknown, key: string): string | undefined {
  return stringValue(objectValue(value)[key]);
}

function numberField(value: unknown, key: string): number | undefined {
  const raw = objectValue(value)[key];
  return typeof raw === "number" ? raw : undefined;
}

function cityOverviewToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return legacy as unknown as PageView;
  }
  return {
    case_id: "xian-city",
    page: "city",
    title: "Xi'an City Situation",
    subtitle: String(model.data_freshness?.source ?? "PostgreSQL city view"),
    nav: [],
    metrics: Array.isArray(primary.metrics) ? (primary.metrics as PageMetric[]) : [],
    sections: Array.isArray(primary.sections) ? (primary.sections as PageSection[]) : [],
    actions: [],
    raw: primary
  };
}

function topicSituationToPageView(model: PageViewModel, sidecar: JsonMap = {}): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      raw: {
        ...objectValue((legacy as JsonMap).raw),
        sidecar
      }
    };
  }
  return {
    case_id: "xian-topic",
    page: "risk",
    title: "Topic Situation",
    subtitle: String(objectValue(primary.topic).title ?? "PostgreSQL topic view"),
    nav: [],
    metrics: [
      { label: "Related events", value: Array.isArray(primary.events) ? primary.events.length : 0, tone: "blue" },
      { label: "Evidence refs", value: Array.isArray(primary.evidence_refs) ? primary.evidence_refs.length : 0, tone: "green" }
    ],
    sections: [
      { id: "sources", title: "Topic source breakdown", kind: "sources", items: Array.isArray(objectValue(primary.source_breakdown).by_source_type) ? (objectValue(primary.source_breakdown).by_source_type as unknown[]) : [] },
      { id: "phase", title: "Topic spread phase", kind: "timeline", items: Array.isArray(primary.spread_paths) ? (primary.spread_paths as unknown[]) : [] },
      { id: "sentiment", title: "Emotion and stance", kind: "sentiment", items: Array.isArray(objectValue(primary.emotion_stance).sentiment) ? (objectValue(primary.emotion_stance).sentiment as unknown[]) : [] },
      { id: "candidates", title: "Candidate mainlines", kind: "mainlines", items: Array.isArray(primary.candidate_mainlines) ? (primary.candidate_mainlines as unknown[]) : [] },
      { id: "review", title: "Evidence references", kind: "signals", items: Array.isArray(primary.events) ? (primary.events as unknown[]) : [] }
    ],
    actions: [{ id: "enter-mainline", label: "Enter mainline modeling", to_page: "mainline" }],
    raw: { ...primary, sidecar }
  };
}

function signalWorkbenchToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const topic = objectValue(primary.topic);
  const topicId = typeof topic.id === "string" ? topic.id : undefined;
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      raw: {
        ...objectValue((legacy as JsonMap).raw),
        topic_id: topicId ?? objectValue((legacy as JsonMap).raw).topic_id,
        source: "postgresql",
        workbench_state: model.page_state
      }
    };
  }
  return {
    case_id: "xian-signal",
    page: "data",
    title: "Data / Signal Workbench",
    subtitle: typeof topic.title === "string" ? topic.title : "PostgreSQL signal workbench",
    nav: [],
    metrics: [
      { label: "Candidate signals", value: Array.isArray(primary.signals) ? primary.signals.length : 0, tone: "blue" },
      { label: "Signal packages", value: Array.isArray(primary.signal_packages) ? primary.signal_packages.length : 0, tone: "green" },
      { label: "Extraction runs", value: Array.isArray(primary.extraction_runs) ? primary.extraction_runs.length : 0, tone: "amber" },
      { label: "Lineage edges", value: Number(objectValue(primary.lineage_summary).lineage_edge_count ?? 0), tone: "violet" }
    ],
    sections: [
      { id: "signals", title: "Signal search results", kind: "signal-table", items: Array.isArray(primary.signals) ? (primary.signals as unknown[]) : [] },
      { id: "packages", title: "Signal packages", kind: "packages", items: Array.isArray(primary.signal_packages) ? (primary.signal_packages as unknown[]) : [] },
      { id: "runs", title: "Extraction runs", kind: "timeline", items: Array.isArray(primary.extraction_runs) ? (primary.extraction_runs as unknown[]) : [] },
      { id: "lineage", title: "Input lineage", kind: "chips", items: Array.isArray(primary.lineage) ? (primary.lineage as unknown[]) : [] }
    ],
    actions: [{ id: "enter-evidence", label: "Enter evidence review", to_page: "evidence" }],
    raw: { ...primary, topic_id: topicId, source: "postgresql", workbench_state: model.page_state }
  };
}

function evidenceReviewToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const review = objectValue(primary.review);
  const evidence = objectValue(primary.evidence);
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      raw: {
        ...objectValue((legacy as JsonMap).raw),
        evidence_review_id: typeof review.evidence_review_id === "string" ? review.evidence_review_id : objectValue((legacy as JsonMap).raw).evidence_review_id,
        evidence_id: typeof evidence.id === "string" ? evidence.id : objectValue((legacy as JsonMap).raw).evidence_id,
        source: "postgresql",
        review_state: model.page_state
      }
    };
  }
  return {
    case_id: typeof evidence.case_id === "string" ? evidence.case_id : "xian-evidence",
    page: "evidence",
    title: "Evidence Review Workbench",
    subtitle: typeof evidence.title === "string" ? evidence.title : "PostgreSQL evidence review",
    nav: [],
    metrics: [
      { label: "Review status", value: String(review.status ?? "pending"), tone: "blue" },
      { label: "Media links", value: Array.isArray(primary.media_links) ? primary.media_links.length : 0, tone: "violet" },
      { label: "Risk factors", value: Array.isArray(primary.risk_factors) ? primary.risk_factors.length : 0, tone: "green" },
      { label: "Conflicts", value: Array.isArray(primary.conflicts) ? primary.conflicts.length : 0, tone: "amber" }
    ],
    sections: [
      { id: "evidence", title: "Evidence material", kind: "evidence", items: evidence.id ? [evidence] : [] },
      { id: "media", title: "Linked media", kind: "sources", items: Array.isArray(primary.media_links) ? (primary.media_links as unknown[]) : [] },
      { id: "processing", title: "Media processing runs", kind: "timeline", items: Array.isArray(primary.media_processing_runs) ? (primary.media_processing_runs as unknown[]) : [] },
      { id: "risk-factors", title: "Risk factors", kind: "signals", items: Array.isArray(primary.risk_factors) ? (primary.risk_factors as unknown[]) : [] },
      { id: "conflicts", title: "Conflict prompts", kind: "chips", items: Array.isArray(primary.conflicts) ? (primary.conflicts as unknown[]) : [] }
    ],
    actions: [{ id: "enter-mainline", label: "Enter mainline modeling", to_page: "mainline" }],
    raw: { ...primary, evidence_review_id: review.evidence_review_id, evidence_id: evidence.id, topic_id: review.topic_id, source: "postgresql", review_state: model.page_state }
  };
}

function mainlineBuilderToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const mainline = objectValue(primary.mainline);
  const mainlinePayload = objectValue(mainline.payload);
  const nodes = Array.isArray(primary.nodes) ? (primary.nodes as JsonMap[]) : [];
  const graphNodes = Array.isArray(primary.case_graph_nodes) ? (primary.case_graph_nodes as JsonMap[]) : [];
  const stakeholders = Array.isArray(primary.stakeholders) ? (primary.stakeholders as JsonMap[]) : [];
  const signalIds = Array.isArray(mainlinePayload.signal_ids) ? (mainlinePayload.signal_ids as unknown[]) : [];
  const raw = {
    ...primary,
    mainline_id: stringField(mainline, "id"),
    topic_id: stringField(mainline, "topic_id") ?? stringField(mainlinePayload, "topic_id"),
    first_node_id: stringField(nodes[0], "id"),
    first_node_version: numberField(nodes[0], "version"),
    first_signal_id: stringValue(signalIds[0]),
    world_state_id: stringField(mainlinePayload, "world_state_id"),
    first_graph_node_id: stringField(graphNodes[0], "id"),
    first_stakeholder_id: stringField(stakeholders[0], "id"),
    source: "postgresql",
    builder_state: model.page_state
  };
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      nav: Array.isArray(legacy.nav) ? (legacy.nav as PageView["nav"]) : [],
      subtitle: typeof legacy.subtitle === "string" ? legacy.subtitle : null,
      raw: {
        ...objectValue((legacy as JsonMap).raw),
        ...raw
      }
    };
  }
  return {
    case_id: typeof mainline.case_id === "string" ? mainline.case_id : "xian-mainline",
    page: "mainline",
    title: typeof mainline.title === "string" ? mainline.title : "Mainline Builder",
    subtitle: `PostgreSQL mainline state: ${String(mainline.status ?? "draft")}`,
    nav: [],
    metrics: [
      { label: "Mainline version", value: String(mainline.version ?? mainlinePayload.version ?? "v1"), tone: "blue" },
      { label: "Evidence refs", value: Array.isArray(mainlinePayload.evidence_refs) ? mainlinePayload.evidence_refs.length : 0, tone: "green" },
      { label: "Graph nodes", value: graphNodes.length, tone: "violet" },
      { label: "Stakeholders", value: stakeholders.length, tone: "amber" }
    ],
    sections: [
      { id: "candidates", title: "Mainline draft", kind: "mainlines", items: mainline.id ? [mainline] : [] },
      { id: "graph", title: "Mainline graph nodes", kind: "nodes", items: nodes },
      { id: "evidence", title: "Evidence references", kind: "evidence", items: Array.isArray(primary.evidence) ? (primary.evidence as unknown[]) : [] },
      { id: "stakeholders", title: "Stakeholders", kind: "stakeholders", items: stakeholders }
    ],
    actions: [{ id: "enter-worldline", label: "Enter worldline projection", to_page: "worldline" }],
    raw
  };
}

function worldlineSimulationToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const run = objectValue(primary.run);
  const nodes = Array.isArray(primary.nodes) ? (primary.nodes as JsonMap[]) : [];
  const interventions = Array.isArray(primary.interventions) ? (primary.interventions as JsonMap[]) : [];
  const selectedNode = nodes.find((node) => objectValue(node.payload).needsCouncil === true) ?? nodes[0];
  const raw = {
    ...primary,
    worldline_run_id: stringField(run, "id"),
    world_state_id: stringField(run, "world_state_id"),
    selected_node_id: stringField(selectedNode, "id"),
    mainline_id: stringField(objectValue(run.payload), "mainline_id"),
    source: "postgresql",
    simulation_state: model.page_state
  };
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      nav: Array.isArray(legacy.nav) ? (legacy.nav as PageView["nav"]) : [],
      actions: Array.isArray(legacy.actions) ? (legacy.actions as PageView["actions"]) : [],
      metrics: Array.isArray(legacy.metrics) ? (legacy.metrics as PageView["metrics"]) : [],
      subtitle: typeof legacy.subtitle === "string" ? legacy.subtitle : null,
      raw: { ...objectValue((legacy as JsonMap).raw), ...raw }
    };
  }
  return {
    case_id: typeof run.case_id === "string" ? run.case_id : "xian-worldline",
    page: "worldline",
    title: "Worldline Simulation",
    subtitle: `PostgreSQL worldline run: ${String(run.status ?? "pending")}`,
    nav: [],
    metrics: [
      { label: "Run status", value: String(run.status ?? "pending"), tone: "blue" },
      { label: "Branches", value: nodes.length, tone: "green" },
      { label: "Version", value: String(run.version ?? "v1"), tone: "amber" },
      { label: "Interventions", value: interventions.length, tone: "violet" }
    ],
    sections: [
      { id: "nodes", title: "Worldline branches", kind: "nodes", items: nodes },
      { id: "interventions", title: "Interventions", kind: "timeline", items: interventions },
      { id: "council", title: "Council-ready nodes", kind: "nodes", items: nodes.filter((node) => objectValue(node.payload).needsCouncil === true) }
    ],
    actions: [{ id: "enter-council", label: "Enter Council", to_page: "council" }],
    raw
  };
}

function councilViewToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const session = objectValue(primary.session);
  const selectedNode = objectValue(primary.selected_node);
  const profiles = Array.isArray(primary.agent_profiles) ? (primary.agent_profiles as JsonMap[]) : [];
  const messages = Array.isArray(primary.messages) ? (primary.messages as JsonMap[]) : [];
  const llmCalls = Array.isArray(primary.llm_calls) ? (primary.llm_calls as JsonMap[]) : [];
  const result = objectValue(primary.result);
  return {
    case_id: typeof session.case_id === "string" ? session.case_id : "xian-council",
    page: "council",
    title: "Agent Council",
    subtitle: `Guardrailed council status: ${String(session.status ?? "created")}`,
    nav: [],
    metrics: [
      { label: "Council status", value: String(session.status ?? "created"), tone: "blue" },
      { label: "Agent profiles", value: profiles.length, tone: "green" },
      { label: "LLM calls", value: llmCalls.length, tone: "violet" },
      { label: "Blocked claims", value: Array.isArray(result.blocked_claims) ? result.blocked_claims.length : 0, tone: "red" }
    ],
    sections: [
      { id: "context", title: "Selected worldline node", kind: "nodes", items: selectedNode.id ? [selectedNode] : [] },
      { id: "profiles", title: "Reviewed Agent Profiles", kind: "agents", items: profiles },
      { id: "messages", title: "Council messages", kind: "timeline", items: messages },
      { id: "result", title: "Council result and blocked claims", kind: "chips", items: result.id ? [result] : [] }
    ],
    actions: [],
    raw: {
      ...primary,
      council_session_id: stringField(session, "id"),
      council_result_id: stringField(result, "id") || stringField(objectValue(session.payload), "result_id"),
      worldline_run_id: stringField(session, "worldline_run_id"),
      selected_node_id: stringField(session, "selected_node_id"),
      source: "postgresql",
      council_state: model.page_state
    }
  };
}

function cityLayerListToMapLayers(layers: CityMapLayer[]): MapLayers {
  const mapLayer = layers.find((layer) => layer.layer_type === "map");
  const pointLayer = layers.find((layer) => layer.layer_type === "point");
  const heatLayer = layers.find((layer) => layer.layer_type === "heat");
  const configFeature = objectValue(mapLayer?.features?.[0]);
  const config = objectValue(configFeature.config);
  const center = Array.isArray(config.center) ? (config.center as number[]) : [108.9398, 34.3416];
  const zoom = typeof config.zoom === "number" ? config.zoom : 10.8;
  return {
    caseId: "xian-city",
    eventPoints: { type: "FeatureCollection", features: ((pointLayer?.features ?? []) as unknown as MapFeature[]) },
    riskAreas: { type: "FeatureCollection", features: ((heatLayer?.features ?? []) as unknown as MapFeature[]) },
    config: { center, zoom }
  };
}

function reportBriefToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const report = objectValue(primary.report);
  const claims = Array.isArray(primary.claims) ? (primary.claims as JsonMap[]) : [];
  const tasks = Array.isArray(primary.tasks) ? (primary.tasks as JsonMap[]) : [];
  const exports = Array.isArray(primary.exports) ? (primary.exports as JsonMap[]) : [];
  const review = objectValue(primary.review);
  const raw = {
    ...primary,
    report_id: stringField(report, "id"),
    topic_id: stringField(report, "topic_id"),
    review_id: stringField(report, "review_id") || stringField(review, "review_id"),
    council_result_id: stringField(objectValue(report.payload), "council_result_id"),
    source: "postgresql",
    report_state: model.page_state
  };
  if (typeof legacy.case_id === "string" && Array.isArray(legacy.sections)) {
    return {
      ...(legacy as unknown as PageView),
      nav: Array.isArray(legacy.nav) ? (legacy.nav as PageView["nav"]) : [],
      subtitle: typeof legacy.subtitle === "string" ? legacy.subtitle : null,
      raw: { ...objectValue((legacy as JsonMap).raw), ...raw }
    };
  }
  return {
    case_id: typeof report.case_id === "string" ? report.case_id : "xian-report",
    page: "brief",
    title: typeof report.title === "string" ? report.title : "Evidence Brief",
    subtitle: `Report status: ${String(report.status ?? "draft")}`,
    nav: [],
    metrics: [
      { label: "Report status", value: String(report.status ?? "draft"), tone: "blue" },
      { label: "Claims", value: claims.length, tone: "green" },
      { label: "Tasks", value: tasks.length, tone: "amber" },
      { label: "Exports", value: exports.length, tone: "violet" }
    ],
    sections: [
      { id: "claims", title: "Evidence-linked claims", kind: "records", items: claims },
      { id: "actions", title: "Task closure", kind: "tasks", items: tasks },
      { id: "exports", title: "Report exports", kind: "records", items: exports }
    ],
    actions: [],
    raw
  };
}

function retrospectiveMemoryToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const retrospective = objectValue(primary.retrospective);
  const report = objectValue(primary.report);
  const review = objectValue(primary.review);
  const raw = {
    primary_data: primary,
    retrospective_id: stringField(retrospective, "id"),
    report_id: stringField(report, "id") || stringField(retrospective, "report_id"),
    review_id: stringField(retrospective, "review_id") || stringField(review, "review_id")
  };
  return {
    case_id: stringField(retrospective, "case_id") || "CASE-CAMPUS-001",
    page: "memory",
    title: stringField(legacy, "title") || stringField(retrospective, "summary") || "复盘知识沉淀",
    subtitle: stringField(report, "title") || "Published report memory extraction",
    nav: [],
    metrics: Array.isArray(legacy.metrics) ? (legacy.metrics as PageMetric[]) : [],
    sections: Array.isArray(legacy.sections) ? (legacy.sections as PageSection[]) : [],
    actions: [],
    raw
  };
}

function caseLibraryToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const entries = Array.isArray(primary.entries) ? (primary.entries as JsonMap[]) : [];
  const firstEntry = objectValue(entries[0]);
  return {
    case_id: stringField(firstEntry, "case_id") || "CASE-CAMPUS-001",
    page: "library",
    title: stringField(legacy, "title") || "主题 / 案例库",
    subtitle: "Approved retrospective knowledge only",
    nav: [],
    metrics: Array.isArray(legacy.metrics) ? (legacy.metrics as PageMetric[]) : [],
    sections: Array.isArray(legacy.sections) ? (legacy.sections as PageSection[]) : [],
    actions: [],
    raw: { primary_data: primary, first_entry_id: stringField(firstEntry, "id"), target_case_id: stringField(firstEntry, "case_id") }
  };
}

function configAdminToPageView(model: PageViewModel): PageView {
  const primary = objectValue(model.primary_data);
  const legacy = objectValue(primary.legacy_page_view);
  const versions = Array.isArray(primary.versions) ? (primary.versions as JsonMap[]) : [];
  const releases = Array.isArray(primary.releases) ? (primary.releases as JsonMap[]) : [];
  const firstVersion = objectValue(versions[0]);
  const firstRelease = objectValue(releases[0]);
  return {
    case_id: "CASE-CAMPUS-001",
    page: "config",
    title: stringField(legacy, "title") || "数据源与模型配置",
    subtitle: "Versioned configuration with regression, approval, and rollback",
    nav: [],
    metrics: Array.isArray(legacy.metrics) ? (legacy.metrics as PageMetric[]) : [],
    sections: Array.isArray(legacy.sections) ? (legacy.sections as PageSection[]) : [],
    actions: [],
    raw: {
      primary_data: primary,
      first_config_version_id: stringField(firstVersion, "id"),
      first_release_id: stringField(firstRelease, "id")
    }
  };
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  login: (username: string, password: string) =>
    request<ApiEnvelope<AuthTokenPair>>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  logout: () => request<ApiEnvelope<{ logged_out: boolean }>>("/api/v1/auth/logout", { method: "POST" }),
  me: () => request<ApiEnvelope<AuthUser>>("/api/v1/me"),
  permissions: () => request<ApiEnvelope<CurrentPermissionResponse>>("/api/v1/me/permissions"),
  navigation: () => request<ApiEnvelope<NavigationResponse>>("/api/v1/me/navigation"),
  listUsers: () => request<ApiEnvelope<AuthUser[]>>("/api/v1/users"),
  listRoles: () => request<ApiEnvelope<RoleRecord[]>>("/api/v1/roles"),
  createRole: (name: string, permissionCodes: string[]) =>
    request<ApiEnvelope<RoleRecord>>("/api/v1/roles", {
      method: "POST",
      body: JSON.stringify({ name, permission_codes: permissionCodes })
    }),
  createUser: (username: string, displayName: string, password: string, roleIds: string[]) =>
    request<ApiEnvelope<AuthUser>>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify({ username, display_name: displayName, password, role_ids: roleIds })
    }),
  listS1AuditLogs: () => request<ApiEnvelope<S1AuditLog[]>>("/api/v1/audit-logs"),
  listReviewTemplates: (objectType?: string) =>
    request<ApiEnvelope<ReviewTemplate[]>>(`/api/v1/review-templates${objectType ? `?object_type=${encodeURIComponent(objectType)}` : ""}`),
  listReviews: () => request<ApiEnvelope<ReviewRecord[]>>("/api/v1/reviews"),
  createReview: (objectType: string, objectId: string, objectVersion: string, templateId: string) =>
    request<ApiEnvelope<ReviewRecord>>("/api/v1/reviews", {
      method: "POST",
      body: JSON.stringify({ object_type: objectType, object_id: objectId, object_version: objectVersion, template_id: templateId })
    }),
  updateReview: (reviewId: string, status: "pass" | "fail", findings: string[], blockers: string[]) =>
    request<ApiEnvelope<ReviewRecord>>(`/api/v1/reviews/${reviewId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, findings, blockers })
    }),
  gateCheck: (reviewId: string) =>
    request<ApiEnvelope<GateCheck>>(`/api/v1/reviews/${reviewId}/gate-check`, { method: "POST" }),
  waiveReview: (reviewId: string, reason: string, risk: string) =>
    request<ApiEnvelope<ReviewRecord>>(`/api/v1/reviews/${reviewId}/waive`, {
      method: "POST",
      body: JSON.stringify({ approved_by: "system_admin", reason, risk, expires_at: "2030-01-01T00:00:00" })
    }),
  opsApiHealth: () => request<ApiEnvelope<OpsHealth>>("/api/v1/ops/api-health"),
  opsDbHealth: () => request<ApiEnvelope<OpsHealth>>("/api/v1/ops/db-health"),
  opsWorkers: () => request<ApiEnvelope<OpsWorker[]>>("/api/v1/ops/workers"),
  opsWorkflowRuns: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/workflow-runs"),
  opsErrorQueue: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/ops/error-queue"),
  opsRetryQueue: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/ops/retry-queue"),
  listDeadLetters: (params: { status?: string; dataSourceId?: string; errorCode?: string; page?: number; pageSize?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.dataSourceId) query.set("data_source_id", params.dataSourceId);
    if (params.errorCode) query.set("error_code", params.errorCode);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<JsonMap[]>>(`/api/v1/dead-letters${qs ? `?${qs}` : ""}`);
  },
  replayDeadLetter: (deadLetterId: string, input: { sourceUri?: string; reason?: string; payload?: JsonMap } = {}) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/dead-letters/${deadLetterId}/replay`, {
      method: "POST",
      body: JSON.stringify({
        source_uri: input.sourceUri,
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  createRawRecordBatch: (input: RawRecordBatchInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/raw-records/batches", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: input.dataSourceId,
        collection_run_id: input.collectionRunId,
        records: (input.records ?? []).map((record) => ({
          title: record.title,
          content: record.content,
          content_hash: record.contentHash,
          raw_uri: record.rawUri,
          metadata: record.metadata ?? {},
          external_id: record.externalId,
          dedupe_key: record.dedupeKey,
          source_type: record.sourceType,
          status: record.status ?? "collected",
          city_id: record.cityId ?? "xian",
          occurred_at: record.occurredAt,
          is_synthetic: record.isSynthetic,
          payload: record.payload ?? {}
        })),
        synthetic_count: input.syntheticCount ?? 0,
        response_limit: input.responseLimit ?? 100,
        complete_run: input.completeRun ?? false,
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  opsMetrics: () => request<ApiEnvelope<JsonMap>>("/api/v1/ops/metrics"),
  listDataSourceTypes: () => request<ApiEnvelope<Array<{ source_type: string; label: string; requires_external_key: boolean }>>>("/api/v1/data-source-types"),
  listCollectionChannels: () => request<ApiEnvelope<CollectionChannel[]>>("/api/v1/collection-channels"),
  validateChannelAdapterContract: () => request<ApiEnvelope<ChannelAdapterContractValidation>>("/api/v1/collection-channels/adapter-contract"),
  mapCollectionChannelErrorCodes: (params: { channel?: string; errorCode?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.channel) query.set("channel", params.channel);
    if (params.errorCode) query.set("error_code", params.errorCode);
    const qs = query.toString();
    return request<ApiEnvelope<ChannelErrorCodeMap>>(`/api/v1/collection-channels/error-codes${qs ? `?${qs}` : ""}`);
  },
  getCollectionChannelSchema: (channel: string) => request<ApiEnvelope<CollectionChannelSchema>>(`/api/v1/collection-channels/${encodeURIComponent(channel)}/schema`),
  listAdapterCapabilities: (sourceType?: string) =>
    request<ApiEnvelope<AdapterCapability[]>>(`/api/v1/adapters/capabilities${sourceType ? `?source_type=${encodeURIComponent(sourceType)}` : ""}`),
  listDataSources: (params: { sourceType?: string; status?: string; page?: number; pageSize?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.sourceType) query.set("source_type", params.sourceType);
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<DataSourceRecord[]>>(`/api/v1/data-sources${qs ? `?${qs}` : ""}`);
  },
  createDataSource: (name: string, sourceType: string, policy: JsonMap = {}) =>
    request<ApiEnvelope<DataSourceRecord>>("/api/v1/data-sources", {
      method: "POST",
      body: JSON.stringify({ name, source_type: sourceType, policy })
    }),
  sendWebhookPayload: async (sourceKey: string, secret: string, payload: JsonMap) => {
    const body = JSON.stringify(payload);
    const timestamp = String(Math.floor(Date.now() / 1000));
    const signature = await hmacSha256(secret, `${timestamp}.${body}`);
    return request<ApiEnvelope<JsonMap>>(`/api/v1/webhooks/${sourceKey}`, {
      method: "POST",
      headers: {
        "x-cet-timestamp": timestamp,
        "x-cet-delivery-id": String(payload.request_id ?? `delivery-${Date.now()}`),
        "x-cet-signature": `sha256=${signature}`
      },
      body
    });
  },
  checkDataSourcePolicy: (dataSourceId: string) =>
    request<ApiEnvelope<{ allowed: boolean; reason: string | null; access_mode: string }>>(`/api/v1/data-sources/${dataSourceId}/policy-check`, { method: "POST" }),
  validateDataSourceUrl: (dataSourceId: string, url: string) =>
    request<ApiEnvelope<DataSourceUrlValidation>>(`/api/v1/data-sources/${dataSourceId}/validate-url`, {
      method: "POST",
      body: JSON.stringify({ url })
    }),
  updateDataSourceCrawlPolicy: (dataSourceId: string, input: { start_url: string; max_depth?: number; respect_robots?: boolean; rate_limit_per_minute?: number; allowed_domains?: string[]; reason?: string }) =>
    request<ApiEnvelope<DataSourceRecord>>(`/api/v1/data-sources/${dataSourceId}/crawl-policy`, {
      method: "PUT",
      body: JSON.stringify(input)
    }),
  discoverPublicWebLinks: (dataSourceId: string, input: { start_url?: string; max_depth?: number; limit?: number; respect_robots?: boolean; allowed_domains?: string[]; reason?: string }) =>
    request<ApiEnvelope<PublicWebLinkDiscovery>>(`/api/v1/data-sources/${dataSourceId}/public-web/discover-links`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  updateDataSourceAuth: (dataSourceId: string, input: { auth_type: string; secret_ref: string; header_name?: string; token_url?: string; reason?: string }) =>
    request<ApiEnvelope<DataSourceRecord>>(`/api/v1/data-sources/${dataSourceId}/auth`, {
      method: "PUT",
      body: JSON.stringify(input)
    }),
  testDataSourceConnection: (dataSourceId: string, input: { sample_path?: string; expected_status?: number }) =>
    request<ApiEnvelope<DataSourceConnectionTest>>(`/api/v1/data-sources/${dataSourceId}/test-connection`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  publishDataSourceVersion: (dataSourceId: string, reason = "S2 frontend source version publish") =>
    request<ApiEnvelope<DataSourceVersion>>(`/api/v1/data-sources/${dataSourceId}/versions/publish`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  rollbackDataSourceVersion: (dataSourceId: string, version: number, reason = "S2 frontend source version rollback") =>
    request<ApiEnvelope<DataSourceVersion>>(`/api/v1/data-sources/${dataSourceId}/versions/${version}/rollback`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  updateDataSourceStatus: (dataSourceId: string, status: "active" | "disabled", reason: string) =>
    request<ApiEnvelope<DataSourceRecord>>(`/api/v1/data-sources/${dataSourceId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason })
    }),
  updateDataSourceCompliance: (dataSourceId: string, input: { authorization_scope: string; authorization_basis: string; retention_days: number; data_classification: string; pii_policy?: string; synthetic_allowed?: boolean; reason?: string }) =>
    request<ApiEnvelope<DataSourceRecord>>(`/api/v1/data-sources/${dataSourceId}/compliance`, {
      method: "PUT",
      body: JSON.stringify(input)
    }),
  updateDataSourcePagination: (dataSourceId: string, input: { strategy: string; page_param?: string; page_size_param?: string; cursor_param?: string; next_url_path?: string; max_pages?: number; dry_run?: boolean; reason?: string }) =>
    request<ApiEnvelope<DataSourceRecord>>(`/api/v1/data-sources/${dataSourceId}/pagination`, {
      method: "PUT",
      body: JSON.stringify(input)
    }),
  listObjectStorageKeys: (dataSourceId: string, input: { max_keys?: number; prefix?: string }) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/data-sources/${dataSourceId}/object-storage/list`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getDataSourceCursorState: (dataSourceId: string) => request<ApiEnvelope<DataSourceCursorState>>(`/api/v1/data-sources/${dataSourceId}/cursor-state`),
  scanDbImportTable: (dataSourceId: string, input: DbImportScanInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/db-import", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        table_name: input.tableName,
        schema_name: input.schemaName,
        cursor_field: input.cursorField ?? "id",
        cursor_value: input.cursorValue,
        limit: input.limit ?? 1000,
        response_limit: input.responseLimit ?? 20,
        city_id: input.cityId ?? "xian",
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  scanObjectStoragePrefix: (dataSourceId: string, input: ObjectStorageScanInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/object-storage", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        prefix: input.prefix,
        limit: input.limit ?? 1000,
        response_limit: input.responseLimit ?? 20,
        city_id: input.cityId ?? "xian",
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  inspectRssFeed: (dataSourceId: string) =>
    request<ApiEnvelope<DataSourceRssInspection>>(`/api/v1/data-sources/${dataSourceId}/rss/inspect`, { method: "POST" }),
  fetchRssItems: (dataSourceId: string, feedUrl = "synthetic://xian/rss-social-issues") =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/rss", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "RSS item fetch",
        source_uri: feedUrl
      })
    }),
  sourceHealthView: () => request<ApiEnvelope<{ page_state: string; sources: JsonMap[] }>>("/api/v1/data-sources/health-view"),
  getDataSourceHealth: (dataSourceId: string) => request<ApiEnvelope<DataSourceHealthDetail>>(`/api/v1/data-sources/${dataSourceId}/health`),
  getDataSourceRateLimit: (dataSourceId: string, channel?: string) => {
    const query = channel ? `?channel=${encodeURIComponent(channel)}` : "";
    return request<ApiEnvelope<DataSourceRateLimitStatus>>(`/api/v1/data-sources/${dataSourceId}/rate-limit${query}`);
  },
  getCollectionChannelQualityMetrics: (channel: string) =>
    request<ApiEnvelope<CollectionChannelQualityMetrics>>(`/api/v1/collection-channels/${encodeURIComponent(channel)}/quality-metrics`),
  getCollectionChannelMaintenance: () =>
    request<ApiEnvelope<CollectionChannelMaintenance>>("/api/v1/collection-channels/maintenance"),
  listCollectionJobs: (params: { status?: string; dataSourceId?: string; createdById?: string; page?: number; pageSize?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.dataSourceId) query.set("data_source_id", params.dataSourceId);
    if (params.createdById) query.set("created_by_id", params.createdById);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<CollectionJobRecord[]>>(`/api/v1/collection-jobs${qs ? `?${qs}` : ""}`);
  },
  getCollectionJob: (collectionJobId: string) => request<ApiEnvelope<CollectionJobDetail>>(`/api/v1/collection-jobs/${collectionJobId}`),
  createCollectionJob: (dataSourceId: string, name: string, schedule?: string | null, payload: JsonMap = {}) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/collection-jobs", {
      method: "POST",
      body: JSON.stringify({ data_source_id: dataSourceId, name, schedule, payload })
    }),
  startCollectionRun: (collectionJobId: string) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/collection-jobs/${collectionJobId}/runs`, { method: "POST" }),
  startFileUploadRun: (collectionJobId: string, fileObjectId: string, input: FileUploadRunInput = {}) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/collection-jobs/${collectionJobId}/file-runs`, {
      method: "POST",
      body: JSON.stringify({
        file_object_id: fileObjectId,
        title: input.title,
        city_id: input.cityId,
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  createManualRecord: (dataSourceId: string, input: ManualRecordInput = {}) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/manual-records", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: input.title,
        content: input.content,
        city_id: input.cityId === undefined ? "xian" : input.cityId,
        location: input.location,
        occurred_at: input.occurredAt,
        source_uri: input.sourceUri,
        is_synthetic: input.isSynthetic ?? false,
        payload: input.payload ?? {},
        reason: input.reason
      })
    }),
  pauseCollectionJob: (collectionJobId: string, reason = "S2 frontend pause collection job") =>
    request<ApiEnvelope<CollectionJobRecord>>(`/api/v1/collection-jobs/${collectionJobId}/pause`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  resumeCollectionJob: (collectionJobId: string, reason = "S2 frontend resume collection job") =>
    request<ApiEnvelope<CollectionJobRecord>>(`/api/v1/collection-jobs/${collectionJobId}/resume`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  cancelCollectionRun: (collectionRunId: string) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/collection-runs/${collectionRunId}/cancel`, { method: "POST" }),
  retryCollectionRun: (collectionRunId: string) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/collection-runs/${collectionRunId}/retry`, { method: "POST" }),
  replayCollectionRunFromCheckpoint: (collectionRunId: string, input: { reason?: string; payload?: JsonMap } = {}) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/collection-runs/${collectionRunId}/channel-replay`, {
      method: "POST",
      body: JSON.stringify({
        reason: input.reason,
        payload: input.payload ?? {}
      })
    }),
  listCollectionRuns: (params: { status?: string; dataSourceId?: string; collectionJobId?: string; createdFrom?: string; createdTo?: string; page?: number; pageSize?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.dataSourceId) query.set("data_source_id", params.dataSourceId);
    if (params.collectionJobId) query.set("collection_job_id", params.collectionJobId);
    if (params.createdFrom) query.set("created_from", params.createdFrom);
    if (params.createdTo) query.set("created_to", params.createdTo);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<CollectionRunRecord[]>>(`/api/v1/collection-runs${qs ? `?${qs}` : ""}`);
  },
  getCollectionRunSteps: (collectionRunId: string) => request<ApiEnvelope<CollectionRunStepsView>>(`/api/v1/collection-runs/${collectionRunId}/steps`),
  getCollectionRunMetrics: (collectionRunId: string) => request<ApiEnvelope<CollectionRunMetricsView>>(`/api/v1/collection-runs/${collectionRunId}/metrics`),
  getCleaningRunMetrics: (cleaningRunId: string) => request<ApiEnvelope<CollectionRunMetricsView>>(`/api/v1/cleaning-runs/${cleaningRunId}/metrics`),
  generateXianSyntheticSamples: () =>
    request<ApiEnvelope<{ raw_records: RawRecord[]; collection_run: JsonMap; data_source: DataSourceRecord }>>("/api/v1/synthetic-scenarios/xian-social-issues", { method: "POST" }),
  listImportRuns: () => request<ApiEnvelope<S2RunRecord[]>>("/api/v1/import-runs"),
  importFile: (dataSourceId: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/files", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Manual file import",
        content: "synthetic import duplicate content. minor identity metadata needs masking.",
        source_uri: "synthetic://imports/file-001.txt",
        is_synthetic: true
      })
    }),
  uploadFile: (dataSourceId: string, file: File, input: { title?: string; isSynthetic?: boolean; sourceUri?: string } = {}) => {
    const formData = new FormData();
    formData.set("data_source_id", dataSourceId);
    formData.set("file", file);
    if (input.title) formData.set("title", input.title);
    formData.set("is_synthetic", input.isSynthetic ? "true" : "false");
    if (input.sourceUri) formData.set("source_uri", input.sourceUri);
    return request<ApiEnvelope<JsonMap>>("/api/v1/uploads", {
      method: "POST",
      body: formData
    });
  },
  importPublicWeb: (dataSourceId: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/public-web", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Public web import",
        source_uri: "synthetic://xian/public-web/community-notice-001",
        payload: {
          district: "雁塔区",
          synthetic_body: "西安社区公告更新：居民关注补偿进度、公开说明和后续沟通窗口。"
        }
      })
    }),
  importOfficialApi: (dataSourceId: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/official-api", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Official API import without key",
        source_uri: "official://xian/no-key"
      })
    }),
  fetchOfficialApi: (dataSourceId: string, pageSize = 2, sourceUri = "synthetic://xian/official-api/issues") =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/official-api", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Official API paginated fetch",
        source_uri: sourceUri,
        payload: { page_size: pageSize }
      })
    }),
  importMedia: (dataSourceId: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/media", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Media import",
        content: "synthetic media import transcript for Xi'an public service issue.",
        source_uri: "synthetic://imports/media-001.png",
        media_type: "image",
        media_uri: "synthetic://imports/media-001.png",
        is_synthetic: true
      })
    }),
  importVideoMedia: (dataSourceId: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/media", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Video media import",
        content: "synthetic video transcript for Xi'an public service issue with phone 13800138000 masked by backend.",
        source_uri: "synthetic://imports/video-media-001.mp4",
        media_type: "video",
        media_uri: "synthetic://imports/video-media-001.mp4",
        is_synthetic: true
      })
    }),
  importLiveSegment: (dataSourceId: string, streamUrl: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/media", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Livestream segment import",
        content: "synthetic livestream segment transcript for Xi'an public service issue with phone 13800138000 masked by backend.",
        source_uri: streamUrl,
        media_type: "live_segment",
        media_uri: `${streamUrl}/segment-ui-001.ts`,
        is_synthetic: true
      })
    }),
  importAudioMedia: (dataSourceId: string, sourceUri: string) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/imports/media", {
      method: "POST",
      body: JSON.stringify({
        data_source_id: dataSourceId,
        title: "Audio media import",
        content: "synthetic audio transcript for Xi'an public service issue with phone 13800138000 masked by backend.",
        source_uri: sourceUri,
        media_type: "audio",
        media_uri: `${sourceUri}/audio-ui-001.mp3`,
        is_synthetic: true
      })
    }),
  listNormalizationRuns: () => request<ApiEnvelope<S2RunRecord[]>>("/api/v1/normalization-runs"),
  runNormalization: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/normalization-runs", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "normalize_text-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runDatetimeNormalization: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/normalization-runs/datetime", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "normalize_datetime-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole", default_timezone: "+08:00" } })
    }),
  runLocationNormalization: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/normalization-runs/location", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "normalize_location-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runSourceTrustAssignment: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/normalization-runs/source-trust", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "assign_source_trust-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runSensitiveFieldDetection: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/detector-runs/sensitive-fields", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "detect_sensitive_fields-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runSensitiveFieldRedaction: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/redaction-runs/sensitive-fields", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "redact_sensitive_fields-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runHtmlMainContentParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/html-main-content", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "parse_html_main_content-ui-v1", payload: { source: "S2SourceConsole" } })
    }),
  runJsonByMappingParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/json-by-mapping", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_json_by_mapping-ui-v1",
        payload: { source: "S2SourceConsole", mapping: { title: "$.title", body: "$.summary", published_at: "$.published_at" } }
      })
    }),
  runRssItemParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/rss-item", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_rss_item-ui-v1",
        response_limit: 12,
        payload: { source: "S2SourceConsole" }
      })
    }),
  runCsvFileParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/csv-file", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_csv_file-ui-v1",
        response_limit: 12,
        payload: { source: "S2SourceConsole", mapping: { title: "title", body: "content", published_at: "published_at" } }
      })
    }),
  runXlsxFileParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/xlsx-file", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_xlsx_file-ui-v1",
        response_limit: 12,
        payload: {
          source: "S2SourceConsole",
          sheet: "Sheet1",
          range: "A1:C1000",
          mapping: { title: "title", body: "content", published_at: "published_at" }
        }
      })
    }),
  runPdfTextParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/pdf-text", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_pdf_text-ui-v1",
        response_limit: 12,
        payload: { source: "S2SourceConsole", title_prefix: "PDF extracted page" }
      })
    }),
  runDocxTextParser: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/parser-runs/docx-text", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "parse_docx_text-ui-v1",
        response_limit: 12,
        payload: { source: "S2SourceConsole", title_prefix: "DOCX extracted block" }
      })
    }),
  listDeduplicationRuns: () => request<ApiEnvelope<S2RunRecord[]>>("/api/v1/deduplication-runs"),
  runDeduplication: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/deduplication-runs", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "dedupe_by_hash_and_external_id-ui-v1", response_limit: 12, payload: { source: "S2SourceConsole" } })
    }),
  runSemanticDeduplication: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/deduplication-runs/semantic", {
      method: "POST",
      body: JSON.stringify({
        raw_record_ids: rawRecordIds,
        rule_version: "semantic_dedupe_records-ui-v1",
        response_limit: 12,
        payload: { source: "S2SourceConsole", similarity_threshold: 0.34 }
      })
    }),
  applyDedupeDecision: (rawRecordId: string, body: JsonMap) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/clean-records/${encodeURIComponent(rawRecordId)}/dedupe-decision`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  listDataQualityRuns: () => request<ApiEnvelope<S2RunRecord[]>>("/api/v1/data-quality-runs"),
  runDataQuality: (rawRecordIds: string[]) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/data-quality-runs", {
      method: "POST",
      body: JSON.stringify({ raw_record_ids: rawRecordIds, rule_version: "s2-ui-quality-v1" })
    }),
  listDataQualityIssues: (params: DataQualityIssueListParams = {}) => {
    const query = new URLSearchParams();
    if (params.issueType) query.set("issue_type", params.issueType);
    if (params.severity) query.set("severity", params.severity);
    if (params.dataQualityRunId) query.set("data_quality_run_id", params.dataQualityRunId);
    if (params.rawRecordId) query.set("raw_record_id", params.rawRecordId);
    if (params.dataSourceId) query.set("data_source_id", params.dataSourceId);
    if (params.sourceType) query.set("source_type", params.sourceType);
    if (params.createdFrom) query.set("created_from", params.createdFrom);
    if (params.createdTo) query.set("created_to", params.createdTo);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<DataQualityIssue[]>>(`/api/v1/data-quality/issues${qs ? `?${qs}` : ""}`);
  },
  listCleanRecords: (params: CleanRecordListParams = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.dataSourceId) query.set("data_source_id", params.dataSourceId);
    if (params.sourceType) query.set("source_type", params.sourceType);
    if (params.createdFrom) query.set("created_from", params.createdFrom);
    if (params.createdTo) query.set("created_to", params.createdTo);
    if (params.page) query.set("page", String(params.page));
    if (params.pageSize) query.set("page_size", String(params.pageSize));
    const qs = query.toString();
    return request<ApiEnvelope<CleanRecord[]>>(`/api/v1/clean-records${qs ? `?${qs}` : ""}`);
  },
  getCleanRecord: (cleanRecordId: string) => request<ApiEnvelope<CleanRecordDetail>>(`/api/v1/clean-records/${encodeURIComponent(cleanRecordId)}`),
  updateCleanRecordStatus: (cleanRecordId: string, status: "valid" | "invalid" | "review_required", reason: string) =>
    request<ApiEnvelope<CleanRecordStatusUpdateResult>>(`/api/v1/clean-records/${encodeURIComponent(cleanRecordId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, reason, payload: { source: "S2SourceConsole" } })
    }),
  listRawRecords: () => request<ApiEnvelope<RawRecord[]>>("/api/v1/raw-records"),
  getRawRecord: (rawRecordId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/raw-records/${encodeURIComponent(rawRecordId)}`),
  exportRawRecordRedacted: (rawRecordId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/raw-records/${encodeURIComponent(rawRecordId)}/redacted-export`),
  getRawRecordOriginal: (rawRecordId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/raw-records/${encodeURIComponent(rawRecordId)}/original`),
  getLineage: (objectType?: string, objectId?: string) =>
    request<ApiEnvelope<JsonMap[]>>(`/api/v1/lineage${objectType && objectId ? `?object_type=${encodeURIComponent(objectType)}&object_id=${encodeURIComponent(objectId)}` : ""}`),
  listCities: () => request<ApiEnvelope<CityRecord[]>>("/api/v1/cities"),
  getCityOverview: (cityId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/cities/${cityId}/overview`),
  getCityOverviewPage: async (cityId: string) => {
    const envelope = await request<ApiEnvelope<PageViewModel>>(`/api/v1/cities/${cityId}/overview`);
    return cityOverviewToPageView(envelope.data);
  },
  getCityMapLayerList: (cityId: string) => request<ApiEnvelope<CityMapLayer[]>>(`/api/v1/cities/${cityId}/map-layers`),
  getCityMapLayers: async (cityId: string) => {
    const envelope = await request<ApiEnvelope<CityMapLayer[]>>(`/api/v1/cities/${cityId}/map-layers`);
    return cityLayerListToMapLayers(envelope.data);
  },
  updateCityMapState: (cityId: string, state: CityMapStateWrite) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/cities/${cityId}/map-state`, {
      method: "PATCH",
      body: JSON.stringify(state)
    }),
  listCityEvents: (cityId: string) => request<ApiEnvelope<CityEventRecord[]>>(`/api/v1/cities/${cityId}/events`),
  listCityEventRankings: (cityId: string, rankMode = "heat") =>
    request<ApiEnvelope<CityEventRecord[]>>(`/api/v1/cities/${cityId}/events/rankings?rank_mode=${encodeURIComponent(rankMode)}`),
  getCitySourceHealthView: (cityId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/cities/${cityId}/source-health-view`),
  listCityMediaEvidence: (cityId: string) => request<ApiEnvelope<JsonMap[]>>(`/api/v1/cities/${cityId}/media-evidence`),
  getCityTimeline: (cityId: string) => request<ApiEnvelope<JsonMap[]>>(`/api/v1/cities/${cityId}/timeline`),
  getCityEvent: (cityEventId: string) => request<ApiEnvelope<CityEventRecord>>(`/api/v1/city-events/${cityEventId}`),
  createTopicFromCityEvent: (cityEventId: string) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/city-events/${cityEventId}/create-topic`, { method: "POST" }),
  listTopics: (cityId?: string, status?: string) =>
    request<ApiEnvelope<TopicRecord[]>>(
      `/api/v1/topics${cityId || status ? `?${new URLSearchParams({ ...(cityId ? { city_id: cityId } : {}), ...(status ? { status } : {}) }).toString()}` : ""}`
    ),
  createTopic: (input: TopicCreateInput) =>
    request<ApiEnvelope<TopicRecord>>("/api/v1/topics", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getTopic: (topicId: string) => request<ApiEnvelope<TopicRecord>>(`/api/v1/topics/${topicId}`),
  updateTopic: (topicId: string, input: TopicPatchInput) =>
    request<ApiEnvelope<TopicRecord>>(`/api/v1/topics/${topicId}`, {
      method: "PATCH",
      body: JSON.stringify(input)
    }),
  getTopicSituationView: (topicId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/situation-view`),
  getTopicSourceBreakdown: (topicId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/source-breakdown`),
  getTopicSpreadPaths: (topicId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/spread-paths`),
  getTopicEmotionStance: (topicId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/emotion-stance`),
  getTopicCandidateMainlines: (topicId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/candidate-mainlines`),
  createExtractionRun: (input: ExtractionRunInput) =>
    request<ApiEnvelope<WorkflowRun>>("/api/v1/extraction-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getSignalWorkbenchView: (topicId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/signal-workbench-view`),
  listSignals: (params: { topicId?: string; status?: string; q?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.topicId) query.set("topic_id", params.topicId);
    if (params.status) query.set("status", params.status);
    if (params.q) query.set("q", params.q);
    const qs = query.toString();
    return request<ApiEnvelope<Signal[]>>(`/api/v1/signals${qs ? `?${qs}` : ""}`);
  },
  getSignal: (signalId: string) => request<ApiEnvelope<Signal & { lineage?: JsonMap[] }>>(`/api/v1/signals/${signalId}`),
  createSignalPackage: (input: SignalPackageCreateInput) =>
    request<ApiEnvelope<SignalPackageRecord>>("/api/v1/signal-packages", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getSignalPackage: (signalPackageId: string) => request<ApiEnvelope<SignalPackageRecord>>(`/api/v1/signal-packages/${signalPackageId}`),
  addSignalPackageItem: (signalPackageId: string, input: SignalPackageItemInput) =>
    request<ApiEnvelope<SignalPackageRecord>>(`/api/v1/signal-packages/${signalPackageId}/items`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  removeSignalPackageItem: (signalPackageId: string, signalId: string) =>
    request<ApiEnvelope<SignalPackageRecord>>(`/api/v1/signal-packages/${signalPackageId}/items?signal_id=${encodeURIComponent(signalId)}`, {
      method: "DELETE"
    }),
  getFirstTopicSituationPage: async (cityId = "xian") => {
    let topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    if (!topics.length) {
      let events = (await request<ApiEnvelope<CityEventRecord[]>>(`/api/v1/cities/${cityId}/events`)).data;
      if (!events.length) {
        await request<ApiEnvelope<{ raw_records: RawRecord[]; collection_run: JsonMap; data_source: DataSourceRecord }>>(
          "/api/v1/synthetic-scenarios/xian-social-issues",
          { method: "POST" }
        );
        events = (await request<ApiEnvelope<CityEventRecord[]>>(`/api/v1/cities/${cityId}/events`)).data;
      }
      const firstEvent = events[0];
      if (firstEvent) {
        await request<ApiEnvelope<TopicRecord>>("/api/v1/topics", {
          method: "POST",
          body: JSON.stringify({
            city_id: cityId,
            title: firstEvent.title,
            created_from: { object_type: "city_event", object_id: firstEvent.id },
            reason: "bootstrap topic situation page from highest available city event",
            payload: { bootstrap_source: "frontend_topic_page", synthetic: Boolean(firstEvent.payload?.synthetic) }
          })
        });
        topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
      }
    }
    const topicId = topics[0]?.id;
    if (!topicId) {
      return topicSituationToPageView({
        page_state: "empty",
        permissions: {},
        refresh_at: new Date().toISOString(),
        data_freshness: { source: "postgresql", derived_from: "topics/city_events/raw_records" },
        degraded_sources: [],
        audit_context: { object_type: "topic", object_id: null },
        primary_data: { topic: null, events: [], evidence_refs: [], degraded_sources: [] },
        actions: []
      });
    }
    const [situation, sourceBreakdown, spreadPaths, emotionStance, candidateMainlines] = await Promise.all([
      request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/situation-view`),
      request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/source-breakdown`),
      request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/spread-paths`),
      request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/emotion-stance`),
      request<ApiEnvelope<JsonMap>>(`/api/v1/topics/${topicId}/candidate-mainlines`)
    ]);
    return topicSituationToPageView(situation.data, {
      source_breakdown: sourceBreakdown.data,
      spread_paths: spreadPaths.data,
      emotion_stance: emotionStance.data,
      candidate_mainlines: candidateMainlines.data
    });
  },
  getFirstSignalWorkbenchPage: async (cityId = "xian") => {
    let topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    if (!topics.length) {
      await api.getFirstTopicSituationPage(cityId);
      topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    }
    const topicId = topics[0]?.id;
    if (!topicId) {
      return signalWorkbenchToPageView({
        page_state: "empty",
        permissions: {},
        refresh_at: new Date().toISOString(),
        data_freshness: { source: "postgresql", derived_from: "topics/raw_records/signals" },
        degraded_sources: [{ code: "NO_TOPIC", message: "No topic is available for signal extraction." }],
        audit_context: { object_type: "topic", object_id: null },
        primary_data: { topic: null, signals: [], signal_packages: [], extraction_runs: [], lineage: [] },
        actions: []
      });
    }
    let workbench = await request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/signal-workbench-view`);
    const primary = objectValue(workbench.data.primary_data);
    if (!Array.isArray(primary.signals) || primary.signals.length === 0) {
      await request<ApiEnvelope<WorkflowRun>>("/api/v1/extraction-runs", {
        method: "POST",
        body: JSON.stringify({
          topic_id: topicId,
          limit: 50,
          rule_version: "s4a-frontend-signal-extract-v1",
          payload: { source: "data_page_load", synthetic_allowed: true }
        })
      });
      workbench = await request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/signal-workbench-view`);
    }
    return signalWorkbenchToPageView(workbench.data);
  },
  createEvidenceCandidates: (input: EvidenceCandidateInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/evidence-candidates", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  listEvidenceRecords: (params: { topicId?: string; status?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.topicId) query.set("topic_id", params.topicId);
    if (params.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ApiEnvelope<Evidence[]>>(`/api/v1/evidence${qs ? `?${qs}` : ""}`);
  },
  getEvidenceRecord: (evidenceId: string) => request<ApiEnvelope<JsonMap & Evidence>>(`/api/v1/evidence/${evidenceId}`),
  getEvidenceReviewView: (reviewId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/evidence-reviews/${reviewId}/review-view`),
  updateEvidenceReview: (reviewId: string, input: EvidenceReviewPatchInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/evidence-reviews/${reviewId}`, {
      method: "PATCH",
      body: JSON.stringify(input)
    }),
  createEvidenceAttachment: (evidenceId: string, input: EvidenceAttachmentInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/evidence/${evidenceId}/attachments`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  createMediaProcessingRun: (input: MediaProcessingRunInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/media-processing-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  createRiskFactorRun: (input: RiskFactorRunInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/risk-factor-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  createConflictDetectionRun: (input: ConflictDetectionRunInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/conflict-detection-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getFirstEvidenceReviewPage: async (cityId = "xian") => {
    let topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    if (!topics.length) {
      await api.getFirstSignalWorkbenchPage(cityId);
      topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    }
    const topicId = topics[0]?.id;
    if (!topicId) {
      return evidenceReviewToPageView({
        page_state: "empty",
        permissions: {},
        refresh_at: new Date().toISOString(),
        data_freshness: { source: "postgresql", derived_from: "topics/signals/evidence" },
        degraded_sources: [{ code: "NO_TOPIC", message: "No topic is available for evidence review." }],
        audit_context: { object_type: "evidence_review", object_id: null },
        primary_data: { review: {}, evidence: {}, media_links: [], risk_factors: [], conflicts: [] },
        actions: []
      });
    }
    let evidenceList = (await request<ApiEnvelope<Evidence[]>>(`/api/v1/evidence?topic_id=${encodeURIComponent(topicId)}`)).data;
    let reviewId: string | undefined;
    if (evidenceList.length) {
      const detail = await request<ApiEnvelope<JsonMap & Evidence>>(`/api/v1/evidence/${evidenceList[0].id}`);
      const review = objectValue(detail.data.review);
      reviewId = typeof review.evidence_review_id === "string" ? review.evidence_review_id : undefined;
    }
    if (!reviewId) {
      let signals = (await request<ApiEnvelope<Signal[]>>(`/api/v1/signals?topic_id=${encodeURIComponent(topicId)}`)).data;
      if (!signals.length) {
        await request<ApiEnvelope<WorkflowRun>>("/api/v1/extraction-runs", {
          method: "POST",
          body: JSON.stringify({ topic_id: topicId, limit: 50, rule_version: "s4b-frontend-signal-bootstrap-v1" })
        });
        signals = (await request<ApiEnvelope<Signal[]>>(`/api/v1/signals?topic_id=${encodeURIComponent(topicId)}`)).data;
      }
      const created = await request<ApiEnvelope<JsonMap>>("/api/v1/evidence-candidates", {
        method: "POST",
        body: JSON.stringify({
          topic_id: topicId,
          signal_ids: signals[0]?.id ? [signals[0].id] : [],
          limit: 10,
          rule_version: "s4b-frontend-evidence-candidate-v1"
        })
      });
      const reviews = Array.isArray(created.data.reviews) ? (created.data.reviews as JsonMap[]) : [];
      reviewId = typeof reviews[0]?.evidence_review_id === "string" ? reviews[0].evidence_review_id : undefined;
      evidenceList = (await request<ApiEnvelope<Evidence[]>>(`/api/v1/evidence?topic_id=${encodeURIComponent(topicId)}`)).data;
    }
    if (!reviewId && evidenceList[0]?.id) {
      const detail = await request<ApiEnvelope<JsonMap & Evidence>>(`/api/v1/evidence/${evidenceList[0].id}`);
      const review = objectValue(detail.data.review);
      reviewId = typeof review.evidence_review_id === "string" ? review.evidence_review_id : undefined;
    }
    if (!reviewId) {
      throw new Error("S4B evidence review could not be initialized from backend data.");
    }
    const reviewView = await request<ApiEnvelope<PageViewModel>>(`/api/v1/evidence-reviews/${reviewId}/review-view`);
    return evidenceReviewToPageView(reviewView.data);
  },
  listMainlines: (params: { caseId?: string; topicId?: string; status?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.caseId) query.set("case_id", params.caseId);
    if (params.topicId) query.set("topic_id", params.topicId);
    if (params.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ApiEnvelope<Mainline[]>>(`/api/v1/mainlines${qs ? `?${qs}` : ""}`);
  },
  createProductionMainline: (input: MainlineCreateInput) =>
    request<ApiEnvelope<Mainline>>("/api/v1/mainlines", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getMainline: (mainlineId: string) => request<ApiEnvelope<Mainline>>(`/api/v1/mainlines/${mainlineId}`),
  getMainlineBuilderView: (mainlineId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/mainlines/${mainlineId}/builder-view`),
  updateMainlineNode: (nodeId: string, input: MainlineNodePatchInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/mainline-nodes/${nodeId}`, {
      method: "PATCH",
      body: JSON.stringify(input)
    }),
  updateMainlineSignal: (mainlineId: string, input: MainlineSignalInput) =>
    request<ApiEnvelope<Mainline>>(`/api/v1/mainlines/${mainlineId}/signals`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  runMainlineQualityCheck: (mainlineId: string) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/mainlines/${mainlineId}/quality-check`, { method: "POST" }),
  confirmProductionMainline: (mainlineId: string) =>
    request<ApiEnvelope<Mainline>>(`/api/v1/mainlines/${mainlineId}/confirm`, { method: "POST" }),
  createWorldState: (input: WorldStateCreateInput) =>
    request<ApiEnvelope<WorldState>>("/api/v1/world-states", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getWorldState: (worldStateId: string) => request<ApiEnvelope<WorldState>>(`/api/v1/world-states/${worldStateId}`),
  createCaseGraphRun: (input: CaseGraphRunInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/case-graph-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  createStakeholderRun: (input: StakeholderRunInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/stakeholder-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  listStakeholders: (params: { topicId?: string; mainlineId?: string; status?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.topicId) query.set("topic_id", params.topicId);
    if (params.mainlineId) query.set("mainline_id", params.mainlineId);
    if (params.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ApiEnvelope<JsonMap[]>>(`/api/v1/stakeholders${qs ? `?${qs}` : ""}`);
  },
  reviewStakeholder: (stakeholderId: string, input: StakeholderReviewInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/stakeholders/${stakeholderId}/review`, {
      method: "PATCH",
      body: JSON.stringify(input)
    }),
  getFirstMainlineBuilderPage: async (cityId = "xian") => {
    let topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    if (!topics.length) {
      await api.getFirstSignalWorkbenchPage(cityId);
      topics = (await request<ApiEnvelope<TopicRecord[]>>(`/api/v1/topics?city_id=${encodeURIComponent(cityId)}`)).data;
    }
    const topicId = topics[0]?.id;
    if (!topicId) {
      return mainlineBuilderToPageView({
        page_state: "empty",
        permissions: {},
        refresh_at: new Date().toISOString(),
        data_freshness: { source: "postgresql", derived_from: "topics/signal_packages/evidence/mainlines" },
        degraded_sources: [{ code: "NO_TOPIC", message: "No topic is available for mainline modeling." }],
        audit_context: { object_type: "mainline", object_id: null },
        primary_data: { mainline: {}, nodes: [], evidence: [], versions: [], case_graph_nodes: [], stakeholders: [] },
        actions: []
      });
    }

    let workbench = await request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/signal-workbench-view`);
    let workbenchPrimary = objectValue(workbench.data.primary_data);
    if (!Array.isArray(workbenchPrimary.signals) || workbenchPrimary.signals.length === 0) {
      await api.createExtractionRun({ topic_id: topicId, limit: 50, rule_version: "s5-frontend-signal-bootstrap-v1", payload: { source: "mainline_page_load" } });
      workbench = await request<ApiEnvelope<PageViewModel>>(`/api/v1/topics/${topicId}/signal-workbench-view`);
      workbenchPrimary = objectValue(workbench.data.primary_data);
    }
    const signals = Array.isArray(workbenchPrimary.signals) ? (workbenchPrimary.signals as Signal[]) : [];
    if (!signals.length) {
      throw new Error("S5 mainline builder requires persisted signals.");
    }

    const packages = Array.isArray(workbenchPrimary.signal_packages) ? (workbenchPrimary.signal_packages as SignalPackageRecord[]) : [];
    let packageRecord = packages.find((item) => Array.isArray(item.items) && item.items.length > 0);
    if (!packageRecord) {
      const createdPackage = await api.createSignalPackage({
        topic_id: topicId,
        name: "S5 frontend mainline signal package",
        rule_version: "s5-frontend-package-v1",
        reason: "Created from mainline builder page bootstrap",
        payload: { source: "mainline_page_load", synthetic_allowed: true }
      });
      packageRecord = createdPackage.data;
      for (const [index, signal] of signals.slice(0, 2).entries()) {
        await api.addSignalPackageItem(packageRecord.signal_package_id, {
          signal_id: signal.id,
          rank: index + 1,
          reason: "Added from mainline builder page bootstrap",
          payload: { source: "mainline_page_load" }
        });
      }
      packageRecord = (await api.getSignalPackage(packageRecord.signal_package_id)).data;
    }
    const packageId = packageRecord.signal_package_id || packageRecord.id;
    if (!packageId) {
      throw new Error("S5 mainline builder requires a persisted signal package.");
    }

    let evidenceList = (await api.listEvidenceRecords({ topicId })).data;
    let confirmedEvidence = evidenceList.find((item) => item.status === "confirmed_fact" || item.status === "used_in_mainline");
    if (!confirmedEvidence) {
      if (!evidenceList.length) {
        await api.createEvidenceCandidates({
          topic_id: topicId,
          signal_ids: signals.slice(0, 2).map((signal) => signal.id),
          limit: 10,
          rule_version: "s5-frontend-evidence-bootstrap-v1",
          payload: { source: "mainline_page_load" }
        });
        evidenceList = (await api.listEvidenceRecords({ topicId })).data;
      }
      const firstEvidence = evidenceList[0];
      if (firstEvidence?.id) {
        const detail = await api.getEvidenceRecord(firstEvidence.id);
        const review = objectValue(detail.data.review);
        const reviewId = stringField(review, "evidence_review_id");
        if (reviewId) {
          await api.updateEvidenceReview(reviewId, {
            status: "confirmed",
            reason: "S5 mainline page requires evidence-confirmed input before drafting.",
            payload: { source: "mainline_page_load" }
          });
        }
      }
    }

    const existingMainlines = (await api.listMainlines({ topicId })).data;
    let mainline = existingMainlines.find((item) => objectValue(item.payload).signal_package_id === packageId && item.status !== "archived");
    if (!mainline) {
      mainline = (await api.createProductionMainline({
        topic_id: topicId,
        signal_package_id: packageId,
        title: "S5 evidence-backed mainline",
        reason: "Generate mainline draft from signal package and confirmed evidence.",
        payload: { source: "mainline_page_load", synthetic_allowed: true }
      })).data;
    }
    const builder = await api.getMainlineBuilderView(mainline.id);
    return mainlineBuilderToPageView(builder.data);
  },
  createWorldlineRun: (input: WorldlineRunCreateInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/worldline-runs", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getWorldlineRun: (worldlineRunId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/worldline-runs/${worldlineRunId}`),
  getWorldlineSimulationView: (worldlineRunId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/worldline-runs/${worldlineRunId}/simulation-view`),
  addWorldlineIntervention: (worldlineRunId: string, input: WorldlineInterventionInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/worldline-runs/${worldlineRunId}/interventions`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  listLlmProviders: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/llm-providers"),
  listLlmCalls: (objectId?: string) => request<ApiEnvelope<JsonMap[]>>(`/api/v1/llm-calls${objectId ? `?object_id=${encodeURIComponent(objectId)}` : ""}`),
  listPromptTemplates: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/prompt-templates"),
  listAgentTemplates: () => request<ApiEnvelope<JsonMap[]>>("/api/v1/agent-templates"),
  createAgentProfile: (input: AgentProfileCreateInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/agent-profiles", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getAgentProfile: (agentProfileId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/agent-profiles/${agentProfileId}`),
  createAgentProfileFiles: (agentProfileId: string, input: AgentProfileFilesInput) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/agent-profiles/${agentProfileId}/files`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  createCouncilSession: (input: CouncilSessionCreateInput) =>
    request<ApiEnvelope<JsonMap>>("/api/v1/council-sessions", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getCouncilView: (councilSessionId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/council-sessions/${councilSessionId}/council-view`),
  runCouncilSession: (councilSessionId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/council-sessions/${councilSessionId}/run`, { method: "POST" }),
  applyCouncilResult: (councilResultId: string) => request<ApiEnvelope<JsonMap>>(`/api/v1/council-results/${councilResultId}/apply`, { method: "POST" }),
  listReports: (params: { topicId?: string; status?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.topicId) query.set("topic_id", params.topicId);
    if (params.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ApiEnvelope<Report[]>>(`/api/v1/reports${qs ? `?${qs}` : ""}`);
  },
  createReportDraft: (input: ReportCreateInput) =>
    request<ApiEnvelope<Report>>("/api/v1/reports", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getReport: (reportId: string) => request<ApiEnvelope<Report>>(`/api/v1/reports/${reportId}`),
  updateReport: (reportId: string, input: ReportPatchInput) =>
    request<ApiEnvelope<Report>>(`/api/v1/reports/${reportId}`, {
      method: "PATCH",
      body: JSON.stringify(input)
    }),
  getReportBriefView: (reportId: string) => request<ApiEnvelope<PageViewModel>>(`/api/v1/reports/${reportId}/brief-view`),
  submitReportReview: (reportId: string) => request<ApiEnvelope<ReviewRecord>>(`/api/v1/reports/${reportId}/submit-review`, { method: "POST" }),
  publishReport: (reportId: string) => request<ApiEnvelope<Report>>(`/api/v1/reports/${reportId}/publish`, { method: "POST" }),
  exportReport: (reportId: string, input: ReportExportInput = {}) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/reports/${reportId}/exports`, {
      method: "POST",
      body: JSON.stringify({ format: input.format ?? "markdown", reason: input.reason ?? "Exported from React report page." })
    }),
  listProductionTasks: (params: { reportId?: string; status?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.reportId) query.set("report_id", params.reportId);
    if (params.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ApiEnvelope<Task[]>>(`/api/v1/tasks${qs ? `?${qs}` : ""}`);
  },
  createRetrospective: (reportId: string, reason = "S7B frontend retrospective bootstrap") =>
    request<ApiEnvelope<Retrospective>>("/api/v1/retrospectives", {
      method: "POST",
      body: JSON.stringify({ report_id: reportId, reason })
    }),
  getRetrospectiveMemoryView: (retrospectiveId: string) =>
    request<ApiEnvelope<PageViewModel>>(`/api/v1/retrospectives/${retrospectiveId}/memory-view`),
  submitRetrospectiveReview: (retrospectiveId: string) =>
    request<ApiEnvelope<ReviewRecord>>(`/api/v1/retrospectives/${retrospectiveId}/submit-review`, { method: "POST" }),
  publishRetrospective: (retrospectiveId: string) =>
    request<ApiEnvelope<Retrospective>>(`/api/v1/retrospectives/${retrospectiveId}/publish`, { method: "POST" }),
  getCaseLibraryView: (q?: string) =>
    request<ApiEnvelope<PageViewModel>>(`/api/v1/cases/library-view${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  listCaseLibraryEntries: (q?: string) =>
    request<ApiEnvelope<CaseLibraryEntry[]>>(`/api/v1/case-library-entries${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getCaseLibraryEntry: (entryId: string) => request<ApiEnvelope<CaseLibraryEntry>>(`/api/v1/case-library-entries/${entryId}`),
  applyCaseLibraryEntry: (entryId: string, input: { case_id: string; object_type: string; object_id: string; reason?: string; payload?: JsonMap }) =>
    request<ApiEnvelope<JsonMap>>(`/api/v1/case-library-entries/${entryId}/apply`, {
      method: "POST",
      body: JSON.stringify(input)
    }),
  getConfigAdminView: () => request<ApiEnvelope<PageViewModel>>("/api/v1/config/admin-view"),
  listConfigVersions: () => request<ApiEnvelope<ConfigVersion[]>>("/api/v1/config/versions"),
  createConfigVersion: (input: ConfigVersionCreateInput) =>
    request<ApiEnvelope<ConfigVersion>>("/api/v1/config/versions", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  runConfigRegression: (configVersionId: string) =>
    request<ApiEnvelope<WorkflowRun>>(`/api/v1/config/versions/${configVersionId}/regression-runs`, { method: "POST" }),
  submitConfigApproval: (configVersionId: string, reason = "S7B frontend config approval") =>
    request<ApiEnvelope<ReviewRecord>>(`/api/v1/config/versions/${configVersionId}/submit-approval`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  publishConfigVersion: (configVersionId: string) =>
    request<ApiEnvelope<ConfigRelease>>(`/api/v1/config/versions/${configVersionId}/publish`, { method: "POST" }),
  rollbackConfigRelease: (configReleaseId: string, reason = "S7B frontend rollback validation") =>
    request<ApiEnvelope<ConfigRelease>>(`/api/v1/config/releases/${configReleaseId}/rollback`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  getFirstRetrospectiveMemoryPage: async (cityId = "xian") => {
    const reportPage = await api.getFirstReportBriefPage(cityId);
    const reportId = stringField(reportPage.raw, "report_id");
    if (!reportId) throw new Error("S7B memory page requires an S7A report.");
    const report = await api.getReport(reportId);
    let reportStatus = report.data.status;
    if (reportStatus !== "published" && reportStatus !== "exported") {
      let reviewId = report.data.review_id || stringField(reportPage.raw, "review_id");
      if (!reviewId) {
        const review = await api.submitReportReview(reportId);
        reviewId = review.data.review_id;
      }
      await api.updateReview(reviewId, "pass", ["Report remains evidence-linked for retrospective memory."], []);
      await api.gateCheck(reviewId);
      await api.publishReport(reportId);
      await api.exportReport(reportId, { format: "markdown", reason: "S7B retrospective source export." });
      reportStatus = "exported";
    }
    void reportStatus;
    const retrospective = await api.createRetrospective(reportId);
    const view = await api.getRetrospectiveMemoryView(retrospective.data.id);
    return retrospectiveMemoryToPageView(view.data);
  },
  getFirstCaseLibraryPage: async (cityId = "xian") => {
    const memoryPage = await api.getFirstRetrospectiveMemoryPage(cityId);
    const retrospectiveId = stringField(memoryPage.raw, "retrospective_id");
    if (!retrospectiveId) throw new Error("S7B case library page requires a retrospective.");
    let reviewId = stringField(memoryPage.raw, "review_id");
    if (!reviewId) {
      const review = await api.submitRetrospectiveReview(retrospectiveId);
      reviewId = review.data.review_id;
    }
    await api.updateReview(reviewId, "pass", ["Retrospective knowledge preserves evidence references and is case-library ready."], []);
    await api.gateCheck(reviewId);
    await api.publishRetrospective(retrospectiveId);
    const view = await api.getCaseLibraryView("information gap");
    return caseLibraryToPageView(view.data);
  },
  getFirstConfigAdminPage: async (cityId = "xian") => {
    const libraryPage = await api.getFirstCaseLibraryPage(cityId);
    const entryId = stringField(libraryPage.raw, "first_entry_id");
    const versions = (await api.listConfigVersions()).data;
    const reusable = versions.find((item) => item.status === "draft" || item.status === "approval_pending" || item.status === "regression_failed");
    if (!reusable) {
      await api.createConfigVersion({
        config_type: "model",
        payload: {
          name: "xian-social-risk-model",
          parameters: { breakout_threshold: 0.61, noise_discount: 0.64 },
          source_refs: entryId ? [{ object_type: "case_library_entry", object_id: entryId }] : []
        },
        reason: "S7B frontend config draft bootstrap"
      });
    }
    const view = await api.getConfigAdminView();
    return configAdminToPageView(view.data);
  },
  getFirstReportBriefPage: async (cityId = "xian") => {
    const councilPage = await api.getFirstCouncilPage(cityId);
    const councilId = stringField(councilPage.raw, "council_session_id");
    let councilResultId = stringField(councilPage.raw, "council_result_id");
    let worldlineRunId = stringField(councilPage.raw, "worldline_run_id");
    if (!councilResultId) {
      if (!councilId) throw new Error("S7A report page requires a Council Session.");
      const council = await api.runCouncilSession(councilId);
      const payload = objectValue(council.data.payload);
      councilResultId = stringField(payload, "result_id");
      worldlineRunId = worldlineRunId || stringField(council.data, "worldline_run_id") || stringField(payload, "worldline_run_id");
    }
    if (!councilResultId) throw new Error("S7A report page requires a Council Result.");
    const councilReview = await api.createReview("council_result", councilResultId, "v1", "TPL-COUNCIL-RESULT-V1");
    await api.updateReview(councilReview.data.review_id, "pass", ["Council result is evidence-linked for report generation."], []);
    await api.gateCheck(councilReview.data.review_id);
    const applied = await api.applyCouncilResult(councilResultId);
    worldlineRunId = worldlineRunId || stringField(applied.data, "worldline_run_id");
    if (!worldlineRunId) throw new Error("S7A report page requires a Worldline Run.");
    const worldline = await api.getWorldlineRun(worldlineRunId);
    const mainlineId = stringField(objectValue(worldline.data.payload), "mainline_id");
    if (!mainlineId) throw new Error("S7A report page requires a Mainline from the Worldline Run.");
    const mainline = await api.getMainline(mainlineId);
    const topicId = stringField(mainline.data, "topic_id") || stringField(objectValue(mainline.data.payload), "topic_id");
    if (!topicId) throw new Error("S7A report page requires a Topic from the Mainline.");
    const reports = (await api.listReports({ topicId })).data;
    let report = reports.find((item) => stringField(objectValue(item.payload), "council_result_id") === councilResultId);
    if (!report) {
      report = (await api.createReportDraft({ topic_id: topicId, council_result_id: councilResultId, reason: "S7A frontend report draft bootstrap" })).data;
    }
    const view = await api.getReportBriefView(report.id);
    return reportBriefToPageView(view.data);
  },
  getFirstWorldlineSimulationPage: async (cityId = "xian") => {
    const mainlinePage = await api.getFirstMainlineBuilderPage(cityId);
    const mainlineId = stringField(mainlinePage.raw, "mainline_id");
    let worldStateId = stringField(mainlinePage.raw, "world_state_id");
    if (mainlineId && !worldStateId) {
      await api.runMainlineQualityCheck(mainlineId);
      const confirmed = await api.confirmProductionMainline(mainlineId);
      const worldState = await api.createWorldState({ mainline_id: mainlineId, reason: "S6 worldline page bootstrap", payload: { source: "worldline_page_load" } });
      worldStateId = stringField(worldState.data, "id");
      if (worldStateId) {
        await api.createCaseGraphRun({ mainline_id: mainlineId, world_state_id: worldStateId, rule_version: "s6-frontend-case-graph-bootstrap-v1" });
        const stakeholderRun = await api.createStakeholderRun({ mainline_id: mainlineId, world_state_id: worldStateId, rule_version: "s6-frontend-stakeholder-bootstrap-v1" });
        const stakeholders = Array.isArray(stakeholderRun.data.stakeholders) ? (stakeholderRun.data.stakeholders as JsonMap[]) : [];
        const stakeholderId = stringField(stakeholders[0], "id");
        if (stakeholderId) await api.reviewStakeholder(stakeholderId, { decision: "pass", reason: "S6 worldline bootstrap stakeholder review." });
      }
      void confirmed;
    }
    if (!worldStateId) throw new Error("S6 worldline page requires a persisted World State.");
    const run = await api.createWorldlineRun({ world_state_id: worldStateId, options: { source: "worldline_page_load", horizon_hours: 72 } });
    const runId = stringField(run.data, "id");
    if (!runId) throw new Error("S6 worldline run creation did not return an id.");
    const view = await api.getWorldlineSimulationView(runId);
    return worldlineSimulationToPageView(view.data);
  },
  getFirstCouncilPage: async (cityId = "xian") => {
    const worldlinePage = await api.getFirstWorldlineSimulationPage(cityId);
    const worldlineRunId = stringField(worldlinePage.raw, "worldline_run_id");
    const selectedNodeId = stringField(worldlinePage.raw, "selected_node_id");
    const mainlineId = stringField(worldlinePage.raw, "mainline_id");
    if (!worldlineRunId || !selectedNodeId || !mainlineId) throw new Error("S6 Council page requires worldline run, selected node, and mainline ids.");
    const stakeholders = (await api.listStakeholders({ mainlineId })).data;
    const stakeholder = stakeholders.find((item) => stringField(item, "status") === "reviewed") ?? stakeholders[0];
    const stakeholderId = stringField(stakeholder, "id");
    if (!stakeholderId) throw new Error("S6 Council page requires a reviewed stakeholder.");
    await api.listLlmProviders();
    await api.listPromptTemplates();
    await api.listAgentTemplates();
    const profile = await api.createAgentProfile({ stakeholder_id: stakeholderId, worldline_run_id: worldlineRunId });
    const profileId = stringField(profile.data, "id");
    if (!profileId) throw new Error("S6 Agent Profile creation did not return an id.");
    await api.createAgentProfileFiles(profileId, {
      user_md: "# User\nReviewed stakeholder context with evidence refs only.",
      soul_md: "# Soul\nEvidence-bounded stance and uncertainty policy.",
      agent_md: "# Agent\nUse guardrails, cite evidence refs, block unsupported claims.",
      reason: "S6 Council page profile file bootstrap"
    });
    const profileReview = await api.createReview("agent_profile", profileId, "v1", "TPL-AGENT-PROFILE-V1");
    await api.updateReview(profileReview.data.review_id, "pass", ["Profile files are evidence-bounded."], []);
    await api.gateCheck(profileReview.data.review_id);
    await api.getAgentProfile(profileId);
    const council = await api.createCouncilSession({
      worldline_run_id: worldlineRunId,
      selected_node_id: selectedNodeId,
      agent_profile_ids: [profileId],
      hypothesis: "Evidence window delay may increase offline pressure."
    });
    const councilId = stringField(council.data, "id");
    if (!councilId) throw new Error("S6 Council Session creation did not return an id.");
    const view = await api.getCouncilView(councilId);
    return councilViewToPageView(view.data);
  },
  seed: (fixture = "all") =>
    request<Record<string, number>>("/api/v1/admin/seed", {
      method: "POST",
      body: JSON.stringify({ fixture })
    }),
  listCases: () => request<CaseOut[]>("/api/v1/cases"),
  getCaseBundle: (caseId: string) => request<CaseBundle>(`/api/v1/cases/${caseId}`),
  getPageView: (caseId: string, page: ProductPageName) => request<PageView>(`/api/v1/cases/${caseId}/pages/${page}`),
  getMapLayers: (caseId: string) => request<MapLayers>(`/api/v1/map-layers/${caseId}`),
  updateSignal: (signalId: string, status: string, priority?: string, reason = "updated from product page") =>
    request<Signal>(`/api/v1/signals/${signalId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, priority, actor: "analyst", reason })
    }),
  updateDraftSignal: (mainlineId: string, signalId: string, action: "add" | "remove") =>
    request<Mainline>(`/api/v1/mainlines/${mainlineId}/draft-signals`, {
      method: "POST",
      body: JSON.stringify({ signal_id: signalId, action, actor: "analyst" })
    }),
  getSimilarSignals: (signalId: string) => request<Signal[]>(`/api/v1/signals/${signalId}/similar`),
  createMainline: (caseId: string, title: string) =>
    request<Mainline>("/api/v1/mainlines", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, title, confidence: 0.62, status: "draft", actor: "analyst" })
    }),
  updateMainline: (mainlineId: string, payload: JsonMap) =>
    request<Mainline>(`/api/v1/mainlines/${mainlineId}`, {
      method: "PATCH",
      body: JSON.stringify({ payload, actor: "analyst", reason: "updated from product page" })
    }),
  confirmMainline: (mainlineId: string) =>
    request<Mainline>(`/api/v1/mainlines/${mainlineId}/confirm`, { method: "POST" }),
  updateEvidence: (evidenceId: string, status: string, reason: string) =>
    request<Evidence>(`/api/v1/evidence/${evidenceId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, actor: "analyst", reason })
    }),
  updateFactor: (factorId: string, status: string, reason: string) =>
    request<RiskFactor>(`/api/v1/risk-factors/${factorId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, actor: "analyst", reason })
    }),
  runCouncil: (nodeId: string) =>
    request<CouncilSession>(`/api/v1/worldline-nodes/${nodeId}/run-council`, { method: "POST" }),
  applyCouncil: (sessionId: string) =>
    request<CouncilSession>(`/api/v1/council-sessions/${sessionId}/apply`, { method: "POST" }),
  runPressureTest: (sessionId: string, hypothesis: string) =>
    request<CouncilSession>(`/api/v1/council-sessions/${sessionId}/pressure-tests`, {
      method: "POST",
      body: JSON.stringify({ hypothesis, actor: "analyst" })
    }),
  confirmReport: (reportId: string) =>
    request<Report>(`/api/v1/reports/${reportId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ actor: "reviewer", reason: "human confirmed from P0 web console" })
    }),
  createTask: (caseId: string, title: string, owner = "operator") =>
    request<Task>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, title, owner, due_label: "2h", status: "suggested", actor: "operator" })
    }),
  updateTask: (taskId: string, status: string, reason: string) =>
    request<Task>(`/api/v1/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({ status, actor: "operator", reason })
    }),
  runCaseMemoryAction: (caseId: string, action: "save_draft" | "submit_review" | "confirm_ingest") =>
    request<{ status: string }> (`/api/v1/case-memories/${caseId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, actor: "analyst" })
    }),
  applyLibraryItem: (caseId: string, objectType: string, objectId: string) =>
    request<{ status: string }>("/api/v1/library/apply", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, object_type: objectType, object_id: objectId, actor: "analyst" })
    }),
  runConfigAction: (versionId: string, caseId: string, action: "run_regression" | "submit_approval" | "publish") =>
    request<{ status: string }>(`/api/v1/config/versions/${versionId}/actions`, {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, action, actor: "admin" })
    }),
  startWorkflow: (workflowName: string, caseId: string, targetId?: string) =>
    request<WorkflowRun>(`/api/v1/workflows/${workflowName}/start`, {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, target_id: targetId ?? null })
    })
};
