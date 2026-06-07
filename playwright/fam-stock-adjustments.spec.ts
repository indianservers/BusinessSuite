import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM stock adjustment page posts adjustment", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/stock-adjustments");
  await expect(page.getByRole("heading", { name: "Stock Adjustments" })).toBeVisible();
  await page.getByRole("button", { name: "Post adjustment" }).click();
  await expect(page.getByText("Adjustment posted").first()).toBeVisible();
});
