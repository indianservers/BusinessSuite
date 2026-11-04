// Requires the disposable backend/scripts/serve_ux_qa.py fixture and Vite :5200.
// Fixed loopback URLs intentionally prevent targeting an external environment.
const {chromium, expect:baseExpect} = require('../frontend/node_modules/playwright/test');
const expect=baseExpect.configure({timeout:30000});
const assert=require('node:assert/strict');
const root='http://127.0.0.1:1562/api/v1', origin='http://127.0.0.1:5200';
(async()=>{
  const response=await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})});
  assert.equal(response.status,200); const login=await response.json();
  const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
  async function api(path,method='GET',body){const r=await fetch(root+path,{method,headers,body:body?JSON.stringify(body):undefined});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;}
  const access=await api('/access/me'), actor=await api('/auth/me');
  const browser=await chromium.launch();
  try {
    for(const width of [1440,390,320]){
      await api('/access/settings/company-profile','PATCH',{email:null});
      if(width===1440){
        for(const path of ['/project-management/task-workspace/tasks/999999/actions','/power-apps/approvals/requests/999999/decisions']){
          const blocked=await fetch(root+path,{method:'POST',headers,body:JSON.stringify({action:'start'})});
          assert.equal(blocked.status,409,`${path}: ${await blocked.text()}`);
          assert.equal(blocked.headers.get('x-suite-setup-required'),'1');
        }
      }
      const context=await browser.newContext({viewport:{width,height:950}});
      await context.addInitScript(({login,actor,access})=>{
        sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');
        sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'admin',is_superuser:true,access}},version:0}));
      },{login,actor,access});
      const page=await context.newPage(), errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(origin+'/settings');
      await expect(page.getByRole('button',{name:'Complete setup',exact:true})).toBeVisible();
      if(width===1440){
        // Exercise the real shared interceptor: failed writes open setup without
        // losing the current page or relying on each module to handle it.
        await page.evaluate(async()=>{
          const {api}=await import('/src/services/api.ts');
          try {await api.post('/project-management/task-workspace/tasks/999999/actions',{action:'start'});} catch {}
        });
      } else await page.getByRole('button',{name:'Complete setup',exact:true}).click();
      const dialog=page.getByRole('dialog',{name:'Complete company setup'});
      await expect(dialog).toBeVisible();
      await dialog.getByRole('link',{name:'Add or repair company details'}).click();
      await expect(page).toHaveURL(/settings\/company-profile/);
      await expect(page.getByLabel('Company name *',{exact:true})).toBeVisible();
      await expect(page.getByLabel('Legal name',{exact:true})).not.toBeVisible();
      await page.getByLabel('Company email *',{exact:true}).fill('office@suiteqa.example.com');
      await page.getByRole('button',{name:'Save company profile',exact:true}).click();
      await expect(page.getByText('Changes saved. They apply immediately across Business Suite.',{exact:true})).toBeVisible();
      await expect(page.getByRole('complementary',{name:'Company setup'})).toHaveCount(0);
      assert.equal((await api('/access/setup')).ready,true);
      await page.reload();
      await expect(page.getByLabel('Company email *',{exact:true})).toHaveValue('office@suiteqa.example.com');
      // Deleted details are rediscovered from persisted data on reload.
      await api('/access/settings/company-profile','PATCH',{email:null});
      await page.reload();
      await expect(page.getByRole('button',{name:'Complete setup',exact:true})).toBeVisible();
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
      assert.equal(overflow,false,`Horizontal overflow at ${width}`);
      assert.deepEqual(errors,[]);
      console.log(`PASS setup, repair, reload and missing-detail recovery at ${width}px`);
      await context.close();
    }
    await api('/access/settings/company-profile','PATCH',{email:'office@suiteqa.example.com'});
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
