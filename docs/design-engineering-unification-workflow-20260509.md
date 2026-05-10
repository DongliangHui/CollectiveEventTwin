# CollectiveEventTwin Design-to-Engineering Unification Workflow

Date: 2026-05-09

Status: Mandatory workflow for all customer-facing frontend pages.

## 1. Problem

Design images, static HTML, and the engineered React frontend have been drifting. The city page required too much manual alignment because there was no frozen page contract, no objective visual diff gate, and no component mapping gate before implementation.

## 2. Operating Decision

From this point forward, no customer-facing page can start implementation until it has a page design contract.

Baseline priority:

1. Explicit business decision from the user.
2. Frozen design image or Figma screen, if available.
3. Rendered static HTML screenshot from `worldline-observer-current`.
4. Existing React implementation.

If design image and static HTML conflict, the implementation owner resolves minor visual differences by matching the customer-facing baseline. Only material product/taste conflicts are escalated to the user.

## 3. Page Design Contract

Each page must have a contract before implementation:

| Field | Requirement |
| --- | --- |
| Route | Production route and page name |
| Baseline assets | Design image, static HTML path, static screenshot, existing React screenshot |
| Viewports | Desktop, small laptop, mobile when applicable |
| Layout regions | Header, sidebar, map/canvas, panels, lists, dialogs, footers |
| Component mapping | Static HTML block -> React component -> API/view model |
| Tokens | Color, typography, spacing, radius, shadow, z-index, chart/map palette |
| Data contract | API endpoints, loading, empty, error, success, permission states |
| Interactions | Click, hover, filter, tab, modal, route transition, persistence |
| Visual acceptance | Pixel-diff threshold and critical-region threshold |
| Browser acceptance | Playwright route and interaction checks |
| Third-party review | Frontend reviewer and Browser QA reviewer |

## 4. Implementation Flow

```text
baseline capture
-> page design contract
-> component mapping
-> backend/API readiness check
-> React implementation
-> automated visual diff
-> browser interaction test
-> third-party frontend review
-> freeze page
```

Rules:

- Do not hand-tune a full page directly from memory.
- Do not implement a page from only a screenshot if static HTML exists.
- Do not migrate static HTML by copying inert markup into React without API/data contracts.
- Do not freeze a page if visual diff, API behavior, or browser interaction checks fail.
- Do not ask the user to judge pixel-level differences. Escalate only real product/taste decisions.

## 5. Automated Visual Gate

For every page:

- Capture static HTML baseline screenshot.
- Capture React implementation screenshot.
- Compare at fixed viewports.
- Produce diff image and numeric mismatch.
- Treat critical regions separately: nav, cards, maps, charts, tables, dialogs, report content.

Default thresholds:

| Area | Threshold |
| --- | --- |
| Whole page | <= 3% mismatch |
| Critical region | <= 1% mismatch |
| Text clipping/overlap | 0 tolerance |
| Broken layout/blank panel | 0 tolerance |
| Missing customer-facing data | 0 tolerance |

Thresholds can be tightened after the first stable page family.

## 6. Component System Gate

Before migrating many pages, extract shared production components:

- App shell
- Top navigation
- Sidebar navigation
- Filter toolbar
- KPI strip
- Data table/list
- Ranking panel
- Evidence card
- Timeline
- Map container and layer controls
- Media evidence viewer
- Workflow status indicator
- Approval/task panel
- Report section renderer
- Empty/error/loading states

Each component must have:

- Props contract.
- API/view-model binding.
- Visual baseline.
- Interaction test.
- Permission/empty/error state.

## 7. Third-Party Checks

Each page requires independent checks:

| Check | Owner |
| --- | --- |
| Baseline contract completeness | Design/Frontend reviewer |
| API/data contract match | Backend/API reviewer |
| Visual diff | Browser QA |
| Interaction behavior | Browser QA |
| Permission/error states | QA reviewer |
| Customer-facing language | Product/Report reviewer |

The implementing frontend agent cannot freeze its own page.

## 8. User Intervention Boundary

The user only needs to intervene for:

- Design image and static HTML express different product intent.
- A customer-facing wording or brand/tone decision is needed.
- A page requires scope reduction or delivery tradeoff.
- DCP launch decision.

The user should not be asked to inspect every pixel, CSS detail, component implementation, or browser diff.

## 9. Immediate Application

Apply this workflow to the next page before coding:

1. Build a screen inventory from `worldline-observer-current`.
2. Capture static screenshots for all customer-facing pages.
3. Create page contracts in delivery order.
4. Extract shared components before further full-page migration.
5. Add automated screenshot diff to the browser QA workflow.
6. Require third-party review before freezing each page.
