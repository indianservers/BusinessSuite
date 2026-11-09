import {expect,test,type Page} from "../frontend/node_modules/playwright/test";
import {resolve} from "node:path";
import {authenticate} from "./srm-test-utils";
import {setupLeads,setupDeals,setupProjects} from "./suite-record-fixtures";

async function setupHR(page:Page){
 await authenticate(page,"admin");
 await page.route("**/api/v1/access/settings/defaults/effective",r=>r.fulfill({json:{values:{},modules:{}}}));
 await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{ready:true,items:[]}}));
 const items=[{id:1,employee_id:"EMP-1",first_name:"Asha",last_name:"Rao",status:"Active",employment_type:"Full-time",date_of_joining:"2026-01-01",department_id:1,personal_email:"asha@example.com"},{id:2,employee_id:"EMP-2",first_name:"Ravi",last_name:"Kumar",status:"Probation",employment_type:"Contract",department_id:2,date_of_joining:"2026-02-01"}];
 await page.route("**/api/v1/employees/**",r=>r.fulfill({json:r.request().url().includes("reporting-managers")?[]:r.request().url().includes("workbench/home")?{pending_counts:{}}:r.request().url().includes("filter-options")?{}:{items,total:2,pages:1,page:1}}));
 await page.route("**/api/v1/company/departments/**",r=>r.fulfill({json:[{id:1,name:"Engineering"},{id:2,name:"Operations"}]}));
 await page.route("**/api/v1/employees/1",r=>r.fulfill({json:items[0]}));await page.route("**/api/v1/project-management/operations/people**",r=>r.fulfill({json:{items:[],total:0,page:1,pages:1,summary:{}}}));await page.goto("/hrms/employees");await page.getByRole("tab",{name:"Cards",exact:true}).click();return items;
}
test.beforeEach(async({page})=>{await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));});
const tabs=(root:any,name:string)=>root.page().getByRole("tab",{name,exact:true});
async function expand(root:any){const button=root.getByRole("button",{name:"Expand loaded groups",exact:true});await expect(button).toBeVisible();await button.click();}

test("HR cards have persistent favorites, frequent previews and a compact list",async({page},testInfo)=>{
 await page.setViewportSize({width:1600,height:1100});await setupHR(page);const collection=page.locator('[data-source-table="apps/hrms/pages/employees/EmployeesPage:table-1"]');
 await collection.getByRole("button",{name:"Favorite Asha Rao",exact:true}).click();await tabs(collection,"Favorites").click();await expand(collection);await expect(collection.getByText("Asha Rao",{exact:true})).toBeVisible();await expect(collection.getByText("Ravi Kumar",{exact:true})).toHaveCount(0);
 await collection.getByRole("button",{name:"Preview Asha Rao",exact:true}).first().click();await expect(page.getByRole("dialog")).toContainText("Asha Rao");await page.keyboard.press("Escape");await tabs(collection,"Frequent").click();await expand(collection);await expect(collection.getByText("Asha Rao",{exact:true})).toBeVisible();
 await page.reload();await expect(tabs(collection,"Frequent")).toHaveAttribute("aria-selected","true");await tabs(collection,"List").click();await expect(collection.locator(".udg-view-list")).toBeVisible();await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/HRMS-list.png"),fullPage:true});
});

test("HR table supports cards, category grouping, favorites and native actions",async({page})=>{
 await setupHR(page);await page.getByRole("tab",{name:"Table",exact:true}).click();const grid=page.locator('[data-source-table="apps/hrms/pages/employees/EmployeesPage:table-1"]');const expandButton=grid.getByRole("button",{name:"Expand loaded groups",exact:true});if(await expandButton.isVisible())await expandButton.click();
 await grid.getByRole("button",{name:/^Favorite Asha Rao/}).click();await tabs(grid,"Favorites").click();await expand(grid);await expect(grid.getByText("Asha Rao",{exact:true})).toBeVisible();await expect(grid.getByText("Ravi Kumar",{exact:true})).toHaveCount(0);
 await tabs(grid,"Cards").click();await expect(grid.locator(".udg-view-cards article")).toHaveCount(2);await tabs(grid,"By Department").click();await expect(grid.locator(".suite-group-badge")).toContainText(["Engineering","Operations"]);
});

