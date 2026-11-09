import {test,expect,type Page} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";
const endpoints={contacts:"/crm/contacts",companies:"/master-data/companies",deals:"/crm/deals",tasks:"/crm/tasks",projects:"/project-management/projects"};
type Kind=keyof typeof endpoints;

for(const width of [1440,390]) for(const kind of Object.keys(endpoints) as Kind[]) for(const entry of ["page","menu"] as const) for(const module of (kind==="tasks"?["crm","pms"]:kind==="projects"?["pms"]:["crm"])) {
  test(`${module} ${kind}: ${entry} create closes and appears immediately at ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:1000});
    await authenticateCrm(page);
    await page.routeWebSocket("**/api/v1/project-management/realtime**",socket=>socket.close());
    let created:any,posts=0;const prompts:string[]=[];const errors:string[]=[];
    page.on("dialog",async dialog=>{prompts.push(dialog.message());await dialog.dismiss();});
    page.on("pageerror",error=>errors.push(error.message));
    const name=`QA ${module} ${kind} ${entry} ${width}`;
    await page.route("**/api/v1/**",async route=>{
      const req=route.request(),url=new URL(req.url()),path=url.pathname.replace(/^\/api\/v1/,"");
      if((path===endpoints[kind] || (kind==="tasks"&&/\/project-management\/(?:task-studio\/)?projects\/\d+\/tasks$/.test(path))) && req.method()==="POST") {
        posts++;const payload=req.postDataJSON();const body=payload.task||payload;
        created={id:900001,name,...body,project_id:kind==="tasks"?1:undefined,task_key:"QA-1",work_type:"Task",assignees:[],created_at:"2026-11-07T00:00:00Z",updated_at:"2026-11-07T00:00:00Z",status:body.status||"Active",version:1,tags:body.tags||[],roles:body.roles||["Prospect"],entityKind:body.entityKind||"Company",phoneCountryCode:body.phoneCountryCode||"+91",dueDate:body.due_date,health:{score:50,reasons:[]}};
        return route.fulfill({status:201,json:path.includes("/task-studio/")?{task:created,assignment:payload.assignment,version:"1",can_edit:true,protected_ids:[]}:created});
      }
      let body:any;
      if(path==="/catalog/items")body={items:[],total:0,pages:0,permissions:{product:true,service:true}};
      else if(path==="/access/settings/defaults/effective") body={values:{},modules:{},companyId:1,branchId:1};
      else if(path==="/pipeline-workspaces/project_management/portfolio/views")body={preferences:{module_filters:{}},views:[],can_share:true};
      else if(path==="/project-management/task-studio/projects")body=[{id:1,name:"QA project",project_key:"QA",workspace_id:1,can_manage_tasks:true}];
      else if(path==="/project-management/projects")body=[];
      else if(path==="/project-management/custom-fields")body={fields:[]};
      else if(path==="/project-management/workspaces")body=[{id:1,name:"QA workspace",role:"Owner"}];
      else if(path==="/project-management/saved-views")body=[];
      else if(path==="/project-management/tasks")body={items:[],total:0,page:1,pageSize:25,pages:0,filters:{projects:[{id:1,name:"QA project",can_manage_tasks:true}],statuses:["To Do","In Progress","Done"],priorities:["Low","Medium","High"],assignees:[],reporters:[],sprints:[],epics:[],tags:[]}};
      else if(path==="/project-management/task-studio/options")body={people:[],teams:[],batches:[],reviewers:[],can_edit:true,can_add_existing:false,batch_reason:""};
      else if(path==="/access/setup")body={companyId:1,ready:true,items:[]};
      else if(path==="/master-data/form-options")body={country:"IN",currency:"INR",phone_country_code:"+91"};
      else if(path==="/master-data/companies/custom-fields"||path==="/crm/custom-fields")body={items:[],customFields:[]};
      else if(path==="/master-data/companies")body={items:[]};
      else if(path==="/crm/contacts")body={items:[],total:0,page:1,pages:1};
      else if(path==="/crm/tasks")body={items:[],total:0,pages:1};
      else if(["/master-data/company-directory/query","/crm/deal-workspace/grid/query"].includes(path))body={rows:[],total:0,pageTotal:0,page:1,pageSize:25,permissions:{edit:true,export:true,archive:true,assign:true},context:{canCreate:true,summary:{counts:{},currencies:[],stages:[],forecast:[],breakdowns:{},definitions:{}}}};
      else if(path==="/crm/deal-workspace/pipelines")body={items:[{id:1,name:"Sales",is_default:true}]};
      else if(path==="/crm/deal-workspace/pipeline-stages")body={items:[{id:1,name:"Qualification",pipeline_id:1,probability:20}]};
      else if(path.startsWith("/crm/deal-workspace/"))body={items:[],can_manual_probability:false};
      if(body===undefined)return route.fallback();
      const list=kind==="contacts"?path==="/crm/contacts":kind==="companies"?path==="/master-data/company-directory/query":kind==="deals"?path==="/crm/deal-workspace/grid/query":kind==="projects"?path==="/project-management/projects":["/crm/tasks","/project-management/tasks"].includes(path);
      if(created&&list) {
        await new Promise(resolve=>setTimeout(resolve,1800));
        if(Array.isArray(body))return route.fulfill({json:[created]});
        const key=Array.isArray(body.rows)?"rows":"items";
        body={...body,[key]:[created],total:1,...(key==="rows"?{pageTotal:1}:{})};
      }
      return route.fulfill({json:body});
    });
    await page.goto(`/${module}/${kind}`);
    const add=kind==="contacts"?"Create contact":kind==="companies"?"Create company":kind==="deals"?"Create deal":kind==="projects"?"New Project":"Add Task";
    await expect(page.getByRole("button",{name:add,exact:true}).first()).toBeVisible({timeout:20000});
    const cards=page.getByRole("tab",{name:"Cards",exact:true});
    if(await cards.isVisible())await cards.click();
    const original=page.url();
    const heading=await page.locator("#suite-main h1,main h1").first().elementHandle();
    if(entry==="page")await page.getByRole("button",{name:add,exact:true}).first().click();
    else {
      if(width<640) {
        const toggle=page.getByRole("button",{name:/open.*(menu|navigation)|toggle.*(menu|navigation)/i}).first();
        if(await toggle.count())await toggle.click();
      }
      const search=page.getByRole("textbox",{name:"Find a page in this application"});
      if(await search.isVisible())await search.fill(kind);
      const label=kind==="contacts"?"Contact":kind==="companies"?"Company":kind==="deals"?"Deal":kind==="projects"?"Project":module==="pms"?"Task":"in Tasks";
      await page.getByRole("button",{name:`Create ${label}`,exact:true}).first().click();
      if(kind==="tasks"&&module==="crm")await page.getByRole("menuitem",{name:/^Task\b/}).click();
    }
    let save;
    if(kind==="contacts") {await page.getByPlaceholder("Enter contact name").fill(name);save=page.getByRole("dialog").getByRole("button",{name:"Create contact",exact:true});}
    else if(kind==="companies") {await page.getByLabel("Company name *",{exact:true}).fill(name);save=page.getByRole("button",{name:"Save company",exact:true});}
    else if(kind==="projects") {await page.getByRole("textbox",{name:"Project name",exact:true}).fill(name);await page.getByLabel("Project workspace",{exact:true}).selectOption("1");save=page.getByRole("dialog").getByRole("button",{name:"Create project",exact:true}).last();}
    else if(kind==="tasks") {await page.getByPlaceholder("What needs to be done?").fill(name);await page.getByRole("textbox",{name:"Task description",exact:true}).fill("Preserve the complete task description");await page.getByRole("dialog").getByLabel("Priority",{exact:true}).selectOption("High");save=page.getByRole("button",{name:/^Create task$/i}).last();}
    else {
      await page.getByPlaceholder("Enter deal name...").fill(name);
      const pipeline=page.getByRole('dialog').last().locator('select[aria-label="Pipeline"]');
      const choice=await pipeline.locator('option').evaluateAll(options=>options.map(o=>(o as HTMLOptionElement).value).find(Boolean));
      await pipeline.selectOption(choice!);
      const stage=page.getByRole('dialog').last().getByLabel(/^Stage/);
      const stageChoice=await stage.locator('option').evaluateAll(options=>options.map(o=>(o as HTMLOptionElement).value).find(Boolean));
      await stage.selectOption(stageChoice!);save=page.getByRole("button",{name:"Create Deal",exact:true});
    }
    await expect(save).toBeVisible();await expect(save).toBeEnabled();
    const box=await save.boundingBox();expect(box!.y).toBeGreaterThanOrEqual(0);expect(box!.y+box!.height).toBeLessThanOrEqual(1000);
    await save.click();
    await expect(page.getByRole("dialog")).toHaveCount(0,{timeout:1200});
    await expect(page.getByText(name,{exact:true}).filter({visible:true}).first()).toBeVisible({timeout:1200});
    if(kind==="tasks"){expect(created.description).toContain("Preserve the complete task description");expect(created.priority).toBe("High");}
    expect(posts).toBe(1);expect(prompts).toEqual([]);expect(errors).toEqual([]);
    expect(page.url()).toBe(original);expect(await heading!.evaluate(el=>el.isConnected)).toBe(true);
  });
}

for(const width of [1440,390])test(`campaign draft review and save close the editor at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  let created:any,posts=0,sends=0;
  await page.route("**/__campaign_save_qa",route=>route.fulfill({contentType:"text/html",body:`<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/campaign-save-qa.tsx"></script></body></html>`}));
  await page.route("**/api/v1/**",route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path.endsWith("/send")){sends++;return route.fulfill({status:409,json:{detail:"Sending is blocked in this test"}});}
    if(path.endsWith("/email-templates"))return route.fulfill({json:{items:[{id:1,name:"QA template",subject:"Draft only",active:true}],total:1}});
    if(path.endsWith("/campaigns")&&req.method()==="POST"){posts++;created={id:900001,...req.postDataJSON()};return route.fulfill({status:201,json:created});}
    if(path.endsWith("/campaigns/900001"))return route.fulfill({json:created});
    return route.fulfill({json:{items:created?[created]:[],total:created?1:0}});
  });
  await page.goto("/__campaign_save_qa");
  await page.getByRole("button",{name:"Create campaign",exact:true}).click();
  await page.getByLabel("Campaign name",{exact:true}).fill("QA draft campaign");
  await page.getByRole("combobox",{name:"Email template",exact:true}).selectOption("1");
  await expect(page.getByRole("contentinfo").getByRole("button",{name:"Review & save draft",exact:true})).toBeVisible();
  await page.getByLabel("Campaign name",{exact:true}).focus();
  await page.keyboard.press("Control+s");
  const save=page.getByRole("contentinfo").getByRole("button",{name:"Create reviewed draft",exact:true});
  await expect(save).toBeVisible();
  await save.click();
  await expect(page.getByRole("heading",{name:"New email campaign",exact:true})).toHaveCount(0);
  await expect(page.getByText("QA draft campaign",{exact:true}).first()).toBeVisible();
  expect(created.status).toBe("draft");expect(posts).toBe(1);expect(sends).toBe(0);
});
