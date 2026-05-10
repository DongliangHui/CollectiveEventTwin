# Local Reference Project Source Study

Date: 2026-05-09

Scope: this file adds two local reference projects provided after the original open-source radar study. They are not counted in the original 69-repository radar inventory because both are local snapshots without `.git` metadata in the provided paths.

Reference paths:

- `E:\GitHub\ref_prj\MiroFish`
- `E:\GitHub\ref_prj\worldmonitor-main`

Use rule: these projects are implementation references only. CollectiveEventTwin must still implement production code inside its own FastAPI/PostgreSQL/Temporal/React stack, with database-backed runtime data, API-backed page interactions, evidence lineage, audit logs, and third-party review.

## 1. MiroFish

### 1.1 Relationship To CollectiveEventTwin

MiroFish is directly relevant to our worldline and Agent workbench direction:

- Graph construction before simulation: it turns event seed material into a graph, then uses that graph as the source for simulation setup.
- Stakeholder/agent profile generation: it derives OASIS-style profiles from graph entities, which is close to our requirement that Council agents are derived from worldline stakeholders.
- Simulation preparation and execution: it separates simulation creation, profile generation, config generation, run start, action logs, timeline, and history.
- Report Agent: it implements a long-running report generator plus a chat loop where the agent can call graph search/statistics tools.
- Visual state freezing: `ObservePreview.vue` plus the visual-audit document provide a concrete pattern for page state inventory, routeable frozen states, and browser screenshot verification.

This maps to our tasks:

- `WorldlineBuildWorkflow`: borrow the sequencing idea of graph first, roles second, simulation/council third.
- `AgentProfileService`: borrow the idea of deriving personas from graph entities, but materialize our own `user.md`, `soul.md`, and `agent.md` profiles.
- `CouncilRunWorkflow`: borrow the progress and action-log surface, but persist state in PostgreSQL/Temporal rather than files.
- `ReportService`: borrow sectioned report generation and agent-tool chat, but require evidence refs, blocked claims, schema validation, and audit.
- Frontend freeze process: borrow routeable state inventory and browser audit. Do not borrow static product data.

### 1.2 Implementation Shape

MiroFish uses a Flask backend with three API blueprints:

- graph: project and graph build APIs.
- simulation: simulation creation, preparation, run control, logs, posts, actions, timeline, interviews, and history.
- report: report generation, report retrieval, report download, report-agent chat, graph search/statistics tools, and log streams.

Source anchors:

Evidence role: these anchors prove backend app creation, route registration, graph APIs, simulation APIs, report APIs, and tool endpoints.

- `E:\GitHub\ref_prj\MiroFish\backend\app\__init__.py:19`
- `E:\GitHub\ref_prj\MiroFish\backend\app\__init__.py:67`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\graph.py:123`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\graph.py:261`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\graph.py:570`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:166`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:360`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:1452`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:1864`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:1918`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\simulation.py:1987`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\report.py:26`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\report.py:473`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\report.py:936`
- `E:\GitHub\ref_prj\MiroFish\backend\app\api\report.py:984`

Short code-shape snippets:

```python
app.register_blueprint(graph_bp, url_prefix='/api/graph')
app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
app.register_blueprint(report_bp, url_prefix='/api/report')
```

```python
builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
```

```python
run_state = SimulationRunner.start_simulation(
    simulation_id=simulation_id,
    platform=platform,
)
```

CollectiveEventTwin adoption:

- Adopt the API surface split: graph/worldline preparation, run control, timeline/action retrieval, report generation, and report chat should be separate endpoints.
- Do not adopt Flask or file-based state as the production backend path. Our services should remain FastAPI, SQLAlchemy, PostgreSQL, Temporal, and Redis.

### 1.3 Graph Construction And Memory

MiroFish graph building is centered on `GraphBuilderService`. It validates `ZEP_API_KEY`, creates a Zep client, creates an async task, chunks document text, sends batches, waits for Zep processing, and exposes graph data retrieval.

Source anchors:

Evidence role: these anchors prove Zep client setup, graph-build task creation, ontology handling, processing wait, and graph data retrieval.

