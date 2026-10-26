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
    await page.goto('http://127.0.0.1:5201/admin/control/ai-security');
    await expect(page.getByRole('heading',{name:'AI Security',exact:true})).toBeVisible();
    await expect(page.getByRole('heading',{name:'Tool and permission registry',exact:true})).toBeVisible();
    await expect(page.locator('main.cc-root')).toHaveAttribute('aria-busy','false');
    await expect(page.getByLabel('Enable suite:crm.create_task')).toBeChecked();
    await page.getByLabel('Enable suite:crm.create_task').uncheck();
    await page.getByLabel('max_calls',{exact:true}).fill('4');
    await page.getByRole('button',{name:'Review and save limits',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Confirm AI security limits',exact:true})).toBeVisible();
    await page.getByLabel('AI policy reason').fill('Browser verified stricter AI limits');
    await page.getByLabel('AI policy password').fill('Admin@123456');
    await page.getByRole('button',{name:'Verify and save AI policy',exact:true}).click();
    await expect(page.getByText('AI limits saved and audited. Existing previews must be reviewed again.',{exact:true})).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('max_calls',{exact:true})).toHaveValue('4');
    await expect(page.getByLabel('Enable suite:crm.create_task')).not.toBeChecked();
    await page.screenshot({path:path.resolve('../docs/qa/suite-access/ai-security-desktop.png'),fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:390,height:844});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.resolve('../docs/qa/suite-access/ai-security-mobile.png'),fullPage:true,animations:'disabled'});
    console.log('AI Security: real login, registry, exact policy review, step-up password, persisted limits/tool disable, desktop/mobile passed');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1);});
