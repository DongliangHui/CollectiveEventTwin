# Frontend Gap Audit v1.0

日期：2026-05-09
结论：S8 发布验收撤销；前端生产级实现未完成。

## 1. 纠偏结论

此前 S8 PASS 结论不成立。它验证了：

- FastAPI、PostgreSQL、Alembic、OpenAPI 与后端测试链路基本可用。
- 11 个路由可以打开，且桌面/移动端截图脚本没有发现 local network、console、page error。

但它没有证明：

- 11 个客户可见页面均按原子任务实现。
- 每个页面都有计划要求的业务交互、状态矩阵、异常路径、权限态、第三方检查态。
- 前端页面没有依赖通用 renderer 或静态设计壳来替代生产 UI。

因此 S8 只能视为后端/API 与路由烟测通过，不能视为发布验收通过。

## 2. 代码审计证据

- `apps/web/src/App.tsx` 将 `city/risk/data/evidence/mainline/worldline/council/brief/memory/library/config` 全部路由到 `ApiDrivenProductPage`。
- `apps/web/src/p0-pages/ApiDrivenProductPage.tsx` 中，`city` 有较完整的定制页面实现。
- `memory/library/config` 使用 S7B 静态设计参考风格实现，但仍需补齐完整状态矩阵和操作覆盖。
- `risk/data/evidence/mainline/worldline/council/brief` 主要落到 `StructuredPage` 通用渲染器，不能等同于生产级页面实现。
- `apps/web/src/FoundationConsole.tsx` 和 `apps/web/src/S2SourceConsole.tsx` 是控制台式局部页面，不覆盖 S1/S2 所有前端原子任务。

## 3. 按原子计划的真实进度

| 阶段 | 后端/API/DB | 前端真实状态 | 纠偏状态 |
|---|---|---|---|
| S0 | 合同与文档基本完成 | 页面合同有，但未形成完整实现门禁 | 部分完成 |
| S1 | 登录、RBAC、审计、Review、Ops API 基本完成 | 缺少完整登录/权限/角色/审计/Review/Ops 产品页面闭环 | 未冻结 |
| S2 | 数据源、采集、导入、清洗 API 基本完成 | 仅有数据源 console，缺少完整 CRUD、状态矩阵和浏览器覆盖 | 未冻结 |
| S3A | City 后端与前端相对最完整 | City 页部分完成，但仍需逐项补状态、权限、异常和截图基线 | 部分完成 |
| S3B | Topic API 基本完成 | 主题态势页仍为通用 renderer，不是完整页面实现 | 未完成 |
| S4A | 信号 API 基本完成 | 数据/信号工作台仍为通用 renderer | 未完成 |
| S4B | 证据/多媒体 API 基本完成 | 证据复核页仍为通用 renderer | 未完成 |
| S5 | 主线/World State/利益方 API 基本完成 | 主线页面仍为通用 renderer，利益方复核前端缺口明显 | 未完成 |
| S6 | 世界线/Agent/Council API 基本完成 | 世界线、Profile readiness、Council 状态页未按原子任务完成 | 未完成 |
| S7A | 报告/任务 API 基本完成 | 报告审批、导出、任务闭环前端未完整实现 | 未完成 |
| S7B | 复盘/案例库/配置 API 基本完成 | 三页有静态参考 body，但仍缺完整状态矩阵与交互验收 | 部分完成 |
| S8 | 后端、合同、烟测有记录 | 前端未完成，发布验收不成立 | 撤销 |

## 4. 当前真实里程碑

真实位置不是 S8 发布通过，而是：

后端/API/DB：接近 S7B 完成，需继续修复合同细节和扩充异常覆盖。
前端：应退回到 S1-S3A 之间重新排产，先补全基础平台和 City 页，再按 S3B -> S7B 顺序做生产页面。
S8：待前端生产实现完成后重新执行。

## 5. 必须重开的前端任务

1. S1 前端：登录、token refresh/logout、当前用户/权限、角色用户、审计、Review、Ops Health。
2. S2 前端：数据源 CRUD、collection job CRUD、run cancel/retry、raw records、processing runs、source health。
3. S3A 前端：City 页状态矩阵补齐，包括 empty/error/degraded/no permission/filter no result/map tile fail/media processing。
4. S3B 前端：主题态势页按静态/设计要求做完整 dashboard，不使用通用 `StructuredPage` 替代。
5. S4A 前端：信号检索工作台、信号详情、信号包 create/add/remove。
6. S4B 前端：证据复核、多媒体处理状态、脱敏、冲突提示、附件上传。
7. S5 前端：主线 builder、节点编辑冲突、质量检查、确认主线、World State、利益方复核。
8. S6 前端：世界线推演、Agent Profile readiness、Council running/provider error/schema invalid/blocked claims/applied 状态。
9. S7A 前端：报告详情/编辑/审阅/发布/导出、任务创建与状态流转。
10. S7B 前端：复盘、案例库、配置中心完整状态矩阵和失败态。
11. S8 前端：真实点击、network、console、截图 diff、移动端、权限态重验。

## 6. 后续执行门禁

- 不允许以路由可打开替代功能完成。
- 不允许以 `StructuredPage` 通用渲染替代计划中明确的生产页面。
- 不允许以静态设计页或截图通过替代真实 API 交互和状态矩阵。
- 每个页面冻结前必须给出页面级 Playwright 脚本，覆盖 loading、empty、error、degraded、no permission、正常态和至少一个业务 mutation。
