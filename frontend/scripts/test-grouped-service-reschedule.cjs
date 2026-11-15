const path = require('node:path');
const {chromium, expect} = require('playwright/test');
(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const {createServer} = await import('vite');
  const server = await createServer({server: {host: '127.0.0.1', port: 0, hmr: false, watch: null}});
  await server.listen();
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const booking = {policy_id: 4, expected_policy_revision: 2, eligibility_id: 5, expected_eligibility_revision: 3, provider_resource_id: 6, employee_id: 7, starts_at: '2030-12-20T15:00:00Z', duration_minutes: 30};
    const payloads = [];
    await page.route('**/srm/service-checkout/**', async route => {
      const request = route.request();
      if (request.url().includes('/options')) return route.fulfill({json: {policy: {id: 4, revision: 2, booking_required: true, default_duration_minutes: 30, min_duration_minutes: 5, max_duration_minutes: 120, allow_duration_override: true, active: true}, specialists: [{eligibility_id: 5, eligibility_revision: 3, provider_resource_id: 6, employee_id: 7, employee_name: 'QA Specialist', provider_name: 'QA Provider', timezone: 'America/New_York'}], has_more: false}});
      if (request.method() === 'GET') return route.fulfill({json: {service_id: 9, provider_timezone: 'America/New_York', appointment_id: 17, appointment_revision: 3, occurrence_id: 8, occurrence_revision: 4, booking, additional_resource_ids: []}});
      const payload = request.postDataJSON(); payloads.push(payload);
      if (payloads.length === 1) return route.fulfill({status: 409, json: {detail: 'Provider unavailable'}});
      return route.fulfill({json: {appointment: {id: 17, revision: 4}, schedule: {}}});
    });
    await page.route('**/grouped-service-reschedule-qa', route => route.fulfill({contentType: 'text/html', body: '<div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/grouped-service-reschedule.tsx");</script>'}));
    await page.goto('http://127.0.0.1:' + server.httpServer.address().port + '/grouped-service-reschedule-qa');
    await page.getByText('Reschedule', {exact: true}).click();
    await expect(page.getByLabel('Booking time reschedule-17')).toHaveValue('10:00');
    await expect(page.getByText(/^Current schedule:/)).toContainText('America/New_York');
    await page.getByLabel('Booking time reschedule-17').fill('14:30');
    await page.getByRole('button', {name: 'Use these booking details', exact: true}).click();
    await page.getByRole('button', {name: 'Save new schedule', exact: true}).click();
    await expect(page.getByRole('alert')).toContainText('Your draft is retained');
    await expect(page.getByLabel('Booking time reschedule-17')).toHaveValue('14:30');
    expect(payloads[0].booking.starts_at).toBe('2030-12-20T19:30:00.000Z');
    expect(payloads[0].expected_appointment_revision).toBe(3);
    expect(payloads[0].expected_occurrence_revision).toBe(4);
    await page.getByRole('button', {name: 'Reload current schedule', exact: true}).click();
    await expect(page.getByLabel('Booking time reschedule-17')).toHaveValue('10:00');
    await page.getByLabel('Booking time reschedule-17').fill('14:30');
    await page.getByRole('button', {name: 'Use these booking details', exact: true}).click();
    await page.getByRole('button', {name: 'Save new schedule', exact: true}).click();
    await expect(page.getByText('Saved revision 4')).toBeVisible();
    console.log('PASS grouped service reschedule: provider timezone, exact revisions, conflict draft retention and saved callback');
  } finally { await browser.close(); await server.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
