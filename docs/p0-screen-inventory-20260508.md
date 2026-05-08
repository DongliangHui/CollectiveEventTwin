# CollectiveEventTwin P0 Screen Inventory

Date: 2026-05-08

Status: implementation contract

## Screen 1: Risk Intake

- User goal: choose a case and see current signal/risk posture.
- Inputs: `Case`, `Signal[]`, `RiskFactor[]`, `Report` summary.
- Outputs: selected `caseId`.
- Primary CTA: open case loop.
- Empty state: no seeded cases, show seed/run instruction.
- Error state: API unavailable.
- Reference: `risk-dashboard.html` and `city-monitor.html`.

## Screen 2: Signal And Evidence Review

- User goal: inspect signals, evidence, source mode, credibility, and sensitivity.
- Inputs: `Signal[]`, `Evidence[]`, `SourceRecord[]`.
- Outputs: evidence status update, selected signals for mainline.
- Primary CTA: mark evidence reviewed / open mainline.
- Empty state: no signals accepted for case.
- Error state: source policy blocked all records.
- Reference: `data-hub.html` and `event-detail-evidence.html`.

## Screen 3: Risk Factor Confirmation

- User goal: confirm or reject suggested factors.
- Inputs: `RiskFactor[]`, linked `Evidence[]`.
- Outputs: factor status changes and audit logs.
- Primary CTA: confirm factor.
- Empty state: no factors suggested.
- Error state: factor update failed.
- Reference: factor-driven docs.

## Screen 4: Mainline Builder

- User goal: review support points, trigger clusters, evidence gaps, and confirm mainline.
- Inputs: `Mainline`, `Signal[]`, `RiskFactor[]`.
- Outputs: confirmed `Mainline`, `WorldState`.
- Primary CTA: confirm mainline.
- Empty state: no eligible signals/factors.
- Error state: missing evidence refs.
- Reference: `mainline-builder.html`.

## Screen 5: Worldline Simulation

- User goal: inspect branches, risk, probability, and council recommendation.
- Inputs: `WorldState`, `WorldlineNode[]`.
- Outputs: selected `nodeId`.
- Primary CTA: run council for recommended node.
- Empty state: mainline not confirmed.
- Error state: worldline generation failed.
- Reference: `worldline-observer.html`.

## Screen 6: Agent Council

- User goal: pressure-test a node with structured stakeholder reactions.
- Inputs: `CouncilSession`, `CouncilResult`, `AgentOutput[]`.
- Outputs: applied council result.
- Primary CTA: apply council result.
- Empty state: no node selected.
- Error state: schema validation failed.
- Reference: `agent-council.html`.

## Screen 7: Decision Brief

- User goal: review draft judgement, formal gate, tasks, and compliance notes.
- Inputs: `Report`, `Task[]`, `AuditLog[]`.
- Outputs: report confirmation, task updates.
- Primary CTA: confirm report / update task.
- Empty state: no report generated.
- Error state: high-risk formal conclusion blocked until confirmation.
- Reference: `decision-brief.html`.

## Screen 8: Audit And Source Policy Summary

- User goal: verify source policy, human confirmation, and state changes.
- Inputs: `SourceRecord[]`, `AuditLog[]`, `WorkflowRun[]`.
- Outputs: none for P0.
- Primary CTA: view audit trail.
- Empty state: no audit entries yet.
- Error state: audit query failed.
- Reference: no static page; embedded in production app.

