# CollectiveEventTwin Open-Source Radar Source Study

Date: 2026-05-09

Status: local source-level research index complete for the current technical radar. This document records downloaded repositories, source anchors, first-pass lessons, and adoption boundaries. It does not approve dependencies by itself.

Research root:

```text
E:\GitHub\ref_prj
```

## 1. Current Result

- The 67 GitHub repositories listed in `docs/technical-reference-open-source-solution-landscape-20260508.md` have been shallow-cloned outside the product repository.
- Two supplemental repositories were added because they are directly relevant to implementation: `agency-agents-zh` for Agent persona/profile grammar, and `temporal-sdk-python` for Python workflow implementation patterns.
- Final verification result: 69 local Git repositories, 0 dirty working trees.
- Heavy repositories use shallow plus sparse checkout, with business-relevant source directories fetched: `airbyte`, `airflow`, `dagster`, `fiftyone`, `grafana`, `opencti`, `OpenSearch`, `seatunnel`, `redpanda`, `pulsar`, and `materialize`.
- These repositories are references, not product runtime truth. CollectiveEventTwin's own persistence, audit, evidence boundary, privacy policy, workflow state, and third-party review gates remain the final authority.
- Source-level deep-dive documents are under `docs/source-studies/`: data ingestion, workflow/Agent/LLM, search/graph/geospatial, and multimedia/policy/quality/observability.
- Additional local reference snapshots provided after the original radar study are documented separately in `docs/source-studies/05-local-reference-projects.md`: `E:\GitHub\ref_prj\MiroFish` and `E:\GitHub\ref_prj\worldmonitor-main`. They are not included in the 69 clean Git repository count.

## 2. Download Inventory

