import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM stock out page posts outward stock movement", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/stock-out");
  await expect(page.getByRole("heading", { name: "Stock Out", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Post movement" }).click();
  await expect(page.getByText("Stock movement posted").first()).toBeVisible();
});
