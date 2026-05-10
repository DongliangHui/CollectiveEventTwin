from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .audit import write_audit
from .foundation import DEFAULT_TENANT_ID, api_error

ALGORITHM_VERSION = "s6-worldline-agent-council-v1"
SYNTHETIC_PROVIDER_ID = "LLM-SYNTHETIC-DETERMINISTIC-V1"
PROMPT_TEMPLATE_ID = "PROMPT-S6-COUNCIL-V1"
AGENT_TEMPLATE_ID = "AGENT-TEMPLATE-S6-STAKEHOLDER-V1"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_worldline_run(session: Session, request: schemas.WorldlineRunCreate, actor: models.User, trace_id: str) -> dict:
    world_state = _world_state_or_404(session, request.world_state_id)
    mainline_id = world_state.payload.get("mainline_id")
    evidence_refs = list(world_state.payload.get("evidence_refs", []))
    if not evidence_refs:
        raise api_error(409, "WORLDLINE_EVIDENCE_REFS_REQUIRED", "Worldline simulation requires evidence refs.")
    run = models.WorldlineRun(
        id=_id("WLR"),
        tenant_id=actor.tenant_id,
        case_id=world_state.case_id,
        world_state_id=world_state.id,
        status="pending",
        version=1,
        current_step="created",
        payload={
            "world_state_version": world_state.payload.get("version", "v1"),
            "mainline_id": mainline_id,
            "input_refs": [{"object_type": "world_state", "object_id": world_state.id, "object_version": world_state.payload.get("version", "v1")}],
            "evidence_refs": evidence_refs,
            "options": request.options,
            "status_history": ["pending"],
            "algorithm_version": ALGORITHM_VERSION,
            "synthetic": world_state.payload.get("synthetic", False),
            "blocked_claims": world_state.payload.get("blocked_claims", []),
        },
    )
    session.add(run)
    session.flush()
    run.status = "running"
    run.current_step = "branch_generation"
    run.payload = jsonable_encoder(run.payload | {"status_history": ["pending", "running"]})
    nodes = _generate_worldline_nodes(session, actor, run, world_state, evidence_refs)
    _generate_worldline_edges(session, actor, run, nodes)
    run.status = "completed"
    run.current_step = "simulation_view_ready"
    run.payload = jsonable_encoder(run.payload | {"status_history": ["pending", "running", "completed"], "node_ids": [node.id for node in nodes]})
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=run.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="worldline_run.completed",
        object_type="worldline_run",
        object_id=run.id,
        object_version=f"v{run.version}",
        after=serialize_worldline_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_worldline_run(run)


def get_worldline_run(session: Session, worldline_run_id: str) -> dict:
    return serialize_worldline_run(_worldline_run_or_404(session, worldline_run_id))


