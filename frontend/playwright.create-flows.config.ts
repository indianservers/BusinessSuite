import { defineConfig } from "playwright/test";
export default defineConfig({outputDir:"test-results/create-flows",
  testDir:"../playwright", testMatch:["crm-create-close.spec.ts","crm-edit-delete.spec.ts","shared-edit-delete.spec.ts","catalog-edit-delete.spec.ts","catalog-views.spec.ts","crm-autosave.spec.ts"], timeout:60000, fullyParallel:true, workers:2,
  use:{baseURL:"http://127.0.0.1:5175",trace:"retain-on-failure"},
});
