# CollectiveEventTwin P0 TR1 Architecture / Data / API / Agent Design

Date: 2026-05-08

Status: implementation contract

## Architecture

P0 uses a production-oriented monorepo structure:

```text
apps/web        React + TypeScript + Vite
apps/api        FastAPI + Pydantic + SQLAlchemy + Alembic
apps/worker     Temporal worker
packages/contracts  OpenAPI/schema contract
infra/docker    Docker Compose and local runtime config
```

`p0-agent-runtime` remains a spike/reference. Reusable logic is migrated into the production API/service layer.

## Runtime Services

- `postgres`: PostgreSQL 16 with pgvector.
- `redis`: cache, idempotency, short-lived state.
- `temporal`: workflow service.
- `api`: FastAPI application.
- `worker`: Temporal worker.
- `web`: React production web app served by Vite preview.

## Data Model

Core tables:

- `cases`
- `source_records`
- `signals`
- `evidence`
- `risk_factors`
- `mainlines`
- `world_states`
- `worldline_nodes`
- `council_sessions`
- `reports`
- `tasks`
- `audit_logs`
- `workflow_runs`

Each table uses typed columns for common filters plus JSONB `payload` for evolvable data.

## State Rules

- `SourceRecord.accepted=false` blocks downstream signal/factor/report generation.
- `Evidence.status` changes write audit.
- `RiskFactor.status` changes write audit.
- `Mainline.status=confirmed` is required before formal world state use.
- `Report.human_confirmed=true` is required before high-risk formal conclusions.
- `Task.status` changes write audit.
- Agent unsupported claims go to `blocked_claims`.

## API Contract

P0 API namespace: `/api/v1`.

Core endpoints:

- `GET /health`
- `POST /api/v1/admin/seed`
- `GET /api/v1/cases`
- `GET /api/v1/cases/{case_id}`
- `GET /api/v1/cases/{case_id}/signals`
- `GET /api/v1/cases/{case_id}/evidence`
- `GET /api/v1/cases/{case_id}/risk-factors`
- `GET /api/v1/cases/{case_id}/mainline`
- `GET /api/v1/cases/{case_id}/worldline`
- `GET /api/v1/cases/{case_id}/report`
- `GET /api/v1/cases/{case_id}/audit`
- `PATCH /api/v1/evidence/{evidence_id}`
- `PATCH /api/v1/risk-factors/{factor_id}`
- `POST /api/v1/mainlines/{mainline_id}/confirm`
- `POST /api/v1/worldline-nodes/{node_id}/run-council`
- `POST /api/v1/council-sessions/{session_id}/apply`
- `POST /api/v1/reports/{report_id}/confirm`
- `PATCH /api/v1/tasks/{task_id}`
- `GET /api/v1/map-layers/{case_id}`

## Agent Contract

Agent output schema:

```json
{
  "role": "string",
  "stance": "string",
  "reaction": "string",
  "support_point_delta": {"string": 0.0},
  "branch_probability_delta": {"string": 0.0},
  "evidence_refs": ["string"],
  "uncertainty": "string",
  "blocked_claims": ["string"]
}
```

P0 implementation is deterministic. Future LLM output must pass the same schema and evidence-bound validator.

## Workflow Design

Temporal workflows:

- `IngestCaseWorkflow`
- `BuildMainlineWorkflow`
- `GenerateWorldlineWorkflow`
- `RunCouncilWorkflow`
- `GenerateReportWorkflow`

P0 API can execute deterministic services directly for low-latency demo paths, but worker and workflow definitions exist from P0 and are part of Docker runtime.

## Observability

- API emits structured logs with request path and status.
- Mutating business actions write `audit_logs`.
- Workflow-style operations write `workflow_runs`.
- OpenTelemetry hooks are available behind configuration for future commercial deployment.

