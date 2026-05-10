# 业务对象字典 v1.0

状态：冻结版

## 通用对象规则

所有业务对象必须具备：

- `id`：稳定字符串 ID，不在前端临时生成正式业务 ID。
- `tenant_id`：租户隔离字段，单租户开发环境也必须保留。
- `status`：来自本合同或领域状态机。
- `created_at`、`updated_at`：服务端时间。
- `created_by`、`updated_by`：可追溯操作者。
- `version` 或 `object_version`：参与审阅、发布、回滚和差异比较的对象必须版本化。
- `payload` / `metadata`：JSONB 扩展字段，不能替代核心状态字段。
- `audit_context`：mutation 必须能写入 `audit_logs`。

## 核心对象

| 对象 | 定义 | 主状态 | 上游 | 下游 | 冻结约束 |
| --- | --- | --- | --- | --- | --- |
| `City` | 城市级态势容器，第一阶段默认西安 | active/archived | tenant/config | CityEvent、Topic | 城市切换和可见范围由权限控制 |
| `CityEvent` | 城市态势页展示的事件聚合对象 | candidate/observing/active/archived | RawRecord、Signal、Evidence | Topic | 从 CityEvent 创建 Topic 必须写审计 |
| `Topic` | 社会议题分析主对象 | candidate/observing/active/merged/archived/converted_to_mainline | CityEvent、RawRecord | Signal、Evidence、Mainline | `active` 后才能进入信号工作台 |
| `DataSource` | 数据来源定义与策略边界 | draft/active/paused/blocked/archived | User/Config | CollectionJob、RawRecord | `source_type=synthetic` 必须全链路保留 |
| `SourcePolicy` | 数据源合规策略判定 | allow/block/needs_review | DataSource | CollectionJob | block 时不得创建 collection run |
| `SourceHealth` | 数据源健康状态 | healthy/degraded/unhealthy/blocked | CollectionRun | PageView、Ops | City/Topic view-model 必须暴露 degraded source |
| `CollectionJob` | 采集任务配置 | draft/active/paused/archived | DataSource | CollectionRun | 启停、重试、取消均写审计 |
| `CollectionRun` | 一次采集运行 | pending/running/retrying/failed/completed/canceled | CollectionJob | RawRecord | 必须记录 counters、错误、retryable |
| `RawRecord` | 原始记录索引 | collected/normalized/rejected/archived | CollectionRun | Signal、Evidence、Lineage | 产品数据必须从 raw record 链路进入 |
| `MediaAsset` | 图片、视频、直播片段、音频资产 | pending/processing/completed/failed | RawRecord/import | Evidence | 未脱敏媒体不得直接进入客户可见事实 |
| `Signal` | 从 raw records 抽取的风险/诉求/传播信号 | raw_candidate/selected/in_package/sent_to_review/excluded/archived | RawRecord、ExtractionRun | SignalPackage、Evidence、Mainline | `in_package` 后才能参与主线草稿 |
| `SignalPackage` | 主线输入信号包 | draft/locked/archived | Signal | Mainline | locked 后修改必须产生审计和版本差异 |
| `Evidence` | 可支撑事实或概率判断的证据对象 | candidate/needs_review/confirmed/rejected/probability_reference_only/used_in_mainline | RawRecord、Signal、MediaAsset | Mainline、Council、Report | `confirmed` 才能支撑正式事实 |
| `EvidenceReview` | 证据人工/第三方复核任务 | pending/pass/fail/waived | Evidence | Evidence.status | conflict 和 sensitive redacted 必须可见 |
| `RiskFactor` | 可解释风险因素 | suggested/confirmed/rejected | Signal、Evidence | Mainline、Report、Task | 必须带 confidence 和 evidence refs |
| `ConflictGroup` | 相互冲突的证据/信号组 | open/resolved/waived | Evidence、Signal | Review、Report | 未解决冲突不得形成无保留事实结论 |
| `Mainline` | 事件主线模型 | draft/quality_failed/pending_confirmation/confirmed/world_state_generated/archived | SignalPackage、Evidence | WorldState | confirmed 后修改必须生成新版本 |
| `MainlineVersion` | 主线版本快照 | draft/frozen/superseded | Mainline | WorldState | 用于 diff、回滚、审阅 |
| `WorldState` | 可推演世界状态输入包 | draft/frozen/superseded | MainlineVersion | WorldlineRun | 输入版本必须锁定 |
| `Stakeholder` | 从主线/世界状态识别的利益方 | candidate/reviewed/rejected | Mainline、Evidence | AgentProfile | 未复核不得生成 Agent Profile |
| `WorldlineRun` | 世界线推演运行 | pending/running/completed/failed/canceled/superseded | WorldState | WorldlineNode、CouncilSession | failed 必须有失败归因 |
| `WorldlineNode` | 世界线分支节点 | generated/reviewed/applied/superseded | WorldlineRun | CouncilSession | 节点详情必须带证据 refs |
| `WorldlineIntervention` | 处置动作注入 | draft/applied/rejected | User、WorldlineRun | WorldlineRun | 处置动作必须写约束和 reason |
| `AgentTemplate` | 专业 Agent 模板 | draft/active/archived | Config | AgentProfile | 模板变化走配置发布 |
| `AgentProfile` | 事件利益方 Agent Profile | draft/checking/ready/blocked/waived | Stakeholder、WorldlineRun | CouncilSession | 必须生成 `user.md`、`soul.md`、`agent.md` |
| `LlmCall` | LLM 调用记录 | pending/completed/failed | Prompt、Provider、InputRefs | Extraction、Council、Report | 必须记录 token、cost、latency、model |
| `CouncilSession` | 多 Agent 研判会话 | created/profile_checking/running/schema_validating/blocked/completed/applied | WorldlineNode、AgentProfile | CouncilResult | profile 未通过不得运行 |
| `CouncilResult` | Council 研判结果 | pending/pass/fail/waived/applied | CouncilSession | WorldlineRun、Report | schema invalid 或无证据结论阻断 |
| `BlockedClaim` | 被阻断声明 | blocked/waived | LlmCall、CouncilResult、ReportClaim | Review | 不得进入正式结论 |
| `Report` | 汇报输出对象 | draft/claim_validation_failed/submitted_review/review_returned/approved/published/exported/archived | Topic、Mainline、Worldline、Council | Task、Retrospective | published 后修改必须新版本 |
| `ReportClaim` | 报告事实声明 | pending/valid/invalid/blocked | ReportVersion、Evidence | Review | 每条事实声明单独校验 |
| `Task` | 处置任务 | suggested/in_progress/completed/overdue/blocked | Report、User | TaskEvent | 状态变化写 task_events 和 audit |
| `Retrospective` | 复盘对象 | draft/submitted_review/approved/published | Report、Task | KnowledgeItem、CaseMemory | 复盘知识不能直接污染生产规则 |
| `CaseMemory` | 案例记忆 | draft/reviewed/published/archived | Retrospective | CaseLibraryEntry | 发布前必须 review |
| `KnowledgeItem` | 可复用知识项 | draft/review_failed/approved_for_memory/published | Retrospective | Config/CaseLibrary | 未审批不得影响生产配置 |
| `CaseLibraryEntry` | 案例库条目 | active/archived/pending_review | CaseMemory | Topic/Report | 应用建议冲突时返回 409 |
| `ConfigVersion` | 配置版本 | draft/regression_running/regression_failed/approval_pending/published/rolled_back | Admin | Runtime config | 发布前必须回归和审批 |
| `ConfigRelease` | 配置发布记录 | published/rollback_available/rollback_failed/rolled_back | ConfigVersion | Runtime config | 回滚必须说明影响范围 |
| `Review` | 第三方检查任务 | pending/pass/fail/waived | Any object | ReleaseGate | fail 阻断冻结和发布 |
| `AuditLog` | 审计日志 | append-only | Mutation | Ops/Review | 禁止物理删除 |

## 对象链路

```text
DataSource -> CollectionJob -> CollectionRun -> RawRecord
RawRecord -> Signal -> SignalPackage -> Mainline -> WorldState -> WorldlineRun
RawRecord/MediaAsset -> Evidence -> RiskFactor -> Mainline/Report
Mainline -> Stakeholder -> AgentProfile -> CouncilSession -> CouncilResult
Topic -> Report -> Task -> Retrospective -> CaseMemory -> CaseLibraryEntry
ConfigVersion -> ConfigRelease -> Runtime behavior
```

## 禁止链路

- 前端直接创建 `Signal`、`Evidence`、`Mainline`、`CouncilResult` 或 `ReportClaim` 作为正式业务事实。
- 无 `RawRecord` 或 `EvidenceRef` 的报告事实判断。
- 未复核 `Stakeholder` 直接生成 `AgentProfile`。
- 未通过 Review 的 `CouncilResult` 直接回写世界线。
- 未回归和审批的 `ConfigVersion` 直接发布。
