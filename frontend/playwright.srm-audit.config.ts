import { defineConfig } from "playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testMatch:["srm-navigation.spec.ts","srm-route-audit.spec.ts","srm-ui-routes.spec.ts"],
  outputDir:"test-results/srm-merge-audit",
  timeout:120_000,
  expect:{timeout:20_000},
  workers:2,
  use:{...base.use,trace:"off"},
});
