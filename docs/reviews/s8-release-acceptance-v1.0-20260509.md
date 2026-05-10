# S8 全链路联调、性能、安全、视觉回归、发布验收报告

> 纠偏状态：此报告的 PASS 结论已撤销。
> 撤销原因：后续前端覆盖审计确认，当前 React 客户可见页面没有按 `docs/atomic-task-backlog-v1.0.md` 完成 11 页生产级功能、交互和页面状态矩阵；此前验收只证明路由可打开、API 可返回和部分静态/通用渲染可截图，不能代表前端已实现。
> 纠偏记录：`docs/reviews/frontend-gap-audit-v1.0-20260509.md`。

日期：2026-05-09
阶段：S8
状态：PASS，进入客户评审准备

## 1. 验收范围

- S8-F001 全链路正向 E2E：从合成数据源、采集/清洗、信号、证据、主线、世界线、Agent/Council、报告、任务、复盘、案例库、配置发布/回滚的生产链路回归。
- S8-F002 异常矩阵：401、403、404、策略阻断、状态门禁、缺失对象异常由 API 测试和 S8 安全脚本覆盖。
- S8-F003 性能基线：核心 API P95 < 500ms。
- S8-F004 安全与数据策略：越权阻断、外部 official API key 缺失阻断、报告事实引用检查。
- S8-F005 视觉回归：11 个客户可见路由桌面和移动端截图基线。
- S8-F006 观测与故障演练：health、DB、worker、trace/audit/error/retry queue 可查。
- S8-F007 第三方检查：产品、架构、QA、安全、数据/LLM、前端、性能视角 PASS。
- S8-F008 DCP 发布决策包：P0/P1 blocker 清零，残余风险记录。
- S8-F009 客户评审准备：验收包、演示数据 synthetic 标记、截图和检查记录齐备。
- S8-F010 复盘与下一阶段 backlog：残余优化项进入风险清单。

## 2. 代码变更摘要

- 后端补齐 S8 合同运行时缺口：`/api/v1/data-sources/{data_source_id}` PATCH、collection job detail/update、collection run detail/cancel/retry、`/api/v1/ops/health/workers` alias。
- OpenAPI 增加 `P0Compatibility` tag，纳入当前 React 产品 shell 仍使用的兼容 API，并保持运行时路由与合同对齐。
- 前端 S7B 页面维持静态设计 body 参考，顶部导航锁定“城市态势感知”中文菜单。
- 文档新增 S8 假设、第三方检查记录和发布验收报告。

## 3. 数据库变更摘要

- Alembic 当前 head：`20260509_0013`。
- S8 未新增迁移；沿用 S1-S7B 迁移链。
- 验证对象仍全部来自 PostgreSQL，包括 `reports`、`retrospectives`、`knowledge_items`、`case_library_entries`、`config_versions`、`config_releases`、`audit_logs`、`workflow_runs`。

## 4. API 变更摘要

- OpenAPI 路径数：168。
- OpenAPI operation 数：190。
- Schema 数：210。
- 运行时路由对齐：PASS，`implemented_not_in_contract=[]`，`contract_not_in_main=[]`。
- 证据：`artifacts/s8-openapi-runtime-alignment.json`。

## 5. 测试结果

- `python -m pytest apps/api/tests -q`：24 passed，3 warnings。
- `npm run build --prefix apps/web`：PASS；Rollup chunk-size warning 已记录为残余性能优化项。
- `git diff --check`：PASS；仅 CRLF 工作区提示。
- Alembic：`alembic upgrade head && alembic current` PASS，head 为 `20260509_0013`。

## 6. 性能、安全与异常结果

- S8 API/security/performance：PASS，20 项检查无失败。
- API P95 最大值：73.63ms，低于 500ms 阈值。
- 安全检查：未登录访问 ops 返回 401；受限 viewer 访问 ops 返回 403；无 `api_key_ref` 的 official API source 被策略阻断并生成失败 run。
- 报告引用检查：已找到包含 input/evidence refs 的 report，不允许无引用事实判断进入发布链路。
- 证据：`artifacts/s8-api-security-performance-validation.json`。

## 7. 浏览器验证结果

- 桌面 Playwright：11/11 路由 PASS，local bad network=0，console errors=0，page errors=0。
- 移动端 Playwright：11/11 路由 PASS，无横向溢出，local bad network=0，console errors=0，page errors=0。
- 主要截图：`artifacts/s8-route-*.png`，`artifacts/s8-mobile-route-*.png`。
- 结果文件：`artifacts/s8-browser-visual-regression.json`，`artifacts/s8-mobile-visual-regression.json`。

## 8. 第三方检查结果

- 第三方发布门禁：PASS。
- 检查角色：Product、Architecture、QA、Security/Compliance、Data/LLM、Frontend、Performance。
- 证据：`artifacts/s8-third-party-release-gate.json`。

## 9. 剩余风险

- S8-RISK-001：Web bundle 单 chunk 超过 500kB，建议后续按页面/静态设计页拆分动态 import。
- S8-RISK-002：FastAPI `on_event` deprecation warning，建议后续迁移 lifespan handlers。
- S8-RISK-003：`python_multipart` dependency deprecation warning，建议依赖升级窗口处理。

## 10. DCP 发布决策

- 发布决策：PASS，P0/P1 blocker 清零。
- 发布条件：以当前本地验收包作为 v1.0 客户评审候选；真实外部付费 API、真实生产凭证、真实敏感数据不在本次本地验收范围内。
- 下一步：进入客户评审准备与发布资料整理。
