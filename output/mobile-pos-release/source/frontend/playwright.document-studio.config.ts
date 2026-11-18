import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: "document-studio.spec.ts",
  workers: 1,
  timeout: 90000,
  expect: { timeout: 20000 },
  outputDir: "../.tmp/document-studio-tests",
  use: {
    baseURL: process.env.STUDIO_BASE_URL || "http://127.0.0.1:5196",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    {
      name: "mobile",
      use: { viewport: { width: 390, height: 844 }, isMobile: true },
    },
  ],
});
