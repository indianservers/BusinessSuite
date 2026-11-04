// Requires a fresh disposable backend/scripts/serve_ux_qa.py fixture and Vite :5200.
// SETUP_GUIDE_ORIGIN can select another local Vite instance for verification.
const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const expect=baseExpect.configure({timeout:30000}),assert=require('node:assert/strict'),fs=require('node:fs');
const root='http://127.0.0.1:1562/api/v1',origin=process.env.SETUP_GUIDE_ORIGIN || 'http://127.0.0.1:5200';
(async()=>{
 const login=await (await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})})).json();
 const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
 async function request(path,method='GET',body){return fetch(root+path,{method,headers,body:body?JSON.stringify(body):undefined});}
 async function api(path,method='GET',body){const r=await request(path,method,body);const d=await r.json();assert.ok(r.ok,path+': '+JSON.stringify(d));return d;}
 const access=await api('/access/me'),actor=await api('/auth/me');
 await api('/access/settings/company-profile','PATCH',{email:'office@suiteqa.example.com'});
 const browser=await chromium.launch();const errors=[];
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'admin',is_superuser:true,access}},version:0}));},{login,actor,access});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 fs.mkdirSync('docs/qa/setup-guide',{recursive:true});
 try{
 const initial=await api('/access/setup');assert.equal(initial.ready,true);
 for(const [path,module] of [['/settings',null],['/crm/dashboard','crm'],['/srm/dashboard','srm'],['/pms/overview','project_management'],['/pms','project_management'],['/pms/dashboards','project_management'],['/crm','crm'],['/srm','srm']]){
  await page.goto(origin+path);const guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide).toBeVisible();await expect(guide.locator('progress')).toBeVisible();
  const expected=[...initial.items,...initial.moduleItems,...initial.recommendations].filter(i=>!module||i.module==='company'||i.module===module);
  assert.equal(await guide.locator('li').count(),expected.length,path);
  const links=await guide.getByRole('link').evaluateAll(nodes=>nodes.map(a=>a.getAttribute('href')));
  assert.deepEqual(links.sort(),expected.filter(i=>!i.ready&&i.canRepair).map(i=>i.destination).sort());
  await guide.getByRole('button',{name:'Check again',exact:true}).click();await expect(guide.getByRole('button',{name:'Check again',exact:true})).toBeEnabled();
  const box=await guide.boundingBox();assert.ok(box.x>=0 && box.x+box.width<=1441,'Guide outside viewport '+path);if(module && path!=='/pms')assert.ok(box.x>=250,'Guide hidden by sidebar '+path);
  await page.screenshot({path:'docs/qa/setup-guide/'+(module||'settings')+'-desktop.png',fullPage:false});
  console.log('PASS dashboard guide, scoped counts, links and refresh',path);
 }
 // Follow every repair link offered in the central guide, including other enabled modules.
 await page.goto(origin+'/settings');let guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('progress')).toBeVisible();
 const targets=await guide.getByRole('link').evaluateAll(nodes=>nodes.map(a=>a.getAttribute('href')));
 for(const target of [...new Set(targets)]){
  await page.goto(origin+'/settings');guide=page.getByRole('region',{name:'Workspace setup guide'});const link=guide.locator('a[href="'+target+'"]');await expect(link).toBeVisible();await link.click();await expect(page).toHaveURL(origin+target);await expect(page.locator('body')).not.toContainText('Setting unavailable');await expect(page.locator('body')).not.toContainText('Page not found');console.log('PASS setup link',target);
 }
 // Company-wide essentials must block writes while repair and reads stay available.
 await api('/access/settings/company-profile','PATCH',{email:null});
 await page.goto(origin+'/crm/dashboard');guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.getByText('Company details',{exact:true})).toBeVisible();await expect(guide.locator('a[href="/settings/company-profile"]')).toBeVisible();
 let r=await request('/crm/lead-management/leads','POST',{values:{full_name:'Blocked setup guide lead'}});assert.equal(r.status,409);assert.equal(r.headers.get('x-suite-setup-required'),'1');
 await api('/access/settings/company-profile','PATCH',{email:'office@suiteqa.example.com'});
 for(const [id,path] of [['pipeline','/crm/deals'],['workspace','/project-management/projects'],['warehouse','/srm/inventory/stock-movements']]){
 const state=await api('/access/setup');assert.equal(state.moduleItems.find(i=>i.id===id).ready,false);
 r=await request(path,'POST',{});assert.equal(r.status,409,path+': '+await r.text());assert.equal(r.headers.get('x-suite-setup-required'),'1');console.log('PASS mandatory module guard',id);
 }
 await api('/crm/pipelines','POST',{name:'Guide QA pipeline'}).then(async p=>{await api('/crm/pipelines/'+p.id+'/stages','POST',{name:'Qualified'});});
 await api('/project-management/workspaces','POST',{name:'Guide QA workspace'});
 await api('/srm/inventory/warehouses','POST',{warehouse_code:'GUIDEQA',warehouse_name:'Guide QA warehouse'});
 const repaired=await api('/access/setup');for(const id of ['pipeline','workspace','warehouse'])assert.equal(repaired.moduleItems.find(i=>i.id===id).ready,true,id);
 for(const path of ['/crm/deals','/project-management/projects','/srm/inventory/stock-movements']){r=await request(path,'POST',{});assert.notEqual(r.status,409,path+' still blocked');}
 r=await request('/crm/lead-management/leads','POST',{values:{full_name:'Optional setup does not block'}});assert.equal(r.status,201,await r.text());
 for(const path of ['/settings','/crm/dashboard','/srm/dashboard','/pms/overview']){
  await page.setViewportSize({width:390,height:950});await page.goto(origin+path);guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('progress')).toBeVisible();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Overflow '+path);assert.equal(await guide.evaluate(el=>el.scrollWidth>el.clientWidth+1),false,'Guide content overflow '+path);await page.screenshot({path:'docs/qa/setup-guide/'+path.split('/')[1]+'-mobile.png'});
 }
 const employeeLogin=await (await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'employee@suiteqa.example.com',password:'SuiteQA@12345'})})).json();
 const employeeHeaders={...headers,Authorization:'Bearer '+employeeLogin.access_token};
 const employeeAccess=await (await fetch(root+'/access/me',{headers:employeeHeaders})).json(),employeeActor=await (await fetch(root+'/auth/me',{headers:employeeHeaders})).json();
 await api('/access/settings/company-profile','PATCH',{email:null});
 const employeeContext=await browser.newContext({viewport:{width:1440,height:1000}});
 await employeeContext.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'employee',is_superuser:false,access}},version:0}));},{login:employeeLogin,actor:employeeActor,access:employeeAccess});
 const employeePage=await employeeContext.newPage();await employeePage.goto(origin+'/settings');const employeeGuide=employeePage.getByRole('region',{name:'Workspace setup guide'});await expect(employeeGuide.locator('progress')).toBeVisible();await expect(employeeGuide.getByText('Ask your company administrator to complete this item.').first()).toBeVisible();await expect(employeeGuide.getByRole('link')).toHaveCount(0);
 const forbidden=await fetch(root+'/access/settings/company-profile',{method:'PATCH',headers:employeeHeaders,body:JSON.stringify({email:'forbidden@example.com'})});assert.equal(forbidden.status,403);
 await employeeContext.close();await api('/access/settings/company-profile','PATCH',{email:'office@suiteqa.example.com'});console.log('PASS non-admin guidance, no repair links and server rejects repair');
 assert.deepEqual(errors,[]);console.log('PASS repair persistence, optional non-blocking, mobile layout and no browser exceptions');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
