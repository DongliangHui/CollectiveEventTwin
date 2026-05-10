# 第三方检查数据模型 v1.0

状态：冻结版

## 支持对象

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

## 状态

```text
pending
pass
fail
waived
```

## Review 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `review_id` | 是 | 检查 ID |
| `object_type` | 是 | 支持对象类型 |
| `object_id` | 是 | 对象 ID |
| `object_version` | 是 | 被检查版本 |
| `template_id` | 是 | 检查模板 |
| `status` | 是 | pending/pass/fail/waived |
| `reviewer_id` | 条件 | PASS/FAIL/waived 必填 |
| `findings` | 否 | 问题记录 |
| `blockers` | 否 | 阻断项 |
| `waiver_reason` | 条件 | waived 必填 |
| `waiver_expires_at` | 条件 | waived 必填 |
| `created_at` | 是 | 创建时间 |
| `completed_at` | 条件 | 完成时间 |

## 阻断规则

- `fail` 阻断冻结和发布。
- `waived` 必须记录业务批准人、原因、有效期、风险。
- 同一对象新版本必须重新检查。
- API 无审计或错误不可追踪，阻断。
- 数据源无 source health 或 run counters，阻断。
- 算法输出无输入 refs 或版本，阻断。
- 多媒体输出未脱敏或直接当事实，阻断。
- Agent Profile 无证据或未复核，阻断。
- Council 输出 schema invalid 或无证据结论，阻断。
- 报告 claim validation failed，阻断。
- 前端页面存在 mock 数据、状态缺失、截图 diff 失败，阻断。
- 高危越权或敏感信息泄露，阻断。

## 模板版本

Review template 必须版本化。模板变化不影响已完成 review，但新对象版本必须使用最新有效模板。
