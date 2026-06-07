import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM GSTR-3B page renders preparation framework", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/gstr3b", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GSTR-3B Framework" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Prepare" })).toBeVisible();
});
