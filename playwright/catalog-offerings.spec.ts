import {test,expect} from "../frontend/node_modules/playwright/test";
import {mkdirSync} from "node:fs";
import {resolve} from "node:path";
import {authenticate} from "./srm-test-utils";

const kinds=["product","service","membership","subscription","bundle"];
const labels=["Products","Services","Memberships","Subscriptions","Bundles"];

test("mobile Sales Report keeps populated results and filters in one view", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await authenticate(page, "admin");

  await page.route("**/api/v1/srm/reporting/offering-sales?**", route => {
    const params = new URL(route.request().url()).searchParams;
    const pageNumber = Number(params.get("page") ?? 1);
    const kind = params.get("kind") ?? "product";
    return route.fulfill({ json: {
      start: params.get("start") ?? "2026-11-01",
      end: params.get("end") ?? "2026-11-21",
      has_more: pageNumber === 1,
      totals: [{ currency: "INR", gross: "1500" }],
      items: [{ kind, name: `QA ${kind} ${pageNumber}`, currency: "INR", quantity: 2, tax: "275", gross: "1500" }],
    } });
  });

  await page.goto("/srm/sales-report");
  const results = page.getByRole("list", { name: "Sales by offering and currency" });
  await expect(results.getByText("QA product 1", { exact: true })).toBeVisible();
  const offering = page.getByRole("combobox", { name: /Offering type/ });
  await offering.selectOption("subscription");
  await expect(results.getByText("QA subscription 1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(results.getByText("QA subscription 2", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Report dates", exact: true }).click();
  const dates = page.getByRole("dialog", { name: "Report dates" });
  await dates.getByLabel("From", { exact: true }).fill("2026-11-10");
  await dates.getByLabel("To", { exact: true }).fill("2026-11-20");
  await dates.getByRole("button", { name: "Apply dates", exact: true }).click();
  await expect(results.getByText("QA subscription 1", { exact: true })).toBeVisible();
  await expect(page.getByText("2026-11-10 – 2026-11-20", { exact: true })).toBeVisible();
});

for(const mobile of [false,true])test(`all native catalog types reuse the same views and editor ${mobile?"mobile":"desktop"}`,async({page})=>{
 await page.setViewportSize(mobile?{width:390,height:844}:{width:1440,height:1000});
 await authenticate(page,"admin");
 const records=kinds.map((kind,i)=>({id:i+1,kind,name:`Business ${kind}`,code:`ITEM-${i+1}`,description:"Configurable business offering",category:"Business",tags:[],price:100,currency:"INR",tax:18,unit:"unit",status:"Active",workspace_id:null,images:[],custom_fields:{},pricing_options:[],version:1,
  ...(kind==="membership"||kind==="subscription"?{plan:{duration:{unit:"month",count:6},activation:"approval",benefits:[],billing:{mode:"prepaid",recurring:false,automation:false,interval_unit:"month",interval_count:1,timezone:"UTC"}}}:{}),
  ...(kind==="bundle"?{bundle:{type:"fixed",pricing:"package",components:[{offering_id:1,quantity:1,optional:false}]}}:{})}));
 await page.route("**/api/v1/catalog/**",async route=>{
  const url=new URL(route.request().url());
  if(url.pathname.endsWith("/items")){
   const items=records.filter(row=>!url.searchParams.get("kind")||url.searchParams.get("kind")===row.kind);
   return route.fulfill({json:{items,total:items.length,pages:1,permissions:Object.fromEntries(kinds.map(k=>[k,true]))}});
  }
  const match=url.pathname.match(/\/items\/([^/]+)\/(\d+)$/);
  if(match)return route.fulfill({json:records.find(row=>row.id===Number(match[2]))});
  return route.fulfill({json:{items:[],categories:[],tags:[]}});
 });
 await page.goto("/srm/products-services");
 const folder=resolve("../output/catalog-offerings",mobile?"mobile":"desktop");mkdirSync(folder,{recursive:true});
 const signatures=[];
 for(let i=0;i<kinds.length;i++){
  if(mobile){for(let step=0;step<5&&!await page.getByRole("group",{name:"Catalog type",exact:true}).isVisible();step++){const previous=page.getByRole("button",{name:"Previous section",exact:true});if(!await previous.isEnabled())break;await previous.click();}}
  await page.getByRole("group",{name:"Catalog type",exact:true}).getByRole("button",{name:labels[i],exact:true}).click();
  const card=page.locator(".sc-card").filter({hasText:`Business ${kinds[i]}`});if(mobile){for(let step=0;step<4&&!await card.isVisible();step++){const next=page.getByRole("button",{name:"Next section",exact:true});if(!await next.isEnabled())break;await next.click();}}await expect(card).toBeVisible();
  signatures.push(await card.evaluate(element=>{const s=getComputedStyle(element);return [s.fontFamily,s.fontSize,s.borderRadius,s.padding].join("|");}));
  await page.screenshot({path:resolve(folder,`${kinds[i]}-catalog.png`),fullPage:true});
  await card.getByRole("button",{name:`Business ${kinds[i]}`,exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();await page.getByRole("button",{name:"Edit item",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  if(["membership","subscription"].includes(kinds[i]))await expect(page.getByText("Plan duration & activation",{exact:true})).toBeVisible();
  if(kinds[i]==="bundle")await expect(page.getByText("Bundle components",{exact:true})).toBeVisible();
  await page.screenshot({path:resolve(folder,`${kinds[i]}-editor.png`),fullPage:true});
  await page.getByRole("button",{name:"Close catalog editor",exact:true}).click();
 }
 expect(new Set(signatures).size).toBe(1);
});
