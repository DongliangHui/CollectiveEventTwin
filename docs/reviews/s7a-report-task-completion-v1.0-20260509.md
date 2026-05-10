# S7A Report / Approval / Export / Task Completion Report

Date: 2026-05-09

## Scope

S7A implemented and froze the report, approval, export, and task closure slice:

- Report drafts are generated from reviewed and applied Council Results only.
- Report claims are persisted as individual `report_claims` rows and blocked unless each claim has evidence refs.
- Report review submission uses the Review Service and `TPL-REPORT-V1`.
- Publication requires a passing report review gate.
- Exports are persisted in `report_exports` with format, content hash, file URI, and synthetic/production watermark.
- Report-linked tasks are persisted, evidence-linked, evented, and audit-logged.
- The React Brief page is backed by real FastAPI/PostgreSQL APIs only.

## Backend

- Added `apps/api/src/worldline_api/reports.py` for S7A report generation, claim validation, review submission, publication, export, task listing/creation/status update, workflow runs, and audit writes.
- Added S7A routes in `apps/api/src/worldline_api/main.py`:
  - `GET /api/v1/reports`
  - `POST /api/v1/reports`
  - `GET /api/v1/reports/{report_id}`
  - `PATCH /api/v1/reports/{report_id}`
  - `GET /api/v1/reports/{report_id}/brief-view`
  - `POST /api/v1/reports/{report_id}/submit-review`
  - `POST /api/v1/reports/{report_id}/publish`
  - `POST /api/v1/reports/{report_id}/exports`
  - `GET /api/v1/tasks`
  - `POST /api/v1/tasks`
  - `PATCH /api/v1/tasks/{task_id}`
- Added `report:read`, `report:write`, `task:read`, and `task:write` permissions.
- Added `TPL-REPORT-V1` third-party review template.
- Fixed S6 deterministic Agent seed idempotency so repeated Agent Profile/LLM calls in one transaction cannot duplicate seed templates.

## Frontend

- Updated `apps/web/src/api.ts` with S7A report/task DTOs, API methods, Brief page adapter, and `getFirstReportBriefPage`.
- Updated `apps/web/src/p0-pages/ApiDrivenProductPage.tsx` so `/cases/CASE-CAMPUS-001/brief` loads through S7A APIs instead of the legacy case page view.
- Added persisted page actions:
  - Submit report review.
  - Publish and export report.
  - Update report-linked task status.
- Hardened shared structured page rendering against missing `actions`, `sections`, and `metrics` fields.

## Database

- Added Alembic revision `20260509_0012_reports_tasks.py`.
- Extended PostgreSQL tables:
  - `reports`
  - `tasks`
- Added PostgreSQL tables:
  - `report_versions`
  - `report_claims`
  - `report_exports`
  - `task_events`
- PostgreSQL migration state: `20260509_0012 (head)`.

## API Contract

- Updated `packages/contracts/openapi/v1.0.yaml` with S7A list/export request contracts and expanded Report/Task DTO fields.
- OpenAPI YAML parse and required path scan passed: 137 paths, missing S7A paths: 0.

## Tests

- `python -m pytest apps/api/tests/test_s7a_reports_tasks_api.py -q`: 2 passed.
- `python -m pytest apps/api/tests/test_s6_worldline_agent_council_api.py apps/api/tests/test_s7a_reports_tasks_api.py -q`: 4 passed.
- `python -m pytest apps/api/tests -q`: 22 passed.
- `npm run build --prefix apps/web`: passed.
- `alembic upgrade head && alembic current` with `WORLDLINE_DATABASE_URL=postgresql+psycopg://worldline:worldline@localhost:55432/worldline`: `20260509_0012 (head)`.

## Browser Validation

Route: `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/brief`

Artifacts:

- `artifacts/s7a-report-brief-before.png`
- `artifacts/s7a-report-brief-after.png`
- `artifacts/s7a-report-brief-playwright-result.json`
- `artifacts/s7a-report-brief-network-clean.log`
- `artifacts/s7a-report-brief-console-clean.log`

Observed required network:

- `POST /api/v1/reports` -> 201
- `GET /api/v1/reports/{id}/brief-view` -> 200
- `POST /api/v1/reports/{id}/submit-review` -> 201
- `PATCH /api/v1/reviews/{id}` -> 200
- `POST /api/v1/reviews/{id}/gate-check` -> 200
- `POST /api/v1/reports/{id}/publish` -> 200
- `POST /api/v1/reports/{id}/exports` -> 201
- `PATCH /api/v1/tasks/{id}` -> 200

Console/page errors: 0.
Failed API network calls: 0.

## Performance

Artifact: `artifacts/s7a-report-api-performance.json`

- Sample size: 22 API calls.
- Max latency: 96.51 ms.
- P95 latency: 77.16 ms.
- Threshold: max < 2000 ms, p95 < 1200 ms.
- Result: PASS.

Exception coverage:

- Missing report: 404 `REPORT_NOT_FOUND`.
- Missing task: 404 `TASK_NOT_FOUND`.

Audit coverage:

- `report_draft.create`
- `report_review.submit`
- `report.publish`
- `report_export.create`
- `task.status_update`

## Third-Party Review Gate

Artifact: `artifacts/s7a-report-review-gate.json`

- API contract review: `REV-ed186d0ae21f47b6aac5`, gate PASS.
- Report evidence/publication review: `REV-5bf919bbf07a4517aa14`, gate PASS.
- Frontend Brief page review: `REV-1c0d1c90899c4f5dbe8b`, gate PASS.

## Remaining Risks

- Export currently persists markdown/json content in PostgreSQL. External PDF/DOCX rendering is intentionally deferred until a document rendering service/key exists.
- Vite build still warns about a large JS chunk; this remains an S8 release-hardening item.
- S7B must ensure retrospectives and configuration changes cannot update production memory/config without review approval.

## Next Stage

S7B starts immediately: retrospectives, topic/case library, data source and model configuration.
