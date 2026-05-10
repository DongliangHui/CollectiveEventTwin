# CollectiveEventTwin 原子任务 Backlog v1.0

日期：2026-05-09

状态：冻结版，用于正式派工

来源：

- `docs/production-plan-v1.0-20260509.md`
- `docs/api-db-contract-v1.0-20260509.md`
- `docs/reviews/production-plan-v1.0-20260509-check.md`

## 1. 派工口径

本 backlog 将 v1.0 生产计划拆成可直接派工、可验收、可回归的原子任务。每个任务默认要求：

- API 或 workflow 有明确输入、输出、错误码和审计行为。
- 数据库读写对象明确，不能依赖产品运行时 mock 或静态 fixture。
- 前端任务必须调用真实 API，并覆盖 loading、empty、error、degraded、no permission 等状态。
- 算法、LLM、Agent、报告结论必须带输入 refs、版本、置信度或状态、blocked claims 或失败原因。
- 完成前必须有单元/集成/浏览器或脚本化验证，并可创建第三方检查记录。

## 2. 阶段依赖

```text
S0 合同冻结
  -> S1 身份/RBAC/审计/Review/Ops/Workflow Run
  -> S2 数据源/采集/清洗/合成数据/多媒体入库
  -> S3A City 页冻结
  -> S3B Topic 态势页冻结
  -> S4A 信号抽取与工作台
  -> S4B 证据复核与多媒体证据闭环
  -> S5 主线/World State/利益方
  -> S6 世界线/Agent Profile/Council
  -> S7A 报告/审批/导出/任务
  -> S7B 复盘/案例库/配置
  -> S8 全链路验收
```

## 3. S0 合同冻结

| ID | Owner | 原子任务 | 依赖 | 交付物 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S0-F000 | 架构/产品 | 冻结业务对象字典 | v1.0 计划 | `object-model.md` | CityEvent、Topic、Signal、Evidence、Mainline、WorldState、Council、Report、CaseMemory 定义完整 |
| S0-F001 | 产品/QA | 冻结页面清单 | S0-F000 | `page-inventory.md` | 11 页、状态矩阵、跳转关系确认 |
| S0-F002 | 架构/前端 | 冻结路由参数合同 | S0-F001 | `routing-contract.md` | 每页输入参数、输出参数、权限要求明确 |
| S0-F003 | 架构/后端 | 冻结 API 命名规范 | API/DB 合同 | `api-style-guide.md` | 路径、分页、错误码、状态码统一 |
| S0-F004 | 架构/后端 | 冻结数据库命名规范 | API/DB 合同 | `db-style-guide.md` | 表名、字段、索引、外键规则统一 |
| S0-F005 | 后端 A/安全 | 冻结审计对象规范 | S0-F003、S0-F004 | `audit-contract.md` | mutation 均定义 actor、object、diff、reason |
| S0-F006 | 产品/安全 | 冻结 RBAC 权限矩阵 | S0-F001、S0-F002 | `rbac-matrix.md` | 角色 x 页面 x 按钮 x 数据权限明确 |
| S0-F007 | 前端/QA | 冻结页面状态矩阵 | S0-F001 | `page-state-matrix.md` | loading、empty、error、degraded、no permission 等覆盖 |
| S0-F008 | 后端/QA | 冻结错误码合同 | S0-F003 | `error-code-contract.md` | 400、401、403、404、409、422、429、500、503 语义统一 |
| S0-F009 | 后端 A/QA | 冻结第三方检查数据模型 | API/DB 合同 | `review-schema.md` | review 对象、状态、阻断条件完整 |
| S0-F010 | LLM Agent/QA | 冻结 LLM 输出 schema | API/DB 合同 | `llm-output-contract.md` | schema-valid、evidence-linked、blocked claims 明确 |
| S0-F011 | 架构/数据 | 冻结证据引用规范 | S0-F010 | `evidence-reference-contract.md` | 报告、Council、主线、推演均可回溯证据 |
| S0-F012 | 数据/合规 | 冻结合成数据标记规范 | API/DB 合同 | `synthetic-data-contract.md` | 合成数据全链路标记，不混淆真实数据 |
| S0-F013 | 安全/数据 | 冻结禁用数据策略 | API/DB 合同 | `data-policy-boundary.md` | 私域、cookie 池、验证码绕过、冒充真人禁止 |
| S0-F014 | 架构/Ops | 冻结验收环境规范 | 环境约束 | `env-contract.md` | dev、test、staging、prod 数据隔离 |
| S0-F015 | 前端/浏览器 QA | 冻结截图基线规范 | S0-F007 | `visual-baseline-contract.md` | 每页 routeable state + 截图 diff 规则明确 |
| S0-F016 | 后端/Ops | 冻结工作流状态规范 | API/DB 合同 | `workflow-state-contract.md` | pending、running、failed、completed、canceled、retrying 明确 |
| S0-F017 | PM/QA | 冻结发布门禁 | S0-F009、S0-F015 | `release-gate.md` | P0/P1 blocker、豁免、DCP 规则明确 |

## 4. S1 基础平台前置能力

