import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "../playwright",
  testMatch: "mobile-workspaces.spec.ts",
  outputDir: "../.tmp/mobile-workspaces-tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5189", trace: "retain-on-failure" },
  projects: [
    { name: "phone-small", use: { viewport: { width: 320, height: 740 } } },
    { name: "phone", use: { viewport: { width: 390, height: 844 } } },
    { name: "tablet", use: { viewport: { width: 768, height: 1024 } } },
  ],
  webServer: [
    { command: '"../backend/venv/Scripts/python.exe" "../backend/scripts/suite_navigation_qa_server.py"', url: "http://127.0.0.1:1551/health", reuseExistingServer: true, timeout: 120_000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5189 --strictPort", url: "http://127.0.0.1:5189", reuseExistingServer: true, timeout: 120_000, env: { VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1551", VITE_SUPPRESS_PROXY_ERRORS: "true" } },
  ],
});
