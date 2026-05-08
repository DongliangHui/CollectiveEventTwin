import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCheck2,
  GitBranch,
  Library,
  MapPinned,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  Users
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { ComponentType, CSSProperties } from "react";
import type {
  P0BranchItem,
  P0EvidenceItem,
  P0Metric,
  P0PageAction,
  P0PageId,
  P0PageRendererProps,
  P0PageTone,
  P0Section,
  P0SubjectOutput,
  P0TableRow,
  P0TimelineItem
} from "./contracts";

const defaultNav: Array<{ page: P0PageId; label: string; helper: string }> = [
  { page: "city", label: "城市态势", helper: "全域发现" },
  { page: "risk", label: "主题态势", helper: "热点聚合" },
  { page: "data", label: "数据检索", helper: "检索抓取" },
  { page: "evidence", label: "证据复核", helper: "脱敏核验" },
  { page: "mainline", label: "主线建模", helper: "支点确认" },
  { page: "worldline", label: "世界线", helper: "分支推演" },
  { page: "council", label: "多主体研判", helper: "压力测试" },
  { page: "brief", label: "决策简报", helper: "任务闭环" },
  { page: "memory", label: "复盘沉淀", helper: "经验回流" },
  { page: "library", label: "案例库", helper: "相似召回" },
  { page: "config", label: "配置", helper: "规则参数" }
];

const pageIcons = {
  city: MapPinned,
  risk: Radar,
  data: Search,
  evidence: ShieldCheck,
  mainline: GitBranch,
  worldline: BarChart3,
  council: Users,
  brief: FileCheck2,
  memory: ClipboardList,
  library: Library,
  config: Settings
} satisfies Record<P0PageId, ComponentType<{ size?: number }>>;

const pageLayouts = {
  city: "geo",
  risk: "dashboard",
  data: "workbench",
  evidence: "review",
  mainline: "builder",
  worldline: "timeline",
  council: "council",
  brief: "brief",
  memory: "archive",
  library: "archive",
  config: "config"
} satisfies Record<P0PageId, string>;

export function P0ApiPage({ view, onAction, isActionPending, className, iconForPage = {} }: P0PageRendererProps) {
  const nav = view.nav?.length ? view.nav : defaultNav;
  const layout = pageLayouts[view.page];
  const pageIconMap = { ...pageIcons, ...iconForPage };
  const PageIcon = pageIconMap[view.page] ?? Radar;

  return (
    <div className={["p0-api-page", `p0-page-${view.page}`, className].filter(Boolean).join(" ")} data-page={view.page}>
      <header className="p0-topbar">
        <Link to="/cases/$caseId/$page" params={{ caseId: view.caseId, page: "city" }} className="p0-brand">
          <span className="p0-brand-mark" />
          <span>
            WORLDLINE OBSERVER
            <small>P0 数据驱动研判闭环</small>
          </span>
        </Link>
        <nav className="p0-flow-nav" aria-label="P0 产品流程">
          {nav.map((item, index) => {
            const Icon = pageIconMap[item.page] ?? Radar;
            return (
              <Link
                key={item.page}
                to="/cases/$caseId/$page"
                params={{ caseId: view.caseId, page: item.page }}
                className={item.page === view.page ? "p0-flow-step active" : "p0-flow-step"}
              >
                <i>{index + 1}</i>
                <b>
                  <Icon size={14} />
                  {item.label}
                  {item.helper ? <span>{item.helper}</span> : null}
                </b>
              </Link>
            );
          })}
        </nav>
        <div className="p0-status">
          <span className="live-dot" />
          <span>{view.caseId}</span>
          {view.updatedAt ? <strong>{view.updatedAt}</strong> : null}
        </div>
      </header>

      <section className="p0-page-head">
        <div>
          <span className="p0-eyebrow">{view.scenarioLabel ?? "P0 / API View Model"}</span>
          <h1>
            <PageIcon size={22} />
            {view.title}
          </h1>
          {view.subtitle ? <p>{view.subtitle}</p> : null}
        </div>
        <div className="p0-head-actions">
          {view.primaryAction ? <ActionButton action={view.primaryAction} onAction={onAction} pending={isActionPending?.(view.primaryAction)} /> : null}
          <Link className="p0-outline" to="/cases/$caseId/$page" params={{ caseId: view.caseId, page: "brief" }}>
            查看决策简报
          </Link>
        </div>
      </section>

      {view.metrics?.length ? (
        <section className="p0-kpi-strip">
          {view.metrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} />
          ))}
        </section>
      ) : null}

      <main className={`p0-layout p0-layout-${layout}`}>
        {view.sections.map((section) => (
          <SectionCard key={section.id} section={section} onAction={onAction} isActionPending={isActionPending} />
        ))}
      </main>
    </div>
  );
}

