import { defineConfig } from "playwright/test";

// Run against an explicitly started QA Vite server; all selected suites intercept APIs.
export default defineConfig({
  testDir: "../playwright",
  testMatch: [
    "sidebar-quick-create.spec.ts",
    "crm-create-close.spec.ts", "priority-colors-shared.spec.ts", "task-priority-rows.spec.ts",
    "form-defaults-recovery.spec.ts",
    "hr-workflow-standards.spec.ts",
    "planner-priority.spec.ts",
    "srm-sales-orders-ui.spec.ts", "srm-contracts-ui.spec.ts", "srm-engagements-ui.spec.ts",
    "srm-invoice-drafts-ui.spec.ts", "srm-invoices-ui.spec.ts", "srm-receipts-ui.spec.ts",
    "fam-voucher-entry.spec.ts", "fam-voucher-posting.spec.ts", "fam-stock-transfers.spec.ts",
    "fam-purchase-bills.spec.ts", "fam-vendor-payments.spec.ts",
    "communication-campaigns.spec.ts", "communication-consents.spec.ts", "communication-webforms.spec.ts",
    "power-apps.spec.ts", "power-context-menu.spec.ts", "power-module-options.spec.ts",
    "shared-edit-delete.spec.ts", "suite-record-views.spec.ts",
  ],
  outputDir: "test-results/business-workflows",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 2,
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5297", trace: "retain-on-failure" },
});
