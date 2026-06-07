import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM GST sales register page renders", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/gst/sales-register", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "GST Sales Register" })).toBeVisible();
  await expect(page.getByText("Sales GST register")).toBeVisible();
});
