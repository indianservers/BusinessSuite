import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM expenses", () => {
  test("creates and posts operational expense claims", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/expenses");
    await expect(page.getByRole("cell", { name: "EXP-001" })).toBeVisible();
    await page.getByRole("button", { name: /Post EXP-001/i }).click();
    await expect(page.getByText("Expense posted").first()).toBeVisible();

    await expectHealthyFamRoute(page, "/fam/expenses/new");
    await expect(page.getByRole("heading", { name: "Expense lines" })).toBeVisible();
    await page.getByRole("button", { name: /Save expense claim/i }).click();
    await expect(page.getByText("Expense claim saved").first()).toBeVisible();
  });
});
