import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM voucher page keeps GST-ready voucher UI stable", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/vouchers/new", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "New Voucher" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Save|Create|Post/i }).first()).toBeVisible();
});
