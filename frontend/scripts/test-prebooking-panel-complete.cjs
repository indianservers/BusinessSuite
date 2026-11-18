const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect: base } = require('playwright/test');
const expect = base.configure({ timeout: 15000 });

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const fixture = path.resolve('scripts', `.prebooking-complete-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import '@/index.css';import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter,Routes,Route} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import Workspace from '@/shared/scheduling/ServiceSchedulingWorkspace';import POS from '@/apps/srm/pages/SRMPOSPage';import {useAuthStore} from '@/store/authStore';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={[location.search.includes('hrms')?'/hrms/service-scheduling':'/srm/service-scheduling']}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><Routes><Route path="/srm/pos/terminal" element={<POS/>}/><Route path="*" element={<Workspace/>}/></Routes></QueryClientProvider></MemoryRouter>);`);
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const server = await createServer({ configFile: false, plugins: [react()], resolve: { alias: { '@': path.resolve('src') } }, cacheDir: path.resolve('node_modules/.vite-prebooking-complete'), optimizeDeps: { entries: [fixture] }, server: { host: '127.0.0.1', port: 0, hmr: false, watch: null } });
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [1440,390]) {
      const page = await browser.newPage({viewport:{width,height:1000},timezoneId:'UTC'});
      const errors=[], reservations=[], customerWrites=[], otherWrites=[];
      let manage=false, failure=false, slow=0, created, uncertain=true, price=800, statusConfirmed=false;
      const day=new Date(Date.now()+2*86400000).toISOString().slice(0,10);
      const meera={id:8,name:'Meera Rao',phone:'9999999999',phone_country_code:'+91',entityKind:'Individual',roles:['Customer']};
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
        else if(/\/catalog\/items\/service\/\d+$/.test(p)) json={...services.find(s=>s.id===Number(p.split('/').pop())),price};
        else if(p.endsWith('/catalog/items')){const category=url.searchParams.get('category'),search=url.searchParams.get('search')||'';json={items:services.filter(s=>(!category||s.category===category)&&(!search||s.name.toLowerCase().includes(search.toLowerCase()))),pages:1,total:2,facets:{categories:['Hair','Therapy'],tags:[]}};}
        else if(p.endsWith('/service-checkout/options')){const therapy=url.searchParams.get('service_id')==='10',search=url.searchParams.get('search')||'';json={policy:{id:1,revision:1,active:true,booking_required:true,default_duration_minutes:therapy?60:45,min_duration_minutes:15,max_duration_minutes:120,allow_duration_override:!therapy,required_resource_types:['room'],employee_categories:therapy?['Therapists']:['Stylists','Therapists']},specialists:people.filter(s=>(!therapy||s.eligibility_id===3)&&(!search||s.employee_name.toLowerCase().includes(search.toLowerCase()))),resources:[{id:30,name:'Room A',resource_type:'room'},{id:31,name:'Room B',resource_type:'room'},{id:40,name:'Projector',resource_type:'equipment'}],has_more:false,can_configure:manage,branch_timezone:'Asia/Kolkata'};}
        else if(p.endsWith('/options/availability') && url.searchParams.get('discover')==='true')json={choices:[{...people[0],starts_at:`${day}T10:00:00Z`,resource_ids:[30],resources:['Room A'],changed_resources:1}],checked_combinations:2,partial:false,next_employee_offset:null,next_resource_offset:null,searched_days:Number(url.searchParams.get('search_days')||1)};
        else if(p.includes('/appointments/requests/'))json=statusConfirmed?{state:'confirmed',appointment:savedRow}:{state:'not_found'};
        else if(p.includes('/appointments/customer-context/'))json={recent:[{...savedRow,id:77}],upcoming:[savedRow],possible_duplicates:url.searchParams.get('service_id')?[savedRow]:[],preferred_provider:{name:'Alex Employee'}};
        else if(p.endsWith('/options/availability')){const fails=failure;if(slow)await new Promise(resolve=>setTimeout(resolve,slow));if(fails)return route.fulfill({status:503,json:{detail:'Temporary availability failure'}});json={selection_available:url.searchParams.getAll('resource_ids').includes('30')||url.searchParams.getAll('resource_ids').includes('31'),conflicts:[],resources:[{id:30,available:true},{id:31,available:true}],slots:[{starts_at:`${url.searchParams.get('day')}T11:00:00Z`,label:'11:00'}]};}
        else if(p.endsWith('/employees/planned-services'))json={timezone:'UTC',items:[],next_cursor:null,filter_options:{employees:[{id:22,name:'Alex Employee'}],services:[],employees_complete:true,services_complete:true}};
        else if(p.endsWith('/industry/appointments') && req.method()==='POST'){reservations.push(req.postDataJSON());if(uncertain){await new Promise(r=>setTimeout(r,600));return route.fulfill({status:503,json:{detail:'Unknown save outcome'}});}json=savedRow;}
        else if(p.endsWith('/prebooking-workflows/appointments/99/summary'))json={row:savedRow,employee:'Alex Employee',timezone:'UTC',resources:['Room A']};
        else if(p.endsWith('/industry/appointments/99'))json=savedRow;
        else if(p.endsWith('/appointments/99/billing'))json={appointment_id:99,revision:1,currency:'INR',total:'800',paid:'0',advance:'0',balance:'800',invoice:null,receipts:[]};
        else if(req.method()!=='GET')otherWrites.push({path:p,body:req.postDataJSON()});
        await route.fulfill({json});
      });
      await page.route('**/prebooking-complete?*',route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>`}));
      await page.goto(server.resolvedUrls.local[0]+`prebooking-complete?module=${width===390?'hrms':'srm'}`);
      await expect(page.getByRole('heading',{name:'Appointment Scheduler',exact:true})).toBeVisible({timeout:60000});
      if(width===390)await page.getByRole('button',{name:/New prebooking/}).click();
      const panel=page.getByRole('complementary',{name:'New prebooking'}),confirm=panel.getByRole('button',{name:'Confirm prebooking',exact:true});
      if(width===390){const drawer=page.getByRole('dialog',{name:'Prebooking editor'});await expect(drawer).toBeVisible();expect((await drawer.boundingBox()).height).toBe(1000);expect(await page.locator('.bookings-heading').evaluate(el=>!!el.closest('[inert]'))).toBe(true);}
      const openPanel=async()=>{if(width===390 && !await panel.isVisible())await page.getByRole('button',{name:/New prebooking/}).click();};
      await panel.getByRole('combobox',{name:'Search customer',exact:true}).fill('Meera');
      await expect(page.getByRole('listbox')).toContainText('9999');
      await expect(page.getByRole('listbox')).toContainText('Customer #8');
      await page.getByRole('listbox').getByRole('option',{name:/Meera/}).click();
      await panel.getByText('Customer visits and preferences',{exact:true}).click();
      await expect(panel.getByLabel('Customer booking context')).toContainText('Suggested provider from recent visits: Alex');
      await panel.getByRole('combobox',{name:'Search service',exact:true}).fill('Sty');await page.getByRole('listbox').getByRole('option',{name:/^Styling/}).click();
      await expect(panel.getByText(/Possible duplicate:/)).toBeVisible();
      await expect(panel.getByLabel('Selected service summary')).toContainText('Estimated price before tax');
      await panel.getByRole('button',{name:/Any qualified employee/}).click();
      await panel.getByLabel('Prebooking date',{exact:true}).fill(day);
      await panel.getByRole('button',{name:/Find any available required resource/}).click();
      await panel.getByRole('button',{name:/Choose Alex Employee/}).click();
      await expect(panel.getByLabel('Prebooking employee',{exact:true})).toHaveValue('2');
      await expect(panel.getByRole('button',{name:'Remove Room A',exact:true})).toBeVisible();
      await expect(confirm).toBeEnabled();
      await expect(panel.getByRole('region',{name:'Available times'})).toBeVisible();
      await expect(panel.getByText(/No extra setup\/cleanup buffer/)).toBeVisible();
      expect(await panel.getByLabel('Prebooking date',{exact:true}).getAttribute('max')).toBeTruthy();
      await panel.locator('.prebooking-more>summary').click();await panel.getByLabel('Visit notes',{exact:true}).fill('Restored note');
      await page.reload();await openPanel();
      await expect(panel.getByLabel('Prebooking employee',{exact:true})).toHaveValue('2');
      await expect(panel.getByLabel('Prebooking date',{exact:true})).toHaveValue(day);
      await expect(panel.getByRole('button',{name:'Remove Room A',exact:true})).toBeVisible();
      await panel.locator('.prebooking-more>summary').click();await expect(panel.getByLabel('Visit notes',{exact:true})).toHaveValue('Restored note');
      await expect(confirm).toBeEnabled();
      price=900;await panel.getByRole('button',{name:'Refresh service quote',exact:true}).click();
      await expect(panel.getByRole('button',{name:'Accept updated estimate'})).toBeVisible();await expect(confirm).toBeDisabled();
      await panel.getByRole('button',{name:'Accept updated estimate'}).click();await expect(confirm).toBeEnabled();
      await page.screenshot({path:`../output/prebooking-complete-${width}.png`,fullPage:true});
      await confirm.click();await expect(panel.getByLabel('Prebooking date',{exact:true})).toBeDisabled();
      await expect(panel.getByRole('button',{name:'Check booking status'})).toBeVisible();
      await panel.getByRole('button',{name:'Check booking status'}).click();await expect(panel.getByText(/No confirmed booking was found yet/)).toBeVisible();
      await page.reload();await openPanel();await expect(panel.getByLabel('Prebooking date',{exact:true})).toBeDisabled();
      uncertain=false;await panel.getByRole('button',{name:'Retry original request'}).click();
      await expect(panel.getByRole('heading',{name:'Prebooking confirmed'})).toBeVisible();expect(reservations).toHaveLength(2);expect(reservations[1]).toEqual(reservations[0]);
      await panel.getByText('More booking actions',{exact:true}).click();const downloadPromise=page.waitForEvent('download');await panel.getByRole('button',{name:'Download calendar event'}).click();const download=await downloadPromise;const calendar=fs.readFileSync(await download.path(),'utf8');expect(calendar).toContain('BEGIN:VCALENDAR');expect(calendar).toContain(`DTSTART:${day.replaceAll('-','')}T100000Z`);expect(calendar).toContain('DTEND:');
      await panel.getByRole('button',{name:'Preview confirmation'}).click();await expect(panel.getByLabel('Confirmation preview')).toContainText('Delivery is not tracked here');await expect(panel.getByRole('link',{name:'Open SMS draft'})).toHaveAttribute('href',/^sms:/);
      await panel.getByRole('button',{name:'Repeat as new draft'}).click();await expect(panel.getByLabel('Selected customer')).toContainText('Meera Rao');await expect(panel.getByLabel('Prebooking employee',{exact:true})).toHaveValue('2');await expect(confirm).toBeEnabled();
      uncertain=true;await confirm.click();await expect(panel.getByRole('button',{name:'Check booking status'})).toBeVisible();statusConfirmed=true;await panel.getByRole('button',{name:'Check booking status'}).click();await expect(panel.getByRole('heading',{name:'Prebooking confirmed'})).toBeVisible();
      await panel.getByText('More booking actions',{exact:true}).click();await panel.getByRole('button',{name:'Book another for this customer'}).click();await expect(panel.getByLabel('Selected customer')).toContainText('Meera Rao');await expect(panel.getByRole('combobox',{name:'Search service',exact:true})).toHaveValue('');
      expect(otherWrites).toEqual([]);expect(errors).toEqual([]);
      await page.close();console.log(`PASS complete prebooking UX: ${width}px ${width===390?'HRMS':'SRM'}, draft restore, discovery, quote changes, immutable retries, repeat, preview and calendar export`);
    }
  } finally {await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1;});
