# CollectiveEventTwin 完整项目原子任务级开发计划

日期：2026-05-08

状态：执行版 WBS，替代 `full-project-api-frontend-test-development-plan-20260508.md` 的粗粒度功能分类。

参考：

- `C:\Users\ROG\Desktop\一、项目总体开发周期.md`
- `docs/p0-production-grade-delivery-plan-20260508.md`
- 用户新增约束：计划必须落到每一个不可再拆的任务；数据采集、清洗、LLM、算法、Agent、workflow 都必须作为真实开发工作量进入计划。
- 用户新增约束：专业 Agent 复用、OpenClaw 风格多 Agent 研判、分渠道采集、多媒体闭环均指 CollectiveEventTwin 产品运行时能力，与 Codex 开发助手无关。

## 0. 原子任务判定标准

一个任务必须满足以下条件才允许进入排期：

- 只交付一个用户可感知功能、一个后端能力、一个 API 行为、一个算法能力、一个 Agent 能力，或一个测试验收能力。
- 不能再拆成多个独立可交付功能。例如“数据采集能力”不合格；“public_web 数据源 URL 连通性检测”合格。
- 必须有明确输入、输出、落库状态、异常结果和测试 Agent。
- 涉及前端交互时，必须说明前端场景；不涉及前端的后端能力，必须说明触发 API、workflow activity、算法服务或内部 service。
- 所有业务数据来自 PostgreSQL 或对象存储引用；前端不允许 mock、fixture、静态假数据。
- 每个 mutation 必须写审计日志；每个长任务必须写 workflow run；每个算法/LLM/Agent 结果必须写版本、输入快照、输出快照、失败原因和血缘。

任务字段：

| 字段 | 说明 |
| --- | --- |
| ID | 原子任务编号，可直接派给一个 agent |
| 原子功能 | 不可再拆的功能点 |
| 后端/API/服务 | 需要实现的接口、服务、activity 或算法 |
| 前端场景 | 有页面时写具体交互；无页面时写后台触发 |
| 正常测试 | 功能测试 Agent 验收 |
| 异常测试 | 异常测试 Agent 验收 |
| 性能/浏览器验收 | 性能测试或内部浏览器测试 |

## 1. 阶段与冻结口径

| 阶段 | 周期 | 冻结条件 |
| --- | --- | --- |
| P0 | 第 1 周 | 数据模型、API 约定、workflow 状态机、测试矩阵冻结 |
| P1 | 第 2-3 周 | 登录、权限、租户、导航、审计、系统配置可用 |
| P2 | 第 4-8 周 | 数据源、采集、解析、清洗、LLM 抽取、质量评分、血缘可用 |
| P3 | 第 9-11 周 | city 冻结页、非校园样本、主题态势、事件发现可用 |
| P4 | 第 12-15 周 | 信号、证据、风险因子、算法评分可用 |
| P5 | 第 16-19 周 | 主线建模、World State、世界线推演可用 |
| P6 | 第 20-22 周 | Agent Council、LLM、guardrail、评测回归可用 |
| P7 | 第 23-25 周 | 报告、任务、审批、导出、复盘可用 |
| P8 | 第 26-28 周 | 案例库、配置中心、回滚、权限、安全、性能验收完成 |

## 2. P0 架构、数据模型、任务底座

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-001 | 定义统一 API 响应结构 | FastAPI response schema `{data, meta, trace_id}` / `{error, trace_id}` | 所有页面统一处理成功/失败 | 成功响应包含 trace_id | 业务错误不返回 200 假成功 | API contract test 全量通过 |
| AT-002 | 定义统一错误码表 | `error_codes` 常量与文档 | 前端按错误码显示提示 | 401/403/404/409/422/429/500 可识别 | 未登记错误码触发测试失败 | 单测覆盖全部错误码 |
| AT-003 | 建立租户表 | `tenants` migration / repository | 登录选择租户 | 可创建 active tenant | 重复 tenant_code 返回 409 | migration rollback 通过 |
| AT-004 | 建立用户表 | `users` migration / password hash | 登录、用户管理 | 可创建 active user | 弱密码、重复用户名失败 | 用户查询 p95 < 100ms |
| AT-005 | 建立角色权限表 | `roles`, `permissions`, `role_permissions` | 菜单和按钮权限 | admin/analyst/reviewer 权限正确 | 越权 API 返回 403 | 权限计算 p95 < 80ms |
| AT-006 | 建立审计日志表 | `audit_logs` migration / audit middleware | 审计中心查询 | mutation 自动写入 actor/action/object | query API 不写 mutation 审计 | 10 万日志分页 p95 < 800ms |
| AT-007 | 建立 workflow run 表 | `workflow_runs`, `workflow_steps` | 任务状态页 | run 有 pending/running/succeeded/failed | 非法状态流转 409 | 状态查询 p95 < 300ms |
| AT-008 | 建立文件对象引用表 | `file_objects` / object storage key | 上传、导出、证据附件 | 文件元数据落库 | 未授权访问文件返回 403 | 文件元数据查询 p95 < 300ms |
| AT-009 | 建立数据血缘表 | `lineage_edges` | 证据追溯、报告追溯 | raw -> clean -> signal -> evidence 可追踪 | 缺 source_node 拒绝写入 | 血缘查询 4 跳 p95 < 1000ms |
| AT-010 | 建立版本化配置表 | `config_versions` | 配置发布/回滚 | draft/published/archived 可流转 | 已发布配置不可直接修改 | 配置读取 p95 < 100ms |
| AT-011 | 建立算法运行表 | `algorithm_runs` | 算法结果详情 | 记录 algorithm_name/version/input/output | 缺版本号拒绝写结果 | 运行列表 p95 < 500ms |
| AT-012 | 建立 LLM 调用表 | `llm_calls` | LLM 追溯页 | 记录 provider/model/prompt_hash/tokens/status | prompt 原文按权限脱敏 | 10 万调用分页 p95 < 1000ms |
| AT-013 | 建立 Agent session 表 | `agent_sessions`, `agent_outputs` | Council 页 | session 和每个 agent 输出落库 | 输出 schema invalid 标 failed | session 查询 p95 < 500ms |
| AT-014 | 建立通知表 | `notifications` | 顶部通知/待办 | 任务成功/失败生成通知 | 已读重复提交幂等 | 未读查询 p95 < 200ms |
| AT-015 | 建立测试种子数据脚本 | test-only seed command | 自动化测试环境 | 只在 test env 可运行 | prod env 运行被拒绝 | CI 初始化 < 60s |

## 3. P1 登录、权限、导航、审计

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-016 | 用户名密码登录 | `POST /api/v1/auth/login` | 登录页提交 | 正确账号返回 token/user/permissions | 用户不存在返回 401 | 浏览器登录后进入 city 页 |
| AT-017 | 密码错误计数 | auth service failed_attempts | 登录失败提示 | 密码错 1 次记录失败次数 | 连续失败达到阈值锁定 | 登录 API p95 < 500ms |
| AT-018 | 锁定账号拒绝登录 | auth service lock check | 登录页显示锁定提示 | 锁定账号返回 `ACCOUNT_LOCKED` | 锁定期间正确密码也失败 | 浏览器显示明确错误 |
| AT-019 | 禁用账号拒绝登录 | auth service active check | 登录页显示禁用提示 | disabled user 返回 403 | 不泄露用户是否存在细节 | 安全测试通过 |
| AT-020 | 租户不存在拒绝登录 | tenant resolver | 登录页租户输入 | 正确租户可登录 | 错误 tenant_code 返回 404/401 | 多租户隔离测试通过 |
| AT-021 | 刷新 access token | `POST /api/v1/auth/refresh` | 页面刷新自动续期 | 有效 refresh token 返回新 token | 过期/吊销 token 返回 401 | 刷新 p95 < 300ms |
| AT-022 | 登出并吊销 token | `POST /api/v1/auth/logout` | 点击退出 | token 加入吊销表 | 重复登出幂等 | 浏览器退出后受保护页 401 |
| AT-023 | 获取当前用户 | `GET /api/v1/me` | 顶栏用户信息 | 返回用户名、角色、租户 | 无 token 返回 401 | 页面刷新后信息不丢 |
| AT-024 | 获取权限菜单 | `GET /api/v1/me/navigation` | 左侧导航渲染 | analyst 只看到授权菜单 | 无权限菜单不返回 | 浏览器校验菜单差异 |
| AT-025 | 按权限隐藏按钮 | `GET /api/v1/me/permissions` | 页面操作按钮 | 有权限显示运行/审批按钮 | 无权限按钮不出现且 API 403 | 浏览器角色切换验收 |
| AT-026 | 用户列表查询 | `GET /api/v1/users` | 用户管理页 | 支持分页/角色/状态筛选 | 非 admin 返回 403 | 1 万用户 p95 < 800ms |
| AT-027 | 创建用户 | `POST /api/v1/users` | 新建用户表单 | 创建后可登录 | 重复用户名/弱密码 422/409 | 审计日志可查 |
| AT-028 | 修改用户角色 | `PATCH /api/v1/users/{id}/roles` | 用户管理角色选择 | 新权限立即生效 | 修改自己 admin 角色需二次确认 | 浏览器重新登录验证 |
| AT-029 | 禁用用户 | `PATCH /api/v1/users/{id}/status` | 用户管理开关 | disabled 后无法登录 | 禁用最后一个 admin 返回 409 | 审计记录 actor/object |
| AT-030 | 审计日志查询 | `GET /api/v1/audit-logs` | 审计中心 | 可按 actor/action/object 查询 | 越权跨租户返回 403 | 10 万日志 p95 < 800ms |
| AT-031 | 审计详情查看 | `GET /api/v1/audit-logs/{id}` | 审计详情弹窗 | 展示 before/after/reason | 敏感字段脱敏 | 浏览器点击日志验收 |

