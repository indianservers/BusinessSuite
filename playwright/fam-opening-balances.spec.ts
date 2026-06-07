import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM opening balances", () => {
  test("opening balance page supports balanced posting action", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/opening-balances");
    await expect(page.getByText("Difference")).toBeVisible();
    await page.getByRole("button", { name: "Post balanced opening" }).click();
    await expect(page.getByText("Opening balances posted", { exact: true }).first()).toBeVisible();
  });
});
