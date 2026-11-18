import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "../playwright",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  workers: 4,
  outputDir: "../.local/postgres-playwright-artifacts",
  reporter: [["line"], ["json", { outputFile: "../.local/postgres-playwright-results.json" }]],
  use: { baseURL: "http://127.0.0.1:5182", trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5182 --strictPort",
    url: "http://127.0.0.1:5182",
    reuseExistingServer: true,
    timeout: 120_000,
    env: { VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:8766", VITE_SUPPRESS_PROXY_ERRORS: "true" },
  },
});
