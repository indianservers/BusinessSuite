import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM price books UI", () => {
  test("renders price book list and filters", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/price-books", "Price Books", "India Standard");
    await expect(page.getByText("INR").first()).toBeVisible();
  });
});