test("CRM Leads retain their capture and detail actions in shared cards and personal views",async({page},testInfo)=>{
 await page.setViewportSize({width:1600,height:1100});await setupLeads(page);const grid=page.locator('[data-source-table="apps/crm/leads/LeadManagementPage:table-1"],.udg-native[data-grid-id="apps/crm/leads/LeadManagementPage:table-1"]').first();
 await grid.getByRole("button",{name:/^Favorite Nisha Rao/}).click();await tabs(grid,"Favorites").click();await expand(grid);await expect(grid.getByRole("button",{name:"Nisha Rao",exact:true})).toBeVisible();
 await tabs(grid,"Cards").click();await grid.getByRole("button",{name:"Nisha Rao",exact:true}).click();await expect(page.getByRole("dialog")).toBeVisible();await page.keyboard.press("Escape");await tabs(grid,"Frequent").click();await expand(grid);await expect(grid.getByRole("button",{name:"Nisha Rao",exact:true})).toBeVisible();await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/CRM-leads.png"),fullPage:true});
});

test("PMS preserves existing project stars and row actions in the new views",async({page},testInfo)=>{
 await page.setViewportSize({width:1600,height:1100});await setupProjects(page);const grid=page.locator('.udg-native[data-grid-id="pms-project-portfolio"]');
 await page.getByRole("button",{name:"Star Website delivery",exact:true}).first().click();await tabs(grid,"Favorites").click();await expect(grid.getByRole("button",{name:"Preview Website delivery; double-click to open project",exact:true})).toBeVisible();await expect(grid.getByText("Completed engagement",{exact:true})).toHaveCount(0);
 await tabs(grid,"Cards").click();await expect(grid.locator('.suite-native-card')).toHaveCount(2);await expect(grid.getByRole("button",{name:"Unstar Website delivery",exact:true})).toBeVisible();await tabs(grid,"Table").click();await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/PMS-projects.png"),fullPage:true});
});

test("CRM deal favorites request their server identifiers before pagination",async({page},testInfo)=>{
 await page.setViewportSize({width:1600,height:1100});await setupDeals(page);const requests:any[]=[];
 const rows=[{id:1,name:"Enterprise renewal",amount:25000,currency:"INR",status:"Open",priority:"High",stage_name:"Qualification",owner_name:"Sales Admin",pipeline_name:"Enterprise Sales",version:1,probability:50},{id:2,name:"Website rollout",amount:15000,currency:"INR",status:"Open",priority:"Medium",stage_name:"Proposal",version:1,probability:60}];
 await page.route("**/api/v1/crm/deal-workspace/grid/query**",r=>{const q=JSON.parse(new URL(r.request().url()).searchParams.get("state")||"{}");requests.push(q);const shown=q.recordIds?rows.filter(row=>q.recordIds.includes(String(row.id))):rows;return r.fulfill({json:{rows:shown,total:shown.length,pageTotal:shown.length,page:1,pageSize:50,permissions:{edit:false,export:false}}});});
 await page.goto("/crm/deals");const grid=page.locator('.udg-workspace').first();await grid.getByRole("button",{name:"Favorite Enterprise renewal",exact:true}).click();await tabs(grid,"Favorites").click();await expect(grid.getByRole("link",{name:"Enterprise renewal",exact:true})).toBeVisible();await expect(grid.getByRole("link",{name:"Website rollout",exact:true})).toHaveCount(0);expect(requests.at(-1)?.recordIds).toEqual(["1"]);
 await tabs(grid,"Cards").click();await expect(grid.locator('.udg-view-cards article')).toHaveCount(2);await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/CRM-deals.png"),fullPage:true});
});

