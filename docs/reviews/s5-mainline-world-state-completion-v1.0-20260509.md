# S5 Mainline / World State / Stakeholder Completion Report

Date: 2026-05-09

## Scope

S5 implemented and froze the evidence-backed mainline modeling slice:

- Mainline draft generation from persisted S4A signal packages and confirmed S4B evidence.
- Versioned mainline node editing, signal membership changes, quality check, and confirmation.
- World State generation from confirmed mainlines.
- Case graph generation and stakeholder identification.
- Stakeholder review gate before S6 Agent Profile generation.
- Mainline builder page integration through real FastAPI/PostgreSQL APIs only.

## Backend

- Added `apps/api/src/worldline_api/mainline.py` for S5 mainline, World State, case graph, stakeholder, workflow, audit, and serialization logic.
- Added S5 routes in `apps/api/src/worldline_api/main.py`:
  - `GET /api/v1/mainlines`
  - `POST /api/v1/mainlines`
  - `GET /api/v1/mainlines/{mainline_id}`
  - `GET /api/v1/mainlines/{mainline_id}/builder-view`
  - `PATCH /api/v1/mainline-nodes/{node_id}`
  - `POST /api/v1/mainlines/{mainline_id}/signals`
  - `POST /api/v1/mainlines/{mainline_id}/quality-check`
  - `POST /api/v1/mainlines/{mainline_id}/confirm`
  - `POST /api/v1/world-states`
  - `GET /api/v1/world-states/{world_state_id}`
  - `POST /api/v1/case-graph-runs`
  - `POST /api/v1/stakeholder-runs`
  - `GET /api/v1/stakeholders`
  - `PATCH /api/v1/stakeholders/{stakeholder_id}/review`
- Added `mainline:read`, `mainline:write`, and `stakeholder:review` permissions.
- S5 write actions persist `workflow_runs`, `mainline_versions`, `audit_logs`, evidence refs, blocked claims, and synthetic markers.

## Frontend

- Updated `apps/web/src/api.ts` with S5 DTOs, production API client methods, and `getFirstMainlineBuilderPage`.
- Updated `apps/web/src/p0-pages/ApiDrivenProductPage.tsx` so `/cases/CASE-CAMPUS-001/mainline` loads mainline builder data from FastAPI/PostgreSQL.
- Added persisted page actions:
  - Edit first mainline node.
  - Run mainline quality check.
  - Confirm mainline and create World State.
  - Create case graph and stakeholder run as part of the confirmation action.
  - Review first stakeholder.
- Fixed mainline page empty `nav` handling discovered during Playwright validation.

## Database

- Added Alembic revision `20260509_0009_mainline_world_state_stakeholders.py`.
- Added PostgreSQL tables:
  - `mainline_versions`
  - `mainline_nodes`
  - `case_graph_nodes`
  - `stakeholders`
- Reused frozen baseline tables for S5 state:
  - `mainlines`
  - `world_states`
  - `workflow_runs`
  - `audit_logs`
- PostgreSQL migration state: `20260509_0009 (head)`.

## API Contract

- Updated `packages/contracts/openapi/v1.0.yaml` with S5 paths and DTOs:
  - `MainlineCreate`
  - `MainlineNodePatch`
  - `MainlineSignalWrite`
  - `WorldStateCreate`
  - `CaseGraphRunCreate`
  - `StakeholderRunCreate`
  - `StakeholderReviewPatch`
  - `MainlineListEnvelope`
- OpenAPI YAML parse and required path scan passed: 137 paths, missing S5 paths: 0.

## Tests

- `python -m pytest apps/api/tests/test_s5_mainline_world_state_api.py -q`: 2 passed.
- `python -m pytest apps/api/tests -q`: 18 passed.
- `npm run build --prefix apps/web`: passed.
- `alembic upgrade head && alembic current`: `20260509_0009 (head)`.

## Browser Validation

Route: `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/mainline`

Artifacts:

- `artifacts/s5-mainline-playwright-clean.png`
- `artifacts/s5-mainline-playwright-result.json`
- `artifacts/s5-mainline-network-clean.log`
- `artifacts/s5-mainline-console-clean.log`

Observed required network:

- `GET /api/v1/mainlines?topic_id=...` -> 200
- `GET /api/v1/mainlines/{id}/builder-view` -> 200
- `PATCH /api/v1/mainline-nodes/{id}` -> 200
- `POST /api/v1/mainlines/{id}/quality-check` -> 200
- `POST /api/v1/mainlines/{id}/confirm` -> 200
- `POST /api/v1/world-states` -> 201
- `POST /api/v1/case-graph-runs` -> 201
- `POST /api/v1/stakeholder-runs` -> 201
- `PATCH /api/v1/stakeholders/{id}/review` -> 200

Console/page errors: 0.
Failed API network calls: 0.

## Performance

Artifact: `artifacts/s5-mainline-api-performance.json`

- Sample size: 48 API calls.
- Max latency: 188.82 ms.
- P95 latency: 77.78 ms.
- Threshold: max < 2000 ms, p95 < 1200 ms.
- Result: PASS.

Exception coverage:

- Stale node edit conflict: 409 `MAINLINE_NODE_VERSION_CONFLICT`.
- Confirm before quality check: 409 `MAINLINE_QUALITY_NOT_PASSED`.
- Missing mainline: 404 `MAINLINE_NOT_FOUND`.
- Missing World State: 404 `WORLD_STATE_NOT_FOUND`.
- Missing node: 404 `MAINLINE_NODE_NOT_FOUND`.
- Missing stakeholder: 404 `STAKEHOLDER_NOT_FOUND`.

Audit coverage:

- `mainline_draft.create`
- `mainline_node.update`
- `mainline_signal.update`
- `mainline_quality_check.completed`
- `mainline.confirm`
- `world_state.create`
- `case_graph_run.completed`
- `stakeholder_run.completed`
- `stakeholder.review`

## Third-Party Review Gate

Artifact: `artifacts/s5-mainline-review-gate.json`

- API contract review: `REV-a6402eb4ea724fec9a97`, status `pass`, gate PASS.
- Algorithm output review: `REV-2d025a81355d49fab9f1`, status `pass`, gate PASS.
- Frontend page review: `REV-d42d76ae0a85453fa4b5`, status `pass`, gate PASS.

## Remaining Risks

- External LLM/Agent providers are not configured. S5 uses deterministic production code, records synthetic lineage when upstream input is synthetic, and blocks unsupported factual claims.
- Vite build still warns about large bundle size; this remains an S8 optimization and release-hardening risk.
- S6 must not generate Agent Profiles from unreviewed stakeholders; S5 now enforces and records stakeholder review status for that handoff.

## Next Stage

S6 starts immediately: worldline projection, Agent Profile, Council, and LLM guardrails.
