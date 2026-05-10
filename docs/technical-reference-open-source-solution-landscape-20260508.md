# CollectiveEventTwin 开源技术方案参考雷达

Date: 2026-05-08

Status: 技术参考，不等于选型决策

## 1. 背景

CollectiveEventTwin 的核心链路是：

```text
数据获取
-> 原始数据治理
-> 信号/证据/因子抽取
-> 主线建模
-> 世界状态与世界线推演
-> Agent Council
-> 报告/任务/审计
-> 案例沉淀
```

这不是单一爬虫、单一地图、单一 LLM Agent 或单一 BI 看板能解决的问题。更合理的技术策略是：保持当前生产骨架，按技术域吸收成熟开源项目的模式。

当前项目已确定的主栈方向：

- Web: React + TypeScript + Vite + TanStack Router/Query。
- API: FastAPI + Pydantic + SQLAlchemy。
- Database: PostgreSQL + JSONB + pgvector。
- Workflow: Temporal。
- Cache / queue assist: Redis。
- Product rule: 所有产品数据必须从 PostgreSQL 经 FastAPI 返回，运行时不依赖 mock。

## 2. 推荐技术雷达

### Adopt：可直接贴近当前架构

| 技术域 | 推荐方向 | 可借鉴项目 | 用法 |
| --- | --- | --- | --- |
| 工作流编排 | Durable workflow | Temporal | 已在项目方向内，继续强化 activities、idempotency、audit |
| 向量检索 | PostgreSQL 内嵌向量 | pgvector | P0 先用 pgvector，避免过早引入独立向量库 |
| LLM 输出约束 | Typed structured output | Instructor / Guardrails | Agent Council 输出 schema、evidence refs、blocked claims |
| LLM 网关 | Provider abstraction | LiteLLM | 后续多 provider、cost、timeout、retry、fallback |
| 公开 Web 采集 | 公网页面采集器 | Scrapling / Crawlee | 只处理 `public_web`，不做登录绕过 |
| 视觉证据后处理 | CV post-processing | supervision | 视频/图像证据处理工具层，不是模型本身 |
| 隐私识别 | PII detection/anonymization | Presidio | 文本/图片敏感信息检测与脱敏参考 |

### Trial：适合做 POC

| 技术域 | 候选项目 | POC 目标 |
| --- | --- | --- |
| 热点/舆情入口 | TrendRadar / RSSHub / newsnow | 热榜、关键词、公开订阅源、城市态势入口 |
| 新闻/公开文章采集 | NewsCrawler | 今日头条、公众号、新闻站点公开内容结构化 |
| App 平台能力边界 | MediaCrawler | 验证抖音/快手/小红书/B站字段可得性，不接生产链路 |
| RAG/案例库 | LlamaIndex / Haystack | 案例库、证据库、前兆库的检索和引用链 |
| 知识图谱 | Graphiti / Neo4j LLM Graph Builder | 时间化事件、主体、证据、关系抽取模式 |
| 地理态势 | MapLibre / deck.gl / H3 / Turf | 热力、聚合、空间索引、传播路径可视化 |
| OCR/ASR | PaddleOCR / FunASR / WhisperX | 短视频 OCR、直播/录屏 ASR、证据转写 |
| LLM 评测 | promptfoo / DeepEval / Ragas / Phoenix / Langfuse | Agent 输出稳定性、RAG 质量、证据引用率、追踪 |
| 数据质量 | Great Expectations | raw_records、source_records、signals 的字段质量门禁 |

### Watch：作为架构模式参考

