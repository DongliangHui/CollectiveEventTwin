# CollectiveEventTwin 调整后生产级开发计划（评审版）

日期：2026-05-09

状态：评审稿

适用范围：完整生产项目，不按 MVP 裁剪。

本文件用于评审。它基于现有计划重新排期，并吸收开源/本地参考项目研究结论。旧计划仍作为依据保留，本文件作为当前评审入口。

相关依据：

- `docs/p0-production-grade-delivery-plan-20260508.md`
- `docs/full-project-api-frontend-test-development-plan-20260508.md`
- `docs/full-project-atomic-task-development-plan-20260508.md`
- `docs/design-engineering-unification-workflow-20260509.md`
- `docs/open-source-radar-source-study-20260509.md`
- `docs/source-studies/05-local-reference-projects.md`
- `docs/tr0-business-decisions-xian-social-issues-20260508.md`

## 1. 评审结论

当前计划需要调整，但不推翻技术路线。

不变：

- 生产级系统，不做前端 mock 演示。
- 所有产品数据来自 PostgreSQL，经 FastAPI 返回。
- 每一个有业务含义的前端交互都必须落到后端 API。
- 算法、工作流、Agent、LLM 是真实业务代码。
- 第一阶段城市为西安。
- 第一阶段社会议题为社区拆迁、养老保险上访等民生社会问题。
- 用户没有外部数据和 key 时，可以先使用“合成数据源”，但必须走真实采集、清洗、抽取、入库、算法、Agent、报告链路。

需要调整：

- 数据源治理提前，先做 source health、run contract、失败归因、数据血缘。
- 数据采集按渠道拆分，不能再写成一个“采集模块”。
- 多媒体能力前置，图片、视频、直播都要有算法/Agent 闭环。
- City 页作为第一张冻结页，必须先建立页面级后端 view-model API 和页面状态基线。
- 世界线先识别利益方，再生成 Agent Profile，再进入多 Agent Council。
- 多 Agent Profile 采用 `user.md`、`soul.md`、`agent.md` 结构表达背景、立场、处事逻辑、思维方式和当前事件权衡。
- 每一项输出必须有第三方检查记录。
- 每个功能点完成后必须由测试 agent 做功能测试、异常测试、性能测试，并用内部浏览器验证。

## 2. 参考项目带来的计划调整

| 调整项 | 参考来源 | 采纳方式 | 不采纳边界 |
| --- | --- | --- | --- |
| 数据源健康、种子任务、采集契约提前 | `worldmonitor-main` | 建立 `source_health`、`collection_runs`、freshness、empty-data policy、failure signature | 不使用 Redis-only 状态作为生产事实 |
| 页面 bootstrap/view-model API | `worldmonitor-main` | 为 City 等页面提供后端聚合视图模型 | 不让前端自行计算业务事实 |
| 地图图层契约测试 | `worldmonitor-main` | 城市地图图层、聚合、热力、筛选都写可执行测试 | 不把地图 SDK 状态当作业务状态 |
| graph -> profile -> run -> report 顺序 | `MiroFish` | 世界线构建后识别利益方，再生成 Agent Profile，再运行 Council 和报告 | 不采用 Flask/file-only state |
| Agent Profile 生成 | `MiroFish`、`agency-agents-zh` | 生成 `user.md`、`soul.md`、`agent.md`，并持久化、审计、复核 | 不用随机人设支撑正式结论 |
| 报告 Agent 进度和工具调用 | `MiroFish` | 报告生成过程可查询，工具调用和证据引用可追踪 | 不允许无证据结论进入报告 |
| 页面状态库存与视觉审计 | `MiroFish` | 每个冻结页建立 routeable state、截图基线、浏览器测试 | 不把静态 HTML 当生产页面 |
| LLM Gateway 校验 | `worldmonitor-main`、Guardrails/Instructor 类项目 | LLM 输出必须 schema-valid、evidence-linked、可审计 | 不做静默 fallback 结论 |
| Worker/ML 分离 | `worldmonitor-main` | 多媒体、抽取、聚类、LLM 长任务走 worker/workflow | 不把重算法放进前端 |
| 数据采集合规边界 | open-source radar | 公共/授权/导入优先，私域、绕验证、cookie 池进入禁用边界 | 不做登录绕过、验证码绕过、冒充真人 |

## 3. 交付硬约束

产品运行时禁止：

- 前端 mock 数据。
- 静态 fixture 作为产品数据源。
- 预置下游对象假装算法结果。
- 前端-only 的业务状态。
- 没有数据库记录的 Agent/LLM 结论。
- 没有证据引用的报告事实判断。

允许但必须标记：

- 合成数据源，用于西安第一阶段社会议题样本。
- 测试 fixture，仅限自动化测试。
- Fake LLM provider，仅限测试环境。

所有输出必须具备：

- 来源记录。
- 算法版本或 prompt 版本。
- 输入对象引用。
- 置信度或状态。
- 审计日志。
- 第三方检查记录。

## 4. 调整后阶段排期

| 阶段 | 周期 | 业务目标 | 主要 Agent | 冻结条件 |
| --- | --- | --- | --- | --- |
| S0 | 第 1 周 | 评审计划、TR1 补丁、API/数据合同冻结 | 架构、产品、QA、数据/LLM | 本文档评审通过，关键 API/Schema 可派工 |
| S1 | 第 2-3 周 | 用户、权限、审计、工作流/算法/LLM 基础记录 | 后端 A、前端 A、QA A | 登录到 City 页链路、审计、权限通过浏览器测试 |
| S2 | 第 4-7 周 | 数据源治理、分渠道采集、清洗、合成西安样本 | 后端 A、数据 Agent、QA A/B | 合成/手工/公开网页/多媒体源可入库并生成 raw records |
| S3 | 第 8-10 周 | 西安 City 第一张冻结页 | 后端 B、前端 A、浏览器 QA | City 所有业务交互后端化，截图基线通过 |
| S4 | 第 11-14 周 | 信号、证据、风险因子、媒体证据算法 | 后端 B、算法 Agent、数据 Agent、QA B | 社会议题样本可从原始记录生成信号、证据、风险 |
| S5 | 第 15-18 周 | 主线、World State、世界线、利益方识别 | 后端 C、算法 Agent、前端 B、QA B | 世界线能生成利益方和可解释分支 |
| S6 | 第 19-22 周 | 专业 Agent 复用、Agent Profile、Council、LLM Guardrails | LLM Agent、后端 C、QA C | Council 输出 schema-valid、证据绑定、第三方检查通过 |
| S7 | 第 23-25 周 | 报告、任务、审批、导出、案例库、配置中心 | 后端 D、前端 B/C、QA A/C | 报告可冻结、可导出、可追踪、可复盘 |
| S8 | 第 26-28 周 | 全链路、性能、安全、观测、DCP | 全部 Agent | 发布验收包通过，进入客户评审 |