| Area | Repo | Local folder | Branch | Commit | Mode | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Data ingestion | Airbyte | `airbyte` | `master` | `2ea285b` | shallow+sparse | downloaded |
| Data ingestion | Meltano | `meltano` | `main` | `35de4f9` | shallow | downloaded |
| Data ingestion | dlt | `dlt` | `devel` | `9ee723f` | shallow | downloaded |
| Data ingestion | SeaTunnel | `seatunnel` | `dev` | `5fb34bc` | shallow+sparse | downloaded |
| Data ingestion | Bytewax | `bytewax` | `main` | `cf75e0a` | shallow | downloaded |
| Realtime stream | Redpanda | `redpanda` | `dev` | `c1e4a0f` | shallow+sparse | downloaded |
| Realtime stream | Pulsar | `pulsar` | `master` | `6d42559` | shallow+sparse | downloaded |
| Streaming SQL | Materialize | `materialize` | `main` | `46f6f15` | shallow+sparse | downloaded |
| Public web | Scrapling | `scrapling` | `main` | `07e0c1c` | shallow | downloaded |
| Public web | Crawlee Python | `crawlee-python` | `master` | `6a1995e` | shallow | downloaded |
| Public web / app POC | MediaCrawler | `MediaCrawler` | `main` | `f328ee3` | shallow | downloaded |
| Hotlist / public entry | TrendRadar | `TrendRadar` | `master` | `b109701` | shallow | downloaded |
| News extraction | NewsCrawler | `NewsCrawler` | `main` | `7495d2f` | shallow | downloaded |
| RSS / route catalog | RSSHub | `RSSHub` | `master` | `0b2b8e0` | shallow | downloaded |
| News aggregation | newsnow | `newsnow` | `main` | `625bf04` | shallow | downloaded |
| Workflow | Temporal server | `temporal` | `main` | `b5af882` | shallow | downloaded |
| Workflow | Temporal Python SDK | `temporal-sdk-python` | `main` | `a161d18` | shallow | downloaded |
| Workflow | Hatchet | `hatchet` | `main` | `0b96f06` | shallow | downloaded |
| Workflow / data asset | Dagster | `dagster` | `master` | `229b92e` | shallow+sparse | downloaded |
| Workflow / data asset | Prefect | `prefect` | `main` | `26aaf5c` | shallow | downloaded |
| Workflow / scheduler | Airflow | `airflow` | `main` | `aeb692f` | shallow+sparse | downloaded |
| Agent workflow | LangGraph | `langgraph` | `main` | `398d6cc` | shallow | downloaded |
| Agent framework | AutoGen | `autogen` | `main` | `027ecf0` | shallow | downloaded |
| Agent framework | CrewAI | `crewAI` | `main` | `cf2fb45` | shallow | downloaded |
| Agent persona grammar | agency-agents-zh | `agency-agents-zh` | `main` | `e5b0c77` | shallow | downloaded |
| LLM gateway | LiteLLM | `litellm` | `litellm_internal_staging` | `98cd057` | shallow | downloaded |
| Structured output | Instructor | `instructor` | `main` | `3f1d6dd` | shallow | downloaded |
| Guardrails | Guardrails | `guardrails` | `main` | `379ab72` | shallow | downloaded |
| Search/vector | pgvector | `pgvector` | `master` | `d238409` | shallow | downloaded |
| Search | OpenSearch | `OpenSearch` | `main` | `139b9f9f` | shallow+sparse | downloaded |
| Vector DB | Qdrant | `qdrant` | `master` | `fd6746e` | shallow | downloaded |
| RAG | LlamaIndex | `llama_index` | `main` | `79cddb5` | shallow | downloaded |
| RAG | Haystack | `haystack` | `main` | `9856dee` | shallow | downloaded |
| Search | Typesense | `typesense` | `v31` | `66b936a` | shallow | downloaded |
| Temporal graph | Graphiti | `graphiti` | `main` | `c427615` | shallow | downloaded |
| Graph builder | Neo4j LLM Graph Builder | `llm-graph-builder` | `main` | `61121df` | shallow | downloaded |
| Graph algorithms | NetworkX | `networkx` | `main` | `4857d9a` | shallow | downloaded |
| PostgreSQL graph extension | Apache AGE | `age` | `master` | `a1b749a` | shallow | downloaded |
| Intel model | OpenCTI | `opencti` | `master` | `60b1fe8` | shallow+sparse | downloaded |
| Intel model | MISP | `MISP` | `2.5` | `2b3d843` | shallow | downloaded |
| Case management | TheHive | `TheHive` | `main` | `d390a03` | shallow | downloaded |
| Case management | DFIR-IRIS | `iris-web` | `master` | `a4bfeda` | shallow | downloaded |
| Crisis map / reports | Ushahidi | `ushahidi-platform` | `develop` | `6f20265` | shallow | downloaded |
| Geospatial DB | PostGIS | `postgis` | `master` | `f3f8329` | shallow | downloaded |
| Map rendering | MapLibre GL JS | `maplibre-gl-js` | `main` | `aebdabf` | shallow | downloaded |
| Large visual layers | deck.gl | `deck.gl` | `master` | `2698434` | shallow | downloaded |
| Spatial index | H3 | `h3` | `master` | `69e01f3` | shallow | downloaded |
| Geo helpers | Turf | `turf` | `master` | `d31e636` | shallow | downloaded |
| Vector tiles | Tippecanoe | `tippecanoe` | `master` | `b677e36` | shallow | downloaded |
| CV post-processing | supervision | `supervision` | `develop` | `2beeda7` | shallow | downloaded |
| Object detection | Ultralytics | `ultralytics` | `main` | `20b7e73` | shallow | downloaded |
| Object detection | RF-DETR | `rf-detr` | `develop` | `b95246f` | shallow | downloaded |
| OCR | PaddleOCR | `PaddleOCR` | `main` | `f0d83fa` | shallow | downloaded |
| ASR | FunASR | `FunASR` | `main` | `b842ff8` | shallow | downloaded |
| ASR alignment | WhisperX | `whisperX` | `main` | `1c4b23e` | shallow | downloaded |
| Vision dataset review | FiftyOne | `fiftyone` | `develop` | `0e320d4` | shallow+sparse | downloaded |
| Privacy | Presidio | `presidio` | `main` | `35f95a3` | shallow | downloaded |
| Policy engine | OPA | `opa` | `main` | `cb54e9c` | shallow | downloaded |
| Authorization | OpenFGA | `openfga` | `main` | `744448e` | shallow | downloaded |
| Authorization | Casbin | `casbin` | `master` | `12ac0c9` | shallow | downloaded |
| LLM observability | Langfuse | `langfuse` | `main` | `9259f78` | shallow | downloaded |
| LLM observability | Phoenix | `phoenix` | `main` | `49aa752` | shallow | downloaded |
| LLM eval | DeepEval | `deepeval` | `main` | `550ea1b` | shallow | downloaded |
| RAG eval | Ragas | `ragas` | `main` | `298b682` | shallow | downloaded |
| Prompt / Agent eval | promptfoo | `promptfoo` | `main` | `2b5db89` | shallow | downloaded |
| Data quality | Great Expectations | `great_expectations` | `develop` | `b77da1f` | shallow | downloaded |
| Ops dashboard | Grafana | `grafana` | `main` | `25c9e015` | shallow+sparse | downloaded |
| BI / internal analytics | Superset | `superset` | `master` | `5bde867` | shallow | downloaded |
| SQL report UI | Evidence | `evidence` | `main` | `bdf2ce1` | shallow | downloaded |