def simulation_view(session: Session, worldline_run_id: str, actor: models.User) -> dict:
    run = _worldline_run_or_404(session, worldline_run_id)
    nodes = _nodes_for_run(session, run.id)
    interventions = _interventions_for_run(session, run.id)
    return {
        "page_state": "ready" if run.status == "completed" else "degraded",
        "permissions": {"worldline:read": True, "worldline:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "worldline_runs/worldline_nodes/worldline_edges/worldline_interventions"},
        "degraded_sources": [] if run.status == "completed" else [{"code": run.error_code or "WORLDLINE_NOT_COMPLETED", "message": run.error_message or run.status}],
        "audit_context": {"object_type": "worldline_run", "object_id": run.id, "object_version": f"v{run.version}"},
        "primary_data": {
            "run": serialize_worldline_run(run),
            "nodes": [serialize_worldline_node(node) for node in nodes],
            "edges": [serialize_worldline_edge(edge) for edge in _edges_for_run(session, run.id)],
            "interventions": [serialize_worldline_intervention(row) for row in interventions],
            "legacy_page_view": _legacy_worldline_view(run, nodes, interventions),
        },
        "actions": [
            {"id": "add-intervention", "label": "Add intervention", "method": "POST", "href": f"/api/v1/worldline-runs/{run.id}/interventions", "enabled": run.status == "completed"},
            {"id": "enter-council", "label": "Enter Council", "method": "POST", "href": "/api/v1/council-sessions", "enabled": bool(nodes)},
        ],
    }


def add_worldline_intervention(session: Session, worldline_run_id: str, request: schemas.WorldlineInterventionCreate, actor: models.User, trace_id: str) -> dict:
    run = _worldline_run_or_404(session, worldline_run_id)
    before = serialize_worldline_run(run)
    intervention = models.WorldlineIntervention(
        id=_id("WLI"),
        tenant_id=actor.tenant_id,
        worldline_run_id=run.id,
        action=request.action,
        reason=request.reason,
        constraints=jsonable_encoder(request.constraints),
        payload={"algorithm_version": ALGORITHM_VERSION, "input_refs": run.payload.get("input_refs", []), "evidence_refs": run.payload.get("evidence_refs", [])},
    )
    session.add(intervention)
    run.version += 1
    run.payload = jsonable_encoder(run.payload | {"latest_intervention_id": intervention.id, "intervention_count": int(run.payload.get("intervention_count", 0)) + 1})
    for node in _nodes_for_run(session, run.id):
        if node.branch == "B":
            node.probability = min(95, node.probability + 4)
        if node.branch == "C":
            node.probability = max(1, node.probability - 4)
        node.version += 1
    write_audit(
        session,
        tenant_id=actor.tenant_id,
        case_id=run.case_id,
        actor=actor.username,
        actor_id=actor.id,
        action="worldline_intervention.create",
        object_type="worldline_intervention",
        object_id=intervention.id,
        object_version=f"v{run.version}",
        reason=request.reason,
        before=before,
        after=serialize_worldline_run(run),
        trace_id=trace_id,
    )
    session.commit()
    return serialize_worldline_run(run)


def list_llm_providers(session: Session, actor: models.User) -> list[dict]:
    _ensure_agent_seed(session, actor)
    session.commit()
    return [serialize_llm_provider(row) for row in session.execute(select(models.LlmProvider).order_by(models.LlmProvider.name)).scalars()]


def list_llm_calls(session: Session, object_id: str | None = None) -> list[dict]:
    statement = select(models.LlmCall).order_by(models.LlmCall.created_at.desc())
    if object_id:
        statement = statement.where(models.LlmCall.object_id == object_id)
    return [serialize_llm_call(row) for row in session.execute(statement).scalars()]


def list_prompt_templates(session: Session, actor: models.User) -> list[dict]:
    _ensure_agent_seed(session, actor)
    session.commit()
    return [serialize_prompt_template(row) for row in session.execute(select(models.PromptTemplate).order_by(models.PromptTemplate.name)).scalars()]


def create_prompt_template(session: Session, payload: dict, actor: models.User, trace_id: str) -> dict:
    template = models.PromptTemplate(
        id=payload.get("id") or _id("PROMPT"),
        tenant_id=actor.tenant_id,
        name=payload.get("name", "Custom prompt"),
        version=payload.get("version", "v1"),
        schema_version=payload.get("schema_version", "s6-prompt-schema-v1"),
        template=payload.get("template", ""),
        payload=jsonable_encoder(payload),
    )
    session.add(template)
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="prompt_template.create", object_type="prompt_template", object_id=template.id, trace_id=trace_id)
    session.commit()
    return serialize_prompt_template(template)


def list_agent_templates(session: Session, actor: models.User) -> list[dict]:
    _ensure_agent_seed(session, actor)
    session.commit()
    return [serialize_agent_template(row) for row in session.execute(select(models.AgentTemplate).order_by(models.AgentTemplate.name)).scalars()]


