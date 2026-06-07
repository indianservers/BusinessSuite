import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";

test.describe("CRM quote RBAC UI metadata", () => {
  test("CRM roles expose quote and CPQ permission names", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/products", { waitUntil: "domcontentloaded" });
    const body = await page.evaluate(async () => {
      const response = await fetch("/api/v1/crm/roles", { headers: { Authorization: "Bearer crm-token" } });
      return response.json();
    });
    const admin = body.items.find((item: { key: string }) => item.key === "crm_admin");
    expect(admin.permissions).toContain("crm_quotes_approve");
    expect(admin.permissions).toContain("crm_quotes_convert_to_srm");
    expect(admin.permissions).toContain("crm_cpq_manage");
  });
});
