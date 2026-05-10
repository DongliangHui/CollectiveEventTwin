# CollectiveEventTwin 完整项目功能点级开发计划

日期：2026-05-08

状态：功能点级派工计划

参考：

- `C:\Users\ROG\Desktop\一、项目总体开发周期.md`
- `docs/p0-production-grade-delivery-plan-20260508.md`

## 0. 交付原则

本计划按完整生产项目执行，不按 MVP 裁剪。

硬约束：

- 产品运行时不允许 mock 数据、静态 fixture、前端假数据。
- 前端每一个有业务含义的交互都必须调用后端 API，并查询或修改数据库状态。
- 所有页面展示数据必须来自 PostgreSQL，经 FastAPI 返回。
- 数据接入可以先从授权导入、公开样例、人工上传开始，但采集框架必须是真实代码。
- 算法、流程编排、Agent、LLM 必须是真实业务实现。
- 测试 fake provider、测试 fixture 只允许出现在自动化测试中。

每个功能点固定交付节奏：

```text
API 设计 -> 后端实现 -> 前端接入 -> 功能测试 -> 异常测试 -> 性能测试 -> 内部浏览器验收 -> 修复 -> 冻结
```

每个功能点固定测试责任：

- 后端 agent：API、数据库、服务、workflow、审计。
- 前端 agent：页面、状态、交互、错误态、权限态。
- 功能测试 agent：正常路径与数据一致性。
- 异常测试 agent：权限、非法输入、错误状态、外部依赖失败。
- 性能测试 agent：API p95、页面首屏、workflow 耗时、LLM 耗时。
- 浏览器测试 agent：内部浏览器真实点击验证。

## 1. 阶段排期

| 阶段 | 周期 | 业务目标 | 并行 agent |
| --- | --- | --- | --- |
| 0 | 第 1 周 | 需求冻结、API 合同、数据模型、测试矩阵 | 架构、产品、QA |
| 1 | 第 2-3 周 | 登录、权限、审计、导航、系统基础 | 后端 A、前端 A、QA A |
| 2 | 第 4-6 周 | 数据源、采集任务、原始数据治理 | 后端 A、数据 Agent、QA A/B |
| 3 | 第 7-8 周 | 城市态势、事件发现、主题创建 | 后端 B、前端 A、浏览器 QA |
| 4 | 第 9-11 周 | 信号检索、证据复核、风险因子 | 后端 B、算法 Agent、前端 A/B |
| 5 | 第 12-14 周 | 主线建模、World State、世界线推演 | 后端 C、算法 Agent、前端 B |
| 6 | 第 15-17 周 | Agent Council、LLM、Guardrails | LLM Agent、后端 C、QA B |
| 7 | 第 18-20 周 | 汇报、任务、审批、导出 | 后端 C、前端 B、QA A |
| 8 | 第 21-23 周 | 复盘、案例库、规则配置、回归 | 后端 D、前端 C、QA C |
| 9 | 第 24-26 周 | 全链路联调、性能、安全、发布验收 | 全部 agent |

## 2. 通用 API 与前端规范

通用响应：

- 成功：`{ data, meta, trace_id }`
- 业务失败：`{ error: { code, message, details }, trace_id }`
- 所有 mutation 返回最新对象或状态快照。
- 所有 mutation 必须写 `audit_logs`。
- 所有长任务必须写 `workflow_runs` 或领域 run 表。

通用前端状态：

- loading：首次加载、局部刷新、mutation pending。
- empty：无数据、无权限数据、筛选无结果。
- error：API 失败、权限失败、数据校验失败、workflow 失败。
- success：操作成功 toast 与页面数据刷新。
- stale：数据过期或 workflow 仍在运行。

通用异常测试：

- 401 未登录。
- 403 越权。
- 404 对象不存在。
- 409 状态冲突或重复提交。
- 422 参数/字段校验失败。
- 429 限流。
- 500/503 服务失败。

## 3. 阶段 1：登录、权限、导航、审计

### F001 用户登录

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/auth/login` |
| 请求 | `username`, `password`, `tenant_code?`, `remember_me?` |
| 前端功能 | 登录页提交账号密码 |
| 正常场景 | 登录成功，返回 access token、refresh token、用户信息、权限列表，跳转城市态势页 |
| 异常场景 | 账号不存在；密码错误；账号禁用；租户不存在；缺少用户名；缺少密码；连续失败被锁定；服务不可用 |
| 性能 | 登录 API p95 < 500ms |
| 测试 agent | 功能测试：成功登录；异常测试：错误密码/禁用/锁定；浏览器测试：真实表单提交和跳转 |

### F002 刷新登录态

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/auth/refresh` |
| 前端功能 | 页面刷新后自动续期 |
| 正常场景 | refresh token 有效，返回新 access token |
| 异常场景 | refresh token 过期；token 被吊销；token 租户不匹配 |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器刷新页面后仍保持登录；过期 token 自动回登录页 |

### F003 退出登录

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/auth/logout` |
| 前端功能 | 点击退出 |
| 正常场景 | token 被吊销，跳转登录页 |
| 异常场景 | 重复退出；无 token 退出；服务失败 |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器点击退出后无法访问受保护页面 |

### F004 当前用户信息

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/auth/me` |
| 前端功能 | 顶部用户信息、角色、当前租户 |
| 正常场景 | 返回用户、角色、权限、租户 |
| 异常场景 | 未登录；用户被禁用；租户被禁用 |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器校验用户名、角色、权限菜单 |

### F005 权限列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/auth/permissions` |
| 前端功能 | 控制菜单、按钮、页面访问 |
| 正常场景 | 返回页面权限、操作权限、数据权限 |
| 异常场景 | 未登录；权限版本过期 |
| 性能 | p95 < 300ms |
| 测试 agent | 不同角色登录后菜单和按钮不同 |