- `E:\GitHub\ref_prj\MiroFish\backend\app\services\graph_builder.py:40`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\graph_builder.py:54`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\graph_builder.py:210`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\graph_builder.py:393`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\graph_builder.py:426`

Short code-shape snippets:

```python
self.client = Zep(api_key=self.api_key)
self.task_manager = TaskManager()
```

```python
def build_graph_async(
    self,
    text: str,
)
```

CollectiveEventTwin adoption:

- Adopt the explicit graph-build task lifecycle: create task, process raw text, extract ontology/entity/edge candidates, monitor progress, expose graph data.
- Replace Zep dependency with our own first-stage persistence: `source_records`, `extracted_entities`, `entity_mentions`, `case_graph_nodes`, `case_graph_edges`, and `worldline_nodes`.
- If a memory graph provider is later introduced, it must be behind an adapter and never be the only source of truth.

### 1.4 Agent Profile Generation

MiroFish defines `OasisAgentProfile` with identity/persona fields and platform-specific export formats. `OasisProfileGenerator` generates profiles from Zep entities, optionally using LLM prompts, and falls back to rule-based profiles.

Source anchors:

Evidence role: these anchors prove profile data shape, platform export fields, LLM profile generation, fallback generation, batch generation, and profile persistence.

- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:30`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:63`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:91`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:212`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:497`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:851`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\oasis_profile_generator.py:1047`

Short code-shape snippets:

```python
class OasisAgentProfile:
    user_id: int
    persona: str
```

```python
profile["persona"] = self.persona
```

```python
profile_data = self._generate_profile_with_llm(
    entity_name=name,
    entity_type=entity_type,
)
```

CollectiveEventTwin adoption:

- Adopt the entity-to-agent-profile transformation point.
- Our profile format must be richer than OASIS export: `AgentProfile` should persist background, stance, decision logic, risk tolerance, tool permissions, forbidden actions, output schema, event-specific tradeoffs, and generated markdown artifacts.
- Each profile must produce or store `user.md`, `soul.md`, and `agent.md` equivalents before a Council run.
- Do not use random default demographics in production conclusions. Generated attributes must be marked as inferred and constrained by evidence.

### 1.5 Simulation Preparation And Run Logs

MiroFish's `SimulationManager.prepare_simulation` filters entities, generates OASIS profiles, generates simulation config with an LLM, writes profile/config files, and moves the simulation state to ready. `SimulationRunner.start_simulation` loads config, computes total rounds, starts a subprocess, captures logs, and reads platform action logs.

Source anchors:

Evidence role: these anchors prove simulation creation, preparation, profile generation, LLM config generation, config persistence, run start, action retrieval, and timeline aggregation.

- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:194`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:230`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:316`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:393`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:403`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_manager.py:423`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_runner.py:196`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_runner.py:313`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_runner.py:488`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_runner.py:894`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\simulation_runner.py:989`

Short code-shape snippets:

```python
profiles = generator.generate_profiles_from_entities(
    entities=filtered.entities,
    use_llm=use_llm_for_profiles,
)
```

```python
sim_params = config_generator.generate_config(
    simulation_id=simulation_id,
    graph_id=state.graph_id,
)
```

```python
cmd = [sys.executable, script_path, "--config", config_path]
```

```python
actions.sort(key=lambda x: x.timestamp, reverse=True)
```

CollectiveEventTwin adoption:

- Adopt the staged lifecycle: prepare profiles, generate config, run, ingest actions, expose timeline and stats.
- Replace subprocess-driven simulation with Temporal workflow activities. Long-running state must be in workflow history and database rows, not only JSON files.
- Action logs should become persisted `council_messages`, `worldline_events`, `workflow_step_logs`, and `agent_run_events`.

### 1.6 Report Agent And Tool Use

MiroFish's `ReportAgent` has a sectioned report generation process, progress persistence, report assembly, and chat mode. In chat mode, it prepares a system prompt with report context and tool descriptions, limits history, parses tool calls, executes a small number of tools, and returns response plus tool call metadata.

Source anchors:

Evidence role: these anchors prove report-agent construction, sectioned generation, progress updates, outline/section persistence, full report assembly, chat, and log streaming.

- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:865`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1532`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1592`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1621`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1673`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1707`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1794`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:1884`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:2005`
- `E:\GitHub\ref_prj\MiroFish\backend\app\services\report_agent.py:2067`

Short code-shape snippets:

```python
ReportManager.save_outline(report_id, outline)
```

```python
ReportManager.save_section(report_id, section_num, section)
```

```python
tool_calls = self._parse_tool_calls(response)
```

CollectiveEventTwin adoption:

- Adopt sectioned generation and visible progress.
- Adopt limited, explicit tool access for report/council agents.
- Our report agent must enforce structured output, evidence refs, blocked claims, source coverage checks, model/provider audit, third-party review status, and customer-visible synthetic-data disclosure where relevant.
- Do not store production reports only as markdown files. Store report metadata, sections, claims, citations, review status, and exports in PostgreSQL/object storage.

### 1.7 Task Status Pattern

MiroFish provides an in-memory `TaskManager` with status, progress, result, error, metadata, and cleanup.

Source anchors:

Evidence role: these anchors prove task status enum, task payload fields, singleton task store, task creation, task update, and completion/failure helpers.

- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:13`
- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:22`
- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:53`
- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:66`
- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:93`
- `E:\GitHub\ref_prj\MiroFish\backend\app\models\task.py:130`

Short code-shape snippets:

```python
status: TaskStatus
progress: int = 0
```

```python
self._tasks[task_id] = task
```

CollectiveEventTwin adoption:

- Adopt the status fields and progress semantics.
- Do not adopt in-memory task state. Use `tasks`, `workflow_runs`, `workflow_step_logs`, and Temporal execution IDs.

### 1.8 Frontend Page State Inventory And Visual Audit

MiroFish's `ObservePreview.vue` is valuable because each page state is routeable by query key, and the visual audit lists 27 page states with screenshots and viewport constraints.

Source anchors:

Evidence role: these anchors prove routeable preview state, worldline/evidence state arrays, page presets, query synchronization, and simulated state transitions.

- `E:\GitHub\ref_prj\MiroFish\docs\worldline-workbench-pages-visual-audit-2026-04-25.md:1`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\router\index.js:47`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:93`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:123`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:265`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:685`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:942`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:971`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:1176`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:1190`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:1257`
- `E:\GitHub\ref_prj\MiroFish\frontend\src\views\ObservePreview.vue:1267`

Short code-shape snippets:

```js
path: '/observe-preview'
```

```js
home: { menu: 'observe', node: 'current', line: 'C', tab: 'overview', canvas: 'graph' },
```

```js
router.replace({ name: 'ObservePreview', query: { page: id } })
```

CollectiveEventTwin adoption:

- Adopt the frozen-state inventory idea for every customer-facing page: route, state key, expected data, interaction behavior, screenshots, overflow checks, and browser interaction checks.
- Do not adopt frontend-static arrays as product data. In our React app, every state must be hydrated by FastAPI from PostgreSQL or by a persisted workflow/run state.

## 2. worldmonitor-main

### 2.1 Relationship To CollectiveEventTwin

worldmonitor-main is directly relevant to our city situation, multi-source ingestion, source-health, map rendering, and runtime verification direction:

- It is a real-time intelligence dashboard with many independent data sources.
- It separates seed jobs, Redis cache keys, bootstrap hydration, public API boundary, and health checks.
- It has a large map layer registry and deck.gl/MapLibre rendering model.
- It keeps heavy clustering/correlation/ML work in Web Workers.
- It has concrete tests for bootstrap hydration, seed contracts, map-layer executability, runtime fetch behavior, and vector-store behavior.

This maps to our tasks:

- `SourceRegistry` and `SourceHealthService`: borrow seed metadata, status classification, freshness thresholds, record-count checks, and failure-log signatures.
- `CitySituationViewModel`: borrow layered map rendering contracts and layer toggles, but keep business truth in backend materialized view models.
- `DataAcquisitionWorkflow`: borrow seed-lock, atomic publish, validate, freshness metadata, and contract-mode ideas.
- `FrontendRuntime`: borrow fast/slow bootstrap tiers and stale cache fallback as UX concepts, but all customer data still comes from our API/database.
- `Testing`: borrow map-layer matrix tests and bootstrap/seed contract tests.

