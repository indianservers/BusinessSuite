import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory HSN summary report renders grouped stock value", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reports/hsn-summary", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "HSN Summary" })).toBeVisible();
  await expect(page.getByText("9983")).toBeVisible();
});
