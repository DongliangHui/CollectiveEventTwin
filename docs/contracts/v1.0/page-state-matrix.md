# 页面状态矩阵 v1.0

状态：冻结版

## 通用状态

所有页面 view-model 必须支持：

- `loading`
- `ready`
- `empty`
- `error`
- `degraded`
- `no_permission`

## 必测状态矩阵

| 页面 | 必测状态 |
| --- | --- |
| 登录页 | 空账号、空密码、账号不存在、密码错误、账号禁用、连续失败锁定、登录成功、服务不可用 |
| 城市态势页 | loading、empty、error、source degraded、filter no result、selected event、map tile fail、media processing、no permission |
| 主题态势页 | loading、empty topic、topic building、source degraded、no signal、video processing、emotion unavailable、candidate mainline empty、selected signal source、error、no permission |
| 数据/信号页 | search success、no result、signal detail、lineage missing、draft add/remove、permission denied、run failed |
| 事件/证据复核页 | review object loading、raw content unavailable、media pending、media failed、source chain missing、truth review pending、emotion review pending、spread review pending、review completed、review conflict、sensitive redacted、no permission |
| 主线建模页 | draft、quality failed、pending confirmation、confirmed、version diff、node edit conflict、evidence gap |
| 世界线推演页 | run pending、running、completed、failed、intervention diff、node detail、superseded |
| Agent Council 页 | session created、profile checking、running、provider error、schema invalid、blocked claims、completed、applied |
| 汇报输出页 | draft、claim validation failed、submitted review、review returned、approved、published、export failed |
| 复盘知识沉淀页 | retrospective draft、case data missing、prediction not comparable、model update pending、review failed、knowledge item duplicated、approved for memory、published to case library |
| 主题/案例库页 | library empty、search no result、case selected、case archived、case pending review、template selected、apply suggestion conflict、no permission |
| 数据源与模型配置页 | config loading、source unhealthy、source policy blocked、model version conflict、regression running、regression failed、approval pending、published、rollback available、rollback failed |

## 验收规则

- 每个状态必须可通过 query、fixture seed、API failure injection 或 Playwright route control 稳定复现。
- 客户可见页面状态必须有截图基线。
- `error` 状态必须显示 trace_id。
- `degraded` 状态必须显示 degraded source 或依赖原因。
- `no_permission` 状态不得泄露对象详情。
