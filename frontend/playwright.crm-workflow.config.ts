import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: "crm-lead-workbench.spec.ts",
  timeout: 45000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5196", trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5196 --strictPort",
    url: "http://127.0.0.1:5196",
    reuseExistingServer: true,
    timeout: 120000,
    env: { VITE_SUPPRESS_PROXY_ERRORS: "true" },
  },
});