## 4. P2 数据源配置原子任务

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-032 | 数据源类型枚举查询 | `GET /api/v1/data-source-types` | 新建数据源第一步 | 返回 public_web/official_api/rss/file_upload/webhook/manual/db_import/object_storage | 未配置类型返回空数组并告警 | p95 < 200ms |
| AT-033 | 数据源列表查询 | `GET /api/v1/data-sources` | 数据源列表筛选 | 按类型/状态/健康分页 | 非授权租户数据不可见 | 1000 源 p95 < 800ms |
| AT-034 | 创建 public_web 数据源基础信息 | `POST /api/v1/data-sources` type=public_web | 表单填写名称、域名、用途 | 创建 draft source | 重名返回 409 | 审计可查 |
| AT-035 | 校验 public_web URL 可达性 | `POST /api/v1/data-sources/{id}/validate-url` | 点击检测 URL | 返回 status_code/content_type/latency | DNS 失败、TLS 失败、超时 | 单 URL p95 < 5s |
| AT-036 | 保存 public_web 抓取策略 | `PUT /api/v1/data-sources/{id}/crawl-policy` | 配置频率、深度、robots、限速 | policy 保存为 draft | 非法频率/深度 422 | 浏览器保存后刷新保留 |
| AT-037 | 创建 official_api 数据源基础信息 | `POST /api/v1/data-sources` type=official_api | 新建官方 API 源 | 保存 base_url/method/schema | URL 非 https 警告或拒绝 | 审计可查 |
| AT-038 | 保存 API 鉴权方式 | `PUT /api/v1/data-sources/{id}/auth` | 选择 api_key/oauth/basic | 凭据只保存 secret_ref | 明文 secret 不落库 | 安全测试查库无明文 |
| AT-039 | 测试 official_api 连接 | `POST /api/v1/data-sources/{id}/test-connection` | 点击测试连接 | 返回 sample response metadata | 401/403/429/5xx 分类展示 | p95 < 8s |
| AT-040 | 配置 API 分页策略 | `PUT /api/v1/data-sources/{id}/pagination` | 配置 page/cursor/next_url | 策略保存并可 dry-run | 缺 next path 返回 422 | dry-run 3 页 < 15s |
| AT-041 | 创建 RSS 数据源 | `POST /api/v1/data-sources` type=rss | 新建 RSS 源 | RSS URL 保存 | 非 RSS 文档返回 422 | p95 < 3s |
| AT-042 | 解析 RSS feed 元数据 | `POST /api/v1/data-sources/{id}/rss/inspect` | 点击预览 | 返回 title/item_count/latest_time | feed 空或格式错返回错误 | p95 < 5s |
| AT-043 | 创建 file_upload 数据源 | `POST /api/v1/data-sources` type=file_upload | 新建上传源 | 保存允许文件类型和 schema | 禁止类型返回 422 | 审计可查 |
| AT-044 | 创建 webhook 数据源 | `POST /api/v1/data-sources` type=webhook | 新建外部推送源 | 生成 webhook endpoint/secret | 重复 secret rotation 需版本 | p95 < 300ms |
| AT-045 | 验证 webhook 签名 | webhook middleware | 外部系统推送 | 正确签名接收 payload | 错签/重放/过期 401/409 | 100 rps 无丢失 |
| AT-046 | 创建 manual 数据源 | `POST /api/v1/data-sources` type=manual | 人工录入入口 | 创建人工数据源 | 非授权角色 403 | 审计可查 |
| AT-047 | 创建 db_import 数据源 | `POST /api/v1/data-sources` type=db_import | 新建数据库导入源 | 保存连接配置引用 | 明文密码拒绝落库 | 连接测试 p95 < 8s |
| AT-048 | 创建 object_storage 数据源 | `POST /api/v1/data-sources` type=object_storage | 新建对象存储导入源 | 保存 bucket/prefix/secret_ref | 无权限 bucket 返回 403 | list 1000 keys < 10s |
| AT-049 | 数据源发布版本 | `POST /api/v1/data-sources/{id}/versions/publish` | 点击发布配置 | draft -> published | 未测试连接不允许发布 | 新采集使用版本号 |
| AT-050 | 数据源回滚版本 | `POST /api/v1/data-sources/{id}/versions/{version}/rollback` | 配置历史回滚 | 新建 rollback 版本 | 正在运行任务不受影响 | 审计包含 from/to |
| AT-051 | 数据源停用 | `PATCH /api/v1/data-sources/{id}/status` disabled | 停用开关 | 停用后不可新建 run | running run 不被强杀 | 浏览器运行按钮禁用 |
| AT-052 | 数据源健康状态查询 | `GET /api/v1/data-sources/{id}/health` | 健康详情 | 返回 last_success/last_failure/error_rate | 无采集历史显示 unknown | p95 < 300ms |
| AT-053 | 数据源合规标签保存 | `PUT /api/v1/data-sources/{id}/compliance` | 标注授权范围/保留期 | 标签落库并影响采集策略 | 缺授权说明不允许发布 | 合规测试通过 |

## 5. P2 Adapter、调度、采集运行

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-054 | Adapter 插件注册 | adapter registry service | 后台启动加载 adapter | public_web/api/rss/file/manual/db/object 注册成功 | adapter 缺必需方法启动失败 | 单测覆盖 registry |
| AT-055 | Adapter 能力查询 | `GET /api/v1/adapters/capabilities` | 数据源表单动态字段 | 返回各 adapter 支持字段 | 未知 adapter 返回 404 | p95 < 200ms |
| AT-056 | 创建一次性采集任务 | `POST /api/v1/collection-jobs` schedule=once | 创建采集任务 | 保存 source_id/query/window | 停用源/未发布源 409 | 浏览器创建后列表出现 |
| AT-057 | 创建定时采集任务 | `POST /api/v1/collection-jobs` schedule=cron | 配置周期任务 | cron 保存并注册调度 | 非法 cron/过密频率 422 | 调度注册 < 1s |
| AT-058 | 采集任务列表查询 | `GET /api/v1/collection-jobs` | 任务列表筛选 | 按状态/源/创建人分页 | 跨租户不可见 | 1 万任务 p95 < 1000ms |
| AT-059 | 采集任务详情查询 | `GET /api/v1/collection-jobs/{id}` | 任务详情 | 返回配置、版本、最近 run | 不存在 404 | p95 < 500ms |
| AT-060 | 启动采集 run | `POST /api/v1/collection-jobs/{id}/runs` | 点击运行 | 创建 workflow run pending | 已有 running run 返回 409 | 浏览器轮询状态 |
| AT-061 | 暂停采集任务 | `POST /api/v1/collection-jobs/{id}/pause` | 点击暂停 | scheduled -> paused | running run 不直接中断 | 暂停后无新 run |
| AT-062 | 恢复采集任务 | `POST /api/v1/collection-jobs/{id}/resume` | 点击恢复 | paused -> scheduled | source disabled 返回 409 | 下一周期正常运行 |
| AT-063 | 取消采集 run | `POST /api/v1/collection-runs/{id}/cancel` | run 详情点击取消 | running -> cancelling -> cancelled | succeeded run 取消返回 409 | worker 停止后状态一致 |
| AT-064 | 重试失败采集 run | `POST /api/v1/collection-runs/{id}/retry` | 点击重试 | 新建 retry run，继承 input snapshot | succeeded run 不可重试 | 不重复写 raw record |
| AT-065 | 采集 run 列表查询 | `GET /api/v1/collection-runs` | run 列表 | 支持 status/source/time 筛选 | 越权 403 | 10 万 run p95 < 1000ms |
| AT-066 | 采集 run 步骤查询 | `GET /api/v1/collection-runs/{id}/steps` | run 详情步骤条 | fetch/parse/store/clean/extract 状态可见 | run 不存在 404 | 浏览器状态实时刷新 |
| AT-067 | public_web 页面抓取 | workflow activity `fetch_public_web_page` | 后台采集 | HTML 原文写 raw_records/object | 超时、403、非 HTML 分类失败 | 单页 < 10s |
| AT-068 | public_web 链接发现 | activity `discover_public_web_links` | 后台采集 | 按深度产生待抓取 URL | robots 禁止则跳过并记录 | 1000 URL < 60s |
| AT-069 | official_api 请求执行 | activity `fetch_official_api_page` | 后台采集 | 按分页策略拉取 JSON | 401/429/5xx 分类重试 | 100 页 < 5min |
| AT-070 | RSS item 拉取 | activity `fetch_rss_items` | 后台采集 | 新 item 写 raw_records | 重复 guid 不重复写 | 1 万 item < 3min |
| AT-071 | 文件上传接收 | `POST /api/v1/uploads` | 上传 CSV/XLSX/PDF/DOCX/JSON | 文件进入对象存储并写 file_objects | 超大小/禁类型/病毒扫描失败 | 100MB 上传可恢复提示 |
| AT-072 | 上传文件绑定采集 run | `POST /api/v1/collection-jobs/{id}/file-runs` | 上传后点击导入 | 创建 file_import run | 文件不属于租户 403 | 浏览器显示导入进度 |
| AT-073 | webhook payload 接收 | `POST /api/v1/webhooks/{source_key}` | 外部推送 | payload 写 raw_records | 签名错、schema 错、重复 request_id | 100 rps p95 < 300ms |
| AT-074 | manual record 创建 | `POST /api/v1/manual-records` | 人工录入 | 保存 raw manual record | 必填缺失 422 | 审计可查 |
| AT-075 | db_import 表扫描 | activity `scan_db_import_table` | 后台采集 | 按 cursor 增量读取行 | 连接失败/权限不足 | 10 万行 < 10min |
| AT-076 | object_storage 文件扫描 | activity `scan_object_storage_prefix` | 后台采集 | 新文件创建 raw record | 权限不足/文件消失 | 1 万 key < 5min |
| AT-077 | 采集限流 | rate limit service | 后台采集 | 按 source policy 限速 | 超限进入 delayed | 限流统计可查 |
| AT-078 | 采集重试退避 | retry policy service | 后台采集 | transient error 指数退避 | permanent error 不重试 | 重试次数落库 |
| AT-079 | 采集死信队列 | dead letter service | run 失败处理 | 失败 payload 进入 dead_letters | 重复 dead letter 幂等 | 死信查询 p95 < 500ms |
| AT-080 | 死信重放 | `POST /api/v1/dead-letters/{id}/replay` | 失败记录重放 | 新 run 从失败点继续 | source 版本不兼容返回 409 | 不重复写成功记录 |
| AT-081 | 原始记录落库 | raw record repository | 后台采集 | 保存 source/run/hash/raw_uri/metadata | 缺 source/run 拒绝写 | 100 万记录批写可测 |
| AT-082 | 原始记录幂等去重 | raw hash service | 后台采集 | 相同 source+external_id/hash 只写一次 | hash 冲突记录 conflict | 去重命中率统计 |
| AT-083 | 采集 cursor 保存 | cursor service | 后台采集 | 成功后更新 cursor | run 失败不推进 cursor | 断点续跑测试通过 |
| AT-084 | 采集 run 指标统计 | collection metrics service | run 详情 | 统计 fetched/parsed/failed/deduped | 指标与 DB 不一致测试失败 | p95 < 500ms |

