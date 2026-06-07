import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory GRNI reconciliation route renders outstanding receipt evidence", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reconciliation/grni", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GRNI Reconciliation", exact: true })).toBeVisible();
  await expect(page.getByText("GRN-001")).toBeVisible();
});
