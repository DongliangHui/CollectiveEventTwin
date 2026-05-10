# CollectiveEventTwin P0 Contracts

This package holds shared API and schema contracts for CollectiveEventTwin.

- `openapi/v1.0.yaml` is the frozen production v1.0 OpenAPI/DTO contract derived from `docs/production-plan-v1.0-20260509.md` and `docs/api-db-contract-v1.0-20260509.md`.
- `openapi/p0.yaml` records the older P0 skeleton route surface consumed by the current React app.
- `schemas/agent-council-output.schema.json` defines the Agent Council output validator contract.

The FastAPI runtime exposes the live OpenAPI document at `/openapi.json`; this package is the source-controlled contract snapshot for review and frontend alignment. Runtime implementation may lag the v1.0 frozen contract while the backlog is executed.
