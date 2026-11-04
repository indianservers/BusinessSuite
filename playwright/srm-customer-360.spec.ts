import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

async function customerWorkspace(page: Page, failHistory = false) {
  await authenticate(page, "srm_admin");
  const customer={id:10,name:"Axiom Telecom",entityKind:"Company",status:"Active",roles:["Customer"],contacts:[],relationships:[],purchases:[],canEdit:false};
  await page.route("**/api/v1/master-data/company-directory/query*", route=>route.fulfill({json:{rows:[customer],total:1,pageTotal:1,page:1,pageSize:25,permissions:{},context:{canCreate:false}}}));
  await page.route("**/api/v1/master-data/companies/10*",route=>route.fulfill({json:customer}));
  await page.route("**/api/v1/master-data/company/10/channels*",route=>route.fulfill({json:{items:[],version:"1"}}));
  await page.route("**/api/v1/record-360/company/10**",async route=>{
    const url=new URL(route.request().url());
    if(url.pathname.endsWith("/events")) {
      if(failHistory) { await route.fulfill({status:500,json:{detail:"History temporarily unavailable"}});return; }
      await route.fulfill({json:{items:[{id:"srm_invoice:1",type:"commercial",title:"INV-360-001",body:"sent · INR 120000",source:"srm_invoice",occurred_at:"2026-11-04T09:00:00Z"}],total:1,page:1,per_page:25,sections:{}}});
    } else if(url.pathname.endsWith("/work")) await route.fulfill({json:{items:[{id:"pms_task:1",source:"pms_task",title:"Deliver migration",status:"To Do",url:"/pms/tasks/1"}],total:1,page:1,per_page:25,sections:{}}});
    else await route.fulfill({json:{...customer,kind:"company",customer:{id:10,name:customer.name},fields:{industry:"Telecom"},projects:[{id:1,name:"Migration project",status:"Active"}],relations:[],sections:{}}});
  });
  return ()=>{failHistory=false;};
}

test.describe("SRM shared Customer 360",()=>{
  test("selecting a customer opens focus, history and linked PMS projects",async({page})=>{
    await customerWorkspace(page);
    await page.goto("/srm/customer-360");
    await expect(page.getByRole("heading",{name:"Customers",exact:true})).toBeVisible();
    await page.getByText("Axiom Telecom",{exact:true}).first().click();
    const workspace=page.getByRole("region",{name:"company 360 view"});
    await expect(workspace.getByRole("heading",{name:"Axiom Telecom"})).toBeVisible();
    await expect(workspace.getByRole("heading",{name:"Focus",exact:true})).toBeVisible();
    await expect(workspace.getByText("Deliver migration",{exact:true})).toBeVisible();
    await expect(workspace.getByText("INV-360-001",{exact:true})).toBeVisible();
    await expect(workspace.getByRole("link",{name:"Migration project"})).toHaveAttribute("href","/pms/projects/1");
  });
  test("history errors are recoverable without losing customer context",async({page})=>{
    const recover=await customerWorkspace(page,true);
    await page.goto("/srm/customer-360");
    await page.getByText("Axiom Telecom",{exact:true}).first().click();
    const workspace=page.getByRole("region",{name:"company 360 view"});
    await expect(workspace.getByRole("alert")).toContainText("History temporarily unavailable");
    recover();
    await workspace.getByRole("button",{name:"Retry",exact:true}).click();
    await expect(workspace.getByText("INV-360-001",{exact:true})).toBeVisible();
  });
});