## 6. P2 解析、清洗、LLM 抽取、质量评分

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-085 | HTML 正文解析 | parser `parse_html_main_content` | 后台解析 | 提取 title/body/published_at | 空正文标 parse_failed | 单文档 < 500ms |
| AT-086 | JSON 字段映射解析 | parser `parse_json_by_mapping` | 字段映射配置预览 | 按 mapping 提取字段 | 缺字段返回 mapping_error | 1 万 JSON < 60s |
| AT-087 | CSV 解析 | parser `parse_csv_file` | 上传 CSV 导入 | 行转 normalized draft | 编码错误/列缺失失败 | 10 万行 < 2min |
| AT-088 | XLSX 解析 | parser `parse_xlsx_file` | 上传 XLSX 导入 | 指定 sheet/range 解析 | 合并单元格/公式错误提示 | 5 万行 < 3min |
| AT-089 | PDF 文本解析 | parser `parse_pdf_text` | 上传 PDF 导入 | 提取页码和文本 | 扫描件无 OCR 标记 | 100 页 < 2min |
| AT-090 | DOCX 文本解析 | parser `parse_docx_text` | 上传 DOCX 导入 | 提取段落和表格文本 | 加密文件失败 | 100 页 < 60s |
| AT-091 | RSS item 解析 | parser `parse_rss_item` | 后台解析 | title/link/summary/time 提取 | 缺 guid 用 link hash | 单 item < 50ms |
| AT-092 | 手工记录 schema 校验 | validator `validate_manual_record` | 人工录入提交 | 合法记录进入 clean draft | 缺 title/time/location 422 | 浏览器错误定位字段 |
| AT-093 | 文本标准化清洗 | cleaner `normalize_text` | 后台清洗 | 去 HTML、空白、控制字符 | 空文本标 invalid | 10 万条 < 5min |
| AT-094 | 时间标准化清洗 | cleaner `normalize_datetime` | 后台清洗 | 多格式转 UTC+原始时区 | 无法解析进入 review | 单条 < 10ms |
| AT-095 | 地点标准化清洗 | cleaner `normalize_location` | 后台清洗 | 提取 city/district/address | 多义地点进入候选 | 1 万条 < 60s |
| AT-096 | 来源可信度赋值 | cleaner `assign_source_trust` | 后台清洗 | 按 source trust 赋分 | 缺 trust 配置使用默认并告警 | 批处理 < 60s |
| AT-097 | 敏感信息检测 | detector `detect_sensitive_fields` | 数据详情脱敏 | 手机/身份证/邮箱标记 | 检测失败不泄露原文 | 单条 < 100ms |
| AT-098 | 敏感信息脱敏 | cleaner `redact_sensitive_fields` | 页面展示/导出 | 默认展示脱敏文本 | 无权限看原文 403 | 浏览器核验脱敏 |
| AT-099 | 规则去重 | dedupe `dedupe_by_hash_and_external_id` | 后台清洗 | 重复记录关联 duplicate_of | 跨源相似不误合并 | 10 万条 < 5min |
| AT-100 | 语义相似去重 | algorithm `semantic_dedupe_records` | 后台清洗 | 相似文本形成候选组 | embedding 失败标 partial | 1 万条 < 10min |
| AT-101 | 去重候选人工确认 | `POST /api/v1/clean-records/{id}/dedupe-decision` | 清洗工作台确认/拆分 | 合并后血缘保留 | 已确认重复提交 409 | 浏览器刷新状态保留 |
| AT-102 | LLM 字段映射建议 | `POST /api/v1/llm/schema-mapping/suggest` | 字段映射页点“建议映射” | 返回 source_field -> target_field + confidence | LLM 失败可手动配置 | 单次 < 30s |
| AT-103 | LLM 事件类型分类 | algorithm `llm_classify_event_type` | 后台抽取 | 输出 event_type/confidence/reason | schema invalid 进入 repair | 100 条 < 5min |
| AT-104 | LLM 实体抽取 | algorithm `llm_extract_entities` | 后台抽取 | 输出 people/org/location/time | 无证据实体进入 low_confidence | 单条 < 20s |
| AT-105 | LLM 事件要素抽取 | algorithm `llm_extract_event_facts` | 后台抽取 | 输出 who/what/when/where/impact | 缺证据字段进入 blocked_claims | 单条 < 25s |
| AT-106 | LLM 证据摘要生成 | algorithm `llm_summarize_evidence_candidate` | 后台抽取/证据页 | 摘要带 source spans | 生成无 span 的句子被阻断 | 单条 < 20s |
| AT-107 | LLM 输出 JSON 修复 | service `repair_llm_json_output` | 后台调用 | 非法 JSON 可修复一次 | 修复仍失败标 failed | 修复率统计 |
| AT-108 | LLM 输出 schema 校验 | service `validate_llm_schema` | 后台调用 | 合法 schema 才落结果 | 缺字段/多字段按策略失败 | 单测覆盖全部 schema |
| AT-109 | LLM 证据边界校验 | guardrail `verify_claim_evidence_refs` | 后台调用 | 每个 claim 有 evidence_ref | 无证据 claim 进入 blocked_claims | 安全测试通过 |
| AT-110 | 清洗记录列表查询 | `GET /api/v1/clean-records` | 清洗工作台列表 | 按状态/源/时间筛选 | 越权 403 | 100 万记录 p95 < 1200ms |
| AT-111 | 清洗记录详情查询 | `GET /api/v1/clean-records/{id}` | 清洗详情 | 显示 raw/clean/extraction/lineage | 敏感原文按权限脱敏 | 浏览器详情验收 |
| AT-112 | 清洗记录状态标记 | `PATCH /api/v1/clean-records/{id}/status` | 标记有效/无效/待复核 | 状态影响后续信号生成 | 已进入报告的记录不可删除 | 审计可查 |
| AT-113 | 数据质量评分 | algorithm `score_clean_record_quality` | 清洗工作台质量列 | 输出 completeness/freshness/trust/overall | 缺必要字段分数降低 | 10 万条 < 5min |
| AT-114 | 数据质量问题列表 | `GET /api/v1/data-quality/issues` | 质量中心 | 返回缺字段、低可信、解析失败 | 权限不足 403 | p95 < 1000ms |
| AT-115 | 清洗 run 指标统计 | `GET /api/v1/cleaning-runs/{id}/metrics` | run 详情 | parsed/cleaned/extracted/failed 统计一致 | 指标缺失测试失败 | p95 < 500ms |

## 7. P3 City 冻结页、非校园样本、主题态势

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-116 | 城市列表查询 | `GET /api/v1/cities` | 城市切换器 | 返回授权城市 | 非授权城市不可见 | p95 < 300ms |
| AT-117 | 城市上下文切换 | `POST /api/v1/session/city` | 切换城市 | session city 更新 | 非授权城市 403 | 浏览器 URL/context 一致 |
| AT-118 | City KPI 聚合 | `GET /api/v1/cities/{city_id}/overview` | city 页顶部指标 | 指标来自 clean/signals/events 聚合 | 无数据返回空态非假数 | p95 < 1000ms |
| AT-119 | City 事件地图点查询 | `GET /api/v1/cities/{city_id}/map-events` | 地图点位 | 返回经纬度/类型/风险 | 无坐标事件不返回地图点 | 5000 点 p95 < 1200ms |
| AT-120 | City 图层开关数据 | `GET /api/v1/cities/{city_id}/layers` | 地图图层开关 | 风险/热度/来源图层可开关 | 不支持图层返回 422 | 浏览器开关不前端造数 |
| AT-121 | City 事件列表查询 | `GET /api/v1/cities/{city_id}/events` | 右侧事件列表 | 后端排序分页 | 前端排序参数非法 422 | 1 万事件 p95 < 1000ms |
| AT-122 | City 事件详情 | `GET /api/v1/events/{id}` | 点击地图点/列表 | 返回事件、信号、证据摘要 | 跨城市事件 403 | 浏览器双入口一致 |
| AT-123 | City 冻结快照创建 | `POST /api/v1/cities/{city_id}/snapshots` | 点击冻结当前页 | 保存 overview/map/list/filter 快照 | 空城市可冻结但标 no_data | 快照创建 < 3s |
| AT-124 | City 冻结快照查看 | `GET /api/v1/city-snapshots/{id}` | 打开冻结页 | 返回冻结时的数据版本 | 快照不存在 404 | 浏览器刷新不变化 |
| AT-125 | City 冻结快照对比 | `GET /api/v1/city-snapshots/{a}/diff/{b}` | 对比两个快照 | 返回 KPI/事件变化 | 不同城市快照 422 | p95 < 1500ms |
| AT-126 | 非校园样本数据源创建 | `POST /api/v1/sample-domains/non-campus` | 配置非校园样本 | 创建市场/民生/交通等样本域 | 重复样本域 409 | 审计可查 |
| AT-127 | 非校园样本导入 run | `POST /api/v1/sample-domains/{id}/import-runs` | 点击导入样本 | 数据走真实采集/清洗链路 | 样本文件缺 schema 失败 | 浏览器看到 run 状态 |
| AT-128 | 非校园样本事件验证 | `GET /api/v1/sample-domains/{id}/validation` | 样本验收页 | 至少生成事件、信号、证据 | 无信号返回失败原因 | 验收 < 60s |
| AT-129 | 主题列表查询 | `GET /api/v1/topics` | 主题页列表 | 按 city/status/type 分页 | 非授权主题不可见 | p95 < 800ms |
| AT-130 | 创建主题 | `POST /api/v1/topics` | 新建主题 | 保存名称、范围、关键词、城市 | 重名/空关键词 422/409 | 浏览器创建后进入详情 |
| AT-131 | 编辑主题范围 | `PATCH /api/v1/topics/{id}/scope` | 主题设置 | 范围变化触发重算标记 | 已归档主题不可改 | 审计可查 |
| AT-132 | 主题概览指标 | `GET /api/v1/topics/{id}/overview` | 主题详情顶部 | 返回信号数、风险、趋势 | 无数据返回 empty | p95 < 1000ms |
| AT-133 | 主题趋势曲线 | `GET /api/v1/topics/{id}/trend` | 趋势图 | 后端按时间桶聚合 | 非法 bucket 422 | 1 年日桶 p95 < 1200ms |
| AT-134 | 主题事件候选 | `GET /api/v1/topics/{id}/event-candidates` | 候选事件列表 | 返回聚类候选和置信度 | 算法未运行返回 pending | p95 < 1200ms |
| AT-135 | 关注主题 | `POST /api/v1/topics/{id}/watch` | 点击关注 | 创建 watch 记录 | 重复关注幂等 | 刷新后状态保留 |
| AT-136 | 取消关注主题 | `DELETE /api/v1/topics/{id}/watch` | 点击取消关注 | 删除 watch 记录 | 未关注幂等 | 浏览器状态更新 |

