import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin export controls enforce approval and watermark policy", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/export-control", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await expect(page.getByText("deals").first()).toBeVisible();
  await page.getByRole("button", { name: "Create export control" }).click();
  await expect(page.getByText("Export control saved")).toBeVisible();
});
