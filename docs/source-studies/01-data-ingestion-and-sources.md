# 01 数据采集与 SourceAdapter 源码深读

研究根目录：`E:\GitHub\ref_prj`

目标：把“从很多渠道拿数据”拆成可执行的生产能力。对 CollectiveEventTwin 来说，数据采集不是一个 API，也不是前端 mock；它是 `SourceAdapter -> CollectionRun -> RawRecord -> CleanedEvidence -> Signal` 的可审计链路。

## CollectiveEventTwin 落地点

- 后端需要 `SourceAdapter` 抽象：`synthetic_scenario`、`public_web`、`rss`、`news_site`、`social_platform_poc`、`media_file`、`manual_upload`、`authorized_feed` 分渠道实现。
- 每次采集都要写 `collection_runs`、`collection_run_steps`、`source_policy_decisions`、`raw_records`、`raw_record_assets`、`data_quality_checks`。
- 合成数据只允许作为 `synthetic_scenario` 渠道进入，不允许变成前端静态 JSON。
- 渠道失败要被结构化：授权失败、反爬失败、解析失败、字段漂移、限流、重复、质量不达标、媒体处理失败。
- 采集后端必须支持回放：同一输入 hash、同一 adapter 版本、同一清洗版本可以复现下游结果。

## 项目深读

### Airbyte

- 关联到本项目：采集 connector 生命周期、source catalog、stream 状态、sync job 审计。
- 它怎么实现：Source connector 暴露 `spec/check/discover/read`，读取时持续产生 Airbyte message，并用 stream status 标记 STARTED/RUNNING/COMPLETE/INCOMPLETE。
- 源码锚点：`airbyte/airbyte-integrations/connectors/source-file/source_file/source.py`，`airbyte/airbyte-integrations/connectors/source-file/source_file/client.py`。
- 短代码片段：`class SourceFile(Source):`；`def read(...):`；`stream_status_as_airbyte_message(... COMPLETE)`。
- 我们怎么用：借鉴 connector 生命周期和 run status，不引入 Airbyte 作为 P0 主链路；我们自己实现轻量 `SourceAdapter` 和 `CollectionRunService`。

### Meltano

- 关联到本项目：数据接入项目组织、插件调用、环境隔离、schema 初始化。
- 它怎么实现：通过 plugin invoker 管理外部 ELT 插件执行，把项目配置、数据库 schema 和运行环境分离。
- 源码锚点：`meltano/src/meltano/core/plugin_invoker.py`，`meltano/src/meltano/core/plugin_install_service.py`，`meltano/src/meltano/core/db.py`。
- 短代码片段：`def ensure_schema_exists(...):`；`CREATE SCHEMA IF NOT EXISTS`。
- 我们怎么用：借鉴“采集能力以插件/adapter 注册”的组织方式；P0 不引入 Meltano 运行时，避免双调度系统。

### dlt

- 关联到本项目：Python 数据加载、schema 演化、字段能力适配、增量入库。
- 它怎么实现：目的端声明 capabilities，加载前根据能力调整 column schema，并由 buffered writer 处理 schema change。
- 源码锚点：`dlt/dlt/common/destination/capabilities.py`，`dlt/dlt/common/data_writers/buffered.py`。
- 短代码片段：`def adjust_column_schema_to_capabilities(...)`；`def adjust_schema_to_capabilities(...)`；`self._supports_schema_changes = ...`。
- 我们怎么用：实现 `RawRecordNormalizer` 时借鉴能力协商；对未知字段进入 `raw_payload JSONB`，稳定字段进入 typed columns。

### Apache SeaTunnel

- 关联到本项目：跨源数据同步、source/transform/sink 分层、清洗 transform 插件。
- 它怎么实现：核心 API 把源、转换、下游 collector 拆开，transform 接收上游 row 并输出新 row。
- 源码锚点：`seatunnel/seatunnel-api/src/main/java/org/apache/seatunnel/api/transform/SeaTunnelTransform.java`，`seatunnel/seatunnel-api/src/main/java/org/apache/seatunnel/api/transform/SeaTunnelMapTransform.java`。
- 短代码片段：`public interface SeaTunnelTransform`；`SeaTunnelMapTransform`；`Collector`。
- 我们怎么用：借鉴 source/transform/sink 拆层；我们用 Python service + Temporal activity 实现，不引入 Java 引擎。

### Bytewax

