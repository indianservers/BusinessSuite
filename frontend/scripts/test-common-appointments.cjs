const fs = require('node:fs');
const { chromium, expect } = require('playwright/test');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = `import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Page from '@/apps/srm/industry/IndustryOperationsPage';import {useAuthStore} from '@/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'test@example.invalid',role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/srm/appointments']}><Page mode="appointments"/></MemoryRouter></QueryClientProvider>);`;
(async () => {
  const fixture = path.join(__dirname, `.common-appointments-${process.pid}-${Date.now()}.tsx`);
  fs.writeFileSync(fixture, source);
  const { createServer } = await import('vite');
  const server = await createServer({ root, server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null } });
  await server.listen();
  const catalog = require('../../backend/app/core/business_profiles.json');
  const terms = { ...catalog.terms, ...catalog.profiles.find(p => p.id === 'hospital').terms };
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [390, 1280]) for (const providerSource of ['account', 'employee']) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      let write;
      await page.route('**/api/v1/**', route => {
        const request = route.request(), url = new URL(request.url());
        if (request.method() === 'POST') { write = { url: url.pathname.replace('/api/v1', ''), body: request.postDataJSON() }; return route.fulfill({ json: { ...write.body, id: 20, kind: 'resource', status: 'active', revision: 1, data: write.body } }); }
        const body = url.pathname.includes('business-profile/effective') ? { business_type: 'hospital', terms } : url.pathname.endsWith('/capabilities') ? { manage: true, approve: false, invoice: false } : url.pathname.endsWith('/employee-options') ? { items: [{ id: 17, name: 'Doctor Example' }], has_more: false } : url.pathname.endsWith('/staff-options') ? { items: [{ id: 7, name: 'doctor@example.invalid' }], has_more: false } : { items: [], total: 0, pages: 1 };
        return route.fulfill({ json: body });
      });
      await page.route('**/qa-common-appointments', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await page.goto(server.resolvedUrls.local[0] + 'qa-common-appointments');
      await expect(page.getByRole('heading', { name: 'Consultations', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'New consultation', exact: true }).click();
      await expect(page.getByRole('combobox', { name: 'Search patient', exact: true })).toBeVisible();
      await expect(page.getByRole('combobox', { name: 'Search consultation type', exact: true })).toBeVisible();
      await expect(page.getByLabel('Consultation date', {exact:true})).toBeVisible();
      await expect(page.getByRole('group', { name: 'Doctors & Consultation rooms', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      await page.getByRole('tab', { name: 'Doctors & Consultation rooms', exact: true }).click();
      await page.getByRole('button', { name: 'New doctor / consultation room', exact: true }).click();
      await expect(page.getByLabel('Resource type')).toHaveValue('provider');
      await expect(page.getByLabel('Resource type').locator('option:checked')).toHaveText('Doctor');
      await page.getByLabel('Title', { exact: true }).fill('Dr Test');
      if (providerSource === 'employee') {
        await page.getByRole('combobox', { name: 'Search hrms employee' }).fill('doctor');
        await page.getByRole('option').filter({ hasText: 'Doctor Example' }).click();
        await expect(page.getByRole('combobox', { name: 'Search staff account' })).toHaveCount(0);
      } else {
        await page.getByRole('combobox', { name: 'Search staff account' }).fill('doctor');
        await page.getByRole('option').filter({ hasText: 'doctor@example.invalid' }).click();
      }
      await page.getByRole('button', { name: 'Save operation', exact: true }).click();
      await expect(page.getByRole('status')).toContainText('Saved successfully');
      expect(write.url).toBe('/srm/industry/resources'); expect(write.body.resource_type).toBe('provider');
      if (providerSource === 'employee') { expect(write.body.employee_id).toBe(17); expect(write.body.user_id).toBeUndefined(); }
      else expect(write.body.user_id).toBe(7);
      expect(errors).toEqual([]); await page.close();
    }
    console.log('Common appointments: hospital terminology and linked staff creation passed at phone and desktop widths.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exit(1); });
