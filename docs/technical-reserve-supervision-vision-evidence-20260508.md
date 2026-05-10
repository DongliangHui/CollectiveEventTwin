# Roboflow Supervision 技术储备：视频与图像证据处理

Date: 2026-05-08

Status: 技术储备，不进入当前 P0 运行时依赖

Target repo:

- GitHub: https://github.com/roboflow/supervision
- Docs: https://supervision.roboflow.com/latest/
- PyPI: https://pypi.org/project/supervision/

## 1. 结论

`supervision` 适合作为 CollectiveEventTwin 后续视频/图像证据处理的工具层，定位是：

```text
模型推理输出
-> supervision 统一检测结果、跟踪、区域统计、视频帧处理、标注
-> VisionEvidenceAdapter
-> raw_records / evidence / audit_logs
```

它不适合作为：

- 数据采集器。
- OCR / ASR 引擎。
- 目标检测或分割模型本身。
- 隐私脱敏模型本身。
- 事实判断或事件结论系统。

对本项目最有价值的能力是：把短视频、直播切片、人工上传图片、截图、无人机或授权视频流中的视觉模型输出，整理成可追溯、可复核、可审计的证据对象。

## 2. 当前项目匹配点

项目现有产品文档已经提出以下视频/图像需求：

- 人工上传视频/图片、直播/视频链接分析。
- 关键帧抽取。
- OCR / ASR。
- 画面场景识别。
- 隐私脱敏。
- 现场事实卡。
- 给 Agent Council 提供现场证据。

`supervision` 可以覆盖其中的工程工具层：

| 项目需求 | supervision 能力 | 说明 |
| --- | --- | --- |
| 视频逐帧处理 | `process_video`, frame generator, `VideoSink` | 适合做离线视频证据分析任务 |
| 模型输出标准化 | `Detections`, `KeyPoints`, adapter methods | 可统一 YOLO、Roboflow Inference、Transformers 等输出 |
| 目标跟踪 | `ByteTrack` | 可把同一人群、车辆、警车、救护车等跨帧关联 |
| 区域/线段计数 | polygon zone, line zone | 可做校门口、道路、广场、通道等区域内计数 |
| 证据可视化 | box, mask, label, trace, zone annotators | 生成人工复核用标注图或标注视频 |
| 大图处理 | slicing / tiled inference utilities | 可处理航拍图、广场图、长截图等 |
| 数据集转换与评估 | YOLO / COCO / Pascal VOC, mAP, confusion matrix | 适合后续自建风险场景视觉数据集 |

## 3. 维护与依赖状态

截至 2026-05-08 核对：

- Latest release: `0.28.0`, published 2026-04-30.
- GitHub default branch: `develop`.
- Latest push: 2026-05-06.
- License: MIT.
- Python support: `>=3.9`, classifiers include Python 3.9 through 3.14.
- PyPI latest: `0.28.0`.
- Core dependencies include `numpy`, `opencv-python`, `pillow`, `matplotlib`, `scipy`, `pyyaml`, `requests`, `tqdm`.
- Optional metrics dependency includes `pandas`.

Current project API runtime uses Python `>=3.11`, so version compatibility is acceptable. The dependency risk is mainly OpenCV and model runtime dependencies, not `supervision` itself.

## 4. 推荐系统位置

新增后续模块时，建议不要直接把 `supervision` 写进 API request path。它应该运行在 worker 或异步任务里：

```text
Data source / manual upload / authorized video
-> raw media object
-> VisionAnalysisWorkflow
-> KeyframeExtractor
-> VisionModelRunner
-> SupervisionPostProcessor
-> VisionEvidenceAdapter
-> raw_records / evidence / audit_logs
```

### 4.1 表与对象映射

建议后续补充或扩展：

| 对象 | 字段建议 |
| --- | --- |
| `raw_records` | `media_type`, `source_url`, `storage_ref`, `capture_time`, `frame_range`, `content_hash`, `access_mode`, `policy_decision` |
| `evidence` | `visual_claim`, `detected_objects`, `zone_counts`, `tracked_objects`, `keyframe_refs`, `masked_media_refs`, `confidence`, `sensitivity` |
| `audit_logs` | `model_version`, `supervision_version`, `input_hash`, `frame_sampling_policy`, `review_actor`, `privacy_mask_status` |

### 4.2 输出结构草案

```json
{
  "schema_version": "vision_evidence.v1",
  "media_ref": "media://case/CASE-CAMPUS-001/video/VID-001",
  "frame_ref": "media://case/CASE-CAMPUS-001/frame/VID-001-000420",
  "timestamp_ms": 14000,
  "model": {
    "name": "yolo/rf-detr/custom",
    "version": "TBD",
    "supervision_version": "0.28.0"
  },
  "detections": [
    {
      "class_name": "crowd",
      "confidence": 0.84,
      "bbox_xyxy": [120, 80, 460, 380],
      "tracker_id": 17,
      "zone": "school_gate"
    }
  ],
  "derived_signals": [
    {
      "type": "crowd_presence",
      "value": "high",
      "evidence_strength": 0.72
    }
  ],
  "privacy": {
    "requires_masking": true,
    "mask_targets": ["face", "license_plate", "minor_identity"],
    "masked_media_ref": "media://case/CASE-CAMPUS-001/masked/VID-001-000420"
  }
}
```

