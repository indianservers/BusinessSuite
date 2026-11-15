const path = require('node:path'), fs = require('node:fs'), assert = require('node:assert/strict');
const { chromium, expect: base } = require('../frontend/node_modules/playwright/test');
const expect = base.configure({ timeout: 120000 }); // Existing actual-app browser budget.
(async () => {
  const qa = JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE, 'utf8')), bridge = process.env.CONTROL_BRIDGE;
  assert.match(bridge, /^http:\/\/127\.0\.0\.1:\d+$/);
  const root = path.resolve(__dirname, '../frontend'); process.chdir(root);
  const { createServer } = await import('../frontend/node_modules/vite/dist/node/index.js');
  const port = await new Promise(resolve => { const socket = require('node:net').createServer(); socket.listen(0, '127.0.0.1', () => { const value = socket.address().port; socket.close(() => resolve(value)); }); });
  const vite = await createServer({ root, server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null } });
  const contexts = [], closing = new Set(), trace = [], errors = [], issued = [], collected = [];
  let browser, origin, current;
  async function open(role, mobile = false) {
    const context = await browser.newContext({ viewport: { width: mobile ? 390 : 1440, height: 1000 } }); contexts.push(context);
    await context.addInitScript(identity => {
      sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', identity.branch);
      sessionStorage.setItem('suite-pack-context', identity.context); sessionStorage.setItem('suite-business-pack-context', identity.context);
      sessionStorage.setItem('suite-pack-context-owner', JSON.stringify([null,'1',identity.branch]));
      sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: identity.token, refreshToken: null, user: identity.user, isAuthenticated: true }, version: 0 }));
    }, { ...qa[role], branch: qa.branch, context: qa.context });
    const page = await context.newPage(); current = page;
    page.on('pageerror', error => errors.push(error.stack || error.message));
    await page.route('**/api/**', async route => {
      try {
        const request = route.request(), url = new URL(request.url());
        const response = await context.request.fetch(bridge + url.pathname + url.search, { method: request.method(), headers: request.headers(), data: request.postDataBuffer() || undefined });
        trace.push({ role, method: request.method(), path: url.pathname, status: response.status() });
        if (request.method() === 'POST' && /\/restaurant\/tabs\/\d+\/bills$/.test(url.pathname) && response.status() === 201) issued.push(await response.json());
        if (request.method() === 'POST' && /\/restaurant\/tabs\/\d+\/bills\/\d+\/payments$/.test(url.pathname) && response.status() === 201) collected.push(await response.json());
        await route.fulfill({ response });
      } catch (error) { if (!closing.has(context)) errors.push(error.message); await route.abort().catch(() => {}); }
    });
    await page.goto(origin + '/srm/restaurant-kitchen');
    await expect(page.getByRole('heading', { name: 'Restaurant orders & kitchen', exact: true })).toBeVisible();
    return page;
  }
  async function close(page) { const context = page.context(); closing.add(context); await context.unrouteAll({ behavior: 'wait' }); await context.close(); }
  async function fits(page) { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false); }
  try {
    await vite.listen(); origin = 'http://127.0.0.1:' + vite.httpServer.address().port; browser = await chromium.launch();
    const manager = await open('manager');
    await expect(manager.getByRole('button', { name: 'Close register', exact: true })).toBeVisible();
    await manager.getByRole('button', { name: 'Expand all menu categories', exact: true }).click();
    await expect(manager.getByRole('navigation', { name: 'Module navigation' }).getByRole('link', { name: 'Construction operations', exact: true })).toHaveCount(0);
    await manager.getByLabel('Table name', { exact: true }).fill('Split dining');
    await manager.getByRole('button', { name: 'Add table', exact: true }).click();
    await expect(manager.getByLabel('Tab customer', { exact: true }).locator('option[value="101"]')).toHaveCount(1);
    await manager.getByLabel('Tab customer', { exact: true }).selectOption('101');
    await expect(manager.getByLabel('Tab table', { exact: true }).locator('option').filter({ hasText: 'Split dining' })).toHaveCount(1);
    await manager.getByLabel('Tab table', { exact: true }).selectOption({ label: 'Split dining' });
    await manager.getByLabel('Menu item', { exact: true }).selectOption(String(qa.product));
    await manager.getByRole('button', { name: 'Add menu item', exact: true }).click();
    await manager.getByRole('button', { name: 'Open unpaid tab', exact: true }).click();
    await expect(manager.getByLabel('Service order ID', { exact: true })).not.toHaveValue('');
    const order = await manager.getByLabel('Service order ID', { exact: true }).inputValue();
    await manager.getByLabel('Send quantity', { exact: true }).fill('1');
    await manager.getByRole('button', { name: 'Send selected items', exact: true }).click();
    await expect(manager.getByText(/Ticket \d+ · queued/)).toBeVisible();
    await manager.getByText('Issue a separate item bill', { exact: true }).click();
    for (let index = 0; index < 2; index++) {
      if (index) await manager.setViewportSize({ width: 390, height: 1000 });
      await manager.getByLabel(/^Bill quantity /).fill('0.5');
      await expect(manager.getByLabel('Selected bill total', { exact: true })).toHaveText('Selected total: INR 59.00');
      await manager.getByRole('button', { name: 'Issue selected item bill', exact: true }).click();
      await expect.poll(() => issued.length).toBe(index + 1);
      await expect(manager.getByText(issued[index].bill.number, { exact: true })).toBeVisible();
      assert.equal(issued[index].bill.total, '59.00'); await fits(manager);
      await manager.screenshot({ path: path.resolve(root, index ? '../.local/restaurant-split-mobile.png' : '../.local/restaurant-split-desktop.png'), fullPage: true });
    }
    assert.notEqual(issued[0].invoice_id, issued[1].invoice_id);
    await manager.getByLabel('Collection register', { exact: true }).selectOption(String(qa.register));
    for (const [index, method, amount, balance] of [[0,'cash','20','39.00'],[0,'card','39','0.00'],[1,'cash','59','0.00']]) {
      await manager.getByLabel('Split invoice to collect', { exact: true }).selectOption(String(issued[index].bill_id));
      await manager.getByLabel('Split payment method', { exact: true }).selectOption(method);
      await manager.getByLabel('Split payment amount', { exact: true }).fill(amount);
      const count = collected.length;
      await manager.getByRole('button', { name: 'Collect split invoice payment', exact: true }).click();
      await expect.poll(() => collected.length).toBe(count + 1); assert.equal(collected.at(-1).bill.balance, balance);
    }
    await expect(manager.getByRole('button', { name: 'Collect split invoice payment', exact: true })).toHaveCount(0); await fits(manager);
    const cashier = await open('cashier', true);
    await cashier.getByRole('button', { name: new RegExp(`^Tab ${order} · table`) }).click();
    await expect(cashier.getByText(issued[0].bill.number, { exact: true })).toBeVisible();
    await expect(cashier.getByText(issued[1].bill.number, { exact: true })).toBeVisible();
    await expect(cashier.getByRole('button', { name: 'Close register', exact: true })).toHaveCount(0); await fits(cashier); await close(cashier);
    const chef = await open('chef', true);
    await expect(chef.getByText('Tab billing & payments', { exact: true })).toHaveCount(0);
    await expect(chef.getByRole('button', { name: 'Close register', exact: true })).toHaveCount(0);
    await chef.getByRole('button', { name: 'Start preparation', exact: true }).click();
    await chef.getByRole('button', { name: 'Mark ready', exact: true }).click();
    await expect(chef.getByText(/Ticket \d+ · ready/)).toBeVisible(); await close(chef);
    const server = await open('server', true);
    await server.getByLabel('Service order ID', { exact: true }).fill(order);
    await server.getByRole('button', { name: 'Mark served', exact: true }).click();
    await expect(server.getByText(`Order ${order} · served`, { exact: true })).toBeVisible(); await fits(server); await close(server);
    await manager.setViewportSize({ width: 1440, height: 1000 });
    await manager.getByRole('button', { name: 'Close register', exact: true }).click();
    await expect(manager.getByRole('heading', { name: 'Cashier Closing', exact: true })).toBeVisible();
    await manager.getByPlaceholder('Counted cash', { exact: true }).fill('79');
    await manager.getByRole('button', { name: 'Close Session', exact: true }).click();
    await expect(manager.getByText('No open session', { exact: true })).toBeVisible(); await fits(manager);
    await manager.screenshot({ path: path.resolve(root, '../.local/restaurant-split-close-desktop.png'), fullPage: true });
    assert(!trace.some(row => row.role === 'chef' && /\/bills/.test(row.path)), 'Chef must not request financial split bills');
    const rejected = trace.filter(row => row.status >= 400);
    assert.deepEqual(rejected.filter(row => row.path !== '/api/v1/follow-ups/statistics' || row.status !== 503), []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-split-browser-proof.json'), JSON.stringify({ production_entry: true, order, issued, collected, trace, errors, viewports: [1440,390] }));
    console.log(JSON.stringify({ production_entry: true, order, invoices: issued.length, receipts: collected.length, native_shift_close: true, viewports: [1440,390] }));
  } catch (error) {
    fs.writeFileSync(path.resolve(root, '../.local/restaurant-split-browser-failure.json'), JSON.stringify({ message: error.message, trace, errors, body: current && !current.isClosed() ? (await current.locator('body').innerText()).slice(-10000) : null })); throw error;
  } finally { for (const context of contexts) { closing.add(context); await context.unrouteAll({ behavior: 'wait' }).catch(() => {}); await context.close().catch(() => {}); } if (browser) await browser.close(); await vite.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