## 8. P4 信号、证据、风险因子、算法能力

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-137 | 信号候选生成 | algorithm `generate_signal_candidates` | 后台从 clean records 生成 | clean records 聚合成 signal candidates | 无有效记录不生成 | 10 万记录 < 10min |
| AT-138 | 信号置信度评分 | algorithm `score_signal_confidence` | 后台评分 | 输出 confidence/trust/novelty | 缺 source trust 降权 | 批处理 < 5min |
| AT-139 | 信号列表查询 | `GET /api/v1/signals` | 信号检索页 | 支持关键词/城市/主题/时间筛选 | 非法时间范围 422 | 100 万信号 p95 < 1500ms |
| AT-140 | 信号详情查询 | `GET /api/v1/signals/{id}` | 点击信号 | 返回来源、证据候选、评分解释 | 跨租户 403 | p95 < 800ms |
| AT-141 | 信号加入草稿区 | `POST /api/v1/signal-drafts/{draft_id}/items` | 点击加入草稿 | draft item 落库 | 重复加入幂等 | 浏览器刷新保留 |
| AT-142 | 信号移出草稿区 | `DELETE /api/v1/signal-drafts/{draft_id}/items/{signal_id}` | 点击移除 | draft item 删除 | 不存在幂等 | 审计可查 |
| AT-143 | 信号状态标记 | `PATCH /api/v1/signals/{id}/status` | 标记有效/噪声/待复核 | 状态影响证据生成 | 已用于报告需说明原因 | 审计包含 reason |
| AT-144 | 证据候选生成 | algorithm `generate_evidence_candidates` | 后台/按钮触发 | 从 signal 和 clean record 生成 evidence | 无 source span 不生成 | 10 万信号 < 10min |
| AT-145 | 证据列表查询 | `GET /api/v1/evidence` | 证据复核页列表 | 按 status/source/type 筛选 | 越权 403 | p95 < 1200ms |
| AT-146 | 证据详情查询 | `GET /api/v1/evidence/{id}` | 证据详情 | 显示原文 span、摘要、血缘 | 敏感原文脱敏 | 浏览器引用可点击 |
| AT-147 | 证据确认 | `POST /api/v1/evidence/{id}/confirm` | 点击确认 | status -> confirmed | 无 source span 409 | 审计可查 |
| AT-148 | 证据驳回 | `POST /api/v1/evidence/{id}/reject` | 点击驳回并填原因 | status -> rejected | 缺原因 422 | 浏览器状态更新 |
| AT-149 | 证据补充附件 | `POST /api/v1/evidence/{id}/attachments` | 上传附件 | 附件绑定 evidence | 文件越权/超大小失败 | 上传后列表出现 |
| AT-150 | 证据血缘图查询 | `GET /api/v1/evidence/{id}/lineage` | 点击追溯 | raw/clean/signal/evidence 图返回 | 血缘断裂标 warning | p95 < 1000ms |
| AT-151 | 风险因子规则生成 | algorithm `generate_risk_factors_rule_based` | 后台生成 | 根据 confirmed evidence 生成 factor | 无 confirmed evidence 不生成 | 1 万证据 < 5min |
| AT-152 | 风险因子 LLM 生成 | algorithm `llm_generate_risk_factors` | 点击智能生成 | 输出 factor + evidence_refs + uncertainty | 无证据 claim blocked | 单主题 < 60s |
| AT-153 | 风险因子评分 | algorithm `score_risk_factors` | 后台评分 | 输出 severity/probability/impact | 缺参数版本失败 | 批处理 < 5min |
| AT-154 | 风险因子列表查询 | `GET /api/v1/risk-factors` | 风险因子列表 | 按主题/事件/状态筛选 | 越权 403 | p95 < 1000ms |
| AT-155 | 风险因子详情查询 | `GET /api/v1/risk-factors/{id}` | 因子详情 | 展示评分解释和证据 | evidence_refs 缺失标异常 | p95 < 800ms |
| AT-156 | 风险因子确认 | `POST /api/v1/risk-factors/{id}/confirm` | 点击确认 | confirmed factor 可进主线 | low confidence 需二次确认 | 审计可查 |
| AT-157 | 风险因子驳回 | `POST /api/v1/risk-factors/{id}/reject` | 点击驳回 | rejected 不进入主线 | 缺原因 422 | 浏览器状态保留 |
| AT-158 | 事件聚类算法运行 | algorithm `cluster_events` | 后台/主题候选 | 输出 cluster_id 和代表事件 | 样本不足返回 insufficient_data | 10 万事件 < 10min |
| AT-159 | 异常趋势检测 | algorithm `detect_trend_anomaly` | 趋势图标记异常 | 输出 anomaly window/score | 数据稀疏标 low_confidence | 1 年数据 < 2min |
| AT-160 | 热点排序算法 | algorithm `rank_hotspots` | city/topic 榜单 | 后端返回排序结果 | 参数版本缺失失败 | 1 万项 p95 < 1200ms |

## 9. P5 主线建模、World State、世界线推演

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-161 | 创建主线草稿 | `POST /api/v1/mainlines` | 从主题/事件创建主线 | mainline draft 落库 | 无信号/无证据 409 | 浏览器跳转主线页 |
| AT-162 | 主线列表查询 | `GET /api/v1/mainlines` | 主线列表 | 按 city/topic/status 筛选 | 跨租户 403 | p95 < 1000ms |
| AT-163 | 主线详情查询 | `GET /api/v1/mainlines/{id}` | 主线详情 | 返回节点、边、证据、质量 | 不存在 404 | p95 < 1200ms |
| AT-164 | 主线节点自动生成 | algorithm `generate_mainline_nodes` | 点击生成节点 | 从 confirmed evidence/factors 生成节点 | 因子不足返回 insufficient_data | 单主线 < 60s |
| AT-165 | 主线边自动生成 | algorithm `generate_mainline_edges` | 点击生成关系 | 输出因果/时间/影响关系 | 循环关系标 warning | 单主线 < 60s |
| AT-166 | 主线图谱布局保存 | `PUT /api/v1/mainlines/{id}/layout` | 拖拽节点保存 | 坐标落库 | 非 owner 403 | 刷新后布局保留 |
| AT-167 | 主线节点人工编辑 | `PATCH /api/v1/mainline-nodes/{id}` | 编辑节点标题/说明 | 修改后版本递增 | confirmed 主线需开新版本 | 审计可查 |
| AT-168 | 主线边人工编辑 | `PATCH /api/v1/mainline-edges/{id}` | 修改关系类型 | 边更新并校验节点存在 | 非法关系类型 422 | 浏览器图谱更新 |
| AT-169 | 主线质量评分 | algorithm `score_mainline_quality` | 质量提示 | 输出 coverage/consistency/evidence_score | 证据冲突降分 | 单主线 < 10s |
| AT-170 | 主线确认冻结 | `POST /api/v1/mainlines/{id}/confirm` | 点击确认主线 | draft -> confirmed | 质量低/无 confirmed evidence 409 | 确认后不可直接改 |
| AT-171 | World State 创建 | `POST /api/v1/world-states` | 从主线生成状态 | 保存 state variables/entities/tensions | 主线未确认 409 | 浏览器进入 World State |
| AT-172 | World State 详情 | `GET /api/v1/world-states/{id}` | 查看状态 | 返回变量、证据、版本 | 跨租户 403 | p95 < 1000ms |
| AT-173 | World State 变量编辑 | `PATCH /api/v1/world-state-variables/{id}` | 调整变量 | 新版本记录 from/to | 已用于推演需新 state version | 审计可查 |
| AT-174 | 世界线参数模板查询 | `GET /api/v1/worldline/parameter-templates` | 推演配置页 | 返回可调参数和范围 | 无模板返回配置错误 | p95 < 300ms |
| AT-175 | 创建世界线推演 run | `POST /api/v1/worldline-runs` | 点击运行推演 | 创建 run pending | world state 未确认 409 | 浏览器显示 running |
| AT-176 | 世界线模拟算法运行 | algorithm `simulate_worldline` | 后台推演 | 输出多个 scenario/timeline/probability | 参数越界失败 | 单 run < 5min |
| AT-177 | 世界线 run 状态查询 | `GET /api/v1/worldline-runs/{id}` | 推演状态轮询 | pending/running/succeeded/failed 正确 | 不存在 404 | p95 < 500ms |
| AT-178 | 世界线结果查询 | `GET /api/v1/worldline-runs/{id}/results` | 推演结果页 | 返回 timeline、分支、风险变化 | running 时不返回假结果 | p95 < 1500ms |
| AT-179 | 干预动作注入 | `POST /api/v1/worldline-runs/{id}/interventions` | 添加干预动作 | 新 intervention version | run 已归档不可注入 | 审计可查 |
| AT-180 | 干预后重算 | `POST /api/v1/worldline-runs/{id}/rerun` | 点击重新推演 | 新 run 继承旧参数+干预 | 上一 run 未完成 409 | 历史 run 可查看 |
| AT-181 | 世界线版本对比 | `GET /api/v1/worldline-runs/compare` | 选择两个版本对比 | 返回概率/路径/风险 diff | 不同 world state 422 | p95 < 2000ms |
| AT-182 | 世界线解释生成 | algorithm `explain_worldline_result` | 结果解释区域 | 解释带 evidence_refs 和 uncertainty | 无证据结论 blocked | 单 run < 60s |
| AT-183 | 世界线标记进入 Council | `POST /api/v1/worldline-runs/{id}/send-to-council` | 点击送研判 | 创建 council input snapshot | failed run 不可送 | Council 页出现入口 |

## 10. P6 LLM Provider、Agent Runtime、Council

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-184 | LLM provider 配置读取 | `GET /api/v1/llm/providers/status` | 系统状态/Council 前置检查 | 返回 provider/model/available | 未配置显示不可运行 | p95 < 300ms |
| AT-185 | LLM provider 健康检查 | service `check_llm_provider_health` | 点击检测 | 真实调用轻量请求成功 | timeout/401/429 分类 | 单 provider < 10s |
| AT-186 | LLM 调用预算校验 | service `check_llm_budget` | 运行前检查 | 未超预算允许调用 | 超预算阻断并提示 | 成本记录可查 |
| AT-187 | LLM 调用封装 | service `invoke_llm` | 后台调用 | 记录 request/response/tokens/status | timeout/429/5xx 重试策略 | 单调用可追踪 |
| AT-188 | Prompt 模板查询 | `GET /api/v1/prompts` | 配置中心 | 返回 published prompts | 未发布 prompt 不可用 | p95 < 300ms |
| AT-189 | Prompt 渲染 | service `render_prompt` | 后台调用 | 使用输入快照渲染 prompt_hash | 缺变量失败 | 单测覆盖变量 |
| AT-190 | Agent profile 列表 | `GET /api/v1/agent-profiles` | Council 配置 | 返回角色、约束、工具权限 | 未发布 profile 不返回生产 | p95 < 500ms |
| AT-191 | 创建 Agent session | `POST /api/v1/agent-sessions` | 点击创建研判 | 保存 input snapshot/worldline/mainline | 缺输入 422 | 浏览器进入 session |
| AT-192 | Agent context pack 构建 | service `build_agent_context_pack` | 后台准备 | 检索 evidence/mainline/worldline/cases | token 超限触发压缩 | 单 session < 30s |
| AT-193 | 单 Agent 运行 | activity `run_single_agent` | 后台执行 | 输出 stance/reaction/risk_delta/uncertainty | LLM 失败记录 failed output | 单 agent < 90s |
| AT-194 | 多 Agent 并行调度 | workflow `run_agent_council` | 点击运行 Council | 多角色并行运行并汇总 | 部分 agent 失败不吞错 | session < 180s |
| AT-195 | Agent 输出 schema 校验 | service `validate_agent_output_schema` | 后台执行 | 合法 JSON 落库 | 非法 schema 进入 repair/failed | 单测全覆盖 |
| AT-196 | Agent 输出证据校验 | guardrail `validate_agent_evidence_boundary` | 后台执行 | 所有事实有 evidence_refs | 无证据事实 blocked | 安全测试通过 |
| AT-197 | Council 汇总结论生成 | algorithm `aggregate_council_outputs` | Council 结果页 | 汇总共识/分歧/建议 | 全部 agent 失败则 session failed | 汇总 < 30s |
| AT-198 | Council session 状态查询 | `GET /api/v1/agent-sessions/{id}` | 轮询状态 | 返回状态、进度、失败 agent | 不存在 404 | p95 < 500ms |
| AT-199 | Council 输出查询 | `GET /api/v1/agent-sessions/{id}/outputs` | 展示多 Agent 卡片 | 每个 agent 输出可查看 | 无权限 403 | 浏览器不显示假结果 |
| AT-200 | Agent 建议应用到世界线 | `POST /api/v1/agent-sessions/{id}/apply-worldline-delta` | 点击应用建议 | 创建 worldline intervention draft | 建议无 delta 返回 409 | 世界线页显示变化 |
| AT-201 | Agent 反事实压测 | `POST /api/v1/agent-sessions/{id}/counterfactual-runs` | 输入假设运行 | 生成独立 counterfactual result | 假设违反政策/为空 422 | 不覆盖原结果 |
| AT-202 | Agent 调用回放 | `GET /api/v1/agent-sessions/{id}/replay` | 调试/审计页 | 返回 input/prompt_hash/output/trace | prompt 原文按权限脱敏 | p95 < 1000ms |
| AT-203 | LLM 调用记录查询 | `GET /api/v1/llm/calls` | LLM 观测页 | 按 provider/model/status 查询 | 非 admin 看脱敏内容 | 10 万调用 p95 < 1200ms |
| AT-204 | LLM 失败重试 | `POST /api/v1/llm/calls/{id}/retry` | 调试重试 | 新调用继承输入快照 | succeeded call 不可重试 | 结果版本可追踪 |
| AT-205 | Agent 回归评测运行 | `POST /api/v1/evaluations/agent-regression-runs` | 配置发布前回归 | 用案例库跑 profile/prompt | 无案例库阻断发布 | 回归报告落库 |

