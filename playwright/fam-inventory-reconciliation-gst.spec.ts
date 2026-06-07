import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory GST reconciliation route renders HSN and GST readiness", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reconciliation/gst", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GST Reconciliation" })).toBeVisible();
  await expect(page.getByText("9983")).toBeVisible();
});