| ID | Owner | 原子任务 | API / 交付物 | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S1-F001 | 后端 A/前端 A | 登录成功/失败链路 | `POST /api/v1/auth/login` | S0-F006、S0-F008 | 浏览器真实提交，账号不存在/密码错误/禁用/锁定可区分，审计可查 |
| S1-F002 | 后端 A/前端 A | token 刷新和退出 | `POST /api/v1/auth/refresh`、`POST /api/v1/auth/logout` | S1-F001 | 过期 token 自动回登录，退出清理会话 |
| S1-F003 | 后端 A/前端 A | 当前用户和权限 | `GET /api/v1/auth/me`、`GET /api/v1/auth/permissions` | S1-F001、S0-F006 | 不同角色菜单、按钮、数据权限不同 |
| S1-F004 | 后端 A/前端 A | 用户和角色管理 | `/api/v1/users`、`/api/v1/roles` | S1-F003 | 越权、重复数据、禁用用户被拒并写审计 |
| S1-F005 | 后端 A/前端 C | 审计查询 | `GET /api/v1/audit-logs` | S0-F005 | 所有 mutation 可按用户、动作、对象、时间查询 |
| S1-F006 | 后端 A/QA | 创建检查任务 | `POST /api/v1/reviews` | S0-F009 | review pending 入库并绑定对象版本 |
| S1-F007 | 后端 A/前端 C | 检查任务列表/详情 | `GET /api/v1/reviews`、`GET /api/v1/reviews/{id}` | S1-F006 | 分页、权限、对象过滤正确 |
| S1-F008 | 后端 A/QA | 提交检查结果 | `PATCH /api/v1/reviews/{id}` | S1-F007 | PASS/FAIL/waived 状态正确，FAIL 生成修复任务 |
| S1-F009 | 后端 A/QA | 检查模板配置 | `GET /api/v1/review-templates` | S1-F006 | 模板版本和对象类型可追踪 |
| S1-F010 | 后端 A/QA | 阻断检查 | `POST /api/v1/reviews/{id}/gate-check` | S1-F008 | blocker 未清不能冻结或发布 |
| S1-F011 | 后端 A/PM | 豁免记录 | `POST /api/v1/reviews/{id}/waive` | S1-F010 | waived 必须有批准人、理由、有效期、风险 |
| S1-F012 | 后端 A/Ops | API 健康检查 | `GET /api/v1/ops/health/api` | S0-F014 | 服务失败可见并返回 trace_id |
| S1-F013 | 后端 A/Ops | DB 健康检查 | `GET /api/v1/ops/health/db` | S0-F014 | 连接、延迟、迁移版本可见 |
| S1-F014 | 后端 A/Ops | Worker 健康检查 | `GET /api/v1/ops/health/workers` | S0-F016 | worker down 和 backlog 可见 |
| S1-F015 | 后端 A/Ops | Workflow 状态查询 | `GET /api/v1/workflow-runs` | S0-F016 | 可按对象追踪 workflow run、activity、错误 |
| S1-F016 | 后端 A/Ops | Error queue 查询 | `GET /api/v1/ops/error-queue` | S1-F015 | 可定位 F033/F047/F140 等失败 |
| S1-F017 | 后端 A/Ops | Retry queue 查询 | `GET /api/v1/ops/retry-queue` | S1-F015 | 重试次数、下次时间、可重试性可见 |
| S1-F018 | 后端 A/Ops | Metrics 上报 | `GET /api/v1/ops/metrics` | S1-F012 至 S1-F017 | p95、错误率、worker、LLM、workflow 指标可见 |
| S1-F019 | 后端 A/Ops | Trace ID 全链路透传 | API middleware + logs | S1-F012 | trace_id 贯穿 API、workflow、LLM 和前端错误展示 |