### F006 用户管理

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{user_id}`, `PATCH /api/v1/users/{user_id}/status` |
| 前端功能 | 用户列表、新建、编辑、启用、禁用 |
| 正常场景 | admin 新建用户；修改角色；禁用用户 |
| 异常场景 | 非 admin 操作；重复用户名；无效角色；禁用自己 |
| 性能 | 用户列表 p95 < 800ms |
| 测试 agent | 权限测试、表单校验、审计记录 |

### F007 角色管理

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/roles`, `POST /api/v1/roles`, `PATCH /api/v1/roles/{role_id}`, `PUT /api/v1/roles/{role_id}/permissions` |
| 前端功能 | 角色列表、角色权限配置 |
| 正常场景 | 创建角色；配置页面/按钮权限 |
| 异常场景 | 删除内置角色；配置不存在权限；非 admin |
| 性能 | p95 < 800ms |
| 测试 agent | 切换角色后权限立即生效 |

### F008 全局导航与上下文

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/navigation/context`, `PATCH /api/v1/navigation/context` |
| 前端功能 | 当前 city/topic/case/mainline/worldline/council/report 上下文保持 |
| 正常场景 | 切换上下文后刷新仍保留 |
| 异常场景 | 上下文对象不存在；无权限访问上下文对象 |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器跨页面跳转参数串联 |

### F009 审计查询

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/audit-logs` |
| 前端功能 | 审计中心按用户、动作、对象、时间、case 查询 |
| 正常场景 | 查询登录、数据查看、证据复核、主线确认、报告导出 |
| 异常场景 | 非审计角色访问；非法时间范围；分页越界 |
| 性能 | 10 万审计数据下 p95 < 1500ms |
| 测试 agent | 每个 mutation 后审计中心可查 |

## 4. 阶段 2：数据源、采集任务、原始数据

### F010 数据源列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/data-sources` |
| 前端功能 | 数据源配置页列表、筛选、分页 |
| 正常场景 | 按类型、状态、健康、授权模式筛选 |
| 异常场景 | 非数据管理员访问；非法筛选值 |
| 性能 | 1000 数据源 p95 < 1000ms |
| 测试 agent | 浏览器筛选组合：类型+状态+健康 |

### F011 新建数据源

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/data-sources` |
| 前端功能 | 新建 public_web、official_api、authorized_export、manual_upload 数据源 |
| 正常场景 | 表单填写完整，新数据源创建成功 |
| 异常场景 | private_chat/cookie_pool/captcha_bypass 被拒；重复 source_code；缺授权说明；trust 超范围 |
| 性能 | p95 < 800ms |
| 测试 agent | 新建成功后列表可见，审计可查 |

### F012 编辑数据源

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/data-sources/{source_id}` |
| 前端功能 | 修改名称、可信度、保留策略、字段映射、权重 |
| 正常场景 | 修改后新采集使用新配置 |
| 异常场景 | 修改不存在数据源；非 admin；非法字段映射 |
| 性能 | p95 < 800ms |
| 测试 agent | 修改 trust 后信号可信度重新计算可追踪 |

### F013 启停数据源

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/data-sources/{source_id}/status` |
| 前端功能 | 启用、停用、归档数据源 |
| 正常场景 | 停用后不可创建新采集 run |
| 异常场景 | 正在运行的 source 禁用需提示；重复禁用 |
| 性能 | p95 < 500ms |
| 测试 agent | 浏览器停用后运行按钮不可用 |

### F014 数据源健康检查

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/data-sources/{source_id}/health-check`, `GET /api/v1/data-sources/{source_id}/health` |
| 前端功能 | 点击测试连接，展示 last_success、last_error、latency |
| 正常场景 | 连接成功，健康状态 healthy |
| 异常场景 | 超时；认证失败；字段映射失败；网络不可达 |
| 性能 | 单 source health check < 5s |
| 测试 agent | 异常测试注入无效 URL/无效 token |

### F015 创建采集任务

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/collection-jobs` |
| 前端功能 | 配置数据源、关键词、地域、时间范围、频率 |
| 正常场景 | 创建一次性/定时采集任务 |
| 异常场景 | 数据源停用；时间范围非法；关键词为空；无权限 |
| 性能 | p95 < 800ms |
| 测试 agent | 创建后任务列表显示 pending |

### F016 采集任务列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/collection-jobs` |
| 前端功能 | 查看任务、状态、来源、频率、最近运行 |
| 正常场景 | 分页、筛选、排序 |
| 异常场景 | 非法状态筛选；跨租户数据不可见 |
| 性能 | 1 万任务 p95 < 1500ms |
| 测试 agent | 浏览器筛选 running/failed/scheduled |

### F017 运行采集任务

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/collection-jobs/{job_id}/run` |
| 前端功能 | 点击运行，启动 collection_run/workflow |
| 正常场景 | 生成 run，状态 running，最终 succeeded |
| 异常场景 | job 不存在；source disabled；已有 run 在运行；adapter 报错 |
| 性能 | run 创建 p95 < 500ms |
| 测试 agent | 浏览器点击运行后轮询状态 |

### F018 暂停采集任务

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/collection-jobs/{job_id}/pause` |
| 前端功能 | 暂停定时任务或运行中任务 |
| 正常场景 | job 状态 paused |
| 异常场景 | 已完成任务不能暂停；无权限 |
| 性能 | p95 < 500ms |
| 测试 agent | 暂停后不会继续产生新 run |

### F019 重试采集 Run

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/collection-runs/{run_id}/retry` |
| 前端功能 | failed run 点击重试 |
| 正常场景 | 新 run 关联原 run，幂等去重 |
| 异常场景 | succeeded run 不可重试；原 job 已禁用 |
| 性能 | p95 < 500ms |
| 测试 agent | 重试不重复写 raw_records |

### F020 采集 Run 详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/collection-runs/{run_id}` |
| 前端功能 | 查看 run counters、错误、耗时、raw record 数量 |
| 正常场景 | 展示 accepted、blocked、duplicated、failed |
| 异常场景 | run 不存在；无权限 |
| 性能 | p95 < 800ms |
| 测试 agent | failed run 可看到 adapter/policy/db 错误 |

