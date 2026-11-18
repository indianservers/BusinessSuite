const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.HRMS_QA_URL || 'http://127.0.0.1:5198';
const html = `<html><meta charset="utf-8"><body><div id="root"></div><script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>(type)=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/hrms-workspaces-harness.tsx');</script></body></html>`;
(async () => {
  const browser = await chromium.launch();
  fs.mkdirSync('../.tmp/hrms-workspaces', { recursive: true });
  try {
    for (const width of [1440, 390]) for (const screen of ['team', 'assets', 'expenses', 'payroll', 'reports']) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      let reviewed = false, returned = false, assigned = false, paid = false, runStatus = 'calculated', batch = false, schedule = false, scheduleStatus = 'Active', follow = false, complete = false;
      let latestSearch = '';
      await page.route('**/hrms-qa?*', route => route.fulfill({ contentType: 'text/html', body: html }));
      await page.route('**/api/v1/**', async route => {
        const req = route.request(), url = new URL(req.url()), path = url.pathname.replace('/api/v1', '');
        const body = req.method() === 'GET' ? {} : req.postDataJSON() || {};
        const json = value => route.fulfill({ json: value });
        if (path === '/reports/my-team') return json({ team: [{ id: 150, name: 'Zebra Findable', employee_code: 'EMP-150', status: 'Active' }], decisions: reviewed ? [] : [{ id: 1, kind: 'expense', employee_id: 150, employee_name: 'Zebra Findable', title: 'Travel: 1000 INR', created_at: '2026-10-28', can_decide: true }], followups: follow ? [{ id: 5, employee_name: 'Zebra Findable', title: 'Review equipment handover', due_date: '2026-11-01', status: complete ? 'Completed' : 'Open' }] : [] });
        if (path === '/reports/my-team/availability') return json({ offset: 3, days: [{ date: '2026-10-28', leaves: [], holidays: [] }], today: [], moments: [], probation_due: [] });
        if (path.includes('/decisions/')) { assert.equal(body.remarks, 'Receipt checked'); reviewed = true; return json({}); }
        if (path === '/reports/my-team/followups') { follow = true; return json({ id: 5 }); }
        if (path.includes('/followups/5/complete')) { complete = true; return json({}); }
        if (path === '/assets/capabilities') return json({ can_manage: true });
        if (path === '/assets/categories') return json([{ id: 1, name: 'Bike' }, { id: 2, name: 'Laptop' }]);
        if (path === '/assets/employees' || path === '/expenses/employees') { latestSearch = url.searchParams.get('search'); return json([{ id: 150, name: 'Zebra Findable', employee_code: 'EMP-150' }, { id: 7, name: 'My Employee', employee_code: 'EMP-7' }]); }
        if (path === '/assets/') return json([{ id: 1, name: 'Honda company bike', asset_tag: 'BIKE-001', serial_number: 'TS09AB1234', status: returned ? 'Under Repair' : assigned ? 'Assigned' : 'Available', category_id: 1 }].filter(a => !url.searchParams.get('status') || a.status === url.searchParams.get('status')));
        if (path === '/assets/assignments' && req.method() === 'POST') { assert.equal(body.employee_id, 150); assigned = true; return json({ id: 2 }); }
        if (path === '/assets/assignments') { const active = url.searchParams.get('active') !== 'false'; return json(assigned && (active ? !returned : returned) ? [{ id: 2, asset_name: 'Honda company bike', asset_tag: 'BIKE-001', employee_id: 150, employee_name: 'Zebra Findable', assigned_date: '2026-10-28', returned_date: returned ? '2026-10-28' : null, acknowledged: false, condition_at_return: returned ? 'Damaged' : null }] : []); }
        if (path.endsWith('/2/return')) { assert.equal(url.searchParams.get('condition_at_return'), 'Damaged'); returned = true; return json({}); }
        if (path === '/assets/exit-clearance') return json([{ exit_id: 1, employee_name: 'Zebra Findable', last_working_date: '2026-10-31', cleared: returned, outstanding_assets: returned ? [] : [{ assignment_id: 2, name: 'Honda company bike', asset_tag: 'BIKE-001' }] }]);
        if (path.startsWith('/expenses/statements/')) return json({ employee_id: 7, employee_name: 'My Employee', can_submit: false, can_manager_review: true, can_finance_review: true, totals: [{ currency: 'INR', claimed: '1000.25', approved: '900.50', outstanding: '900.50', paid: '0', pending_review: '99.75', rejected: '0' }, { currency: 'USD', claimed: '10.25', approved: '10.25', outstanding: '0', paid: '10.25', pending_review: '0', rejected: '0' }], claims: [{ id: 1, claim_number: 'EXP-ONE', claim_type: 'Travel', expense_date: '2026-10-20', amount: '1000.25', approved_amount: '900.50', currency: 'INR', status: 'finance_approved', payroll_run_id: 9, payroll_reimbursement_id: 1, reimbursed_at: null, reimbursement_reference: null, remarks: 'Receipt verified', receipt_url: null }] });
        if (path === '/payroll/runs') return json([{ id: 9, month: 10, year: 2026, status: runStatus }]);
        if (path.endsWith('/9/variance')) return json([{ id: 1, employee_id: 7, previous_net: 90, current_net: 100, net_delta_percent: 11.11, severity: 'Medium' }]);
        if (path.endsWith('/9/guided') && req.method() === 'GET') return json({ id: 9, status: runStatus, reviewed, blocked: false, can_process: true, can_approve: true, issues: [], blockers: [], records: [{ id: 1, employee_id: 7, employee_name: 'My Employee', gross: '110', deductions: '10', net: '100' }], batches: batch ? [{ id: 3, status: paid ? 'Paid' : 'Generated', total: '100', file_url: '/uploads/test.csv', lines: [{ employee_id: 7, payroll_record_id: 1, status: paid ? 'Paid' : 'Pending', utr: paid ? 'BANK-001' : null, failure_reason: null }] }] : [] });
        if (path.endsWith('/9/guided')) { if (body.action === 'review') reviewed = true; if (body.action === 'approve') runStatus = 'approved'; if (body.action === 'lock') runStatus = 'locked'; if (body.action === 'pay') batch = true; if (body.action === 'reconcile') { assert(paid); runStatus = 'paid'; } return json({}); }
        if (path.endsWith('/3/status-import')) { assert.equal(body.lines[0].utr_number, 'BANK-001'); paid = true; return json({ updated: 1 }); }
        if (path === '/reports/definitions') return json([{ id: 1, name: 'People report' }]);
        if (path === '/reports/schedule-capabilities') return json({ can_manage: true });
        if (path === '/reports/schedules' && req.method() === 'POST') { assert.equal(body.cron_expression, '0 9 * * 1'); schedule = true; return json({ id: 1 }); }
        if (path === '/reports/schedules') return json(schedule ? [{ id: 1, name: 'Weekly people review', status: scheduleStatus, recipients_json: ['qa@example.com'], next_run_at: '2026-11-02T03:30:00Z', last_run_at: null, created_by: 1 }] : []);
        if (path.endsWith('/1/status')) { scheduleStatus = body.status; return json({}); }
        if (path.endsWith('/1/deliveries')) return json([{ id: 1, recipient: 'qa@example.com', status: 'queued', attempts: 0, error: null }]);
        return json([]);
      });
      await page.goto(`${base}/hrms-qa?screen=${screen}`);
      if (screen === 'team') {
        await page.getByRole('button', { name: 'Review request', exact: true }).click();
        await page.getByLabel('Decision reason').fill('Receipt checked');
        await page.getByRole('button', { name: 'Save decision' }).click();
        await page.getByText('No matching pending requests.').waitFor();
        await page.getByLabel('Team member').selectOption('150');
        await page.getByLabel('Follow-up task').fill('Review equipment handover');
        await page.getByLabel('Due date').fill('2026-11-01');
        await page.getByRole('button', { name: 'Add follow-up' }).click();
        await page.getByRole('button', { name: 'Mark complete' }).click();
        await page.getByText('No open follow-ups.').waitFor();
      } else if (screen === 'assets') {
        await page.getByLabel('Search employee', { exact: true }).fill('Zebra');
        await page.waitForResponse(r => r.url().includes('/assets/employees?search=Zebra'));
        await page.getByLabel('Employee', { exact: true }).selectOption('150');
        await page.getByLabel('Available asset').selectOption('1');
        await page.getByRole('button', { name: 'Assign asset', exact: true }).click();
        await page.getByRole('button', { name: 'Employee custody', exact: true }).click();
        await page.getByRole('button', { name: 'Record return' }).waitFor();
        await page.getByLabel('Return condition for BIKE-001').selectOption('Damaged');
        await page.getByRole('button', { name: 'Record return' }).click();
        await page.getByText('No assigned assets.').waitFor();
        await page.getByRole('button', { name: 'Exit clearance', exact: true }).click();
        await page.getByText('Assets cleared', { exact: true }).waitFor();
        assert.equal(latestSearch, 'Zebra');
      } else if (screen === 'expenses') {
        await page.getByText('EXP-ONE', { exact: false }).first().waitFor();
        assert(await page.getByText('₹900.50', { exact: true }).count() >= 1);
        assert(await page.getByText('$10.25', { exact: true }).count() >= 1);
        assert.equal(await page.getByRole('button', { name: 'Record payment' }).count(), 0, 'Payroll-linked claims cannot be paid twice');
      } else if (screen === 'payroll') {
        await page.getByRole('button', { name: '2. Review changes' }).click();
        await page.getByLabel('Payroll action notes', { exact: false }).fill('Reviewed payroll changes');
        await page.getByLabel('I reviewed calculations and changes for this run.').check();
        await page.getByRole('button', { name: 'Save reviewed changes' }).click();
        await page.getByRole('button', { name: 'Approve payroll', exact: true }).click();
        await page.getByRole('button', { name: 'Lock approved payroll' }).click();
        await page.getByRole('button', { name: 'Prepare payment file' }).click();
        await page.getByLabel('Bank reference or failure reason for 7').fill('BANK-001');
        await page.getByRole('button', { name: 'Save bank results' }).click();
        await page.getByRole('button', { name: 'Reconcile & close payroll' }).click();
        await page.getByText('Payments reconciled', { exact: true }).waitFor();
      } else {
        await page.getByLabel('Saved report', { exact: true }).selectOption('1');
        await page.getByLabel('Schedule name').fill('Weekly people review');
        await page.getByRole('button', { name: 'Create report schedule' }).click();
        await page.getByRole('button', { name: 'Pause schedule' }).click();
        await page.getByText('Paused', { exact: true }).waitFor();
        await page.getByRole('button', { name: 'View delivery audit' }).click();
        await page.getByText('qa@example.com · queued · 0 attempts', { exact: true }).waitFor();
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${screen} horizontal overflow at ${width}`);
      assert.deepEqual(errors, []);
      await page.screenshot({ path: `../.tmp/hrms-workspaces/${screen}-${width}.png`, fullPage: true });
      await page.close(); console.log(`PASS ${screen} ${width}px`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
