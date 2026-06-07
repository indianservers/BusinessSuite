import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory GL reconciliation route renders valuation to ledger status", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reconciliation/gl", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Inventory GL Reconciliation" })).toBeVisible();
  await expect(page.getByText("matched").first()).toBeVisible();
});