## 3. Source Anchors By Product Area

| CollectiveEventTwin Area | Local Source Anchors | Borrow | Do Not Borrow |
| --- | --- | --- | --- |
| Channel-level data collection | `scrapling/scrapling/fetchers`, `scrapling/scrapling/engines`, `crawlee-python/src/crawlee/crawlers`, `crawlee-python/src/crawlee/storages` | Separate static fetch, browser fetch, request context, retry, parser, run state, and storage client interfaces | Do not let crawler objects become product domain objects |
| Connector registry and schema evolution | `airbyte/airbyte-cdk/python`, `airbyte/airbyte-integrations/connectors/source-file`, `airbyte/airbyte-integrations/connectors/source-faker`, `airbyte/connector-writer`, `meltano/src/meltano/core/plugin*`, `dlt/dlt`, `seatunnel/seatunnel-api`, `seatunnel/seatunnel-connectors-v2` | Connector contract, source specs, config validation, incremental state, acceptance tests, schema inference, transform boundaries | Do not introduce full Airbyte/Meltano/SeaTunnel platforms into P0 |
| Public hotlist/news/RSS entry | `TrendRadar/trendradar/crawler`, `TrendRadar/trendradar/storage`, `TrendRadar/trendradar/ai`, `RSSHub/lib/routes`, `RSSHub/lib/middleware`, `NewsCrawler/news_crawler`, `NewsCrawler/news_extractor_core`, `NewsCrawler/video_crawler`, `newsnow/server`, `newsnow/src`, `newsnow/shared` | Channel-specific handlers, route catalog, extraction pipeline, storage schema, MCP-style tool wrapper ideas | Do not use hidden account/cookie pools or private App reverse engineering |
| App platform field POC | `MediaCrawler/media_platform`, `MediaCrawler/base`, `MediaCrawler/store`, `MediaCrawler/proxy` | Understand field availability, failure modes, and adapter separation for risk assessment | Do not put App scraping into the production main path without explicit legal/business approval |
| Stream/backfill patterns | `bytewax/pysrc/bytewax`, `bytewax/src`, `bytewax/examples`, `redpanda/src`, `redpanda/proto`, `pulsar/pulsar-broker`, `pulsar/pulsar-client`, `pulsar/pulsar-functions`, `pulsar/pulsar-io`, `materialize/src`, `materialize/test` | Dataflow, recovery, connectors, metrics, replayable examples, streaming broker/service boundaries, streaming SQL ideas | Do not add streaming infrastructure before batch/workflow paths are reliable |
| Durable workflows | `temporal-sdk-python/temporalio/workflow.py`, `temporal-sdk-python/temporalio/worker`, `temporal-sdk-python/temporalio/client.py`, `temporal-sdk-python/temporalio/testing`, `temporal/service/history`, `temporal/common` | Workflow/activity boundary, worker lifecycle, replay safety, testing harness, history-driven recovery | Do not replace Temporal with a second orchestrator in P0 |
| Workflow alternatives | `hatchet/pkg/worker`, `hatchet/cmd/hatchet-cli/cli`, `dagster/python_modules/dagster/dagster`, `prefect/src/prefect`, `airflow/airflow-core/src/airflow` | Worker/task UX, run status, DAG display, asset/backfill language, operational visibility | Do not mix multiple workflow engines for the same production chain |
| Agent profile and council grammar | `agency-agents-zh/*/*.md`, `agency-agents-zh/CATALOG.md`, `agency-agents-zh/AGENT-LIST.md`, `langgraph/libs/langgraph`, `autogen/python`, `crewAI/lib/crewai` | Profile front matter, identity, memory, mission, mandatory workflow, deliverables, role/team patterns, state graph ideas | Do not make Agent output a fact source; Agent can only reason over evidence |
| LLM gateway and validation | `litellm/litellm`, `instructor/instructor`, `guardrails/guardrails` | Provider normalization, retries, fallback visibility, cost accounting, Pydantic-style structured output, guardrail validation | Do not silently fallback into a formal conclusion after model/output failure |
| Search and RAG | `pgvector/sql`, `pgvector/src`, `OpenSearch/server`, `qdrant/lib/segment`, `llama_index/llama-index-core`, `haystack/haystack`, `typesense/src` | Postgres vector usage, hybrid search ideas, retriever/reranker/citation pipeline, filterable vector search concepts | Do not introduce OpenSearch/Qdrant/Typesense before PostgreSQL FTS plus pgvector limits are proven |
| Temporal graph and case intelligence | `graphiti/graphiti_core`, `llm-graph-builder/backend`, `llm-graph-builder/frontend`, `networkx/networkx/algorithms`, `age/src`, `opencti/opencti-platform/opencti-graphql`, `MISP/app`, `TheHive/app`, `iris-web/source`, `ushahidi-platform/app` | Actor/evidence/relation models, confidence/source/TLP-like fields, case/observable/task/audit language, graph algorithms, map report concepts | Do not require Neo4j/AGE/OpenCTI/MISP/TheHive as P0 runtime dependencies |
| Geospatial and heat maps | `postgis/extensions`, `postgis/liblwgeom`, `h3/src/h3lib/lib`, `turf/packages`, `tippecanoe`, `maplibre-gl-js/src`, `deck.gl/modules` | Backend spatial truth, H3 aggregation, vector tiles, frontend map layers, large point/heat rendering | Do not let the map SDK compute business truth |
| Multimedia evidence | `supervision/src/supervision/detection`, `supervision/src/supervision/annotators`, `ultralytics/ultralytics`, `rf-detr/src`, `PaddleOCR/tools/infer`, `FunASR/funasr`, `whisperX/whisperx`, `fiftyone/fiftyone` | Detection result schema, boxes/masks, annotation/redaction artifacts, OCR/ASR wrappers, timestamps, dataset review workflow | Do not let OCR/ASR/CV output become unreviewed factual conclusion |
| Privacy and policy | `presidio/presidio-analyzer`, `presidio/presidio-anonymizer`, `presidio/presidio-image-redactor`, `openfga/pkg/typesystem`, `opa/rego`, `opa/topdown`, `casbin/enforcer.go` | Analyzer/anonymizer split, redaction operator, relationship authorization, policy evaluation, RBAC/ABAC ideas | Do not expose raw sensitive evidence without policy, audit, and redaction checks |
| Evaluation and observability | `promptfoo/src/assertions`, `promptfoo/src/redteam`, `deepeval/deepeval`, `ragas/src`, `phoenix/src`, `langfuse/packages`, `great_expectations/great_expectations`, `grafana/pkg`, `superset/superset`, `evidence/packages`, `evidence/sites` | Prompt/Agent regression tests, RAG metrics, trace/replay, data quality expectations, admin observability dashboards, SQL-backed report UI patterns | Do not use BI dashboards as a replacement for the customer-facing product UX |

