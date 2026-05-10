# 04 多媒体、合规、质量与观测源码深读

研究根目录：`E:\GitHub\ref_prj`

目标：覆盖大量视频、直播、图片、截图、OCR、ASR、隐私脱敏、策略阻断、LLM/数据质量评测和运维观测。CollectiveEventTwin 的多媒体输出只能进入证据链和复核链，不能绕过事实校验直接形成结论。

## CollectiveEventTwin 落地点

- `MediaAnalysisWorkflow` 异步处理视频、图片、直播切片、截图、音频，不进入 API request path。
- 每个媒体产物必须记录 `source_record_id`、`media_asset_id`、`time_range`、`bbox/region`、`model_name`、`model_version`、`confidence`、`redaction_status`、`review_status`。
- OCR/ASR/CV 结果先成为 `evidence_candidates`，高风险结果默认 `needs_review`。
- 隐私策略、source policy、RBAC、审计日志、第三方检查是生产主线，不是后期补丁。
- LLM/Agent 评测要有 regression dataset、prompt hash、trace、evidence citation metric 和第三方 review record。

## 视频 / OCR / ASR 项目

### supervision

- 关联到本项目：目标检测结果标准化、区域计数、线穿越、视频/图片标注、检测结果导出。
- 它怎么实现：用 `Detections` 表示检测框/置信度/class id，提供 annotator、zone、sink 等后处理工具。
- 源码锚点：`supervision/src/supervision/detection/core.py`，`supervision/src/supervision/detection/tools/json_sink.py`，`supervision/src/supervision/detection/tools/csv_sink.py`，`supervision/src/supervision/detection/tools/polygon_zone.py`。
- 短代码片段：`class Detections`；`json_sink.py`；`polygon_zone.py`。
- 我们怎么用：实现 `VisionDetectionResult` 标准格式；区域计数/截图标注进入证据候选，不直接判定事件。

### Ultralytics

- 关联到本项目：目标检测模型候选、视频帧目标识别、人员/车辆/横幅等对象检测 POC。
- 它怎么实现：YOLO model class 统一 train/predict/val/export 等能力。
- 源码锚点：`ultralytics/ultralytics/models/yolo/model.py`，`ultralytics/ultralytics/engine/model.py`，`ultralytics/ultralytics/engine/results.py`。
- 短代码片段：`class YOLO(Model):`；`engine/results.py`；`predict`。
- 我们怎么用：模型候选，不默认生产依赖；必须建立本项目测试集和误报/漏报复核。

### RF-DETR

- 关联到本项目：DETR 系列目标检测候选，作为 YOLO 之外的视觉模型对照。
- 它怎么实现：不同模型规格继承 RFDETR base，variants 管 Nano/Small/Medium/Large。
- 源码锚点：`rf-detr/src/rfdetr/variants.py`，`rf-detr/src/rfdetr/detr.py`。
- 短代码片段：`class RFDETRBase(RFDETR):`；`class RFDETRSmall`；`class RFDETRLarge`。
- 我们怎么用：作为模型评估候选；只有在 FiftyOne/人工复核集上指标通过才可进入生产。

### PaddleOCR

- 关联到本项目：图片/视频帧 OCR、公告/截图/横幅/文档文字提取。
- 它怎么实现：检测、识别、方向分类分文件，`predict_system.py` 串联 det/rec/cls。
- 源码锚点：`PaddleOCR/tools/infer/predict_system.py`，`PaddleOCR/tools/infer/predict_det.py`，`PaddleOCR/tools/infer/predict_rec.py`，`PaddleOCR/tools/infer/predict_cls.py`。
- 短代码片段：`predict_system.py`；`predict_det.py`；`predict_rec.py`。
- 我们怎么用：`OcrAnalysisActivity` 输出 text spans、bbox、confidence、language、review_status。

### FunASR

- 关联到本项目：中文 ASR、直播/视频音频转写、会议/现场音频证据。
- 它怎么实现：AutoModel 封装模型加载和推理，utils 处理时间戳、tokenizer、vad 等。
- 源码锚点：`FunASR/funasr/auto/auto_model.py`，`FunASR/funasr/utils/timestamp_tools.py`，`FunASR/funasr/models`。
- 短代码片段：`AutoModel`；`timestamp_tools.py`；`funasr/models`。
- 我们怎么用：中文音频优先候选；转写内容必须带时间戳和置信度，敏感内容先脱敏。

### WhisperX

- 关联到本项目：ASR 时间戳对齐、说话人/片段级证据定位。
- 它怎么实现：`transcribe` 先转写，`align` 对齐词级/片段级时间戳。
- 源码锚点：`whisperX/whisperx/asr.py`，`whisperX/whisperx/alignment.py`，`whisperX/whisperx/transcribe.py`。
- 短代码片段：`def transcribe(...)`；`def align(...)`；`transcribe_task(...)`。
- 我们怎么用：作为 ASR 对齐能力参考；输出必须写 `media_transcripts` 并绑定 media time range。

### FiftyOne

