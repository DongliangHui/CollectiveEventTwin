# 03 检索、图谱与地理态势源码深读

研究根目录：`E:\GitHub\ref_prj`

目标：把城市态势页、证据检索、相似案例、世界线解释链做成后端真实能力。前端地图、图谱和列表只消费 view model；事实、聚合、排序、空间计算、图算法全部在后端完成并可回放。

## CollectiveEventTwin 落地点

- P0 检索：PostgreSQL FTS + pgvector，统一由 `EvidenceSearchService` 提供关键词、语义、时间、区域、来源过滤。
- P0 图谱：PostgreSQL relational refs + JSONB 保存 `case/event/actor/evidence/signal/risk_factor/worldline_node` 关系，NetworkX 做离线/工作流内算法。
- P0 地理：后端生成 Xi'an city view model，包含点位、行政区聚合、空间网格/区域聚合字段、热度、置信度、证据数量、时间窗口。
- H3 仅作为 P1/P2 或经 TR1 明确提升后的实现方案。
- 前端 city 页不能自己算风险分和热区，只渲染 `/api/cities/{city_id}/situation` 返回的 view model。
- 后续压力上来后再评估 OpenSearch/Qdrant/AGE/Materialize 等，不在 P0 过早堆基础设施。

## 搜索 / RAG 项目

### pgvector

- 关联到本项目：P0 向量检索、相似证据、相似案例、Agent 引用上下文。
- 它怎么实现：PostgreSQL extension 增加 vector 类型，提供 HNSW/IVFFlat 索引和距离查询。
- 源码锚点：`pgvector/vector.control`，`pgvector/sql/vector.sql`，`pgvector/test/sql/hnsw_vector.sql`，`pgvector/test/sql/ivfflat_vector.sql`。
- 短代码片段：`comment = 'vector data type and ivfflat and hnsw access methods'`；`USING hnsw`；`USING ivfflat`。
- 我们怎么用：`evidence_embeddings` 和 `case_embeddings` 直接落 PostgreSQL；不用让 Agent 直连向量库。

### OpenSearch

- 关联到本项目：后续全文检索、聚合、hybrid search、日志和运营搜索。
- 它怎么实现：server/modules/plugins/rest-api-spec 分层，REST API 接搜索请求，底层 Lucene 管索引与聚合。
- 源码锚点：`OpenSearch/server`，`OpenSearch/modules`，`OpenSearch/plugins`，`OpenSearch/rest-api-spec`。
- 短代码片段：`rest-api-spec`；`server`；`plugins`。
- 我们怎么用：P1/P2 候选；P0 先用 PostgreSQL，避免多一套索引一致性问题。

### Qdrant

- 关联到本项目：独立向量库候选、高性能语义检索、过滤查询。
- 它怎么实现：collection 配置包含 HNSW 参数，points API 管 upsert/search/scroll/query。
- 源码锚点：`qdrant/lib/storage/src/types.rs`，`qdrant/lib/shard/src/search.rs`，`qdrant/src/tonic/api/points_api.rs`。
- 短代码片段：`pub hnsw_index: HnswConfig`；`search.rs`；`points_api.rs`。
- 我们怎么用：当 pgvector 性能或过滤复杂度不足时再引入；P0 保持一套 PostgreSQL 事务边界。

### LlamaIndex

- 关联到本项目：RAG pipeline、retriever、query engine、citation、向量库接入。
- 它怎么实现：把文档节点、索引、retriever、query engine 拆分，示例覆盖 citation 和多种 vector store。
- 源码锚点：`llama_index/docs/examples/workflow/citation_query_engine.ipynb`，`llama_index/docs/examples/vector_stores/postgres.ipynb`，`llama_index/docs/examples/vector_stores/QdrantIndexDemo.ipynb`。
- 短代码片段：`citation_query_engine`；`vector_stores/postgres`；`QdrantIndexDemo`。
- 我们怎么用：借鉴 citation pipeline；本项目 `RagContextBuilder` 必须返回 evidence ids，不返回无来源文本。

