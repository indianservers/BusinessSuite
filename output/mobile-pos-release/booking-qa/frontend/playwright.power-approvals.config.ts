import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: ["power-approvals-live.spec.ts"],
  outputDir: "../.tmp/power-approvals-browser",
  timeout: 60_000,
  // The isolated SQLite API serializes authenticated requests; startup is not a canvas performance benchmark.
  expect: { timeout: 25_000 },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5196",
    trace: "retain-on-failure",
    viewport: { width: 1600, height: 1000 },
  },
  webServer: [
    {
      command:
        '"../backend/venv/Scripts/python.exe" "../backend/scripts/power_studio_qa_server.py" --runtime --approvals',
      url: "http://127.0.0.1:1547/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5196 --strictPort",
      url: "http://127.0.0.1:5196",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1547",
        VITE_SUPPRESS_PROXY_ERRORS: "true",
      },
    },
  ],
});
