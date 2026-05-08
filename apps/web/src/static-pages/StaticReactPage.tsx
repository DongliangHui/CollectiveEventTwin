import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { PageView, ProductPageName } from "../api";
import { staticReplicaPages } from "./generated";
import type { StaticReplicaPageId } from "./StaticReplicaPage";

type StaticReactPageProps = {
  caseId: string;
  page: ProductPageName;
};

type StaticDocument = {
  body: string;
  scripts: string[];
  scriptSrcs: string[];
  styles: string;
  stylesheetHrefs: string[];
  title: string;
};

const hrefPageMap: Record<string, ProductPageName> = {
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

export function StaticReactPage({ caseId, page }: StaticReactPageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pageQuery = useQuery({
    queryKey: ["p0-page", caseId, page],
    queryFn: () => api.getPageView(caseId, page)
  });
  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["p0-page", caseId] });
      await queryClient.invalidateQueries({ queryKey: ["case-bundle", caseId] });
    }
  });
  const documentParts = useMemo(() => {
    const html = staticReplicaPages[page as StaticReplicaPageId];
    return extractStaticDocument(html, caseId);
  }, [caseId, page]);
  const [assetRun, setAssetRun] = useState(0);

  useEffect(() => {
    return installStaticAssets(documentParts, page, () => setAssetRun((run) => run + 1));
  }, [documentParts, page]);

  useEffect(() => {
    if (assetRun === 0) return;
    const host = hostRef.current;
    if (!host) return;
    return runInlineStaticScripts(documentParts.scripts, page);
  }, [assetRun, documentParts.scripts, page, pageQuery.status]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;

      const anchor = target.closest("a[href]");
      if (anchor instanceof HTMLAnchorElement) {
        const targetPage = productPageFromHref(anchor.getAttribute("href") ?? "", caseId);
        if (targetPage) {
          event.preventDefault();
          void navigate({ to: "/cases/$caseId/$page", params: { caseId, page: targetPage } });
          return;
        }
      }

      const button = target.closest("button");
      if (button instanceof HTMLButtonElement) {
        handleStaticButtonClick(page, button.innerText, pageQuery.data, (fn) => action.mutate(fn));
      }
    };
    host.addEventListener("click", onClick, true);
    return () => host.removeEventListener("click", onClick, true);
  }, [action, caseId, navigate, page, pageQuery.data]);

  return (
    <div
      ref={hostRef}
      className="static-react-page"
      data-testid={`product-${page}-page`}
      data-api-state={pageQuery.isError ? "error" : pageQuery.isLoading ? "loading" : "ready"}
      data-static-scripts={documentParts.scripts.length}
      dangerouslySetInnerHTML={{ __html: documentParts.body }}
    />
  );
}

function extractStaticDocument(html: string, caseId: string): StaticDocument {
  const styles = Array.from(html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi))
    .map((match) => match[1])
    .join("\n\n");
  const stylesheetHrefs = Array.from(html.matchAll(/<link\b[^>]*rel=["']stylesheet["'][^>]*>/gi))
    .map((match) => match[0].match(/\bhref=["']([^"']+)["']/i)?.[1])
    .filter((href): href is string => Boolean(href));
  const title = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.trim() ?? "WORLDLINE OBSERVER";
  const scripts = Array.from(html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))
    .filter((match) => !/\bsrc=/i.test(match[1]))
    .map((match) => match[2].trim())
    .filter(Boolean);
  const scriptSrcs = Array.from(html.matchAll(/<script\b([^>]*)><\/script>/gi))
    .map((match) => match[1].match(/\bsrc=["']([^"']+)["']/i)?.[1])
    .filter((src): src is string => Boolean(src))
    .filter(isAllowedStaticScript);
  const body = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1] ?? html;
  const inertBody = body
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/\son[a-z]+\s*=\s*(['"])[\s\S]*?\1/gi, "");

  return {
    title,
    scripts,
    scriptSrcs,
    styles,
    stylesheetHrefs,
    body: rewriteStaticLinks(inertBody, caseId)
  };
}

function isAllowedStaticScript(src: string) {
  return /^https:\/\/unpkg\.com\/maplibre-gl@[\w.-]+\/dist\/maplibre-gl\.js$/i.test(src);
}

function installStaticAssets(documentParts: StaticDocument, page: ProductPageName, onReady: () => void) {
  const style = document.createElement("style");
  style.dataset.staticReactPage = page;
  style.textContent = documentParts.styles;
  document.head.appendChild(style);

  const links = documentParts.stylesheetHrefs.map((href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.dataset.staticReactPage = page;
    document.head.appendChild(link);
    return link;
  });
  let disposed = false;
  const markReady = () => {
    if (!disposed) onReady();
  };
  const scripts = documentParts.scriptSrcs.map((src) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    script.dataset.staticReactPage = page;
    script.onload = markReady;
    script.onerror = markReady;
    document.head.appendChild(script);
    return script;
  });
  const readyTimer = window.setTimeout(markReady, 0);

  const previousTitle = document.title;
  document.title = documentParts.title;
  document.body.classList.add("static-react-active");

  return () => {
    disposed = true;
    window.clearTimeout(readyTimer);
    style.remove();
    for (const link of links) link.remove();
    for (const script of scripts) script.remove();
    document.body.classList.remove("static-react-active");
    document.title = previousTitle;
  };
}

function runInlineStaticScripts(scripts: string[], page: ProductPageName) {
  const previousFetch = window.fetch;
  let didRun = false;
  let timer: number | null = null;
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/worldline-observer-current/mock/") || url.includes("worldline-observer-current/mock/") || url.includes("/mock/fixtures/")) {
      return Promise.reject(new Error(`blocked static mock request: ${url}`));
    }
    return previousFetch(input, init);
  }) as typeof window.fetch;

  timer = window.setTimeout(() => {
    didRun = true;
    for (const [index, script] of scripts.entries()) {
      try {
        new Function(`${script}\n//# sourceURL=static-react-${page}-${index}.js`)();
      } catch (error) {
        console.warn(`[static-react:${page}] inline script skipped`, error);
      }
    }
  }, 0);

  return () => {
    if (!didRun && timer !== null) window.clearTimeout(timer);
    window.fetch = previousFetch;
  };
}

