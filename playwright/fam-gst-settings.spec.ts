import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM GST settings page renders provider readiness", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GST Settings" })).toBeVisible();
  await expect(page.getByText("not configured").first()).toBeVisible();
});
