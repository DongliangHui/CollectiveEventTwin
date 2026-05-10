# CollectiveEventTwin S1 基础平台开发计划 v1.0

日期：2026-05-09

状态：启动版

前置：

- `docs/contracts/v1.0/`
- `docs/reviews/s0-contract-freeze-v1.0-20260509-check.md`
- `packages/contracts/openapi/v1.0.yaml`
- `docs/alembic-migration-order-v1.0.md`

## 1. 阶段目标

S1 用 2 个纵切完成基础平台前置能力：

1. 身份、RBAC、审计闭环。
2. Review、Ops Health、Workflow Run、error/retry queue、metrics、trace_id 闭环。

冻结条件：

- 登录链路、权限、审计、检查任务、健康检查通过浏览器或脚本化验收。
- 所有 mutation 写审计。
- Review gate 能阻断冻结/发布。
- Workflow/Ops 能查询失败、重试、指标和 trace。

## 2. 输入合同

| 输入 | 用途 |
| --- | --- |
| `docs/contracts/v1.0/rbac-matrix.md` | 角色、权限点、页面/动作权限 |
| `docs/contracts/v1.0/audit-contract.md` | mutation 审计字段和动作 |
| `docs/contracts/v1.0/review-schema.md` | review 对象、状态、阻断规则 |
| `docs/contracts/v1.0/workflow-state-contract.md` | workflow run 状态、幂等、错误 |
| `docs/contracts/v1.0/error-code-contract.md` | 统一错误码 |
| `docs/contracts/v1.0/env-contract.md` | dev/test/staging/prod 行为 |
| `packages/contracts/openapi/v1.0.yaml` | API/DTO source-of-truth |
| `docs/alembic-migration-order-v1.0.md` | S1 migration 顺序 |

## 3. 纵切拆分

### Slice S1-A：Identity / RBAC / Audit

范围：

- `S1-F001` 登录成功/失败链路。
- `S1-F002` token 刷新和退出。
- `S1-F003` 当前用户和权限。
- `S1-F004` 用户和角色管理。
- `S1-F005` 审计查询。
- `S1-F019` trace_id 中间件基础。

后端交付：

- Alembic：`20260509_0002_identity_rbac_review_audit` 中的 identity/RBAC/audit 部分。
- SQLAlchemy models：Tenant、User、Role、Permission、RolePermission、UserRole、Session、AuditLog 扩展。
- Pydantic DTO：LoginRequest、AuthTokenPair、User、Role、Permission、AuditLog。
- Services：password verify、session issue/revoke、permission resolution、audit writer。
- API：`/api/v1/auth/*`、`/api/v1/users`、`/api/v1/roles`、`/api/v1/audit-logs`。

前端交付：

- 登录页接真实 API。
- 登录失败状态：空账号、空密码、账号不存在、密码错误、禁用、锁定、服务不可用。
- 顶部当前用户、菜单/按钮权限隐藏或禁用。
- 审计查询基础页或运维入口。

测试：

- 单元：密码校验、权限解析、audit writer。
- API：login/refresh/logout/me/permissions/users/roles/audit。
- 异常：401、403、404、409、422。
- 浏览器：真实登录成功/失败和权限差异。

### Slice S1-B：Review / Ops / Workflow Run

范围：

- `S1-F006` 创建检查任务。
- `S1-F007` 检查任务列表/详情。
- `S1-F008` 提交检查结果。
- `S1-F009` 检查模板配置。
- `S1-F010` 阻断检查。
- `S1-F011` 豁免记录。
- `S1-F012` API 健康检查。
- `S1-F013` DB 健康检查。
- `S1-F014` Worker 健康检查。
- `S1-F015` Workflow 状态查询。
- `S1-F016` Error queue 查询。
- `S1-F017` Retry queue 查询。
- `S1-F018` Metrics 上报。
- `S1-F019` trace_id 全链路透传补齐。

后端交付：

