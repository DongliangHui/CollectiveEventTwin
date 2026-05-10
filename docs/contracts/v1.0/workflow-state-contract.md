# 工作流状态规范 v1.0

状态：冻结版

## 通用状态

```text
pending
running
retrying
failed
completed
canceled
```

## WorkflowRun 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `workflow_run_id` | 是 | run ID |
| `workflow_type` | 是 | workflow 类型 |
| `object_type` | 是 | 绑定对象类型 |
| `object_id` | 是 | 绑定对象 ID |
| `input_hash` | 是 | 幂等输入 hash |
| `status` | 是 | 通用状态 |
| `current_step` | 否 | 当前步骤 |
| `attempt` | 是 | 尝试次数 |
| `error_code` | 条件 | 失败时必填 |
| `error_message` | 条件 | 失败时必填 |
| `is_retryable` | 是 | 是否可重试 |
| `started_at` | 否 | 开始时间 |
| `completed_at` | 否 | 完成时间 |
| `trace_id` | 是 | 链路追踪 |

## 幂等规则

- 以 `object_type + object_id + workflow_type + input_hash` 作为幂等边界。
- 重试不能重复创建下游对象。
- completed run 不得被覆盖，只能创建新版本或 supersede。
- failed run 必须可查询失败步骤和原因。

## 必须接入的 workflow

- collection run。
- normalization run。
- deduplication run。
- extraction run。
- data quality run。
- media processing run。
- risk factor run。
- mainline draft run。
- worldline run。
- council run。
- report draft run。
- config regression run。
