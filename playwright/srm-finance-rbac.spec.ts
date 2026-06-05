import { test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthySrmRoute } from "./srm-test-utils";

test.describe("SRM finance RBAC", () => {
  test("business owner can view revenue dashboards and employee is blocked from finance routes", async ({ page }) => {
    await authenticate(page, "srm_business_owner");
    await expectHealthySrmRoute(page, "/srm/invoices");
    await expectHealthySrmRoute(page, "/srm/collections");
    await expectHealthySrmRoute(page, "/srm/profitability");

    await authenticate(page, "employee");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/collections");
    await expectDenied(page, "/srm/profitability");
  });
});
