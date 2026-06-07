import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory audit page shows audited stock activity", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/audit", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Inventory Audit" })).toBeVisible();
  await expect(page.getByText("inventory movement", { exact: false })).toBeVisible();
});
