const path = require('node:path'), fs = require('node:fs'), assert = require('node:assert/strict');
const { chromium, expect: base } = require('../frontend/node_modules/playwright/test');
const expect = base.configure({ timeout: 120000 });
(async () => {
  const qa = JSON.parse(process.env.SUITE_QA_AUTH), bridge = process.env.CONTROL_BRIDGE;
  assert.match(bridge, /^http:\/\/127\.0\.0\.1:\d+$/);
  const root = path.resolve(__dirname, '../frontend');
  process.chdir(root);
  const { createServer } = await import('../frontend/node_modules/vite/dist/node/index.js');
  const port = await new Promise(resolve => { const socket = require('node:net').createServer(); socket.listen(0, '127.0.0.1', () => { const value = socket.address().port; socket.close(() => resolve(value)); }); });
  const vite = await createServer({ root, server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null } });
  let browser, context, page;
  const trace = [], errors = [];
  try {
    await vite.listen();
    const origin = 'http://127.0.0.1:' + vite.httpServer.address().port;
    browser = await chromium.launch();
    context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addInitScript(qa => {
      sessionStorage.setItem('suite-organization', '1');
      sessionStorage.setItem('suite-branch', qa.branch);
      sessionStorage.setItem('suite-pack-context', qa.context);
      sessionStorage.setItem('suite-business-pack-context', qa.context);
      sessionStorage.setItem('suite-pack-context-owner', JSON.stringify([null, '1', qa.branch]));
      sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: qa.token, refreshToken: null, user: qa.user, isAuthenticated: true }, version: 0 }));
    }, qa);
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.stack || error.message));
    page.on('requestfailed', request => trace.push({ path: new URL(request.url()).pathname, failure: request.failure()?.errorText }));
    await page.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url());
      const response = await context.request.fetch(bridge + url.pathname + url.search, { method: request.method(), headers: request.headers(), data: request.postDataBuffer() || undefined });
      trace.push({ method: request.method(), path: url.pathname, status: response.status() });
      await route.fulfill({ response });
    });
    // The untouched production index.html boots src/main.tsx and the real App/layout/guards.
    await page.goto(origin + '/srm/restaurant-kitchen');
    await expect(page.getByRole('navigation', { name: 'Module navigation' })).toBeVisible();
    const expand = page.getByRole('button', { name: 'Expand all menu categories', exact: true });
    if (await expand.count()) await expand.click();
    const link = page.getByRole('navigation', { name: 'Module navigation' }).getByRole('link', { name: 'Restaurant kitchen', exact: true });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page.getByText('Open tabs', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: `Tab ${qa.order} · counter`, exact: true }).click();
    await expect(page.getByText(new RegExp(`Order ${qa.order} · open · unpaid`))).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open unpaid tab', exact: true })).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Kitchen queue', exact: true })).toHaveCount(0);
    const authority = await page.evaluate(async qa => {
      const headers = { Authorization: 'Bearer ' + qa.token, 'X-Suite-Organization': '1', 'X-Suite-Branch': qa.branch, 'X-Suite-Pack-Context': qa.context, 'Content-Type': 'application/json' };
      const tabs = await fetch('/api/v1/srm/restaurant/tabs', { headers });
      const items = await tabs.json();
      const denied = await fetch('/api/v1/srm/restaurant/tabs', { method: 'POST', headers, body: JSON.stringify(qa.create) });
      const kitchen = await fetch('/api/v1/srm/restaurant/kitchen', { headers });
      return { status: tabs.status, items: items.items, create: denied.status, kitchen: kitchen.status };
    }, qa);
    assert.equal(authority.status, 200);
    assert(authority.items.some(item => item.id === qa.order));
    assert.equal(authority.create, 403);
    assert.equal(authority.kitchen, 403);
    await page.screenshot({ path: path.resolve(root, '../.local/restaurant-cashier-shell-desktop.png'), fullPage: true });
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-cashier-shell-proof.json'), JSON.stringify({ production_entry: true, authority, trace, errors }));
    console.log(JSON.stringify({ production_entry: true, native_cashier: true, ...authority }));
  } catch (error) {
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-cashier-shell-failure.json'), JSON.stringify({ message: error.message, trace, errors, body: page ? (await page.locator('body').innerText()).slice(-12000) : null }));
    throw error;
  } finally { if (context) { await context.unrouteAll({ behavior: 'wait' }); await context.close(); } if (browser) await browser.close(); await vite.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
