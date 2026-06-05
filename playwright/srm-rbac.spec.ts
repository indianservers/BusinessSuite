import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM RBAC routes", () => {
  test("Collection Executive can access collections and read-only settings", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    await expectHealthySrmRoute(page, "/srm/collections");
    await expectDenied(page, "/srm/invoices");
    await expectHealthySrmRoute(page, "/srm/settings");
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
  });

  test("Sales Executive is blocked from finance routes and can view settings read-only", async ({ page }) => {
    await authenticate(page, "srm_sales_executive");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await expectHealthySrmRoute(page, "/srm/engagements");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/profitability");
    await expectHealthySrmRoute(page, "/srm/settings");
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
  });

  test("Non-SRM employee cannot open SRM", async ({ page }) => {
    await authenticate(page, "employee");
    await expectDenied(page, "/srm");
  });
});
