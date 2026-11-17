const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect: base } = require('playwright/test');
const expect = base.configure({ timeout: 15000 });

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const fixture = path.resolve('scripts', `.prebooking-polish-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import '@/index.css';import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter,Routes,Route} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Workspace from '@/shared/scheduling/ServiceSchedulingWorkspace';import POS from '@/apps/srm/pages/SRMPOSPage';import {useAuthStore} from '@/store/authStore';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={[location.search.includes('hrms')?'/hrms/service-scheduling':'/srm/service-scheduling']}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><Routes><Route path="/srm/pos/terminal" element={<POS/>}/><Route path="*" element={<Workspace/>}/></Routes></QueryClientProvider></MemoryRouter>);`);
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const server = await createServer({ configFile: false, plugins: [react()], resolve: { alias: { '@': path.resolve('src') } }, cacheDir: path.resolve('node_modules/.vite-prebooking-polish'), optimizeDeps: { entries: [fixture] }, server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [1440,390]) {
      const page = await browser.newPage({viewport:{width,height:1000},timezoneId:'UTC'});
      const errors=[], reservations=[], customerWrites=[], otherWrites=[];
      let manage=false, failure=false, slow=0, created;
      const day=new Date(Date.now()+2*86400000).toISOString().slice(0,10);
      const meera={id:8,name:'Meera Rao',phone:'9999999999',entityKind:'Individual',roles:['Customer']};
      const services=[{id:9,kind:'service',name:'Styling',code:'S9',category:'Hair',price:800,currency:'INR'},{id:10,kind:'service',name:'Therapy',code:'S10',category:'Therapy',price:1000,currency:'INR'}];
      const people=[{eligibility_id:2,eligibility_revision:1,provider_resource_id:12,employee_id:22,employee_name:'Alex Employee',provider_name:'Alex',timezone:'UTC',work_categories:['Stylists']},{eligibility_id:3,eligibility_revision:1,provider_resource_id:13,employee_id:23,employee_name:'Sam Therapist',provider_name:'Sam',timezone:'Asia/Kolkata',work_categories:['Therapists']}];
      const savedRow={id:99,kind:'appointment',title:'Service prebooking',status:'booked',revision:1,customer_id:9,data:{customer_name:'Neha Iyer',service_name:'Styling',starts_at:`${day}T10:00:00Z`,duration_minutes:45,resource_ids:[12,30]}};
      page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
      await page.route('**/api/v1/**',async route=>{
        const req=route.request(),url=new URL(req.url()),p=url.pathname;
        let json={items:[],total:0,pages:1};
        if(p.endsWith('/industry/capabilities'))json={manage:true,billing:true,collect:false,invoice:false,approve_invoice:false,projects_enabled:false,crm_enabled:false};
        else if(p.endsWith('/master-data/companies') && req.method()==='POST'){const body=req.postDataJSON();customerWrites.push(body);created={...body,id:9,name:body.name,phone:'8888888888',entityKind:'Individual'};json=created;}
        else if(p.endsWith('/master-data/companies')){const search=url.searchParams.get('search')||'';json={items:[meera,...(created?[created]:[])].filter(c=>!search||c.name.toLowerCase().includes(search.toLowerCase())),total:created?2:1,canCreate:true};}
        else if(p.endsWith('/master-data/companies/8'))json=meera;
        else if(p.endsWith('/master-data/companies/9'))json=created;
        else if(p.endsWith('/master-data/form-options'))json={country:'IN',currency:'INR',phone_country_code:'+91'};
        else if(p.endsWith('/master-data/companies/custom-fields'))json={items:[],customFields:[]};
        else if(p.endsWith('/branches/context'))json={company_id:1,selected:1,branches:[{id:1,name:'City branch',can_write:true}]};
        else if(/\/catalog\/items\/service\/\d+$/.test(p)) json=services.find(s=>s.id===Number(p.split('/').pop()));
        else if(p.endsWith('/catalog/items')){const category=url.searchParams.get('category'),search=url.searchParams.get('search')||'';json={items:services.filter(s=>(!category||s.category===category)&&(!search||s.name.toLowerCase().includes(search.toLowerCase()))),pages:1,total:2,facets:{categories:['Hair','Therapy'],tags:[]}};}
        else if(p.endsWith('/service-checkout/options')){const therapy=url.searchParams.get('service_id')==='10',search=url.searchParams.get('search')||'';json={policy:{id:1,revision:1,active:true,booking_required:true,default_duration_minutes:therapy?60:45,min_duration_minutes:15,max_duration_minutes:120,allow_duration_override:!therapy,required_resource_types:['room'],employee_categories:therapy?['Therapists']:['Stylists','Therapists']},specialists:people.filter(s=>(!therapy||s.eligibility_id===3)&&(!search||s.employee_name.toLowerCase().includes(search.toLowerCase()))),resources:[{id:30,name:'Room A',resource_type:'room'},{id:31,name:'Room B',resource_type:'room'},{id:40,name:'Projector',resource_type:'equipment'}],has_more:false,can_configure:manage,branch_timezone:'Asia/Kolkata'};}
        else if(p.endsWith('/options/availability')){const fails=failure;if(slow)await new Promise(resolve=>setTimeout(resolve,slow));if(fails)return route.fulfill({status:503,json:{detail:'Temporary availability failure'}});json={selection_available:url.searchParams.getAll('resource_ids').includes('30')||url.searchParams.getAll('resource_ids').includes('31'),conflicts:[],resources:[{id:30,available:true},{id:31,available:true}],slots:[{starts_at:`${url.searchParams.get('day')}T11:00:00Z`,label:'11:00'}]};}
        else if(p.endsWith('/employees/planned-services'))json={timezone:'UTC',items:[],next_cursor:null,filter_options:{employees:[{id:22,name:'Alex Employee'}],services:[],employees_complete:true,services_complete:true}};
        else if(p.endsWith('/industry/appointments') && req.method()==='POST'){reservations.push(req.postDataJSON());json=savedRow;}
        else if(p.endsWith('/industry/appointments/99'))json=savedRow;
        else if(p.endsWith('/appointments/99/billing'))json={appointment_id:99,revision:1,currency:'INR',total:'800',paid:'0',advance:'0',balance:'800',invoice:null,receipts:[]};
        else if(req.method()!=='GET')otherWrites.push({path:p,body:req.postDataJSON()});
        await route.fulfill({json});
      });
      await page.route('**/prebooking-polish?*',route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>`}));
      await page.goto(server.resolvedUrls.local[0]+`prebooking-polish?module=${width===390?'hrms':'srm'}`);
      await expect(page.getByRole('heading',{name:'Appointment Scheduler',exact:true})).toBeVisible({timeout:60000});
      if(width===390)await page.getByRole('button',{name:/New prebooking/}).click();
      const panel=page.getByRole('complementary',{name:'New prebooking'}),confirm=panel.getByRole('button',{name:'Confirm prebooking',exact:true});
      if(width===390){const drawer=page.getByRole('dialog',{name:'Prebooking editor'});await expect(drawer).toBeVisible();expect((await drawer.boundingBox()).height).toBe(1000);expect(await page.locator('.bookings-heading').evaluate(el=>!!el.closest('[inert]'))).toBe(true);}
      // Keyboard selection, selected-customer identity, and in-page quick creation.
      const customerInput=panel.getByRole('combobox',{name:'Search customer',exact:true});
      await customerInput.fill('Meera');await customerInput.press('ArrowDown');await customerInput.press('Enter');
      await expect(panel.getByRole('region',{name:'Selected customer'})).toContainText('Meera Rao');
      await expect(panel.getByRole('region',{name:'Selected customer'})).toContainText('9999999999');
      await panel.getByRole('button',{name:'Change customer',exact:true}).click();
      await panel.getByRole('combobox',{name:'Search customer',exact:true}).fill('Neha Iyer');
      await panel.getByRole('button',{name:/Create customer/}).first().click();
      const customerDialog=page.getByRole('dialog',{name:/^Create customer$/i});
      await expect(customerDialog).toBeVisible();
      await customerDialog.getByLabel('Customer / vendor type',{exact:true}).selectOption('Individual');
      await customerDialog.getByLabel(/Full name/).fill('Neha Iyer');
      await customerDialog.getByRole('button',{name:/^Save customer$/i}).click();
      await expect(customerDialog).toHaveCount(0);
      await expect(panel.getByRole('region',{name:'Selected customer'})).toContainText('Neha Iyer');
      expect(customerWrites).toHaveLength(1);expect(customerWrites[0].roles).toEqual(['Customer']);expect(reservations).toHaveLength(0);
      // Category filtering, real price/duration summary, readonly end time, employee role/avatar.
      await panel.getByLabel('Service category',{exact:true}).selectOption('Hair');
      await panel.getByRole('combobox',{name:'Search service',exact:true}).click();
      await page.getByRole('listbox').getByRole('option',{name:/^Styling/}).click();
      await expect(panel.getByLabel('Selected service summary')).toContainText('45 min');
      await expect(panel.getByLabel('Selected service summary')).toContainText('800');
      await expect(panel.getByRole('button',{name:'Configure service scheduling',exact:true})).toHaveCount(0);
      await expect(panel.getByRole('link',{name:/Manage service scheduling/})).toHaveCount(0);
      await panel.getByLabel('Prebooking employee',{exact:true}).selectOption('2');
      await expect(panel.locator('[aria-label="Selected employee"]')).toContainText('Stylists');
      await expect(panel.locator('[aria-label="Selected employee"] .prebooking-initials')).toHaveText('AE');
      await expect(panel.getByLabel('Booking timezone')).toContainText('UTC');
      await expect(panel.locator('.prebooking-zone-warning')).toContainText('Asia/Kolkata');
      await panel.getByLabel('Prebooking date',{exact:true}).fill(day);await panel.getByLabel('Prebooking start time',{exact:true}).fill('10:00');
      await expect(panel.locator('.prebooking-end')).toContainText('10:45');
      await expect(panel.getByLabel('Prebooking duration',{exact:true})).toHaveCount(0);
      await expect(panel.getByLabel('Booking end time')).toHaveCount(0);
      await expect(panel.getByRole('group',{name:'room resources'})).toContainText('Required');
      await expect(panel.getByRole('group',{name:'equipment resources'})).toContainText('Optional');
      if(await panel.getByRole('button',{name:'Remove Room A',exact:true}).count())await panel.getByRole('button',{name:'Remove Room A',exact:true}).click();
      await expect(confirm).toBeDisabled();
      await panel.getByRole('form',{name:'Create operation'}).evaluate(el=>el.requestSubmit());
      await expect(panel.getByRole('combobox',{name:'Search room',exact:true})).toBeFocused();
      const roomSearch=panel.getByRole('combobox',{name:'Search room',exact:true});
      await roomSearch.fill('Room A');await roomSearch.press('ArrowDown');await roomSearch.press('Enter');
      await expect(confirm).toBeEnabled();
      await expect(panel.locator('[data-availability-state=available]')).toBeVisible();
      // Different employee timezone preserves the instant, and category filtering never expands eligibility.
      await panel.getByLabel('Prebooking employee',{exact:true}).selectOption('3');await expect(panel.getByLabel('Prebooking start time',{exact:true})).toHaveValue('15:30');
      await expect(panel.locator('.prebooking-zone-warning')).toHaveCount(0);
      await panel.getByLabel('Prebooking employee',{exact:true}).selectOption('2');await expect(panel.getByLabel('Prebooking start time',{exact:true})).toHaveValue('10:00');
      manage=true;
      page.once('dialog',d=>d.accept());await panel.getByLabel('Service category',{exact:true}).selectOption('Therapy');
      await expect(panel.getByLabel('Prebooking employee',{exact:true})).toBeDisabled();
      await panel.getByRole('combobox',{name:'Search service',exact:true}).click();await page.getByRole('listbox').getByRole('option',{name:/^Therapy/}).click();
      await expect(panel.getByLabel('Prebooking employee',{exact:true}).locator('option').filter({hasText:'Alex Employee'})).toHaveCount(0);
      await expect(panel.getByRole('button',{name:'Edit duration',exact:true})).toHaveCount(0);
      await expect(panel.getByRole('link',{name:/Manage service scheduling/})).toBeVisible();
      page.once('dialog',d=>d.accept());await panel.getByLabel('Service category',{exact:true}).selectOption('Hair');
      await expect(panel.getByRole('combobox',{name:'Search service',exact:true})).toHaveValue('');
      await panel.getByRole('combobox',{name:'Search service',exact:true}).fill('Styl');await page.getByRole('listbox').getByRole('option',{name:/^Styling/}).click();
      await panel.getByLabel('Employee category',{exact:true}).selectOption('Stylists');
      await expect(panel.getByLabel('Prebooking employee',{exact:true}).locator('option').filter({hasText:'Sam Therapist'})).toHaveCount(0);
      await panel.getByLabel('Prebooking employee',{exact:true}).selectOption('2');await panel.getByLabel('Prebooking date',{exact:true}).fill(day);await panel.getByLabel('Prebooking start time',{exact:true}).fill('10:00');
      if(!await panel.getByRole('button',{name:'Remove Room A',exact:true}).count()){await panel.getByRole('combobox',{name:'Search room',exact:true}).fill('Room A');await page.getByRole('listbox').getByRole('option',{name:/^Room A/}).click();}
      await expect(confirm).toBeEnabled();
      failure=true;await panel.getByRole('button',{name:'Refresh availability',exact:true}).click();await expect(panel.locator('[data-availability-state=error]')).toBeVisible();await expect(confirm).toBeDisabled();
      failure=false;slow=900;await panel.getByRole('button',{name:'Retry availability',exact:true}).click();await expect(panel.locator('[data-availability-state=checking]')).toBeVisible();await expect(confirm).toBeEnabled();slow=0;
      await expect(panel.getByLabel('Visit notes',{exact:true})).toBeHidden();await panel.locator('.prebooking-more>summary').click();await panel.getByLabel('Visit notes',{exact:true}).fill('Quiet room requested');
      await expect(panel.getByText('Private booking link',{exact:true})).toBeVisible();
      if(width===390){await page.keyboard.press('Escape');await expect(panel).toBeHidden();expect(await page.locator('#root').evaluate(el=>el.inert)).toBe(false);await page.getByRole('button',{name:/New prebooking/}).click();await expect(panel.getByLabel('Visit notes',{exact:true})).toHaveValue('Quiet room requested');const drawer=page.getByRole('dialog',{name:'Prebooking editor'});await drawer.locator('button').last().focus();await page.keyboard.press('Tab');expect(await drawer.evaluate(el=>el.contains(document.activeElement))).toBe(true);}
      if(width===1440){await page.setViewportSize({width:390,height:1000});await expect(page.getByRole('dialog',{name:'Prebooking editor'})).toBeVisible();await expect(panel.getByLabel('Visit notes',{exact:true})).toHaveValue('Quiet room requested');await expect(panel.getByLabel('Prebooking employee',{exact:true})).toHaveValue('2');await page.setViewportSize({width:1440,height:1000});await expect(panel.getByRole('button',{name:'Confirm prebooking',exact:true})).toBeEnabled();}
      await page.screenshot({path:`../output/prebooking-polish-${width}.png`,fullPage:true});
      await confirm.click();await expect(panel.getByRole('heading',{name:'Prebooking confirmed'})).toBeFocused();await expect(panel.getByRole('region',{name:'Prebooking confirmation'})).toContainText('Neha Iyer');await expect(panel.getByRole('region',{name:'Prebooking confirmation'})).toContainText('Alex Employee');await expect(panel.getByRole('region',{name:'Prebooking confirmation'})).toContainText('Reference #99');
      await page.screenshot({path:`../output/prebooking-success-${width}.png`,fullPage:true});
      await panel.getByRole('button',{name:'View booking',exact:true}).click();await expect(page.getByRole('region',{name:'Visit details'})).toContainText('Neha Iyer');await page.getByRole('button',{name:'Close dialog',exact:true}).click();
      await panel.getByRole('link',{name:'Open in POS',exact:true}).click();await expect(page.getByRole('heading',{name:'Prebooking at POS',exact:true})).toBeVisible();await expect(page.getByRole('region',{name:'Visit details'})).toContainText('Neha Iyer');await expect(page.getByRole('region',{name:'Visit payments'})).toContainText('800');
      expect(reservations).toHaveLength(1);expect(reservations[0].customer_id).toBe(9);expect(reservations[0].booking.duration_minutes).toBe(45);expect(reservations[0].notes).toBe('Quiet room requested');expect(reservations[0].payments).toBeUndefined();expect(otherWrites).toEqual([]);expect(errors).toEqual([]);
      await page.close();console.log(`PASS prebooking UX 11–25: ${width}px ${width===390?'HRMS':'SRM'}, quick customer creation, required resources, categories, timezones, drawer/focus and existing booking POS handoff`);
    }
  } finally {await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1;});
