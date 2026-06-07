import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectHealthyFamRoute } from "./fam-test-utils";

test("FAM inventory items list and create form render", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await expectHealthyFamRoute(page, "/fam/inventory/items");
  await expect(page.getByRole("heading", { name: "Stock Items", exact: true })).toBeVisible();
  await expect(page.getByLabel("sku")).toBeVisible();
  await expect(page.getByRole("cell", { name: "SKU-001" })).toBeVisible();
  await page.getByRole("button", { name: "Save item" }).click();
  await expect(page.getByText("Stock item saved").first()).toBeVisible();
});
