const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium, expect} = require('playwright/test');

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const {createServer} = await import('vite');
  const server = await createServer({cacheDir: path.resolve('../.local/schedule-recovery-vite'),
    optimizeDeps: {entries: ['scripts/fixtures/scheduled-services-recovery.tsx']},
    server: {host: '127.0.0.1', port: 0, hmr: false, watch: null}});
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      let denied = false, revision = 1, writes = 0;
      const errors = [];
      page.on('pageerror', error => { errors.push(error.message); console.error('Schedule browser error:', error.message); });
      await page.route('**/api/v1/**', async route => {
        if (route.request().method() !== 'GET') writes++;
        if (denied) return route.fulfill({status: 403, json: {detail: 'Schedule access revoked'}});
        const start = new Date(); start.setHours(10, 0, 0, 0);
        return route.fulfill({json: {company_id: 1, pack_context_id: null, timezone: 'UTC', next_cursor: null,
          filter_options: {employees: [{id: 1, name: 'Private specialist', code: 'QA'}], services: [{id: 2, name: 'Private service'}], employees_complete: true, services_complete: true},
          items: [{appointment_id: 3, revision, employee_id: 1, employee_name: 'Private specialist', employee_code: 'QA',
            service_id: 2, service_name: 'Private service ' + revision, starts_at: start.toISOString(), ends_at: new Date(+start + 30 * 60000).toISOString(),
            planned_minutes: 30, status: 'booked', blocks_availability: true}]}});
      });
      await page.route('**/scheduled-services-recovery-qa', route => route.fulfill({contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/scheduled-services-recovery.tsx");</script>'}));
      await page.goto('http://127.0.0.1:' + server.httpServer.address().port + '/scheduled-services-recovery-qa');
      await page.getByRole('button', {name: 'List', exact: true}).click();
      await expect(page.getByRole('button', {name: 'Private service 1', exact: true})).toBeVisible({timeout: 30000});
      await page.getByRole('button', {name: 'Filters', exact: true}).click();
      await expect(page.getByRole('option', {name: 'Private specialist (QA)'})).toHaveCount(1);
      await page.getByRole('combobox', {name: 'Employee', exact: true}).selectOption('1');
      await page.getByRole('combobox', {name: 'Service', exact: true}).selectOption('2');
      for (const mode of ['List', 'Calendar', 'Gantt']) {
        await page.getByRole('button', {name: mode === 'Gantt' ? 'Timeline' : mode, exact: true}).click();
        const booking = page.getByRole('button', {name: /Private service/}).first();
        await expect(booking).toBeVisible({timeout: 30000});
        await booking.click();
        await expect(page.getByRole('dialog')).toContainText('Private specialist');
        denied = true;
        await page.evaluate(() => window.refreshSchedule());
        await expect(page.getByRole('alert')).toContainText('Schedule access revoked');
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(page.getByRole('button', {name: /Private service/})).toHaveCount(0);
        await expect(page.getByRole('option', {name: /Private specialist|Private service/})).toHaveCount(0);
        denied = false; revision++;
        await page.getByRole('button', {name: 'Retry', exact: true}).click();
        await expect(page.getByRole('button', {name: new RegExp('Private service ' + revision)}).first()).toBeVisible();
      }
      assert.equal(writes, 0);
      assert.deepEqual(errors, []);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await page.screenshot({path: path.resolve('../.local/scheduled-services-' + width + '.png'), fullPage: true});
      await page.close();
    }
    console.log('PASS scheduled services: List/Calendar/Gantt, revoked read clears rows/options/dialog, retry restores fresh data, no writes, 1440/390px');
  } finally {await browser.close(); await server.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