## 5. 适合的第一批 POC

### POC A: 人工上传图片现场事实卡

输入：

- 10 到 30 张人工上传图片或截图。
- 场景：校门口聚集、食品安全现场、社区停水排队、交通拥堵。

验证：

- 检测人员、车辆、警车、救护车、校门、队列、烟雾、拥堵等对象。
- 生成标注图。
- 生成 `VisionEvidence` JSON。
- 写入测试库 `raw_records` 和 `evidence`。

通过标准：

- 每条视觉结论都有 frame/image ref。
- 每条 evidence 有模型版本和输入 hash。
- 敏感内容默认标记 `needs_masking`。
- 人工复核可以看到原图、标注图、模型输出和不确定性。

### POC B: 短视频关键帧与人群/车辆跟踪

输入：

- 5 到 10 条授权短视频或手工样例视频。

验证：

- 固定间隔抽帧或场景变化抽帧。
- 用检测模型产生 `Detections`。
- 用 `ByteTrack` 追踪跨帧对象。
- 统计指定 polygon zone 内人数或车辆数。
- 输出关键帧证据和趋势摘要。

通过标准：

- 处理失败可重试且不重复写 evidence。
- 每个 tracked object 有 `tracker_id`，但不形成个人画像。
- 只保留必要证据帧，不默认长期保存完整视频。

### POC C: 区域计数与传播风险信号

输入：

- 校门口、医院门口、商圈入口、道路路口等固定视角视频。

验证：

- 建立 polygon zones。
- 统计区域内人数、车辆、排队长度或穿越线次数。
- 生成 `RiskFactor` 候选：线下聚集、交通拥堵、现场冲突、二次围观。

通过标准：

- 视觉信号只作为 evidence 支撑，不直接生成正式事实结论。
- 高风险结论仍需人工确认。

## 6. 不应承诺的能力

当前技术储备不承诺：

- 自动识别具体个人身份。
- 从画面直接判断责任归属。
- 仅凭视频判断事件真伪。
- 绕平台风控下载视频。
- 对未授权平台视频做批量采集。
- 自动发布处置建议或对外结论。

需要单独引入或自研的能力：

- OCR: PaddleOCR、EasyOCR、云 OCR 或自研服务。
- ASR: Whisper、FunASR、云 ASR 或本地语音模型。
- 隐私脱敏: 人脸、车牌、门牌、证件、未成年人信息检测与遮挡。
- 模型推理: Ultralytics、RF-DETR、Roboflow Inference、ONNX Runtime、TensorRT 等。
- 媒体存储: 对象存储、本地 minio、hash 索引、保留策略。

## 7. 推荐落地边界

P0 当前不建议把 `supervision` 加入产品运行时依赖。建议在生产后端主链路稳定后，以独立实验分支推进：

1. 新建 `apps/vision-worker` 或在 `apps/worker` 下增加 isolated vision activity。
2. 只处理 `manual_upload`、`authorized_export`、`public_web` 已落库媒体。
3. 先支持图片和短视频文件，不接实时流。
4. 所有输出先进入 `raw_records` / `evidence`，不直接改 `mainlines`。
5. 强制写入 `audit_logs`：输入 hash、模型版本、supervision 版本、处理参数、操作者。
6. 加人审 gate：高风险视觉结论进入 `needs_review`。

## 8. 技术验证任务清单

| Task | 输出 |
| --- | --- |
| TV-01 安装与依赖 smoke test | Windows/Python 3.11 下 import、OpenCV 视频读写可用 |
| TV-02 图片检测后处理 | `Detections` 转标准 JSON，生成标注图 |
| TV-03 视频帧处理 | `process_video` 或 frame generator 处理样例视频 |
| TV-04 ByteTrack | 同一目标跨帧 tracker id 稳定性报告 |
| TV-05 Zone counting | polygon zone 人数/车辆计数报告 |
| TV-06 隐私标记联动 | face/license plate detector 输出 `needs_masking` |
| TV-07 DB 写入试验 | 通过测试服务写 `raw_records` / `evidence` / `audit_logs` |
| TV-08 失败恢复 | 重试不重复写 evidence，失败状态可见 |

## 9. 采购/自研影响

`supervision` 降低的是视觉工程胶水成本，不替代模型采购或训练成本。

推荐组合：

```text
supervision
+ Ultralytics/RF-DETR/custom detector
+ OCR/ASR service
+ privacy masking detector
+ object storage
+ workflow/audit/policy service
```

如果后续要做城市级视频态势，`supervision` 可以继续用于帧级后处理和可视化，但实时流调度、GPU 资源、模型服务、保留策略、权限审计仍要由项目自己的后端架构负责。

## 10. 资料来源

- https://github.com/roboflow/supervision
- https://supervision.roboflow.com/latest/
- https://pypi.org/project/supervision/
- https://github.com/roboflow/supervision/blob/develop/docs/how_to/track_objects.md
- https://github.com/roboflow/supervision/blob/develop/docs/how_to/count_in_zone.md
