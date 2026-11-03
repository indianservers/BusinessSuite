import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM accounts UI", () => {
  test("renders account list and account detail with related CRM records", async ({ page }) => {
    await authenticateCrm(page);
    await page.goto("/crm/accounts", {waitUntil:"domcontentloaded"});
    await expect(page.getByRole("heading", {name:"Customers",exact:true})).toBeVisible();
    await expect(page.getByText("Acme India").first()).toBeVisible();

    await page.goto("/crm/accounts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Acme India" })).toBeVisible();
    await expect(page.getByText("Software").first()).toBeVisible();
    await page.getByRole("tab", {name:"More details",exact:true}).click();
    await page.getByRole("combobox", {name:"CRM record information section",exact:true}).selectOption("activity");
    await expect(page.getByRole("heading", { name: "Activity Timeline" })).toBeVisible();
  });
});