## 5. S2 数据源、采集、清洗、多媒体入库

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S2-F020 | 后端 A/数据 | 数据源类型字典 | `GET /api/v1/data-source-types` | S1-F003 | 支持 synthetic、manual_upload、public_web、official_api、media、live_segment |
| S2-F021 | 后端 A/前端 A | 新建合成数据源 | `POST /api/v1/data-sources` | S2-F020、S0-F012 | `source_type=synthetic` 入库并写审计 |
| S2-F022 | 后端 A/前端 A | 新建手工上传源 | `POST /api/v1/data-sources` | S2-F020 | 上传策略、大小、格式限制可配置 |
| S2-F023 | 后端 A/前端 A | 新建公开网页源 | `POST /api/v1/data-sources` | S2-F020、S0-F013 | policy blocked 时不创建 collection run |
| S2-F024 | 后端 A/前端 A | 新建官方 API 源 | `POST /api/v1/data-sources` | S2-F020、S0-F013 | API key 缺失、限流、不可用可区分 |
| S2-F025 | 后端 B/前端 A | 新建图片/视频/直播源 | `POST /api/v1/data-sources` | S2-F020 | 媒体类型、保留期、脱敏要求入库 |
| S2-F026 | 后端 A/安全 | 数据源策略校验 | `POST /api/v1/data-sources/{id}/policy-check` | S2-F021 至 S2-F025 | 返回 allow/block、原因、审计和 `SOURCE_POLICY_BLOCKED` |
| S2-F027 | 后端 A/Ops | 数据源健康检查 | `GET /api/v1/source-health` | S2-F026 | 健康、降级、失败原因、最近 run counters 可见 |
| S2-F028 | 后端 A/前端 A | collection job CRUD | `/api/v1/collection-jobs` | S2-F026 | 创建、列表、详情、编辑、暂停、归档可审计 |
| S2-F029 | 后端 A/Ops | collection run 控制 | `/api/v1/collection-jobs/{id}/runs` | S2-F028、S1-F015 | 启动、暂停、取消、重试、详情状态正确 |
| S2-F030 | 数据 Agent/后端 A | 合成西安社会议题样本生成 | `POST /api/v1/synthetic-scenarios/xian-social-issues` | S2-F021 | 原始记录通过真实采集链路产生，保留 synthetic 标记 |
| S2-F031 | 后端 B/数据 | 文件导入 | `POST /api/v1/imports/files` | S2-F022 | 导入结果写 raw records 和 payload，不预置下游对象 |
| S2-F032 | 后端 B/数据 | 公开网页采集 | `POST /api/v1/imports/public-web` | S2-F023、S2-F026 | robots/policy/失败原因可追踪 |
| S2-F033 | 后端 B/数据 | 官方 API 采集 | `POST /api/v1/imports/official-api` | S2-F024 | 限流、超时、响应 schema 错误可追踪 |
| S2-F034 | 后端 B/数据 | 媒体文件导入 | `POST /api/v1/imports/media` | S2-F025 | `media_assets` 入库，处理 run 可查询 |
| S2-F035 | 后端 B/前端 B | raw records 列表/详情 | `GET /api/v1/raw-records`、`GET /api/v1/raw-records/{id}` | S2-F031 至 S2-F034 | 分页、筛选、payload、来源链路正确 |
| S2-F036 | 后端 B/前端 B | raw record 标签 | `POST /api/v1/raw-records/{id}/labels` | S2-F035 | 标签、操作者、原因、审计入库 |
| S2-F037 | 数据 Agent/后端 B | normalization run | `POST /api/v1/normalization-runs` | S2-F035 | 输入范围、规则版本、结果 counters 可见 |
| S2-F038 | 数据 Agent/后端 B | deduplication run | `POST /api/v1/deduplication-runs` | S2-F037 | 去重组、合并解释、保留记录可追踪 |
| S2-F039 | 数据 Agent/后端 B | data quality run | `POST /api/v1/data-quality-runs` | S2-F037 | 缺字段、低可信、异常 payload 可定位 |
| S2-F040 | 后端 B/数据 | lineage 查询 | `GET /api/v1/lineage` | S2-F031 至 S2-F039 | 任意下游对象可回溯 raw record 和 synthetic 标记 |
| S2-F041 | 后端 B/Ops | 失败隔离 | error queue | S1-F016、S2-F029 | 失败 run 不污染已成功对象 |
| S2-F042 | 后端 B/Ops | 失败重放 | retry queue | S1-F017、S2-F041 | 可重试和不可重试错误分开 |
| S2-F043 | 前端 A/后端 A | 数据源健康面板 API | `GET /api/v1/data-sources/health-view` | S2-F027 | City/配置页可消费同一健康 DTO |
| S2-F044 | 安全/后端 A | 策略阻断审计 | audit logs | S2-F026 | blocked source 写 source policy、审计，不创建 run |
| S2-F045 | Ops/后端 A | run counters metrics | metrics | S2-F029、S2-F037 至 S2-F039 | collection、normalization、dedup、quality 指标可见 |
| S2-F046 | QA/第三方检查 | S2 第三方检查 | `POST /api/v1/reviews` | S2-F020 至 S2-F045 | source health、run counters、policy boundary PASS |

### F047 LLM 结构化抽取

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F047-1 | 后端 B/LLM Agent | 创建 extraction run | S2-F035、S1-F015 | run 状态、输入范围、操作者入库 |
| F047-2 | LLM Agent/数据 | 构造抽取输入包 | F047-1、S2-F034 | 文本/OCR/ASR、来源、时间、region、证据上下文完整 |
| F047-3 | LLM Agent/后端 B | 调用 LLM provider | F047-2、S1-F019 | timeout、retry、token、cost、model 记录 |
| F047-4 | LLM Agent/QA | LLM 输出 schema 校验 | F047-3、S0-F010 | schema invalid 进入失败态 |
| F047-5 | LLM Agent/数据 | evidence refs 校验 | F047-4、S0-F011 | 引用不存在或越权时阻断 |
| F047-6 | LLM Agent/安全 | blocked claims 识别 | F047-5 | 无证据事实进入 blocked claims |
| F047-7 | 后端 B/数据 | 抽取结果入库 | F047-4 至 F047-6 | entities、mentions、claims、risk hints 可追溯 |
| F047-8 | 后端 B/Ops | 抽取失败重试 | F047-3 至 F047-7 | 可重试错误和不可重试错误分开 |
| F047-9 | 前端 B/QA | 抽取结果人工复核 | F047-7 | 复核状态影响后续算法 |
| F047-10 | LLM Agent/Ops | 抽取版本对比 | F047-7 | prompt/model/schema 版本差异可查 |

## 6. S3A City 页冻结

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S3A-F048 | 后端 B/前端 A | 城市列表与切换 | `GET /api/v1/cities` | S2-F027 | 西安为第一阶段默认城市，权限过滤正确 |
| S3A-F049 | 后端 B/前端 A | City 页面 overview | `GET /api/v1/cities/{city_id}/overview` | S2-F043 | 聚合城市总览、风险、事件、地图摘要、数据源健康、媒体摘要 |
| S3A-F050 | 后端 B/前端 A | 地图图层数据 | `GET /api/v1/cities/{city_id}/map-layers` | S3A-F049 | map/satellite/heat 数据后端返回 |
| S3A-F051 | 后端 B/前端 A | 图层状态保存 | `PATCH /api/v1/cities/{city_id}/map-state` | S3A-F050、S1-F005 | 业务交互写后端和审计 |
| S3A-F052 | 后端 B/前端 A | 城市事件排行榜 | `GET /api/v1/cities/{city_id}/events/rankings` | S3A-F049 | 热度、风险、来源新鲜度排序可解释 |
| S3A-F053 | 后端 B/前端 A | 城市事件筛选 | `GET /api/v1/cities/{city_id}/events` | S3A-F052 | 区域、类型、来源、风险筛选来自 API |
| S3A-F054 | 后端 B/前端 A | 事件详情抽屉 | `GET /api/v1/city-events/{event_id}` | S3A-F053 | 点击 map/rank/timeline 返回同一事件详情 |
| S3A-F055 | 后端 A/前端 A | 数据源健康面板 | `GET /api/v1/cities/{city_id}/source-health-view` | S2-F043 | degraded source 可见并影响 page_state |
| S3A-F056 | 后端 B/前端 A | 城市媒体证据面板 | `GET /api/v1/cities/{city_id}/media-evidence` | S2-F034 | media processing/failed 状态可见 |
| S3A-F057 | 后端 B/前端 A | 城市时间线 | `GET /api/v1/cities/{city_id}/timeline` | S3A-F049 | 时间线来自持久对象，不前端拼装事实 |
| S3A-F058 | 后端 B/前端 A | 从城市事件创建主题 | `POST /api/v1/city-events/{event_id}/create-topic` | S3A-F054、S3B-F073 | 创建 topic 并跳转主题态势页 |
| S3A-F059 | QA/前端 A | City 页面状态库存 | Playwright states | S0-F007、S3A-F049 至 S3A-F058 | loading、empty、error、source degraded、filter no result、selected event、map tile fail、media processing、no permission 覆盖 |
| S3A-F060 | 浏览器 QA/第三方检查 | City 第三方视觉/功能检查 | `POST /api/v1/reviews` | S3A-F059 | 截图 diff、真实点击、network/console 检查 PASS |

