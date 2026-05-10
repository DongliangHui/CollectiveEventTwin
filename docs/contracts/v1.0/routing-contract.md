# 路由参数合同 v1.0

状态：冻结版

## 通用路由规则

- 所有客户可见业务路由必须由权限系统判断可访问性。
- URL 参数只表示对象定位，不承载正式业务状态。
- 筛选、排序、分页可以放 query string，但必须提交给后端 API 处理。
- hover、tooltip、panel open/close 可以留在前端本地状态。
- 页面跳转必须优先使用后端返回的 `actions[].href` 或约定 route builder。

## 路由表

| Route | 输入参数 | Query | 输出/跳转 | 权限 |
| --- | --- | --- | --- | --- |
| `/login` | 无 | `redirect` 可选 | 成功后跳转默认 City | anonymous |
| `/cities/:cityId` | `cityId` | `region`、`source_type`、`risk_level`、`rank_mode` | 创建 Topic 后跳 `/topics/:topicId/situation` | `city:view` |
| `/topics/:topicId/situation` | `topicId` | `source_type`、`time_window`、`stance` | 进入信号页或候选主线 | `topic:view` |
| `/topics/:topicId/signals` | `topicId` | `q`、`status`、`source_type`、`page`、`page_size` | 打开 signal detail、创建 signal package | `signal:view` |
| `/evidence-reviews/:reviewId` | `reviewId` | `tab` | 复核 evidence、绑定 media、生成 risk factor | `evidence:review` |
| `/mainlines/:mainlineId/builder` | `mainlineId` | `version` 可选 | 确认后生成 World State | `mainline:edit` |
| `/worldline-runs/:runId/simulation` | `runId` | `branch`、`node_id` | 选择节点创建 Council Session | `worldline:view` |
| `/council-sessions/:sessionId` | `sessionId` | `agent_profile_id` 可选 | 应用 Council Result 或生成报告草稿 | `council:run` |
| `/reports/:reportId/brief` | `reportId` | `version` 可选 | 提交审阅、发布、导出、生成任务 | `report:view` |
| `/retrospectives/:retrospectiveId/memory` | `retrospectiveId` | `tab` | 知识项提交审批、发布案例库 | `retrospective:edit` |
| `/cases/library` | 无 | `q`、`tag`、`scenario_type`、`page` | 应用案例建议 | `library:view` |
| `/config` | 无 | `config_type`、`status` | 创建配置版本、回归、发布、回滚 | `config:admin` |

## 跳转约束

| 来源 | 动作 | 目标 | 后端前置 |
| --- | --- | --- | --- |
| City | 从城市事件创建主题 | Topic Situation | `POST /api/v1/city-events/{id}/create-topic` 成功 |
| Topic Situation | 查看数据/信号 | Signal Workbench | Topic 状态为 `active` |
| Signal Workbench | 进入主线建模 | Mainline Builder | SignalPackage 状态可作为主线输入 |
| Evidence Review | 回到主线建模 | Mainline Builder | Evidence 复核状态刷新 |
| Mainline Builder | 生成世界状态 | Worldline Simulation | Mainline `confirmed` 且 WorldState 已创建 |
| Worldline Simulation | 创建 Council | Agent Council | WorldlineRun `completed` 且节点版本锁定 |
| Agent Council | 生成报告草稿 | Report Brief | CouncilResult review PASS |
| Report Brief | 进入复盘 | Retrospective Memory | Report `published` |
| Retrospective Memory | 发布案例 | Case Library | KnowledgeItem approved |
| Config | 发布配置 | Config | Regression PASS 且 Review PASS |
