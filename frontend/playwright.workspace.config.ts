import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: "../playwright",
  testMatch: "pms-workspaces.spec.ts",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: { baseURL: "http://127.0.0.1:5181", trace: "retain-on-failure" },
});