## 5. 功能点拆分原则

每个功能点必须满足：

- 有明确用户动作或系统动作。
- 有明确后端 API 或 workflow/activity。
- 有明确数据库读写对象。
- 有明确前端状态。
- 有正常测试和异常测试。
- 有性能指标。
- 有浏览器验证方式。
- 有第三方检查结论。

如果一个任务还能继续拆成“新建、编辑、删除、状态变更、详情、列表、重试、导出”等动作，则不能作为一个功能点派工。

## 6. 功能点级开发计划

### S1：登录、权限、导航、审计

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F001 | 登录成功 | `POST /api/v1/auth/login` | 输入账号密码，提交后进入 City 页 | 返回 token、用户、权限、审计日志 | 无 | p95 < 500ms；浏览器提交表单后跳转 |
| F002 | 登录失败：账号不存在 | `POST /api/v1/auth/login` | 登录页展示账号或密码错误 | 不创建会话，写失败审计 | unknown username | p95 < 500ms；错误提示不泄露账号存在性 |
| F003 | 登录失败：密码错误 | `POST /api/v1/auth/login` | 登录页展示错误，失败次数增加 | 不创建会话，记录失败次数 | 连续失败触发锁定 | 浏览器连续输错后按钮/提示正确 |
| F004 | 登录失败：账号禁用/锁定 | `POST /api/v1/auth/login` | 展示账号不可用状态 | 不发 token | disabled、locked | 浏览器不可进入受保护页面 |
| F005 | 登录失败：租户无效 | `POST /api/v1/auth/login` | 租户选择或租户码错误提示 | 不创建会话 | tenant missing、tenant disabled | 错误码可区分，文案不暴露敏感信息 |
| F006 | 刷新登录态 | `POST /api/v1/auth/refresh` | 页面刷新保持登录 | access token 更新 | refresh token 过期、被吊销 | p95 < 300ms；浏览器刷新后权限不丢失 |
| F007 | 退出登录 | `POST /api/v1/auth/logout` | 点击退出回登录页 | token 吊销，审计可查 | 重复退出、无 token | 浏览器退出后不能返回受保护页 |
| F008 | 当前用户信息 | `GET /api/v1/auth/me` | 顶部用户、角色、租户展示 | 返回用户、角色、租户 | 未登录、用户禁用 | p95 < 300ms |
| F009 | 权限列表 | `GET /api/v1/auth/permissions` | 菜单和按钮按权限展示 | 返回页面/按钮/数据权限 | 权限版本过期、无权限 | 不同角色浏览器菜单不同 |
| F010 | 用户管理列表 | `GET /api/v1/users` | 用户列表、筛选、分页 | admin 可查 | 非 admin、分页非法 | 1 万用户 p95 < 1000ms |
| F011 | 新建用户 | `POST /api/v1/users` | 用户表单提交 | 创建成功，审计可查 | 重复用户名、无效角色、弱密码 | 浏览器新建后列表可见 |
| F012 | 编辑/禁用用户 | `PATCH /api/v1/users/{id}`、`PATCH /api/v1/users/{id}/status` | 修改用户信息、启停账号 | 状态生效 | 禁用自己、跨租户、对象不存在 | 浏览器禁用后该用户不能登录 |
| F013 | 角色权限配置 | `GET /api/v1/roles`、`POST /api/v1/roles`、`PUT /api/v1/roles/{id}/permissions` | 角色列表、权限勾选 | 权限发布成功 | 修改内置角色、非法权限 | 切换角色后菜单实时变化 |
| F014 | 导航上下文 | `GET /api/v1/navigation/context`、`PATCH /api/v1/navigation/context` | city/case/topic 切换后保持 | 刷新后上下文恢复 | 对象不存在、无权限对象 | 浏览器跨页跳转上下文一致 |
| F015 | 审计查询 | `GET /api/v1/audit-logs` | 按用户、动作、对象、时间查询 | 所有 mutation 可追踪 | 非审计角色、非法时间范围 | 10 万审计 p95 < 1500ms |

