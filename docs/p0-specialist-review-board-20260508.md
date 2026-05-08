# CollectiveEventTwin P0 Specialist Review Board

Date: 2026-05-08

Status: accepted for implementation

## Product Review

Decision: pass with scope lock.

- P0 must remain a business closed-loop validation, not a real connector project.
- Campus golden path plus community-water smoke path is sufficient for P0 scope.
- Static HTML is reference only; production app must be React/API backed.

## UX / Frontend Review

Decision: pass with production web requirement.

- Build a dense operational interface, not a landing page.
- Each screen must expose loading, empty, and error states.
- Screen language must separate facts, rumors, opinions, emotions, and propagation.
- No card-heavy marketing composition; use structured operational panels.

## Architecture Review

Decision: pass with production stack lock.

- Use React/Vite, FastAPI, SQLAlchemy, PostgreSQL JSONB/pgvector, Alembic, Redis, Temporal, Docker Compose.
- Do not make the old static pages the production frontend.
- Temporal is required from P0 to avoid later migration from ad hoc jobs.
- Repository/search interfaces should allow OpenSearch later without changing business services.

## QA Review

Decision: pass with test gate.

- Tests must cover campus golden, community smoke, and compliance-negative fixtures.
- Seed must be idempotent and non-destructive.
- API and frontend closed loop must be verified.
- Docker compose must boot a fresh local stack.

## Data / Compliance Review

Decision: pass with policy gate.

- Unauthorized sources must be rejected before signal generation.
- Sensitive person/minor data must be masked by default.
- High-risk formal conclusions require human confirmation.
- Every meaningful state mutation must produce audit logs.

## LLM / Agent Review

Decision: pass with deterministic P0 Agent.

- P0 Agent Council may be deterministic, but output must follow schema.
- Unsupported facts go to `blocked_claims`.
- Agent results are pressure tests, not facts or real public opinion.
- LLM gateway can be added behind the same schema later.

## Implementation Blockers Cleared

- Scope is locked to方案 A.
- Production stack is locked.
- Static frontend is no longer the implementation target.
- Implementation can proceed after TR1 and delivery plan are recorded.

