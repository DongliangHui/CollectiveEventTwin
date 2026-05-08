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
  title: string;
  confidence: number;
  status: string;
  payload: { signals?: string[]; support_points?: string[]; evidence_gaps?: string[] };
};

export type WorldState = {
  id: string;
  case_id: string;
  title: string;
  status: string;
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
  title: string;
  human_confirmed: boolean;
  status: string;
  payload: { draft_summary?: string; formal_conclusion?: string; compliance_note?: string };
};

export type Task = {
  id: string;
  case_id: string;
  title: string;
  owner: string;
  due_label: string;
  status: string;
  payload: JsonMap;
};

export type WorkflowRun = {
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

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
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
