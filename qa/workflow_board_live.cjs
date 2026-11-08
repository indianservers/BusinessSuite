// Full running app and actual local APIs. No request interception or mocked data.
const { chromium, expect: baseExpect } = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { auth } = require('./custom_fields_live.cjs');
const expect = baseExpect.configure({ timeout: 90000 });
const origin = process.env.WORKFLOW_LIVE_ORIGIN || 'http://localhost:5125';
const output = path.resolve('docs/qa/workflow-board-live');
fs.mkdirSync(output, { recursive: true });
const report = { origin, started: new Date().toISOString(), pages: [], checks: [], issues: [] };
const save = () => fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(report, null, 2));
const all = value => Array.isArray(value) ? value : value.items || [];
const ts = require('../frontend/node_modules/typescript'), vm = require('node:vm');
function compile(name, imports = {}) {
  const file = path.resolve('frontend/src/shared/workflow-board', name + '.ts');
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const module = { exports: {} }; vm.runInNewContext(code, { exports: module.exports, require: name => imports[name], Date, Intl, Map, Set, Number, String, Object, Array }); return module.exports;
}
async function run() {
  const authData = process.env.WORKFLOW_LIVE_QA_ACTOR === '1'
    ? await require('./workflow_board_live_approval_records.cjs').session(JSON.parse(fs.readFileSync('.tmp/workflow-board-live-records.json', 'utf8')).qaActors.requester)
    : await auth();
  const live = { get: async (url, config = {}) => ({ data: await authData.api(url + (config.params ? '?' + new URLSearchParams(Object.entries(config.params).filter(([, v]) => v !== undefined)) : '')) }) };
  const model = compile('model'), adapters = compile('adapters', { '@/services/api': { api: live }, './model': model });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1480, height: 1000 } });
  await context.addInitScript(({ login, actor, access }) => {
    if (!sessionStorage.getItem('hrms-auth')) {
      sessionStorage.setItem('suite-organization', '1'); sessionStorage.setItem('suite-branch', '6');
      sessionStorage.setItem('hrms-auth', JSON.stringify({ state: { accessToken: login.access_token, refreshToken: login.refresh_token, isAuthenticated: true, user: { ...actor, role: actor.role?.name || 'admin', access } }, version: 0 }));
    }
  }, authData);
  const page = await context.newPage();
  const pending = new Map();
  page.on('request', request => { if (!request.url().includes('/realtime')) pending.set(request, { url: new URL(request.url()).pathname, type: request.resourceType() }); });
  page.on('requestfinished', request => pending.delete(request));
  page.on('requestfailed', request => pending.delete(request));
  let current;
  page.on('pageerror', e => current?.errors.push(e.message));
  page.on('response', response => { if (current && response.url().includes('/api/')) current.network.push({ path: new URL(response.url()).pathname, status: response.status() }); });
  const navigate = async route => { await page.goto(origin + route, { waitUntil: 'domcontentloaded' }); };
  try {
    const modules = process.env.WORKFLOW_LIVE_MODULES?.split(',');
    for (const [module, route] of [['crm', '/crm'], ['hrms', '/hrms'], ['pms', '/pms/overview'], ['srm', '/srm'], ['fam', '/fam'], ['power_apps', '/power-apps']].filter(([module]) => !modules || modules.includes(module))) {
      if (report.pages.length) await page.waitForTimeout(45000); // Respect the running app's normal actor request budget.
      current = { module, route, checks: [], errors: [], network: [] }; report.pages.push(current); save();
      try {
        await navigate(route);
        const board = page.locator('.workflow-board').first();
        await expect(board).toBeVisible();
        await expect(board.locator('.workflow-board-lanes')).toBeVisible();
        // Inspect the actual React Query result received by this full-app page.
        // This avoids a second sweep of the live dataset while testing the UI.
        const data = await page.evaluate(module => {
          const root = document.getElementById('root');
          const key = Object.keys(root).find(key => key.startsWith('__reactContainer'));
          let client;
          function visit(fiber) { if (!fiber || client) return; if (fiber.type?.name === 'QueryClientProvider') client = fiber.memoizedProps.client; visit(fiber.child); visit(fiber.sibling); }
          visit(root[key].stateNode.current);
          return client?.getQueryCache().getAll().find(q => q.queryKey[0] === 'dashboard-workflow' && q.queryKey[1] === module)?.state.data;
        }, module);
        assert(data, 'Actual dashboard query must contain live API data');
        current.apiRecords = data.records.length;
        await expect(board.locator('.workflow-board-caption').first()).toContainText(`of ${data.records.length} loaded records`);
        current.checks.push('Dashboard board renders actual API records');
        const total = async () => (await board.locator('.workflow-board-stage b').allTextContents()).reduce((n, v) => n + Number(v), 0);
        assert.equal(await total(), data.records.length);
        for (const [name, field] of [['Team', 'teams'], ['Owner', 'owners']]) {
          const options = model.workflowFacets(data.records, field);
          const value = options[0]?.id || '__unassigned';
          await board.getByLabel(name, { exact: true }).selectOption(value);
          const filters = { ...model.emptyWorkflowFilters, [name.toLowerCase()]: value };
          assert.equal(await total(), model.filterWorkflowRecords(data.records, filters).length);
          await board.getByRole('button', { name: 'Clear filters', exact: true }).click();
          current.checks.push(name + ' filter matches real assignments');
        }
        const dated = data.records.find(r => r.date);
        const date = dated ? model.localDay(new Date(/^\d{4}-\d{2}-\d{2}$/.test(dated.date) ? dated.date + 'T12:00:00' : dated.date)) : '2099-01-01';
        await board.getByLabel(data.dateLabel + ' from', { exact: true }).fill(date);
        await board.getByLabel('To', { exact: true }).fill(date);
        assert.equal(await total(), model.filterWorkflowRecords(data.records, { ...model.emptyWorkflowFilters, from: date, to: date }).length);
        await board.getByRole('button', { name: 'Clear filters', exact: true }).click();
        current.checks.push('Date range is inclusive and excludes undated records');
        const firstStage = data.stages.find(s => data.records.some(r => r.stageId === s.id)) || data.stages[0];
        if (firstStage) {
          await board.getByRole('button', { name: 'View all ' + firstStage.name + ' records', exact: true }).click();
          await expect(page.getByRole('dialog').locator('.workflow-board-card')).toHaveCount(data.records.filter(r => r.stageId === firstStage.id).length);
          await page.keyboard.press('Escape');
          current.checks.push('Column drill-down opens the filtered list');
        }
        await page.screenshot({ path: path.join(output, module + '-desktop.png'), fullPage: false });
        await page.setViewportSize({ width: 390, height: 844 });
        current.mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        await page.screenshot({ path: path.join(output, module + '-mobile.png'), fullPage: false });
        await page.setViewportSize({ width: 1480, height: 1000 });
        const link = board.locator('.workflow-board-record').first();
        if (await link.count()) {
          current.recordHref = await link.getAttribute('href');
          current.recordTitle = await link.locator('strong').innerText();
          await link.click();
          await expect(page).toHaveURL(new RegExp(current.recordHref.split('?')[0].replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
          await expect(page.getByText(current.recordTitle, { exact: true }).first()).toBeVisible();
          current.checks.push('Card opens its actual record');
        } else current.checks.push('Empty real dataset: no record link available yet');
        if (current.errors.length) throw Error('Browser errors: ' + current.errors.join('; '));
        console.log(JSON.stringify({ module, records: current.apiRecords, checks: current.checks, href: current.recordHref, failedApi: current.network.filter(n => n.status >= 400), mobileOverflow: current.mobileOverflow }));
      } catch (error) {
        current.failure = error.message;
        current.pending = [...pending.values()];
        current.visibleText = (await page.locator('body').innerText()).slice(-1600);
        report.issues.push({ module, error: error.message });
        console.log('FAIL', module, error.message.split('\n').slice(0, 4).join(' '));
        await page.screenshot({ path: path.join(output, module + '-failure.png'), fullPage: false }).catch(() => {});
      }
      save();
    }
  } finally { await browser.close(); save(); }
}
run().catch(error => { console.error(error.message); save(); process.exitCode = 1; });