### S2：数据源治理、分渠道采集、清洗

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F020 | 数据源类型字典 | `GET /api/v1/source-types` | 新建数据源时选择渠道 | 返回 synthetic、manual_upload、authorized_export、public_web、official_api、image、video、live | 禁用类型不可选 | p95 < 300ms |
| F021 | 数据源列表 | `GET /api/v1/data-sources` | 数据源列表筛选、分页 | 按类型、状态、健康筛选 | 非法筛选、越权租户 | 1000 source p95 < 1000ms |
| F022 | 新建合成数据源 | `POST /api/v1/data-sources` | 创建西安社会议题合成源 | 创建成功，标记 synthetic | 未标记 synthetic、重复 code | 浏览器创建后可见 |
| F023 | 新建手工上传源 | `POST /api/v1/data-sources` | 配置文件上传字段映射 | 创建成功 | 缺字段映射、格式不支持 | 浏览器表单校验 |
| F024 | 新建公开网页源 | `POST /api/v1/data-sources` | 配置 URL、抓取频率、地域关键词 | 创建成功 | 私域/登录绕过/captcha_bypass 被拒 | 策略拦截可见 |
| F025 | 新建官方 API 源 | `POST /api/v1/data-sources` | 配置 endpoint、credential ref | 创建成功 | token 直存明文、schema 缺失 | p95 < 800ms |
| F026 | 新建图片/视频/直播源 | `POST /api/v1/data-sources` | 配置媒体来源、存储策略 | 创建成功 | 超出大小/格式/保留策略非法 | 浏览器展示媒体源类型 |
| F027 | 编辑数据源 | `PATCH /api/v1/data-sources/{id}` | 修改名称、权重、字段映射、保留策略 | 新 run 使用新配置 | 正在运行时修改冲突、字段非法 | 写配置版本和审计 |
| F028 | 启停/归档数据源 | `PATCH /api/v1/data-sources/{id}/status` | 启用、停用、归档 | 停用后不可运行 | 正在运行禁用、重复禁用 | 浏览器运行按钮随状态变化 |
| F029 | 数据源策略校验 | `POST /api/v1/source-policy/validate` | 表单提交前检查合规 | public/authorized/manual 通过 | cookie_pool、captcha_bypass、private_chat 拒绝 | 拒绝原因可读 |
| F030 | 数据源健康检查 | `POST /api/v1/data-sources/{id}/health-check`、`GET /api/v1/data-sources/{id}/health` | 点击测试连接，展示健康状态 | healthy、latency、last_success 更新 | timeout、auth_failed、schema_failed、empty_result | 单源 < 5s |
| F031 | 采集任务创建 | `POST /api/v1/collection-jobs` | 配置关键词、地域、时间、频率 | pending job 创建 | source 停用、关键词空、时间非法 | p95 < 800ms |
| F032 | 采集任务列表 | `GET /api/v1/collection-jobs` | 任务列表、筛选、排序 | 返回最近运行状态 | 非法状态、跨租户 | 1 万 job p95 < 1200ms |
| F033 | 启动采集 run | `POST /api/v1/collection-jobs/{id}/runs`、`IngestCaseWorkflow` | 点击运行 | 创建 `collection_run`，进入 workflow | source unhealthy、重复运行、policy blocked | 浏览器能看到进度变化 |
| F034 | 暂停/取消 run | `POST /api/v1/collection-runs/{id}/pause`、`POST /api/v1/collection-runs/{id}/cancel` | 暂停或取消运行 | run 状态变更 | 已完成 run 不可取消 | workflow 状态一致 |
| F035 | 重试 run | `POST /api/v1/collection-runs/{id}/retry` | 失败后重试 | 新 run 继承配置 | 不可重试错误、source 已归档 | 审计记录原 run |
| F036 | 采集 run 详情 | `GET /api/v1/collection-runs/{id}` | 查看 counters、errors、sample raw records | 返回成功/失败/阻断计数 | run 不存在、无权限 | p95 < 800ms |
| F037 | 合成西安样本生成 | `POST /api/v1/synthetic-scenarios` | 选择社区拆迁/养老保险上访样本 | 生成 raw seed，经采集链路入库 | 未选择城市、未声明 synthetic | 所有下游带 synthetic 标记 |
| F038 | 文件导入 | `POST /api/v1/imports/files` | 上传 CSV/JSON/Excel | 解析并生成 raw records | 文件损坏、字段缺失、超大小 | 上传进度、错误行可见 |
| F039 | 公开网页采集 | `POST /api/v1/public-web-runs` | 从公开 URL 拉取 | HTML/RSS 解析入库 | robots/policy blocked、404、超时 | run error 分类可查 |
| F040 | 官方 API 采集 | `POST /api/v1/official-api-runs` | 调用已授权 API | records 入库 | 401、429、schema drift | retry/backoff 可查 |
| F041 | 媒体文件导入 | `POST /api/v1/media-assets` | 上传/登记图片、视频、直播片段 | 生成 media asset 与 raw record | 格式不支持、病毒扫描失败、超大小 | 浏览器显示处理状态 |
| F042 | 原始记录列表 | `GET /api/v1/raw-records` | 按 source/run/case/status 查询 | 返回 raw records | 非法筛选、无权限 | 10 万记录 p95 < 1500ms |
| F043 | 原始记录详情 | `GET /api/v1/raw-records/{id}` | 查看原文、媒体、来源、hash、lineage | 返回完整 metadata | 对象不存在、敏感字段无权 | 浏览器敏感字段脱敏 |
| F044 | 原始记录标记 | `PATCH /api/v1/raw-records/{id}/labels` | 标记无关、重复、敏感、需复核 | 标签生效，审计可查 | 已归档不可改、非法标签 | mutation 后列表刷新 |
| F045 | 清洗任务启动 | `POST /api/v1/normalization-runs` | 对 run/case 启动清洗 | 生成 canonical text、time、region | 输入为空、重复启动冲突 | workflow 可观察 |
| F046 | 去重合并 | `POST /api/v1/deduplication-runs` | 对相似 raw records 去重 | 写 duplicate group | hash 冲突、低置信度需人工 | 1 万记录耗时有基线 |
| F047 | LLM 结构化抽取 | `POST /api/v1/extraction-runs` | 抽取主体、诉求、地点、时间、风险线索 | schema-valid 输出入库 | LLM timeout、schema invalid、无证据字段 | token/cost/error 记录 |
| F048 | 数据质量评分 | `POST /api/v1/data-quality-runs`、`GET /api/v1/data-quality/{object_id}` | 展示完整性、可信度、新鲜度 | 评分和原因可查 | 缺字段、来源低可信 | 评分版本可追溯 |
| F049 | 数据血缘查询 | `GET /api/v1/lineage/{object_type}/{object_id}` | 从报告/证据反查原始记录 | 返回链路图 | 链路断裂标红 | 浏览器能从报告跳回证据 |
| F050 | 失败隔离与重放 | `POST /api/v1/quarantine/{id}/replay` | 修复配置后重放失败记录 | 重放成功生成下游对象 | 原始数据已删除、schema 仍错误 | 错误队列可清空 |