## 7. S3B 主题态势页冻结

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S3B-F073 | 后端 B/前端 A | 从城市事件创建主题 | `POST /api/v1/topics` | S3A-F054 | 创建 topic，跳转主题态势页 |
| S3B-F074 | 后端 B/前端 A | 主题列表查询 | `GET /api/v1/topics` | S3B-F073 | 按城市、区域、状态、热度筛选，分页正常 |
| S3B-F075 | 后端 B/前端 A | 主题详情 | `GET /api/v1/topics/{id}` | S3B-F074 | 返回主题基础信息和状态机 |
| S3B-F076 | 后端 B/前端 A | 主题态势 view-model | `GET /api/v1/topics/{id}/situation-view` | S3B-F075 | 返回热度、情绪、传播、来源、候选主线 |
| S3B-F077 | 后端 B/前端 A | 主题信号来源聚合 | `GET /api/v1/topics/{id}/source-breakdown` | S3B-F076 | 视频、直播、评论、图文分布正确 |
| S3B-F078 | 后端 B/前端 A | 主题传播路径 | `GET /api/v1/topics/{id}/spread-paths` | S3B-F076 | 平台路径、圈层迁移可视化 |
| S3B-F079 | 后端 B/前端 A | 主题情绪立场 | `GET /api/v1/topics/{id}/emotion-stance` | S3B-F076 | 同城情绪、诉求、评论样本正确 |
| S3B-F080 | 后端 B/前端 A | 主题候选主线 | `GET /api/v1/topics/{id}/candidate-mainlines` | S3B-F076 | 主线概率、证据缺口、进入主线按钮 |
| S3B-F081 | QA/前端 A | 主题页状态库存 | Playwright states | S3B-F076 至 S3B-F080 | loading、empty、error、degraded、selected、no permission 覆盖 |
| S3B-F082 | 浏览器 QA/第三方检查 | 主题页第三方检查 | `POST /api/v1/reviews` | S3B-F081 | 业务表达和页面状态 PASS 后冻结 |

## 8. S4A 信号抽取与数据/信号工作台

### F080 信号抽取运行

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F080-1 | 数据 Agent/后端 B | 选择输入 raw records | S2-F035 | 输入范围、来源、时间窗口可追踪 |
| F080-2 | 算法 Agent/后端 B | 生成候选 signal | F080-1 | 候选信号带输入 refs |
| F080-3 | 算法 Agent/后端 B | signal 去重 | F080-2 | 重复信号合并可解释 |
| F080-4 | 算法 Agent/后端 B | signal 聚合 | F080-3 | 聚合规则和版本可查 |
| F080-5 | 算法 Agent/后端 B | signal 情绪识别 | F080-4 | 情绪结果带置信度 |
| F080-6 | 算法 Agent/后端 B | signal 诉求识别 | F080-4 | 诉求标签带 evidence refs |
| F080-7 | 算法 Agent/后端 B | signal 传播特征计算 | F080-4 | 平台、扩散速度、传播路径可查 |
| F080-8 | 算法 Agent/后端 B | signal 同城占比计算 | F080-4 | 西安本地占比和来源依据明确 |
| F080-9 | 算法 Agent/后端 B | signal 可信度计算 | F080-5 至 F080-8 | source trust、交叉印证、复核状态参与计算 |
| F080-10 | 后端 B | signal 入库 | F080-9 | 写 signals、lineage、algorithm version |
| F080-11 | 后端 B/Ops | signal 失败归因 | F080-2 至 F080-10 | schema、数据不足、算法异常可区分 |
| F080-12 | 后端 B/前端 B | signal run 结果查询 | F080-10、F080-11 | run counters、errors、sample outputs 可见 |

### 数据/信号工作台

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S4A-WB-01 | 后端 B/前端 B | 工作台 view-model | `GET /api/v1/topics/{id}/signal-workbench-view` | F080-12 | 信号列表、筛选、信号包、抽取 run、lineage 聚合 |
| S4A-WB-02 | 后端 B/前端 B | 信号搜索 | `GET /api/v1/signals` | S4A-WB-01 | search success、no result 状态覆盖 |
| S4A-WB-03 | 后端 B/前端 B | 信号详情 | `GET /api/v1/signals/{id}` | S4A-WB-02 | 输入 refs、版本、置信度、lineage 可见 |
| S4A-WB-04 | 后端 B/前端 B | 信号加入/移出信号包 | `POST /api/v1/signal-packages/{id}/items`、`DELETE ...` | S4A-WB-03 | draft add/remove 审计可查 |
| S4A-WB-05 | 后端 B/前端 B | 信号包创建和状态查询 | `/api/v1/signal-packages` | S4A-WB-04 | 信号包状态影响主线输入资格 |
| S4A-WB-06 | QA/浏览器 QA | 信号页面状态与浏览器验收 | Playwright states | S4A-WB-01 至 S4A-WB-05 | lineage missing、permission denied、run failed 可复现 |

