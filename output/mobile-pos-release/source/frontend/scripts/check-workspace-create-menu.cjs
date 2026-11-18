const { chromium, expect } = require('playwright/test');
const base = process.env.CREATE_MENU_BASE_URL || 'http://127.0.0.1:5189';
const html = `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/workspace-create-menu.tsx');</script>`;
(async () => {
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) for (const module of ['pms', 'crm']) {
      const page = await browser.newPage({ viewport: { width, height: 850 } });
      const errors = [], writes = [];
      page.on('pageerror', e => { errors.push(e.message); console.error(e.message); });
      await page.route('**/api/v1/**', route => {
        if (route.request().method() !== 'GET') writes.push(route.request().url());
        const url = new URL(route.request().url());
        const data = url.pathname.endsWith('/workspaces') ? [{ id: 7, name: 'QA workspace', role: 'Owner' }] : url.pathname.endsWith('/project-management/projects') ? [{id:10,name:'QA project',workspace_id:7,can_manage_tasks:true}] : url.pathname.endsWith('/task-studio/options') ? {people:[{id:1,name:'QA'}],can_edit:true} : /\/projects\/10\/(tasks|sprints)$/.test(url.pathname) ? (url.pathname.endsWith('/tasks') ? [{id:42,title:'Parent task',parent_task_id:null}] : []) : { items: [] };
        return route.fulfill({ json: data });
      });
      await page.route('**/create-menu-qa?*', route => route.fulfill({ contentType: 'text/html', body: html }));
      const visit = async (path = `/${module}/records?workspace=7`) => {
        await page.goto(`${base}/create-menu-qa?path=${encodeURIComponent(path)}`);
        await page.getByRole('button', { name: 'Create', exact: true }).click();
        await expect(page.getByRole('menuitem').filter({ has: page.locator('.suite-new-item-copy').filter({ hasText: /^Task/ }) })).toHaveCount(1);
      };
      const item = label => page.getByRole('menuitem').filter({ has: page.locator('.suite-new-item-copy').filter({ hasText: new RegExp(`^${label}(?=[A-Z]|$)`) }) });
      await visit();
      const menuBounds = await page.getByRole('menu').boundingBox();
      expect(menuBounds.x).toBeGreaterThanOrEqual(0);
      expect(menuBounds.x + menuBounds.width).toBeLessThanOrEqual(width);
      expect(menuBounds.y + menuBounds.height).toBeLessThanOrEqual(850);
      await page.keyboard.press('Escape');
      await expect(page.getByRole('button', { name: 'Create', exact: true })).toBeFocused();
      const destinations = {
        List: module === 'pms' ? '/pms/tasks?layout=list&workspace=7' : '/crm/tasks?workspace=7',
        Folder: `/${module}/files?workspace=7`, Space: module === 'pms' ? '/pms/workspaces?new=workspace&workspace=7' : '/crm/workspaces?workspace=7',
        Document: '/pms/docs', Conversation: `/${module}/messages?workspace=7`, Page: '/pms/notes?new=1',
        'Custom Field': module === 'pms' ? '/pms/custom-fields?workspace=7' : '/crm/record-metadata?workspace=7',
        Dashboard: `/${module}/${module === 'pms' ? 'dashboards' : 'dashboard'}?workspace=7`, Tag: module === 'pms' ? '/pms/tags' : '/crm/records?workspace=7',
        'Time Tracked': '/pms/time-tracking', 'View List': module === 'pms' ? '/pms/tasks?layout=list&workspace=7' : '/crm/leads?view=table&workspace=7',
        Whiteboard: module === 'pms' ? '/pms/tasks?layout=whiteboard&workspace=7' : '/crm/leads?view=whiteboard&workspace=7',
      };
      // Same-module destinations retain the selected workspace.
      for (const label of ['Document', 'Page', 'Tag', 'Time Tracked']) if (module === 'pms') destinations[label] += destinations[label].includes('?') ? '&workspace=7' : '?workspace=7';
      for (const [label, destination] of Object.entries(destinations)) {
        await visit(); await item(label).click();
        await expect(page.getByTestId('destination')).toHaveText(destination);
      }
      for (const label of ['Sheet', 'Artifact', 'Clip']) {
        await visit(); await item(label).click();
        await expect(page.getByRole('dialog')).toBeVisible();
        await page.getByRole('button', { name: 'Open Files', exact: true }).click();
        await expect(page.getByRole('dialog')).toHaveCount(0);
        await expect(page.getByTestId('destination')).toHaveText(`/${module}/files?workspace=7`);
      }
      await visit(); await item('Form').click();
      await expect(page.getByTestId('destination')).toHaveText(`/${module}/forms/new`);
      await visit(); await item('Reminder').click();
      if (module === 'crm') await expect(page.getByRole('dialog')).toBeVisible();
      else await expect(page.getByTestId('destination')).toHaveText('/pms/tasks-follow-ups?workspace=7');
      if (module === 'pms') {
        await visit('/pms/tasks/42?projectId=10&workspace=7'); await item('Subtask').click();
        await expect(page.getByRole('dialog', {name:'Create subtask',exact:true})).toBeVisible();
        await expect(page.getByLabel('Parent task',{exact:true})).toHaveValue('42');
      }
      expect(errors).toEqual([]); expect(writes).toEqual([]);
      console.log(`${module.toUpperCase()} Create: mapped entries, destinations, compact windows, keyboard focus, no unintended writes (${width}px) passed`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
