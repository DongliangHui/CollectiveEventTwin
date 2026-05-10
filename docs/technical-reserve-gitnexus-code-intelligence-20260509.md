# GitNexus 代码智能与 Agent 工程化技术储备
Date: 2026-05-09

Status: 技术储备，优先作为开发侧/QA 侧能力参考，不作为 CollectiveEventTwin 业务生产运行时依赖。

## 1. 结论

GitNexus 的核心价值不是数据采集，也不是舆情业务分析，而是：

```text
代码库分析
-> 代码知识图谱
-> Hybrid Search / Graph Query
-> MCP 工具暴露
-> Agent 上下文增强
-> API / 路由 / 工具 / 数据模型影响分析
```

对 CollectiveEventTwin 来说，最值得借鉴的是“开发侧智能工程基础设施”：

- 帮助 Agent 和开发者理解当前代码库。
- 在修改 API、schema、workflow、Agent tool、前端页面之前做影响面分析。
- 在 P0 生产级交付中，降低后端 API、前端调用、数据模型、测试、Agent 工具之间的静默断裂风险。

它不解决“去哪拿抖音、快手、小红书、头条、B 站数据”的问题，也不应进入数据采集主链路。

## 2. 项目快照

调研时间：2026-05-09

项目地址：

- https://github.com/abhigyanpatwari/GitNexus
- https://github.com/abhigyanpatwari/GitNexus/blob/main/ARCHITECTURE.md
- https://github.com/abhigyanpatwari/GitNexus/blob/main/GUARDRAILS.md
- https://github.com/abhigyanpatwari/GitNexus/blob/main/RUNBOOK.md

调研快照：

- 定位：Zero-server code intelligence engine / client-side knowledge graph / Graph RAG Agent。
- 最新 release：v1.6.3，发布时间为 2026-04-24。
- 仓库近期仍活跃，GitHub API 显示 2026-05-08 有推送。
- 主要形态：CLI、MCP server、HTTP API、React/Vite Web UI、代码知识图谱、嵌入检索、影响分析工具。
- 许可证风险：GitHub API 返回 license 不明确；项目文档中出现 PolyForm Noncommercial 1.0.0 相关表述。商业项目中不能直接拷贝代码或作为生产依赖，除非后续确认授权。

## 3. 值得借鉴的设计

### 3.1 阶段化代码分析 DAG

GitNexus 的分析过程不是一次性脚本，而是分阶段 pipeline：

```text
scan
-> structure
-> markdown / cobol
-> parse
-> routes / tools / orm
-> crossFile
-> mro
-> communities
-> processes
```

可借鉴点：

- 每个 phase 有明确输入、输出和依赖。
- 分析结果累积到统一 knowledge graph。
- 支持跳过、重跑、增量检测和 stale 判断。

映射到 CollectiveEventTwin，可以形成类似结构：

```text
source_check
-> fetch_or_import
-> policy_check
-> normalize
-> dedup
-> evidence_extract
-> signal_extract
-> factor_extract
-> mainline_update
-> worldline_update
-> council_review
-> report_publish
```

但业务数据 pipeline 应继续由 Temporal + PostgreSQL 承载，不引入 GitNexus 的运行时。

### 3.2 MCP 工具化接口

GitNexus 把代码理解能力通过 MCP 暴露给 Agent，例如：

- `query`
- `context`
- `impact`
- `detect_changes`
- `route_map`
- `api_impact`
- `tool_map`
- `shape_check`
- `group_list`
- `group_sync`

可借鉴点：

- Agent 不应该直接凭上下文猜代码关系。
- Agent 修改前应先查询相关代码、影响面和契约。
- 复杂仓库应给 Agent 提供可调用的代码理解工具，而不是只依赖全文搜索。

对本项目最有价值的是：

```text
route_map      # 后端 route 到前端调用点
api_impact    # API 变更影响面
shape_check   # 后端响应 shape 与前端读取字段一致性
impact        # 服务、模型、workflow、tool 变更影响范围
detect_changes # 提交前识别变更和索引状态
```

### 3.3 Hybrid Search 与代码图谱

GitNexus 同时使用文本检索、向量检索和图谱关系来回答代码问题。

可借鉴点：

- 单靠向量检索不够，代码/业务对象需要结构化关系。
- 单靠全文检索也不够，Agent 需要语义上下文。
- 影响分析必须依赖显式 graph edge，而不是只靠 LLM 推断。

映射到 CollectiveEventTwin：

```text
PostgreSQL FTS
+ pgvector
+ relational refs / graph-like tables
+ explicit evidence_refs
+ audit_logs
```

P0 仍建议用 PostgreSQL / JSONB / pgvector，不急于引入独立图数据库。

### 3.4 Staleness Detection

GitNexus 会比较已索引 commit 与当前 HEAD，判断代码图谱是否过期。

可借鉴到两个方向：

开发侧：

- 代码索引必须记录 commit hash。
- Agent 修改前发现索引过期，应先刷新索引。
- PR / 本地提交前应运行 detect changes。

业务侧：

- 数据源记录 last_seen、last_collected_at、source_version、content_hash。
- 案件主线、风险因子、世界线节点应知道自己基于哪些 evidence 版本。
- 当关键 evidence 更新或删除时，触发 downstream stale 标记。

### 3.5 Guardrails

GitNexus 的 guardrails 值得吸收为工程规范：

- 不提交密钥。
- 共享符号修改前先做影响分析。
- rename 走工具 dry-run，不做粗暴 find/replace。
- 提交前检测变更。
- 索引过期时先刷新。
- 数据库锁冲突时保持单 writer。

