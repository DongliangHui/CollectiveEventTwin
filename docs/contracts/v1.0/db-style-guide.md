# 数据库命名规范 v1.0

状态：冻结版

## 命名规则

- 表名使用小写复数 snake_case：`raw_records`、`review_results`。
- 主键字段统一为 `id`，字符串 ID 优先。
- 外键字段统一为 `{object}_id`。
- 时间字段使用 `created_at`、`updated_at`、`started_at`、`completed_at`。
- 状态字段统一为 `status`。
- 版本字段使用 `version` 或 `object_version`。
- JSONB 扩展字段使用 `payload`、`metadata`、`config`、`details`。

## 通用字段

除纯连接表外，业务表默认包含：

- `id`
- `tenant_id`
- `status`
- `created_at`
- `updated_at`
- `created_by`
- `updated_by`
- `payload` 或 `metadata`

连接表至少包含：

- 两端外键。
- 唯一约束。
- `created_at`。

## 外键和索引

- 所有 `tenant_id`、`topic_id`、`city_id`、`status`、`created_at` 建索引。
- 所有高频查询的 `object_type + object_id` 建复合索引。
- `lineage_edges` 使用对象引用字段，不对跨领域下游对象强制外键。
- JSONB 高频字段可建 GIN 索引，但必须放在后置索引迁移。
- pgvector 索引只在字段和检索用例冻结后创建。

## 迁移规则

- 不改写既有 `20260508_0001_p0_core`。
- v1.0 之后只追加 forward migrations。
- 不在 migration 里写产品业务数据。
- 默认不实现 destructive downgrade。
- 字段新增优先 nullable 或带安全 default，数据回填单独迁移。

## 状态字段

状态值必须来自合同：

- Topic：`candidate`、`observing`、`active`、`merged`、`archived`、`converted_to_mainline`
- Signal：`raw_candidate`、`selected`、`in_package`、`sent_to_review`、`excluded`、`archived`
- Evidence：`candidate`、`needs_review`、`confirmed`、`rejected`、`probability_reference_only`、`used_in_mainline`
- Mainline：`draft`、`quality_failed`、`pending_confirmation`、`confirmed`、`world_state_generated`、`archived`
- Worldline Run：`pending`、`running`、`completed`、`failed`、`canceled`、`superseded`
- Council：`created`、`profile_checking`、`running`、`schema_validating`、`blocked`、`completed`、`applied`
- Report：`draft`、`claim_validation_failed`、`submitted_review`、`review_returned`、`approved`、`published`、`exported`、`archived`