### S3：西安 City 第一张冻结页

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F060 | 城市列表与切换 | `GET /api/v1/cities`、`PATCH /api/v1/navigation/context` | 选择西安并刷新保持 | City context 持久化 | 城市无权限、城市不存在 | 浏览器刷新不丢城市 |
| F061 | City 页面 bootstrap | `GET /api/v1/cities/{city_id}/overview` | 首屏加载总览、风险、事件、数据源摘要 | 返回 view-model | 无数据 empty、API 失败 error | 首屏接口 p95 < 1200ms |
| F062 | 地图图层数据 | `GET /api/v1/cities/{city_id}/map-layers` | 切换点位/热力/聚合/卫星模式 | 图层从后端数据生成 | 参数非法、瓦片失败、无点位 | 浏览器点位不重叠，瓦片失败有 fallback |
| F063 | 图层状态保存 | `PATCH /api/v1/cities/{city_id}/map-state` | 切换图层后刷新保持 | 状态保存 | 无权限、非法 zoom/layer | 浏览器刷新状态一致 |
| F064 | 城市事件排行榜 | `GET /api/v1/cities/{city_id}/event-rankings` | 热度/风险/增长/媒体维度切换 | 排名正确 | 维度非法、无数据 | p95 < 1000ms |
| F065 | 城市事件筛选 | `GET /api/v1/cities/{city_id}/events` | 关键词、区域、时间、类型、风险筛选 | 返回筛选结果 | 筛选无结果、非法时间 | 浏览器组合筛选正确 |
| F066 | 事件详情抽屉 | `GET /api/v1/events/{event_id}` | 点击地图/榜单/时间线打开详情 | 返回事件、证据、媒体、风险 | 事件不存在、无权限 | 跨组件选中状态一致 |
| F067 | 数据源健康面板 | `GET /api/v1/cities/{city_id}/source-health-summary` | 展示 source health、freshness、失败源 | 健康/降级/失败可区分 | source 全失败、freshness 过期 | 浏览器异常状态有明确提示 |
| F068 | 城市媒体证据面板 | `GET /api/v1/cities/{city_id}/media-evidence` | 展示图片、视频、直播片段 | 可按事件/类型筛选 | 媒体处理中、媒体失败 | 缩略图/片段状态稳定 |
| F069 | 时间线 | `GET /api/v1/cities/{city_id}/timeline` | 城市事件时间线、点击联动地图 | 返回时间段事件 | 无时间戳、时区异常 | 浏览器点击联动详情 |
| F070 | 从城市事件创建主题 | `POST /api/v1/topics` | 选事件创建主题态势 | topic 创建并绑定事件 | 事件未确认、重复创建 | 创建后导航到主题页 |
| F071 | City 页面状态库存 | 文档 + Playwright route states | loading、empty、error、degraded、selected、filtered、media-processing、no-permission | 每个状态有截图基线 | 状态缺失则不得冻结 | 内部浏览器截图 diff 通过 |
| F072 | City 第三方视觉/功能检查 | `POST /api/v1/reviews`、`PATCH /api/v1/reviews/{id}` | 检查员查看页面状态、提交结论 | PASS 后冻结 | FAIL 后生成修复任务 | 检查记录绑定页面版本 |

### S4：信号、证据、风险、多媒体算法

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F080 | 信号抽取运行 | `POST /api/v1/signal-runs`、`BuildMainlineWorkflow` activity | 从 raw/source records 生成 signals | 信号入库，带算法版本 | 输入不足、重复运行、schema 错 | 1 万记录耗时基线 |
| F081 | 事件聚类 | `POST /api/v1/event-clustering-runs` | 把相近信号聚为事件 | 生成 cluster 和原因 | 低置信度需人工、错误合并可拆 | 聚类结果可解释 |
| F082 | 信号搜索 | `GET /api/v1/signals` | 按关键词、地点、时间、风险、来源查信号 | 返回列表 | 无结果、非法筛选 | p95 < 1200ms |
| F083 | 信号详情 | `GET /api/v1/signals/{id}` | 查看来源、热度、证据、lineage | 返回完整链路 | 信号不存在、无权限 | 从信号跳原始记录 |
| F084 | 信号加入/移出草稿包 | `POST /api/v1/signal-packages/{id}/signals`、`DELETE /api/v1/signal-packages/{id}/signals/{signal_id}` | 勾选信号形成分析包 | 状态保存 | 重复加入、已确认包不可改 | 浏览器勾选后刷新保持 |
| F085 | 证据候选生成 | `POST /api/v1/evidence-runs` | 从信号生成证据候选 | evidence candidate 入库 | 无可用信号、来源低可信 | 证据有 refs |
| F086 | 证据详情 | `GET /api/v1/evidence/{id}` | 查看原文、媒体、来源、可信度、敏感项 | 返回脱敏视图 | 无权限看敏感字段 | 浏览器脱敏正确 |
| F087 | 证据复核状态更新 | `PATCH /api/v1/evidence/{id}/review` | 确认、驳回、需补充 | 状态和审计更新 | 状态冲突、无权限、重复提交 | mutation 后风险因子可重算 |
| F088 | 证据补充上传 | `POST /api/v1/evidence/{id}/attachments` | 上传补充材料 | 附件入库并绑定 | 格式非法、病毒扫描失败 | 浏览器可预览 |
| F089 | 风险因子生成 | `POST /api/v1/risk-factor-runs` | 从证据生成风险因子 | 因子、置信度、规则版本入库 | 无确认过证据、规则缺失 | 规则版本可追踪 |
| F090 | 风险因子列表 | `GET /api/v1/risk-factors` | 按 case/topic/status 查询 | 返回因子列表 | 非法筛选、无权限 | p95 < 1000ms |
| F091 | 风险因子确认/驳回 | `PATCH /api/v1/risk-factors/{id}/decision` | 人工确认或驳回 | 状态改变，审计可查 | 已进入报告不可随意改 | 浏览器状态刷新 |
| F092 | 风险置信度调整 | `PATCH /api/v1/risk-factors/{id}/confidence` | 调整置信度并写理由 | 保存理由和操作者 | 超范围、无理由 | 后续主线引用更新 |
| F093 | 冲突检测 | `POST /api/v1/conflict-detection-runs` | 标出事实冲突和来源冲突 | 生成 conflict groups | 证据不足、低置信冲突 | 冲突在证据页可见 |
| F094 | 图片 OCR | `POST /api/v1/media-assets/{id}/ocr-runs` | 图片处理状态从 pending 到 completed | OCR 文本入库并可引用 | 模糊、无文字、OCR 失败 | 单图处理耗时记录 |
| F095 | 图片主体/场景识别 | `POST /api/v1/media-assets/{id}/vision-runs` | 图片识别主体、场景、敏感元素 | 结果可绑定证据 | 低置信度需复核 | 输出不直接作为事实 |
| F096 | 视频抽帧 | `POST /api/v1/media-assets/{id}/frame-runs` | 视频生成关键帧 | 帧入库，带时间戳 | 格式不支持、超长视频 | 处理进度可见 |
| F097 | 视频 ASR | `POST /api/v1/media-assets/{id}/asr-runs` | 生成 transcript | 字幕片段可搜索 | 噪音、无语音、语言识别失败 | transcript 带时间码 |
| F098 | 视频 OCR | `POST /api/v1/media-assets/{id}/video-ocr-runs` | 从关键帧提取文字 | 文本与帧绑定 | 无文字、OCR 失败 | 片段可回放定位 |
| F099 | 关键片段检测 | `POST /api/v1/media-assets/{id}/segment-runs` | 标记高风险片段 | 片段绑定事件/证据 | 低置信度、无片段 | 浏览器点击片段播放 |
| F100 | 直播片段化 | `POST /api/v1/live-runs/{id}/segments` | 直播源切分片段并入库 | segment 可后续 OCR/ASR | 流中断、格式漂移 | 断点续跑记录 |
| F101 | 多媒体证据绑定 | `POST /api/v1/evidence/{id}/media-links` | 把媒体片段绑定证据 | 绑定成功 | 重复绑定、媒体未处理完成 | 证据详情显示媒体证据 |
| F102 | 敏感信息脱敏 | `POST /api/v1/redaction-runs` | 对文本/图片/视频字幕脱敏 | 脱敏版本可展示 | 无法脱敏、人工复核 | 前端默认展示脱敏版本 |

