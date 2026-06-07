import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM stock summary renders item balances", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/stock-summary");
  await expect(page.getByRole("heading", { name: "Stock Summary" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SKU-001" })).toBeVisible();
});
