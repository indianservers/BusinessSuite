const path = require('node:path'), fs = require('node:fs'), assert = require('node:assert/strict');
const { chromium, expect: base } = require('../frontend/node_modules/playwright/test');
const expect = base.configure({ timeout: 120000 });
(async () => {
  const qa = JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE, 'utf8')), bridge = process.env.CONTROL_BRIDGE;
  assert.match(bridge, /^http:\/\/127\.0\.0\.1:\d+$/);
  const root = path.resolve(__dirname, '../frontend'); process.chdir(root);
  const { createServer } = await import('../frontend/node_modules/vite/dist/node/index.js');
  const port = await new Promise(resolve => { const socket = require('node:net').createServer(); socket.listen(0, '127.0.0.1', () => { const value = socket.address().port; socket.close(() => resolve(value)); }); });
  const vite = await createServer({ root, server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null } });
  let browser, current, origin;
  const contexts = [], trace = [], errors = [], closing = new Set();
  async function open(role, mobile=false) {
    const context = await browser.newContext({ viewport: { width: mobile ? 390 : 1440, height: 1000 } }); contexts.push(context);
    await context.addInitScript(qa => {
      sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', qa.branch);
      sessionStorage.setItem('suite-pack-context', qa.context); sessionStorage.setItem('suite-business-pack-context', qa.context);
      sessionStorage.setItem('suite-pack-context-owner', JSON.stringify([null, '1', qa.branch]));
      sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: qa.token, refreshToken: null, user: qa.user, isAuthenticated: true }, version: 0 }));
    }, { ...qa[role], branch: qa.branch, context: qa.context });
    const page = await context.newPage(); current = page;
    page.on('pageerror', error => errors.push(error.stack || error.message));
    await page.route('**/api/**', async route => {
      try {
        const request = route.request(), url = new URL(request.url());
        const response = await context.request.fetch(bridge + url.pathname + url.search, { method: request.method(), headers: request.headers(), data: request.postDataBuffer() || undefined });
        trace.push({ role, method: request.method(), path: url.pathname, status: response.status() });
        await route.fulfill({ response });
      } catch(error) { if (!closing.has(context)) errors.push(error.message); await route.abort().catch(()=>{}); }
    });
    await page.goto(origin + '/srm/restaurant-kitchen');
    await expect(page.getByRole('heading', { name: 'Restaurant orders & kitchen', exact: true })).toBeVisible();
    return page;
  }
  async function close(page) { const context = page.context(); closing.add(context); await context.unrouteAll({ behavior:'wait' }); await context.close(); }
  async function fits(page) { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false); }
  try {
    await vite.listen(); origin = 'http://127.0.0.1:' + vite.httpServer.address().port; browser = await chromium.launch();
    let page = await open('manager');
    await page.getByRole('button', { name:'Expand all menu categories', exact:true }).click();
    await expect(page.getByRole('navigation', { name:'Module navigation' }).getByRole('link', { name:'Restaurant kitchen', exact:true })).toBeVisible();
    await expect(page.getByRole('navigation', { name:'Module navigation' }).getByRole('link', { name:'Construction operations', exact:true })).toHaveCount(0);
    await page.getByLabel('Table name', { exact:true }).fill('Settlement dining');
    await page.getByRole('button', { name:'Add table', exact:true }).click();
    await expect(page.getByLabel('Tab customer', { exact:true }).locator('option[value="101"]')).toHaveCount(1);
    if (!qa.walkin) await page.getByLabel('Tab customer', { exact:true }).selectOption('101');
    await expect(page.getByLabel('Tab table', { exact:true }).locator('option').filter({ hasText:'Settlement dining' })).toHaveCount(1);
    await page.getByLabel('Tab table', { exact:true }).selectOption({ label:'Settlement dining' });
    await page.getByLabel('Menu item', { exact:true }).selectOption(String(qa.product));
    await page.getByRole('button', { name:'Add menu item', exact:true }).click();
    await page.getByRole('button', { name:'Open unpaid tab', exact:true }).click();
    await expect(page.getByLabel('Service order ID', { exact:true })).not.toHaveValue('');
    const order = await page.getByLabel('Service order ID', { exact:true }).inputValue();
    if (qa.walkin) {
      await expect(page.getByLabel('Assign tab customer', { exact:true }).locator('option[value="101"]')).toHaveCount(1);
      await page.getByLabel('Assign tab customer', { exact:true }).selectOption('101');
      await page.getByRole('button', { name:'Assign customer to tab', exact:true }).click();
      await expect(page.getByRole('button', { name:'Assign customer to tab', exact:true })).toHaveCount(0);
    }
    await page.getByLabel('Send quantity', { exact:true }).fill('1');
    await page.getByRole('button', { name:'Send selected items', exact:true }).click();
    await expect(page.getByText(/Ticket \d+ · queued/)).toBeVisible();
    await fits(page); await page.screenshot({ path:path.resolve(root,qa.walkin?'../.local/restaurant-walkin-desktop.png':'../.local/restaurant-settlement-desktop.png'),fullPage:true }); await close(page);
    page = await open('cashier', true);
    await page.getByRole('button', { name:new RegExp(`^Tab ${order} · table`) }).click();
    await expect(page.getByLabel('Collection register', { exact:true }).locator(`option[value="${qa.register}"]`)).toHaveCount(1);
    await page.getByLabel('Collection register', { exact:true }).selectOption(String(qa.register));
    await page.getByRole('button', { name:'Issue tab invoice', exact:true }).click();
    await expect(page.getByText(/Paid 0\.00 · Balance 118\.00/)).toBeVisible();
    for (const [method, amount, paid, balance] of [['cash','50','50.00','68.00'],['card','68','118.00','0.00']]) {
      await page.getByLabel('Tab payment method', { exact:true }).selectOption(method);
      await page.getByLabel('Tab payment amount', { exact:true }).fill(amount);
      await page.getByRole('button', { name:'Collect payment', exact:true }).click();
      await expect(page.getByText(`Paid ${paid} · Balance ${balance}`, { exact:true })).toBeVisible();
    }
    await expect(page.getByRole('heading', {name:'Kitchen queue',exact:true})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Open unpaid tab',exact:true})).toHaveCount(0);
    await fits(page); await page.screenshot({ path:path.resolve(root,qa.walkin?'../.local/restaurant-walkin-cashier-mobile.png':'../.local/restaurant-settlement-cashier-mobile.png'),fullPage:true }); await close(page);
    page = await open('chef', true);
    await expect(page.getByText('Tab billing & payments',{exact:true})).toHaveCount(0);
    await page.getByRole('button',{name:'Start preparation',exact:true}).click();
    await page.getByRole('button',{name:'Mark ready',exact:true}).click();
    await expect(page.getByText(/Ticket \d+ · ready/)).toBeVisible(); await close(page);
    page = await open('server', true);
    await page.getByLabel('Service order ID',{exact:true}).fill(order);
    await page.getByRole('button',{name:'Mark served',exact:true}).click();
    await expect(page.getByText(`Order ${order} · served`,{exact:true})).toBeVisible();
    await expect(page.locator('.udg-adapted-cell').filter({ hasText:/^Available$/ }).first()).toBeVisible(); await fits(page);
    for (const endpoint of ['/api/v1/access/enterprise/branding','/api/v1/notifications/summary','/api/v1/business-os/modules']) {
      assert(trace.some(row=>row.path===endpoint && row.status===200), `Actual bootstrap 200 missing: ${endpoint}`);
      assert(!trace.some(row=>row.path===endpoint && row.status>=400), `Actual bootstrap failure: ${endpoint}`);
    }
    const closed = trace.filter(row=>row.status>=400);
    assert.deepEqual(closed.filter(row=>row.path!=='/api/v1/follow-ups/statistics'||row.status!==503),[]); assert.deepEqual(errors,[]);
    fs.writeFileSync(path.resolve(root,qa.walkin?'../.local/restaurant-walkin-browser-proof.json':'../.local/restaurant-settlement-browser-proof.json'),JSON.stringify({production_entry:true,walkin:qa.walkin,order,trace,errors,nonblocking_closed_routes:closed,viewports:[1440,390]}));
    console.log(JSON.stringify({production_entry:true,order,split_payments:['cash','card'],bootstrap200:true,roles:['manager','cashier','chef','server'],requests:trace.length}));
  } catch(error) {
    fs.writeFileSync(path.resolve(root,'../.local/restaurant-settlement-browser-failure.json'),JSON.stringify({message:error.message,trace,errors,body:current && !current.isClosed()?(await current.locator('body').innerText()).slice(-10000):null})); throw error;
  } finally { for(const context of contexts) { closing.add(context); await context.unrouteAll({behavior:'wait'}).catch(()=>{}); await context.close().catch(()=>{}); } if(browser)await browser.close(); await vite.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