function rewriteStaticLinks(html: string, caseId: string) {
  return html.replace(/\bhref=(["'])([^"']+)\1/gi, (full, quote: string, href: string) => {
    const target = productPageFromHref(href, caseId);
    return target ? `href=${quote}/cases/${caseId}/${target}${quote}` : full;
  });
}

function productPageFromHref(href: string, caseId: string): ProductPageName | null {
  const cleanHref = href.split("?")[0].split("#")[0].replace(/^.*\//, "");
  if (cleanHref in hrefPageMap) return hrefPageMap[cleanHref];
  try {
    const url = new URL(href, window.location.origin);
    const prefix = `/cases/${caseId}/`;
    if (url.pathname.startsWith(prefix)) {
      const page = url.pathname.slice(prefix.length);
      if (isProductPage(page)) return page;
    }
  } catch {
    return null;
  }
  return null;
}

function handleStaticButtonClick(page: ProductPageName, label: string, view: PageView | undefined, run: (fn: () => Promise<unknown>) => void) {
  if (!view) return;
  const text = label.replace(/\s+/g, "");

  if (page === "mainline" && /确认|主线/.test(text)) {
    const id = objectId(view.raw.active_mainline);
    if (id) run(() => api.confirmMainline(id));
    return;
  }
  if (page === "worldline" && /多主体研判|开始研判|启动/.test(text)) {
    const nodeId = objectId(view.raw.current_node) ?? objectId(firstSectionItem(view, "nodes"));
    if (nodeId) run(() => api.runCouncil(nodeId));
    return;
  }
  if (page === "council" && /注入世界线|重跑|应用/.test(text)) {
    const id = objectId(view.raw.latest_council);
    if (id) run(() => api.applyCouncil(id));
    return;
  }
  if (page === "council" && /压力测试/.test(text)) {
    const id = objectId(view.raw.latest_council);
    if (id) run(() => api.runPressureTest(id, "人工压力测试：静态页触发"));
    return;
  }
  if (page === "brief" && /完成|确认|报告/.test(text)) {
    const id = objectId(view.raw.report);
    if (id) run(() => api.confirmReport(id));
    return;
  }
  if (page === "brief" && /创建任务|任务/.test(text)) {
    run(() => api.createTask(view.case_id, "静态简报页创建的处置任务", "operator"));
    return;
  }
  if (page === "memory" && /保存/.test(text)) {
    run(() => api.runCaseMemoryAction(view.case_id, "save_draft"));
    return;
  }
  if (page === "memory" && /审阅|提交/.test(text)) {
    run(() => api.runCaseMemoryAction(view.case_id, "submit_review"));
    return;
  }
  if (page === "memory" && /入库|确认/.test(text)) {
    run(() => api.runCaseMemoryAction(view.case_id, "confirm_ingest"));
    return;
  }
  if (page === "library" && /应用|加入/.test(text)) {
    run(() => api.applyLibraryItem(view.case_id, "Pattern", "PATTERN-FACT-GAP"));
    return;
  }
  if (page === "config" && /回归/.test(text)) {
    run(() => api.runConfigAction("v2.4.2", view.case_id, "run_regression"));
    return;
  }
  if (page === "config" && /审批|发布/.test(text)) {
    run(() => api.runConfigAction("v2.4.2", view.case_id, "submit_approval"));
  }
}

function firstSectionItem(view: PageView, sectionId: string): unknown {
  return view.sections.find((section) => section.id === sectionId)?.items?.[0];
}

function objectId(value: unknown): string | null {
  if (typeof value === "object" && value !== null && "id" in value && typeof (value as { id?: unknown }).id === "string") {
    return (value as { id: string }).id;
  }
  return null;
}

function isProductPage(value: string): value is ProductPageName {
  return ["city", "risk", "data", "evidence", "mainline", "worldline", "council", "brief", "memory", "library", "config"].includes(value);
}
