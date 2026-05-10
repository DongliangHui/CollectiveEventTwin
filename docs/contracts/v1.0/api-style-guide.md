# API 命名规范 v1.0

状态：冻结版

## 基础规则

- 所有正式业务 API 使用 `/api/v1` 前缀。
- 页面级聚合 API 使用 `*-view` 或语义化聚合名，如 `/overview`、`/situation-view`、`/brief-view`。
- 列表使用复数资源名：`/topics`、`/reviews`、`/workflow-runs`。
- 单对象使用 `/{resource_id}`。
- 动作型 mutation 使用子资源或动作端点：`/confirm`、`/publish`、`/retry`、`/gate-check`。
- 不使用前端页面名作为数据对象名，除非该 API 是明确 view-model。

## 响应 Envelope

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

## 分页和筛选

- 分页参数固定为 `page`、`page_size`。
- `page` 从 1 开始。
- `page_size` 默认 50，最大 200。
- 列表响应 `meta` 必须包含 `page`、`page_size`、`total`。
- 筛选参数必须传给后端，前端不得绕过 view-model 形成正式业务判断。

## Mutation 要求

所有 mutation 必须：

- 校验认证和权限。
- 校验状态机。
- 写 `audit_logs`。
- 返回最新对象或状态快照。
- 返回 `trace_id`。
- 对状态冲突返回 409 `STATE_CONFLICT`。
- 对字段或 schema 失败返回 422 `VALIDATION_ERROR`。

## 长任务要求

所有长任务必须：

- 创建 run 记录。
- 写 workflow/activity 状态。
- 记录失败原因。
- 支持查询。
- 区分可重试和不可重试错误。
- 幂等边界使用 `case/topic/run/object id` 与 `input_hash`。

## 状态码

| HTTP | 用途 |
| --- | --- |
| 200 | 查询或同步 mutation 成功 |
| 201 | 对象或 run 创建成功 |
| 400 | 请求语义错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 对象不存在 |
| 409 | 状态冲突、重复提交、版本冲突 |
| 422 | 字段或 schema 校验失败 |
| 429 | 限流 |
| 500 | 内部错误 |
| 503 | DB、worker、LLM、外部依赖不可用 |
