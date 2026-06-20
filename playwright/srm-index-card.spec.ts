import { expect, test } from "../frontend/node_modules/playwright/test";
import { installApiStubs } from "./srm-test-utils";

test.describe("SRM index card", () => {
  test("Business Suite index shows the exact SRM module card", async ({ page }) => {
    await installApiStubs(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const card = page.locator("div").filter({ hasText: "Sales & Inventory Management" }).first();
    await expect(card).toContainText("SRM");
    await expect(card).toContainText("Manage sales orders, contracts, billing, invoices, collections, and revenue profitability.");
    await expect(page.getByRole("link", { name: "Open SRM" })).toHaveAttribute("href", "/srm/login");
  });
});
