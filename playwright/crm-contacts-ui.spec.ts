import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticateCrm, expectCrmListPage } from "./crm-core-test-utils";

test.describe("CRM contacts UI", () => {
  for (const width of [1440, 390]) {
    test(`contact 360 popup and visible row actions at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await authenticateCrm(page);
      await expectCrmListPage(page, "/crm/contacts", "Contacts", "Nisha Rao");
      const view = page.getByRole("button", {name: "Open Nisha Rao popup", exact: true});
      const edit = page.getByRole("button", {name: "Edit Nisha Rao", exact: true});
      await view.scrollIntoViewIfNeeded();
      await expect(view).toBeInViewport();
      await edit.scrollIntoViewIfNeeded();
      await expect(edit).toBeInViewport();
      await view.click();
      const popup = page.getByRole("dialog", {name: "Record 360"});
      await expect(popup).toBeVisible();
      await popup.getByRole("button", {name: "Close dialog"}).click();
      await expect(popup).toHaveCount(0);
      if (width >= 768) {
        await page.getByRole("button", { name: "Nisha Rao", exact: true }).dblclick();
        await expect(popup).toBeVisible();
        await popup.getByRole("button", {name: "Close dialog"}).click();
      }
      await edit.click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Edit contact", exact: true })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      if (width < 768) {
        await page.getByRole("button", { name: /filters/i }).click();
        const filters = page.getByRole("dialog", { name: "Contact filters" });
        await expect(filters.getByText("Lifecycle stage")).toBeVisible();
        await filters.getByRole("button", { name: "Done" }).click();
        await expect(filters).toHaveCount(0);
        await page.getByRole("link", { name: "Nisha Rao", exact: true }).click();
        await expect(page).toHaveURL(/\/crm\/contacts\/1$/);
        await expect(page.getByRole("heading", { name: "Nisha Rao", level: 1 })).toBeVisible();
      }
    });
  }
  test("renders contact list and contact detail with lifecycle data", async ({ page }) => {
    await authenticateCrm(page);
    await expectCrmListPage(page, "/crm/contacts", "Contacts", "Nisha Rao");

    await page.goto("/crm/contacts/1", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Nisha Rao", level: 1 })).toBeVisible();
    await page.locator("summary").getByText("Details & related records", {exact:true}).click();
    await page.getByRole("tab", {name:"Details",exact:true}).click();
    const details = page.getByRole("tabpanel", {name:"Details",exact:true});
    await expect(details.getByText("Founder", {exact:true})).toBeVisible();
    await expect(details.getByText("Customer", {exact:true})).toBeVisible();
  });
});
