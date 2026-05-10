# CollectiveEventTwin API / DB / 状态合同 v1.0

日期：2026-05-09

状态：评审版

关联计划：

- `docs/production-plan-v1.0-20260509.md`

本文件用于约束后续 OpenAPI、数据库迁移、前端 view-model、测试用例和第三方检查。

## 1. 通用 API 合同

成功响应：

```json
{
  "data": {},
  "meta": {},
  "trace_id": "string"
}
```

失败响应：

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  },
  "trace_id": "string"
}
```

所有 mutation 必须：

- 校验权限。
- 校验状态机。
- 写审计日志。
- 返回最新对象或状态快照。
- 返回 `trace_id`。

所有长任务必须：

- 创建 run 记录。
- 写 workflow/activity 状态。
- 记录失败原因。
- 支持查询。
- 可区分可重试和不可重试错误。

## 2. 页面级 view-model API 合同

所有客户可见核心页面必须由后端返回页面级聚合 view-model。

通用字段：

```json
{
  "page_state": "loading|ready|empty|error|degraded|no_permission",
  "permissions": {},
  "refresh_at": "datetime",
  "data_freshness": {},
  "degraded_sources": [],
  "audit_context": {},
  "primary_data": {},
  "actions": []
}
```

| 页面 | API | 必须聚合 |
| --- | --- | --- |
| 城市态势页 | `GET /api/v1/cities/{id}/overview` | 城市总览、风险、事件、地图摘要、数据源健康、媒体摘要 |
| 主题态势页 | `GET /api/v1/topics/{id}/situation-view` | 热度、情绪、传播、来源、候选主线、数据新鲜度 |
| 数据/信号页 | `GET /api/v1/topics/{id}/signal-workbench-view` | 信号列表、筛选、信号包、抽取 run 状态、lineage |
| 证据复核页 | `GET /api/v1/evidence-reviews/{id}/review-view` | 证据对象、原始来源、媒体、敏感脱敏、复核动作、冲突 |
| 主线建模页 | `GET /api/v1/mainlines/{id}/builder-view` | 主线节点、证据缺口、质量检查、版本、可推演性 |
| 世界线推演页 | `GET /api/v1/worldline-runs/{id}/simulation-view` | 分支节点、概率、风险、intervention、证据引用 |
| Agent Council 页 | `GET /api/v1/council-sessions/{id}/council-view` | Agent Profile、消息、分歧、blocked claims、校验状态 |
| 汇报输出页 | `GET /api/v1/reports/{id}/brief-view` | 报告章节、声明校验、证据链、审阅状态、导出状态 |
| 复盘页 | `GET /api/v1/retrospectives/{id}/memory-view` | 复盘草稿、预测对比、知识项、审批状态 |
| 案例库页 | `GET /api/v1/cases/library-view` | 案例搜索、模板、相似案例、应用建议 |
| 配置页 | `GET /api/v1/config/admin-view` | 配置版本、回归结果、审批、回滚、影响范围 |

前端限制：

- 不允许前端计算业务事实。
- 不允许页面绕过 view-model 自行拼多个接口形成正式判断。
- 允许前端维护 hover、tooltip、panel open/close 等纯视觉状态。

## 3. 数据库表级交付清单

### 3.1 基础表

| 表 | 用途 |
| --- | --- |
| `tenants` | 租户 |
| `users` | 用户 |
| `roles` | 角色 |
| `permissions` | 权限点 |
| `role_permissions` | 角色权限 |
| `user_roles` | 用户角色 |
| `sessions` | 登录会话和 refresh token |
| `audit_logs` | 审计日志 |
| `reviews` | 第三方检查任务 |
| `review_templates` | 检查模板 |
| `review_results` | 检查结果和阻断项 |

### 3.2 数据源表

| 表 | 用途 |
| --- | --- |
| `data_sources` | 数据源定义 |
| `source_health` | 数据源健康状态 |
| `source_policies` | 数据源策略和合规边界 |
| `collection_jobs` | 采集任务 |
| `collection_runs` | 采集运行 |
| `collection_run_events` | run 事件、进度、错误 |
| `raw_records` | 原始记录索引 |
| `raw_record_payloads` | 原始 payload |
| `raw_record_labels` | 原始记录标签 |
| `media_assets` | 图片、视频、直播片段资产 |
| `media_processing_runs` | OCR/ASR/CV/抽帧处理 run |
| `lineage_edges` | 数据血缘边 |

### 3.3 信号 / 证据表

| 表 | 用途 |
| --- | --- |
| `topics` | 主题 |
| `city_events` | 城市事件 |
| `signals` | 信号 |
| `signal_packages` | 信号包 |
| `signal_package_items` | 信号包条目 |
| `evidence` | 证据 |
| `evidence_reviews` | 证据复核 |
| `evidence_media_links` | 证据与媒体绑定 |
| `risk_factors` | 风险因子 |
| `conflict_groups` | 冲突组 |

### 3.4 主线 / 推演表

| 表 | 用途 |
| --- | --- |
| `mainlines` | 主线 |
| `mainline_versions` | 主线版本 |
| `mainline_nodes` | 主线节点 |
| `mainline_edges` | 主线边 |
| `world_states` | World State |
| `worldline_runs` | 世界线运行 |
| `worldline_nodes` | 世界线节点 |
| `worldline_edges` | 世界线边 |
| `worldline_interventions` | 处置动作注入 |
| `stakeholders` | 利益方 |

### 3.5 Agent / LLM 表

| 表 | 用途 |
| --- | --- |
| `llm_providers` | LLM provider 配置状态 |
| `llm_calls` | LLM 调用记录 |
| `prompt_templates` | Prompt 模板版本 |
| `agent_templates` | 专业 Agent 模板 |
| `agent_profiles` | 事件 Agent Profile |
| `agent_profile_files` | `user.md`、`soul.md`、`agent.md` |
| `council_sessions` | Council Session |
| `council_messages` | Council 消息 |
| `council_results` | Council 结果 |
| `blocked_claims` | 被阻断声明 |

### 3.6 报告 / 任务 / 复盘表

| 表 | 用途 |
| --- | --- |
| `reports` | 报告 |
| `report_versions` | 报告版本 |
| `report_claims` | 报告事实声明 |
| `report_exports` | 报告导出 |
| `tasks` | 处置任务 |
| `task_events` | 任务状态事件 |
| `retrospectives` | 复盘 |
| `case_memories` | 案例记忆 |
| `knowledge_items` | 知识项 |
| `case_library_entries` | 案例库条目 |
| `config_versions` | 配置版本 |
| `config_releases` | 配置发布 |

## 4. 生命周期状态机

### 4.1 Topic

```text
candidate
observing
active
merged
archived
converted_to_mainline
```

约束：

- `candidate` 可以来自 City event。
- `active` 才能进入信号工作台。
- `converted_to_mainline` 后不能直接删除。

### 4.2 Signal

```text
raw_candidate
selected
in_package
sent_to_review
excluded
archived
```

约束：

- `raw_candidate` 不能直接进入报告。
- `in_package` 才能参与主线草稿。
- `excluded` 必须记录原因。

### 4.3 Evidence

```text
candidate
needs_review
confirmed
rejected
probability_reference_only
used_in_mainline
```

约束：

- `confirmed` 才能支撑正式事实。
- `probability_reference_only` 只能用于概率参考，不能作为事实断言。
- `used_in_mainline` 修改需产生新版本。

### 4.4 Mainline

```text
draft
quality_failed
pending_confirmation
confirmed
world_state_generated
archived
```

约束：

- `quality_failed` 不得生成 World State。
- `confirmed` 后修改必须生成新版本。
- `world_state_generated` 后进入世界线输入。

### 4.5 Worldline Run

```text
pending
running
completed
failed
canceled
superseded
```

约束：

- `completed` 后可进入 Council 节点选择。
- `failed` 必须有失败归因。
- `superseded` 保留历史，不删除。

### 4.6 Council

```text
created
profile_checking
running
schema_validating
blocked
completed
applied
```

约束：

- `profile_checking` 未通过不得进入 `running`。
- `schema_validating` 失败进入 `blocked`。
- `applied` 只能使用第三方检查通过的结果。

### 4.7 Report

```text
draft
claim_validation_failed
submitted_review
review_returned
approved
published
exported
archived
```

约束：

- `claim_validation_failed` 不得提交第三方审阅。
- `published` 后修改必须生成新版本。
- `exported` 必须保留导出文件元数据和水印信息。

## 5. Review 合同

支持对象：

```text
api
data_source
algorithm_output
media_output
agent_profile
council_result
report
frontend_page
config_version
```

状态：

```text
pending
pass
fail
waived
```

核心字段：

- `review_id`
- `object_type`
- `object_id`
- `object_version`
- `template_id`
- `status`
- `reviewer_id`
- `findings`
- `blockers`
- `waiver_reason`
- `created_at`
- `completed_at`

阻断规则：

- `fail` 阻断冻结和发布。
- `waived` 必须记录业务批准人、原因、有效期、风险。
- 同一对象新版本必须重新检查。

## 6. 审计合同

所有 mutation 写 `audit_logs`。

核心字段：

- `tenant_id`
- `actor_id`
- `action`
- `object_type`
- `object_id`
- `object_version`
- `before`
- `after`
- `diff`
- `reason`
- `trace_id`
- `ip`
- `user_agent`
- `created_at`

必须审计的动作：

- 登录成功/失败。
- 权限变化。
- 数据源创建、编辑、启停、策略校验。
- collection run 启动、取消、重试。
- 原始记录标签。
- 证据复核。
- 风险因子确认。
- 主线确认。
- 世界线运行。
- Agent Profile 生成和检查。
- Council 运行、校验、应用。
- 报告提交、退回、发布、导出。
- 任务状态变化。
- 配置发布和回滚。

## 7. 错误码合同

| HTTP | 业务 code 示例 | 语义 |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | 请求语义错误 |
| 401 | `UNAUTHENTICATED` | 未登录或 token 无效 |
| 403 | `FORBIDDEN` | 无权限 |
| 404 | `NOT_FOUND` | 对象不存在 |
| 409 | `STATE_CONFLICT` | 状态冲突、重复提交、版本冲突 |
| 422 | `VALIDATION_ERROR` | 字段或 schema 校验失败 |
| 429 | `RATE_LIMITED` | 限流 |
| 500 | `INTERNAL_ERROR` | 内部错误 |
| 503 | `DEPENDENCY_UNAVAILABLE` | 外部依赖、LLM、worker、DB 不可用 |

特殊错误 code：

- `SOURCE_POLICY_BLOCKED`
- `SOURCE_UNHEALTHY`
- `RUN_NOT_RETRYABLE`
- `SCHEMA_INVALID`
- `EVIDENCE_REF_MISSING`
- `CLAIM_BLOCKED`
- `REVIEW_REQUIRED`
- `CLAIM_VALIDATION_FAILED`
- `VISUAL_BASELINE_FAILED`

## 8. Workflow Run 合同

通用状态：

```text
pending
running
retrying
failed
completed
canceled
```

核心字段：

- `workflow_run_id`
- `workflow_type`
- `object_type`
- `object_id`
- `input_hash`
- `status`
- `current_step`
- `attempt`
- `error_code`
- `error_message`
- `is_retryable`
- `started_at`
- `completed_at`
- `trace_id`

所有 workflow/activity 必须幂等：

- 以 case/topic/run/object id 作为幂等边界。
- 重试不能重复创建下游对象。
- 失败必须能查询失败步骤和错误原因。

## 9. LLM 输出合同

所有 LLM 输出必须：

- 使用版本化 prompt。
- 使用结构化 schema。
- 记录 provider、model、token、cost、latency。
- 记录输入对象 refs。
- 校验证据引用。
- 输出 blocked claims。
- 失败时显式返回错误，不允许静默 fallback 正式结论。

通用输出结构：

```json
{
  "summary": "string",
  "claims": [],
  "evidence_refs": [],
  "uncertainties": [],
  "blocked_claims": [],
  "confidence": 0.0,
  "schema_version": "string"
}
```

## 10. 合成数据合同

合成数据允许用于第一阶段西安社会议题样本，但必须：

- 数据源标记 `source_type = synthetic`。
- 原始记录标记 `is_synthetic = true`。
- 下游 lineage 保留 synthetic 标记。
- 报告和导出带 synthetic 水印或声明。
- 不能和真实数据混合后去掉标识。
- 不能绕过采集、清洗、抽取、算法、Agent、报告链路。

## 11. 禁用数据策略

禁止进入生产链路：

- cookie 池。
- CAPTCHA 绕过。
- 私信/私域聊天采集。
- 未授权登录态采集。
- 冒充真人互动。
- 绕平台访问控制。
- 非法个人敏感信息采集。

被策略阻断的数据源必须：

- 返回 `SOURCE_POLICY_BLOCKED`。
- 写 source policy 记录。
- 写审计。
- 不创建 collection run。
