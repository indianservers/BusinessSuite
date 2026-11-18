import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "../playwright",
  testMatch: "intern-task-programs.spec.ts",
  workers: 1,
  timeout: 90000,
  expect: { timeout: 20000 },
  outputDir: "../.tmp/intern-task-programs-tests",
  use: {
    baseURL: process.env.PROGRAMS_BASE_URL || "http://127.0.0.1:5198",
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
