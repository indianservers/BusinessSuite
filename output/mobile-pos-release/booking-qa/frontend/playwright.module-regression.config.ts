import { defineConfig } from "playwright/test";

// Own the QA server and cache so another chat cannot stop a reused dev server mid-run.
export default defineConfig({
  testDir: "../playwright",
  testMatch: ["sidebar-quick-create.spec.ts", "crm-create-close.spec.ts", "priority-colors-shared.spec.ts", "task-priority-rows.spec.ts", "form-defaults-recovery.spec.ts", "hr-workflow-standards.spec.ts"],
  outputDir: "test-results/module-regression",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 2,
  use: { baseURL: "http://127.0.0.1:5297", trace: "retain-on-failure" },
  webServer: {
    command: "node --max-old-space-size=4096 node_modules/vite/bin/vite.js --config scripts/vite-module-regression.config.mjs --host 127.0.0.1 --port 5297 --strictPort",
    url: "http://127.0.0.1:5297",
    reuseExistingServer: false,
    timeout: 120_000,
    env: { VITE_CACHE_DIR: "node_modules/.vite-module-regression", VITE_SUPPRESS_PROXY_ERRORS: "true" },
  },
});