- 关联到本项目：实时流处理、状态化算子、采集后在线去重/聚合。
- 它怎么实现：以 `Dataflow` 为核心，把 `input`、operator、`output` 组成可运行图，底层 Rust 负责执行。
- 源码锚点：`bytewax/pysrc/bytewax/dataflow.py`，`bytewax/pysrc/bytewax/operators/__init__.py`，`bytewax/src/dataflow.rs`。
- 短代码片段：`class Dataflow:`；`def input(...):`；`def output(step_id, up, sink) -> None:`。
- 我们怎么用：借鉴流式 pipeline 表达；P0 先用数据库事务和 Temporal workflow，只有实时量上来后再评估独立流处理。

### Redpanda

- 关联到本项目：未来事件总线、采集流、媒体分析任务流、agent 事件流。
- 它怎么实现：Kafka-compatible broker，支持 transform 模块、probe、partition 级处理和可观测指标。
- 源码锚点：`redpanda/src/v/wasm/transform_module.cc`，`redpanda/src/v/wasm/transform_probe.cc`，`redpanda/src/v/wasm/README.md`。
- 短代码片段：`transform_module`；`transform_probe`；`src/v/wasm`。
- 我们怎么用：P2 实时增强候选；P0 不把 Kafka/Redpanda 放进主链路，避免运维复杂度提前膨胀。

### Apache Pulsar

- 关联到本项目：多租户消息流、函数式处理、IO connector、大规模 channel fan-out。
- 它怎么实现：broker、function、IO source/sink 分层；函数可以对 topic 输入做处理再输出。
- 源码锚点：`pulsar/pulsar-io/data-generator/src/main/java/org/apache/pulsar/io/datagenerator/DataGeneratorSource.java`，`pulsar/pulsar-functions/python-examples`。
- 短代码片段：`DataGeneratorSource`；`pulsar-functions/python-examples`；`Source`。
- 我们怎么用：作为后续事件平台对比项；P0 用 Temporal task queue 和 PostgreSQL 状态表。

### Materialize

- 关联到本项目：连续视图、流式物化、城市态势页增量聚合。
- 它怎么实现：把 source/table/view 编译为持续维护的计算视图，测试中大量覆盖 upsert/debezium/source 组合。
- 源码锚点：`materialize/src/controller/src/lib.rs`，`materialize/src/transform/tests/test_transforms.rs`，`materialize/test/upsert/kafka-upsert-debezium-sources.td`。
- 短代码片段：`CREATE TABLE ... FROM SOURCE ...`；`test_transforms`；`controller`。
- 我们怎么用：借鉴“态势 view model 可持续刷新”的思想；P0 用 PostgreSQL materialized view 或业务表缓存实现。

### Scrapling

- 关联到本项目：公开网页抓取、浏览器抓取、静态 fetch、反自动化失败类型识别。
- 它怎么实现：把普通 requests fetcher 和 stealth chrome fetcher 分开，统一暴露 `fetch`。
- 源码锚点：`scrapling/scrapling/fetchers/requests.py`，`scrapling/scrapling/fetchers/stealth_chrome.py`，`scrapling/scrapling/engines/static.py`。
- 短代码片段：`class Fetcher(BaseFetcher):`；`class StealthyFetcher(BaseFetcher):`；`def fetch(...):`。
- 我们怎么用：`public_web` adapter 参考其 fetcher 分层；带登录、绕限制或高风险平台只做 POC，不进入生产默认采集。

### Crawlee Python

- 关联到本项目：爬取路由、请求队列、重试、并发控制、失败记录。
- 它怎么实现：`BasicCrawler` 驱动 request queue，`Router` 根据请求上下文派发 handler。
- 源码锚点：`crawlee-python/src/crawlee/router.py`，`crawlee-python/src/crawlee/crawlers/_basic/_basic_crawler.py`，`crawlee-python/src/crawlee/storage_clients/_base/_request_queue_client.py`。
- 短代码片段：`class Router(Generic[TCrawlingContext]):`；`class BasicCrawler(...)`；`async def fetch_next_request(...)`。
- 我们怎么用：实现 `CrawlerRun` 的 request queue、retry、dead-letter 表；不让 crawler 直接写业务证据表。

### MediaCrawler

- 关联到本项目：社交平台字段可得性、评论采集、平台差异、登录态/限流失败模式。
- 它怎么实现：平台 crawler 继承 `AbstractCrawler`，各平台 client 自己处理请求、间隔、评论分页和数据保存。
- 源码锚点：`MediaCrawler/base/base_crawler.py`，`MediaCrawler/media_platform/douyin/core.py`，`MediaCrawler/media_platform/douyin/client.py`。
- 短代码片段：`class AbstractCrawler(ABC):`；`class DouYinCrawler(AbstractCrawler):`；`await asyncio.sleep(crawl_interval)`。
- 我们怎么用：只作为 POC 研究字段和失败类型；未经授权的平台抓取不进入生产主链路。

