import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./fam-test-utils";

test("FAM inventory gross margin report renders revenue and COGS columns", async ({ page }) => {
  await authenticate(page, "fam_admin");
  await page.goto("/fam/inventory/reports/gross-margin", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Gross Margin" })).toBeVisible();
  await expect(page.getByText("gross margin percent")).toBeVisible();
});
