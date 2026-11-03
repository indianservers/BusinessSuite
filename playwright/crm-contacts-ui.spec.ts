import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM contacts UI", () => {
  test("renders contact list and contact detail with lifecycle data", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/contacts", "Contacts", "Nisha Rao");

    await page.goto("/crm/contacts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Nisha Rao" })).toBeVisible();
    await page.getByRole("tab", {name:"Details",exact:true}).click();
    await expect(page.getByRole("tabpanel",{name:"Details",exact:true}).getByText("Founder").first()).toBeVisible();
    await expect(page.getByRole("tabpanel",{name:"Details",exact:true}).getByText("Customer").first()).toBeVisible();
  });
});
