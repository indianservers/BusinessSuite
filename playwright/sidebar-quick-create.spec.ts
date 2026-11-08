import { resolve } from "node:path";
import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

async function setup(page: Page, role: "admin" | "srm_viewer" = "admin") {
  await authenticate(page, role);
  await page.route("**/api/v1/access/settings/defaults/effective", r => r.fulfill({json:{values:{},modules:{},companyId:1}}));
  await page.route("**/api/v1/access/setup", r => r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  await page.route("**/api/v1/employees/workbench/home**", r => r.fulfill({json:{pending_counts:{}}}));
}
async function menu(page: Page, query: string) {
  const navigation = page.locator(".module-menu").first();
  await navigation.getByRole("textbox", {name:"Find a page in this application"}).fill(query);
  return navigation;
}

test("CRM menu opens capture directly without navigating to the list", async ({page}) => {
  await setup(page); await page.goto("/crm/contacts");
  const navigation = await menu(page,"Contacts");
  await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Create contact");
  await expect(page).toHaveURL(/\/crm\/contacts$/);
  await page.keyboard.press("Escape");
  await navigation.getByRole("button",{name:"Create Contact",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Create contact");
});

test("PMS project shortcut keeps the chosen workspace and opens its project form", async ({page}) => {
  await setup(page);
  await page.route("**/api/v1/project-management/**", r => {
    const path = new URL(r.request().url()).pathname;
    return r.fulfill({json:path.endsWith("/workspaces")?[{id:7,name:"Design studio",role:"Owner"}]:path.endsWith("/overview")?{role:"Owner",projects:[],tasks:[]}:path.endsWith("/workspaces/7")?{id:7,name:"Design studio",role:"Owner"}:path.includes("custom-fields")?{fields:[]}:[]});
  });
  await page.goto("/pms/projects?workspace=7");
  const navigation = await menu(page,"Projects");
  await navigation.getByRole("button",{name:"Create Project",exact:true}).click();
  await expect(page.getByRole("dialog").getByRole("textbox",{name:"Project name",exact:true})).toBeVisible();
  await expect(page).toHaveURL(/workspace=7/);
});

test("sales menu focuses the existing order form without submitting it", async ({page}) => {
  await setup(page); let writes=0;
  page.on("request", r => {if(r.url().includes("/api/")&&r.method()==="POST") writes++;});
  await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  await navigation.getByRole("button",{name:"Create Sales order",exact:true}).click();
  await expect(page).toHaveURL(/sales-orders#new-record$/);
  await expect(page.locator("#new-record").locator("input").first()).toBeFocused();
  expect(writes).toBe(0);
});

test("finance shortcut opens the voucher draft", async ({page}) => {
  await setup(page); await page.goto("/fam/vouchers"); const navigation=await menu(page,"Vouchers");
  await navigation.getByRole("button",{name:"Create Voucher",exact:true}).click();
  await expect(page).toHaveURL(/\/fam\/vouchers\/new$/);
});

test("HR employee shortcut opens quick capture", async ({page}) => {
  await setup(page); await page.goto("/hrms/employees"); const navigation=await menu(page,"Employees");
  await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Quick Add Employee");
  await expect(page.getByRole("dialog").getByLabel("first_name",{exact:true})).toBeVisible();
});

test("view-only sales users do not receive create shortcuts", async ({page}) => {
  await setup(page,"srm_viewer"); await page.goto("/srm/sales-orders"); const navigation=await menu(page,"Sales orders");
  await expect(navigation.locator(".module-menu-create")).toHaveCount(0);
  await expect(navigation.getByRole("link",{name:"Sales Orders",exact:true})).toBeVisible();
});

test("customization shortcut opens the field editor and can be reused", async ({page}) => {
  await setup(page); await page.route("**/api/v1/customization/**",r=>r.fulfill({json:{items:[]}}));
  await page.goto("/admin/customization/fields"); const navigation=await menu(page,"Fields");
  await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await navigation.getByRole("button",{name:"Create Field",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("catalog quick create works on the same page repeatedly", async ({page}) => {
  await setup(page); await page.route("**/api/v1/catalog/items**",r=>r.fulfill({json:{items:[],total:0,pages:0,permissions:{product:true,service:true}}}));
  await page.goto("/srm/inventory/products"); const navigation=await menu(page,"Products");
  await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape");
  await navigation.getByRole("button",{name:"Create Catalog item",exact:true}).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("ellipsis offers contextual creation and configuration without changing pages", async ({page}) => {
  await setup(page); await page.goto("/crm/contacts"); const navigation=await menu(page,"Contacts");
  await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  const dropdown=page.getByRole("menu").first();
  await expect(dropdown.getByRole("menuitem",{name:"Add to favorites",exact:true})).toBeVisible();
  await expect(dropdown.getByRole("menuitem",{name:"Custom fields",exact:true})).toBeVisible();
  await expect(page).toHaveURL(/\/crm\/contacts$/);
  await dropdown.getByRole("menuitem",{name:"Create new",exact:true}).hover();
  await page.getByRole("menuitem",{name:"Contact",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Create contact");
});

test("menu appearance and favorites persist without renaming business records", async ({page}) => {
  await setup(page);let writes=0;
  page.on("request",r=>{if(r.url().includes("/api/")&&["POST","PUT","PATCH","DELETE"].includes(r.method()))writes++;});
  await page.goto("/crm/contacts");let navigation=await menu(page,"Contacts");
  await navigation.getByRole("button",{name:"More options for Contacts",exact:true}).click();
  await page.getByRole("menuitem",{name:"Rename menu item",exact:true}).click();
  const dialog=page.getByRole("dialog");await dialog.getByLabel("Menu name",{exact:true}).fill("Our contacts");
  await dialog.getByLabel("Menu icon",{exact:true}).selectOption("people");await dialog.getByRole("button",{name:"green menu color",exact:true}).click();await dialog.getByRole("button",{name:"Save menu item",exact:true}).click();
  await navigation.getByRole("button",{name:"More options for Our contacts",exact:true}).click();
  await page.getByRole("menuitem",{name:"Add to favorites",exact:true}).click();await page.reload();
  navigation=page.locator(".module-menu").first();await expect(navigation.getByRole("list",{name:"Favorite menu pages"})).toContainText("Our contacts");
  await menu(page,"Our contacts");await expect(navigation.getByRole("link",{name:"Our contacts",exact:true})).toBeVisible();
  expect(writes).toBe(0);
});

test("ellipsis copy link preserves workspace context and keyboard dismissal", async ({page,context}) => {
  await context.grantPermissions(["clipboard-read","clipboard-write"]);await setup(page);
  await page.route("**/api/v1/project-management/workspaces",r=>r.fulfill({json:[{id:7,name:"Design",role:"Guest"}]}));
  await page.goto("/pms/projects?workspace=7");const navigation=await menu(page,"Projects");
  const more=navigation.getByRole("button",{name:"More options for Projects",exact:true});await more.click();
  await page.getByRole("menuitem",{name:"Copy link",exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toContain("/pms/projects?workspace=7");
  await more.click();await page.keyboard.press("Escape");await expect(page.getByRole("menu")).toHaveCount(0);await expect(more).toBeFocused();
  await expect(navigation.getByRole("button",{name:"Create Project",exact:true})).toHaveCount(0);
});

test("mobile menu create closes the drawer and focuses employee capture", async ({page}) => {
  await page.setViewportSize({width:390,height:844});await setup(page);await page.goto("/hrms/employees");
  await page.getByRole("button",{name:"Open navigation",exact:true}).click();
  const navigation=await menu(page,"Employees");await navigation.getByRole("button",{name:"Create Employee",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText("Quick Add Employee");
  await expect(page.getByRole("button",{name:"Close navigation",exact:true})).not.toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

for (const [path,query,label] of [["/hrms/employees","Employees","Employees"],["/srm/sales-orders","Sales orders","Sales Orders"],["/fam/vouchers","Vouchers","Vouchers"],["/ai/copilot","Copilot","Copilot"],["/analytics/reports","Reports","Reports"],["/admin/customization/fields","Fields","Fields"]]) {
  test(`context menu works in ${path}`, async ({page})=>{
    await setup(page);await page.goto(path);const navigation=await menu(page,query);
    await navigation.getByRole("button",{name:`More options for ${label}`,exact:true}).click();
    await expect(page.getByRole("menuitem",{name:"Copy link",exact:true})).toBeVisible();
    await expect(page.getByRole("menuitem",{name:"Delete",exact:true})).toHaveCount(0);
    await page.keyboard.press("Escape");await expect(page.getByRole("menu")).toHaveCount(0);
  });
}

test("Power Apps quick creation preserves the selected environment",async({page})=>{
  await setup(page);await page.route("**/api/v1/power-apps/**",r=>{
    const path=new URL(r.request().url()).pathname;
    return r.fulfill({json:path.endsWith("catalog")?{applications:[{id:"automations",name:"Automations",route:"/power-apps/automations",icon:"Workflow",status:"available",description:"Automations",environments:["testing"],required_permissions:[],feature_flags:[]}],permissions:["power_apps_view","power_apps_create"],templates:[]}:path.endsWith("environments")?{items:[{key:"testing",enabled:true}]}:path.endsWith("overview")?{counts:{},recent:[],unsupported_metrics:[]}: {items:[],total:0}});
  });
  await page.goto("/power-apps?environment=testing");const navigation=await menu(page,"Automations");
  await navigation.getByRole("button",{name:"Create Automation",exact:true}).click();
  await expect(page).toHaveURL(/\/power-apps\/automations\/new\?environment=testing/);
});

test("asset shortcut reveals its form from a different asset tab",async({page})=>{
  await setup(page);await page.route("**/api/v1/assets**",r=>r.fulfill({json:r.request().url().includes("capabilities")?{can_manage:true}:[]}));
  await page.goto("/hrms/assets");await page.getByRole("button",{name:"Employee custody",exact:true}).click();
  const navigation=await menu(page,"Assets");await navigation.getByRole("button",{name:"Create Asset",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Register an asset",exact:true})).toBeVisible();
  await expect(page.locator('input:focus')).toHaveCount(1);
});

test("HR sidebar actions render with populated employee cards",async({page},testInfo)=>{
  await page.setViewportSize({width:1500,height:1000});await setup(page);
  const items=[{id:1,employee_id:"EMP-1",first_name:"Asha",last_name:"Rao",status:"Active",employment_type:"Full-time",date_of_joining:"2026-01-01",personal_email:"asha@example.com",phone_number:null},{id:2,employee_id:"EMP-2",first_name:"Ravi",last_name:"Kumar",status:"Probation",employment_type:"Contract",date_of_joining:"2026-02-01",personal_email:null,phone_number:null}];
  await page.route("**/api/v1/employees/**",r=>r.fulfill({json:r.request().url().includes("workbench/home")?{pending_counts:{}}:r.request().url().includes("filter-options")?{}:{items,total:2,pages:1,page:1}}));
  await page.goto("/hrms/employees");await expect(page.getByText("Asha Rao",{exact:true})).toBeVisible();
  const navigation=page.locator(".module-menu").first();await navigation.getByRole("button",{name:"Expand all menu categories",exact:true}).click();
  await navigation.getByRole("button",{name:"More options for People",exact:true}).click();
  await page.getByRole("menuitem",{name:"Create new",exact:true}).hover();
  await expect(page.getByRole("menuitem",{name:"Add Employee",exact:true})).toBeVisible();
  await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/navigation-actions/HRMS-menu-preview.png")});
});
