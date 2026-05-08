from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import write_audit
from .fixtures_v2 import p0_fixtures
from .models import (
    AuditLog,
    Case,
    CouncilSession,
    Evidence,
    Mainline,
    Report,
    RiskFactor,
    Signal,
    SourceRecord,
    Task,
    WorkflowRun,
    WorldState,
    WorldlineNode,
)
from .page_view_models import build_page_view
from .policy import mask_sensitive_text, sensitivity_level, source_allowed
from .schemas import CouncilAgentOutput


def list_cases(session: Session) -> list[Case]:
    return list(session.scalars(select(Case).order_by(Case.id)))


def get_case(session: Session, case_id: str) -> Case:
    return session.get(Case, case_id) or _not_found("case", case_id)


def get_case_bundle(session: Session, case_id: str) -> dict:
    case = get_case(session, case_id)
    return {
        "case": case,
        "source_records": _all(session, SourceRecord, case_id),
        "signals": _all(session, Signal, case_id),
        "evidence": _all(session, Evidence, case_id),
        "risk_factors": _all(session, RiskFactor, case_id),
        "mainline": session.scalars(select(Mainline).where(Mainline.case_id == case_id)).first(),
        "world_state": session.scalars(select(WorldState).where(WorldState.case_id == case_id)).first(),
        "worldline_nodes": _all(session, WorldlineNode, case_id),
        "council_sessions": _all(session, CouncilSession, case_id),
        "report": session.scalars(select(Report).where(Report.case_id == case_id)).first(),
        "tasks": _all(session, Task, case_id),
        "workflow_runs": _all(session, WorkflowRun, case_id),
        "audit": _all_audit(session, case_id),
    }


def seed_p0(session: Session, fixture: str = "all") -> dict[str, int]:
    fixtures = p0_fixtures()
    wanted = {fixture} if fixture != "all" else {"campus", "community", "negative"}
    counts = {"cases": 0, "blocked_sources": 0, "audits": 0}

    for case_def in fixtures["cases"]:
        slug = case_def["case"]["slug"]
        if ("campus" not in wanted and slug.startswith("campus")) or ("community" not in wanted and slug.startswith("community")):
            continue
        _seed_case(session, case_def)
        counts["cases"] += 1

    session.flush()

    if "negative" in wanted:
        for source in fixtures["blocked_sources"]:
            _upsert_source(session, source)
            session.flush()
            _write_seed_audit(
                session,
                case_id=source["case_id"],
                actor="system",
                action="source_rejected",
                object_type="SourceRecord",
                object_id=source["id"],
                reason="source_not_allowed_for_p0",
                payload={"access_mode": source["access_mode"]},
            )
            counts["blocked_sources"] += 1
            counts["audits"] += 1

    session.commit()
    return counts


def update_evidence_status(session: Session, evidence_id: str, status: str, actor: str, reason: str | None) -> Evidence:
    evidence = session.get(Evidence, evidence_id) or _not_found("evidence", evidence_id)
    old = evidence.status
    evidence.status = status
    write_audit(
        session,
        case_id=evidence.case_id,
        actor=actor,
        action="evidence_status_updated",
        object_type="Evidence",
        object_id=evidence.id,
        reason=reason,
        payload={"from": old, "to": status},
    )
    session.commit()
    session.refresh(evidence)
    return evidence


def update_factor_status(session: Session, factor_id: str, status: str, actor: str, reason: str | None) -> RiskFactor:
    factor = session.get(RiskFactor, factor_id) or _not_found("risk_factor", factor_id)
    old = factor.status
    factor.status = status
    write_audit(
        session,
        case_id=factor.case_id,
        actor=actor,
        action="risk_factor_status_updated",
        object_type="RiskFactor",
        object_id=factor.id,
        reason=reason,
        payload={"from": old, "to": status},
    )
    session.commit()
    session.refresh(factor)
    return factor


