import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("CEO can view audit but not mutate profile administration", async ({ page }) => {
  await authenticateAdminSecurity(page, "ceo");
  await page.goto("/admin/audit-logs", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await page.goto("/admin/profiles", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
});

test("non CRM admin employee cannot open admin security routes", async ({ page }) => {
  await authenticateAdminSecurity(page, "employee");
  await page.goto("/admin/security", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
});
