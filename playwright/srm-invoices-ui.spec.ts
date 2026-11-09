import { expect, test, type Page } from "../frontend/node_modules/playwright/test";
import { authenticate } from "./srm-test-utils";

async function invoiceFlow(page:Page,rejectSend=false){
  await authenticate(page,"srm_finance_manager");
  const access={managed:true,companyId:1,grants:{srm:{enabled:true,role:"Finance",scope:"organization",permissions:["srm_invoice_create","srm_invoice_approve"],actions:["view","create","edit","approve","export"]}},modules:[{key:"srm",route:"/srm",label:"Sales"}],memberships:[1],isAccessAdmin:false,isGlobalAdmin:false};
  await page.route("**/api/v1/access/me",route=>route.fulfill({json:access}));
  await page.route("**/api/v1/auth/me",route=>route.fulfill({json:{id:103,email:"finance@srm.example.com",role:{name:"srm_finance_manager"},is_superuser:false,access}}));
  await page.addInitScript(access=>{const session=JSON.parse(sessionStorage.getItem("hrms-auth")||"{}");if(session.state?.user){session.state.user.access=access;sessionStorage.setItem("hrms-auth",JSON.stringify(session));}},access);
  await page.evaluate(async access=>{const {useAuthStore}=await import("/src/store/authStore.ts");const state=useAuthStore.getState();useAuthStore.setState({user:{...state.user!,access} as typeof state.user});},access);
  const invoice={id:1,invoice_number:"INV-000001",status:"draft",customer_id:10,total_amount:100,paid_amount:0,balance_amount:100,lines:[] as {id:number;description:string;line_total:number}[],history:[] as {to_status:string}[],allocations:[]};
  await page.route("**/api/v1/srm/invoices**",async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(path.endsWith("/pdf"))return route.fulfill({contentType:"application/pdf",body:"%PDF-1.4\n%%EOF"});
    if(request.method()==="POST"){
      if(path.endsWith("/approve")){invoice.status="approved";invoice.history.push({to_status:"approved"});}
      if(path.endsWith("/send")){
        if(rejectSend)return route.fulfill({status:400,json:{detail:"Invoice changed; reload before sending"}});
        invoice.status="sent";invoice.history.push({to_status:"sent"});
      }
      if(path.endsWith("/lines")){const line=request.postDataJSON();invoice.lines.push({id:invoice.lines.length+1,description:line.description,line_total:line.line_total});}
    }
    return route.fulfill({json:path==="/api/v1/srm/invoices"?[invoice]:invoice});
  });
}

test.describe("SRM invoices UI", () => {
  test("shows invoice detail, approval, send/export, PDF, lines, history, and allocation sections", async ({ page }) => {
    await invoiceFlow(page);
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: "Invoices", level: 1 })).toBeVisible();
    await expect(page.getByText("Invoice Number",{exact:true})).toBeVisible();
    await expect(page.getByText("Balance Amount",{exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:"Send / Export Invoice",exact:true})).toBeDisabled();

    const lineEditor=page.locator("form").filter({has:page.getByRole("button",{name:"Add Line",exact:true})});
    await lineEditor.getByPlaceholder("Line description",{exact:true}).fill("Implementation service");
    await page.getByRole("button",{name:"Add Line",exact:true}).click();
    await expect(page.getByRole("main").getByRole("status").filter({hasText:"Invoice line added"})).toBeVisible();

    await page.getByRole("button", { name: "Approve Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status").filter({hasText:"Invoice approval completed"})).toBeVisible();
    await expect(lineEditor).toHaveCount(0);

    await page.getByRole("button", { name: "Send / Export Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status").filter({hasText:"Invoice send/export completed"})).toBeVisible();

    const download=page.waitForEvent("download");
    await page.getByRole("button",{name:"Download PDF",exact:true}).click();
    expect((await download).suggestedFilename()).toBe("invoice-1.pdf");

    await expect(page.getByText("Invoice Lines")).toBeVisible();
    await expect(page.getByRole("heading",{name:"Receipt Allocations",exact:true})).toBeVisible();
    await expect(page.getByText("Audit / History")).toBeVisible();
  });

  test("shows invoice validation errors from the API", async ({ page }) => {
    await invoiceFlow(page,true);
    await page.goto("/srm/invoices", { waitUntil: "domcontentloaded" });
    await page.getByRole("button",{name:"Approve Invoice",exact:true}).click();
    await expect(page.getByRole("button",{name:"Send / Export Invoice",exact:true})).toBeEnabled();
    await page.getByRole("button", { name: "Send / Export Invoice" }).click();
    await expect(page.getByRole("main").getByRole("status").filter({hasText:"Invoice changed; reload before sending"})).toBeVisible();
    await expect(page.getByRole("button",{name:"Send / Export Invoice",exact:true})).toBeEnabled();
  });
});
