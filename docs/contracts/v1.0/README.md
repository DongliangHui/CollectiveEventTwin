# CollectiveEventTwin S0 合同冻结包 v1.0

日期：2026-05-09

状态：冻结版

来源：

- `docs/production-plan-v1.0-20260509.md`
- `docs/api-db-contract-v1.0-20260509.md`
- `docs/atomic-task-backlog-v1.0.md`
- `packages/contracts/openapi/v1.0.yaml`
- `docs/alembic-migration-order-v1.0.md`

## 冻结结论

S0 目标是冻结后续派工所需的对象、页面、路由、API、DB、审计、RBAC、页面状态、错误码、Review、LLM、证据引用、合成数据、数据策略、环境、视觉基线、workflow 状态和发布门禁。

本目录是 S1 开发的输入边界。S1 不得绕过这些合同直接实现临时接口、运行时 mock、前端-only 业务状态或无审计 mutation。

## 文件清单

| S0 ID | 文件 | 冻结内容 |
| --- | --- | --- |
| S0-F000 | `object-model.md` | 业务对象字典 |
| S0-F001 | `page-inventory.md` | 11 个核心页面清单 |
| S0-F002 | `routing-contract.md` | 路由参数和跳转合同 |
| S0-F003 | `api-style-guide.md` | API 命名、响应、分页、mutation 规范 |
| S0-F004 | `db-style-guide.md` | 数据库命名、字段、索引、迁移规范 |
| S0-F005 | `audit-contract.md` | 审计对象和必审计动作 |
| S0-F006 | `rbac-matrix.md` | 角色、页面、动作、数据权限矩阵 |
| S0-F007 | `page-state-matrix.md` | 页面状态和浏览器验收矩阵 |
| S0-F008 | `error-code-contract.md` | HTTP 与业务错误码 |
| S0-F009 | `review-schema.md` | 第三方检查对象、状态、门禁 |
| S0-F010 | `llm-output-contract.md` | LLM 输出、调用、校验和阻断合同 |
| S0-F011 | `evidence-reference-contract.md` | 证据引用格式和校验规则 |
| S0-F012 | `synthetic-data-contract.md` | 合成数据全链路标记合同 |
| S0-F013 | `data-policy-boundary.md` | 禁用数据策略和阻断行为 |
| S0-F014 | `env-contract.md` | dev/test/staging/prod 环境隔离 |
| S0-F015 | `visual-baseline-contract.md` | 截图基线、diff、routeable state |
| S0-F016 | `workflow-state-contract.md` | workflow 状态、幂等、失败重试 |
| S0-F017 | `release-gate.md` | P0/P1 blocker、豁免、DCP |

## S1 准入

S1 开发只能在以下条件满足后启动：

- 18 个合同文件存在且能对应 S0-F000 至 S0-F017。
- `packages/contracts/openapi/v1.0.yaml` 能解析且本地 `$ref` 完整。
- `docs/alembic-migration-order-v1.0.md` 覆盖 API/DB 合同列出的表。
- 自检记录为 PASS 或仅有非阻断项。
