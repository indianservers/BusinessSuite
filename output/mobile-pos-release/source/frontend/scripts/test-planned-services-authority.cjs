const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium, expect} = require('playwright/test');

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const {createServer} = await import('vite');
  const server = await createServer({server: {host: '127.0.0.1', port: 0, hmr: false, watch: null}});
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      let gate = null, held = 0, revision = 1, writes = 0, revoked = false;
      const errors = [];
      page.on('pageerror', error => {errors.push(error.message); console.error(error.message);});
      await page.route('**/api/v1/**', async route => {
        const req = route.request(), pathname = new URL(req.url()).pathname;
        if (req.method() !== 'GET') writes++;
        if (revoked) return route.fulfill({status: 403, json: {detail: 'Current schedule access denied'}});
        if (pathname.endsWith('/directory')) {
          const data = {items: [{id: 900, full_name: 'DIRECTORY-' + revision, employee_id: 'QA-900'}], total: 1};
          if (gate) {held++; await gate;}
          return route.fulfill({json: data});
        }
        if (pathname.endsWith('/planned-services')) {
          const employee = Number(pathname.split('/').at(-2));
          const data = {employee_id: employee, timezone: 'Asia/Kolkata', next_cursor: null, items: [{appointment_id: 1, revision, service_id: 1, service_name: 'BOOKING-' + employee + '-' + revision, starts_at: '2026-11-15T09:00:00Z', ends_at: '2026-11-15T09:30:00Z', planned_minutes: 30, status: 'booked', blocks_availability: true}]};
          if (gate) {held++; await gate;}
          return route.fulfill({json: data});
        }
        return route.fulfill({json: {items: [], total: 0}});
      });
      await page.route('**/planned-services-authority-qa', route => route.fulfill({contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/planned-services-authority.tsx");</script>'}));
      await page.goto('http://127.0.0.1:' + server.httpServer.address().port + '/planned-services-authority-qa');
      await expect(page.getByText('BOOKING-900-1', {exact: true})).toBeVisible({timeout: 30000});
      await expect(page.getByRole('option', {name: 'DIRECTORY-1 (QA-900)'})).toHaveCount(1);
      for (const employee of [901, 900]) {
        revision++;
        let release;
        gate = new Promise(resolve => {release = resolve;}); held = 0;
        await page.evaluate(id => window.plannedServiceAuthority(id), employee);
        await expect.poll(() => held).toBeGreaterThanOrEqual(2);
        await expect(page.getByText(/^BOOKING-/, {exact: false})).toHaveCount(0);
        await expect(page.getByRole('option', {name: /^DIRECTORY-/})).toHaveCount(0);
        release(); gate = null;
        await expect(page.getByText('BOOKING-' + employee + '-' + revision, {exact: true})).toBeVisible();
      }
      revoked = true;
      await page.evaluate(() => window.refreshPlannedServices());
      await expect(page.getByText('Current schedule access denied', {exact: true})).toBeVisible();
      await expect(page.getByText(/^BOOKING-/, {exact: false})).toHaveCount(0);
      await expect(page.getByRole('option', {name: /^DIRECTORY-/})).toHaveCount(0);
      assert.equal(writes, 0, 'Viewing planned services must never create actual timesheets');
      assert.deepEqual(errors, []);
      const overflow = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth, elements: Array.from(document.querySelectorAll('*')).filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(-10).map(el => [el.tagName, el.className, el.getBoundingClientRect().width])}));
      assert.ok(overflow.scroll <= width + 1, JSON.stringify(overflow));
      await page.close();
    }
    console.log('PASS planned-service profile/timesheet component: employee relink and restored authority await fresh schedule/directory, no writes, desktop/mobile fit');
  } finally {await browser.close(); await server.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
