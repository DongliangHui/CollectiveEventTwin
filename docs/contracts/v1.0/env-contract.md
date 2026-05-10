# 验收环境规范 v1.0

状态：冻结版

## 环境分层

| 环境 | 用途 | 数据 |
| --- | --- | --- |
| `dev` | 本地开发 | 可重置合成/测试数据 |
| `test` | 自动化测试 | 测试 fixture 和 fake LLM provider |
| `staging` | 发布前验收 | 标记合成数据，不使用 fake LLM provider 作为正式结论 |
| `prod` | 生产 | 仅授权数据，禁止测试 fixture 和 fake LLM provider |

## 隔离规则

- 不同环境使用不同数据库、Redis、Temporal namespace 和对象存储 bucket。
- `AUTO_CREATE_TABLES` 只允许 dev/test 使用。
- prod/staging 必须使用 Alembic migration。
- fake LLM provider 仅限 test。
- 合成数据可进 dev/staging，但必须带标记。

## 验收前置

- `GET /api/v1/ops/health/api` 返回 ok。
- `GET /api/v1/ops/health/db` 返回 ok 和 migration revision。
- `GET /api/v1/ops/health/workers` 能看到 worker 状态。
- `GET /api/v1/ops/metrics` 能看到 API/DB/workflow/LLM 指标。
