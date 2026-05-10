from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .audit import write_audit
from .foundation import DEFAULT_TENANT_ID, api_error

ALGORITHM_VERSION = "s5-mainline-world-state-v1"
DEFAULT_CASE_ID = "CASE-CAMPUS-001"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_mainline_draft(session: Session, request: schemas.MainlineCreate, actor: models.User, trace_id: str) -> dict:
    topic = _topic_or_404(session, request.topic_id)
    package = _signal_package_or_404(session, request.signal_package_id)
    if package.topic_id != topic.id:
        raise api_error(409, "SIGNAL_PACKAGE_TOPIC_MISMATCH", "Signal package does not belong to the requested topic.")
    signals = _signals_for_package(session, package.id)
    if not signals:
        raise api_error(422, "SIGNAL_PACKAGE_EMPTY", "Signal package has no signals.")
    case = _case_for_signals_or_topic(session, signals, topic)
    evidence_rows = _confirmed_evidence_for_signals(session, [signal.id for signal in signals])
    evidence_refs = [_evidence_ref(row) for row in evidence_rows]
    signal_refs = [{"object_type": "signal", "object_id": signal.id, "object_version": signal.payload.get("algorithm_version", "unknown")} for signal in signals]
    confidence = _mainline_confidence(signals, evidence_rows)
    payload = jsonable_encoder(
        {
            **request.payload,
            "topic_id": topic.id,
            "signal_package_id": package.id,
            "signal_ids": [signal.id for signal in signals],
            "input_refs": signal_refs,
            "evidence_refs": evidence_refs,
            "version_number": 1,
            "version": "v1",
            "algorithm_version": ALGORITHM_VERSION,
            "rule_version": "s5-mainline-draft-v1",
            "synthetic": _has_synthetic_inputs(signals, evidence_rows),
            "probability": round(min(0.96, 0.42 + confidence * 0.45 + len(evidence_refs) * 0.03), 4),
            "confidence_inputs": {
                "signal_count": len(signals),
                "confirmed_evidence_count": len(evidence_rows),
                "average_signal_risk": _average([float(signal.scores.get("mainlineRisk", 0)) for signal in signals]),
            },
            "support_points": _support_points(signals, evidence_rows),
            "evidence_gaps": _evidence_gaps(signals, evidence_rows),
            "quality_gate": {"status": "not_run", "passed": False, "checked_at": None, "blockers": []},
            "blocked_claims": [
                {
                    "claim": "Mainline draft is not a public factual conclusion until quality check and human confirmation pass.",
                    "reason": "S5 draft material must remain reviewable.",
                }
            ],
        }
    )
    mainline = models.Mainline(
        id=_id("ML"),
        case_id=case.id,
        title=request.title,
        confidence=confidence,
        status="draft",
        payload=payload,
    )
    session.add(mainline)
    session.flush()
    _create_default_nodes(session, actor, mainline, signals, evidence_refs)
    _save_version(session, actor, mainline, {"created_from": "signal_package", "signal_package_id": package.id})
    _workflow_run(session, actor, case.id, "mainline_draft_generation", f"mainline-draft:{mainline.id}", trace_id, {"mainline_id": mainline.id, "topic_id": topic.id, "signal_package_id": package.id, "evidence_refs": evidence_refs})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=case.id,
        actor=actor.username,
        actor_id=actor.id,
        action="mainline_draft.create",
        object_type="mainline",
        object_id=mainline.id,
        object_version=payload["version"],
        reason=request.reason,
        after=serialize_mainline(mainline),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_mainline(mainline)


def get_mainline(session: Session, mainline_id: str) -> dict:
    return serialize_mainline(_mainline_or_404(session, mainline_id))


def list_mainlines(session: Session, case_id: str | None = None, topic_id: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.Mainline).order_by(models.Mainline.updated_at.desc())
    if case_id:
        statement = statement.where(models.Mainline.case_id == case_id)
    if status:
        statement = statement.where(models.Mainline.status == status)
    rows = list(session.execute(statement).scalars())
    if topic_id:
        rows = [row for row in rows if row.payload.get("topic_id") == topic_id]
    return [serialize_mainline(row) for row in rows]


