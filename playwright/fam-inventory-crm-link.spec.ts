import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory CRM link page shows product catalog linkage", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/crm-link", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "CRM Inventory Link" })).toBeVisible();
  await expect(page.getByText("SKU-001")).toBeVisible();
});
