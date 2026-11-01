import {expect, test} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";
for (const entry of ["full", "quick"] as const) {
  test(`${entry} deal capture creates related records and saves service lines`, async ({page}) => {
    await authenticateCrm(page);
    let saved: any;
    await page.route("**/api/v1/crm/deals", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      saved = route.request().postDataJSON();
      await route.fulfill({status: 201, json: {id: 88, ...saved}});
    });
    for (const resource of ["companies", "contacts"]) await page.route(`**/api/v1/crm/${resource}`, async route => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({status: 201, json: {id: 88, ...route.request().postDataJSON()}});
    });
    await page.goto("/crm/deals", {waitUntil: "domcontentloaded"});
    if (entry === "quick") {
      await page.getByRole("button", {name: "New", exact: true}).click();
      await page.getByRole("menuitem", {name: /^Deal/}).click();
    } else await page.getByRole("button", {name: "Create deal", exact: true}).click();
    const dialog = page.getByRole("dialog", {name: "Create deal", exact: true});
    await expect(dialog.getByRole("heading", {name: "Create deal", exact: true})).toBeVisible();
    await dialog.getByPlaceholder("Enter deal name...").fill("Catalog opportunity");
    await dialog.locator("label").filter({hasText: /^Stage/}).locator("select").selectOption("1");
    await dialog.getByRole("button", {name: "Add company", exact: true}).click();
    await page.getByPlaceholder("Acme India").fill("Inline company");
    await page.getByRole("button", {name: "Create", exact: true}).click();
    await expect(dialog.locator("label").filter({hasText: /^Company/}).locator("select")).toHaveValue("88");
    await dialog.getByRole("button", {name: "Add contact", exact: true}).click();
    await page.getByPlaceholder("Jane Shah").fill("Inline contact");
    await page.getByRole("button", {name: "Create", exact: true}).click();
    await expect(dialog.locator("label").filter({hasText: /^Contact/}).locator("select")).toHaveValue("88");
    await dialog.getByRole("button", {name: "Add line", exact: true}).click();
    const row = dialog.locator("tbody tr").first();
    await row.locator("select").selectOption("service:1");
    await row.locator('input[type="number"]').nth(1).fill("2");
    await page.screenshot({path: `test-results/deal-${entry}.png`, fullPage: true});
    await dialog.getByRole("button", {name: "Save", exact: true}).click();
    await expect.poll(() => saved).toBeTruthy();
    expect(saved.company_id).toBe(88);
    expect(saved.contact_id).toBe(88);
    expect(saved.catalog_items).toEqual([expect.objectContaining({kind: "service", item_id: 1, quantity: 2})]);
  });
}
