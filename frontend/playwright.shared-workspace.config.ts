import { defineConfig } from "playwright/test";
export default defineConfig({
  outputDir: "../.tmp/shared-workspace-results",
  testDir: "../playwright", testMatch: "shared-workspace.spec.ts", timeout: 45000,
  use: { channel: "chrome", baseURL: "http://127.0.0.1:5177", trace: "retain-on-failure" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5177", url: "http://127.0.0.1:5177", reuseExistingServer: true, env: { VITE_SUPPRESS_PROXY_ERRORS: "true" } },
});
