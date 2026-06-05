import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate, expectDenied, expectHealthySrmRoute } from "./srm-test-utils";

const commercialRoutes = ["/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/billing-plans"];

test.describe("SRM commercial workflow RBAC", () => {
  test("SRM Admin and Sales Manager can use commercial workflow routes", async ({ page }) => {
    await authenticate(page, "srm_admin");
    for (const route of commercialRoutes) await expectHealthySrmRoute(page, route);
    await page.goto("/srm/sales-orders", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Submit" })).toBeVisible();

    await authenticate(page, "srm_sales_manager");
    for (const route of commercialRoutes) await expectHealthySrmRoute(page, route);
  });

  test("Sales Executive stays in assigned commercial lane and cannot access finance/settings actions", async ({ page }) => {
    await authenticate(page, "srm_sales_executive");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await expectHealthySrmRoute(page, "/srm/engagements");
    await expectDenied(page, "/srm/invoices");
    await expectDenied(page, "/srm/collections");
    await page.goto("/srm/settings", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Read-only mode", { exact: false })).toBeVisible();
  });

  test("Owner and Viewer have read-only behavior while non-SRM employee is blocked", async ({ page }) => {
    await authenticate(page, "srm_business_owner");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Approve Invoice" })).toHaveCount(0);

    await authenticate(page, "srm_viewer");
    await expectHealthySrmRoute(page, "/srm/sales-orders");
    await page.goto("/srm/sales-orders", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: "Submit" })).toHaveCount(0);

    await authenticate(page, "employee");
    for (const route of commercialRoutes) await expectDenied(page, route);
  });
});
