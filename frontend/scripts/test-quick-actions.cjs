// Run against the local Vite server: node scripts/test-quick-actions.cjs
const { chromium, expect } = require('playwright/test');
(async () => {
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      const errors = [], writes = [];
      let status = 'To Do', blocked = false, editable = true, denied = false, approved = false;
      page.on('pageerror', e => {errors.push(e.message); console.error(e.message);});
      await page.route('**/api/v1/**', async route => {
        const req = route.request(), p = new URL(req.url()).pathname;
        if (req.method() !== 'GET') {
          const body = req.postDataJSON(); writes.push({p, body});
          if (p.endsWith('/decisions')) {
            if (denied) return route.fulfill({status: 403, json: {detail: 'Decision permission revoked'}});
            approved = true;
          }
          if (p.endsWith('/approvals/decide')) return route.fulfill({json: {results: [{key: 'leave:1', ok: true}]}});
          if (body.status) status = body.status;
          return route.fulfill({json: {}});
        }
        let data = {};
        if (p.endsWith('/employees/workbench/home')) data = {pending_counts: {}, counts: {}, upcoming: []};
        if (p.endsWith('/employees/workbench/approvals')) data = {counts: {leave: 1}, items: [{key: 'leave:1', employee: {name:'Test employee', employee_code:'E1'}, kind:'leave', status:'Pending', description:'Annual leave', approval_path:[], can_decide:true, url:'/hrms/leave'}]};
        if (p.endsWith('/management/tasks/7')) data = {id: 7, title: 'Test task', project_id: 2, status, can_edit: editable, execution: {revision: 1, blocked_reason: '', responsible_user_id: null, review_date: null, evidence_required: false, evidence: ''}, completion: {checklist: [], subtasks: [], blockers: blocked ? ['Evidence required'] : []}, note_sources: []};
        if (p.endsWith('/approvals/requests')) data = {items: approved ? [] : [{id: 8, title: 'Travel expense', description: 'Train fare', status: 'Pending', priority: 'Normal', created_at: new Date().toISOString()}], total: approved ? 0 : 1};
        if (p.endsWith('/approvals/requests/8')) data = {id: 8, description: 'Train fare', state: {revision: 3, fields: {amount: 500}}, assignments: [{id: 9, can_decide: true}]};
        if (p.endsWith('/people-management/options')) data = {workspaces: [{id: 2, name: 'Operations'}], projects: [{id: 3, name: 'Launch', workspace_id: 2}]};
        if (p.endsWith('/employees/workbench/people/7')) data = {user_id: 1, permissions: {edit: true}, scope: {company: 'Company', branch: 'Branch', department: 'Engineering'}, completion: [], timeline: []};
        if (p.endsWith('/lifecycle-checklist')) data = {joiner: [], offboarding: []};
        if (p.endsWith('/onboarding-templates')) data = {items: []};
        if (p.endsWith('/people-management/1')) data = {id: 1, name: 'Test employee', status: 'active', email: 'test@example.com', workspaces: [], projects: [], permissions: {memberships: true}};
        if (p.endsWith('/leads/7')) data = {id: 7, version: 'v1', activities: []};
        return route.fulfill({json: data});
      });
      await page.route('**/quick-actions-qa?**', route => route.fulfill({contentType: 'text/html', body: `<html><body><div id="root"></div><script type="module">import R from '/@react-refresh'; R.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>(type)=>type; window.__vite_plugin_react_preamble_installed__=true; await import('/scripts/quick-actions-harness.tsx');</script></body></html>`}));
      const open = screen => page.goto(`http://127.0.0.1:5198/quick-actions-qa?screen=${screen}`);
      await open('task');
      await page.getByRole('button', {name: 'Start task', exact: true}).click();
      await expect(page.getByRole('status').filter({hasText: 'Task started'})).toBeVisible();
      await page.getByRole('button', {name: 'Complete task', exact: true}).click();
      await expect(page.getByText('Task completed', {exact: true})).toBeVisible();
      status = 'To Do'; blocked = true; await open('task');
      await expect(page.getByRole('button', {name: 'Complete task', exact: true})).toBeDisabled();
      editable = false; await open('task');
      await expect(page.getByRole('group', {name: 'Quick task updates'})).toHaveCount(0);
      await open('hr');
      const toolbar = page.getByRole('group', {name: 'Employee management actions', exact: true});
      await expect(toolbar.getByRole('button')).toHaveCount(4);
      await toolbar.getByRole('button', {name: 'Add to project / workspace', exact: true}).click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await page.getByRole('button', {name: 'Project', exact: true}).click();
      await page.getByLabel('Assignment destination', {exact: true}).selectOption('3');
      await page.getByRole('button', {name: 'Assign', exact: true}).click();
      await expect.poll(() => writes.some(w => w.body.project_ids?.includes(3) && w.body.user_ids?.includes(1))).toBe(true);
      await open('approvals');
      await page.getByRole('button', {name: 'Review & decide'}).click();
      await expect(page.getByRole('button', {name: 'Reject', exact: true})).toBeDisabled();
      denied = true;
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await expect(page.getByRole('alert')).toContainText('Decision permission revoked');
      denied = false;
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await expect(page.getByText('Your queue is clear')).toBeVisible();
      const decision = writes.find(w => w.p.endsWith('/decisions')).body;
      expect(decision.expected_revision).toBe(3); expect(decision.assignment_id).toBe(9);
      await open('crm');
      await expect(page.getByLabel('Follow-up type', {exact: true})).toBeHidden();
      await page.getByRole('button', {name: 'Tomorrow', exact: true}).click();
      await page.getByRole('button', {name: 'Save follow-up', exact: true}).click();
      await expect.poll(() => writes.some(w => w.body.title === 'Follow up with Test customer' && w.body.ownerId === 1)).toBe(true);
      await open('hr-review&view=approvals');
      await expect(page.getByLabel('Approval decision reason', {exact: true})).toHaveCount(0);
      await page.getByRole('button', {name:'Approve', exact:true}).click();
      await expect(page.getByRole('button', {name:'Confirm decision',exact:true})).toBeDisabled();
      await page.getByLabel('Individual approval reason').fill('Reviewed leave request');
      await page.getByRole('button', {name:'Confirm decision',exact:true}).click();
      await expect.poll(() => writes.some(w => w.body.keys?.[0] === 'leave:1' && w.body.reason === 'Reviewed leave request')).toBe(true);
      await expect(page.getByRole('dialog')).toHaveCount(0);
      expect(errors).toEqual([]);
      await page.close();
      console.log(`PASS ${width}px: quick task updates, completion gates, employee assignment dialog/payload, approval revision/access checks, simplified CRM scheduling`);
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