### F021 授权数据导入

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/imports/authorized-export` |
| 前端功能 | 上传 JSON/CSV/XLSX 授权导出文件 |
| 正常场景 | 文件解析，生成 collection_run 和 raw_records |
| 异常场景 | 文件类型非法；字段缺失；重复上传；文件过大；编码错误 |
| 性能 | 10 万行导入可分批完成，首个响应 < 2s |
| 测试 agent | 浏览器上传成功/失败文件 |

### F022 原始记录列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/raw-records` |
| 前端功能 | 查看原始记录摘要、来源、时间、地域、状态 |
| 正常场景 | 关键词、来源、时间、状态筛选 |
| 异常场景 | 无权限查看原文；非法分页 |
| 性能 | 100 万记录索引查询 p95 < 2000ms |
| 测试 agent | 查询结果与 DB 一致 |

### F023 原始记录详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/raw-records/{raw_id}` |
| 前端功能 | 查看 raw payload、masked text、source metadata |
| 正常场景 | 有权限用户查看脱敏详情 |
| 异常场景 | 原文无权限；记录不存在；敏感字段越权 |
| 性能 | p95 < 800ms |
| 测试 agent | 敏感信息默认脱敏 |

### F024 原始记录标记

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/raw-records/{raw_id}/status` |
| 前端功能 | 标记 irrelevant、duplicate、low_trust、needs_review |
| 正常场景 | 状态更新并写审计 |
| 异常场景 | 已进入 confirmed evidence 的 raw 不可直接删除；无权限 |
| 性能 | p95 < 500ms |
| 测试 agent | 状态变化影响后续 signal 生成 |

## 5. 阶段 3：城市态势、事件发现、主题态势

### F025 城市列表与切换

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/cities`, `PATCH /api/v1/navigation/context/city` |
| 前端功能 | 城市、区县切换 |
| 正常场景 | 切换后地图、指标、榜单刷新 |
| 异常场景 | 城市不存在；无权限城市；数据为空 |
| 性能 | 城市列表 p95 < 500ms |
| 测试 agent | 浏览器切换城市后 URL/context 保持 |

### F026 城市态势总览

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/cities/{city_id}/situation` |
| 前端功能 | 今日事件总量、新增事件、最高热度、视频/直播量、讨论量、多平台事件数 |
| 正常场景 | 返回指标和更新时间 |
| 异常场景 | 无数据；指标计算失败；时间范围非法 |
| 性能 | p95 < 1500ms |
| 测试 agent | 指标与 DB 聚合一致 |

### F027 城市地图图层

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/cities/{city_id}/map-layers` |
| 前端功能 | 事件点位、热力、聚合点、视频/直播点、传播路径、区域边界 |
| 正常场景 | 按时间范围和筛选条件返回 GeoJSON |
| 异常场景 | 地图服务失败；非法 bbox；无点位 |
| 性能 | 5000 点位 p95 < 2000ms |
| 测试 agent | 浏览器点位可点击，图层开关生效 |

### F028 城市图层状态保存

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/user-view-state/city-map` |
| 前端功能 | 保存 map/satellite/heat、打开图层、缩放位置 |
| 正常场景 | 刷新后恢复图层状态 |
| 异常场景 | 非法图层 ID；未登录 |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器刷新验证状态保持 |

### F029 城市事件排行榜

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/cities/{city_id}/event-rankings` |
| 前端功能 | 综合热度、讨论量、传播速度、视频/直播排行切换 |
| 正常场景 | 不同 rank_type 返回不同排序 |
| 异常场景 | rank_type 非法；空结果 |
| 性能 | p95 < 1200ms |
| 测试 agent | 排序结果由后端返回，不在前端排序 |

### F030 城市事件筛选

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/cities/{city_id}/events` |
| 前端功能 | 按事件类型、区域、来源、时间、风险等级筛选 |
| 正常场景 | 多条件筛选返回事件列表 |
| 异常场景 | 时间范围过大；非法区域；无结果 |
| 性能 | p95 < 1500ms |
| 测试 agent | 浏览器组合筛选并检查 API query |

### F031 事件详情抽屉

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/events/{event_id}` |
| 前端功能 | 地图点、榜单、时间线点击打开同一事件详情 |
| 正常场景 | 展示标题、地点、首次发现、热度、来源、情绪、诉求、话题 |
| 异常场景 | 事件不存在；无权限；事件已归档 |
| 性能 | p95 < 800ms |
| 测试 agent | 浏览器从地图和榜单双入口打开同一详情 |

### F032 事件关注

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/events/{event_id}/follow`, `DELETE /api/v1/events/{event_id}/follow` |
| 前端功能 | 关注/取消关注事件 |
| 正常场景 | 状态落库，筛选“我关注的”可见 |
| 异常场景 | 重复关注；事件不存在；无权限 |
| 性能 | p95 < 500ms |
| 测试 agent | 刷新页面后关注状态保持 |

### F033 从事件创建主题

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/events/{event_id}/topics` |
| 前端功能 | 城市事件详情点击“加入主题/创建主题” |
| 正常场景 | 创建 topic 并跳转主题态势页 |
| 异常场景 | 重复创建；事件信号不足；无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 浏览器完成事件到主题跳转 |

### F034 主题态势总览

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/topics/{topic_id}/situation` |
| 前端功能 | 主题名、阶段、状态、核心指标、传播趋势、情绪立场 |
| 正常场景 | 指标从 signals/raw/evidence 聚合 |
| 异常场景 | topic 不存在；topic 无信号；计算失败 |
| 性能 | p95 < 2000ms |
| 测试 agent | 页面指标与 API 返回一致 |

### F035 主题趋势

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/topics/{topic_id}/trends` |
| 前端功能 | 热度趋势、同城讨论趋势、平台分布、传播路径 |
| 正常场景 | 切换 1h/3h/6h/24h 返回不同序列 |
| 异常场景 | 非法窗口；无时间序列 |
| 性能 | p95 < 1200ms |
| 测试 agent | 图表数据不由前端伪造 |

