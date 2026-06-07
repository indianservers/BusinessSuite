import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin audit log page renders auditable actions", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/audit-logs", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("profile_created")).toBeVisible();
  await expect(page.getByRole("button", { name: "Export audit CSV" })).toBeVisible();
});
