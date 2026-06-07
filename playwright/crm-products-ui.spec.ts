import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM products and services UI", () => {
  test("renders product and service catalogs", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/products", "Products", "CRM Enterprise");
    await expect(page.getByText("CRM-ENT").first()).toBeVisible();

    await expectCrmListPage(page, "/crm/services", "Services", "Implementation");
    await expect(page.getByText("IMPL-STD").first()).toBeVisible();
  });
});
