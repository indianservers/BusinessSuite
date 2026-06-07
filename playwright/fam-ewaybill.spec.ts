import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM e-way bill page clearly shows not configured", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/ewaybill", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "E-Way Bill Readiness" })).toBeVisible();
  await expect(page.getByText("not configured").first()).toBeVisible();
});
