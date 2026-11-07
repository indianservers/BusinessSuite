// Real local HTTP and browser acceptance; use only the disposable QA server.
const { chromium, expect: baseExpect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const expect = baseExpect.configure({ timeout: 30000 });
const origin = 'http://127.0.0.1:5200', root = 'http://127.0.0.1:1562/api/v1';
const output = path.join(__dirname, '../outputs/setup-live');
fs.mkdirSync(output, { recursive: true });
const report = { origin, database: 'disposable local QA database', checks: [], passed: false };
const pass = name => { report.checks.push(name); console.log('PASS', name); };
(async () => {
  let health;
  for (let attempt = 0; attempt < 90; attempt++) {
    try { health = await (await fetch('http://127.0.0.1:1562/health')).json(); break; }
    catch { await new Promise(resolve=>setTimeout(resolve, 1000)); }
  }
  assert.ok(health, 'Disposable backend starts successfully');
  assert.equal(health.environment, 'test');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let headers;
  async function api(url, method = 'GET', body) {
    const response = await fetch(root + url, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json();
    assert.ok(response.ok, `${method} ${url}: ${response.status} ${JSON.stringify(data)}`);
    return data;
  }
  const guide = () => page.getByRole('region', { name: 'Workspace setup guide' });
  const navigate = async url => {
    await Promise.all([page.waitForResponse(response=>response.url().endsWith('/api/v1/access/setup') && response.status() === 200), page.goto(origin + url)]);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText('Page not found');
  };
  try {
    await page.goto(origin + '/login');
    await page.locator('input[type=email]').fill('admin@suiteqa.example.com');
    await page.locator('input[type=password]').fill('SuiteQA@12345');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForURL(url => !url.pathname.includes('login'), { timeout: 60000 });
    const token = await page.evaluate(() => JSON.parse(sessionStorage.getItem('hrms-auth')).state.accessToken);
    headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'X-Suite-Organization': '1', 'X-Suite-Branch': '1' };
    await navigate('/setup-guide');
    await expect(guide()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Setup guide', exact: false }).first()).toBeVisible();
    await expect(guide().locator('details').first().locator('summary')).toContainText('Shared essentials');
    await page.screenshot({ path: path.join(output, 'guide-before.png') });
    pass('Real sign-in, dedicated setup page, shared-first groups and sidebar entry');

    await navigate('/settings/starter-values');
    for (const title of ['People & HR', 'CRM', 'Finance']) {
      const group = page.locator('article').filter({ has: page.getByRole('heading', { name: title, exact: true }) });
      await group.getByRole('button', { name: 'Add starter values', exact: true }).click();
      await expect(page.getByRole('status').filter({ hasText: 'starter records' })).toBeVisible();
    }
    await page.screenshot({ path: path.join(output, 'starter-values.png'), fullPage: true });
    pass('Added HR, CRM and finance starter values from real Settings UI');

    for (const [url, values] of [
      ['/settings/leaveTypes', ['Casual Leave', 'Sick Leave', 'Earned Leave']],
      ['/settings/salaryComponents', ['Basic Salary', 'House Rent Allowance', 'Transport Allowance', 'Other Deduction']],
      ['/settings/departments', ['General']], ['/settings/designations', ['Team Member', 'Manager']], ['/settings/shifts', ['General']],
    ]) {
      await navigate(url);
      for (const value of values) await expect(page.getByText(value, { exact: true }).first()).toBeVisible();
      await page.screenshot({ path: path.join(output, url.split('/').pop() + '.png') });
    }
    const salary = await api('/payroll/components');
    assert.ok(salary.length >= 4 && salary.every(row => Number(row.amount) === 0));
    pass('Leave types, zero-amount salary components, departments, designations and shift visible in Settings');

    await navigate('/settings/crm-lead-sources');
    const sources = page.getByRole('textbox', { name: 'Lead sources', exact: true });
    await expect(sources).toHaveValue(/Website[\s\S]*Referral/);
    await sources.fill((await sources.inputValue()) + '\nTrade Show');
    await page.getByRole('button', { name: 'Save sources', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lead sources saved' })).toBeVisible();
    await page.reload();
    await expect(sources).toHaveValue(/Trade Show/);
    await page.screenshot({ path: path.join(output, 'lead-sources.png') });
    const effective = await api('/access/settings/defaults/effective');
    assert.ok(effective.leadSources.includes('Trade Show'));
    pass('Custom lead source saved, survives reload and is included in effective form choices');

    await navigate('/settings/business-defaults');
    await expect(page.getByText('Currency', { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Currency', exact: true })).toContainText('INR');
    await page.getByRole('checkbox', { name: 'Custom currency', exact: true }).check();
    await page.getByRole('button', { name: 'Currency', exact: true }).click();
    const searchCurrency = page.getByRole('combobox', { name: 'Search currency', exact: true });
    await searchCurrency.fill('USD');
    await expect(page.getByRole('option').filter({ hasText: 'USD' })).toBeVisible();
    await searchCurrency.fill('AED');
    await expect(page.getByRole('option').filter({ hasText: 'AED' })).toBeVisible();
    await searchCurrency.press('Escape');
    await page.getByRole('checkbox', { name: 'Custom currency', exact: true }).uncheck();
    await page.screenshot({ path: path.join(output, 'business-defaults.png') });
    const configuration = await api('/access/settings/defaults/configuration');
    assert.equal(configuration.effective.currency, 'INR');
    assert.ok(configuration.fields.find(field => field.key === 'lead_source').options.some(option => option.value === 'Trade Show'));
    pass('Currency default is INR and custom lead sources appear in Defaults configuration');

    const status = await api('/access/setup');
    for (const id of ['departments', 'designations', 'shifts', 'leave-types', 'salary-components', 'pipeline']) assert.equal(status.moduleItems.find(item => item.id === id).ready, true, id);
    const workspace = await api('/project-management/workspaces', 'POST', { name: 'Setup live workspace' });
    const project = await api('/project-management/projects', 'POST', { name: 'Setup live project', project_key: 'SETUPLIVE', workspace_id: workspace.id });
    await api('/srm/inventory/warehouses', 'POST', { warehouse_code: 'SETUPLIVE', warehouse_name: 'Setup live warehouse' });
    await api('/fam/ledgers');
    let complete = await api('/access/setup');
    const pending = [...complete.items, ...complete.moduleItems].filter(item => item.required !== false && !item.ready);
    assert.deepEqual(pending.map(item => item.id), []);
    assert.ok(complete.recommendations.some(item => !item.ready));
    await navigate('/setup-guide');
    await expect(page).toHaveURL(origin + '/dashboard');
    await expect(guide()).toHaveCount(0);
    await expect(page.getByRole('link', { name: /^Setup guide/ })).toHaveCount(0);
    await page.screenshot({ path: path.join(output, 'guide-complete.png') });
    for (const url of ['/settings', '/hrms/dashboard', '/crm/dashboard', '/pms/overview', '/fam/dashboard', '/srm/dashboard']) {
      await navigate(url); await expect(guide()).toHaveCount(0);
    }
    pass('All mandatory setup complete: guide and sidebar hidden, including with recommendations incomplete');

    await api('/access/settings/company-profile', 'PATCH', { email: null });
    await navigate('/setup-guide'); await expect(guide()).toBeVisible();
    await expect(guide().getByText('Company details', { exact: true })).toBeVisible();
    await api('/access/settings/company-profile', 'PATCH', { email: 'company1@suiteqa.example.com' });
    await page.evaluate(()=>document.querySelector('.setup-guide-header button')?.click());
    await expect(guide()).toHaveCount(0);
    await expect(page).toHaveURL(origin + '/dashboard');
    pass('Guide reappears when a mandatory prerequisite is missing and hides after live recheck');

    await api(`/project-management/projects/${project.id}/archive`, 'POST', { archived: true });
    await navigate('/setup-guide'); await expect(guide()).toBeVisible();
    await page.setViewportSize({ width: 390, height: 950 });
    await expect.poll(async () => { const box = await guide().boundingBox(); return !!box && box.x < 40 && box.width > 300; }).toBe(true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    await page.screenshot({ path: path.join(output, 'guide-mobile.png') });
    assert.deepEqual(errors, []);
    pass('Project prerequisite reappears after archive; mobile layout has no overflow or browser exceptions');
    report.passed = true;
  } catch (error) {
    report.error = error.stack;
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
