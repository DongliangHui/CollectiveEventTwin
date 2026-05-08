import { expect, type Page, type Request, type Response, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const apiBase = process.env.E2E_API_BASE_URL ?? process.env.VITE_API_BASE_URL ?? "http://localhost:8080";
const outputDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..", "artifacts", "output");
const campusCaseId = "CASE-CAMPUS-001";
const communityCaseId = "CASE-COMMUNITY-WATER-001";

type ProductPageId =
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

const productRoutes: ProductPageId[] = [
  "risk",
  "data",
  "evidence",
  "mainline",
  "worldline",
  "council",
  "brief",
  "memory",
  "library",
  "config"
];

function productUrl(caseId: string, pageId: ProductPageId) {
  return `/cases/${caseId}/${pageId}`;
}

function pageApiPath(caseId: string, pageId: ProductPageId) {
  return `/api/v1/cases/${caseId}/pages/${pageId}`;
}

function pageApiResponse(page: Page, caseId: string, pageId: ProductPageId) {
  const expectedPath = pageApiPath(caseId, pageId);
  return page.waitForResponse((response) => new URL(response.url()).pathname === expectedPath, { timeout: 8_000 }).catch((error) => {
    throw new Error(
      `Timed out waiting for page API ${expectedPath}. ` +
        `The P0 product page must call this route instead of static iframe/mock data. ${String(error)}`
    );
  });
}

function installNetworkGuards(page: Page) {
  const forbiddenUrls: string[] = [];

  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/worldline-observer-current/mock/")) {
      forbiddenUrls.push(url);
    }
  });

  return {
    async expectClean() {
      expect(forbiddenUrls, "product pages must not request legacy static mock URLs").toEqual([]);
      await expect(page.locator("iframe"), "product pages must render native React, not iframe static replicas").toHaveCount(0);
    }
  };
}

