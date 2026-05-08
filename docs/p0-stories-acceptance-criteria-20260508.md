# CollectiveEventTwin P0 Stories / Acceptance Criteria

Date: 2026-05-08

Status: implementation contract

## Epic 1: Authorized/Test Data Ingestion

### Story P0-S1: Seed campus golden fixture

As a risk analyst, I need a stable campus high-intensity fixture so the full P0 business loop can be verified repeatedly.

Acceptance criteria:

- Given an empty database, when the seed command runs, `CASE-CAMPUS-001` is available.
- The seed command is idempotent and does not delete existing rows.
- The case includes accepted source records, signals, evidence, risk factors, mainline, world state, worldline nodes, council result, report, tasks, and audit logs.
- The case includes blocked source evidence for compliance-negative validation without entering the main processing chain.

### Story P0-S2: Seed non-campus smoke fixture

As a product owner, I need a non-campus fixture so P0 proves the system is not hardcoded to a campus event template.

Acceptance criteria:

- Given an empty database, when the seed command runs, `CASE-COMMUNITY-WATER-001` is available.
- The fixture uses community-water outage language, factors, agents, tasks, and report text.
- The fixture enters the same object chain as the campus case.
- No generated report or Agent output for the smoke case contains campus-only wording.

### Story P0-S3: Reject unauthorized source

As a compliance reviewer, I need unauthorized sources to be blocked before processing.

Acceptance criteria:

- A source with `access_mode=private_or_bypassed`, `cookie_pool`, `captcha_bypass`, `private_chat`, or `unknown` is marked rejected.
- Rejected records do not produce signals, evidence, factors, mainlines, reports, or tasks.
- Rejection creates an audit log entry with reason `source_not_allowed_for_p0`.

## Epic 2: Evidence, Factors, And Human Confirmation

### Story P0-S4: Review signal evidence

As a risk analyst, I need to inspect evidence for each signal and mark its review state.

Acceptance criteria:

- The API returns signal details with linked evidence.
- Evidence has one of: `confirmed_fact`, `needs_review`, `rumor`, `opinion`, `emotion`, `propagation`.
- Updating evidence status writes an audit log.
- Sensitive evidence returns masked text by default.

### Story P0-S5: Confirm and reject risk factors

As a risk analyst, I need to confirm or reject suggested risk factors before they influence formal reporting.

Acceptance criteria:

- Each factor includes trigger reason, confidence, evidence refs, and status.
- Confirming or rejecting a factor writes an audit log.
- Confirmed factors appear in the mainline and report context.
- Rejected factors remain visible for audit but do not drive report conclusions.

### Story P0-S6: Enforce report confirmation gate

As a reviewer, I need high-risk conclusions to require human confirmation before they become formal report conclusions.

Acceptance criteria:

- A report has `draft_summary` and `formal_conclusion`.
- If `human_confirmed=false`, high-risk text appears only in draft/review sections.
- Confirming a report writes an audit log and sets `formal_conclusion`.
- The API never returns an unconfirmed high-risk conclusion in the formal section.

## Epic 3: Mainline, Worldline, And Agent Council

### Story P0-S7: Build and confirm mainline

As a risk analyst, I need to turn selected signals and factors into a reviewable mainline.

Acceptance criteria:

- A case has a mainline with signals, support points, trigger clusters, evidence gaps, and confirmation status.
- Confirming the mainline creates or updates the world state.
- Mainline confirmation writes an audit log.
- Mainline payload preserves evidence gaps and uncertainty.

### Story P0-S8: Generate worldline nodes

As a decision maker, I need 24-72 hour worldline branches for an accepted mainline.

Acceptance criteria:

- A confirmed mainline returns at least root, risk escalation, and de-escalation nodes.
- Each node includes probability, risk, support point state, evidence refs, and whether council is recommended.
- Node data is available through API and web UI.

### Story P0-S9: Run Agent Council with schema validation

As a decision material preparer, I need Agent Council output to be structured and bounded by evidence.

Acceptance criteria:

- Council output includes `role`, `stance`, `reaction`, `support_point_delta`, `branch_probability_delta`, `evidence_refs`, `uncertainty`, and `blocked_claims`.
- Unsupported claims are put in `blocked_claims`, not formal output.
- Applying council result updates council status and writes audit.
- Council output can be used by the report without adding unverified facts.

## Epic 4: Report, Tasks, Audit, And UI Closed Loop

### Story P0-S10: Generate decision report

As a decision material preparer, I need a report that summarizes evidence, worldline, council result, tasks, and compliance warnings.

Acceptance criteria:

- A report includes current judgement, evidence summary, risk path, council changes, uncertainty, tasks, and compliance notes.
- The report links back to case, mainline, world state, node, and council session.
- Report generation writes audit.

### Story P0-S11: Manage tasks

As an operator, I need to update task status and keep task origin traceable.

Acceptance criteria:

- Tasks include owner, due label, status, source object, and payload.
- Task status updates write audit.
- Reports show updated task states.

### Story P0-S12: Use production web app

As a user, I need a React web app that completes the P0 closed loop without reading static fixtures directly.

Acceptance criteria:

- The web app fetches from `/api/v1`.
- Campus golden path reaches report and task updates.
- Community smoke path reaches report without campus-only wording.
- Loading, empty, and error states exist.
- UI does not rely on `worldline-observer-current` runtime files.

