# P0 API Page CSS Notes

The renderer emits stable class names only; it does not import CSS. Main-thread wiring can paste or adapt these into `apps/web/src/styles.css`.

## Page Shell

```css
.p0-api-page {
  min-width: 1320px;
  height: 100dvh;
  display: grid;
  grid-template-rows: 58px 86px auto minmax(0, 1fr);
  overflow: hidden;
  background: linear-gradient(180deg, #faf7f0 0%, #f3efe7 100%);
  color: var(--ink);
}

.p0-topbar {
  display: grid;
  grid-template-columns: 248px minmax(760px, 1fr) 260px;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
  background: var(--nav);
  color: #f3f8ff;
}

.p0-brand,
.p0-flow-step,
.p0-status,
.p0-page-head,
.p0-head-actions {
  display: flex;
  align-items: center;
}

.p0-flow-nav {
  display: grid;
  grid-template-columns: repeat(11, minmax(72px, 1fr));
  gap: 6px;
}

.p0-flow-step {
  min-height: 42px;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 6px;
  padding: 0 8px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  color: rgba(243, 248, 255, 0.74);
  font-size: 11px;
  font-weight: 900;
}

.p0-flow-step.active {
  background: var(--paper);
  color: var(--blue);
}

.p0-page-head {
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 253, 248, 0.82);
}

.p0-page-head h1 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 22px;
}

.p0-page-head p,
.p0-section-head p,
.p0-meta-row,
.p0-subject-card small {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
```

## Layouts

```css
.p0-layout {
  min-height: 0;
  display: grid;
  gap: 10px;
  padding: 10px 18px 14px;
  overflow: hidden;
}

.p0-layout-geo,
.p0-layout-dashboard {
  grid-template-columns: 300px minmax(680px, 1fr) 360px;
  grid-auto-rows: minmax(150px, 1fr);
}

.p0-layout-workbench,
.p0-layout-review,
.p0-layout-builder,
.p0-layout-timeline,
.p0-layout-council,
.p0-layout-brief,
.p0-layout-archive,
.p0-layout-config {
  grid-template-columns: minmax(0, 1fr) 380px;
  grid-auto-rows: minmax(180px, auto);
}

.p0-section {
  min-width: 0;
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--soft);
  overflow: hidden;
}

.p0-section[data-section*="map"],
.p0-section[data-section*="canvas"],
.p0-section[data-section*="timeline"] {
  grid-row: span 2;
}
```

## Reusable Blocks

```css
.p0-kpi-strip,
.p0-metric-grid,
.p0-branch-list,
.p0-subject-grid,
.p0-evidence-list,
.p0-item-list {
  display: grid;
  gap: 8px;
}

.p0-kpi-strip {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  padding: 8px 18px 0;
}

.p0-metric {
  min-height: 72px;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 253, 247, 0.72);
}

.p0-table {
  min-height: 0;
  overflow: auto;
}

.p0-table-head,
.p0-table-row {
  display: grid;
  grid-template-columns: var(--columns) auto;
  gap: 8px;
  align-items: center;
  min-height: 36px;
  border-bottom: 1px solid rgba(216, 205, 188, 0.64);
  font-size: 12px;
  font-weight: 850;
}

.p0-evidence-card,
.p0-branch-card,
.p0-subject-card,
.p0-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 253, 247, 0.72);
  padding: 10px;
}

.p0-primary,
.p0-outline,
.p0-danger {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 11px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 950;
}

.p0-primary {
  color: white;
  background: var(--blue);
}

.p0-outline {
  border: 1px solid var(--line);
  background: var(--paper);
}

.p0-danger {
  color: white;
  background: var(--red);
}
```

## Tone Hooks

```css
.tone-blue { --tone: var(--blue); }
.tone-green { --tone: var(--green); }
.tone-amber { --tone: var(--amber); }
.tone-red { --tone: var(--red); }
.tone-violet { --tone: var(--violet); }
.tone-cyan { --tone: #009fb7; }
.tone-gray { --tone: var(--muted); }
```