- Alembic：补齐 review tables、workflow run events、ops queues、metrics snapshots。
- SQLAlchemy models：ReviewTemplate、Review、ReviewResult、WorkflowRun 扩展、WorkflowRunEvent、OpsErrorQueue、OpsRetryQueue、MetricsSnapshot。
- Pydantic DTO：Review、ReviewTemplate、GateCheck、WorkflowRun、QueueItem、MetricsSnapshot、Health。
- API：`/api/v1/reviews*`、`/api/v1/review-templates`、`/api/v1/ops/*`、`/api/v1/workflow-runs`。
- Middleware：trace_id request/response/log propagation。

前端交付：

- 检查中心列表/详情/提交结果。
- gate-check 和 waive 操作入口。
- 运维健康页：API、DB、workers、workflow runs、error queue、retry queue、metrics。
- 错误态展示 trace_id。

测试：

- API：review CRUD、gate-check、waive、ops health、workflow query、queues、metrics。
- 异常：review fail 阻断、waive 缺 reason 拒绝、DB/worker degraded。
- 浏览器：检查任务创建/提交、健康页 degraded 状态、trace_id 可见。

## 4. 代码落点

| 区域 | 文件/目录 |
| --- | --- |
| API runtime | `apps/api/src/worldline_api/` |
| API tests | `apps/api/tests/` |
| Alembic | `apps/api/alembic/versions/` |
| Web runtime | `apps/web/src/` |
| Contracts | `packages/contracts/openapi/v1.0.yaml` |

## 5. 迁移计划

S1 优先实现：

1. `20260509_0002_identity_rbac_review_audit`
2. `20260509_0003_workflow_ops_contracts`

实现要求：

- 不改写 `20260508_0001_p0_core`。
- 旧 `audit_logs`、`workflow_runs` 用兼容性 ALTER 扩展。
- 权限点、review templates 使用幂等 seed，不写产品业务数据。
- migration 后 `GET /api/v1/ops/health/db` 返回当前 revision。

## 6. S1 验收清单

| 验收项 | 方法 | 通过标准 |
| --- | --- | --- |
| 登录成功 | API + browser | 返回 token，写 audit |
| 登录失败 | API + browser | 错误码明确，写 audit |
| token refresh/logout | API | session 状态正确 |
| 当前用户/权限 | API + browser | 菜单/按钮随角色变化 |
| 用户/角色管理 | API | 越权、重复、禁用被拒 |
| 审计查询 | API | 所有 mutation 可查 |
| Review 创建/列表/详情 | API + browser | pending 入库、分页正确 |
| Review PASS/FAIL | API | FAIL 生成 blocker 或修复任务入口 |
| Gate check | API | blocker 未清不能冻结 |
| Waive | API | 必须有批准人、理由、风险、有效期 |
| API/DB/Worker health | API + browser | ok/degraded/failed 可见 |
| Workflow runs | API | object_type/object_id 可追踪 |
| Error/retry queue | API | retryable 和 non-retryable 分开 |
| Metrics | API | p95、错误率、worker、workflow 指标可见 |
| Trace ID | API + logs + browser | response、错误页、日志一致 |

## 7. 风险和边界

- S1 不实现 S2 数据源采集业务，只实现能支撑 S2 的 source/review/ops 基础。
- S1 不冻结客户页面视觉，仅提供登录、检查中心、运维页的基础验收界面。
- S1 不允许使用前端-only 权限判断；后端必须做权限校验。
- S1 不允许用内存 mock 存储 session、review、audit、workflow run。

## 8. 第一批执行顺序

1. 写 S1-A 行为测试：login、permission、audit。
2. 实现 `20260509_0002` migration 的 identity/RBAC/audit 部分。
3. 实现 Auth/RBAC/Audit models、DTO、services、routes。
4. 接入前端登录和权限显示。
5. 写 S1-B 行为测试：review、ops、workflow、trace。
6. 补齐 `20260509_0002` review 部分和 `20260509_0003` workflow/ops migration。
7. 实现 Review/Ops/Workflow routes。
8. 接入检查中心和运维页。
9. 跑 API tests、浏览器验收、S1 第三方检查。