### S5：主线、World State、世界线、利益方识别

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F110 | 主线草稿生成 | `POST /api/v1/mainlines/drafts` | 从风险因子和证据生成主线 | 主线节点、依据、缺口入库 | 证据不足、风险因子未确认 | 主线页展示草稿 |
| F111 | 主线详情 | `GET /api/v1/mainlines/{id}` | 查看触发点、支撑证据、风险变化 | 返回完整结构 | 不存在、无权限 | p95 < 1000ms |
| F112 | 主线节点编辑 | `PATCH /api/v1/mainlines/{id}/nodes/{node_id}` | 调整节点标题、顺序、说明 | 保存版本 | 已确认主线需新版本 | 浏览器拖拽/编辑后刷新一致 |
| F113 | 主线信号操作 | `POST /api/v1/mainlines/{id}/signals`、`DELETE /api/v1/mainlines/{id}/signals/{signal_id}` | 加入/移除信号 | 影响质量检查 | 重复加入、已冻结主线 | lineage 更新 |
| F114 | 主线质量检查 | `POST /api/v1/mainlines/{id}/quality-check` | 检查证据覆盖、时间完整、冲突 | 返回问题清单 | 严重缺口阻止确认 | 质量结果可下载 |
| F115 | 确认主线 | `POST /api/v1/mainlines/{id}/confirm` | 人工确认主线 | confirmed，审计可查 | 质量未通过、无权限 | 确认后进入 World State |
| F116 | World State 生成 | `POST /api/v1/world-states` | 从确认主线生成当前态势 | world state 入库 | 主线未确认、输入过期 | 版本可比较 |
| F117 | World State 版本查询 | `GET /api/v1/world-states/{id}`、`GET /api/v1/world-states?case_id=` | 查看版本、输入、摘要 | 返回版本列表 | 版本不存在 | 浏览器可切换版本 |
| F118 | 案件图谱节点生成 | `POST /api/v1/case-graphs/{case_id}/build` | 从证据/主体/地点生成图谱 | nodes/edges 入库 | 实体不足、重复边冲突 | 图谱可视化不读静态数据 |
| F119 | 利益方识别 | `POST /api/v1/case-graphs/{case_id}/stakeholders` | 识别政府、社区、居民、企业、媒体等利益方 | stakeholder 入库，带证据 refs | 无证据角色、低置信度需复核 | 为 Agent Profile 做输入 |
| F120 | 利益方人工复核 | `PATCH /api/v1/stakeholders/{id}/review` | 确认、合并、驳回利益方 | 状态更新 | 无权限、已用于 Council 需新版本 | 浏览器复核记录可查 |
| F121 | 世界线运行创建 | `POST /api/v1/worldline-runs`、`GenerateWorldlineWorkflow` | 选择 World State 生成 24-72 小时分支 | nodes、probability、risk 入库 | state 未确认、输入过期 | workflow 可观察 |
| F122 | 世界线结果查询 | `GET /api/v1/worldline-runs/{id}` | 查看分支、概率、风险、证据 | 返回完整结果 | run 失败、无权限 | p95 < 1200ms |
| F123 | 世界线节点详情 | `GET /api/v1/worldline-nodes/{id}` | 查看节点依据、风险、建议 | 返回 refs | 节点不存在 | 点击节点联动证据 |
| F124 | 处置动作注入 | `POST /api/v1/worldline-runs/{id}/interventions` | 添加处置动作做反事实推演 | 生成新分支版本 | 动作非法、状态冲突 | 版本对比可见 |
| F125 | 世界线重跑 | `POST /api/v1/worldline-runs/{id}/rerun` | 数据更新后重跑 | 新 run 产生 | 旧 run 未完成、输入无变化 | 审计记录输入差异 |
| F126 | 世界线版本对比 | `GET /api/v1/worldline-runs/compare` | 对比两个版本概率和风险变化 | 返回 diff | 版本不兼容 | 浏览器差异高亮 |
| F127 | 标记 Council 节点 | `POST /api/v1/worldline-nodes/{id}/council-marker` | 选择需多 Agent 研判节点 | marker 保存 | 节点无风险、重复标记 | Council 创建时可选 |