## 11. P7 报告、任务、审批、导出、复盘

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-206 | 创建报告草稿 | `POST /api/v1/reports` | 从主线/Council 创建报告 | draft report 落库 | 缺 mainline/council 422 | 浏览器进入报告编辑 |
| AT-207 | 报告大纲生成 | algorithm `generate_report_outline` | 点击生成大纲 | 章节带 evidence_refs | 无证据章节 blocked | 单报告 < 60s |
| AT-208 | 报告段落生成 | algorithm `generate_report_sections` | 点击生成正文 | 每段有引用和 uncertainty | LLM 超时显示失败段落 | 单报告 < 180s |
| AT-209 | 报告详情查询 | `GET /api/v1/reports/{id}` | 报告页 | 返回章节、引用、状态 | 非授权 403 | p95 < 1000ms |
| AT-210 | 报告段落人工编辑 | `PATCH /api/v1/report-sections/{id}` | 编辑段落 | 保存新版本 | confirmed report 不可改 | 审计可查 |
| AT-211 | 报告引用校验 | `POST /api/v1/reports/{id}/validate-citations` | 点击校验引用 | 返回缺引用/断链列表 | 断链阻断提交审批 | < 30s |
| AT-212 | 提交报告审批 | `POST /api/v1/reports/{id}/submit` | 点击提交 | draft -> submitted，创建审批任务 | 引用校验失败 409 | 浏览器按钮状态变化 |
| AT-213 | 审批任务列表 | `GET /api/v1/approval-tasks` | 待办页 | reviewer 看到待审批报告 | 非 reviewer 403 | p95 < 800ms |
| AT-214 | 审批通过报告 | `POST /api/v1/reports/{id}/approve` | 审批通过 | submitted -> approved | 非 reviewer 403 | 审计可查 |
| AT-215 | 审批退回报告 | `POST /api/v1/reports/{id}/reject` | 审批退回填原因 | submitted -> rejected | 缺原因 422 | 报告页显示退回原因 |
| AT-216 | 报告确认成正式结论 | `POST /api/v1/reports/{id}/confirm` | 点击确认 | approved -> confirmed，formal_conclusion 生成 | 未审批 409 | 正式结论可查 |
| AT-217 | 导出 PDF | `POST /api/v1/reports/{id}/exports` format=pdf | 点击导出 PDF | 创建 export run，生成文件 | 报告未确认按权限限制 | PDF < 60s |
| AT-218 | 导出 DOCX | `POST /api/v1/reports/{id}/exports` format=docx | 点击导出 DOCX | 生成 docx 文件对象 | 导出模板缺失失败 | DOCX 内容一致 |
| AT-219 | 导出任务状态查询 | `GET /api/v1/export-runs/{id}` | 导出进度 | 返回 running/succeeded/failed | 不存在 404 | 浏览器下载按钮出现 |
| AT-220 | 创建业务任务 | `POST /api/v1/tasks` | 从报告/事件创建任务 | task 绑定 source_object | 缺负责人 422 | 审计可查 |
| AT-221 | 任务列表查询 | `GET /api/v1/tasks` | 任务中心 | 按负责人/状态/来源筛选 | 越权 403 | p95 < 800ms |
| AT-222 | 更新任务状态 | `PATCH /api/v1/tasks/{id}/status` | 任务看板拖拽/按钮 | todo->doing->done | 非法状态流转 409 | 浏览器刷新保留 |
| AT-223 | 任务评论 | `POST /api/v1/tasks/{id}/comments` | 添加评论 | 评论落库并通知相关人 | 空评论 422 | p95 < 300ms |
| AT-224 | 创建复盘记录 | `POST /api/v1/reviews` | 报告页创建复盘 | review 绑定 report/worldline | 报告未确认 409 | 浏览器进入复盘页 |
| AT-225 | 复盘指标填写 | `PATCH /api/v1/reviews/{id}/metrics` | 填写实际结果 | 保存 outcome metrics | 缺关键指标 422 | 审计可查 |
| AT-226 | 复盘结论提交 | `POST /api/v1/reviews/{id}/submit` | 提交复盘 | 生成 lessons learned | 未填指标 409 | 进入案例候选 |

## 12. P8 案例库、配置中心、发布回滚

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-227 | 案例候选生成 | algorithm `generate_case_candidate` | 复盘后生成候选 | 从 confirmed report/review 生成 | 缺复盘不生成 | < 60s |
| AT-228 | 案例详情查询 | `GET /api/v1/cases/{id}` | 案例详情 | 返回背景、主线、决策、结果 | 未发布案例无权限 403 | p95 < 1000ms |
| AT-229 | 案例审批发布 | `POST /api/v1/cases/{id}/publish` | 发布案例 | draft -> published | 无复盘指标 409 | 审计可查 |
| AT-230 | 案例语义检索 | `GET /api/v1/cases/search` | 案例库搜索 | 返回相似案例和证据 | embedding 索引缺失提示重建 | p95 < 1500ms |
| AT-231 | 案例召回给 Agent | service `retrieve_cases_for_agent` | Council context | 返回 top_k cases | 无案例返回 empty 非假数 | < 5s |
| AT-232 | taxonomy 列表查询 | `GET /api/v1/config/taxonomies` | 配置中心 | 返回事件类型/风险标签 | 非 admin 403 | p95 < 500ms |
| AT-233 | taxonomy 草稿编辑 | `POST /api/v1/config/taxonomies/versions` | 编辑分类 | 创建 draft version | 重复 code 409 | 审计可查 |
| AT-234 | taxonomy 发布 | `POST /api/v1/config/taxonomies/versions/{id}/publish` | 点击发布 | 新任务使用新版本 | 回归失败禁止发布 | 浏览器版本显示 |
| AT-235 | 算法参数查询 | `GET /api/v1/config/algorithm-params` | 算法配置页 | 返回 published params | 越权 403 | p95 < 500ms |
| AT-236 | 算法参数草稿保存 | `POST /api/v1/config/algorithm-params/versions` | 编辑阈值 | 保存 draft | 参数越界 422 | 审计可查 |
| AT-237 | 算法参数回归测试 | `POST /api/v1/evaluations/algorithm-runs` | 点击回归 | 输出指标对比 | 无测试集 409 | 报告 < 10min |
| AT-238 | 算法参数发布 | `POST /api/v1/config/algorithm-params/versions/{id}/publish` | 发布参数 | published 后新 run 使用 | 回归失败禁止发布 | 版本写入 algorithm_runs |
| AT-239 | Agent profile 草稿保存 | `POST /api/v1/config/agent-profiles/versions` | 编辑 Agent 角色 | 保存角色/约束/schema | 缺 schema 422 | 审计可查 |
| AT-240 | Agent profile 发布 | `POST /api/v1/config/agent-profiles/versions/{id}/publish` | 发布 Agent | 新 Council 使用新 profile | 回归失败禁止发布 | session 记录版本 |
| AT-241 | Prompt 草稿保存 | `POST /api/v1/config/prompts/versions` | 编辑 prompt | 保存 template/variables | 缺变量声明 422 | 审计可查 |
| AT-242 | Prompt 发布 | `POST /api/v1/config/prompts/versions/{id}/publish` | 发布 prompt | 新 LLM 调用使用版本 | 回归失败禁止发布 | llm_calls 记录版本 |
| AT-243 | 配置版本回滚 | `POST /api/v1/config/versions/{id}/rollback` | 点击回滚 | 创建 rollback version | 当前有关键 run 需确认 | 审计 from/to |
| AT-244 | 配置变更影响分析 | `GET /api/v1/config/versions/{id}/impact` | 发布前查看影响 | 返回受影响任务/算法/Agent | 版本不存在 404 | p95 < 1200ms |

