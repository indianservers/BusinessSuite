import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin manages compliance and data retention rules", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/compliance", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("consent_required").first()).toBeVisible();
  await page.getByRole("button", { name: "Save consent policy" }).click();
  await expect(page.getByText("Compliance setting saved")).toBeVisible();
  await page.goto("/admin/data-retention", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Create retention rule" }).click();
  await expect(page.getByText("Retention rule saved")).toBeVisible();
});
