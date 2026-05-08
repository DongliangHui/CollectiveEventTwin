import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const apiBase = process.env.E2E_API_BASE_URL ?? "http://localhost:8080";
const webDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 8_000
  },
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "on-first-retry",
    screenshot: "only-on-failure"
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port 5174`,
    cwd: webDir,
    url: "http://127.0.0.1:5174",
    reuseExistingServer: true,
    env: {
      E2E_API_BASE_URL: apiBase,
      VITE_API_BASE_URL: ""
    }
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }
    }
  ],
  outputDir: "../../artifacts/playwright-web"
});
