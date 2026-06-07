import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin creates record sharing rule and manual share", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/record-sharing", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("Share enterprise deals").first()).toBeVisible();
  await page.getByRole("button", { name: "Create sharing rule" }).click();
  await expect(page.getByText("Sharing rule saved")).toBeVisible();
  await page.getByRole("button", { name: "Manual share" }).click();
  await expect(page.getByText("Record shared")).toBeVisible();
});
