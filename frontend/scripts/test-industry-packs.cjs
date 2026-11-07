const { chromium, expect } = require('playwright/test');
const path = require('node:path'), fs = require('node:fs');
(async () => {
  const { createServer } = await import('vite');
  const server = await createServer({ root: path.resolve(__dirname, '..'), server: { host: '127.0.0.1', port: 0 }, plugins: [{ name: 'industry-packs-qa', configureServer(server) {
    server.middlewares.use('/industry-packs-qa', async (_req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await server.transformIndexHtml('/industry-packs-qa', '<html><body><div id="root"></div><script type="module" src="/scripts/fixtures/industry-packs-qa.tsx"></script></body></html>')); });
  } }] });
  await server.listen(); const browser = await chromium.launch({ headless: true });
  const errors = [], requests = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    page.on('pageerror', e => { errors.push(e.message); console.error(e.message); });
    let current = null, conflict = true, samples = 0;
    const catalog = [{ key: 'salon-spa', name: 'Salon & Spa', version: 1, requiredModules: ['crm'], recommendedModules: ['srm', 'fam', 'hrms'], automations: ['New record follow-up task', 'Open-record reminder after 24 hours', 'Stage handoff task'], reports: ['Pipeline records', 'Stage totals', 'Follow-up task queue'] }];
    const pack = { pack_key: 'salon-spa', version: 1, status: 'Enabled', run_as_user_id: 7, modules: ['crm'], assets: [{ kind: 'pipeline', key: 'pipeline', id: 1 }, ...[0,1,2].map(i => ({ kind: 'report', key: String(i), id: 10+i }))] };
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), pathname = new URL(request.url()).pathname.replace('/api/v1', '');
      requests.push({ pathname, method: request.method(), data: request.postData() ? request.postDataJSON() : null, headers: request.headers() });
      let json = { items: [] };
      if (pathname === '/industry-packs/catalog') json = { items: catalog };
      if (pathname === '/industry-packs/installed') json = { items: current ? [current] : [] };
      if (pathname === '/industry-packs/execution-identities') json = { items: [{ id: 7, name: 'Managed CRM operator' }] };
      if (pathname.endsWith('/preflight')) { if (conflict) { conflict = false; return route.fulfill({ status: 409, json: { detail: 'Resolve edited pack assets before upgrading' } }); } json = { conflicts: [] }; }
      if (pathname === '/access/step-up') json = { token: 'qa-step-up-token' };
      if (pathname.endsWith('/install')) json = current = { ...pack };
      if (pathname.endsWith('/disable')) json = current = { ...pack, status: 'Disabled' };
      if (pathname.endsWith('/sample-data')) { samples++; json = { ids: [20,21], created: true }; }
      if (pathname === '/analytics/reports/10/run') json = { fields: ['name', 'amount'], items: [{ name: 'Real booking', amount: 350 }], total: 1 };
      await route.fulfill({ json });
    });
    await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/industry-packs-qa`);
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Salon & Spa setup' })).toBeVisible({ timeout: 60000 });
    await expect(dialog.getByRole('button', { name: 'Install industry pack', exact: true })).toBeDisabled();
    await dialog.getByRole('combobox', { name: 'Workflow execution identity', exact: true }).selectOption('7');
    await dialog.getByLabel('Current administrator password', { exact: true }).fill('qa-only-password');
    await dialog.getByRole('button', { name: 'Install industry pack', exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('Resolve edited pack assets');
    expect(requests.filter(r => r.pathname.endsWith('/install'))).toHaveLength(0);
    await dialog.getByRole('button', { name: 'Install industry pack', exact: true }).click();
    await expect(dialog.getByRole('status')).toContainText('No sample customers or deals were added');
    const sent = requests.find(r => r.pathname.endsWith('/install'));
    expect(sent.data).toEqual({ run_as_user_id: 7, modules: ['crm'] });
    expect(sent.headers['x-access-step-up']).toBe('qa-step-up-token');
    expect(samples).toBe(0);
    await dialog.getByRole('button', { name: 'Pipeline records', exact: true }).click();
    await expect(dialog.getByRole('cell', { name: 'Real booking', exact: true })).toBeVisible();
    await dialog.getByLabel('Current administrator password', { exact: true }).fill('qa-only-password');
    await dialog.getByRole('button', { name: 'Add optional sample records', exact: true }).click();
    await expect(dialog.getByRole('status')).toContainText('labelled sample records added'); expect(samples).toBe(1);
    const out = path.resolve(__dirname, '../../outputs/industry-packs-phase-2'); fs.mkdirSync(out, { recursive: true });
    await page.screenshot({ path: path.join(out, 'onboarding-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth+1)).toBe(true);
    await page.screenshot({ path: path.join(out, 'onboarding-mobile.png'), fullPage: true });
    await dialog.getByLabel('Current administrator password', { exact: true }).fill('qa-only-password');
    await dialog.getByRole('button', { name: 'Disable pack', exact: true }).click();
    await expect(dialog.getByRole('status')).toContainText('Business records were preserved');
    await expect(dialog.getByRole('button', { name: 'Pipeline records', exact: true })).toBeDisabled();
    expect(errors).toEqual([]);
    console.log(JSON.stringify({ status: 'passed', checks: ['managed identity required', 'preflight blocks conflict', 'administrator verification', 'clean installation', 'real report preview', 'explicit sample opt-in', 'disable lifecycle', 'mobile layout', 'no page errors'] }, null, 2));
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
