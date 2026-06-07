import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory reconciliation page shows GL and SRM checks", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reconciliation", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Inventory Reconciliation" })).toBeVisible();
  await expect(page.getByText("Inventory to GL")).toBeVisible();
  await expect(page.getByText("Inventory to SRM")).toBeVisible();
  await expect(page.getByText(/duplicate stock deduction/i)).toBeVisible();
});