## 9. S4B 证据复核与多媒体证据闭环

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S4B-F001 | 算法 Agent/后端 B | 证据候选生成 | `POST /api/v1/evidence-candidates` | F080-10 | evidence 带 signal/raw refs 和状态 candidate |
| S4B-F002 | 后端 B/前端 B | 证据详情 | `GET /api/v1/evidence/{id}` | S4B-F001 | 原始来源、masked excerpt、可信度可见 |
| S4B-F003 | 后端 B/前端 B | 证据复核状态更新 | `PATCH /api/v1/evidence-reviews/{id}` | S4B-F002 | confirmed/rejected/probability_reference_only 状态合法 |
| S4B-F004 | 后端 B/前端 B | 证据补充上传 | `POST /api/v1/evidence/{id}/attachments` | S4B-F002、S2-F034 | 上传媒体进入 media_assets 并绑定证据 |
| S4B-F005 | 算法 Agent/后端 B | 风险因子生成 | `POST /api/v1/risk-factor-runs` | S4B-F003 | 风险因子带 evidence refs 和算法版本 |
| S4B-F006 | 后端 B/前端 B | 风险因子列表 | `GET /api/v1/risk-factors` | S4B-F005 | 可按 topic/status/category 筛选 |
| S4B-F007 | 后端 B/前端 B | 风险因子确认/驳回 | `PATCH /api/v1/risk-factors/{id}` | S4B-F006 | 状态流转写审计 |
| S4B-F008 | 算法 Agent/前端 B | 风险置信度调整 | `POST /api/v1/risk-factors/{id}/confidence-adjustments` | S4B-F007 | 调整原因、输入 refs、版本可查 |
| S4B-F009 | 算法 Agent/后端 B | 冲突检测 | `POST /api/v1/conflict-detection-runs` | S4B-F003 | 冲突组可解释且可转复核 |
| S4B-F010 | 数据 Agent/后端 B | 图片 OCR | `POST /api/v1/media-processing-runs` | S2-F034 | OCR 文本入库，不直接当事实 |
| S4B-F011 | 数据 Agent/后端 B | 图片主体/场景识别 | `POST /api/v1/media-processing-runs` | S2-F034 | CV 输出带置信度和 blocked claims |
| S4B-F012 | 数据 Agent/后端 B | 视频抽帧 | `POST /api/v1/media-processing-runs` | S2-F034 | frame refs 可追踪 |
| S4B-F013 | 数据 Agent/后端 B | 视频 ASR | `POST /api/v1/media-processing-runs` | S2-F034 | ASR 文本带时间戳和置信度 |
| S4B-F014 | 数据 Agent/后端 B | 视频 OCR | `POST /api/v1/media-processing-runs` | S4B-F012 | OCR 与 frame refs 绑定 |
| S4B-F015 | 数据 Agent/后端 B | 关键片段检测 | `POST /api/v1/media-segment-runs` | S4B-F012 至 S4B-F014 | 片段不直接作为事实，需证据复核 |
| S4B-F016 | 数据 Agent/后端 B | 直播片段化 | `POST /api/v1/live-segment-runs` | S2-F025 | 片段边界、来源、时间戳可追踪 |
| S4B-F017 | 后端 B/前端 B | 多媒体证据绑定 | `POST /api/v1/evidence-media-links` | S4B-F010 至 S4B-F016 | 媒体与 evidence 双向可查 |
| S4B-F018 | 安全/数据 Agent | 敏感信息脱敏 | `POST /api/v1/redaction-runs` | S4B-F010 至 S4B-F017 | 原文访问受控，展示默认 masked |
| S4B-F019 | 后端 B/前端 B | 证据复核页 view-model | `GET /api/v1/evidence-reviews/{id}/review-view` | S4B-F001 至 S4B-F018 | 复核状态、媒体处理状态、来源链路、敏感脱敏、冲突提示完整 |
| S4B-F020 | QA/第三方检查 | 证据与多媒体检查 | `POST /api/v1/reviews` | S4B-F019 | 多媒体未脱敏或直接当事实时阻断 |

## 10. S5 主线、World State、利益方识别

### F110 主线草稿生成

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F110-1 | 算法 Agent/后端 C | 从信号包生成信号簇 | S4A-WB-05 | 输入信号包和聚类参数可追踪 |
| F110-2 | 算法 Agent/后端 C | 生成诉求/情绪聚合节点 | F110-1 | 诉求和情绪节点带证据 refs |
| F110-3 | 算法 Agent/后端 C | 生成主叙事节点 | F110-2 | 主叙事不允许无证据断言 |
| F110-4 | 算法 Agent/后端 C | 生成扩散路径节点 | F110-2 | 平台和圈层路径可解释 |
| F110-5 | 算法 Agent/后端 C | 生成关键不确定性节点 | F110-2 | 信息缺口可进入报告 |
| F110-6 | 算法 Agent/后端 C | 生成候选主线 | F110-3 至 F110-5 | 多候选可比较 |
| F110-7 | 算法 Agent/后端 C | 计算主线成立概率 | F110-6 | 概率算法版本可查 |
| F110-8 | 算法 Agent/后端 C | 计算主线置信度 | F110-6 | 置信度由证据质量支撑 |
| F110-9 | 算法 Agent/后端 C | 生成证据缺口 | F110-6 | 缺口可转任务 |
| F110-10 | 算法 Agent/后端 C | 生成可推演性检查 | F110-6 | 不满足条件不得进入世界线 |
| F110-11 | 后端 C | 保存主线草稿版本 | F110-7 至 F110-10 | 版本和 diff 可查 |
| F110-12 | 后端 C/前端 B | 返回 builder view-model | F110-11 | `GET /api/v1/mainlines/{id}/builder-view` 可用 |

