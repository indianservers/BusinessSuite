const path = require('node:path'), assert = require('node:assert/strict'), fs = require('node:fs');
const { chromium, expect: base } = require('../frontend/node_modules/playwright/test');
const expect = base.configure({ timeout: 30000 });
const bridge = process.env.CONTROL_BRIDGE;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge || '')) throw Error('Disposable real API bridge required');
(async () => {
  const auth = JSON.parse(process.env.SUITE_QA_AUTH), root = path.resolve(__dirname, '../frontend');
  process.chdir(root);
  const { createServer } = await import('../frontend/node_modules/vite/dist/node/index.js');
  // Vite treats 0 as its configured default (5173), not an ephemeral port.
  // Reserve a positive OS-assigned port so the user's review server is untouched.
  const port = await new Promise(resolve => { const socket = require('node:net').createServer(); socket.listen(0, '127.0.0.1', () => { const assigned = socket.address().port; socket.close(() => resolve(assigned)); }); });
  const server = await createServer({ root, server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null } });
  let origin, browser;
  const contexts = [], trace = [], errors = [];
  const stage = value => fs.writeFileSync(path.resolve(root, '../.local/restaurant-browser-progress.json'), JSON.stringify({ stage: value, trace: trace.slice(-30), errors }));
  let closing = false, current;
  async function pageFor(role, mobile = false) {
    const context = await browser.newContext({ viewport: { width: mobile ? 390 : 1440, height: 1000 } });
    contexts.push(context);
    await context.addInitScript(identity => { window.qaAuth = identity; window.__AI_HRMS_CONFIG__ = { apiBaseUrl: '/api/v1' }; }, { token: auth[role], branch: auth.branch, context: auth.context });
    const page = await context.newPage();
    page.on('pageerror', error => { errors.push(error.message); stage('page error '+role); });
    await page.route(origin + '/**', async route => {
      const request = route.request(), url = new URL(request.url());
      try {
        if (url.pathname.startsWith('/api/')) {
          const requestTrace = { role, method: request.method(), path: url.pathname, status: 'pending' };
          trace.push(requestTrace); stage('API '+role);
          const response = await context.request.fetch(bridge + url.pathname + url.search, { method: request.method(), headers: request.headers(), data: request.postDataBuffer() || undefined });
          requestTrace.status = response.status(); stage('API response '+role);
          return route.fulfill({ response });
        }
        if (request.isNavigationRequest()) return route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/restaurant-native.tsx");</script>' });
        return route.continue();
      } catch (error) { if (!closing) errors.push(error.message); await route.abort().catch(() => {}); }
    });
    stage('opening '+role);
    await page.goto(origin + '/srm/restaurant-kitchen' + (auth.checkout ? '?checkout=' + auth.checkout : ''));
    stage('loaded '+role);
    return page;
  }
  async function fits(page) {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
  }
  try {
    stage('starting owned Vite');
    await server.listen();
    origin = 'http://127.0.0.1:' + server.httpServer.address().port;
    browser = await chromium.launch();
    current = await pageFor('manager');
    stage('manager table form');
    await current.getByLabel('Table name', { exact: true }).fill('Dining 1');
    await current.getByRole('button', { name: 'Add table', exact: true }).click();
    stage('manager table submitted');
    const addMenu = async page => {
      await expect(page.getByLabel('Menu item', { exact: true }).locator(`option[value="${auth.product}"]`)).toHaveCount(1);
      await page.getByLabel('Menu item', { exact: true }).selectOption(String(auth.product));
      await page.getByLabel('Menu quantity', { exact: true }).fill('1');
      await page.getByRole('button', { name: 'Add menu item', exact: true }).click();
    };
    if (auth.unpaid) {
      await expect(current.getByLabel('Tab table', { exact: true }).locator('option').filter({ hasText: 'Dining 1' })).toHaveCount(1);
      await current.getByLabel('Tab table', { exact: true }).selectOption({ label: 'Dining 1' });
      await addMenu(current);
      await current.getByRole('button', { name: 'Open unpaid tab', exact: true }).click();
    } else {
      await expect(current.getByLabel('Dining table', { exact: true }).locator('option').filter({ hasText: 'Dining 1' })).toHaveCount(1);
      await current.getByLabel('Dining table', { exact: true }).selectOption({ label: 'Dining 1' });
      await current.getByRole('button', { name: 'Open fulfillment order', exact: true }).click();
    }
    stage('manager order submitted');
    await expect(current.getByLabel('Service order ID', { exact: true })).not.toHaveValue('');
    const order = await current.getByLabel('Service order ID', { exact: true }).inputValue();
    if (auth.unpaid) {
      await expect(current.getByLabel('Send quantity', { exact: true })).toHaveCount(1);
      await current.getByLabel('Tab action', { exact: true }).selectOption('add');
      await addMenu(current);
      await current.getByRole('button', { name: 'Add items to tab', exact: true }).click();
      await expect(current.getByLabel('Send quantity', { exact: true })).toHaveCount(2);
      for (const input of await current.getByLabel('Send quantity', { exact: true }).all()) await input.fill('1');
    } else await current.getByLabel('Send quantity', { exact: true }).fill('2');
    await current.getByLabel('Kitchen instruction', { exact: true }).first().fill('No salt');
    await current.getByRole('button', { name: 'Send selected items', exact: true }).click();
    stage('manager kitchen submitted');
    await expect(current.getByText('No salt', { exact: true }).first()).toBeVisible();
    await fits(current);
    await current.screenshot({ path: path.resolve(root, auth.unpaid ? '../.local/restaurant-unpaid-desktop.png' : '../.local/restaurant-server-desktop.png'), fullPage: true });
    const chef = current = await pageFor('chef', true);
    await expect(chef.getByRole('heading', { name: 'Kitchen queue', exact: true })).toBeVisible();
    await expect(chef.getByLabel('Paid POS checkout ID', { exact: true })).toHaveCount(0);
    await expect(chef.getByLabel('Service order ID', { exact: true })).toHaveCount(0);
    await expect(chef.getByRole('heading', { name: 'Tables', exact: true })).toHaveCount(0);
    await chef.getByRole('button', { name: 'Start preparation', exact: true }).click();
    stage('chef preparation submitted');
    await chef.getByRole('button', { name: 'Mark ready', exact: true }).click();
    stage('chef ready submitted');
    await expect(chef.getByText(/Ticket \d+ · ready/)).toBeVisible();
    await expect(chef.getByRole('button', { name: 'Mark served', exact: true })).toHaveCount(0);
    await fits(chef);
    await chef.screenshot({ path: path.resolve(root, auth.unpaid ? '../.local/restaurant-unpaid-chef-mobile.png' : '../.local/restaurant-chef-mobile.png'), fullPage: true });
    const waiter = current = await pageFor('server', true);
    await waiter.getByLabel('Service order ID', { exact: true }).fill(order);
    await waiter.getByRole('button', { name: 'Mark served', exact: true }).click();
    stage('server served submitted');
    if (auth.unpaid) {
      await expect(waiter.getByText(`Order ${order} · open · unpaid · INR 236.00`, { exact: true })).toBeVisible();
      await waiter.getByLabel('Tab action', { exact: true }).selectOption('add');
      await addMenu(waiter);
      await waiter.getByRole('button', { name: 'Add items to tab', exact: true }).click();
      await expect(waiter.getByText(`Order ${order} · open · unpaid · INR 354.00`, { exact: true })).toBeVisible();
    } else await expect(waiter.getByText(`Order ${order} · served`, { exact: true })).toBeVisible();
    await fits(waiter);
    await waiter.screenshot({ path: path.resolve(root, auth.unpaid ? '../.local/restaurant-unpaid-served-mobile.png' : '../.local/restaurant-served-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    assert.deepEqual(trace.filter(row => row.status >= 400), []);
    stage('complete');
    console.log(JSON.stringify({ real_api: true, roles: ['manager', 'chef', 'server'], order, viewports: [1440, 390], state: auth.unpaid ? 'open_unpaid_after_serving' : 'served', requests: trace.length }));
  } catch (error) {
    const failure = { message: error.message, trace: trace.slice(-25), errors, body: current ? (await current.locator('body').innerText()).slice(-4000) : null };
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-browser-failure.json'), JSON.stringify(failure));
    if (current) await current.screenshot({ path: path.resolve(root, '../.local/restaurant-browser-failure.png'), fullPage: true }).catch(() => {});
    console.error(JSON.stringify(failure)); throw error;
  }
  finally { closing = true; for (const context of contexts) { await Promise.all(context.pages().map(page => page.close())); await context.unrouteAll({ behavior: 'wait' }); await context.close(); } if (browser) await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
