import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM accounts UI", () => {
  test("renders account list and account detail with related CRM records", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/accounts", "Accounts", "Acme India");

    await page.goto("/crm/accounts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Acme India" })).toBeVisible();
    await expect(page.getByText("Software").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Activity Timeline" })).toBeVisible();
  });
});
