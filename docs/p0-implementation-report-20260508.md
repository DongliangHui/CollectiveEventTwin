# CollectiveEventTwin P0 Implementation Report

Date: 2026-05-08

## Result

P0 scheme A business closed loop is implemented on the commercial-ready stack selected in TR1.

The old `worldline-observer-current` static page remains non-production source code. After user review, it is now explicitly the visual/product-flow baseline for the official React implementation. Production code lives under `apps/`, `packages/contracts/`, and `infra/docker/`. No directory cleanup, repository reset, volume removal, or destructive database action was executed.

Frontend status correction: the current `apps/web` validates the P0 API/workflow loop and can remain as an internal ops/debug console, but it should not be treated as the final user-facing production UX. The next delivery step is to migrate the existing static稿 experience into `apps/web` while keeping it API-driven.

## Delivered Artifacts

- Formal gate docs:
  - `docs/p0-tr0-scope-20260508.md`
  - `docs/p0-prd-business-closed-loop-20260508.md`
  - `docs/p0-stories-acceptance-criteria-20260508.md`
  - `docs/p0-screen-inventory-20260508.md`
  - `docs/p0-specialist-review-board-20260508.md`
  - `docs/p0-tr1-architecture-data-api-agent-design-20260508.md`
  - `docs/p0-delivery-plan-20260508.md`
- Backend/API:
  - `apps/api`: FastAPI, Pydantic, SQLAlchemy, Alembic, source policy, masking, audit writer, workflow run records, search adapter.
  - `apps/api/alembic/versions/20260508_0001_p0_core.py`: P0 core schema with JSON payload columns and pgvector extension.
  - `apps/api/tests/test_p0_api.py`: API/unit coverage for golden path, smoke path, source policy, masking, audit.
- Temporal worker:
  - `apps/worker`: Temporal worker registering `IngestCaseWorkflow`, `BuildMainlineWorkflow`, `GenerateWorldlineWorkflow`, `RunCouncilWorkflow`, `GenerateReportWorkflow`.
  - API endpoint: `POST /api/v1/workflows/{workflow_name}/start`.
- Frontend:
  - `apps/web`: React + TypeScript + Vite + TanStack Router + TanStack Query.
  - Screens: intake/source gate, signals, evidence review, factor/mainline, worldline, council, brief/tasks, audit.
- Contracts:
  - `packages/contracts/openapi/p0.yaml`
  - `packages/contracts/schemas/agent-council-output.schema.json`
- Docker:
  - `infra/docker/docker-compose.yml`
  - API, worker, web Dockerfiles.
  - Postgres 16 + pgvector, Redis, Temporal, API, worker, web.

## Local Demo

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml up --build -d
```

URLs and ports:

- Web: `http://localhost:5173`
- API health: `http://localhost:8080/health`
- API OpenAPI: `http://localhost:8080/openapi.json`
- Temporal gRPC host port: `localhost:17233` mapped to container `7233`
- Postgres host port: `localhost:55432`
- Redis host port: `localhost:56379`

Note: host port `7233` was already occupied locally, so Temporal was mapped to `17233:7233`. Internal service traffic still uses `temporal:7233`.

## Validation Results

- `python -m pytest apps/api/tests -q`: passed, `3 passed`.
- `npm run build --prefix apps/web`: passed.
- `docker compose -f infra/docker/docker-compose.yml config`: passed.
- `docker compose -f infra/docker/docker-compose.yml up --build -d`: passed.
- API health: `{"status":"ok","service":"collective-event-twin-api"}`.
- Web HTTP check: `http://localhost:5173` returned `200`.
- Docker services:
  - postgres healthy
  - redis healthy
  - api healthy
  - temporal running
  - worker running
  - web running
- Temporal workflow smoke through API:
  - 5 completed workflow starts: ingest, build mainline, generate worldline, run council, generate report.
  - Worker logs show all workflow types executed on task queue `worldline-p0`.
- Campus golden path:
  - blocked unauthorized source count: `1`
  - minor evidence masked: `Comment thread includes [MASKED] and [MASKED].`
  - Agent Council schema: `p0.agent_council.v1`
  - council agents: `3`
  - report confirmed: `true`
  - formal conclusion populated.
- Non-campus smoke:
  - community water case loads through the same API/app flow.
  - water council agents: `3`
  - no campus-only hardcoding required for smoke path.

## Compliance And Audit

- Source policy blocks `private_chat`, `cookie_pool`, `captcha_bypass`, `private_or_bypassed`, and unknown sources.
- Minor/person-sensitive fields are masked before display.
- Agent Council output follows the required schema fields:
  - `role`
  - `stance`
  - `reaction`
  - `support_point_delta`
  - `branch_probability_delta`
  - `evidence_refs`
  - `uncertainty`
  - `blocked_claims`
- Formal report conclusion remains empty until human confirmation.
- Evidence, factor, mainline, council, report, task, source rejection, and workflow run state changes write audit records.

## Known Risks

- Frontend product UX is incomplete: the current React page reads like a test/process console. It needs correction against `worldline-observer-current` before being accepted as the production page.
- Auth/RBAC is not implemented yet. P0 local demo assumes trusted local operator access.
- Real connectors are still out of P0 acceptance. Source adapters and source policy exist, but production connector onboarding needs TR1.1 security review.
- Observability is at structured logs/request/workflow/audit IDs level. OTLP exporters, dashboards, alert rules, and trace sampling are not wired yet.
- Search is a database adapter now. The OpenSearch adapter is reserved by interface but not implemented.
- Docker API startup runs Alembic and idempotent seed. It does not clear data, but seed upsert can restore fixture fields on restart for demo consistency.
- Frontend validation covered TypeScript build and live HTTP/API behavior. Browser screenshot regression is not yet added.
- Generated local artifacts from dependency install/build exist (`node_modules`, `dist`, caches, egg-info). They are ignored via `.gitignore`; no cleanup was performed per instruction.

## Recommended Decision

Accept this as P0 technical skeleton and local demo baseline. Before TR4 hardening, correct the frontend product surface by migrating the `worldline-observer-current` static稿 visual/product flow into the React/API app and moving debug controls out of the main user flow.
