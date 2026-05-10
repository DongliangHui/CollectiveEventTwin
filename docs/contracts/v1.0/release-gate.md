# 发布冻结门禁 v1.0

状态：冻结版

## Gate 类型

| Gate | 适用 |
| --- | --- |
| Page Freeze | 客户可见页面冻结 |
| API Freeze | API/DTO 合同冻结 |
| Data Freeze | 数据源、采集、算法输出冻结 |
| Agent Freeze | Agent Profile、Council 输出冻结 |
| Report Freeze | 报告发布和导出 |
| Config Freeze | 配置发布 |
| DCP | 发布决策 |

## 阻断等级

| 等级 | 定义 | 行为 |
| --- | --- | --- |
| P0 | 安全、数据、结论、发布链路严重问题 | 必须修复，不可豁免 |
| P1 | 核心业务链路、验收状态、可追踪性问题 | 默认阻断，可业务批准豁免 |
| P2 | 非核心体验、文案、低风险观测问题 | 可进入风险清单 |

## P0 Blocker

- 产品运行时 mock 数据。
- 前端-only 业务状态。
- 无数据库记录的 Agent/LLM 结论。
- 无 evidence refs 的报告事实判断。
- 高危越权。
- 敏感信息泄露。
- 禁用数据策略被绕过。
- schema invalid 的 Council 或报告输出被应用。
- claim validation failed 的报告被发布。

## 豁免规则

P1 豁免必须记录：

- 批准人。
- 原因。
- 风险。
- 有效期。
- 后续修复任务。

P0 不允许豁免。

## DCP 输入

- 所有 P0/P1 blocker 清零或有有效 P1 豁免。
- S8 全链路验收通过。
- 视觉回归 PASS。
- 第三方检查 PASS。
- 发布包包含残余风险清单。
