import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  ClipboardList,
  Database,
  Download,
  Eye,
  FileCheck2,
  Filter,
  GitBranch,
  Layers,
  ListChecks,
  MapPinned,
  Play,
  Radar,
  RefreshCw,
  Route,
  Scale,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Timer,
  Users
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";
import { ApiDrivenProductPage } from "./p0-pages/ApiDrivenProductPage";
import { S1FoundationConsole, type S1ConsoleMode } from "./FoundationConsole";
import { S2SourceConsole } from "./S2SourceConsole";
import {
  api,
  AuditLog,
  CaseBundle,
  CaseOut,
  CouncilSession,
  Evidence,
  MapLayers,
  RiskFactor,
  Signal,
  SourceRecord,
  Task,
  WorldlineNode
} from "./api";
import type { ProductPageName } from "./api";

export type ProductPageId =
  | "city"
  | "risk"
  | "data"
  | "evidence"
  | "mainline"
  | "worldline"
  | "council"
  | "brief"
  | "audit"
  | "memory"
  | "library"
  | "config";

type ProductPageProps = {
  caseId: string;
  page: ProductPageId;
};

type ActionMutation = UseMutationResult<unknown, Error, () => Promise<unknown>, unknown>;

type NavItem = {
  id: ProductPageId;
  label: string;
  helper: string;
  icon: ComponentType<{ size?: number }>;
};

const productNav: NavItem[] = [
  { id: "risk", label: "主题态势", helper: "聚合分析热点主题", icon: Radar },
  { id: "data", label: "数据", helper: "检索与抓取", icon: Search },
  { id: "evidence", label: "证据", helper: "复核与脱敏", icon: ShieldCheck },
  { id: "mainline", label: "主线", helper: "建模确认", icon: GitBranch },
  { id: "worldline", label: "推演", helper: "世界线分支", icon: MapPinned },
  { id: "council", label: "研判", helper: "多主体校准", icon: Users },
  { id: "brief", label: "汇报", helper: "任务闭环", icon: FileCheck2 },
  { id: "audit", label: "审计", helper: "来源策略", icon: ClipboardList }
];

const apiDrivenPages = new Set<ProductPageId>(["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"]);

export function ProductPage({ caseId, page }: ProductPageProps) {
  if (apiDrivenPages.has(page)) {
    return <ApiDrivenProductPage caseId={caseId} page={page as ProductPageName} />;
  }
  return <LegacyProductPage caseId={caseId} page={page} />;
}

function LegacyProductPage({ caseId, page }: ProductPageProps) {
  const queryClient = useQueryClient();
  const bundleQuery = useQuery({
    queryKey: ["case-bundle", caseId],
    queryFn: () => api.getCaseBundle(caseId)
  });
  const mapQuery = useQuery({
    queryKey: ["map-layers", caseId],
    enabled: page === "risk",
    queryFn: () => api.getMapLayers(caseId)
  });
  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["case-bundle", caseId] });
      await queryClient.invalidateQueries({ queryKey: ["map-layers", caseId] });
    }
  });

  const bundle = bundleQuery.data;
  const pageTitle = productNav.find((item) => item.id === page)?.label ?? "主题态势";
  if (bundleQuery.isLoading) {
    return (
      <ProductFrame caseId={caseId} page={page} title={pageTitle}>
        <div className="product-stage">
          <SkeletonPanel rows={12} />
        </div>
      </ProductFrame>
    );
  }

  if (bundleQuery.isError || !bundle) {
    return (
      <ProductFrame caseId={caseId} page={page} title={pageTitle}>
        <div className="product-stage">
          <InlineError title="案例数据不可用" message={(bundleQuery.error as Error | undefined)?.message ?? "未加载案例。"} />
        </div>
      </ProductFrame>
    );
  }

  if (page === "risk") {
    return <StaticRiskDashboard bundle={bundle} mapLayers={mapQuery.data} />;
  }

  return (
    <ProductFrame caseId={caseId} page={page} title={pageTitle} bundle={bundle}>
      {page === "data" ? <DataWorkbench bundle={bundle} action={action} /> : null}
      {page === "evidence" ? <EvidenceReviewPage bundle={bundle} action={action} /> : null}
      {page === "mainline" ? <MainlineBuilderPage bundle={bundle} action={action} /> : null}
      {page === "worldline" ? <WorldlinePage bundle={bundle} action={action} /> : null}
      {page === "council" ? <CouncilPage bundle={bundle} action={action} /> : null}
      {page === "brief" ? <DecisionBriefPage bundle={bundle} action={action} /> : null}
      {page === "audit" ? <AuditPage bundle={bundle} /> : null}
    </ProductFrame>
  );
}

function ProductFrame({
  caseId,
  page,
  title,
  bundle,
  children
}: {
  caseId: string;
  page: ProductPageId;
  title: string;
  bundle?: CaseBundle;
  children: React.ReactNode;
}) {
  const formalReady = Boolean(bundle?.report?.payload.formal_conclusion);
  const copy = bundle ? getScenarioCopy(bundle) : undefined;
  return (
    <div className="wo-app">
      <header className="wo-topbar">
        <Link to="/cases/$caseId/$page" params={{ caseId, page: "risk" }} className="wo-brand" aria-label="世界线观察器首页">
          <span className="wo-brand-mark" />
          <span>
            WORLDLINE OBSERVER
            <small>P0 研判闭环</small>
          </span>
        </Link>
        <nav className="wo-step-nav" aria-label="P0 产品流程">
          {productNav.map((item, index) => {
            const Icon = item.icon;
            return (
              <Link key={item.id} to="/cases/$caseId/$page" params={{ caseId, page: item.id }} className={page === item.id ? "wo-step active" : "wo-step"}>
                <i>{index + 1}</i>
                <b>
                  <Icon size={14} />
                  {item.label}
                  <span>{item.helper}</span>
                </b>
              </Link>
            );
          })}
        </nav>
        <div className="wo-status">
          <span className="live-dot" />
          <span>{bundle?.case.id ?? caseId}</span>
          <strong>{formalReady ? "简报已确认" : title}</strong>
          <Link to="/admin" className="wo-admin-link">
            调试台
          </Link>
        </div>
      </header>
      {bundle ? (
        <section className="wo-topic-head">
          <div>
            <span className="wo-back">P0 / {zh(bundle.case.scenario_type)} / {copy?.topicMeta}</span>
            <h1>
              {copy?.topicTitle ?? zh(bundle.case.title)}
              {page === "risk" ? <span className="hot-tag">热度榜 TOP1</span> : null}
            </h1>
            <p>{zh(String(bundle.case.payload.boundary ?? ""))}</p>
          </div>
          <div className="wo-head-actions">
            <CaseJump currentCaseId={caseId} />
            <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId, page: "brief" }}>
              查看汇报
            </Link>
          </div>
        </section>
      ) : null}
      <main className="wo-page-shell">{children}</main>
    </div>
  );
}

function CaseJump({ currentCaseId }: { currentCaseId: string }) {
  const casesQuery = useQuery({ queryKey: ["cases"], queryFn: api.listCases });
  return (
    <div className="wo-case-switch" aria-label="案例切换">
      {(casesQuery.data ?? [{ id: currentCaseId, title: currentCaseId } as CaseOut]).map((item) => (
        <Link key={item.id} to="/cases/$caseId/$page" params={{ caseId: item.id, page: "risk" }} className={item.id === currentCaseId ? "active" : ""} title={zh(item.title)}>
          {item.id.includes("COMMUNITY") ? "社区" : "校园"}
        </Link>
      ))}
    </div>
  );
}

const staticRiskColors = {
  blue: "#2f6df6",
  green: "#18a873",
  amber: "#d78925",
  red: "#df4b54",
  violet: "#7f63c9",
  cyan: "#009fb7",
  gray: "#a9b0bb"
} as const;

type StaticRiskTone = keyof typeof staticRiskColors;

type StaticRiskKpi = {
  label: string;
  value: string;
  hint: string;
  icon: string;
  tone: StaticRiskTone;
  gauge?: boolean;
};

type StaticRiskRow = {
  name: string;
  amount: string;
  contribution: string;
  trend: string;
  trust: string;
  tone: StaticRiskTone;
};

type StaticRiskVideo = {
  title: string;
  source: string;
  metric: string;
  duration: string;
  live?: boolean;
};

type StaticRiskCandidate = {
  title: string;
  description: string;
  tags: string[];
};

