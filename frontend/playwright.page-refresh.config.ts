import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright", testMatch: "page-refresh.spec.ts", workers: 1,
  timeout: 60000, expect: { timeout: 15000 },
  outputDir: "../.tmp/page-refresh-tests",
  use: { baseURL: process.env.REFRESH_BASE_URL || "http://127.0.0.1:5193", trace: "retain-on-failure", serviceWorkers: "block" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true } },
  ],
  webServer: process.env.REFRESH_PREVIEW ? undefined : {
    command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort",
    url: "http://127.0.0.1:5193", reuseExistingServer: true, timeout: 120000,
    env: { NODE_OPTIONS: "--max-old-space-size=8192", VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1551", VITE_API_BASE_URL: "/api/v1", VITE_SUPPRESS_PROXY_ERRORS: "true" },
  },
});
