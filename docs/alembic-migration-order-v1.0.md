# CollectiveEventTwin Alembic 迁移顺序 v1.0

日期：2026-05-09

状态：冻结版，用于后续迁移派工

来源：

- `docs/api-db-contract-v1.0-20260509.md`
- `docs/production-plan-v1.0-20260509.md`
- `apps/api/alembic/versions/20260508_0001_p0_core.py`

## 1. 冻结原则

- 现有 `20260508_0001_p0_core` 是历史 P0 skeleton 基线，不在本轮直接改写。
- v1.0 之后只追加 forward migrations；如需把现有 skeleton 表扩展到合同字段，用 `ALTER TABLE`、新增索引、新增约束完成。
- 每个 revision 只负责一个领域边界，保证失败可定位、回滚策略可描述、第三方检查可按领域验收。
- 表结构先满足身份/RBAC、审计、Review、Workflow Run，再进入数据源、raw records、信号、证据、主线、世界线、Agent/Council、报告、复盘/配置。
- Alembic 不承载产品运行时业务数据。权限点、review templates、默认配置模板等参考数据可以用单独 seed 脚本幂等写入，但不得把合成场景、信号、证据、报告等产品数据写进迁移。
- 每个迁移必须能通过 `alembic upgrade head`、模型元数据 smoke test、关键外键/索引检查。

## 2. 既有基线

| Revision | 名称 | 状态 | 说明 |
| --- | --- | --- | --- |
| `20260508_0001` | `p0 core schema` | 已存在 | 创建 `cases`、`source_records`、`signals`、`evidence`、`risk_factors`、`mainlines`、`world_states`、`worldline_nodes`、`council_sessions`、`reports`、`tasks`、`workflow_runs`、`audit_logs`，并启用 `vector` extension |

处理规则：

- 新迁移的 `down_revision` 从 `20260508_0001` 开始串行接上。
- 已存在但合同字段不足的表在对应领域 revision 中做兼容性 `ALTER`。
- `source_records` 是 skeleton 名称；v1.0 合同表为 `raw_records` / `raw_record_payloads`。迁移时保留旧表作为历史兼容输入，新增正式 v1.0 表，不直接重命名旧表，避免破坏已有测试和 seed。

## 3. 冻结迁移序列

| 顺序 | Revision ID | 领域 | 主要表/动作 | 依赖 | 解锁阶段 |
| --- | --- | --- | --- | --- | --- |
| 0 | `20260508_0001` | P0 skeleton baseline | 保留既有基线 | 无 | 历史 P0 |
| 1 | `20260509_0002_identity_rbac_review_audit` | 身份、RBAC、Review、审计扩展 | `tenants`、`users`、`roles`、`permissions`、`role_permissions`、`user_roles`、`sessions`、`review_templates`、`reviews`、`review_results`，扩展 `audit_logs` | 0001 | S1 |
| 2 | `20260509_0003_workflow_ops_contracts` | Workflow/Ops 基础 | 扩展 `workflow_runs`，新增 `workflow_run_events`、`ops_error_queue`、`ops_retry_queue`、`metrics_snapshots` | 0002 | S1 |
| 3 | `20260509_0004_sources_collection` | 数据源与采集任务 | `data_sources`、`source_health`、`source_policies`、`collection_jobs`、`collection_runs`、`collection_run_events` | 0003 | S2 |
| 4 | `20260509_0005_raw_media_lineage` | raw records、多媒体、血缘 | `raw_records`、`raw_record_payloads`、`raw_record_labels`、`media_assets`、`media_processing_runs`、`lineage_edges` | 0004 | S2 |
| 5 | `20260509_0006_import_processing_runs` | imports、normalization、dedup、data quality | `import_runs`、`normalization_runs`、`raw_record_normalizations`、`deduplication_runs`、`raw_record_dedup_groups`、`data_quality_runs`、`raw_record_quality_issues` | 0005 | S2 |
| 6 | `20260509_0007_city_topic_signal` | City、Topic、Signal | `topics`、`city_events`，扩展 `signals`，新增 `signal_packages`、`signal_package_items` | 0006 | S3A/S3B/S4A |
| 7 | `20260509_0008_evidence_review_closure` | 证据、多媒体复核 | 新增 `evidence_reviews`、`evidence_media_links`；risk/conflict 通过既有 `risk_factors` 和 `workflow_runs.payload` 持久化 | 0007 | S4B |
| 8 | `20260509_0009_mainline_world_state_stakeholders` | 主线、World State、利益方 | 新增 `mainline_versions`、`mainline_nodes`、`case_graph_nodes`、`stakeholders`；`mainlines`、`world_states` 通过既有 baseline 表与 JSONB 合同承载 S5 状态 | 0008 | S5 |
| 9 | `20260509_0010_worldline_runs` | 世界线推演 | `worldline_runs`、扩展 `worldline_nodes`、新增 `worldline_edges`、`worldline_interventions` | 0009 | S6 |
| 10 | `20260509_0011_llm_agent_council` | LLM、Agent Profile、Council | `llm_providers`、`llm_calls`、`prompt_templates`、`agent_templates`、`agent_profiles`、`agent_profile_files`，扩展 `council_sessions`，新增 `council_messages`、`council_results`、`blocked_claims` | 0010 | S6 |
| 11 | `20260509_0012_reports_tasks` | 报告、导出、任务 | 扩展 `reports`、`tasks`，新增 `report_versions`、`report_claims`、`report_exports`、`task_events` | 0011 | S7A |
| 12 | `20260509_0013_memory_library_config` | 复盘、案例库、配置 | `retrospectives`、`knowledge_items`、`case_library_entries`、`case_library_applications`、`config_versions`、`config_releases` | 0012 | S7B |
| 13 | `20260509_0014_indexes_constraints_views` | 全局索引、约束、只读视图 | GIN/JSONB、FTS、pgvector、状态索引、唯一约束、运维只读视图 | 0013 | S8 |