### F036 主题候选主线

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/topics/{topic_id}/candidate-mainlines` |
| 前端功能 | 显示候选主线、概率、证据缺口、进入主线建模 |
| 正常场景 | 返回候选主线池 |
| 异常场景 | 证据不足；topic 未激活 |
| 性能 | p95 < 1500ms |
| 测试 agent | 点击候选主线进入主线页并带参数 |

## 6. 阶段 4：数据/信号检索、证据复核、风险因子

### F037 信号搜索

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/signals/search` |
| 前端功能 | 关键词、语义、同区域、同标签、同平台、时间窗口、相似信号搜索 |
| 正常场景 | 返回分页 signals 和聚合统计 |
| 异常场景 | 空关键词；非法时间；搜索服务失败 |
| 性能 | p95 < 2000ms |
| 测试 agent | 多条件搜索结果与后端一致 |

### F038 热门聚合

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/signals/hot-clusters` |
| 前端功能 | 热门问题排名、热度、升温、来源构成、负向情绪、可信度、成线相关度 |
| 正常场景 | 返回 top clusters |
| 异常场景 | 数据不足；聚类失败 |
| 性能 | p95 < 3000ms |
| 测试 agent | 点击“一键汇集信号”后进入草稿区 |

### F039 信号详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/signals/{signal_id}` |
| 前端功能 | 查看原始片段摘要、来源链、真实性、情绪代表性、传播影响、相关推荐 |
| 正常场景 | 展示 signal、raw_records、evidence、related_signals |
| 异常场景 | signal 不存在；敏感内容无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 详情证据引用可点击 |

### F040 信号加入草稿区

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/signal-packages/{package_id}/signals` |
| 前端功能 | 将信号加入当前草稿包 |
| 正常场景 | 信号加入并刷新草稿区 |
| 异常场景 | 重复加入；状态不可加入；跨 topic |
| 性能 | p95 < 500ms |
| 测试 agent | 刷新后草稿区仍包含该信号 |

### F041 信号移出草稿区

| 项 | 内容 |
| --- | --- |
| 后端 API | `DELETE /api/v1/signal-packages/{package_id}/signals/{signal_id}` |
| 前端功能 | 从草稿区移除信号 |
| 正常场景 | 移除后不参与主线建议 |
| 异常场景 | signal 不在草稿区；草稿包已锁定 |
| 性能 | p95 < 500ms |
| 测试 agent | DB 关联删除，审计可查 |

### F042 创建信号包

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/signal-packages` |
| 前端功能 | 从搜索页创建当前分析包 |
| 正常场景 | 创建包并选择 signals |
| 异常场景 | topic 不存在；名称重复；无 signal |
| 性能 | p95 < 800ms |
| 测试 agent | 创建后可进入证据复核 |

### F043 证据复核对象

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/evidence-reviews/{review_id}` |
| 前端功能 | 复核对象状态、所属主题、来源页面、进度 |
| 正常场景 | 返回 review、evidence list、progress |
| 异常场景 | review 不存在；已关闭；无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 复核页入口参数正确 |

### F044 证据详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/evidence/{evidence_id}` |
| 前端功能 | 原文、视频片段、评论样本、来源链路、可信度 |
| 正常场景 | 展示 masked 原文和 metadata |
| 异常场景 | 原文权限不足；证据被删除；证据与 review 不匹配 |
| 性能 | p95 < 1000ms |
| 测试 agent | 敏感字段不泄露 |

### F045 证据状态更新

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/evidence/{evidence_id}/status` |
| 前端功能 | 标记可用、待复核、不可用、仅概率参考 |
| 正常场景 | 状态更新，进度刷新，写审计 |
| 异常场景 | 非 reviewer；非法状态流转；已锁定报告关联证据 |
| 性能 | p95 < 500ms |
| 测试 agent | 四种状态逐一测试 |

### F046 证据补充上传

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/evidence-reviews/{review_id}/supplements` |
| 前端功能 | 上传补充材料、链接、说明 |
| 正常场景 | 生成新 raw_record/evidence |
| 异常场景 | 文件过大；类型非法；病毒扫描失败；重复材料 |
| 性能 | 50MB 文件异步上传，初始响应 < 2s |
| 测试 agent | 上传成功后证据列表出现 |

### F047 风险因子生成

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/topics/{topic_id}/risk-factors/generate` |
| 前端功能 | 点击生成或刷新风险因子 |
| 正常场景 | 根据 evidence/signals 生成 factors |
| 异常场景 | 无有效证据；算法版本缺失；重复生成 |
| 性能 | 单 topic < 10s |
| 测试 agent | 校园/民生/市场三类生成不同因子 |

### F048 风险因子列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/topics/{topic_id}/risk-factors` |
| 前端功能 | 展示因子、触发原因、证据引用、置信度、状态 |
| 正常场景 | 按状态/类别/置信度筛选 |
| 异常场景 | topic 不存在；空列表 |
| 性能 | p95 < 1000ms |
| 测试 agent | 因子 evidence_refs 可点击 |

### F049 风险因子确认/驳回

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/risk-factors/{factor_id}/status` |
| 前端功能 | 确认、驳回、待复核 |
| 正常场景 | 状态更新并影响主线候选 |
| 异常场景 | 无证据因子不可确认；非 reviewer；非法状态 |
| 性能 | p95 < 500ms |
| 测试 agent | 驳回因子不进入主线 |

### F050 风险因子置信度调整

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/risk-factors/{factor_id}/confidence` |
| 前端功能 | 用户调整置信度并填写原因 |
| 正常场景 | confidence 更新，写 audit |
| 异常场景 | 超出 0-1；无原因；无权限 |
| 性能 | p95 < 500ms |
| 测试 agent | 审计中有 from/to/reason |

## 7. 阶段 5：主线建模与 World State

