import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM invoice draft UI", () => {
  test("generates invoice drafts from supported sources and shows duplicate prevention errors", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.goto("/srm/invoice-drafts", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Invoice Drafts", level: 1 })).toBeVisible();
    await expect(page.getByText("Source Evidence")).toBeVisible();

    await page.getByRole("button", { name: "Draft from Engagement" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Engagement draft completed");

    await page.getByRole("button", { name: "Draft from Billing Milestone" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Billing milestone draft completed");

    await page.getByRole("button", { name: "Draft from PMS Milestone" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("PMS milestone draft completed");

    await page.getByRole("button", { name: "Draft from Timesheets" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Timesheet draft completed");

    await page.getByRole("button", { name: "Create Manual Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Manual invoice draft completed");

    await page.route("**/api/v1/srm/invoices/draft-from-sales-order/1", async (route) => {
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Invoice already drafted for this source" }) });
    });
    await page.getByRole("button", { name: "Draft from Sales Order" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Invoice already drafted for this source");
  });
});
