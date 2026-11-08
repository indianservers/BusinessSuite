import { test, expect, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

async function setup(page:Page){
 await authenticate(page,"admin");
 await page.route("**/api/v1/access/settings/defaults/effective",route=>route.fulfill({json:{values:{},modules:{},companyId:1,branchId:null}}));
 await page.route("**/api/v1/access/setup",route=>route.fulfill({json:{companyId:1,ready:true,items:[]}}));
 await page.route("**/api/v1/employees/workbench/home**",route=>route.fulfill({json:{pending_counts:{leave:0,approvals:0,expenses:0,helpdesk:0}}}));
}

test("employee cards and rendered table cells group by real record values",async({page})=>{
 await setup(page);
 const items=[{id:1,employee_id:"EMP-1",first_name:"Asha",last_name:"Rao",status:"Active",employment_type:"Full-time",date_of_joining:"2026-01-01",personal_email:"asha@example.com",phone_number:null},{id:2,employee_id:"EMP-2",first_name:"Ravi",last_name:"Kumar",status:"Probation",employment_type:"Contract",date_of_joining:"2026-02-01",personal_email:null,phone_number:null}];
 await page.route("**/api/v1/employees/**",route=>route.fulfill({json:new URL(route.request().url()).pathname.endsWith("filter-options")?{}:route.request().url().includes("workbench/home")?{pending_counts:{}}:{items,total:2,pages:1,page:1}}));
 await page.goto("/hrms/employees");
 const cards=page.locator('[data-card-collection="hrms-employees"]');await cards.getByLabel("Group cards by",{exact:true}).selectOption("status");
 await expect(cards.locator(".suite-group-badge")).toHaveText(["Active","Probation"]);
 await cards.getByRole("button",{name:"Collapse Status: Active",exact:true}).click();await expect(cards.getByText("Asha Rao",{exact:true})).toHaveCount(0);await expect(cards.getByText("Ravi Kumar",{exact:true})).toBeVisible();
 await page.reload();await expect(cards.getByLabel("Group cards by",{exact:true})).toHaveValue("status");
 await page.getByRole("button",{name:"Table",exact:true}).click();const table=page.locator('[data-source-table="apps/hrms/pages/employees/EmployeesPage:table-1"]');
 await table.getByLabel("Add grouping column",{exact:true}).selectOption({label:"Status"});await table.getByRole("button",{name:"Expand loaded groups",exact:true}).click();
 await expect(table.locator(".suite-group-badge")).toHaveText(["Active","Probation"]);await expect(table.getByText("Asha Rao",{exact:true})).toBeVisible();
 await expect(table.getByLabel("Search grid",{exact:true})).toHaveCount(0);await expect(table.locator('.udg-pagination')).toHaveCount(0);
});

test("asset collection groups without changing its repair action permissions",async({page})=>{
 await page.setViewportSize({width:390,height:844});await setup(page);let writes=0;
 await page.route("**/api/v1/assets**",route=>{if(route.request().method()!=="GET")writes++;const p=new URL(route.request().url()).pathname;return route.fulfill({json:p.endsWith("capabilities")?{can_manage:false}:p.endsWith("categories")?[]:[{id:1,name:"Office laptop",asset_tag:"L-1",status:"Available",category_id:null},{id:2,name:"Field laptop",asset_tag:"L-2",status:"Under Repair",category_id:null}]});});
 await page.goto("/hrms/assets");const list=page.locator('[data-card-collection="hrms-assets"]');await list.getByLabel("Group cards by",{exact:true}).selectOption("status");await expect(list.locator(".suite-group-badge")).toHaveText(["Available","Under Repair"]);await expect(page.getByRole("button",{name:"Repair complete: make available",exact:true})).toHaveCount(0);await list.getByRole("button",{name:"Collapse all card groups",exact:true}).click();await expect(list.getByText("Office laptop",{exact:true})).toHaveCount(0);expect(writes).toBe(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

test("AI cards preserve content when grouping by module and status",async({page})=>{
 await setup(page);await page.route("**/api/v1/ai-agents**",route=>{const p=new URL(route.request().url()).pathname;return route.fulfill({json:p==="/api/v1/ai-agents"?[{id:1,code:"CRM-1",name:"Sales assistant",module:"CRM",is_active:true,requires_approval:true},{id:2,code:"PMS-1",name:"Project assistant",module:"PMS",is_active:false,requires_approval:false}]:[]});});
 await page.goto("/ai-agents");const list=page.locator('[data-card-collection="ai-agents"]');await list.getByLabel("Group cards by",{exact:true}).selectOption("module");await expect(list.locator(".suite-group-badge")).toHaveText(["CRM","PMS"]);await list.getByRole("button",{name:"Collapse Module: CRM",exact:true}).click();await expect(list.getByText("Sales assistant",{exact:true})).toHaveCount(0);await expect(list.getByText("Project assistant",{exact:true})).toBeVisible();await list.getByLabel("Group cards by",{exact:true}).selectOption("status");await expect(list.locator(".suite-group-badge")).toHaveText(["Active","Paused"]);
});

test("customization collections group by module and preserve edit controls",async({page})=>{
 await setup(page);await page.route("**/api/v1/customization/**",route=>{const p=new URL(route.request().url()).pathname;return route.fulfill({json:{items:p.endsWith("/fields")?[{id:1,module_name:"crm",field_api_name:"region",field_label:"Region",field_type:"text"},{id:2,module_name:"pms",field_api_name:"phase",field_label:"Phase",field_type:"text"}]:[{id:1,module_api_name:"crm",module_label:"CRM"},{id:2,module_api_name:"pms",module_label:"PMS"}],total:2}});});
 await page.goto("/admin/customization/fields");const list=page.locator('[data-card-collection="customization-fields"]');await list.getByLabel("Group cards by",{exact:true}).selectOption("module");await expect(list.locator(".suite-group-badge")).toHaveText(["crm","pms"]);await expect(list.getByRole("button",{name:"Edit",exact:true})).toHaveCount(2);await list.getByRole("button",{name:"Collapse Module: crm",exact:true}).click();await expect(list.getByRole("button",{name:"Edit",exact:true})).toHaveCount(1);
});

test("portal grouping retains view-only quote permissions",async({page})=>{
 await page.route("**/api/v1/customer-portal/**",route=>route.fulfill({json:route.request().url().endsWith('/me')?{user:{display_name:"Viewer",permissions_json:["view"]}}:{items:[{id:1,quote_number:"Q-1",status:"sent"},{id:2,quote_number:"Q-2",status:"accepted"}],total:2}}));
 await page.goto("/portal/customer/quotes");const list=page.locator('[data-card-collection="portal-records"]');await list.getByLabel("Group cards by",{exact:true}).selectOption("status");await expect(list.locator(".suite-group-badge")).toHaveText(["sent","accepted"]);await expect(page.getByRole("button",{name:"Accept quote",exact:true})).toHaveCount(0);await list.getByRole("button",{name:"Collapse Status: sent",exact:true}).click();await expect(page.getByText("Q-1",{exact:true})).toHaveCount(0);await expect(page.getByText("Q-2",{exact:true}).first()).toBeVisible();
});
