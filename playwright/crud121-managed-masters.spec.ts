import {test,expect} from "../frontend/node_modules/playwright/test";
import {installNativeActor} from "./crud121-ui-actor";
const BASE="http://127.0.0.1:1582";
test.setTimeout(120000);
for(const kind of ["ledger-groups","ledgers"]){
 test(`/fam/${kind} managed native create rename delete`,async({page,request})=>{
  const login=await request.post(BASE+"/api/v1/auth/login",{data:{email:"admin@suiteqa.example.com",password:"SuiteQA@12345"}});
  await installNativeActor(page,request,BASE,await login.json());
  const name="Managed master "+kind+" "+Date.now(),prefix=kind==="ledgers"?"ledger":"group";
  await page.goto(BASE+"/fam/"+kind);
  await page.getByLabel(prefix+" name",{exact:true}).fill(name);
  await page.getByLabel(prefix+" code",{exact:true}).fill("MM"+Date.now());
  const write=(method:string)=>page.waitForResponse(r=>r.url().includes("/api/v1/fam/"+kind)&&r.request().method()===method);
  let pending=write("POST");await page.getByRole("button",{name:"Create",exact:true}).click();let response=await pending;expect(response.ok(),await response.text()).toBeTruthy();
  await page.getByRole("button",{name:"Rename "+name,exact:true}).click();let dialog=page.getByRole("dialog");
  await dialog.getByLabel("Definition name",{exact:true}).fill(name+" renamed");pending=write("PUT");await dialog.getByRole("button",{name:"Save name",exact:true}).click();response=await pending;expect(response.ok(),await response.text()).toBeTruthy();await expect(dialog).toHaveCount(0);
  await page.getByRole("button",{name:"Delete "+name+" renamed",exact:true}).click();pending=write("DELETE");await page.getByRole("dialog").getByRole("button",{name:"Confirm delete",exact:true}).click();response=await pending;expect(response.ok(),await response.text()).toBeTruthy();await expect(page.getByRole("button",{name:"Rename "+name+" renamed",exact:true})).toHaveCount(0);
 });
}
