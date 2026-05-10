# Frontend Production Restart Backlog v1.0

日期：2026-05-09
依据：`docs/atomic-task-backlog-v1.0.md`、`docs/reviews/frontend-gap-audit-v1.0-20260509.md`

## 当前真实起点

后端/API/DB 已推进到 S7B 级别；前端生产实现未同步完成。前端重启应从 S1 开始补基础平台，再进入 S2 数据源治理和 S3A City 页冻结。

## P0 重启顺序

1. S1-FE-001 登录页：成功、账号不存在、密码错误、禁用/锁定、loading、error。
2. S1-FE-002 会话：token refresh、logout、过期回登录、trace_id 错误展示。
3. S1-FE-003 权限：`/auth/me`、`/auth/permissions` 驱动菜单和按钮。
4. S1-FE-004 用户/角色：列表、新建、编辑、禁用、重复数据、越权。
5. S1-FE-005 审计：筛选、详情、按对象追溯 mutation。
6. S1-FE-006 Review：创建、列表、详情、通过、退回、waive、gate-check。
7. S1-FE-007 Ops Health：API/DB/workers/workflow/error queue/retry queue/metrics。
8. S2-FE-001 数据源治理：类型列表、source CRUD、policy check、blocked 状态。
9. S2-FE-002 Collection Job：列表、详情、创建、编辑、启动 run、cancel、retry。
10. S2-FE-003 Raw Records：列表、详情、标签、lineage、masked payload。
11. S2-FE-004 Import/Processing：file/public/media/official API import、normalization、dedup、quality。
12. S3A-FE-001 City 页冻结：补齐状态矩阵和真实点击，不再只做 route smoke。
13. S3B-FE-001 Topic 态势页：替换 `StructuredPage`，按页面合同实现完整 dashboard。
14. S4A-FE-001 Signal 工作台：搜索、详情、抽取 run、信号包 create/add/remove。
15. S4B-FE-001 Evidence 复核：证据详情、复核、附件、媒体处理、脱敏、冲突。
16. S5-FE-001 Mainline/World State：builder、节点编辑冲突、质量检查、确认、利益方复核。
17. S6-FE-001 Worldline/Agent/Council：推演、profile readiness、Council 全状态。
18. S7A-FE-001 Report/Task：报告编辑、审批、发布、导出、任务状态流转。
19. S7B-FE-001 Memory/Library/Config：在静态设计 body 基础上补齐状态矩阵和失败态。
20. S8-FE-001 重新发布验收：11 页 desktop/mobile、network、console、截图 diff、权限态。

## 冻结门禁

- 每个 FE slice 必须有页面级 API 查询和至少一个业务 mutation。
- 每个页面必须覆盖 loading、empty、error、degraded、no permission、正常态。
- 每个页面必须生成 Playwright 记录：network、console、截图。
- `StructuredPage` 只能作为临时 fallback，不能作为页面冻结依据。
- 静态设计页只能作为视觉参考，不能作为产品数据源或交互替代。
