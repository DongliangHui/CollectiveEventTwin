# 02 工作流、Agent 与 LLM Runtime 源码深读

研究根目录：`E:\GitHub\ref_prj`

目标：把“多 Agent 研判”和“LLM 能力”落成生产后端代码，而不是前端演示状态。CollectiveEventTwin 的长流程必须由 durable workflow 承载；Agent 输出必须结构化、可追溯、可评测、可复核。

## CollectiveEventTwin 落地点

- Temporal 是主工作流：数据采集、清洗、媒体分析、信号生成、世界线构建、Agent Council、报告生成、第三方检查都必须是可重试 workflow/activity。
- Agent Profile 在创建世界线时生成：基于利益方识别结果，准备 `user.md`、`soul.md`、`agent.md` 等价字段，持久化版本和 prompt hash。
- LLM Gateway 是后端服务：统一 provider、timeout、retry、fallback、cost、trace，不允许前端直连模型。
- 所有 LLM 输出必须走 Pydantic schema、Guardrail、evidence ref 校验、blocked claims 校验。
- 多 Agent Council 结果不能直接当事实，必须落 `agent_runs`、`agent_messages`、`agent_claims`、`evidence_refs`、`third_party_reviews`。

## 项目深读

### Temporal Server

- 关联到本项目：durable workflow 历史、状态机、update/signal、重试和 worker versioning。
- 它怎么实现：服务端围绕 workflow execution history 和 task state machine 维护可恢复状态，worker 只执行可重放任务。
- 源码锚点：`temporal/service/history/workflow/workflow_task_state_machine.go`，`temporal/service/history/workflow_rebuilder.go`，`temporal/service/history/workflow/update`。
- 短代码片段：`workflow_task_state_machine`；`workflow_rebuilder`；`workflow/update`。
- 我们怎么用：生产主链路由 Temporal 承载；本项目数据库保存业务状态和审计，不重复实现 workflow engine。

### temporal-sdk-python

- 关联到本项目：Python worker、workflow/activity 定义、sandbox、replay、testing。
- 它怎么实现：workflow class 用 `@workflow.defn` 和 `@workflow.run` 定义，workflow 通过 `execute_activity` 调用外部 activity，worker 注册 workflows/activities。
- 源码锚点：`temporal-sdk-python/temporalio/workflow.py`，`temporal-sdk-python/temporalio/worker/_worker.py`，`temporal-sdk-python/temporalio/worker/_workflow_instance.py`。
- 短代码片段：`def defn(...)`；`@workflow.run`；`async def execute_activity(...)`；`class Worker:`。
- 我们怎么用：`apps/worker` 的业务工作流直接参考 Python SDK 模式；每个业务 workflow 都配 replay/timeout/retry 单测。

### Hatchet

- 关联到本项目：AI/background workflow 的开发者体验、worker 注册、runs/workers/crons 可见性。
- 它怎么实现：workflow、worker、context、CLI runs/workers/crons 分层，强调任务运行记录和后台 worker 可观测。
- 源码锚点：`hatchet/pkg/worker/workflow.go`，`hatchet/pkg/worker/worker.go`，`hatchet/cmd/hatchet-cli/cli/runs.go`，`hatchet/cmd/hatchet-cli/cli/worker.go`。
- 短代码片段：`pkg/worker/workflow.go`；`pkg/worker/worker.go`；`cli/runs.go`。
- 我们怎么用：借鉴 workflow run 可见性和后台任务 UX；不替代 Temporal。

### Dagster

- 关联到本项目：数据资产、作业图、asset/materialization 语义、backfill。
- 它怎么实现：以 definitions、assets、ops/jobs 管理数据管道，强调数据资产状态而不只是任务执行。
- 源码锚点：`dagster/python_modules/dagster/dagster/_core/definitions`，`dagster/python_modules/dagster/dagster/_core/execution`。
- 短代码片段：`definitions`；`execution`；`assets`。
- 我们怎么用：数据质量、清洗产物、城市态势缓存可借鉴“资产状态”；P0 不引入 Dagster 调度。

### Prefect