### S6：专业 Agent、LLM、Council

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F130 | LLM Provider 状态 | `GET /api/v1/llm/providers/status` | 配置页展示 provider 可用性 | 返回可用、延迟、模型、配额 | 未配置、超时、限流 | p95 < 800ms |
| F131 | LLM 调用记录 | `GET /api/v1/llm/calls` | 查看 prompt 版本、token、cost、error | 调用可追踪 | 非管理员无权 | token/cost 统计正确 |
| F132 | 专业 Agent 模板库 | `GET /api/v1/agent-templates`、`POST /api/v1/agent-templates` | 管理舆情、治理、法律、传播、民生等专业模板 | 模板可复用 | schema 不合法、重复版本 | 模板发布需审批 |
| F133 | 从利益方生成 Agent Profile | `POST /api/v1/agent-profiles/generate` | 选择 worldline/stakeholders 生成 Agent | 生成角色、立场、约束、工具权限 | 利益方未复核、证据不足 | 生成记录可审计 |
| F134 | Agent `user.md` 生成 | `POST /api/v1/agent-profiles/{id}/user-md` | 展示背景、身份、事件上下文 | markdown 持久化 | 缺 stakeholder refs | 不得出现无证据事实 |
| F135 | Agent `soul.md` 生成 | `POST /api/v1/agent-profiles/{id}/soul-md` | 展示立场、价值权衡、风险偏好 | markdown 持久化 | 立场和证据冲突 | 第三方检查必须通过 |
| F136 | Agent `agent.md` 生成 | `POST /api/v1/agent-profiles/{id}/agent-md` | 展示工具、输出 schema、禁止动作 | markdown 持久化 | 工具权限越界 | Council 前必须 ready |
| F137 | Agent Profile 列表/详情 | `GET /api/v1/agent-profiles`、`GET /api/v1/agent-profiles/{id}` | 查看 Profile readiness | 返回状态、版本、检查记录 | 无权限、版本不存在 | p95 < 1000ms |
| F138 | Agent Profile 第三方检查 | `POST /api/v1/reviews`、`PATCH /api/v1/reviews/{id}` | 检查人确认人设可信、合规、无越界 | PASS 后可用于 Council | FAIL 阻断 Council | 检查意见生成修复任务 |
| F139 | 创建 Council Session | `POST /api/v1/council-sessions` | 选择世界线节点和 Agent 角色 | session created | Agent 未 ready、节点未标记 | 浏览器可看到参与角色 |
| F140 | 运行 Council | `POST /api/v1/council-sessions/{id}/run`、`RunCouncilWorkflow` | 点击运行，展示进度 | LLM 调用、消息、结论入库 | provider down、schema invalid、guardrail blocked | 运行状态可轮询 |
| F141 | Council 状态轮询 | `GET /api/v1/council-sessions/{id}/status` | 进度条、当前 Agent、失败原因 | 返回 running/completed/failed | session 不存在 | p95 < 500ms |
| F142 | Council 消息/过程 | `GET /api/v1/council-sessions/{id}/messages` | 查看每个 Agent 观点、证据引用、反驳 | 消息按顺序展示 | 无证据消息标记 blocked | 浏览器不展示未校验结论为事实 |
| F143 | Council 结果详情 | `GET /api/v1/council-sessions/{id}/result` | 查看共识、分歧、风险、建议 | schema-valid、evidence-linked | blocked claims、低置信度 | p95 < 1000ms |
| F144 | Council Guardrail 校验 | `POST /api/v1/council-sessions/{id}/validate` | 手动/自动校验输出 | 返回通过、阻断项、缺失证据 | schema invalid、引用不存在 | 不通过不得应用 |
| F145 | 假设压力测试 | `POST /api/v1/council-sessions/{id}/stress-tests` | 修改关键假设重新研判 | 生成 stress result | 假设非法、输入过大 | 结果与原结论对比 |
| F146 | Council 结果应用 | `POST /api/v1/council-sessions/{id}/apply` | 将结论应用到报告/任务/世界线 | 生成引用和审计 | 未通过校验、未复核 | 浏览器应用后目标页面更新 |

### S7：报告、第三方检查、任务、导出、案例库、配置

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F150 | 报告草稿生成 | `POST /api/v1/reports`、`GenerateReportWorkflow` | 从证据、世界线、Council 生成报告 | 草稿生成，章节可追踪 | 输入缺失、Council 未校验 | workflow 可观察 |
| F151 | 报告声明校验 | `POST /api/v1/reports/{id}/claim-validation` | 检查每个事实声明证据引用 | 输出 passed/blocked/warning | 引用不存在、证据未确认 | 无证据结论不得发布 |
| F152 | 报告详情 | `GET /api/v1/reports/{id}` | 查看章节、证据、风险、任务建议 | 返回完整报告 | 无权限、报告不存在 | p95 < 1200ms |
| F153 | 报告编辑 | `PATCH /api/v1/reports/{id}` | 编辑摘要、措辞、章节说明 | 生成新版本 | 已冻结不可改、缺修改理由 | 版本 diff 可查 |
| F154 | 提交第三方审阅 | `POST /api/v1/reports/{id}/submit-review` | 提交给检查人 | review task created | claim validation 未通过 | 浏览器显示审阅中 |
| F155 | 第三方审阅通过 | `PATCH /api/v1/reviews/{id}` | 检查人 PASS | 报告进入待发布 | 无权限、检查项缺失 | 审阅记录绑定报告版本 |
| F156 | 第三方审阅退回 | `PATCH /api/v1/reviews/{id}` | 检查人 FAIL 并写意见 | 报告回到修复 | 无退回理由 | 自动生成修复任务 |
| F157 | 报告冻结发布 | `POST /api/v1/reports/{id}/publish` | 发布正式版本 | frozen version created | 未审阅、过期输入 | 发布后不可直接改 |
| F158 | 报告导出 | `POST /api/v1/reports/{id}/exports`、`GET /api/v1/exports/{id}` | 导出 PDF/Word/JSON | 文件生成，带水印和引用 | export 失败、无权限 | 下载可用，内容脱敏 |
| F159 | 任务自动生成 | `POST /api/v1/tasks/generate` | 从报告/Council 生成处置任务 | task 入库 | 报告未发布、建议无责任方 | 任务和证据链接可查 |
| F160 | 手动创建任务 | `POST /api/v1/tasks` | 手动补充任务 | 创建成功 | 缺责任人、非法截止时间 | p95 < 800ms |
| F161 | 任务状态更新 | `PATCH /api/v1/tasks/{id}/status` | 待办、处理中、完成、关闭 | 状态流转正确 | 非法流转、无权限 | 浏览器任务看板更新 |
| F162 | 复盘创建 | `POST /api/v1/retrospectives` | 对事件处置做复盘 | 复盘记录入库 | 报告未关闭、重复复盘 | 浏览器进入复盘页 |
| F163 | 复盘知识入库 | `POST /api/v1/knowledge-items` | 把复盘经验入库 | 知识项可检索 | 敏感内容未脱敏 | 审批后可用 |
| F164 | 案例库搜索 | `GET /api/v1/cases` | 搜索历史案例、过滤城市/类型/风险 | 返回列表 | 无结果、非法筛选 | 10 万案例 p95 < 1500ms |
| F165 | 案例详情 | `GET /api/v1/cases/{id}` | 查看案例全链路 | 返回对象链路 | 无权限、案例归档 | lineage 可跳转 |
| F166 | 应用案例建议 | `POST /api/v1/cases/{id}/suggestions/apply` | 复用相似案例策略 | 生成建议草稿 | 案例不兼容、需审批 | 应用结果可回滚 |
| F167 | 数据源配置版本 | `GET /api/v1/config/data-sources/versions`、`POST /api/v1/config/data-sources/versions` | 配置版本化 | 新版本待审批 | schema 不兼容 | 发布后新 run 生效 |
| F168 | 标签体系配置 | `GET /api/v1/config/taxonomy`、`PATCH /api/v1/config/taxonomy` | 配置议题、风险、主体标签 | 保存新版本 | 标签删除被引用 | 回归测试必须通过 |
| F169 | 模型参数配置 | `GET /api/v1/config/models`、`PATCH /api/v1/config/models` | 配置 embedding、聚类、风险阈值 | 保存版本 | 阈值越界 | 回归测试比较差异 |
| F170 | Agent 配置 | `GET /api/v1/config/agents`、`PATCH /api/v1/config/agents` | 配置专业 Agent 模板和权限 | 保存版本 | 工具权限越界 | 审批后发布 |
| F171 | Prompt 模板配置 | `GET /api/v1/config/prompts`、`PATCH /api/v1/config/prompts` | 管理 prompt 模板版本 | 保存版本 | schema 不匹配 | prompt 回归测试通过 |
| F172 | 配置回归测试 | `POST /api/v1/config/regression-runs` | 发布前跑样本回归 | 返回差异和风险 | 回归失败阻断发布 | 回归结果可审阅 |
| F173 | 配置审批发布 | `POST /api/v1/config/releases` | 审批并发布配置 | release 生效 | 审批缺失、版本冲突 | 审计可查 |
| F174 | 配置回滚 | `POST /api/v1/config/releases/{id}/rollback` | 回滚到旧版本 | 回滚成功 | 有运行中 workflow 冲突 | 回滚影响范围可见 |

