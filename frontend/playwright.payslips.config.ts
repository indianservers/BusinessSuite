import { defineConfig } from "playwright/test";
import base from "./playwright.mobile-workspaces.config";

export default defineConfig({
  ...base,
  testMatch: "payslips.spec.ts",
  outputDir: "../.tmp/payslip-tests",
  use: { baseURL: "http://127.0.0.1:5195", trace: "retain-on-failure", serviceWorkers: "block" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "phone", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    ...(Array.isArray(base.webServer) ? base.webServer.slice(0, 1) : []),
    { command: "npm run dev -- --host 127.0.0.1 --port 5195 --strictPort", url: "http://127.0.0.1:5195", reuseExistingServer: true, timeout: 120000,
      env: { VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1551", VITE_SUPPRESS_PROXY_ERRORS: "true", VITE_CACHE_DIR: "../.tmp/payslips-vite" } },
  ],
});
