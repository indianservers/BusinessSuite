import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM quotes UI", () => {
  test("renders quote list and opens builder route", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/quotes", "Quotes", "QT-001");
    await page.goto("/crm/quotes/1", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/crm\/quotes\/1/);
    await expect(page.getByRole("heading", { name: "Quote Builder" })).toBeVisible();
  });
});