def confirm_mainline(session: Session, mainline_id: str, actor: str = "analyst") -> Mainline:
    mainline = session.get(Mainline, mainline_id) or _not_found("mainline", mainline_id)
    old = mainline.status
    mainline.status = "confirmed"
    world_state = session.scalars(select(WorldState).where(WorldState.case_id == mainline.case_id)).first()
    if world_state:
        world_state.status = "world_state_ready"
    write_audit(
        session,
        case_id=mainline.case_id,
        actor=actor,
        action="mainline_confirmed",
        object_type="Mainline",
        object_id=mainline.id,
        payload={"from": old, "to": mainline.status},
    )
    _record_workflow(session, mainline.case_id, "BuildMainlineWorkflow", f"build-{mainline.id}", "completed")
    session.commit()
    session.refresh(mainline)
    return mainline


def run_council(session: Session, node_id: str, actor: str = "analyst") -> CouncilSession:
    node = session.get(WorldlineNode, node_id) or _not_found("worldline_node", node_id)
    case = get_case(session, node.case_id)
    evidence_refs = [item.id for item in _all(session, Evidence, node.case_id)[:2]]
    agents = _agent_outputs(case, node, evidence_refs)
    session_id = "COUNCIL-001" if node.case_id == "CASE-CAMPUS-001" else f"COUNCIL-{node.case_id.replace('CASE-', '')}"
    council = CouncilSession(
        id=session_id,
        case_id=node.case_id,
        node_id=node.id,
        hypothesis=node.payload.get("hypothesis", "What changes if the response remains vague?"),
        status="ready_to_apply",
        payload={
            "agents": [agent.model_dump() for agent in agents],
            "summary": _council_summary(case.scenario_type),
            "branch_changes": [{"branch": node.branch, "from": max(0, node.probability - 8), "to": node.probability}],
            "schema_version": "p0.agent_council.v1",
        },
    )
    session.merge(council)
    write_audit(
        session,
        case_id=node.case_id,
        actor=actor,
        action="council_generated",
        object_type="CouncilSession",
        object_id=council.id,
        payload={"node_id": node.id},
    )
    _record_workflow(session, node.case_id, "RunCouncilWorkflow", f"council-{node.id}", "completed")
    session.commit()
    return session.get(CouncilSession, council.id) or council


def apply_council(session: Session, session_id: str, actor: str = "analyst") -> CouncilSession:
    council = session.get(CouncilSession, session_id) or _not_found("council_session", session_id)
    old = council.status
    council.status = "applied"
    write_audit(
        session,
        case_id=council.case_id,
        actor=actor,
        action="council_applied",
        object_type="CouncilSession",
        object_id=council.id,
        payload={"from": old, "to": council.status},
    )
    session.commit()
    session.refresh(council)
    return council


def confirm_report(session: Session, report_id: str, actor: str, reason: str) -> Report:
    report = session.get(Report, report_id) or _not_found("report", report_id)
    report.human_confirmed = True
    report.status = "confirmed"
    payload = dict(report.payload)
    payload["formal_conclusion"] = payload.get("draft_summary", "")
    report.payload = payload
    write_audit(
        session,
        case_id=report.case_id,
        actor=actor,
        action="report_confirmed",
        object_type="Report",
        object_id=report.id,
        reason=reason,
    )
    session.commit()
    session.refresh(report)
    return report


def update_task_status(session: Session, task_id: str, status: str, actor: str, reason: str | None) -> Task:
    task = session.get(Task, task_id) or _not_found("task", task_id)
    old = task.status
    task.status = status
    write_audit(
        session,
        case_id=task.case_id,
        actor=actor,
        action="task_status_updated",
        object_type="Task",
        object_id=task.id,
        reason=reason,
        payload={"from": old, "to": status},
    )
    session.commit()
    session.refresh(task)
    return task