- 关联到本项目：flow/task 装饰器、状态对象、runner、失败重试、用户可读运行状态。
- 它怎么实现：`@flow`、`@task` 是用户侧 API，底层 flow/task engine 维护 async 执行和 state。
- 源码锚点：`prefect/src/prefect/flows.py`，`prefect/src/prefect/tasks.py`，`prefect/src/prefect/states.py`，`prefect/src/prefect/flow_engine.py`。
- 短代码片段：`@flow`；`@task`；`class State`；`flow_engine.py`。
- 我们怎么用：借鉴状态命名和错误暴露；实际执行由 Temporal。

### Airflow

- 关联到本项目：批处理 DAG、调度依赖、任务重试、运维 UI 的成熟模式。
- 它怎么实现：DAG 描述依赖图，scheduler/executor 分离执行，适合批处理而不是交互式产品请求。
- 源码锚点：`airflow/airflow-core/src/airflow/models/dag.py`，`airflow/airflow-core/src/airflow/jobs/scheduler_job_runner.py`。
- 短代码片段：`DAG`；`scheduler_job_runner`；`airflow-core/src/airflow`。
- 我们怎么用：只借鉴批处理依赖图和运维概念；不作为 P0 产品主链路。

### LangGraph

- 关联到本项目：Agent 状态图、多步骤推理、可恢复节点、分支条件、checkpoint。
- 它怎么实现：用 `StateGraph` 定义状态 schema，加 node/edge 后 compile；Pregel runtime 负责图执行和 checkpoint。
- 源码锚点：`langgraph/libs/langgraph/langgraph/pregel/main.py`，`langgraph/libs/langgraph/tests/test_type_checking.py`，`langgraph/examples/rag/langgraph_adaptive_rag.ipynb`。
- 短代码片段：`StateGraph(State)`；`add_node("retrieve", retrieve)`；`compile()`。
- 我们怎么用：Agent Council 内部可借鉴状态图，但生产调度仍由 Temporal；状态图结果必须持久化到 `agent_runs`。

### AutoGen

- 关联到本项目：多 Agent group chat、assistant/user proxy、round-robin/selector/swarm、human-in-the-loop。
- 它怎么实现：agentchat 包定义 agent、team、message、termination condition，group chat 管理多个 agent 的回合。
- 源码锚点：`autogen/python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py`，`autogen/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_round_robin_group_chat.py`，`autogen/python/packages/autogen-agentchat/src/autogen_agentchat/conditions/_terminations.py`。
- 短代码片段：`AssistantAgent(...)`；`RoundRobinGroupChat`；`TerminationCondition`。
- 我们怎么用：借鉴多角色协作和终止条件；我们的 agent 角色由世界线利益方生成，不固定写死。

### CrewAI

- 关联到本项目：Agent/Crew/Task 角色协作、任务描述、输出约束、LangGraph adapter。
- 它怎么实现：`Crew` 聚合多个 `Agent` 和 `Task`，adapter 可把 Agent 执行映射到 LangGraph workflow。
- 源码锚点：`crewAI/lib/crewai/src/crewai/crew.py`，`crewAI/lib/crewai/src/crewai/agent/core.py`，`crewAI/lib/crewai/src/crewai/task.py`，`crewAI/lib/crewai/src/crewai/agents/agent_adapters/langgraph/langgraph_adapter.py`。
- 短代码片段：`class Crew(...)`；`class Agent(...)`；`class Task(BaseModel):`；`Set up the LangGraph workflow graph`。
- 我们怎么用：借鉴 role/task/output 的组织；不把 CrewAI 作为黑盒执行器，避免证据绑定和审计不可控。

### agency-agents-zh

- 关联到本项目：`user.md`、`soul.md`、`agent.md` 风格的 Agent 人格、背景、立场、处事逻辑、权衡方式。
- 它怎么实现：每个 agent markdown 有 front matter、身份与记忆、使命、工作流程、规则、输出物、失败处理。
- 源码锚点：`agency-agents-zh/testing/testing-reality-checker.md`，`agency-agents-zh/legal/legal-policy-writer.md`，`agency-agents-zh/engineering/engineering-backend-architect.md`，`agency-agents-zh/CATALOG.md`。
- 短代码片段：`name: 现实检验者`；`## 身份与记忆`；`## 工作流程`；`## 输出物`。
- 我们怎么用：实现 `AgentProfile` 模型：`background`、`stance`、`decision_logic`、`constraints`、`evidence_policy`、`conflict_weights`、`review_protocol`。

### LiteLLM

