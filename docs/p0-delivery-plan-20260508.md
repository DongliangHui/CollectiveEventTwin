# CollectiveEventTwin P0 Delivery Plan

Date: 2026-05-08

Status: implementation contract

## Slice 1: Production Skeleton

Deliver:

- `apps/api`, `apps/worker`, `apps/web`, `packages/contracts`, `infra/docker`.
- Docker Compose for postgres, redis, temporal, api, worker, web.

Validation:

- API imports.
- Web builds.
- Compose config validates.

## Slice 2: Data Foundation

Deliver:

- SQLAlchemy models.
- Alembic migration.
- Seed fixtures for campus, community-water, and compliance-negative records.
- Source policy gate and masking.

Validation:

- Migration from empty DB succeeds.
- Seed is idempotent.
- Unauthorized source is rejected.

## Slice 3: Business Closed Loop API

Deliver:

- Cases, signals, evidence, factors, mainline, worldline, council, report, tasks, audit endpoints.
- Audit writer for all mutating state changes.
- Report confirmation gate.

Validation:

- API integration test completes case -> report -> task flow.

## Slice 4: Workflow And Agent

Deliver:

- Temporal workflow definitions and worker.
- Deterministic Agent Council service with schema validation.
- Workflow run records.

Validation:

- Workflow classes import.
- Worker starts in Docker.
- Council result blocks unsupported claims.

## Slice 5: Production Web Closed Loop

Deliver:

- React app with risk intake, signal/evidence, factors, mainline, worldline, council, report, audit summary.
- TanStack Query API access.
- Loading, empty, and error states.

Validation:

- Campus golden path visible.
- Community smoke path visible without campus hardcoding.
- Web build succeeds.

## Slice 6: End-To-End Validation

Deliver:

- Unit tests.
- API tests.
- Docker smoke check.
- Final implementation report.

Validation:

- Python tests pass.
- Frontend build passes.
- Docker stack starts or failure is documented with exact evidence.

