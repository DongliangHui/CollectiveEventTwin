# S6 Worldline / Agent Profile / Council Completion Report

Date: 2026-05-09

## Scope

S6 implemented and froze the worldline projection and guarded Agent Council slice:

- Worldline Run creation from persisted S5 World State inputs.
- Versioned worldline nodes, edges, probability branches, and interventions.
- Deterministic synthetic LLM provider with persisted `llm_calls` when no external key is available.
- Agent Profile generation from reviewed stakeholders and persisted profile files (`user.md`, `soul.md`, `agent.md`).
- Council Session creation, execution, blocked-claim handling, result review, and controlled apply back to the worldline.
- React worldline and council pages connected only through FastAPI/PostgreSQL APIs.

## Backend

- Added `apps/api/src/worldline_api/worldline.py` for S6 worldline, intervention, LLM provider, prompt template, Agent Profile, Council, review gate, workflow, audit, and serialization logic.
- Added S6 routes in `apps/api/src/worldline_api/main.py`:
  - `POST /api/v1/worldline-runs`
  - `GET /api/v1/worldline-runs/{worldline_run_id}`
  - `GET /api/v1/worldline-runs/{worldline_run_id}/simulation-view`
  - `POST /api/v1/worldline-runs/{worldline_run_id}/interventions`
  - `GET /api/v1/llm-providers`
  - `GET /api/v1/llm-calls`
  - `GET /api/v1/prompt-templates`
  - `POST /api/v1/prompt-templates`
  - `GET /api/v1/agent-templates`
  - `POST /api/v1/agent-profiles`
  - `GET /api/v1/agent-profiles/{agent_profile_id}`
  - `POST /api/v1/agent-profiles/{agent_profile_id}/files`
  - `POST /api/v1/council-sessions`
  - `GET /api/v1/council-sessions/{council_session_id}/council-view`
  - `POST /api/v1/council-sessions/{council_session_id}/run`
  - `POST /api/v1/council-results/{council_result_id}/apply`
- Added `worldline:read`, `worldline:write`, and `agent:review` permissions.
- Added Review templates for `agent_profile` and `council_result`.
- S6 write actions persist `workflow_runs`, `worldline_runs`, `worldline_nodes`, `worldline_edges`, `worldline_interventions`, `llm_calls`, `agent_profiles`, `agent_profile_files`, `council_messages`, `council_results`, `blocked_claims`, and `audit_logs`.

## Frontend

- Updated `apps/web/src/api.ts` with S6 DTOs, production API client methods, and page adapters for worldline simulation and Council views.
- Updated `apps/web/src/p0-pages/ApiDrivenProductPage.tsx` so:
  - `/cases/CASE-CAMPUS-001/worldline` loads and mutates a real Worldline Run through FastAPI.
  - `/cases/CASE-CAMPUS-001/council` creates reviewed Agent Profiles, runs Council, reviews the result, and applies it through real APIs.
- Added persisted page actions:
  - Add evidence-window intervention.
  - Prepare Agent Council.
  - Run guarded Council.
  - Review and apply Council result.

## Database

- Added Alembic revision `20260509_0010_worldline_runs.py`.
- Added PostgreSQL tables:
  - `worldline_runs`
  - `worldline_edges`
  - `worldline_interventions`
- Extended `worldline_nodes` with S6 run/version/evidence references.
- Added Alembic revision `20260509_0011_llm_agent_council.py`.
- Added PostgreSQL tables:
  - `llm_providers`
  - `prompt_templates`
  - `llm_calls`
  - `agent_templates`
  - `agent_profiles`
  - `agent_profile_files`
  - `council_messages`
  - `council_results`
  - `blocked_claims`
- PostgreSQL migration state: `20260509_0011 (head)`.

## API Contract

- `packages/contracts/openapi/v1.0.yaml` already contains the frozen S6 routes and DTO families for Worldline, LLM, Agent Profile, and Council.
- OpenAPI required-path scan passed for all S6 routes.

## Tests

- `python -m pytest apps/api/tests/test_s6_worldline_agent_council_api.py -q`: 2 passed.
- `python -m pytest apps/api/tests -q`: 20 passed.
- `npm run build --prefix apps/web`: passed.
- `alembic upgrade head && alembic current`: `20260509_0011 (head)`.

## Browser Validation

Routes:

- `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/worldline`
- `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/council`

Artifacts:

- `artifacts/s6-worldline-playwright-clean.png`
- `artifacts/s6-council-playwright-clean.png`
- `artifacts/s6-worldline-council-playwright-result.json`
- `artifacts/s6-worldline-council-network-clean.log`
- `artifacts/s6-worldline-council-console-clean.log`

Observed required network:

- `POST /api/v1/worldline-runs` -> 201
- `GET /api/v1/worldline-runs/{id}/simulation-view` -> 200
- `POST /api/v1/worldline-runs/{id}/interventions` -> 201
- `GET /api/v1/llm-providers` -> 200
- `POST /api/v1/agent-profiles` -> 201
- `POST /api/v1/agent-profiles/{id}/files` -> 201
- `POST /api/v1/reviews` for Agent Profile -> 200
- `POST /api/v1/council-sessions` -> 201
- `GET /api/v1/council-sessions/{id}/council-view` -> 200
- `POST /api/v1/council-sessions/{id}/run` -> 200
- `POST /api/v1/council-results/{id}/apply` -> 200

Console/page errors: 0.
Failed API network calls: 0.

## Performance

Artifact: `artifacts/s6-worldline-council-api-performance.json`

- Sample size: 41 API calls.
- Max latency: 116.57 ms.
- P95 latency: 47.48 ms.
- Threshold: max < 2000 ms, p95 < 1200 ms.
- Result: PASS.

Exception coverage:

- Missing Worldline Run: 404 `WORLDLINE_RUN_NOT_FOUND`.
- Missing Agent Profile: 404 `AGENT_PROFILE_NOT_FOUND`.
- Missing Council Session: 404 `COUNCIL_SESSION_NOT_FOUND`.
- Council before Agent Profile review: 409 `AGENT_PROFILE_REVIEW_NOT_PASSED`.
- Council apply before result review: 409 `COUNCIL_REVIEW_NOT_PASSED`.

Audit coverage:

- `worldline_run.completed`
- `worldline_intervention.create`
- `agent_profile.create`
- `agent_profile.files_write`
- `council_session.create`
- `llm_call.completed`
- `council_result.create`
- `council_result.apply`

## Third-Party Review Gate

Artifact: `artifacts/s6-worldline-council-review-gate.json`

- API contract review: `REV-d719e48911084e9f8d55`, gate PASS.
- Algorithm output review: `REV-2dba8a5bc2c6464bbcfc`, gate PASS.
- Agent Profile aggregate review: `REV-22f98fa9f406417eb8a9`, gate PASS.
- Council result aggregate review: `REV-b8fa14ff99b4470cad53`, gate PASS.
- Frontend page review: `REV-e2bdd31e6da0487dab89`, gate PASS.

## Remaining Risks

- External commercial LLM providers are not configured. S6 uses a deterministic synthetic provider, marks provider metadata clearly, and persists all LLM calls and blocked claims.
- Vite build still warns about large bundle size; this remains an S8 optimization and release-hardening risk.
- S7A must validate every report claim against persisted evidence and block publication when any claim lacks references.

## Next Stage

S7A starts immediately: reports, approval, export, and task closure.
