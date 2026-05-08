# CollectiveEventTwin Project Structure

Last updated: 2026-05-08

This repository is being prepared for a real P0 implementation path:

```text
test data
-> P0 agent/runtime backend
-> generated Signal/Mainline/WorldState/Map objects
-> current static frontend mock contract
-> later real platform/data connectors
```

## Active Directories

| Path | Purpose |
| --- | --- |
| `worldline-observer-current/` | Current static frontend demo. Keep this path stable. It is also an independent Git worktree with local changes. |
| `p0-agent-runtime/` | P0 backend/agent runtime. Generates signals, map layers, mainlines, world states, worldline nodes, council results, and report tasks from test data. |
| `docs/` | Product, business, UX, architecture, and research notes. |
| `infra/` | Infrastructure workspace. Currently reserved for local services such as Postgres, Redis, workflow engines, and future Docker Compose files. |

## Supporting Directories

| Path | Purpose |
| --- | --- |
| `design/` | Design images and static mockups. |
| `artifacts/` | Generated screenshots, validation outputs, Playwright logs, and other disposable run artifacts. |
| `archive/` | Historical demos, sealed versions, Figma demo plugin, and older generated variants kept for reference. |

## Current P0 Runtime Outputs

The P0 runtime writes generated files to:

```text
p0-agent-runtime/output/
```

Important generated files:

| File | Purpose |
| --- | --- |
| `p0_bundle.json` | Full runtime object bundle. |
| `signals.generated.json` | Generated signal list. |
| `map_layers.generated.json` | Generic event point and heat-zone output. |
| `demo-data.generated.json` | Static frontend mock-compatible demo data. |
| `map-layers.static.generated.json` | Static frontend mock-compatible map layers. |
| `geo-points.static.generated.json` | Static frontend mock-compatible geo points. |

## P0 Development Rule

Do not integrate real Douyin, Kuaishou, Weibo, WeChat, Xiaohongshu, or forum connectors until the local frontend-backend chain runs on test data.

Connector integration comes after:

1. P0 runtime contracts are stable.
2. Static frontend can consume generated test data.
3. Local API service is running through Docker-backed infrastructure.
4. Compliance mode and source authorization checks are enforced.

## File Organization Notes

- Do not move `worldline-observer-current/` without planning; current links and local Git state depend on it.
- Keep generated validation files under `artifacts/`.
- Keep historical versions under `archive/`.
- Keep product and technical docs under `docs/`.
- Keep Codex memory outside this repository, under `C:\Users\ROG\.codex\workspace\memory`.
