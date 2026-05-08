(function () {
  const cache = new Map();
  const basePath = "mock/fixtures/";
  const stateKey = "worldline-observer-demo-state";

  async function readJson(name) {
    if (cache.has(name)) return cache.get(name);
    const response = await fetch(basePath + name, { cache: "no-store" });
    if (!response.ok) throw new Error(`Mock fixture ${name} failed: ${response.status}`);
    const data = await response.json();
    cache.set(name, data);
    return data;
  }

  function flattenFeatures(layers) {
    return [
      ...(layers.riskAreas?.features || []),
      ...(layers.eventPoints?.features || []),
      ...(layers.spreadRoutes?.features || []),
      ...(layers.impactAreas?.features || [])
    ];
  }

  function delay(value, ms = 120) {
    return new Promise(resolve => window.setTimeout(() => resolve(value), ms));
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  async function readDemo() {
    return readJson("demo-data.json");
  }

  function readState() {
    try {
      return JSON.parse(localStorage.getItem(stateKey) || "{}");
    } catch (error) {
      return {};
    }
  }

  function writeState(patch) {
    const next = { ...readState(), ...patch, updatedAt: new Date().toISOString() };
    localStorage.setItem(stateKey, JSON.stringify(next));
    return next;
  }

  function normalizeMainlineId(id) {
    return ["campus-safety", "campus-trust-mainline", "ML-CAMPUS-001", "", null, undefined].includes(id) ? "ML-001" : id;
  }

  function paginate(list, page = 1, pageSize = 8) {
    const start = (Number(page) - 1) * Number(pageSize);
    return {
      items: list.slice(start, start + Number(pageSize)),
      page: Number(page),
      pageSize: Number(pageSize),
      total: list.length
    };
  }

  window.MockAPI = {
    state: { read: readState, write: writeState, key: stateKey },
    normalizeMainlineId,

    async getCase(caseId = "CASE-CAMPUS-001") {
      const demo = await readDemo();
      return delay(clone({ ...demo.case, requestedId: caseId }));
    },

    async getDashboard(caseId = "CASE-CAMPUS-001") {
      const demo = await readDemo();
      return delay(clone({ caseId, ...demo.dashboard, case: demo.case }));
    },

    async searchSignals(params = {}) {
      const demo = await readDemo();
      const query = (params.query || "").toLowerCase();
      const regionId = params.regionId;
      const mainlineId = normalizeMainlineId(params.mainlineId);
      let rows = demo.signals;
      if (mainlineId) rows = rows.filter(item => normalizeMainlineId(item.mainlineId) === mainlineId);
      if (regionId) rows = rows.filter(item => item.regionId === regionId);
      if (query) {
        rows = rows.filter(item => [item.title, item.summary, item.source, ...(item.tags || [])].join(" ").toLowerCase().includes(query));
      }
      return delay(paginate(clone(rows), params.page || 1, params.pageSize || 8));
    },

    async getSignalDetail(signalId = "SIG-001") {
      const demo = await readDemo();
      const signal = demo.signals.find(item => item.id === signalId) || demo.signals[0];
      return delay(clone(signal));
    },

    async getRecommendations(signalId = "SIG-001") {
      const demo = await readDemo();
      const signal = demo.signals.find(item => item.id === signalId) || demo.signals[0];
      const related = demo.signals.filter(item => item.id !== signal.id && item.regionId === signal.regionId);
      return delay(clone({
        signalId: signal.id,
        buckets: [
          { label: "同区域同时间", count: related.length, items: related.map(item => item.id) },
          { label: "可能属于同一主线", count: demo.signals.filter(item => normalizeMainlineId(item.mainlineId) === "ML-001").length, items: ["SIG-001", "SIG-012", "SIG-017"] },
          { label: "历史相似前兆", count: 3, items: ["campus-bullying-gathering", "minor-privacy-leak", "vague-response-escalation"] }
        ]
      }));
    },

    async getMainline(mainlineId = "ML-001") {
      const demo = await readDemo();
      const id = normalizeMainlineId(mainlineId);
      const mainline = demo.mainlines.find(item => item.id === id) || demo.mainlines[0];
      return delay(clone(mainline));
    },

    async confirmMainline(mainlineId = "ML-001", options = {}) {
      const demo = await readDemo();
      const mainline = demo.mainlines.find(item => item.id === normalizeMainlineId(mainlineId)) || demo.mainlines[0];
      const worldState = demo.worldStates.find(item => item.mainlineId === mainline.id) || demo.worldStates[0];
      const state = writeState({
        caseId: demo.case.id,
        mainlineId: mainline.id,
        worldStateId: worldState.id,
        mainlineStatus: options.withGaps ? "confirmed_with_gaps" : "confirmed",
        selectedSignalIds: mainline.signals
      });
      return delay(clone({ mainline, worldState, state }));
    },

    async getWorldline(mainlineId = "ML-001") {
      const demo = await readDemo();
      return delay(clone({
        mainlineId: normalizeMainlineId(mainlineId),
        worldState: demo.worldStates[0],
        nodes: demo.worldlineNodes,
        selectedNodeId: "NODE-C3"
      }));
    },

    async runCouncil(nodeId = "NODE-C3", hypothesis) {
      const demo = await readDemo();
      const result = { ...demo.councilResults[0], nodeId, hypothesis: hypothesis || demo.councilResults[0].hypothesis };
      const state = writeState({ councilId: result.id, selectedNodeId: nodeId, councilStatus: "completed", lastCouncilResult: result });
      return delay(clone({ result, agents: demo.agents, state }), 180);
    },

    async injectCouncilResult(councilId = "COUNCIL-001") {
      const demo = await readDemo();
      const result = demo.councilResults.find(item => item.id === councilId) || demo.councilResults[0];
      const state = writeState({
        councilId: result.id,
        councilStatus: "injected",
        selectedNodeId: result.nodeId,
        branchC: result.branchChanges?.[0]?.to || 58,
        reportId: demo.case.reportId
      });
      return delay(clone({ result, state }));
    },

    async getReport(reportId = "REPORT-001") {
      const demo = await readDemo();
      const report = demo.reports.find(item => item.id === reportId) || demo.reports[0];
      return delay(clone({ report, tasks: demo.tasks, councilResult: demo.councilResults[0] }));
    },

    async updateTask(taskId, status = "in_progress") {
      const state = readState();
      const tasks = { ...(state.tasks || {}), [taskId]: status };
      return delay(clone(writeState({ tasks })));
    },

    async getMapConfig(caseId = "campus-death-high-intensity") {
      const layers = await readJson("map-layers.json");
      return { caseId, ...layers.config };
    },

    async getMapLayers(caseId = "campus-death-high-intensity") {
      const layers = await readJson("map-layers.json");
      return { caseId, ...layers };
    },

    async getMapFeatureDetail(featureId) {
      const layers = await readJson("map-layers.json");
      const feature = flattenFeatures(layers).find(item => item.properties?.featureId === featureId || item.id === featureId);
      if (!feature) return null;
      const mainlineId = normalizeMainlineId(feature.properties.mainlineId);
      return {
        id: feature.properties.featureId || feature.id,
        regionId: feature.properties.regionId,
        featureType: feature.properties.featureType,
        title: feature.properties.title,
        summary: feature.properties.summary,
        mainlineId,
        riskScore: feature.properties.riskScore,
        signalCount: feature.properties.signalCount,
        eventCount: feature.properties.eventCount,
        source: feature.properties.source,
        time: feature.properties.time,
        relatedRoute: feature.properties.relatedRoute,
        status: feature.properties.status,
        sentiment: feature.properties.sentiment,
        spreadDensity: feature.properties.spreadDensity,
        breakoutProbability: feature.properties.breakoutProbability,
        responseGap: feature.properties.responseGap,
        confidence: feature.properties.confidence,
        coordinates: feature.geometry?.coordinates
      };
    },

    async filterMainlinesByGeoFeature(featureId) {
      const detail = await this.getMapFeatureDetail(featureId);
      return {
        featureId,
        regionId: detail?.regionId || null,
        mainlineId: normalizeMainlineId(detail?.mainlineId),
        label: detail?.title || "地图空间要素"
      };
    }
  };
})();