async function openProductPage(page: Page, caseId: string, pageId: ProductPageId): Promise<Response> {
  const [response] = await Promise.all([
    pageApiResponse(page, caseId, pageId),
    page.goto(productUrl(caseId, pageId))
  ]);
  expect(response.ok(), `${pageApiPath(caseId, pageId)} should return 2xx`).toBeTruthy();
  await expect(page.getByTestId(`product-${pageId}-page`)).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/cases/${caseId}/${pageId}$`));
  return response;
}

async function clickRouterLink(page: Page, caseId: string, pageId: ProductPageId) {
  const documentRequests: string[] = [];
  const listener = (request: Request) => {
    if (request.resourceType() === "document") {
      documentRequests.push(request.url());
    }
  };

  page.on("request", listener);
  const [response] = await Promise.all([
    pageApiResponse(page, caseId, pageId),
    page.locator(`a[href="${productUrl(caseId, pageId)}"]`).first().click()
  ]);
  page.off("request", listener);

  expect(response.ok(), `${pageApiPath(caseId, pageId)} should return 2xx after router navigation`).toBeTruthy();
  expect(documentRequests, "React Router navigation should not trigger a new document load").toEqual([]);
  await expect(page).toHaveURL(new RegExp(`/cases/${caseId}/${pageId}$`));
  await expect(page.getByTestId(`product-${pageId}-page`)).toBeVisible();
}

async function clickAndWaitForApi(page: Page, pathPattern: RegExp, locator: ReturnType<Page["locator"]>) {
  const [response] = await Promise.all([
    page.waitForResponse((response) => pathPattern.test(new URL(response.url()).pathname)),
    locator.click()
  ]);
  expect(response.ok(), `${pathPattern.toString()} should return 2xx`).toBeTruthy();
  return response;
}

test.beforeEach(async ({ request }) => {
  const health = await request.get(`${apiBase}/health`, { timeout: 2_000 }).catch(() => null);
  test.skip(!health?.ok(), `API is not available at ${apiBase}`);

  const seed = await request.post(`${apiBase}/api/v1/admin/seed`, {
    data: { fixture: "all" },
    timeout: 5_000
  });
  expect(seed.ok(), "P0 fixture seed should succeed before E2E").toBeTruthy();
});

test("each product route uses its page API and never requests legacy static mocks", async ({ page }) => {
  const guards = installNetworkGuards(page);

  for (const pageId of productRoutes) {
    await openProductPage(page, campusCaseId, pageId);
    await guards.expectClean();
  }
});

test("golden path closes the P0 loop through API-driven React pages", async ({ page }) => {
  const guards = installNetworkGuards(page);

  await openProductPage(page, campusCaseId, "risk");
  await clickRouterLink(page, campusCaseId, "data");
  await openProductPage(page, campusCaseId, "evidence");
  await openProductPage(page, campusCaseId, "mainline");

  await clickAndWaitForApi(
    page,
    /^\/api\/v1\/mainlines\/[^/]+\/confirm$/,
    page.getByTestId("product-mainline-page").locator("button").filter({ hasText: /confirm|确认/i }).first()
  );

  await clickRouterLink(page, campusCaseId, "worldline");
  await clickAndWaitForApi(
    page,
    /^\/api\/v1\/worldline-nodes\/[^/]+\/run-council$/,
    page.getByTestId("product-worldline-page").getByRole("button", { name: /启动多主体研判/ })
  );

  await clickRouterLink(page, campusCaseId, "council");
  await clickAndWaitForApi(
    page,
    /^\/api\/v1\/council-sessions\/[^/]+\/apply$/,
    page.getByTestId("product-council-page").getByRole("button", { name: /将结果注入世界线并重跑|应用/ })
  );

  await clickRouterLink(page, campusCaseId, "brief");
  await clickAndWaitForApi(
    page,
    /^\/api\/v1\/reports\/[^/]+\/confirm$/,
    page.getByTestId("product-brief-page").getByRole("button", { name: /完成并回主线|确认报告|confirm/i })
  );
  await clickAndWaitForApi(
    page,
    /^\/api\/v1\/tasks(?:\/[^/]+)?$/,
    page.getByTestId("product-brief-page").locator("button").filter({ hasText: /创建任务|更新/i }).first()
  );

  await openProductPage(page, campusCaseId, "memory");
  await openProductPage(page, campusCaseId, "library");
  await openProductPage(page, campusCaseId, "config");
  await guards.expectClean();
});

test("product navigation stays in React Router while admin keeps debug controls", async ({ page }) => {
  const guards = installNetworkGuards(page);

  await openProductPage(page, campusCaseId, "risk");
  await expect(page.getByRole("button", { name: /Seed P0/i })).toHaveCount(0);
  await expect(page.getByText(/Workflow|工作流/i)).toHaveCount(0);

  await clickRouterLink(page, campusCaseId, "mainline");
  await guards.expectClean();

  await page.goto("/admin");
  await expect(page.getByTestId("admin-console")).toBeVisible();
  await expect(page.getByRole("button", { name: /Seed P0/i })).toBeVisible();
  await expect(page.getByText("工作流运行").first()).toBeVisible();
});

test("captures P0 product visual baselines", async ({ page }) => {
  fs.mkdirSync(outputDir, { recursive: true });
  const guards = installNetworkGuards(page);

  await page.setViewportSize({ width: 1440, height: 900 });
  await openProductPage(page, campusCaseId, "risk");
  await guards.expectClean();
  await page.screenshot({ path: path.join(outputDir, "p0-product-risk-1440x900.png"), fullPage: true });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await openProductPage(page, campusCaseId, "worldline");
  await guards.expectClean();
  await page.screenshot({ path: path.join(outputDir, "p0-product-worldline-1920x1080.png"), fullPage: true });
});

test("community smoke enters the product chain without campus-only copy", async ({ page }) => {
  const guards = installNetworkGuards(page);

  await openProductPage(page, communityCaseId, "risk");
  await expect(page.locator("body")).not.toContainText(/青澜中学|校园|学生|校方|家属|坠楼|欺凌/);

  await clickRouterLink(page, communityCaseId, "mainline");
  await expect(page.locator("body")).not.toContainText(/青澜中学|校园|学生|校方|家属|坠楼|欺凌/);
  await guards.expectClean();
});