def builder_view(session: Session, mainline_id: str, actor: models.User) -> dict:
    mainline = _mainline_or_404(session, mainline_id)
    nodes = _nodes_for_mainline(session, mainline.id)
    evidence_rows = _evidence_for_mainline(session, mainline)
    graph_nodes = _graph_nodes_for_mainline(session, mainline.id)
    stakeholders = _stakeholders_for_mainline(session, mainline.id)
    primary = {
        "mainline": serialize_mainline(mainline),
        "nodes": [serialize_mainline_node(node) for node in nodes],
        "evidence": [_serialize_evidence(row) for row in evidence_rows],
        "versions": [serialize_mainline_version(row) for row in _versions_for_mainline(session, mainline.id)],
        "quality_gate": mainline.payload.get("quality_gate", {"status": "not_run", "passed": False, "blockers": []}),
        "case_graph_nodes": [serialize_case_graph_node(row) for row in graph_nodes],
        "stakeholders": [serialize_stakeholder(row) for row in stakeholders],
        "legacy_page_view": _legacy_page_view(mainline, nodes, evidence_rows, stakeholders),
    }
    return {
        "page_state": "ready" if nodes else "empty",
        "permissions": {"mainline:read": True, "mainline:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "mainlines/mainline_nodes/evidence/world_states/stakeholders"},
        "degraded_sources": [] if evidence_rows else [{"code": "EVIDENCE_GAP", "message": "Mainline has no confirmed evidence refs."}],
        "audit_context": {"object_type": "mainline", "object_id": mainline.id, "object_version": mainline.payload.get("version"), "actor_id": actor.id},
        "primary_data": primary,
        "actions": [
            {"id": "quality-check", "label": "Run quality check", "method": "POST", "href": f"/api/v1/mainlines/{mainline.id}/quality-check", "enabled": mainline.status in {"draft", "quality_failed"}},
            {"id": "confirm-mainline", "label": "Confirm mainline", "method": "POST", "href": f"/api/v1/mainlines/{mainline.id}/confirm", "enabled": mainline.payload.get("quality_gate", {}).get("passed") is True},
            {"id": "create-world-state", "label": "Generate World State", "method": "POST", "href": "/api/v1/world-states", "enabled": mainline.status == "confirmed"},
        ],
    }


def update_mainline_node(session: Session, node_id: str, request: schemas.MainlineNodePatch, actor: models.User, trace_id: str) -> dict:
    node = _mainline_node_or_404(session, node_id)
    if node.version != request.expected_version:
        raise api_error(
            409,
            "MAINLINE_NODE_VERSION_CONFLICT",
            "Mainline node version conflict.",
            {"expected_version": request.expected_version, "current_version": node.version},
        )
    mainline = _mainline_or_404(session, node.mainline_id)
    before = serialize_mainline_node(node)
    if request.title is not None:
        node.title = request.title
    if request.body is not None:
        node.body = request.body
    if request.status is not None:
        node.status = request.status
    node.version += 1
    node.payload = jsonable_encoder({**node.payload, **request.payload, "last_edit_reason": request.reason})
    _bump_mainline_version(session, actor, mainline, {"node_id": node.id, "action": "node_update", "before": before, "after": serialize_mainline_node(node)})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="mainline_node.update",
        object_type="mainline_node",
        object_id=node.id,
        object_version=str(node.version),
        reason=request.reason,
        before=before,
        after=serialize_mainline_node(node),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_mainline_node(node)


def update_mainline_signal(session: Session, mainline_id: str, request: schemas.MainlineSignalWrite, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, mainline_id)
    signal = session.get(models.Signal, request.signal_id)
    if signal is None or signal.case_id != mainline.case_id:
        raise api_error(404, "SIGNAL_NOT_FOUND", "Signal not found for mainline case.")
    payload = dict(mainline.payload)
    signal_ids = list(payload.get("signal_ids", []))
    before = {"signal_ids": signal_ids, "version": payload.get("version")}
    if request.action == "add" and signal.id not in signal_ids:
        signal_ids.append(signal.id)
        signal.mainline_id = mainline.id
        signal.status = "selected_for_mainline"
    if request.action == "remove":
        signal_ids = [item for item in signal_ids if item != signal.id]
        if signal.mainline_id == mainline.id:
            signal.mainline_id = None
            signal.status = "needs_review"
    payload["signal_ids"] = signal_ids
    payload["input_refs"] = [{"object_type": "signal", "object_id": signal_id} for signal_id in signal_ids]
    mainline.payload = jsonable_encoder(payload)
    _bump_mainline_version(session, actor, mainline, {"action": f"signal_{request.action}", "signal_id": signal.id, "before": before, "after": {"signal_ids": signal_ids}})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="mainline_signal.update",
        object_type="mainline",
        object_id=mainline.id,
        object_version=mainline.payload.get("version"),
        reason=request.reason,
        diff={"signal_id": signal.id, "action": request.action},
        trace_id=trace_id,
    )
    session.commit()
    return serialize_mainline(mainline)


