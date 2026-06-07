import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM core RBAC", () => {
  test("exposes Phase 1 CRM roles and renders CRM routes for an admin", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/dashboard", { waitUntil: "domcontentloaded" });
    const roles = await page.evaluate(async () => {
      const response = await fetch("/api/v1/crm/roles");
      return response.json();
    });
    expect(roles.items.map((item: { key: string }) => item.key)).toEqual(expect.arrayContaining(["crm_admin", "sales_executive", "business_owner", "non_crm_employee"]));

    await expect(page.getByRole("heading", { name: "VyaparaCRM" })).toBeVisible();
  });
});
