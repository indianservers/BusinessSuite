import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: "pms-dashboard-builder-live.spec.ts",
  workers: 1,
  timeout: 90000,
  use: {
    baseURL: "http://127.0.0.1:5191",
    screenshot: "only-on-failure",
    reducedMotion: "reduce",
  },
  outputDir: "../test-results/dashboard-builder",
});