### Haystack

- 关联到本项目：RAG pipeline、组件编排、retriever/ranker/generator 分层。
- 它怎么实现：Pipeline 连接组件，组件有输入输出类型，e2e 测试覆盖 RAG、hybrid search、evaluation pipeline。
- 源码锚点：`haystack/haystack/core/pipeline`，`haystack/haystack/tools/pipeline_tool.py`，`haystack/e2e/pipelines/test_rag_pipelines_e2e.py`。
- 短代码片段：`class PipelineTool(ComponentTool):`；`test_rag_pipelines_e2e.py`；`hybrid_doc_search_pipeline`。
- 我们怎么用：借鉴组件式检索链；实现自己的 `EvidenceRetrievalPipeline`，避免通用框架吞掉证据边界。

### Typesense

- 关联到本项目：轻量搜索体验、快速关键词/过滤、向量参数模式。
- 它怎么实现：索引层创建 HNSW vector index，字段层校验 `hnsw_params`、`ef_construction`、`M` 等参数。
- 源码锚点：`typesense/src/index.cpp`，`typesense/src/field.cpp`。
- 短代码片段：`hnsw_index_t(...)`；`vector_index.emplace(...)`；`hnsw_params`。
- 我们怎么用：可参考搜索 API 体验；P0 不引入 Typesense，避免搜索栈分裂。

## 图谱 / 情报 / 案例项目

### Graphiti

- 关联到本项目：时序知识图谱、episode/entity/edge、agent 可检索记忆。
- 它怎么实现：core 中有 graphiti、nodes、edges、graph_queries、search、maintenance/dedupe，支持把事件片段建成时间相关图。
- 源码锚点：`graphiti/graphiti_core/graphiti.py`，`graphiti/graphiti_core/nodes.py`，`graphiti/graphiti_core/edges.py`，`graphiti/graphiti_core/graph_queries.py`。
- 短代码片段：`graphiti_core/nodes.py`；`graphiti_core/edges.py`；`graph_queries.py`。
- 我们怎么用：借鉴 episode/edge 时间化；P0 图关系仍落 PostgreSQL，Agent 只能读有 evidence id 的上下文。

### Neo4j LLM Graph Builder

- 关联到本项目：从 URL/YouTube/文本源创建知识图谱、source node、chunk、community。
- 它怎么实现：后端 API 根据 `source_type` 分派 web-url/youtube/Wikipedia/S3/GCS，创建 source node 后抽取 chunk 和 graph。
- 源码锚点：`llm-graph-builder/backend/score.py`，`llm-graph-builder/backend/src/graphDB_dataAccess.py`，`llm-graph-builder/backend/src/create_chunks.py`，`llm-graph-builder/backend/src/communities.py`。
- 短代码片段：`async def create_source_knowledge_graph_url(...)`；`if source_type == "youtube"`；`def create_source_node(...)`。
- 我们怎么用：借鉴“source -> chunk -> graph -> community”的流水线；我们必须多一步 evidence review。

### NetworkX

- 关联到本项目：世界线图算法、连通分量、中心性、传播路径、社区识别。
- 它怎么实现：纯 Python algorithm 包覆盖 centrality、components、community、shortest_paths 等。
- 源码锚点：`networkx/networkx/algorithms/centrality`，`networkx/networkx/algorithms/components`，`networkx/networkx/algorithms/community`，`networkx/networkx/algorithms/shortest_paths`。
- 短代码片段：`algorithms/centrality`；`algorithms/community`；`shortest_paths`。
- 我们怎么用：P0 直接作为算法库或实现参考；结果入库为 `graph_metrics`，不能只在内存里给前端。

### Apache AGE