## 4. First-Pass Implementation Lessons

### 4.1 Data Collection

- Implement our own `SourceAdapter` interface and keep adapters channel-specific: `public_web`, `rss`, `news_site`, `synthetic_scenario`, `media_file`, `manual_upload`, and later authorized third-party feeds.
- Every collection run must persist `collection_runs`, step logs, source policy decisions, failure reason, retry counters, input hash, output raw record ids, and audit logs.
- Synthetic data is a source channel, not a frontend fixture. It must start as raw records and pass through the same cleaning, extraction, evidence, signal, worldline, council, report, and review gates.
- Public web/news/RSS can borrow Crawlee/Scrapling/RSSHub/TrendRadar/NewsCrawler patterns. App-platform crawlers remain POC references only unless explicitly promoted.

### 4.2 Workflow And Backend Algorithms

- Temporal remains the production workflow owner. The Python SDK source is the primary implementation reference for `apps/worker` workflows and activities.
- Dagster/Prefect/Airflow/Hatchet are pattern references for run status, visibility, backfill language, and worker UX, not P0 engines.
- Algorithm tasks must be real backend code: deduplication, entity extraction, quality gates, evidence scoring, risk factor generation, geospatial aggregation, graph ranking, worldline branching, and report consistency checks.

### 4.3 Agent And LLM Runtime

