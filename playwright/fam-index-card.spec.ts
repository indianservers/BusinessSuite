import { expect, test } from "../frontend/node_modules/playwright/test";
import { installApiStubs } from "./fam-test-utils";

test.describe("FAM index card", () => {
  test("Business Suite index shows the FAM module card", async ({ page }) => {
    await installApiStubs(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const card = page
      .getByRole("heading", { name: "Finance & Accounting Management" })
      .locator("xpath=ancestor::div[contains(@class, 'overflow-hidden')][1]");
    await expect(card).toContainText("FAM");
    await expect(card).toContainText("Manage financial settings, chart of accounts, ledgers, opening balances, branches, cost centers, and audit-ready books.");
    await expect(card.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/fam/login");
  });
});