### F051 生成主线草稿

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/generate` |
| 前端功能 | 从 signal_package/topic 生成候选主线 |
| 正常场景 | 返回 mainline draft、support points、evidence gaps |
| 异常场景 | 无信号；无 confirmed evidence；因子不足；算法失败 |
| 性能 | < 10s |
| 测试 agent | 生成结果落库，不是前端计算 |

### F052 主线详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/mainlines/{mainline_id}` |
| 前端功能 | 输入信号包、候选主线池、结构图谱、判定报告 |
| 正常场景 | 返回完整 mainline graph |
| 异常场景 | mainline 不存在；无权限 |
| 性能 | p95 < 1500ms |
| 测试 agent | 图谱节点数据与 API 一致 |

### F053 主线节点操作

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/{mainline_id}/nodes`, `PATCH /api/v1/mainline-nodes/{node_id}`, `DELETE /api/v1/mainline-nodes/{node_id}` |
| 前端功能 | 添加、删除、合并、拆分、标记证据缺口、标记不确定性 |
| 正常场景 | 节点变更保存为新版本 |
| 异常场景 | 已确认主线不可直接改；节点有 report 引用；缺原因 |
| 性能 | 单操作 p95 < 800ms |
| 测试 agent | 浏览器拖拽/编辑后刷新保留 |

### F054 主线信号操作

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/{mainline_id}/signals`, `DELETE /api/v1/mainlines/{mainline_id}/signals/{signal_id}` |
| 前端功能 | 添加/移除主线输入信号 |
| 正常场景 | 支点和缺口重新计算 |
| 异常场景 | signal 已 rejected；跨 topic；主线锁定 |
| 性能 | p95 < 1000ms |
| 测试 agent | 移除关键 signal 后质量提示变化 |

### F055 主线质量检查

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/{mainline_id}/validate` |
| 前端功能 | 缺口检查、补数据建议、合并/拆分建议、噪声排除建议 |
| 正常场景 | 返回可确认/不可确认和原因 |
| 异常场景 | 无 evidence_refs；规则版本缺失 |
| 性能 | < 5s |
| 测试 agent | 不满足条件时确认按钮不可用 |

### F056 确认主线

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/{mainline_id}/confirm` |
| 前端功能 | 用户确认主线，进入 World State |
| 正常场景 | mainline=confirmed，写 audit |
| 异常场景 | 质量检查失败；非 reviewer；重复确认 |
| 性能 | p95 < 1000ms |
| 测试 agent | 确认后可生成 World State |

### F057 生成 World State

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/mainlines/{mainline_id}/world-state` |
| 前端功能 | 生成推演输入包 |
| 正常场景 | 生成核心诉求、情绪、扩散源、主叙事、不确定变量 |
| 异常场景 | 主线未确认；输入缺口不可带入；重复生成版本 |
| 性能 | < 5s |
| 测试 agent | World State 详情可追溯到 mainline |

## 8. 阶段 6：世界线推演

### F058 世界线运行创建

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/worldline-runs` |
| 前端功能 | 从 World State 启动 24-72 小时推演 |
| 正常场景 | 创建 worldline_run，workflow running |
| 异常场景 | world_state 不存在；未确认；已有运行中 run |
| 性能 | 创建 run p95 < 500ms |
| 测试 agent | 浏览器点击“运行推演”看到状态变化 |

### F059 世界线结果查询

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/worldline-runs/{run_id}` |
| 前端功能 | 展示输入摘要、分支概率、画布节点、节点详情 |
| 正常场景 | 返回 nodes、edges、branch probabilities |
| 异常场景 | run failed；run running；run 不存在 |
| 性能 | p95 < 1500ms |
| 测试 agent | running 状态不显示假结果 |

### F060 处置动作注入

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/worldline-runs/{run_id}/actions` |
| 前端功能 | 选择预设动作或自定义动作，设置时间、主体、渠道、反馈机制 |
| 正常场景 | action 注入后触发 rerun 或版本更新 |
| 异常场景 | 动作字段缺失；run 已锁定；执行主体无效 |
| 性能 | p95 < 1000ms |
| 测试 agent | 注入动作后概率变化有版本记录 |

### F061 世界线重跑

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/worldline-runs/{run_id}/rerun` |
| 前端功能 | 基于新动作/参数重跑 |
| 正常场景 | 生成新 run_version |
| 异常场景 | 上一 run 未完成；参数未变；算法失败 |
| 性能 | 单 run < 180s |
| 测试 agent | 历史版本仍可查看 |

### F062 世界线版本对比

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/worldline-runs/{run_id}/versions/compare` |
| 前端功能 | 对比不同版本概率、节点、支点变化 |
| 正常场景 | 返回 diff |
| 异常场景 | 版本不存在；跨 run 对比 |
| 性能 | p95 < 1500ms |
| 测试 agent | 浏览器选择两个版本，diff 正确展示 |

### F063 世界线节点详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/worldline-nodes/{node_id}` |
| 前端功能 | 当前阶段、情绪、诉求、传播源、破圈苗头、证据、下一跳 |
| 正常场景 | 节点详情完整 |
| 异常场景 | 节点不存在；证据缺失；无权限 |
| 性能 | p95 < 800ms |
| 测试 agent | evidence_refs 可点击回证据页 |

### F064 标记 Council 节点

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/worldline-nodes/{node_id}/council-flag` |
| 前端功能 | 系统/人工标记是否需要多主体研判 |
| 正常场景 | needs_council 更新 |
| 异常场景 | run 未完成；节点已进入 report；无权限 |
| 性能 | p95 < 500ms |
| 测试 agent | 标记后 Council 页入口出现 |

## 9. 阶段 7：Agent Council 与 LLM

### F065 LLM Provider 状态

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/llm/providers/status` |
| 前端功能 | 配置中心展示 provider 可用性 |
| 正常场景 | 返回 provider、model、status、latency |
| 异常场景 | API key 缺失；provider 不可达；模型无权限 |
| 性能 | health check < 5s |
| 测试 agent | 配置错误时 Council 按钮提示不可运行 |