## 13. 全链路、性能、安全、浏览器验收任务

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-245 | 登录到 City 全链路浏览器测试 | Playwright/browser QA | 登录后进入 city | city KPI/map/list 均来自 API | token 过期回登录 | 桌面/移动各跑一遍 |
| AT-246 | public_web 采集到证据全链路 | E2E workflow test | 创建源->采集->清洗->信号->证据 | 每步 DB 状态正确 | 抓取失败进入 dead letter | 全链路 < 15min |
| AT-247 | file_upload 采集到证据全链路 | E2E workflow test | 上传文件并导入 | 文件解析、清洗、抽取成功 | 错 schema 文件失败可见 | 浏览器验证进度 |
| AT-248 | 非校园样本全链路 | E2E workflow test | 导入非校园样本 | 生成事件/风险因子/报告 | 样本数据不足给失败原因 | < 20min |
| AT-249 | 主题到主线全链路 | E2E workflow test | 创建主题->候选->主线 | 主线节点/边/质量生成 | 证据不足阻断确认 | 浏览器验收 |
| AT-250 | 主线到世界线全链路 | E2E workflow test | 主线确认->World State->推演 | 推演结果落库 | running 不显示假结果 | < 10min |
| AT-251 | 世界线到 Council 全链路 | E2E workflow test | 送 Council->多 Agent->汇总 | 每个 agent output 有版本/证据 | LLM 部分失败可见 | session < 180s |
| AT-252 | Council 到报告全链路 | E2E workflow test | 生成报告->审批->确认 | 正式结论生成 | 引用断链阻断提交 | 浏览器验收 |
| AT-253 | 报告导出全链路 | E2E workflow test | confirmed report 导出 PDF/DOCX | 文件可下载且内容一致 | 模板缺失失败可见 | PDF/DOCX < 60s |
| AT-254 | 案例沉淀全链路 | E2E workflow test | 复盘->案例候选->发布->召回 | Agent 可召回案例 | 未审批案例不可召回 | 浏览器验收 |
| AT-255 | 权限越权测试 | security test suite | 多角色访问页面/API | 授权操作成功 | 跨租户/越权全部 403 | CI 必跑 |
| AT-256 | 敏感信息脱敏测试 | security test suite | 详情页/导出/LLM context | 无权限只见脱敏 | LLM context 不含未授权原文 | 安全测试通过 |
| AT-257 | LLM 异常矩阵测试 | LLM QA suite | 触发 Council/抽取/报告 | timeout/429/schema invalid 均可恢复或失败可见 | 不产生假结果 | 报告异常率 |
| AT-258 | 数据库性能基准 | performance suite | 页面/API 压测 | 核心查询达 p95 目标 | 慢查询失败构建 | 生成性能报告 |
| AT-259 | workflow 并发性能基准 | performance suite | 并发采集/清洗/推演 | 不丢 run、不乱状态 | worker 重启可恢复 | 50 并发 run 验收 |
| AT-260 | 前端首屏性能测试 | browser performance | city/topic/report 页面 | 首屏和交互延迟达标 | API 慢时显示 loading/error | Lighthouse/trace 归档 |
| AT-261 | 审计覆盖率测试 | audit test suite | 执行所有 mutation | mutation 均有 audit_logs | 漏审计测试失败 | 覆盖率 100% |
| AT-262 | 血缘完整性测试 | lineage test suite | 从报告反查 raw | 每条结论可追溯 | 断链标失败 | 4 跳查询达标 |
| AT-263 | 配置发布回滚回归 | regression suite | 发布/回滚 taxonomy/算法/Agent/prompt | 新任务用新版本 | 旧 run 结果不被覆盖 | 浏览器验证版本 |
| AT-264 | 发布前 DCP 验收报告 | release service/checklist | 发布看板 | 汇总测试、性能、安全、风险 | 任一 P0 失败禁止发布 | 自动生成验收记录 |

## 14. Agent 派工规则

每个任务只能派给一个主责开发 agent；需要协作时增加协作 agent，但主责不变。

| Agent | 主责任务范围 |
| --- | --- |
| Backend-Agent-Platform | AT-001 至 AT-031 |
| Backend-Agent-DataSource | AT-032 至 AT-053 |
| Backend-Agent-Ingestion | AT-054 至 AT-084 |
| Backend-Agent-Cleaning-LLM | AT-085 至 AT-115 |
| Backend-Agent-CityTopic | AT-116 至 AT-136 |
| Backend-Agent-SignalEvidence | AT-137 至 AT-160 |
| Algorithm-Agent-MainlineWorldline | AT-161 至 AT-183 |
| LLM-Agent-Council | AT-184 至 AT-205 |
| Backend-Agent-ReportCaseConfig | AT-206 至 AT-244 |
| Frontend-Agent-Core | AT-016 至 AT-031 的页面接入 |
| Frontend-Agent-Data | AT-032 至 AT-115 的页面接入 |
| Frontend-Agent-Analysis | AT-116 至 AT-183 的页面接入 |
| Frontend-Agent-CouncilReport | AT-184 至 AT-244 的页面接入 |
| QA-Agent-Functional | 每个 AT 的正常测试 |
| QA-Agent-Abnormal | 每个 AT 的异常测试 |
| QA-Agent-Performance | 每个 AT 的性能测试和基准 |
| Browser-QA-Agent | 所有带前端场景的 AT 内部浏览器验收 |
| Security-QA-Agent | AT-184 至 AT-205、AT-255、AT-256 |
| Release-Agent | AT-257 至 AT-264 |

## 15. 单任务完成定义

每个 AT 只有同时满足以下条件才算完成：

- API 或 service 已实现，不是 stub。
- 数据写入 PostgreSQL 或对象存储引用，能从数据库反查。
- 涉及 workflow 的任务有 run 状态、step 状态、失败原因和重试策略。
- 涉及算法/LLM/Agent 的任务有版本、输入快照、输出快照、schema 校验和失败落库。
- 涉及页面的任务完成 loading、empty、success、error、permission denied 状态。
- 功能测试 Agent 正常路径通过。
- 异常测试 Agent 至少覆盖 401/403/404/409/422/429/500 中适用项。
- 性能测试 Agent 达到本任务阈值，或记录明确性能缺陷。
- Browser-QA-Agent 对所有前端交互做真实点击验收。
- 审计日志、血缘、权限、租户隔离检查通过。
- 第三方检查通过。实现该任务的 agent 不能作为最终验收方；必须由独立 reviewer 或 QA agent 给出结论。
- 第三方检查结论必须落库或记录到验收报告，包含 reviewer、检查项、通过/失败、阻断问题、复测结果。

## 16. 新增原则：产品运行时 Agent 复用、分渠道采集、多媒体闭环

本节补充 2026-05-08 的新增要求，作为 AT-001 至 AT-264 的扩展任务。

本节中的 Agent 指 CollectiveEventTwin 产品内部运行的业务 Agent、数据 Agent、研判 Agent、配置 Agent、质检 Agent，不是 Codex 开发 Agent，也不是开发过程中的测试 Agent。

### 16.1 产品运行时专业 Agent 复用原则

- 常规代码不能因为 Agent 存在而省略：认证、权限、存储、workflow、审计、血缘、安全边界仍然必须是真实代码。
- 可以由产品内专业 Agent 降低维护成本的部分：字段映射建议、采集策略建议、解析规则建议、数据质量诊断、LLM prompt 生成、业务测试用例生成、异常归因、报告表达、研判视角生成、回归结果解释。
- 专业 Agent 必须通过工具和 schema 工作，不允许直接写生产数据库；所有建议先落 draft，经校验、测试、发布后才进入生产版本。
- 每个专业 Agent 都是可复用资产：有 profile、工具权限、输入 schema、输出 schema、guardrail、评测集、版本号和审计。

### 16.2 多 Agent 人设文件结构

借鉴 OpenClaw 与 `agency-agents-zh` 的玩法，但不照搬。我们的运行时 Agent Profile 采用三层核心文件：

| 文件 | 作用 | 必填内容 |
| --- | --- | --- |
| `user.md` | 当前事件中的角色背景 | 角色身份、所在组织/群体、利益诉求、信息来源、当前约束、可接受/不可接受结果 |
| `soul.md` | 立场与处事逻辑 | 价值排序、风险偏好、决策风格、冲突处理方式、证据偏好、认知盲区 |
| `agent.md` | 可执行能力定义 | 工具权限、任务边界、工作流、输出 schema、禁止事项、失败处理 |

可选文件：

| 文件 | 作用 |
| --- | --- |
| `memory.md` | 关联历史案例、长期偏好、曾经判断错误 |
| `tools.md` | 可调用工具清单和参数限制 |
| `eval.md` | 回归评测用例和通过标准 |

多 Agent 研判时，每个产品内 Agent 不是“专家标签”，而是一个带背景、立场、权衡和行为方式的事件参与者或专业观察者。例如监管方、学校方、家长方、平台方、媒体方、商户方、消费者方、应急处置方、数据合规方。

### 16.3 分渠道采集原则

- 不建设一个巨大的通用采集器。所有采集按 channel 单独处理。
- 每个 channel 有独立 adapter、配置 schema、凭据策略、限流策略、解析器、质量指标、异常码、回放策略和测试集。
- channel 之间只共享标准 contract：`discover -> fetch -> parse -> normalize -> extract -> quality -> lineage -> replay`。
- 新增 channel 只新增对应 adapter 和 parser，不改动其他 channel，减少维护成本。

### 16.4 多媒体闭环原则

- 图片、视频、直播、音频不是附件，而是一级数据源。
- 多媒体数据必须进入同一条业务闭环：media raw -> media artifacts -> multimodal clean record -> signal -> evidence -> risk factor -> mainline -> worldline -> council -> report。
- 视频/直播/图片算法优先采用成熟模型或服务封装：OCR、ASR、VLM caption、关键帧、镜头切分、视觉目标检测、场景分类、相似去重、敏感信息打码。
- 默认不做人脸身份识别、个人身份推断、未授权跟踪。只允许做人脸区域检测、打码、人数/密度估计、画面证据抽取。确需身份识别必须单独合规审批和权限隔离。

## 17. 新增原子任务：产品运行时专业 Agent 复用底座

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-265 | 专业 Agent 类型枚举 | `GET /api/v1/professional-agent-types` | Agent 配置页选择类型 | 返回 data_engineer、collector、cleaner、qa、security、analyst、reporter 等类型 | 未配置类型返回空数组并告警 | p95 < 200ms |
| AT-266 | 创建专业 Agent profile draft | `POST /api/v1/professional-agents` | 新建专业 Agent | profile draft 落库 | 重名 409；缺输出 schema 422 | 审计可查 |
| AT-267 | 保存专业 Agent 工具权限 | `PUT /api/v1/professional-agents/{id}/tools` | 配置可调用工具 | 工具白名单落库 | 越权工具被拒绝 | 安全测试通过 |
| AT-268 | 保存专业 Agent 输出 schema | `PUT /api/v1/professional-agents/{id}/output-schema` | 配置结构化输出 | schema 可校验 | 非法 JSON schema 422 | 单测覆盖 schema |
| AT-269 | 运行专业 Agent 生成字段映射建议 | `POST /api/v1/professional-agents/{id}/runs` purpose=schema_mapping | 字段映射页点“Agent 建议” | 返回 draft mapping 和 confidence | LLM 失败、schema invalid 可见 | 单次 < 30s |
| AT-270 | 运行专业 Agent 生成解析规则建议 | `POST /api/v1/professional-agents/{id}/runs` purpose=parse_rule | 数据源配置页生成 parser rule | 返回 parser rule draft | 规则测试失败不允许发布 | dry-run < 60s |
| AT-271 | 运行专业 Agent 诊断采集失败 | `POST /api/v1/professional-agents/{id}/runs` purpose=collection_failure_diagnosis | run 失败页点“诊断” | 返回失败分类、建议动作、证据 | 无 run 权限 403 | p95 < 30s |
| AT-272 | 运行专业 Agent 生成测试用例 | `POST /api/v1/professional-agents/{id}/runs` purpose=test_case_generation | 任务详情生成测试 | 返回正常/异常/性能用例草稿 | 缺需求上下文 422 | 生成 < 60s |
| AT-273 | 专业 Agent 建议草稿落库 | service `persist_agent_suggestion_draft` | 所有 Agent 建议结果 | suggestion draft 可审核 | 无 source run/session 拒绝写入 | p95 < 300ms |
| AT-274 | 专业 Agent 建议审批通过 | `POST /api/v1/agent-suggestions/{id}/approve` | 审批建议 | draft -> approved，可进入配置版本 | 非 reviewer 403 | 审计可查 |
| AT-275 | 专业 Agent 建议驳回 | `POST /api/v1/agent-suggestions/{id}/reject` | 驳回建议 | 记录 reject reason | 缺原因 422 | 审计可查 |
| AT-276 | 专业 Agent profile 发布 | `POST /api/v1/professional-agents/{id}/publish` | 发布 Agent | published 后可被任务调用 | 回归失败禁止发布 | 版本写入 agent_runs |
| AT-277 | 专业 Agent profile 回归评测 | `POST /api/v1/evaluations/professional-agent-runs` | 发布前回归 | 输出准确率、schema 通过率、失败样例 | 无评测集 409 | 报告 < 10min |
| AT-278 | 专业 Agent 运行记录查询 | `GET /api/v1/professional-agent-runs` | Agent 观测页 | 按类型/状态/任务查询 | 跨租户 403 | 10 万 run p95 < 1200ms |

