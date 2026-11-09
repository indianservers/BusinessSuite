// Run against a fresh disposable serve_ux_qa.py server (:1562) and Vite (:5200).
const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const fs=require('fs');
(async()=>{
const root='http://127.0.0.1:1562/api/v1';
const login=await (await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})})).json();
const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
const api=async(path,method='GET',body)=>{const r=await fetch(root+path,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(path+JSON.stringify(d));return d;};
const actor=await api('/auth/me'),access=await api('/access/me');

const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'admin',is_superuser:true,access}},version:0}));},{login,actor,access});
const errors=[];const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
fs.mkdirSync('outputs/setup-flow',{recursive:true});
if(process.env.SETUP_FLOW_COMPLETE){
 for(const [route,title] of [['/pms/tasks','Task workspace'],['/crm/tasks','Task workspace'],['/crm/workspaces','Sales & Customer Workspaces']]){
  await page.goto('http://127.0.0.1:5200'+route);
  await expect(page.getByRole('heading',{name:new RegExp('^'+title)})).toBeVisible({timeout:30000});
  await expect(page.getByRole('region',{name:'Workspace setup guide'})).toHaveCount(0);
  await page.screenshot({path:'outputs/setup-flow/'+route.replaceAll('/','_')+'-complete.png'});
  console.log('PASS loaded completed page hides guide',route);
 }
 expect(errors).toEqual([]);await browser.close();return;
}


if(!process.env.SETUP_FLOW_RESUME){
for(const path of ['/pms','/pms/tasks','/crm','/crm/tasks','/crm/workspaces']){
await page.goto('http://127.0.0.1:5200'+path);await expect(page.getByRole('region',{name:'Workspace setup guide'})).toBeVisible({timeout:60000});
const guide=page.getByRole('region',{name:'Workspace setup guide'});
if(path !== '/crm' && path !== '/crm/workspaces'){await expect(guide.getByText('Complete Project workspace first.')).toBeVisible();await expect(guide.locator('a[href="/pms/projects"]')).toHaveCount(0);}
else await expect(guide.getByText('Sales workspace',{exact:true})).toBeVisible();
console.log('PASS empty setup guide',path);
await page.screenshot({path:'outputs/setup-flow/'+path.replaceAll('/','_')+'-empty.png'});
}
await page.goto('http://127.0.0.1:5200/pms/workspaces');await expect(page.getByRole('region',{name:'Workspace setup guide'})).toBeVisible();

await page.getByRole('region',{name:'Workspace list',exact:true}).getByRole('button',{name:'Create Workspace',exact:true}).click();
let dialog=page.getByRole('dialog');
await dialog.getByRole('textbox',{name:'Workspace name',exact:true}).fill('Setup Browser Workspace');
await dialog.getByRole('button',{name:'Create Workspace',exact:true}).click();
await expect(dialog).toHaveCount(0);
let guide=page.getByRole('region',{name:'Workspace setup guide'});
await expect(guide.locator('li').filter({has:page.getByText('Project workspace',{exact:true})})).toContainText('Complete');
await expect(guide.locator('a[href="/pms/projects"]')).toBeVisible();
await expect(guide.getByText('Complete Project workspace first.')).toHaveCount(0);
await page.screenshot({path:'outputs/setup-flow/pms-workspace-created.png'});
console.log('PASS PMS: workspace created through UI; guide automatically completes workspace and unlocks project');
await guide.locator('a[href="/pms/projects"]').click();


await page.getByRole('link',{name:'Create project',exact:true}).last().click();

await page.getByRole('textbox',{name:'Project name',exact:true}).fill('Setup Browser Project');
await page.getByRole('textbox',{name:'Project key',exact:true}).fill('BROWSETUP');
await page.getByRole('button',{name:'Create project',exact:true}).last().click();
await expect(page.getByRole('region',{name:'Workspace setup guide'})).toHaveCount(0,{timeout:30000});
console.log('PASS PMS: guide hidden automatically after project creation');
for(const route of ['/pms','/pms/tasks','/crm/tasks']){await page.goto('http://127.0.0.1:5200'+route);await expect(page.getByRole('region',{name:'Workspace setup guide'})).toHaveCount(0);console.log('PASS completed tasks guide hidden',route);}
await page.goto('http://127.0.0.1:5200/crm/workspaces');
guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide).toBeVisible();
await page.getByRole('region',{name:'Workspace list',exact:true}).getByRole('button',{name:'Create Workspace',exact:true}).click();
dialog=page.getByRole('dialog');await dialog.getByRole('textbox',{name:'Workspace name',exact:true}).fill('Setup Browser Sales');
await dialog.getByRole('button',{name:'Create Workspace',exact:true}).click();await expect(dialog).toHaveCount(0);
await expect(guide.locator('li').filter({has:page.getByText('Sales workspace',{exact:true})})).toContainText('Complete');
console.log('PASS CRM: sales workspace created through UI and guide updated automatically');
}
await page.goto('http://127.0.0.1:5200/crm/workspaces');
let crmGuide=page.getByRole('region',{name:'Workspace setup guide'});await expect(crmGuide).toBeVisible();

