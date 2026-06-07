import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM stock transfer page posts transfer", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/stock-transfers");
  await expect(page.getByRole("heading", { name: "Stock Transfers" })).toBeVisible();
  await page.getByRole("button", { name: "Post transfer" }).click();
  await expect(page.getByText("Transfer posted").first()).toBeVisible();
});
