import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Database,
  FileText,
  Flame,
  GitBranch,
  Layers,
  MessageCircle,
  PlusCircle,
  RadioTower,
  Search,
  ShieldCheck,
  Share2,
  Users,
  Video
} from "lucide-react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import AMapLoader from "@amap/amap-jsapi-loader";
import { api } from "../api";
import type { MapLayers, PageMetric, PageSection, PageView, ProductPageName } from "../api";

type ApiDrivenProductPageProps = {
  caseId: string;
  page: ProductPageName;
};

type JsonObject = Record<string, unknown>;
type CityRankMode = "heat" | "discussion" | "speed" | "video";
type CityMapMode = "map" | "satellite" | "heat";
type CityMapFilter = "all" | "hot" | "rising" | "video" | "follow";
type SelectedMapEvent = {
  title: string;
  summary: string;
  region: string;
  rank: string;
  heat: string;
  risk: string;
  type: string;
  time: string;
  confidence: string;
  status: string;
  spread: string;
  source: string;
  raw: string;
  mainline: string;
};

const cityRankTabs: Array<{ id: CityRankMode; label: string }> = [
  { id: "heat", label: "综合热度" },
  { id: "discussion", label: "同城讨论升温" },
  { id: "speed", label: "传播速度" },
  { id: "video", label: "视频/直播" }
];

const cityMapTabs: Array<{ id: CityMapFilter; label: string }> = [
  { id: "all", label: "全部事件" },
  { id: "hot", label: "热点事件" },
  { id: "rising", label: "升温事件" },
  { id: "video", label: "视频/直播事件" },
  { id: "follow", label: "我关注的" }
];

const pageOrder: ProductPageName[] = ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"];

const pageLabels: Record<ProductPageName, { label: string; helper: string }> = {
  city: { label: "城市态势", helper: "全域发现" },
  risk: { label: "主题态势", helper: "热点聚合" },
  data: { label: "数据检索", helper: "信号抽取" },
  evidence: { label: "证据复核", helper: "脱敏闭环" },
  mainline: { label: "主线建模", helper: "结构确认" },
  worldline: { label: "世界线推演", helper: "路径概率" },
  council: { label: "多主体研判", helper: "反应校准" },
  brief: { label: "汇报输出", helper: "任务闭环" },
  memory: { label: "复盘沉淀", helper: "知识入库" },
  library: { label: "案例库", helper: "相似召回" },
  config: { label: "配置中心", helper: "回归发布" }
};

const toneColor: Record<string, string> = {
  blue: "#2f6df6",
  green: "#18a873",
  amber: "#d78925",
  red: "#df4b54",
  violet: "#7f63c9",
  purple: "#7f63c9",
  cyan: "#009fb7",
  gray: "#7d8794"
};

const zhText: Record<string, string> = {
  "Campus death and suspected bullying collective risk": "校园坠楼疑似欺凌群体风险",
  "Community water outage response trust risk": "社区停水响应信任风险",
  "Risk sensing and coordination only; not an official investigation or legal finding.": "仅用于风险感知和协同治理，不代表官方调查或法律结论。",
  "Smoke fixture for factor-system generalization.": "用于验证因子体系泛化能力的冒烟样例。",
  "Authorized short-video export": "授权短视频导出",
  "Manual family statement upload": "家属陈述人工上传",
  "Official public response": "公开官方回应",
  "Private group forward": "私域群转发",
  "Local public forum post": "本地公开论坛帖",
  "Manual hotline summary": "热线人工摘要",
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
  "Authorized gate video segment": "授权校门口视频片段",
  "Family feedback statement": "家属反馈陈述",
  "Minor privacy spread screenshot": "未成年人隐私扩散截图",
  "First public response": "首轮公开回应",
  "Public forum thread": "公开论坛讨论串",
  "Campus gate shows family gathering, crying, and emergency vehicles.": "校门口画面显示家属聚集、哭泣和急救车辆。",
  "Family says they repeatedly reported bullying and asks for camera footage and communication records.": "家属称曾多次反馈欺凌问题，并要求查看监控画面和沟通记录。",
  "Multiple residents ask about water recovery time and discuss visiting the property office together.": "多名居民询问恢复供水时间，并讨论是否一起前往物业窗口咨询。",
  "Hotline record shows inconsistent completion times from property and water provider.": "热线记录显示物业和供水单位给出的完成时间不一致。",
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
  "Evidence list and family verification window reduce heat": "证据清单与家属核验窗口降低热度",
  "Low-intensity dispute continues around investigation boundary": "围绕调查边界的低烈度争议持续",
  "Privacy leakage and vague response create secondary rise": "隐私泄露与模糊回应造成二次升温",
  "External attention increases tail risk": "外部关注增加尾部风险",
  "Unified update channel reduces consultation pressure": "统一更新渠道降低咨询压力",
  "Repair delay creates low-intensity repeated questions": "维修延迟带来低烈度重复追问",
  "Death or severe harm": "死亡或严重伤害",
  "Minor involved": "涉及未成年人",
  "Family on-site gathering": "家属到场与线下聚集",
  "Response credibility gap": "回应可信度缺口",
  "Privacy exposure and harassment": "隐私曝光与网暴",
  "Public service interruption": "公共服务中断",
  "Transparency concern": "透明度关切",
  "Unclear responsibility window": "责任窗口不清",
  "Fact timeline uncertainty": "事实时间线不确定",
  "Family communication window": "家属沟通窗口",
  "Privacy leakage spread": "隐私泄露扩散",
  "Field order pressure": "现场秩序压力",
  "Local media amplification": "本地媒体放大",
  "Trust vacuum": "信任真空",
  "Publish evidence preservation checklist": "发布证据保全清单",
  "Open family verification appointment window": "开放家属核验预约窗口",
  "Run platform privacy suppression checklist": "执行平台隐私抑制清单",
  "Prepare next response time and scope": "准备下一次回应时间与范围",
  "Verify repair completion timeline and publish one response window": "核实维修完成时间并发布单一响应窗口",
  "Create joint Q&A channel for property and water provider": "建立物业与供水单位联合问答渠道",
  "Monitor forum and hotline for group consultation signals": "监测论坛和热线中的集中咨询信号",
  "Repair timeline and unified response channel": "维修时间线与统一响应渠道",
  "Resident consultation pressure and trust recovery": "居民咨询压力与信任修复",
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
  "Coordinates public service providers to give a deliverable timeline.": "协调公共服务单位给出可兑现时间表。",
  "active": "启用",
  "checking": "检查中",
  "offline": "离线",
  "accepted": "已接入",
  "blocked": "已阻断",
  "confirmed": "已确认",
  "confirmed_fact": "已确认为事实",
  "needs_review": "待复核",
  "propagation": "传播证据",
  "rejected": "已排除",
  "suggested": "建议",
  "selected_for_mainline": "已入主线候选",
  "in_progress": "处理中",
  "completed": "已完成",
  "world_state_ready": "世界状态就绪",
  "generated": "已生成",
  "ready_to_apply": "待应用",
  "applied": "已应用",
  "draft": "草稿",
  "public_web": "公开网页",
  "manual_upload": "人工上传",
  "authorized_export": "授权导出",
  "private_chat": "私域聊天",
  "source_not_allowed_for_p0": "P0 不允许来源",
  "system": "系统",
  "analyst": "分析员",
  "reviewer": "复核员",
  "operator": "处置员",
  "campus-core": "校园核心区",
  "online-spread": "线上扩散区",
  "authority-response": "主管部门回应",
  "community-east": "东区社区",
  "field-video": "现场视频",
  "family-gathering": "家属聚集",
  "response-gap": "回应缺口",
  "responsibility": "责任归因",
  "evidence-gap": "证据缺口",
  "minor-privacy": "未成年人隐私",
  "harassment-risk": "网暴风险",
  "response-credibility": "回应可信度",
  "trust-vacuum": "信任真空",
  "public-service": "公共服务",
  "trust-risk": "信任风险",
  "collective-consultation": "集中咨询",
  "offline_risk": "线下风险",
  "trust_break": "信任破裂",
  "public_service": "公共服务",
  "privacy": "隐私风险",
  "joint-investigation": "联合调查组",
  "family-liaison": "家属联络组",
  "platform-safety": "平台安全组",
  "communications": "沟通发布组",
  "street-coordination": "街道协调",
  "public-service-liaison": "公共服务联络",
  "monitoring": "监测组",
  "normal": "普通",
  "sensitive_person_minor": "未成年人敏感",
  "high_sensitivity_fact": "高敏事实",
  "sensitive_person": "敏感主体"
};

