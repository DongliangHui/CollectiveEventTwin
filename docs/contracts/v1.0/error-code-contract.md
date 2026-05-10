# 错误码规范 v1.0

状态：冻结版

## HTTP 到业务 code

| HTTP | 业务 code | 语义 | 前端处理 |
| --- | --- | --- | --- |
| 400 | `BAD_REQUEST` | 请求语义错误 | 显示请求错误 |
| 401 | `UNAUTHENTICATED` | 未登录或 token 无效 | 回登录页 |
| 403 | `FORBIDDEN` | 无权限 | 显示 no_permission |
| 404 | `NOT_FOUND` | 对象不存在 | 显示 empty/error |
| 409 | `STATE_CONFLICT` | 状态冲突、重复提交、版本冲突 | 显示冲突并刷新对象 |
| 422 | `VALIDATION_ERROR` | 字段或 schema 校验失败 | 展示字段/检查项 |
| 429 | `RATE_LIMITED` | 限流 | 显示重试时间 |
| 500 | `INTERNAL_ERROR` | 内部错误 | 显示 trace_id |
| 503 | `DEPENDENCY_UNAVAILABLE` | DB、worker、LLM、外部依赖不可用 | 显示 degraded/error |

## 特殊 code

| Code | 使用场景 | 阻断 |
| --- | --- | --- |
| `SOURCE_POLICY_BLOCKED` | 数据源策略阻断 | 不创建 collection run |
| `SOURCE_UNHEALTHY` | 数据源不可用 | page_state degraded |
| `RUN_NOT_RETRYABLE` | 不可重试 run 失败 | 进入 error queue |
| `SCHEMA_INVALID` | LLM/API/schema 输出无效 | 阻断 downstream |
| `EVIDENCE_REF_MISSING` | 证据引用缺失或越权 | 阻断结论 |
| `CLAIM_BLOCKED` | 无证据 claim | 进入 blocked_claims |
| `REVIEW_REQUIRED` | 需要第三方检查 | 阻断冻结/发布 |
| `CLAIM_VALIDATION_FAILED` | 报告声明校验失败 | 阻断提交审阅 |
| `VISUAL_BASELINE_FAILED` | 视觉基线失败 | 阻断页面冻结 |

## 失败响应格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable message",
    "details": {
      "field": "status",
      "expected": ["draft", "pending_confirmation"]
    }
  },
  "trace_id": "req_..."
}
```

所有错误必须可被 audit、ops 或 logs 通过 `trace_id` 追踪。