### S8：全链路、性能、安全、发布验收

| ID | 功能点 | 后端 API / 工作流 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| F180 | 社区拆迁全链路 | E2E workflow set | 从合成/公开源到报告导出 | 完整对象链路完成 | 中途 workflow 失败可恢复 | 内部浏览器全流程点击 |
| F181 | 养老保险上访全链路 | E2E workflow set | 从采集到 Council 再到任务 | 完整对象链路完成 | 数据不足、角色冲突 | 浏览器检查报告引用 |
| F182 | 多媒体证据全链路 | Media workflow set | 图片/视频/直播证据进入研判 | OCR/ASR/片段绑定证据 | 媒体处理失败、低置信 | 浏览器回放片段 |
| F183 | 权限异常全链路 | Auth/RBAC APIs | 不同角色访问不同页面和动作 | 权限正确 | 401/403/跨租户 | 浏览器越权跳转正确 |
| F184 | LLM 异常全链路 | LLM provider/council APIs | provider down、timeout、schema invalid | 错误可见，run failed | 静默 fallback 禁止 | 错误记录可查 |
| F185 | Workflow 异常全链路 | Temporal workflow APIs | activity 失败、重试、幂等 | 可重试、可恢复 | 重复提交、状态冲突 | workflow_runs 和 audit 一致 |
| F186 | API 性能基线 | 所有核心 GET/POST | 城市页、检索、报告、任务 | 达到 p95 指标 | 压测错误率超阈 | 输出性能报告 |
| F187 | 页面视觉回归 | Playwright/Codex Browser | City、数据源、证据、世界线、Council、报告页 | 截图 diff 通过 | 布局错位、文字溢出 | 每页有基线和状态截图 |
| F188 | 安全测试 | Auth/RBAC/input APIs | 登录、上传、导出、配置 | 常规攻击被拒 | SQLi、XSS、越权、文件攻击 | 输出安全检查报告 |
| F189 | 观测面板 | `GET /api/v1/ops/health`、`GET /api/v1/ops/metrics` | 查看 API、worker、DB、LLM、workflow 状态 | 状态可见 | 服务降级可见 | 生产演示前通过 |
| F190 | 发布验收包 | 文档 + 自动化报告 | 打包评审材料、测试报告、风险清单 | DCP 材料完整 | P0/P1 blocker 未清零 | 客户评审前冻结 |

## 7. 页面状态与浏览器验收矩阵

每个客户可见页面必须建立以下状态，不允许只实现 happy path。

| 页面 | 必测状态 |
| --- | --- |
| 登录页 | 空账号、空密码、账号不存在、密码错误、账号禁用、连续失败锁定、登录成功、服务不可用 |
| City 页 | loading、empty、error、source degraded、filter no result、selected event、map tile fail、media processing、no permission |
| 数据源页 | source empty、create success、policy blocked、health healthy、health failed、run running、run failed、retry success |
| 信号页 | search success、no result、signal detail、lineage missing、draft add/remove、permission denied |
| 证据页 | candidate、confirmed、rejected、needs review、sensitive redacted、media pending、media failed |
| 主线页 | draft、quality failed、confirmed、version diff、node edit conflict |
| 世界线页 | run pending、running、completed、failed、intervention diff、node detail |
| Agent Profile 页 | profile generating、ready、review failed、markdown missing、version conflict |
| Council 页 | session created、running、provider error、schema invalid、blocked claims、completed、applied |
| 报告页 | draft、claim validation failed、submitted review、review returned、published、export failed |
| 配置页 | draft config、regression failed、approved、published、rollback |

浏览器验收要求：

- 使用内部浏览器或 Playwright 打开真实路由。
- 点击真实控件，不接受只调用 API 的替代验收。
- 捕获 console error、network failure、关键截图。
- 客户可见页面必须做截图基线和 diff。
- 发现设计稿、静态页、工程页不一致时，以页面设计合同为准，不现场靠肉眼反复调。

## 8. 第三方检查门禁

每个功能点完成后，必须生成第三方检查记录。

| 输出类型 | 检查重点 | 阻断条件 |
| --- | --- | --- |
| API | 参数、权限、状态码、错误码、审计、幂等 | 业务交互无 API、错误不可追踪 |
| 数据源 | 合规策略、source health、run counters、失败归因 | 私域绕过、无健康状态、无 run 记录 |
| 算法 | 输入引用、算法版本、输出可解释、置信度 | 无输入 refs、不可复现、无版本 |
| 多媒体 | OCR/ASR/CV 输出、时间戳、证据绑定、脱敏 | 媒体结果直接当事实、未脱敏 |
| Agent Profile | 背景、立场、逻辑、工具权限、禁止动作 | 无证据人设、角色越界、未复核 |
| Council | schema、证据引用、blocked claims、分歧记录 | 无证据结论、静默 fallback、schema invalid |
| 报告 | 每个事实声明是否可追溯 | 未校验声明、引用不存在、未审阅 |
| 前端页面 | 状态覆盖、API 真实调用、视觉基线、浏览器操作 | 前端 mock、页面状态缺失、截图 diff 失败 |
| 性能 | p95、错误率、workflow 耗时、LLM 耗时 | 核心链路超阈且无降级方案 |
| 安全 | 权限、越权、上传、导出、敏感信息 | 高危越权、敏感信息泄露 |

