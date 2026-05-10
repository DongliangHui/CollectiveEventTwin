# 截图基线规范 v1.0

状态：冻结版

## 范围

客户可见页面冻结前必须建立视觉基线：

- 城市态势页。
- 主题态势页。
- 数据/信号页。
- 证据复核页。
- 主线建模页。
- 世界线推演页。
- Agent Council 页。
- 汇报输出页。
- 复盘页。
- 案例库页。
- 配置页。

## Viewports

- Desktop：1440 x 900。
- Laptop：1366 x 768。
- Mobile：390 x 844，若页面不支持移动操作，仍需验证无严重重叠。

## Routeable state

每个页面状态必须能用 route/query/test seed 稳定复现：

- loading。
- empty。
- error。
- degraded。
- no permission。
- 该页面关键 selected/detail/edit 状态。

## Diff 规则

- 视觉基线由 Playwright 或内部浏览器生成。
- 截图保存在约定 baseline 目录，文件名包含 route、state、viewport。
- Diff 失败返回 `VISUAL_BASELINE_FAILED`。
- 前端页面存在 runtime mock、状态缺失或关键文案遮挡时，review 必须 FAIL。

## 冻结条件

- 真实路由可打开。
- 控件真实点击可执行。
- network 无未解释业务 API failure。
- console 无 React runtime error。
- 截图 diff PASS。
- `frontend_page` review PASS 或批准豁免。
