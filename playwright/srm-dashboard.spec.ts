import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM dashboard", () => {
  test("renders KPI, invoice, collection, profitability, and CRM/PMS sections", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Sales Revenue Management" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open POS", exact: true })).toBeVisible();
    for (const label of ["Total invoiced", "Collected", "Outstanding", "Overdue", "Revenue performance", "Order pipeline", "Sales Orders", "Invoices", "Collection health"]) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }
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
