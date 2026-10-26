const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const path = require('path');
const bridge = process.env.CONTROL_BRIDGE;
if (!bridge || !bridge.startsWith('http://127.0.0.1:')) throw new Error('Disposable test bridge required');
(async () => {
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addInitScript(() => {window.__AI_HRMS_CONFIG__ = {apiBaseUrl:'/api/v1'};});
  await context.route('**/api/**', async route => {
    try {
    const request = route.request();
    const url = new URL(request.url());
    const response = await context.request.fetch(bridge+url.pathname+url.search, {method:request.method(),headers:request.headers(),data:request.postDataBuffer() || undefined,failOnStatusCode:false});
    await route.fulfill({response});
    } catch(e) { console.log('Bridge failed: '+new URL(route.request().url()).pathname+' '+e.message.split('\n')[0]); await route.abort().catch(()=>{}); }
  });
  const page = await context.newPage();
  const api = async (method, url, data, token) => {
    const response = await context.request.fetch(bridge+'/api/v1'+url,{method,data,headers:token?{Authorization:'Bearer '+token}:{}});
    return {status:response.status(),body:await response.json()};
  };
  const verify = async () => {await page.getByLabel('Current administrator password').fill('Admin@123456');await page.getByRole('button',{name:'Verify & continue',exact:true}).click();};
  try {
    await page.goto('http://127.0.0.1:5201/login');
    await page.getByPlaceholder('you@company.com').fill('testadmin@test.com');
    await page.getByPlaceholder('Enter your password').fill('Admin@123456');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await expect.poll(async()=>page.evaluate(()=>!!JSON.parse(sessionStorage.getItem('hrms-auth')||'{}').state?.accessToken)).toBe(true);
    for (const [section,title] of [['dashboard','Dashboard'],['organizations','Organizations'],['modules','Module Management'],['security','Security Center'],['audit','Audit Logs']]) {
      await page.goto('http://127.0.0.1:5201/admin/control/'+section);
      await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
      await expect(page.getByLabel('Loading control center')).toHaveCount(0);
      if(await page.locator('.cc-error').count()) throw new Error(section+': '+await page.locator('.cc-error').textContent());
    }
    await page.goto('http://127.0.0.1:5201/admin/access?action=add');
    await page.getByLabel('Full name',{exact:true}).fill('Phase One Browser User');
    await page.getByLabel('Email',{exact:true}).fill('phase1.browser@example.com');
    await page.getByLabel('Initial password').fill('Browser@123456');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await verify();
    await expect(page.getByRole('checkbox',{name:'Phase One Browser User: CRM',exact:true})).toBeVisible();
    for(const module of ['CRM','PMS']) await page.getByRole('checkbox',{name:'Phase One Browser User: '+module,exact:true}).check();
    await page.getByLabel('Reason for access changes').fill('Browser verified PMS and CRM assignment');
    await page.getByRole('button',{name:'Review changes',exact:true}).click();
    await page.getByRole('button',{name:'Reauthenticate & apply',exact:true}).click();await verify();
    await expect(page.getByText('1 users updated. Existing sessions were revoked.',{exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByRole('checkbox',{name:'Phase One Browser User: CRM',exact:true})).toBeChecked();
    const login = await api('POST','/auth/login',{email:'phase1.browser@example.com',password:'Browser@123456'});
    expect(login.status).toBe(200);
    expect((await api('GET','/crm/lead-management/leads',undefined,login.body.access_token)).status).toBe(200);
    const access = await api('GET','/access/me',undefined,login.body.access_token);
    expect(access.body.grants.project_management.enabled).toBe(true);
    await page.getByRole('checkbox',{name:'Phase One Browser User: CRM',exact:true}).uncheck();
    await page.getByLabel('Reason for access changes').fill('Browser verified CRM revocation');
    await page.getByRole('button',{name:'Review changes',exact:true}).click();
    await page.getByRole('button',{name:'Reauthenticate & apply',exact:true}).click();await verify();
    await expect(page.getByText('1 users updated. Existing sessions were revoked.',{exact:true})).toBeVisible();
    const relogin = await api('POST','/auth/login',{email:'phase1.browser@example.com',password:'Browser@123456'});
    expect((await api('GET','/crm/lead-management/leads',undefined,relogin.body.access_token)).status).toBe(403);
    expect((await api('GET','/access/control/security?companyId=999999',undefined,relogin.body.access_token)).status).toBe(403);
    const userContext = await browser.newContext();
    await userContext.route('**/api/**', async route => {const req=route.request();const url=new URL(req.url());const res=await context.request.fetch(bridge+url.pathname+url.search,{method:req.method(),headers:req.headers(),data:req.postDataBuffer()||undefined});await route.fulfill({response:res});});
    const userPage = await userContext.newPage();
    await userPage.addInitScript(({login,access})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:login.user_id,email:login.email,role:login.role,is_superuser:false,access}},version:0})),{login:relogin.body,access:(await api('GET','/access/me',undefined,relogin.body.access_token)).body});
    await userPage.goto('http://127.0.0.1:5201/crm');
    await expect(userPage.getByText('403 Access Denied',{exact:true})).toBeVisible();
    await userContext.close();
    await page.goto('http://127.0.0.1:5201/admin/control/audit');
    await expect(page.getByText('Browser verified CRM revocation',{exact:true})).toBeVisible();
    await page.goto('http://127.0.0.1:5201/admin/control/dashboard');
    await expect(page.getByText('Total companies',{exact:true})).toBeVisible();
    await page.screenshot({path:path.resolve('../docs/qa/suite-access/phase1-dashboard.png'),fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:390,height:844});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.resolve('../docs/qa/suite-access/phase1-mobile.png'),fullPage:true,animations:'disabled'});
    console.log('Real browser login, five pages, user creation, PMS/CRM grants, reload, CRM API and navigation revocation, cross-company denial, audit and mobile layout passed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
