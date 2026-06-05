import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthySrmRoute, srmRoutes } from "./srm-test-utils";

test.describe("SRM role-based UAT", () => {
  test("SRM Admin can access all SRM routes and major actions", async ({ page }) => {
    await authenticate(page, "srm_admin");
    for (const route of srmRoutes) await expectHealthySrmRoute(page, route);
    await page.goto("/srm/sales-orders", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Submit" })).toBeVisible();
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Approve Invoice" })).toBeVisible();
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Save Settings" })).toBeVisible();
  });

  test("Sales Manager and Sales Executive stay in commercial sales lanes", async ({ page }) => {
    await authenticate(page, "srm_sales_manager");
    for (const route of ["/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/billing-plans"]) await expectHealthySrmRoute(page, route);
    await expectDenied(page, "/srm/invoices");

    await authenticate(page, "srm_sales_executive");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/collections");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
  });

  test("Finance, Revenue, Collection, Owner, Viewer, and Employee access matches role intent", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    for (const route of ["/srm/invoices", "/srm/collections", "/srm/profitability", "/srm/reports"]) await expectHealthySrmRoute(page, route);

    await authenticate(page, "srm_revenue_manager");
    for (const route of ["/srm/revenue-recognition", "/srm/profitability", "/srm/reports"]) await expectHealthySrmRoute(page, route);

    await authenticate(page, "srm_collection_executive");
    await expectHealthySrmRoute(page, "/srm/collections");
    await expectDenied(page, "/srm/invoices");

    await authenticate(page, "srm_business_owner");
    for (const route of ["/srm/dashboard", "/srm/reports", "/srm/profitability"]) await expectHealthySrmRoute(page, route);
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Approve Invoice" })).toHaveCount(0);

    await authenticate(page, "srm_viewer");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await expectHealthySrmRoute(page, "/srm/reports");
    await expectDenied(page, "/srm/profitability");

    await authenticate(page, "employee");
    await expectDenied(page, "/srm");
  });
});