### 主线与利益方工作台

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S5-MAIN-01 | 后端 C/前端 B | 主线详情 | `GET /api/v1/mainlines/{id}` | F110-12 | 主线状态、版本、证据缺口可见 |
| S5-MAIN-02 | 后端 C/前端 B | 主线节点编辑 | `PATCH /api/v1/mainline-nodes/{id}` | S5-MAIN-01 | node edit conflict 可复现并返回 409 |
| S5-MAIN-03 | 后端 C/前端 B | 主线信号操作 | `/api/v1/mainlines/{id}/signals` | S5-MAIN-01 | 增删信号生成新版本和审计 |
| S5-MAIN-04 | 算法 Agent/QA | 主线质量检查 | `POST /api/v1/mainlines/{id}/quality-check` | S5-MAIN-02 | quality failed 阻断确认 |
| S5-MAIN-05 | 后端 C/前端 B | 确认主线 | `POST /api/v1/mainlines/{id}/confirm` | S5-MAIN-04 | pending_confirmation -> confirmed 状态合法 |
| S5-MAIN-06 | 后端 C/算法 Agent | World State 生成 | `POST /api/v1/world-states` | S5-MAIN-05 | world_state_generated 后进入世界线输入 |
| S5-MAIN-07 | 后端 C/前端 B | World State 版本查询 | `GET /api/v1/world-states/{id}` | S5-MAIN-06 | 输入版本锁定，可比对历史 |
| S5-MAIN-08 | 算法 Agent/后端 C | 案件图谱节点生成 | `POST /api/v1/case-graph-runs` | S5-MAIN-06 | 图谱节点带来源和证据 refs |
| S5-MAIN-09 | 算法 Agent/后端 C | 利益方识别 | `POST /api/v1/stakeholder-runs` | S5-MAIN-08 | 利益方角色、诉求、证据 refs 可查 |
| S5-MAIN-10 | 前端 B/QA | 利益方人工复核 | `PATCH /api/v1/stakeholders/{id}/review` | S5-MAIN-09 | 未复核利益方不能进入 Agent Profile |

## 11. S6 世界线、Agent Profile、Council

### F121 世界线运行创建

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F121-1 | 后端 C | 创建 worldline run | S5-MAIN-07 | run 入库，状态 pending |
| F121-2 | 后端 C/算法 Agent | 加载 World State 输入包 | F121-1 | 输入版本锁定 |
| F121-3 | 算法 Agent | 生成初始状态节点 | F121-2 | 当前状态可解释 |
| F121-4 | 算法 Agent | 生成回应动作候选 | F121-3 | 候选动作和约束明确 |
| F121-5 | 算法 Agent | 生成情绪变化路径 | F121-3 | 变化依据可追踪 |
| F121-6 | 算法 Agent | 生成传播速度路径 | F121-3 | 传播假设可解释 |
| F121-7 | 算法 Agent | 生成破圈路径 | F121-3 | 破圈条件和证据明确 |
| F121-8 | 算法 Agent | 生成主叙事转向路径 | F121-3 | 叙事转向有输入 refs |
| F121-9 | 算法 Agent | 计算 A/B/C/D 分支概率 | F121-4 至 F121-8 | 概率版本和输入可查 |
| F121-10 | 后端 C/数据 | 绑定证据引用 | F121-9 | 引用缺失则阻断 |
| F121-11 | 后端 C/前端 B | 生成节点详情 | F121-10 | 节点可点击查看 |
| F121-12 | 后端 C | 保存 worldline version | F121-11 | 版本可比较 |
| F121-13 | 后端 C/前端 B | 生成 simulation view-model | F121-12 | `GET /api/v1/worldline-runs/{id}/simulation-view` 可用 |
| F121-14 | 后端 C/Ops | 失败归因与重试 | F121-1 至 F121-13 | 可重试和不可重试错误区分 |

### Agent Profile

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S6-PROFILE-01 | LLM Agent/后端 C | 生成 Agent Profile 草稿 | `POST /api/v1/agent-profiles` | F121-13、S5-MAIN-10 | 只为已复核利益方生成 profile |
| S6-PROFILE-02 | LLM Agent/后端 C | 生成 profile 文件 | `POST /api/v1/agent-profiles/{id}/files` | S6-PROFILE-01 | `user.md`、`soul.md`、`agent.md` 入库并版本化 |
| S6-PROFILE-03 | QA/第三方检查 | Profile 第三方检查 | `POST /api/v1/reviews` | S6-PROFILE-02 | 未 PASS 不得创建 Council Session |
| S6-PROFILE-04 | 后端 C/前端 B | Profile readiness view | `GET /api/v1/agent-profiles/{id}` | S6-PROFILE-03 | ready、blocked、waived 状态可见 |

