const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');
const root = path.resolve(__dirname, '..');
const catalog = require('../../backend/app/core/business_profiles.json');
const source = `import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Panel from '@/apps/srm/industry/AppointmentVisitPanel';import {useAuthStore} from '@/store/authStore';import '@/index.css';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'test@example.invalid',role:'super_admin',is_superuser:true}});const finance=!new URLSearchParams(location.search).has('no-finance');createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/srm/appointments']}><Panel row={{id:1,title:'Follow-up consultation',status:'completed',revision:1,customer_id:2,data:{customer_name:'Patient Example',service_name:'Consultation',currency:'INR',starts_at:'2026-11-16T10:00:00+05:30',duration_minutes:30}}} canViewBilling={finance} canCollect={finance} canInvoice={finance} canApprove={finance} onChanged={()=>{}}/></MemoryRouter></QueryClientProvider>);`;
(async () => {
  const fixture = path.join(__dirname, `.visit-payments-${process.pid}-${Date.now()}.tsx`);
  fs.writeFileSync(fixture, source);
  const { createServer } = await import('vite');
  const server = await createServer({ root, server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null } });
  await server.listen(); const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = [], writes = []; let financeReads = 0;
      page.on('pageerror', error => errors.push(error.message));
      const billing = { revision: 1, currency: 'INR', total: 590, paid: 0, advance: 0, balance: 590, invoice: null, receipts: [] };
      await page.route('**/api/v1/**', route => {
        const request = route.request(), url = new URL(request.url());
        if (url.pathname.includes('business-profile/effective')) return route.fulfill({ json: { business_type: 'hospital', terms: { ...catalog.terms, ...catalog.profiles.find(p => p.id === 'hospital').terms } } });
        if (url.pathname.endsWith('/billing')) { financeReads++; return route.fulfill({ json: billing }); }
        if (request.method() === 'POST') {
          writes.push(url.pathname); const body = request.postDataJSON() || {};
          if (url.pathname.endsWith('/payments')) { const amount = Number(body.amount); billing.receipts.push({ id: billing.receipts.length + 1, number: 'RCT-' + (billing.receipts.length + 1), amount, status: billing.invoice ? 'allocated' : 'confirmed', method: body.payment_method }); billing.balance -= amount; if (billing.invoice) { billing.paid += amount; billing.invoice.balance -= amount; billing.invoice.status = billing.balance === 0 ? 'paid' : 'partially_paid'; } else billing.advance += amount; }
          if (url.pathname.endsWith('/invoice')) billing.invoice = { id: 9, number: 'INV-9', status: 'draft', balance: 590 };
          if (url.pathname.endsWith('/approve')) billing.invoice.status = 'approved';
          if (url.pathname.endsWith('/apply-advances')) { billing.paid += billing.advance; billing.invoice.balance -= billing.advance; billing.advance = 0; billing.invoice.status = 'partially_paid'; }
          billing.revision++; return route.fulfill({ json: billing });
        }
        return route.fulfill({ json: { items: [] } });
      });
      await page.route('**/qa-visit-payments*', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      const url = server.resolvedUrls.local[0] + 'qa-visit-payments';
      await page.goto(url); await page.getByRole('button', { name: 'Open visit & payments' }).click();
      const dialog = page.getByRole('dialog');
      await expect(dialog).toContainText('Patient Example');
      await dialog.getByLabel('Payment amount', { exact: true }).fill('100');
      await dialog.getByRole('button', { name: 'Record payment', exact: true }).click();
      await expect(dialog.getByRole('status')).toHaveText('Payment recorded.');
      await expect(dialog.getByRole('region', { name: 'Payment receipts' })).toContainText('RCT-1');
      await dialog.getByRole('button', { name: 'Create invoice draft', exact: true }).click();
      await dialog.getByRole('button', { name: 'Approve invoice', exact: true }).click();
      await dialog.getByRole('button', { name: 'Apply advance to invoice', exact: true }).click();
      await expect(dialog.getByRole('status')).toHaveText('Advance applied to the invoice.');
      await dialog.getByLabel('Payment amount', { exact: true }).fill('490');
      await dialog.getByLabel('Payment method', { exact: true }).selectOption('upi');
      await dialog.getByRole('button', { name: 'Record payment', exact: true }).click();
      await expect(dialog).toContainText('INV-9 · paid');
      await expect(dialog.getByRole('form', { name: 'Collect visit payment' })).toHaveCount(0);
      expect(writes.filter(path => path.endsWith('/payments'))).toHaveLength(2);
      await page.goto(url + '?no-finance=1'); financeReads = 0;
      await page.getByRole('button', { name: 'Open visit & payments' }).click();
      await expect(page.getByRole('dialog').getByRole('region', { name: 'Visit payments' })).toHaveCount(0);
      expect(financeReads).toBe(0); expect(errors).toEqual([]); await page.close();
    }
    console.log('Visit checkout: advance, invoice approval, allocation, final payment and restricted finance access passed at phone/desktop widths.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exit(1); });