## 4. 每个 revision 的表内顺序

### 4.1 `20260509_0002_identity_rbac_review_audit`

1. `tenants`
2. `users`
3. `roles`
4. `permissions`
5. `role_permissions`
6. `user_roles`
7. `sessions`
8. `review_templates`
9. `reviews`
10. `review_results`
11. `audit_logs` 兼容扩展：补 `tenant_id`、`actor_id`、`object_version`、`before`、`after`、`diff`、`trace_id`、`ip`、`user_agent`

关键约束：

- `users.tenant_id -> tenants.id`
- `sessions.user_id -> users.id`
- `role_permissions.role_id -> roles.id`
- `role_permissions.permission_id -> permissions.id`
- `user_roles.user_id -> users.id`
- `user_roles.role_id -> roles.id`
- `reviews.template_id -> review_templates.id`

### 4.2 `20260509_0003_workflow_ops_contracts`

1. 扩展 `workflow_runs`：补 `workflow_run_id`、`workflow_type`、`object_type`、`object_id`、`input_hash`、`current_step`、`attempt`、`error_code`、`error_message`、`is_retryable`、`started_at`、`completed_at`、`trace_id`
2. `workflow_run_events`
3. `ops_error_queue`
4. `ops_retry_queue`
5. `metrics_snapshots`

关键约束：

- workflow run 必须能按 `object_type + object_id` 查询。
- queue 表必须保留 `is_retryable` 和 `next_retry_at`，支持 S1 error/retry queue。

### 4.3 `20260509_0004_sources_collection`

1. `data_sources`
2. `source_policies`
3. `source_health`
4. `collection_jobs`
5. `collection_runs`
6. `collection_run_events`

关键约束：

- `source_policies.data_source_id -> data_sources.id`
- `source_health.data_source_id -> data_sources.id`
- `collection_jobs.data_source_id -> data_sources.id`
- `collection_runs.collection_job_id -> collection_jobs.id`
- `collection_run_events.collection_run_id -> collection_runs.id`
- `data_sources.source_type` 只能为 `synthetic`、`manual_upload`、`public_web`、`official_api`、`media`、`live_segment`。

### 4.4 `20260509_0005_raw_media_lineage`

1. `raw_records`
2. `raw_record_payloads`
3. `raw_record_labels`
4. `media_assets`
5. `media_processing_runs`
6. `lineage_edges`

关键约束：

- `raw_records.data_source_id -> data_sources.id`
- `raw_records.collection_run_id -> collection_runs.id`
- `raw_record_payloads.raw_record_id -> raw_records.id`
- `raw_record_labels.raw_record_id -> raw_records.id`
- `media_assets.raw_record_id -> raw_records.id`
- `media_processing_runs.media_asset_id -> media_assets.id`
- `lineage_edges` 使用 `from_object_type/from_object_id/to_object_type/to_object_id`，避免跨领域硬外键阻塞演进。
- `is_synthetic` 必须从 `data_sources` 和 `raw_records` 延续到 `lineage_edges`。

### 4.5 `20260509_0006_import_processing_runs`

1. `import_runs`
2. `normalization_runs`
3. `raw_record_normalizations`
4. `deduplication_runs`
5. `raw_record_dedup_groups`
6. `data_quality_runs`
7. `raw_record_quality_issues`

关键约束：
- `import_runs` 必须绑定 `data_source_id`，可选绑定 `collection_run_id`，失败时进入 `ops_error_queue`，可重试失败进入 `ops_retry_queue`。
- normalization/dedup/data-quality run 必须保留 `rule_version`、输入/输出 counters、`trace_id` 和失败原因。
- normalization 输出、dedup 合并和 quality issue 必须可追溯 raw record。

