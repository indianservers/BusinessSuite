const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const fixture = path.resolve('scripts', `.service-workspace-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import '@/index.css';import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Workspace from '@/shared/scheduling/ServiceSchedulingWorkspace';import {useAuthStore} from '@/store/authStore';useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/hrms/service-scheduling']}><QueryClientProvider client={new QueryClient()}><Workspace/></QueryClientProvider></MemoryRouter>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [390, 1440]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const failures = [], checks = [];
      page.on('pageerror', e => failures.push(e.message));
      await page.route('**/api/v1/**', async route => {
        const url = new URL(route.request().url());
        let json = {};
        if (url.pathname.endsWith('/catalog/items')) json = { items: [{ id: 9, kind: 'service', name: 'Consultation', code: 'S9' }], pages: 1 };
        else if (url.pathname.endsWith('/options/availability')) {
          checks.push(url.searchParams);
          json = { timezone: 'UTC', checked_at: new Date().toISOString(), selection_available: !url.searchParams.has('resource_ids'), slots: [{ starts_at: '2030-12-20T11:00:00Z', label: '11:00' }], resources: [{ id: 30, available: false }] };
        } else if (url.pathname.endsWith('/service-checkout/options')) json = { policy: { active: true, default_duration_minutes: 30 }, specialists: [{ eligibility_id: 2, employee_id: 22, employee_name: 'Alex Employee', timezone: 'UTC', work_categories: ['Consultants', 'Senior'] }], resources: [{ id: 30, name: 'Room A', resource_type: 'room', opens: '09:00', closes: '19:00', timezone: 'UTC' }], has_more: false };
        else if (url.pathname.endsWith('/employees/planned-services')) json = { timezone: 'UTC', items: [{ appointment_id: 44, revision: 1, employee_id: 22, employee_name: 'Alex Employee', employee_code: 'E22', employee_categories: ['Consultants', 'Senior'], service_id: 9, service_name: 'Consultation', starts_at: new Date(Date.now() + 3600000).toISOString(), ends_at: new Date(Date.now() + 5400000).toISOString(), planned_minutes: 30, status: 'booked', blocks_availability: true, resources: [{ id: 30, name: 'Room A', resource_type: 'room' }] }], next_cursor: null, filter_options: { employees: [{ id: 22, name: 'Alex Employee', code: 'E22' }], services: [{ id: 9, name: 'Consultation' }], employees_complete: true, services_complete: true } };
        await route.fulfill({ json });
      });
      await page.route('**/service-workspace-qa', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await page.goto(server.resolvedUrls.local[0] + 'service-workspace-qa');
      await expect(page.getByRole('heading', { name: '1. Create and assign employee categories' })).toBeVisible();
      await page.getByRole('button', { name: 'Available resources', exact: true }).click();
      await page.getByLabel('Availability service').selectOption('9');
      await page.getByRole('checkbox', { name: 'Consultants', exact: true }).check();
      await page.getByLabel('Availability employee').selectOption('2');
      await page.getByLabel('Availability from', { exact: true }).fill('2030-12-20T10:00');
      await page.getByLabel('Availability to', { exact: true }).fill('2030-12-20T10:45');
      await page.getByRole('checkbox', { name: /Room A/ }).check();
      await expect(page.getByRole('status')).toContainText('unavailable');
      expect(checks.some(p => p.get('duration_minutes') === '45' && p.get('starts_at') === '2030-12-20T10:00:00.000Z' && p.get('resource_ids') === '30')).toBeTruthy();
      await page.getByRole('button', { name: '11:00', exact: true }).click();
      await expect(page.getByLabel('Availability to', { exact: true })).toHaveValue('2030-12-20T11:45');
      await page.getByRole('button', { name: 'Schedule & Gantt', exact: true }).click();
      await expect(page.getByRole('cell', { name: 'Room A', exact: true })).toBeVisible();
      await expect(page.getByRole('cell', { name: 'Consultants, Senior', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Consultation', exact: true }).click();
      await expect(page.getByRole('dialog')).toContainText('Room A (room)');
      await expect(page.getByRole('dialog')).toContainText('Consultants, Senior');
      await page.keyboard.press('Escape');
      await page.getByRole('button', { name: 'Gantt', exact: true }).click();
      await expect(page.getByRole('button', { name: /Alex Employee: Consultation/ })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBeTruthy();
      expect(failures).toEqual([]);
      await page.close();
    }
    console.log('PASS service setup guide, category filtering, exact From/To availability, room conflicts, schedule details and Gantt on desktop/mobile');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(e => { console.error(e); process.exitCode = 1; });
