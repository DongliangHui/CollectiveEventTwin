# CollectiveEventTwin TR0 Business Decisions: Xi'an Social Issues

Date: 2026-05-08

Status: TR0 business decisions frozen for the current delivery plan.

This document supplements:

- `docs/full-project-atomic-task-development-plan-20260508.md`
- `docs/p0-production-grade-delivery-plan-20260508.md`

## 1. Frozen Business Decisions

| Decision Area | Frozen Decision |
| --- | --- |
| First-phase city | Xi'an |
| First-phase non-campus scenario domain | Social issues, starting with community demolition and pension-insurance petition scenarios |
| Data availability | The user currently has no external data keys or private data feeds |
| Data strategy | Build a synthetic scenario data channel first, but it must enter the system through real ingestion, cleaning, extraction, workflow, database, lineage, algorithm, Agent, and report paths |
| Mock boundary | Synthetic data is allowed only as labeled product seed/demo data; frontend mock data, static fixtures, and pre-materialized downstream objects remain forbidden |
| Multi-Agent role strategy | Agent roles are derived from stakeholders discovered while building the worldline, not hardcoded upfront |
| Agent readiness point | When a worldline is created, the system must identify involved stakeholders and prepare corresponding `user.md`, `soul.md`, and `agent.md` profiles before Council runs |
| Delivery bar | Customer-facing production-grade system |
| Third-party review | Every output must pass an independent review gate before it can be frozen or used in release acceptance |

## 2. Product Implications

- Xi'an becomes the default first-phase city filter, seed city, acceptance city, and browser test city.
- Community demolition and pension-insurance petition scenarios replace the previous generic non-campus sample direction.
- The synthetic data channel is a real product capability for bootstrapping and demo readiness. It must be visibly labeled as synthetic and cannot be confused with live public data or authorized customer data.
- Synthetic scenario records must still start from raw records. They cannot skip directly to signals, evidence, risk factors, reports, or Agent outputs.
- The channel system must support later replacement by real public, authorized, media, live-stream, document, and platform connectors without changing downstream business logic.
- Worldline construction must output stakeholder candidates. Council Agent profiles are generated or selected from those stakeholders.
- Customer-facing UI, report wording, permission model, audit trail, and exported artifacts must avoid internal demo language.
- Each Xi'an social-issue scenario output must pass third-party review: implementation owner cannot self-approve API, data, algorithm, Agent, frontend, media, report, security, performance, or release artifacts.

## 3. New Atomic Tasks

These tasks extend `AT-001` through `AT-343` in the main atomic plan.

