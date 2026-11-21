import { test, expect } from "../frontend/node_modules/playwright/test";
import { authenticateCrm } from "./crm-core-test-utils";
for (const width of [390,1440]) {
  test(`calendar controls and report discovery at ${width}px`, async ({page}) => {
    await authenticateCrm(page);
    await page.route("**/api/v1/crm/report-builder", route => route.fulfill({json:[]}));
    await page.setViewportSize({width,height:844});
    await page.goto("/crm/calendar");
    await expect(page.getByRole("heading",{name:"CRM calendar",exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:width===390?"Agenda":"Month",exact:true})).toHaveAttribute("aria-pressed","true");
    await page.getByRole("button",{name:"Week",exact:true}).click();
    await expect(page.getByRole("button",{name:"Week",exact:true})).toHaveAttribute("aria-pressed","true");
    if(width===390) {
      const scroll = page.locator(".crm-calendar-grid-scroll");
      await expect.poll(() => scroll.evaluate(node => node.scrollWidth - node.clientWidth)).toBeGreaterThan(0);
    }
    await page.goto("/crm/reports");
    await expect(page.getByRole("heading",{name:"Reports and insights",level:1})).toBeVisible();
    const search=page.getByRole("textbox",{name:"Search report directory"});
    await search.fill("no such report");
    await expect(page.getByText("No reports match. Try another search or category.")).toBeVisible();
    await search.fill("Sales funnel");
    await expect(page.getByRole("link",{name:/Sales funnel/}).first()).toHaveAttribute("href","/crm/funnel");
  });
}

test("catalog type controls fit a phone viewport", async ({ page }) => {
  await authenticateCrm(page);
  await page.route("**/api/v1/catalog/items?*", route => route.fulfill({
    json: { items: [], total: 0, pages: 1, permissions: { product: true, service: true } },
  }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/crm/products-services");
  const typeControls = page.getByRole("group", { name: "Catalog type" });
  await expect(typeControls).toBeVisible();
  await expect.poll(() => page.locator(".ws-crm .ws-page-content").evaluate(
    node => node.scrollWidth - node.clientWidth,
  )).toBeLessThanOrEqual(2);
  await typeControls.getByRole("button", { name: "Services", exact: true }).click();
  await expect(typeControls.getByRole("button", { name: "Services", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
});