def record_workflow_execution(
    session: Session,
    *,
    case_id: str,
    workflow_name: str,
    workflow_id: str,
    status: str,
    payload: dict | None = None,
) -> WorkflowRun:
    run = WorkflowRun(
        id=f"WFR-{workflow_id}"[:100],
        case_id=case_id,
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        status=status,
        payload=payload or {},
    )
    session.merge(run)
    write_audit(
        session,
        case_id=case_id,
        actor="system",
        action="workflow_run_recorded",
        object_type="WorkflowRun",
        object_id=run.id,
        payload={"workflow_name": workflow_name, "workflow_id": workflow_id, "status": status},
    )
    session.commit()
    return session.get(WorkflowRun, run.id) or run


def map_layers(session: Session, case_id: str) -> dict:
    signals = _all(session, Signal, case_id)
    features = []
    for signal in signals:
        coordinates = signal.payload.get("coordinates", [120.1551, 30.2741])
        features.append(
            {
                "type": "Feature",
                "id": signal.id,
                "geometry": {"type": "Point", "coordinates": coordinates},
                "properties": {
                    "featureId": signal.id,
                    "regionId": signal.region_id,
                    "featureType": "event-point",
                    "title": signal.title,
                    "summary": signal.summary,
                    "mainlineId": signal.mainline_id,
                    "riskScore": signal.scores.get("mainlineRisk", 0),
                    "confidence": signal.scores.get("factCredibility", 0),
                },
            }
        )
    return {
        "caseId": case_id,
        "eventPoints": {"type": "FeatureCollection", "features": features},
        "riskAreas": {"type": "FeatureCollection", "features": features},
        "config": {"center": features[0]["geometry"]["coordinates"] if features else [120.1551, 30.2741], "zoom": 12.4},
    }


def get_page_view(session: Session, case_id: str, page: str) -> dict:
    bundle = get_case_bundle(session, case_id)
    mainlines = _all(session, Mainline, case_id)
    return build_page_view(bundle, page, mainlines)


def update_signal(session: Session, signal_id: str, status: str | None, priority: str | None, actor: str, reason: str | None) -> Signal:
    signal = session.get(Signal, signal_id) or _not_found("signal", signal_id)
    old = {"status": signal.status, "priority": signal.priority}
    if status is not None:
        signal.status = status
    if priority is not None:
        signal.priority = priority
    write_audit(
        session,
        case_id=signal.case_id,
        actor=actor,
        action="signal_updated",
        object_type="Signal",
        object_id=signal.id,
        reason=reason,
        payload={"from": old, "to": {"status": signal.status, "priority": signal.priority}},
    )
    session.commit()
    session.refresh(signal)
    return signal


def update_mainline_draft_signal(session: Session, mainline_id: str, signal_id: str, action: str, actor: str, reason: str | None) -> Mainline:
    mainline = session.get(Mainline, mainline_id) or _not_found("mainline", mainline_id)
    signal = session.get(Signal, signal_id) or _not_found("signal", signal_id)
    if signal.case_id != mainline.case_id:
        _not_found("signal_for_mainline", signal_id)
    payload = dict(mainline.payload)
    draft_signals = list(payload.get("draft_signals", payload.get("signals", [])))
    if action == "add" and signal_id not in draft_signals:
        draft_signals.append(signal_id)
        signal.mainline_id = mainline.id
        signal.status = "selected_for_mainline"
    if action == "remove":
        draft_signals = [item for item in draft_signals if item != signal_id]
    payload["draft_signals"] = draft_signals
    mainline.payload = payload
    write_audit(
        session,
        case_id=mainline.case_id,
        actor=actor,
        action="mainline_draft_signal_updated",
        object_type="Mainline",
        object_id=mainline.id,
        reason=reason,
        payload={"signal_id": signal_id, "action": action, "draft_signals": draft_signals},
    )
    session.commit()
    session.refresh(mainline)
    return mainline


def similar_signals(session: Session, signal_id: str, limit: int = 6) -> list[Signal]:
    signal = session.get(Signal, signal_id) or _not_found("signal", signal_id)
    signal_tags = set(signal.payload.get("tags", []))
    candidates = [item for item in _all(session, Signal, signal.case_id) if item.id != signal.id and item.status != "excluded"]
    candidates.sort(key=lambda item: (len(signal_tags.intersection(item.payload.get("tags", []))), item.scores.get("mainlineRisk", 0)), reverse=True)
    return candidates[:limit]