- 关联到本项目：视觉数据集评估、样本、标签、人工复核、误报漏报分析。
- 它怎么实现：Dataset/Sample/Label 抽象管理视觉数据集，App/工具支持查看和筛选。
- 源码锚点：`fiftyone/fiftyone/core/dataset.py`，`fiftyone/fiftyone/core/sample.py`，`fiftyone/fiftyone/core/labels.py`。
- 短代码片段：`class Dataset(...)`；`class Sample(...)`；`class Detections(...)`。
- 我们怎么用：建立内部视觉回归集和人工 review 集；不把模型 demo 结果当生产验收。

## 隐私 / 策略 / 权限项目

### Presidio

- 关联到本项目：PII 检测、文本匿名化、图片脱敏、敏感字段审计。
- 它怎么实现：AnalyzerEngine 负责识别，AnonymizerEngine 负责脱敏，image redactor 把分析结果映射到图片框。
- 源码锚点：`presidio/presidio-analyzer/presidio_analyzer/__init__.py`，`presidio/presidio-anonymizer/presidio_anonymizer/__init__.py`，`presidio/presidio-image-redactor`。
- 短代码片段：`AnalyzerEngine`；`AnonymizerEngine`；`image_redactor`。
- 我们怎么用：实现 `SensitiveInfoDetector` 和 `RedactionService`；原文可见性按 RBAC 和审计控制。

### OPA

- 关联到本项目：policy-as-code、source policy、数据出域/脱敏/操作阻断候选。
- 它怎么实现：Rego parser、topdown query evaluator、policy compiler。
- 源码锚点：`opa/rego/rego.go`，`opa/topdown/query.go`，`opa/ast/parser.go`。
- 短代码片段：`rego.go`；`topdown/query.go`；`ast/parser.go`。
- 我们怎么用：P1/P2 策略引擎候选；P0 先写项目内 `SourcePolicyService`，避免过早引入第二套规则语言。

### OpenFGA

- 关联到本项目：关系型授权、组织/部门/案例/证据可见性、跨租户共享候选。
- 它怎么实现：typesystem、tuple、validation 管 Zanzibar-style relationship authorization。
- 源码锚点：`openfga/pkg/typesystem/typesystem.go`，`openfga/pkg/tuple/tuple.go`，`openfga/internal/validation/validate.go`。
- 短代码片段：`typesystem.go`；`tuple.go`；`validate.go`。
- 我们怎么用：P1 多组织权限复杂后评估；P0 做内部 RBAC + row-level policy + audit。

### Casbin

- 关联到本项目：RBAC/ABAC 权限模型、policy enforcement、effect 合并。
- 它怎么实现：Enforcer 加载 model/policy，请求匹配后用 effector 合并 allow/deny。
- 源码锚点：`casbin/enforcer.go`，`casbin/model/model.go`，`casbin/rbac_api.go`，`casbin/effector/default_effector.go`。
- 短代码片段：`enforcer.go`；`rbac_api.go`；`default_effector.go`。
- 我们怎么用：可借鉴 model/enforcer 分层；P0 不强制引入库，先保证权限检查覆盖 API 和敏感字段。

## 质量 / 评测 / 观测项目

### Langfuse

- 关联到本项目：LLM trace、prompt version、dataset/eval、cost、replay。
- 它怎么实现：trace/session/dataset score 绑定，shared utils 校验 score 目标对象。
- 源码锚点：`langfuse/packages/shared/src/utils/scores.ts`，`langfuse/packages/shared`，`langfuse/web`。
- 短代码片段：`const hasTraceId = !!data.traceId`；`traceId`；`dataset`。
- 我们怎么用：实现 `LLMTrace` 表和 prompt/run replay；可后续接 Langfuse，不在 P0 强依赖。

### Phoenix

- 关联到本项目：LLM/RAG tracing、trace dataset、instrumentation、回放分析。
- 它怎么实现：导出 TraceDataset/register/instrumentor 等能力。
- 源码锚点：`phoenix/src/phoenix/__init__.py`，`phoenix/src/phoenix/trace`，`phoenix/packages/phoenix-evals/src/phoenix/evals`。
- 短代码片段：`TraceDataset`；`register()`；`phoenix/evals`。
- 我们怎么用：借鉴 trace dataset 和 eval；本项目先实现轻量 trace schema。

### DeepEval

- 关联到本项目：LLM/Agent 评测、trace/span、测试集执行、指标。
- 它怎么实现：tracing 模块提供 trace/span 生命周期，评测函数可绑定到运行上下文。
- 源码锚点：`deepeval/deepeval/tracing/__init__.py`，`deepeval/deepeval/tracing/tracing.py`。
- 短代码片段：`start_new_trace(...)`；`end_trace(...)`；`active_traces`。
- 我们怎么用：实现 Agent regression suite：证据引用率、unsupported claim rate、schema pass rate。

### Ragas