### 2.2 Implementation Shape

worldmonitor-main is a TypeScript/Vite application with edge API handlers, seed scripts, shared contracts, workers, map components, and extensive tests.

Source anchors:

Evidence role: these anchors prove the architecture overview, API entrypoints, gateway, router, seed utility, map class, panel base class, and analysis/ML workers.

- `E:\GitHub\ref_prj\worldmonitor-main\ARCHITECTURE.md:1`
- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:1`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:1`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:304`
- `E:\GitHub\ref_prj\worldmonitor-main\server\router.ts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:830`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:409`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\Panel.ts:199`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\analysis.worker.ts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:1`

Short code-shape snippets:

```ts
export function createDomainGateway(routes: RouteDescriptor[])
```

```js
const BOOTSTRAP_CACHE_KEYS = {
  earthquakes: 'seismology:earthquakes:v1',
}
```

```ts
export class DeckGLMap {
  private static readonly MAX_CLUSTER_LEAVES = 200;
}
```

CollectiveEventTwin adoption:

- Adopt the production discipline: explicit cache tiers, route/gateway boundaries, health checks, and tests that enforce data-source contracts.
- Do not adopt Vercel Edge or Redis as the product source of truth. Our source of truth is PostgreSQL plus Temporal workflow history; Redis can be a cache/queue accelerator only.

### 2.3 API Gateway, Rate Limit, Cache Tier, And ETag

worldmonitor-main's `createDomainGateway` wraps domain routes with origin checks, CORS, API-key validation, rate limiting, POST-to-GET compatibility, route matching, handler error boundaries, cache headers, CDN cache guards, and ETag generation.

Source anchors:

Evidence role: these anchors prove the shared gateway wrapper, origin/preflight gates, rate limit, route matching, response cache logic, ETag generation, and endpoint policies.

- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:297`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:304`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:379`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:397`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:573`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:589`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:663`
- `E:\GitHub\ref_prj\worldmonitor-main\server\gateway.ts:713`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\rate-limit.ts:73`

Short code-shape snippets:

```ts
const router = createRouter(routes);
```

```ts
const rateLimitResponse = await checkRateLimit(request, corsHeaders);
```

```ts
mergedHeaders.set('ETag', etag);
```

CollectiveEventTwin adoption:

- Adopt one shared API gateway/middleware layer for auth, rate limits, request IDs, cache headers, audit context, and error boundaries.
- Our FastAPI implementation should have middleware and dependency boundaries that produce consistent `request_id`, `actor_id`, `case_id`, `route`, `source`, and `review_context`.
- Do not copy POST-to-GET compatibility unless we explicitly need legacy client support.

### 2.4 Bootstrap Hydration And Cache-Miss Coalescing

worldmonitor-main's `/api/bootstrap` reads named keys in a batch, strips seed-internal envelopes before returning public data, supports fast/slow tiers, and falls back to cached tier data in the frontend. Shared Redis helpers prevent request storms by coalescing concurrent cache misses.

Source anchors:

Evidence role: these anchors prove named bootstrap keys, Redis batch reads, envelope stripping, tier selection, cache headers, miss coalescing, and frontend fast/slow hydration.

- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:8`
- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:212`
- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:221`
- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:244`
- `E:\GitHub\ref_prj\worldmonitor-main\api\bootstrap.js:283`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\redis.ts:247`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\redis.ts:258`
- `E:\GitHub\ref_prj\worldmonitor-main\src\services\bootstrap.ts:110`
- `E:\GitHub\ref_prj\worldmonitor-main\src\services\bootstrap.ts:167`

Short code-shape snippets:

```js
const tier = url.searchParams.get('tier');
```

```js
result.set(keys[i], unwrapEnvelope(parsed).data);
```

```ts
const existing = inflight.get(key);
```

CollectiveEventTwin adoption:

