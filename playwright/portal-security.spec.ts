import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticatePhase10, installPhase10ApiStubs } from "./phase10-test-utils";

test.describe("portal security", () => {
  test("portal routes do not grant employee CRM access", async ({ page }) => {
    await installPhase10ApiStubs(page);
    await page.goto("/portal/customer", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Customer Portal" })).toBeVisible();
    await page.goto("/crm", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/crm\/login|\/login/);
  });

  test("non-SaaS employee is blocked from developer routes", async ({ page }) => {
    await authenticatePhase10(page, "employee");
    await page.goto("/developer", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
  });
});
