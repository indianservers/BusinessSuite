import {test,expect} from "../frontend/node_modules/playwright/test";
import {mkdirSync} from "node:fs";
import {resolve} from "node:path";
import {authenticate} from "./srm-test-utils";

const kinds=["product","service","membership","subscription","bundle"];
const labels=["Products","Services","Memberships","Subscriptions","Bundles"];
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
