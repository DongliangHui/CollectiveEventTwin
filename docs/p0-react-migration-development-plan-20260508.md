# CollectiveEventTwin P0 React Migration Development Plan

Date: 2026-05-08

Status: frontend workstream only; superseded as overall MVP plan

Superseded by:

- `docs/p0-production-grade-delivery-plan-20260508.md`

This document no longer defines the overall MVP delivery critical path. It remains useful only for the React page migration workstream after the production-grade backend spine is implemented.

New delivery constraints:

- Product runtime must not use mock data, static runtime fixtures, or frontend-only business state.
- Every meaningful page interaction must call the backend and query or mutate database state.
- The backend must provide real ingestion, algorithm, workflow, Agent, and LLM services before broad page migration proceeds.

## Current Baseline

The P0 commercial-ready skeleton is implemented and locally verified:

- FastAPI, SQLAlchemy, Alembic, PostgreSQL, Temporal worker, Redis, and React/Vite app exist.
- API tests pass.
- Web production build passes.
- The official production frontend path is `apps/web`, not `worldline-observer-current`.
- `worldline-observer-current` remains the visual and product-flow reference only.

Current product work is the React/TanStack app under `apps/web`.

## Product Decisions

1. Freeze `city` as the first accepted product page.
   - Primary route: `/cases/CASE-CAMPUS-001/city`.
   - The city page becomes the first visual, interaction, and API-driven baseline for the remaining migration.

2. Add one more non-campus P0 sample.
   - Existing golden sample: `CASE-CAMPUS-001`.
   - Existing non-campus smoke sample: `CASE-COMMUNITY-WATER-001`.
   - New required non-campus sample: default implementation target is `CASE-MARKET-FOOD-001`, a city market or food-safety consumer-protection trust-risk scenario.
   - The new sample must run through the same object chain: `Case -> SourceRecord -> Signal -> Evidence -> RiskFactor -> Mainline -> WorldState -> WorldlineNode -> CouncilResult -> Report -> Task -> Audit`.

## Delivery Goals

- Migrate all P0 product pages into API-driven React.
- Keep admin, seed, workflow, and debug controls under `/admin`, not in the main product flow.
- Preserve source authorization, masking, audit, and human confirmation gates.
- Verify that multiple scenario types work without campus-specific hardcoding.

## Phase 0: City Page Freeze

Target window: 2026-05-08 to 2026-05-10

Deliver:

- Treat `city` as the first frozen page.
- Add `city` to Playwright product route coverage.
- Capture city screenshots at desktop and narrow viewport sizes.
- Verify map mode feedback, clustering, filters, ranking, event detail linkage, and fallback behavior when external map tiles fail.

Validation:

- `npm run build --prefix apps/web`
- `python -m pytest apps/api/tests -q`
- Playwright route/API check for `/cases/CASE-CAMPUS-001/city`
- No requests to `worldline-observer-current/mock`

Exit criteria:

- City page can be used as the style and interaction baseline for later pages.
- No known React runtime error blocks city use.

## Phase 1: Scenario Data Expansion

Target window: 2026-05-10 to 2026-05-12

Deliver:

- Add `CASE-MARKET-FOOD-001` seed fixture or equivalent non-campus sample.
- Add source records, signals, evidence, risk factors, mainline, world state, worldline nodes, council result, report, tasks, and audit rows.
- Add API tests proving the third scenario enters the same chain.
- Add frontend smoke coverage proving the page copy does not contain campus-only language.

Validation:

- Seed from empty database is idempotent.
- Existing campus and community-water fixtures still pass.
- API test asserts all three cases are available.
- Frontend smoke visits at least `risk`, `mainline`, and `brief` for the third sample.

Exit criteria:

- P0 no longer depends on a single campus case plus one smoke sample.

## Phase 2: Risk, Data, Evidence

Target window: 2026-05-12 to 2026-05-15

Deliver:

- `risk`: migrate the topic situation cockpit into API-driven React.
- `data`: provide source, signal, credibility, sensitivity, filter, and review workflow.
- `evidence`: provide evidence review, masking, factor linkage, and status updates.

Validation:

- Each page fetches `/api/v1/cases/{caseId}/pages/{page}`.
- Campus, community-water, and market-food scenarios render without static fixture requests.
- Evidence status updates write audit logs.

Exit criteria:

- A user can move from city discovery into topic, data, and evidence review without leaving the React app.

## Phase 3: Mainline, Worldline, Council

Target window: 2026-05-15 to 2026-05-19

Deliver:

- `mainline`: support signal selection, support points, evidence gaps, and confirmation.
- `worldline`: support branch probability, risk path, node detail, and council trigger.
- `council`: support agent outputs, pressure tests, blocked claims, and apply-to-worldline action.

Validation:

- Mainline confirmation creates or updates world state.
- Running council and applying results mutate through API endpoints.
- Unsupported claims stay in `blocked_claims`.

Exit criteria:

- The core analytical loop is usable from React with no admin console dependency.

## Phase 4: Brief, Memory, Library, Config

Target window: 2026-05-19 to 2026-05-22

Deliver:

- `brief`: decision brief, formal confirmation gate, tasks, compliance notes, export affordance.
- `memory`: post-case review and reusable pattern capture.
- `library`: similar case recall and apply action.
- `config`: rule version actions, regression run, approval, and publish flow.

Validation:

- Formal conclusion remains blocked until human confirmation.
- Task updates write audit logs.
- Memory, library, and config actions call their API endpoints.

Exit criteria:

- The full P0 product route set is React/API-driven.

## Phase 5: TR4 Test-Ready Review

Target window: 2026-05-22 to 2026-05-25

Deliver:

- Expanded Playwright coverage for `city`, `risk`, `data`, `evidence`, `mainline`, `worldline`, `council`, `brief`, `memory`, `library`, and `config`.
- Visual baseline screenshots for city, risk, worldline, council, and brief.
- Docker smoke validation.
- TR4 readiness report.

Validation:

- `npm run build --prefix apps/web`
- `python -m pytest apps/api/tests -q`
- `npm run test:e2e --prefix apps/web` when API/web are running
- `docker compose -f infra/docker/docker-compose.yml config`
- Docker stack health and API health check

Exit criteria:

- P0 can enter DCP decision as a local product demo candidate.

## DCP Demo Path

Demo route:

```text
city -> risk -> data -> evidence -> mainline -> worldline -> council -> brief -> task/audit -> memory/library/config
```

Required demo scenarios:

- `CASE-CAMPUS-001`: campus high-intensity golden path.
- `CASE-COMMUNITY-WATER-001`: public-service trust-risk smoke path.
- `CASE-MARKET-FOOD-001`: additional non-campus scenario to prove broader generalization.

## Residual Risks

- Some current UI text and tests still reflect encoding artifacts; clean-up should be included before TR4.
- Third-scenario implementation must not become copy-only data. It needs the same API and audit chain as the existing fixtures.
- External map tiles can fail; city page must preserve local interactive feedback.
- Bundle size warning exists in Vite build; this is not a P0 blocker, but route-level code splitting should be considered after product parity.