test("Sales list views preserve read-only permissions and favorite state",async({page},testInfo)=>{
 await page.setViewportSize({width:1600,height:1100});await authenticate(page,"srm_viewer");await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));await page.route("**/api/v1/access/settings/defaults/effective",r=>r.fulfill({json:{values:{},modules:{}}}));
 await page.route("**/api/v1/srm/sales-orders**",r=>r.fulfill({json:[{id:11,title:"Acme implementation",status:"Draft",customer_id:1,total_amount:4500,currency:"INR"},{id:12,title:"Annual support",status:"Approved",customer_id:2,total_amount:2000,currency:"INR"}]}));
 await page.goto("/srm/sales-orders");const grid=page.locator('.udg-workspace').first();await tabs(grid,"Cards").click();await grid.getByRole("button",{name:/^Favorite Acme implementation/}).click();await tabs(grid,"Favorites").click();await expand(grid);await expect(grid.getByRole("gridcell",{name:"Acme implementation",exact:true})).toBeVisible();await expect(grid.getByRole("gridcell",{name:"Annual support",exact:true})).toHaveCount(0);await tabs(grid,"Cards").click();await expect(page.getByRole("button",{name:"Add record",exact:true})).toHaveCount(0);await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/Sales-orders.png"),fullPage:true});
});

test("mobile record views and quick tools do not overflow the app",async({page},testInfo)=>{
 await page.setViewportSize({width:390,height:844});await setupHR(page);const collection=page.locator('[data-source-table="apps/hrms/pages/employees/EmployeesPage:table-1"]');await tabs(collection,"List").click();await collection.getByRole("button",{name:"Favorite Asha Rao",exact:true}).click();await tabs(collection,"Favorites").click();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();await expect(page.locator("[data-record-views]")).toHaveCount(1);await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/compact-lists/HRMS-mobile.png")});
});






test("personal view keyboard navigation, empty states and copy quick action work",async({page,context})=>{
 await context.grantPermissions(["clipboard-read","clipboard-write"]);await setupHR(page);const collection=page.locator('[data-source-table="apps/hrms/pages/employees/EmployeesPage:table-1"]');
 await collection.locator(".udg-view-cards article").filter({has:page.getByRole("button",{name:"Favorite Asha Rao",exact:true})}).getByRole("button",{name:"Record quick actions",exact:true}).click();await page.getByRole("menuitem",{name:"Copy record name",exact:true}).click();await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toBe("Asha Rao");
 await tabs(collection,"Favorites").click();await expect(collection.getByRole("heading",{name:"No records match",exact:true})).toBeVisible();await tabs(collection,"Favorites").press("Home");await expect(tabs(collection,"Table")).toHaveAttribute("aria-selected","true");await tabs(collection,"Table").press("End");await expect(tabs(collection,"Favorites")).toHaveAttribute("aria-selected","true");
});



test("PMS has one view strip and one preview action without an extra tools column",async({page})=>{
 await setupProjects(page);const strip=page.locator(".wv-unified-records");await expect(strip.locator('[role="tablist"]')).toHaveCount(1);await expect(strip.getByRole("tab",{name:"Table",exact:true})).toHaveCount(1);await expect(strip.getByRole("button",{name:"List",exact:true})).toHaveCount(0);await expect(page.getByRole("columnheader",{name:"Quick tools",exact:true})).toHaveCount(0);
 const row=page.locator(".portfolio-table tbody tr:not(.native-group-row):not(.native-group-create)").first();await expect(row.getByRole("button",{name:"Preview Website delivery",exact:true})).toHaveCount(1);await expect(row.getByRole("button",{name:"Preview record",exact:true})).toHaveCount(0);await row.getByRole("button",{name:"Preview Website delivery",exact:true}).click();await expect(page.getByRole("dialog")).toBeVisible();await page.keyboard.press("Escape");await expect(strip.getByRole("tab",{name:"Table",exact:true})).toHaveCount(1);
});
