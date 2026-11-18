import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright", testMatch: "payroll-delivery.spec.ts", workers: 1,
  outputDir: "../.tmp/payroll-delivery-tests", timeout: 60000, expect: { timeout: 15000 },
  use: { baseURL: "http://127.0.0.1:5197", trace: "retain-on-failure", serviceWorkers: "block" },
  projects: [{ name: "desktop", use: { viewport: { width: 1440, height: 1000 } } }, { name: "phone", use: { viewport: { width: 390, height: 844 } } }],
  webServer: [
    { command: '"../backend/venv/Scripts/python.exe" "../backend/scripts/suite_navigation_qa_server.py"', url: "http://127.0.0.1:1553/health", reuseExistingServer: true, timeout: 120000, env: { SUITE_QA_PORT: "1553" } },
    { command: "npm run dev -- --host 127.0.0.1 --port 5197 --strictPort", url: "http://127.0.0.1:5197", reuseExistingServer: true, timeout: 120000,
      env: { VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1553", VITE_SUPPRESS_PROXY_ERRORS: "true", VITE_CACHE_DIR: "../.tmp/payroll-delivery-vite" } },
  ],
});
