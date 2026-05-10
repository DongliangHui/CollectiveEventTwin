# 页面清单 v1.0

状态：冻结版

## 页面总览

| 序号 | 页面 | Route | View-model API | 主要对象 | 所属阶段 | 冻结条件 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 登录页 | `/login` | `POST /api/v1/auth/login`、`GET /api/v1/auth/me` | User、Session | S1 | 成功/失败/锁定/服务不可用均可验收 |
| 2 | 城市态势页 | `/cities/:cityId` | `GET /api/v1/cities/{id}/overview` | City、CityEvent、SourceHealth | S3A | 所有业务数据来自后端，截图 diff PASS |
| 3 | 主题态势页 | `/topics/:topicId/situation` | `GET /api/v1/topics/{id}/situation-view` | Topic、Signal、Mainline | S3B | 热度、情绪、传播、来源、候选主线可用 |
| 4 | 数据/信号页 | `/topics/:topicId/signals` | `GET /api/v1/topics/{id}/signal-workbench-view` | RawRecord、Signal、SignalPackage | S4A | 信号检索、入包、lineage、run 状态可用 |
| 5 | 证据复核页 | `/evidence-reviews/:reviewId` | `GET /api/v1/evidence-reviews/{id}/review-view` | Evidence、MediaAsset、RiskFactor | S4B | 复核、脱敏、冲突、媒体处理状态可用 |
| 6 | 主线建模页 | `/mainlines/:mainlineId/builder` | `GET /api/v1/mainlines/{id}/builder-view` | Mainline、Evidence、WorldState | S5 | 质量检查、版本 diff、确认主线可用 |
| 7 | 世界线推演页 | `/worldline-runs/:runId/simulation` | `GET /api/v1/worldline-runs/{id}/simulation-view` | WorldlineRun、WorldlineNode | S6 | 分支概率、节点详情、intervention diff 可用 |
| 8 | Agent Council 页 | `/council-sessions/:sessionId` | `GET /api/v1/council-sessions/{id}/council-view` | AgentProfile、CouncilResult | S6 | schema invalid、blocked claims、applied 状态可见 |
| 9 | 汇报输出页 | `/reports/:reportId/brief` | `GET /api/v1/reports/{id}/brief-view` | Report、ReportClaim、Task | S7A | 声明校验、审阅、发布、导出可用 |
| 10 | 复盘页 | `/retrospectives/:retrospectiveId/memory` | `GET /api/v1/retrospectives/{id}/memory-view` | Retrospective、KnowledgeItem | S7B | 知识沉淀需审批 |
| 11 | 案例库页 | `/cases/library` | `GET /api/v1/cases/library-view` | CaseLibraryEntry、CaseMemory | S7B | 搜索、相似案例、应用建议可用 |
| 12 | 配置页 | `/config` | `GET /api/v1/config/admin-view` | ConfigVersion、ConfigRelease | S7B | 回归、审批、发布、回滚可用 |

说明：v1.0 计划称“11 个核心页面”时，将复盘/案例库合并为知识沉淀链路；工程实现保留 12 个 routeable 页面，其中客户核心状态矩阵仍覆盖 11 类页面域。

## 页面导航链路

```text
Login
  -> City
  -> Topic Situation
  -> Signal Workbench
  -> Evidence Review
  -> Mainline Builder
  -> Worldline Simulation
  -> Agent Council
  -> Report Brief
  -> Retrospective Memory
  -> Case Library / Config
```

## 页面通用要求

每个客户可见页面必须：

- 通过页面级 view-model API 加载首屏业务事实。
- 返回 `page_state`、`permissions`、`refresh_at`、`data_freshness`、`degraded_sources`、`audit_context`、`primary_data`、`actions`。
- 不在前端计算正式业务判断。
- 不从 `worldline-observer-current/mock` 或静态 fixture 读取产品数据。
- 有 routeable state 和截图基线。
- 有真实点击验收，检查 network、console、关键截图。
- 冻结前创建 `frontend_page` review 并 PASS 或有批准豁免。
