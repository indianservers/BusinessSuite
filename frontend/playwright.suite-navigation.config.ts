import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "../playwright",
  testMatch: ["suite-navigation.spec.ts"],
  outputDir: "../.tmp/suite-navigation-browser",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5187", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1672, height: 1000 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: [
    {
      command:
        '"../backend/venv/Scripts/python.exe" "../backend/scripts/suite_navigation_qa_server.py"',
      url: "http://127.0.0.1:1551/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5187 --strictPort",
      url: "http://127.0.0.1:5187",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_DEV_API_PROXY_TARGET: "http://127.0.0.1:1551",
        VITE_SUPPRESS_PROXY_ERRORS: "true",
      },
    },
  ],
});