### 4.6 `20260509_0007_city_topic_signal`

1. `cities`
2. `topics`
3. `city_events`
4. `city_map_states`
5. 扩展 `signals`
6. `signal_packages`
7. `signal_package_items`

关键约束：

- `topics.city_id -> cities.id`
- `topics.status` 使用 Topic 生命周期状态机。
- `city_events.city_id -> cities.id`
- `city_events.raw_record_id -> raw_records.id`，不使用前端 fixture 生成事件。
- `city_events.topic_id -> topics.id` 可空。
- `city_map_states.city_id -> cities.id`，与 `user_id` 唯一组合，所有地图交互落到后端状态。
- `signals.topic_id -> topics.id`
- `signals.status` 使用 Signal 生命周期状态机。
- `signal_packages.topic_id -> topics.id`
- `signal_package_items.signal_package_id -> signal_packages.id`
- `signal_package_items.signal_id -> signals.id`

### 4.7 `20260509_0008_evidence_review_closure`

1. `evidence_reviews`
2. `evidence_media_links`
3. `risk_factors` 继续使用 P0 baseline 表，S4B service 写入 evidence refs / confidence adjustments / algorithm version
4. `workflow_runs` 继续承载 evidence candidate、redaction、risk factor、conflict detection run

关键约束：

- `evidence.status` 使用 Evidence 生命周期状态机。
- `evidence_reviews.evidence_id -> evidence.id`
- `evidence_media_links.evidence_id -> evidence.id`
- `evidence_media_links.media_asset_id -> media_assets.id`
- `risk_factors.payload.topic_id` 和 `risk_factors.payload.evidence_refs` 保留 JSONB 追踪，同时通过 service 校验 refs 存在。
- `conflict_detection_run` 使用 `workflow_runs` 持久化 run，conflict groups 写入 run/evidence payload，避免 S4B 在未进入 S5 主线建模前增加过早独立事实表。

### 4.8 `20260509_0009_mainline_world_state_stakeholders`

S5 implemented freeze note: concrete 0009 creates `mainline_versions`, `mainline_nodes`, `case_graph_nodes`, and `stakeholders`; `mainline_edges` remains deferred to S6 `worldline_runs` unless a separate S5 edge contract is introduced.

1. 复用 `mainlines`
2. `mainline_versions`
3. `mainline_nodes`
4. 复用 `world_states`
5. `case_graph_nodes`
6. `stakeholders`

关键约束：

- `mainlines.topic_id -> topics.id`
- `mainlines.status` 使用 Mainline 生命周期状态机。
- `mainline_versions.mainline_id -> mainlines.id`
- `mainline_nodes.mainline_id -> mainlines.id`
- `case_graph_nodes.mainline_id -> mainlines.id`
- `case_graph_nodes.world_state_id -> world_states.id` 可空
- `world_states.payload.mainline_id` 由 S5 service 校验并写入
- `stakeholders.topic_id -> topics.id`
- confirmed 主线修改必须新增 `mainline_versions`，不能原地覆盖。

### 4.9 `20260509_0010_worldline_runs`

1. `worldline_runs`
2. 扩展 `worldline_nodes`
3. `worldline_edges`
4. `worldline_interventions`

关键约束：

- `worldline_runs.world_state_id -> world_states.id`
- `worldline_runs.status` 使用 Worldline Run 生命周期状态机。
- `worldline_nodes.worldline_run_id -> worldline_runs.id`
- `worldline_edges.worldline_run_id -> worldline_runs.id`
- `worldline_interventions.worldline_run_id -> worldline_runs.id`
- `superseded` 历史保留，不删除旧 run。

### 4.10 `20260509_0011_llm_agent_council`

S6 implemented freeze note: concrete 0010 extends `worldline_nodes` and creates `worldline_runs`, `worldline_edges`, and `worldline_interventions`; concrete 0011 creates LLM provider/call, prompt template, Agent Profile/file, Council message/result, and blocked-claim tables. Council apply is guarded by service-level review gate checks and does not rely on migration seed data.

1. `llm_providers`
2. `prompt_templates`
3. `llm_calls`
4. `agent_templates`
5. `agent_profiles`
6. `agent_profile_files`
7. 扩展 `council_sessions`
8. `council_messages`
9. `council_results`
10. `blocked_claims`

关键约束：

- `llm_calls.provider_id -> llm_providers.id`
- `llm_calls.prompt_template_id -> prompt_templates.id`
- `agent_profiles.stakeholder_id -> stakeholders.id`
- `agent_profile_files.agent_profile_id -> agent_profiles.id`
- `council_sessions.worldline_run_id -> worldline_runs.id`
- `council_messages.council_session_id -> council_sessions.id`
- `council_results.council_session_id -> council_sessions.id`
- `blocked_claims.llm_call_id -> llm_calls.id` 可空；`blocked_claims.council_result_id -> council_results.id` 可空。
- Council `applied` 只能引用第三方检查 PASS 的结果，由 service 层和 review gate 双重校验。

