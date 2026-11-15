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
          requestTrace.status = response.status(); if (response.status() >= 400) requestTrace.detail = (await response.json()).detail; stage('API response '+role);
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
    await current.getByLabel('Table name', { exact: true }).fill('Modifier table');
    await current.getByRole('button', { name: 'Add table', exact: true }).click();
    await expect(current.getByLabel('Tab table', { exact: true }).locator('option').filter({ hasText: 'Modifier table' })).toHaveCount(1);
    await current.getByLabel('Tab table', { exact: true }).selectOption({ label: 'Modifier table' });
    await expect(current.getByLabel('Menu item', { exact: true }).locator(`option[value="${auth.product}"]`)).toHaveCount(1);
    await current.getByLabel('Menu item', { exact: true }).selectOption(String(auth.product));
    await expect(current.getByLabel('Extras: QA-OTHER', { exact: true })).toBeVisible();
    await current.getByLabel('Extras: QA-OTHER', { exact: true }).fill('2');
    await current.getByRole('button', { name: 'Add menu item', exact: true }).click();
    await current.getByLabel('Menu item', { exact: true }).selectOption(String(auth.option));
    await current.getByRole('button', { name: 'Add menu item', exact: true }).click();
    await current.getByRole('button', { name: 'Open unpaid tab', exact: true }).click();
    await expect(current.getByText(/Order \d+ · open · unpaid · INR 472.00/, { exact: true })).toBeVisible();
    const order = await current.getByLabel('Service order ID', { exact: true }).inputValue();
    await current.getByText('Remove unissued items', { exact: true }).click();
    await current.getByLabel('Remove QA-STOCK', { exact: true }).check();
    await current.getByLabel('Remove QA-STOCK / Extras: QA-OTHER', { exact: true }).check();
    await current.getByLabel('Removal reason', { exact: true }).fill('Guest changed selection');
    await current.getByRole('button', { name: 'Remove selected items', exact: true }).click();
    await expect(current.getByText(/Order \d+ . open . unpaid . INR 118.00/, { exact: true })).toBeVisible();

    await current.getByLabel('Table name', { exact: true }).fill('Moved table');
    await current.getByRole('button', { name: 'Add table', exact: true }).click();
    await expect(current.getByLabel('Transfer destination', { exact: true }).locator('option').filter({ hasText: 'Moved table' })).toHaveCount(1);
    await current.getByLabel('Transfer destination', { exact: true }).selectOption({ label: 'Moved table' });
    await current.getByRole('button', { name: 'Transfer tab', exact: true }).click();
    await expect(current.getByRole('row').filter({ hasText: 'Modifier table' })).toContainText('Available');
    await expect(current.getByRole('row').filter({ hasText: 'Moved table' })).toContainText('Occupied');
    await expect(current.getByText('1 orders opened · 0 tickets created · 0 reservations starting', { exact: true })).toBeVisible();
    const reservationTable = current.getByLabel('Reservation table', { exact: true });
    const tableId = await reservationTable.locator('option').filter({ hasText: 'Moved table' }).getAttribute('value');
    await reservationTable.selectOption(tableId);
    const localTime = days => { const value = new Date(Date.now() + days * 86400000); value.setMinutes(value.getMinutes() - value.getTimezoneOffset()); return value.toISOString().slice(0, 16); };
    await current.getByLabel('Reservation customer', { exact: true }).selectOption('101');
    await current.getByLabel('Reservation time', { exact: true }).fill(localTime(2));
    await current.getByLabel('Reservation guests', { exact: true }).fill('3');
    await current.getByRole('button', { name: 'Book table', exact: true }).click();
    await expect(current.getByRole('button', { name: 'Reschedule reservation', exact: true })).toBeVisible();
    await current.getByRole('button', { name: 'Reschedule reservation', exact: true }).click();
    await current.getByLabel('Reservation time', { exact: true }).fill(localTime(3));
    await current.getByRole('button', { name: 'Save reservation schedule', exact: true }).click();
    await expect(current.getByRole('button', { name: 'Book table', exact: true })).toBeVisible();
    await current.getByRole('button', { name: 'Cancel reservation', exact: true }).click();
    await expect(current.getByRole('row').filter({ hasText: 'Moved table' }).filter({ hasText: '3 guests' })).toContainText('cancelled');
    await fits(current);
    await current.screenshot({ path: path.resolve(root, '../.local/restaurant-extension-desktop.png'), fullPage: true });
    await current.setViewportSize({ width: 390, height: 844 });
    await fits(current);
    await current.screenshot({ path: path.resolve(root, '../.local/restaurant-extension-mobile.png'), fullPage: true });
    const chef = current = await pageFor('chef', true);
    await expect(chef.getByText('Kitchen queue', { exact: true })).toBeVisible();
    await expect(chef.getByText('Daily operations', { exact: true })).toHaveCount(0);
    await expect(chef.getByRole('button', { name: 'Transfer tab', exact: true })).toHaveCount(0);
    assert.deepEqual(errors, []);
    assert.deepEqual(trace.filter(row => row.status >= 400), []);
    console.log(JSON.stringify({ real_api: true, order, modifiers: 2, transferred: true, summary: true, viewports: [1440, 390] }));
  } catch (error) {
    const failure = { message: error.message, trace: trace.slice(-25), errors, body: current ? (await current.locator('body').innerText()).slice(-4000) : null };
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-browser-failure.json'), JSON.stringify(failure));
    if (current) await current.screenshot({ path: path.resolve(root, '../.local/restaurant-browser-failure.png'), fullPage: true }).catch(() => {});
    console.error(JSON.stringify(failure)); throw error;
  }
  finally { closing = true; for (const context of contexts) { await Promise.all(context.pages().map(page => page.close())); await context.unrouteAll({ behavior: 'wait' }); await context.close(); } if (browser) await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
