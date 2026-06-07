import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM SRM invoice posting", () => {
  test("posts an invoice from dashboard controls", async ({ page }) => {
    await authenticate(page, "finance_manager");
    await expectHealthyFamRoute(page, "/fam/integrations/srm");

    await page.getByRole("button", { name: "Post SRM invoice" }).click();
    await expect(page.getByText("Accounting integration updated", { exact: true }).first()).toBeVisible();
  });
});