### 4.11 `20260509_0012_reports_tasks`

S7A implemented freeze note: concrete 0012 extends existing `reports` and `tasks`, then creates `report_versions`, `report_claims`, `report_exports`, and `task_events`. The migration carries no report content seed data; report drafts, claim validation, exports, and task closure records are created only through FastAPI services.

1. 扩展 `reports`
2. `report_versions`
3. `report_claims`
4. `report_exports`
5. 扩展 `tasks`
6. `task_events`

关键约束：

- `reports.topic_id -> topics.id`
- `reports.status` 使用 Report 生命周期状态机。
- `report_versions.report_id -> reports.id`
- `report_claims.report_version_id -> report_versions.id`
- `report_exports.report_id -> reports.id`
- `tasks.report_id -> reports.id` 可空。
- `task_events.task_id -> tasks.id`
- `published` 报告修改必须新增 `report_versions`，不能原地覆盖正式版本。

### 4.12 `20260509_0013_memory_library_config`

S7B implemented freeze note: concrete 0013 creates retrospective, knowledge, case-library entry/application, config version, and config release tables. The planned `case_memories` table is not introduced in S7B; memory identity is represented by `retrospectives` plus evidence-linked `knowledge_items`, and production reuse is represented by `case_library_entries` and persisted `case_library_applications`.

1. `retrospectives`
2. `knowledge_items`
3. `case_library_entries`
4. `case_library_applications`
5. `config_versions`
6. `config_releases`

关键约束：

- `retrospectives.report_id -> reports.id`
- `knowledge_items.retrospective_id -> retrospectives.id`
- `case_library_entries.retrospective_id -> retrospectives.id`
- `case_library_entries.knowledge_item_id -> knowledge_items.id`
- `case_library_applications.case_library_entry_id -> case_library_entries.id`
- `config_releases.config_version_id -> config_versions.id`
- 复盘知识进入生产案例库或配置前必须经过 Review。

### 4.13 `20260509_0014_indexes_constraints_views`

全局补强，不创建新业务主表：

- 为所有 `tenant_id`、`topic_id`、`city_id`、`status`、`created_at`、`object_type + object_id` 增加查询索引。
- 为 JSONB payload/config/evidence refs 增加必要 GIN 索引。
- 为搜索字段增加 Postgres FTS 索引。
- 为向量字段增加 pgvector 索引，仅在字段已经存在且 P0 需要时启用。
- 创建只读运维视图，例如 source health summary、workflow failure summary、review blocker summary。
- 不在此 revision 中补业务字段，避免索引迁移和模型迁移混杂。

## 5. 验证清单

每个 revision 合入前必须完成：

```powershell
python -m alembic -c apps/api/alembic.ini upgrade head
python -m alembic -c apps/api/alembic.ini current
python -m pytest apps/api/tests
```

如果本地 Postgres 未启动，至少完成：

- Alembic revision 文件静态导入检查。
- SQLAlchemy metadata 表名与 migration 表名对照。
- OpenAPI DTO 中引用的对象名与表组对照。

## 6. 第三方检查入口

迁移顺序冻结后，第三方检查应按以下对象创建 review：

| Review 对象 | 检查内容 | 阻断条件 |
| --- | --- | --- |
| `api` | v1.0 OpenAPI DTO 与表组是否对齐 | DTO 引用无表、状态机缺失、错误码缺失 |
| `data_source` | 数据源、策略、健康、collection run 表是否完整 | 无 policy/source health/run counters |
| `algorithm_output` | Signal/Evidence/Mainline/Worldline 输出表是否可追踪 | 无 input refs、版本、置信度 |
| `agent_profile` | Stakeholder -> profile 文件 -> review 是否有顺序 | 未复核利益方直接生成 profile |
| `council_result` | Council 输出、blocked claims、review gate 是否落表 | schema invalid 或无证据结论可应用 |
| `report` | report claims、versions、exports、tasks 是否闭环 | claim validation failed 仍可发布 |
| `config_version` | 配置版本、回归、发布、回滚是否闭环 | 未回归或未审批可发布 |

## 7. 明确不做

- 不在 Alembic 迁移里生成西安合成场景业务数据。
- 不把现有 `source_records` 直接删除或重命名。
- 不在当前冻结文档里决定每个字段的最终 SQL 类型长度；字段级类型在对应 revision 的实现 PR 中按 OpenAPI/DTO 和 SQLAlchemy 模型一起评审。
- 不启用 destructive downgrade；与现有 P0 基线保持一致，生产迁移只前进。
