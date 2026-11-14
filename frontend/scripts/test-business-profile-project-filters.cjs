const fs = require('node:fs'), path = require('node:path');
const { chromium, expect } = require('playwright/test');
const catalog = require('../../backend/app/core/business_profiles.json');
(async () => {
  const fixture = path.join(__dirname, `.business-project-filters-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/apps/project-management/pages/AnalyticsPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';const user={id:1,email:'test@example.invalid',role:'super_admin',is_superuser:true,access:{companyId:1}};sessionStorage.setItem('suite-organization','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,user});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/pms/analytics/projects']}><button onClick={()=>{sessionStorage.setItem('suite-organization','2');useAuthStore.setState({user:{...user,access:{companyId:2}}});}}>Switch profile company</button><Page mode='project'/></MemoryRouter></QueryClientProvider>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen(); const browser = await chromium.launch();
  const counts = { total: 1, completed: 0, open: 1, blocked: 0, overdue: 0, completion_percent: 0, tracked_minutes: 0 };
  const project = { ...counts, id: 71, name: 'Original project name', status: 'Active', estimated_hours: 1, created_in_range: 1, completed_in_range: 0 };
  const data = { start_date: '2026-11-01', end_date: '2026-11-14', generated_at: '2026-11-14T00:00:00Z', summary: { ...counts, people: 0, projects: 1, recently_active: 0 }, people: [], projects: [project], trend: [], hourly_activity: [], status_distribution: [], filters: { projects: [project], teams: [], people: [] }, definitions: { snapshot: 'Fixture task snapshot.', activity: 'Fixture activity.', shared_tasks: 'Fixture shared tasks.' } };
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } }), errors = [], reads = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/v1/**', route => {
        const url = new URL(route.request().url());
        if (url.pathname.endsWith('/business-profile/effective')) {
          const pair = route.request().headers()['x-suite-organization'] === '2' ? ['Engagement', 'Engagements'] : ['Case', 'Cases'];
          return route.fulfill({ json: { business_type: 'custom', terms: { ...catalog.terms, project: pair } } });
        }
        if (url.pathname.endsWith('/analytics/overview')) { reads.push(url); return route.fulfill({ json: data }); }
        return route.fulfill({ json: [] });
      });
      await page.route('**/qa-business-project-filters', route => route.fulfill({ contentType: 'text/html', body: `<meta name='viewport' content='width=device-width,initial-scale=1'><div id='root'></div><script type='module'>import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await page.goto(server.resolvedUrls.local[0] + 'qa-business-project-filters');
      await expect(page.getByRole('heading', { name: 'Case analytics', exact: true })).toBeVisible({ timeout: 30000 });
      if (width < 481) await page.getByText(/^Scope filters/).click();
      const select = page.getByRole('combobox', { name: 'Case', exact: true });
      await expect(select).toBeVisible(); await select.selectOption('71');
      await expect.poll(() => reads.some(url => url.searchParams.get('project_id') === '71')).toBe(true);
      await page.getByRole('button', { name: 'Switch profile company', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Engagement analytics', exact: true })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Engagement', exact: true })).toHaveValue('71');
      await expect(page.getByRole('option', { name: 'Original project name', exact: true })).toHaveAttribute('value', '71');
      expect(reads.every(url => !url.searchParams.has('case_id') && !url.searchParams.has('engagement_id'))).toBe(true);
      expect(errors).toEqual([]); await page.close();
    }
    console.log('Project terminology: native analytics filters, company switching, record names and canonical project_id requests passed on phone/desktop.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exitCode = 1; });