| ID | Atomic Function | Backend/API/Service | Frontend Scenario | Normal Test | Abnormal Test | Performance/Browser Acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| AT-344 | Register Xi'an as first-phase city | `POST /api/v1/cities` or migration seed | Admin city config | Xi'an city exists with code, districts, coordinates, timezone | Duplicate city code returns 409 | City selector shows Xi'an |
| AT-345 | Set Xi'an as default first-phase workspace city | `PUT /api/v1/config/workspace-defaults` | Workspace settings | New case/session defaults to Xi'an | Unauthorized update returns 403 | Browser opens city page with Xi'an context |
| AT-346 | Define community-demolition scenario taxonomy | `POST /api/v1/config/taxonomies/versions` | Taxonomy config | Adds demolition, compensation, relocation, construction, resident appeal tags | Duplicate tag code returns 409 | Taxonomy regression passes |
| AT-347 | Define pension-insurance petition taxonomy | `POST /api/v1/config/taxonomies/versions` | Taxonomy config | Adds pension payment, eligibility, arrears, petition, social-security bureau tags | Missing parent taxonomy returns 422 | Taxonomy regression passes |
| AT-348 | Create synthetic scenario data source type | `POST /api/v1/data-sources` type=synthetic_scenario | Data source page | Creates a labeled synthetic source | Source cannot be marked as live/authorized | Source badge clearly says synthetic |
| AT-349 | Generate synthetic community-demolition raw records | `POST /api/v1/synthetic-scenarios/community-demolition/runs` | Scenario bootstrap page | Raw records generated through collection run | Missing Xi'an city config returns 409 | Run completes under 5 minutes |
| AT-350 | Generate synthetic pension-petition raw records | `POST /api/v1/synthetic-scenarios/pension-petition/runs` | Scenario bootstrap page | Raw records generated through collection run | Invalid time window returns 422 | Run completes under 5 minutes |
| AT-351 | Label synthetic data through lineage | service `mark_synthetic_lineage` | Data detail badges | raw, clean, signal, evidence, report all retain synthetic flag | Any derived object missing flag fails lineage test | Lineage query shows synthetic origin |
| AT-352 | Prevent synthetic data from being exported as live evidence | guardrail `block_unlabeled_synthetic_export` | Report export | Report can export with synthetic watermark | Export without watermark returns 409 | PDF/DOCX include synthetic watermark |
| AT-353 | Convert synthetic raw records through normal cleaning workflow | workflow `run_synthetic_channel_cleaning` | Bootstrap run details | Synthetic raw records pass parser, cleaner, extractor | Direct downstream insertion is rejected | DB verifies full chain |
| AT-354 | Discover worldline stakeholders from mainline/world state | algorithm `discover_worldline_stakeholders` | Worldline creation | Outputs stakeholder candidates and evidence refs | No evidence returns insufficient_data | Single worldline < 30s |
| AT-355 | Generate Council Agent candidates from stakeholders | service `prepare_council_agents_from_stakeholders` | Worldline-to-Council step | Creates draft Agent profiles for each stakeholder | Stakeholder without role definition enters review | Browser shows Agent readiness checklist |
| AT-356 | Generate `user.md` from stakeholder context | service `generate_agent_user_md` | Agent profile draft | Background, organization, interests, constraints generated with refs | Missing evidence refs blocked | Single profile < 20s |
| AT-357 | Generate `soul.md` from stakeholder role | service `generate_agent_soul_md` | Agent profile draft | Values, risk preference, decision logic generated | Contradictory stance flagged | Single profile < 20s |
| AT-358 | Generate `agent.md` from allowed tools and task boundary | service `generate_agent_agent_md` | Agent profile draft | Tools, workflow, schema, forbidden actions generated | Unauthorized tool blocked | Single profile < 20s |
| AT-359 | Customer-facing delivery language gate | QA/service `validate_customer_facing_copy` | All customer pages/reports | No mock/demo/dev/internal wording appears | Forbidden wording fails release gate | Browser/report scan passes |
| TR0-REVIEW-001 | Xi'an scenario third-party review gate | `POST /api/v1/review-gates` with Xi'an scenario scope | Scenario acceptance page | Every scenario output has independent reviewer result | Missing review blocks scenario freeze | Release summary shows all green |

## 4. First Acceptance Scenarios

| Scenario | Acceptance Goal |
| --- | --- |
| Xi'an community demolition | Synthetic raw records enter ingestion, cleaning, LLM extraction, signal generation, evidence review, risk factor generation, mainline, world state, worldline, stakeholder-derived Agent Council, report, task, and audit |
| Xi'an pension-insurance petition | Same chain as above, proving the system handles a second social-issue scenario without hardcoded demolition wording |
| Customer-facing report | Exported report clearly labels synthetic data when synthetic data is used and otherwise looks production-ready for customer review |

## 5. User Intervention Still Needed Later

These are not blockers for development start, but they are future business decisions:

- Confirm exact Xi'an districts or keep city-wide scope for phase one.
- Confirm whether synthetic demo reports may be shown to customers if clearly watermarked.
- Confirm first real data channels when customer/project access becomes available.
- Confirm customer report template and official wording style before DCP launch.