### F140 Council 运行

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F140-1 | 后端 C | 创建 Council run | S6-PROFILE-03 | session/run 状态入库 |
| F140-2 | 后端 C | 加载当前 worldline node | F140-1 | 节点版本锁定 |
| F140-3 | 后端 C | 加载 Agent Profiles | F140-1 | 所有 profile ready |
| F140-4 | LLM Agent | 加载研判假设 | F140-2 | 假设来源和版本明确 |
| F140-5 | LLM Agent | 生成各 Agent 输入上下文 | F140-2 至 F140-4 | 每个 Agent context evidence-bounded |
| F140-6 | LLM Agent | 单 Agent 反应生成 | F140-5 | LLM call 可追踪 |
| F140-7 | LLM Agent/QA | 单 Agent schema 校验 | F140-6 | schema invalid 阻断 |
| F140-8 | LLM Agent/数据 | 单 Agent evidence refs 校验 | F140-7 | 引用缺失阻断 |
| F140-9 | LLM Agent/安全 | 单 Agent blocked claims 检查 | F140-8 | 无证据 claims 不进入结论 |
| F140-10 | LLM Agent/后端 C | 多 Agent 观点合并 | F140-6 至 F140-9 | 合并规则和 prompt 版本可查 |
| F140-11 | LLM Agent | 分歧点识别 | F140-10 | 分歧显式展示 |
| F140-12 | 算法 Agent | 支点变化计算 | F140-10 | 支点变化有依据 |
| F140-13 | 算法 Agent | 分支概率变化计算 | F140-10 | 世界线概率变更可解释 |
| F140-14 | 算法 Agent | 信息缺口变化计算 | F140-10 | 缺口可转任务 |
| F140-15 | 后端 C | Council Result 入库 | F140-11 至 F140-14 | result、messages、blocked claims 入库 |
| F140-16 | QA/第三方检查 | Council 第三方检查 | `POST /api/v1/reviews` | F140-15 | PASS 后可应用 |
| F140-17 | 后端 C/前端 B | 回写世界线 | F140-16 | 只回写已校验结果 |
| S6-COUNCIL-UI | 前端 B/浏览器 QA | Council 页 view-model 和状态 | `GET /api/v1/council-sessions/{id}/council-view` | F140-1 至 F140-17 | session created、profile checking、running、provider error、schema invalid、blocked claims、completed、applied 覆盖 |

## 12. S7A 报告、审批、导出、任务

### F150 报告草稿生成

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| F150-1 | 后端 D | 创建报告草稿 | F140-16 | report draft 入库 |
| F150-2 | 后端 D/产品 | 汇总主题态势摘要 | F150-1、S3B-F076 | 来自 Topic view-model 或持久对象 |
| F150-3 | 后端 D/数据 | 汇总证据链 | F150-1、S4B-F019 | 证据 refs 完整 |
| F150-4 | 后端 D | 汇总主线结构 | F150-1、S5-MAIN-05 | 主线版本锁定 |
| F150-5 | 后端 D | 汇总世界线概率 | F150-1、F121-13 | worldline run 版本锁定 |
| F150-6 | 后端 D | 汇总 Council 结果 | F150-1、F140-16 | 只使用校验通过结果 |
| F150-7 | 后端 D/产品 | 生成建议动作 | F150-2 至 F150-6 | 建议动作带约束和风险 |
| F150-8 | 后端 D/产品 | 生成不确定性说明 | F150-2 至 F150-6 | 信息缺口可见 |
| F150-9 | 后端 D/产品 | 生成后续观察变量 | F150-2 至 F150-6 | 可转监测任务 |
| F150-10 | 后端 D/前端 C | 生成任务建议 | F150-7 至 F150-9 | 责任方、截止时间、依据明确 |
| F150-11 | 后端 D/LLM Agent | 报告声明抽取 | F150-2 至 F150-10 | 每条事实声明单独记录 |
| F150-12 | 后端 D/QA | 报告声明证据校验 | F150-11 | 失败则不能提交审阅 |
| F150-13 | 后端 D | 报告版本保存 | F150-12 | 版本和 diff 可查 |
| F150-14 | 后端 D/前端 C | 报告 view-model 返回 | F150-13 | `GET /api/v1/reports/{id}/brief-view` 可用 |

### 报告与任务闭环

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S7A-REPORT-01 | 后端 D/前端 C | 报告详情 | `GET /api/v1/reports/{id}` | F150-14 | 章节、声明、证据链、状态可见 |
| S7A-REPORT-02 | 后端 D/前端 C | 报告编辑 | `PATCH /api/v1/reports/{id}` | S7A-REPORT-01 | published 后修改必须新版本 |
| S7A-REPORT-03 | 后端 D/QA | 提交第三方审阅 | `POST /api/v1/reports/{id}/submit-review` | F150-12 | claim validation failed 阻断提交 |
| S7A-REPORT-04 | QA/第三方检查 | 第三方审阅通过/退回 | `PATCH /api/v1/reviews/{id}` | S7A-REPORT-03 | review returned/approved 状态合法 |
| S7A-REPORT-05 | 后端 D/前端 C | 报告冻结发布 | `POST /api/v1/reports/{id}/publish` | S7A-REPORT-04 | 发布写审计，后续修改走新版本 |
| S7A-REPORT-06 | 后端 D/前端 C | 报告导出 | `POST /api/v1/reports/{id}/exports` | S7A-REPORT-05 | 导出元数据、水印和失败原因入库 |
| S7A-TASK-01 | 后端 D | 任务自动生成 | F150-10 | 建议任务转正式任务并保留依据 |
| S7A-TASK-02 | 后端 D/前端 C | 手动创建任务 | `POST /api/v1/tasks` | S7A-TASK-01 | 责任方、截止时间、来源 refs 必填 |
| S7A-TASK-03 | 后端 D/前端 C | 任务状态更新 | `PATCH /api/v1/tasks/{id}` | S7A-TASK-02 | task_events 记录状态流转 |
| S7A-QA-01 | 浏览器 QA/第三方检查 | 报告页状态与浏览器验收 | Playwright states | S7A-REPORT-01 至 S7A-TASK-03 | draft、claim validation failed、submitted review、review returned、approved、published、export failed 覆盖 |