def run_quality_check(session: Session, mainline_id: str, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, mainline_id)
    evidence_refs = list(mainline.payload.get("evidence_refs", []))
    nodes = _nodes_for_mainline(session, mainline.id)
    blockers = []
    if not evidence_refs:
        blockers.append("evidence_refs_missing")
    if not nodes:
        blockers.append("mainline_nodes_missing")
    if any(not node.evidence_refs for node in nodes):
        blockers.append("node_evidence_refs_missing")
    if not mainline.payload.get("signal_ids"):
        blockers.append("signal_inputs_missing")
    passed = not blockers
    gate = {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "checked_at": utcnow().isoformat(),
        "blockers": blockers,
        "algorithm_version": ALGORITHM_VERSION,
        "evidence_ref_count": len(evidence_refs),
        "node_count": len(nodes),
    }
    payload = dict(mainline.payload)
    payload["quality_gate"] = gate
    mainline.payload = jsonable_encoder(payload)
    mainline.status = "pending_confirmation" if passed else "quality_failed"
    _bump_mainline_version(session, actor, mainline, {"action": "quality_check", "quality_gate": gate})
    _workflow_run(session, actor, mainline.case_id, "mainline_quality_check", f"mainline-quality:{mainline.id}:{mainline.payload.get('version')}", trace_id, {"mainline_id": mainline.id, "passed": passed, "blockers": blockers})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="mainline_quality_check.completed",
        object_type="mainline",
        object_id=mainline.id,
        object_version=mainline.payload.get("version"),
        after={"quality_gate": gate, "status": mainline.status},
        trace_id=trace_id,
    )
    session.commit()
    return {"passed": passed, "blockers": blockers, "mainline": serialize_mainline(mainline)}


def confirm_mainline(session: Session, mainline_id: str, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, mainline_id)
    if mainline.payload.get("quality_gate", {}).get("passed") is not True:
        raise api_error(409, "MAINLINE_QUALITY_NOT_PASSED", "Mainline quality check must pass before confirmation.")
    before = serialize_mainline(mainline)
    mainline.status = "confirmed"
    for evidence_ref in mainline.payload.get("evidence_refs", []):
        evidence = session.get(models.Evidence, evidence_ref.get("object_id"))
        if evidence is not None and evidence.status == "confirmed_fact":
            evidence.status = "used_in_mainline"
    _bump_mainline_version(session, actor, mainline, {"action": "confirm", "before_status": before["status"], "after_status": "confirmed"})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="mainline.confirm",
        object_type="mainline",
        object_id=mainline.id,
        object_version=mainline.payload.get("version"),
        before=before,
        after=serialize_mainline(mainline),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_mainline(mainline)


def create_world_state(session: Session, request: schemas.WorldStateCreate, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, request.mainline_id)
    if mainline.status not in {"confirmed", "world_state_generated"}:
        raise api_error(409, "MAINLINE_NOT_CONFIRMED", "World State requires confirmed mainline.")
    nodes = _nodes_for_mainline(session, mainline.id)
    evidence_refs = list(mainline.payload.get("evidence_refs", []))
    world_state = models.WorldState(
        id=_id("WS"),
        case_id=mainline.case_id,
        title=f"{mainline.title} World State",
        status="world_state_ready",
        payload=jsonable_encoder(
            {
                **request.payload,
                "mainline_id": mainline.id,
                "mainline_version": mainline.payload.get("version"),
                "topic_id": mainline.payload.get("topic_id"),
                "input_refs": [{"object_type": "mainline", "object_id": mainline.id, "object_version": mainline.payload.get("version")}],
                "evidence_refs": evidence_refs,
                "state_payload": {
                    "mainline_title": mainline.title,
                    "support_points": mainline.payload.get("support_points", []),
                    "nodes": [serialize_mainline_node(node) for node in nodes],
                    "uncertainties": mainline.payload.get("evidence_gaps", []),
                },
                "version": "v1",
                "algorithm_version": ALGORITHM_VERSION,
                "synthetic": mainline.payload.get("synthetic", False),
                "blocked_claims": mainline.payload.get("blocked_claims", []),
            }
        ),
    )
    session.add(world_state)
    mainline.status = "world_state_generated"
    payload = dict(mainline.payload)
    payload["world_state_id"] = world_state.id
    mainline.payload = jsonable_encoder(payload)
    _workflow_run(session, actor, mainline.case_id, "world_state_generation", f"world-state:{world_state.id}", trace_id, {"mainline_id": mainline.id, "world_state_id": world_state.id, "evidence_refs": evidence_refs})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="world_state.create",
        object_type="world_state",
        object_id=world_state.id,
        object_version="v1",
        reason=request.reason,
        after=serialize_world_state(world_state),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_world_state(world_state)