def create_mainline(session: Session, case_id: str, title: str, confidence: float, status: str, payload: dict, actor: str) -> Mainline:
    get_case(session, case_id)
    count = len(_all(session, Mainline, case_id)) + 1
    mainline = Mainline(
        id=f"ML-{case_id.replace('CASE-', '')}-{count:03d}"[:100],
        case_id=case_id,
        title=title,
        confidence=confidence,
        status=status,
        payload=payload,
    )
    session.merge(mainline)
    write_audit(
        session,
        case_id=case_id,
        actor=actor,
        action="mainline_created",
        object_type="Mainline",
        object_id=mainline.id,
        payload={"title": title, "status": status},
    )
    session.commit()
    return session.get(Mainline, mainline.id) or mainline


def update_mainline(session: Session, mainline_id: str, title: str | None, confidence: float | None, status: str | None, payload: dict | None, actor: str, reason: str | None) -> Mainline:
    mainline = session.get(Mainline, mainline_id) or _not_found("mainline", mainline_id)
    old = {"title": mainline.title, "confidence": mainline.confidence, "status": mainline.status, "payload": mainline.payload}
    if title is not None:
        mainline.title = title
    if confidence is not None:
        mainline.confidence = confidence
    if status is not None:
        mainline.status = status
    if payload is not None:
        merged = dict(mainline.payload)
        merged.update(payload)
        mainline.payload = merged
    write_audit(
        session,
        case_id=mainline.case_id,
        actor=actor,
        action="mainline_updated",
        object_type="Mainline",
        object_id=mainline.id,
        reason=reason,
        payload={"from": old, "to": {"title": mainline.title, "confidence": mainline.confidence, "status": mainline.status, "payload": mainline.payload}},
    )
    session.commit()
    session.refresh(mainline)
    return mainline


def run_pressure_test(session: Session, session_id: str, hypothesis: str, actor: str) -> CouncilSession:
    council = session.get(CouncilSession, session_id) or _not_found("council_session", session_id)
    payload = dict(council.payload)
    tests = list(payload.get("pressure_tests", []))
    result = {
        "id": f"PT-{len(tests) + 1:03d}",
        "hypothesis": hypothesis,
        "result": "如果补齐证据清单和核验窗口，缓和分支概率上调；如果只发布模糊回应，二次升温风险保留。",
        "branch_delta": {"A": 0.08, "C": -0.06},
    }
    tests.append(result)
    payload["pressure_tests"] = tests
    council.payload = payload
    write_audit(
        session,
        case_id=council.case_id,
        actor=actor,
        action="pressure_test_run",
        object_type="CouncilSession",
        object_id=council.id,
        payload=result,
    )
    session.commit()
    session.refresh(council)
    return council


def create_task(session: Session, case_id: str, title: str, owner: str, due_label: str, status: str, payload: dict, actor: str) -> Task:
    get_case(session, case_id)
    task = Task(
        id=f"TASK-{case_id.replace('CASE-', '')}-{uuid4().hex[:8]}"[:100],
        case_id=case_id,
        title=title,
        owner=owner,
        due_label=due_label,
        status=status,
        payload=payload,
    )
    session.add(task)
    write_audit(
        session,
        case_id=case_id,
        actor=actor,
        action="task_created",
        object_type="Task",
        object_id=task.id,
        payload={"title": title, "owner": owner, "status": status},
    )
    session.commit()
    session.refresh(task)
    return task


