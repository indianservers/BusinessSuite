// Stage actions in the full app, followed by independent reads from the real API.
const { chromium, expect: baseExpect } = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { session } = require('./workflow_board_live_approval_records.cjs');
const { auth } = require('./custom_fields_live.cjs');
const stateFile = '.tmp/workflow-board-live-records.json';
const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
const origin = process.env.WORKFLOW_LIVE_ORIGIN || 'http://localhost:5125';
const output = path.resolve('docs/qa/workflow-board-live');
const expect = baseExpect.configure({ timeout: 90000 });
const reportPath = path.join(output, 'stages.json');
const previous = fs.existsSync(reportPath) ? JSON.parse(fs.readFileSync(reportPath, 'utf8')) : {};
const report = { checks: previous.checks || [], failures: previous.failures || [], records: previous.records || {}, started: new Date().toISOString() };
const save = () => fs.writeFileSync(path.join(output, 'stages.json'), JSON.stringify(report, null, 2));
const pause = () => new Promise(resolve => setTimeout(resolve, 45000));
async function contextFor(browser, identity) {
  const data = identity ? await session(identity) : await auth();
  const context = await browser.newContext({ viewport: { width: 1480, height: 1050 } });
  await context.addInitScript(({ login, actor, access }) => {
    if (sessionStorage.getItem('hrms-auth')) return;
    sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', '6');
    sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: login.access_token, refreshToken: login.refresh_token, isAuthenticated: true, user: { ...actor, role: actor.role?.name || 'employee', access } }, version: 0 }));
  }, data);
  return { ...data, context, page: await context.newPage() };
}
async function run() {
  fs.mkdirSync(output, { recursive: true });
  const requested = (process.env.WORKFLOW_STAGE_MODULES || 'crm,hrms,pms,srm,power_apps,fam').split(',');
  const browser = await chromium.launch({ headless: true });
  try {
    const identity = await contextFor(browser, process.env.WORKFLOW_STAGE_ADMIN === '1' ? undefined : state.qaActors[process.env.WORKFLOW_STAGE_ACTOR || 'requester']);
    const { page, api } = identity;
    page.setDefaultTimeout(30000);
    let activePage = page;
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const go = async route => {
      await page.goto(origin + route, { waitUntil: 'domcontentloaded' });
      await expect(page.locator('.workflow-board-heading h2')).toHaveText(({ '/crm': 'Sales pipeline', '/hrms': 'Hiring pipeline', '/pms/overview': 'Work delivery pipeline', '/srm': 'Sales order pipeline', '/fam': 'Collections pipeline' })[route]);
      await expect(page.locator('.workflow-board-lanes').first()).toBeVisible();
    };
    const findCard = async record => {
      await page.locator('.workflow-board-heading').getByRole('button', { name: 'View all', exact: true }).click();
      const card = page.getByRole('dialog').locator('.workflow-board-card').filter({ has: page.getByText(record.title, { exact: true }) });
      await expect(card).toHaveCount(1); return card;
    };
    for (const module of requested) {
      console.log('Checking', module, origin);
      if (report.checks.length) await pause();
      report.checks = report.checks.filter(check => !check.startsWith(module + ':'));
      report.failures = report.failures.filter(failure => failure.module !== module);
      try {
        if (module === 'crm') {
          await go('/crm');
          const r = state.records.deal, card = await findCard(r);
          await card.getByRole('button', { name: 'Change stage', exact: true }).click();
          const review = page.getByRole('dialog', { name: 'Review deal stage move', exact: true });
          await review.getByLabel('Destination stage', { exact: true }).selectOption(String(r.targetStage));
          const required = review.locator('input[required]');
          for (let i = 0; i < await required.count(); i++) {
            const input = required.nth(i);
            if (!await input.inputValue()) {
              const type = await input.getAttribute('type');
              if (type === 'datetime-local') await input.fill('2026-12-01T12:00');
              else if (type === 'date') await input.fill('2026-12-01');
              else throw Error('Required deal field needs review: ' + await input.evaluate(el => el.closest('label')?.textContent));
            }
          }
          const response = page.waitForResponse(rsp => rsp.request().method() === 'POST' && rsp.url().includes(`/crm/productivity/deals/${r.id}/transition`));
          await review.getByRole('button', { name: 'Apply reviewed stage move', exact: true }).click();
          assert.equal((await response).status(), 200);
          assert.equal((await api(`/crm/deals/${r.id}`)).stage_id, r.targetStage);
          report.records.crm = { id: r.id, persistedStage: r.targetStage };
          await page.keyboard.press('Escape'); await go('/crm'); await findCard(r);
        } else if (module === 'hrms' || module === 'pms' || module === 'srm') {
          const r = state.records[module === 'hrms' ? 'candidate' : module === 'pms' ? 'task' : 'order'];
          await go(module === 'hrms' ? '/hrms' : module === 'pms' ? '/pms/overview' : '/srm');
          const card = await findCard(r);
          await card.getByRole('button', { name: 'Change stage', exact: true }).click();
          const review = page.getByRole('dialog', { name: 'Review stage change', exact: true });
          const target = module === 'hrms' ? 'Screening' : module === 'pms' ? ((await api('/project-management/tasks/' + r.id)).status === 'In Progress' ? 'In Review' : 'In Progress') : 'Submit for approval';
          await review.getByLabel('Destination stage', { exact: true }).selectOption(target);
          const requestPath = module === 'hrms' ? `/recruitment/candidates/${r.id}/status` : module === 'pms' ? `/project-management/tasks/${r.id}` : `/srm/sales-orders/${r.id}/submit`;
          const response = page.waitForResponse(rsp => rsp.request().method() !== 'GET' && new URL(rsp.url()).pathname.endsWith(requestPath), { timeout: 90000 });
          await review.getByRole('button', { name: 'Confirm stage change', exact: true }).click();
          assert.equal((await response).status(), 200);
          const record = await api(module === 'hrms' ? `/recruitment/candidates/${r.id}` : module === 'pms' ? `/project-management/tasks/${r.id}` : `/srm/sales-orders/${r.id}`);
          assert.equal(record.status, module === 'srm' ? 'approved' : target);
          report.records[module] = { id: r.id, persistedStage: record.status };
          if (module === 'srm') {
            await page.keyboard.press('Escape');
            await page.locator('.workflow-board-heading').getByRole('button', { name: 'View all', exact: true }).click();
            const refreshed = page.getByRole('dialog').locator('.workflow-board-card').filter({ has: page.getByText(r.title, { exact: true }) });
            await refreshed.getByRole('button', { name: 'Change stage', exact: true }).click();
            await page.getByRole('dialog', { name: 'Review stage change', exact: true }).getByLabel('Destination stage', { exact: true }).selectOption('Confirm order');
            const confirmed = page.waitForResponse(rsp => rsp.request().method() === 'POST' && rsp.url().includes(`/srm/sales-orders/${r.id}/confirm`));
            await page.getByRole('dialog', { name: 'Review stage change', exact: true }).getByRole('button', { name: 'Confirm stage change', exact: true }).click();
            assert.equal((await confirmed).status(), 200);
            assert.equal((await api(`/srm/sales-orders/${r.id}`)).status, 'confirmed');
            report.records.srm.persistedStage = 'confirmed';
          }
          await page.keyboard.press('Escape');
        } else if (module === 'power_apps') {
          const reviewer = await contextFor(browser, state.qaActors.reviewer), p = reviewer.page, r = state.records.approval;
          activePage = p;
          await p.goto(origin + '/power-apps', { waitUntil: 'domcontentloaded' });
          const board = p.locator('.workflow-board'); await expect(board.locator('.workflow-board-lanes')).toBeVisible();
          await expect(board.getByRole('button', { name: 'Change stage', exact: true })).toHaveCount(0);
          await board.locator('.workflow-board-record').filter({ has: p.getByText(r.title, { exact: true }) }).click();
          await expect(p.getByRole('heading', { name: r.title, exact: true })).toBeVisible();
          const detail = await reviewer.api(`/power-apps/approvals/requests/${r.id}?environment=development`);
          if (detail.status !== 'Approved') {
            const assignment = detail.assignments.find(a => a.can_decide); assert(assignment);
            await assert.rejects(() => api(`/power-apps/approvals/requests/${r.id}/decisions?environment=development`, 'POST', { assignment_id: assignment.id, expected_revision: detail.state.revision, decision: 'approve', reason: 'Self approval must be rejected', request_key: state.run + '-self-denied' }), /403/);
            await p.locator('.ap-decision textarea').fill('Verified dashboard approval routing with a separate assigned reviewer.');
            const approved = p.waitForResponse(rsp => rsp.request().method() === 'POST' && rsp.url().includes(`/requests/${r.id}/decisions`));
            await p.locator('.ap-decision').getByRole('button', { name: 'Approve', exact: true }).click();
            assert.equal((await approved).status(), 200);
          } else {
            assert(detail.history.some(h => h.event_type === 'approve' && h.actor_user_id === state.qaActors.reviewer.id), 'Prior UI decision must have the real reviewer evidence');
            assert.equal(detail.evidence_valid, true);
          }
          // The running legacy database has no continuously running queue worker.
          // Execute only this tagged run using the production worker functions.
          require('node:child_process').execFileSync(path.resolve('backend/venv/Scripts/python.exe'), [path.resolve('qa/process_workflow_board_approval.py')], { cwd: path.resolve('backend'), windowsHide: true, timeout: 60000, stdio: 'pipe' });
          assert.equal((await reviewer.api(`/power-apps/approvals/requests/${r.id}?environment=development`)).status, 'Approved');
          await p.goto(origin + '/power-apps');
          await expect(p.locator('.workflow-board-lane').filter({ has: p.getByRole('button', { name: /^View Approved:/ }) }).getByText(r.title, { exact: true })).toBeVisible();
          report.records.power_apps = { id: r.id, persistedStage: 'Approved', selfApprovalRejected: true };
          await p.screenshot({ path: path.join(output, 'power-apps-approved.png'), fullPage: false }); await reviewer.context.close();
        } else if (module === 'fam') {
          await go('/fam'); const board = page.locator('.workflow-board');
          assert.equal(await board.getByRole('button', { name: 'Change stage', exact: true }).count(), 0);
          for (const [index, name] of ['Upcoming', 'Due today', '1–30 days overdue', '31–60 days overdue', '60+ days overdue'].entries()) {
            const lane = board.getByRole('region', { name: name + ' stage', exact: true });
            await expect(lane.getByText(state.records.bills[index].title, { exact: true })).toBeVisible();
          }
          report.records.fam = { ageingBuckets: 5, manualMovesDisabled: true };
        }
        report.checks.push(module + ': live stage workflow verified');
        console.log('PASS', report.checks.at(-1));
        if (module !== 'power_apps') await page.screenshot({ path: path.join(output, module + '-stage.png'), fullPage: false });
      } catch (error) { report.failures.push({ module, error: error.message, visibleText: (await activePage.locator('body').innerText()).slice(-5000) }); console.log('FAIL', module, error.message.split('\n').slice(0, 4).join(' ')); await activePage.screenshot({ path: path.join(output, module + '-stage-failure.png'), fullPage: false }); }
      save();
    }
    report.pageErrors = errors; assert.deepEqual(errors, []);
    assert.deepEqual(report.failures, [], 'All requested live stage checks must pass');
  } finally { await browser.close(); save(); }
}
run().catch(error => { console.error(error.message); save(); process.exitCode = 1; });