- Adopt fast/slow view-model hydration for expensive city pages: critical counts and map points first, secondary timelines/media/report detail second.
- Adopt cache-miss coalescing for expensive upstream/source or algorithm reads.
- Do not let Redis cached blobs bypass PostgreSQL lineage. Every product record must trace back to database rows and workflow events.

### 2.5 Seed Jobs, Atomic Publish, Freshness Metadata, And Contracts

worldmonitor-main's seed utility wraps data-source jobs with lock acquisition, retry, validation, atomic staging/canonical publish, seed metadata, record-count contracts, zero-data policy, extra keys, graceful fetch failure, SIGTERM cleanup, and verification.

Source anchors:

Evidence role: these anchors prove atomic publish, freshness metadata, seed-meta invariant, run wrapper, lock behavior, publish phase, validation branch, and final metadata write.

- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:223`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:265`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:331`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:830`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:858`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:954`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:1003`
- `E:\GitHub\ref_prj\worldmonitor-main\scripts\_seed-utils.mjs:1077`

Short code-shape snippets:

```js
await redisSet(url, token, stagingKey, payloadValue, 300);
```

```js
await redisCommand(url, token, ['SET', canonicalKey, payload, 'EX', ttlSeconds]);
```

```js
const meta = await writeFreshnessMetadata(
  domain, resource, recordCount, opts.sourceVersion, ttlSeconds
);
```

CollectiveEventTwin adoption:

- Adopt the ingestion job wrapper as a design pattern: source run lock, validation function, record count, freshness metadata, empty-data policy, publish transaction, and verification.
- In our stack, implement this as `DataAcquisitionWorkflow` and database transactions, not Redis-only seed scripts.
- Empty upstream responses must be explicitly classified: valid quiet period, retryable empty, policy-blocked, auth-failed, parse-failed, stale-last-good, or hard failure.

### 2.6 Source Health Classification

worldmonitor-main's health endpoint classifies data keys by data existence, seed metadata, staleness, record count, on-demand behavior, empty-data allowances, cascade coverage, Redis partial failures, and coverage thresholds. It then derives overall health and persists failure signatures.

Source anchors:

Evidence role: these anchors prove seed metadata registry, on-demand and empty-data policies, staleness classification, coverage thresholds, status buckets, and incident signature persistence.

- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:223`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:436`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:496`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:544`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:582`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:608`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:624`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:636`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:734`
- `E:\GitHub\ref_prj\worldmonitor-main\api\health.js:767`

Short code-shape snippets:

```js
else if (seedStale === true) status = 'STALE_SEED';
```

```js
else if (records < seedCfg.minRecordCount) status = 'COVERAGE_PARTIAL';
```

```js
const sig = `${overall}|${sigKeys.join(',')}`;
```

CollectiveEventTwin adoption:

- Adopt the status vocabulary style, but adapt it to our domain: `OK`, `STALE`, `EMPTY_VALID`, `EMPTY_ERROR`, `POLICY_BLOCKED`, `AUTH_FAILED`, `PARSE_FAILED`, `COVERAGE_PARTIAL`, `REVIEW_REQUIRED`, `UNHEALTHY`.
- Expose this in admin/source operations and in customer-facing data-source badges where appropriate.
- Store health snapshots and incident signatures in PostgreSQL so audit and customer reports can cite data freshness.

### 2.7 Map Layers, Clustering, And City Situation Rendering

worldmonitor-main's `DeckGLMap` builds layers from a central state object and data arrays, uses MapLibre plus deck.gl layers, filters datasets by time, adds empty ghost layers for stable toggles, uses supercluster for protests and other dense layers, and warns when layer rebuild exceeds a frame budget.

Source anchors:

Evidence role: these anchors prove deck.gl imports, map class, supercluster setup, layer construction, performance warning, layer setting, toggling, and layer registry sanitization.

- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:8`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:57`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:409`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:1139`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:1500`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:1743`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:1939`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:1942`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:5537`
- `E:\GitHub\ref_prj\worldmonitor-main\src\components\DeckGLMap.ts:6627`
- `E:\GitHub\ref_prj\worldmonitor-main\src\config\map-layer-definitions.ts:165`

Short code-shape snippets:

```ts
const layers: (Layer | null | false)[] = [];
```

```ts
this.protestSC = new Supercluster({
  radius: 60,
  maxZoom: 14,
});
```

```ts
this.deckOverlay?.setProps({ layers: this.buildLayers() });
```

CollectiveEventTwin adoption:

- Adopt layer contracts, stable toggles, clustering, render-performance warnings, and tests that prove a layer can actually render in the selected map mode.
- Our city page should use backend view models such as `event_points`, `h3_heat_cells`, `administrative_heat`, `source_health`, `timeline_buckets`, and `media_markers`.
- Do not let deck.gl/MapLibre calculate business scores. They render backend-calculated view models.

### 2.8 Workers, Clustering, Correlation, ML, And Client-Side Vector Store

worldmonitor-main pushes heavy clustering/correlation to workers. `analysis.worker.ts` calls shared clustering/correlation core logic and maintains duplicate-signal state. `ml.worker.ts` handles embeddings, summarization, sentiment, NER, semantic clustering, vector-store ingest/search, and model loading. `vector-db.ts` stores client-side vectors in IndexedDB with capped retention.

Source anchors:

Evidence role: these anchors prove worker message contracts, clustering/correlation delegation, embedding/summarization/sentiment/NER functions, semantic clustering, IndexedDB storage, and vector search.

- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\analysis.worker.ts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\analysis.worker.ts:74`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\analysis.worker.ts:93`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:184`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:196`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:217`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:243`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\ml.worker.ts:300`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\vector-db.ts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\vector-db.ts:54`
- `E:\GitHub\ref_prj\worldmonitor-main\src\workers\vector-db.ts:118`

Short code-shape snippets:

```ts
const clusters = clusterNewsCore(items, getSourceTier);
```

```ts
const similarity = cosineSimilarity(embeddingI, embeddingJ);
```

```ts
store.put({
  id,
  text: clean,
  embedding: entry.embedding,
});
```

CollectiveEventTwin adoption:

- Adopt the separation between shared algorithm core and worker/runtime wrapper.
- In our production system, core clustering, entity extraction, risk scoring, worldline branching, and report validation should run in backend services/workers, not browser-only workers.
- Browser workers are acceptable for UI-only performance work such as local layout filtering or non-authoritative visualization, but not for persisted conclusions.

### 2.9 LLM Gateway And Brief Enrichment

worldmonitor-main implements a provider chain for LLM calls, prompt sanitization, optional response validation, thinking-tag stripping, provider health checks, and streaming fallback. Its brief helpers constrain editorial outputs and parse/validate response shape.

Source anchors:

Evidence role: these anchors prove provider chain definition, call wrappers, streaming/non-streaming calls, thinking-tag stripping, validation hook, and brief response validation.

- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:105`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:127`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:153`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:194`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:198`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:360`
- `E:\GitHub\ref_prj\worldmonitor-main\server\_shared\llm.ts:448`
- `E:\GitHub\ref_prj\worldmonitor-main\shared\brief-llm-core.js:52`
- `E:\GitHub\ref_prj\worldmonitor-main\shared\brief-llm-core.js:137`

Short code-shape snippets:

```ts
const PROVIDER_CHAIN = ['ollama', 'groq', 'openrouter', 'generic'] as const;
```

```ts
if (validate && !validate(content)) {
  console.warn(`[llm:${providerName}] validate() rejected response, trying next`);
}
```

```js
// Parse + validate the LLM response into a single editorial sentence.
```

CollectiveEventTwin adoption:

- Adopt provider-chain normalization, health gate, prompt sanitization, and validation hooks.
- Our LLM runtime must additionally record prompt version, model, provider, token/cost metadata, evidence refs, blocked claims, reviewer state, and output schema validation errors.
- Do not allow silent fallback to produce a formal product conclusion. Failed provider/output validation should be visible in task and review state.

### 2.10 Testing Practices

worldmonitor-main has targeted tests that enforce implementation contracts rather than only high-level smoke behavior. The map-layer executable test is especially relevant to our design drift and frontend interaction problem because it locks the truth table of layer capability versus renderer state.

Source anchors:

Evidence role: these anchors prove map-layer executable matrix tests, bootstrap tests, seed utility tests, envelope/empty-data tests, runtime fetch E2E, and vector-store E2E.

- `E:\GitHub\ref_prj\worldmonitor-main\tests\map-layer-executable.test.mts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\tests\bootstrap.test.mjs:1`
- `E:\GitHub\ref_prj\worldmonitor-main\tests\seed-utils.test.mjs:1`
- `E:\GitHub\ref_prj\worldmonitor-main\tests\seed-utils-envelope-reads.test.mjs:1`
- `E:\GitHub\ref_prj\worldmonitor-main\tests\seed-utils-empty-data-failure.test.mjs:1`
- `E:\GitHub\ref_prj\worldmonitor-main\e2e\runtime-fetch.spec.ts:1`
- `E:\GitHub\ref_prj\worldmonitor-main\e2e\rag-vector-store.spec.ts:1`

Short code-shape snippets:

```ts
assert.equal(isLayerExecutable('storageFacilities', 'flat', true), true);
```

```ts
assert.equal(isLayerExecutable('nonexistentLayer', 'flat', true), false);
```

CollectiveEventTwin adoption:

- Adopt contract tests for every source channel, every page interaction API, every map layer, every workflow transition, and every Agent output schema.
- For each feature iteration, run a test-agent pass for functional tests, performance tests, and browser interaction verification.
- Browser tests must verify page interactions actually hit backend APIs and update or read persisted state.

## 3. Combined Impact On CollectiveEventTwin Development

### 3.1 New Task-Level Implications

These local references add concrete tasks to the existing plan:

1. Add `SourceRunHealth` model and API statuses inspired by worldmonitor health classification.
2. Add `SourceRunContract` validation per channel: expected record count, freshness threshold, empty-data policy, and publish verification.
3. Add `DataAcquisitionWorkflow` lock and publish semantics using PostgreSQL transactions plus Redis/Temporal where useful.
4. Add `WorldlineStakeholderDiscovery` after graph construction and before Council profile generation.
5. Add `AgentProfileMaterializer` that creates persisted `user.md`, `soul.md`, and `agent.md` artifacts for discovered stakeholders.
6. Add `CouncilRunEventLog` and `CouncilTimeline` endpoints modeled after simulation actions/timeline, but persisted in database.
7. Add `ReportClaimValidator` before report freeze: evidence refs required, unsupported claims blocked.
8. Add `PageStateInventory` for each customer-facing route, following MiroFish's routeable frozen-state pattern.
9. Add `MapLayerContractTest` so frontend layer toggles cannot enter impossible states.
10. Add `SourceBootstrapViewModel` fast/slow API split for city page and later evidence/worldline pages.

### 3.2 Explicit Non-Adoption Boundaries

- No frontend static arrays as runtime product data.
- No file-only simulation state for production workflows.
- No Redis-only canonical product state.
- No browser-worker-only authoritative algorithms.
- No Zep/OASIS/worldmonitor/MiroFish runtime dependency without a separate architecture decision.
- No App/private-platform scraping pattern promoted into production without explicit legal/business approval.
- No report/Agent output accepted without schema validation, evidence refs, blocked-claim handling, audit, and third-party review.

### 3.3 Priority Borrowing Order

P0 production spine should borrow in this order:

1. worldmonitor seed/health contract ideas for source acquisition reliability.
2. MiroFish graph-to-profile-to-run-to-report sequencing for worldline and Council.
3. worldmonitor map-layer contract tests for city page map interactions.
4. MiroFish visual-state inventory for page freeze.
5. worldmonitor LLM gateway validation/fallback discipline for our LLM runtime.
6. MiroFish report-agent sectioned generation for customer reports.

## 4. Verification Checklist For This Study

- Both local paths exist.
- Neither provided local path contains `.git`; treat as local snapshot, not clean repository inventory.
- Each project section states relevance, implementation shape, source anchors, code-shape snippets, and adoption boundaries.
- Source anchors are absolute local paths with line numbers.
- Original 69-repository radar count remains unchanged.
- Third-party review is required before treating this document as accepted.
