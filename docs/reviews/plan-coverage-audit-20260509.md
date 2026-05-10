# Plan Coverage Audit

日期：2026-05-09
对比对象：

- 旧计划：`docs/full-project-atomic-task-development-plan-20260508.md`
- 当前计划：`docs/atomic-task-backlog-v1.0.md`

## 1. 结论

当前 `atomic-task-backlog-v1.0.md` 没有完整覆盖旧计划。它把旧计划按 S0-S8 重新组织，并强化了证据、审计、Review Gate、页面状态和生产级约束，但也压缩/删除了大量旧计划里的原子任务。

更重要的是，即使按当前计划计算，前端也没有完成。当前 S8 发布验收结论已经撤销，详见：

- `docs/reviews/frontend-gap-audit-v1.0-20260509.md`
- `docs/reviews/s8-release-acceptance-v1.0-20260509.md`

## 2. 数量级差异

| 项 | 旧计划 | 当前计划 | 说明 |
|---|---:|---:|---|
| 文档行数 | 630 | 381 | 当前计划明显压缩 |
| 表格任务/规则行 | 420 | 244 | 当前计划少约 176 行 |
| 明确 AT 编号 | 351 个 AT | 不沿用 AT 编号 | 当前计划改为 S/F 编号 |
| 当前计划任务 ID | - | 约 220 个 | 不是旧 AT 的逐项映射 |

## 3. 当前计划新增/强化的内容

当前计划比旧计划更强的地方：

- S0 合同冻结更明确：对象、路由、状态机、权限、错误码、证据引用、截图基线。
- 强化生产级约束：禁止前端 mock、禁止无 DB 记录的 Agent/LLM 结论、报告事实必须有证据引用。
- 强化 Review Gate 和第三方检查：S1 引入 reviews、templates、gate-check、waive。
- 强化页面状态矩阵：loading、empty、error、degraded、no permission 被写入每阶段验收。
- S6/S7 对 Agent Profile、Council、blocked claims、报告 claim validation 的约束更清晰。

这些不是缺点，但它们不能抵消旧计划被删掉的原子工程任务。

## 4. 旧计划被当前计划遗漏或弱化的主要任务

### 4.1 数据源和采集能力被明显压缩

旧计划有大量数据源和采集原子任务，当前计划只保留了较粗的 synthetic/manual/public_web/official_api/media/live_segment。

遗漏或弱化项：

- public_web URL 可达性校验：`validate-url`
- public_web 抓取策略保存：`crawl-policy`
- official_api 连接测试：`test-connection`
- API 分页策略配置
- RSS 数据源、RSS inspect、RSS item 拉取
- webhook 数据源、webhook 签名校验、webhook payload 接收
- db_import 数据源和表扫描
- object_storage 数据源和对象扫描
- Adapter 插件注册、adapter capability 查询
- channel 注册表和 channel schema
- channel 独立限流、错误码、回放、质量指标、维护成本看板
- collection job pause/resume
- collection run steps 查询
- dead letter queue 和 dead letter replay
- cursor checkpoint 保存

当前实现中也基本没有这些完整产品能力。

### 4.2 文件解析和清洗能力被压缩

旧计划明确要求多格式解析和 clean-records 工作台，当前计划只保留 normalization/dedup/data quality run 的粗粒度链路。

遗漏或弱化项：

- HTML 正文解析
- JSON mapping parser
- CSV/XLSX/PDF/DOCX parser
- RSS item parser
- manual record schema 校验
- 时间、地点标准化
- source trust 赋值
- semantic dedupe
- dedupe candidate 人工确认
- clean-records 列表/详情/状态
- data-quality/issues
- cleaning-runs metrics

### 4.3 LLM 数据抽取底座被改写，旧任务未完整继承

当前计划有 F047 LLM 结构化抽取，但旧计划的若干通用 LLM 能力没有逐项进入。

遗漏或弱化项：

- LLM schema mapping suggest
- LLM event type classify
- LLM entity extraction
- LLM event facts extraction
- LLM evidence summary generation
- LLM JSON repair service
- 通用 LLM output schema validation
- 通用 claim evidence boundary verification

当前实现用 deterministic synthetic provider 覆盖部分链路，但不是旧计划里“通用 LLM 抽取平台”的完整实现。

### 4.4 City / Topic 的旧功能被简化

当前计划覆盖 City/Topic 核心页面，但旧计划里部分功能消失。

遗漏或弱化项：

- City context session switch：`POST /api/v1/session/city`
- map-events / layers 旧命名和兼容能力
- City snapshot create/view/diff
- 非校园样本 domain/import/validation
- Topic scope edit
- Topic overview/trend/event-candidates
- Topic watch / unwatch

### 4.5 信号、证据、风险能力缺少旧计划的若干细项

遗漏或弱化项：

- signal draft 区独立对象：`signal-drafts`
- evidence lineage 专用查询：`GET /api/v1/evidence/{id}/lineage`
- evidence confirm/reject 独立 endpoints
- risk factor detail endpoint
- risk factor confirm/reject 独立 endpoints
- 事件聚类、趋势异常、热点排序算法作为独立 algorithm runs

当前计划改成 signal packages、evidence reviews、risk factor runs，方向可接受，但没有完整覆盖旧计划粒度。

