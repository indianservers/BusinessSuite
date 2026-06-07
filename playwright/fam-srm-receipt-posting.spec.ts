import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM SRM receipt posting", () => {
  test("posts a receipt and allocation from dashboard controls", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/integrations/srm");

    await page.getByRole("button", { name: "Post SRM receipt" }).click();
    await expect(page.getByText("Accounting integration updated", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Post allocation" }).click();
    await expect(page.getByText("Accounting integration updated", { exact: true }).first()).toBeVisible();
  });
});
