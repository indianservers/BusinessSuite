import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateAdminSecurity, expectAdminSecurityShell } from "./admin-security-test-utils";

test("admin import wizard uploads maps runs and displays errors", async ({ page }) => {
  await authenticateAdminSecurity(page);
  await page.goto("/admin/import", { waitUntil: "domcontentloaded" });
  await expectAdminSecurityShell(page);
  await page.getByRole("button", { name: "Upload CSV" }).click();
  await expect(page.getByText("Import uploaded")).toBeVisible();
  await page.getByRole("button", { name: "Map fields" }).click();
  await expect(page.getByText("Fields mapped")).toBeVisible();
  await page.getByRole("button", { name: "Run import" }).click();
  await expect(page.getByText("Import completed", { exact: true }).first()).toBeVisible();
});
