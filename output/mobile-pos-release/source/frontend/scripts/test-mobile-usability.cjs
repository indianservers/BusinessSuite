const { chromium, expect: baseExpect } = require('playwright/test');
const path = require('node:path'), fs = require('node:fs');
process.chdir(path.resolve(__dirname, '..'));
const expect = baseExpect.configure({ timeout: 15000 });
(async () => {
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  const output = path.resolve(__dirname, '../../outputs/mobile-usability'); fs.mkdirSync(output, { recursive: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } }), errors = [];
    page.on('pageerror', error => { errors.push(error.message); console.error('Browser error:', error.message); });
    await page.route('**/api/v1/**', route => {
      const p = new URL(route.request().url()).pathname;
      let data = {};
      if (p.endsWith('/project-management/workspaces')) data = [{ id: 1, name: 'Operations', role: 'Owner' }];
      if (p.endsWith('/project-management/projects')) data = [];
      if (p.endsWith('/project-management/users/search')) data = [];
      if (p.endsWith('/project-management/tasks')) data = { items: [{ id: 8, title: 'Prepare launch', status: 'Open' }], summary: { overdue: 2, in_review: 1 } };
      if (p.endsWith('/follow-ups/statistics')) data = { Overdue: 2 };
      if (p.endsWith('/follow-ups')) data = { items: [{ id: 9, title: 'Call customer', customer_name: 'Acme' }] };
      if (p.endsWith('/crm/lead-management/leads')) data = { items: [{ id: 42, full_name: 'Alex Morgan', company_name: 'Acme' }] };
      if (p.endsWith('/srm/sales-orders')) data = [{ id: 43, title: 'Alex order', order_number: 'SO-43' }];
      if (p.endsWith('/employees/workbench/search')) data = { items: [{ id: 44, name: 'Alex Employee', employee_code: 'E44' }] };
      if (p.endsWith('/branches/context')) data = { company_id: 1, selected: 1, all_branches: false, manage_access: false, branches: [{ id: 1, name: 'Current branch', code: 'MAIN', can_write: true }] };
      if (p.endsWith('/notifications/summary')) data = { groups: [{ module: 'crm', action_url: '/crm/leads/42', count: 1 }] };
      if (p.endsWith('/notifications/')) data = { items: [{ id: 1, title: 'Lead needs attention', message: 'Call Alex today', module: 'crm', action_url: '/crm/leads/42', is_read: false, created_at: new Date().toISOString() }], pages: 1 };
      if (/\/(company\/|company\/(branches|departments|designations|cost-centers)\/?|attendance\/shifts|employees\/reporting-managers)$/.test(p)) data = [];
      if (p.endsWith('/employees/custom-fields/definitions')) data = { items: [] };
      return route.fulfill({ json: data });
    });
    await page.route('**/qa-mobile-usability**', route => route.fulfill({ contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/mobile-usability.tsx");</script>' }));
    const url = `http://127.0.0.1:${server.httpServer.address().port}/qa-mobile-usability`;
    const open = query => page.goto(url + '?' + query, { waitUntil: 'domcontentloaded' });
    if (process.argv.includes('--native-only')) {
      for (const width of [320, 390]) {
        await page.setViewportSize({ width, height: 844 }); await open('route=/pms/tasks&screen=native');
        await page.getByRole('checkbox', { name: 'Select native request' }).check(); await expect(page.getByLabel('Native selection')).toHaveText('true');
        await page.getByText('Travel request', { exact: true }).click(); await expect(page.getByLabel('Native open')).toHaveText('true');
        await page.locator('.udg-card-native-actions>summary').click(); await page.getByRole('button', { name: 'Approve request', exact: true }).click(); await expect(page.getByLabel('Native approval')).toHaveText('true');
      }
      expect(errors).toEqual([]); console.log('PASS adapted mobile cards preserve native selection, row-opening and action handlers at 320/390px'); return;
    }
    if (process.argv.includes('--forms-only')) {
      await open('route=/hrms/employees/new&screen=employee');
      await page.evaluate(() => sessionStorage.setItem('suite-form-draft:v1:55:1::hrms-employee:new', JSON.stringify({ values: { first_name: 'Asha', last_name: 'Rao', date_of_joining: '2026-11-08', create_user_account: true, user_email: 'asha@example.test' }, customValues: {}, step: 4 })));
      await page.reload(); const password = page.locator('#employee-login-password'); await expect(password).toBeVisible(); await password.fill('DraftSecret123456');
      await expect.poll(() => page.evaluate(() => sessionStorage.getItem('suite-form-draft:v1:55:1::hrms-employee:new'))).not.toContain('DraftSecret123456');
      await page.reload(); await expect(password).toHaveValue('');
      expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('suite-form-draft:v1:55:1::hrms-employee:new')).values.first_name)).toBe('Asha');
      expect(errors).toEqual([]); console.log('PASS actual employee form: restored step and entered details, password excluded from session draft and empty after reload'); return;
    }
    if (!process.argv.includes('--grid-only')) {
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 });
      for (const [module, first] of [['crm', 'Add Lead'], ['pms', 'Task'], ['srm', 'Sales order'], ['hrms', 'Add Employee']]) {
        await open('route=/' + module + (module === 'pms' ? '/tasks' : ''));
        const add = page.getByRole('button', { name: 'Add new record', exact: true }); await add.click();
        const sheet = page.getByRole('dialog', { name: 'Create something new' }); await expect(sheet).toBeVisible();
        await expect(sheet.getByRole('button', { name: new RegExp(first) }).first()).toBeVisible();
        expect(await sheet.locator('.mobile-create-list>button').count()).toBeLessThanOrEqual(6);
        const all = sheet.getByRole('button', { name: /View all/ });
        if (await all.count()) { await all.click(); expect(await sheet.locator('.mobile-create-list>button').count()).toBeGreaterThan(6); }
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width === 390) await page.screenshot({ path: path.join(output, module + '-create.png') });
        await page.keyboard.press('Escape'); await expect(add).toBeFocused();
      }
    }
    await open('route=/crm&restricted=1'); await expect(page.getByRole('button', { name: 'Add new record', exact: true })).toHaveCount(0);
    await open('route=/pms/tasks'); await page.getByRole('button', { name: 'Workspace tools', exact: true }).click();
    await page.getByRole('button', { name: 'Today & recent work', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Today', exact: true })).toBeVisible(); await expect(page.getByText('Prepare launch', { exact: true })).toBeVisible();
    await page.keyboard.press('Escape');
    for (const module of ['crm', 'srm', 'hrms']) {
      await open('route=/' + module); await page.getByRole('button', { name: 'Workspace tools', exact: true }).click(); await page.getByRole('button', { name: 'Open search', exact: true }).click();
      await page.getByRole('combobox', { name: 'Search authorized applications and pages' }).fill('Alex');
      await page.getByRole('option', { name: module === 'crm' ? /Alex Morgan/ : module === 'srm' ? /Alex order/ : /Alex Employee/ }).click();
      await expect(page.getByLabel('Current route')).toHaveText(module === 'crm' ? '/crm/leads/42' : module === 'srm' ? '/srm/sales-orders/43' : '/hrms/employees/44');
    }
    await open('route=/crm'); await page.getByRole('button', { name: 'Workspace tools', exact: true }).click(); await page.getByRole('button', { name: 'Open search', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Alex', exact: true })).toBeVisible(); await page.keyboard.press('Escape'); await page.keyboard.press('Escape');
    await page.evaluate(() => window.dispatchEvent(new Event('offline'))); await expect(page.getByText('You’re offline', { exact: true })).toBeVisible();
    await page.evaluate(() => window.dispatchEvent(new Event('online'))); await expect(page.getByText('Back online', { exact: true })).toBeVisible(); await page.getByRole('button', { name: 'Dismiss connection status' }).click();
    await open('route=/pms/tasks&screen=draft'); await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Retained mobile draft'); await page.reload(); await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Retained mobile draft');
    await page.getByRole('combobox', { name: 'Employee', exact: true }).click(); const picker = page.locator('.suite-choice-menu'); await expect(picker).toBeVisible();
    const pickerBox = await picker.boundingBox(); expect(pickerBox.x).toBeLessThanOrEqual(1); expect(pickerBox.width).toBeGreaterThan(380);
    await page.getByRole('combobox', { name: 'Search Employee', exact: true }).fill('Employee 12'); await picker.getByRole('option', { name: 'Employee 12', exact: true }).click(); await expect(page.getByRole('combobox', { name: 'Employee', exact: true })).toHaveValue('11');
    await open('route=/crm&screen=notifications'); await expect(page.getByText('Lead needs attention', { exact: true })).toBeVisible(); await page.getByRole('button', { name: 'Snooze 1 hour' }).click(); await expect(page.getByText('Lead needs attention', { exact: true })).toHaveCount(0); await page.reload(); await expect(page.getByText('Lead needs attention', { exact: true })).toHaveCount(0); await page.getByRole('button', { name: 'Snoozed on this device' }).click(); await expect(page.getByText('Lead needs attention', { exact: true })).toBeVisible(); await page.getByRole('button', { name: 'Unsnooze', exact: true }).click(); await page.getByRole('button', { name: 'Show active updates' }).click(); await expect(page.getByText('Lead needs attention', { exact: true })).toBeVisible();
    }
    await open('route=/pms/tasks&screen=grid'); const grid = page.getByRole('region', { name: 'Your tasks', exact: true });
    await expect(grid.locator('.udg-view-cards>article')).toHaveCount(3);
    await grid.getByRole('button', { name: 'Mine', exact: true }).click(); await expect(grid.locator('.udg-view-cards>article')).toHaveCount(2); await grid.getByRole('button', { name: 'Mine', exact: true }).click();
    await grid.getByRole('button', { name: 'Overdue', exact: true }).click(); await expect(grid.locator('.udg-view-cards>article')).toHaveCount(1); await expect(grid.locator('.udg-record-field').filter({ hasText: 'Review proposal' })).toBeVisible(); await grid.getByRole('button', { name: 'Overdue', exact: true }).click();
    await grid.getByRole('button', { name: 'Due today', exact: true }).click(); await expect(grid.locator('.udg-view-cards>article')).toHaveCount(1); await grid.getByRole('button', { name: 'Due today', exact: true }).click();
    await grid.getByRole('button', { name: 'Mine', exact: true }).click(); await grid.getByRole('button', { name: 'Due today', exact: true }).click(); await expect(grid.locator('.udg-view-cards>article')).toHaveCount(1); await expect(grid.getByRole('button', { name: 'Mine', exact: true })).toHaveAttribute('aria-pressed', 'true'); await grid.getByRole('button', { name: 'Due today', exact: true }).click(); await expect(grid.locator('.udg-view-cards>article')).toHaveCount(2); await grid.getByRole('button', { name: 'Mine', exact: true }).click();
    const card = grid.locator('.udg-view-cards>article').filter({ hasText: 'Launch campaign' }); await card.getByRole('button', { name: 'More details' }).click(); await expect(card.locator('.udg-record-field').filter({ hasText: 'More context' })).toBeVisible(); await card.getByRole('button', { name: 'Start task', exact: true }).click(); await expect(page.getByLabel('Opened record')).toHaveText('started:1');
    await grid.getByRole('button', { name: 'Select records', exact: true }).click(); await card.getByRole('checkbox', { name: 'Select record 1' }).check(); await expect(grid.getByText('1 selected', { exact: true })).toBeVisible(); await grid.getByRole('button', { name: 'Assign to me', exact: true }).click(); await expect(grid.getByText('1 selected', { exact: true })).toHaveCount(0);
    await page.screenshot({ path: path.join(output, 'record-cards.png') });
    await grid.getByRole('button', { name: 'Table view' }).click(); const removeGroup = grid.getByRole('button', { name: 'Remove grouping Status' }); if (await removeGroup.count()) await removeGroup.click(); const cell = grid.locator('[data-row-id="1"][data-cell-id="name"]'); await cell.focus(); await cell.press('F2'); await grid.getByRole('textbox', { name: 'Edit Name', exact: true }).fill('Updated campaign'); await grid.getByRole('textbox', { name: 'Edit Name', exact: true }).press('Enter'); await expect(cell).toHaveText('Updated campaign'); await grid.getByRole('button', { name: 'Undo', exact: true }).click(); await expect(cell).toHaveText('Launch campaign');
    expect(errors).toEqual([]);
    console.log(process.argv.includes('--grid-only') ? 'PASS record cards, quick filters, closed-work exclusion, details, primary/bulk actions, edit/Undo' : 'PASS mobile usability: four contextual sheets, six/all actions, phone widths, permissions, focus, live Today, CRM/Sales record search/history, offline/reconnect, draft recovery, full-width searchable picker, persistent snooze/unsnooze, cards, quick filters, closed-work exclusion, details, primary/bulk actions, edit/Undo');
  } catch (error) { throw error; } finally { await browser.close(); await server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

