const { chromium, expect: baseExpect } = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { session } = require('./workflow_board_live_approval_records.cjs');
const state = JSON.parse(fs.readFileSync('.tmp/workflow-board-live-records.json', 'utf8'));
const expect = baseExpect.configure({ timeout: 90000 });
const origin = process.env.WORKFLOW_LIVE_ORIGIN || 'http://localhost:5125', output = path.resolve('docs/qa/workflow-board-live');
const previous = process.env.WORKFLOW_BRANCH_MODULES && fs.existsSync(path.join(output, 'branches.json')) ? JSON.parse(fs.readFileSync(path.join(output, 'branches.json'), 'utf8')) : {};
const report = { checks: previous.checks || [], failures: previous.failures || [], started: new Date().toISOString() };
const save = () => fs.writeFileSync(path.join(output, 'branches.json'), JSON.stringify(report, null, 2));
(async () => {
  const data = await session(state.qaActors.requester), browser = await chromium.launch({ headless: true });
  try {
    for (const [module, route] of [['crm', '/crm'], ['hrms', '/hrms'], ['pms', '/pms/overview'], ['srm', '/srm'], ['fam', '/fam'], ['power_apps', '/power-apps']]) {
      if (process.env.WORKFLOW_BRANCH_MODULES && !process.env.WORKFLOW_BRANCH_MODULES.split(',').includes(module)) continue;
      if (report.checks.length || report.failures.length) await new Promise(resolve => setTimeout(resolve, 45000));
      report.checks = report.checks.filter(check => check.module !== module);
      report.failures = report.failures.filter(failure => failure.module !== module);
      const context = await browser.newContext({ viewport: { width: 1480, height: 1050 } });
      await context.addInitScript(({ login, actor, access }) => {
        if (sessionStorage.getItem('hrms-auth')) return;
        sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', '6');
        sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: login.access_token, refreshToken: login.refresh_token, isAuthenticated: true, user: { ...actor, role: actor.role?.name || 'employee', access } }, version: 0 }));
      }, data);
      const page = await context.newPage();
      try {
        await page.goto(origin + route, { waitUntil: 'domcontentloaded' });
        const board = page.locator('.workflow-board').first();
        await expect(board.locator('.workflow-board-lanes')).toBeVisible();
        await expect(board.getByLabel('Current branch', { exact: true })).toHaveValue('6');
        const before = await board.locator('.workflow-board-caption').first().innerText();
        await board.getByLabel('Current branch', { exact: true }).selectOption('1');
        const confirmation = page.getByRole('dialog', { name: 'Switch branch?', exact: true });
        await expect(confirmation).toBeVisible();
        await Promise.all([page.waitForEvent('domcontentloaded'), confirmation.getByRole('button', { name: 'Switch branch', exact: true }).click()]);
        await expect(board.locator('.workflow-board-lanes')).toBeVisible();
        await expect(board.getByLabel('Current branch', { exact: true })).toHaveValue('1');
        assert.equal(await page.evaluate(() => sessionStorage.getItem('suite-branch')), '1');
        await expect(board.getByRole('button', { name: 'Change stage', exact: true })).toHaveCount(0);
        const after = await board.locator('.workflow-board-caption').first().innerText();
        report.checks.push({ module, before, after, persistedBranch: 1, readOnlyStageControlsHidden: true });
        await page.screenshot({ path: path.join(output, module + '-read-only-branch.png'), fullPage: false });
        console.log('PASS', module, 'branch switch and read-only stage controls');
      } catch (error) { report.failures.push({ module, error: error.message }); console.log('FAIL', module, error.message.split('\n').slice(0, 4).join(' ')); await page.screenshot({ path: path.join(output, module + '-branch-failure.png'), fullPage: false }); }
      await context.close(); save();
    }
    assert.deepEqual(report.failures, [], 'All requested branch checks must pass');
  } finally { await browser.close(); save(); }
})().catch(error => { console.error(error.message); save(); process.exitCode = 1; });
