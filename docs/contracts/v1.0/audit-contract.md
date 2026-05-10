# 审计对象规范 v1.0

状态：冻结版

## 审计记录结构

所有 mutation 必须写 `audit_logs`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `tenant_id` | 是 | 租户 |
| `actor_id` | 是 | 操作者 |
| `action` | 是 | 动作，如 `topic.create` |
| `object_type` | 是 | 对象类型 |
| `object_id` | 是 | 对象 ID |
| `object_version` | 否 | 对象版本 |
| `before` | 否 | 修改前快照 |
| `after` | 否 | 修改后快照 |
| `diff` | 否 | 差异 |
| `reason` | 条件必填 | 关键状态变更、豁免、发布、回滚必填 |
| `trace_id` | 是 | 请求链路 ID |
| `ip` | 否 | 客户端 IP |
| `user_agent` | 否 | 客户端 UA |
| `created_at` | 是 | 服务端时间 |

## 必审计动作

- 登录成功/失败、退出、刷新 token。
- 用户、角色、权限变化。
- 数据源创建、编辑、启停、策略校验。
- collection run 启动、取消、重试。
- raw record 标签。
- 证据复核、风险因子确认/驳回。
- 主线创建、编辑、质量检查、确认。
- World State 生成、世界线运行、intervention 注入。
- Stakeholder 复核、Agent Profile 生成和检查。
- Council 运行、schema 校验、应用。
- 报告创建、编辑、提交、退回、发布、导出。
- 任务创建和状态变化。
- 复盘、知识项、案例库发布。
- 配置版本创建、回归、发布、回滚。
- Review 创建、PASS、FAIL、waive。

## 审计阻断

以下情况必须阻断 mutation：

- 无 `actor_id`。
- 需要 reason 的动作未提供 reason。
- 状态机不允许的变更。
- `trace_id` 缺失。
- 高危动作无权限。
