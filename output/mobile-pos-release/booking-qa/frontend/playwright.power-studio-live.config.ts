import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: ["power-studio-live.spec.ts", "power-intelligence-live.spec.ts"],
  outputDir: "../.tmp/power-studio-live-browser",
  timeout: 60_000,
  // The isolated SQLite API serializes authenticated requests; startup is not a canvas performance benchmark.
  expect: { timeout: 25_000 },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5194",
    trace: "retain-on-failure",
    viewport: { width: 1600, height: 1000 },
  },
  webServer: [
    {
      command:
        '"../backend/venv/Scripts/python.exe" "../backend/scripts/power_studio_qa_server.py"',
      url: "http://127.0.0.1:1545/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5194 --strictPort",
      url: "http://127.0.0.1:5194",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1545",
        VITE_SUPPRESS_PROXY_ERRORS: "true",
      },
    },
  ],
});