def run_case_memory_action(session: Session, case_id: str, action: str, actor: str, payload: dict) -> dict:
    case = get_case(session, case_id)
    case_payload = dict(case.payload)
    memory = dict(case_payload.get("memory", {}))
    memory["last_action"] = action
    memory["status"] = {"save_draft": "draft_saved", "submit_review": "review_pending", "confirm_ingest": "ingested"}[action]
    memory["payload"] = payload
    case_payload["memory"] = memory
    case.payload = case_payload
    write_audit(session, case_id=case.id, actor=actor, action=f"case_memory_{action}", object_type="CaseMemory", object_id=case.id, payload=memory)
    session.commit()
    return {"status": memory["status"], "object_type": "CaseMemory", "object_id": case.id, "payload": memory}


def apply_library_item(session: Session, case_id: str, object_type: str, object_id: str, actor: str, payload: dict) -> dict:
    case = get_case(session, case_id)
    case_payload = dict(case.payload)
    applied = list(case_payload.get("library_applications", []))
    applied.append({"object_type": object_type, "object_id": object_id, "payload": payload})
    case_payload["library_applications"] = applied
    case.payload = case_payload
    write_audit(session, case_id=case.id, actor=actor, action="library_item_applied", object_type=object_type, object_id=object_id, payload=payload)
    session.commit()
    return {"status": "applied", "object_type": object_type, "object_id": object_id, "payload": {"applications": applied}}


def run_config_version_action(session: Session, version_id: str, case_id: str, action: str, actor: str, payload: dict) -> dict:
    get_case(session, case_id)
    result = {
        "version_id": version_id,
        "action": action,
        "status": {"run_regression": "regression_passed", "submit_approval": "approval_pending", "publish": "published"}[action],
        "payload": payload,
    }
    write_audit(session, case_id=case_id, actor=actor, action=f"config_{action}", object_type="ConfigVersion", object_id=version_id, payload=result)
    session.commit()
    return {"status": result["status"], "object_type": "ConfigVersion", "object_id": version_id, "payload": result}


def _seed_case(session: Session, case_def: dict) -> None:
    case_payload = case_def["case"]
    case = Case(
        id=case_payload["id"],
        slug=case_payload["slug"],
        title=case_payload["title"],
        scenario_type=case_payload["scenario_type"],
        status="active",
        payload=case_payload.get("payload", {}),
    )
    session.merge(case)
    session.flush()

    for source in case_def["sources"]:
        _upsert_source(session, {**source, "case_id": case.id})

    mainline_defs = case_def.get("mainlines") or [case_def["mainline"]]
    mainline = Mainline(case_id=case.id, **mainline_defs[0])
    for mainline_def in mainline_defs:
        session.merge(Mainline(case_id=case.id, **mainline_def))

    for signal_def in case_def["signals"]:
        session.merge(
            Signal(
                id=signal_def["id"],
                case_id=case.id,
                mainline_id=signal_def.get("mainline_id", mainline.id),
                title=signal_def["title"],
                summary=signal_def["summary"],
                priority=signal_def["priority"],
                region_id=signal_def.get("region_id", "default-region"),
                status=signal_def.get("status", "selected_for_mainline"),
                scores=signal_def["scores"],
                payload={
                    **signal_def.get("payload", {}),
                    "tags": signal_def.get("tags", []),
                    "coordinates": signal_def.get("coordinates", _coordinates(case.id, signal_def.get("region_id", "default-region"))),
                },
            )
        )

    session.flush()

    for evidence_def in case_def["evidence"]:
        evidence_id, signal_id, title, excerpt, source, credibility, status, sensitivity = evidence_def
        session.merge(
            Evidence(
                id=evidence_id,
                case_id=case.id,
                signal_id=signal_id,
                title=title,
                excerpt=excerpt,
                masked_excerpt=mask_sensitive_text(excerpt),
                source=source,
                credibility=credibility,
                status=status,
                sensitivity=sensitivity_level(excerpt, sensitivity),
                payload={},
            )
        )

    for factor_id, name, category, confidence, status, evidence_refs in case_def["factors"]:
        session.merge(
            RiskFactor(
                id=factor_id,
                case_id=case.id,
                name=name,
                category=category,
                confidence=confidence,
                status=status,
                payload={"evidence_refs": evidence_refs, "trigger_reason": f"{name} was detected from linked evidence."},
            )
        )

    ws = case_def["world_state"]
    session.merge(
        WorldState(
            id=ws["id"],
            case_id=case.id,
            title=ws["title"],
            status=ws["status"],
            payload={"mainline_id": mainline.id, "inputs": mainline.payload.get("signals", [])},
        )
    )

    for node_def in case_def["nodes"]:
        node_id, title, branch, probability, risk, needs_council = node_def[:6]
        node_payload = node_def[6] if len(node_def) > 6 else {}
        session.merge(
            WorldlineNode(
                id=node_id,
                case_id=case.id,
                title=title,
                branch=branch,
                probability=probability,
                risk=risk,
                status="generated",
                payload={"needsCouncil": needs_council, "support_point_state": mainline.payload.get("support_points", []), **node_payload},
            )
        )

    report_def = case_def["report"]
    session.merge(
        Report(
            id=report_def["id"],
            case_id=case.id,
            title=report_def["title"],
            human_confirmed=False,
            status="draft",
            payload={
                "draft_summary": report_def["draft_summary"],
                "formal_conclusion": "",
                "compliance_note": "High-risk conclusions require human confirmation.",
            },
        )
    )

    for task_id, title, owner, due_label, status in case_def["tasks"]:
        session.merge(Task(id=task_id, case_id=case.id, title=title, owner=owner, due_label=due_label, status=status, payload={"source": "seed"}))

    for workflow_name in ["IngestCaseWorkflow", "BuildMainlineWorkflow", "GenerateWorldlineWorkflow", "GenerateReportWorkflow"]:
        _record_workflow(session, case.id, workflow_name, f"{workflow_name}-{case.id}", "seeded")

    session.flush()
    _write_seed_audit(
        session,
        case_id=case.id,
        actor="system",
        action="case_seeded",
        object_type="Case",
        object_id=case.id,
        payload={"fixture": case.scenario_type},
    )