def create_agent_profile(session: Session, request: schemas.AgentProfileCreate, actor: models.User, trace_id: str) -> dict:
    _ensure_agent_seed(session, actor)
    stakeholder = _stakeholder_or_404(session, request.stakeholder_id)
    if stakeholder.status != "reviewed":
        raise api_error(409, "STAKEHOLDER_REVIEW_REQUIRED", "Agent Profile requires reviewed stakeholder.")
    run = _worldline_run_or_404(session, request.worldline_run_id)
    if run.status != "completed":
        raise api_error(409, "WORLDLINE_RUN_NOT_COMPLETED", "Agent Profile requires completed worldline run.")
    evidence_refs = list(stakeholder.evidence_refs or run.payload.get("evidence_refs", []))
    profile = models.AgentProfile(
        id=_id("AP"),
        tenant_id=actor.tenant_id,
        stakeholder_id=stakeholder.id,
        worldline_run_id=run.id,
        status="draft",
        version=1,
        files={},
        evidence_refs=evidence_refs,
        payload={
            "agent_template_id": AGENT_TEMPLATE_ID,
            "input_refs": [{"object_type": "stakeholder", "object_id": stakeholder.id}, {"object_type": "worldline_run", "object_id": run.id, "object_version": f"v{run.version}"}],
            "synthetic": stakeholder.payload.get("synthetic", run.payload.get("synthetic", False)),
            "blocked_claims": [{"claim": "Agent Profile cannot infer private traits or assign blame.", "reason": "S6 guardrail"}],
        },
    )
    session.add(profile)
    _record_llm_call(session, actor, "agent_profile", profile.id, evidence_refs, {"status": "draft", "stakeholder_id": stakeholder.id})
    write_audit(session, tenant_id=actor.tenant_id, case_id=stakeholder.case_id, actor=actor.username, actor_id=actor.id, action="agent_profile.create", object_type="agent_profile", object_id=profile.id, object_version="v1", after=serialize_agent_profile(profile), trace_id=trace_id)
    session.commit()
    return serialize_agent_profile(profile)


def get_agent_profile(session: Session, profile_id: str) -> dict:
    profile = _agent_profile_or_404(session, profile_id)
    if profile.status == "checking" and _has_passed_review(session, "agent_profile", profile.id):
        profile.status = "ready"
        session.commit()
    return serialize_agent_profile(profile)


def create_agent_profile_files(session: Session, profile_id: str, request: schemas.AgentProfileFilesWrite, actor: models.User, trace_id: str) -> dict:
    profile = _agent_profile_or_404(session, profile_id)
    before = serialize_agent_profile(profile)
    files = {"user_md": request.user_md, "soul_md": request.soul_md, "agent_md": request.agent_md}
    profile.files = jsonable_encoder(files)
    profile.status = "checking"
    for file_type, content in files.items():
        session.add(models.AgentProfileFile(id=_id("APF"), tenant_id=actor.tenant_id, agent_profile_id=profile.id, file_type=file_type, version=profile.version, content=content, payload={"reason": request.reason, "evidence_refs": profile.evidence_refs}))
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="agent_profile.files_write", object_type="agent_profile", object_id=profile.id, object_version=f"v{profile.version}", reason=request.reason, before=before, after=serialize_agent_profile(profile), trace_id=trace_id)
    session.commit()
    return serialize_agent_profile(profile)


