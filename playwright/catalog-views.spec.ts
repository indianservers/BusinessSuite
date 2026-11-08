import {test,expect,type Page} from "../frontend/node_modules/playwright/test";
import {resolve} from "node:path";
import {authenticate} from "./srm-test-utils";

async function setup(page:Page,write=true){
  await authenticate(page,"admin");
  await page.route("**/api/v1/access/settings/defaults/effective",r=>r.fulfill({json:{values:{},modules:{},companyId:1}}));
  await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  let records=Array.from({length:28},(_,i)=>({id:i+1,kind:i===2?"service":"product",name:i===0?"Cloud Platform":i===1?"Laptop Pro":i===2?"Consulting":`Offering ${String(i+1).padStart(2,"0")}`,code:`SKU-${i+1}`,description:"Shared offering for your business",category:i%2===0?"Software":"Hardware",tags:i===0?["cloud","recurring"]:i===1?["equipment"]:[],price:100+i,currency:"INR",tax:18,unit:"unit",status:"Active",workspace_id:null,images:[],custom_fields:{},pricing_options:[],version:1}));
  const writes:{method:string;path:string;body:any}[]=[],requests:URL[]=[];
  await page.route("**/api/v1/catalog/**",async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname.replace("/api/v1/catalog","");
    if(request.method()!=="GET")writes.push({method:request.method(),path,body:request.postDataJSON()});
    if(path==="/items"&&request.method()==="GET"){
      requests.push(url);const p=url.searchParams;
      let items=records.filter(item=>(!p.get("kind")||item.kind===p.get("kind"))&&(p.get("status")==="all"||item.status===(p.get("status")||"Active"))&&(!p.get("search")||(item.name+item.code+item.description).toLowerCase().includes(p.get("search")!.toLowerCase()))&&(!p.get("category")||item.category===p.get("category")));
      const keys=p.has("item_keys")?(p.get("item_keys")||"").split(",").filter(Boolean):null;
      if(keys)items=items.filter(item=>keys.includes(`${item.kind}:${item.id}`));
      const facets={categories:[...new Set(items.map(item=>item.category))],tags:[...new Set(items.flatMap(item=>item.tags))]};
      if(p.get("tag"))items=items.filter(item=>item.tags.includes(p.get("tag")!));
      items.sort((a,b)=>p.get("key_order")==="true"&&keys?keys.indexOf(`${a.kind}:${a.id}`)-keys.indexOf(`${b.kind}:${b.id}`):String((a as any)[p.get("sort")||"name"]).localeCompare(String((b as any)[p.get("sort")||"name"]))*(p.get("direction")==="desc"?-1:1));
      const count=Number(p.get("per_page")||24),pageNumber=Number(p.get("page")||1);
      return route.fulfill({json:{items:items.slice((pageNumber-1)*count,pageNumber*count),total:items.length,pages:Math.ceil(items.length/count),permissions:{product:write,service:write},facets}});
    }
    const match=path.match(/^\/items\/(product|service)\/(\d+)(?:\/(duplicate|archive))?$/);
    if(match){let item=records.find(item=>item.kind===match[1]&&item.id===Number(match[2]))!;
      if(match[3]==="duplicate"){const copy={...item,id:100+records.length,name:item.name+" copy",code:item.code+"-COPY"};records.push(copy);return route.fulfill({status:201,json:copy});}
      if(match[3]==="archive"){item.status="Archived";return route.fulfill({json:item});}
      if(request.method()==="PUT"){Object.assign(item,request.postDataJSON(),{version:item.version+1});}
      return route.fulfill({json:item});
    }
    return route.fulfill({json:{items:[]}});
  });
  return {writes,requests};
}
const panel=(page:Page)=>page.getByRole("tabpanel");
const view=(page:Page,name:string)=>page.getByRole("tab",{name,exact:true}).click();
const card=(page:Page,name:string)=>panel(page).locator(".sc-card").filter({has:page.getByRole("button",{name,exact:true})});

