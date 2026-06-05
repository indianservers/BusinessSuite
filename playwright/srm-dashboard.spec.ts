import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM dashboard", () => {
  test("renders KPI, invoice, collection, profitability, and CRM/PMS sections", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "SRM Dashboard" })).toBeVisible();
    await expect(page.getByText("Total sales orders", { exact: true })).toBeVisible();
    await expect(page.getByText("Pending approvals", { exact: true })).toBeVisible();
    await expect(page.getByText("Total invoiced", { exact: true })).toBeVisible();
    await expect(page.getByText("Recent Sales Orders", { exact: true })).toBeVisible();
    await expect(page.getByText("Recent Invoices", { exact: true })).toBeVisible();
    await expect(page.getByText("Collection Alerts", { exact: true })).toBeVisible();
    await expect(page.getByText("Revenue Trend", { exact: true })).toBeVisible();
    await expect(page.getByText("Profitability Summary", { exact: true })).toBeVisible();
    await expect(page.getByText("CRM/PMS Linked Activity", { exact: true })).toBeVisible();
  });

  test("handles dashboard API errors without a broken page", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.route("**/api/v1/srm/dashboard", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "dashboard unavailable" }) });
    });
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Unable to load dashboard.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  });
});