| 技术域 | 候选项目 | 可借鉴点 |
| --- | --- | --- |
| 数据集成平台 | Airbyte / Meltano / dlt / SeaTunnel | connector registry、run state、schema evolution、failure counters |
| 数据编排 | Dagster / Prefect / Airflow | data asset、backfill、retry、observability；但 P0 不建议替代 Temporal |
| OSINT / 事件情报 | OpenCTI / MISP | 情报对象模型、关系图、confidence、source、sharing、taxonomy |
| 危机地图 | Ushahidi | 众包上报、地图态势、事件验证、公开反馈流 |
| 事件/案件管理 | TheHive / DFIR-IRIS | Case、Observable、Task、Audit、collaboration 模式 |
| 实时流 | Redpanda / Pulsar / Materialize / Bytewax | 后续高吞吐实时源、流式聚合和增量态势 |
| BI/运营看板 | Grafana / Superset / Evidence | 内部运营/审计报表，不替代产品主界面 |

### Avoid / 不进入生产主链路

| 类型 | 原因 |
| --- | --- |
| Cookie 池、多账号池、验证码绕过、App 私有接口逆向 | 合规、稳定性、审计不可控 |
| 把开源 App 爬虫作为生产承诺 | 平台风控变化快，授权边界不清 |
| Agent 模拟真人刷 App 获取数据 | 本质仍是浏览器自动化绕平台边界 |
| 让 Agent 直接产出事实结论 | Agent 只能解释证据，不是事实来源 |
| 过早引入多套编排系统 | Temporal、Airflow、Dagster、Prefect 并存会提高复杂度 |
| 用 BI 工具替代产品体验 | 本项目需要证据链和业务动作闭环，不是通用仪表盘 |

## 3. 技术域展开

### 3.1 数据获取与 SourceAdapter

项目可能遇到的问题：

- 多平台数据源异构。
- 授权模式不同。
- 抓取失败原因复杂。
- 字段结构经常变化。
- 原始数据需要去重、脱敏、留痕和可回放。

可借鉴：

- Airbyte: connector catalog、source/destination 抽象、sync job 状态。
- Meltano: code-first 数据集成项目组织方式。
- dlt: Python data loading、schema inference、incremental loading。
- Scrapling / Crawlee: public web 的 fetcher、browser、retry、proxy、selector 模式。
- TrendRadar / RSSHub / NewsCrawler: 低风险热点、RSS、新闻和公开文章入口。
- MediaCrawler: 仅作为 App 平台字段可得性和失败类型 POC。

建议在项目里坚持：

```text
SourceAdapter
-> CollectionRunService
-> RawRecordNormalizer
-> SourcePolicyService
-> raw_records
```

所有 adapter 都必须写入 run counters、failure reason、input hash、source policy decision、audit logs。

### 3.2 工作流与异步任务

项目可能遇到的问题：

- 数据采集、信号生成、世界线推演、Agent Council、报告生成都需要可重试、可观测、可恢复。
- 单个 API 请求不能承载长流程。
- P0 要避免“返回状态字符串”的假工作流。

可借鉴：

- Temporal: durable workflow、activity retry、workflow history、idempotency。
- Hatchet: background task + AI workflow 的简洁模式。
- Dagster / Prefect: 数据资产、运行状态、backfill、可观察性。
- Airflow: 批处理调度和依赖图，但不适合交互式产品链路主控。

推荐：

- P0 继续用 Temporal 做主工作流。
- Dagster/Prefect/Airflow 只作为数据平台模式参考，不在 P0 并行引入。

### 3.3 Agent / LLM Runtime

项目可能遇到的问题：

- 多角色 Agent 要有角色边界、证据边界和输出结构。
- LLM 会超时、限流、输出非法 JSON、引用不存在证据、产生 unsupported claims。
- Agent Council 需要审计、成本、token、prompt 版本和 schema 版本。

可借鉴：

- LangGraph: 状态图式 Agent workflow，适合多步骤、多角色、可恢复状态。
- AutoGen / CrewAI: 多 Agent 角色协作模式。
- LiteLLM: LLM gateway、provider 统一、成本、日志、fallback。
- Instructor: typed structured output。
- Guardrails: output validation 和约束。
- promptfoo / DeepEval / Ragas: prompt、Agent、RAG 评测。
- Langfuse / Phoenix: LLM tracing、prompt 版本、评价和回放。

