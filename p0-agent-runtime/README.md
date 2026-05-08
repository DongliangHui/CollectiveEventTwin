# Worldline Observer P0 Agent Runtime

This directory contains the first runnable P0 slice for the Worldline Observer project.

It does not scrape protected platforms. It accepts only records from allowed source modes:

- `public_web`
- `official_api`
- `authorized_export`
- `manual_upload`
- `third_party_contract`

Blocked modes include private chats, login bypasses, cookie pools, captcha bypasses, and any source that is not explicitly approved.

## P0 Flow

```text
source registry
-> raw records
-> policy filter
-> multimodal text merge
-> risk tags and narrative frames
-> Signal objects
-> map event points and heat zones
-> mainline
-> world state
-> worldline nodes
-> Agent Council result
-> report tasks
```

## Run Tests

```powershell
$env:PYTHONPATH="E:\GitHub\CollectiveEventTwin\p0-agent-runtime\src"
python -m unittest discover -s E:\GitHub\CollectiveEventTwin\p0-agent-runtime\tests
```

## Generate The P0 Bundle

```powershell
$env:PYTHONPATH="E:\GitHub\CollectiveEventTwin\p0-agent-runtime\src"
python -m worldline_p0.cli `
  --source-registry E:\GitHub\CollectiveEventTwin\p0-agent-runtime\config\source_registry.json `
  --records E:\GitHub\CollectiveEventTwin\p0-agent-runtime\data\seed_records.json `
  --gazetteer E:\GitHub\CollectiveEventTwin\p0-agent-runtime\data\geo_gazetteer.json `
  --output-dir E:\GitHub\CollectiveEventTwin\p0-agent-runtime\output
```

Outputs:

- `output/p0_bundle.json`
- `output/map_layers.generated.json`
- `output/signals.generated.json`
- `output/demo-data.generated.json`
- `output/map-layers.static.generated.json`
- `output/geo-points.static.generated.json`

## Integration Boundary

The current static pages in `worldline-observer-current` already consume `Signal`, `Mainline`, `WorldState`, `WorldlineNode`, `CouncilResult`, `Report`, and map feature-like objects.

This runtime intentionally writes generated artifacts beside itself first. `demo-data.generated.json`, `map-layers.static.generated.json`, and `geo-points.static.generated.json` are shaped for the current static `MockAPI` contract. After review, they can be copied into `worldline-observer-current/mock/fixtures/` as a separate integration step without changing page layout.

## Platform Notes

P0 treats Douyin, Kuaishou, Weibo, WeChat official accounts, Xiaohongshu, and local forums as connector families, not as permission to crawl everything. A connector must declare its access mode and policy status before records can enter the pipeline.

For images, video, and live clips, P0 accepts structured OCR, ASR, keyframe, scene-tag, and manual-note payloads. Real OCR/ASR/video processing can replace this input layer later without changing downstream signal, map, mainline, and council objects.