### F066 Agent Profile 列表

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/agent-profiles` |
| 前端功能 | 查看不同事件类型的 Agent 编队 |
| 正常场景 | 校园、民生、市场事件加载不同角色 |
| 异常场景 | profile 缺失；版本未发布 |
| 性能 | p95 < 800ms |
| 测试 agent | profile 与事件类型匹配 |

### F067 创建 Council Session

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/council-sessions` |
| 前端功能 | 从 worldline node 创建多主体研判 |
| 正常场景 | 保存 session、输入上下文、agent profiles |
| 异常场景 | node 不存在；无 evidence；provider 不可用 |
| 性能 | p95 < 1000ms |
| 测试 agent | session 创建后可打开 Council 页 |

### F068 运行 Council

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/council-sessions/{session_id}/run` |
| 前端功能 | 点击运行，多 Agent 调真实 LLM |
| 正常场景 | 各 Agent 输出 stance/reaction/delta/uncertainty |
| 异常场景 | LLM timeout；限流；非法 JSON；schema 失败；部分 Agent 失败 |
| 性能 | session < 180s，单 Agent latency 记录 |
| 测试 agent | 生产配置不允许 fake provider |

### F069 Council 状态轮询

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/council-sessions/{session_id}/status` |
| 前端功能 | 展示 pending/running/partial/failed/completed |
| 正常场景 | 运行中展示进度，完成后刷新结果 |
| 异常场景 | workflow failed；provider failed |
| 性能 | p95 < 300ms |
| 测试 agent | 浏览器运行时不出现假结果 |

### F070 Council 结果详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/council-sessions/{session_id}/result` |
| 前端功能 | 展示主体立场、接受度、质疑点、传播意愿、支点变化、概率影响 |
| 正常场景 | 所有输出 schema-valid，有 evidence_refs |
| 异常场景 | blocked_claims 非空；部分 Agent 失败 |
| 性能 | p95 < 1000ms |
| 测试 agent | 无证据事实必须进入 blocked_claims |

### F071 Council 假设压力测试

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/council-sessions/{session_id}/pressure-tests` |
| 前端功能 | 输入自然语言或结构化处置动作测试各方反应 |
| 正常场景 | 生成 pressure_test_result 并持久化 |
| 异常场景 | 假设为空；违反政策；LLM 失败 |
| 性能 | < 180s |
| 测试 agent | 压测结果不会覆盖原 Council 结果 |

### F072 Council 结果应用

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/council-sessions/{session_id}/apply` |
| 前端功能 | 保存 Council Result、回写世界线、进入汇报 |
| 正常场景 | worldline 新版本或节点解释更新，写 audit |
| 异常场景 | session 未完成；schema invalid；已应用 |
| 性能 | p95 < 1000ms |
| 测试 agent | 应用后世界线页面显示变化 |

## 10. 阶段 8：报告、任务、审批、导出、复盘

### F073 生成报告草稿

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/generate` |
| 前端功能 | 从 worldline/council 生成阶段性研判报告 |
| 正常场景 | 生成 draft report，包含证据摘要、分支概率、建议动作、不确定性 |
| 异常场景 | worldline 未完成；Council 未完成；证据不足 |
| 性能 | < 90s |
| 测试 agent | 每段结论必须有 evidence_refs 或 uncertainty |

### F074 报告详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/reports/{report_id}` |
| 前端功能 | 展示报告内容、审阅状态、任务、证据引用 |
| 正常场景 | 返回 draft/formal/compliance/tasks |
| 异常场景 | report 不存在；无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 未确认 formal_conclusion 为空 |

### F075 提交审阅

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/{report_id}/submit-review` |
| 前端功能 | analyst 提交 reviewer 审阅 |
| 正常场景 | 状态 draft -> under_review |
| 异常场景 | 缺证据引用；无任务；重复提交 |
| 性能 | p95 < 800ms |
| 测试 agent | 审阅人可在待办中看到 |

### F076 审阅退回

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/{report_id}/reject` |
| 前端功能 | reviewer 填原因退回 |
| 正常场景 | 状态 under_review -> revision_required |
| 异常场景 | 非 reviewer；原因为空；状态不允许 |
| 性能 | p95 < 800ms |
| 测试 agent | 退回原因显示在报告页 |

### F077 确认发布报告

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/{report_id}/confirm` |
| 前端功能 | reviewer 确认高风险 formal conclusion |
| 正常场景 | formal_conclusion 生效，写 audit |
| 异常场景 | 未审阅；证据不足；高风险未二次确认；无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 未确认前 formal 为空，确认后出现 |

### F078 报告导出

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/{report_id}/exports`, `GET /api/v1/report-exports/{export_id}/download` |
| 前端功能 | Markdown/PDF/DOCX/JSON 导出 |
| 正常场景 | 生成 export job，完成后下载 |
| 异常场景 | 无导出权限；报告未确认；导出服务失败 |
| 性能 | PDF/DOCX < 30s |
| 测试 agent | 下载文件内容与报告一致 |

### F079 任务生成

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/reports/{report_id}/tasks/generate` |
| 前端功能 | 根据报告生成处置任务 |
| 正常场景 | 生成事实核验、证据保全、沟通机制、隐私保护、后续监测任务 |
| 异常场景 | report 未生成；重复生成；无任务来源 |
| 性能 | p95 < 1500ms |
| 测试 agent | 每个任务有 source_object |

### F080 手动创建任务

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/tasks` |
| 前端功能 | 用户手动创建任务，关联 evidence/factor/node/report |
| 正常场景 | 任务入库并显示 |
| 异常场景 | source_object 不存在；owner 无权限；due 时间非法 |
| 性能 | p95 < 800ms |
| 测试 agent | 创建后任务列表和审计可查 |

### F081 任务状态更新