## 18. 新增原子任务：OpenClaw 风格研判 Agent Profile

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-279 | 创建事件研判 Agent Profile | `POST /api/v1/council-agent-profiles` | Council 配置页新建角色 | 创建 profile draft | 重名 409 | 审计可查 |
| AT-280 | 保存 `user.md` | `PUT /api/v1/council-agent-profiles/{id}/user-md` | 编辑角色背景 | 背景、利益、约束落库 | 缺当前事件角色 422 | 浏览器刷新保留 |
| AT-281 | 保存 `soul.md` | `PUT /api/v1/council-agent-profiles/{id}/soul-md` | 编辑立场逻辑 | 价值排序、风险偏好、证据偏好落库 | 空立场 422 | 浏览器刷新保留 |
| AT-282 | 保存 `agent.md` | `PUT /api/v1/council-agent-profiles/{id}/agent-md` | 编辑能力定义 | 工具、流程、输出 schema 落库 | 工具越权 422/403 | 浏览器刷新保留 |
| AT-283 | 渲染 Agent 系统提示词 | service `render_council_agent_prompt` | 后台运行前 | user/soul/agent 合成 prompt_hash | 缺文件拒绝运行 | 单次 < 500ms |
| AT-284 | Agent 立场冲突检测 | service `detect_agent_stance_conflict` | profile 保存时提示 | 检测立场与禁止项冲突 | 冲突 profile 不允许发布 | p95 < 2s |
| AT-285 | 当前事件权衡注入 | service `build_event_tradeoff_context` | 运行 Council | 注入事件利益方、压力、约束、可选动作 | 缺事件上下文 422 | 单 session < 5s |
| AT-286 | Agent 记忆召回 | service `retrieve_agent_memory` | Council context | 根据角色召回历史判断/错误案例 | 无 memory 返回 empty | < 5s |
| AT-287 | Agent 输出立场一致性校验 | guardrail `validate_agent_position_consistency` | 后台校验 | 输出符合其 user/soul/agent 设定 | 自相矛盾进入 warning | 单输出 < 1s |
| AT-288 | Agent 间交叉质询 | workflow activity `run_agent_cross_examination` | Council 页二轮质询 | Agent 对其他观点提出质疑 | 被质询对象失败时记录 partial | session < 180s |
| AT-289 | Agent 让步与权衡生成 | algorithm `generate_agent_tradeoff_delta` | Council 结果页 | 输出各 Agent 可接受让步和底线 | 无 evidence_refs 的让步 blocked | 单 session < 60s |
| AT-290 | Council 决策矩阵生成 | algorithm `generate_council_decision_matrix` | 研判汇总 | 生成选项、支持方、反对方、风险、证据 | 全部 Agent 失败则 failed | p95 < 30s |
| AT-291 | Agent Profile 导入 | `POST /api/v1/council-agent-profiles/import` | 从文件导入 user/soul/agent | 导入为 draft | 文件缺项或 schema 错 422 | 浏览器上传验收 |
| AT-292 | Agent Profile 导出 | `GET /api/v1/council-agent-profiles/{id}/export` | 导出 profile 包 | 导出 md + metadata | 未授权 403 | 文件内容一致 |

## 19. 新增原子任务：按渠道拆分采集

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-293 | Channel 注册表 | `GET /api/v1/collection-channels` | 新建数据源选择 channel | 返回 web_page、official_api、rss、document_file、image_file、video_file、livestream、audio_file、webhook、database、object_storage | 未配置 channel 告警 | p95 < 200ms |
| AT-294 | Channel adapter contract 校验 | service `validate_channel_adapter_contract` | 后台启动 | 每个 adapter 实现 discover/fetch/parse/normalize | 缺方法启动失败 | 单测覆盖所有 adapter |
| AT-295 | web_page channel 配置 schema | `GET /api/v1/collection-channels/web_page/schema` | web 源配置表单 | 返回 url/depth/robots/rate_limit 字段 | schema 缺字段测试失败 | p95 < 200ms |
| AT-296 | official_api channel 配置 schema | `GET /api/v1/collection-channels/official_api/schema` | API 源配置表单 | 返回 auth/pagination/request 字段 | 明文 secret 字段禁止 | p95 < 200ms |
| AT-297 | document_file channel 配置 schema | `GET /api/v1/collection-channels/document_file/schema` | 文档上传源配置 | 返回 allowed_types/schema_mapping | 禁止类型不可选 | p95 < 200ms |
| AT-298 | image_file channel 配置 schema | `GET /api/v1/collection-channels/image_file/schema` | 图片源配置 | 返回格式、OCR、VLM、脱敏策略 | 未启用脱敏需提示风险 | p95 < 200ms |
| AT-299 | video_file channel 配置 schema | `GET /api/v1/collection-channels/video_file/schema` | 视频源配置 | 返回 keyframe/asr/ocr/vlm 策略 | 超大视频策略缺失 422 | p95 < 200ms |
| AT-300 | livestream channel 配置 schema | `GET /api/v1/collection-channels/livestream/schema` | 直播源配置 | 返回 HLS/DASH/RTMP、segment、buffer 策略 | 无保留期 422 | p95 < 200ms |
| AT-301 | audio_file channel 配置 schema | `GET /api/v1/collection-channels/audio_file/schema` | 音频源配置 | 返回 ASR、分段、语言策略 | 不支持语言提示 | p95 < 200ms |
| AT-302 | channel 独立错误码映射 | service `map_channel_error_codes` | run 详情错误展示 | 不同 channel 错误可读 | 未映射错误标 unknown 并告警 | 单测覆盖 |
| AT-303 | channel 独立限流策略 | service `apply_channel_rate_limit` | 后台采集 | 每个 channel 独立限流 | 超限进入 delayed | 压测无互相影响 |
| AT-304 | channel 独立回放策略 | service `replay_channel_run_from_checkpoint` | run 失败重放 | 从 channel checkpoint 继续 | checkpoint 缺失返回 409 | 不重复写 raw |
| AT-305 | channel 独立质量指标 | `GET /api/v1/collection-channels/{channel}/quality-metrics` | 质量中心按渠道查看 | 返回 channel 专属指标 | 未知 channel 404 | p95 < 500ms |
| AT-306 | channel 维护成本看板 | `GET /api/v1/collection-channels/maintenance` | 运维看板 | 返回失败率、代码版本、配置版本、测试覆盖 | 指标缺失告警 | p95 < 1000ms |

## 20. 新增原子任务：图片算法与 Agent 闭环

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-307 | 图片文件接收 | `POST /api/v1/media/images` | 上传图片/导入图片源 | 图片对象和 raw media record 落库 | 禁止格式/超大小/病毒扫描失败 | 50MB 图片可提示进度 |
| AT-308 | 图片元数据提取 | algorithm `extract_image_metadata` | 后台处理 | 提取尺寸、格式、EXIF、拍摄时间 | EXIF 缺失不失败 | 单图 < 300ms |
| AT-309 | 图片感知哈希去重 | algorithm `dedupe_image_phash` | 后台去重 | 相似图片形成候选组 | 低质量图片标 uncertain | 10 万图 < 10min |
| AT-310 | 图片 OCR | algorithm `ocr_image_text` | 后台抽取/详情页 | 提取文本、坐标、置信度 | 无文字返回 empty | 单图 < 5s |
| AT-311 | 图片敏感信息打码 | algorithm `redact_image_sensitive_regions` | 展示/导出前处理 | 人脸区域、证件号、手机号区域打码 | 打码失败禁止公开展示 | 单图 < 5s |
| AT-312 | 图片场景分类 | algorithm `classify_image_scene` | 后台抽取 | 输出场景标签和置信度 | 低置信度进入人工复核 | 单图 < 3s |
| AT-313 | 图片目标检测 | algorithm `detect_image_objects` | 后台抽取 | 输出目标类别、框、置信度 | 模型不可用标 failed | 单图 < 5s |
| AT-314 | 图片 VLM 证据描述 | algorithm `vlm_describe_image_evidence` | 证据页生成描述 | 描述带 image_region_refs | 无区域引用 claim blocked | 单图 < 20s |
| AT-315 | 图片证据候选生成 | algorithm `generate_image_evidence_candidates` | 后台生成 | OCR/VLM/检测结果转 evidence candidate | 无有效 artifact 不生成 | 1 万图 < 30min |
| AT-316 | 图片证据详情查看 | `GET /api/v1/media/images/{id}/evidence` | 图片证据页 | 展示原图、打码图、OCR、区域引用 | 无权限只看打码图 | 浏览器区域点击验收 |

