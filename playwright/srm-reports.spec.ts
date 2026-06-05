import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

const reports = [
  "Sales Order Report",
  "Contract Report",
  "Invoice Register",
  "Invoice Aging",
  "Collection Aging",
  "Customer Outstanding",
  "Engagement Profitability",
  "Project Profitability",
  "Customer Profitability",
  "Lead-to-Cash Report",
  "Sales-to-Delivery Margin",
  "Cash Margin Report",
];

test.describe("SRM reports", () => {
  test("renders business report cards, filters, preview, drill-down, and export status", async ({ page }) => {
    await authenticate(page, "srm_business_owner");
    await page.goto("/srm/reports", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
    for (const title of reports) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }

    await page.getByRole("button", { name: "View details" }).first().click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("preview loaded");
    await expect(page.getByLabel("report customer filter")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Preview/ })).toBeVisible();

    await page.getByRole("button", { name: "Export" }).first().click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("export is not yet supported");
  });
});