const settings=page;
await crmGuide.locator('a[href="/settings/crm-pipelines"]').click();

const existing=await api('/crm/pipelines');
if(!(existing.items||existing).length){
 await settings.getByRole('button',{name:'Create pipeline',exact:true}).click();
 await settings.getByRole('textbox',{name:'New pipeline name',exact:true}).fill('Setup Browser Pipeline');
 await settings.getByRole('button',{name:'Create pipeline',exact:true}).last().click();
 await expect(settings.getByRole('textbox',{name:'New pipeline name',exact:true})).toHaveCount(0);
}
if(await settings.getByRole('button',{name:'Close creation window',exact:true}).count()) await settings.getByRole('button',{name:'Close creation window',exact:true}).click();
if(await settings.getByRole('button',{name:'Discard Changes',exact:true}).count()) await settings.getByRole('button',{name:'Discard Changes',exact:true}).click();
await expect(settings.locator('.smart-create-overlay')).toHaveCount(0);
await expect(settings.getByRole('button',{name:'Add stage',exact:true})).toBeVisible({timeout:30000});
await settings.getByRole('button',{name:'Add stage',exact:true}).click();
await settings.getByRole('textbox',{name:/Stage name new:/}).fill('Qualified');
await settings.getByRole('button',{name:'Save',exact:true}).click();
await expect.poll(async()=> (await api('/access/setup')).moduleItems.find(i=>i.id==='pipeline').ready).toBe(true);
console.log('PASS CRM: pipeline and named stage created through UI');
await expect(settings.getByRole('button',{name:'Save',exact:true})).toBeEnabled();
await settings.goBack();
if(!new URL(page.url()).pathname.endsWith('/crm/workspaces')) await settings.goBack();
await expect(page).toHaveURL(/\/crm\/workspaces(?:[?#]|$)/);
await expect(crmGuide).toHaveCount(0,{timeout:30000});
await expect(page.getByRole('heading',{name:'Sales & Customer Workspaces',exact:true})).toBeVisible({timeout:30000});
await page.screenshot({path:'outputs/setup-flow/crm-complete.png'});
console.log('PASS CRM: guide hides after completing sales workspace and pipeline setup, without reloading or Check again');
await page.goto('http://127.0.0.1:5200/crm');await expect(crmGuide).toHaveCount(0);
for(const route of ['/pms/tasks','/crm/tasks']){await page.setViewportSize({width:390,height:950});await page.goto('http://127.0.0.1:5200'+route);await expect(crmGuide).toHaveCount(0);await page.screenshot({path:'outputs/setup-flow/'+route.replaceAll('/','_')+'-complete-mobile.png'});}
console.log('PASS completed guide stays hidden on mobile PMS and CRM tasks');

expect(errors).toEqual([]);
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
