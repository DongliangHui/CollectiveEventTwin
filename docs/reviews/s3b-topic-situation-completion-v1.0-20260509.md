# S3B Topic Situation Completion Report

Date: 2026-05-09
Stage: S3B - Topic situation page freeze
Status: passed

## Scope Completed

- Implemented PostgreSQL-backed Topic lifecycle APIs:
  - `GET /api/v1/topics`
  - `POST /api/v1/topics`
  - `GET /api/v1/topics/{topic_id}`
  - `PATCH /api/v1/topics/{topic_id}`
  - `GET /api/v1/topics/{topic_id}/situation-view`
  - `GET /api/v1/topics/{topic_id}/source-breakdown`
  - `GET /api/v1/topics/{topic_id}/spread-paths`
  - `GET /api/v1/topics/{topic_id}/emotion-stance`
  - `GET /api/v1/topics/{topic_id}/candidate-mainlines`
- Implemented deterministic situation snapshot generation from `topics`, `city_events`, and `raw_records`.
- Persisted situation snapshot generation as audit-backed derived state; no Agent or report conclusion is stored without upstream evidence references.
- Connected the risk/topic frontend page to the Topic APIs and removed legacy page data dependency for the S3B page.
- Added frontend bootstrap behavior for an empty `xian` topic set: create a topic through `POST /api/v1/topics` from the highest available city event, or trigger the explicit synthetic Xi'an source path first if no city event exists.

## Database Changes

- Reused S3A migration `20260509_0007_city_topic_signal.py`.
- Topic state is persisted in `topics`.
- Related city event linkage is persisted in `city_events.topic_id`.
- Topic creation and situation snapshot updates write `audit_logs`.
- Topic creation writes `lineage_edges` from city events to topics.

## API And DTO Changes

- Added backend DTOs: `EntityRef`, `TopicCreate`, `TopicPatch`.
- Added frontend DTOs: `EntityRef`, `TopicRecord`, `TopicCreateInput`, `TopicPatchInput`.
- Extended audit query support with `page`, `page_size`, `limit`, `object_type`, `object_id`, `actor_id`, and `action`.
- OpenAPI contract check confirmed required S3B topic paths are present in `packages/contracts/openapi/v1.0.yaml`.

## Tests

- Backend tests: `python -m pytest apps/api/tests -q`
  - Result: 12 passed.
  - Includes normal path, invalid topic source, missing topic, and unauthenticated request coverage.
- Frontend build: `npm run build`
  - Result: passed.
  - Residual warning: existing Vite chunk-size warning.
- Alembic SQLite fresh migration: passed.
- Alembic PostgreSQL upgrade: passed.
- OpenAPI path check: 127 paths loaded; all 7 S3B required paths present.
- `git diff --check`: passed with CRLF warnings only.

## Browser Verification

- URL: `http://127.0.0.1:5175/cases/CASE-CAMPUS-001/risk`
- Screenshot: `artifacts/s3b-topic-playwright-clean.png`
- Console: `artifacts/s3b-topic-console-clean.log`
  - 0 errors, 0 warnings.
- Network: `artifacts/s3b-topic-network-clean.log`
  - Topic list, situation-view, source-breakdown, spread-paths, emotion-stance, and candidate-mainlines all returned 200.
- Click validation: `artifacts/s3b-topic-click-network.log`
  - Clicked `Enter mainline modeling`; route API `/api/v1/cases/CASE-CAMPUS-001/pages/mainline` returned 200 with no console errors.

## Performance

- Artifact: `artifacts/s3b-topic-api-performance.json`
- Thresholds:
  - Read p95 <= 250 ms.
  - Write p95 <= 500 ms.
- Result: passed.
- Max observed read p95: `144.413 ms` for `situation_view`.
- Topic status PATCH p95: `200.044 ms`.

## Review Gate

- Artifact: `artifacts/s3b-topic-review-gate.json`
- Review ID: `REV-2b79192bac2b47968146`
- Object: `frontend_page/s3b_topic_situation_page`
- Template: `TPL-FRONTEND-PAGE-V1`
- Status: pass.
- Gate: passed.
- Blockers: none.

## Residual Risks

- The S3B situation model is deterministic and evidence-linked, but not yet an LLM/Agent judgment. S6 will add guarded Agent/Council behavior.
- The frontend still carries existing large bundle size from the integrated P0 console; this remains a performance optimization item outside S3B correctness.
