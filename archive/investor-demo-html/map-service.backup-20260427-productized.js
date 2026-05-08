(function () {
  const toneColors = {
    red: "#df4b54",
    amber: "#d78925",
    blue: "#2f6df6",
    green: "#18a873",
    violet: "#7f63c9"
  };

  const groupedLayers = {
    risk: ["risk-areas-fill", "risk-areas-outline", "risk-areas-label"],
    events: ["event-points", "event-points-halo", "event-labels"],
    routes: ["shipping-routes", "shipping-routes-casing", "route-labels"],
    impact: ["impact-points", "impact-halo", "impact-labels"]
  };

  function toneExpression(alpha = 1) {
    return [
      "match",
      ["get", "tone"],
      "red", alpha === 1 ? toneColors.red : `rgba(223, 75, 84, ${alpha})`,
      "amber", alpha === 1 ? toneColors.amber : `rgba(215, 137, 37, ${alpha})`,
      "green", alpha === 1 ? toneColors.green : `rgba(24, 168, 115, ${alpha})`,
      "violet", alpha === 1 ? toneColors.violet : `rgba(127, 99, 201, ${alpha})`,
      alpha === 1 ? toneColors.blue : `rgba(47, 109, 246, ${alpha})`
    ];
  }

  function popupHtml(properties) {
    const score = properties.riskScore ? `<span>风险 ${properties.riskScore}</span>` : "";
    const signals = properties.signalCount ? `<span>信号 ${properties.signalCount}</span>` : "";
    const status = properties.status ? `<span>${properties.status}</span>` : "";
    const route = properties.relatedRoute ? `<span>${properties.relatedRoute}</span>` : "";
    const meta = [score, signals, status, route].filter(Boolean).join("");
    return `
      <div class="map-popup-card">
        <b>${properties.title || "地图要素"}</b>
        <p>${properties.summary || "暂无摘要。"}</p>
        <div class="map-popup-meta">${meta}</div>
        <a href="data-hub.html?regionId=${encodeURIComponent(properties.regionId || "")}&mainlineId=${encodeURIComponent(properties.mainlineId || "")}">查看详情</a>
      </div>
    `;
  }

  function initRiskMap(options) {
    const { container, layers, onFeatureClick, onReady, onError } = options;
    const el = typeof container === "string" ? document.getElementById(container) : container;
    if (!el) throw new Error("Map container not found");
    if (!window.maplibregl) {
      const err = new Error("MapLibre GL JS is not loaded");
      onError?.(err);
      throw err;
    }

    const config = layers.config || {};
    const map = new maplibregl.Map({
      container: el,
      center: config.center || [47.8, 27.6],
      zoom: config.zoom || 4.1,
      minZoom: config.minZoom || 3,
      maxZoom: config.maxZoom || 8,
      maxBounds: config.maxBounds,
      attributionControl: true,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: config.attribution || "© OpenStreetMap contributors"
          }
        },
        layers: [
          { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.92, "raster-saturation": -0.26 } }
        ]
      }
    });

    map.on("error", event => {
      onError?.(event?.error || new Error("Map tile/style error"));
    });

    function addSourcesAndLayers() {
      map.addSource("risk-areas", { type: "geojson", data: layers.riskAreas });
      map.addSource("event-points", { type: "geojson", data: layers.eventPoints });
      map.addSource("shipping-routes", { type: "geojson", data: layers.shippingRoutes });
      map.addSource("impact-areas", { type: "geojson", data: layers.impactAreas });

      map.addLayer({
        id: "risk-areas-fill",
        type: "fill",
        source: "risk-areas",
        paint: { "fill-color": toneExpression(0.18), "fill-outline-color": toneExpression(), "fill-opacity": 0.78 }
      });
      map.addLayer({
        id: "risk-areas-outline",
        type: "line",
        source: "risk-areas",
        paint: { "line-color": toneExpression(), "line-width": 1.8, "line-opacity": 0.78 }
      });
      map.addLayer({
        id: "shipping-routes-casing",
        type: "line",
        source: "shipping-routes",
        paint: { "line-color": "rgba(12, 18, 25, .58)", "line-width": 6, "line-opacity": 0.7 }
      });
      map.addLayer({
        id: "shipping-routes",
        type: "line",
        source: "shipping-routes",
        paint: { "line-color": toneExpression(), "line-width": 3, "line-dasharray": [1.2, 1.1], "line-opacity": 0.92 }
      });
      map.addLayer({
        id: "impact-halo",
        type: "circle",
        source: "impact-areas",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 22, 6, 68],
          "circle-color": toneExpression(0.12),
          "circle-stroke-color": toneExpression(0.34),
          "circle-stroke-width": 1
        }
      });
      map.addLayer({
        id: "impact-points",
        type: "circle",
        source: "impact-areas",
        paint: { "circle-radius": 7, "circle-color": toneExpression(), "circle-stroke-color": "#fffdf7", "circle-stroke-width": 1.4 }
      });
      map.addLayer({
        id: "event-points-halo",
        type: "circle",
        source: "event-points",
        paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8, 6, 16], "circle-color": toneExpression(0.16) }
      });
      map.addLayer({
        id: "event-points",
        type: "circle",
        source: "event-points",
        paint: { "circle-radius": 5.8, "circle-color": toneExpression(), "circle-stroke-color": "#fffdf7", "circle-stroke-width": 1.6 }
      });
      map.addLayer({
        id: "risk-areas-label",
        type: "symbol",
        source: "risk-areas",
        layout: { "text-field": ["get", "title"], "text-size": 11, "text-variable-anchor": ["top", "bottom", "left", "right"], "text-radial-offset": 0.65 },
        paint: { "text-color": "#111820", "text-halo-color": "rgba(255,253,247,.88)", "text-halo-width": 1.2 }
      });
      map.addLayer({
        id: "event-labels",
        type: "symbol",
        source: "event-points",
        minzoom: 4.6,
        layout: { "text-field": ["get", "title"], "text-size": 10, "text-offset": [0.8, -0.7], "text-anchor": "left" },
        paint: { "text-color": "#111820", "text-halo-color": "rgba(255,253,247,.92)", "text-halo-width": 1.2 }
      });
      map.addLayer({
        id: "route-labels",
        type: "symbol",
        source: "shipping-routes",
        minzoom: 4.4,
        layout: { "symbol-placement": "line", "text-field": ["get", "title"], "text-size": 10 },
        paint: { "text-color": "#111820", "text-halo-color": "rgba(255,253,247,.92)", "text-halo-width": 1.2 }
      });
      map.addLayer({
        id: "impact-labels",
        type: "symbol",
        source: "impact-areas",
        minzoom: 4.8,
        layout: { "text-field": ["get", "title"], "text-size": 10, "text-offset": [0.6, 0.7], "text-anchor": "top-left" },
        paint: { "text-color": "#111820", "text-halo-color": "rgba(255,253,247,.92)", "text-halo-width": 1.2 }
      });

      ["risk-areas-fill", "event-points", "shipping-routes", "impact-points"].forEach(layerId => {
        map.on("mouseenter", layerId, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layerId, () => { map.getCanvas().style.cursor = ""; });
        map.on("click", layerId, event => {
          const feature = event.features?.[0];
          if (!feature) return;
          const props = feature.properties || {};
          new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "270px" })
            .setLngLat(event.lngLat)
            .setHTML(popupHtml(props))
            .addTo(map);
          onFeatureClick?.({ feature, properties: props, lngLat: event.lngLat });
        });
      });

      onReady?.(map);
    }

    map.on("load", addSourcesAndLayers);

    return {
      map,
      setLayerVisibility(group, visible) {
        (groupedLayers[group] || []).forEach(layerId => {
          if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
        });
      },
      zoomIn() {
        map.zoomTo(Math.min(map.getZoom() + 0.75, map.getMaxZoom()), { duration: 260 });
      },
      zoomOut() {
        map.zoomTo(Math.max(map.getZoom() - 0.75, map.getMinZoom()), { duration: 260 });
      },
      flyToFeature(feature) {
        const geometry = feature?.geometry;
        if (!geometry) return;
        if (geometry.type === "Point") {
          map.flyTo({ center: geometry.coordinates, zoom: Math.max(map.getZoom(), 5.4), duration: 420 });
        }
      }
    };
  }

  window.WorldlineMap = { initRiskMap };
})();
