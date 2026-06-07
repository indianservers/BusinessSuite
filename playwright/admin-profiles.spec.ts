import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin creates CRM profile and permission set", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/profiles", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByRole("main").getByText("CRM Admin", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create profile" }).click();
  await expect(page.getByText("Profile created")).toBeVisible();
});