建议在项目里落成：

```text
LLMProvider
AgentProfile
AgentContextBuilder
AgentCouncilRunner
AgentGuardrailService
AgentOutputValidator
AgentEvaluationSuite
```

硬规则：

- Agent 输出不是事实源。
- 每条 claim 必须绑定 `evidence_refs`。
- 不支持或越界内容进入 `blocked_claims`。
- 失败必须可见，不能静默 fallback 成结论。

### 3.4 搜索、RAG 与案例库

项目可能遇到的问题：

- 用户要按关键词、语义、区域、时间、平台、相似案例检索。
- 主线建模要找历史相似事件、前兆模式、处置动作和偏差。
- Agent 要引用证据和案例，而不是读全量原始流。

可借鉴：

- pgvector: P0 低复杂度向量检索。
- OpenSearch: 后续全文 + 聚合 + hybrid search。
- Qdrant: 独立高性能向量库候选。
- LlamaIndex / Haystack: RAG pipeline、retriever、reranker、citation。
- Typesense / Meilisearch: 轻量搜索体验候选。

推荐：

- P0 先使用 PostgreSQL FTS + pgvector。
- 后续当搜索压力和聚合复杂度上来，再引入 OpenSearch。
- RAG 框架作为案例库/证据库服务层参考，不让前端或 Agent 直连向量库。

### 3.5 知识图谱与世界线

项目可能遇到的问题：

- Case、Actor、SourceRecord、Evidence、Signal、RiskFactor、Mainline、WorldState、WorldlineNode 之间关系复杂。
- 事件会随时间演化，证据会更新、反转、降权。
- 世界线推演需要解释链，不是黑盒分数。

可借鉴：

- Graphiti: real-time / temporal knowledge graph for AI agents。
- Neo4j LLM Graph Builder: 从非结构化文本构建图谱的交互与流程。
- NetworkX: 图算法、传播路径、中心性、社区。
- Apache AGE: PostgreSQL 图扩展，后续如果不想单独运维 Neo4j 可评估。
- OpenCTI / MISP: 情报对象、source、confidence、relationship、taxonomy 模式。

推荐：

- P0 不强行引入 Neo4j。
- 先在 PostgreSQL JSONB + relational refs 中保留图关系。
- 图算法可用 NetworkX 离线/活动内计算。
- 进入 P1/P2 后再评估 Neo4j 或 AGE。

### 3.6 地理态势与热力图

项目可能遇到的问题：

- 城市态势页需要事件点、热区、聚合、传播路径、行政区/街道/学校/医院/商圈等空间对象。
- 点位既要高性能渲染，也要支持区域聚合、距离查询和空间过滤。

可借鉴：

- PostGIS: 空间数据、区域查询、距离、buffer、intersection。
- H3: 六边形空间索引、热区聚合。
- MapLibre GL JS: 浏览器矢量地图。
- deck.gl: 大规模点、热力、弧线、网格、hexagon 可视化。
- Turf.js: 前端/轻量空间分析。
- Tippecanoe: 大量 GeoJSON 生成 vector tiles。

推荐：

- 后端用 PostGIS 或 PostgreSQL + H3 做空间聚合。
- 前端用 MapLibre/deck.gl 模式改造现有地图层。
- 不把地图 SDK 作为业务真相来源；地图只是 view model。

### 3.7 视频、图像、OCR、ASR 证据

项目可能遇到的问题：

- 短视频/直播/截图是强证据来源，但事实可信度不稳定。
- 需要关键帧、OCR、ASR、目标检测、区域计数、隐私脱敏和人工复核。

可借鉴：

- supervision: 检测结果标准化、跟踪、区域计数、标注图/视频。
- Ultralytics / RF-DETR: 目标检测模型候选。
- PaddleOCR: OCR。
- FunASR / WhisperX: ASR 和时间戳对齐。
- FiftyOne: 视觉数据集评估和人工复核。
- Presidio: PII detection/anonymization，可作为文本/图片隐私识别参考。

