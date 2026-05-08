(function () {
  const cache = new Map();
  const basePath = "mock/fixtures/";

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
      ...(layers.shippingRoutes?.features || []),
      ...(layers.impactAreas?.features || [])
    ];
  }

  window.MockAPI = {
    async getMapConfig(caseId = "iran-war-escalation") {
      const layers = await readJson("map-layers.json");
      return { caseId, ...layers.config };
    },

    async getMapLayers(caseId = "iran-war-escalation") {
      const layers = await readJson("map-layers.json");
      return { caseId, ...layers };
    },

    async getMapFeatureDetail(featureId) {
      const layers = await readJson("map-layers.json");
      const feature = flattenFeatures(layers).find(item => item.properties?.featureId === featureId || item.id === featureId);
      if (!feature) return null;
      return {
        id: feature.properties.featureId || feature.id,
        regionId: feature.properties.regionId,
        featureType: feature.properties.featureType,
        title: feature.properties.title,
        summary: feature.properties.summary,
        mainlineId: feature.properties.mainlineId,
        riskScore: feature.properties.riskScore,
        signalCount: feature.properties.signalCount,
        eventCount: feature.properties.eventCount,
        source: feature.properties.source,
        time: feature.properties.time,
        relatedRoute: feature.properties.relatedRoute,
        status: feature.properties.status,
        insurance: feature.properties.insurance,
        rerouteCost: feature.properties.rerouteCost,
        coordinates: feature.geometry?.coordinates
      };
    },

    async filterMainlinesByGeoFeature(featureId) {
      const detail = await this.getMapFeatureDetail(featureId);
      return {
        featureId,
        regionId: detail?.regionId || null,
        mainlineId: detail?.mainlineId || null,
        label: detail?.title || "地图空间要素"
      };
    }
  };
})();