def create_council_session(session: Session, request: schemas.CouncilSessionCreate, actor: models.User, trace_id: str) -> dict:
    run = _worldline_run_or_404(session, request.worldline_run_id)
    node = _worldline_node_or_404(session, request.selected_node_id)
    if node.worldline_run_id != run.id:
        raise api_error(409, "WORLDLINE_NODE_RUN_MISMATCH", "Selected node does not belong to worldline run.")
    profiles = [_agent_profile_or_404(session, profile_id) for profile_id in request.agent_profile_ids]
    for profile in profiles:
        if profile.status == "checking" and _has_passed_review(session, "agent_profile", profile.id):
            profile.status = "ready"
        if profile.status != "ready":
            raise api_error(409, "AGENT_PROFILE_REVIEW_NOT_PASSED", "All Agent Profiles must pass review before Council Session creation.")
    council = models.CouncilSession(
        id=_id("CS"),
        case_id=run.case_id,
        node_id=node.id,
        hypothesis=request.hypothesis or "Assess worldline pressure against evidence-bounded stakeholder perspectives.",
        status="created",
        payload={
            "worldline_run_id": run.id,
            "selected_node_id": node.id,
            "agent_profile_ids": [profile.id for profile in profiles],
            "profile_status": "ready",
            "evidence_refs": node.evidence_refs,
            "status_history": ["created"],
            "schema_valid": None,
            "blocked_claims": [],
        },
    )
    session.add(council)
    write_audit(session, tenant_id=actor.tenant_id, case_id=run.case_id, actor=actor.username, actor_id=actor.id, action="council_session.create", object_type="council_session", object_id=council.id, after=serialize_council_session(council), trace_id=trace_id)
    session.commit()
    return serialize_council_session(council)


def council_view(session: Session, council_session_id: str, actor: models.User) -> dict:
    council = _council_session_or_404(session, council_session_id)
    run = _worldline_run_or_404(session, council.payload.get("worldline_run_id"))
    node = _worldline_node_or_404(session, council.node_id)
    profiles = [_agent_profile_or_404(session, profile_id) for profile_id in council.payload.get("agent_profile_ids", [])]
    result = _latest_council_result(session, council.id)
    return {
        "page_state": "ready",
        "permissions": {"worldline:read": True, "worldline:write": True, "actor_id": actor.id},
        "refresh_at": utcnow(),
        "data_freshness": {"source": "postgresql", "derived_from": "council_sessions/agent_profiles/llm_calls/council_results/blocked_claims"},
        "degraded_sources": [] if council.status not in {"blocked"} else [{"code": "COUNCIL_BLOCKED", "message": "Council blocked by guardrails."}],
        "audit_context": {"object_type": "council_session", "object_id": council.id},
        "primary_data": {
            "session": serialize_council_session(council),
            "worldline_run": serialize_worldline_run(run),
            "selected_node": serialize_worldline_node(node),
            "agent_profiles": [serialize_agent_profile(profile) for profile in profiles],
            "messages": [serialize_council_message(row) for row in _messages_for_council(session, council.id)],
            "result": serialize_council_result(result) if result else None,
            "llm_calls": list_llm_calls(session, object_id=council.id),
        },
        "actions": [{"id": "run-council", "label": "Run Council", "method": "POST", "href": f"/api/v1/council-sessions/{council.id}/run", "enabled": council.status in {"created", "blocked"}}],
    }