推荐：

- 视觉能力作为 `VisionAnalysisWorkflow`，运行在 worker，不进 API request path。
- 输出只进入 `raw_records` / `evidence`，高风险结论进入 `needs_review`。
- 默认最小化保存和脱敏。

### 3.8 权限、合规、审计

项目可能遇到的问题：

- 不同角色可见不同原文、证据、敏感信息和操作。
- 每次证据状态、主线确认、报告确认、Agent 输出都必须可追溯。
- 数据来源 policy 需要程序化阻断。

可借鉴：

- OpenFGA: Zanzibar-style relationship authorization。
- Casbin: RBAC/ABAC 权限模型。
- OPA: policy-as-code。
- Presidio: PII 检测与匿名化。
- MISP / OpenCTI: confidence、source、sharing、audit 模式。

推荐：

- P0 先做项目内 RBAC + SourcePolicyService + audit logs。
- 后续组织/多租户/跨部门共享变复杂后评估 OpenFGA。
- OPA 适合作为 policy engine 候选，但不要过早引入第二套规则语言。

### 3.9 观测、评测与质量门禁

项目可能遇到的问题：

- LLM/Agent 输出质量不可凭感觉上线。
- RAG 检索命中、证据引用、幻觉率、schema 失败率要可测。
- 数据质量要在进入算法前被挡住。

可借鉴：

- Langfuse / Phoenix: LLM tracing、prompt 版本、dataset/eval。
- promptfoo: prompt、RAG、Agent 测试和 red team。
- DeepEval / Ragas: LLM/RAG 评价指标。
- Great Expectations: 数据质量规则。
- Grafana: 系统指标和业务 counters。

推荐指标：

- Agent schema pass rate。
- evidence ref validity。
- blocked claims rate。
- unsupported claim rate。
- raw_records accepted/blocked/duplicate counters。
- source health and latency。
- workflow success/failure/retry。
- report human confirmation changes。

### 3.10 产品 UI 与内部运营看板

项目可能遇到的问题：

- 产品主界面需要强业务表达，不是通用 BI。
- 但内部运营、审计、数据质量和系统健康可以借助成熟看板。

可借鉴：

- Grafana: API/worker/workflow/LLM 观测。
- Superset: 数据运营和离线分析。
- Evidence: SQL + Markdown 的内部报告。
- TanStack Table: 高密度数据表格。
- React Flow / xyflow: 主线/世界线图交互参考。
- Recharts / ECharts: 常规图表。

推荐：

- 用户-facing 产品页继续按 `apps/web` 定制。
- 管理/审计/系统健康可后续接 Grafana/Superset。
- 世界线图不要照搬通用 DAG 组件，需要保留产品语义：支点、概率、风险、证据、触发条件。

## 4. 组合架构建议

### P0 推荐组合

```text
FastAPI + PostgreSQL/JSONB/pgvector
+ Temporal + Redis
+ SourceAdapter + SourcePolicyService
+ Postgres FTS + pgvector search
+ LLMProvider + Instructor/Guardrails-style validation
+ Prompt/eval tests
+ React/TanStack product UI
```

### P1/P2 可评估增强

```text
OpenSearch
+ PostGIS/H3
+ MapLibre/deck.gl
+ VisionAnalysisWorkflow with supervision/OCR/ASR
+ Langfuse/Phoenix
+ OpenFGA
+ Third-party data provider adapters
```

### P2+ 大规模实时增强

```text
Redpanda/Pulsar
+ streaming SQL / Materialize / Bytewax
+ vector tile pipeline
+ graph store or AGE/Neo4j
+ dedicated data quality and evaluation platform
```

## 5. 参考项目清单

### 数据接入