def _upsert_source(session: Session, source: dict) -> None:
    accepted, reason = source_allowed(source["access_mode"], source["status"])
    session.merge(
        SourceRecord(
            id=source["id"],
            case_id=source["case_id"],
            source_id=source["source_id"],
            source_name=source["source_name"],
            access_mode=source["access_mode"],
            status=source["status"],
            trust=source["trust"],
            accepted=accepted,
            blocked_reason=reason,
            payload=source.get("payload", {}),
        )
    )


def _record_workflow(session: Session, case_id: str, name: str, workflow_id: str, status: str) -> None:
    session.merge(
        WorkflowRun(
            id=f"WFR-{name}-{case_id}",
            case_id=case_id,
            workflow_name=name,
            workflow_id=workflow_id,
            status=status,
            payload={},
        )
    )


def _write_seed_audit(
    session: Session,
    *,
    case_id: str,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    reason: str | None = None,
    payload: dict | None = None,
) -> AuditLog:
    audit = AuditLog(
        id=f"AUD-SEED-{action}-{object_id}"[:120],
        case_id=case_id,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        payload=payload or {},
    )
    session.merge(audit)
    return audit


def _agent_outputs(case: Case, node: WorldlineNode, evidence_refs: list[str]) -> list[CouncilAgentOutput]:
    if case.scenario_type == "campus_high_intensity":
        roles = [
            ("家属与亲属共同体", "要求解释死亡原因、查看证据并确认学校责任边界"),
            ("校方", "控制现场并等待调查，但承受知情不作为质疑"),
            ("教育主管与属地部门", "建立联合调查、现场沟通和未成年人保护机制"),
        ]
    else:
        roles = [
            ("居民", "要求明确恢复时间和责任窗口"),
            ("物业或服务单位", "需要统一口径并降低现场咨询压力"),
            ("街道/属地", "协调公共服务单位给出可兑现时间表"),
        ]
    outputs = []
    for role, stance in roles:
        blocked_claims = []
        if role in {"公众与媒体/KOL", "居民"}:
            blocked_claims.append("unsupported claim: assigning individual blame without confirmed evidence")
        outputs.append(
            CouncilAgentOutput(
                role=role,
                stance=stance,
                reaction=f"{role} treats node {node.title} as requiring clearer evidence and response rhythm.",
                support_point_delta={"trust": -0.12 if node.branch == "C" else 0.08, "evidence_completeness": -0.05 if node.branch == "C" else 0.1},
                branch_probability_delta={node.branch: 0.08 if node.branch == "C" else -0.06},
                evidence_refs=evidence_refs,
                uncertainty="Agent Council is a pressure test and not a factual finding.",
                blocked_claims=blocked_claims,
            )
        )
    return outputs


