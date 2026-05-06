(function () {
  const page = location.pathname.split("/").pop() || "risk-dashboard.html";
  const params = new URLSearchParams(location.search);
  const flow = {
    caseId: "CASE-CAMPUS-001",
    caseSlug: "campus-death-high-intensity",
    regionId: params.get("regionId") || "campus-core",
    signalId: params.get("signalId") || "SIG-001",
    mainlineId: "ML-001",
    worldStateId: "WS-001",
    nodeId: params.get("nodeId") || "NODE-C3",
    councilId: "COUNCIL-001",
    reportId: "REPORT-001"
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const api = window.MockAPI;
  const state = api?.state;
  const golden = {
    dashboard: `risk-dashboard.html?caseId=${flow.caseSlug}`,
    data: `data-hub.html?caseId=${flow.caseSlug}&regionId=${flow.regionId}&mainlineId=${flow.mainlineId}&signalId=${flow.signalId}`,
    mainline: `mainline-builder.html?caseId=${flow.caseSlug}&mainlineId=${flow.mainlineId}&signalId=${flow.signalId}`,
    worldline: `worldline-observer.html?caseId=${flow.caseSlug}&mainlineId=${flow.mainlineId}&worldStateId=${flow.worldStateId}&nodeId=${flow.nodeId}`,
    council: `agent-council.html?caseId=${flow.caseSlug}&mainlineId=${flow.mainlineId}&nodeId=${flow.nodeId}&councilId=${flow.councilId}`,
    report: `decision-brief.html?caseId=${flow.caseSlug}&reportId=${flow.reportId}&mainlineId=${flow.mainlineId}`
  };

  function toast(message) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => el.classList.remove("show"), 1800);
  }

  function mergeState(patch) {
    if (state) return state.write(patch);
    try {
      const key = "worldline-observer-demo-state";
      const current = JSON.parse(localStorage.getItem(key) || "{}");
      const next = { ...current, ...patch, updatedAt: new Date().toISOString() };
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    } catch (error) {
      return patch;
    }
  }

  function updateHref(selector, href) {
    $$(selector).forEach(el => { el.href = href; });
  }

  function markDefaults() {
    mergeState({
      caseId: flow.caseId,
      regionId: flow.regionId,
      signalId: flow.signalId,
      mainlineId: flow.mainlineId,
      worldStateId: flow.worldStateId,
      selectedNodeId: flow.nodeId,
      councilId: flow.councilId,
      reportId: flow.reportId
    });
  }

  function bindRiskDashboard() {
    updateHref('nav a[href="data-hub.html"]', golden.data);
    updateHref('nav a[href="mainline-builder.html"]', golden.mainline);
    updateHref('nav a[href="worldline-observer.html"]', golden.worldline);
    updateHref('nav a[href="agent-council.html"]', golden.council);
    updateHref('nav a[href="decision-brief.html"]', golden.report);
    $$(".mainline .primary-mini").forEach(link => {
      link.textContent = "进入数据";
      link.href = golden.data;
      link.addEventListener("click", () => mergeState({ regionId: flow.regionId, mainlineId: flow.mainlineId, signalId: flow.signalId }));
    });
    $$(".mainline a").forEach(link => {
      if (/data-hub\.html/.test(link.getAttribute("href") || "") && /(hormuz-blockade|campus-safety)/.test(link.href)) link.href = golden.data;
    });
    $$(".weak-card").forEach(card => {
      card.addEventListener("click", () => mergeState({ signalId: card.dataset.weak || flow.signalId, mainlineId: flow.mainlineId }));
    });
    $$('.review-row a[href="#"]').forEach((link, index) => {
      link.href = `event-detail-evidence.html?signalId=${index ? "SIG-017" : "SIG-012"}&mainlineId=${flow.mainlineId}`;
    });
  }

  function bindDataHub() {
    updateHref('a[href="mainline-builder.html"]', golden.mainline);
    const addDraft = $("#addDraft");
    if (addDraft) {
      addDraft.addEventListener("click", () => {
        mergeState({ selectedSignalIds: ["SIG-001", "SIG-012", "SIG-017"], signalId: flow.signalId, mainlineDraftStatus: "ready" });
        toast("SIG-001/SIG-012/SIG-017 已进入校园高烈度事件主线草稿包");
      });
    }
    $$(".signal-row").forEach(row => row.addEventListener("click", () => mergeState({ signalId: row.dataset.id || flow.signalId })));
  }

  function bindMainline() {
    updateHref('a[href^="worldline-observer.html"]', golden.worldline);
    const enter = $("#enterWorldline");
    if (enter) {
      enter.href = golden.worldline;
      enter.addEventListener("click", () => mergeState({ mainlineStatus: "confirmed", worldStateId: flow.worldStateId }));
    }
    const withGaps = $("#withGaps");
    if (withGaps) {
      withGaps.addEventListener("click", () => {
        mergeState({ mainlineStatus: "confirmed_with_gaps", worldStateId: flow.worldStateId });
        window.setTimeout(() => { location.href = golden.worldline; }, 650);
      });
    }
  }

  function bindWorldline() {
    updateHref('a[href="agent-council.html"]', golden.council);
    updateHref('a[href="decision-brief.html"]', golden.report);
    const learn = $("#learnCouncil");
    if (learn) learn.href = golden.council;
    const run = $("#runCouncil");
    if (run) {
      run.addEventListener("click", () => {
        api?.runCouncil?.(flow.nodeId, ($("#councilQuestion") || $("#sideCouncilQuestion"))?.value);
        mergeState({ councilStatus: "completed", selectedNodeId: flow.nodeId });
      });
    }
  }

  function bindCouncil() {
    updateHref('a[href="worldline-observer.html"]', golden.worldline);
    updateHref('a[href="decision-brief.html"]', golden.report);
    const inject = $("#injectBtn");
    if (inject) {
      inject.addEventListener("click", () => {
        api?.injectCouncilResult?.(flow.councilId);
        mergeState({ councilStatus: "injected", selectedNodeId: flow.nodeId, branchC: 58 });
        window.setTimeout(() => { location.href = `${golden.worldline}&councilId=${flow.councilId}&injected=1`; }, 700);
      });
    }
  }

  function bindReport() {
    updateHref('a[href="worldline-observer.html"]', `${golden.worldline}&councilId=${flow.councilId}&injected=1`);
    updateHref('a[href="risk-dashboard.html"]', golden.dashboard);
    const complete = $("#completeBtn");
    if (complete) {
      complete.addEventListener("click", () => mergeState({ reportStatus: "completed", actionTracking: "started" }));
    }
  }

  function run() {
    markDefaults();
    if (page === "risk-dashboard.html") bindRiskDashboard();
    if (page === "data-hub.html") bindDataHub();
    if (page === "mainline-builder.html") bindMainline();
    if (page === "worldline-observer.html") bindWorldline();
    if (page === "agent-council.html") bindCouncil();
    if (page === "decision-brief.html") bindReport();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