这些规则可以转化成本项目的 Agent 开发守则。

## 4. 不建议借鉴或引入的部分

### 4.1 不作为业务运行时依赖

GitNexus 不应成为 CollectiveEventTwin 的生产运行时组件。

原因：

- 它的领域是代码库分析，不是公共风险事件业务模型。
- 它的数据存储和索引策略服务于本地代码智能，不服务于我们的 case / evidence / worldline。
- 许可证存在不确定性。

### 4.2 不引入 LadybugDB 到业务数据层

GitNexus 使用 LadybugDB 做代码图谱存储。对我们来说：

- 业务主库继续是 PostgreSQL。
- 图谱关系先用 relational refs / JSONB / pgvector / audit tables 表达。
- 后续如确实需要图数据库，再评估 Neo4j、Apache AGE、Graphiti 等。

### 4.3 不把 MCP 放到用户产品主链路

MCP 适合内部 Agent、开发工具和 QA 工具。

P0 用户产品主链路仍应是：

```text
apps/web
-> FastAPI
-> PostgreSQL
-> Temporal workers
-> audit logs
```

MCP 可以作为内部能力，不作为最终用户交互协议。

## 5. 推荐落地方式

### 5.1 短期：隔离验证 GitNexus

目标：

- 在 CollectiveEventTwin 仓库上跑一次 GitNexus。
- 验证它对 FastAPI route、React frontend、API client、工具函数、SQLAlchemy model 的识别效果。
- 重点验证 `route_map`、`api_impact`、`shape_check`、`impact` 是否能发现真实问题。

通过标准：

- 能定位后端 API 到前端调用页面。
- 能发现响应字段变更对前端的影响。
- 能输出可用的影响面清单。
- 不修改项目业务代码。
- 不把 GitNexus 作为生产依赖提交。

### 5.2 中期：自研 Contract Impact 工具

如果验证效果好，建议吸收其设计，做一个更贴合本项目的内部工具：

```text
CollectiveEventTwin Contract Impact
```

输入：

- FastAPI routes
- Pydantic schemas
- SQLAlchemy models
- OpenAPI schema
- apps/web API clients
- TanStack Query hooks
- frontend page consumers
- Temporal workflow/activity signatures
- Agent tool schemas

输出：

- route -> frontend consumer map
- schema -> DB model map
- API response field -> frontend property access map
- workflow/activity -> API/report impact map
- Agent tool schema -> backend handler impact map
- missing test suggestions
- risky change report

### 5.3 长期：Case Knowledge MCP

当本项目的 `raw_records`、`evidence`、`signals`、`risk_factors`、`mainlines`、`worldlines` 链路稳定后，可以借鉴 GitNexus 的 MCP 模式，为内部 Agent 暴露业务知识查询工具：

```text
case_query
evidence_context
factor_impact
worldline_trace
source_health
report_claim_check
```

注意：这应该建立在真实数据库和审计链路上，不应由 LLM 自行生成事实。

## 6. 与当前 P0 的关系

GitNexus 对 P0 的直接价值排序：

| 优先级 | 方向 | 价值 |
| --- | --- | --- |
| P0 | API / frontend contract impact | 防止后端 API 和前端页面静默断裂 |
| P0 | Agent 开发前上下文查询 | 减少 Agent 误改代码 |
| P0 | shape_check 思路 | 检查后端返回结构和前端读取字段一致性 |
| P0 | detect_changes / stale check | 避免基于旧索引做开发决策 |
| P1 | multi-repo group mode | 后续拆分 connector、worker、contracts 仓库时使用 |
| P1/P2 | Case Knowledge MCP | 业务知识查询和 Agent 辅助分析 |

当前不进入 P0 的内容：

- GitNexus 作为生产依赖。
- LadybugDB 作为业务数据库。
- GitNexus Web UI 作为产品 UI。
- 直接复制其源码实现。

## 7. 推荐沉淀到项目规范的规则

建议后续加入 `AGENTS.md` 或工程规范：

```text
修改 shared schema / API route / Agent tool 前：
1. 查找 route / schema / consumer。
2. 输出影响面。
3. 更新或新增契约测试。
4. 更新前端调用。
5. 运行相关测试。
```

```text
Agent 修改代码前：
1. 先定位上下文。
2. 对共享符号做影响分析。
3. 不做全局 find/replace rename。
4. 不提交 secrets。
5. 不在索引过期时继续推断。
```

## 8. 后续待办

建议后续单独做一次技术验证：

```text
Spike: GitNexus on CollectiveEventTwin
```

验证项：

- 安装和运行成本。
- 对当前 monorepo 的识别质量。
- FastAPI route 识别能力。
- React/Vite frontend consumer 识别能力。
- API shape mismatch 检查能力。
- MCP 工具是否能被 Codex/本地 Agent 稳定调用。
- 许可证和商业使用风险确认。

输出：

```text
docs/spike-gitnexus-collectiveeventtwin-evaluation-YYYYMMDD.md
```

## 9. 资料来源

- GitNexus: https://github.com/abhigyanpatwari/GitNexus
- Architecture: https://github.com/abhigyanpatwari/GitNexus/blob/main/ARCHITECTURE.md
- Guardrails: https://github.com/abhigyanpatwari/GitNexus/blob/main/GUARDRAILS.md
- Runbook: https://github.com/abhigyanpatwari/GitNexus/blob/main/RUNBOOK.md
