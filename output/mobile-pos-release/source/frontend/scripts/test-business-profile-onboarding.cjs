const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');
const root = path.resolve(__dirname, '..');
const catalog = require('../../backend/app/core/business_profiles.json');
const source = `import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter,Routes,Route} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Page from '@/pages/PostLoginPage';import {useAuthStore} from '@/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'admin@example.invalid',role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/post-login?next=/dashboard']}><Routes><Route path='/post-login' element={<Page/>}/><Route path='/dashboard' element={<h1>Authorized workspace</h1>}/></Routes></MemoryRouter></QueryClientProvider>);`;
(async () => {
  const fixture = path.join(__dirname, `.profile-onboarding-${process.pid}-${Date.now()}.tsx`);
  fs.writeFileSync(fixture, source);
  const { createServer } = await import('vite');
  const server = await createServer({ root, server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch({ headless: true });
  try {
    for (const multiCompany of [false, true]) {
      const page = await browser.newPage();
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      let values = {}, version = 0, savedCompany, onboardingReads = 0;
      await page.route('**/api/v1/**', route => {
        const request = route.request(), url = new URL(request.url());
        const companyId = Number(request.headers()['x-suite-organization'] || 1);
        if (url.pathname.endsWith('/access/me')) return route.fulfill({ json: { companyId, companyName: 'Approved company', organizations: multiCompany ? [{ id: 1, name: 'Company One' }, { id: 2, name: 'Company Two' }] : [{ id: 1, name: 'Company One' }] } });
        if (url.pathname.endsWith('/access/onboarding')) return route.fulfill({ json: { available: false, done: true } });
        if (url.pathname.endsWith('/business-profile/onboarding')) { onboardingReads++; return route.fulfill({ json: { companyId, required: !values.business_type, editable: true } }); }
        if (url.pathname.endsWith('/business-profile/configuration')) {
          if (request.method() === 'PUT') { values = request.postDataJSON().values; version++; savedCompany = companyId; return route.fulfill({ json: { saved: true, version } }); }
          return route.fulfill({ json: { overrides: values, version, inherited: { business_type: 'general', terms: catalog.terms, custom_terms: {} }, branches: [], companyId } });
        }
        return route.fulfill({ json: { items: [], total: 0 } });
      });
      await page.route('**/qa-profile-onboarding', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await page.goto(server.resolvedUrls.local[0] + 'qa-profile-onboarding');
      if (multiCompany) {
        await expect(page.getByRole('heading', { name: 'Choose your company' })).toBeVisible();
        expect(onboardingReads).toBe(0);
        await page.getByRole('button', { name: 'Company Two', exact: true }).click();
      }
      await expect(page.getByRole('heading', { name: 'Choose your business type' })).toBeVisible();
      await expect(page.getByLabel('Business profile scope')).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Save business profile', exact: true })).toBeDisabled();
      await page.getByLabel('Business type', { exact: true }).selectOption('hospital');
      await expect(page.getByRole('region', { name: 'Business terminology preview' })).toContainText('Patients');
      await page.getByRole('button', { name: 'Save business profile', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Authorized workspace' })).toBeVisible();
      expect(savedCompany).toBe(multiCompany ? 2 : 1);
      expect(values.business_type).toBe('hospital');
      expect(errors).toEqual([]);
      await page.close();
    }
    console.log('First-login business selection: company choice, preview, persistence and return to workspace passed.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exit(1); });
