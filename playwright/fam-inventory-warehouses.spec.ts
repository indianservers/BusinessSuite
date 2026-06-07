import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory warehouses render and save", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/warehouses");
  await expect(page.getByRole("heading", { name: "Warehouses" })).toBeVisible();
  await expect(page.getByLabel("warehouse code")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Inventory master saved").first()).toBeVisible();
});
