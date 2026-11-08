import {test,expect,type Page} from "../frontend/node_modules/playwright/test";
import {authenticateCrm} from "./crm-core-test-utils";
const endpoints={contacts:"/crm/contacts",companies:"/master-data/companies",deals:"/crm/deals",tasks:"/crm/tasks",projects:"/project-management/projects"};
type Kind=keyof typeof endpoints;

for(const width of [1440,390]) for(const kind of ["contacts","companies","deals","tasks",...(width===1440?["projects" as const]:[])] as Kind[]) for(const entry of ["page"] as const) for(const module of (kind==="tasks"?["crm","pms"]:kind==="projects"?["pms"]:["crm"])) {
  test(`${module} ${kind}: ${entry} create edit delete refresh in place at ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:1000});
    await authenticateCrm(page);
    await page.addInitScript(()=>{const auth=JSON.parse(sessionStorage.getItem('hrms-auth')||'{}');auth.state.accessToken=`qa.${btoa(JSON.stringify({sid:'edit-delete-qa'}))}.signature`;sessionStorage.setItem('hrms-auth',JSON.stringify(auth));});
    await page.routeWebSocket("**/api/v1/project-management/realtime**",socket=>socket.close());
    let created:any,posts=0,mutated=false,deleted=false;const prompts:string[]=[];const errors:string[]=[];
    page.on("dialog",async dialog=>{prompts.push(dialog.message());if(/discard|unsaved/i.test(dialog.message()))await dialog.dismiss();else await dialog.accept();});
    page.on("pageerror",error=>errors.push(error.message));
    const name=`QA ${module} ${kind} ${entry} ${width}`;
    await page.route("**/api/v1/**",async route=>{
      const req=route.request(),url=new URL(req.url()),path=url.pathname.replace(/^\/api\/v1/,"");
      if((path===endpoints[kind] || (kind==="tasks"&&/\/project-management\/projects\/\d+\/tasks$/.test(path))) && req.method()==="POST") {
        posts++;const body=req.postDataJSON();
        created={id:900001,name,...body,project_id:kind==="tasks"?1:undefined,task_key:"QA-1",work_type:"Task",assignees:[],created_at:"2026-11-07T00:00:00Z",updated_at:"2026-11-07T00:00:00Z",status:body.status||"Active",version:1,can_edit_project:true,can_manage_tasks:true,project_key:"QA",tags:body.tags||[],roles:body.roles||["Prospect"],entityKind:body.entityKind||"Company",phoneCountryCode:body.phoneCountryCode||"+91",dueDate:body.due_date,health:{score:50,reasons:[]}};
        return route.fulfill({status:201,json:created});
      }
      const recordPath=path===`${endpoints[kind]}/${created?.id}`||path===`/project-management/tasks/${created?.id}`;
      if(created&&recordPath&&['PATCH','PUT','DELETE'].includes(req.method())){mutated=true;if(req.method()==='DELETE'){deleted=true;return route.fulfill({status:204});}created={...created,...req.postDataJSON(),version:2};return route.fulfill({json:created});}
      if(created&&recordPath&&req.method()==='GET')return route.fulfill({json:created});
      if(created&&path===`/crm/deal-workspace/${created.id}/record`)return route.fulfill({json:created});
      if(created&&path==='/master-data/company-directory/bulk'&&req.method()==='POST'){mutated=true;deleted=true;return route.fulfill({json:{successful_ids:[created.id]}});}
      let body:any;
      if(path==="/catalog/items")body={items:[],total:0,pages:0,permissions:{product:true,service:true}};
      else if(path==="/access/settings/defaults/effective") body={values:{},modules:{},companyId:1,branchId:1};
      else if(path==="/pipeline-workspaces/project_management/portfolio/views")body={preferences:{module_filters:{}},views:[],can_share:true};
      else if(path==="/project-management/projects")body=[];
      else if(path==="/project-management/custom-fields")body={fields:[]};
      else if(path==="/project-management/workspaces")body=[{id:1,name:"QA workspace",role:"Owner"}];
      else if(path==="/project-management/saved-views")body=[];
      else if(path==="/project-management/tasks")body={items:[],total:0,page:1,pageSize:25,pages:0,filters:{projects:[{id:1,name:"QA project",can_manage_tasks:true}],statuses:["To Do","In Progress","Done"],priorities:["Low","Medium","High"],assignees:[],reporters:[],sprints:[],epics:[],tags:[]}};
      else if(path==="/project-management/task-studio/options")body={people:[]};
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
        if(mutated)await new Promise(resolve=>setTimeout(resolve,2500));
        if(Array.isArray(body))return route.fulfill({json:deleted?[]:[created]});
        const key=Array.isArray(body.rows)?"rows":"items";
        body={...body,[key]:deleted?[]:[created],total:deleted?0:1,...(key==="rows"?{pageTotal:1}:{})};
      }
      return route.fulfill({json:body});
    });
    await page.goto(`/${module}/${kind}`);
    const add=kind==="contacts"?"Create contact":kind==="companies"?"Create company":kind==="deals"?"Create deal":kind==="projects"?"New Project":"Add Task";
    await expect(page.getByRole("button",{name:add,exact:true}).first()).toBeVisible({timeout:20000});
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
    else if(kind==="projects") {await page.getByPlaceholder("What are you working on?").fill(name);await page.getByLabel("Project workspace",{exact:true}).selectOption("1");save=page.getByRole("dialog").getByRole("button",{name:"Create project",exact:true});}
    else if(kind==="tasks") {await page.getByPlaceholder("What needs to be done?").fill(name);await page.getByText("More task details",{exact:true}).click();await page.getByPlaceholder("Context and acceptance criteria").fill("Preserve the complete task description");await page.getByRole("dialog").getByLabel("Priority",{exact:true}).selectOption("High");save=page.getByRole("button",{name:"Create task",exact:true}).last();}
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
    if(kind==="tasks"){expect(created.description).toBe("Preserve the complete task description");expect(created.priority).toBe("High");}
    expect(posts).toBe(1);
    const edited=kind==='tasks'&&width<640?name:name+' edited';
    if(kind==='tasks'&&width<640){
      await page.getByRole('button',{name:`Task actions for ${name}`,exact:true}).click();await page.getByRole('menuitem',{name:'Mark complete',exact:true}).click();
      await expect(page.getByRole('article').filter({hasText:name}).getByText('✓ Completed',{exact:true})).toBeVisible({timeout:1200});
    }else if(kind==='tasks'){
      await page.getByRole('button',{name:`Edit title for ${name}`,exact:true}).click();const input=page.getByLabel('Title for QA-1',{exact:true});await input.fill(edited);await input.press('Enter');
    }else if(kind==='projects'){
      await page.getByRole('button',{name:'Rename',exact:true}).click();const input=page.getByLabel(`New name for ${name}`,{exact:true});await input.fill(edited);await input.press('Enter');await expect(input).toHaveCount(0,{timeout:1200});
    }else{
      await page.getByRole('button',{name:kind==='deals'?`Edit deal ${name}`:`Edit ${name}`,exact:true}).click();const d=page.getByRole('dialog').last();
      if(kind==='contacts')await d.getByPlaceholder('Enter contact name').fill(edited);
      else if(kind==='companies')await d.getByLabel('Company name *',{exact:true}).fill(edited);
      else await d.getByPlaceholder('Enter deal name...').fill(edited);
      await d.getByRole('button',{name:kind==='companies'?'Save company':'Save changes',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0,{timeout:1200});
    }
    await expect(page.getByText(edited,{exact:true}).filter({visible:true}).first()).toBeVisible({timeout:1200});
    if(kind==='contacts'){await page.getByLabel(`Select ${edited}`,{exact:true}).check();await page.getByRole('button',{name:'Delete',exact:true}).click();}
    else if(kind==='companies'){await page.getByRole('row').filter({hasText:edited}).getByRole('checkbox').check();await page.getByRole('button',{name:'Move to trash',exact:true}).click();}
    else if(kind==='deals'){await page.getByRole('button',{name:`Actions for ${edited}`,exact:true}).click();await page.getByRole('menuitem',{name:'Archive deal',exact:true}).click();}
    else{await page.getByRole('button',{name:`${kind==='projects'?'Project':'Task'} actions for ${edited}`,exact:true}).click();await page.getByRole('menuitem',{name:kind==='projects'?/Move to trash/:/Delete task/}).click();await page.getByRole('dialog').getByRole('button',{name:'Move to trash',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0,{timeout:1200});await expect(page.getByLabel(`Select ${edited}`,{exact:true})).toHaveCount(0,{timeout:1200});}
    await expect(page.getByRole('row').filter({hasText:edited})).toHaveCount(0,{timeout:1200});expect(prompts.filter(text=>/discard|unsaved/i.test(text))).toEqual([]);expect(errors).toEqual([]);

    expect(page.url()).toBe(original);expect(await heading!.evaluate(el=>el.isConnected)).toBe(true);
  });
}
