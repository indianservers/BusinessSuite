import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM GST rates page renders", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/rates", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GST Rates" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
});
