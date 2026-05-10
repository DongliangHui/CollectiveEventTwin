# LLM 输出 Schema 规范 v1.0

状态：冻结版

## 调用记录

每次 LLM 调用必须写 `llm_calls`：

- `provider_id`
- `model`
- `prompt_template_id`
- `prompt_version`
- `schema_version`
- `input_refs`
- `status`
- `tokens`
- `cost`
- `latency_ms`
- `error_code`
- `trace_id`

## 通用输出结构

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

## 校验顺序

1. JSON/schema 校验。
2. `schema_version` 校验。
3. `evidence_refs` 存在性和权限校验。
4. claim 与 evidence refs 对齐校验。
5. blocked claims 识别。
6. 输出对象入库。
7. 创建 review 或进入下游状态机。

## 禁止行为

- LLM 失败后静默 fallback 成正式结论。
- 无 evidence refs 的事实声明进入报告。
- schema invalid 的 Council Result 进入 applied。
- Agent Profile 未经 review 进入 Council run。
- Fake LLM provider 用于产品运行时。

## 失败状态

| 场景 | 错误码 | 后续 |
| --- | --- | --- |
| provider timeout | `DEPENDENCY_UNAVAILABLE` | retry queue |
| schema invalid | `SCHEMA_INVALID` | blocked/fail |
| evidence ref missing | `EVIDENCE_REF_MISSING` | blocked |
| unsupported claim | `CLAIM_BLOCKED` | blocked_claims |