## 21. 新增原子任务：视频算法与 Agent 闭环

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-317 | 视频文件接收 | `POST /api/v1/media/videos` | 上传视频/导入视频源 | 视频对象和 raw media record 落库 | 禁止格式/超大小失败 | 上传进度可见 |
| AT-318 | 视频转码代理任务 | workflow activity `prepare_video_proxy` | 后台处理 | 生成可浏览 proxy | 转码失败记录原因 | 1GB 视频 < 20min |
| AT-319 | 视频关键帧抽取 | algorithm `extract_video_keyframes` | 后台处理 | 按策略抽关键帧并落库 | 视频损坏失败可见 | 1 小时视频 < 10min |
| AT-320 | 视频镜头切分 | algorithm `detect_video_shots` | 后台处理 | 生成 shot segments | 低质量视频标 uncertain | 1 小时视频 < 10min |
| AT-321 | 视频音轨抽取 | algorithm `extract_video_audio_track` | 后台处理 | 音轨文件落库 | 无音轨返回 empty | 1 小时视频 < 5min |
| AT-322 | 视频 ASR 转写 | algorithm `asr_transcribe_video_audio` | 视频详情字幕 | 生成带时间戳 transcript | 语言不支持/噪声过高提示 | 1 小时音频 < 20min |
| AT-323 | 视频帧 OCR | algorithm `ocr_video_keyframes` | 后台抽取 | 关键帧文字带时间戳 | OCR 失败标 partial | 1000 帧 < 20min |
| AT-324 | 视频视觉事件检测 | algorithm `detect_video_visual_events` | 后台抽取 | 输出动作/场景/目标事件片段 | 低置信度进入复核 | 1 小时视频 < 30min |
| AT-325 | 视频片段摘要 | algorithm `summarize_video_segments` | 视频详情摘要 | 每段摘要带时间戳和证据引用 | 无引用摘要 blocked | 1 小时视频 < 10min |
| AT-326 | 视频证据候选生成 | algorithm `generate_video_evidence_candidates` | 后台生成 | transcript/OCR/keyframe/segment 转证据 | 无 artifact 不生成 | 1 小时视频 < 10min |
| AT-327 | 视频证据详情查看 | `GET /api/v1/media/videos/{id}/evidence` | 视频证据页 | 播放定位到证据时间戳 | 无权限不可下载原视频 | 浏览器点击证据跳时间 |

## 22. 新增原子任务：直播算法与 Agent 闭环

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-328 | 直播源创建 | `POST /api/v1/media/livestream-sources` | 新建直播源 | 保存 HLS/DASH/RTMP URL 和策略 | URL 不可达 422 | 审计可查 |
| AT-329 | 直播连通性检测 | `POST /api/v1/media/livestream-sources/{id}/probe` | 点击检测直播 | 返回协议、码率、延迟、可用性 | 404/403/超时分类 | < 10s |
| AT-330 | 直播 segment 采集 | workflow activity `capture_livestream_segments` | 后台采集 | segment 写对象存储并落库 | 断流进入 reconnecting | 延迟 < 30s |
| AT-331 | 直播滚动缓冲 | service `maintain_livestream_rolling_buffer` | 后台运行 | 按保留期滚动保存 | 存储满告警 | 缓冲状态可查 |
| AT-332 | 直播实时 ASR | algorithm `streaming_asr_livestream` | 直播监控页字幕 | 生成低延迟 transcript | ASR 失败自动降级批处理 | 延迟 < 15s |
| AT-333 | 直播关键帧采样 | algorithm `sample_livestream_keyframes` | 直播监控页截图 | 按间隔生成关键帧 | 黑屏/卡顿标异常 | 延迟 < 10s |
| AT-334 | 直播实时 OCR | algorithm `ocr_livestream_keyframes` | 直播监控页文字信号 | OCR 文本带时间戳 | OCR partial 可见 | 延迟 < 20s |
| AT-335 | 直播异常事件触发 | algorithm `detect_livestream_event_triggers` | 直播告警 | 关键词/视觉/音频触发 signal draft | 低置信度不自动确认 | 告警延迟 < 30s |
| AT-336 | 直播片段剪裁成证据 | `POST /api/v1/media/livestreams/{id}/clips` | 点击保存证据片段 | clip 文件和 evidence candidate 落库 | 时间范围越界 422 | 浏览器播放 clip |
| AT-337 | 直播断流恢复 | workflow activity `recover_livestream_capture` | 后台恢复 | 断流后重连并记录 gap | 长时间断流标 failed | 恢复策略测试通过 |

## 23. 新增原子任务：多模态 Agent 与跨源印证

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-338 | 多模态 artifact 统一查询 | `GET /api/v1/media/artifacts` | 多媒体证据工作台 | 可按 image/video/live/audio/OCR/ASR/VLM 筛选 | 越权 403 | 100 万 artifact p95 < 1500ms |
| AT-339 | 多模态证据 Agent | professional agent purpose=multimodal_evidence_review | 证据页点击智能复核 | Agent 汇总 OCR/ASR/VLM/metadata 输出证据判断 | 无 artifact 返回 insufficient_data | 单证据 < 60s |
| AT-340 | 跨源印证算法 | algorithm `corroborate_cross_modal_evidence` | 证据复核页 | 文本、图片、视频、直播互相印证评分 | 时间/地点冲突标 warning | 单事件 < 30s |
| AT-341 | 多模态时间线对齐 | algorithm `align_multimodal_timeline` | 主线页时间线 | 对齐 ASR、OCR、关键帧、文本事件 | 时间戳缺失标 uncertain | 1 万 artifact < 5min |
| AT-342 | 多模态风险因子生成 | algorithm `generate_multimodal_risk_factors` | 风险因子页 | 基于文字+视觉+音频证据生成因子 | 无证据引用 blocked | 单主题 < 90s |
| AT-343 | 多模态证据进入报告 | service `render_multimodal_evidence_in_report` | 报告页引用多媒体 | 报告引用可跳转图片区域/视频时间戳/直播 clip | 文件权限不足时脱敏展示 | 浏览器跳转验收 |

## 24. 第三方检查门禁

第三方检查是所有 AT 任务的冻结前置条件。实现方只能提交完成证据，不能自行冻结任务。

### 24.1 检查矩阵

| 输出类型 | 第三方检查方 | 必查内容 | 阻断条件 |
| --- | --- | --- | --- |
| API / 后端服务 | Backend Reviewer + QA Agent | API contract、状态码、权限、审计、数据库落库、幂等、异常码 | contract 不一致；无审计；越权可访问；错误码不规范 |
| 数据采集 | Data QA Agent | source 配置、adapter、run 状态、raw record、cursor、幂等、dead letter、重放 | 跳过 raw 直接写下游；重试重复写；失败原因不可见 |
| 数据清洗 | Data QA Agent | parser、cleaner、去重、质量评分、敏感信息、血缘 | 血缘断裂；敏感信息未脱敏；清洗结果不可复现 |
| 算法结果 | Algorithm Reviewer + Regression QA | algorithm version、config version、input snapshot、output schema、评测指标 | 无版本；无输入快照；回归指标下降未解释 |
| LLM 输出 | LLM Reviewer + Safety Reviewer | prompt version、schema validation、evidence_refs、blocked_claims、token/cost、失败处理 | 无证据事实进入正式结论；非法 JSON 被当成功 |
| 产品运行时 Agent 输出 | Agent Reviewer + LLM Reviewer | `user.md`、`soul.md`、`agent.md`、工具权限、立场一致性、输出 schema | 角色背景缺失；工具越权；输出与立场冲突且无标记 |
| 多 Agent Council | Council Reviewer + QA Agent | stakeholder 来源、Agent 组成、共识/分歧、让步、决策矩阵、证据引用 | 固定硬编码角色；无利益方来源；无证据结论进入报告 |
| 前端页面 | Frontend Reviewer + Browser QA | 真实 API、loading、empty、error、success、permission denied、刷新保持状态 | 前端 mock；纯前端业务状态；错误态缺失 |
| 图片/视频/直播 | Multimodal QA + Security Reviewer | OCR/ASR/VLM、时间戳、区域引用、敏感区域打码、文件权限 | 未脱敏展示；证据无法跳到时间戳/区域；媒体原件越权下载 |
| 报告/导出物 | Report Reviewer + Compliance Reviewer | 引用、正式措辞、合成数据水印、客户级语言、导出内容一致性 | 引用断链；合成数据无声明；出现 mock/demo/dev/internal 文案 |
| 性能结果 | Performance QA | p95、吞吐、并发、慢查询、workflow 恢复、资源占用 | 核心路径超过阈值且无风险登记 |
| 安全合规 | Security/Compliance Reviewer | 租户隔离、权限、脱敏、数据保留、外部源授权、审计 | 跨租户泄露；明文 secret；未授权数据进入正式链路 |
| 发布包 | Release/DCP Reviewer | 功能、异常、性能、安全、浏览器验收、残余风险 | 任一 P0/P1 阻断项未关闭 |

### 24.2 检查记录要求

每次第三方检查必须产生一条检查记录：

| 字段 | 要求 |
| --- | --- |
| `task_id` | 对应 AT 编号 |
| `artifact_type` | api、workflow、algorithm、llm、agent、frontend、media、report、security、release |
| `implementer` | 实现 agent 或实现人 |
| `reviewer` | 第三方检查 agent 或 reviewer |
| `checklist_version` | 检查清单版本 |
| `result` | passed、failed、blocked、waived |
| `blocking_findings` | 阻断问题列表 |
| `evidence_refs` | 测试结果、截图、日志、DB 查询、报告文件、trace id |
| `retest_result` | 修复后的复测结果 |

`waived` 只能用于非阻断项，并且必须写明业务负责人接受的残余风险。

## 25. 新增原子任务：第三方检查系统

| ID | 原子功能 | 后端/API/服务 | 前端场景 | 正常测试 | 异常测试 | 性能/浏览器验收 |
| --- | --- | --- | --- | --- | --- | --- |
| AT-360 | 建立第三方检查记录表 | `review_gate_records` migration | 质量门禁页 | 可保存 task_id、artifact_type、reviewer、result | 缺 task_id 或 reviewer 拒绝写入 | migration rollback 通过 |
| AT-361 | 创建第三方检查记录 | `POST /api/v1/review-gates` | reviewer 提交检查结论 | passed/failed/blocked/waived 落库 | 实现方给自己验收返回 409 | 审计可查 |
| AT-362 | 查询任务检查状态 | `GET /api/v1/tasks/{task_id}/review-gates` | 任务详情质量门禁 | 返回所有检查记录和最新状态 | 无权限 403 | p95 < 500ms |
| AT-363 | 阻断项创建修复任务 | service `create_fix_task_from_blocking_finding` | failed 检查后自动生成修复任务 | 阻断项生成 fix task | 重复阻断项幂等 | 任务链路可追踪 |
| AT-364 | 第三方复测记录 | `POST /api/v1/review-gates/{id}/retest` | reviewer 复测 | 复测结果关联原检查 | 非原 reviewer 需更高权限 | 审计可查 |
| AT-365 | 禁止未通过检查的任务冻结 | guardrail `block_freeze_without_review_gate` | 点击冻结任务 | 检查全通过才可冻结 | 缺第三方检查返回 409 | 浏览器冻结按钮禁用 |
| AT-366 | 检查清单版本管理 | `POST /api/v1/review-checklists/versions` | 配置中心 | 发布不同 artifact_type 的 checklist | 回归失败禁止发布 | 版本写入检查记录 |
| AT-367 | 发布前检查门禁汇总 | `GET /api/v1/release/review-gates-summary` | 发布看板 | 汇总每个 AT 的第三方检查状态 | 存在 blocked 时 DCP 禁止通过 | p95 < 1000ms |
