import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: "shared-profiles.spec.ts",
  timeout: 45000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5193", trace: "retain-on-failure" },
  webServer: [
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5193",
      url: "http://127.0.0.1:5193",
      reuseExistingServer: true,
      timeout: 120000,
      env: { VITE_SUPPRESS_PROXY_ERRORS: "true" },
    },
    {
      command:
        "npm --prefix interns-hub run dev -- --host 127.0.0.1 --port 5178",
      url: "http://127.0.0.1:5178",
      reuseExistingServer: true,
      timeout: 120000,
    },
  ],
});