def run_council(session: Session, council_session_id: str, actor: models.User, trace_id: str) -> dict:
    council = _council_session_or_404(session, council_session_id)
    run = _worldline_run_or_404(session, council.payload.get("worldline_run_id"))
    node = _worldline_node_or_404(session, council.node_id)
    profiles = [_agent_profile_or_404(session, profile_id) for profile_id in council.payload.get("agent_profile_ids", [])]
    council.status = "running"
    council.payload = jsonable_encoder(council.payload | {"status_history": ["created", "profile_checking", "running"]})
    evidence_refs = list(node.evidence_refs or run.payload.get("evidence_refs", []))
    messages = []
    blocked_claims = []
    for profile in profiles:
        llm_call = _record_llm_call(session, actor, "council_session", council.id, evidence_refs, {"agent_profile_id": profile.id, "node_id": node.id})
        message = models.CouncilMessage(id=_id("CM"), tenant_id=actor.tenant_id, council_session_id=council.id, agent_profile_id=profile.id, role="stakeholder_agent", content=f"Profile {profile.id} reacts to branch {node.branch} using evidence refs only.", evidence_refs=evidence_refs, payload={"llm_call_id": llm_call.id, "schema_valid": True})
        session.add(message)
        messages.append(message)
        blocked_claims.append({"id": _id("BCL"), "claim": "Assigning individual blame or private motive without evidence is blocked.", "reason": "No verified evidence ref supports the claim.", "source_ref": {"object_type": "llm_call", "object_id": llm_call.id}})
    summary = f"Council pressure test for branch {node.branch}: evidence-bounded response recommends transparent update cadence and privacy guardrails."
    result = models.CouncilResult(id=_id("CR"), tenant_id=actor.tenant_id, council_session_id=council.id, worldline_run_id=run.id, status="pending", summary=summary, evidence_refs=evidence_refs, payload={"schema_valid": True, "branch_probability_delta": {node.branch: -3 if node.risk > 60 else 2}, "support_point_delta": {"trust_window": 0.08}, "information_gaps": ["Need updated evidence preservation window."], "blocked_claims": blocked_claims})
    session.add(result)
    session.flush()
    for item in blocked_claims:
        session.add(models.BlockedClaim(id=item["id"], tenant_id=actor.tenant_id, claim=item["claim"], reason=item["reason"], source_ref=item["source_ref"], council_result_id=result.id, payload={"council_session_id": council.id}))
    council.status = "completed"
    council.payload = jsonable_encoder(council.payload | {"status_history": ["created", "profile_checking", "running", "schema_validating", "completed"], "result_id": result.id, "schema_valid": True, "blocked_claims": blocked_claims})
    write_audit(session, tenant_id=actor.tenant_id, case_id=council.case_id, actor=actor.username, actor_id=actor.id, action="council_result.create", object_type="council_result", object_id=result.id, after=serialize_council_result(result), trace_id=trace_id)
    session.commit()
    return serialize_council_session(council)


def apply_council_result(session: Session, council_result_id: str, actor: models.User, trace_id: str) -> dict:
    result = _council_result_or_404(session, council_result_id)
    if not _has_passed_review(session, "council_result", result.id):
        raise api_error(409, "COUNCIL_REVIEW_NOT_PASSED", "Council Result must pass third-party review before apply.")
    council = _council_session_or_404(session, result.council_session_id)
    run = _worldline_run_or_404(session, result.worldline_run_id)
    result.status = "pass"
    result.payload = jsonable_encoder(result.payload | {"applied": True, "applied_at": utcnow().isoformat()})
    council.status = "applied"
    council.payload = jsonable_encoder(council.payload | {"applied_result_id": result.id})
    run.version += 1
    run.payload = jsonable_encoder(run.payload | {"applied_council_result_id": result.id})
    write_audit(session, tenant_id=actor.tenant_id, case_id=run.case_id, actor=actor.username, actor_id=actor.id, action="council_result.apply", object_type="council_result", object_id=result.id, object_version="v1", after=serialize_council_result(result), trace_id=trace_id)
    session.commit()
    return serialize_council_result(result)


def serialize_worldline_run(run: models.WorldlineRun) -> dict:
    return {"id": run.id, "case_id": run.case_id, "world_state_id": run.world_state_id, "status": run.status, "version": f"v{run.version}", "current_step": run.current_step, "error_code": run.error_code, "payload": run.payload, "created_at": run.created_at, "updated_at": run.updated_at}


def serialize_worldline_node(node: models.WorldlineNode) -> dict:
    return {"id": node.id, "case_id": node.case_id, "worldline_run_id": node.worldline_run_id, "world_state_id": node.world_state_id, "title": node.title, "branch": node.branch, "probability": node.probability, "risk": node.risk, "status": node.status, "version": node.version, "evidence_refs": node.evidence_refs, "payload": node.payload, "created_at": node.created_at, "updated_at": node.updated_at}


def serialize_worldline_edge(edge: models.WorldlineEdge) -> dict:
    return {"id": edge.id, "worldline_run_id": edge.worldline_run_id, "from_node_id": edge.from_node_id, "to_node_id": edge.to_node_id, "probability_delta": edge.probability_delta, "payload": edge.payload}


