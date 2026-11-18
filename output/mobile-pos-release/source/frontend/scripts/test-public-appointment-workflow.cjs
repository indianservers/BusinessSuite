const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');
(async () => {
  const apiOrigin = process.env.WORKFLOW_TEST_ORIGIN;
  if (!apiOrigin) throw new Error('This test requires an isolated fixture API.');
  const fixture = path.join(__dirname, `.public-appointment-workflow-${process.pid}-${Date.now()}.tsx`);
  fs.writeFileSync(fixture, `import React from 'react';import{createRoot}from'react-dom/client';import{BrowserRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/apps/srm/industry/IndustryOperationsPage';import{useAuthStore}from'@/store/authStore';import{api}from'@/services/api';import'@/index.css';const c=window.__BOOKING_QA__;sessionStorage.setItem('suite-branch',c.branch);sessionStorage.setItem('suite-organization','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:c.token});const{data:user}=await api.get('/auth/me');useAuthStore.setState({user:{...user,role:typeof user.role==='object'?user.role.name:user.role}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Page mode="appointments"/></BrowserRouter></QueryClientProvider>);`);
  const { createServer } = await import('vite');
  const server = await createServer({ root: process.cwd(), cacheDir: process.env.WORKFLOW_TEST_CACHE, server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null, proxy: { '/api': { target: apiOrigin, changeOrigin: true } } } });
  await server.listen(); const browser = await chromium.launch({ headless: true });
  const headers = { Authorization: 'Bearer ' + process.env.BOOKING_TOKEN, 'X-Suite-Organization': '1', 'X-Suite-Branch': process.env.BOOKING_BRANCH };
  try {
    let expected = 0;
    for (const width of [390, 1280]) {
      const staff = await browser.newPage({ viewport: { width, height: 1000 } }), errors = [];
      staff.on('pageerror', error => errors.push(error.message));
      await staff.route('**/qa-public-appointment-staff', route => route.fulfill({ contentType: 'text/html', body: `<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};window.__BOOKING_QA__=${JSON.stringify({ token: process.env.BOOKING_TOKEN, branch: process.env.BOOKING_BRANCH })}</script><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await staff.goto(server.resolvedUrls.local[0] + 'qa-public-appointment-staff');
      await expect(staff.getByRole('heading', { name: 'Consultations', exact: true })).toBeVisible({timeout: 45000}).catch(async error => { throw new Error(error.message + '\nPage errors: ' + JSON.stringify(errors) + '\nBody: ' + await staff.locator('body').innerText()); });
      await staff.getByRole('button', { name: 'New consultation', exact: true }).click();
      await staff.getByRole('combobox', { name: 'Search patient', exact: true }).fill(process.env.BOOKING_CUSTOMER);
      await staff.getByRole('option').filter({ hasText: process.env.BOOKING_CUSTOMER }).first().click();
      await staff.getByRole('combobox', { name: 'Search consultation type', exact: true }).fill(process.env.BOOKING_SERVICE);
      await staff.getByRole('option').filter({ hasText: process.env.BOOKING_SERVICE }).first().click();
      await staff.getByLabel('Duration (minutes)', { exact: true }).fill('30');
      await staff.getByRole('checkbox').filter({ hasText: '' }).count();
      await staff.getByLabel(process.env.BOOKING_PROVIDER + ' · Doctor', { exact: true }).check();
      await staff.getByRole('button', { name: 'Create private booking link', exact: true }).click();
      const urlInput = staff.getByLabel('Private booking URL', { exact: true });
      await expect(urlInput).toBeVisible();
      const privatePath = new URL(await urlInput.inputValue()).pathname;
      const patient = await browser.newPage({ viewport: { width, height: 1000 } });
      patient.on('pageerror', error => errors.push(error.message));
      await patient.goto(apiOrigin + privatePath);
      await expect(patient.getByRole('heading', { name: 'Book consultation', exact: true })).toBeVisible();
      await patient.getByLabel('Date', { exact: true }).fill(process.env.BOOKING_DAY);
      await patient.getByRole('button', { name: 'Show available times', exact: true }).click();
      await expect(patient.getByRole('combobox', { name: 'Available time', exact: true })).toBeVisible();
      expect(await patient.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await patient.getByRole('button', { name: 'Confirm consultation', exact: true }).click();
      await expect(patient.getByRole('heading', { name: 'Consultation confirmed', exact: true })).toBeVisible();
      await patient.goto(apiOrigin + privatePath);
      await expect(patient.getByRole('heading', { name: 'Consultation confirmed', exact: true })).toBeVisible();
      const response = await staff.request.get(apiOrigin + '/api/v1/srm/industry/records?kind=appointment', { headers });
      expect(response.status()).toBe(200); const items = (await response.json()).items;
      expect(items).toHaveLength(++expected);
      expect(items.every(row => row.status === 'booked' && row.invoice_id === null)).toBe(true);
      await staff.getByRole('button', { name: 'Revoke link', exact: true }).click();
      await expect(staff.getByRole('status').filter({ hasText: 'Booking link revoked.' })).toBeVisible();
      const revoked = await patient.goto(apiOrigin + privatePath); expect(revoked.status()).toBe(404);
      expect(errors).toEqual([]); await patient.close(); await staff.close();
    }
    console.log('Real public appointment workflow: staff link creation, anonymous slot selection, native booking, replay protection and revocation passed at phone/desktop widths.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exit(1); });