function SectionCard({
  section,
  onAction,
  isActionPending
}: {
  section: P0Section;
  onAction?: (action: P0PageAction) => void | Promise<void>;
  isActionPending?: (action: P0PageAction) => boolean;
}) {
  return (
    <section className={["p0-section", section.tone ? `tone-${section.tone}` : undefined].filter(Boolean).join(" ")} data-section={section.id}>
      <header className="p0-section-head">
        <div>
          {section.eyebrow ? <span>{section.eyebrow}</span> : null}
          <h2>{section.title}</h2>
          {section.helper ? <p>{section.helper}</p> : null}
        </div>
        {section.actions?.length ? (
          <div className="p0-section-actions">
            {section.actions.map((action) => (
              <ActionButton key={`${action.id}-${action.targetId ?? action.label}`} action={action} onAction={onAction} pending={isActionPending?.(action)} />
            ))}
          </div>
        ) : null}
      </header>

      {section.metrics?.length ? (
        <div className="p0-metric-grid">
          {section.metrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} compact />
          ))}
        </div>
      ) : null}
      {section.timeline?.length ? <Timeline items={section.timeline} /> : null}
      {section.branches?.length ? <BranchList branches={section.branches} onAction={onAction} isActionPending={isActionPending} /> : null}
      {section.evidence?.length ? <EvidenceList evidence={section.evidence} onAction={onAction} isActionPending={isActionPending} /> : null}
      {section.subjects?.length ? <SubjectGrid subjects={section.subjects} /> : null}
      {section.table ? <DataTable columns={section.table.columns} rows={section.table.rows} onAction={onAction} isActionPending={isActionPending} /> : null}
      {section.items?.length ? <ItemList items={section.items} onAction={onAction} isActionPending={isActionPending} /> : null}
      {section.tags?.length ? <TagRow tags={section.tags} /> : null}
      {section.body ? <div className="p0-section-body">{section.body}</div> : null}
      {!hasRenderableContent(section) ? <EmptyState /> : null}
    </section>
  );
}

function MetricCard({ metric, compact }: { metric: P0Metric; compact?: boolean }) {
  return (
    <article className={["p0-metric", compact ? "compact" : undefined, toneClass(metric.tone)].filter(Boolean).join(" ")}>
      <span className="p0-metric-icon">
        <BarChart3 size={compact ? 14 : 18} />
      </span>
      <div>
        <label>{metric.label}</label>
        <strong>{metric.value}</strong>
        {metric.helper ? <small>{metric.helper}</small> : null}
      </div>
    </article>
  );
}

function Timeline({ items }: { items: P0TimelineItem[] }) {
  return (
    <ol className="p0-timeline">
      {items.map((item) => (
        <li key={item.id} className={item.status}>
          <i />
          <b>{item.label}</b>
          {item.helper ? <span>{item.helper}</span> : null}
        </li>
      ))}
    </ol>
  );
}

function BranchList({
  branches,
  onAction,
  isActionPending
}: {
  branches: P0BranchItem[];
  onAction?: (action: P0PageAction) => void | Promise<void>;
  isActionPending?: (action: P0PageAction) => boolean;
}) {
  return (
    <div className="p0-branch-list">
      {branches.map((branch) => (
        <article key={branch.id} className="p0-branch-card">
          <header>
            <span>{branch.branch}</span>
            <b>{branch.title}</b>
            <StatusPill label={branch.status} tone={branch.risk >= 80 ? "red" : branch.risk >= 65 ? "amber" : "green"} />
          </header>
          {branch.summary ? <p>{branch.summary}</p> : null}
          <div className="p0-risk-strip">
            <Meter label="概率" value={branch.probability} />
            <Meter label="风险" value={branch.risk} />
          </div>
          {branch.action ? <ActionButton action={branch.action} onAction={onAction} pending={isActionPending?.(branch.action)} /> : null}
        </article>
      ))}
    </div>
  );
}

