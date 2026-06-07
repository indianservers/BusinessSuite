import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin duplicate management creates rule scans and logs merge", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/duplicates", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("Lead email duplicate").first()).toBeVisible();
  await page.getByRole("button", { name: "Create duplicate rule" }).click();
  await page.getByRole("button", { name: "Scan duplicates" }).click();
  await page.getByRole("button", { name: "Record merge" }).click();
  await expect(page.getByText("Merge log recorded")).toBeVisible();
});
