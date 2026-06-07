import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthyFamRoute } from "./fam-test-utils";

test.describe("FAM RBAC", () => {
  test("FAM Admin can open settings and non-FAM employee is denied", async ({ page }) => {
    await authenticate(page, "fam_admin");
    await expectHealthyFamRoute(page, "/fam/settings");
    await authenticate(page, "employee");
    await expectDenied(page, "/fam");
  });

  test("auditor can open audit but cannot open settings", async ({ page }) => {
    await authenticate(page, "auditor");
    await expectHealthyFamRoute(page, "/fam/audit");
    await page.goto("/fam/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("403 Access Denied", { exact: false })).toBeVisible();
  });
});
