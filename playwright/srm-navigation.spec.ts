import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";
import { navigationOperationPath } from "../frontend/src/lib/navigation-workspaces";

test.describe("SRM navigation", () => {
  test("merged menu has one entry per workspace and no duplicate destinations", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard");
    const menu = page.getByRole("navigation", { name: "Module navigation", exact: true });
    await menu.getByRole("button", { name: "Expand all menu categories" }).click();
    for (const label of ["Customers & suppliers", "Sales orders & contracts", "POS sessions & returns", "Products & pricing", "Stock & warehouses", "Stock movements", "Purchasing", "Invoices & payments", "Sales reports", "Stock reports"]) {
      await expect(menu.getByRole("link", { name: label, exact: true })).toHaveCount(1);
      await expect(menu.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
    const links = await menu.locator(".module-menu-categories a[href]").evaluateAll(nodes => nodes.map(node => node.getAttribute("href")!));
    const destinations = links.map(navigationOperationPath);
    expect(new Set(destinations).size).toBe(destinations.length);
    await menu.getByRole("link", { name: "Sales orders & contracts", exact: true }).click();
    await expect(page.getByRole("tablist", { name: "Sales orders & contracts operations" })).toBeVisible();
    const register=page.waitForRequest(request=>new URL(request.url()).pathname==='/api/v1/srm/documents/contracts'&&request.method()==='GET');
    register.catch(()=>{});
    await page.getByRole("tab", { name: "Contracts", exact: true }).click();
    expect(new URL((await register).url()).pathname).toBe('/api/v1/srm/documents/contracts');
    await expect(page).toHaveURL(/operation=%2Fsrm%2Fcontracts/);
    await expect(menu.getByRole("link", { name: "Sales orders & contracts", exact: true })).toHaveAttribute("aria-current", "page");
    await page.reload();
    await expect(page.getByRole("tab", { name: "Contracts", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.goBack();
    await expect(page.getByRole("tab", { name: /^Sales orders$/i, exact: true })).toHaveAttribute("aria-selected", "true");
  });

  test("shared catalog and supplier links render the merged tabs", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/common/catalog?module=srm");
    await expect(page.getByRole("tablist", { name: "Products & pricing operations" })).toBeVisible();
    await page.getByRole("tab", { name: "Price Lists", exact: true }).click();
    await expect(page).toHaveURL(/\/common\/catalog\?module=srm&operation=%2Fsrm%2Finventory%2Fprice-lists/);
    await expect(page.locator('[id^="operation-panel-"]:visible').getByRole("heading", { name: /Price Lists/i }).first()).toBeVisible({timeout:30_000});
    await page.reload();
    await expect(page.getByRole("tab", { name: "Price Lists", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.goto("/common/vendors?module=srm");
    await expect(page).toHaveURL(/\/common\/customers\?module=srm&operation=%2Fsrm%2Fvendors/);
    await expect(page.getByRole("tab", { name: "Vendors", exact: true })).toHaveAttribute("aria-selected", "true");
    await page.goto("/srm/services");
    await expect(page).toHaveURL(/kind=service/);
    await expect(page.locator('[id^="operation-panel-"]:visible')).toHaveCount(1);
  });

  test("collection role retains payments and cannot open finance through an operation query", async ({ page }) => {
    await authenticate(page, "srm_collection_executive");
    const deniedRegisters:string[]=[];
    page.on('request',request=>{if(new URL(request.url()).pathname==='/api/v1/srm/documents/invoices')deniedRegisters.push(request.url());});
    await page.goto("/srm/collections?operation=/srm/invoices");
    const menu = page.getByRole("navigation", { name: "Module navigation", exact: true });
    await menu.getByRole("button", { name: "Expand all menu categories" }).click();
    await expect(menu.getByRole("link", { name: /^(Payments & collections|Collections)$/, exact: true })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Sales & inventory settings", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Invoices", exact: true })).toHaveCount(0);
    await expect(page.locator('[id^="operation-panel-"]:visible')).toHaveCount(1);
    await expect(menu.getByRole("link", { name: "Invoices", exact: true })).toHaveCount(0);
    expect(deniedRegisters).toEqual([]);
  });

  test("create intents target only the selected tab and submit to its original API", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/sales-orders");
    await page.getByRole("tab", {name:"Contracts",exact:true}).click();
    await page.getByRole("tab", {name:/^Sales orders$/i}).click();
    await page.evaluate(() => {
      window.history.pushState({}, "", window.location.pathname + "?operation=%2Fsrm%2Fcontracts#new-record");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await expect(page.getByRole("dialog")).toHaveCount(1);
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Create Contract");
    await dialog.getByLabel("Title", {exact:true}).fill("Merged workspace contract");
    await page.evaluate(() => {
      window.history.pushState({}, "", window.location.pathname);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("tab", {name:"Contracts",exact:true}).click();
    await expect(dialog.getByLabel("Title", {exact:true})).toHaveValue("Merged workspace contract");
    const write = page.waitForRequest(request => new URL(request.url()).pathname === "/api/v1/srm/contracts" && request.method() === "POST");
    await dialog.locator('button[type="submit"]').click();
    expect((await write).postDataJSON().title).toBe("Merged workspace contract");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("tab", {name:"Contracts",exact:true})).toHaveAttribute("aria-selected","true");
  });
});
