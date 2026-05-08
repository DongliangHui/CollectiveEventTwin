# CollectiveEventTwin P0 Contracts

This package holds shared API and schema contracts for the production P0 skeleton.

- `openapi/p0.yaml` records the stable P0 route surface consumed by the React app.
- `schemas/agent-council-output.schema.json` defines the Agent Council output validator contract.

The FastAPI runtime exposes the live OpenAPI document at `/openapi.json`; this package is the source-controlled contract snapshot for P0 review and frontend alignment.