def _council_summary(scenario_type: str) -> str:
    if scenario_type == "campus_high_intensity":
        return "Vague response increases trust vacuum, privacy risk, and offline gathering pressure."
    return "Inconsistent repair and responsibility explanations increase collective consultation risk."


def _all(session: Session, model, case_id: str):
    return list(session.scalars(select(model).where(model.case_id == case_id).order_by(model.id)))


def _all_audit(session: Session, case_id: str) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.created_at, AuditLog.id)))


def _not_found(kind: str, object_id: str):
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"{kind} {object_id} not found")


def _coordinates(case_id: str, region_id: str) -> list[float]:
    campus = {
        "campus-core": [120.1348, 30.2825],
        "online-spread": [120.1551, 30.2741],
        "authority-response": [120.1686, 30.2767],
    }
    community = {"community-east": [120.2142, 30.2994]}
    return (campus if case_id == "CASE-CAMPUS-001" else community).get(region_id, [120.1551, 30.2741])


def _agent_outputs(case: Case, node: WorldlineNode, evidence_refs: list[str]) -> list[CouncilAgentOutput]:
    if case.scenario_type == "campus_high_intensity":
        roles = [
            ("family-community", "Needs cause explanation, evidence access, and clear school responsibility boundary."),
            ("school", "Needs site stabilization while addressing perceived knowledge gaps."),
            ("education-and-local-authority", "Needs joint investigation, field communication, and minor-protection mechanism."),
            ("local-street-office", "Needs field order stabilization and a documented family communication channel."),
            ("platform-safety", "Needs privacy leakage suppression and rumor handling without amplifying personal data."),
            ("local-media", "Needs a verifiable timeline and avoids naming minors or assigning unsupported blame."),
            ("public-observers", "Needs transparent evidence preservation and next update cadence."),
        ]
    else:
        roles = [
            ("residents", "Need clear recovery time and responsibility contact window."),
            ("property-or-service-provider", "Needs a unified response channel and reduced field consultation pressure."),
            ("street-office", "Coordinates public service providers to give a deliverable timeline."),
            ("utility-provider", "Needs repair progress and technical cause explanation."),
            ("hotline-operator", "Needs one response script and escalation policy."),
            ("local-media", "Needs verified service recovery milestones."),
            ("community-grid", "Needs field feedback and resident care routing."),
        ]

    outputs = []
    for role, stance in roles:
        blocked_claims = []
        if role in {"public-media", "residents", "public-observers", "local-media"}:
            blocked_claims.append("unsupported claim: assigning individual blame without confirmed evidence")
        outputs.append(
            CouncilAgentOutput(
                role=role,
                stance=stance,
                reaction=f"{role} treats node {node.title} as requiring clearer evidence and response rhythm.",
                support_point_delta={"trust": -0.12 if node.branch == "C" else 0.08, "evidence_completeness": -0.05 if node.branch == "C" else 0.1},
                branch_probability_delta={node.branch: 0.08 if node.branch == "C" else -0.06},
                evidence_refs=evidence_refs,
                uncertainty="Agent Council is a pressure test and not a factual finding.",
                blocked_claims=blocked_claims,
            )
        )
    return outputs