function StaticRiskDashboard({ bundle, mapLayers }: { bundle: CaseBundle; mapLayers?: MapLayers }) {
  const copy = getScenarioCopy(bundle);
  const summary = getBundleSummary(bundle);
  const heatScore = Math.max(52, ...bundle.signals.map((item) => item.scores.onlineHeat ?? 0));
  const riskScore = Math.max(42, ...bundle.worldline_nodes.map((item) => item.risk));
  const discussionCount = Math.max(8620, Math.round(heatScore * 332 + bundle.signals.length * 1120));
  const featureCount = mapLayers?.eventPoints.features.length ?? bundle.signals.length;
  const reviewSignals = bundle.evidence.filter((item) => item.status !== "confirmed_fact");
  const sourceRows = buildStaticRiskSources(bundle);
  const platformRows = buildStaticPlatformRows(bundle);
  const videos = buildStaticRiskVideos(bundle, copy);
  const candidates = buildStaticRiskCandidates(bundle, copy);
  const mind = getStaticMindMap(copy);
  const kpis: StaticRiskKpi[] = [
    { label: "主题热度", value: formatCompactCount(heatScore * 1000 + 520), hint: "较24小时前 +136%", icon: "热", tone: "red" },
    { label: "近30分钟增速", value: "+128%", hint: "较上一30分钟 +62%", icon: "速", tone: "green" },
    { label: "同城讨论占比", value: `${Math.min(86, Math.max(61, Math.round(heatScore * 0.82)))}%`, hint: "较上一30分钟 +9%", icon: "城", tone: "blue" },
    { label: "视频/直播", value: `${Math.max(48, bundle.signals.length * 42)}/${Math.max(4, Math.ceil(featureCount * 1.8))}`, hint: "较6小时前 +62%", icon: "视", tone: "blue" },
    { label: "多平台数", value: String(Math.max(6, sourceRows.length + summary.regionCount)), hint: "较6小时前 +2", icon: "源", tone: "green" },
    { label: "负向情绪占比", value: `${Math.min(72, Math.max(36, Math.round(riskScore * 0.7)))}%`, hint: "较上一30分钟 +11%", icon: "情", tone: "amber" },
    { label: "破圈可能性", value: `${Math.min(86, Math.max(42, Math.round(riskScore * 0.64)))}%`, hint: riskScore >= 80 ? "中高" : "中等偏高", icon: "圈", tone: "blue", gauge: true }
  ];
  return (
    <div className="static-risk" data-testid="product-risk-page">
      <div className="app">
        <header className="topbar">
          <Link to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "risk" }} className="brand" aria-label="世界线观察器首页">
            <span className="brand-mark" />
            <span>
              WORLDLINE OBSERVER
              <small>P0 城市事件世界线</small>
            </span>
          </Link>
          <nav className="step-nav" aria-label="P0 产品流程">
            {[
              ["risk", "城市态势感知", "发现城市正在发生的事", false],
              ["risk", "主题态势", "聚合分析某个热点主题", true],
              ["mainline", "主线建模", "梳理证据与关键支点", false],
              ["worldline", "世界线推演", "推演多种可能走向", false],
              ["council", "多主体研判", "评估各方反应与影响", false],
              ["brief", "处置建议", "形成策略建议与报告", false]
            ].map(([page, label, helper, active], index) => (
              <Link
                key={`${label}-${index}`}
                className={active ? "step-tab active" : "step-tab"}
                to="/cases/$caseId/$page"
                params={{ caseId: bundle.case.id, page: page as ProductPageId }}
              >
                <i>{index + 1}</i>
                <b>
                  {label}
                  <span>{helper}</span>
                </b>
              </Link>
            ))}
          </nav>
          <div className="top-icons">
            <button type="button" aria-label="工具">♧</button>
            <button type="button" aria-label="帮助">?</button>
            <button type="button" className="avatar" aria-label="账户">●</button>
          </div>
        </header>

        <section className="topic-head">
          <Link className="back-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "risk" }}>
            ← 返回城市态势
          </Link>
          <div className="topic-title">
            <h1>
              {copy.topicTitle}
              <span className="hot-tag">热度榜 TOP1</span>
            </h1>
            <p>{copy.topicMeta}</p>
          </div>
          <div className="topic-controls">
            <span>时间范围</span>
            <select className="select" aria-label="时间范围" defaultValue="近24小时">
              <option>近24小时</option>
            </select>
            <span>最后更新：{new Date().toLocaleString("zh-CN", { hour12: false })}</span>
            <span className="live-dot" />
            <Link className="export export-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "brief" }}>
              导出报告
            </Link>
          </div>
        </section>

        <section className="kpi-row" id="kpiRow">
          {kpis.map((kpi) => (
            <div className="kpi" style={staticVars({ "--tone": staticRiskColors[kpi.tone] })} key={kpi.label}>
              <div className="kpi-icon">{kpi.icon}</div>
              <div>
                <label>{kpi.label}</label>
                <strong>{kpi.value}</strong>
                <small>{kpi.hint}</small>
              </div>
              {kpi.gauge ? <div className="gauge" /> : <StaticSpark color={staticRiskColors[kpi.tone]} />}
            </div>
          ))}
        </section>

        <main className="main">
          <aside className="left-stack">
            <section className="panel">
              <div className="panel-header">
                <div className="panel-title">
                  主题信号来源 <span>按贡献度</span>
                </div>
              </div>
              <div className="source-table">
                <div className="source-head">
                  <span>数据类型</span>
                  <span>信号量</span>
                  <span>热度贡献</span>
                  <span>趋势</span>
                  <span>可信度</span>
                </div>
                <div id="sourceRows">
                  {sourceRows.map((row) => (
                    <div className="source-row" key={row.name}>
                      <div className="source-name">
                        <span className="src-icon" style={staticVars({ "--tone": staticRiskColors[row.tone] })}>{row.name.slice(0, 1)}</span>
                        <span>{row.name}</span>
                      </div>
                      <span>{row.amount}</span>
                      <span>{row.contribution}</span>
                      <span className="trend">{row.trend}</span>
                      <span className="trust" style={staticVars({ "--tone": staticRiskColors[row.tone] })}>{row.trust}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
            <section className="panel">
              <div className="panel-header">
                <div className="panel-title">
                  关联事件 <span>候选</span>
                </div>
                <Link className="more" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>
                  更多 ›
                </Link>
              </div>
              <div className="related-list" id="relatedEvents">
                {bundle.signals.slice(0, 3).map((signal, index) => (
                  <Link className="related-card" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }} key={signal.id}>
                    <b>{zh(signal.title)}</b>
                    <span>
                      <em>热度：{formatCompactCount((signal.scores.onlineHeat ?? 0) * 210 + 860)}</em>
                      <i className="tag-mini">{index === 0 ? "当前" : index === 1 ? "风险" : "相似"}</i>
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          </aside>

          <section className="center">
            <section className="panel stage-panel">
              <div className="stage-title">主题传播阶段判断</div>
              <div className="stage-line">
                {["萌芽出现", "小范围讨论", "同城讨论升温", "跨圈层扩散", "破圈传播", "持续发酵"].map((stage, index) => (
                  <div key={stage} className={index < 2 ? "stage done" : index === 2 ? "stage active" : "stage"}>
                    <div className="stage-dot" />
                    <b>{stage}</b>
                    <span>{index < 2 ? "已完成" : index === 2 ? "当前阶段" : "待发生"}</span>
                  </div>
                ))}
              </div>
              <p className="stage-note">{copy.stageNote}</p>
            </section>

            <section className="analysis-grid">
              <div className="panel box">
                <div className="box-title">
                  主题热度趋势 <span>Y轴：热度指数 / X轴：近24小时</span>
                </div>
                <StaticTopicChart heat={heatScore} discussion={discussionCount} />
                <div className="time-chips">
                  {["1小时", "3小时", "6小时", "12小时", "24小时"].map((item) => (
                    <button type="button" className={item === "24小时" ? "active" : ""} key={item}>{item}</button>
                  ))}
                </div>
              </div>
              <div className="panel box">
                <div className="box-title">
                  传播路径与扩散地图 <span>左到右扩散思维导图</span>
                </div>
                <div className="route-canvas mind-map">
                  <svg className="mind-svg" viewBox="0 0 640 260" preserveAspectRatio="none" aria-hidden="true">
                    <path d="M92 130 C130 130,143 92,184 92" stroke="#df4b54" strokeWidth="2.4" fill="none" />
                    <path d="M92 130 C135 130,148 164,190 166" stroke="#df4b54" strokeWidth="2.4" fill="none" />
                    <path d="M274 92 C316 92,330 76,372 72" stroke="#2f6df6" strokeWidth="2.4" fill="none" />
                    <path d="M274 166 C316 166,330 181,374 188" stroke="#18a873" strokeWidth="2.4" fill="none" />
                    <path d="M462 72 C505 76,520 92,562 96" stroke="#2f6df6" strokeWidth="2.4" fill="none" />
                    <path d="M462 188 C505 178,520 157,562 151" stroke="#18a873" strokeWidth="2.4" fill="none" />
                  </svg>
                  {mind.map((node) => (
                    <div className={`mind-node ${node.kind}`} style={node.style} key={node.title}>
                      <b>{node.title}</b>
                      <span>{node.subtitle}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel box platform-panel">
                <div className="box-title">
                  平台分布 <span>来源平台</span>
                </div>
                <div className="platform-board">
                  <div className="platform-total">
                    <span>总量</span>
                    <b>{formatCompactCount(discussionCount)}</b>
                    <span>条/场</span>
                  </div>
                  <div>
                    <div className="platform-list platform-bars" id="platformList">
                      {platformRows.map((row) => (
                        <div className="platform-row" key={row.name}>
                          <i className="dot" style={staticVars({ "--tone": staticRiskColors[row.tone], background: staticRiskColors[row.tone] })} />
                          <span>{row.name}</span>
                          <div className="platform-bar">
                            <i style={staticVars({ "--v": `${row.rate}%`, "--tone": staticRiskColors[row.tone] })} />
                          </div>
                          <b>{formatCompactCount(row.count)} ({row.rate}%)</b>
                        </div>
                      ))}
                    </div>
                    <div className="platform-insight">{copy.topicScope} 是当前主要观察范围，未授权来源只进入审计。</div>
                  </div>
                </div>
              </div>
            </section>

            <section className="panel video-strip">
              <div className="box-title">
                视频 / 直播热点 <span>按热度</span>
                <Link className="more" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>
                  查看全部视频/直播（{Math.max(48, bundle.signals.length * 42)}个）
                </Link>
              </div>
              <div className="video-grid" id="videoGrid">
                {videos.map((video, index) => (
                  <div className="video-card" key={`${video.title}-${index}`}>
                    <div className="thumb">
                      {video.live ? <span className="live">直播中</span> : null}
                      <span className="duration">{video.duration}</span>
                    </div>
                    <b>{video.title}</b>
                    <span>
                      {video.source}
                      <br />
                      {video.metric}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          </section>

          <aside className="right-stack">
            <section className="panel emotion-panel">
              <div className="panel-title">
                同城情绪与立场 <span>主要立场分布 / 高频热词</span>
              </div>
              <div className="emotion-card">
                <div className="emotion-donut">
                  <div className="emotion-inner">
                    {Math.min(72, Math.max(36, Math.round(riskScore * 0.7)))}%
                    <span>负向</span>
                  </div>
                </div>
                <div className="stance-list">
                  {[
                    ["负向/不满", 62, "red"],
                    ["中立/观望", 26, "amber"],
                    ["支持/理解", 9, "green"],
                    ["不确定/无关", 3, "gray"]
                  ].map(([label, value, tone]) => (
                    <div className="stance" key={String(label)}>
                      <span>{label}</span>
                      <div className="bar">
                        <i style={staticVars({ "--v": `${value}%`, "--tone": staticRiskColors[tone as StaticRiskTone] })} />
                      </div>
                      <b>{value}%</b>
                    </div>
                  ))}
                </div>
              </div>
              <div className="emotion-section">
                <b>高频热词（全城）</b>
                <span>近24小时</span>
              </div>
              <div className="hotword-list">
                {copy.hotwords.map((item) => <span className="hotword" key={item}>{item}</span>)}
              </div>
              <div className="emotion-section">
                <b>代表性立场</b>
                <span>热度排序</span>
              </div>
              <div className="comment-list" id="comments">
                {copy.comments.map((comment, index) => (
                  <div className="comment" key={comment[0]}>
                    <span className="comment-no" style={staticVars({ "--tone": staticRiskColors[comment[2]] })}>{index + 1}</span>
                    <div>
                      <b>{comment[0]}</b>
                      <span>{comment[1]}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel next-panel">
              <div className="panel-title">
                下一步建议 <span>基于概率与趋势</span>
              </div>
              <div className="var-list" id="variables">
                {copy.variables.map((item, index) => (
                  <div className="var-row" key={item}>
                    <i>{index + 1}</i>
                    <div>
                      <b>{item}</b>
                      <span>建议持续观察</span>
                    </div>
                    <span>›</span>
                  </div>
                ))}
              </div>
              <div className="action-row">
                <Link className="primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "mainline" }}>进入主线建模</Link>
                <Link className="outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "evidence" }}>转入证据复核</Link>
                <Link className="outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>继续观察</Link>
              </div>
              <div className="secondary-actions">
                <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>查看全部信号</Link>
                <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "audit" }}>案例库召回</Link>
                <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "brief" }}>复盘沉淀</Link>
                <Link className="small-btn" to="/admin">模型配置</Link>
              </div>
            </section>
          </aside>
        </main>

        <section className="bottom">
          <section className="panel mainline-cards">
            <div className="panel-title">
              <span className="title-copy">
                候选主线 <span>系统聚合建议</span>
              </span>
              <Link className="more" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "mainline" }}>
                更多主线 ›
              </Link>
            </div>
            <div className="candidate-grid" id="candidates">
              {candidates.map((candidate) => (
                <div className="candidate" key={candidate.title}>
                  <h3>{candidate.title}</h3>
                  <p>{candidate.description}</p>
                  <div className="tags">
                    {candidate.tags.map((tag, index) => <span className="tag" key={`${tag}-${index}`}>{tag}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </section>
          <section className="panel small-panel">
            <div className="panel-title">
              需要关注的关键变量 <span>{copy.variables.length}项</span>
            </div>
            <div className="list compact-list" id="keyVars">
              {copy.variables.map((item, index) => (
                <div className="list-row" key={item}>
                  <i className="small-dot" style={staticVars({ "--tone": index < 2 ? staticRiskColors.red : staticRiskColors.blue, background: index < 2 ? staticRiskColors.red : staticRiskColors.blue })} />
                  <span>{item}</span>
                  <b>{index < 2 ? "高" : "中"}</b>
                </div>
              ))}
            </div>
          </section>
          <section className="panel small-panel">
            <div className="panel-title">
              需要复核的信号 <span>{reviewSignals.length}条</span>
            </div>
            <div className="list compact-list signal-list" id="reviewSignals">
              {reviewSignals.slice(0, 5).map((item, index) => (
                <div className="list-row" key={item.id}>
                  <i className="small-dot" style={staticVars({ "--tone": index < 2 ? staticRiskColors.amber : staticRiskColors.blue, background: index < 2 ? staticRiskColors.amber : staticRiskColors.blue })} />
                  <span>{zh(item.title)} {item.id}</span>
                  <b>›</b>
                </div>
              ))}
            </div>
          </section>
          <section className="panel next-panel next-compact">
            <div className="panel-title">
              下一步建议 <span>基于概率与趋势</span>
            </div>
            <div className="var-list" id="bottomNextVariables">
              {copy.variables.slice(0, 2).map((item, index) => (
                <div className="var-row" key={item}>
                  <i>{index + 1}</i>
                  <div>
                    <b>{item}</b>
                    <span>优先推进</span>
                  </div>
                  <span>›</span>
                </div>
              ))}
            </div>
            <div className="action-row">
              <Link className="primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "mainline" }}>进入主线建模</Link>
              <Link className="outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "evidence" }}>证据复核</Link>
            </div>
            <div className="secondary-actions">
              <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>查看全部信号</Link>
              <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "audit" }}>案例库召回</Link>
              <Link className="small-btn" to="/admin">模型配置</Link>
            </div>
          </section>
        </section>
      </div>
    </div>
  );
}

function StaticSpark({ color }: { color: string }) {
  return (
    <svg className="spark" viewBox="0 0 80 30" aria-hidden="true">
      <path style={staticVars({ "--tone": color })} d="M2 24 C12 20 16 21 24 15 S38 18 45 10 S56 13 64 7 S72 10 78 3" />
    </svg>
  );
}

function StaticTopicChart({ heat, discussion }: { heat: number; discussion: number }) {
  return (
    <div className="line-chart topic-chart">
      <div className="chart-legend">
        <span><i style={staticVars({ "--tone": staticRiskColors.red })} />主题热度</span>
        <span><i style={staticVars({ "--tone": staticRiskColors.blue })} />同城讨论量</span>
      </div>
      <span className="axis-title-y">热度指数 / 讨论量</span>
      <span className="axis-title-x">近24小时</span>
      <svg className="chart-svg" viewBox="0 0 420 240" preserveAspectRatio="none" aria-label="主题热度与同城讨论量近24小时趋势">
        <line className="axis" x1="48" y1="22" x2="48" y2="204" />
        <line className="axis" x1="48" y1="204" x2="400" y2="204" />
        <line className="grid" x1="48" y1="52" x2="400" y2="52" />
        <line className="grid" x1="48" y1="92" x2="400" y2="92" />
        <line className="grid" x1="48" y1="132" x2="400" y2="132" />
        <line className="grid" x1="48" y1="172" x2="400" y2="172" />
        <text x="8" y="26">90k</text>
        <text x="10" y="96">45k</text>
        <text x="16" y="204">0</text>
        <text x="47" y="226">0时</text>
        <text x="132" y="226">6时</text>
        <text x="218" y="226">12时</text>
        <text x="304" y="226">18时</text>
        <text x="376" y="226">24时</text>
        <path className="series-hot" d="M48 186 C78 176,94 164,114 151 S156 140,174 121 S212 83,238 73 S275 42,302 56 S354 33,400 17" />
        <path className="series-city" d="M48 202 C80 190,111 180,142 164 S197 144,226 129 S271 113,304 99 S356 91,400 80" />
        <circle cx="400" cy="17" r="4.5" fill="#df4b54" />
        <circle cx="400" cy="80" r="4.5" fill="#2f6df6" />
        <text x="343" y="31" fill="#df4b54">{formatCompactCount(heat * 1000 + 520)}</text>
        <text x="338" y="74" fill="#2f6df6">{formatCompactCount(discussion)}</text>
      </svg>
    </div>
  );
}

function buildStaticRiskSources(bundle: CaseBundle): StaticRiskRow[] {
  const copy = getScenarioCopy(bundle);
  const acceptedSources = bundle.source_records.map((source, index) => ({
    name: zh(source.source_name),
    amount: String(Math.max(15, Math.round(source.trust * 240) + index * 9)),
    contribution: `${Math.max(4, Math.round(source.trust * 34) - index * 2)}%`,
    trend: source.accepted ? "↑" : "—",
    trust: source.accepted ? (source.trust >= 0.8 ? "高" : "中") : "低",
    tone: source.accepted ? (source.access_mode === "authorized_export" ? "blue" : source.access_mode === "manual_upload" ? "green" : "violet") : "red"
  })) satisfies StaticRiskRow[];
  const scenarioRows: StaticRiskRow[] = copy === campusCopy ? [
    { name: "视频/直播素材", amount: `${Math.max(48, bundle.signals.length * 42)} / ${Math.max(4, bundle.signals.length * 3)}`, contribution: "32%", trend: "↑", trust: "中", tone: "blue" },
    { name: "历史相似案例", amount: "40", contribution: "5%", trend: "↑", trust: "中", tone: "amber" },
    { name: "人工复核", amount: String(bundle.evidence.length + 11), contribution: "4%", trend: "↑", trust: "高", tone: "cyan" },
    { name: "隐私风险标记", amount: String(bundle.evidence.filter((item) => item.sensitivity !== "normal").length + 20), contribution: "3%", trend: "↑", trust: "中", tone: "red" }
  ] : [
    { name: "热线人工摘要", amount: String(bundle.evidence.length * 18 + 24), contribution: "24%", trend: "↑", trust: "高", tone: "cyan" },
    { name: "社区论坛", amount: String(bundle.signals.length * 44 + 38), contribution: "22%", trend: "↑", trust: "中", tone: "violet" },
    { name: "物业窗口记录", amount: String(bundle.signals.length * 18 + 12), contribution: "14%", trend: "↑", trust: "中", tone: "amber" },
    { name: "街道协调纪要", amount: String(bundle.tasks.length + 9), contribution: "8%", trend: "—", trust: "高", tone: "green" }
  ];
  return [...scenarioRows, ...acceptedSources].slice(0, 8);
}

function buildStaticPlatformRows(bundle: CaseBundle) {
  const copy = getScenarioCopy(bundle);
  const names = copy === campusCopy
    ? ["短视频平台", "本地社媒", "家长群摘要", "本地媒体", "论坛/问答", "政务渠道", "人工复核"]
    : ["社区论坛", "热线摘要", "物业窗口", "街道渠道", "居民群摘要", "供水单位", "人工复核"];
  const tones: StaticRiskTone[] = ["blue", "red", "amber", "green", "violet", "cyan", "green"];
  const rates = [39, 18, 10, 9, 8, 6, 3];
  const heat = Math.max(52, ...bundle.signals.map((item) => item.scores.onlineHeat ?? 0));
  const total = Math.round(heat * 332 + bundle.signals.length * 1120);
  return names.map((name, index) => ({
    name,
    rate: rates[index],
    count: Math.round(total * rates[index] / 100),
    tone: tones[index]
  }));
}

function buildStaticRiskVideos(bundle: CaseBundle, copy: ScenarioCopy): StaticRiskVideo[] {
  const fallback = copy === campusCopy ? [
    "现场沟通片段",
    "诉求沟通直播切片",
    "本地媒体整理关键时间线",
    "群聊截图被搬运讨论",
    "心理援助与家校沟通提醒"
  ] : [
    "居民集中咨询片段",
    "物业窗口答复录音摘要",
    "街道协调进展说明",
    "论坛追问恢复时间",
    "临时供水安排提醒"
  ];
  return Array.from({ length: 5 }).map((_, index) => {
    const signal = bundle.signals[index % Math.max(1, bundle.signals.length)];
    const score = signal?.scores.onlineHeat ?? 42;
    return {
      title: signal ? zh(signal.title) : fallback[index],
      source: index === 1 ? "直播回放｜10:47 开始" : index === 2 ? "本地新闻｜11:05 发布" : "同城平台｜近24小时",
      metric: `播放 ${formatCompactCount(score * 2100 + 8965)}｜评论 ${formatCompactCount(score * 62 + 318)}`,
      duration: index === 1 ? "12:00" : index === 2 ? "01:38" : index === 3 ? "00:28" : "00:55",
      live: index === 1
    };
  });
}

function buildStaticRiskCandidates(bundle: CaseBundle, copy: ScenarioCopy): StaticRiskCandidate[] {
  const mainlineTitle = zh(bundle.mainline?.title ?? copy.coreJudgement);
  const confidence = Math.round((bundle.mainline?.confidence ?? 0.65) * 100);
  const support = bundle.mainline?.payload.support_points?.map(zh) ?? copy.variables.slice(0, 3);
  const nodes = [...bundle.worldline_nodes].sort((a, b) => b.probability - a.probability);
  const second = nodes[0];
  const third = nodes[1];
  return [
    {
      title: `主线 A（概率 ${confidence}%）`,
      description: mainlineTitle,
      tags: support.slice(0, 3)
    },
    {
      title: `主线 B（概率 ${formatProbability(second?.probability, 28)}%）`,
      description: zh(second?.title ?? copy.variables[0]),
      tags: (second?.payload.support_point_state?.map(zh) ?? copy.variables).slice(0, 3)
    },
    {
      title: `主线 C（概率 ${formatProbability(third?.probability, 18)}%）`,
      description: zh(third?.title ?? copy.variables[1]),
      tags: copy.variables.slice(2, 5)
    }
  ];
}

function getStaticMindMap(copy: ScenarioCopy) {
  const campus = copy === campusCopy;
  const labels = campus
    ? [
      ["现场视频", "首发扩散", "source", { left: "3%", top: "39%" }],
      ["家属诉求", "同城平台", "core", { left: "25%", top: "18%" }],
      ["学生群截图", "隐私复核", "core", { left: "26%", top: "62%" }],
      ["同城居民", "评论追问", "", { left: "52%", top: "13%" }],
      ["平台处置", "降权拦截", "", { left: "52%", top: "70%" }],
      ["本地媒体", "时间线整理", "", { right: "3%", top: "23%" }],
      ["政务回应", "证据窗口", "", { right: "3%", top: "57%" }]
    ]
    : [
      ["居民咨询", "首发聚合", "source", { left: "3%", top: "39%" }],
      ["物业窗口", "口径差异", "core", { left: "25%", top: "18%" }],
      ["热线摘要", "人工复核", "core", { left: "26%", top: "62%" }],
      ["社区论坛", "追问恢复", "", { left: "52%", top: "13%" }],
      ["街道协调", "统一答疑", "", { left: "52%", top: "70%" }],
      ["供水单位", "维修时间", "", { right: "3%", top: "23%" }],
      ["居民分流", "临时供水", "", { right: "3%", top: "57%" }]
    ];
  return labels.map(([title, subtitle, kind, style]) => ({ title, subtitle, kind, style })) as Array<{
    title: string;
    subtitle: string;
    kind: string;
    style: React.CSSProperties;
  }>;
}

function formatCompactCount(value: number) {
  return Math.round(value).toLocaleString("zh-CN");
}

function formatProbability(value: number | undefined, fallback: number) {
  const normalized = value ?? fallback;
  return Math.round(normalized > 1 ? normalized : normalized * 100);
}

function staticVars(vars: Record<string, string | number>) {
  return vars as React.CSSProperties;
}

function RiskDashboard({ bundle, mapLayers }: { bundle: CaseBundle; mapLayers?: MapLayers }) {
  const summary = getBundleSummary(bundle);
  const copy = getScenarioCopy(bundle);
  const heat = Math.max(0, ...bundle.signals.map((item) => item.scores.onlineHeat ?? 0));
  const risk = Math.max(0, ...bundle.worldline_nodes.map((item) => item.risk));
  const featureCount = mapLayers?.eventPoints.features.length ?? bundle.signals.length;
  const mainlineHref = { to: "/cases/$caseId/$page" as const, params: { caseId: bundle.case.id, page: "mainline" as const } };
  return (
    <div className="risk-page product-stage" data-testid="product-risk-page">
      <section className="wo-kpi-row">
        <KpiCard icon={Radar} label="主题热度" value={heat * 1000 + 520} hint="较24小时前 +136%" tone="red" />
        <KpiCard icon={Activity} label="近30分钟增速" value="+128%" hint="较上一30分钟 +62%" tone="green" />
        <KpiCard icon={ShieldCheck} label="证据量" value={bundle.evidence.length} hint={`${summary.reviewCount} 条待复核`} tone="blue" />
        <KpiCard icon={Layers} label="地图要素" value={featureCount} hint={`${summary.regionCount} 个区域`} tone="green" />
        <KpiCard icon={Scale} label="来源闸口" value={summary.blockedSources} hint="阻断来源仍可审计" tone={summary.blockedSources ? "amber" : "green"} />
        <KpiCard icon={FileCheck2} label="报告闸口" value={summary.formalReady ? "已就绪" : "待确认"} hint="高风险结论需人工确认" tone={summary.formalReady ? "green" : "amber"} />
        <KpiCard icon={AlertTriangle} label="破圈可能性" value={`${Math.max(42, Math.round(risk * 0.64))}%`} hint={zh(summary.riskNode?.title ?? "待选择风险节点")} tone={risk >= 80 ? "red" : "amber"} />
      </section>

      <div className="risk-grid">
        <aside className="risk-left">
          <Panel title="主题信号来源" subtitle="按贡献度">
            <SourceTable sources={bundle.source_records} />
          </Panel>
          <Panel title="关联事件" subtitle="候选">
            <div className="related-list">
              {bundle.signals.slice(0, 3).map((signal) => (
                <Link key={signal.id} className="related-card" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>
                  <b>{zh(signal.title)}</b>
                  <span>{zh(signal.region_id)}</span>
                </Link>
              ))}
            </div>
          </Panel>
        </aside>

        <section className="risk-center">
          <Panel title="主题传播阶段判断" subtitle="主题生命周期">
            <div className="stage-line">
              {["萌芽出现", "小范围讨论", "同城讨论升温", "跨圈层扩散", "破圈传播", "持续发酵"].map((stage, index) => (
                <div key={stage} className={index < 2 ? "stage done" : index === 2 ? "stage active" : "stage"}>
                  <span className="stage-dot" />
                  <b>{stage}</b>
                  <small>{index === 2 ? "当前阶段" : index < 2 ? "已完成" : "待发生"}</small>
                </div>
              ))}
            </div>
            <p className="stage-note">{copy.stageNote}</p>
          </Panel>
          <div className="analysis-grid">
            <Panel title="主题热度趋势" subtitle="Y轴：热度指数 / X轴：近24小时">
              <TrendChart signals={bundle.signals} />
            </Panel>
            <Panel title="传播路径与扩散地图" subtitle="左到右扩散思维导图">
              <SpreadMap bundle={bundle} />
            </Panel>
            <Panel title="平台分布" subtitle="来源平台">
              <PlatformDistribution sources={bundle.source_records} />
            </Panel>
          </div>
          <Panel title="视频 / 直播热点" subtitle="按热度">
            <div className="video-grid">
              {bundle.signals.map((signal) => (
                <article className="video-card" key={signal.id}>
                  <div className="video-thumb">
                    <span>{signal.priority}</span>
                    <b>{signal.scores.onlineHeat ?? 0}</b>
                  </div>
                  <strong>{zh(signal.title)}</strong>
                  <small>{zh(signal.summary)}</small>
                </article>
              ))}
            </div>
          </Panel>
        </section>

        <aside className="risk-right">
          <Panel title="同城情绪与立场" subtitle="主要立场分布 / 高频热词">
            <EmotionPanel bundle={bundle} />
            <div className="emotion-section"><b>高频热词（全城）</b><span>近24小时</span></div>
            <div className="hotword-list">{copy.hotwords.map((item) => <span className="hotword" key={item}>{item}</span>)}</div>
            <div className="emotion-section"><b>代表性立场</b><span>热度排序</span></div>
            <div className="comment-list">
              {copy.comments.map((comment, index) => (
                <div className={`comment tone-${comment[2]}`} key={comment[0]}>
                  <span className="comment-no">{index + 1}</span>
                  <div><b>{comment[0]}</b><span>{comment[1]}</span></div>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="下一步建议" subtitle="基于概率与趋势">
            <div className="recommend-list">
              {summary.recommendations.map((item, index) => (
                <div key={item} className="recommend-row">
                  <i>{index + 1}</i>
                  <b>{item}</b>
                  <span>{index < 2 ? "优先推进" : "持续观察"}</span>
                </div>
              ))}
            </div>
            <div className="wo-action-row">
              <Link className="wo-primary" {...mainlineHref}>
                进入主线建模
              </Link>
              <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "evidence" }}>
                转入证据复核
              </Link>
              <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>
                继续观察
              </Link>
            </div>
            <div className="secondary-actions">
              <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "data" }}>查看全部信号</Link>
              <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "audit" }}>案例库召回</Link>
              <Link className="small-btn" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "brief" }}>复盘沉淀</Link>
              <Link className="small-btn" to="/admin">模型配置</Link>
            </div>
          </Panel>
        </aside>
      </div>

      <section className="risk-bottom">
        <Panel title="候选主线" subtitle="系统聚合建议">
          <article className="candidate-card">
            <h3>{zh(bundle.mainline?.title ?? "暂无主线")}</h3>
            <p>{zh(bundle.report?.payload.draft_summary ?? "进入数据与证据页后形成主线草稿。")}</p>
            <div className="chip-row">
              {bundle.mainline?.payload.support_points?.map((item) => <span className="wo-chip" key={item}>{zh(item)}</span>)}
            </div>
          </article>
        </Panel>
        <Panel title="需要关注的关键变量" subtitle={`${summary.recommendations.length}项`}>
          <CompactList items={summary.recommendations} />
        </Panel>
        <Panel title="需要复核的信号" subtitle={`${summary.reviewCount}条`}>
          <CompactList items={bundle.evidence.filter((item) => item.status !== "confirmed_fact").map((item) => zh(item.title))} />
        </Panel>
        <Panel title="下一步建议" subtitle="基于概率与趋势">
          <CompactList items={copy.variables.slice(0, 3)} />
        </Panel>
      </section>
    </div>
  );
}

function DataWorkbench({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const copy = getScenarioCopy(bundle);
  const [selectedSignalId, setSelectedSignalId] = useState(bundle.signals[0]?.id ?? "");
  const selectedSignal = bundle.signals.find((item) => item.id === selectedSignalId) ?? bundle.signals[0];
  const linkedEvidence = bundle.evidence.filter((item) => item.signal_id === selectedSignal?.id);
  return (
    <div className="workbench-page product-stage" data-testid="product-data-page">
      <section className="data-metrics">
        <KpiCard icon={Search} label="候选信号" value={bundle.signals.length} hint="已进入主线候选池" tone="blue" />
        <KpiCard icon={ShieldCheck} label="支撑证据" value={bundle.evidence.length} hint="默认脱敏展示" tone="green" />
        <KpiCard icon={Filter} label="活跃区域" value={new Set(bundle.signals.map((item) => item.region_id)).size} hint="筛选条件可联动" tone="amber" />
        <KpiCard icon={ShieldAlert} label="阻断来源" value={bundle.source_records.filter((item) => !item.accepted).length} hint="只进审计不进处理链" tone="red" />
      </section>
      <div className="data-grid">
        <Panel title="数据源与条件筛选" subtitle="当前：全部接口">
          <div className="filter-stack">
            <div className="filter-hint">本页只做检索、筛选、查相似和加入草稿；数据源治理、字段映射、可信度校正在调试台处理。</div>
            <FilterGroup title="优先级" items={unique(bundle.signals.map((item) => item.priority))} />
            <FilterGroup title="区域 / 对象" items={unique(bundle.signals.map((item) => zh(item.region_id)))} />
            <FilterGroup title="标签体系" items={unique(bundle.signals.flatMap((item) => asStringArray(item.payload.tags).map(tagZh)))} />
            <FilterGroup title="来源类型" items={unique(bundle.source_records.map((item) => zh(item.access_mode)))} />
            <div className="policy-box">
              <ShieldCheck size={16} />
              敏感证据在展示前默认脱敏；未授权来源只保留审计可见，不进入处理链。
            </div>
          </div>
        </Panel>
        <section className="data-center-stack">
          <Panel title="数据 / 信号检索工作台" subtitle="当前阶段：数据检索与抓取">
            <div className="search-line">
              <input value={copy.dataQuery} readOnly aria-label="检索关键词" />
              <button className="wo-primary" type="button">检索</button>
            </div>
            <div className="tag-row">
              {copy.hotwords.slice(0, 5).map((item) => <span className="wo-chip" key={item}>{item}</span>)}
            </div>
          </Panel>
          <Panel title="候选数据表" subtitle="按相似度、可信度和证据完整度排序">
            <div className="signal-table-head">
              <span>优先级</span><span>数据 / 信号摘要</span><span>来源</span><span>区域 / 对象</span><span>标签</span><span>状态</span><span>操作</span>
            </div>
            <div className="signal-table">
            {bundle.signals.map((signal) => (
              <button key={signal.id} className={signal.id === selectedSignal?.id ? "signal-row active" : "signal-row"} onClick={() => setSelectedSignalId(signal.id)} type="button">
                <span className="priority-pill">{signal.priority}</span>
                <div className="signal-main">
                  <b>{zh(signal.title)}</b>
                  <small>{zh(signal.summary)}</small>
                  <ScoreStrip signal={signal} />
                </div>
                <span>{zh(bundle.source_records.find((source) => source.accepted)?.source_name ?? "系统聚合")}</span>
                <span>{zh(signal.region_id)}</span>
                <span>{asStringArray(signal.payload.tags).map(tagZh).slice(0, 2).join(" / ")}</span>
                <span>{zh(signal.status)}</span>
                <span>查看详情</span>
              </button>
            ))}
            </div>
            <div className="table-foot">
              <span>当前显示 1-{bundle.signals.length} / 共 {bundle.signals.length * 10 + 2} 条候选数据</span>
              <div className="pager" aria-label="信号分页"><button>上一页</button><button className="active">1</button><button>2</button><button>3</button><button>下一页</button></div>
            </div>
          </Panel>
          <Panel title="当前主线草稿包" subtitle="本页输出">
            <div className="draft-grid">
              <div className="draft-card"><b>已选数据</b><strong>{bundle.signals.length + 3}</strong><span>支撑证据 {bundle.evidence.length}</span></div>
              <div className="draft-card"><b>系统初步识别</b><span>{zh(bundle.mainline?.title ?? "")}</span></div>
              <div className="draft-card"><b>证据缺口</b><span>{bundle.mainline?.payload.evidence_gaps?.map(zh).slice(0, 2).join(" / ")}</span></div>
              <div className="draft-actions"><small>草稿包不是最终主线，只是可追溯材料集合。下一页由人工确认成线路径、诱因、支点和缺口。</small><Link className="wo-primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "mainline" }}>进入主线建模</Link></div>
            </div>
          </Panel>
        </section>
        <Panel title="选中数据详情" subtitle={selectedSignal?.id ?? "无"}>
          {selectedSignal ? (
            <SignalDetail signal={selectedSignal} evidence={linkedEvidence} bundle={bundle} action={action} />
          ) : (
            <EmptyPanel label="暂无选中信号" />
          )}
        </Panel>
      </div>
      <ProductFlowFooter active={1} caseId={bundle.case.id} />
    </div>
  );
}

function EvidenceReviewPage({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const copy = getScenarioCopy(bundle);
  return (
    <div className="evidence-page product-stage" data-testid="product-evidence-page">
      <section className="evidence-hero">
        <div>
          <span className="wo-back">风险事件详情 / 同页状态</span>
          <h2>{copy.topicTitle.replace("主题：", "")}证据复核</h2>
          <p>系统把现场信号、主体陈述、公开回应、历史样本与审计策略聚合为一个可复核风险事件；本页先解释事件本身，再展示证据链、评分拆解与人工复核状态。</p>
        </div>
        <div className="wo-action-row">
          <a className="wo-outline" href="#evidence-chain">查看证据链</a>
          <Link className="wo-primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "worldline" }}>进入推演</Link>
        </div>
      </section>
      <section className="data-metrics evidence-metrics">
        <KpiCard icon={AlertTriangle} label="风险概率" value={`${Math.max(...bundle.worldline_nodes.map((node) => node.risk))}%`} hint="近 2 小时信号共同抬升" tone="amber" />
        <KpiCard icon={Activity} label="影响程度" value="高" hint={copy.topicScope} tone="red" />
        <KpiCard icon={ShieldCheck} label="可控程度" value={bundle.case.scenario_type === "community_public_service" ? "中" : "中低"} hint="取决于证据清单和沟通机制" tone="blue" />
        <KpiCard icon={Scale} label="置信度" value={`${Math.round((bundle.mainline?.confidence ?? 0.7) * 100)}%`} hint="仍需人工复核关键材料" tone="green" />
      </section>
      <section className="evidence-layout">
        <main className="evidence-main-stack">
          <div className="section-grid">
            <Panel title="事件概览" subtitle="what happened">
              <div className="facts-grid">
                {copy.eventFacts.map((item) => (
                  <div className="fact" key={item[0]}><span>{item[0]}</span><b>{item[1]}</b><p>{item[2]}</p></div>
                ))}
              </div>
            </Panel>
            <Panel title="事件时间线" subtitle="signal timeline">
              <div className="timeline-list">
                {copy.eventTimeline.map((item) => <div className="time-row" key={item[0]}><time>{item[0]}</time><b>{item[1]}</b><span className="wo-chip">{item[2]}</span></div>)}
              </div>
            </Panel>
          </div>
          <Panel title="证据链 / 风险评分 / 人工复核" subtitle="同页状态切换">
            <div className="state-tabs"><button className="active">概览</button><button>证据链</button><button>风险评分</button><button>人工复核</button></div>
            <div className="evidence-list" id="evidence-chain">
              {bundle.evidence.map((item) => (
                <EvidenceRecord key={item.id} item={item} action={action} />
              ))}
            </div>
          </Panel>
        </main>
        <aside className="evidence-side">
          <Panel title="相关方" subtitle="stakeholders">
            <div className="stakeholders">
              {copy.stakeholders.map((item) => <div className="stakeholder" key={item[1]}><i>{item[0]}</i><div><b>{item[1]}</b><span>{item[2]}</span></div><em>{item[3]}</em></div>)}
            </div>
          </Panel>
          <Panel title="核心判断" subtitle="not a final decision">
            <div className="principle"><b>当前结论</b>{copy.coreJudgement}</div>
          </Panel>
          <Panel title="产品边界" subtitle="safety boundary">
            <div className="principle"><b>不可替代人工决策</b>{copy.productBoundary}</div>
          </Panel>
          <Panel title="来源策略摘要" subtitle="合规闸口">
            <SourcePolicySummary sources={bundle.source_records} />
          </Panel>
          <section className="next-card">
            <p>复核通过后，进入世界线推演页，比较不同沟通、证据公开和协同机制下的后续可能性。</p>
            <Link className="wo-primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "worldline" }}>进入世界线推演</Link>
          </section>
        </aside>
      </section>
      <ProductFlowFooter active={2} caseId={bundle.case.id} />
    </div>
  );
}

function MainlineBuilderPage({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const mainline = bundle.mainline;
  const confirmedFactors = bundle.risk_factors.filter((item) => item.status === "confirmed").length;
  return (
    <div className="mainline-page product-stage" data-testid="product-mainline-page">
      <section className="mainline-metrics">
        <KpiCard icon={Database} label="输入数据包" value={bundle.signals.length + bundle.evidence.length} hint="联动起点与数据依据" tone="blue" />
        <KpiCard icon={ListChecks} label="已识别线索" value={bundle.signals.length * 18 + 14} hint="联动扩散信号列" tone="amber" />
        <KpiCard icon={GitBranch} label="系统成线建议" value="4" hint="联动候选池" tone="blue" />
        <KpiCard icon={ShieldAlert} label="证据缺口" value={mainline?.payload.evidence_gaps?.length ?? 0} hint="联动质量控制" tone="red" />
        <KpiCard icon={CheckCircle2} label="可推演主线" value="1" hint={zh(mainline?.status ?? "pending")} tone="green" />
        <KpiCard icon={Activity} label="建模完成度" value={`${Math.round((mainline?.confidence ?? 0) * 100)}%`} hint="建议补充证据以提升完整度" tone="green" />
      </section>
      <div className="mainline-workspace">
        <aside className="left-rail">
          <Panel title="信号簇识别" subtitle="点击线索后右侧解释链同步刷新">
            <div className="clue-list">
              {[
                ["起", "起点线索箱", "定义主线起点的关键事件/异常", "7条", "blue"],
                ["支", "支撑线索箱", "支持问题持续存在的证据", "14条", "green"],
                ["官", "官方回应线索", "官方声明/通报/公告", "3条", "amber"],
                ["现", "现场反馈线索", "一线反馈/日志/视频/图片", "8条", "blue"],
                ["史", "冲突与历史线索", "信号冲突/历史相似前兆", "3项", "red"]
              ].map((item, index) => <button className={index === 0 ? "clue-card active" : "clue-card"} key={item[1]} type="button"><span>{item[0]}</span><b>{item[1]}</b><small>{item[2]}</small><em>{item[3]}</em></button>)}
            </div>
          </Panel>
          <Panel title="线索标签快速筛选">
            <div className="filter-chips">{["现场事实", "同城舆情", "公众情绪场", "官方声明", "隐私保护", "主体立场", "证据核验", "24小时内", "高可信度"].map((item) => <span className="filter-chip" key={item}>{item}</span>)}</div>
          </Panel>
          <Panel title="候选主线池" subtitle="系统建议 / 人工草稿 / 已确认">
            <div className="candidate-tabs"><button className="active">系统建议 4</button><button>人工草稿 3</button><button>已确认 1</button></div>
            <div className="candidate-list">
              {[mainline?.title, "现场信号扩散与回应缺口主线", "证据保全与责任争议主线", "隐私外泄与不实搬运主线"].filter(Boolean).map((item, index) => (
                <button className={index === 0 ? "mainline-card active" : "mainline-card"} key={String(item)} type="button"><b>{zh(String(item))}</b><small>证据 {bundle.evidence.length + index * 3} · 缺口 {mainline?.payload.evidence_gaps?.length ?? 0}</small><span>成线 {Math.round((mainline?.confidence ?? 0.76) * 100 - index * 5)}%</span></button>
              ))}
            </div>
          </Panel>
        </aside>
        <main className="main-area">
          <Panel title="主线结构图谱画布" subtitle={mainline?.id ?? "无主线"}>
            {mainline ? (
              <div className="mainline-structure">
                <div className="current-mainline-strip">当前主线 <b>{zh(mainline.title)}</b><span className="wo-chip">系统建议</span></div>
                <div className="view-tabs"><span>视图：</span><button className="active">结构图</button><button>证据链</button><button>时间线</button><button>全屏</button></div>
                <div className="lanes">
                  {[
                    ["起点 / 背景", [bundle.signals[0]?.title ?? ""]],
                    ["扩散信号", bundle.signals.map((signal) => signal.title)],
                    ["诉求 / 情绪聚合", mainline.payload.support_points ?? []],
                    ["叙事形成", bundle.risk_factors.map((factor) => factor.name)],
                    ["推演输入支点", mainline.payload.support_points ?? []],
                    ["证据缺口", mainline.payload.evidence_gaps ?? []],
                    ["确认主线", [mainline.title]]
                  ].map((lane, laneIndex) => (
                    <div className="lane" key={lane[0] as string}>
                      <div className="lane-head">{lane[0] as string}</div>
                      <div className="lane-body">
                        {(lane[1] as string[]).slice(0, 4).map((item, index) => <button className={laneIndex === 6 ? "node-card confirm-card" : "node-card"} key={`${item}-${index}`} type="button"><b>{zh(item)}</b><small>{bundle.evidence[index % Math.max(1, bundle.evidence.length)]?.id}</small></button>)}
                        {laneIndex >= 3 && laneIndex <= 5 ? <button className="add-node" type="button">添加{laneIndex === 5 ? "缺口" : "支点"}</button> : null}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="legend"><span>起点/背景</span><span>扩散信号</span><span>叙事形成</span><span>推演输入支点</span><span>证据缺口</span><span>可编辑</span></div>
                <button className="wo-primary" disabled={action.isPending || mainline.status === "confirmed"} onClick={() => action.mutate(() => api.confirmMainline(mainline.id))} type="button">
                  <CheckCircle2 size={15} />
                  确认主线并生成推演输入
                </button>
              </div>
            ) : (
              <EmptyPanel label="暂无主线" />
            )}
          </Panel>
          <Panel title="建模质量控制" subtitle="建议优先补充">
            <div className="quality-grid">
              <CompactList items={(mainline?.payload.evidence_gaps ?? []).map(zh)} />
              <CompactList items={["平台隐私处置与删除记录", "本地媒体与平台传播影响报告", "同城情绪综合波动率", "主管部门联合调查表态"]} />
              <CompactList items={["合并现场信号扩散与回应缺口主线", "排除弱相关重复转述片段", "关联证据保全争议作为背景说明"]} />
            </div>
          </Panel>
        </main>
        <aside className="right-rail">
          <Panel title="主线解释" subtitle={`系统生成 ${mainline?.id ?? ""}`}>
            <div className="explain-body">
              <div className="explain-block"><b>1. 当前判断</b><p>系统将当前信号簇整理为候选输入，建议人工确认后进入世界线推演。</p></div>
              <div className="explain-kpis"><span>置信度<b>{Math.round((mainline?.confidence ?? 0) * 100)}%</b></span><span>证据数<b>{bundle.evidence.length}</b></span><span>缺口<b>{mainline?.payload.evidence_gaps?.length ?? 0}</b></span></div>
              <div className="explain-block"><b>2. 成线路径</b><p>{(mainline?.payload.support_points ?? []).map(zh).join(" → ")}</p></div>
              <div className="explain-block"><b>3. 不确定性 / 待复核</b><CompactList items={(mainline?.payload.evidence_gaps ?? []).map(zh)} /></div>
            </div>
          </Panel>
          <Panel title="人工确认项" subtitle="待填写">
            <div className="manual-grid">
              <label><span>主线名称确认</span><input value={zh(mainline?.title ?? "")} readOnly /></label>
              <label><span>建模依据说明</span><input value="请说明选择这条主线的判断依据..." readOnly /></label>
              <label><span>特殊备注（可选）</span><input value="请填写备注..." readOnly /></label>
            </div>
          </Panel>
          <Panel title="风险因子确认" subtitle={`${confirmedFactors}/${bundle.risk_factors.length} 已确认`}>
            <div className="factor-list">{bundle.risk_factors.map((factor) => <FactorRecord key={factor.id} factor={factor} action={action} />)}</div>
          </Panel>
          <Panel title="进入推演前检查">
            <div className="check-list"><span>起点已确认</span><span>推演输入支点已确认</span><span>主线名称已确认</span><span className="warn">证据缺口 {mainline?.payload.evidence_gaps?.length ?? 0} 项</span><span>人工判断说明已填写</span></div>
            <Link className="wo-primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "worldline" }}>进入世界线推演</Link>
          </Panel>
        </aside>
      </div>
      <ProductFlowFooter active={3} caseId={bundle.case.id} />
    </div>
  );
}

function WorldlinePage({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const copy = getScenarioCopy(bundle);
  const defaultNode = bundle.worldline_nodes.find((node) => node.payload.needsCouncil) ?? bundle.worldline_nodes[0];
  const [selectedNodeId, setSelectedNodeId] = useState(defaultNode?.id ?? "");
  const selectedNode = bundle.worldline_nodes.find((node) => node.id === selectedNodeId) ?? defaultNode;
  return (
    <div className="worldline-page product-stage" data-testid="product-worldline-page">
      <section className="distribution-strip">
        {bundle.worldline_nodes.map((node) => <div className="distribution-card" key={node.id}><span>{branchLabel(node)}</span><b>{node.probability}%</b><small>风险 {node.risk}/100</small></div>)}
      </section>
      <section className="worldline-grid">
        <main className="worldline-center">
          <Panel title="世界状态输入包" subtitle={bundle.world_state?.id ?? "未就绪"}>
            <div className="world-state-card">
              <h2>{zh(bundle.world_state?.title ?? "世界状态不可用")}</h2>
              <p>{zh(bundle.mainline?.title ?? "")}</p>
              <CompactList items={(bundle.mainline?.payload.support_points ?? []).map(zh)} />
            </div>
          </Panel>
          <Panel title="24-72h 世界线分支" subtitle="点击节点查看证据、影响和下一跳">
            <div className="world-canvas">
              <div className="canvas-heading">
                <b>主要表达：当前状态如何分裂成多条未来世界线</b>
                <span>时间从左向右推进；点击节点查看证据、影响和下一跳。</span>
              </div>
              <div className="time-grid">{["低可见信号", "家属/居民到场", "视频/咨询扩散", "当前研判时刻", "后续24h", "未来72h"].map((item) => <span key={item}>{item}</span>)}</div>
              <svg className="graph-svg" viewBox="0 0 1000 420" preserveAspectRatio="none"><path d="M120 210 C260 90 420 120 560 160 S760 180 900 88" /><path d="M120 210 C280 260 420 300 600 280 S780 260 910 330" /></svg>
              <div className="branch-canvas">
                {bundle.worldline_nodes.map((node) => (
                  <button key={node.id} className={node.id === selectedNode?.id ? "branch-node active" : "branch-node"} onClick={() => setSelectedNodeId(node.id)} type="button">
                    <span>{node.branch}</span>
                    <b>{zh(node.title)}</b>
                    <small>{node.probability}% 概率 / {node.risk}% 风险</small>
                  </button>
                ))}
              </div>
              <div className="minimap">缩略图</div>
            </div>
          </Panel>
          <section className="bottom-timeline">
            <button className="play-btn" type="button">▶</button>
            <div className="step-track">{["1", "2", "3", "4", "5"].map((item) => <span key={item} />)}</div>
            <button className="wo-primary" type="button">下一阶段</button>
          </section>
        </main>
        <aside className="right-panel">
          <Panel title="当前选中节点" subtitle={selectedNode?.id ?? "无"}>
            {selectedNode ? (
              <div className="node-detail">
                <h2>{zh(selectedNode.title)}</h2>
                <p>点击图谱节点，查看它从哪个父节点演化而来、下一步可能走向、证据链、指标变化与干预建议。</p>
                <div className="risk-strip">
                  <StatusLine label="风险概率" value={`约 ${selectedNode.risk}%`} tone={selectedNode.risk >= 80 ? "red" : "amber"} />
                  <StatusLine label="倾向分支" value={branchLabel(selectedNode)} tone="blue" />
                  <StatusLine label="复核概率" value={`${Math.min(95, selectedNode.probability + 24)}%`} tone="green" />
                </div>
              </div>
            ) : <EmptyPanel label="暂无节点" />}
          </Panel>
          <Panel title="多主体研判" subtitle="Beta">
            <div className="council-reasons"><b>触发原因</b><CompactList items={["风险概率超过人工复核阈值", "证据缺口会影响后续分支", "需要模拟不同主体对响应动作的反应"]} /></div>
            <div className="agent-grid">{copy.stakeholders.map((item) => <span className="wo-chip" key={item[1]}>{item[1]}</span>)}</div>
            <label className="council-input"><span>输入研判假设</span><textarea value={copy.councilHypothesis} readOnly /></label>
            <div className="wo-action-row">
              <button
                className="wo-primary"
                disabled={action.isPending || !selectedNode?.payload.needsCouncil}
                onClick={() => selectedNode && action.mutate(() => api.runCouncil(selectedNode.id))}
                type="button"
              >
                <Play size={15} />
                启动多主体研判
              </button>
              <button className="wo-outline" type="button">仅作为普通假设继续推演</button>
            </div>
          </Panel>
          <Panel title="进入多主体研判" subtitle="研判前确认">
            <div className="modal-body-mini">
              <section><b>1 当前节点信息</b><p>{selectedNode ? zh(selectedNode.title) : "暂无"}</p></section>
              <section><b>2 本次研判目标</b><p>{copy.councilHypothesis}</p></section>
              <section><b>3 参与主体（推荐）</b><div className="agent-grid">{copy.stakeholders.map((item) => <span className="wo-chip" key={item[0]}>{item[1]}</span>)}</div></section>
              <section><b>4 输入证据</b><CompactList items={bundle.evidence.slice(0, 3).map((item) => zh(item.title))} /></section>
              <section><b>5 识别到的证据缺口</b><CompactList items={(bundle.mainline?.payload.evidence_gaps ?? []).map(zh)} /></section>
            </div>
          </Panel>
          <Panel title="详情标签" subtitle="当前 / 证据 / 变化 / 下一步">
            <div className="state-tabs"><button className="active">当前</button><button>证据</button><button>变化</button><button>下一步</button></div>
            <CompactList items={selectedNode?.payload.support_point_state?.map(zh) ?? []} />
          </Panel>
        </aside>
      </section>
      <ProductFlowFooter active={4} caseId={bundle.case.id} />
    </div>
  );
}

function CouncilPage({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const copy = getScenarioCopy(bundle);
  const session = bundle.council_sessions[0];
  const node = bundle.worldline_nodes.find((item) => item.payload.needsCouncil) ?? bundle.worldline_nodes[0];
  return (
    <div className="council-page product-stage" data-testid="product-council-page">
      <section className="council-grid">
        <aside className="left">
          <Panel title="当前主线与节点" subtitle={node?.id ?? "无"}>
            <div className="mainline-card">
              <h2>{zh(bundle.mainline?.title ?? "")}</h2>
              <p>当前节点：{zh(node?.title ?? "")}。研判目标是模拟各方反应，判断证据保全、沟通节奏和线下风险是否需要注入世界线重跑。</p>
              <div className="timebar"><StatusLine label="T+72h" value={node?.risk ?? 0} tone="red" /><StatusLine label="透明度" value="不足" tone="amber" /><StatusLine label="外溢风险" value="升温" tone="red" /></div>
            </div>
          </Panel>
          <Panel title="关键支点状态" subtitle="当前">
            <CompactList items={(bundle.mainline?.payload.support_points ?? []).map(zh)} />
          </Panel>
          <Panel title="输入证据" subtitle={`${bundle.evidence.length} 条`}>
            <CompactList items={bundle.evidence.map((item) => zh(item.title))} />
          </Panel>
        </aside>
        <section className="center">
          <Panel title="参与主体" subtitle={session?.payload.schema_version ?? "待生成"}>
            <div className="agent-strip">
              {(session?.payload.agents ?? []).length ? session?.payload.agents?.map((agent) => (
                <article className="agent-mini" key={agent.role}><span>{roleZh(agent.role).slice(0, 1)}</span><b>{roleZh(agent.role)}</b><small>{zh(agent.stance)}</small></article>
              )) : copy.stakeholders.map((item) => <article className="agent-mini" key={item[1]}><span>{item[0]}</span><b>{item[1]}</b><small>{item[2]}</small></article>)}
            </div>
          </Panel>
          <Panel title="研判轮次" subtitle="1/4">
            <div className="round-tabs">{["第1轮 各方初始反应", "第2轮 外部信号介入", "第3轮 方案响应动作", "第4轮 概率变化与总结"].map((item, index) => <button className={index === 0 ? "active" : ""} key={item} type="button">{item}</button>)}</div>
          </Panel>
          <Panel title="多主体会议" subtitle="对话与证据引用">
            {session ? <CouncilSessionMeeting session={session} /> : <EmptyPanel label="启动研判后生成主体输出" />}
            <div className="round-summary"><span>本轮将收集各方初始反应，并把影响标签写入右侧变化面板。</span><button className="wo-primary" type="button">进入下一轮</button></div>
          </Panel>
        </section>
        <aside className="right">
          <Panel title="演变变化面板" subtitle="重新分析">
            <div className="conflict-card"><b>当前最大矛盾</b><p>证据保全状态、沟通时限与责任归因之间出现落差，模糊回应会强化二次解读。</p></div>
            <div className="impact-list">
              <StatusLine label="分支 C" value={node ? `${Math.max(0, node.probability - 8)}% → ${node.probability}%` : "待生成"} tone="blue" />
              <StatusLine label="研判状态" value={zh(session?.status ?? "未启动")} tone={session ? "green" : "amber"} />
            </div>
            <button className="wo-primary" disabled={action.isPending || !node} onClick={() => action.mutate(() => api.runCouncil(node.id))} type="button">
              <Sparkles size={15} />
              运行研判
            </button>
          </Panel>
          <Panel title="支点变化 Top5" subtitle="影响来源">
            {session ? <CouncilImpact session={session} action={action} /> : <CompactList items={["support_point_delta", "branch_probability_delta", "evidence_refs", "blocked_claims"].map(zh)} />}
          </Panel>
          <Panel title="下一步建议" subtitle="可执行">
            <CompactList items={copy.actionPlan.map((item) => item[1])} />
          </Panel>
        </aside>
      </section>
      <section className="stress">
        <Panel title="假设压力测试" subtitle="用户输入">
          <textarea value={copy.councilHypothesis} readOnly />
          <button className="wo-primary" type="button">运行压力测试</button>
        </Panel>
        <Panel title="假设方案库" subtitle="观察各方反应与概率变化">
          <div className="test-grid">{copy.variables.slice(0, 4).map((item) => <button className="wo-outline" key={item} type="button">{item}</button>)}</div>
        </Panel>
        <Panel title="最终动作" subtitle="写回世界线">
          <div className="wo-action-row">
            {session ? <button className="wo-primary" disabled={action.isPending || session.status === "applied"} onClick={() => action.mutate(() => api.applyCouncil(session.id))} type="button">应用研判结果</button> : null}
            <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "worldline" }}>将结果注入世界线并重跑</Link>
            <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "brief" }}>生成推演汇报</Link>
            <button className="wo-outline" type="button">保存研判</button>
          </div>
        </Panel>
      </section>
      <ProductFlowFooter active={5} caseId={bundle.case.id} />
    </div>
  );
}

function DecisionBriefPage({ bundle, action }: { bundle: CaseBundle; action: ActionMutation }) {
  const copy = getScenarioCopy(bundle);
  const report = bundle.report;
  const formal = report?.payload.formal_conclusion;
  return (
    <div className="brief-page product-stage" data-testid="product-brief-page">
      <section className="brief-actions">
        <div>
          <h2>推演完成：{copy.topicTitle.replace("主题：", "")}</h2>
          <p>推演完成于 2026-05-08 10:30:22</p>
          <div className="meta-pills"><span>推演版本 v2.3.1</span><span>使用数据 {bundle.signals.length * 32} 条</span><span>使用证据 {bundle.evidence.length * 17} 条</span><span>参与主体 {Math.max(3, bundle.council_sessions[0]?.payload.agents?.length ?? 3)} 个</span><span>耗时 03:42</span></div>
        </div>
        <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "worldline" }}>回到推演画布</Link>
        <button className="wo-outline" onClick={() => downloadBrief(bundle, "json")} type="button">
          <Download size={15} />
          导出 JSON
        </button>
        <button className="wo-outline" onClick={() => downloadBrief(bundle, "markdown")} type="button">
          <Download size={15} />
          导出 Markdown
        </button>
      </section>
      <div className="brief-grid">
        <Panel title="推演结果摘要" subtitle="阶段性分支概率">
          <div className="donut-wrap">
            <div className="donut" />
            <div className="legend">
              {bundle.worldline_nodes.map((node) => <div key={node.id}><i /><span>{branchLabel(node)}</span><b>{node.probability}%</b></div>)}
            </div>
          </div>
          <div className="finding-list"><div><b>阶段性判断：</b>{zh(report?.payload.draft_summary ?? "")}</div><div><b>不确定性说明：</b>证据保全、沟通落差和传播外溢仍需继续观察，不输出确定责任结论。</div></div>
        </Panel>
        <Panel title="当前判断" subtitle={formal ? "正式结论" : "审核闸口"}>
          <div className={formal ? "conclusion-card ready" : "conclusion-card gated"}>
            <b>{formal ? "正式结论" : "正式结论待确认"}</b>
            <p>{formal ? zh(formal) : zh(report?.payload.compliance_note || "High-risk conclusions require human confirmation.")}</p>
          </div>
          {report ? (
            <button className="wo-primary" disabled={action.isPending || report.human_confirmed} onClick={() => action.mutate(() => api.confirmReport(report.id))} type="button">
              <FileCheck2 size={15} />
              确认报告
            </button>
          ) : null}
        </Panel>
        <Panel title="关键时间节点与路径回看" subtitle="查看完整世界线">
          <div className="path-list">
            {bundle.worldline_nodes.map((node) => (
              <div key={node.id} className="path-row">
                <i>{node.branch}</i>
                <b>{zh(node.title)}</b>
                <span>{node.probability}% / 风险 {node.risk}%</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="多方主体研判结论" subtitle="已执行 · 查看详情">
          {bundle.council_sessions[0] ? <CouncilBrief session={bundle.council_sessions[0]} /> : <EmptyPanel label="暂无研判会话" />}
        </Panel>
        <aside className="right-col">
          <Panel title="建议行动方案" subtitle="优先级排序">
            <div className="action-list">{copy.actionPlan.map((item) => <div className={`action-item tone-${item[3]}`} key={item[0]}><i>{item[0]}</i><b>{item[1]}</b><span>{item[2]}</span></div>)}</div>
          </Panel>
          <Panel title="系统学习 / 支撑工具" subtitle="已自动完成">
            <div className="data-metrics compact"><StatusLine label="使用数据" value={bundle.signals.length * 32} tone="blue" /><StatusLine label="关键支点" value={bundle.mainline?.payload.support_points?.length ?? 0} tone="green" /><StatusLine label="支撑证据" value={bundle.evidence.length * 17} tone="amber" /></div>
          </Panel>
          <Panel title="现实结果跟踪状态" subtitle="已开启">
            <div className="data-metrics compact"><StatusLine label="跟踪周期" value="7天" tone="blue" /><StatusLine label="数据源" value={bundle.source_records.length} tone="green" /><StatusLine label="下一评估" value="03天" tone="amber" /></div>
          </Panel>
          <Panel title="推演信息" subtitle="模型与时间">
            <CompactList items={["推演成本 v2.3.1", "模型 Worldline Engine 2.3", "开始时间 10:26:40", "完成时间 10:30:22"]} />
          </Panel>
        </aside>
        <Panel title="研判报告与文档" subtitle="批量导出">
          <div className="docs">{copy.docs.map((doc) => <div className="doc-card" key={doc[0]}><b>{doc[0]}</b><span>{doc[1]}</span></div>)}</div>
        </Panel>
        <Panel title="处置任务与跟踪" subtitle={`${bundle.tasks.length} 项任务`}>
          <div className="task-list">
            {bundle.tasks.map((task) => (
              <TaskRecord key={task.id} task={task} action={action} />
            ))}
          </div>
        </Panel>
        <Panel title="后续监测重点" subtitle="用于结果回流">
          <CompactList items={copy.watchFocus} />
        </Panel>
      </div>
      <ProductFlowFooter active={6} caseId={bundle.case.id} />
    </div>
  );
}

function AuditPage({ bundle }: { bundle: CaseBundle }) {
  const audit = useMemo(() => [...bundle.audit].reverse(), [bundle.audit]);
  return (
    <div className="audit-page product-stage" data-testid="product-audit-page">
      <section className="audit-grid">
        <Panel title="来源策略" subtitle="允许 / 阻断">
          <SourcePolicySummary sources={bundle.source_records} />
        </Panel>
        <Panel title="审计轨迹" subtitle={`${audit.length} 条`}>
          <div className="audit-list">
            {audit.map((entry) => (
              <AuditRecord key={entry.id} entry={entry} />
            ))}
          </div>
        </Panel>
      </section>
    </div>
  );
}

export function AdminConsole() {
  const queryClient = useQueryClient();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<S1ConsoleMode | "sources" | "intake" | "signals" | "evidence" | "mainline" | "worldline" | "council" | "brief" | "audit">("foundation");
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const casesQuery = useQuery({ queryKey: ["cases"], queryFn: api.listCases });
  const bundleQuery = useQuery({
    queryKey: ["case-bundle", selectedCaseId],
    enabled: Boolean(selectedCaseId),
    queryFn: () => api.getCaseBundle(selectedCaseId as string)
  });

  useEffect(() => {
    if (!selectedCaseId && casesQuery.data?.length) {
      setSelectedCaseId(casesQuery.data[0].id);
    }
  }, [casesQuery.data, selectedCaseId]);

  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
      await queryClient.invalidateQueries({ queryKey: ["case-bundle"] });
    }
  });
  const seedAction = useMutation({
    mutationFn: () => api.seed("all"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
      await queryClient.invalidateQueries({ queryKey: ["case-bundle"] });
    }
  });
  const bundle = bundleQuery.data;

  return (
    <div className="admin-shell" data-testid="admin-console">
      <header className="admin-topbar">
        <div>
          <span className="admin-eyebrow">CollectiveEventTwin P0</span>
          <h1>Worldline Observer 调试台</h1>
        </div>
        <div className="admin-actions">
          <StatusPill label="API" value={healthQuery.data?.status ?? (healthQuery.isError ? "offline" : "checking")} tone={healthQuery.data ? "ok" : "warn"} />
          <Link className="admin-button secondary" to="/cases/$caseId/$page" params={{ caseId: selectedCaseId ?? "CASE-CAMPUS-001", page: "risk" }}>
            产品页
          </Link>
          <button className="admin-button secondary" onClick={() => queryClient.invalidateQueries()} type="button">
            <RefreshCw size={16} />
            刷新
          </button>
          <button className="admin-button primary" disabled={seedAction.isPending} onClick={() => seedAction.mutate()} type="button">
            <Database size={16} />
            Seed P0
          </button>
        </div>
      </header>

      <div className="admin-workspace">
        <aside className="admin-rail">
          <div className="rail-heading">案例</div>
          {casesQuery.data?.map((item) => (
            <button key={item.id} className={item.id === selectedCaseId ? "admin-case active" : "admin-case"} onClick={() => setSelectedCaseId(item.id)} type="button">
              <b>{item.id}</b>
              <span>{zh(item.title)}</span>
            </button>
          ))}
        </aside>
        <main className="admin-stage">
          <nav className="admin-tabs">
            {["foundation", "reviews", "ops", "sources", "intake", "signals", "evidence", "mainline", "worldline", "council", "brief", "audit"].map((tab) => (
              <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab as typeof activeTab)} type="button">
                {adminTabZh(tab)}
              </button>
            ))}
          </nav>
          {bundleQuery.isLoading ? <SkeletonPanel rows={8} /> : null}
          {bundleQuery.isError ? <InlineError title="调试数据不可用" message={(bundleQuery.error as Error).message} /> : null}
          {(["foundation", "reviews", "ops"] as string[]).includes(activeTab) ? (
            <S1FoundationConsole mode={activeTab as S1ConsoleMode} />
          ) : activeTab === "sources" ? (
            <S2SourceConsole />
          ) : bundle ? (
            <AdminPanel tab={activeTab} bundle={bundle} action={action} />
          ) : (
            <EmptyPanel label="请先 Seed 或选择案例" />
          )}
        </main>
      </div>
    </div>
  );
}

function AdminPanel({ tab, bundle, action }: { tab: string; bundle: CaseBundle; action: ActionMutation }) {
  if (tab === "intake") {
    const workflowActions = [
      { name: "IngestCaseWorkflow", targetId: undefined },
      { name: "BuildMainlineWorkflow", targetId: undefined },
      { name: "GenerateWorldlineWorkflow", targetId: bundle.mainline?.id },
      { name: "RunCouncilWorkflow", targetId: bundle.worldline_nodes.find((node) => node.payload.needsCouncil)?.id },
      { name: "GenerateReportWorkflow", targetId: undefined }
    ];
    return (
      <div className="admin-grid">
        <Panel title="来源闸口" subtitle="策略">
          <SourceTable sources={bundle.source_records} />
        </Panel>
        <Panel title="工作流运行" subtitle="手动控制">
          <div className="admin-flow">
            {workflowActions.map((item) => (
              <div className="admin-flow-row" key={item.name}>
                <span>{item.name}</span>
                <button className="admin-button secondary" disabled={action.isPending} onClick={() => action.mutate(() => api.startWorkflow(item.name, bundle.case.id, item.targetId))} type="button">
                  启动
                </button>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    );
  }
  if (tab === "signals") return <div className="admin-card-grid">{bundle.signals.map((signal) => <SignalCard key={signal.id} signal={signal} />)}</div>;
  if (tab === "evidence") return <div className="admin-card-grid">{bundle.evidence.map((item) => <EvidenceRecord key={item.id} item={item} action={action} />)}</div>;
  if (tab === "mainline") return <MainlineBuilderPage bundle={bundle} action={action} />;
  if (tab === "worldline") return <WorldlinePage bundle={bundle} action={action} />;
  if (tab === "council") return <CouncilPage bundle={bundle} action={action} />;
  if (tab === "brief") return <DecisionBriefPage bundle={bundle} action={action} />;
  return <AuditPage bundle={bundle} />;
}

function ProductFlowFooter({ active, caseId }: { active: number; caseId: string }) {
  const steps = [
    { label: "1 数据接入与治理", helper: "接口、质量、标签体系", page: "data" as ProductPageId },
    { label: "2 数据检索与抓取", helper: "筛选、查相似、加入草稿", page: "data" as ProductPageId },
    { label: "3 主线建模确认", helper: "组织证据、诱因、支点", page: "mainline" as ProductPageId },
    { label: "4 世界线推演", helper: "分支与多主体研判", page: "worldline" as ProductPageId },
    { label: "5 多主体研判", helper: "主体立场与回应效果校准", page: "council" as ProductPageId },
    { label: "6 汇报与闭环", helper: "输出结论与处置建议", page: "brief" as ProductPageId }
  ];
  return (
    <footer className="product-flow">
      {steps.map((step, index) => (
        <Link key={step.label} className={index + 1 <= active ? "flow-step active" : "flow-step"} to="/cases/$caseId/$page" params={{ caseId, page: step.page }}>
          <b>{step.label}</b>
          <span>{step.helper}</span>
        </Link>
      ))}
      <Link className="flow-next" to="/cases/$caseId/$page" params={{ caseId, page: active >= 6 ? "risk" : steps[Math.min(active, steps.length - 1)].page }}>
        {active >= 6 ? "回到主题态势" : "下一步"}
      </Link>
    </footer>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="wo-panel">
      <header className="wo-panel-title">
        <span>{title}</span>
        {subtitle ? <small>{subtitle}</small> : null}
      </header>
      {children}
    </section>
  );
}

function KpiCard({ icon: Icon, label, value, hint, tone }: { icon: ComponentType<{ size?: number }>; label: string; value: string | number; hint: string; tone: "blue" | "green" | "amber" | "red" }) {
  return (
    <article className={`wo-kpi tone-${tone}`}>
      <span className="wo-kpi-icon">
        <Icon size={18} />
      </span>
      <div>
        <label>{label}</label>
        <strong>{value}</strong>
        <small>{hint}</small>
      </div>
    </article>
  );
}

function SourceTable({ sources }: { sources: SourceRecord[] }) {
  return (
    <div className="source-table">
      <div className="source-head">
        <span>数据类型</span>
        <span>信号量</span>
        <span>热度贡献</span>
        <span>趋势</span>
        <span>可信度</span>
      </div>
      {sources.map((source) => (
        <div className="source-row" key={source.id}>
          <b>{zh(source.source_name)}</b>
          <span>{Math.max(12, Math.round(source.trust * 260))}</span>
          <span>{Math.round(source.trust * 36)}%</span>
          <span className="trend">↑</span>
          <StatusPill label={source.id} value={source.accepted ? "accepted" : source.blocked_reason ?? "blocked"} tone={source.accepted ? "ok" : "warn"} />
        </div>
      ))}
    </div>
  );
}

function TrendChart({ signals }: { signals: Signal[] }) {
  const points = signals.map((signal, index) => {
    const x = 40 + index * (300 / Math.max(1, signals.length - 1));
    const y = 170 - ((signal.scores.onlineHeat ?? 0) / 100) * 130;
    return `${x},${y}`;
  });
  return (
    <div className="trend-chart">
      <svg viewBox="0 0 380 190" role="img" aria-label="主题热度趋势">
        <line x1="36" y1="20" x2="36" y2="168" />
        <line x1="36" y1="168" x2="350" y2="168" />
        <polyline points={points.join(" ")} />
        {points.map((point) => {
          const [x, y] = point.split(",");
          return <circle key={point} cx={x} cy={y} r="4" />;
        })}
      </svg>
    </div>
  );
}

function SpreadMap({ bundle }: { bundle: CaseBundle }) {
  const copy = getScenarioCopy(bundle);
  const labels = bundle.case.scenario_type === "community_public_service"
    ? ["居民咨询", "物业窗口", "热线摘要", "街道协调", "统一答疑", "恢复时间"]
    : ["现场视频", "家属诉求", "学生群截图", "同城居民", "平台处置", "政务回应"];
  return (
    <div className="spread-map">
      <svg viewBox="0 0 640 260" preserveAspectRatio="none">
        <path d="M82 132 C142 82,188 86,242 98" />
        <path d="M82 132 C142 174,192 184,254 168" />
        <path d="M276 98 C348 82,420 78,548 92" />
        <path d="M286 168 C358 188,438 174,552 150" />
      </svg>
      {labels.map((label, index) => (
        <div key={label} className={`spread-node node-${index}`}>
          <b>{label}</b>
          <span>{index === 0 ? "首发扩散" : index === labels.length - 1 ? "证据窗口" : copy.topicScope.split("、")[0]}</span>
        </div>
      ))}
    </div>
  );
}

function PlatformDistribution({ sources }: { sources: SourceRecord[] }) {
  return (
    <div className="platform-list">
      {sources.map((source) => (
        <div className="platform-row" key={source.id}>
          <span>{zh(source.source_name)}</span>
          <i>
            <b style={{ width: `${Math.max(8, Math.round(source.trust * 100))}%` }} />
          </i>
          <strong>{Math.round(source.trust * 100)}%</strong>
        </div>
      ))}
    </div>
  );
}

function EmotionPanel({ bundle }: { bundle: CaseBundle }) {
  const highRisk = Math.max(0, ...bundle.worldline_nodes.map((node) => node.risk));
  return (
    <div className="emotion-panel">
      <div className="emotion-donut" style={{ "--risk": `${highRisk}%` } as React.CSSProperties}>
        <b>{highRisk}%</b>
        <span>风险</span>
      </div>
      <div className="stance-list">
        {["负向 / 不满", "中立 / 观望", "支持 / 理解", "不确定 / 无关"].map((item, index) => (
          <div key={item} className="stance-row">
            <span>{item}</span>
            <i>
              <b style={{ width: `${[62, 26, 9, 47][index]}%` }} />
            </i>
            <strong>{[62, 26, 9, 47][index]}%</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function SignalDetail({ signal, evidence, bundle, action }: { signal: Signal; evidence: Evidence[]; bundle: CaseBundle; action: ActionMutation }) {
  return (
    <div className="signal-detail">
      <span className="priority-pill">{signal.priority}</span>
      <h2>{zh(signal.title)}</h2>
      <p>{zh(signal.summary)}</p>
      <ScoreStrip signal={signal} />
      <div className="chip-row">
        {asStringArray(signal.payload.tags).map((item) => (
          <span className="wo-chip" key={item}>{tagZh(item)}</span>
        ))}
      </div>
      <div className="trust-grid">
        <StatusLine label="为什么值得关注" value={scoreValue(signal, "mainlineRisk")} tone="red" />
        <StatusLine label="事实可信度" value={scoreValue(signal, "factCredibility")} tone="green" />
        <StatusLine label="热度指数" value={scoreValue(signal, "onlineHeat")} tone="blue" />
      </div>
      <Panel title="可补强主线位置" subtitle="进入草稿后可调整">
        <CompactList items={(bundle.mainline?.payload.support_points ?? []).map(zh).slice(0, 3)} />
      </Panel>
      <div className="linked-evidence">
        {evidence.map((item) => (
          <EvidenceRecord key={item.id} item={item} action={action} compact />
        ))}
      </div>
      <div className="wo-action-row">
        <Link className="wo-primary" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "mainline" }}>
          加入主线草稿
        </Link>
        <Link className="wo-outline" to="/cases/$caseId/$page" params={{ caseId: bundle.case.id, page: "evidence" }}>
          打开证据复核
        </Link>
      </div>
    </div>
  );
}

function EvidenceRecord({ item, action, compact = false }: { item: Evidence; action: ActionMutation; compact?: boolean }) {
  return (
    <article className={compact ? "evidence-record compact" : "evidence-record"}>
      <header>
        <StatusPill label={item.id} value={item.status} tone={item.status === "confirmed_fact" ? "ok" : item.status === "rejected" ? "risk" : "warn"} />
        <span className={item.sensitivity === "normal" ? "muted" : "sensitive"}>{zh(item.sensitivity)}</span>
      </header>
      <h3>{zh(item.title)}</h3>
      <p>{evidenceText(item)}</p>
      <small>{zh(item.source)} / 可信度 {item.credibility}</small>
      <div className="wo-action-row">
        <button className="wo-outline" disabled={action.isPending || item.status === "confirmed_fact"} onClick={() => action.mutate(() => api.updateEvidence(item.id, "confirmed_fact", "confirmed from product evidence review"))} type="button">
          确认事实
        </button>
        <button className="wo-outline" disabled={action.isPending || item.status === "rejected"} onClick={() => action.mutate(() => api.updateEvidence(item.id, "needs_review", "marked for follow-up review"))} type="button">
          标记复核
        </button>
      </div>
    </article>
  );
}

function FactorRecord({ factor, action }: { factor: RiskFactor; action: ActionMutation }) {
  return (
    <article className="factor-record">
      <div>
        <b>{zh(factor.name)}</b>
        <span>{zh(factor.category)} / {Math.round(factor.confidence * 100)}%</span>
        <small>由关联证据 {factor.payload.evidence_refs?.join("、") ?? "待补"} 触发</small>
      </div>
      <div className="factor-actions">
        <button className="wo-outline" disabled={action.isPending || factor.status === "confirmed"} onClick={() => action.mutate(() => api.updateFactor(factor.id, "confirmed", "confirmed from product mainline builder"))} type="button">
          确认因子
        </button>
        <button className="wo-outline" disabled={action.isPending || factor.status === "rejected"} onClick={() => action.mutate(() => api.updateFactor(factor.id, "rejected", "rejected from product mainline builder"))} type="button">
          排除
        </button>
      </div>
    </article>
  );
}

function CouncilSessionMeeting({ session }: { session: CouncilSession }) {
  return (
    <div className="agent-output-grid">
      {session.payload.agents?.map((agent) => (
        <article className="agent-output" key={agent.role}>
          <header>
            <span className="agent-avatar">{roleZh(agent.role).slice(0, 1)}</span>
            <div>
              <b>{roleZh(agent.role)}</b>
              <small>{zh(agent.stance)}</small>
            </div>
          </header>
          <p>{councilReactionZh(agent.reaction)}</p>
          <div className="chip-row">
            {agent.evidence_refs.map((ref) => (
              <span className="wo-chip" key={ref}>{ref}</span>
            ))}
          </div>
          {agent.blocked_claims.length ? <small className="blocked-claim">{agent.blocked_claims.map(zh).join("；")}</small> : null}
        </article>
      ))}
    </div>
  );
}

function CouncilImpact({ session, action }: { session: CouncilSession; action: ActionMutation }) {
  return (
    <div className="council-impact">
      <p>{session.payload.summary}</p>
      <div className="impact-list">
        {session.payload.branch_changes?.map((change, index) => (
          <StatusLine key={index} label={`分支 ${String(change.branch)}`} value={`${String(change.from)} → ${String(change.to)}`} tone="blue" />
        ))}
      </div>
      <button className="wo-primary" disabled={action.isPending || session.status === "applied"} onClick={() => action.mutate(() => api.applyCouncil(session.id))} type="button">
        <CheckCircle2 size={15} />
        应用研判结果
      </button>
    </div>
  );
}

function CouncilBrief({ session }: { session: CouncilSession }) {
  return (
    <div className="council-brief">
      <p>{zh(session.payload.summary)}</p>
      <CompactList items={session.payload.agents?.map((agent) => `${roleZh(agent.role)}：${zh(agent.stance)}`) ?? []} />
    </div>
  );
}

function TaskRecord({ task, action }: { task: Task; action: ActionMutation }) {
  return (
    <article className={task.status === "completed" ? "task-record done" : "task-record"}>
      <div>
        <b>{zh(task.title)}</b>
        <span>{zh(task.owner)} / {task.due_label}</span>
      </div>
      <button className="wo-outline" disabled={action.isPending || task.status === "completed"} onClick={() => action.mutate(() => api.updateTask(task.id, "in_progress", "started from product brief"))} type="button">
        {zh(task.status)}
      </button>
    </article>
  );
}

function SourcePolicySummary({ sources }: { sources: SourceRecord[] }) {
  return (
    <div className="policy-summary">
      {sources.map((source) => (
        <article key={source.id} className={source.accepted ? "policy-row accepted" : "policy-row blocked"}>
          {source.accepted ? <ShieldCheck size={17} /> : <ShieldAlert size={17} />}
          <div>
            <b>{zh(source.source_name)}</b>
            <span>{zh(source.access_mode)}</span>
          </div>
          <strong>{source.accepted ? "已接入" : zh(source.blocked_reason)}</strong>
        </article>
      ))}
    </div>
  );
}

function AuditRecord({ entry }: { entry: AuditLog }) {
  return (
    <article className="audit-row">
      <span className="audit-dot" />
      <div>
        <b>{zhAudit(entry.action)}</b>
        <span>{entry.object_type} {entry.object_id} / {zh(entry.actor)}</span>
        {entry.reason ? <small>{zh(entry.reason)}</small> : null}
      </div>
      <time>{new Date(entry.created_at).toLocaleString()}</time>
    </article>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  return (
    <article className="signal-card">
      <span className="priority-pill">{signal.priority}</span>
      <h3>{zh(signal.title)}</h3>
      <p>{zh(signal.summary)}</p>
      <ScoreStrip signal={signal} />
    </article>
  );
}

function ScoreStrip({ signal }: { signal: Signal }) {
  return (
    <div className="score-strip">
      <StatusLine label="热度" value={signal.scores.onlineHeat ?? 0} tone="red" />
      <StatusLine label="事实" value={signal.scores.factCredibility ?? 0} tone="green" />
      <StatusLine label="风险" value={signal.scores.mainlineRisk ?? 0} tone="blue" />
    </div>
  );
}

function StatusLine({ label, value, tone }: { label: string; value: string | number; tone: "blue" | "green" | "amber" | "red" }) {
  return (
    <div className={`status-line tone-${tone}`}>
      <span>{label}</span>
      <b>{typeof value === "string" ? zh(value) : value}</b>
    </div>
  );
}

function StatusPill({ label, value, tone }: { label: string; value: string | number | null | undefined; tone: "ok" | "warn" | "risk" }) {
  return (
    <span className={`status-pill ${tone}`}>
      <span>{label}</span>
      <strong>{zh(value)}</strong>
    </span>
  );
}

function CompactList({ items }: { items: string[] }) {
  return (
    <div className="compact-list">
      {items.length ? items.map((item, index) => (
        <div className="compact-row" key={`${item}-${index}`}>
          <CircleDot size={12} />
          <span>{item}</span>
        </div>
      )) : <EmptyPanel label="暂无记录" />}
    </div>
  );
}

function FilterGroup({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="filter-group">
      <b>{title}</b>
      <div className="filter-chips">
        {items.map((item, index) => <span className={index === 0 ? "filter-chip active" : "filter-chip"} key={item}>{item}</span>)}
      </div>
    </div>
  );
}

function InlineError({ title, message }: { title: string; message: string }) {
  return (
    <div className="inline-error">
      <AlertTriangle size={20} />
      <div>
        <b>{title}</b>
        <span>{message}</span>
      </div>
    </div>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="empty-panel">
      <Database size={18} />
      <span>{label}</span>
    </div>
  );
}

function SkeletonPanel({ rows }: { rows: number }) {
  return (
    <div className="skeleton-panel">
      {Array.from({ length: rows }).map((_, index) => <span key={index} />)}
    </div>
  );
}

type ScenarioCopy = {
  topicTitle: string;
  topicMeta: string;
  topicScope: string;
  dataQuery: string;
  stageNote: string;
  hotwords: string[];
  comments: Array<[string, string, "blue" | "green" | "amber" | "red"]>;
  variables: string[];
  eventFacts: Array<[string, string, string]>;
  eventTimeline: Array<[string, string, string]>;
  stakeholders: Array<[string, string, string, string]>;
  coreJudgement: string;
  productBoundary: string;
  councilHypothesis: string;
  actionPlan: Array<[string, string, string, "blue" | "green" | "amber" | "red"]>;
  watchFocus: string[];
  docs: Array<[string, string]>;
};

const campusCopy: ScenarioCopy = {
  topicTitle: "主题：青澜中学事件回应与同城情绪升温",
  topicMeta: "主题ID：T20260417001　首次发现：2026-04-17 09:42:00　关联区域：杭州市 西湖区 青澜中学",
  topicScope: "学校周边、家长群、同城平台",
  dataQuery: "青澜中学 学生坠亡 疑似欺凌 近24小时",
  stageNote: "阶段解读：当前主题在同城范围内讨论显著升温，视频内容成为主要传播载体，负向情绪占比上升，存在向更大范围扩散的可能。",
  hotwords: ["证据清单", "家属核验", "监控时间线", "急救记录", "隐私保护", "下一次通报"],
  comments: [
    ["不是只说正在调查，至少要说明监控、急救和通知家属的时间线。", "点赞 3.2k｜回复 856", "red"],
    ["希望先保护孩子隐私，不要继续搬运照片和群聊截图。", "点赞 2.1k｜回复 623", "amber"],
    ["需要有家属可核验的证据清单和下一次通报时间。", "点赞 1.8k｜回复 512", "blue"],
    ["现场围观视频持续搬运，平台应该先压低未核实片段。", "点赞 1.4k｜回复 318", "green"]
  ],
  variables: ["证据保全范围是否可被家属核验", "下一次通报是否给出明确时间", "现场围观和直播切片是否继续升温", "隐私外泄内容是否被平台降权", "同城情绪是否从追问转向线下聚集"],
  eventFacts: [
    ["当前阶段", "事中接管 / 待复核", "学生死亡事实已确认，线下聚集与线上扩散同时发生。"],
    ["影响范围", "学校周边、家长群、同城平台", "主要涉及家属问责、校园欺凌指控、证据保全和隐私保护。"],
    ["核心矛盾", "事实责任诉求 vs 模糊回应", "证据保全清单尚未被公开核验。"],
    ["当前建议", "先锁定证据缺口，再进入推演", "高风险结论必须保留人工确认。"]
  ],
  eventTimeline: [
    ["05-02 09:12", "校门口现场视频出现，死亡事实与家属问责同步扩散", "来源"],
    ["05-02 10:04", "学生群截图传播，疑似欺凌指控进入证据链复核", "现场"],
    ["05-02 10:20", "校方发布简短说明，但未说明监控、报警和通知家属时间线", "公开"],
    ["05-02 11:32", "系统合并为校园高烈度事中风险事件，进入人工复核", "复核"]
  ],
  stakeholders: [
    ["家", "家属群体", "关注事实、责任、证据核验", "问责 ↑"],
    ["校", "校方 / 属地", "关注现场秩序与回应口径", "承压 ↑"],
    ["教", "主管部门", "关注联合调查和隐私保护", "介入"],
    ["媒", "媒体 / 公开讨论", "关注透明度与责任归因", "放大 ↑"]
  ],
  coreJudgement: "系统倾向认为该事件具备进入世界线推演的条件，但不自动认定责任和处置方案。风险概率、证据链和建议动作均需人工复核后生效。",
  productBoundary: "本页不做个人画像，不追踪具体个人，不自动下发处置。后续主体模型只用于角色立场模拟，不代表真实个人或组织官方立场。",
  councilHypothesis: "如果 2 小时内发布证据保全清单，并明确家属参与核验与联合调查时间表，会怎样？",
  actionPlan: [
    ["1", "发布证据保全清单，明确家属核验和下一次通报时间", "高", "red"],
    ["2", "组织家属代表进入固定沟通空间，形成可记录沟通纪要", "高", "red"],
    ["3", "统一学校、教育部门、属地现场口径，避免模糊表述", "中高", "amber"],
    ["4", "启动未成年人隐私保护巡查，处理外泄截图与不实搬运", "中", "blue"]
  ],
  watchFocus: ["家属核验窗口是否真实开放", "隐私外泄内容是否继续传播", "短视频现场围观是否升温", "下一次通报是否覆盖证据缺口"],
  docs: [["世界线推演结果报告 PDF", "10:30"], ["多方主体研判纪要 PDF", "10:28"], ["关键支点变化分析 PDF", "10:25"], ["处置建议单 DOCX", "10:30"]]
};

const communityCopy: ScenarioCopy = {
  topicTitle: "主题：社区停水响应信任风险",
  topicMeta: "主题ID：T20260508002　首次发现：2026-05-08 08:10:00　关联区域：东区社区与公共服务窗口",
  topicScope: "社区住户、物业窗口、街道热线",
  dataQuery: "社区停水 恢复时间 责任窗口 联合答疑",
  stageNote: "阶段解读：当前风险来自恢复时间口径不一致和责任窗口模糊，居民咨询集中但仍处于可沟通、可分流阶段。",
  hotwords: ["恢复时间", "责任窗口", "联合答疑", "物业回应", "街道协调", "统一口径"],
  comments: [
    ["需要一个明确恢复时间，不要每个窗口说法都不一样。", "点赞 986｜回复 143", "red"],
    ["如果维修进展能按小时更新，大家会愿意等待。", "点赞 642｜回复 88", "green"],
    ["物业、街道和供水单位至少要给一个联合答疑入口。", "点赞 581｜回复 76", "blue"],
    ["目前主要是咨询集中，还没有必要扩大线下聚集。", "点赞 320｜回复 41", "amber"]
  ],
  variables: ["维修完成时间是否可兑现", "物业与供水单位口径是否一致", "居民是否从咨询转向集中到访", "统一问答渠道是否建立", "补偿或临时供水方案是否明确"],
  eventFacts: [
    ["当前阶段", "服务中断 / 待协同", "停水事实已确认，争议集中在恢复时间与责任解释。"],
    ["影响范围", "东区社区、物业窗口、街道热线", "主要涉及居民咨询、公共服务信任和线下到访压力。"],
    ["核心矛盾", "恢复诉求 vs 多方口径不一", "缺少统一答疑渠道和可兑现时间表。"],
    ["当前建议", "先统一响应窗口，再持续监测咨询信号", "不输出个人责任结论。"]
  ],
  eventTimeline: [
    ["05-08 08:10", "居民论坛集中询问恢复时间", "来源"],
    ["05-08 09:05", "热线摘要显示多个窗口给出不同完成时间", "现场"],
    ["05-08 10:30", "街道开始协调物业和供水单位统一回应", "公开"],
    ["05-08 11:20", "系统合并为公共服务信任风险事件", "复核"]
  ],
  stakeholders: [
    ["居", "居民群体", "关注恢复时间、责任说明和临时用水", "咨询 ↑"],
    ["物", "物业 / 服务单位", "关注维修进展和现场分流", "承压"],
    ["街", "街道属地", "关注统一口径和公共服务协调", "协调"],
    ["媒", "社区论坛", "关注进展透明度", "观察"]
  ],
  coreJudgement: "系统认为该事件可进入轻量世界线推演：关键不是停水本身，而是恢复窗口、责任解释和咨询分流是否一致。",
  productBoundary: "本页只做公共服务风险协调辅助，不自动归责，不生成执法或处罚建议。",
  councilHypothesis: "如果 4 小时内发布统一维修时间表，并建立物业、街道、供水单位联合答疑，会怎样？",
  actionPlan: [
    ["1", "核实维修完成时间并发布单一响应窗口", "高", "red"],
    ["2", "建立物业、街道、供水单位联合答疑入口", "高", "amber"],
    ["3", "安排临时供水与重点人群提醒", "中", "blue"],
    ["4", "持续监测论坛和热线中的集中咨询信号", "中", "green"]
  ],
  watchFocus: ["恢复时间是否兑现", "热线与论坛是否继续集中追问", "联合答疑是否降低线下到访", "临时供水方案是否覆盖重点住户"],
  docs: [["公共服务响应简报 PDF", "11:30"], ["联合答疑纪要 PDF", "11:20"], ["维修时间线校验表 XLSX", "11:10"], ["居民沟通任务单 DOCX", "11:35"]]
};

const textZh: Record<string, string> = {
  "Campus death and suspected bullying collective risk": "校园坠楼疑似欺凌群体风险",
  "Community water outage response trust risk": "社区停水响应信任风险",
  "Risk sensing and coordination only; not an official investigation or legal finding.": "仅用于风险感知和协同治理，不代表官方调查或法律结论。",
  "Smoke fixture for factor-system generalization.": "用于验证因子体系泛化能力的冒烟样例。",
  "Gate video and family gathering spread quickly": "校门口视频与家属聚集快速扩散",
  "Family claims prior feedback and bullying context": "家属称此前曾反馈并涉及欺凌背景",
  "Minor identity exposure and online harassment risk rises": "未成年人身份曝光与网暴风险升高",
  "First response is viewed as too vague": "首轮回应被认为过于模糊",
  "Water outage notice causes concentrated consultation": "停水通知引发集中咨询",
  "Service providers give inconsistent response windows": "服务方给出的恢复窗口不一致",
  "Authorized sample shows family questions, emergency vehicles, and bystander discussion at the campus gate.": "授权样本显示校门口存在家属追问、急救车辆和围观讨论。",
  "Manual statements point to prior feedback and school awareness dispute; context still needs verification.": "人工陈述指向此前反馈和校方知情争议，背景仍需核验。",
  "Comments include minor identity and class metadata, creating secondary harm risk.": "评论包含未成年人姓名与班级信息，存在二次伤害风险。",
  "Public response does not explain evidence preservation, family communication, or the next update time.": "公开回应未说明证据保全、家属沟通机制和下一次更新时间。",
  "Residents question recovery time, repair responsibility, and transparent compensation rules.": "居民集中询问恢复时间、维修责任和补偿规则。",
  "Property office, street office, and utility provider statements differ on timing and responsibility.": "物业、街道和供水单位对时间与责任的说法不一致。",
  "Authorized short-video export": "授权短视频导出",
  "Manual family statement upload": "家属陈述人工上传",
  "Official public response": "公开官方回应",
  "Private group forward": "私域群转发",
  "Local public forum post": "本地公开论坛帖",
  "Manual hotline summary": "热线人工摘要",
  "Authorized gate video segment": "授权校门口视频片段",
  "Family feedback statement": "家属反馈陈述",
  "Minor privacy spread screenshot": "未成年人隐私扩散截图",
  "First public response": "首轮公开回应",
  "Public forum thread": "公开论坛讨论串",
  "Campus accountability narrative and offline escalation risk": "校园责任叙事与线下升级风险",
  "Water outage response transparency and resident trust risk": "停水响应透明度与居民信任风险",
  "Campus high-intensity event World State": "校园高烈度事件世界状态",
  "Community water outage trust-risk World State": "社区停水信任风险世界状态",
  "Low-visibility campus signal drift": "低可见校园信号漂移",
  "Vague response hardens the accountability narrative": "模糊回应固化责任叙事",
  "Evidence preservation and joint investigation compress the trust vacuum": "证据保全与联合调查压缩信任真空",
  "Residents gather consultation threads online": "居民在线聚合咨询线索",
  "Inconsistent response window increases group consultation": "响应窗口不一致抬升集中咨询",
  "Clear timeline and responsibility window reduce distrust": "清晰时间线与责任窗口降低不信任",
  "Death or severe harm": "死亡或严重伤害",
  "Minor involved": "涉及未成年人",
  "Family on-site gathering": "家属到场与线下聚集",
  "Response credibility gap": "回应可信度缺口",
  "Privacy exposure and harassment": "隐私曝光与网暴",
  "Public service interruption": "公共服务中断",
  "Transparency concern": "透明度关切",
  "Unclear responsibility window": "责任窗口不清",
  "fact timeline": "事实时间线",
  "responsibility attribution": "责任归因",
  "emotion ignition": "情绪点火",
  "offline gathering": "线下聚集",
  "minor protection": "未成年人保护",
  "service recovery": "服务恢复",
  "responsibility explanation": "责任说明",
  "resident trust": "居民信任",
  "offline consultation": "线下咨询",
  "camera and emergency records": "监控与急救记录",
  "prior family feedback records": "此前家属反馈记录",
  "student-group screenshot context": "学生群截图上下文",
  "joint-investigation timeline": "联合调查时间表",
  "repair timeline": "维修时间线",
  "responsible entity statement": "责任主体说明",
  "next update time": "下一次更新时间",
  "Fix fact, emergency, and on-site timeline records": "固定事实、急救和现场时间线记录",
  "Preserve cameras, family-school records, and student-group screenshots": "封存监控、家校沟通记录和学生群截图",
  "Reduce minor name, photo, and class exposure across platforms": "降低未成年人姓名、照片和班级信息曝光",
  "Verify repair completion timeline and publish one response window": "核实维修完成时间并发布单一响应窗口",
  "Create joint Q&A channel for property and water provider": "建立物业与供水单位联合问答渠道",
  "Monitor forum and hotline for group consultation signals": "监测论坛和热线中的集中咨询信号",
  "Campus high-intensity event P0 decision brief": "校园高烈度事件 P0 决策简报",
  "Community water outage trust-risk P0 decision brief": "社区停水信任风险 P0 决策简报",
  "Branch C is the primary risk path: vague response hardens the accountability narrative. Mitigation requires evidence preservation, family communication, joint investigation, and privacy protection.": "C 线是当前主要风险路径：模糊回应会固化责任叙事。缓释动作需要同时覆盖证据保全、家属沟通、联合调查和隐私保护。",
  "The main risk is not the outage itself, but the inconsistent repair window and responsibility explanation. A single update channel and repair timeline are required.": "主要风险不是停水本身，而是维修窗口与责任解释不一致。需要单一更新渠道和可兑现维修时间线。",
  "High-risk conclusions require human confirmation.": "高风险结论需要人工确认后生效。",
  "Agent Council is a pressure test and not a factual finding.": "多主体研判是压力测试，不是事实认定。",
  "unsupported claim: assigning individual blame without confirmed evidence": "已阻断：缺少确认证据时不得指向个人责任",
  "Vague response increases trust vacuum, privacy risk, and offline gathering pressure.": "模糊回应会扩大信任真空、隐私风险和线下聚集压力。",
  "Inconsistent repair and responsibility explanations increase collective consultation risk.": "维修与责任说明不一致会增加集中咨询风险。",
  "Needs cause explanation, evidence access, and clear school responsibility boundary.": "需要原因说明、证据核验入口和清晰的校方责任边界。",
  "Needs site stabilization while addressing perceived knowledge gaps.": "需要稳定现场秩序，同时回应公众感知中的信息缺口。",
  "Needs joint investigation, field communication, and minor-protection mechanism.": "需要联合调查、现场沟通和未成年人保护机制。",
  "Need clear recovery time and responsibility contact window.": "需要明确恢复时间和责任联系窗口。",
  "Needs a unified response channel and reduced field consultation pressure.": "需要统一响应渠道，并降低现场集中咨询压力。",
  "Coordinates public service providers to give a deliverable timeline.": "协调公共服务单位给出可兑现时间表。"
};

const evidenceExcerptZh: Record<string, string> = {
  "EVD-001": "校门口画面显示家属聚集、哭泣和急救车辆，需与现场时间线交叉核验。",
  "EVD-012": "家属称曾多次反馈欺凌问题，并要求查看监控画面和沟通记录。",
  "EVD-017": "评论区出现 [MASKED] 等未成年人信息，需默认脱敏展示并进入隐私复核。",
  "EVD-024": "回应称调查支持正在进行，但未给出证据保全范围和下一次更新时间。",
  "EVD-WATER-001": "多名居民询问恢复供水时间，并讨论是否一起前往物业窗口咨询。",
  "EVD-WATER-002": "热线记录显示物业和供水单位给出的完成时间不一致。"
};

function getScenarioCopy(bundle: CaseBundle): ScenarioCopy {
  return bundle.case.scenario_type === "community_public_service" ? communityCopy : campusCopy;
}

function zh(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const raw = String(value);
  return textZh[raw] ?? statusZh(raw) ?? raw;
}

function statusZh(value: string): string | undefined {
  const map: Record<string, string> = {
    active: "启用",
    checking: "检查中",
    offline: "离线",
    accepted: "已接入",
    blocked: "已阻断",
    confirmed: "已确认",
    confirmed_fact: "已确认为事实",
    needs_review: "待复核",
    propagation: "传播证据",
    rejected: "已排除",
    suggested: "建议",
    selected_for_mainline: "已入主线候选",
    in_progress: "处理中",
    completed: "已完成",
    world_state_ready: "世界状态就绪",
    generated: "已生成",
    ready_to_apply: "待应用",
    applied: "已应用",
    draft: "草稿",
    public_web: "公开网页",
    manual_upload: "人工上传",
    authorized_export: "授权导出",
    private_chat: "私域聊天",
    source_not_allowed_for_p0: "P0 不允许来源",
    campus_high_intensity: "校园高烈度事件",
    community_public_service: "公共服务事件",
    system: "系统",
    analyst: "分析员",
    reviewer: "复核员",
    operator: "处置员",
    "fact-verification": "事实核验",
    "evidence-preservation": "证据保全",
    "privacy-response": "隐私响应",
    "street-coordination": "街道协调",
    "public-service-liaison": "公共服务联络",
    monitoring: "监测",
    "campus-core": "校园核心区",
    "online-spread": "线上扩散区",
    "authority-response": "主管部门回应",
    "community-east": "东区社区",
    normal: "普通",
    sensitive_person_minor: "未成年人敏感",
    high_sensitivity_fact: "高敏事实",
    sensitive_person: "敏感主体",
    offline_risk: "线下风险",
    response_gap: "回应缺口",
    privacy: "隐私风险",
    public_service: "公共服务",
    trust_break: "信任破裂",
    responsibility: "责任说明"
  };
  return map[value];
}

function tagZh(value: string): string {
  const map: Record<string, string> = {
    "field-video": "现场视频",
    "family-gathering": "家属聚集",
    "response-gap": "回应缺口",
    responsibility: "责任归因",
    "evidence-gap": "证据缺口",
    "minor-privacy": "未成年人隐私",
    "harassment-risk": "网暴风险",
    "response-credibility": "回应可信度",
    "trust-vacuum": "信任真空",
    support_point_delta: "支点变化",
    branch_probability_delta: "分支概率变化",
    evidence_refs: "证据引用",
    blocked_claims: "阻断声明",
    "public-service": "公共服务",
    "trust-risk": "信任风险",
    "collective-consultation": "集中咨询"
  };
  return map[value] ?? zh(value);
}

function evidenceText(item: Evidence): string {
  return evidenceExcerptZh[item.id] ?? zh(item.masked_excerpt);
}

function roleZh(value: string): string {
  const map: Record<string, string> = {
    "family-community": "家属与亲属共同体",
    "家属与亲属共同体": "家属与亲属共同体",
    school: "校方",
    "校方": "校方",
    "education-and-local-authority": "教育主管与属地部门",
    "教育主管与属地部门": "教育主管与属地部门",
    residents: "居民",
    "居民": "居民",
    "property-or-service-provider": "物业或服务单位",
    "street-office": "街道/属地",
    "物业或服务单位": "物业或服务单位",
    "街道/属地": "街道/属地"
  };
  return map[value] ?? zh(value);
}

function councilReactionZh(value: string): string {
  const rawRole = ["family-community", "school", "education-and-local-authority", "residents", "property-or-service-provider", "street-office"].find((item) => value.includes(item));
  if (rawRole) {
    return `${roleZh(rawRole)}认为当前节点需要更清晰的证据、沟通节奏和响应边界。`;
  }
  const role = Object.keys({
    "家属与亲属共同体": true,
    "校方": true,
    "教育主管与属地部门": true,
    "居民": true,
    "物业或服务单位": true,
    "街道/属地": true
  }).find((item) => value.includes(item));
  if (role) {
    return `${role}认为当前节点需要更清晰的证据、沟通节奏和响应边界。`;
  }
  return zh(value);
}

function branchLabel(node: WorldlineNode): string {
  const map: Record<string, string> = {
    root: "起点",
    C: "C 二次升温",
    D: "D 缓和注入"
  };
  return map[node.branch] ?? node.branch;
}

function adminTabZh(tab: string): string {
  const map: Record<string, string> = {
    foundation: "S1 基础",
    reviews: "S1 Review",
    ops: "S1 Ops",
    sources: "S2 Sources",
    intake: "接入",
    signals: "信号",
    evidence: "证据",
    mainline: "主线",
    worldline: "推演",
    council: "研判",
    brief: "汇报",
    audit: "审计"
  };
  return map[tab] ?? tab;
}

function zhAudit(action: string): string {
  const map: Record<string, string> = {
    case_seeded: "案例初始化",
    source_rejected: "来源阻断",
    evidence_status_updated: "证据状态更新",
    risk_factor_status_updated: "风险因子状态更新",
    mainline_confirmed: "主线确认",
    council_generated: "研判生成",
    council_applied: "研判应用",
    report_confirmed: "报告确认",
    task_status_updated: "任务状态更新",
    workflow_run_recorded: "工作流运行记录"
  };
  return map[action] ?? action;
}

function scoreValue(signal: Signal, key: string): number {
  return signal.scores[key] ?? 0;
}

function getBundleSummary(bundle: CaseBundle) {
  const riskNode = bundle.worldline_nodes.find((item) => item.payload.needsCouncil) ?? [...bundle.worldline_nodes].sort((a, b) => b.risk - a.risk)[0];
  const copy = getScenarioCopy(bundle);
  return {
    riskNode,
    formalReady: Boolean(bundle.report?.payload.formal_conclusion),
    blockedSources: bundle.source_records.filter((item) => !item.accepted).length,
    reviewCount: bundle.evidence.filter((item) => item.status !== "confirmed_fact").length,
    regionCount: new Set(bundle.signals.map((item) => item.region_id)).size,
    recommendations: copy.variables
  };
}

function unique(items: string[]) {
  return Array.from(new Set(items.filter(Boolean)));
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function downloadBrief(bundle: CaseBundle, format: "json" | "markdown") {
  const payload = {
    case: bundle.case,
    report: bundle.report,
    tasks: bundle.tasks,
    council: bundle.council_sessions[0] ?? null,
    audit_count: bundle.audit.length
  };
  const content =
    format === "json"
      ? JSON.stringify(payload, null, 2)
      : `# ${zh(bundle.report?.title ?? bundle.case.title)}\n\n${zh(bundle.report?.payload.draft_summary ?? "")}\n\n## 处置任务\n${bundle.tasks.map((task) => `- [${zh(task.status)}] ${zh(task.title)}`).join("\n")}\n`;
  const blob = new Blob([content], { type: format === "json" ? "application/json" : "text/markdown" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${bundle.case.id}-brief.${format === "json" ? "json" : "md"}`;
  link.click();
  URL.revokeObjectURL(link.href);
}
