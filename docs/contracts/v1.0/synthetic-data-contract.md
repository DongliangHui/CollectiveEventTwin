# 合成数据标记规范 v1.0

状态：冻结版

## 使用范围

合成数据仅用于第一阶段西安社会议题样本，包括：

- 社区拆迁场景。
- 养老保险 petition 场景。

合成数据允许用于产品演示和开发验收，但必须明确标记，不得伪装成真实数据。

## 标记规则

| 层级 | 字段 |
| --- | --- |
| DataSource | `source_type = synthetic` |
| RawRecord | `is_synthetic = true` |
| LineageEdge | `is_synthetic = true` |
| Evidence/Signal/RiskFactor | `source_flags.synthetic = true` |
| Report/Export | `synthetic_watermark = true` 或显示声明 |

## 链路规则

合成数据必须经过真实链路：

```text
DataSource -> CollectionRun -> RawRecord -> Processing -> Signal/Evidence -> Mainline -> Worldline -> Council -> Report
```

禁止：

- 直接预置 downstream Signal/Evidence/Mainline/Report 作为产品数据。
- 与真实数据混合后去掉 synthetic 标记。
- 在报告或导出中隐藏 synthetic 声明。

## 验收

- 任一下游对象可通过 lineage 回溯到 synthetic source。
- City/Topic/Report 页面能显示合成数据声明。
- 导出文件带水印或声明。
