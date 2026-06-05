import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM Customer 360", () => {
  test("search renders linked CRM, SRM, PMS, billing, collection, and audit sections", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/customer-360", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Customer 360" })).toBeVisible();
    await expect(page.getByLabel("Customer 360 search")).toBeVisible();
    await expect(page.getByText("No Customer 360 data found for the current filters.")).toBeVisible();

    await page.getByLabel("Customer 360 search").fill("10");
    await page.getByRole("button", { name: "Search Customer 360" }).click();

    await expect(page.getByRole("heading", { name: "CRM References" })).toBeVisible();
    await expect(page.locator("h3").filter({ hasText: /^Sales Orders$/ }).last()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Contracts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Billing Plans" })).toBeVisible();
    await expect(page.locator("h3").filter({ hasText: /^Invoices$/ }).last()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Receipts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Collection Reminders" })).toBeVisible();
    await expect(page.locator("h3").filter({ hasText: /^Profitability$/ }).last()).toBeVisible();
    await expect(page.getByRole("heading", { name: "PMS Projects" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Timeline / Audit Trail" })).toBeVisible();
  });

  test("handles Customer 360 API errors", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.route("**/api/v1/srm/customer-360**", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "customer unavailable" }) });
    });
    await page.goto("/srm/customer-360", { waitUntil: "domcontentloaded" });
    await page.getByLabel("Customer 360 search").fill("SO-000001");
    await page.getByRole("button", { name: "Search Customer 360" }).click();
    await expect(page.getByText("Unable to load Customer 360 data.", { exact: true })).toBeVisible();
  });
});