- https://github.com/airbytehq/airbyte
- https://github.com/meltano/meltano
- https://github.com/dlt-hub/dlt
- https://github.com/apache/seatunnel
- https://github.com/bytewax/bytewax
- https://github.com/redpanda-data/redpanda
- https://github.com/apache/pulsar
- https://github.com/MaterializeInc/materialize
- https://github.com/D4Vinci/Scrapling
- https://github.com/apify/crawlee-python
- https://github.com/NanmiCoder/MediaCrawler
- https://github.com/sansan0/TrendRadar
- https://github.com/NanmiCoder/NewsCrawler
- https://github.com/DIYgod/RSSHub
- https://github.com/ourongxing/newsnow

### 工作流

- https://github.com/temporalio/temporal
- https://github.com/hatchet-dev/hatchet
- https://github.com/dagster-io/dagster
- https://github.com/PrefectHQ/prefect
- https://github.com/apache/airflow

### Agent / LLM

- https://github.com/langchain-ai/langgraph
- https://github.com/microsoft/autogen
- https://github.com/crewAIInc/crewAI
- https://github.com/BerriAI/litellm
- https://github.com/guardrails-ai/guardrails
- https://github.com/567-labs/instructor

### 搜索 / RAG

- https://github.com/pgvector/pgvector
- https://github.com/opensearch-project/OpenSearch
- https://github.com/qdrant/qdrant
- https://github.com/run-llama/llama_index
- https://github.com/deepset-ai/haystack
- https://github.com/typesense/typesense

### 图谱 / 情报 / 案例

- https://github.com/getzep/graphiti
- https://github.com/neo4j-labs/llm-graph-builder
- https://github.com/networkx/networkx
- https://github.com/apache/age
- https://github.com/OpenCTI-Platform/opencti
- https://github.com/MISP/MISP
- https://github.com/thehive-project/TheHive
- https://github.com/dfir-iris/iris-web
- https://github.com/ushahidi/platform

### 地理态势

- https://github.com/postgis/postgis
- https://github.com/maplibre/maplibre-gl-js
- https://github.com/visgl/deck.gl
- https://github.com/uber/h3
- https://github.com/Turfjs/turf
- https://github.com/mapbox/tippecanoe

### 视觉 / OCR / ASR

- https://github.com/roboflow/supervision
- https://github.com/ultralytics/ultralytics
- https://github.com/roboflow/rf-detr
- https://github.com/PaddlePaddle/PaddleOCR
- https://github.com/modelscope/FunASR
- https://github.com/m-bain/whisperX
- https://github.com/voxel51/fiftyone

### 合规 / 权限 / 隐私

- https://github.com/microsoft/presidio
- https://github.com/open-policy-agent/opa
- https://github.com/openfga/openfga
- https://github.com/casbin/casbin

### 观测 / 评测 / 质量

- https://github.com/langfuse/langfuse
- https://github.com/Arize-ai/phoenix
- https://github.com/confident-ai/deepeval
- https://github.com/explodinggradients/ragas
- https://github.com/promptfoo/promptfoo
- https://github.com/great-expectations/great_expectations
- https://github.com/grafana/grafana
- https://github.com/apache/superset
- https://github.com/evidence-dev/evidence

## 6. 当前最值得马上推进的技术验证

| 优先级 | 技术验证 | 目标 |
| --- | --- | --- |
| P0 | SourceAdapter + raw_records + policy + audit | 把数据进入链路做真 |
| P0 | Temporal real activities | 替换 placeholder workflow |
| P0 | LLMProvider + structured output + guardrails | Agent Council 生产化 |
| P0 | pgvector + FTS 搜索 | 支持信号/证据/案例检索 |
| P1 | TrendRadar/RSSHub/NewsCrawler POC | 热点和公开新闻入口 |
| P1 | MapLibre/deck.gl/H3 POC | 城市态势热力和聚合 |
| P1 | supervision + OCR/ASR POC | 视频/图片证据链 |
| P1 | Langfuse/Phoenix + promptfoo | Agent 可观测和评测 |
| P2 | OpenSearch / Qdrant / Graphiti | 大规模搜索、图谱和历史案例增强 |
