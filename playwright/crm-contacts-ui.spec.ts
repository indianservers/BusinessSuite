import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM contacts UI", () => {
  test("renders contact list and contact detail with lifecycle data", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/contacts", "Contacts", "Nisha Rao");

    await page.goto("/crm/contacts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Nisha Rao" })).toBeVisible();
    await expect(page.getByText("Founder").first()).toBeVisible();
    await expect(page.getByText("Customer").first()).toBeVisible();
  });
});
