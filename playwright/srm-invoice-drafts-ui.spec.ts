import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

test.describe("SRM invoice draft UI", () => {
  test("generates invoice drafts from supported sources and shows duplicate prevention errors", async ({ page }) => {
    await authenticate(page, "srm_finance_manager");
    await page.route("**/api/v1/master-data/companies**",route=>route.fulfill({json:new URL(route.request().url()).pathname.endsWith("/1")?{id:1,name:"QA customer",roles:["Customer"]}:{items:[{id:1,name:"QA customer",roles:["Customer"]}],total:1,canCreate:true}}));
    await page.goto("/srm/invoice-drafts", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Invoice Drafts", level: 1 })).toBeVisible();
    await expect(page.getByText("Source Evidence")).toBeVisible();

    for (const label of ["Engagement ID", "Billing milestone ID", "PMS milestone ID", "Sales order ID", "Timesheet engagement ID"]) {
      await page.getByLabel(label, { exact: true }).first().fill("1");
    }
    await page.getByLabel("Time log IDs", { exact: true }).fill("901");
    await page.getByRole("button", { name: "Draft from Engagement" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Engagement draft completed");

    await page.getByRole("button", { name: "Draft from Billing Milestone" }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Billing milestone draft completed");

    const sources=page.getByRole("heading",{name:"Generate Invoice From Source",exact:true}).locator("../..");
    if(!await sources.getByRole("button",{name:"Draft from PMS Milestone",exact:true}).isVisible())await sources.getByRole("button",{name:"More actions",exact:true}).click();
    await sources.getByRole("button", { name: "Draft from PMS Milestone",exact:true }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("PMS milestone draft completed");

    if(!await sources.getByRole("button",{name:"Draft from Timesheets",exact:true}).isVisible())await sources.getByRole("button",{name:"More actions",exact:true}).click();
    await sources.getByRole("button", { name: "Draft from Timesheets",exact:true }).click();
    await expect(page.getByRole("main").getByRole("status")).toContainText("Timesheet draft completed");

    const composer=page.getByRole("heading",{name:"Invoice Template and Preview",exact:true}).locator("../..");
    await composer.getByRole("button",{name:"Additional details",exact:true}).click();
    await page.getByRole("combobox",{name:"Search shared customer",exact:true}).fill("QA");
    await page.getByRole("option").filter({hasText:"QA customer"}).click();
    await composer.getByRole("button",{name:"More details",exact:true}).click();
    await page.getByLabel("Line description", { exact: true }).fill("Implementation service");
    await page.getByLabel("Unit price", { exact: true }).fill("100");
    await page.getByRole("button", { name: "Create Invoice", exact: true }).click();
    await expect(page.getByRole("main").getByRole("status").filter({ hasText: "Manual invoice created" })).toBeVisible();

    await page.route("**/api/v1/srm/invoices/draft-from-sales-order/1", async (route) => {
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Invoice already drafted for this source" }) });
    });
    await page.getByRole("button", { name: "Draft from Sales Order" }).click();
    await expect(page.getByRole("main").getByRole("status").filter({ hasText: "Invoice already drafted for this source" })).toBeVisible();
  });
});