- 关联到本项目：RAG 评估、faithfulness、context recall/relevance、citation 质量。
- 它怎么实现：`src` 下组织 metrics、dataset schema、evaluation 执行。
- 源码锚点：`ragas/src/ragas`。
- 短代码片段：`metrics`；`evaluation`；`dataset_schema`。
- 我们怎么用：借鉴 RAG 指标；我们的评测必须加 evidence id validity 和 blocked claim rate。

### promptfoo

- 关联到本项目：prompt regression、RAG/Agent 测试、red team、断言体系。
- 它怎么实现：assertions 下有 json/latency/model-graded/context 断言，redteam command 生成和运行安全测试。
- 源码锚点：`promptfoo/src/assertions/json.ts`，`promptfoo/src/assertions/latency.ts`，`promptfoo/src/assertions/contextFaithfulness.ts`，`promptfoo/src/redteam/commands/run.ts`。
- 短代码片段：`json.ts`；`latency.ts`；`contextFaithfulness.ts`；`redteam/commands/run.ts`。
- 我们怎么用：实现 `AgentEvalSuite`；每次 prompt/schema 变更必须跑回归测试。

### Great Expectations

- 关联到本项目：数据质量规则、validation result、quarantine 阻断。
- 它怎么实现：Validator 执行 expectation，validation graph 管依赖和结果。
- 源码锚点：`great_expectations/great_expectations/validator/validator.py`，`great_expectations/great_expectations/validator/validation_graph.py`。
- 短代码片段：`class Validator:`；`class ExpectationValidationGraph:`。
- 我们怎么用：实现 `DataQualityGate`：必填字段、时间范围、source trust、geo validity、media metadata。

### Grafana

- 关联到本项目：系统指标、worker/workflow/API/LLM 成本、业务 counters 观测。
- 它怎么实现：后端 web、前端 routes、panel 插件、fetch utils 管 dashboards 和 panels。
- 源码锚点：`grafana/pkg/web/web.go`，`grafana/public/app/routes/routes.tsx`，`grafana/public/app/core/utils/fetch.ts`，`grafana/public/app/plugins/panel/xychart/XYChartPanel.tsx`。
- 短代码片段：`pkg/web/web.go`；`routes.tsx`；`XYChartPanel.tsx`。
- 我们怎么用：P0 暴露 Prometheus/metrics endpoint；P1 接 Grafana dashboard。

### Superset

- 关联到本项目：内部运营分析、SQL Lab、可视化 dashboard、离线分析。
- 它怎么实现：Flask/React 平台围绕 datasets、charts、dashboards、SQL Lab 管分析工作流。
- 源码锚点：`superset/superset`，`superset/superset/charts`，`superset/superset/dashboards`。
- 短代码片段：`charts`；`dashboards`；`SQL Lab`。
- 我们怎么用：P1 内部运营看板候选；用户-facing 研判页继续自研。

### Evidence

- 关联到本项目：SQL + Markdown 内部报告、数据质量/运营日报、审计输出。
- 它怎么实现：CLI 和 packages 组织 Evidence 项目，Markdown 页面可嵌 SQL 查询和图表。
- 源码锚点：`evidence/packages/evidence/cli.js`，`evidence/packages/evidence/index.js`，`evidence/packages/ui`。
- 短代码片段：`cli.js`；`packages/evidence`；`packages/ui`。
- 我们怎么用：内部技术/数据报告候选；客户正式报告由本项目 ReportService 生成和复核。

## 转成开发任务

| 任务 | 不可再拆的功能点 | 验收点 |
| --- | --- | --- |
| `MediaAssetService` | 保存媒体文件元数据和访问策略 | 文件 hash、source_record_id、redaction_status 必填 |
| `VideoFrameExtractor` | 视频/直播切片抽帧 | 失败记录 time range 和原因 |
| `OcrAnalysisActivity` | 图片/帧 OCR | 输出 text/bbox/confidence/model_version |
| `AsrAnalysisActivity` | 音频转写和时间戳 | 输出 transcript/time_range/confidence |
| `ObjectDetectionActivity` | 目标检测和区域计数 | 输出 detections/bbox/class/confidence |
| `SensitiveInfoDetector` | 文本/图片敏感信息识别 | 检出结果必须绑定字段或 bbox |
| `RedactionService` | 文本/图片脱敏 | 脱敏前后版本和审计日志可查 |
| `EvidenceReviewQueue` | 高风险媒体证据进入复核 | 未复核证据不能驱动正式结论 |
| `SourcePolicyService` | 渠道合规策略判断 | blocked/needs_review/allowed 可追溯 |
| `RBACService` | API/字段级权限校验 | 越权访问返回 403 并写审计 |
| `LLMTraceService` | prompt/model/token/cost/error trace | 每次 agent run 都能回放输入输出 |
| `AgentEvalSuite` | schema/evidence/faithfulness/regression | prompt 变更自动触发评测 |
| `DataQualityGate` | raw/clean/evidence 质量阻断 | quarantine 数据不能进入算法 |
| `MetricsEndpoint` | API/worker/workflow/business counters | Grafana/Prometheus 可接入 |
| `ThirdPartyReviewRecord` | 每项输出独立检查 | 没有 review 不能 frozen |