### 4.6 主线 / World State / 世界线缺少旧计划部分建模能力

遗漏或弱化项：

- mainline edge 自动生成
- mainline layout 保存
- mainline edge 人工编辑
- World State variable edit
- worldline parameter templates
- worldline results 专用查询
- worldline rerun
- worldline compare
- worldline explanation generation
- send-to-council 独立动作

### 4.7 LLM Provider / Agent Runtime 被当前计划重构但未全覆盖

当前计划转向 Agent Profile + Council，但旧计划中的通用 Agent Runtime 没有完整继承。

遗漏或弱化项：

- `GET /api/v1/llm/providers/status`
- provider health check
- LLM budget check
- generic `invoke_llm`
- prompt render
- agent profile list
- agent session create
- agent context pack
- single agent run
- multi-agent parallel scheduling
- agent session output / replay
- apply worldline delta
- counterfactual runs
- LLM call retry
- agent regression evaluations

### 4.8 报告 / 审批 / 导出能力被缩减

当前计划覆盖报告、review、publish、markdown/json export、tasks；旧计划要求更完整的报告编辑和导出链路。

遗漏或弱化项：

- report section 独立编辑
- citation validation endpoint
- approval-tasks
- approve/reject 独立审批动作
- PDF 导出
- DOCX 导出
- export-runs 状态查询
- task comments
- review metrics / review submit 旧复盘路径

### 4.9 案例库和配置中心缺少旧计划细粒度配置域

当前计划有 case_library_entries、config_versions、config_releases，但旧计划配置域更细。

遗漏或弱化项：

- case semantic search：`GET /api/v1/cases/search`
- retrieve cases for Agent
- taxonomy list / draft / publish
- algorithm params list / draft / regression / publish
- agent profile config versions
- prompt config versions
- config impact endpoint

### 4.10 专业 Agent 复用底座几乎没有进入当前计划

旧计划 17 节 `AT-265` 至 `AT-278` 基本没有被当前计划完整继承。

遗漏项包括：

- professional agent types
- professional agents CRUD/version/publish
- tool permissions
- output schema
- schema_mapping / parse_rule / collection_failure_diagnosis / test_case_generation runs
- agent suggestions approve/reject
- professional agent regression
- professional agent run records

### 4.11 OpenClaw 风格 Agent Profile 未完整继承

当前 S6 有 Agent Profile 文件，但旧计划要求更细：

- council-agent-profiles 独立资源
- user.md / soul.md / agent.md 独立保存
- profile import/export
- prompt rendering
- stance conflict detection
- event tradeoff context
- agent memory retrieval
- position consistency validation
- cross examination
- concession/tradeoff delta
- council decision matrix

### 4.12 图片、视频、直播、多模态能力被大幅压缩

当前计划有 media processing runs、segment runs、live segment runs，但旧计划 20-23 节更完整。

遗漏或弱化项：

- image upload endpoint
- image metadata extraction
- image pHash dedupe
- image sensitive region redaction
- image scene classification
- image object detection
- VLM image evidence description
- image evidence detail view
- video upload endpoint
- video proxy/transcode
- video keyframes
- video shot detection
- video audio extraction
- video ASR/OCR/visual event detection
- video segment summary
- video evidence detail time jump
- livestream source/probe
- rolling buffer
- streaming ASR
- livestream keyframe sampling
- live OCR
- livestream event triggers
- livestream clip creation
- livestream recovery
- multimodal artifact unified query
- multimodal evidence Agent
- cross-modal corroboration
- multimodal timeline alignment
- multimodal risk factors
- multimodal evidence in report

### 4.13 第三方检查系统没有完整继承旧计划

当前计划使用 reviews/review_results/review_templates，但旧计划 25 节定义的是独立 review gate 系统。

遗漏或弱化项：

- `review_gate_records` 独立表
- `/api/v1/review-gates`
- `/api/v1/tasks/{task_id}/review-gates`
- blocking finding 自动生成修复任务
- retest records
- freeze guardrail
- review checklist versions
- release review gates summary

## 5. 按当前计划的完成度纠偏

按当前计划本身看，也不能判定全部完成：

- 后端/API/DB：已推进到 S7B 附近，但仍有旧计划覆盖缺口和部分兼容合同问题。
- 前端：未完成。`risk/data/evidence/mainline/worldline/council/brief` 主要仍由通用 `StructuredPage` 渲染，不满足原子计划的页面级实现和状态矩阵。
- S8：撤销。此前只能算路由烟测和 API/后端局部验收，不是全链路发布验收。

## 6. 建议修正

1. 不要继续使用 “S8 已通过” 作为项目状态。
2. 将旧计划遗漏项分成两类：
   - 必须补回当前 v1 范围：前端生产页面、状态矩阵、权限态、Review Gate、报告导出、配置/案例基本闭环。
   - 可以进入 v1.1/v2：RSS/webhook/db_import/object_storage、专业 Agent 平台、完整多媒体算法、cross-modal、PDF/DOCX、Lighthouse、大规模性能。
3. 当前执行应先按 `docs/frontend-production-restart-backlog-v1.0-20260509.md` 从 S1 前端重启。
4. 同时补一份 `old-plan-delta-backlog`，把本报告第 4 节转成可排期任务。
