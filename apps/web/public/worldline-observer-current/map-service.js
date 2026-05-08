(function () {
  const toneColors = {
    red: "#d84d4d",
    amber: "#d68a24",
    blue: "#2f6df6",
    green: "#1d9f72",
    violet: "#7b61c9"
  };

  const groupedLayers = {
    risk: ["risk-hotspot-pulse", "risk-hotspot-core", "risk-areas-label"],
    events: ["event-points", "event-points-halo", "event-labels"],
    routes: ["spread-routes", "spread-routes-casing", "route-labels"],
    impact: ["impact-points", "impact-halo", "impact-labels"]
  };

  function toneExpression(alpha = 1) {
    return [
      "match",
      ["get", "tone"],
      "red", alpha === 1 ? toneColors.red : `rgba(216, 77, 77, ${alpha})`,
      "amber", alpha === 1 ? toneColors.amber : `rgba(214, 138, 36, ${alpha})`,
      "green", alpha === 1 ? toneColors.green : `rgba(29, 159, 114, ${alpha})`,
      "violet", alpha === 1 ? toneColors.violet : `rgba(123, 97, 201, ${alpha})`,
      alpha === 1 ? toneColors.blue : `rgba(47, 109, 246, ${alpha})`
    ];
  }

  function popupHtml(properties) {
    const mainlineId = window.MockAPI?.normalizeMainlineId?.(properties.mainlineId) || properties.mainlineId || "";
    const score = properties.riskScore ? `<span>风险 ${properties.riskScore}</span>` : "";
    const signals = properties.signalCount ? `<span>信号 ${properties.signalCount}</span>` : "";
    const status = properties.status ? `<span>${properties.status}</span>` : "";
    const route = properties.relatedRoute ? `<span>${properties.relatedRoute}</span>` : "";
    const sentiment = properties.sentiment ? `<span>情绪 ${properties.sentiment}</span>` : "";
    const density = properties.spreadDensity ? `<span>扩散 ${properties.spreadDensity}</span>` : "";
    const breakout = properties.breakoutProbability ? `<span>破圈 ${properties.breakoutProbability}</span>` : "";
    const confidence = properties.confidence ? `<span>置信 ${properties.confidence}</span>` : "";
    const meta = [score, signals, status, route, sentiment, density, breakout, confidence].filter(Boolean).join("");
    const responseGap = properties.responseGap ? `<p><b>回应缺口：</b>${properties.responseGap}</p>` : "";
    return `
      <div class="map-popup-card">
        <b>${properties.title || "地图要素"}</b>
        <p>${properties.summary || "暂无摘要。"}</p>
        ${responseGap}
        <div class="map-popup-meta">${meta}</div>
        <a href="risk-dashboard.html?caseId=campus-death-high-intensity&regionId=${encodeURIComponent(properties.regionId || "")}&mainlineId=${encodeURIComponent(mainlineId)}&signalId=SIG-001&featureId=${encodeURIComponent(properties.featureId || "")}">进入主题态势</a>
      </div>
    `;
  }

  function addSourceIfMissing(map, id, data) {
    if (!map.getSource(id)) map.addSource(id, { type: "geojson", data });
  }

  function ensureMapLabelStyles() {
    if (document.getElementById("worldline-map-label-styles")) return;
    const style = document.createElement("style");
    style.id = "worldline-map-label-styles";
    style.textContent = `
      .cn-map-label {
        padding: 2px 7px;
        border-radius: 999px;
        background: rgba(255, 253, 247, .9);
        border: 1px solid rgba(17, 24, 39, .16);
        color: #111827;
        font: 700 12px/1.35 "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
        white-space: nowrap;
        box-shadow: 0 4px 14px rgba(17, 24, 39, .10);
        pointer-events: none;
      }
      .cn-map-label.risk {
        background: rgba(255, 247, 232, .95);
        border-color: rgba(216, 77, 77, .24);
      }
      .cn-map-label.place {
        opacity: .92;
        font-weight: 600;
      }
    `;
    document.head.appendChild(style);
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
    const htmlLabelGroups = { risk: [], places: [] };
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
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: config.attribution || "© OpenStreetMap contributors"
          }
        },
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
            paint: {
              "raster-opacity": 0.9,
              "raster-saturation": -0.28,
              "raster-contrast": -0.08
            }
          }
        ]
      }
    });

    map.on("error", event => onError?.(event?.error || new Error("Map tile/style error")));

    function addSourcesAndLayers() {
      ensureMapLabelStyles();
      addSourceIfMissing(map, "risk-areas", layers.riskAreas);
      addSourceIfMissing(map, "event-points", layers.eventPoints);
    addSourceIfMissing(map, "spread-routes", layers.spreadRoutes);
      addSourceIfMissing(map, "impact-areas", layers.impactAreas);
      if (layers.placeLabels) addSourceIfMissing(map, "place-labels", layers.placeLabels);

      map.addLayer({
        id: "risk-hotspot-pulse",
        type: "circle",
        source: "risk-areas",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 22, 6, 76],
          "circle-color": toneExpression(0.15),
          "circle-stroke-color": toneExpression(0.36),
          "circle-stroke-width": 1.2,
          "circle-opacity": 0.72
        }
      });
      map.addLayer({
        id: "risk-hotspot-core",
        type: "circle",
        source: "risk-areas",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 7, 6, 14],
          "circle-color": toneExpression(),
          "circle-stroke-color": "#fffdf7",
          "circle-stroke-width": 1.8,
          "circle-opacity": 0.95
        }
      });
      map.addLayer({
      id: "spread-routes-casing",
        type: "line",
      source: "spread-routes",
        paint: { "line-color": "rgba(22, 25, 30, .42)", "line-width": 6, "line-opacity": 0.7 }
      });
      map.addLayer({
      id: "spread-routes",
        type: "line",
      source: "spread-routes",
        paint: { "line-color": toneExpression(), "line-width": 3, "line-dasharray": [1.2, 1.1], "line-opacity": 0.9 }
      });
      map.addLayer({
        id: "impact-halo",
        type: "circle",
        source: "impact-areas",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 18, 6, 64],
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
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 9, 6, 18],
          "circle-color": toneExpression(0.16)
        }
      });
      map.addLayer({
        id: "event-points",
        type: "circle",
        source: "event-points",
        paint: { "circle-radius": 6, "circle-color": toneExpression(), "circle-stroke-color": "#fffdf7", "circle-stroke-width": 1.6 }
      });
      (layers.riskAreas?.features || []).forEach(feature => {
        if (feature.geometry?.type !== "Point") return;
        const el = document.createElement("div");
        el.className = "cn-map-label risk";
        el.textContent = feature.properties?.title || "";
        htmlLabelGroups.risk.push(
          new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -15] })
            .setLngLat(feature.geometry.coordinates)
            .addTo(map)
        );
      });
      (layers.placeLabels?.features || []).forEach(feature => {
        if (feature.geometry?.type !== "Point") return;
        const el = document.createElement("div");
        el.className = "cn-map-label place";
        el.textContent = feature.properties?.title || "";
        htmlLabelGroups.places.push(
          new maplibregl.Marker({ element: el, anchor: "center" })
            .setLngLat(feature.geometry.coordinates)
            .addTo(map)
        );
      });
      map.addLayer({
        id: "risk-areas-label",
        type: "symbol",
        source: "risk-areas",
        layout: {
          "text-field": ["get", "title"],
          "text-size": 11,
          "text-variable-anchor": ["top", "bottom", "left", "right"],
          "text-radial-offset": 0.65
        },
        paint: { "text-color": "#15191f", "text-halo-color": "rgba(255,253,247,.9)", "text-halo-width": 1.2 }
      });
      if (layers.placeLabels) {
        map.addLayer({
          id: "place-labels",
          type: "symbol",
          source: "place-labels",
          layout: {
            "text-field": ["get", "title"],
            "text-size": ["interpolate", ["linear"], ["zoom"], 3, 11, 6, 15],
            "text-allow-overlap": false,
            "text-variable-anchor": ["top", "bottom", "left", "right"],
            "text-radial-offset": 0.4
          },
          paint: {
            "text-color": "#111827",
            "text-halo-color": "rgba(255,253,247,.96)",
            "text-halo-width": 1.6,
            "text-opacity": 0.92
          }
        });
      }
      map.addLayer({
        id: "event-labels",
        type: "symbol",
        source: "event-points",
        minzoom: 4.5,
        layout: { "text-field": ["get", "title"], "text-size": 10, "text-offset": [0.8, -0.7], "text-anchor": "left" },
        paint: { "text-color": "#15191f", "text-halo-color": "rgba(255,253,247,.94)", "text-halo-width": 1.2 }
      });
      map.addLayer({
        id: "route-labels",
        type: "symbol",
      source: "spread-routes",
        minzoom: 4.4,
        layout: { "symbol-placement": "line", "text-field": ["get", "title"], "text-size": 10 },
        paint: { "text-color": "#15191f", "text-halo-color": "rgba(255,253,247,.94)", "text-halo-width": 1.2 }
      });
      map.addLayer({
        id: "impact-labels",
        type: "symbol",
        source: "impact-areas",
        minzoom: 4.8,
        layout: { "text-field": ["get", "title"], "text-size": 10, "text-offset": [0.6, 0.7], "text-anchor": "top-left" },
        paint: { "text-color": "#15191f", "text-halo-color": "rgba(255,253,247,.94)", "text-halo-width": 1.2 }
      });

      let pulseTick = 0;
      const pulseTimer = window.setInterval(() => {
        if (!map.getLayer("risk-hotspot-pulse")) return;
        pulseTick = (pulseTick + 1) % 120;
        const wave = Math.sin((pulseTick / 120) * Math.PI * 2);
        const base = 24 + wave * 5;
        map.setPaintProperty("risk-hotspot-pulse", "circle-radius", ["interpolate", ["linear"], ["zoom"], 3, base, 6, base * 3.1]);
        map.setPaintProperty("risk-hotspot-pulse", "circle-opacity", 0.58 + wave * 0.14);
      }, 80);
      map.on("remove", () => window.clearInterval(pulseTimer));

    ["risk-hotspot-core", "risk-hotspot-pulse", "event-points", "spread-routes", "impact-points"].forEach(layerId => {
        map.on("mouseenter", layerId, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layerId, () => { map.getCanvas().style.cursor = ""; });
        map.on("click", layerId, event => {
          const feature = event.features?.[0];
          if (!feature) return;
          const properties = feature.properties || {};
          new maplibregl.Popup({ closeButton: true, closeOnClick: true, maxWidth: "280px" })
            .setLngLat(event.lngLat)
            .setHTML(popupHtml(properties))
            .addTo(map);
          onFeatureClick?.({ feature, properties, lngLat: event.lngLat });
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
        if (group === "risk") {
          htmlLabelGroups.risk.forEach(marker => {
            marker.getElement().style.display = visible ? "" : "none";
          });
        }
      },
      zoomIn() {
        map.zoomTo(Math.min(map.getZoom() + 0.75, map.getMaxZoom()), { duration: 260 });
      },
      zoomOut() {
        map.zoomTo(Math.max(map.getZoom() - 0.75, map.getMinZoom()), { duration: 260 });
      },
      flyToRegion(region) {
        if (!region?.center) return;
        map.flyTo({ center: region.center, zoom: Math.max(map.getZoom(), 5.25), duration: 450 });
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