### TrendRadar

- 关联到本项目：热点采集、榜单历史、RSS 抓取、AI filter、来源状态表。
- 它怎么实现：爬虫抓取后写 SQLite schema，维护 `news_items`、`rank_history`、`crawl_records`、`ai_filter_results` 等表。
- 源码锚点：`TrendRadar/trendradar/crawler/fetcher.py`，`TrendRadar/trendradar/storage/schema.sql`，`TrendRadar/trendradar/storage/ai_filter_schema.sql`。
- 短代码片段：`def fetch_data(...)`；`CREATE TABLE IF NOT EXISTS news_items`；`CREATE TABLE IF NOT EXISTS ai_filter_results`。
- 我们怎么用：借鉴热点 item、rank history、AI 过滤结果表；本项目需要把 AI filter 结果绑定 evidence refs 和 review 状态。

### NewsCrawler

- 关联到本项目：新闻站点 adapter、内容提取、后端 extract API、MCP 化工具入口。
- 它怎么实现：`BaseNewsCrawler` 定义通用爬虫形态，平台 adapter 继承 `CrawlerAdapter`，后端以 FastAPI router 暴露 extract/health/platforms。
- 源码锚点：`NewsCrawler/news_crawler/core/base.py`，`NewsCrawler/news_extractor_core/adapters/base.py`，`NewsCrawler/news_extractor_backend/api/extract.py`。
- 短代码片段：`class BaseNewsCrawler(ABC):`；`class CrawlerAdapter(ABC):`；`@router.get("/platforms")`。
- 我们怎么用：`news_site` adapter 参考其“平台 adapter + extract API”分层；提取结果必须先进入 raw/clean/evidence，不直接成为事实。

### RSSHub

- 关联到本项目：RSS 入口、route registry、统一输出 RSS/JSON/Atom。
- 它怎么实现：通过 registry/router 组织海量 route，view 层把 route result 渲染成多种 feed 格式。
- 源码锚点：`RSSHub/lib/router.js`，`RSSHub/lib/registry.ts`，`RSSHub/lib/views/rss.tsx`，`RSSHub/lib/views/json.ts`。
- 短代码片段：`router`；`registry`；`views/rss.tsx`。
- 我们怎么用：实现 `rss` adapter 的 route/source registry；输出统一转成 `RawRecord`，不把 RSS schema 泄露到业务层。

### newsnow

- 关联到本项目：热点源目录、轻量新闻聚合、源校验、搜索交互和缓存。
- 它怎么实现：`shared/sources.json` 管来源清单，server 下每个 source 独立实现，前端用 query/search hooks 消费。
- 源码锚点：`newsnow/shared/sources.json`，`newsnow/shared/metadata.ts`，`newsnow/server/sources/weibo.ts`，`newsnow/src/hooks/query.ts`，`newsnow/src/hooks/useSearch.ts`。
- 短代码片段：`export function useSearchBar()`；`server/sources/*.ts`；`shared/sources.json`。
- 我们怎么用：借鉴“每个渠道单独文件”的维护方式；前端搜索必须调用后端 API，不能只在本地过滤静态数据。

## 转成开发任务

| 任务 | 不可再拆的功能点 | 验收点 |
| --- | --- | --- |
| `SourceAdapter` 协议 | 定义 `discover/check/collect/normalize` 接口 | 单测覆盖成功、授权失败、字段漂移、重复、超时 |
| `synthetic_scenario` adapter | 西安拆迁/养老保险样本生成并入 raw_records | 生成记录带 source/channel/run_id/input_hash |
| `rss` adapter | 读取配置源并生成 raw_records | RSS 解析失败写失败原因，不吞错 |
| `news_site` adapter | URL 列表采集、正文抽取、媒体 asset 发现 | 提取失败不影响同批其他 URL |
| `public_web` crawler queue | request queue、retry、dead-letter | 请求失败可重试、可回放 |
| `CollectionRunService` | 创建 run、执行 step、记录 counters | API 可查询 run 状态和失败明细 |
| `RawRecordNormalizer` | JSONB 原文、稳定字段、去重键、hash | 重复记录不生成新业务证据 |
| `SourcePolicyService` | 渠道授权、robots/合规标记、风险阻断 | 高风险渠道默认 blocked 或 needs_review |
| `DataQualityGate` | 必填字段、时间、地域、来源可信度检查 | 不达标进入 quarantine，不进入信号计算 |
