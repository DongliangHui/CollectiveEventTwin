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
    case_id: str
    title: str
    confidence: float = 0.6
    status: str = "draft"
    payload: dict[str, Any] = {}
    actor: str = "analyst"


class MainlinePatch(BaseModel):
    title: str | None = None
    confidence: float | None = None
    status: str | None = None
    payload: dict[str, Any] | None = None
    actor: str = "analyst"
    reason: str | None = None


class PressureTestRequest(BaseModel):
    hypothesis: str
    actor: str = "analyst"


class TaskCreate(BaseModel):
    case_id: str
    title: str
    owner: str
    due_label: str = "2h"
    status: str = Field(default="suggested", pattern="^(suggested|in_progress|completed|overdue|blocked)$")
    payload: dict[str, Any] = {}
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
