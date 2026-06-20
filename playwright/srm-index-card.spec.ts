import { expect, test } from "../frontend/node_modules/playwright/test";
import { installApiStubs } from "./srm-test-utils";

test.describe("SRM index card", () => {
  test("Business Suite index shows the exact SRM module card", async ({ page }) => {
    await installApiStubs(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const card = page.locator("div").filter({ hasText: "Sales & Inventory Management" }).first();
    await expect(card).toContainText("Sales, Inventory & POS");
    await expect(card).toContainText("Sales + Inventory 1.02");
    await expect(card).toContainText("Manage sales orders, POS, products, stock, delivery, billing, invoices, collections, and profitability.");
    await expect(page.getByRole("link", { name: "Open Sales, Inventory & POS" })).toHaveAttribute("href", "/srm/login");
    await expect(page.getByRole("heading", { name: /^Inventory$/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Inventory login/i })).toHaveCount(0);
    const footer = page.locator("footer");
    await expect(footer.getByText("Business Suite 1.01")).toBeVisible();
    await expect(footer.getByText("CRM 1.01")).toBeVisible();
    await expect(footer.getByText("Sales + Inventory 1.02")).toBeVisible();
  });

  test("legacy inventory login redirects to Sales and Inventory login", async ({ page }) => {
    await installApiStubs(page);
    await page.goto("/inventory/login", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/srm\/login$/);
    await expect(page.getByText("Sales, Inventory and POS")).toBeVisible();
  });
});