检查状态：

- `pending`：待检查。
- `pass`：通过，可冻结。
- `fail`：不通过，必须修复。
- `waived`：业务方批准豁免，必须记录原因和风险。

## 9. 多 Agent 开发与测试分工

开发 Agent：

- 后端 A：认证、权限、审计、数据源治理。
- 后端 B：采集 run、清洗、信号、证据、风险。
- 后端 C：主线、世界线、Agent Profile、Council、LLM。
- 后端 D：报告、任务、配置、案例库、观测。
- 前端 A：登录、导航、City、数据源。
- 前端 B：信号、证据、主线、世界线、Council。
- 前端 C：报告、任务、案例库、配置、运维页面。
- 数据/算法 Agent：抽取、聚类、风险、多媒体、质量评分。
- LLM Agent：provider、prompt、schema、guardrails、blocked claims。

测试 Agent：

- 功能测试 Agent：验证正常路径和数据一致性。
- 异常测试 Agent：验证 401/403/404/409/422/429/500/503、外部依赖失败、状态冲突。
- 性能测试 Agent：验证 API p95、页面首屏、workflow 耗时、LLM 耗时、媒体处理耗时。
- 浏览器测试 Agent：用内部浏览器真实点击，检查 network、console、截图。
- 第三方检查 Agent：从产品、架构、QA、安全、数据/LLM 视角做 PASS/FAIL。

每个功能点迭代顺序：

```text
功能需求冻结
-> API/Schema 合同
-> 后端实现和数据库迁移
-> 后端单测/集成测试
-> 前端接入和页面状态
-> 功能测试 Agent
-> 异常测试 Agent
-> 性能测试 Agent
-> 内部浏览器测试 Agent
-> 第三方检查 Agent
-> 修复
-> 冻结
```

## 10. 关键算法清单与方案

| 算法点 | 方案 | 输入 | 输出 | 验收 |
| --- | --- | --- | --- | --- |
| 原始记录去重 | hash + 近似文本相似度 + 来源时间窗口 | raw records | duplicate groups | 重复记录不重复进入信号 |
| 实体抽取 | 规则 + LLM schema extraction | 文本/OCR/ASR | entities、mentions | schema-valid，证据 refs 完整 |
| 地点归一 | 行政区划词典 + geocoding adapter + 人工复核 | 地点文本 | region hints、coordinates | 西安市区县可稳定归一 |
| 事件聚类 | 时间/地点/主体/语义向量综合聚类 | signals | event clusters | 误合并可人工拆分 |
| 热度计算 | 来源权重、传播量、时间衰减、媒体权重 | signals/source health | heat score | 计算可解释，有版本 |
| 可信度评分 | source trust、证据类型、交叉印证、复核状态 | evidence/raw/source | credibility score | 低可信不会变成正式事实 |
| 风险因子生成 | 规则库 + LLM 辅助解释 + 人工确认 | confirmed evidence | risk factors | 规则版本和证据 refs 可查 |
| 冲突检测 | 同主体/同时间/同地点的事实断言比对 | evidence claims | conflict groups | 冲突必须在报告中标注 |
| 主线构建 | 触发点、升级点、扩散点、处置点排序 | signals/evidence/risk | mainline draft | 质量检查通过才能确认 |
| World State | 当前事实、风险、利益方、信息缺口汇总 | confirmed mainline | world state version | 版本可比对 |
| 世界线推演 | 规则模型 + Agent/LLM 辅助解释 + 概率分支 | world state | worldline nodes | 分支必须引用证据 |
| 利益方识别 | 图谱主体 + 诉求/权责/影响关系抽取 | case graph | stakeholders | 角色需复核 |
| Agent Profile 生成 | stakeholder -> `user.md/soul.md/agent.md` | stakeholders/evidence | agent profiles | 第三方检查通过才能 Council |
| Council 研判 | 多 Agent schema 输出 + guardrails + blocked claims | worldline node/context | council result | 无证据 claim 被阻断 |
| 报告声明校验 | claim extraction + evidence ref validation | report draft | claim validation result | 失败不能发布 |
| 图片 OCR | OCR engine adapter + 置信度 | images | OCR text | 可绑定证据 |
| 图片主体/场景识别 | CV adapter + 人工复核 | images | scene/entity hints | 不直接作为事实结论 |
| 视频 ASR | ASR adapter + 时间码 | video/audio | transcript segments | 可搜索可定位 |
| 视频 OCR/抽帧 | key frames + OCR | video | frame text | 片段与证据绑定 |
| 直播片段化 | segmenter + run state | live stream | segments | 中断可恢复 |

## 11. 评审关注点

评审时建议重点看这些问题：

- 数据源是否已经从“一个模块”拆成了渠道级功能点。
- 合成数据源是否被明确标记，并且必须走真实 pipeline。
- City 页是否先做后端 view-model，再做冻结页。
- 每个前端业务交互是否都有对应 API。
- 多媒体是否进入主链路，而不是后期补丁。
- 世界线、利益方、Agent Profile、Council 的顺序是否正确。
- `user.md`、`soul.md`、`agent.md` 是否成为产品运行时对象，而不是 Codex 自身配置。
- Agent 输出、报告输出是否有证据引用和 blocked claims。
- 第三方检查是否是系统功能，不只是人工口头检查。
- 每个功能点是否都有功能测试、异常测试、性能测试、浏览器测试。

## 12. 当前计划与旧计划的关系

旧计划继续作为资料保留：

- `docs/p0-production-grade-delivery-plan-20260508.md` 作为生产级交付原则依据。
- `docs/full-project-api-frontend-test-development-plan-20260508.md` 作为早期功能/API/测试草案。
- `docs/full-project-atomic-task-development-plan-20260508.md` 作为原子任务拆分草案。

本评审稿调整了执行顺序和功能边界：

- 把数据源治理、source health、run contract 提前。
- 把分渠道采集和多媒体采集拆成独立功能点。
- 把 City 页面 view-model、页面状态库存、浏览器 diff 前置。
- 把利益方识别和 Agent Profile 生成放在 Council 之前。
- 把第三方检查变成系统级门禁。
- 把测试 Agent 介入点绑定到每个功能点，而不是阶段末尾。
