import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin creates role hierarchy record", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/roles", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("Sales Manager").first()).toBeVisible();
  await page.getByRole("button", { name: "Create role" }).click();
  await expect(page.getByText("Role created")).toBeVisible();
});
