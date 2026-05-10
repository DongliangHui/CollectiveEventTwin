# 证据引用规范 v1.0

状态：冻结版

## 引用格式

```json
{
  "object_type": "evidence",
  "object_id": "ev_...",
  "object_version": "v1",
  "excerpt_hash": "sha256:...",
  "span": {
    "start": 0,
    "end": 120
  },
  "confidence": 0.82
}
```

## 允许引用的对象

- `raw_record`
- `media_asset`
- `media_processing_run`
- `signal`
- `evidence`
- `risk_factor`
- `mainline_node`
- `worldline_node`
- `council_message`
- `report_claim`

## 必须引用证据的输出

- Signal 诉求识别、情绪识别、传播特征。
- Evidence 候选和复核结论。
- RiskFactor。
- Mainline 节点和质量检查。
- Worldline 节点、概率、转向、intervention diff。
- Agent Profile 立场和约束。
- Council 单 Agent 输出、多 Agent 合并、分歧点。
- ReportClaim。
- Task 建议。

## 校验规则

- 引用对象必须存在且同租户可见。
- `confirmed` Evidence 才能支撑正式事实。
- `probability_reference_only` 只能用于概率参考。
- 引用被删除、归档或版本变化时，下游对象必须重新校验或标记 degraded。
- 缺失引用返回 `EVIDENCE_REF_MISSING`。
