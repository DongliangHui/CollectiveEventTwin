# WORLDLINE OBSERVER 内部工程 Demo 流程说明

## 固定演示对象

- Case：`CASE-IRAN-001 / iran-war-escalation`
- 主线：`ML-001 霍尔木兹通航受限与能源外溢主线`
- 信号：`SIG-001 / SIG-012 / SIG-017`
- World State：`WS-001`
- 推演节点：`NODE-C3 通航限制升级风险`
- 多方研判：`COUNCIL-001`
- 汇报：`REPORT-001`

运行时数据来自 `mock/fixtures/demo-data.json`，接口由 `mock/mock-api.js` 模拟。页面之间通过 query 参数和 `localStorage.worldline-observer-demo-state` 保持状态。

## 黄金路径

1. `risk-dashboard.html`
   - 接收：`caseId`
   - 主任务：发现霍尔木兹热区和高价值弱信号。
   - 输出：`regionId=hormuz、mainlineId=ML-001、signalId=SIG-001`
   - 关键接口：`getDashboard、getMapLayers、getMapFeatureDetail`

2. `data-hub.html`
   - 接收：`regionId、mainlineId、signalId`
   - 主任务：查看信号详情、证据片段、推荐理由，并加入主线草稿。
   - 输出：`selectedSignalIds=[SIG-001,SIG-012,SIG-017]`
   - 关键接口：`searchSignals、getSignalDetail、getRecommendations`

3. `mainline-builder.html`
   - 接收：`mainlineId、signalId`
   - 主任务：解释为什么信号能成线，确认诱因、支点和证据缺口。
   - 输出：`worldStateId=WS-001`
   - 关键接口：`getMainline、confirmMainline`

4. `worldline-observer.html`
   - 接收：`mainlineId、worldStateId、nodeId`
   - 主任务：展示未来分支，默认聚焦 `NODE-C3`，说明为什么建议进入 Agent Council。
   - 输出：`selectedNodeId=NODE-C3`
   - 关键接口：`getWorldline、runCouncil`

5. `agent-council.html`
   - 接收：`mainlineId、nodeId、councilId`
   - 主任务：模拟主体反应，生成支点变化和概率变化。
   - 输出：`councilStatus=injected`
   - 关键接口：`runCouncil、injectCouncilResult`

6. `decision-brief.html`
   - 接收：`reportId、mainlineId`
   - 主任务：交付最终判断、行动建议、报告文档和任务跟踪。
   - 输出：`reportStatus=completed、actionTracking=started`
   - 关键接口：`getReport、updateTask`

## 状态约定

- `signal.status`：`raw / tagged / selected_for_mainline / confirmed_evidence`
- `mainline.status`：`pending_confirmation / confirmed / confirmed_with_gaps / world_state_ready`
- `worldlineNode.status`：`generated / selected / agent_council_recommended / agent_reviewed / rerun_applied`
- `council.status`：`draft / completed / ready_to_inject / injected`
- `task.status`：`suggested / in_progress / completed / overdue`

## 验收标准

- 从驾驶舱开始能一路点击到汇报页，不能出现死链、空状态、旧城市治理文案或状态丢失。
- 霍尔木兹地图弹窗的“查看详情”必须进入数据页，并携带 `regionId=hormuz&mainlineId=ML-001&signalId=SIG-001`。
- 数据页点击“加入主线草稿”后，主线页能按 `ML-001` 继续。
- 主线页确认后进入推演页，推演页启动 Agent Council 后能生成 `COUNCIL-001`。
- Agent Council 注入后返回推演页，汇报页能展示 `REPORT-001`、单文件导出、批量导出和任务更新。