- 关联到本项目：PostgreSQL 内图查询扩展候选、Cypher 查询、图 label/edge 管理。
- 它怎么实现：在 PostgreSQL extension 中实现 graph commands、label commands、Cypher parser/executor。
- 源码锚点：`age/src/backend/commands/graph_commands.c`，`age/src/backend/parser/cypher_parser.c`，`age/src/backend/executor/cypher_create.c`。
- 短代码片段：`graph_commands.c`；`cypher_parser.c`；`cypher_create.c`。
- 我们怎么用：P1/P2 可评估；P0 不引入，先让 relational graph model 清晰。

### OpenCTI

- 关联到本项目：情报对象、source、confidence、relationship、sharing、audit。
- 它怎么实现：GraphQL 平台、worker、Python client，把情报对象和关系作为一等对象管理。
- 源码锚点：`opencti/opencti-platform/opencti-graphql`，`opencti/opencti-worker`，`opencti/client-python`。
- 短代码片段：`opencti-graphql`；`opencti-worker`；`client-python`。
- 我们怎么用：借鉴 STIX-like object、confidence、source marking；我们的领域对象是社会事件，不照搬威胁情报模型。

### MISP

- 关联到本项目：事件、attribute、taxonomy、sharing group、组织间共享边界。
- 它怎么实现：以 event 为核心组织 attributes、tags、galaxies、sharing、correlation。
- 源码锚点：`MISP/app/Model/Event.php`，`MISP/app/Model/MispAttribute.php`，`MISP/app/Model/Taxonomy.php`。
- 短代码片段：`class Event`；`class Attribute`；`Taxonomy`。
- 我们怎么用：借鉴事件属性和标签体系；客户侧共享/脱敏策略必须按本项目合规模型重做。

### TheHive

- 关联到本项目：case 管理、task、observable、case timeline、分析协同。
- 它怎么实现：后端和前端围绕 case/task/observable/alert 管协作流程。
- 源码锚点：`TheHive/app`，`TheHive/frontend`。
- 短代码片段：`case`；`task`；`observable`。
- 我们怎么用：借鉴 Case 工作台的信息架构；我们的“研判”要加入世界线、风险因子和 Agent Council。

### DFIR-IRIS

- 关联到本项目：事件响应 case、asset、ioc、report、timeline。
- 它怎么实现：`source` 目录组织 case management、资产、证据、报告和 Web API。
- 源码锚点：`iris-web/source`。
- 短代码片段：`source`；`case`；`report`。
- 我们怎么用：借鉴调查报告和 case timeline；不要照搬安全事件术语。

### Ushahidi

- 关联到本项目：群众上报、地理事件、分类、审核、公众事件地图。
- 它怎么实现：platform 后端管理 posts/surveys/categories，前端呈现地图和事件流。
- 源码锚点：`ushahidi-platform/app`，`ushahidi-platform/httpdocs`。
- 短代码片段：`posts`；`surveys`；`categories`。
- 我们怎么用：借鉴群众事件上报和审核流；本项目 P0 先做后台合成/公开源采集，不做公众投稿入口。

## 地理态势项目

### PostGIS

- 关联到本项目：空间字段、区域查询、距离、buffer、intersection、行政区聚合。
- 它怎么实现：PostgreSQL extension 提供 geometry/geography 类型和空间函数。
- 源码锚点：`postgis/extensions`，`postgis/liblwgeom`。
- 短代码片段：`extensions`；`liblwgeom`；`geometry/geography`。
- 我们怎么用：先用 PostgreSQL 经纬度和行政区字段形成后端态势聚合；PostGIS/H3 作为 P1/P2 或经 TR1 明确提升后的方案，城市态势聚合必须后端完成。

### MapLibre GL JS

- 关联到本项目：city 页地图渲染、矢量瓦片、交互层、样式。
- 它怎么实现：`Map` 管理地图状态，source/layer/style 驱动浏览器渲染。
- 源码锚点：`maplibre-gl-js/src/ui/map.ts`，`maplibre-gl-js/src/source`，`maplibre-gl-js/src/style`。
- 短代码片段：`class Map`；`src/source`；`src/style`。
- 我们怎么用：前端地图 SDK；不得在前端自行推导风险分或证据真相。

