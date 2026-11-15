const path = require('node:path'), assert = require('node:assert/strict'), fs = require('node:fs');
const { chromium, expect: base } = require('../frontend/node_modules/playwright/test');
const expect = base.configure({ timeout: 30000 }), bridge = process.env.CONTROL_BRIDGE;
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge || '')) throw Error('Disposable actual API bridge required');

(async () => {
  const auth = JSON.parse(process.env.SUITE_QA_AUTH), root = path.resolve(__dirname, '../frontend');
  process.chdir(root);
  const { createServer } = await import('../frontend/node_modules/vite/dist/node/index.js');
  const port = await new Promise(resolve => { const socket = require('node:net').createServer(); socket.listen(0, '127.0.0.1', () => { const assigned = socket.address().port; socket.close(() => resolve(assigned)); }); });
  const server = await createServer({ root, cacheDir: path.resolve(root, '../.local/vite-accounts-delivery-browser'), server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null } });
  const contexts = [], errors = [], trace = [];
  let browser, origin, current, closing = false, droppedActualTimeResponse = false;
  const artifacts = path.resolve(root, '../.local/accounts-delivery-browser');
  fs.mkdirSync(artifacts, { recursive: true });
  async function pageFor(role, mobile = false) {
    const context = await browser.newContext({ viewport: { width: mobile ? 390 : 1440, height: 1000 }, acceptDownloads: true });
    contexts.push(context);
    await context.addInitScript(identity => { window.qaAuth = identity; window.__AI_HRMS_CONFIG__ = { apiBaseUrl: '/api/v1' }; }, { token: auth[role], branch: auth.branch, context: auth.context });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.route(origin + '/**', async route => {
      const request = route.request(), url = new URL(request.url());
      try {
        if (url.pathname.startsWith('/api/')) {
          const response = await context.request.fetch(bridge + url.pathname + url.search, { method: request.method(), headers: request.headers(), data: request.postDataBuffer() || undefined });
          const row = { role, method: request.method(), path: url.pathname, status: response.status() };
          trace.push(row);
          if (!droppedActualTimeResponse && role === 'preparer' && request.method() === 'POST' && url.pathname.endsWith('/time') && response.status() === 201) {
            droppedActualTimeResponse = true; row.dropped_response = true;
            // The native operation already committed. Lose only the response to
            // prove the UI retains its request key across an unknown outcome.
            return route.abort('failed');
          }
          return route.fulfill({ response });
        }
        if (request.isNavigationRequest()) return route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/accounts-native.tsx");</script>' });
        return route.continue();
      } catch (error) { if (!closing) errors.push(error.message); await route.abort().catch(() => {}); }
    });
    await page.goto(origin + '/srm/accounts-periods');
    return page;
  }
  async function sections(page) {
    const details = page.locator('details');
    for (let index = 0; index < await details.count(); index++) {
      const item = details.nth(index);
      if (await item.isVisible() && await item.getAttribute('open') === null) await item.locator('summary').first().click();
    }
  }
  async function openFirst(page, mobile = false) {
    if (mobile) await page.getByText('More actions', { exact: true }).first().click();
    await page.getByRole('button', { name: 'Open period', exact: true }).first().click();
    await sections(page);
  }
  async function fits(page) {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, 'Page overflowed the viewport');
  }
  async function snapshot(name) { await fits(current); await current.screenshot({ path: path.join(artifacts, name + '.png'), fullPage: true }); }
  try {
    await server.listen(); origin = 'http://127.0.0.1:' + server.httpServer.address().port;
    browser = await chromium.launch();

    current = await pageFor('manager');
    await current.getByRole('button', { name: 'Create engagement', exact: true }).click();
    await current.getByLabel('Engagement client', { exact: true }).selectOption(String(auth.client));
    await current.getByLabel('Engagement name', { exact: true }).fill('Accounts browser service');
    await current.getByLabel('Engagement currency', { exact: true }).fill('INR');
    await current.getByRole('button', { name: 'Save engagement', exact: true }).click();
    const engagementSelect = current.getByLabel('Client engagement', { exact: true });
    await expect(engagementSelect.locator('option').filter({ hasText: 'Accounts browser service' })).toHaveCount(1);
    const engagement = await engagementSelect.locator('option').filter({ hasText: 'Accounts browser service' }).getAttribute('value');
    await engagementSelect.selectOption(engagement);
    await current.getByLabel('Period title', { exact: true }).fill('January Accounts delivery');
    await current.getByLabel('Period starts', { exact: true }).fill('2026-01-01');
    await current.getByLabel('Period ends', { exact: true }).fill('2026-01-31');
    await current.getByLabel('Due date', { exact: true }).fill('2026-02-10');
    await current.getByLabel('Preparer', { exact: true }).selectOption(String(auth.preparer_employee));
    await current.getByLabel('Independent reviewer', { exact: true }).selectOption(String(auth.reviewer_employee));
    await sections(current);
    await current.getByLabel('Occurrences', { exact: true }).fill('2');
    await current.getByLabel('Interval months', { exact: true }).fill('1');
    await current.getByRole('button', { name: 'Create period', exact: true }).click();
    await expect(current.getByRole('button', { name: 'Open period', exact: true })).toHaveCount(2);
    await sections(current);
    await current.getByLabel('Delivery project', { exact: true }).selectOption(String(auth.project));
    await current.getByRole('button', { name: 'Link delivery project', exact: true }).click();
    await expect(current.getByText('Canonical client delivery', { exact: true }).last()).toBeVisible();
    await snapshot('manager-desktop');
    await current.setViewportSize({ width: 390, height: 1000 });
    await snapshot('manager-mobile');

    current = await pageFor('preparer', true);
    await expect(current.getByRole('button', { name: 'Create engagement', exact: true })).toHaveCount(0);
    await expect(current.getByRole('heading', { name: 'New service period', exact: true })).toHaveCount(0);
    await openFirst(current, true);
    await current.getByLabel('Document title', { exact: true }).fill('Client bank statements');
    await current.getByLabel('Document due date', { exact: true }).fill('2026-02-05');
    await current.getByRole('button', { name: 'Request document', exact: true }).click();
    await expect(current.getByText(/^Client bank statements — requested — Due:/)).toBeVisible();
    await current.getByLabel('Delivery task', { exact: true }).selectOption(String(auth.task));
    const bytes = Buffer.from('Browser uploaded canonical client statements');
    await current.getByLabel('Document file', { exact: true }).setInputFiles({ name: 'client-statements.txt', mimeType: 'text/plain', buffer: bytes });
    await current.getByRole('button', { name: 'Upload document', exact: true }).click();
    await expect(current.getByRole('button', { name: 'Download document', exact: true })).toBeVisible();
    const downloaded = current.waitForEvent('download');
    await current.getByRole('button', { name: 'Download document', exact: true }).click();
    const file = await downloaded;
    assert.deepEqual(fs.readFileSync(await file.path()), bytes);
    await current.getByLabel('Actual work date', { exact: true }).fill('2026-01-15');
    await current.getByLabel('Actual minutes', { exact: true }).fill('75');
    await current.getByLabel('Actual work description', { exact: true }).fill('Actual reconciliation of supplied client records');
    await current.getByRole('button', { name: 'Record actual time', exact: true }).click();
    await expect(current.getByRole('alert').first()).toBeVisible();
    await expect(current.getByRole('button', { name: 'Record actual time', exact: true })).toBeEnabled();
    await current.getByRole('button', { name: 'Record actual time', exact: true }).click();
    await expect(current.getByText(/Recorded 75 minutes/)).toBeVisible();
    await current.getByLabel('Updated work summary', { exact: true }).fill('Prepared reconciliation using uploaded records');
    await current.getByRole('button', { name: 'Save work', exact: true }).click();
    await current.getByRole('button', { name: 'Submit for review', exact: true }).click();
    await expect(current.getByText('Status: submitted | Work revision: 1', { exact: true })).toBeVisible();
    await expect(current.getByRole('button', { name: 'Approve work', exact: true })).toHaveCount(0);
    await expect(current.getByRole('button', { name: 'Create service invoice', exact: true })).toHaveCount(0);
    await snapshot('preparer-mobile');

    current = await pageFor('reviewer', true); await openFirst(current, true);
    await expect(current.getByLabel('Updated work summary', { exact: true })).toHaveCount(0);
    await expect(current.getByRole('button', { name: 'Record actual time', exact: true })).toHaveCount(0);
    await current.getByLabel('Review notes', { exact: true }).fill('Explain the bank reconciliation difference');
    await current.getByRole('button', { name: 'Return for changes', exact: true }).click();
    await expect(current.getByText('Status: returned | Work revision: 1', { exact: true })).toBeVisible();
    await snapshot('reviewer-return-mobile');

    current = await pageFor('preparer', true); await openFirst(current, true);
    await current.getByLabel('Updated work summary', { exact: true }).fill('Corrected reconciliation with the explained bank difference');
    await current.getByRole('button', { name: 'Save work', exact: true }).click();
    await current.getByRole('button', { name: 'Submit for review', exact: true }).click();
    await expect(current.getByText('Status: submitted | Work revision: 2', { exact: true })).toBeVisible();
    current = await pageFor('reviewer', true); await openFirst(current, true);
    await current.getByLabel('Review notes', { exact: true }).fill('Independently reviewed corrected source records');
    await current.getByRole('button', { name: 'Approve work', exact: true }).click();
    await expect(current.getByText('Status: approved | Work revision: 2', { exact: true })).toBeVisible();
    await snapshot('reviewer-approved-mobile');

    current = await pageFor('manager'); await openFirst(current);
    await current.getByLabel('Service fee', { exact: true }).fill('1500.00');
    await current.getByRole('button', { name: 'Create service invoice', exact: true }).click();
    await expect(current.getByText('Outstanding: 1500.00 INR', { exact: true })).toBeVisible();
    await current.getByRole('button', { name: 'Issue service invoice', exact: true }).click();
    await expect(current.getByRole('button', { name: 'Issue service invoice', exact: true })).toHaveCount(0);
    await snapshot('issued-invoice-desktop');

    current = await pageFor('billing', true); await openFirst(current, true);
    await expect(current.getByRole('button', { name: 'Create engagement', exact: true })).toHaveCount(0);
    await expect(current.getByRole('heading', { name: 'New service period', exact: true })).toHaveCount(0);
    await expect(current.getByLabel('Updated work summary', { exact: true })).toHaveCount(0);
    await expect(current.getByRole('button', { name: 'Approve work', exact: true })).toHaveCount(0);
    await current.getByLabel('Collection amount', { exact: true }).fill('500.00');
    await current.getByLabel('Payment method', { exact: true }).selectOption('bank_transfer');
    await current.getByLabel('Payment reference', { exact: true }).fill('Native partial collection');
    await current.getByRole('button', { name: 'Record collection', exact: true }).click();
    await expect(current.getByText('Outstanding: 1000.00 INR', { exact: true })).toBeVisible();
    await current.getByLabel('Collection amount', { exact: true }).fill('1000.00');
    await current.getByLabel('Payment reference', { exact: true }).fill('Native final collection');
    await current.getByRole('button', { name: 'Record collection', exact: true }).click();
    await expect(current.getByText('Outstanding: 0.00 INR', { exact: true })).toBeVisible();
    await expect(current.getByRole('button', { name: 'Record collection', exact: true })).toHaveCount(0);
    await expect(current.getByRole('button', { name: 'Create service invoice', exact: true })).toHaveCount(0);
    await snapshot('collected-mobile');
    assert.deepEqual(errors, []);
    assert.deepEqual(trace.filter(row => row.status >= 400), []);
    const count = suffix => trace.filter(row => row.method === 'POST' && row.path.endsWith(suffix)).length;
    assert.equal(count('/srm/accounts/engagements'), 1);
    assert.equal(count('/srm/accounts/periods'), 1);
    assert.equal(count('/upload'), 1);
    assert.equal(count('/time'), 2);
    assert.equal(trace.filter(row => row.dropped_response).length, 1);
    assert.equal(count('/submit'), 2);
    assert.equal(count('/return'), 1);
    assert.equal(count('/invoice'), 1);
    assert.equal(count('/payments'), 2);
    const result = { real_api: true, roles: ['manager', 'preparer', 'reviewer', 'billing'], viewports: [1440, 390], recurring_periods: 2, work_revision: 2, actual_minutes: 75, actual_time_attempts: 2, unknown_outcome_retries: 1, receipts: 2, outstanding: '0.00', requests: trace.length, trace };
    fs.writeFileSync(path.join(artifacts, 'results.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } catch (error) {
    const failure = { message: error.message, trace: trace.slice(-40), errors, body: current ? (await current.locator('body').innerText()).slice(-10000) : null };
    fs.writeFileSync(path.join(artifacts, 'failure.json'), JSON.stringify(failure, null, 2));
    if (current) await current.screenshot({ path: path.join(artifacts, 'failure.png'), fullPage: true }).catch(() => {});
    console.error(JSON.stringify(failure)); throw error;
  } finally {
    closing = true;
    for (const context of contexts) { await Promise.all(context.pages().map(page => page.close())); await context.unrouteAll({ behavior: 'wait' }); await context.close(); }
    if (browser) await browser.close(); await server.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
