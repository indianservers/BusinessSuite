import { test, expect } from "../frontend/node_modules/playwright/test";
test("view-only customer cannot see quote acceptance",async({page})=>{
 await page.route("**/api/v1/customer-portal/**",r=>r.fulfill({json:r.request().url().endsWith('/me')?{user:{display_name:'Viewer',permissions_json:['view']}}:{items:[{id:1,quote_number:'READ-ONLY',status:'sent'}],total:1}}));
 await page.goto('/portal/customer/quotes');
 await expect(page.getByText('READ-ONLY',{exact:true}).first()).toBeVisible();
 await expect(page.getByRole('button',{name:'Accept quote',exact:true})).toHaveCount(0);
});
test("portal quote acceptance reviews and calls existing API",async({page})=>{
 let accepted=false,requests=0;
 await page.route("**/api/v1/customer-portal/**",async r=>{
  const p=new URL(r.request().url()).pathname;
  if(p.endsWith("/me"))return r.fulfill({json:{user:{display_name:"QA customer",permissions_json:["view","accept_quote"]}}});
  if(p.endsWith("/quotes/1/accept")){accepted=true;requests++;return r.fulfill({json:{id:1,status:"accepted"}});}
  if(p.endsWith("/quotes"))return r.fulfill({json:{items:[{id:1,quote_number:"Q-1",status:accepted?"accepted":"sent",amount:100}],total:1}});
  return r.fulfill({json:{items:[],total:0}});
 });
 await page.goto("/portal/customer/quotes");await page.getByRole("button",{name:"Accept quote",exact:true}).click();
 await expect(page.getByRole("dialog",{name:"Review quote acceptance",exact:true})).toContainText("Q-1");expect(requests).toBe(0);
 await page.getByRole("button",{name:"Confirm acceptance",exact:true}).click();
 await expect.poll(()=>requests).toBe(1);await expect(page.getByText("accepted",{exact:true})).toBeVisible();await expect(page.getByRole("button",{name:"Accept quote",exact:true})).toBeDisabled();
});
for(const type of ["customer","partner"]){test(`${type} portal login hides token and guards empty submission`,async({page})=>{
 await page.goto(`/portal/${type}/login`);const token=page.getByLabel("Portal session token",{exact:true});await expect(token).toHaveAttribute("type","password");const open=page.getByRole("button",{name:"Open portal",exact:false});await expect(open).toBeDisabled();await token.fill("test-session");await expect(open).toBeEnabled();
});}
