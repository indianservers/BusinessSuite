import {expect, test} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";
for (const entry of ["full", "quick", "mobile"] as const) {
  test(`${entry} deal capture creates related records and saves service lines`, async ({page}) => {
    await authenticateCrm(page);
    let saved: any;
    await page.route("**/api/v1/crm/deal-workspace/**", async route => {
      const path = new URL(route.request().url()).pathname;
      const payload = path.endsWith("query") ? {items: [], total: 0, pages: 1, can_manage: true, can_assign: true} : path.endsWith("summary") ? {counts: {}, currencies: [], stages: [], forecast: []} : path.endsWith("assignees") ? {items: [{id: 100, userId: 100, name: "Admin"}], total: 1, pages: 1} : {items: []};
      await route.fulfill({json: payload});
    });
    page.on("request", request => {const perPage = new URL(request.url()).searchParams.get("per_page");if (perPage) expect(Number(perPage)).toBeLessThanOrEqual(100);});
    await page.route("**/api/v1/crm/deals", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      saved = route.request().postDataJSON();
      await route.fulfill({status: 201, json: {id: 88, ...saved}});
    });
    for (const resource of ["companies", "contacts", "products", "services"]) await page.route(`**/api/v1/crm/${resource}`, async route => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({status: 201, json: {id: 88, ...route.request().postDataJSON()}});
    });
    if (entry === "mobile") await page.setViewportSize({width: 390, height: 844});
    await page.goto("/crm/deals", {waitUntil: "domcontentloaded"});
    if (entry === "quick") {
      await page.getByRole("button", {name: "New", exact: true}).click();
      await page.getByRole("menuitem", {name: /^Deal/}).click();
    } else await page.getByRole("button", {name: "Create deal", exact: true}).first().click();
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
    await dialog.getByRole("button", {name: "Create product", exact: true}).click();
    await page.getByPlaceholder("CRM Starter", {exact: true}).fill("New license");
    await page.getByPlaceholder("25000", {exact: true}).fill("125.50");
    await page.getByRole("button", {name: "Create", exact: true}).click();
    await expect(dialog.locator("tbody tr")).toHaveCount(2);
    await dialog.getByRole("button", {name: "Create service", exact: true}).click();
    await page.getByPlaceholder("Implementation", {exact: true}).fill("New setup");
    await page.getByPlaceholder("IMPL-STD", {exact: true}).fill("NEW-SETUP");
    await page.getByPlaceholder("5000", {exact: true}).fill("50");
    await page.getByRole("button", {name: "Create", exact: true}).click();
    await expect(dialog.locator("tbody tr")).toHaveCount(3);
    if (entry === "mobile") expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    await page.screenshot({path: `test-results/deal-${entry}.png`, fullPage: true});
    await dialog.getByRole("button", {name: "Create Deal", exact: true}).click();
    await expect.poll(() => saved).toBeTruthy();
    expect(saved.company_id).toBe(88);
    expect(saved.contact_id).toBe(88);
    expect(saved.catalog_items).toEqual([expect.objectContaining({kind: "service", item_id: 1, quantity: 2}), expect.objectContaining({kind: "product", item_id: 88, unit_price: 125.5}), expect.objectContaining({kind: "service", item_id: 88, unit_price: 50})]);
  });
}