- Product runtime Agents should use a project-owned `AgentProfile` model plus file materialization equivalent to `user.md`, `soul.md`, and `agent.md`.
- `agency-agents-zh` provides a useful profile grammar: front matter, identity, memory, mission, mandatory workflow, rules, output artifacts, and failure behavior.
- OpenClaw/Codex workflow material is process inspiration only. Product runtime Agent behavior must be implemented inside CollectiveEventTwin, persisted in the database, audited, versioned, and tested.
- Each Agent claim must bind to `evidence_refs`; unsupported claims go to `blocked_claims`; schema validation failure blocks formal conclusion.

### 4.4 Search, Graph, And Worldline

- P0 should start with PostgreSQL FTS plus pgvector. OpenSearch, Qdrant, Typesense, Neo4j/AGE, and OpenCTI-style intelligence platforms remain later-stage or POC candidates.
- NetworkX is enough for first-pass graph algorithms: connected components, centrality, shortest paths, influence approximation, clustering, and role/stakeholder discovery.
- Worldline graph state should remain queryable from PostgreSQL with explicit node/edge/evidence lineage before introducing a specialized graph database.

### 4.5 Multimedia Evidence

- Video, live stream, image, screenshot, OCR, ASR, and CV outputs should enter a `MediaAnalysisWorkflow`, not an API request path.
- Each media-derived artifact needs source record id, media asset id, timestamp/range, region/bounding box where relevant, model/version, confidence, redaction status, and reviewer state.
- High-risk media conclusions must default to `needs_review`; the UI may show extracted evidence, but cannot treat it as final truth without review.

### 4.6 Geospatial Product Boundary

- Backend creates the city situation view model: event points, administrative aggregations, H3 cells, heat score, confidence, time window, and evidence counts.
- MapLibre/deck.gl are rendering technologies. H3/PostGIS/Turf patterns inform spatial computation, but business truth stays in backend services and persisted view models.

### 4.7 Quality, Security, And Third-Party Review

- Great Expectations-like validation result objects fit our `data_quality_checks` and downstream blocker model.
- Presidio-like analyzer/anonymizer separation should become `SensitiveInfoDetector` and `RedactionService`.
- OpenFGA/OPA/Casbin are references for later authorization/policy evolution; P0 should implement internal RBAC, source policy, redaction policy, and audit logs first.
- promptfoo/DeepEval/Ragas/Phoenix/Langfuse patterns should inform Agent/LLM regression testing, trace replay, and evidence-citation metrics.
- Every feature freeze requires a third-party review record; implementer self-review is not enough.

## 5. Adoption Boundary

| Decision | Boundary |
| --- | --- |
| SourceAdapter | Borrow connector and crawler separation patterns, but implement our own adapter contract, raw record storage, source policy, and audit model |
| Data platform tools | Use Airbyte/Meltano/dlt/SeaTunnel as source references; do not introduce full platforms into P0 without explicit architecture decision |
| Temporal | Use Temporal plus Python SDK as production workflow path |
| Agent runtime | Borrow Agent profile grammar and state graph ideas; implement CollectiveEventTwin-owned Agent profiles, prompts, schemas, LLM provider, guardrails, and evaluation |
| LLM output | Use schema validation and guardrails before product persistence; failure remains visible |
| Search | P0 uses PostgreSQL FTS plus pgvector; external search/vector stores require later promotion |
| Graph | P0 uses PostgreSQL relations/JSONB plus NetworkX algorithms; graph database is optional later evolution |
| Multimedia | Use media workflows and artifacts; OCR/ASR/CV outputs require confidence, lineage, redaction, and review |
| Geospatial | Backend is source of truth; map layers are view models |
| Compliance | Use internal RBAC/source policy/redaction/audit first; OpenFGA/OPA/Casbin are evolution references |
| Observability / BI | Use Grafana/Superset as internal operations references only; they do not replace product pages |

## 6. Rule For Future Feature Work

Before implementing any feature in these technical areas, the responsible implementation pass must:

1. Open the corresponding local reference repository.
2. Inspect the source anchors listed above.
3. State which pattern is being borrowed.
4. State which parts are intentionally not adopted.
5. Keep CollectiveEventTwin's production contracts, persistence, audit, evidence boundary, compliance boundary, and third-party review gates as the final authority.

This rule applies to implementation agents, reviewer agents, and testing agents.