| 项 | 内容 |
| --- | --- |
| 后端 API | `PATCH /api/v1/tasks/{task_id}/status` |
| 前端功能 | suggested/in_progress/completed/closed 状态流转 |
| 正常场景 | 状态更新，写 audit |
| 异常场景 | 非 owner；非法状态流转；已关闭任务再修改 |
| 性能 | p95 < 500ms |
| 测试 agent | 浏览器更新状态后报告任务区刷新 |

### F082 创建复盘

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/case-memories` |
| 前端功能 | 关闭 case 后创建复盘 |
| 正常场景 | 保存最终路径、预测命中、偏差类型、处置结果 |
| 异常场景 | case 未关闭；缺实际结果；重复复盘 |
| 性能 | p95 < 1000ms |
| 测试 agent | 复盘页从报告页回流 |

### F083 复盘知识入库

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/case-memories/{memory_id}/knowledge-items` |
| 前端功能 | 沉淀前因信号模板、扩散路径、误判样本、动作效果 |
| 正常场景 | 创建 knowledge item，状态 draft |
| 异常场景 | 缺引用；重复知识项；未审批 |
| 性能 | p95 < 1000ms |
| 测试 agent | 未审批不进入正式案例库 |

## 11. 阶段 9：案例库、配置中心、回归

### F084 案例库搜索

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/case-library/search` |
| 前端功能 | 按主题、信号、扩散路径、处置动作、误判样本召回 |
| 正常场景 | 返回相似案例、相似度、适用阶段 |
| 异常场景 | 跨组织不可见；无结果；搜索服务失败 |
| 性能 | p95 < 3000ms |
| 测试 agent | 召回结果可追溯到知识项 |

### F085 案例详情

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/case-library/{case_memory_id}` |
| 前端功能 | 查看案例摘要、最终路径、预测命中、动作效果、误判样本 |
| 正常场景 | 详情完整展示 |
| 异常场景 | 无权限；案例未发布 |
| 性能 | p95 < 1000ms |
| 测试 agent | 跨组织用户返回 403 |

### F086 应用案例建议

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/case-library/{case_memory_id}/apply` |
| 前端功能 | 将历史案例建议回写当前 topic/mainline/worldline/council |
| 正常场景 | 创建 application record，不直接覆盖业务结果 |
| 异常场景 | 当前 case 状态不允许；案例不适用；重复应用 |
| 性能 | p95 < 1000ms |
| 测试 agent | 应用记录可撤销和审计 |

### F087 数据源配置版本

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/config/data-sources`, `POST /api/v1/config/data-sources/versions` |
| 前端功能 | 新增、启停、权重、可信度、字段映射配置版本 |
| 正常场景 | 修改生成 draft version |
| 异常场景 | 非 admin；非法字段映射；未跑回归 |
| 性能 | p95 < 1000ms |
| 测试 agent | 发布后新采集使用新版本 |

### F088 标签体系配置

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/config/taxonomies`, `POST /api/v1/config/taxonomies/versions` |
| 前端功能 | 主题、信号、情绪、诉求、传播、证据、圈层标签配置 |
| 正常场景 | 标签增删改生成版本 |
| 异常场景 | 删除被引用标签；重复标签；未审批 |
| 性能 | p95 < 1000ms |
| 测试 agent | 标签变更后旧数据保持历史版本 |

### F089 模型参数配置

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/config/model-parameters`, `POST /api/v1/config/model-parameters/versions` |
| 前端功能 | 破圈概率阈值、同城占比阈值、情绪升温窗口、召回数量、噪声降权 |
| 正常场景 | 修改参数生成 draft |
| 异常场景 | 参数越界；影响范围未确认；无权限 |
| 性能 | p95 < 1000ms |
| 测试 agent | 参数变更影响回归结果 |

### F090 Agent 配置

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/config/agents`, `POST /api/v1/config/agents/versions` |
| 前端功能 | Agent 角色、立场约束、输出结构、禁止项、版本管理 |
| 正常场景 | 创建 Agent profile draft |
| 异常场景 | 输出 schema 不合法；缺 guardrail；无审批 |
| 性能 | p95 < 1000ms |
| 测试 agent | 未发布 profile 不能用于生产 Council |

### F091 Prompt 模板配置

| 项 | 内容 |
| --- | --- |
| 后端 API | `GET /api/v1/config/prompts`, `POST /api/v1/config/prompts/versions` |
| 前端功能 | Prompt 模板创建、编辑、版本化 |
| 正常场景 | 新版本进入 draft |
| 异常场景 | prompt 含禁止指令；缺 evidence boundary；未审批 |
| 性能 | p95 < 1000ms |
| 测试 agent | prompt 版本写入 LLM 调用记录 |

### F092 配置回归测试

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/config/versions/{version_id}/regression-runs`, `GET /api/v1/regression-runs/{run_id}` |
| 前端功能 | 发布前跑历史案例回归 |
| 正常场景 | 返回通过率、失败案例、指标变化 |
| 异常场景 | 回归失败不可发布；版本不存在；case 数据缺失 |
| 性能 | 10 个案例 < 10min |
| 测试 agent | 回归失败时发布按钮禁用 |

