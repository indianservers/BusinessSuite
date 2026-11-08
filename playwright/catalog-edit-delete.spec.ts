import {test,expect,type Page} from "../frontend/node_modules/playwright/test";
import {resolve} from "node:path";
import {authenticate} from "./srm-test-utils";

async function setup(page:Page,write=true,delay=0){
  await authenticate(page,"admin");
  await page.route("**/api/v1/access/settings/defaults/effective",r=>r.fulfill({json:{values:{},modules:{},companyId:1}}));
  await page.route("**/api/v1/access/setup",r=>r.fulfill({json:{companyId:1,ready:true,items:[]}}));
  let records=Array.from({length:28},(_,i)=>({id:i+1,kind:i===2?"service":"product",name:i===0?"Cloud Platform":i===1?"Laptop Pro":i===2?"Consulting":`Offering ${String(i+1).padStart(2,"0")}`,code:`SKU-${i+1}`,description:"Shared offering for your business",category:i%2===0?"Software":"Hardware",tags:i===0?["cloud","recurring"]:i===1?["equipment"]:[],price:100+i,currency:"INR",tax:18,unit:"unit",status:"Active",workspace_id:null,images:[],custom_fields:{},pricing_options:[],version:1}));
  const writes:{method:string;path:string;body:any}[]=[],requests:URL[]=[];
  await page.route("**/api/v1/catalog/**",async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname.replace("/api/v1/catalog","");
    if(request.method()!=="GET")writes.push({method:request.method(),path,body:request.postDataJSON()});
    if(path==="/items"&&request.method()==="GET"){
      if(writes.length&&delay)await new Promise(resolve=>setTimeout(resolve,delay));
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

for(const width of [1440,390])for(const source of ['crm','srm'])test(`catalog ${source} edit/archive retains rows during refresh at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});await setup(page,true,2500);await page.goto(`/${source}/products-services`);
 const row=card(page,'Cloud Platform');await expect(row).toBeVisible({timeout:20000});const other=await card(page,'Laptop Pro').elementHandle();const heading=await page.getByRole('heading',{name:'Products & services',exact:true}).elementHandle();const prompts:string[]=[];page.on('dialog',async d=>{prompts.push(d.message());await d.dismiss();});
 await row.getByRole('button',{name:'Edit Cloud Platform',exact:true}).click();const d=page.getByRole('dialog');await d.getByLabel('Name',{exact:true}).fill('Cloud Platform immediate');await expect(d.getByRole('button',{name:'Save item',exact:true})).toBeInViewport();await d.getByRole('button',{name:'Save item',exact:true}).click();
 await expect(d).toHaveCount(0,{timeout:1200});await expect(card(page,'Cloud Platform immediate')).toBeVisible({timeout:1200});await expect(card(page,'Laptop Pro')).toBeVisible({timeout:1200});
 await card(page,'Cloud Platform immediate').getByRole('button',{name:'More actions for Cloud Platform immediate',exact:true}).click();await page.getByRole('menuitem',{name:'Archive item',exact:true}).click();await d.getByRole('button',{name:'Archive item',exact:true}).click();await expect(d).toHaveCount(0,{timeout:1200});await expect(card(page,'Cloud Platform immediate')).toHaveCount(0,{timeout:1200});await expect(card(page,'Laptop Pro')).toBeVisible({timeout:1200});expect(await heading!.evaluate(el=>el.isConnected)).toBe(true);expect(prompts).toEqual([]);
});
