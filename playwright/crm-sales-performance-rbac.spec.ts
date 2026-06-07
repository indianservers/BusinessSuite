import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM sales performance RBAC Phase 2", () => {
  test("renders sales performance and exposes Phase 2 role permissions", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/sales-performance", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Sales Performance", exact: true })).toBeVisible();
    await expect(page.getByText("Ananya Rao")).toBeVisible();

    const roles = await page.evaluate(async () => {
      const response = await fetch("/api/v1/crm/roles");
      return response.json();
    });
    const admin = roles.items.find((item: { key: string }) => item.key === "crm_admin");
    expect(admin.permissions).toEqual(expect.arrayContaining(["crm_pipeline_manage", "crm_forecast_manage", "crm_targets_manage", "crm_territory_manage", "crm_sales_performance_view"]));
  });
});
