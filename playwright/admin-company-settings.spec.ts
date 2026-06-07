import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10 } from "./phase10-test-utils";

test("admin company settings save tenant defaults", async ({ page }) => {
  await authenticatePhase10(page);
  await page.goto("/admin/company-settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Business Suite").first()).toBeVisible();
  await page.getByRole("button", { name: "Save default settings" }).click();
  await expect(page.getByText("Asia/Calcutta")).toBeVisible();
});