test("list, category and multi-tag views display the same catalog with working filters",async({page})=>{
  await setup(page);await page.goto("/srm/products-services");await expect(card(page,"Cloud Platform")).toBeVisible();
  await view(page,"List");await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Cloud Platform"})).toBeVisible();
  await view(page,"Categories");await expect(panel(page).getByRole("button",{name:"Collapse category Software",exact:true})).toBeVisible();
  await panel(page).getByRole("button",{name:"Collapse category Software",exact:true}).click();await expect(card(page,"Cloud Platform")).toHaveCount(0);
  await view(page,"Tags");await expect(panel(page).getByRole("button",{name:"Collapse tag cloud",exact:true})).toBeVisible();await expect(card(page,"Cloud Platform")).toHaveCount(2);
  await page.getByLabel("Filter tag",{exact:true}).selectOption("equipment");await expect(card(page,"Laptop Pro")).toHaveCount(1);await expect(card(page,"Cloud Platform")).toHaveCount(0);
  await page.getByRole("button",{name:"Clear filters",exact:true}).click();await expect(card(page,"Cloud Platform")).toHaveCount(2);
});

test("favorites retrieve records from another page and persist across reloads",async({page})=>{
  const {requests}=await setup(page);await page.goto("/srm/products-services");await page.getByLabel("Catalog rows per page",{exact:true}).selectOption("12");
  await page.getByRole("button",{name:"Next",exact:true}).last().click();await expect(card(page,"Offering 13")).toBeVisible();
  await card(page,"Offering 13").getByRole("button",{name:"Favorite Offering 13",exact:true}).click();await view(page,"Favorites");
  await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Offering 13"})).toBeVisible();expect(requests.at(-1)?.searchParams.get("item_keys")).toBe("product:13");
  await page.reload();await expect(page.getByRole("tab",{name:"Favorites",exact:true})).toHaveAttribute("aria-selected","true");await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Offering 13"})).toBeVisible();
  await panel(page).getByRole("button",{name:"Unfavorite Offering 13",exact:true}).click();await expect(panel(page).getByText("No matching favorites",{exact:true})).toBeVisible();
  await page.evaluate(()=>sessionStorage.setItem("suite-organization","99"));await page.reload();await view(page,"Favorites");await expect(panel(page).getByText("No matching favorites",{exact:true})).toBeVisible();
});

test("frequent view ranks real preview opens and saves them",async({page})=>{
  await setup(page);await page.goto("/srm/products-services");
  for(const name of ["Laptop Pro","Cloud Platform","Laptop Pro"]){await card(page,name).getByRole("button",{name,exact:true}).click();await page.getByRole("button",{name:"Close preview",exact:true}).click();}
  await view(page,"Frequent");await expect(panel(page).locator(".sc-list-identity").first()).toContainText("Laptop Pro");await expect(panel(page).locator(".sc-list-identity")).toHaveCount(2);
  await page.reload();await expect(panel(page).locator(".sc-list-identity").first()).toContainText("Laptop Pro");
});

