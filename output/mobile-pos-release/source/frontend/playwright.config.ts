import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "../playwright",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5173",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      VITE_SUPPRESS_PROXY_ERRORS: "true",
    },
  },
});
