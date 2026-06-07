import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory COGS reconciliation route renders matched stock issue evidence", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reconciliation/cogs", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "COGS Reconciliation", exact: true })).toBeVisible();
  await expect(page.getByText("MOV-OUT-001")).toBeVisible();
});