test("tag action saves shared tags using the current version and updates tag view",async({page})=>{
  const {writes}=await setup(page);await page.goto("/srm/products-services");await card(page,"Cloud Platform").getByRole("button",{name:"Manage tags for Cloud Platform",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Item tags",{exact:true}).fill("Priority, recurring");await page.getByRole("button",{name:"Save tags",exact:true}).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);expect(writes.find(write=>write.method==="PUT")?.body).toMatchObject({tags:["priority","recurring"],version:1});
  await view(page,"Tags");await expect(panel(page).getByRole("button",{name:"Collapse tag priority",exact:true})).toBeVisible();
});

test("quick copy, duplicate and reviewed archive invoke their existing actions",async({page,context})=>{
  await context.grantPermissions(["clipboard-read","clipboard-write"]);const {writes}=await setup(page);await page.goto("/srm/products-services");
  await card(page,"Cloud Platform").getByRole("button",{name:"Copy code for Cloud Platform",exact:true}).click();await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toBe("SKU-1");
  await card(page,"Cloud Platform").getByRole("button",{name:"More actions for Cloud Platform",exact:true}).click();await page.getByRole("menuitem",{name:"Duplicate item",exact:true}).click();await expect(card(page,"Cloud Platform copy")).toBeVisible();
  await card(page,"Cloud Platform").getByRole("button",{name:"More actions for Cloud Platform",exact:true}).click();await page.getByRole("menuitem",{name:"Archive item",exact:true}).click();expect(writes.filter(write=>write.path.endsWith("archive"))).toHaveLength(0);
  await page.getByRole("dialog").getByRole("button",{name:"Archive item",exact:true}).click();await expect(card(page,"Cloud Platform")).toHaveCount(0);expect(writes.filter(write=>write.path.endsWith("archive"))).toHaveLength(1);
});

test("view-only users can browse and favorite but cannot mutate catalog records",async({page})=>{
  const {writes}=await setup(page,false);await page.goto("/srm/products-services");await view(page,"List");await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Cloud Platform"})).toBeVisible();
  await expect(panel(page).getByRole("button",{name:/^(Edit |Manage tags for |More actions for )/})).toHaveCount(0);await panel(page).getByRole("button",{name:"Favorite Cloud Platform",exact:true}).click();await view(page,"Favorites");await expect(panel(page).locator(".sc-list-identity")).toHaveCount(1);expect(writes).toHaveLength(0);
});

test("edit and branch reuse keep their existing working forms",async({page})=>{
  const {writes}=await setup(page);await page.goto("/srm/products-services");await card(page,"Cloud Platform").getByRole("button",{name:"Edit Cloud Platform",exact:true}).click();
  await page.getByRole("dialog").getByLabel("Name",{exact:true}).fill("Cloud Platform Plus");await page.getByRole("button",{name:"Save item",exact:true}).click();await expect(card(page,"Cloud Platform Plus")).toBeVisible();
  expect(writes.find(write=>write.method==="PUT")?.body).toMatchObject({name:"Cloud Platform Plus",tags:["cloud","recurring"]});
  await card(page,"Cloud Platform Plus").getByRole("button",{name:"More actions for Cloud Platform Plus",exact:true}).click();await page.getByRole("menuitem",{name:"Reuse in other branches",exact:true}).click();
  await expect(page.getByRole("dialog")).toContainText(/branches/i);expect(writes.filter(write=>write.path.includes("reuse"))).toHaveLength(0);await page.keyboard.press("Escape");
});

test("failed tag saves retain the draft and keyboard view navigation works",async({page})=>{
  await setup(page);await page.route("**/api/v1/catalog/items/product/1**",r=>r.request().method()==="PUT"?r.fulfill({status:409,json:{detail:"This item changed. Reload before saving."}}):r.fallback());
  await page.goto("/srm/products-services");await page.getByRole("tab",{name:"Cards",exact:true}).focus();await page.keyboard.press("ArrowRight");await expect(page.getByRole("tab",{name:"List",exact:true})).toHaveAttribute("aria-selected","true");
  await panel(page).getByRole("button",{name:"Manage tags for Cloud Platform",exact:true}).click();await page.getByLabel("Item tags",{exact:true}).fill("important");await page.getByRole("button",{name:"Save tags",exact:true}).click();await expect(page.getByRole("dialog").getByRole("alert")).toContainText("This item changed");await expect(page.getByLabel("Item tags",{exact:true})).toHaveValue("important");
});

for(const source of ["pms","crm"]){test(`catalog views work through ${source}`,async({page})=>{const {requests}=await setup(page);await page.goto(`/${source}/products-services`);await view(page,"List");await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Cloud Platform"})).toBeVisible();expect(requests.at(-1)?.searchParams.get("source")).toBe(source);});}

test("mobile category view stays within the viewport and keeps actions usable",async({page})=>{
  await page.setViewportSize({width:390,height:844});await setup(page);await page.goto("/srm/products-services");await view(page,"Categories");await expect(card(page,"Cloud Platform")).toBeVisible();
  await card(page,"Cloud Platform").getByRole("button",{name:"Favorite Cloud Platform",exact:true}).click();await expect(card(page,"Cloud Platform").getByRole("button",{name:"Unfavorite Cloud Platform",exact:true})).toHaveAttribute("aria-pressed","true");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBeTruthy();
});

test("capture the finished list and category workspaces",async({page},testInfo)=>{
  await page.setViewportSize({width:1600,height:1100});await setup(page);await page.goto("/srm/products-services");await view(page,"List");await expect(panel(page).locator(".sc-list-identity").filter({hasText:"Cloud Platform"})).toBeVisible();await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/catalog-views/List.png")});
  await view(page,"Categories");await expect(card(page,"Cloud Platform")).toBeVisible();await page.screenshot({path:resolve(testInfo.project.testDir,"../outputs/catalog-views/Categories.png")});
});
