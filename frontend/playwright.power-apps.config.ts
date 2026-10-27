import { defineConfig } from "playwright/test";

// Own a separate server so other local browser suites cannot stop this run.
export default defineConfig({
  testDir: "../playwright",
  testMatch: ["power-apps.spec.ts", "power-studio.spec.ts", "power-studio-premium.spec.ts"],
  outputDir: "../.tmp/power-apps-browser",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  use: { baseURL: "http://127.0.0.1:5193", trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort",
    url: "http://127.0.0.1:5193",
    reuseExistingServer: false,
    timeout: 120_000,
    env: { VITE_SUPPRESS_PROXY_ERRORS: "true" },
  },
});
