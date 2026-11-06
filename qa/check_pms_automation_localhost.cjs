// Uses only the explicitly seeded, isolated localhost workflow sandbox.
const { chromium } = require('../frontend/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const info = JSON.parse(fs.readFileSync(path.join(root, '.local/workflow-localhost-session.json')));
  assert.match(info.database, /^business_suite_workflow_localhost_[a-f0-9]+_test$/);
  assert.ok(['localhost', '127.0.0.1'].includes(new URL(info.frontend).hostname));
  const browser = await chromium.launch({ headless: true });
  const report = { site: info.frontend, checks: [], passed: false };
  try {
    const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(info.frontend + '/login');
    await page.locator('input[type=email]').fill(info.accounts.owner);
    await page.locator('input[type=password]').fill(info.password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForURL(u => !u.pathname.includes('login'), { timeout: 60000 });
    await page.goto(info.frontend + `/pms/automation?workspace=${info.workspace_id}`);
    await page.getByLabel('Rule name', { exact: true }).fill('Compound localhost ' + Date.now(), { timeout: 60000 });
    await page.getByLabel('Automation project', { exact: true }).selectOption(String(info.project_id));
    await page.getByRole('button', { name: 'Add conditions', exact: true }).click();
    await page.getByLabel('Conditions 1 field', { exact: true }).selectOption('work_type');
    await page.getByLabel('Conditions 1 value', { exact: true }).fill('Bug');
    await page.getByRole('button', { name: 'Add group', exact: true }).click();
    await page.getByLabel('Conditions 2 1 value', { exact: true }).fill('High');
    const group = page.getByRole('group', { name: 'Conditions 2', exact: true });
    await group.getByRole('button', { name: 'Add condition', exact: true }).click();
    await page.getByLabel('Conditions 2 2 field', { exact: true }).selectOption('title');
    await page.getByLabel('Conditions 2 2 operator', { exact: true }).selectOption('contains');
    await page.getByLabel('Conditions 2 2 value', { exact: true }).fill('outage');
    await page.getByLabel('Automation priority', { exact: true }).selectOption('Urgent');
    const saved = page.waitForResponse(r => r.url().endsWith('/automations') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Save and enable rule', exact: true }).click();
    const response = await saved; assert.equal(response.status(), 201);
    const rule = await response.json();
    assert.deepEqual(rule.conditions, { all: [{ field: 'work_type', operator: 'equals', value: 'Bug' }, { any: [{ field: 'priority', operator: 'equals', value: 'High' }, { field: 'title', operator: 'contains', value: 'outage' }] }] });
    report.checks.push('Create nested AND/OR rule in full localhost UI');
    await page.reload();
    const card = page.getByRole('article').filter({ hasText: rule.name });
    await card.getByRole('button', { name: 'Edit', exact: true }).click({ timeout: 60000 });
    assert.equal(await page.getByLabel('Conditions 2 match', { exact: true }).inputValue(), 'any');
    assert.equal(await page.getByLabel('Conditions 2 2 value', { exact: true }).inputValue(), 'outage');
    report.checks.push('Reload and edit preserves nested condition tree');
    for (const [work_type, title, priority, expected] of [['Bug', 'Service outage', 'Low', 'Urgent'], ['Bug', 'Cosmetic', 'Low', 'Low'], ['Task', 'Service outage', 'Low', 'Low']]) {
      const task = await page.evaluate(async ({ pid, work_type, title, priority }) => {
        const { api } = await import('/src/services/api.ts');
        return (await api.post(`/project-management/projects/${pid}/tasks`, { task_key: 'AUTOQA-' + crypto.randomUUID().slice(0, 8), title, work_type, priority })).data;
      }, { pid: info.project_id, work_type, title, priority });
      assert.equal(task.priority, expected);
    }
    report.checks.push('Real task events execute matching rule and exclude both nonmatches');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile overflow');
    await page.screenshot({ path: path.join(root, 'outputs/pms-compound-localhost-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    report.checks.push('Mobile layout and browser runtime'); report.passed = true;
  } finally {
    fs.writeFileSync(path.join(root, 'outputs/pms-automation-localhost-browser.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
  console.log(JSON.stringify(report));
})().catch(e => { console.error(e.message); process.exitCode = 1; });
