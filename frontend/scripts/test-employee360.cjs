// Isolated browser acceptance checks against Vite: real component, controlled API data.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const data = {
  employee_id: 7, as_of: '2026-10-28', currency: 'INR', access: { payroll: true, assets: true, expenses: true, profile_changes: true },
  salary: { id: 1, ctc: '600000', effective_from: '2026-01-01', effective_to: null, payroll_type: 'monthly_fixed' },
  salary_history: [], increments: [{ id: 3, current_ctc: '600000', proposed_ctc: '660000', effective_from: '2026-11-01', status: 'Pending', reason: 'Annual review' }],
  assets: [{ id: 2, name: 'Work laptop', asset_tag: 'LT-007', serial_number: 'SN-007', assigned_date: '2026-01-01', condition: 'Good', acknowledged: false }],
  expenses: [{ id: 1, claim_number: 'EXP-ONE', claim_type: 'Travel', expense_date: '2026-10-20', amount: '1000', approved_amount: '900', currency: 'INR', status: 'finance_approved', reimbursed_at: null, payment_reference: null, payroll_run_id: 9 }, { id: 2, claim_number: 'EXP-TWO', claim_type: 'Travel', expense_date: '2026-10-20', amount: '20', approved_amount: '0', currency: 'USD', status: 'submitted', reimbursed_at: null, payment_reference: null, payroll_run_id: null }],
  pending_actions: [{ id: 'asset-2', title: 'Acknowledge Work laptop', section: 'assets', owner: 'Employee' }],
};
(async () => {
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = []; page.on('pageerror', e => { errors.push(e.message); console.error(e.message); });
      page.on('console', message => { if (message.type() === 'error') console.error(message.text()); });
      let restricted = false, fail = false;
      const state = structuredClone(data);
      await page.route('**/api/v1/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith('/acknowledge')) { state.assets[0].acknowledged = true; state.pending_actions = []; return route.fulfill({ json: {} }); }
        if (url.pathname.endsWith('/360')) {
          if (fail) return route.fulfill({ status: 500, json: { detail: 'Unavailable' } });
          return route.fulfill({ json: restricted ? { ...state, access: { payroll: false, assets: false, expenses: false, profile_changes: false }, salary: null, increments: [], assets: [], expenses: [], pending_actions: [] } : state });
        }
        return route.fulfill({ json: [] });
      });
      await page.route('**/employee360-qa', route => route.fulfill({ contentType: 'text/html', body: `<html><meta charset="utf-8"><body><div id="root"></div><script type="module">
        import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => (type) => type; window.__vite_plugin_react_preamble_installed__ = true;
        await import('/scripts/employee360-harness.tsx');
      </script></body></html>` }));
      await page.goto('http://127.0.0.1:5198/employee360-qa');
      await page.getByRole('heading', { name: 'Employee 360', exact: true }).waitFor();
      await page.getByText('EXP-ONE', { exact: true }).waitFor();
      fs.mkdirSync('../.tmp/employee360', { recursive: true });
      await page.screenshot({ path: `../.tmp/employee360/initial-${width}.png`, fullPage: true });
      await page.getByRole('button', { name: 'View details' }).click();
      assert.equal(await page.evaluate(() => document.activeElement.id), 'employee-7-assets');
      await page.getByRole('button', { name: 'Acknowledge receipt' }).click();
      await page.getByText('Acknowledged', { exact: true }).waitFor();
      await page.getByLabel('Claim status').selectOption('submitted');
      assert.equal(await page.getByText('EXP-ONE', { exact: true }).count(), 0);
      await page.getByText('EXP-TWO', { exact: true }).waitFor();
      await page.getByRole('button', { name: 'Open salary setup' }).click();
      assert.equal(await page.evaluate(() => window.openedTab), 'payroll');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
      fs.mkdirSync('../.tmp/employee360', { recursive: true });
      await page.screenshot({ path: `../.tmp/employee360/overview-${width}.png`, fullPage: true });
      restricted = true;
      await page.getByRole('button', { name: 'Refresh overview' }).click();
      await page.getByText('This section is restricted by your access permissions.').first().waitFor();
      assert.equal(await page.getByText('Annual review', { exact: true }).count(), 0);
      fail = true;
      await page.reload();
      await page.getByRole('button', { name: 'Try again' }).waitFor();
      fail = false;
      await page.getByRole('button', { name: 'Try again' }).click();
      await page.getByRole('heading', { name: 'Employee 360', exact: true }).waitFor();
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`PASS ${width}px: context, acknowledgement, status filter, navigation, access, retry, overflow`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
