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
    const open = () => page.goto(info.frontend + `/pms/automation?workspace=${info.workspace_id}`);
    async function api(method, url, data) {
      return page.evaluate(async ({ method, url, data }) => {
        const { api } = await import('/src/services/api.ts'); return (await api.request({ method, url, data })).data;
      }, { method, url: '/project-management' + url, data });
    }
    const task = (title, extra = {}) => api('post', `/projects/${info.project_id}/tasks`, { title, task_key: 'CLOCKQA-' + crypto.randomUUID().slice(0, 8), priority: 'Low', ...extra });
    async function clock() {
      const response = await fetch(info.api + '/api/v1/internal/pms-automations', { headers: { Authorization: 'Bearer ' + info.scheduler_secret } });
      assert.equal(response.status, 200); const result = await response.json(); assert.deepEqual(result.failed_rule_ids, []); return result;
    }
    async function create(trigger, marker, assign = false) {
      await open(); await page.getByLabel('Rule name', { exact: true }).fill(marker, { timeout: 60000 });
      await page.getByLabel('Automation project', { exact: true }).selectOption(String(info.project_id));
      await page.getByLabel('Automation trigger', { exact: true }).selectOption(trigger);
      await page.getByLabel('Automation schedule time', { exact: true }).fill('00:00');
      await page.getByLabel('Automation timezone', { exact: true }).fill('UTC');
      if (trigger === 'task.due_date') await page.getByLabel('Automation due offset', { exact: true }).fill('-1');
      await page.getByRole('button', { name: 'Add conditions', exact: true }).click();
      await page.getByLabel('Conditions 1 field', { exact: true }).selectOption('title');
      await page.getByLabel('Conditions 1 operator', { exact: true }).selectOption('contains');
      await page.getByLabel('Conditions 1 value', { exact: true }).fill(marker);
      if (assign) {
        await page.getByLabel('Automation action', { exact: true }).selectOption('assign_user');
        await page.getByLabel('Automation assignee', { exact: true }).selectOption({ label: info.accounts.reviewer });
      }
      const saved = page.waitForResponse(r => r.url().endsWith('/automations') && r.request().method() === 'POST');
      await page.getByRole('button', { name: 'Save and enable rule', exact: true }).click();
      const response = await saved; assert.equal(response.status(), 201); return response.json();
    }
    assert.equal((await fetch(info.api + '/api/v1/internal/pms-automations')).status, 401);
    report.checks.push('Scheduler requires dedicated credentials');
    const dailyName = 'Daily QA ' + Date.now();
    const daily = await create('schedule.daily', dailyName);
    const dailyTask = await task(dailyName);
    await clock(); assert.equal((await api('get', `/tasks/${dailyTask.id}`)).priority, 'High');
    await api('patch', `/tasks/${dailyTask.id}`, { priority: 'Low' });
    await clock(); assert.equal((await api('get', `/tasks/${dailyTask.id}`)).priority, 'Low');
    report.checks.push('Daily UI rule runs through real scheduler, retries do not replay');
    await api('patch', `/workspaces/${info.workspace_id}/automations/${daily.id}`, { enabled: false });
    const dueName = 'Due QA ' + Date.now();
    const due = await create('task.due_date', dueName, true);
    const date = days => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
    const dueTask = await task(dueName + ' tomorrow', { due_date: date(1) });
    const overdue = await task(dueName + ' overdue', { due_date: date(-2) });
    const future = await task(dueName + ' future', { due_date: date(2) });
    const undated = await task(dueName + ' undated');
    await api('patch', `/workspaces/${info.workspace_id}/automations/${due.id}`, { enabled: false });
    await clock(); assert.ok(!(await api('get', `/tasks/${dueTask.id}`)).assignee_user_ids.includes(due.assignee_id));
    await api('patch', `/workspaces/${info.workspace_id}/automations/${due.id}`, { enabled: true });
    await clock();
    for (const t of [dueTask, overdue]) assert.ok((await api('get', `/tasks/${t.id}`)).assignee_user_ids.includes(due.assignee_id));
    for (const t of [future, undated]) assert.ok(!(await api('get', `/tasks/${t.id}`)).assignee_user_ids.includes(due.assignee_id));
    report.checks.push('Due-date offset, overdue catchup, future/undated exclusion and pause/resume');
    await api('patch', `/tasks/${dueTask.id}`, { assignee_user_id: null, assignee_user_ids: [], due_date: date(0) });
    await clock(); assert.ok((await api('get', `/tasks/${dueTask.id}`)).assignee_user_ids.includes(due.assignee_id));
    report.checks.push('Rescheduled due date creates a fresh occurrence');
    await open(); await page.getByRole('article').filter({ hasText: dueName }).getByRole('button', { name: 'Edit', exact: true }).click({ timeout: 60000 });
    assert.equal(await page.getByLabel('Automation due offset', { exact: true }).inputValue(), '-1');
    assert.equal(await page.getByLabel('Automation timezone', { exact: true }).inputValue(), 'UTC');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: path.join(root, 'outputs/pms-clock-localhost-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []); report.checks.push('Saved schedule reloads and mobile layout fits'); report.passed = true;
  } finally {
    fs.writeFileSync(path.join(root, 'outputs/pms-clock-localhost-browser.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
  console.log(JSON.stringify(report));
})().catch(e => { console.error(e.message); process.exitCode = 1; });
