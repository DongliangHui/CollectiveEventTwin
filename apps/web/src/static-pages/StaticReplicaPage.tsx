import { useEffect, useMemo } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { ProductPageId } from "../App";
import { staticReplicaPages } from "./generated";

export type StaticReplicaPageId =
  | "city"
  | "risk"
  | "data"
  | "evidence"
  | "mainline"
  | "worldline"
  | "council"
  | "brief"
  | "memory"
  | "library"
  | "config";

const hrefPageMap: Record<string, StaticReplicaPageId> = {
  "city-monitor.html": "city",
  "risk-dashboard.html": "risk",
  "data-hub.html": "data",
  "event-detail-evidence.html": "evidence",
  "mainline-builder.html": "mainline",
  "worldline-observer.html": "worldline",
  "agent-council.html": "council",
  "decision-brief.html": "brief",
  "case-memory.html": "memory",
  "topic-case-library.html": "library",
  "data-source-model-config.html": "config"
};

const productPageMap: Record<StaticReplicaPageId, ProductPageId> = {
  city: "city",
  risk: "risk",
  data: "data",
  evidence: "evidence",
  mainline: "mainline",
  worldline: "worldline",
  council: "council",
  brief: "brief",
  memory: "memory",
  library: "library",
  config: "config"
};

export const productPageToStaticReplica: Partial<Record<ProductPageId, StaticReplicaPageId>> = {
  city: "city",
  risk: "risk",
  data: "data",
  evidence: "evidence",
  mainline: "mainline",
  worldline: "worldline",
  council: "council",
  brief: "brief",
  memory: "memory",
  library: "library",
  config: "config"
};

type StaticReplicaPageProps = {
  caseId: string;
  pageId: StaticReplicaPageId;
};

export function StaticReplicaPage({ caseId, pageId }: StaticReplicaPageProps) {
  const navigate = useNavigate();
  const srcDoc = useMemo(() => buildSrcDoc(staticReplicaPages[pageId], pageId), [pageId]);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (!event.data || event.data.type !== "worldline-static-navigate") return;
      const target = pageFromHref(String(event.data.href ?? ""));
      if (!target) return;
      void navigate({
        to: "/cases/$caseId/$page",
        params: { caseId, page: productPageMap[target] }
      });
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [caseId, navigate]);

  return (
    <div className="static-replica-frame" data-testid={`static-${pageId}-page`}>
      <iframe
        key={pageId}
        title={`worldline-observer-${pageId}`}
        srcDoc={srcDoc}
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads"
      />
    </div>
  );
}

function pageFromHref(href: string): StaticReplicaPageId | null {
  const cleanHref = href.split("?")[0].split("#")[0].replace(/^.*\//, "");
  return hrefPageMap[cleanHref] ?? null;
}

function buildSrcDoc(html: string, pageId: StaticReplicaPageId) {
  const withBase = html.replace(
    /<head>/i,
    `<head><base href="/worldline-observer-current/" /><meta name="worldline-react-page" content="${pageId}" />`
  );
  const bridge = `<script>
(() => {
  const map = new Set(${JSON.stringify(Object.keys(hrefPageMap))});
  function pageFromHref(href) {
    const clean = String(href || "").split("?")[0].split("#")[0].replace(/^.*\\//, "");
    return map.has(clean) ? clean : "";
  }
  document.addEventListener("click", event => {
    const anchor = event.target && event.target.closest ? event.target.closest("a[href]") : null;
    if (!anchor) return;
    const href = anchor.getAttribute("href") || "";
    if (!pageFromHref(href)) return;
    event.preventDefault();
    window.parent.postMessage({ type: "worldline-static-navigate", href }, "*");
  }, true);
})();
</script>`;
  return withBase.includes("</body>") ? withBase.replace(/<\/body>/i, `${bridge}</body>`) : `${withBase}${bridge}`;
}
