import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory GRNI page renders goods received not invoiced rows", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/grni", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GRNI", exact: true })).toBeVisible();
  await expect(page.getByText(/Inventory GRNI reconciliation/i)).toBeVisible();
  await expect(page.getByText("GRN-001")).toBeVisible();
});
