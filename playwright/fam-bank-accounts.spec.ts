import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM bank accounts", () => {
  test("renders bank account master and create action", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/bank-accounts");

    await expect(page.getByRole("heading", { name: "Bank Accounts", exact: true })).toBeVisible();
    await expect(page.getByText("HDFC Bank")).toBeVisible();
    await page.getByRole("button", { name: "Save bank account" }).click();
    await expect(page.getByText("Bank account saved", { exact: true }).first()).toBeVisible();
  });
});

