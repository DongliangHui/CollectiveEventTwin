# S4A Signal Workbench Completion Report

Date: 2026-05-09

## Scope

S4A implemented and froze the signal extraction and Data / Signal Workbench slice:

- `F080-1` through `F080-12`: input raw-record selection, candidate signal generation, deterministic deduplication, aggregation metadata, sentiment, appeal tags, spread features, Xi'an local share, credibility inputs, signal persistence, failure attribution, and run result query.
- `S4A-WB-01` through `S4A-WB-06`: signal workbench view-model, signal list/search/detail, signal package create/add/remove, package query, page state, Playwright browser validation, performance probe, and review gate.

## Backend

- Added S4A routes in `apps/api/src/worldline_api/main.py`:
  - `POST /api/v1/extraction-runs`
  - `GET /api/v1/topics/{topic_id}/signal-workbench-view`
  - `GET /api/v1/signals`
  - `GET /api/v1/signals/{signal_id}`
  - `POST /api/v1/signal-packages`
  - `GET /api/v1/signal-packages/{signal_package_id}`
  - `POST /api/v1/signal-packages/{signal_package_id}/items`
  - `DELETE /api/v1/signal-packages/{signal_package_id}/items`
- Added `apps/api/src/worldline_api/signals.py` for deterministic signal extraction, serialization, lineage, package operations, and audit writes.
- Added request DTOs in `apps/api/src/worldline_api/schemas.py`:
  - `ExtractionRunCreate`
  - `SignalPackageCreate`
  - `SignalPackageItemWrite`
- Added `signal:read` and `signal:write` permissions.

## Frontend

- Updated `apps/web/src/api.ts` with S4A DTOs and API client methods.
- Updated `apps/web/src/p0-pages/ApiDrivenProductPage.tsx` so `/cases/CASE-CAMPUS-001/data` uses `GET /api/v1/topics/{id}/signal-workbench-view`.
- If a topic has no signals, the data page triggers `POST /api/v1/extraction-runs`; no frontend mock signals are rendered.
- Added persisted page actions:
  - Create signal package and add first signal.
  - Remove first packaged signal.

## Database

No new Alembic revision was required for S4A. The slice uses tables already frozen in `20260509_0007_city_topic_signal.py` and S1/S2 foundations:

- `workflow_runs`
- `signals`
- `signal_packages`
- `signal_package_items`
- `lineage_edges`
- `audit_logs`
- `ops_error_queue`

PostgreSQL migration state: `20260509_0007 (head)`.

## API Contract

- Updated `packages/contracts/openapi/v1.0.yaml` to freeze `ExtractionRunCreate` as a named request DTO.
- Aligned `SignalPackageCreate` and `SignalPackageItemWrite` schemas with backend DTOs.
- Contract scan passed for all S4A paths and DTO names.

## Tests

- `python -m pytest apps/api/tests/test_s4a_signal_api.py -q`: 2 passed.
- `python -m pytest apps/api/tests -q`: 14 passed.
- `npm run build --prefix apps/web`: passed.
- Alembic current on PostgreSQL: `20260509_0007 (head)`.

## Browser Validation

Route: `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/data`

Artifacts:

- `artifacts/s4a-signal-workbench-playwright-clean.png`
- `artifacts/s4a-signal-playwright-result.json`
- `artifacts/s4a-signal-network-clean.log`
- `artifacts/s4a-signal-console-clean.log`

Observed network:

- `GET /api/v1/topics?city_id=xian` -> 200
- `GET /api/v1/topics/{topic_id}/signal-workbench-view` -> 200
- `POST /api/v1/extraction-runs` -> 201
- `POST /api/v1/signal-packages` -> 201
- `POST /api/v1/signal-packages/{id}/items` -> 201
- `DELETE /api/v1/signal-packages/{id}/items?signal_id=...` -> 200

Console/page errors: 0.

## Performance

Artifact: `artifacts/s4a-signal-api-performance.json`

- Sample size: 19 API calls.
- Max latency: 185.07 ms.
- P95 latency: 185.07 ms.
- Threshold: max < 2000 ms, p95 < 1200 ms.
- Result: PASS.

Exception coverage:

- Missing topic: 404 `TOPIC_NOT_FOUND`.
- Missing signal: 404 `SIGNAL_NOT_FOUND`.
- Empty raw scope: persisted failed workflow run with `RAW_RECORD_SCOPE_EMPTY`.

## Third-Party Review Gate

Artifact: `artifacts/s4a-signal-review-gate.json`

- Algorithm output review: `REV-266cc58206544ffebc78`, status `pass`, gate PASS.
- Frontend page review: `REV-fe58344530834baf901f`, status `pass`, gate PASS.

## Remaining Risks

- S4A signals are deterministic candidate interpretations and are not factual findings. S4B must convert candidate signals into evidence candidates and require evidence review before report facts.
- Current development data uses the labeled synthetic Xi'an source channel when external feeds/keys are absent. Synthetic flags and input references are preserved.
- Vite build still warns about a large bundle; this is a performance optimization risk for S8, not a S4A functional blocker.

## Next Stage

S4B starts immediately: evidence candidate generation, evidence review workbench, multimedia evidence closure, evidence status transitions, and proof-backed report inputs.
