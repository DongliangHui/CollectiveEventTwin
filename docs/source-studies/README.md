# 开源项目源码深读索引

日期：2026-05-09

本目录是 `technical-reference-open-source-solution-landscape-20260508.md` 后续的源码级研究交付物。当前本地研究根目录为：

```text
E:\GitHub\ref_prj
```

这里覆盖 69 个本地仓库：技术雷达中的 67 个 GitHub 项目，加上 `agency-agents-zh` 与 `temporal-sdk-python` 两个补充项目。它们是实现参考，不是默认生产依赖。后续任何功能开发如果借鉴这些项目，必须回到对应源码锚点确认实现边界，并把 CollectiveEventTwin 自己的数据库、审计、证据、权限、工作流和第三方检查作为生产事实源。

## 文档拆分

| 文档 | 覆盖项目数 | 对应本项目能力 |
| --- | ---: | --- |
| `05-local-reference-projects.md` | 2 extra local snapshots | MiroFish worldline/Agent/report/page-state patterns and worldmonitor multi-source health/map/API/test patterns; not part of the original 69-repository count |
| `01-data-ingestion-and-sources.md` | 15 | 数据源采集、渠道适配、流式/批式接入、清洗前原始记录入库 |
| `02-workflow-agent-llm.md` | 13 | Temporal 工作流、多 Agent 研判、LLM 网关、结构化输出与约束 |
| `03-search-graph-geospatial.md` | 21 | 检索/RAG、案例图谱、世界线图算法、城市空间态势 |
| `04-multimedia-policy-quality-observability.md` | 20 | 视频/图片/OCR/ASR、隐私脱敏、权限策略、质量评测、观测看板 |

## 使用规则

1. 开发任务引用这些项目时，先打开对应深读文档，再打开本地源码锚点，不直接凭项目名想象实现。
2. “短代码片段”只保留 1 到 3 行关键形态，完整实现以本地源码为准。
3. POC 项目不能直接进入生产主链路；必须经过 TR1 架构复核、测试用例设计、性能测试和第三方检查。
4. 合规、隐私、反爬、平台授权、模型输出真实性不能通过参考项目背书，必须落在本项目自己的 `SourcePolicyService`、`AuditLog`、`EvidenceReview` 和 `ThirdPartyReview`。
5. 用户可见页面不能只做前端状态变化。页面上每个交互都必须有后端 API、数据库记录、审计或可回放工作流支撑。

## 对后续开发的直接约束

- 数据采集：按渠道拆 `SourceAdapter`，每个渠道有独立配置、授权策略、失败类型、重试策略、去重键和原始记录格式。
- 算法能力：去重、实体抽取、证据评分、风险因子、图算法、空间聚合、世界线分支、多 Agent 研判全部属于后端真实代码。
- Agent 能力：世界线创建时先识别利益方，再生成对应 `AgentProfile`，物化 `user.md`、`soul.md`、`agent.md` 风格内容，并要求每条 claim 绑定证据。
- 多媒体能力：视频、直播、图片、截图、OCR、ASR 进入异步 `MediaAnalysisWorkflow`，不能阻塞 API 请求，也不能绕过人工复核。
- 质量门禁：每项输出都要第三方检查；实现者自测不等于冻结。
