import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM contacts UI", () => {
  for (const width of [1440, 390]) {
    test(`contact 360 popup and visible row actions at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await authenticateCrm(page);
      await expectCrmListPage(page, "/crm/contacts", "Contacts", "Nisha Rao");
      const row = page.getByRole("row").filter({ has: page.getByRole("button", { name: "View Nisha Rao", exact: true }) });
      const view = row.getByRole("button", { name: "View Nisha Rao", exact: true });
      const edit = row.getByRole("button", { name: "Edit Nisha Rao", exact: true });
      await row.scrollIntoViewIfNeeded();
      await expect(view).toBeInViewport();
      await expect(edit).toBeInViewport();
      await view.click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("tab", { name: "Work & Relationships" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await row.getByRole("button", { name: "Nisha Rao", exact: true }).dblclick();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("tab", { name: "Notes & Activity" })).toBeVisible();
      await page.keyboard.press("Escape");
      await edit.click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Edit contact", exact: true })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });
  }
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
