import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM GSTR-1 page renders preparation framework", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/gstr1", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GSTR-1 Framework" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Prepare" })).toBeVisible();
});
