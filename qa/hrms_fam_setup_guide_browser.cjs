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
 const initial=await api('/access/setup');
 const targetItems=[...initial.moduleItems,...initial.recommendations].filter(i=>['hrms','fam'].includes(i.module));
 assert.equal(targetItems.filter(i=>i.required).length,7);
 assert.equal(targetItems.filter(i=>!i.required).length,3);
 for(const [path,module] of [['/hrms/dashboard','hrms'],['/hrms','hrms'],['/hrms/manager-dashboard','hrms'],['/fam/dashboard','fam'],['/fam','fam']]){
  await page.goto(origin+path);const guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('progress')).toBeVisible();
  const expected=[...initial.items,...targetItems.filter(i=>i.module===module)];assert.equal(await guide.locator('li').count(),expected.length);
  await expect(guide.getByRole('heading',{name:module==='hrms'?'HRMS setup':'Finance setup'})).toBeVisible();
  for(const item of expected)await expect(guide.getByText(item.title,{exact:true})).toHaveCount(1);
  await guide.getByRole('button',{name:'Check again',exact:true}).click();await expect(guide.getByRole('button',{name:'Check again',exact:true})).toBeEnabled();
  const box=await guide.boundingBox();assert.ok(box.x>=250 && box.x+box.width<=1441,'Sidebar overlap '+path);
  await page.screenshot({path:'docs/qa/setup-guide/'+module+'-desktop.png'});console.log('PASS scoped mandatory and optional tasks, refresh and layout',path);
 }
 // Check each missing module setup link from its own dashboard.
 for(const module of ['hrms','fam']){
  await page.goto(origin+'/'+module+'/dashboard');let guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('progress')).toBeVisible();
  const links=await guide.getByRole('link').evaluateAll(nodes=>nodes.map(a=>a.getAttribute('href')));
  for(const target of [...new Set(links)]){
   await page.goto(origin+'/'+module+'/dashboard');guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('a[href="'+target+'"]')).toBeVisible();await guide.locator('a[href="'+target+'"]').click();await expect(page).toHaveURL(origin+target);await expect(page.locator('body')).not.toContainText('Setting unavailable');await expect(page.locator('body')).not.toContainText('Page not found');console.log('PASS module setup link',target);
  }
 }
 // Also verify destinations of tasks already completed by native module defaults.
 for(const item of targetItems){await page.goto(origin+item.destination);await expect(page.locator('main').first()).toBeVisible();await expect(page.locator('body')).not.toContainText('Setting unavailable');}
 const year=new Date().getFullYear();await api('/attendance/holidays','POST',{name:'Setup guide holiday',holiday_date:year+'-12-31'});
 await api('/fam/cost-centers','POST',{code:'GUIDE'+Date.now(),name:'Setup guide cost center'});
 await api('/fam/payment-modes','POST',{name:'Setup guide bank '+Date.now(),type:'neft'});
 const completed=await api('/access/setup');for(const id of ['hrms-holidays','fam-cost-centers','fam-payment-modes'])assert.equal(completed.recommendations.find(i=>i.id===id).ready,true,id);
 for(const module of ['hrms','fam']){
  await page.setViewportSize({width:390,height:950});await page.goto(origin+'/'+module+'/dashboard');const guide=page.getByRole('region',{name:'Workspace setup guide'});await expect(guide.locator('progress')).toBeVisible();assert.equal(await guide.evaluate(el=>el.scrollWidth>el.clientWidth+1),false,'Guide overflow '+module);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'Page overflow '+module);await page.screenshot({path:'docs/qa/setup-guide/'+module+'-mobile.png'});console.log('PASS optional completion and mobile layout',module);
 }
 assert.deepEqual(errors,[]);console.log('PASS HRMS/FAM live checks, setup links and no browser exceptions');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
