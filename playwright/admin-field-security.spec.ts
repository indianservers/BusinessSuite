import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin configures field security and sees backend validation", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/field-security", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("annual_revenue").first()).toBeVisible();
  await page.getByRole("button", { name: "Add read-only rule" }).click();
  await expect(page.getByText("Field rule saved")).toBeVisible();
  await page.getByRole("button", { name: "Validate field update" }).click();
  await expect(page.getByText("Field annual_revenue is read-only", { exact: false })).toBeVisible();
});
