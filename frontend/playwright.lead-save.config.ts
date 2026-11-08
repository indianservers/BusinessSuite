import { defineConfig } from "playwright/test";
export default defineConfig({outputDir:"test-results/lead-save",
  testDir: "../playwright",
  testMatch: "crm-lead-workbench.spec.ts",
  timeout: 45000,
  workers: 1,
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5175", trace: "retain-on-failure" },
});
