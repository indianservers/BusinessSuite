import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory valuation renders weighted average position", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/valuation");
  await expect(page.getByRole("heading", { name: "Inventory Valuation" })).toBeVisible();
  await expect(page.getByText("Total value")).toBeVisible();
  await expect(page.getByRole("cell", { name: "SKU-001" })).toBeVisible();
});
