import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM e-invoice page clearly shows not configured", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/einvoice", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "E-Invoice Readiness" })).toBeVisible();
  await expect(page.getByText("not configured").first()).toBeVisible();
});
