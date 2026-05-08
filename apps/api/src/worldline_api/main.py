from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, services
from .config import settings
from .database import engine, get_session
from .search import search_adapter
from .workflow_runtime import execute_p0_workflow

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="CollectiveEventTwin P0 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_tables:
        models.Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "collective-event-twin-api"}


@app.post("/api/v1/admin/seed")
def seed(request: schemas.SeedRequest, session: Session = Depends(get_session)) -> dict[str, int]:
    return services.seed_p0(session, request.fixture)


@app.get("/api/v1/cases", response_model=list[schemas.CaseOut])
def cases(session: Session = Depends(get_session)):
    return services.list_cases(session)


@app.get("/api/v1/search", response_model=list[schemas.SearchResultOut])
def search(q: str, limit: int = 20, session: Session = Depends(get_session)):
    return search_adapter.search(session, q, limit)


@app.get("/api/v1/cases/{case_id}", response_model=schemas.ClosedLoopOut)
def case_bundle(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)


@app.get("/api/v1/cases/{case_id}/pages/{page}", response_model=schemas.PageViewOut)
def case_page(case_id: str, page: str, session: Session = Depends(get_session)):
    return services.get_page_view(session, case_id, page)


@app.get("/api/v1/cases/{case_id}/signals", response_model=list[schemas.SignalOut])
def case_signals(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["signals"]


@app.get("/api/v1/cases/{case_id}/sources", response_model=list[schemas.SourceRecordOut])
def case_sources(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["source_records"]


@app.get("/api/v1/cases/{case_id}/evidence", response_model=list[schemas.EvidenceOut])
def case_evidence(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["evidence"]


@app.get("/api/v1/cases/{case_id}/risk-factors", response_model=list[schemas.RiskFactorOut])
def case_risk_factors(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["risk_factors"]


@app.get("/api/v1/cases/{case_id}/mainline", response_model=schemas.MainlineOut | None)
def case_mainline(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["mainline"]


@app.get("/api/v1/cases/{case_id}/worldline", response_model=list[schemas.WorldlineNodeOut])
def case_worldline(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["worldline_nodes"]


@app.get("/api/v1/cases/{case_id}/report", response_model=schemas.ReportOut | None)
def case_report(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["report"]


@app.get("/api/v1/cases/{case_id}/audit", response_model=list[schemas.AuditLogOut])
def case_audit(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["audit"]


@app.get("/api/v1/cases/{case_id}/workflow-runs", response_model=list[schemas.WorkflowRunOut])
def case_workflow_runs(case_id: str, session: Session = Depends(get_session)):
    return services.get_case_bundle(session, case_id)["workflow_runs"]


@app.get("/api/v1/map-layers/{case_id}")
def case_map_layers(case_id: str, session: Session = Depends(get_session)):
    return services.map_layers(session, case_id)


@app.patch("/api/v1/evidence/{evidence_id}", response_model=schemas.EvidenceOut)
def update_evidence(evidence_id: str, update: schemas.EvidenceUpdate, session: Session = Depends(get_session)):
    return services.update_evidence_status(session, evidence_id, update.status, update.actor, update.reason)


@app.patch("/api/v1/signals/{signal_id}", response_model=schemas.SignalOut)
def update_signal(signal_id: str, update: schemas.SignalUpdate, session: Session = Depends(get_session)):
    return services.update_signal(session, signal_id, update.status, update.priority, update.actor, update.reason)


@app.get("/api/v1/signals/{signal_id}/similar", response_model=list[schemas.SignalOut])
def similar_signals(signal_id: str, limit: int = 6, session: Session = Depends(get_session)):
    return services.similar_signals(session, signal_id, limit)


@app.patch("/api/v1/risk-factors/{factor_id}", response_model=schemas.RiskFactorOut)
def update_factor(factor_id: str, update: schemas.RiskFactorUpdate, session: Session = Depends(get_session)):
    return services.update_factor_status(session, factor_id, update.status, update.actor, update.reason)


@app.post("/api/v1/mainlines", response_model=schemas.MainlineOut)
def create_mainline(request: schemas.MainlineCreate, session: Session = Depends(get_session)):
    return services.create_mainline(session, request.case_id, request.title, request.confidence, request.status, request.payload, request.actor)


@app.patch("/api/v1/mainlines/{mainline_id}", response_model=schemas.MainlineOut)
def update_mainline(mainline_id: str, request: schemas.MainlinePatch, session: Session = Depends(get_session)):
    return services.update_mainline(session, mainline_id, request.title, request.confidence, request.status, request.payload, request.actor, request.reason)


@app.post("/api/v1/mainlines/{mainline_id}/draft-signals", response_model=schemas.MainlineOut)
def update_mainline_draft_signal(mainline_id: str, request: schemas.DraftSignalRequest, session: Session = Depends(get_session)):
    return services.update_mainline_draft_signal(session, mainline_id, request.signal_id, request.action, request.actor, request.reason)


@app.post("/api/v1/mainlines/{mainline_id}/confirm", response_model=schemas.MainlineOut)
def confirm_mainline(mainline_id: str, session: Session = Depends(get_session)):
    return services.confirm_mainline(session, mainline_id)


@app.post("/api/v1/worldline-nodes/{node_id}/run-council", response_model=schemas.CouncilSessionOut)
def run_council(node_id: str, session: Session = Depends(get_session)):
    return services.run_council(session, node_id)


@app.post("/api/v1/council-sessions/{session_id}/apply", response_model=schemas.CouncilSessionOut)
def apply_council(session_id: str, session: Session = Depends(get_session)):
    return services.apply_council(session, session_id)


@app.post("/api/v1/council-sessions/{session_id}/pressure-tests", response_model=schemas.CouncilSessionOut)
def run_pressure_test(session_id: str, request: schemas.PressureTestRequest, session: Session = Depends(get_session)):
    return services.run_pressure_test(session, session_id, request.hypothesis, request.actor)


@app.post("/api/v1/reports/{report_id}/confirm", response_model=schemas.ReportOut)
def confirm_report(report_id: str, request: schemas.ReportConfirm, session: Session = Depends(get_session)):
    return services.confirm_report(session, report_id, request.actor, request.reason)


@app.post("/api/v1/tasks", response_model=schemas.TaskOut)
def create_task(request: schemas.TaskCreate, session: Session = Depends(get_session)):
    return services.create_task(session, request.case_id, request.title, request.owner, request.due_label, request.status, request.payload, request.actor)


@app.patch("/api/v1/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: str, update: schemas.TaskUpdate, session: Session = Depends(get_session)):
    return services.update_task_status(session, task_id, update.status, update.actor, update.reason)


@app.post("/api/v1/case-memories/{case_id}/actions", response_model=schemas.GenericActionOut)
def run_case_memory_action(case_id: str, request: schemas.CaseMemoryActionRequest, session: Session = Depends(get_session)):
    return services.run_case_memory_action(session, case_id, request.action, request.actor, request.payload)


@app.post("/api/v1/library/apply", response_model=schemas.GenericActionOut)
def apply_library_item(request: schemas.LibraryApplyRequest, session: Session = Depends(get_session)):
    return services.apply_library_item(session, request.case_id, request.object_type, request.object_id, request.actor, request.payload)


@app.post("/api/v1/config/versions/{version_id}/actions", response_model=schemas.GenericActionOut)
def run_config_version_action(version_id: str, request: schemas.ConfigVersionActionRequest, session: Session = Depends(get_session)):
    return services.run_config_version_action(session, version_id, request.case_id, request.action, request.actor, request.payload)


@app.post("/api/v1/workflows/{workflow_name}/start", response_model=schemas.WorkflowRunOut)
async def start_workflow(workflow_name: str, request: schemas.WorkflowStartRequest, session: Session = Depends(get_session)):
    try:
        workflow_id, result = await execute_p0_workflow(workflow_name, case_id=request.case_id, target_id=request.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return services.record_workflow_execution(
        session,
        case_id=request.case_id,
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        status="completed",
        payload={"result": result, "target_id": request.target_id},
    )
