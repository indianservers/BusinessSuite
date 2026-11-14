const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');
const root = path.resolve(__dirname, '..');
const catalog = require('../../backend/app/core/business_profiles.json');
const source = `import React from 'react';import{useBusinessTerms}from'@/hooks/use-business-terms';import{businessRouteLabel}from'@/lib/business-profile';import BusinessTerm from '@/components/BusinessTerm';import EmployeeSearchSelect from '@/apps/hrms/components/EmployeeSearchSelect';import MobileQuotesWorkspace from '@/components/mobile/MobileQuotesWorkspace';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import SharedDataGrid from '@/shared/data-grid/SharedDataGrid';import GridTable from '@/shared/data-grid/GridTable';import {localGridSource} from '@/shared/data-grid/local-source';import {useAuthStore} from '@/store/authStore';import '@/index.css';const user={id:1,email:'test@example.invalid',role:'super_admin',is_superuser:true,access:{companyId:1}};useAuthStore.setState({isAuthenticated:true,isHydrated:true,user});const columns=[{id:'customer_id',title:'Customer ID'},{id:'customer_name',title:'Customer name'},{id:'custom_customer',title:'Customer'},{id:'project_id',title:'Engagement'}];const rows=[{id:1,customer_id:'C-100',customer_name:'Original record name',custom_customer:'Unchanged value',project_id:'P-100'}];const dataSource=localGridSource('business-terms-records',rows,columns,row=>String(row.id));function App(){const{profile}=useBusinessTerms();return <><span data-testid='built-in-route'>{businessRouteLabel(profile,'/crm/customers','Customers')}</span><span data-testid='custom-route'>{businessRouteLabel(profile,'/crm/customers','Priority accounts')}</span><span data-testid='directory-route'>{businessRouteLabel(profile,'/hrms/employee-directory','Employee Directory')}</span>{innerWidth<768&&<MobileQuotesWorkspace/>}<EmployeeSearchSelect endpoint='/hrms/business-profile-qa/employee-options' value='' onChange={()=>{}}/><section aria-label='Built-in captions'><label htmlFor='caption-customer'><BusinessTerm name='customer'/></label><input id='caption-customer'/><label htmlFor='caption-employee'><BusinessTerm name='employee'/></label><input id='caption-employee'/><h2><BusinessTerm name='project' plural/></h2><select aria-label='Record type'><option value='project'><BusinessTerm name='project'/></option></select></section><button onClick={()=>{sessionStorage.setItem('suite-organization','2');useAuthStore.setState({user:{...user,access:{companyId:2}}});}}>Switch company</button><section aria-label='Semantic grid'><SharedDataGrid gridId='business-terms-grid' columns={columns} dataSource={dataSource} getRowId={row=>String(row.id)} selectionEnabled={false} detailsEnabled={false} overview={false}/></section><section aria-label='Native table'><GridTable gridId='business-terms-native' variant='matrix'><thead><tr><th data-business-field='customer_id'>Customer ID</th><th>Customer</th></tr></thead><tbody><tr><td>C-100</td><td>Unchanged value</td></tr></tbody></GridTable></section></>};createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/srm/invoices']}><App/></MemoryRouter></QueryClientProvider>);`;
(async () => {
  const fixture = path.join(__dirname, `.business-terms-surfaces-${process.pid}-${Date.now()}.tsx`);
  fs.writeFileSync(fixture, source);
  const { createServer } = await import('vite');
  const server = await createServer({ root, server: { host: '127.0.0.1', port: 0, strictPort: false, hmr: false, watch: null } });
  await server.listen(); const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      await page.route('**/api/v1/**', route => {
        const request = route.request(), url = new URL(request.url());
        if(url.pathname.endsWith('/crm/companies'))return route.fulfill({json:{items:[{id:71,name:'Original customer name'}],total:1}});
        if(url.pathname.endsWith('/business-profile-qa/employee-options'))return route.fulfill({json:[]});
        if (url.pathname.endsWith('/business-profile/effective')) {
          const type = request.headers()['x-suite-organization'] === '2' ? 'consulting' : 'hospital';
          return route.fulfill({ json: { business_type: type, terms: { ...catalog.terms, ...catalog.profiles.find(p => p.id === type).terms, ...(type==='hospital'?{employee:['Team member','Team members'],project:['Case','Cases']}:{}) } } });
        }
        return route.fulfill({ json: { items: [], total: 0 } });
      });
      await page.route('**/qa-business-terms-surfaces', route => route.fulfill({ contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>` }));
      await page.goto(server.resolvedUrls.local[0] + 'qa-business-terms-surfaces');
      const grid = page.getByRole('region', { name: 'Semantic grid', exact: true }), native = page.getByRole('region', { name: 'Native table', exact: true });
      const caption = text => width < 768 ? grid.getByRole('article').getByText(text, { exact: true }).first() : grid.getByRole('columnheader', { name: new RegExp(text) }).first();
      await expect(page.getByRole('textbox',{name:'Patient',exact:true})).toBeVisible();
      await expect(page.getByRole('textbox',{name:'Team member',exact:true})).toBeVisible();
      await expect(page.getByRole('textbox',{name:'Search team member',exact:true})).toBeVisible();
      await expect(page.getByRole('heading',{name:'Cases',exact:true})).toBeVisible();
      await expect(page.getByRole('combobox',{name:'Record type',exact:true})).toHaveValue('project');
      await expect(page.getByRole('option',{name:'Case',exact:true})).toBeAttached();
      if(width<768){await page.getByRole('button',{name:'New quote',exact:true}).click();await expect(page.getByRole('combobox',{name:'Patient',exact:true})).toBeVisible();await page.getByRole('combobox',{name:'Patient',exact:true}).selectOption('71');}
      await expect(page.getByTestId('built-in-route')).toHaveText('Patients');
      await expect(page.getByTestId('custom-route')).toHaveText('Priority accounts');
      await expect(page.getByTestId('directory-route')).toHaveText('Team member Directory');
      await expect(caption('Patient ID')).toBeVisible();
      await expect(caption('Patient name')).toBeVisible();
      await expect(caption('Customer')).toBeVisible();
      await expect(caption('Engagement')).toBeVisible();
      await expect(native.getByRole('columnheader', { name: /Patient ID/ }).first()).toBeVisible();
      await expect(native.getByRole('columnheader', { name: /Customer/ }).first()).toBeVisible();
      await expect(grid).toContainText('Original record name');
      await expect(grid.getByRole('button', { name: 'Favorite Original record name', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Switch company', exact: true }).click();
      await expect(native.getByRole('columnheader', { name: /Client ID/ }).first()).toBeVisible();
      await expect(caption('Client name')).toBeVisible();
      await expect(native).toContainText('Unchanged value');
      expect(errors).toEqual([]); await page.close();
    }
    console.log('Business terms: semantic headers, custom caption preservation, record values and company switching passed at phone/desktop widths.');
  } finally { await browser.close(); await server.close(); fs.unlinkSync(fixture); }
})().catch(error => { console.error(error); process.exit(1); });
