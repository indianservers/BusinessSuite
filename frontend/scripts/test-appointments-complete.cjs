const fs = require('node:fs');
const path = require('node:path');
const { chromium, expect } = require('playwright/test');

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const fixture = path.resolve('scripts', `.appointments-complete-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import '@/index.css';import Page from '@/apps/srm/industry/IndustryOperationsPage';import {useAuthStore} from '@/store/authStore';sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('suite-organization','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,name:'Aditi Sharma',email:'aditi@example.invalid',role:'super_admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/srm/appointments']}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><Page mode="appointments"/></QueryClientProvider></MemoryRouter>);`);
  const { createServer } = await import('vite');
  const { default: react } = await import('@vitejs/plugin-react');
  const server = await createServer({ configFile:false, plugins:[react()], resolve:{alias:{'@':path.resolve('src')}}, cacheDir:path.resolve('node_modules/.vite-appointments-complete'), optimizeDeps:{entries:[fixture]}, server:{host:'127.0.0.1',port:0,hmr:false,watch:null} });
  await server.listen();
  const browser = await chromium.launch();
  try {
    for(const width of (process.env.APPOINTMENTS_QA_WIDTHS || '1586,390').split(',').map(Number)) {
      const page = await browser.newPage({viewport:{width,height:width===390?844:992},timezoneId:'Asia/Kolkata'});
      await page.clock.setFixedTime(new Date('2026-11-17T06:00:00Z'));
      const errors=[], writes=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
      const base = {timezone:'Asia/Kolkata',opens:'09:00',closes:'19:00',weekdays:[0,1,2,3,4],capacity:1,assigned_color:'Lavender'};
      let resources = [
        ...['Anita Rao','Rahul Kumar','Priya Shah'].map((title,i)=>({id:i+1,title,kind:'resource',revision:1,status:'active',data:{...base,resource_type:'provider',employee_id:i+21}})),
        ...['Chair 01','Chair 02','Treatment Room 01','Consultation Room','Meeting Room','Equipment Kit','Studio Room','Chair 03','Equipment 02'].map((title,i)=>({id:i+10,title,kind:'resource',revision:1,status:i===5?'maintenance':'active',data:{...base,resource_type:i<2||i===7?'chair':i===5||i===8?'equipment':'room',location:i<2||i===5?'Ground floor':'First floor'}})),
      ];
      let appointments = [
        {id:100,title:'Meera Nair',kind:'appointment',revision:1,status:'checked_in',customer_id:8,data:{customer_name:'Meera Nair',service_name:'Hair styling',starts_at:'2026-11-17T03:30:00Z',duration_minutes:60,resource_ids:[1,10]}},
        {id:101,title:'Arjun Rao',kind:'appointment',revision:1,status:'booked',data:{customer_name:'Arjun Rao',service_name:'Consultation',starts_at:'2026-11-17T04:15:00Z',duration_minutes:90,resource_ids:[2,13]}},
        {id:102,title:'Kavya Reddy',kind:'appointment',revision:1,status:'completed',data:{customer_name:'Kavya Reddy',service_name:'Therapy',starts_at:'2026-11-17T05:00:00Z',duration_minutes:90,resource_ids:[3,12]}},
        {id:103,title:'Sneha Das',kind:'appointment',revision:1,status:'booked',data:{customer_name:'Sneha Das',service_name:'Consultation',starts_at:'2026-11-17T08:30:00Z',duration_minutes:45,resource_ids:[3,13]}},
      ];
      const customer={id:8,name:'Meera Nair',phone:'9876543210',phone_country_code:'+91',entityKind:'Individual',roles:['Customer']};
      const service={id:9,kind:'service',name:'Hair styling',code:'HAIR',category:'Hair',price:1200,currency:'INR',tax:0};
      let stale=false,failedAvailability=false,bookingFails=false;
      await page.route('**/api/v1/**', async route=>{
        const req=route.request(),u=new URL(req.url()),p=u.pathname;let json={items:[],total:0,pages:1};
        if(req.method()!=='GET')writes.push({path:p,body:req.postDataJSON()});
        if(p.endsWith('/industry/capabilities'))json={manage:true,billing:false,projects_enabled:false,crm_enabled:false};
        else if(p.endsWith('/industry/records'))json={items:u.searchParams.get('kind')==='resource'?resources:appointments};
        else if(/\/industry\/resources\/\d+$/.test(p)&&req.method()==='PUT'){
          const data=req.postDataJSON(),id=Number(p.split('/').pop()),row=resources.find(r=>r.id===id);
          if(stale)return route.fulfill({status:409,json:{detail:'Record changed. Reload before continuing'}});
          if(data.status==='archived'&&id===12)return route.fulfill({status:409,json:{detail:'This resource has upcoming bookings. Reschedule them before deleting it.'}});
          row.title=data.title;row.status=data.status;row.revision++;row.data={...row.data,...data};json=row;
        }else if(p.endsWith('/industry/resources')&&req.method()==='POST'){
          const data=req.postDataJSON();json={id:50,kind:'resource',title:data.title,status:data.initial_status || 'active',revision:1,data};resources.push(json);
        }else if(p.endsWith('/prebooking-workflows/appointments/110/summary'))json={row:appointments.find(r=>r.id===110),employee:'Anita Rao',employee_id:21,provider_resource_id:1,timezone:'Asia/Kolkata',resources:['Chair 01']};
        else if(p.endsWith('/branches/context'))json={company_id:1,selected:1,all_branches:false,branches:[{id:1,name:'Indian Servers - Main',can_write:true,is_active:true}]};
        else if(p.endsWith('/master-data/companies/8'))json=customer;
        else if(p.endsWith('/master-data/companies'))json={items:[customer],total:1,canCreate:true};
        else if(p.endsWith('/catalog/items/service/9'))json=service;
        else if(p.endsWith('/catalog/items'))json={items:[service],total:1,pages:1,facets:{categories:['Hair'],tags:[]}};
        else if(p.endsWith('/service-checkout/options'))json={policy:{id:1,revision:1,active:true,booking_required:true,default_duration_minutes:60,min_duration_minutes:15,max_duration_minutes:120,allow_duration_override:true,required_resource_types:['chair']},specialists:[{eligibility_id:2,eligibility_revision:1,provider_resource_id:1,employee_id:21,employee_name:'Anita Rao',timezone:'Asia/Kolkata',work_categories:['Stylist']}],resources:resources.filter(r=>r.id>=10&&r.status==='active').map(r=>({id:r.id,name:r.title,...r.data})),has_more:false,branch_timezone:'Asia/Kolkata'};
        else if(p.endsWith('/options/availability')){if(failedAvailability)return route.fulfill({status:503,json:{detail:'Availability temporarily unavailable'}});json={selection_available:true,conflicts:[],resources:resources.filter(r=>r.id>=10).map(r=>({id:r.id,available:true})),slots:['06:30','07:00','08:30','09:00','09:30'].map(t=>({starts_at:`2026-11-17T${t}:00Z`,label:t}))};}
        else if(p.endsWith('/industry/appointments')&&req.method()==='POST'){if(bookingFails)return route.fulfill({status:409,json:{detail:'This time has just been booked. Choose another available time.'}});const data=req.postDataJSON();json={id:110,title:'Hair styling',kind:'appointment',status:'booked',revision:1,customer_id:8,data:{...data,customer_name:customer.name,service_name:service.name}};appointments.push(json);}
        else if(p.includes('/customer-context/'))json={recent:[],suggestions:[]};
        await route.fulfill({json});
      });
      await page.route('**/appointments-complete',route=>route.fulfill({contentType:'text/html',body:`<meta charset="utf-8"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}')</script>`}));
      await page.goto(server.resolvedUrls.local[0]+'appointments-complete');
      async function geometry(name) { await page.evaluate(async()=>{await document.fonts.ready;if(document.activeElement instanceof HTMLElement&&document.activeElement.closest('.resource-editor'))document.activeElement.blur();for(const el of document.querySelectorAll('.appointment-reference-body,.prebooking-reference-modal'))el.scrollTop=0;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});const data=await page.evaluate(()=>{const selectors=['.appointment-reference-topbar','.appointment-reference-breadcrumb','.resource-page-heading','.resource-statistics','.resource-filters','.resource-table-scroll','.resource-pagination','.resource-editor header','.resource-editor form>fieldset','.resource-editor form>footer','.appointment-reference-datebar','.appointment-reference-filters','.appointment-reference-views','.appointment-gantt-scroll','.appointment-reference-upcoming','.prebooking-reference-modal','.prebooking-reference-header','.reference-appointment-form','.booking-reference-summary','.reference-appointment-form>.prebooking-footer'];return Object.fromEntries(selectors.map(selector=>{const node=document.querySelector(selector);if(!node)return [selector,null];const r=node.getBoundingClientRect(),c=getComputedStyle(node);return [selector,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,fontFamily:c.fontFamily}];}));});fs.writeFileSync(path.resolve('../output',`appointments-geometry-${name}-${width}.json`),JSON.stringify(data,null,2)); }

      await expect(page.locator('.appointment-timeline')).toBeVisible({timeout:120000});await page.getByRole('button',{name:'Gantt',exact:true}).click();await expect(page.locator('.appointment-reference-upcoming h2')).toBeVisible();
      await geometry('schedule');await page.screenshot({path:`../output/appointments-complete-schedule-${width}.png`,fullPage:false,animations:'disabled'});await page.locator('.appointment-gantt-event').first().click();await expect(page.locator('#booking-record-100')).toBeVisible();await page.locator('.appointment-record-details>summary').click();
      async function nav(name){if(width===390){await page.getByRole('navigation',{name:'SRM mobile navigation'}).getByRole('link',{name:name==='Available resources'?'Resources':name,exact:true}).click();}else await page.getByRole('navigation',{name:'Schedule navigation'}).getByRole('button',{name,exact:true}).click();}
      await nav('Available resources');
      await expect(page.getByRole('heading',{name:'Available resources',exact:true})).toBeVisible();
      if(width===390){
        const categories=page.locator('.resource-mobile-categories');await categories.getByRole('button',{name:'Chairs',exact:true}).click();await expect(page.locator('.resource-table tbody tr')).toHaveCount(3);await categories.getByRole('button',{name:'All',exact:true}).click();
        async function filterResource(location,status){await page.getByRole('button',{name:'Resource filters',exact:true}).click();const sheet=page.getByRole('dialog');await sheet.getByLabel('Mobile resource location').selectOption(location);await sheet.getByLabel('Mobile resource status').selectOption(status);await sheet.getByRole('button',{name:'Apply filters',exact:true}).click();}
        await filterResource('First floor','');await expect(page.locator('.resource-table tbody tr')).toHaveCount(6);await filterResource('','Maintenance');await expect(page.locator('.resource-table tbody tr')).toHaveCount(1);await filterResource('','');
      }else{
      await page.getByLabel('Resource type filter').selectOption('chair');await expect(page.locator('.resource-table tbody tr')).toHaveCount(3);await page.getByLabel('Resource type filter').selectOption('');await page.getByLabel('Resource location filter').selectOption('First floor');await expect(page.locator('.resource-table tbody tr')).toHaveCount(6);await page.getByLabel('Resource location filter').selectOption('');await page.getByLabel('Resource status filter').selectOption('Maintenance');await expect(page.locator('.resource-table tbody tr')).toHaveCount(1);await page.getByLabel('Resource status filter').selectOption('');}
      await page.getByLabel('Next resources').click();await expect(page.locator('.resource-table tbody tr')).toHaveCount(3);await page.getByLabel('Previous resources').click();await page.getByLabel('Search resources').fill('Treatment');
      await expect(page.locator('.resource-table tbody tr')).toHaveCount(1);if(width===390){await page.getByLabel('Actions for Treatment Room 01').click();await page.getByRole('button',{name:'Edit resource',exact:true}).click();}else await page.getByRole('button',{name:'Edit Treatment Room 01',exact:true}).click();
      const editor=page.locator('.resource-editor');
      await expect(editor.getByLabel('Resource name',{exact:true})).toHaveValue('Treatment Room 01');
      await page.getByLabel('Search resources').fill('');if(width>760)await page.getByLabel('Actions for Treatment Room 01').click();await editor.getByLabel('Resource type',{exact:true}).focus();await geometry('resources');await page.screenshot({path:`../output/appointments-complete-resources-${width}.png`,fullPage:false,animations:'disabled'});
      await editor.getByLabel('Resource name',{exact:true}).fill('Treatment Room 02');
      await editor.getByLabel('Assigned color').selectOption('Mint');
      await editor.getByRole('button',{name:'Mon',exact:true}).click();
      await editor.getByRole('switch',{name:'Resource active'}).click();
      stale=true;await editor.getByRole('button',{name:'Save changes'}).click();await expect(editor.getByRole('alert')).toContainText('Record changed');await expect(editor.getByLabel('Resource name',{exact:true})).toHaveValue('Treatment Room 02');
      stale=false;await editor.getByRole('button',{name:'Save changes'}).click();await expect(editor).toHaveCount(0);
      const write=writes.filter(w=>w.path.endsWith('/resources/12')).at(-1).body;expect(write.assigned_color).toBe('Mint');expect(write.status).toBe('inactive');expect(write.weekdays).not.toContain(0);
      await page.getByLabel('Search resources').fill('');
      await page.getByRole('button',{name:'Add resource',exact:true}).filter({visible:true}).first().click();await editor.getByLabel('Resource name',{exact:true}).fill('New Studio');await editor.getByLabel('Resource location',{exact:true}).fill('Second floor');await editor.getByRole('button',{name:'Save changes'}).click();await expect(editor).toHaveCount(0);
      await page.getByLabel('Search resources').fill('New Studio');await expect(page.locator('.resource-table tbody tr')).toHaveCount(1);
      await page.getByLabel('Actions for New Studio').click();await page.getByRole('button',{name:'Delete resource',exact:true}).click();const remove=page.getByRole('dialog');await remove.getByRole('button',{name:'Delete resource',exact:true}).click();await expect(remove).toHaveCount(0);await expect(page.locator('.resource-table tbody tr')).toHaveCount(0);
      await nav('Schedule');await page.getByRole('button',{name:'Calendar',exact:true}).click();
      await page.getByRole('button',{name:'New appointment',exact:true}).click();
      const modal=page.getByRole('dialog',{name:'Prebooking editor'});async function submitBooking(){for(let step=0;step<12&&!await modal.locator('button[type=submit]').isVisible();step++){const next=modal.getByRole('button',{name:'Next step',exact:true});if(!await next.isEnabled())break;await next.click();}await modal.locator('button[type=submit]').click();}
      await modal.getByRole('combobox',{name:'Search customer',exact:true}).fill('Meera');await page.getByRole('option').filter({hasText:'Meera Nair'}).click();
      await modal.getByRole('combobox',{name:'Search service',exact:true}).click();await page.getByRole('listbox').getByRole('option').filter({hasText:'Hair styling'}).click();
      await modal.getByLabel('Prebooking employee',{exact:true}).selectOption('2');await modal.getByLabel('Prebooking resource',{exact:true}).selectOption('10');
      await modal.getByLabel('Prebooking date',{exact:true}).fill('2026-11-17');await modal.locator('.reference-more-options>summary').click();await modal.locator('.reference-custom-time>summary').click();await modal.getByLabel('Prebooking start time',{exact:true}).fill('14:00');await modal.locator('.reference-custom-time>summary').click();await modal.locator('.reference-more-options>summary').click();
      const summary=modal.getByRole('complementary',{name:'Booking summary'});
      await expect(summary).toContainText('Meera Nair');await expect(summary).toContainText('Anita Rao');await expect(summary).toContainText('Chair 01');await expect(summary.getByLabel('Booking estimated total')).toContainText('1,200');await expect(modal.locator('.reference-start-times button[aria-pressed=true]')).toHaveCount(1);
      await modal.getByLabel('Appointment notes',{exact:true}).fill('Customer prefers a quiet space.');
      await modal.getByRole('button',{name:'SMS',exact:true}).click();
      await expect(modal.locator('button[type=submit]')).toBeEnabled();
      await geometry('booking');await page.screenshot({path:`../output/appointments-complete-booking-${width}.png`,fullPage:false,animations:'disabled'});
      await modal.getByLabel('Prebooking duration',{exact:true}).selectOption('90');await expect(summary).toContainText('90 minutes');
      failedAvailability=true;await modal.locator('.reference-more-options>summary').click();await modal.locator('.reference-custom-time>summary').click();await modal.getByLabel('Prebooking start time',{exact:true}).fill('15:00');await expect(modal.getByRole('button',{name:'Retry availability',exact:true})).toBeVisible();await expect(modal.locator('button[type=submit]')).toBeDisabled();
      failedAvailability=false;await modal.getByRole('button',{name:'Retry availability',exact:true}).click();await expect(modal.locator('button[type=submit]')).toBeEnabled();
      bookingFails=true;await submitBooking();await expect(modal.locator('.reference-booking-error')).toContainText('This time has just been booked');bookingFails=false;await expect(modal.locator('button[type=submit]')).toBeEnabled();await submitBooking();await expect(modal.getByRole('heading',{name:'Prebooking confirmed'})).toBeVisible();await modal.getByRole('button',{name:'Review selected confirmation messages'}).click();await expect(modal.getByRole('link',{name:'Open WhatsApp confirmation draft'})).toHaveAttribute('href',/^https:\/\/wa.me\/919876543210\?text=/);await expect(modal.getByLabel('Selected confirmation message')).not.toContainText('Customer prefers a quiet space.');
      const saved=writes.find(w=>w.path.endsWith('/industry/appointments')).body;expect(saved.booking.duration_minutes).toBe(90);expect(saved.confirmation_channels).toEqual(['whatsapp']);expect(saved.notes).toBe('Customer prefers a quiet space.');await modal.getByRole('button',{name:'More booking actions'}).count();
      expect(errors).toEqual([]);expect(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&getComputedStyle(e).position!=='fixed').slice(0,8).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right}))}))).toMatchObject({scroll:width});await page.close();
    }
    console.log('PASS complete appointments: resource create/edit/status/color/working days/stale conflicts/delete, booking live summary/duration/price/availability failure and retry/confirmation on desktop and mobile');
  } finally {await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1;});
