const { chromium, expect } = require('playwright/test');
const path = require('node:path');
const fs = require('node:fs');

(async () => {
  const { createServer } = await import('vite');
  const server = await createServer({ root: path.resolve(__dirname, '..'), server: { host: '127.0.0.1', port: 0 }, plugins: [{ name: 'customization-qa-shell', configureServer(server) {
    server.middlewares.use('/customization-runtime-qa', async (_req, res) => {
      const html = await server.transformIndexHtml('/customization-runtime-qa', '<html><body><div id="root"></div><script type="module" src="/scripts/fixtures/customization-runtime-qa.tsx"></script></body></html>');
      res.setHeader('Content-Type', 'text/html'); res.end(html);
    });
  } }] });
  await server.listen();
  const browser = await chromium.launch({ headless: true });
  const errors = [], saves = [], actions = [], fieldSaves = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', e => { errors.push(e.message); console.error('Browser error:', e.message); });
    page.on('console', msg => { if (msg.type() === 'error') console.error('Browser console:', msg.text()); });
    const modules = [{ id: 1, module_api_name: 'vehicles', module_label: 'Vehicles', enabled: true }, { id: 2, module_api_name: 'jobs', module_label: 'Jobs', enabled: true }];
    const fields = [
      { id: 1, module_name: 'jobs', field_api_name: 'quantity', field_label: 'Quantity', field_type: 'number', editable: true, visible: true },
      { id: 2, module_name: 'jobs', field_api_name: 'vehicle', field_label: 'Vehicle', field_type: 'lookup', lookup_module: 'vehicles', editable: true, visible: true },
      { id: 3, module_name: 'jobs', field_api_name: 'total', field_label: 'Total', field_type: 'formula', formula_expression: 'quantity * 10', editable: false, visible: true },
    ];
    const job = { id: 7, values_json: { quantity: 2, vehicle: 11, total: '20' } };
    await page.route('**/api/v1/**', async route => {
      const req = route.request(), url = new URL(req.url()), pathname = url.pathname.replace('/api/v1', '');
      let body = { items: [], total: 0 };
      if (pathname === '/customization/modules') body = { items: modules, total: modules.length };
      if (pathname === '/customization/fields') {
        if (req.method() === 'POST') { const data = req.postDataJSON(); fieldSaves.push(data); fields.push({ id: fields.length + 1, ...data }); body = fields.at(-1); }
        else body = { items: fields, total: fields.length };
      }
      if (pathname === '/customization/buttons') body = { items: [{ id: 3, module_name: 'jobs', label: 'Log inspection', active: true }], total: 1 };
      if (pathname === '/customization/related-lists') body = { items: [{ id: 4, module_name: 'jobs', label: 'Parts', active: true }], total: 1 };
      if (pathname === '/custom/jobs') body = { items: [job], total: 21 };
      if (pathname === '/custom/jobs/7' && req.method() === 'PUT') { const data = req.postDataJSON(); saves.push(data); job.values_json = { ...job.values_json, ...data.values, total: String(data.values.quantity * 10) }; body = job; }
      if (pathname === '/custom/vehicles') body = { items: [{ id: 11, values_json: { registration: 'KA-01-1234' } }], total: 1 };
      if (pathname === '/custom/jobs/7/related/4') body = { items: [{ id: 31, values_json: { part: 'Brake pad' } }], total: 1 };
      if (pathname === '/customization/buttons/3/execute') { actions.push(req.postDataJSON()); body = { status: 'executed', event_id: 9 }; }
      await route.fulfill({ json: body });
    });
    await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/customization-runtime-qa`);
    await expect(page.getByRole('button', { name: 'Fields', exact: true })).toBeVisible({ timeout: 60000 });
    await page.getByRole('button', { name: 'Fields', exact: true }).click();
    await page.getByRole('button', { name: 'Add field', exact: true }).click();
    const form = page.getByRole('dialog');
    await form.getByLabel('Module', { exact: true }).selectOption('jobs');
    await form.getByLabel('Field name', { exact: true }).fill('Tax');
    await form.getByLabel('Type', { exact: true }).selectOption('formula');
    await form.getByLabel('Formula expression', { exact: true }).fill('quantity * 0.18');
    await form.getByRole('button', { name: 'Save field', exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(fieldSaves[0]).toMatchObject({ field_type: 'formula', formula_expression: 'quantity * 0.18', editable: false, required: false });
    await page.getByRole('button', { name: 'Modules', exact: true }).click();
    await page.locator('article').filter({ has: page.getByRole('heading', { name: 'Jobs', exact: true }) }).getByRole('button', { name: 'Open records' }).click();
    const records = page.getByRole('dialog');
    await records.getByRole('button', { name: 'Edit', exact: true }).click();
    await records.getByRole('spinbutton', { name: 'Quantity', exact: true }).fill('3');
    await records.getByRole('textbox', { name: 'Search Vehicle', exact: true }).fill('KA-');
    await records.getByRole('combobox', { name: 'Vehicle', exact: true }).selectOption('11');
    await expect(records.getByRole('textbox', { name: 'Total', exact: true })).toHaveAttribute('readonly', '');
    await records.getByRole('button', { name: 'Save record', exact: true }).click();
    await expect(records.getByText('30', { exact: true })).toBeVisible();
    expect(saves[0]).toEqual({ values: { quantity: 3, vehicle: 11 } });
    await records.getByRole('button', { name: 'Log inspection', exact: true }).click();
    await expect(records.getByRole('status')).toContainText('executed');
    await records.getByRole('button', { name: 'Log inspection', exact: true }).click();
    await expect.poll(() => actions.length).toBe(2);
    expect(actions[0].request_key).toBe(actions[1].request_key);
    await records.getByRole('button', { name: 'Show Parts', exact: true }).click();
    await expect(records.getByText(/Brake pad/)).toBeVisible();
    await expect(records.getByRole('button', { name: 'Next', exact: true })).toBeEnabled();
    const out = path.resolve(__dirname, '../../outputs/customization-phase-1'); fs.mkdirSync(out, { recursive: true });
    await page.screenshot({ path: path.join(out, 'records-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(records.getByRole('button', { name: 'Edit', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await records.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    await page.screenshot({ path: path.join(out, 'records-mobile.png'), fullPage: true });
    expect(errors).toEqual([]);
    console.log(JSON.stringify({ status: 'passed', checks: ['computed field configuration', 'lookup picker', 'computed values read-only', 'partial save omits computed fields', 'action replay key', 'related records', 'paging', 'mobile width', 'no page errors'], screenshots: out }, null, 2));
  } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
