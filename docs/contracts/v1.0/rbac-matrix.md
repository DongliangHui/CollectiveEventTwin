# RBAC 权限矩阵 v1.0

状态：冻结版

## 角色

| 角色 | 定位 |
| --- | --- |
| `system_admin` | 系统级运维和租户管理 |
| `tenant_admin` | 租户内用户、角色、配置管理 |
| `analyst` | 议题、信号、证据、主线、世界线分析 |
| `reviewer` | 第三方检查、证据复核、报告审阅 |
| `operator` | 任务处置、运行监控、导出 |
| `viewer` | 只读查看客户可见页面 |
| `qa_reviewer` | 测试验收、视觉基线、发布门禁检查 |

## 页面权限

| 页面 | system_admin | tenant_admin | analyst | reviewer | operator | viewer | qa_reviewer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 登录页 | use | use | use | use | use | use | use |
| 城市态势页 | view | view | view/create_topic | view | view | view | view/test |
| 主题态势页 | view | view | view/edit | view | view | view | view/test |
| 数据/信号页 | view | view | view/edit/package | view | view | view | view/test |
| 证据复核页 | view | view | view | review | view | view_masked | view/test |
| 主线建模页 | view | view | edit/confirm | review | view | view | view/test |
| 世界线推演页 | view | view | run/intervene | review | view | view | view/test |
| Agent Council 页 | view | view | run/apply_after_review | review | view | view | view/test |
| 汇报输出页 | view | view | draft/edit | review | publish/export/task | view | view/test |
| 复盘页 | view | view | draft | review | view | view | view/test |
| 案例库页 | view | manage | apply | review | view | view | view/test |
| 配置页 | manage | manage_tenant | view | review | view | no | test |

## 动作权限

| 动作 | 权限码 |
| --- | --- |
| 创建主题 | `topic:create` |
| 编辑主题 | `topic:update` |
| 运行采集 | `collection:run` |
| 标记 raw record | `raw_record:label` |
| 创建/编辑信号包 | `signal_package:write` |
| 复核证据 | `evidence:review` |
| 确认风险因子 | `risk_factor:confirm` |
| 确认主线 | `mainline:confirm` |
| 运行世界线 | `worldline:run` |
| 复核利益方 | `stakeholder:review` |
| 生成 Agent Profile | `agent_profile:create` |
| 运行 Council | `council:run` |
| 应用 Council Result | `council:apply` |
| 提交/通过 Review | `review:write` |
| 发布报告 | `report:publish` |
| 导出报告 | `report:export` |
| 发布配置 | `config:publish` |
| 回滚配置 | `config:rollback` |

## 数据权限

- 所有查询必须按 `tenant_id` 隔离。
- `viewer` 默认只能看 masked evidence 和 published/approved 对象。
- `analyst` 可编辑 draft/pending 对象，不能通过第三方 review。
- `reviewer` 可 PASS/FAIL，但不能绕过业务状态机。
- `operator` 可操作任务和导出，但不能修改证据事实。
- `qa_reviewer` 可创建验收 review，不能改变生产业务结论。