## 13. S7B 复盘、案例库、配置中心

| ID | Owner | 原子任务 | API / Workflow | 依赖 | 验收 |
| --- | --- | --- | --- | --- | --- |
| S7B-F001 | 后端 D/前端 C | 复盘创建 | `POST /api/v1/retrospectives` | S7A-REPORT-05 | retrospective draft 入库 |
| S7B-F002 | 后端 D/数据 | 复盘知识入库 | `POST /api/v1/knowledge-items` | S7B-F001 | 未审批知识不能污染生产规则 |
| S7B-F003 | 后端 D/前端 C | 复盘 view-model | `GET /api/v1/retrospectives/{id}/memory-view` | S7B-F002 | 预测对比、知识项、审批状态完整 |
| S7B-F004 | 后端 D/前端 C | 案例库搜索 | `GET /api/v1/case-library-entries` | S7B-F002 | library empty、search no result 覆盖 |
| S7B-F005 | 后端 D/前端 C | 案例详情 | `GET /api/v1/case-library-entries/{id}` | S7B-F004 | 案例来源、适用条件、风险可见 |
| S7B-F006 | 后端 D/前端 C | 案例库 view-model | `GET /api/v1/cases/library-view` | S7B-F004、S7B-F005 | 模板、相似案例、应用建议聚合 |
| S7B-F007 | 后端 D/前端 C | 应用案例建议 | `POST /api/v1/case-library-entries/{id}/apply` | S7B-F006 | conflict 时返回 409 和影响说明 |
| S7B-F008 | 后端 D/前端 C | 数据源配置版本 | `POST /api/v1/config/versions` | S2-F020 | 配置版本可审阅、发布、回滚 |
| S7B-F009 | 后端 D/前端 C | 标签体系配置 | `POST /api/v1/config/versions` | S7B-F008 | 影响 signals/evidence 的范围可见 |
| S7B-F010 | 后端 D/LLM Agent | 模型参数配置 | `POST /api/v1/config/versions` | S7B-F008 | provider/model/version 冲突可检测 |
| S7B-F011 | 后端 D/LLM Agent | Agent 配置 | `POST /api/v1/config/versions` | S7B-F008 | Agent 模板修改需审阅 |
| S7B-F012 | 后端 D/LLM Agent | Prompt 模板配置 | `POST /api/v1/prompt-templates` | S7B-F010 | prompt 版本可回归、可审计 |
| S7B-F013 | QA/Ops | 配置回归测试 | `POST /api/v1/config/versions/{id}/regression-runs` | S7B-F008 至 S7B-F012 | regression running/failed 状态可见 |
| S7B-F014 | PM/QA | 配置审批发布 | `POST /api/v1/config/versions/{id}/publish` | S7B-F013 | 回归通过且审批后才能发布 |
| S7B-F015 | 后端 D/Ops | 配置回滚 | `POST /api/v1/config/releases/{id}/rollback` | S7B-F014 | 回滚必须有影响范围提示 |
| S7B-F016 | 后端 D/前端 C | 配置页 view-model | `GET /api/v1/config/admin-view` | S7B-F008 至 S7B-F015 | config loading、source unhealthy、policy blocked、model conflict、approval pending、published、rollback failed 覆盖 |
| S7B-F017 | 浏览器 QA/第三方检查 | 复盘/案例库/配置检查 | `POST /api/v1/reviews` | S7B-F001 至 S7B-F016 | 复盘、案例库、配置版本均 PASS 或有批准豁免 |

## 14. S8 全链路验收

| ID | Owner | 原子任务 | 依赖 | 验收 |
| --- | --- | --- | --- | --- |
| S8-F001 | QA A/C | 全链路正向 E2E | S1 至 S7B | 从合成 raw record 到报告、任务、复盘全链路通过 |
| S8-F002 | 异常测试 Agent | 全链路异常矩阵 | S1 至 S7B | 401/403/404/409/422/429/500/503、依赖失败、状态冲突覆盖 |
| S8-F003 | 性能测试 Agent | 性能基线 | S1 至 S7B | API p95、首屏、workflow、LLM、媒体处理耗时有阈值或降级 |
| S8-F004 | 安全/合规 | 安全与数据策略检查 | S0-F013、S2、S6、S7A | 禁用数据策略、敏感脱敏、越权、无证据结论阻断 |
| S8-F005 | 浏览器 QA | 客户可见页面视觉回归 | S3A 至 S7B | 11 页 routeable state 截图基线和 diff PASS |
| S8-F006 | Ops | 观测与故障演练 | S1-F012 至 S1-F019 | trace、metrics、error queue、retry queue 可定位故障 |
| S8-F007 | 第三方检查 Agent | 发布包第三方检查 | S1 至 S8-F006 | API、数据源、算法、多媒体、Agent、Council、报告、页面、配置 PASS |
| S8-F008 | PM/产品 | DCP 发布决策包 | S8-F001 至 S8-F007 | P0/P1 blocker 清零，豁免有批准和风险 |
| S8-F009 | 全体 | 客户评审准备 | S8-F008 | 发布验收包、演示数据标记、残余风险清单齐备 |
| S8-F010 | PM/架构 | 复盘与下一阶段 backlog | S8-F009 | 记录架构、QA、数据/LLM、前端可复用经验 |