def serialize_worldline_intervention(row: models.WorldlineIntervention) -> dict:
    return {"id": row.id, "worldline_run_id": row.worldline_run_id, "action": row.action, "reason": row.reason, "constraints": row.constraints, "payload": row.payload, "created_at": row.created_at}


def serialize_llm_provider(row: models.LlmProvider) -> dict:
    return {"id": row.id, "name": row.name, "status": row.status, "model_defaults": row.model_defaults}


def serialize_llm_call(row: models.LlmCall) -> dict:
    return {"id": row.id, "provider_id": row.provider_id, "model": row.model, "prompt_version": row.prompt_version, "status": row.status, "tokens": row.tokens, "cost": row.cost, "latency_ms": row.latency_ms, "input_refs": row.input_refs, "payload": row.payload, "created_at": row.created_at}


def serialize_prompt_template(row: models.PromptTemplate) -> dict:
    return {"id": row.id, "name": row.name, "version": row.version, "schema_version": row.schema_version}


def serialize_agent_template(row: models.AgentTemplate) -> dict:
    return {"id": row.id, "name": row.name, "version": row.version}


def serialize_agent_profile(row: models.AgentProfile) -> dict:
    return {"id": row.id, "stakeholder_id": row.stakeholder_id, "worldline_run_id": row.worldline_run_id, "status": row.status, "version": f"v{row.version}", "files": row.files or {"user_md": "", "soul_md": "", "agent_md": ""}, "evidence_refs": row.evidence_refs, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_council_session(row: models.CouncilSession) -> dict:
    return {"id": row.id, "case_id": row.case_id, "worldline_run_id": row.payload.get("worldline_run_id"), "selected_node_id": row.node_id, "node_id": row.node_id, "hypothesis": row.hypothesis, "status": row.status, "agent_profile_ids": row.payload.get("agent_profile_ids", []), "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def serialize_council_message(row: models.CouncilMessage) -> dict:
    return {"id": row.id, "council_session_id": row.council_session_id, "agent_profile_id": row.agent_profile_id, "role": row.role, "content": row.content, "evidence_refs": row.evidence_refs, "payload": row.payload}


def serialize_council_result(row: models.CouncilResult) -> dict:
    blocked_claims = list(row.payload.get("blocked_claims", []))
    return {"id": row.id, "council_session_id": row.council_session_id, "worldline_run_id": row.worldline_run_id, "status": row.status, "summary": row.summary, "evidence_refs": row.evidence_refs, "blocked_claims": blocked_claims, "payload": row.payload, "created_at": row.created_at, "updated_at": row.updated_at}


def _world_state_or_404(session: Session, world_state_id: str | None) -> models.WorldState:
    row = session.get(models.WorldState, world_state_id) if world_state_id else None
    if row is None:
        raise api_error(404, "WORLD_STATE_NOT_FOUND", "World State not found.")
    return row


def _worldline_run_or_404(session: Session, worldline_run_id: str | None) -> models.WorldlineRun:
    row = session.get(models.WorldlineRun, worldline_run_id) if worldline_run_id else None
    if row is None:
        raise api_error(404, "WORLDLINE_RUN_NOT_FOUND", "Worldline run not found.")
    return row


def _worldline_node_or_404(session: Session, node_id: str | None) -> models.WorldlineNode:
    row = session.get(models.WorldlineNode, node_id) if node_id else None
    if row is None:
        raise api_error(404, "WORLDLINE_NODE_NOT_FOUND", "Worldline node not found.")
    return row


def _stakeholder_or_404(session: Session, stakeholder_id: str) -> models.Stakeholder:
    row = session.get(models.Stakeholder, stakeholder_id)
    if row is None:
        raise api_error(404, "STAKEHOLDER_NOT_FOUND", "Stakeholder not found.")
    return row


def _agent_profile_or_404(session: Session, profile_id: str) -> models.AgentProfile:
    row = session.get(models.AgentProfile, profile_id)
    if row is None:
        raise api_error(404, "AGENT_PROFILE_NOT_FOUND", "Agent Profile not found.")
    return row


def _council_session_or_404(session: Session, council_session_id: str) -> models.CouncilSession:
    row = session.get(models.CouncilSession, council_session_id)
    if row is None:
        raise api_error(404, "COUNCIL_SESSION_NOT_FOUND", "Council Session not found.")
    return row


def _council_result_or_404(session: Session, council_result_id: str) -> models.CouncilResult:
    row = session.get(models.CouncilResult, council_result_id)
    if row is None:
        raise api_error(404, "COUNCIL_RESULT_NOT_FOUND", "Council Result not found.")
    return row


def _has_passed_review(session: Session, object_type: str, object_id: str) -> bool:
    return session.execute(select(models.Review).where(models.Review.object_type == object_type, models.Review.object_id == object_id, models.Review.status == "pass")).scalar_one_or_none() is not None


def _generate_worldline_nodes(session: Session, actor: models.User, run: models.WorldlineRun, world_state: models.WorldState, evidence_refs: list[dict]) -> list[models.WorldlineNode]:
    definitions = [
        ("A", "Rapid evidence window reduces escalation", 28, 46, False),
        ("B", "Coordinated update stabilizes public trust", 31, 38, False),
        ("C", "Vague response hardens accountability narrative", 27, 74, True),
        ("D", "External attention creates long-tail uncertainty", 14, 62, True),
    ]
    rows = []
    for branch, title, probability, risk, needs_council in definitions:
        node = models.WorldlineNode(id=_id("WLN"), tenant_id=actor.tenant_id, case_id=run.case_id, worldline_run_id=run.id, world_state_id=world_state.id, title=title, branch=branch, probability=probability, risk=risk, status="active", version=1, evidence_refs=evidence_refs, payload={"needsCouncil": needs_council, "algorithm_version": ALGORITHM_VERSION, "support_point_state": world_state.payload.get("state_payload", {}).get("support_points", []), "input_refs": run.payload.get("input_refs", [])})
        session.add(node)
        rows.append(node)
    session.flush()
    return rows


def _generate_worldline_edges(session: Session, actor: models.User, run: models.WorldlineRun, nodes: list[models.WorldlineNode]) -> None:
    for left, right in zip(nodes, nodes[1:]):
        session.add(models.WorldlineEdge(id=_id("WLE"), tenant_id=actor.tenant_id, worldline_run_id=run.id, from_node_id=left.id, to_node_id=right.id, probability_delta=right.probability - left.probability, payload={"algorithm_version": ALGORITHM_VERSION}))


def _nodes_for_run(session: Session, run_id: str) -> list[models.WorldlineNode]:
    return list(session.execute(select(models.WorldlineNode).where(models.WorldlineNode.worldline_run_id == run_id).order_by(models.WorldlineNode.branch)).scalars())


def _edges_for_run(session: Session, run_id: str) -> list[models.WorldlineEdge]:
    return list(session.execute(select(models.WorldlineEdge).where(models.WorldlineEdge.worldline_run_id == run_id)).scalars())


def _interventions_for_run(session: Session, run_id: str) -> list[models.WorldlineIntervention]:
    return list(session.execute(select(models.WorldlineIntervention).where(models.WorldlineIntervention.worldline_run_id == run_id).order_by(models.WorldlineIntervention.created_at.desc())).scalars())


def _messages_for_council(session: Session, council_id: str) -> list[models.CouncilMessage]:
    return list(session.execute(select(models.CouncilMessage).where(models.CouncilMessage.council_session_id == council_id).order_by(models.CouncilMessage.created_at)).scalars())


def _latest_council_result(session: Session, council_id: str) -> models.CouncilResult | None:
    return session.execute(select(models.CouncilResult).where(models.CouncilResult.council_session_id == council_id).order_by(models.CouncilResult.created_at.desc())).scalars().first()


def _ensure_agent_seed(session: Session, actor: models.User) -> None:
    tenant_id = actor.tenant_id or DEFAULT_TENANT_ID
    added = False
    if session.get(models.LlmProvider, SYNTHETIC_PROVIDER_ID) is None:
        session.add(models.LlmProvider(id=SYNTHETIC_PROVIDER_ID, tenant_id=tenant_id, name="Deterministic synthetic LLM provider", status="active", model_defaults={"model": "synthetic-s6-guardrailed-v1", "external_key_required": False}, payload={"synthetic": True, "reason": "No external LLM key configured."}))
        added = True
    if session.get(models.PromptTemplate, PROMPT_TEMPLATE_ID) is None:
        session.add(models.PromptTemplate(id=PROMPT_TEMPLATE_ID, tenant_id=tenant_id, name="S6 Council evidence-bounded prompt", version="v1", schema_version="s6-council-output-schema-v1", template="Use only provided evidence refs; unsupported claims must be blocked.", payload={"synthetic": True}))
        added = True
    if session.get(models.AgentTemplate, AGENT_TEMPLATE_ID) is None:
        session.add(models.AgentTemplate(id=AGENT_TEMPLATE_ID, tenant_id=tenant_id, name="Reviewed stakeholder agent template", version="v1", payload={"guardrails": ["evidence_refs_required", "no_private_trait_inference"]}))
        added = True
    if added:
        session.flush()


def _record_llm_call(session: Session, actor: models.User, object_type: str, object_id: str, evidence_refs: list[dict], output: dict) -> models.LlmCall:
    _ensure_agent_seed(session, actor)
    call = models.LlmCall(id=_id("LLMC"), tenant_id=actor.tenant_id, provider_id=SYNTHETIC_PROVIDER_ID, prompt_template_id=PROMPT_TEMPLATE_ID, object_type=object_type, object_id=object_id, model="synthetic-s6-guardrailed-v1", prompt_version="v1", status="completed", tokens=512, cost=0.0, latency_ms=1, input_refs=evidence_refs, output=jsonable_encoder(output), payload={"synthetic": True, "schema_valid": True, "guardrails": ["evidence_refs_required", "blocked_claims_required"]})
    session.add(call)
    session.flush()
    write_audit(session, tenant_id=actor.tenant_id, actor=actor.username, actor_id=actor.id, action="llm_call.completed", object_type="llm_call", object_id=call.id, after=serialize_llm_call(call))
    return call


def _legacy_worldline_view(run: models.WorldlineRun, nodes: list[models.WorldlineNode], interventions: list[models.WorldlineIntervention]) -> dict:
    return {
        "page": "worldline",
        "case_id": run.case_id,
        "title": "Worldline simulation",
        "metrics": [
            {"label": "Run status", "value": run.status, "tone": "blue"},
            {"label": "Branches", "value": len(nodes), "tone": "green"},
            {"label": "Version", "value": f"v{run.version}", "tone": "amber"},
        ],
        "sections": [
            {"id": "nodes", "title": "Worldline branches", "kind": "nodes", "items": [serialize_worldline_node(node) for node in nodes]},
            {"id": "interventions", "title": "Interventions", "kind": "timeline", "items": [serialize_worldline_intervention(row) for row in interventions]},
            {"id": "council", "title": "Council-ready nodes", "kind": "nodes", "items": [serialize_worldline_node(node) for node in nodes if node.payload.get("needsCouncil")]},
        ],
        "actions": [{"id": "add-intervention", "label": "Add intervention"}, {"id": "enter-council", "label": "Enter Council"}],
        "raw": {"worldline_run_id": run.id, "world_state_id": run.world_state_id, "selected_node_id": next((node.id for node in nodes if node.payload.get("needsCouncil")), nodes[0].id if nodes else None)},
    }