### F093 配置审批发布

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/config/versions/{version_id}/submit`, `POST /api/v1/config/versions/{version_id}/approve`, `POST /api/v1/config/versions/{version_id}/publish` |
| 前端功能 | 草稿、提交审批、批准、发布 |
| 正常场景 | draft -> under_review -> approved -> published |
| 异常场景 | 未回归；审批人不能是提交人；状态不允许 |
| 性能 | p95 < 1000ms |
| 测试 agent | 发布后新 workflow 记录 config_version |

### F094 配置回滚

| 项 | 内容 |
| --- | --- |
| 后端 API | `POST /api/v1/config/versions/{version_id}/rollback` |
| 前端功能 | 回滚到上一发布版本 |
| 正常场景 | 新建 rollback version 并发布 |
| 异常场景 | 无上一版本；当前有运行中 workflow；无权限 |
| 性能 | p95 < 1500ms |
| 测试 agent | 回滚后新任务使用旧配置 |

## 12. 全链路、异常、性能、浏览器验收

### F095 校园案例全链路

| 项 | 内容 |
| --- | --- |
| API 链路 | data source -> collection run -> raw -> signal -> evidence -> factor -> mainline -> world state -> worldline -> council -> report -> task -> memory |
| 前端场景 | 城市态势发现校园事件，完成报告和任务 |
| 正常结果 | 全链路对象入库，审计完整 |
| 异常结果 | 任一环节失败可见，不生成假结果 |
| 性能 | 全链路可在验收阈值内完成 |
| 浏览器验收 | 录制完整路径截图和 API trace |

### F096 民生服务案例全链路

| 项 | 内容 |
| --- | --- |
| API 链路 | 同 F095 |
| 前端场景 | 社区停水/公共服务事件从发现到报告 |
| 正常结果 | 不出现校园专用文案或角色 |
| 异常结果 | 证据不足时主线/报告阻断 |
| 性能 | 同 F095 |
| 浏览器验收 | 检查非校园因子、Agent、报告 |

### F097 市场/食品安全案例全链路

| 项 | 内容 |
| --- | --- |
| API 链路 | 同 F095 |
| 前端场景 | 市场/食品安全消费保护事件从发现到复盘 |
| 正常结果 | 生成市场监管、消费者、商户、媒体等 Agent 角色 |
| 异常结果 | 无官方来源时正式结论必须保持不确定 |
| 性能 | 同 F095 |
| 浏览器验收 | 检查第三场景泛化能力 |

### F098 权限异常全链路

| 项 | 内容 |
| --- | --- |
| 覆盖 API | 所有 GET/mutation/export/admin/config API |
| 前端场景 | 不同角色访问页面、按钮、对象 |
| 正常结果 | 有权限操作成功 |
| 异常结果 | 无 token=401；越权=403；跨组织=403；按钮隐藏 |
| 性能 | 权限校验 p95 < 100ms 额外开销 |
| 浏览器验收 | 分角色录制菜单和按钮状态 |

### F099 LLM 异常全链路

| 项 | 内容 |
| --- | --- |
| 覆盖 API | `POST /council-sessions/{id}/run`, pressure tests, report generate |
| 前端场景 | LLM 超时、限流、非法 JSON、schema invalid、部分 Agent 失败 |
| 正常结果 | 成功时结果入库 |
| 异常结果 | 失败状态可见，不写假结论，可重试 |
| 性能 | timeout 和 retry 策略可配置 |
| 浏览器验收 | Council 页展示 partial/failed 状态 |

### F100 Workflow 异常全链路

| 项 | 内容 |
| --- | --- |
| 覆盖 API | collection run、worldline run、council run、report generate |
| 前端场景 | activity 失败、重试、幂等、取消 |
| 正常结果 | workflow 成功改变数据库状态 |
| 异常结果 | failed 可查看错误，可重试，不重复写 |
| 性能 | 50 并发 workflow 稳定 |
| 浏览器验收 | 页面轮询 workflow 状态 |

### F101 系统性能基线

| 项 | 内容 |
| --- | --- |
| API | 所有列表/详情/mutation/run/status API |
| 前端场景 | 11 个页面首屏、筛选、详情、mutation |
| 正常结果 | 达到性能阈值 |
| 异常结果 | 慢查询报警，页面展示降级 |
| 性能 | 页面首屏 < 3s；普通 API p95 < 1500ms；长任务按业务阈值 |
| 浏览器验收 | Playwright 性能 trace 和截图 |

### F102 发布验收包

| 项 | 内容 |
| --- | --- |
| API | `GET /api/v1/system/readiness`, `GET /api/v1/system/version` |
| 前端场景 | 交付验收页展示版本、服务、测试、风险 |
| 正常结果 | 所有必测项通过，生成交付报告 |
| 异常结果 | 存在阻断项时不可标记 ready |
| 性能 | readiness p95 < 1000ms |
| 浏览器验收 | 内部浏览器打开验收页并截图 |

## 13. Agent 派工规则

第一批启动：

- Backend-Agent-Auth：F001-F009。
- Backend-Agent-Data：F010-F024。
- QA-Agent-Core：F001-F024 正常/异常/API 测试。

第二批启动：

- Backend-Agent-CityTopic：F025-F036。
- Frontend-Agent-CityTopic：F025-F036 页面和交互。
- Browser-QA-Agent：F025-F036 内部浏览器验收。

第三批启动：

- Backend-Agent-SignalEvidenceFactor：F037-F050。
- Algorithm-Agent：F047-F050 与后续主线/世界线算法。
- Frontend-Agent-DataEvidence：F037-F050。
- QA-Agent-Data：F037-F050 功能、异常、性能。

第四批启动：

- Backend-Agent-MainlineWorldline：F051-F064。
- Frontend-Agent-Worldline：F051-F064。
- Performance-QA-Agent：F058-F064 推演性能。

第五批启动：

- LLM-Agent：F065-F072。
- Backend-Agent-Council：F065-F072。
- Security-QA-Agent：LLM evidence boundary、guardrails、blocked_claims。

第六批启动：

- Backend-Agent-ReportTaskMemory：F073-F083。
- Frontend-Agent-ReportMemory：F073-F083。
- Browser-QA-Agent：报告、任务、导出、复盘验收。

第七批启动：

- Backend-Agent-LibraryConfig：F084-F094。
- Frontend-Agent-Config：F084-F094。
- QA-Agent-Regression：配置回归、发布、回滚。

第八批启动：

- E2E-QA-Agent：F095-F102。
- Performance-QA-Agent：全系统性能。
- Release-Agent：验收报告和发布包。

## 14. 每个功能点的完成定义

每个 F 编号必须同时满足：

- API 已实现并有接口测试。
- 前端已接真实 API，无 mock。
- 正常测试通过。
- 异常测试通过。
- 数据库状态、审计、workflow 状态可验证。
- 性能测试达到该功能阈值。
- 内部浏览器完成真实点击验收。
- 验收截图、API trace、测试日志已归档。
