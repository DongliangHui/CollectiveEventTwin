# S3A Xi'an City Page Completion Report v1.0

Date: 2026-05-09
Stage: S3A
Scope: Xi'an City page freeze

## Completed

- Added persisted City, Topic, CityEvent, CityMapState, SignalPackage, and SignalPackageItem objects.
- Added `20260509_0007_city_topic_signal` Alembic migration after S2 import/processing migration.
- Implemented frozen City APIs under `/api/v1/cities/xian/*` and `/api/v1/city-events/*`.
- Derived CityEvent rows from PostgreSQL `raw_records`; no frontend fixture or frontend-only event state is used.
- Preserved `evidence_refs`, `synthetic` flags, lineage edges, and audit logs for city-event derivation, map-state updates, and topic creation.
- Updated the City frontend page to consume frozen City APIs, persist map interactions, fetch event details, and create topics through backend APIs.
- Replaced unauthenticated external tile fallback with an offline local map background when no AMap key is configured.

## Database Changes

- `cities`
- `topics`
- `city_events`
- `city_map_states`
- nullable `signals.topic_id`
- `signal_packages`
- `signal_package_items`

Migration validation:

- SQLite Alembic fresh upgrade to `20260509_0007`: passed.
- PostgreSQL Alembic upgrade from `20260509_0006` to `20260509_0007`: passed.

## API Changes

- `GET /api/v1/cities`
- `GET /api/v1/cities/{city_id}/overview`
- `GET /api/v1/cities/{city_id}/map-layers`
- `PATCH /api/v1/cities/{city_id}/map-state`
- `GET /api/v1/cities/{city_id}/events`
- `GET /api/v1/cities/{city_id}/events/rankings`
- `GET /api/v1/cities/{city_id}/source-health-view`
- `GET /api/v1/cities/{city_id}/media-evidence`
- `GET /api/v1/cities/{city_id}/timeline`
- `GET /api/v1/city-events/{city_event_id}`
- `POST /api/v1/city-events/{city_event_id}/create-topic`

OpenAPI parse check: 127 paths, S3A required paths present.

## Validation

- `python -m compileall apps/api/src/worldline_api -q`: passed.
- `python -m pytest apps/api/tests/test_s3a_city_api.py -q`: 1 passed.
- `python -m pytest apps/api/tests -q`: 10 passed.
- `npm run build`: passed with existing Vite large chunk warning.
- `git diff --check`: no whitespace errors; existing CRLF conversion warnings only.

## Performance

Artifact: `artifacts/s3a-city-api-performance.json`

- Max observed p95: 29.4 ms.
- Read threshold: 250 ms p95.
- Write threshold: 500 ms p95.
- Result: passed.

## Browser Verification

Artifact: `artifacts/s3a-city-playwright-clean.png`

- Real login token used.
- API responses captured: 40.
- Statuses: 39 x 200, 1 x 201.
- Failed requests: 0.
- Console errors/warnings: 0.
- Observed endpoints: overview, map layers, events, rankings, source health, media evidence, timeline, map-state PATCH, event detail, create-topic.

## Third-Party Check

Artifact: `artifacts/s3a-city-review-gate.json`

- Review ID: `REV-f8cc4c7067d148e79272`
- Object: `frontend_page/s3a_xian_city_page`
- Status: pass.
- Gate: passed.
- Blockers: none.

## Residual Risk

- Local verification uses synthetic-labelled Xi'an data because no external source credentials were provided.
- City page text still inherits some legacy mojibake strings from the existing P0 page; behavior and API source-of-truth are frozen, but copy cleanup remains visual polish.
- Vite bundle size warning remains from the existing product page bundle and is tracked as non-blocking until broader frontend splitting.

## Next Stage

Automatic next stage: S3B topic situation page freeze.
