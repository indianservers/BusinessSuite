/* Real browser, real HTTP, fresh isolated backend. No API interception. */
const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const fs=require('node:fs'),path=require('node:path');
const origin=process.env.CREATE_REAL_ORIGIN||'http://127.0.0.1:5193';
if(new URL(origin).hostname!=='127.0.0.1')throw Error('Use the isolated loopback fixture');
const out=path.resolve('.local/create-menu-real');fs.mkdirSync(out,{recursive:true});
const tag='CREATEQA-'+Date.now();
const resultFile=path.join(out,'results.json');
const results=fs.existsSync(resultFile)?JSON.parse(fs.readFileSync(resultFile,'utf8')):[];
const esc=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
let browser,context,page,auth,headers,fixtures;
async function api(endpoint,method='GET',data){const response=await fetch(origin+'/api/v1'+endpoint,{method,headers:{...headers,...(data?{'Content-Type':'application/json'}:{})},body:data?JSON.stringify(data):undefined});const text=await response.text();let body;try{body=JSON.parse(text);}catch{body=text.slice(0,500);}if(!response.ok)throw Error(`${method} ${endpoint} ${response.status}: ${JSON.stringify(body).slice(0,900)}`);return body;}
async function setup(){
 const session=await api('/auth/login','POST',{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'});auth=session;headers={Authorization:'Bearer '+session.access_token,'X-Suite-Branch':'1','X-Suite-Organization':'1'};
 auth.access=await api('/access/me');auth.me=await api('/auth/me');
 const saved=path.join(out,'fixtures.json');
 if(fs.existsSync(saved)){fixtures=JSON.parse(fs.readFileSync(saved,'utf8'));try{await api('/project-management/projects/'+fixtures.project.id);return;}catch{}}
 const workspace=await api('/project-management/workspaces','POST',{name:tag+' workspace'});
 const project=await api('/project-management/projects','POST',{name:tag+' project',project_key:'CQ'+Date.now(),workspace_id:workspace.id});
 const parent=await api(`/project-management/projects/${project.id}/tasks`,'POST',{title:tag+' parent',task_key:'CQP'+Date.now(),status:'To Do'});
 fixtures={workspace,project,parent};fs.writeFileSync(saved,JSON.stringify(fixtures,null,2));
}
async function visit(module,width){
 context=await browser.newContext({viewport:{width,height:950},timezoneId:'Asia/Kolkata',serviceWorkers:'block'});
 await context.addInitScript(a=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:a.access_token,refreshToken:a.refresh_token,user:{...a.me,id:a.user_id,role:a.role,is_superuser:a.is_superuser,employee_id:a.employee_id,access:a.access},isAuthenticated:true},version:0}));},auth);
 page=await context.newPage();page.setDefaultTimeout(20000);page.setDefaultNavigationTimeout(90000);
 const route=module==='pms'?`/pms/workspaces?workspace=${fixtures.workspace.id}`:module==='crm'?'/crm/leads':'/hrms/employees';
 await page.goto(origin+route,{waitUntil:'domcontentloaded'});
 await page.locator('.suite-new-trigger:visible,.mobile-module-add:visible').first().waitFor({timeout:90000});
}
async function openMenu(){
 await page.locator('.suite-new-trigger:visible,.mobile-module-add:visible').first().click();
 await page.locator('.suite-new-menu:visible,.mobile-create-list:visible').first().waitFor();
 const all=page.getByRole('button',{name:/^View all \d+ actions$/});if(await all.count())await all.click();
}
async function select(label){await openMenu();const item=page.getByRole('menuitem').filter({has:page.locator('.suite-new-item-copy').filter({hasText:new RegExp('^'+esc(label)+'(?=[A-Z]|$)')})});if(await item.count())await item.click();else await page.locator('.mobile-create-list button').filter({has:page.locator('strong',{hasText:new RegExp('^'+esc(label)+'$')})}).click();}
async function fields(){return page.locator('input,select,textarea,[contenteditable=true]').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length).map(n=>({tag:n.tagName,type:n.type,name:n.name,label:n.getAttribute('aria-label')||n.labels?.[0]?.textContent?.trim(),placeholder:n.placeholder,value:n.value,options:n.tagName==='SELECT'?Array.from(n.options).map(o=>({value:o.value,text:o.text})):undefined})));}
async function diagnostic(row){row.url=page.url();row.headings=await page.locator('h1,h2,h3').allTextContents();row.fields=await fields();row.buttons=await page.locator('button').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length).map(n=>({text:n.textContent.trim(),label:n.getAttribute('aria-label'),disabled:n.disabled})));row.alerts=await page.locator('[role=alert],.md-error,.lm-error').allTextContents();}
async function record(module,action,width,run){
 const row={module,action,width,tag,status:'running',writes:[],errors:[]};
 try{await visit(module,width);page.on('pageerror',error=>row.errors.push(error.message));page.on('response',async response=>{const request=response.request(),p=new URL(response.url()).pathname;if(p.startsWith('/api/v1/')&&['POST','PUT','PATCH','DELETE'].includes(request.method()))row.writes.push({path:p,method:request.method(),status:response.status()});});await select(action);await run(row);row.status='passed';}
 catch(error){row.status='failed';row.error=error.message;await diagnostic(row).catch(()=>{});await page?.screenshot({path:path.join(out,`${module}-${action.replace(/[^a-z0-9]/gi,'-')}-${width}.png`)}).catch(()=>{});}
 finally{results.push(row);fs.writeFileSync(resultFile,JSON.stringify(results,null,2));console.log(JSON.stringify({module,action,width,status:row.status,error:row.error?.split('\n')[0]}));await context?.close();}
}
async function inventory(){
 const inventory=[];
 for(const module of ['pms','crm','hrms'])for(const width of [1440,390]){
  await visit(module,width);await openMenu();let labels=await page.locator('.suite-new-menu .suite-new-item-copy').evaluateAll(nodes=>nodes.map(n=>n.childNodes[0].textContent));if(!labels.length)labels=await page.locator('.mobile-create-list strong').allTextContents();inventory.push({module,width,labels});await page.screenshot({path:path.join(out,`menu-${module}-${width}.png`)});console.log(JSON.stringify(inventory.at(-1)));await context.close();
 }
 fs.writeFileSync(path.join(out,'inventory.json'),JSON.stringify(inventory,null,2));
}
async function inspect(){const module=process.env.CREATE_MODULE||'pms',action=process.env.CREATE_ACTION||'Quick task',width=Number(process.env.CREATE_WIDTH||1440);await record(module,action,width,async row=>{await page.waitForTimeout(1200);await diagnostic(row);row.status='inspected';});}
async function main(){await setup();browser=await chromium.launch();try{if(process.argv.includes('--inventory'))await inventory();else if(process.argv.includes('--inspect'))await inspect();else await runCases();}catch(error){if(page){await page.screenshot({path:path.join(out,'last-failure.png')}).catch(()=>{});fs.writeFileSync(path.join(out,'last-failure.txt'),(await page.locator('body').innerText()).slice(0,16000));}throw error;}finally{await browser?.close();}}
function dialog(){return page.locator('[role="dialog"]:visible').last();}
async function reveal(field,scope=dialog()){
 await field.waitFor({state:'attached'});if(await field.isVisible())return;
 for(const tab of await scope.locator('.suite-form-tabs button').all()){await tab.click();if(await field.isVisible())return;}
 await expect(field).toBeVisible();
}
async function fill(label,value,scope=dialog()){const input=scope.getByLabel(label,{exact:true});await reveal(input,scope);await input.fill(value);}
async function click(name,scope=page){const buttons=scope.getByRole('button',{name,exact:typeof name==='string'});for(let i=0;i<await buttons.count();i++)if(await buttons.nth(i).isVisible()){await buttons.nth(i).click();return;}await buttons.first().click();}
async function save(row,matcher,clicker){
 const waiting=page.waitForResponse(response=>['POST','PUT','PATCH'].includes(response.request().method())&&matcher(new URL(response.url()).pathname),{timeout:30000});
 await clicker();const response=await waiting;const body=await response.json();if(!response.ok())throw Error(`Save ${response.status()} ${new URL(response.url()).pathname}: ${JSON.stringify(body).slice(0,1000)}`);
 row.saved={path:new URL(response.url()).pathname,status:response.status(),id:body.id||body.task?.id};return body;
}
async function read(row,endpoint,needle){const stored=await api(endpoint);if(needle&&!JSON.stringify(stored).includes(needle))throw Error('Persisted readback did not contain '+needle);row.readback={endpoint,matched:true};return stored;}
const cases=[];
function test(module,action,handler){cases.push({module,action,handler});}
for(const action of ['Task','Story','Bug'])test('pms',action,async row=>{
 const name=tag+' '+action;await fill('Task Title',name);const project=dialog().getByLabel('Project',{exact:true});await reveal(project);await project.selectOption(String(fixtures.project.id));
 const data=await save(row,p=>/\/task-studio\/projects\/\d+\/tasks$/.test(p),()=>click('Create Task',dialog().locator('[data-smart-create-footer]')));const task=data.task||data;
 const stored=await read(row,'/project-management/tasks/'+task.id,name);if(stored.work_type!==action)throw Error('Work type was not retained');
});
for(const action of ['Quick task','Subtask'])for(const module of action==='Subtask'?['pms','crm']:['pms'])test(module,action,async row=>{
 const name=tag+' '+module+' '+action;const d=dialog();await d.getByLabel('Quick task project',{exact:true}).selectOption(String(fixtures.project.id));if(action==='Subtask')await d.getByLabel('Parent task',{exact:true}).selectOption(String(fixtures.parent.id));await fill('Title',name,d);
 const data=await save(row,p=>p===`/api/v1/project-management/projects/${fixtures.project.id}/tasks`,()=>click(action==='Subtask'?'Create subtask':'Create task',d));const stored=await read(row,'/project-management/tasks/'+data.id,name);if(action==='Subtask'&&stored.parent_task_id!==fixtures.parent.id)throw Error('Parent task not saved');
});
test('pms','Project',async row=>{const name=tag+' project';await fill('Project name',name);const workspace=dialog().getByLabel('Project workspace',{exact:true});await reveal(workspace);await workspace.selectOption(String(fixtures.workspace.id));const data=await save(row,p=>p==='/api/v1/project-management/projects',()=>click('Create project',dialog().locator('[data-smart-create-footer]')));await read(row,'/project-management/projects/'+data.id,name);});
for(const module of ['pms','crm'])for(const action of module==='pms'?['Private note','Page']:['Note','Page'])test(module,action,async row=>{
 const name=tag+' '+module+' '+action;const title=page.getByLabel('Note title',{exact:true});await title.waitFor();await title.fill(name);const editor=page.locator('[contenteditable=true]:visible').last();await editor.fill('Real API Create menu acceptance.');const data=await save(row,p=>/\/project-management\/notes(?:\/\d+)?$/.test(p),()=>page.keyboard.press('Control+s'));await read(row,'/project-management/notes/'+data.id,name);
});
for(const module of ['pms','crm'])test(module,'Document',async row=>{const name=tag+' '+module+' document';await click('New document');await fill('Document title',name,page);await page.getByLabel('Document project',{exact:true}).selectOption(String(fixtures.project.id));await page.locator('[contenteditable=true]:visible').last().fill('Create menu real API document.');const data=await save(row,p=>/\/projects\/\d+\/docs$/.test(p),()=>click('Save document'));await read(row,'/project-management/docs/'+data.id,name);});
test('crm','Add Lead',async row=>{const name=tag+' lead';await fill('Lead Name *',name);await fill('Email','createqa-'+Date.now()+'@example.com');const data=await save(row,p=>p==='/api/v1/crm/lead-management/leads',()=>click('Create lead',dialog()));await read(row,'/crm/lead-management/leads/'+data.id,name);});
for(const action of ['Company','Add Customer'])test('crm',action,async row=>{const name=tag+' '+action;await fill(action==='Company'?'Company name *':'Full name *',name);const data=await save(row,p=>p==='/api/v1/master-data/companies',()=>click('Save '+(action==='Company'?'company':'customer'),dialog()));await read(row,'/master-data/companies/'+data.id+'?source=crm',name);});
test('crm','Contact',async row=>{const name=tag+' contact';const input=dialog().getByPlaceholder('Enter contact name',{exact:true});await reveal(input);await input.fill(name);const data=await save(row,p=>p==='/api/v1/crm/contacts',()=>click('Create contact',dialog()));await read(row,'/crm/contacts/'+data.id,name);});
test('crm','Reminder',async row=>{const name=tag+' reminder';await fill('Title',name);await click('Tomorrow, 9 AM',dialog());const data=await save(row,p=>p==='/api/v1/crm/tasks',()=>click('Create reminder',dialog()));await read(row,'/crm/tasks/'+data.id,name);});
for(const action of ['Product','Service'])test('crm',action,async row=>{const name=tag+' '+action;await fill('Name',name);await fill('SKU / Code','C'+Date.now());const data=await save(row,p=>p==='/api/v1/catalog/items',()=>click('Save item',dialog()));await read(row,'/catalog/items/'+action.toLowerCase()+'/'+data.id,name);});
test('crm','Task',async row=>{const name=tag+' CRM linked task';await fill('Task Title',name);const project=dialog().getByLabel('Project',{exact:true});await reveal(project);await project.selectOption(String(fixtures.project.id));const data=await save(row,p=>/\/task-studio\/projects\/\d+\/tasks$/.test(p),()=>click('Create Task',dialog().locator('[data-smart-create-footer]')));await read(row,'/project-management/tasks/'+(data.task||data).id,name);});
for(const module of ['pms','crm','hrms'])test(module,'Form',async row=>{const name=tag+' '+module+' form';await fill('Form name',name);const data=await save(row,p=>p==='/api/v1/forms',()=>click('Save draft',dialog().locator('.forms-actions')));await read(row,'/forms/'+data.id,name);});
test('hrms','Add employee',async row=>{const name='CreateQA'+Date.now();await fill('First Name *',name);const body=dialog().locator('.smart-create-body');await click('Next',body);await body.locator('input[name=date_of_joining]').fill('2026-11-11');for(let i=0;i<3;i++)await click('Next',body);const data=await save(row,p=>p.replace(/\/$/,'')==='/api/v1/employees',()=>click('Create Employee',body));await read(row,'/employees/'+data.id,name);});
test('hrms','Submit expense',async row=>{const name=tag+' expense';await fill('Claim amount','12.50');await fill('Business purpose',name);const data=await save(row,p=>p==='/api/v1/expenses/claims',()=>click('Submit expense claim',dialog().locator('[data-smart-create-footer]')));await read(row,'/expenses/claims',name);});
test('hrms','Apply for leave',async row=>{const name=tag+' leave';const d=dialog();await d.locator('select[name=leave_type_id]').selectOption({label:'Create QA annual leave'});const offset=row.width===1440?10:11;const date=new Date();date.setDate(date.getDate()+offset);const day=date.toISOString().slice(0,10);await d.locator('input[name=from_date]').fill(day);await d.locator('input[name=to_date]').fill(day);await fill('Reason',name);const data=await save(row,p=>p==='/api/v1/leave/apply',()=>click('Submit Application',d));await read(row,'/leave/my-requests',name);});
async function runCases(){const modules=process.env.CREATE_MODULE?.split(','),actions=process.env.CREATE_ACTION?.split('|'),widths=process.env.CREATE_WIDTH?[Number(process.env.CREATE_WIDTH)]:[1440,390];for(const item of cases.filter(item=>(!modules||modules.includes(item.module))&&(!actions||actions.includes(item.action))))for(const width of widths)await record(item.module,item.action,width,item.handler);}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