def get_world_state(session: Session, world_state_id: str) -> dict:
    return serialize_world_state(_world_state_or_404(session, world_state_id))


def create_case_graph_run(session: Session, request: schemas.CaseGraphRunCreate, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, request.mainline_id)
    world_state = _world_state_or_404(session, request.world_state_id) if request.world_state_id else None
    if world_state is not None and world_state.case_id != mainline.case_id:
        raise api_error(409, "WORLD_STATE_MAINLINE_MISMATCH", "World State does not belong to mainline case.")
    run = _workflow_run(session, actor, mainline.case_id, "case_graph_generation", f"case-graph:{request.rule_version}:{mainline.id}", trace_id, {"mainline_id": mainline.id, "world_state_id": request.world_state_id, "rule_version": request.rule_version, "output_count": 0})
    nodes = _upsert_case_graph_nodes(session, actor, mainline, world_state, request.rule_version)
    run.status = "completed"
    run.payload = jsonable_encoder(run.payload | {"output_count": len(nodes), "case_graph_node_ids": [node.id for node in nodes]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="case_graph_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        after={"nodes": [serialize_case_graph_node(node) for node in nodes]},
        trace_id=trace_id,
    )
    session.commit()
    return {"run": serialize_workflow_run(run), "nodes": [serialize_case_graph_node(node) for node in nodes]}


def create_stakeholder_run(session: Session, request: schemas.StakeholderRunCreate, actor: models.User, trace_id: str) -> dict:
    mainline = _mainline_or_404(session, request.mainline_id)
    world_state = _world_state_or_404(session, request.world_state_id) if request.world_state_id else None
    graph_nodes = _graph_nodes_for_mainline(session, mainline.id)
    if not graph_nodes:
        graph_nodes = _upsert_case_graph_nodes(session, actor, mainline, world_state, request.rule_version)
    run = _workflow_run(session, actor, mainline.case_id, "stakeholder_identification", f"stakeholder:{request.rule_version}:{mainline.id}", trace_id, {"mainline_id": mainline.id, "world_state_id": request.world_state_id, "rule_version": request.rule_version, "output_count": 0})
    stakeholders = _upsert_stakeholders(session, actor, mainline, graph_nodes, request.rule_version)
    run.status = "completed"
    run.payload = jsonable_encoder(run.payload | {"output_count": len(stakeholders), "stakeholder_ids": [row.id for row in stakeholders]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=mainline.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="stakeholder_run.completed",
        object_type="workflow_run",
        object_id=run.id,
        after={"stakeholders": [serialize_stakeholder(row) for row in stakeholders]},
        trace_id=trace_id,
    )
    session.commit()
    return {"run": serialize_workflow_run(run), "stakeholders": [serialize_stakeholder(row) for row in stakeholders]}


def list_stakeholders(session: Session, topic_id: str | None = None, mainline_id: str | None = None, status: str | None = None) -> list[dict]:
    statement = select(models.Stakeholder).order_by(models.Stakeholder.updated_at.desc())
    if topic_id:
        statement = statement.where(models.Stakeholder.topic_id == topic_id)
    if mainline_id:
        statement = statement.where(models.Stakeholder.mainline_id == mainline_id)
    if status:
        statement = statement.where(models.Stakeholder.status == status)
    return [serialize_stakeholder(row) for row in session.execute(statement).scalars()]


def review_stakeholder(session: Session, stakeholder_id: str, request: schemas.StakeholderReviewPatch, actor: models.User, trace_id: str) -> dict:
    stakeholder = _stakeholder_or_404(session, stakeholder_id)
    before = serialize_stakeholder(stakeholder)
    stakeholder.status = "reviewed" if request.decision in {"pass", "waive"} else "rejected"
    stakeholder.reviewer_id = actor.id
    stakeholder.payload = jsonable_encoder({**stakeholder.payload, **request.payload, "review_decision": request.decision, "review_reason": request.reason, "reviewed_at": utcnow().isoformat()})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=stakeholder.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="stakeholder.review",
        object_type="stakeholder",
        object_id=stakeholder.id,
        reason=request.reason,
        before=before,
        after=serialize_stakeholder(stakeholder),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_stakeholder(stakeholder)


def serialize_mainline(mainline: models.Mainline) -> dict:
    return {
        "id": mainline.id,
        "case_id": mainline.case_id,
        "topic_id": mainline.payload.get("topic_id"),
        "title": mainline.title,
        "confidence": mainline.confidence,
        "status": mainline.status,
        "version": mainline.payload.get("version", "v1"),
        "evidence_gap_count": len(mainline.payload.get("evidence_gaps", [])),
        "payload": mainline.payload,
        "created_at": mainline.created_at,
        "updated_at": mainline.updated_at,
    }


def serialize_mainline_node(node: models.MainlineNode) -> dict:
    return {
        "id": node.id,
        "mainline_id": node.mainline_id,
        "node_type": node.node_type,
        "title": node.title,
        "body": node.body,
        "position": node.position,
        "version": node.version,
        "status": node.status,
        "evidence_refs": node.evidence_refs,
        "payload": node.payload,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


def serialize_mainline_version(row: models.MainlineVersion) -> dict:
    return {"id": row.id, "mainline_id": row.mainline_id, "version": row.version, "status": row.status, "diff": row.diff, "payload": row.payload, "created_at": row.created_at}


def serialize_world_state(world_state: models.WorldState) -> dict:
    return {
        "id": world_state.id,
        "case_id": world_state.case_id,
        "mainline_id": world_state.payload.get("mainline_id"),
        "title": world_state.title,
        "status": world_state.status,
        "version": world_state.payload.get("version", "v1"),
        "payload": world_state.payload,
        "created_at": world_state.created_at,
        "updated_at": world_state.updated_at,
    }


def serialize_case_graph_node(node: models.CaseGraphNode) -> dict:
    return {
        "id": node.id,
        "case_id": node.case_id,
        "topic_id": node.topic_id,
        "mainline_id": node.mainline_id,
        "world_state_id": node.world_state_id,
        "node_type": node.node_type,
        "title": node.title,
        "status": node.status,
        "evidence_refs": node.evidence_refs,
        "payload": node.payload,
        "created_at": node.created_at,
        "updated_at": node.updated_at,
    }


def serialize_stakeholder(row: models.Stakeholder) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "topic_id": row.topic_id,
        "mainline_id": row.mainline_id,
        "graph_node_id": row.graph_node_id,
        "name": row.name,
        "role": row.role,
        "stance": row.stance,
        "status": row.status,
        "reviewer_id": row.reviewer_id,
        "evidence_refs": row.evidence_refs,
        "payload": row.payload,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_workflow_run(run: models.WorkflowRun) -> dict:
    return {"id": run.id, "case_id": run.case_id, "workflow_name": run.workflow_name, "workflow_id": run.workflow_id, "status": run.status, "payload": run.payload, "trace_id": run.trace_id, "started_by": run.started_by, "created_at": run.created_at, "updated_at": run.updated_at}


def _mainline_or_404(session: Session, mainline_id: str) -> models.Mainline:
    mainline = session.get(models.Mainline, mainline_id)
    if mainline is None:
        raise api_error(404, "MAINLINE_NOT_FOUND", "Mainline not found.")
    return mainline


def _mainline_node_or_404(session: Session, node_id: str) -> models.MainlineNode:
    node = session.get(models.MainlineNode, node_id)
    if node is None:
        raise api_error(404, "MAINLINE_NODE_NOT_FOUND", "Mainline node not found.")
    return node


def _world_state_or_404(session: Session, world_state_id: str | None) -> models.WorldState:
    world_state = session.get(models.WorldState, world_state_id) if world_state_id else None
    if world_state is None:
        raise api_error(404, "WORLD_STATE_NOT_FOUND", "World State not found.")
    return world_state


def _stakeholder_or_404(session: Session, stakeholder_id: str) -> models.Stakeholder:
    stakeholder = session.get(models.Stakeholder, stakeholder_id)
    if stakeholder is None:
        raise api_error(404, "STAKEHOLDER_NOT_FOUND", "Stakeholder not found.")
    return stakeholder


def _topic_or_404(session: Session, topic_id: str | None) -> models.Topic:
    if not topic_id:
        raise api_error(422, "TOPIC_REQUIRED", "Topic id is required for S5 production mainline generation.")
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise api_error(404, "TOPIC_NOT_FOUND", "Topic not found.")
    return topic


def _signal_package_or_404(session: Session, package_id: str | None) -> models.SignalPackage:
    if not package_id:
        raise api_error(422, "SIGNAL_PACKAGE_REQUIRED", "Signal package id is required for S5 production mainline generation.")
    package = session.get(models.SignalPackage, package_id)
    if package is None:
        raise api_error(404, "SIGNAL_PACKAGE_NOT_FOUND", "Signal package not found.")
    return package


def _signals_for_package(session: Session, package_id: str) -> list[models.Signal]:
    items = list(session.execute(select(models.SignalPackageItem).where(models.SignalPackageItem.signal_package_id == package_id).order_by(models.SignalPackageItem.rank)).scalars())
    if not items:
        return []
    by_id = {signal.id: signal for signal in session.execute(select(models.Signal).where(models.Signal.id.in_([item.signal_id for item in items]))).scalars()}
    return [by_id[item.signal_id] for item in items if item.signal_id in by_id]


def _case_for_signals_or_topic(session: Session, signals: list[models.Signal], topic: models.Topic) -> models.Case:
    case_id = signals[0].case_id if signals else DEFAULT_CASE_ID
    case = session.get(models.Case, case_id)
    if case is None:
        case = models.Case(id=case_id, slug=case_id.lower(), title=topic.title, scenario_type="xian_social_issue", status="active", payload={"created_by": "s5_mainline", "topic_id": topic.id})
        session.add(case)
        session.flush()
    return case


def _confirmed_evidence_for_signals(session: Session, signal_ids: list[str]) -> list[models.Evidence]:
    if not signal_ids:
        return []
    rows = list(session.execute(select(models.Evidence).where(models.Evidence.signal_id.in_(signal_ids))).scalars())
    return [row for row in rows if row.status in {"confirmed_fact", "used_in_mainline"}]


def _evidence_for_mainline(session: Session, mainline: models.Mainline) -> list[models.Evidence]:
    ids = [ref.get("object_id") for ref in mainline.payload.get("evidence_refs", []) if ref.get("object_id")]
    if not ids:
        return []
    rows = list(session.execute(select(models.Evidence).where(models.Evidence.id.in_(ids))).scalars())
    by_id = {row.id: row for row in rows}
    return [by_id[row_id] for row_id in ids if row_id in by_id]


def _evidence_ref(evidence: models.Evidence) -> dict:
    return {"object_type": "evidence", "object_id": evidence.id, "object_version": evidence.payload.get("algorithm_version", "unknown")}


def _has_synthetic_inputs(signals: list[models.Signal], evidence_rows: list[models.Evidence]) -> bool:
    return any(signal.payload.get("is_synthetic") or signal.payload.get("synthetic") for signal in signals) or any(row.payload.get("is_synthetic") or row.payload.get("synthetic") for row in evidence_rows)


def _mainline_confidence(signals: list[models.Signal], evidence_rows: list[models.Evidence]) -> float:
    if not signals:
        return 0.0
    signal_score = _average([float(signal.scores.get("factCredibility", 55)) / 100 for signal in signals])
    evidence_score = _average([_credibility_score(row) for row in evidence_rows]) if evidence_rows else 0.35
    return round(min(0.96, max(0.1, signal_score * 0.45 + evidence_score * 0.45 + min(len(evidence_rows), 3) * 0.03)), 4)


def _credibility_score(evidence: models.Evidence) -> float:
    if evidence.credibility == "high":
        return 0.88
    if evidence.credibility == "medium":
        return 0.66
    return 0.42


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _support_points(signals: list[models.Signal], evidence_rows: list[models.Evidence]) -> list[str]:
    points = [signal.title for signal in signals[:3]]
    if evidence_rows:
        points.append(f"{len(evidence_rows)} confirmed evidence materials support the draft path")
    return points[:4]


def _evidence_gaps(signals: list[models.Signal], evidence_rows: list[models.Evidence]) -> list[str]:
    gaps = []
    if len(evidence_rows) < max(1, min(2, len(signals))):
        gaps.append("Need additional independently confirmed evidence for weaker signal nodes.")
    if any(float(signal.scores.get("factCredibility", 0)) < 55 for signal in signals):
        gaps.append("Low credibility signal requires further review before report use.")
    return gaps


def _create_default_nodes(session: Session, actor: models.User, mainline: models.Mainline, signals: list[models.Signal], evidence_refs: list[dict]) -> None:
    definitions = [
        ("signal_cluster", "Signal package cluster", "Signals grouped from the selected S4A package."),
        ("appeal_emotion", "Appeal and emotion node", "Appeal and sentiment aggregation remains evidence-bounded."),
        ("main_narrative", "Main narrative node", "Narrative is a reviewable draft and cannot be used as a fact without confirmed evidence."),
        ("spread_path", "Spread path node", "Spread path uses source and platform metadata from persisted inputs."),
        ("uncertainty", "Uncertainty and evidence gap node", "Evidence gaps stay visible for report and task generation."),
    ]
    for position, (node_type, title, body) in enumerate(definitions, start=1):
        node_refs = evidence_refs or [{"object_type": "signal", "object_id": signal.id, "object_version": signal.payload.get("algorithm_version", "unknown")} for signal in signals[:2]]
        session.add(
            models.MainlineNode(
                id=_id("MLN"),
                tenant_id=actor.tenant_id,
                mainline_id=mainline.id,
                node_type=node_type,
                title=title,
                body=body,
                position=position,
                version=1,
                status="draft",
                evidence_refs=node_refs,
                payload={"algorithm_version": ALGORITHM_VERSION, "synthetic": mainline.payload.get("synthetic", False)},
            )
        )


def _nodes_for_mainline(session: Session, mainline_id: str) -> list[models.MainlineNode]:
    return list(session.execute(select(models.MainlineNode).where(models.MainlineNode.mainline_id == mainline_id).order_by(models.MainlineNode.position)).scalars())


def _versions_for_mainline(session: Session, mainline_id: str) -> list[models.MainlineVersion]:
    return list(session.execute(select(models.MainlineVersion).where(models.MainlineVersion.mainline_id == mainline_id).order_by(models.MainlineVersion.version.desc())).scalars())


def _save_version(session: Session, actor: models.User, mainline: models.Mainline, diff: dict) -> None:
    version_number = int(mainline.payload.get("version_number", 1))
    session.merge(
        models.MainlineVersion(
            id=f"MLV-{mainline.id}-{version_number}"[:120],
            tenant_id=actor.tenant_id,
            mainline_id=mainline.id,
            version=version_number,
            status=mainline.status,
            diff=jsonable_encoder(diff),
            payload=jsonable_encoder(mainline.payload),
        )
    )


def _bump_mainline_version(session: Session, actor: models.User, mainline: models.Mainline, diff: dict) -> None:
    payload = dict(mainline.payload)
    current = int(payload.get("version_number", 1)) + 1
    payload["version_number"] = current
    payload["version"] = f"v{current}"
    mainline.payload = jsonable_encoder(payload)
    _save_version(session, actor, mainline, diff)


def _workflow_run(session: Session, actor: models.User, case_id: str, name: str, workflow_id: str, trace_id: str, payload: dict) -> models.WorkflowRun:
    run = models.WorkflowRun(
        id=_id("WRUN"),
        case_id=case_id,
        tenant_id=actor.tenant_id,
        workflow_name=name,
        workflow_id=workflow_id,
        status="completed",
        started_by=actor.id,
        trace_id=trace_id,
        payload=jsonable_encoder({"algorithm_version": ALGORITHM_VERSION, **payload}),
    )
    session.add(run)
    return run


def _graph_nodes_for_mainline(session: Session, mainline_id: str) -> list[models.CaseGraphNode]:
    return list(session.execute(select(models.CaseGraphNode).where(models.CaseGraphNode.mainline_id == mainline_id).order_by(models.CaseGraphNode.created_at)).scalars())


def _upsert_case_graph_nodes(session: Session, actor: models.User, mainline: models.Mainline, world_state: models.WorldState | None, rule_version: str) -> list[models.CaseGraphNode]:
    topic_id = mainline.payload.get("topic_id")
    evidence_refs = list(mainline.payload.get("evidence_refs", []))
    definitions = [
        ("event", mainline.title),
        ("evidence_cluster", "Confirmed evidence cluster"),
        ("risk", "Mainline risk and uncertainty"),
        ("stakeholder_hint", "Stakeholder interaction surface"),
    ]
    rows: list[models.CaseGraphNode] = []
    for node_type, title in definitions:
        node_id = _stable_id("CGN", mainline.id, node_type, world_state.id if world_state else "none")
        node = models.CaseGraphNode(
            id=node_id,
            tenant_id=actor.tenant_id,
            case_id=mainline.case_id,
            topic_id=topic_id,
            mainline_id=mainline.id,
            world_state_id=world_state.id if world_state else None,
            node_type=node_type,
            title=title,
            status="active",
            evidence_refs=evidence_refs,
            payload={"rule_version": rule_version, "algorithm_version": ALGORITHM_VERSION, "synthetic": mainline.payload.get("synthetic", False)},
        )
        session.merge(node)
        rows.append(node)
    session.flush()
    return [session.get(models.CaseGraphNode, row.id) or row for row in rows]


def _upsert_stakeholders(session: Session, actor: models.User, mainline: models.Mainline, graph_nodes: list[models.CaseGraphNode], rule_version: str) -> list[models.Stakeholder]:
    topic_id = mainline.payload.get("topic_id")
    evidence_refs = list(mainline.payload.get("evidence_refs", []))
    definitions = [
        ("Campus family representatives", "affected_group", "Needs transparent evidence handling and communication cadence."),
        ("School response team", "institution", "Needs verifiable facts, privacy protection, and operational risk control."),
        ("Local public service operators", "governance", "Needs escalation thresholds and public communication timing."),
    ]
    rows: list[models.Stakeholder] = []
    graph_node_id = graph_nodes[0].id if graph_nodes else None
    for name, role, stance in definitions:
        stakeholder_id = _stable_id("STK", mainline.id, name)
        stakeholder = models.Stakeholder(
            id=stakeholder_id,
            tenant_id=actor.tenant_id,
            case_id=mainline.case_id,
            topic_id=topic_id,
            mainline_id=mainline.id,
            graph_node_id=graph_node_id,
            name=name,
            role=role,
            stance=stance,
            status="candidate",
            reviewer_id=None,
            evidence_refs=evidence_refs,
            payload={"rule_version": rule_version, "algorithm_version": ALGORITHM_VERSION, "synthetic": mainline.payload.get("synthetic", False), "blocked_claims": [{"claim": "Stakeholder profile is not generated until this stakeholder is reviewed.", "reason": "S6 guardrail"}]},
        )
        session.merge(stakeholder)
        rows.append(stakeholder)
    session.flush()
    return [session.get(models.Stakeholder, row.id) or row for row in rows]


def _stakeholders_for_mainline(session: Session, mainline_id: str) -> list[models.Stakeholder]:
    return list(session.execute(select(models.Stakeholder).where(models.Stakeholder.mainline_id == mainline_id).order_by(models.Stakeholder.name)).scalars())


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _serialize_evidence(evidence: models.Evidence) -> dict:
    return {"id": evidence.id, "signal_id": evidence.signal_id, "title": evidence.title, "status": evidence.status, "credibility": evidence.credibility, "evidence_refs": evidence.payload.get("evidence_refs", []), "payload": evidence.payload}


def _legacy_page_view(mainline: models.Mainline, nodes: list[models.MainlineNode], evidence_rows: list[models.Evidence], stakeholders: list[models.Stakeholder]) -> dict:
    return {
        "page": "mainline",
        "case_id": mainline.case_id,
        "title": "Mainline builder",
        "metrics": [
            {"label": "Versions", "value": mainline.payload.get("version", "v1"), "tone": "blue"},
            {"label": "Evidence refs", "value": len(mainline.payload.get("evidence_refs", [])), "tone": "green"},
            {"label": "Stakeholders", "value": len(stakeholders), "tone": "amber"},
        ],
        "sections": [
            {"id": "candidates", "title": "Candidate mainlines", "kind": "mainlines", "items": [serialize_mainline(mainline)]},
            {"id": "graph", "title": "Mainline graph nodes", "kind": "nodes", "items": [serialize_mainline_node(node) for node in nodes]},
            {"id": "evidence", "title": "Evidence references", "kind": "evidence", "items": [_serialize_evidence(row) for row in evidence_rows]},
            {"id": "stakeholders", "title": "Stakeholders", "kind": "stakeholders", "items": [serialize_stakeholder(row) for row in stakeholders]},
        ],
        "actions": [
            {"id": "quality-check", "label": "Run mainline quality check"},
            {"id": "confirm-mainline", "label": "Confirm mainline"},
            {"id": "create-world-state", "label": "Generate World State"},
        ],
        "raw": {"mainline_id": mainline.id, "topic_id": mainline.payload.get("topic_id"), "quality_gate": mainline.payload.get("quality_gate")},
    }