- 关联到本项目：统一 LLM provider、fallback、成本、日志、router、pass-through endpoint。
- 它怎么实现：主入口封装 completion/embedding 等能力，router 和 fallback utils 负责模型选择、失败降级和日志回调。
- 源码锚点：`litellm/litellm/main.py`，`litellm/litellm/router.py`，`litellm/litellm/litellm_core_utils/fallback_utils.py`，`litellm/litellm/cost_calculator.py`。
- 短代码片段：`def completion(...)`；`class Router`；`fallback_utils.py`；`cost_calculator.py`。
- 我们怎么用：实现项目内 `LLMProviderGateway`；记录 provider/model/prompt_hash/token/cost/latency/error，不让业务代码到处调模型 SDK。

### Instructor

- 关联到本项目：Pydantic structured output、schema 驱动解析、非法 JSON 修复/重试。
- 它怎么实现：patch client create 方法，增加 `response_model`，用 Pydantic schema 验证模型返回。
- 源码锚点：`instructor/instructor/core/patch.py`，`instructor/instructor/processing/response.py`，`instructor/instructor/cache/__init__.py`。
- 短代码片段：`response_model: type[T_Model] | None = None`；`handle_response_model(...)`；`model_validate_json(...)`。
- 我们怎么用：所有 Agent 输出定义 Pydantic schema；schema validation fail 不能吞掉，必须进入 `agent_run_failures`。

### Guardrails

- 关联到本项目：输出验证、re-ask、约束失败、validation outcome。
- 它怎么实现：Guard 对 LLM output 调 `validate/avalidate`，validator service 返回 ValidationOutcome，失败可触发 reask。
- 源码锚点：`guardrails/guardrails/guard.py`，`guardrails/guardrails/api_client.py`，`guardrails/guardrails/actions/reask.py`，`guardrails/guardrails/validator_base.py`。
- 短代码片段：`def validate(self, llm_output, ...)`；`async def avalidate`；`ReAsk.model_validate(obj)`。
- 我们怎么用：实现 `AgentOutputGuard`：证据引用存在、claim 有来源、禁止越权结论、敏感信息已脱敏、schema version 匹配。

## Agent Council 实现方案

1. `WorldlineBuildWorkflow` 先从证据和图谱中识别利益方：居民、社区、街办、住建/人社、媒体、平台、潜在组织者、第三方专家。
2. `StakeholderAgentFactory` 为每个利益方生成 `AgentProfile`，包括背景、立场、目标函数、风险偏好、证据偏好、冲突权重。
3. `AgentPromptMaterializer` 把 profile 物化为 `user.md/soul.md/agent.md` 等价文本，并记录 `prompt_version` 与 `prompt_hash`。
4. `CouncilWorkflow` 逐 agent 运行：事实摘要 -> 立场判断 -> 风险权衡 -> 证据引用 -> 反方质询 -> 修正。
5. `CouncilAdjudicator` 合并结论：只接受证据支持的 claims；unsupported claims 写入 `blocked_claims`。
6. `ThirdPartyReviewWorkflow` 独立检查：schema、证据有效性、偏见/遗漏、结论强度、是否越权。

## 转成开发任务

| 任务 | 不可再拆的功能点 | 验收点 |
| --- | --- | --- |
| `LLMProviderGateway` | provider/model/fallback/cost/trace 统一入口 | 模型成功、超时、限流、fallback、成本记录单测 |
| `AgentProfile` 数据模型 | 保存背景、立场、逻辑、约束、证据策略 | profile version/prompt hash 可回放 |
| `StakeholderAgentFactory` | 从世界线利益方生成 agent profiles | 缺利益方时阻断 Council，不默认补假角色 |
| `AgentPromptMaterializer` | 生成 user/soul/agent 文本 | 生成内容入库并带 schema/version |
| `AgentRunService` | 创建 agent run、messages、claims | 每条 claim 必须绑定 evidence_refs |
| `AgentOutputGuard` | schema/evidence/policy 校验 | 非法 JSON、缺证据、越权结论均失败 |
| `CouncilWorkflow` | 多 agent 研判流程 | 任一 agent 失败可见，整体状态可查询 |
| `CouncilAdjudicator` | 汇总支持/反对/冲突 claims | unsupported claims 不进入正式结论 |
| `ThirdPartyReviewWorkflow` | 独立检查 agent/report 输出 | 实现者自测无法把结果标记 frozen |
