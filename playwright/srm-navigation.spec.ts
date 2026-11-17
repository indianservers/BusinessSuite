import { expect, test } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";
import { navigationOperationPath } from "../frontend/src/lib/navigation-workspaces";

test.describe("SRM navigation", () => {
  for(const [path,heading] of [['/srm/inventory/gantt','Inventory Gantt'],['/srm/inventory/purchase-receipts','Purchase Receipts']]){
    test(`purchasing operation opens its native screen: ${path}`,async({page})=>{
      await authenticate(page,'srm_admin');
      await page.goto(`/common/purchase-orders?module=srm&operation=${encodeURIComponent(path)}`);
      await expect(page).toHaveURL(new RegExp(path+'\\?module=srm'));
      await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible();
      await expect(page.getByRole('navigation',{name:'Shared page breadcrumbs'})).toHaveCount(0);
    });
  }
  test("Sales shortcuts are unique and open the shared invoice manager", async ({ page }) => {
    await authenticate(page, "srm_admin");
    await page.goto("/srm/dashboard");
    const menu=page.getByRole("navigation",{name:"Module navigation",exact:true});
    const shortcuts=menu.getByRole("navigation",{name:"Sticky shortcuts"});
    for(const label of ["POS","Appointments","Scheduling","Customers","Transactions","Reports"])await expect(shortcuts.getByRole("link",{name:label,exact:true})).toBeVisible();
    const links=await shortcuts.locator('a[href]').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href')!));
    expect(new Set(links.map(navigationOperationPath)).size).toBe(links.length);
    await menu.getByRole('button',{name:/^More \d+$/}).click();
    await expect(menu.locator('.module-menu-categories a[href]').first()).toBeVisible();
    await shortcuts.getByRole('link',{name:'Transactions',exact:true}).click();
    await expect(page).toHaveURL(/\/common\/invoices\?module=srm/);
    await expect(page.getByRole('navigation',{name:'Shared page breadcrumbs'})).toContainText('Invoices');
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
    await menu.getByRole("button", { name: /^More \d+$/ }).click();
    await expect(menu.getByRole("link", { name: /^(Payments & collections|Collections)$/, exact: true })).toBeVisible();
    await expect(menu.getByRole("link", { name: "Sales & inventory settings", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Invoices", exact: true })).toHaveCount(0);
    await expect(page.getByRole("navigation",{name:"Shared page breadcrumbs"})).toContainText("Collections");
    await expect(page).not.toHaveURL(/operation=/);
    await expect(menu.getByRole("link", { name: "Invoices", exact: true })).toHaveCount(0);
    expect(deniedRegisters).toEqual([]);
  });

  test("legacy create intents open exactly one native contract form", async ({ page }) => {
    await authenticate(page,"srm_admin");
    await page.goto('/srm/sales-orders?operation=%2Fsrm%2Fcontracts#new-record');
    await expect(page).toHaveURL(/\/common\/contracts\?module=srm#new-record/);
    await expect(page.getByRole('dialog')).toHaveCount(1);
    const dialog=page.getByRole('dialog');
    await expect(dialog).toContainText('Create Contract');
    await dialog.getByLabel('Title',{exact:true}).fill('Shared manager contract');
    const write=page.waitForRequest(request=>new URL(request.url()).pathname==='/api/v1/srm/contracts'&&request.method()==='POST');
    await dialog.locator('button[type="submit"]').click();
    expect((await write).postDataJSON().title).toBe('Shared manager contract');
    await expect(dialog).toHaveCount(0);
    await expect(page).toHaveURL(/\/common\/contracts\?module=srm/);
  });
});