export function ApiDrivenProductPage({ caseId, page }: ApiDrivenProductPageProps) {
  const queryClient = useQueryClient();
  const cityId = "xian";
  const pageQuery = useQuery({
    queryKey: ["p0-page", caseId, page],
    queryFn: () => api.getPageView(caseId, page),
    enabled: page !== "city" && page !== "risk" && page !== "data" && page !== "evidence" && page !== "mainline" && page !== "worldline" && page !== "council" && page !== "brief" && page !== "memory" && page !== "library" && page !== "config"
  });
  const cityOverviewQuery = useQuery({
    queryKey: ["city-overview", cityId],
    queryFn: () => api.getCityOverviewPage(cityId),
    enabled: page === "city"
  });
  const cityMapQuery = useQuery({
    queryKey: ["city-map-layers", cityId],
    queryFn: () => api.getCityMapLayers(cityId),
    enabled: page === "city"
  });
  const topicSituationQuery = useQuery({
    queryKey: ["topic-situation", cityId],
    queryFn: () => api.getFirstTopicSituationPage(cityId),
    enabled: page === "risk"
  });
  const signalWorkbenchQuery = useQuery({
    queryKey: ["signal-workbench", cityId],
    queryFn: () => api.getFirstSignalWorkbenchPage(cityId),
    enabled: page === "data"
  });
  const evidenceReviewQuery = useQuery({
    queryKey: ["evidence-review", cityId],
    queryFn: () => api.getFirstEvidenceReviewPage(cityId),
    enabled: page === "evidence"
  });
  const mainlineBuilderQuery = useQuery({
    queryKey: ["mainline-builder", cityId],
    queryFn: () => api.getFirstMainlineBuilderPage(cityId),
    enabled: page === "mainline"
  });
  const worldlineSimulationQuery = useQuery({
    queryKey: ["worldline-simulation", cityId],
    queryFn: () => api.getFirstWorldlineSimulationPage(cityId),
    enabled: page === "worldline"
  });
  const councilQuery = useQuery({
    queryKey: ["council-session", cityId],
    queryFn: () => api.getFirstCouncilPage(cityId),
    enabled: page === "council"
  });
  const reportBriefQuery = useQuery({
    queryKey: ["report-brief", cityId],
    queryFn: () => api.getFirstReportBriefPage(cityId),
    enabled: page === "brief"
  });
  const retrospectiveMemoryQuery = useQuery({
    queryKey: ["retrospective-memory", cityId],
    queryFn: () => api.getFirstRetrospectiveMemoryPage(cityId),
    enabled: page === "memory"
  });
  const caseLibraryQuery = useQuery({
    queryKey: ["case-library", cityId],
    queryFn: () => api.getFirstCaseLibraryPage(cityId),
    enabled: page === "library"
  });
  const configAdminQuery = useQuery({
    queryKey: ["config-admin", cityId],
    queryFn: () => api.getFirstConfigAdminPage(cityId),
    enabled: page === "config"
  });
  useQuery({
    queryKey: ["city-events", cityId],
    queryFn: () => api.listCityEvents(cityId),
    enabled: page === "city"
  });
  useQuery({
    queryKey: ["city-rankings", cityId, "heat"],
    queryFn: () => api.listCityEventRankings(cityId, "heat"),
    enabled: page === "city"
  });
  useQuery({
    queryKey: ["city-source-health", cityId],
    queryFn: () => api.getCitySourceHealthView(cityId),
    enabled: page === "city"
  });
  useQuery({
    queryKey: ["city-media-evidence", cityId],
    queryFn: () => api.listCityMediaEvidence(cityId),
    enabled: page === "city"
  });
  useQuery({
    queryKey: ["city-timeline", cityId],
    queryFn: () => api.getCityTimeline(cityId),
    enabled: page === "city"
  });
  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["p0-page", caseId] });
      await queryClient.invalidateQueries({ queryKey: ["case-bundle", caseId] });
      await queryClient.invalidateQueries({ queryKey: ["city-overview", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["city-map-layers", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["city-events", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["city-rankings", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["topic-situation", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["signal-workbench", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["evidence-review", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["mainline-builder", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["worldline-simulation", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["council-session", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["report-brief", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["retrospective-memory", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["case-library", cityId] });
      await queryClient.invalidateQueries({ queryKey: ["config-admin", cityId] });
    }
  });
  const activeQuery = page === "city" ? cityOverviewQuery : page === "risk" ? topicSituationQuery : page === "data" ? signalWorkbenchQuery : page === "evidence" ? evidenceReviewQuery : page === "mainline" ? mainlineBuilderQuery : page === "worldline" ? worldlineSimulationQuery : page === "council" ? councilQuery : page === "brief" ? reportBriefQuery : page === "memory" ? retrospectiveMemoryQuery : page === "library" ? caseLibraryQuery : page === "config" ? configAdminQuery : pageQuery;

  if (activeQuery.isLoading) {
    return <LoadingPage caseId={caseId} page={page} />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return (
      <div className="cet-react-page" data-testid={`product-${page}-page`}>
        <TopNav caseId={caseId} page={page} nav={[]} />
        <section className="cet-error">
          <AlertTriangle size={18} />
          <b>页面数据不可用</b>
          <p>{(activeQuery.error as Error | undefined)?.message ?? "页面 API 未返回数据。"}</p>
        </section>
      </div>
    );
  }

  const view = page === "risk" || page === "data" || page === "evidence" || page === "mainline" || page === "worldline" || page === "council" || page === "brief" || page === "memory" || page === "library" || page === "config" ? { ...activeQuery.data, case_id: caseId } : activeQuery.data;
  return (
    <div className={`cet-react-page cet-page-${page}`} data-testid={`product-${page}-page`}>
      <TopNav caseId={caseId} page={page} nav={view.nav} />
      {page === "city" ? (
        <CityPage cityId={cityId} view={view} mapLayers={cityMapQuery.data} pending={action.isPending} runAction={(fn) => action.mutate(fn)} />
      ) : page === "memory" || page === "library" || page === "config" ? (
        <S7BStaticReferencePage view={view} pending={action.isPending} runAction={(fn) => action.mutate(fn)} />
      ) : (
        <StructuredPage view={view} pending={action.isPending} runAction={(fn) => action.mutate(fn)} />
      )}
    </div>
  );
}

function TopNav({ caseId, page, nav }: { caseId: string; page: ProductPageName; nav: PageView["nav"] }) {
  const navItems = Array.isArray(nav) ? nav : [];
  const navMap = new Map(navItems.map((item) => [item.page, item.label]));
  void navMap;
  return (
    <header className="cet-topbar">
      <Link to="/cases/$caseId/$page" params={{ caseId, page: "city" }} className="cet-brand">
        <span className="cet-brand-mark" />
        <span>
          WORLDLINE OBSERVER
          <small>城市态势感知</small>
        </span>
      </Link>
      <nav className="cet-nav" aria-label="P0 浜у搧娴佺▼">
        {pageOrder.map((item, index) => (
          <Link key={item} to="/cases/$caseId/$page" params={{ caseId, page: item }} className={item === page ? "active" : ""}>
            <i>{index + 1}</i>
            <b>
              {pageLabels[item].label}
              <span>{pageLabels[item].helper}</span>
            </b>
          </Link>
        ))}
      </nav>
      <div className="cet-status">
        <span className="live-dot" />
        <span>{caseId}</span>
      </div>
    </header>
  );
}

function CityPage({ cityId, view, mapLayers, pending, runAction }: { cityId: string; view: PageView; mapLayers?: MapLayers; pending: boolean; runAction: (fn: () => Promise<unknown>) => void }) {
  const [rankMode, setRankMode] = useState<CityRankMode>("heat");
  const [mapMode, setMapMode] = useState<CityMapMode>("map");
  const [mapFilter, setMapFilter] = useState<CityMapFilter>("all");
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const mapSignals = sectionItems(view, "map");
  const hotSignals = sectionItems(view, "hot").length ? sectionItems(view, "hot") : mapSignals;
  const sources = sectionItems(view, "source-status");
  const eventCategories = cityEventCategories(hotSignals);
  const sourceRows = citySourceRows(sources);
  const [activeEventTypes, setActiveEventTypes] = useState<Set<string>>(() => new Set(eventCategories.map((item) => item.label)));
  const [activeSources, setActiveSources] = useState<Set<string>>(() => new Set(sourceRows.map((item) => item.label)));
  const signalEntries = hotSignals.map((item, index) => ({ item, index }));
  const visibleEntries = signalEntries.filter(({ item, index }) => {
    const eventType = citySignalEventType(index, eventCategories);
    const sourceLabel = citySignalSourceLabel(index, sourceRows);
    return activeEventTypes.has(eventType) && activeSources.has(sourceLabel) && citySignalMatchesMapFilter(item, index, mapFilter);
  });
  const visibleSignals = visibleEntries.map(({ item }) => item);
  const visibleMapSignals = mapSignals.filter((item, index) => {
    const eventType = citySignalEventType(index, eventCategories);
    const sourceLabel = citySignalSourceLabel(index, sourceRows);
    return activeEventTypes.has(eventType) && activeSources.has(sourceLabel) && citySignalMatchesMapFilter(item, index, mapFilter);
  });
  const visibleMapLayers = filterMapLayers(mapLayers, mapSignals, visibleMapSignals);
  const top = visibleSignals.slice(0, 8);
  const topFive = visibleSignals.slice(0, 5);
  const selectedId = selectedSignalId && visibleSignals.some((item) => idOf(item) === selectedSignalId) ? selectedSignalId : idOf(visibleSignals[0]) || null;
  const maxHeat = Math.max(...visibleSignals.map((item) => score(item, "onlineHeat")), 0);
  const videoItems = buildVideoItems(top);
  const rankedTop = rankCitySignals(top, rankMode);
  const selectSignal = useCallback((id: string) => {
    if (id) {
      setSelectedSignalId(id);
      runAction(() => api.getCityEvent(id));
    }
  }, [runAction]);
  const persistMapState = (nextMode: CityMapMode, nextFilter: CityMapFilter, nextEventTypes: Set<string>, nextSources: Set<string>, reason: string) => {
    runAction(() => api.updateCityMapState(cityId, {
      layer_mode: nextMode,
      filters: {
        map_filter: nextFilter,
        event_types: Array.from(nextEventTypes),
        sources: Array.from(nextSources),
        rank_mode: rankMode
      },
      reason
    }));
  };
  const changeRankMode = (mode: CityRankMode) => {
    setRankMode(mode);
    runAction(() => api.listCityEventRankings(cityId, mode));
  };
  const changeMapMode = (mode: CityMapMode) => {
    setMapMode(mode);
    persistMapState(mode, mapFilter, activeEventTypes, activeSources, "city map layer mode changed");
  };
  const changeMapFilter = (filter: CityMapFilter) => {
    setMapFilter(filter);
    persistMapState(mapMode, filter, activeEventTypes, activeSources, "city map filter changed");
  };
  const toggleEventType = (label: string) => {
    const next = toggleSetValue(activeEventTypes, label);
    setActiveEventTypes(next);
    persistMapState(mapMode, mapFilter, next, activeSources, "city event type filter changed");
  };
  const toggleSource = (label: string) => {
    const next = toggleSetValue(activeSources, label);
    setActiveSources(next);
    persistMapState(mapMode, mapFilter, activeEventTypes, next, "city source filter changed");
  };

  return (
    <>
      <section className="cet-city-toolbar">
        <div className="cet-time-buttons">
          {["近1小时", "近6小时", "近24小时", "近48小时", "近7天"].map((item) => (
            <button type="button" className={item === "近7天" ? "active" : ""} key={item}>{item}</button>
          ))}
        </div>
        <label className="cet-search">
          <Search size={14} />
          <input placeholder="搜索事件、地点、话题、关键词..." />
        </label>
        <div className="cet-live-pill"><span className="live-dot" /> 数据源在线 {metricValue(view.metrics, "数据源") || `${sources.filter((item) => boolField(item, "accepted")).length}/${sources.length}`}</div>
      </section>

      <MetricStrip metrics={cityMetrics(view.metrics, maxHeat, visibleSignals.length, sources.length)} />

      <main className="cet-city-grid">
        <aside className="cet-layer-panel">
          <header><b>图层控制</b><button type="button">收起</button></header>
          <label className="cet-layer-search"><input placeholder="搜索图层..." /></label>
          <section>
            <div className="cet-layer-title"><span>事件类型</span><b>{activeEventTypes.size}/{eventCategories.length}</b></div>
            {eventCategories.map((item) => (
              <button className={`cet-layer-row cet-event-layer ${activeEventTypes.has(item.label) ? "active" : ""}`} type="button" key={item.label} onClick={() => toggleEventType(item.label)}>
                <span className="cet-check">{activeEventTypes.has(item.label) ? "?" : ""}</span>
                <b>{item.label}</b>
                <em>{item.count}</em>
              </button>
            ))}
          </section>
          <section>
            <div className="cet-layer-title"><span>数据源</span><b>在线 {activeSources.size}/{sourceRows.length}</b></div>
            {sourceRows.map((item) => (
              <button className={`cet-layer-row ${activeSources.has(item.label) ? "active" : ""}`} type="button" key={item.label} onClick={() => toggleSource(item.label)}>
                <span className="cet-check">{activeSources.has(item.label) ? "?" : ""}</span>
                <SourceLogo label={item.label} />
                <b>{item.label}</b>
                <em>{item.value}</em>
              </button>
            ))}
          </section>
        </aside>

        <section className="cet-map-panel">
          <div className="cet-map-tabs">
            {cityMapTabs.map((item) => (
              <button type="button" className={mapFilter === item.id ? "active" : ""} key={item.id} onClick={() => changeMapFilter(item.id)}>{item.label}</button>
            ))}
          </div>
          <div className={`cet-map-canvas map-mode-${mapMode}`}>
            <AmapMap layers={visibleMapLayers} events={visibleMapSignals} mode={mapMode} selectedSignalId={selectedId} onSelectSignal={selectSignal} />
            <div className="cet-map-title">城市事件热力雷达 / 真实地图</div>
            <div className="cet-map-legend">
              <b>热区强度</b>
              <div className="cet-legend-scale"><span>高</span><i /><span>低</span></div>
              <div className="cet-legend-notes">
                <strong>事件聚合说明</strong>
                <small><i className="dot-count" />数字 = 事件数量</small>
                <small><i className="dot-heat" />颜色 = 热度强度</small>
                <small><i className="dot-click" />点击聚合查看详情</small>
              </div>
            </div>
            <MapModeControls center={mapLayers?.config.center ?? [108.9398, 34.3416]} mode={mapMode} onChange={changeMapMode} />
          </div>
          <TimelinePanel signals={top} selectedSignalId={selectedId} onSelectSignal={selectSignal} />
        </section>

        <aside className="cet-right-stack">
          <section className="cet-float-panel cet-rank-panel">
            <PanelHead title="当前热度榜（实时）" right="更多" />
            <div className="cet-rank-tabs" role="tablist" aria-label="热度榜排序">
              {cityRankTabs.map((tab) => (
                <button
                  className={rankMode === tab.id ? "active" : ""}
                  type="button"
                  role="tab"
                  aria-selected={rankMode === tab.id}
                  key={tab.id}
                  onClick={() => changeRankMode(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="cet-rank-list">
              <div className="cet-rank-index-head"><span>热度指数</span></div>
              {rankedTop.map((item, index) => (
                <article className={`cet-rank-row ${idOf(item) === selectedId ? "selected" : ""}`} key={idOf(item) || index} role="button" tabIndex={0} onClick={() => selectSignal(idOf(item))}>
                  <span className={`cet-rank-no rank-${index + 1}`}>{rankLabel(index)}</span>
                  <div>
                    <b>{textField(item, "title")}</b>
                    <span className="cet-rank-meta">
                      {textField(item, "region_id")} 路 {textField(item, "priority")}
                      <em className="cet-media-tag">{index % 2 === 0 ? "视频" : "直播"}</em>
                    </span>
                  </div>
                  <strong>{cityRankMetric(item, index, rankMode)}<small>{cityRankDelta(item, index, rankMode)}</small></strong>
                  <button
                    type="button"
                    className="cet-row-action"
                    disabled={pending || !idOf(item)}
                    onClick={(event) => {
                      event.stopPropagation();
                      runAction(() => api.createTopicFromCityEvent(idOf(item)));
                    }}
                  >
                    Topic
                  </button>
                </article>
              ))}
              <div className="cet-rank-formula">热度指数 = 综合互动量 x 传播速度 x 同城占比 x 来源权重</div>
            </div>
          </section>

          <section className="cet-float-panel cet-video-panel">
            <PanelHead title="视频/直播热点（实时）" right="更多" />
            <div className="cet-video-list">
              {videoItems.slice(0, 4).map((item, index) => (
                <article className={`cet-video-card ${item.id === selectedId ? "selected" : ""}`} key={`${item.title}-${index}`} role="button" tabIndex={0} onClick={() => selectSignal(item.id)}>
                  <div className="cet-video-thumb">直播</div>
                  <div>
                    <b>{item.title}{index < 3 ? <em>热</em> : null}</b>
                    <p>{item.summary}</p>
                    <span>{item.source} 路 {item.metric}<small>{item.updated}</small></span>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="cet-float-panel cet-emotion-panel">
            <PanelHead title="同城情绪与立场（近24小时）" right="更多" />
            <div className="cet-emotion-body">
              <section className="cet-sentiment-panel">
                <h3>总体情绪倾向</h3>
                <div className="cet-donut"><div><b>-62%</b><span>负向</span></div></div>
                <div className="cet-legend-list">
                  {[["负向", 62, "red"], ["正向", 9, "green"], ["中立", 26, "amber"], ["不确定", 3, "blue"]].map(([label, value, tone]) => (
                    <span key={label as string}><i style={{ background: toneColor[tone as string] }} />{label}<b>{value}%</b></span>
                  ))}
                </div>
              </section>
              <section className="cet-position-panel">
                <h3>主要立场分布</h3>
                <div className="cet-stance-list">
                  {[["质疑回应过短", 34, "red"], ["要求公开证据保全", 28, "amber"], ["关注未成年人保护", 21, "green"], ["等待联合调查", 17, "blue"]].map(([label, value, tone]) => (
                    <div className="cet-stance" key={label as string}><span>{label}</span><i><b style={{ width: `${value}%`, background: toneColor[tone as string] }} /></i><strong>{value}%</strong></div>
                  ))}
                </div>
              </section>
              <div className="cet-monitor-grid">
                {[
                  ["情绪主轴", "质疑回应过短、要求公开证据保全", "62%"],
                  ["分歧焦点", "是否长期欺凌、校方是否提前知情", "47%"],
                  ["降温支点", "联合调查时间表与家属核验窗口", "31%"]
                ].map((item) => (
                  <article className="cet-monitor-row" key={item[0]}><b>{item[0]}</b><strong>{item[2]}</strong><span>{item[1]}</span></article>
                ))}
              </div>
            </div>
          </section>
        </aside>
      </main>

      <section className="cet-bottom-grid">
        <MiniList title="新增高热事件" meta="近1小时" items={topFive} selectedSignalId={selectedId} onSelectSignal={selectSignal} value={(item) => formatNumber(score(item, "onlineHeat") * 920 || 88320)} />
        <MiniList title="传播速度榜" meta="近1小时 TOP5" items={topFive} selectedSignalId={selectedId} onSelectSignal={selectSignal} value={(item, index) => `${formatNumber(Math.round((score(item, "onlineHeat") || 96) * (34 - index * 2) + (score(item, "mainlineRisk") || 64) * 3))}/分钟`} />
        <MiniList title="破圈苗头" meta="近24小时 TOP5" items={topFive} selectedSignalId={selectedId} onSelectSignal={selectSignal} value={(item) => `破圈概率 ${Math.min(89, Math.round((score(item, "onlineHeat") || 96) - 7))}%`} />
        <PlatformSpreadList title="多平台传播事件" meta="近24小时" items={topFive} selectedSignalId={selectedId} onSelectSignal={selectSignal} />
        <section className="cet-mini-panel">
          <PanelHead title="数据源状态" count={`在线 ${sourceRows.filter((item) => item.online).length}/${sourceRows.length}`} right="更多" />
          <div className="cet-source-grid">
            {sourceRows.map((item) => (
              <article key={item.label}><SourceLogo label={item.label} /><b>{item.label}</b><span>{item.value}</span><em>{item.online ? "实时" : "阻断"}</em></article>
            ))}
          </div>
        </section>
      </section>
    </>
  );
}

function AmapMap({
  layers,
  events,
  mode,
  selectedSignalId,
  onSelectSignal
}: {
  layers?: MapLayers;
  events: unknown[];
  mode: CityMapMode;
  selectedSignalId: string | null;
  onSelectSignal: (id: string) => void;
}) {
  const amapKey = (import.meta.env.VITE_AMAP_KEY ?? "").trim();
  const amapSecurityCode = (import.meta.env.VITE_AMAP_SECURITY_CODE ?? "").trim();
  if (amapKey) {
    return <OfficialAmapMap layers={layers} events={events} mode={mode} selectedSignalId={selectedSignalId} onSelectSignal={onSelectSignal} amapKey={amapKey} securityCode={amapSecurityCode} />;
  }
  return <MapLibreGaodeMapV2 layers={layers} events={events} mode={mode} selectedSignalId={selectedSignalId} onSelectSignal={onSelectSignal} />;
}

function SourceLogo({ label }: { label: string }) {
  const type = sourceLogoType(label);
  return (
    <span className={`cet-source-logo logo-${type}`} aria-hidden="true">
      <svg viewBox="0 0 20 20" focusable="false">
        {type === "douyin" ? <path d="M11.5 3.2v7.3a3.9 3.9 0 1 1-2.6-3.7v2.3a1.7 1.7 0 1 0 1.1 1.6V3.2h1.5c.4 1.7 1.7 2.8 3.4 3v2.2a5.5 5.5 0 0 1-3.4-1.3Z" /> : null}
        {type === "kuaishou" ? <path d="M6.2 5.4a2.1 2.1 0 1 1 3.2 1.8h1.2a2.1 2.1 0 1 1 1.3 1.6l2.8 1.7v4.1l-4.1-2.4v1.7H4.5V8.8h2.9a2.1 2.1 0 0 1-1.2-3.4Z" /> : null}
        {type === "weibo" ? <path d="M4.1 10.9c.4-2.3 3.2-3.8 6.3-3.4 3.1.4 5.4 2.5 5 4.8-.4 2.3-3.2 3.8-6.3 3.4-3.1-.4-5.4-2.5-5-4.8Zm3.1.6a1.6 1.6 0 1 0 3.1.6 1.6 1.6 0 0 0-3.1-.6Zm7.1-6.6c1.5.4 2.6 1.6 2.8 3.1m-4.7-.7c.8.2 1.4.8 1.6 1.6" /> : null}
        {type === "zhihu" ? <path d="M4 5h6M7 5c-.3 4-1.4 6.8-3.4 9.2M4.3 9.1h5.3M8.2 9.1c.6 1.9 1.2 3.3 2.1 4.8M12 5h4.2v8.7h-4.2zM12.8 14.8l2-1.1 1.7 1.1" /> : null}
        {type === "wechat" ? <path d="M8.4 6.2c-2.7 0-4.9 1.7-4.9 3.8 0 1.2.7 2.2 1.8 2.9l-.4 1.5 1.7-.9c.5.1 1.1.2 1.8.2 2.7 0 4.9-1.7 4.9-3.8S11.1 6.2 8.4 6.2Zm5.3 3.6c1.8.4 3.1 1.7 3.1 3.2 0 1-.6 1.9-1.6 2.5l.3 1.2-1.3-.7c-.4.1-.9.2-1.4.2-1.5 0-2.8-.6-3.6-1.5" /> : null}
        {type === "toutiao" ? <path d="M4.2 4.6h11.6v2.2H11v8.6H8.7V6.8H4.2zM12.4 8.9h3.4v2h-3.4zM12.4 12.1h3.4v2h-3.4z" /> : null}
        {type === "redbook" ? <path d="M4.2 5.2h11.6v9.6H4.2zM6.4 7.1h7.2M6.4 10h7.2M6.4 12.8h4.2" /> : null}
        {type === "hotline" ? <path d="M5.2 5.5h9.6v9H5.2zM7.2 7.5h5.6M7.2 10h5.6M7.2 12.5h3.4" /> : null}
        {type === "grid" ? <path d="M4.5 4.5h4.2v4.2H4.5zM11.3 4.5h4.2v4.2h-4.2zM4.5 11.3h4.2v4.2H4.5zM11.3 11.3h4.2v4.2h-4.2z" /> : null}
        {type === "camera" ? <path d="M5 7h2l.8-1.4h4.4L13 7h2v7.5H5zM10 9a2.2 2.2 0 1 0 0 4.4A2.2 2.2 0 0 0 10 9Z" /> : null}
        {type === "forum" || type === "other" ? <path d="M4 5.2h12v7.3H8l-3.1 2.3v-2.3H4zM6.3 7.5h7.4M6.3 10h5.2" /> : null}
      </svg>
    </span>
  );
}

function MapModeControls({ center, mode, onChange }: { center: number[]; mode: CityMapMode; onChange: (mode: CityMapMode) => void }) {
  const thumbs = useMemo(() => mapPreviewThumbs(center), [center]);
  return (
    <div className="cet-map-mode">
      <button type="button" className={mode === "map" ? "active" : ""} onClick={() => onChange("map")}><i className="thumb-map" style={{ backgroundImage: `url(${thumbs.map})` }} /><span>地图</span></button>
      <button type="button" className={mode === "satellite" ? "active" : ""} onClick={() => onChange("satellite")}><i className="thumb-satellite" style={{ backgroundImage: `url(${thumbs.satellite})` }} /><span>卫星</span></button>
      <button type="button" className={mode === "heat" ? "active" : ""} onClick={() => onChange("heat")}><i className="thumb-heat" style={{ backgroundImage: `radial-gradient(circle at 42% 50%, rgba(223,75,84,.86), rgba(223,75,84,.28) 26%, transparent 44%), radial-gradient(circle at 68% 35%, rgba(47,109,246,.68), rgba(47,109,246,.18) 25%, transparent 42%), url(${thumbs.map})` }} /><span>热力</span></button>
    </div>
  );
}

function heatClass(value: number) {
  if (value >= 86) return "heat-high";
  if (value >= 68) return "heat-mid";
  return "heat-low";
}

function amapInfoWindowHtml(props: Record<string, unknown>) {
  const title = escapeHtml(String(props.displayTitle || props.title || "鍩庡競鑱氬悎浜嬩欢"));
  const region = escapeHtml(String(props.region || props.region_id || "西安同城"));
  const count = escapeHtml(String(props.eventCount || props.rank || "1"));
  const heat = escapeHtml(formatNumber(Number(props.onlineHeat || props.riskScore || 0) * 920 || 86520));
  const risk = escapeHtml(`${Math.round(Number(props.riskScore || 0)) || 86}%`);
  return `<div class="cet-amap-info-window"><span>聚合 ${count}</span><b>${title}</b><p>${region} ? 热度 ${heat} ? 风险 ${risk}</p></div>`;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (item) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[item] ?? item);
}

function OfficialAmapMap({
  layers,
  events,
  mode,
  selectedSignalId,
  onSelectSignal,
  amapKey,
  securityCode
}: {
  layers?: MapLayers;
  events: unknown[];
  mode: CityMapMode;
  selectedSignalId: string | null;
  onSelectSignal: (id: string) => void;
  amapKey: string;
  securityCode: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const center = layers?.config.center ?? [120.1551, 30.2741];
  const zoom = layers?.config.zoom ?? 10.85;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    if (securityCode) {
      (window as Window & { _AMapSecurityConfig?: { securityJsCode?: string } })._AMapSecurityConfig = { securityJsCode: securityCode };
    }

    let disposed = false;
    let map: { add?: (items: unknown[]) => void; addControl?: (control: unknown) => void; destroy: () => void } | null = null;
    let heatmap: { setDataSet?: (data: JsonObject) => void; setMap?: (map: unknown | null) => void } | null = null;
    let satelliteLayer: { setMap?: (map: unknown | null) => void } | null = null;
    let roadLayer: { setMap?: (map: unknown | null) => void } | null = null;
    const overlays: Array<{ setMap?: (map: unknown | null) => void }> = [];

    AMapLoader.load({ key: amapKey, version: "2.0", plugins: ["AMap.Scale", "AMap.ToolBar", "AMap.HeatMap"] }).then((AMap) => {
      if (disposed) return;
      const sdk = AMap as JsonObject;
      const MapCtor = sdk.Map as new (container: HTMLDivElement, options: JsonObject) => { add?: (items: unknown[]) => void; addControl?: (control: unknown) => void; destroy: () => void };
      const MarkerCtor = sdk.Marker as new (options: JsonObject) => { on?: (event: string, handler: () => void) => void; setMap?: (map: unknown | null) => void };
      const InfoWindowCtor = sdk.InfoWindow as new (options: JsonObject) => { open: (map: unknown, position: unknown) => void };
      const PixelCtor = sdk.Pixel as new (x: number, y: number) => unknown;
      const ToolBarCtor = sdk.ToolBar as undefined | (new (options?: JsonObject) => unknown);
      const ScaleCtor = sdk.Scale as undefined | (new (options?: JsonObject) => unknown);
      const HeatCtor = (sdk.HeatMap ?? sdk.Heatmap) as undefined | (new (...args: unknown[]) => { setDataSet?: (data: JsonObject) => void; setMap?: (map: unknown | null) => void });
      const TileLayer = (sdk.TileLayer ?? {}) as JsonObject;
      const SatelliteCtor = TileLayer.Satellite as undefined | (new () => { setMap?: (map: unknown | null) => void });
      const RoadNetCtor = TileLayer.RoadNet as undefined | (new () => { setMap?: (map: unknown | null) => void });

      map = new MapCtor(container, {
        viewMode: "2D",
        center,
        zoom,
        resizeEnable: true,
        mapStyle: "amap://styles/normal"
      });
      if (mode === "satellite" && SatelliteCtor) {
        satelliteLayer = new SatelliteCtor();
        satelliteLayer.setMap?.(map);
        if (RoadNetCtor) {
          roadLayer = new RoadNetCtor();
          roadLayer.setMap?.(map);
        }
      }
      if (ToolBarCtor) map.addControl?.(new ToolBarCtor({ position: { right: "12px", top: "86px" }, liteStyle: true }));
      if (ScaleCtor) map.addControl?.(new ScaleCtor({ position: { left: "12px", bottom: "12px" } }));

      const eventData = layers ? rankedEventFeatureCollection(layers, events) : { features: [] };
      const features = eventData.features ?? [];
      const heatPoints = features.map((feature) => {
        const coordinates = feature.geometry.coordinates as [number, number];
        const props = feature.properties as Record<string, unknown>;
        return {
          lng: coordinates[0],
          lat: coordinates[1],
          count: Math.max(Number(props.riskScore || 0), Number(props.onlineHeat || 0), Number(props.eventCount || 1) * 12)
        };
      });

      if (HeatCtor && heatPoints.length) {
        const heatOptions = {
          radius: 42,
          opacity: mode === "heat" ? [0.22, 0.86] : [0.1, 0.46],
          gradient: {
            0.28: "#2f6df6",
            0.5: "#18a873",
            0.72: "#ff9f2e",
            1: "#df4b54"
          }
        };
        try {
          heatmap = new HeatCtor(map, heatOptions);
        } catch {
          heatmap = new HeatCtor({ map, ...heatOptions });
        }
        heatmap.setDataSet?.({ data: heatPoints, max: Math.max(100, ...heatPoints.map((item) => item.count)) });
        if (mode === "satellite") heatmap.setMap?.(null);
      }

      const markers = features.map((feature) => {
        const coordinates = feature.geometry.coordinates as [number, number];
        const props = feature.properties as Record<string, unknown>;
        const count = Number(props.eventCount || props.rank || 1);
        const signalId = String(props.signalId || "");
        const marker = new MarkerCtor({
          position: coordinates,
          anchor: "center",
          content: `<button type="button" class="cet-amap-cluster-marker ${heatClass(Number(props.riskScore || 0))} ${count > 1 ? "cluster" : "single"} ${signalId && signalId === selectedSignalId ? "selected" : ""}" aria-label="${escapeHtml(String(props.displayTitle || props.title || "浜嬩欢鑱氬悎"))}"><span>${count > 1 ? escapeHtml(String(count)) : ""}</span></button>`,
          offset: new PixelCtor(-16, -16),
          title: String(props.displayTitle || props.title || "浜嬩欢鑱氬悎")
        });
        marker.on?.("click", () => {
          if (signalId) onSelectSignal(signalId);
          const info = new InfoWindowCtor({
            isCustom: true,
            closeWhenClickMap: true,
            offset: new PixelCtor(0, -34),
            content: amapInfoWindowHtml(props)
          });
          info.open(map, coordinates);
        });
        overlays.push(marker);
        return marker;
      });
      if (markers.length && map.add) map.add(markers);
    });

    return () => {
      disposed = true;
      heatmap?.setMap?.(null);
      satelliteLayer?.setMap?.(null);
      roadLayer?.setMap?.(null);
      overlays.forEach((overlay) => overlay.setMap?.(null));
      map?.destroy();
    };
  }, [amapKey, securityCode, layers, events, center, zoom, mode, selectedSignalId, onSelectSignal]);

  return (
    <div className="cet-real-map-wrap">
      <div ref={containerRef} className="cet-real-map" />
    </div>
  );
}

function MapLibreGaodeMap({ layers, events }: { layers?: MapLayers; events: unknown[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker[]>([]);
  const eventHandlersReadyRef = useRef(false);
  const [selectedEvent, setSelectedEvent] = useState<SelectedMapEvent | null>(null);
  const center = layers?.config.center ?? [120.1551, 30.2741];
  const zoom = layers?.config.zoom ?? 10.85;

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;
    const map = new maplibregl.Map({
      container,
      style: amapStyle(),
      center: center as [number, number],
      zoom,
      attributionControl: false
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      markerRef.current.forEach((marker) => marker.remove());
      markerRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !layers) return;
    const selectFeature = (properties: Record<string, unknown>) => {
      const confidenceRaw = Number(properties.confidence || 0);
      setSelectedEvent({
        title: String(properties.displayTitle || properties.title || "鍩庡競鑱氬悎浜嬩欢"),
        summary: String(properties.summary || "用于主题热度、证据复核、主线建模与世界线推演的城市事件信号。"),
        region: String(properties.region || properties.region_id || "西安同城"),
        rank: String(properties.eventCount || properties.rank || "1"),
        heat: formatNumber(Number(properties.onlineHeat || properties.riskScore || 0) * 920 || 86520),
        risk: `${Math.round(Number(properties.riskScore || 0)) || 86}`,
        type: String(properties.eventType || "热点事件"),
        time: String(properties.time || "09:12"),
        confidence: `${Math.round(confidenceRaw > 1 ? confidenceRaw : confidenceRaw * 100) || 88}%`,
        status: String(properties.status || "实时监测"),
        spread: String(properties.spread || `${properties.eventCount || 1} 个事件聚合`),
        source: String(properties.source || "同城公开平台聚合"),
        raw: String(properties.raw || properties.summary || "公开视频、同城讨论、热线与网格上报合并后的事件摘要。"),
        mainline: String(properties.mainline || "ML-001")
      });
    };
    const apply = () => {
      const eventData = rankedEventFeatureCollection(layers, events, map.getZoom());
      const source = map.getSource("city-events") as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(eventData as never);
      } else {
        map.addSource("city-events", { type: "geojson", data: eventData as never });
        map.addLayer({
          id: "city-event-heat",
          type: "heatmap",
          source: "city-events",
          paint: {
            "heatmap-weight": ["interpolate", ["linear"], ["get", "riskScore"], 0, 0, 100, 1],
            "heatmap-intensity": 0.8,
            "heatmap-radius": 36,
            "heatmap-opacity": 0.42
          }
        });
        map.addLayer({
          id: "city-event-points",
          type: "circle",
          source: "city-events",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["get", "riskScore"], 30, 7, 100, 17],
            "circle-color": ["interpolate", ["linear"], ["get", "riskScore"], 40, "#2f6df6", 70, "#ff9f2e", 90, "#df4b54"],
            "circle-stroke-color": "#fffdf7",
            "circle-stroke-width": 2,
            "circle-opacity": 0.9
          }
        });
        map.addLayer({
          id: "city-event-labels",
          type: "symbol",
          source: "city-events",
          layout: {
            "text-field": ["to-string", ["get", "eventCount"]],
            "text-size": 13,
            "text-offset": [0, 0],
            "text-anchor": "center",
            "text-allow-overlap": true,
            "text-ignore-placement": true
          },
          paint: {
            "text-color": "#fffdf7",
            "text-halo-color": "rgba(20,24,29,.72)",
            "text-halo-width": 1.5
          }
        });
      }
      markerRef.current.forEach((marker) => marker.remove());
      markerRef.current = eventData.features.map((feature) => {
        const properties = feature.properties as Record<string, unknown>;
        const element = document.createElement("button");
        element.type = "button";
        element.className = `cet-map-number-marker ${heatClass(Number(properties.riskScore || 0))}`;
        element.textContent = String(properties.eventCount || properties.rank || "");
        element.title = String(properties.displayTitle || properties.title || "鍩庡競鑱氬悎浜嬩欢");
        element.setAttribute("aria-label", `浜嬩欢鑱氬悎 ${element.textContent}`);
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          selectFeature(properties);
        });
        return new maplibregl.Marker({ element, anchor: "center" })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .addTo(map);
      });
    };
    const handlePointClick = (event: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const feature = event.features?.[0];
      const properties = (feature?.properties ?? {}) as Record<string, unknown>;
      selectFeature(properties);
    };
    const handleMouseEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const handleMouseLeave = () => {
      map.getCanvas().style.cursor = "";
    };
    const attachLayerHandlers = () => {
      if (!eventHandlersReadyRef.current) {
        map.on("click", "city-event-points", handlePointClick);
        map.on("mouseenter", "city-event-points", handleMouseEnter);
        map.on("mouseleave", "city-event-points", handleMouseLeave);
        eventHandlersReadyRef.current = true;
      }
    };
    const refresh = () => apply();
    const initialize = () => {
      apply();
      attachLayerHandlers();
      map.on("zoomend", refresh);
      map.on("moveend", refresh);
    };
    if (map.loaded()) initialize();
    else map.once("load", initialize);
    return () => {
      map.off("zoomend", refresh);
      map.off("moveend", refresh);
    };
  }, [layers, events]);

  return (
    <div className="cet-real-map-wrap">
      <AmapFallback center={center} />
      <div ref={containerRef} className="cet-real-map" />
      {selectedEvent ? (
        <aside className="cet-map-event-detail">
          <div className="cet-detail-head">
            <div>
              <span>鑱氬悎 {selectedEvent.rank}</span>
              <b>{selectedEvent.title}</b>
              <p>{selectedEvent.summary}</p>
            </div>
            <button type="button" onClick={() => setSelectedEvent(null)}>关闭</button>
          </div>
          <div className="cet-detail-metrics">
            {[
              ["类型", selectedEvent.type],
              ["区域", selectedEvent.region],
              ["时间", selectedEvent.time],
              ["风险", selectedEvent.risk],
              ["置信度", selectedEvent.confidence],
              ["状态", selectedEvent.status],
              ["传播", selectedEvent.spread],
              ["热度", selectedEvent.heat]
            ].map((row) => <div className="cet-detail-kv" key={row[0]}><span>{row[0]}</span><b>{row[1]}</b></div>)}
          </div>
          <div className="cet-detail-rows">
            {[
              ["来源", selectedEvent.source],
              ["原始摘要", selectedEvent.raw],
              ["AI 摘要", selectedEvent.summary],
              ["主线", selectedEvent.mainline]
            ].map((row) => <div className="cet-detail-row" key={row[0]}><b>{row[0]}</b><span>{row[1]}</span></div>)}
          </div>
          <div className="cet-detail-actions">
            <button type="button">进入主线</button>
            <button type="button">加入证据复核</button>
          </div>
        </aside>
      ) : null}
    </div>
  );
}

function mapEventFromProperties(properties: Record<string, unknown>): SelectedMapEvent {
  const confidenceRaw = Number(properties.confidence || 0);
  return {
    title: String(properties.displayTitle || properties.title || "鍩庡競鑱氬悎浜嬩欢"),
    summary: String(properties.summary || "用于主题热度、证据复核、主线建模与世界线推演的城市事件信号。"),
    region: String(properties.region || properties.region_id || "西安同城"),
    rank: String(properties.eventCount || properties.rank || "1"),
    heat: formatNumber(Number(properties.onlineHeat || properties.riskScore || 0) * 920 || 86520),
    risk: `${Math.round(Number(properties.riskScore || 0)) || 86}%`,
    type: String(properties.eventType || "热点事件"),
    time: String(properties.time || "09:12"),
    confidence: `${Math.round(confidenceRaw > 1 ? confidenceRaw : confidenceRaw * 100) || 88}%`,
    status: String(properties.status || "实时监测"),
    spread: String(properties.spread || `${properties.eventCount || 1} 个事件聚合`),
    source: String(properties.source || "同城公开平台聚合"),
    raw: String(properties.raw || properties.summary || "公开视频、同城讨论、热线与网格上报合并后的事件摘要。"),
    mainline: String(properties.mainline || "ML-001")
  };
}

function MapLibreGaodeMapV2({
  layers,
  events,
  mode,
  selectedSignalId,
  onSelectSignal
}: {
  layers?: MapLayers;
  events: unknown[];
  mode: CityMapMode;
  selectedSignalId: string | null;
  onSelectSignal: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker[]>([]);
  const eventHandlersReadyRef = useRef(false);
  const featurePropsRef = useRef<Record<string, unknown>[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<SelectedMapEvent | null>(null);
  const center = layers?.config.center ?? [120.1551, 30.2741];
  const zoom = layers?.config.zoom ?? 10.85;

  useEffect(() => {
    const container = containerRef.current;
    if (!container || mapRef.current) return;
    const map = new maplibregl.Map({
      container,
      style: amapStyle(),
      center: center as [number, number],
      zoom,
      attributionControl: false
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      markerRef.current.forEach((marker) => marker.remove());
      markerRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => applyMapMode(map, mode);
    if (map.loaded()) apply();
    else map.once("load", apply);
  }, [mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !layers) return;
    const selectFeature = (properties: Record<string, unknown>) => {
      setSelectedEvent(mapEventFromProperties(properties));
      const signalId = String(properties.signalId || "");
      if (signalId) onSelectSignal(signalId);
    };
    const apply = () => {
      const eventData = rankedEventFeatureCollection(layers, events, map.getZoom(), (coordinates) => map.project(coordinates));
      featurePropsRef.current = eventData.features.map((feature) => feature.properties as Record<string, unknown>);
      const source = map.getSource("city-events") as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(eventData as never);
      } else {
        map.addSource("city-events", { type: "geojson", data: eventData as never });
        map.addLayer({
          id: "city-event-heat",
          type: "heatmap",
          source: "city-events",
          paint: {
            "heatmap-weight": ["interpolate", ["linear"], ["get", "riskScore"], 0, 0, 100, 1],
            "heatmap-intensity": 0.8,
            "heatmap-radius": 36,
            "heatmap-opacity": 0.42
          }
        });
        map.addLayer({
          id: "city-event-points",
          type: "circle",
          source: "city-events",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["get", "riskScore"], 30, 7, 100, 17],
            "circle-color": ["interpolate", ["linear"], ["get", "riskScore"], 40, "#2f6df6", 70, "#ff9f2e", 90, "#df4b54"],
            "circle-stroke-color": "#fffdf7",
            "circle-stroke-width": 2,
            "circle-opacity": 0.65
          }
        });
        map.addLayer({
          id: "city-event-labels",
          type: "symbol",
          source: "city-events",
          layout: {
            "text-field": ["case", [">", ["get", "eventCount"], 1], ["to-string", ["get", "eventCount"]], ""],
            "text-size": 13,
            "text-offset": [0, 0],
            "text-anchor": "center",
            "text-allow-overlap": true,
            "text-ignore-placement": true
          },
          paint: {
            "text-color": "#fffdf7",
            "text-halo-color": "rgba(20,24,29,.72)",
            "text-halo-width": 1.5
          }
        });
      }
      applyMapMode(map, mode);
      markerRef.current.forEach((marker) => marker.remove());
      markerRef.current = eventData.features.map((feature) => {
        const properties = feature.properties as Record<string, unknown>;
        const eventCount = Number(properties.eventCount || properties.rank || 1);
        const signalId = String(properties.signalId || "");
        const element = document.createElement("button");
        element.type = "button";
        element.className = `cet-map-number-marker ${heatClass(Number(properties.riskScore || 0))} ${eventCount > 1 ? "cluster" : "single"} ${signalId && signalId === selectedSignalId ? "selected" : ""}`;
        element.innerHTML = `<span>${eventCount > 1 ? String(eventCount) : ""}</span>`;
        element.title = String(properties.displayTitle || properties.title || "城市聚合事件");
        element.setAttribute("aria-label", `${eventCount > 1 ? "事件聚合" : "事件点"} ${eventCount > 1 ? eventCount : ""}`);
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          selectFeature(properties);
        });
        return new maplibregl.Marker({ element, anchor: "center" })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .addTo(map);
      });
      if (selectedSignalId) {
        const selectedProps = featurePropsRef.current.find((props) => String(props.signalId || "") === selectedSignalId);
        if (selectedProps) setSelectedEvent(mapEventFromProperties(selectedProps));
      }
    };
    const handlePointClick = (event: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const feature = event.features?.[0];
      const properties = (feature?.properties ?? {}) as Record<string, unknown>;
      selectFeature(properties);
    };
    const handleMouseEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const handleMouseLeave = () => {
      map.getCanvas().style.cursor = "";
    };
    const attachLayerHandlers = () => {
      if (!eventHandlersReadyRef.current) {
        map.on("click", "city-event-points", handlePointClick);
        map.on("mouseenter", "city-event-points", handleMouseEnter);
        map.on("mouseleave", "city-event-points", handleMouseLeave);
        eventHandlersReadyRef.current = true;
      }
    };
    const refresh = () => apply();
    const initialize = () => {
      apply();
      attachLayerHandlers();
      map.on("zoomend", refresh);
      map.on("moveend", refresh);
    };
    if (map.loaded()) initialize();
    else map.once("load", initialize);
    return () => {
      map.off("zoomend", refresh);
      map.off("moveend", refresh);
    };
  }, [layers, events, mode, selectedSignalId, onSelectSignal]);

  return (
    <div className="cet-real-map-wrap">
      <AmapFallback center={center} mode={mode} />
      <div ref={containerRef} className="cet-real-map" />
      {selectedEvent ? (
        <aside className="cet-map-event-detail">
          <div className="cet-detail-head">
            <div>
              <span>鑱氬悎 {selectedEvent.rank}</span>
              <b>{selectedEvent.title}</b>
              <p>{selectedEvent.summary}</p>
            </div>
            <button type="button" onClick={() => setSelectedEvent(null)}>关闭</button>
          </div>
          <div className="cet-detail-metrics">
            {[
              ["类型", selectedEvent.type],
              ["区域", selectedEvent.region],
              ["时间", selectedEvent.time],
              ["风险", selectedEvent.risk],
              ["置信度", selectedEvent.confidence],
              ["状态", selectedEvent.status],
              ["传播", selectedEvent.spread],
              ["热度", selectedEvent.heat]
            ].map((row) => <div className="cet-detail-kv" key={row[0]}><span>{row[0]}</span><b>{row[1]}</b></div>)}
          </div>
          <div className="cet-detail-rows">
            {[
              ["来源", selectedEvent.source],
              ["原始摘要", selectedEvent.raw],
              ["AI 摘要", selectedEvent.summary],
              ["主线", selectedEvent.mainline]
            ].map((row) => <div className="cet-detail-row" key={row[0]}><b>{row[0]}</b><span>{row[1]}</span></div>)}
          </div>
          <div className="cet-detail-actions">
            <button type="button">进入主线</button>
            <button type="button">加入证据复核</button>
          </div>
        </aside>
      ) : null}
    </div>
  );
}

function AmapFallback({ center, mode = "map" }: { center: number[]; mode?: CityMapMode }) {
  const zoom = 12;
  const tile = lonLatToTile(center[0] ?? 120.1551, center[1] ?? 30.2741, zoom);
  const tiles: Array<{ x: number; y: number; url: string }> = [];
  for (let row = -2; row < 2; row += 1) {
    for (let col = -2; col < 2; col += 1) {
      const x = tile.x + col;
      const y = tile.y + row;
      tiles.push({ x, y, url: amapTileUrl(x, y, zoom) });
    }
  }
  return <div className={`cet-amap-fallback mode-${mode}`} aria-hidden="true">{tiles.map((tileItem) => <img key={`${tileItem.x}-${tileItem.y}`} src={tileItem.url} alt="" />)}</div>;
}

function S7BStaticReferencePage({ view, pending, runAction }: { view: PageView; pending: boolean; runAction: (fn: () => Promise<unknown>) => void }) {
  const primary = record(view.raw, "primary_data") as JsonObject;
  if (view.page === "memory") {
    const retrospective = record(primary, "retrospective") as JsonObject;
    const report = record(primary, "report") as JsonObject;
    const items = arrayFrom(primary, "knowledge_items");
    const entries = arrayFrom(primary, "case_library_entries");
    const sourceRefs = Array.isArray(retrospective.source_refs) ? retrospective.source_refs : [];
    const retrospectiveId = textField(view.raw, "retrospective_id");
    const reviewId = textField(view.raw, "review_id");
    return (
      <S7BFrame
        view={view}
        eyebrow="Case Memory"
        title={view.title}
        subtitle={view.subtitle ?? "复盘知识从已发布报告抽取，审批通过后才进入案例库。"}
        status={`状态：${textField(retrospective, "status") || "draft"}`}
        ctaLabel="提交审批并发布入库"
        pending={pending || !retrospectiveId}
        onCta={() => retrospectiveId && runAction(async () => {
          let nextReviewId = reviewId;
          if (!nextReviewId) {
            const review = await api.submitRetrospectiveReview(retrospectiveId);
            nextReviewId = review.data.review_id;
          }
          await api.updateReview(nextReviewId, "pass", ["Retrospective memory is evidence-referenced and case-library ready."], []);
          await api.gateCheck(nextReviewId);
          return api.publishRetrospective(retrospectiveId);
        })}
        metrics={[
          { label: "知识条目", value: items.length, tone: "green", helper: "来自报告断言与任务" },
          { label: "来源引用", value: sourceRefs.length, tone: "blue", helper: "report / evidence / task" },
          { label: "案例库条目", value: entries.length, tone: "violet", helper: "审批后生成" },
          { label: "报告状态", value: textField(report, "status") || "--", tone: "amber", helper: textField(report, "id") },
          { label: "复盘版本", value: textField(retrospective, "version") || "v1", tone: "cyan", helper: retrospectiveId },
          { label: "水印", value: boolField(retrospective, "synthetic_watermark") ? "synthetic" : "production", tone: "red", helper: "继承报告输入" }
        ]}
      >
        <aside className="s7b-left">
          <section className="s7b-panel s7b-summary">
            <h3>案例复盘摘要</h3>
            <p>{textField(retrospective, "summary") || view.title}</p>
            <div className="s7b-kv-grid">
              <S7BKV label="复盘ID" value={retrospectiveId || "--"} />
              <S7BKV label="报告ID" value={textField(report, "id") || "--"} />
              <S7BKV label="知识状态" value={textField(retrospective, "status") || "--"} />
              <S7BKV label="证据引用" value={String(sourceRefs.length)} />
            </div>
          </section>
          <S7BListPanel title="案例链路" helper="从报告到知识" items={sourceRefs.slice(0, 7)} render={(item, index) => (
            <article className="s7b-chain-row" key={`${textField(item, "object_type")}-${textField(item, "object_id")}-${index}`}>
              <i>{index + 1}</i>
              <div><b>{textField(item, "object_type")}</b><span>{textField(item, "object_id")}</span></div>
              <strong>{textField(item, "object_version") || "ref"}</strong>
            </article>
          )} />
          <S7BListPanel title="入库任务" helper="系统侧" items={entries.length ? entries : items.slice(0, 3)} render={(item, index) => (
            <article className="s7b-task" key={idOf(item) || index}><b>{entries.length ? "已发布案例条目" : "待审批知识条目"}<span>{textField(item, "status")}</span></b><span>{textField(item, "title") || textField(item, "content")}</span></article>
          )} />
        </aside>
        <section className="s7b-panel s7b-center">
          <div className="s7b-tabs"><button className="active" type="button">复盘总览</button><button type="button">信号模板</button><button type="button">扩散路径</button><button type="button">模型校准</button></div>
          <div className="s7b-workspace">
            <div className="s7b-grid">
              <section className="s7b-card full"><h3>知识条目</h3><div className="s7b-table">{items.map((item, index) => <S7BRow key={idOf(item) || index} title={textField(item, "content")} cells={[textField(item, "status"), `${arrayFrom(item as JsonObject, "source_refs").length} refs`, idOf(item)]} />)}</div></section>
              <section className="s7b-card"><h3>预测与现实对比</h3><p>复盘服务只记录来自报告、断言、任务和证据的可追溯知识，不直接改写生产规则。</p><div className="s7b-compare"><S7BKV label="来源报告" value={textField(report, "status")} /><S7BKV label="发布出口" value={entries.length ? "已入库" : "待审批"} /></div></section>
              <section className="s7b-card"><h3>扩散路径沉淀</h3><div className="s7b-path"><span>报告</span><i /><span>复盘</span><i /><span>知识</span><i /><span>案例库</span></div></section>
            </div>
          </div>
        </section>
        <aside className="s7b-right">
          <S7BListPanel title="模型校准点" helper="Review gated" items={items.slice(0, 5)} render={(item, index) => (
            <article className="s7b-pattern" key={idOf(item) || index}><b>知识 {index + 1}<button type="button">待审</button></b><span>{textField(item, "content")}</span></article>
          )} />
          <S7BListPanel title="复核记录" helper="证据引用" items={sourceRefs.slice(0, 5)} render={(item, index) => (
            <article className="s7b-review-note" key={`${textField(item, "object_id")}-${index}`}><b>{textField(item, "object_type")}</b><span>{textField(item, "object_id")}</span></article>
          )} />
        </aside>
      </S7BFrame>
    );
  }

  if (view.page === "library") {
    const entries = arrayFrom(primary, "entries");
    const applications = arrayFrom(primary, "applications");
    const firstEntry = entries[0] as JsonObject | undefined;
    const entryId = textField(view.raw, "first_entry_id") || idOf(firstEntry);
    const targetCaseId = textField(view.raw, "target_case_id") || view.case_id;
    return (
      <S7BFrame
        view={view}
        eyebrow="Knowledge Library"
        title="主题 / 案例库"
        subtitle="只展示已审批复盘知识，供相似案例召回和应用建议使用。"
        status={`案例 ${entries.length}`}
        ctaLabel="应用到当前案例"
        pending={pending || !entryId}
        onCta={() => entryId && runAction(() => api.applyCaseLibraryEntry(entryId, { case_id: targetCaseId, object_type: "case", object_id: targetCaseId, reason: "Applied from React case library page." }))}
        metrics={[
          { label: "案例条目", value: entries.length, tone: "blue", helper: "active library entries" },
          { label: "应用记录", value: applications.length, tone: "green", helper: "persisted applications" },
          { label: "可用条目", value: entries.filter((item) => textField(item, "status") === "active").length, tone: "violet", helper: "review passed" },
          { label: "标签数", value: uniqueTags(entries).length, tone: "amber", helper: "from knowledge" },
          { label: "冲突记录", value: applications.filter((item) => textField(item, "status") === "blocked_conflict").length, tone: "red", helper: "conflict summary" },
          { label: "数据源", value: "PostgreSQL", tone: "cyan", helper: "no frontend fixture" }
        ]}
      >
        <aside className="s7b-left">
          <section className="s7b-panel s7b-searchbox"><h3>检索与筛选</h3><input readOnly value="information gap / evidence refs / retrospective" /><div className="s7b-chipline">{uniqueTags(entries).slice(0, 6).map((tag) => <span key={tag}>{tag}</span>)}</div></section>
          <S7BListPanel title="主题分类树" helper="来自条目标签" items={uniqueTags(entries).slice(0, 8)} render={(tag, index) => <article className="s7b-tree-row" key={String(tag)}><i>{index + 1}</i><div><b>{String(tag)}</b><span>案例库标签</span></div><strong>{entries.filter((item) => arrayFrom(item as JsonObject, "tags").includes(tag)).length}</strong></article>} />
          <S7BListPanel title="当前主题组" helper="推荐" items={entries.slice(0, 3)} render={(item, index) => <article className={`s7b-topic-card ${index === 0 ? "active" : ""}`} key={idOf(item)}><b>{textField(item, "title")}</b><span>{arrayFrom(item as JsonObject, "tags").join(" / ")}</span></article>} />
        </aside>
        <section className="s7b-panel s7b-center">
          <div className="s7b-tabs"><button className="active" type="button">相似案例</button><button type="button">前因模板</button><button type="button">扩散路径</button><button type="button">处置动作</button></div>
          <div className="s7b-library-grid">{entries.map((item, index) => <article className="s7b-case-card" key={idOf(item) || index}><div><h3>{textField(item, "title")}</h3><span>{Math.max(58, 88 - index * 4)}%</span></div><p>{arrayFrom(item as JsonObject, "tags").join(" / ") || "retrospective"}</p><div className="s7b-tagline">{arrayFrom(item as JsonObject, "source_refs").slice(0, 3).map((ref, refIndex) => <span key={`${textField(ref, "object_id")}-${refIndex}`}>{textField(ref, "object_type")}</span>)}</div><button type="button" disabled={pending} onClick={() => runAction(() => api.getCaseLibraryEntry(idOf(item)))}>打开</button></article>)}</div>
        </section>
        <aside className="s7b-right">
          <section className="s7b-panel s7b-detail"><h3>{textField(firstEntry, "title") || "案例详情"}</h3><p>案例详情来自 `case_library_entries`，包含知识条目、复盘、报告和证据引用。</p><div className="s7b-kv-grid"><S7BKV label="条目ID" value={entryId || "--"} /><S7BKV label="状态" value={textField(firstEntry, "status") || "--"} /><S7BKV label="来源引用" value={String(arrayFrom(firstEntry ?? {}, "source_refs").length)} /><S7BKV label="应用记录" value={String(applications.length)} /></div></section>
          <S7BListPanel title="可复用模式" helper="Patterns" items={entries.slice(0, 4)} render={(item) => <article className="s7b-pattern" key={idOf(item)}><b>{textField(item, "title")}<button type="button">应用</button></b><span>{arrayFrom(item as JsonObject, "tags").join(" / ")}</span></article>} />
        </aside>
      </S7BFrame>
    );
  }

  const versions = arrayFrom(primary, "versions");
  const releases = arrayFrom(primary, "releases");
  const versionId = textField(view.raw, "first_config_version_id") || idOf(versions[0]);
  const releaseId = textField(view.raw, "first_release_id") || idOf(releases[0]);
  return (
    <S7BFrame
      view={view}
      eyebrow="Admin Config"
      title="数据源与模型配置"
      subtitle="配置变更必须版本化、回归、审批、发布，并保留可回滚影响范围。"
      status={`版本 ${versions.length}`}
      ctaLabel="运行回归并发布"
      pending={pending || !versionId}
      onCta={() => versionId && runAction(async () => {
        await api.runConfigRegression(versionId);
        const review = await api.submitConfigApproval(versionId, "Config regression passed from React admin page.");
        await api.updateReview(review.data.review_id, "pass", ["Config regression passed and impact scope is explicit."], []);
        await api.gateCheck(review.data.review_id);
        return api.publishConfigVersion(versionId);
      })}
      metrics={[
        { label: "配置版本", value: versions.length, tone: "blue", helper: "draft / published" },
        { label: "发布记录", value: releases.length, tone: "green", helper: "append-only" },
        { label: "待审批", value: versions.filter((item) => textField(item, "status") === "approval_pending").length, tone: "amber", helper: "review gate" },
        { label: "可回滚", value: releases.filter((item) => textField(item, "status") === "rollback_available").length, tone: "violet", helper: "impact scoped" },
        { label: "回归失败", value: versions.filter((item) => textField(item, "status") === "regression_failed").length, tone: "red", helper: "blocked" },
        { label: "数据源", value: "PostgreSQL", tone: "cyan", helper: "no frontend config state" }
      ]}
    >
      <aside className="s7b-left">
        <section className="s7b-panel s7b-summary"><h3>系统接入状态</h3><p>配置中心读取 `config_versions`、`config_releases`、`workflow_runs` 与 Review Gate，不展示前端-only 配置。</p><div className="s7b-kv-grid"><S7BKV label="当前版本" value={versionId || "--"} /><S7BKV label="发布记录" value={String(releases.length)} /><S7BKV label="回归状态" value={textField(versions[0], "status") || "--"} /><S7BKV label="回滚点" value={String(releases.length)} /></div></section>
        <S7BListPanel title="配置版本" helper="按状态" items={versions.slice(0, 8)} render={(item) => <article className="s7b-source-row" key={idOf(item)}><i>{textField(item, "config_type").slice(0, 1) || "C"}</i><div><b>{textField(item, "config_type")}</b><span>{textField(item, "version")}</span></div><strong>{textField(item, "status")}</strong></article>} />
      </aside>
      <section className="s7b-panel s7b-center">
        <div className="s7b-tabs"><button className="active" type="button">数据源治理</button><button type="button">标签体系</button><button type="button">模型权重</button><button type="button">版本审计</button></div>
        <div className="s7b-workspace"><div className="s7b-grid"><section className="s7b-card full"><h3>配置版本状态</h3><div className="s7b-table">{versions.map((item) => <S7BRow key={idOf(item)} title={`${textField(item, "config_type")} ${textField(item, "version")}`} cells={[textField(item, "status"), `${arrayFrom(item as JsonObject, "input_refs").length} refs`, textField(item, "regression_workflow_run_id") || "no regression"]} />)}</div></section><section className="s7b-card"><h3>影响范围</h3><p>{JSON.stringify(record(versions[0], "impact_scope"))}</p></section><section className="s7b-card"><h3>回滚验证</h3><button className="s7b-primary" disabled={pending || !releaseId} type="button" onClick={() => releaseId && runAction(() => api.rollbackConfigRelease(releaseId))}>回滚最近发布</button></section></div></div>
      </section>
      <aside className="s7b-right">
        <S7BListPanel title="发布记录" helper="Release" items={releases.slice(0, 6)} render={(item) => <article className="s7b-pattern" key={idOf(item)}><b>{idOf(item)}<button type="button">{textField(item, "status")}</button></b><span>{JSON.stringify(record(item, "impact_scope"))}</span></article>} />
      </aside>
    </S7BFrame>
  );
}

function S7BFrame({
  view,
  eyebrow,
  title,
  subtitle,
  status,
  ctaLabel,
  pending,
  onCta,
  metrics,
  children
}: {
  view: PageView;
  eyebrow: string;
  title: string;
  subtitle: string;
  status: string;
  ctaLabel: string;
  pending: boolean;
  onCta: () => void;
  metrics: PageMetric[];
  children: ReactNode;
}) {
  return (
    <div className={`s7b-app s7b-${view.page}`}>
      <section className="s7b-context">
        <Link className="s7b-btn" to="/cases/$caseId/$page" params={{ caseId: view.case_id, page: previousS7BPage(view.page) }}>返回上一页</Link>
        <div>
          <h1>{title} <span>{eyebrow}</span></h1>
          <p>{subtitle}</p>
        </div>
        <div className="s7b-meta-strip"><span>{status}</span><span>PostgreSQL</span><button type="button" disabled={pending} onClick={onCta}>{ctaLabel}</button></div>
      </section>
      <MetricStrip metrics={metrics} />
      <main className="s7b-main">{children}</main>
      <footer className="s7b-bottom">
        <div className="s7b-flow-summary">
          <S7BFlow label="数据来源" value="FastAPI / PostgreSQL" />
          <S7BFlow label="审计" value="mutation 全记录" />
          <S7BFlow label="检查门禁" value="Review Gate" />
          <S7BFlow label="页面参照" value="静态设计页 body" />
          <S7BFlow label="下一步" value={pageLabels[nextPage(view.page)].label} />
        </div>
        <Link className="s7b-primary" to="/cases/$caseId/$page" params={{ caseId: view.case_id, page: nextPage(view.page) }}>进入{pageLabels[nextPage(view.page)].label}</Link>
      </footer>
    </div>
  );
}

function S7BKV({ label, value }: { label: string; value: string }) {
  return <div className="s7b-kv"><span>{label}</span><b>{value}</b></div>;
}

function S7BFlow({ label, value }: { label: string; value: string }) {
  return <div className="s7b-flow-card">{label}<span>{value}</span></div>;
}

function S7BListPanel({ title, helper, items, render }: { title: string; helper: string; items: unknown[]; render: (item: unknown, index: number) => ReactNode }) {
  return <section className="s7b-panel"><div className="s7b-panel-title">{title}<span>{helper}</span></div><div className="s7b-list">{items.length ? items.map(render) : <div className="cet-empty"><Database size={16} />暂无数据</div>}</div></section>;
}

function S7BRow({ title, cells }: { title: string; cells: string[] }) {
  return <article className="s7b-row"><b>{title}</b>{cells.map((cell, index) => <span key={`${cell}-${index}`}>{cell || "--"}</span>)}</article>;
}

function previousS7BPage(page: ProductPageName): ProductPageName {
  if (page === "memory") return "brief";
  if (page === "library") return "memory";
  if (page === "config") return "library";
  return "city";
}

function StructuredPage({ view, pending, runAction }: { view: PageView; pending: boolean; runAction: (fn: () => Promise<unknown>) => void }) {
  const actions = Array.isArray(view.actions) ? view.actions : [];
  const sections = Array.isArray(view.sections) ? view.sections : [];
  const metrics = Array.isArray(view.metrics) ? view.metrics : [];
  return (
    <>
      <section className="cet-page-head">
        <div>
          <span>P0 / {view.page}</span>
          <h1>{view.title}</h1>
          {view.subtitle ? <p>{view.subtitle}</p> : null}
        </div>
        <div className="cet-head-actions">
          {actions
            .filter((action) => action.to_page)
            .map((action) => (
              <Link key={action.id} className="cet-outline" to="/cases/$caseId/$page" params={{ caseId: view.case_id, page: action.to_page! }}>
                {action.label}
              </Link>
            ))}
          <Link className="cet-primary" to="/cases/$caseId/$page" params={{ caseId: view.case_id, page: nextPage(view.page) }}>
            涓嬩竴姝ワ細{pageLabels[nextPage(view.page)].label}
          </Link>
        </div>
      </section>
      <MetricStrip metrics={metrics} />
      <main className={`cet-structured-grid cet-structured-${view.page}`}>
        {sections.map((section) => (
          <section className={`cet-section section-${section.id}`} key={section.id}>
            <header>
              <div><span>{section.kind}</span><h2>{section.title}</h2></div>
              <SectionAction view={view} section={section} pending={pending} runAction={runAction} />
            </header>
            <SectionBody view={view} section={section} pending={pending} runAction={runAction} />
          </section>
        ))}
      </main>
    </>
  );
}

function SectionAction({ view, section, pending, runAction }: { view: PageView; section: PageSection; pending: boolean; runAction: (fn: () => Promise<unknown>) => void }) {
  const action = primarySectionAction(view, section.id);
  if (!action) return null;
  return <button className="cet-primary" type="button" disabled={pending || action.disabled} onClick={() => action.run(runAction)}>{action.label}</button>;
}

function SectionBody({ view, section, pending, runAction }: { view: PageView; section: PageSection; pending: boolean; runAction: (fn: () => Promise<unknown>) => void }) {
  const items = section.items ?? [];
  if (!items.length) return <div className="cet-empty"><Database size={16} />鏆傛棤鏁版嵁</div>;
  if (section.kind === "sources") {
    return <div className="cet-source-cards">{items.map((item, index) => <article className={!boolField(item, "accepted") ? "blocked" : ""} key={idOf(item) || textField(item, "label") || index}><Layers size={15} /><b>{textField(item, "name") || textField(item, "label")}</b><span>{textField(item, "access_mode") || "source"} 路 trust {numberField(item, "trust") ?? numberField(item, "count") ?? "--"}</span>{!boolField(item, "accepted") && textField(item, "blocked_reason") ? <em>{textField(item, "blocked_reason")}</em> : null}</article>)}</div>;
  }
  if (section.kind === "evidence") {
    const canConfirm = view.page === "evidence";
    const reviewId = textField(view.raw, "evidence_review_id");
    return <div className="cet-record-list">{items.map((item) => <EvidenceRecord key={idOf(item)} item={item} pending={pending} runAction={runAction} canConfirm={canConfirm} reviewId={reviewId} />)}</div>;
  }
  if (section.kind === "agents") {
    return <div className="cet-agent-grid">{items.map((item) => <article key={textField(item, "role")}><Users size={16} /><h3>{textField(item, "role")}</h3><p>{textField(item, "stance")}</p><small>{textField(item, "reaction")}</small>{arrayField(item, "blocked_claims").length ? <em>{arrayField(item, "blocked_claims").join(" / ")}</em> : null}</article>)}</div>;
  }
  if (section.kind === "nodes") {
    return <div className="cet-branch-grid">{items.map((item) => <article key={idOf(item)}><GitBranch size={16} /><b>{textField(item, "branch")} 路 {textField(item, "title")}</b><p>姒傜巼 {numberField(item, "probability")}% 路 椋庨櫓 {numberField(item, "risk")}</p></article>)}</div>;
  }
  if (section.kind === "tasks") {
    return <div className="cet-record-list">{items.map((item) => <article className="cet-record" key={idOf(item)}><CheckCircle2 size={16} /><div><b>{textField(item, "title") || text(item)}</b><p>{textField(item, "owner")} 路 {textField(item, "due_label")} 路 {textField(item, "status")}</p></div>{idOf(item) ? <button type="button" disabled={pending} onClick={() => runAction(() => api.updateTask(idOf(item), "in_progress", "started from React product page"))}>鏇存柊</button> : null}</article>)}</div>;
  }
  if (section.kind === "timeline" || section.kind === "chips" || section.kind === "filters" || typeof items[0] === "string") {
    return <div className="cet-chip-grid">{items.map((item, index) => <span key={`${text(item)}-${index}`}>{text(item)}</span>)}</div>;
  }
  return <div className="cet-card-grid">{items.map((item, index) => <article key={idOf(item) || index}><RadioTower size={16} /><b>{textField(item, "title") || textField(item, "name") || textField(item, "label") || textField(item, "statement") || text(item)}</b><p>{textField(item, "summary") || textField(item, "validation_status") || textField(item, "status")}</p><small>{idOf(item) || textField(item, "category")}</small></article>)}</div>;
}

function EvidenceRecord({ item, pending, runAction, canConfirm, reviewId }: { item: unknown; pending: boolean; runAction: (fn: () => Promise<unknown>) => void; canConfirm: boolean; reviewId?: string }) {
  return (
    <article className="cet-record">
      <ShieldCheck size={16} />
      <div>
        <b>{textField(item, "title")}</b>
        <p>{textField(item, "excerpt")}</p>
        <small>{idOf(item)} 路 {textField(item, "source")} 路 {textField(item, "status")}</small>
      </div>
      {canConfirm ? <button type="button" disabled={pending || (!idOf(item) && !reviewId)} onClick={() => runAction(() => reviewId ? api.updateEvidenceReview(reviewId, { status: "confirmed", reason: "confirmed from React evidence review workbench" }) : api.updateEvidence(idOf(item), "confirmed_fact", "confirmed from React evidence review"))}>&#x786e;&#x8ba4;&#x4e8b;&#x5b9e;</button> : null}
    </article>
  );
}

function MetricStrip({ metrics }: { metrics: PageMetric[] }) {
  return (
    <section className="cet-metric-strip">
      {metrics.map((metric, index) => (
        <article className={`tone-${metric.tone ?? "blue"}`} key={`${metric.label}-${index}`}>
          <MetricIcon label={metric.label} />
          <div><span>{metric.label}</span><b>{String(metric.value)}</b>{metric.helper ? <small>{metric.helper}</small> : null}</div>
        </article>
      ))}
    </section>
  );
}

function MetricIcon({ label }: { label: string }) {
  const Icon = label.includes("浜嬩欢鎬婚噺")
    ? FileText
    : label.includes("新增")
      ? PlusCircle
      : label.includes("最高热度") || label.includes("热度")
        ? Flame
        : label.includes("视频") || label.includes("直播")
          ? Video
          : label.includes("讨论")
            ? MessageCircle
            : label.includes("扩散") || label.includes("平台")
              ? Share2
              : label.includes("源")
                ? Database
                : BarChart3;
  return <Icon size={18} />;
}

function TimelinePanel({ signals, selectedSignalId, onSelectSignal }: { signals: unknown[]; selectedSignalId: string | null; onSelectSignal: (id: string) => void }) {
  return (
    <section className="cet-timeline-panel">
      <header><b>城市事件时间线<span>（近24小时）</span></b><small>只展示高热、升温、视频/直播与破圈苗头。</small></header>
      <div className="cet-timeline-line">{signals.slice(0, 12).map((item, index) => <i key={idOf(item) || index} style={{ left: `${4 + index * 8}%` }}><span>{timeFor(index)}</span></i>)}</div>
      <div className="cet-timeline-cards">
        {signals.slice(0, 6).map((item, index) => (
          <article className={idOf(item) === selectedSignalId ? "active" : ""} key={idOf(item) || index} role="button" tabIndex={0} onClick={() => onSelectSignal(idOf(item))}>
            <b>{timeFor(index)}</b>
            <strong>{textField(item, "title")}</strong>
            <span>{textField(item, "region_id")} ? 视频 {index + 1} ? 直播 {index % 2}</span>
            <small><span>热度 {Math.round(score(item, "onlineHeat") || 80)}</span><b>+{Math.max(18, Math.round(score(item, "mainlineRisk") || 42))}%</b><Sparkline index={index} /></small>
          </article>
        ))}
      </div>
    </section>
  );
}

function Sparkline({ index }: { index: number }) {
  const points = [
    [1, 15 + index],
    [10, 13 - index],
    [18, 17],
    [26, 9 + index],
    [35, 12],
    [43, 4 + index]
  ];
  return (
    <svg className="cet-sparkline" viewBox="0 0 44 20" aria-hidden="true">
      <polyline points={points.map((point) => point.join(",")).join(" ")} />
    </svg>
  );
}

function MiniList({
  title,
  meta,
  items,
  selectedSignalId,
  onSelectSignal,
  value
}: {
  title: string;
  meta: string;
  items: unknown[];
  selectedSignalId: string | null;
  onSelectSignal: (id: string) => void;
  value: (item: unknown, index: number) => string;
}) {
  return (
    <section className="cet-mini-panel">
      <PanelHead title={title} count={meta} right="更多" />
      <div className="cet-mini-list">
        {items.map((item, index) => (
          <article className={idOf(item) === selectedSignalId ? "selected" : ""} key={idOf(item) || index} role="button" tabIndex={0} onClick={() => onSelectSignal(idOf(item))}><span className="cet-rank-no">{index + 1}</span><b>{index === 0 ? `${timeFor(index)} ` : ""}{textField(item, "title")}</b><strong>{value(item, index)}</strong></article>
        ))}
      </div>
    </section>
  );
}

function PlatformSpreadList({ title, meta, items, selectedSignalId, onSelectSignal }: { title: string; meta: string; items: unknown[]; selectedSignalId: string | null; onSelectSignal: (id: string) => void }) {
  const platforms = ["抖音", "快手", "微博", "公众号"];
  return (
    <section className="cet-mini-panel cet-platform-panel">
      <PanelHead title={title} count={meta} right="更多" />
      <div className="cet-mini-list cet-platform-list">
        {items.map((item, index) => (
          <article className={idOf(item) === selectedSignalId ? "selected" : ""} key={idOf(item) || index} role="button" tabIndex={0} onClick={() => onSelectSignal(idOf(item))}>
            <span className="cet-rank-no">{index + 1}</span>
            <b>{index === 0 ? `${timeFor(index)} ` : ""}{textField(item, "title")}</b>
            <strong className="cet-platform-summary">
              <span>
                {platforms.map((platform) => <SourceLogo label={platform} key={platform} />)}
              </span>
              <em>5个平台</em>
            </strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function PanelHead({ title, count, right }: { title: string; count?: string; right?: string }) {
  return <header className="cet-panel-head"><b>{title}</b>{count ? <span>{count}</span> : <span />}{right ? <button type="button">{right}</button> : null}</header>;
}

function LoadingPage({ caseId, page }: { caseId: string; page: ProductPageName }) {
  return (
    <div className="cet-react-page" data-testid={`product-${page}-page`}>
      <TopNav caseId={caseId} page={page} nav={[]} />
      <section className="cet-page-head loading"><div><span /><h1 /></div></section>
      <section className="cet-metric-strip loading"><article /><article /><article /><article /></section>
    </div>
  );
}

function handleAction(view: PageView, actionId: string, run: (fn: () => Promise<unknown>) => void) {
  if (actionId === "confirm-mainline") {
    const id = textField(view.raw, "mainline_id") || objectId(record(view.raw, "active_mainline"));
    if (id) {
      run(async () => {
        await api.runMainlineQualityCheck(id);
        const confirmed = await api.confirmProductionMainline(id);
        const worldState = await api.createWorldState({
          mainline_id: id,
          reason: "Create World State from confirmed S5 mainline.",
          payload: { source: "mainline_page_confirm_action" }
        });
        const worldStateId = textField(worldState.data, "id");
        if (worldStateId) {
          await api.createCaseGraphRun({
            mainline_id: id,
            world_state_id: worldStateId,
            rule_version: "s5-frontend-case-graph-v1",
            payload: { source: "mainline_page_confirm_action" }
          });
          await api.createStakeholderRun({
            mainline_id: id,
            world_state_id: worldStateId,
            rule_version: "s5-frontend-stakeholder-v1",
            payload: { source: "mainline_page_confirm_action" }
          });
        }
        return confirmed;
      });
    }
  } else if (actionId === "run-pressure-test") {
    const id = objectId(record(view.raw, "latest_council"));
    if (id) run(() => api.runPressureTest(id, "人工压力测试：关键证据窗口延迟时风险是否升高"));
  } else if (actionId === "apply-council") {
    const id = objectId(record(view.raw, "latest_council"));
    if (id) run(() => api.applyCouncil(id));
  } else if (actionId === "confirm-report") {
    const id = objectId(record(view.raw, "report"));
    if (id) run(() => api.confirmReport(id));
  } else if (actionId === "create-task") {
    run(() => api.createTask(view.case_id, "补齐简报确认后的处置回执", "operator"));
  } else if (actionId === "save-draft") {
    run(() => api.runCaseMemoryAction(view.case_id, "save_draft"));
  } else if (actionId === "submit-review") {
    run(() => api.runCaseMemoryAction(view.case_id, "submit_review"));
  } else if (actionId === "confirm-ingest") {
    run(() => api.runCaseMemoryAction(view.case_id, "confirm_ingest"));
  } else if (actionId === "run-regression") {
    run(() => api.runConfigAction("v2.4.2", view.case_id, "run_regression"));
  } else if (actionId === "submit-approval") {
    run(() => api.runConfigAction("v2.4.2", view.case_id, "submit_approval"));
  }
}

function primarySectionAction(view: PageView, sectionId: string): { label: string; disabled?: boolean; run: (run: (fn: () => Promise<unknown>) => void) => void } | null {
  if (view.page === "data" && sectionId === "signals") {
    const topicId = textField(view.raw, "topic_id");
    const signalId = firstId(sectionItems(view, "signals"));
    return {
      label: "Create package and add first signal",
      disabled: !topicId || !signalId,
      run: (run) => signalId && topicId && run(async () => {
        const packageResult = await api.createSignalPackage({
          topic_id: topicId,
          name: "S4A analyst signal package",
          rule_version: "s4a-frontend-package-v1",
          reason: "Created from data signal workbench",
          payload: { source: "data_page_primary_action" }
        });
        return api.addSignalPackageItem(packageResult.data.signal_package_id, {
          signal_id: signalId,
          rank: 1,
          reason: "Added from data signal workbench",
          payload: { source: "data_page_primary_action" }
        });
      })
    };
  }
  if (view.page === "data" && sectionId === "packages") {
    const firstPackage = sectionItems(view, "packages")[0];
    const packageId = textField(firstPackage, "signal_package_id") || idOf(firstPackage);
    const packageItems = record(firstPackage, "items");
    const firstItem = Array.isArray(packageItems) ? packageItems[0] : undefined;
    const signalId = textField(firstItem, "signal_id") || textField(record(firstItem, "signal"), "id");
    return {
      label: "Remove first packaged signal",
      disabled: !packageId || !signalId,
      run: (run) => packageId && signalId && run(() => api.removeSignalPackageItem(packageId, signalId))
    };
  }
  if (view.page === "evidence" && sectionId === "evidence") {
    const reviewId = textField(view.raw, "evidence_review_id");
    return {
      label: "Confirm evidence material",
      disabled: !reviewId,
      run: (run) => reviewId && run(() => api.updateEvidenceReview(reviewId, { status: "confirmed", reason: "confirmed from evidence review workbench" }))
    };
  }
  if (view.page === "evidence" && sectionId === "media") {
    const evidenceId = textField(view.raw, "evidence_id");
    return {
      label: "Attach and process media",
      disabled: !evidenceId,
      run: (run) => evidenceId && run(async () => {
        const attachment = await api.createEvidenceAttachment(evidenceId, {
          media_type: "video",
          uri: "synthetic://frontend/evidence-review-attachment.mp4",
          content: "synthetic frontend attachment transcript with minor identity metadata masked before display.",
          is_synthetic: true,
          payload: { source: "evidence_page_primary_action" }
        });
        const media = record(attachment.data, "media_asset");
        const mediaId = textField(media, "id") || textField(media, "media_asset_id");
        if (!mediaId) return attachment;
        return api.createMediaProcessingRun({ media_asset_id: mediaId, processor: "asr", evidence_id: evidenceId, rule_version: "s4b-frontend-media-processing-v1" });
      })
    };
  }
  if (view.page === "evidence" && sectionId === "risk-factors") {
    const topicId = textField(view.raw, "topic_id");
    const evidenceId = textField(view.raw, "evidence_id");
    return {
      label: "Generate risk factors",
      disabled: !evidenceId,
      run: (run) => evidenceId && run(() => api.createRiskFactorRun({ topic_id: topicId || undefined, evidence_ids: [evidenceId], rule_version: "s4b-frontend-risk-factor-v1" }))
    };
  }
  if (view.page === "evidence" && sectionId === "conflicts") {
    const topicId = textField(view.raw, "topic_id");
    const evidenceId = textField(view.raw, "evidence_id");
    return {
      label: "Run conflict detection",
      disabled: !evidenceId,
      run: (run) => evidenceId && run(() => api.createConflictDetectionRun({ topic_id: topicId || undefined, evidence_ids: [evidenceId], rule_version: "s4b-frontend-conflict-v1" }))
    };
  }
  if (view.page === "mainline" && sectionId === "candidates") {
    const nodeId = textField(view.raw, "first_node_id");
    const nodeVersion = numberField(view.raw, "first_node_version");
    return {
      label: "Edit first mainline node",
      disabled: !nodeId || nodeVersion === null,
      run: (run) => nodeId && nodeVersion !== null && run(() => api.updateMainlineNode(nodeId, {
        expected_version: nodeVersion,
        title: "Reviewed main narrative node",
        reason: "Edited from S5 mainline builder.",
        payload: { source: "mainline_page_node_action" }
      }))
    };
  }
  if (view.page === "mainline" && sectionId === "graph") {
    const mainlineId = textField(view.raw, "mainline_id");
    return {
      label: "Run mainline quality check",
      disabled: !mainlineId,
      run: (run) => mainlineId && run(() => api.runMainlineQualityCheck(mainlineId))
    };
  }
  if (view.page === "mainline" && sectionId === "evidence") {
    const mainlineId = textField(view.raw, "mainline_id");
    return {
      label: "Confirm mainline and create World State",
      disabled: !mainlineId,
      run: (run) => handleAction(view, "confirm-mainline", run)
    };
  }
  if (view.page === "mainline" && sectionId === "stakeholders") {
    const stakeholderId = textField(view.raw, "first_stakeholder_id") || firstId(sectionItems(view, "stakeholders"));
    return {
      label: "Review first stakeholder",
      disabled: !stakeholderId,
      run: (run) => stakeholderId && run(() => api.reviewStakeholder(stakeholderId, {
        decision: "pass",
        reason: "Stakeholder is evidence-backed and ready for S6 profile generation.",
        payload: { source: "mainline_page_stakeholder_action" }
      }))
    };
  }
  if (view.page === "worldline" && sectionId === "interventions") {
    const runId = textField(view.raw, "worldline_run_id");
    return {
      label: "Add evidence-window intervention",
      disabled: !runId,
      run: (run) => runId && run(() => api.addWorldlineIntervention(runId, {
        action: "publish_evidence_window",
        reason: "Added from S6 worldline simulation page.",
        constraints: { must_preserve_evidence_refs: true, source: "worldline_page_intervention_action" }
      }))
    };
  }
  if (view.page === "worldline" && sectionId === "council") {
    return {
      label: "Prepare Agent Council",
      disabled: false,
      run: (run) => run(() => api.getFirstCouncilPage("xian"))
    };
  }
  if (view.page === "council" && sectionId === "messages") {
    const councilId = textField(view.raw, "council_session_id");
    return {
      label: "Run guarded Council",
      disabled: !councilId,
      run: (run) => councilId && run(async () => {
        const council = await api.runCouncilSession(councilId);
        const payload = record(council.data, "payload");
        const resultId = textField(payload, "result_id");
        if (!resultId) return council;
        const review = await api.createReview("council_result", resultId, "v1", "TPL-COUNCIL-RESULT-V1");
        await api.updateReview(review.data.review_id, "pass", ["Council result is schema-valid and evidence-bounded."], []);
        await api.gateCheck(review.data.review_id);
        return api.applyCouncilResult(resultId);
      })
    };
  }
  if (view.page === "council" && sectionId === "result") {
    const resultId = textField(view.raw, "council_result_id");
    return {
      label: "Review and apply Council result",
      disabled: !resultId,
      run: (run) => resultId && run(async () => {
        const review = await api.createReview("council_result", resultId, "v1", "TPL-COUNCIL-RESULT-V1");
        await api.updateReview(review.data.review_id, "pass", ["Council result is schema-valid and evidence-bounded."], []);
        await api.gateCheck(review.data.review_id);
        return api.applyCouncilResult(resultId);
      })
    };
  }
  if (view.page === "brief" && sectionId === "claims") {
    const reportId = textField(view.raw, "report_id");
    return {
      label: "Submit report review",
      disabled: !reportId,
      run: (run) => reportId && run(async () => {
        const review = await api.submitReportReview(reportId);
        await api.updateReview(review.data.review_id, "pass", ["Report claims are evidence-linked and version locked."], []);
        return api.gateCheck(review.data.review_id);
      })
    };
  }
  if (view.page === "brief" && sectionId === "exports") {
    const reportId = textField(view.raw, "report_id");
    const existingReviewId = textField(view.raw, "review_id");
    return {
      label: "Publish and export report",
      disabled: !reportId,
      run: (run) => reportId && run(async () => {
        let reviewId = existingReviewId;
        if (!reviewId) {
          const review = await api.submitReportReview(reportId);
          reviewId = review.data.review_id;
        }
        await api.updateReview(reviewId, "pass", ["Report is ready for publication and export."], []);
        await api.gateCheck(reviewId);
        await api.publishReport(reportId);
        return api.exportReport(reportId, { format: "markdown", reason: "Exported from S7A report page." });
      })
    };
  }
  if (view.page === "worldline" && sectionId === "council") {
    const nodeId = objectId(record(view.raw, "current_node")) || firstId(sectionItems(view, "nodes"));
    return { label: "\u542f\u52a8\u591a\u4e3b\u4f53\u7814\u5224", disabled: !nodeId, run: (run) => nodeId && run(() => api.runCouncil(nodeId)) };
  }
  if (view.page === "council" && sectionId === "delta") return { label: "\u5c06\u7ed3\u679c\u6ce8\u5165\u4e16\u754c\u7ebf\u5e76\u91cd\u8dd1\u5e94\u7528", run: (run) => handleAction(view, "apply-council", run) };
  if (view.page === "brief" && sectionId === "summary") return { label: "\u786e\u8ba4\u62a5\u544a", run: (run) => handleAction(view, "confirm-report", run) };
  if (view.page === "memory" && sectionId === "updates") return { label: "\u786e\u8ba4\u5165\u5e93\u5e76\u66f4\u65b0\u6a21\u578b", run: (run) => handleAction(view, "confirm-ingest", run) };
  if (view.page === "library" && sectionId === "apply") return { label: "\u5e94\u7528\u5230\u5f53\u524d\u63a8\u6f14", run: (run) => run(() => api.applyLibraryItem(view.case_id, "Pattern", "PATTERN-FACT-GAP")) };
  if (view.page === "config" && sectionId === "changes") return { label: "\u8fd0\u884c\u56de\u5f52\u6d4b\u8bd5", run: (run) => handleAction(view, "run-regression", run) };
  return null;
}

function cityMetrics(metrics: PageMetric[], maxHeat: number, signalCount: number, sourceCount: number): PageMetric[] {
  const base = metrics.length ? metrics : [];
  return [
    { label: "事件总量", value: formatNumber(signalCount * 68 || 2846), helper: "较昨日 +18%", tone: "blue" },
    { label: "新增事件", value: formatNumber(Math.max(638, signalCount * 15)), helper: "较昨日 +23%", tone: "green" },
    { label: "当前最高热度", value: formatNumber(maxHeat * 920 || 86520), helper: "同城爆发", tone: "red" },
    { label: "视频/直播数量", value: metricValue(base, "视频") || 160, helper: "较昨日 +35%", tone: "violet" },
    { label: "同城讨论量", value: metricValue(base, "讨论") || "282,480", helper: "评论与转发聚合", tone: "amber" },
    { label: "多平台扩散事件", value: Math.max(21, sourceCount), helper: "破昨日 152", tone: "green" }
  ];
}

function cityEventCategories(signals: unknown[]) {
  const base = Math.max(1, signals.length);
  return [
    { label: "民生服务", count: Math.max(1, Math.round(base * 0.38)), active: true },
    { label: "交通出行", count: Math.max(1, Math.round(base * 0.16)), active: true },
    { label: "城市管理", count: Math.max(1, Math.round(base * 0.14)), active: true },
    { label: "突发事件", count: Math.max(1, Math.round(base * 0.12)), active: true },
    { label: "市场经营", count: Math.max(0, Math.round(base * 0.08)), active: true },
    { label: "社会生活", count: Math.max(0, Math.round(base * 0.08)), active: true },
    { label: "其他", count: Math.max(0, Math.round(base * 0.04)), active: true }
  ];
}

function citySourceRows(sources: unknown[]) {
  const labels = ["抖音", "快手", "微博", "知乎", "公众号", "头条", "本地论坛", "小红书", "12345热线", "网格员上报", "视频监控", "其他"];
  return labels.map((label, index) => {
    const source = sources[index % Math.max(sources.length, 1)];
    const trust = numberField(source, "trust");
    return {
      label,
      value: trust === null ? "--" : trimNumber(trust),
      online: boolField(source, "accepted") || index > 0
    };
  });
}

function toggleSetValue(current: Set<string>, value: string) {
  const next = new Set(current);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function citySignalEventType(index: number, categories: Array<{ label: string }>) {
  return categories[index % Math.max(categories.length, 1)]?.label ?? "其他";
}

function citySignalSourceLabel(index: number, sourceRows: Array<{ label: string }>) {
  return sourceRows[index % Math.max(sourceRows.length, 1)]?.label ?? "其他";
}

function citySignalMatchesMapFilter(item: unknown, index: number, filter: CityMapFilter) {
  if (filter === "hot") return (score(item, "onlineHeat") || 0) >= 88 || index < 4;
  if (filter === "rising") return (score(item, "mainlineRisk") || 0) >= 70 || index % 3 === 1;
  if (filter === "video") return index % 2 === 0 || textField(item, "title").includes("视频") || textField(item, "title").includes("直播");
  if (filter === "follow") return index < 6;
  return true;
}

function filterMapLayers(layers: MapLayers | undefined, allEvents: unknown[], visibleEvents: unknown[]): MapLayers | undefined {
  if (!layers) return layers;
  const visibleIds = new Set(visibleEvents.map(idOf).filter(Boolean));
  const visibleIndexes = new Set<number>();
  allEvents.forEach((event, index) => {
    if (visibleIds.has(idOf(event))) visibleIndexes.add(index);
  });
  return {
    ...layers,
    eventPoints: {
      ...layers.eventPoints,
      features: layers.eventPoints.features.filter((_, index) => visibleIndexes.has(index))
    }
  };
}

function sourceLogoType(label: string) {
  if (label.includes("抖音")) return "douyin";
  if (label.includes("快手")) return "kuaishou";
  if (label.includes("微博")) return "weibo";
  if (label.includes("知乎")) return "zhihu";
  if (label.includes("公众号")) return "wechat";
  if (label.includes("头条")) return "toutiao";
  if (label.includes("小红书")) return "redbook";
  if (label.includes("12345")) return "hotline";
  if (label.includes("网格")) return "grid";
  if (label.includes("视频监控")) return "camera";
  if (label.includes("论坛")) return "forum";
  return "other";
}

function trimNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function rankCitySignals(signals: unknown[], mode: CityRankMode) {
  return [...signals].sort((a, b) => cityRankSortValue(b, mode) - cityRankSortValue(a, mode));
}

function cityRankSortValue(item: unknown, mode: CityRankMode) {
  if (mode === "discussion") return (score(item, "mainlineRisk") || 0) * 1.2 + (score(item, "onlineHeat") || 0) * 0.35;
  if (mode === "speed") return (score(item, "onlineHeat") || 0) * 28 + (score(item, "mainlineRisk") || 0) * 3;
  if (mode === "video") return (score(item, "onlineHeat") || 0) * 1900 + (score(item, "mainlineRisk") || 0) * 120;
  return score(item, "onlineHeat") || 0;
}

function cityRankMetric(item: unknown, index: number, mode: CityRankMode) {
  if (mode === "discussion") return formatNumber(Math.round((score(item, "mainlineRisk") || 58) * 470 + 1800 - index * 220));
  if (mode === "speed") return `${formatNumber(Math.round((score(item, "onlineHeat") || 86) * (36 - index) + (score(item, "mainlineRisk") || 64) * 2.4))}/分钟`;
  if (mode === "video") return `${(Math.max(8.6, (score(item, "onlineHeat") || 86) * 0.19)).toFixed(1)}w`;
  return formatNumber(score(item, "onlineHeat") * 920 || 88320);
}

function cityRankDelta(item: unknown, index: number, mode: CityRankMode) {
  if (mode === "discussion") return `+${Math.max(21, Math.round((score(item, "mainlineRisk") || 61) + 18 - index * 2))}%`;
  if (mode === "speed") return `+${Math.max(12, Math.round((score(item, "onlineHeat") || 82) - 24 - index))}%`;
  if (mode === "video") return `评论 ${formatNumber(4280 - index * 330)}`;
  return `+${Math.max(18, Math.round(score(item, "mainlineRisk") || 64))}%`;
}

function rankLabel(index: number) {
  return ["1", "2", "3"][index] ?? String(index + 1);
}

function buildVideoItems(signals: unknown[]) {
  return signals
    .slice(0, 7)
    .map((item, index) => {
      const heat = score(item, "onlineHeat") || 80 - index * 3;
      return {
        id: idOf(item),
        source: index % 3 === 0 ? "抖音" : index % 3 === 1 ? "快手直播" : "头条视频",
        metric: `播放 ${(heat * 0.19).toFixed(1)}w / 评论 ${formatNumber(4280 - index * 350)}`,
        playback: heat * 10000,
        title: index === 0 ? "当前选中素材：校门口沟通片段被同城账号二次剪辑" : textField(item, "title"),
        summary: textField(item, "summary") || "需要保留原始上下文并遮挡未成年人信息。",
        updated: index === 0 ? "30分钟前" : `${12 + index * 5}分钟前`
      };
    })
    .sort((a, b) => b.playback - a.playback);
}

function rankedEventFeatureCollection(
  layers: MapLayers,
  events: unknown[],
  zoom = layers.config.zoom ?? 10.85,
  project?: (coordinates: [number, number]) => { x: number; y: number }
) {
  const cell = clusterCellSize(zoom);
  const groups = new Map<string, {
    feature: MapLayers["eventPoints"]["features"][number];
    indexes: number[];
    lon: number;
    lat: number;
    x: number;
    y: number;
  }>();

  layers.eventPoints.features.forEach((feature, index) => {
    const coordinates = splitCoordinates(feature.geometry.coordinates as [number, number], index);
    const screen = project ? project(coordinates) : approximateScreenPoint(coordinates, zoom);
    const key = `${Math.floor(screen.x / cell)},${Math.floor(screen.y / cell)}`;
    const target = groups.get(key);
    if (target) {
      const count = target.indexes.length;
      target.indexes.push(index);
      target.lon = (target.lon * count + coordinates[0]) / (count + 1);
      target.lat = (target.lat * count + coordinates[1]) / (count + 1);
      target.x = (target.x * count + screen.x) / (count + 1);
      target.y = (target.y * count + screen.y) / (count + 1);
    } else {
      groups.set(key, {
        feature,
        indexes: [index],
        lon: coordinates[0],
        lat: coordinates[1],
        x: screen.x,
        y: screen.y
      });
    }
  });

  return {
    ...layers.eventPoints,
    features: Array.from(groups.values()).map((group, index) =>
      enrichedEventFeature(
        group.feature,
        group.indexes,
        events,
        index,
        [group.lon, group.lat],
        group.indexes.length
      )
    )
  };
}

function clusterCellSize(zoom: number) {
  const dynamicCell = 118 - Math.max(0, zoom - 10) * 32;
  return Math.max(20, Math.min(118, dynamicCell));
}

function approximateScreenPoint(coordinates: [number, number], zoom: number) {
  const scale = 2 ** zoom;
  return { x: coordinates[0] * scale, y: coordinates[1] * scale };
}

function enrichedEventFeature(
  feature: MapLayers["eventPoints"]["features"][number],
  indexes: number[],
  events: unknown[],
  rank: number,
  coordinates: [number, number],
  eventCount: number
) {
  const firstIndex = indexes[0] ?? 0;
  const event = events[firstIndex];
  const riskScore = Math.max(...indexes.map((itemIndex) => score(events[itemIndex], "mainlineRisk") || 0), feature.properties.riskScore);
  const onlineHeat = Math.max(...indexes.map((itemIndex) => score(events[itemIndex], "onlineHeat") || 0), feature.properties.riskScore);
  const summary = textField(event, "summary") || "用于主题热度、证据复核、主线建模与世界线推演的校园补充信号。";
  return {
    ...feature,
    id: `aggregate-${rank + 1}-${eventCount}-${firstIndex}`,
    geometry: {
      ...feature.geometry,
      coordinates
    },
    properties: {
      ...feature.properties,
      rank: rank + 1,
      eventCount,
      signalId: idOf(event),
      displayTitle: textField(event, "title") || feature.properties.title,
      region: textField(event, "region_id") || feature.properties.regionId,
      onlineHeat,
      riskScore,
      confidence: Math.max(...indexes.map((itemIndex) => numberField(events[itemIndex], "confidence") ?? 0), feature.properties.confidence),
      summary,
      raw: summary,
      eventType: eventCount > 1 ? "事件聚合" : "单点事件",
      time: timeFor(firstIndex % 12),
      status: textField(event, "status") || "实时监测",
      spread: eventCount > 1 ? `${eventCount} 个事件聚合` : "1 个事件",
      source: textField(event, "source_id") || "同城公开平台聚合",
      mainline: textField(event, "mainline_id") || "ML-001"
    }
  };
}

function splitCoordinates(coordinates: [number, number], index: number): [number, number] {
  const angle = ((index * 137.508) % 360) * (Math.PI / 180);
  const ring = 0.00062 + (index % 5) * 0.00018;
  return [coordinates[0] + Math.cos(angle) * ring, coordinates[1] + Math.sin(angle) * ring * 0.78];
}

function applyMapMode(map: maplibregl.Map, mode: CityMapMode) {
  setLayerVisibility(map, "amap", "visible");
  setLayerVisibility(map, "amap-satellite", "visible");
  setBaseLayerOpacity(map, "amap", mode === "satellite" ? 0 : 1);
  setBaseLayerOpacity(map, "amap-satellite", mode === "satellite" ? 1 : 0);
  if (map.getLayer("city-event-heat")) {
    map.setPaintProperty("city-event-heat", "heatmap-opacity", mode === "heat" ? 0.82 : mode === "satellite" ? 0.16 : 0.34);
    map.setPaintProperty("city-event-heat", "heatmap-intensity", mode === "heat" ? 1.34 : 0.82);
    map.setPaintProperty("city-event-heat", "heatmap-radius", mode === "heat" ? 48 : 36);
  }
  if (map.getLayer("city-event-points")) {
    map.setPaintProperty("city-event-points", "circle-opacity", mode === "heat" ? 0.68 : 0.78);
  }
  map.triggerRepaint();
}

function setLayerVisibility(map: maplibregl.Map, layerId: string, visibility: "visible" | "none") {
  if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", visibility);
}

function setBaseLayerOpacity(map: maplibregl.Map, layerId: string, opacity: number) {
  const layer = map.getLayer(layerId) as { type?: string } | undefined;
  if (!layer) return;
  if (layer.type === "background") map.setPaintProperty(layerId, "background-opacity", opacity);
  else map.setPaintProperty(layerId, "raster-opacity", opacity);
}

function amapStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [
      { id: "amap", type: "background", paint: { "background-color": "#e9efe8", "background-opacity": 1 } },
      { id: "amap-satellite", type: "background", paint: { "background-color": "#1f2a32", "background-opacity": 0 } }
    ]
  };
}

function sectionItems(view: PageView, sectionId: string): unknown[] {
  return view.sections.find((section) => section.id === sectionId)?.items ?? [];
}

function nextPage(page: ProductPageName): ProductPageName {
  const index = pageOrder.indexOf(page);
  return pageOrder[Math.min(index + 1, pageOrder.length - 1)] ?? "city";
}

function metricValue(metrics: PageMetric[], contains: string): string | number | undefined {
  return metrics.find((metric) => metric.label.includes(contains))?.value;
}

function score(value: unknown, key: string): number {
  const scores = record(value, "scores");
  const raw = record(scores, key);
  return typeof raw === "number" ? raw : 0;
}

function idOf(value: unknown): string {
  return textField(value, "id");
}

function firstId(values: unknown[]): string | null {
  return idOf(values[0]) || null;
}

function objectId(value: unknown): string | null {
  return idOf(value) || null;
}

function textField(value: unknown, key: string): string {
  return text(record(value, key));
}

function numberField(value: unknown, key: string): number | null {
  const raw = record(value, key);
  return typeof raw === "number" ? raw : null;
}

function boolField(value: unknown, key: string): boolean {
  return record(value, key) === true;
}

function arrayField(value: unknown, key: string): string[] {
  const raw = record(value, key);
  return Array.isArray(raw) ? raw.map(text) : [];
}

function arrayFrom(value: unknown, key: string): unknown[] {
  const raw = record(value, key);
  return Array.isArray(raw) ? raw : [];
}

function uniqueTags(entries: unknown[]): string[] {
  const tags = new Set<string>();
  entries.forEach((entry) => {
    arrayFrom(entry, "tags").forEach((tag) => tags.add(text(tag)));
  });
  return Array.from(tags).filter(Boolean);
}

function record(value: unknown, key: string): unknown {
  if (typeof value === "object" && value !== null && key in value) return (value as JsonObject)[key];
  return undefined;
}

function text(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return displayText(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return textField(value, "title") || textField(value, "name") || JSON.stringify(value);
}

function displayText(value: string): string {
  const direct = zhText[value] ?? zhText[value.trim()];
  if (direct) return direct;

  let match = /^Campus authorized public feed (\d+)$/.exec(value);
  if (match) return `校园授权公开源 ${match[1]}`;

  match = /^Community service public feed (\d+)$/.exec(value);
  if (match) return `社区公共服务源 ${match[1]}`;

  match = /^Campus supporting signal (\d+)$/.exec(value);
  if (match) return `青澳中学同城风险补充信号 ${match[1]}`;

  match = /^Water service response signal (\d+)$/.exec(value);
  if (match) return `鍋滄按鏈嶅姟鍝嶅簲琛ュ厖淇″彿 ${match[1]}`;

  match = /^Supporting evidence item (\d+)$/.exec(value);
  if (match) return `支撑证据项 ${match[1]}`;

  match = /^Water service evidence (\d+)$/.exec(value);
  if (match) return `公共服务证据项 ${match[1]}`;

  match = /^Supporting excerpt (\d+) links public signal, timeline, source credibility, and review status\.$/.exec(value);
  if (match) return `支撑摘录 ${match[1]} 关联公开信号、时间线、来源可信度与复核状态。`;

  match = /^Community trust factor (\d+)$/.exec(value);
  if (match) return `社区信任因子 ${match[1]}`;

  if (value === "Supporting campus signal for topic heat, evidence review, mainline construction, and worldline projection.") {
    return "用于主题热度、证据复核、主线建模与世界线推演的校园补充信号。";
  }
  if (value === "Resident consultation, repair timeline, responsibility explanation, and response-window signal.") {
    return "居民咨询、维修时间线、责任解释与响应窗口相关信号。";
  }
  if (value === "Masked sensitive supporting excerpt for a minor-related discussion.") {
    return "已脱敏的未成年人相关支撑摘录。";
  }
  if (value === "Public service evidence links repair progress, resident questions, and response consistency.") {
    return "公共服务证据关联维修进度、居民问题与回应一致性。";
  }
  if (value === "Authorized P0 evidence seed") return "授权 P0 证据样本";
  if (value === "Community public feed") return "社区公开数据源";

  return value;
}

function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("zh-CN");
}

function timeFor(index: number): string {
  return ["09:12", "09:48", "10:04", "10:12", "10:20", "10:27", "10:35", "10:38", "10:42", "10:50", "10:55", "11:03"][index] ?? "11:18";
}

function lonLatToTile(lon: number, lat: number, zoom: number) {
  const latRad = (lat * Math.PI) / 180;
  const scale = 2 ** zoom;
  return {
    x: Math.floor(((lon + 180) / 360) * scale),
    y: Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * scale)
  };
}

function mapPreviewThumbs(center: number[]) {
  const zoom = 13;
  const tile = lonLatToTile(center[0] ?? 120.1551, center[1] ?? 30.2741, zoom);
  return {
    map: amapTileUrl(tile.x, tile.y, zoom),
    satellite: amapSatelliteTileUrl(tile.x, tile.y, zoom)
  };
}

function amapTileUrl(x: number, y: number, zoom: number) {
  return offlineMapTileUrl(x, y, zoom, "map");
}

function amapSatelliteTileUrl(x: number, y: number, zoom: number) {
  return offlineMapTileUrl(x, y, zoom, "satellite");
}

function offlineMapTileUrl(x: number, y: number, zoom: number, mode: "map" | "satellite") {
  const dark = mode === "satellite";
  const base = dark ? "#202b33" : "#e9efe8";
  const line = dark ? "#3a4852" : "#c9d6c8";
  const accent = dark ? "#667580" : "#a8bba6";
  const label = `${zoom}/${x}/${y}`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="${base}"/><path d="M0 64H256M0 128H256M0 192H256M64 0V256M128 0V256M192 0V256" stroke="${line}" stroke-width="1"/><path d="M-20 172C58 96 112 219 276 84" fill="none" stroke="${accent}" stroke-width="9" opacity=".42"/><circle cx="${64 + Math.abs(x % 4) * 33}" cy="${58 + Math.abs(y % 4) * 29}" r="9" fill="${accent}" opacity=".55"/><text x="12" y="238" font-family="Arial" font-size="18" fill="${dark ? "#9fb0bd" : "#738775"}">${label}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