function EvidenceList({
  evidence,
  onAction,
  isActionPending
}: {
  evidence: P0EvidenceItem[];
  onAction?: (action: P0PageAction) => void | Promise<void>;
  isActionPending?: (action: P0PageAction) => boolean;
}) {
  return (
    <div className="p0-evidence-list">
      {evidence.map((item) => (
        <article key={item.id} className="p0-evidence-card">
          <header>
            <div>
              <span>{item.id}</span>
              <h3>{item.title}</h3>
            </div>
            <StatusPill label={item.status} tone={item.status.includes("拒") || item.status.includes("reject") ? "red" : "blue"} />
          </header>
          <p>{item.excerpt}</p>
          <div className="p0-meta-row">
            <span>{item.source}</span>
            {item.credibility ? <span>可信度 {item.credibility}</span> : null}
            {item.sensitivity ? <span>{item.sensitivity}</span> : null}
          </div>
          {item.tags?.length ? <TagRow tags={item.tags} /> : null}
          {item.actions?.length ? (
            <div className="p0-card-actions">
              {item.actions.map((action) => (
                <ActionButton key={`${item.id}-${action.id}`} action={action} onAction={onAction} pending={isActionPending?.(action)} />
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function SubjectGrid({ subjects }: { subjects: P0SubjectOutput[] }) {
  return (
    <div className="p0-subject-grid">
      {subjects.map((subject) => (
        <article key={subject.id} className="p0-subject-card">
          <header>
            <Users size={16} />
            <div>
              <h3>{subject.role}</h3>
              <span>{subject.stance}</span>
            </div>
          </header>
          <p>{subject.reaction}</p>
          {subject.deltas?.length ? (
            <div className="p0-delta-grid">
              {subject.deltas.map((delta) => (
                <span key={`${subject.id}-${delta.label}`} className={toneClass(delta.tone)}>
                  <b>{delta.value}</b>
                  {delta.label}
                </span>
              ))}
            </div>
          ) : null}
          {subject.evidenceRefs?.length ? <TagRow tags={subject.evidenceRefs.map((ref) => ({ id: ref, label: ref, tone: "blue" }))} /> : null}
          {subject.blockedClaims?.length ? (
            <div className="p0-warning">
              <AlertTriangle size={14} />
              {subject.blockedClaims.join(" / ")}
            </div>
          ) : null}
          {subject.uncertainty ? <small>{subject.uncertainty}</small> : null}
        </article>
      ))}
    </div>
  );
}

function DataTable({
  columns,
  rows,
  onAction,
  isActionPending
}: {
  columns: Array<{ key: string; label: string; width?: string }>;
  rows: P0TableRow[];
  onAction?: (action: P0PageAction) => void | Promise<void>;
  isActionPending?: (action: P0PageAction) => boolean;
}) {
  return (
    <div className="p0-table" style={{ "--columns": columns.map((column) => column.width ?? "minmax(0, 1fr)").join(" ") } as CSSProperties}>
      <div className="p0-table-head">
        {columns.map((column) => (
          <span key={column.key}>{column.label}</span>
        ))}
        {rows.some((row) => row.action) ? <span>操作</span> : null}
      </div>
      {rows.map((row) => (
        <div key={row.id} className={["p0-table-row", toneClass(row.tone)].filter(Boolean).join(" ")}>
          {columns.map((column) => (
            <span key={`${row.id}-${column.key}`}>{row.cells[column.key] ?? "—"}</span>
          ))}
          {row.action ? <ActionButton action={row.action} onAction={onAction} pending={isActionPending?.(row.action)} /> : rows.some((item) => item.action) ? <span /> : null}
        </div>
      ))}
    </div>
  );
}

function ItemList({
  items,
  onAction,
  isActionPending
}: {
  items: NonNullable<P0Section["items"]>;
  onAction?: (action: P0PageAction) => void | Promise<void>;
  isActionPending?: (action: P0PageAction) => boolean;
}) {
  return (
    <div className="p0-item-list">
      {items.map((item) => (
        <article key={item.id} className={["p0-item", toneClass(item.tone)].filter(Boolean).join(" ")}>
          <span className="p0-item-dot" />
          <div>
            <b>{item.title}</b>
            {item.helper ? <p>{item.helper}</p> : null}
            {item.tags?.length ? <TagRow tags={item.tags} /> : null}
          </div>
          {item.value ? <strong>{item.value}</strong> : null}
          {item.status ? <StatusPill label={item.status} tone={item.tone} /> : null}
          {item.action ? <ActionButton action={item.action} onAction={onAction} pending={isActionPending?.(item.action)} /> : null}
        </article>
      ))}
    </div>
  );
}

function ActionButton({
  action,
  onAction,
  pending
}: {
  action: P0PageAction;
  onAction?: (action: P0PageAction) => void | Promise<void>;
  pending?: boolean;
}) {
  const className = action.variant === "primary" ? "p0-primary" : action.variant === "danger" ? "p0-danger" : "p0-outline";
  return (
    <button className={className} type="button" disabled={action.disabled || pending || !onAction} onClick={() => void onAction?.(action)} title={action.reason}>
      {pending ? "处理中" : action.label}
    </button>
  );
}

function TagRow({ tags }: { tags: Array<{ id: string; label: string; tone?: P0PageTone }> }) {
  return (
    <div className="p0-tag-row">
      {tags.map((tag) => (
        <span key={tag.id} className={["p0-tag", toneClass(tag.tone)].filter(Boolean).join(" ")}>
          {tag.label}
        </span>
      ))}
    </div>
  );
}

function StatusPill({ label, tone = "gray" }: { label: string; tone?: P0PageTone }) {
  return <span className={["p0-status-pill", toneClass(tone)].join(" ")}>{label}</span>;
}

function Meter({ label, value }: { label: string; value: number }) {
  const normalized = Math.max(0, Math.min(100, value));
  return (
    <div className="p0-meter">
      <span>
        {label}
        <b>{normalized}%</b>
      </span>
      <i style={{ "--value": `${normalized}%` } as CSSProperties} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="p0-empty">
      <Database size={18} />
      <span>当前 page API 暂无可渲染数据</span>
    </div>
  );
}

function hasRenderableContent(section: P0Section) {
  return Boolean(
    section.metrics?.length ||
      section.tags?.length ||
      section.body ||
      section.table?.rows.length ||
      section.items?.length ||
      section.evidence?.length ||
      section.subjects?.length ||
      section.timeline?.length ||
      section.branches?.length
  );
}

function toneClass(tone?: P0PageTone) {
  return tone ? `tone-${tone}` : undefined;
}
