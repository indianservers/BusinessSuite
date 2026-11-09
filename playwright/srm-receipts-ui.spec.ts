import {expect,test,type Page} from "../frontend/node_modules/playwright/test";
import {authenticate} from "./srm-test-utils";

async function collections(page:Page,reject=false){
  await authenticate(page,"admin");
  let paid=0;const payments:any[]=[];
  const invoice=()=>({id:1,invoice_number:"QA-INV-1",customer_id:1,currency:"INR",total_amount:100,paid_amount:paid,balance_amount:100-paid,document_status:"issued",delivery_status:"sent",payment_status:paid===100?"paid":paid?"partially_paid":"unpaid"});
  await page.route("**/api/v1/srm/business/collection-invoices",r=>r.fulfill({json:{items:[invoice()],can_record:true}}));
  await page.route("**/api/v1/srm/business/invoices/1/payments",r=>{
    const payload=r.request().postDataJSON();payments.push(payload);
    if(reject)return r.fulfill({status:400,json:{detail:"Allocation amount exceeds invoice balance"}});
    paid+=Number(payload.amount);return r.fulfill({json:{receipt_id:payments.length,invoice:invoice()}});
  });
  await page.goto("/srm/collections");
  await page.getByText("Payment and collection actions",{exact:true}).click();
  return payments;
}

test("collections records partial and final receipts against the selected invoice",async({page})=>{
  const payments=await collections(page);
  await page.getByLabel("Amount received",{exact:true}).fill("40");
  await page.getByLabel("Bank / payment reference",{exact:true}).fill("QA-PARTIAL");
  await page.getByRole("button",{name:"Record received payment",exact:true}).click();
  await expect(page.getByText("Outstanding: 60",{exact:true})).toBeVisible();
  await page.getByLabel("Amount received",{exact:true}).fill("60");
  await page.getByRole("button",{name:"Record received payment",exact:true}).click();
  await expect(page.getByText("Outstanding: 0",{exact:true})).toBeVisible();
  await expect(page.getByText("Payment: paid",{exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Record received payment",exact:true})).toHaveCount(0);
  expect(payments.map(p=>p.amount)).toEqual(["40","60"]);
  expect(payments[0].request_id).not.toBe(payments[1].request_id);
});

test("collection API rejection retains the payment draft for correction",async({page})=>{
  await collections(page,true);
  await page.getByLabel("Amount received",{exact:true}).fill("40");
  await page.getByLabel("Bank / payment reference",{exact:true}).fill("QA-RETRY");
  await page.getByRole("button",{name:"Record received payment",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Allocation amount exceeds invoice balance");
  await expect(page.getByLabel("Amount received",{exact:true})).toHaveValue("40");
  await expect(page.getByLabel("Bank / payment reference",{exact:true})).toHaveValue("QA-RETRY");
});