### deck.gl

- 关联到本项目：大量点、热力、hexagon、arc/flow layer、WebGL 可视化。
- 它怎么实现：View/Viewport/Layer 模块分离，React binding 提供渲染入口。
- 源码锚点：`deck.gl/modules/core/src/views/map-view.ts`，`deck.gl/modules/core/src/viewports/web-mercator-viewport.ts`，`deck.gl/modules/layers`，`deck.gl/modules/react`。
- 短代码片段：`export default class MapView`；`web-mercator-viewport`；`modules/layers`。
- 我们怎么用：city 页高密度可视层；输入只能是后端 view model。

### H3

- 关联到本项目：六边形空间索引、热区聚合、同尺度城市风险对比。
- 它怎么实现：核心 C 库把 lat/lng 转成 H3 cell，polyfill 用 cell 覆盖区域。
- 源码锚点：`h3/src/h3lib/lib/h3Index.c`，`h3/src/h3lib/lib/polyfill.c`。
- 短代码片段：`latLngToCell(...)`；`polyfill.c`；`H3Error`。
- 我们怎么用：后端生成 `h3_cell_metrics`；前端只渲染 cell geometry 和 score。

### Turf.js

- 关联到本项目：轻量空间计算参考，如中心点、缓冲、相交、voronoi。
- 它怎么实现：packages 按空间函数拆分，每个函数独立包。
- 源码锚点：`turf/packages/turf-center`，`turf/packages/turf-buffer`，`turf/packages/turf-intersect`，`turf/packages/turf-voronoi`。
- 短代码片段：`packages/turf-center`；`packages/turf-buffer`；`packages/turf-intersect`。
- 我们怎么用：前端可做非事实性辅助计算；正式聚合和风险判断在后端。

### Tippecanoe

- 关联到本项目：大量 GeoJSON 转 vector tiles、离线瓦片生成。
- 它怎么实现：`tile.cpp` 和 vector tile proto 处理要素简化、切片、合并。
- 源码锚点：`tippecanoe/tile.cpp`，`tippecanoe/tile.hpp`，`tippecanoe/vector_tile.proto`，`tippecanoe/tile-join.cpp`。
- 短代码片段：`tile.cpp`；`vector_tile.proto`；`tile-join.cpp`。
- 我们怎么用：后续如果 city 页数据量大，可离线生成 tiles；P0 直接 API view model 足够。

## 转成开发任务

| 任务 | 不可再拆的功能点 | 验收点 |
| --- | --- | --- |
| `EvidenceSearchService` | 关键词 + 语义 + 时间 + 地域 + 来源过滤 | 搜索结果必须返回 evidence_id 和高亮/相似度 |
| `EmbeddingJob` | raw/clean/evidence 文本生成 embedding | 重复文本不重复计费，失败可重试 |
| `CaseSimilarityService` | 当前 case 与历史 case 相似度 | 输出相似原因和 evidence refs |
| `CaseGraphBuilder` | case/actor/evidence/signal/risk_factor 建图 | 每条 edge 有来源和置信度 |
| `GraphMetricJob` | 中心性、连通分量、传播路径 | 指标入库，可被 API 查询 |
| `WorldlineGraphService` | 世界线节点、触发条件、概率、证据链 | unsupported edge 不进入正式图 |
| `CitySituationViewModelJob` | Xi'an 点位、区县、街道、空间网格/区域聚合 | API 返回 view model，无前端本地计算 |
| `GeoAggregationService` | 距离、区域、空间网格/区域聚合 | 异常坐标进入 quarantine；H3 仅在 TR1 提升后作为实现 |
| `MapLayerApi` | city 页 layers/data 接口 | 前端切图层时请求后端，不本地 mock |
