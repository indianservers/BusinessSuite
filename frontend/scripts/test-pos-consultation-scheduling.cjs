const fs = require('node:fs');
const path = require('node:path');
const {chromium, expect} = require('playwright/test');

(async () => {
  process.chdir(path.resolve(__dirname, '..'));
  const fixture = path.resolve('scripts', `.consultation-${process.pid}.tsx`);
  fs.writeFileSync(fixture, `import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import EmployeeCategories from '@/shared/EmployeeCategories';import Scheduling from '@/apps/srm/industry/POSServiceScheduling';import {useAuthStore} from '@/store/authStore';useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true}});function App(){const [categories,setCategories]=useState([]);const [booking,setBooking]=useState();return <><EmployeeCategories create options={["Consultants","Stylists"]} value={categories} onChange={setCategories}/><output id="categories">{JSON.stringify(categories)}</output><Scheduling productId={9} lineKey="consultation" value={booking} onChange={setBooking}/><output id="booking">{JSON.stringify(booking)}</output></>}createRoot(document.getElementById('root')).render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><App/></QueryClientProvider></MemoryRouter>);`);
  const {createServer} = await import('vite');
  const server = await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();
  const browser = await chromium.launch();
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({viewport:{width,height:1000}});
      await page.route('**/api/v1/**', route => route.fulfill({json:{policy:{id:4,revision:1,booking_required:false,default_duration_minutes:30,min_duration_minutes:5,max_duration_minutes:120,allow_duration_override:true,active:true},specialists:[1,2].map(id=>({eligibility_id:id,eligibility_revision:1,provider_resource_id:id+10,employee_id:id+20,employee_name:`Employee ${id}`,provider_name:'Consultations',timezone:'UTC'})),resources:[{id:30,name:'Consultation room',resource_type:'room'}],has_more:false}}));
      await page.route('**/options/availability*', route=>route.fulfill({json:{timezone:'UTC',slots:[],resources:[],selection_available:null}}));
      await page.route('**/consultation-qa', route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>`}));
      await page.goto(server.resolvedUrls.local[0]+'consultation-qa');
      await page.getByRole('checkbox',{name:'Consultants',exact:true}).check();
      await page.getByRole('checkbox',{name:'Stylists',exact:true}).check();
      await page.getByLabel('New employee category').fill('Senior staff');
      await page.getByRole('button',{name:'Add category',exact:true}).click();
      expect(JSON.parse(await page.locator('#categories').textContent())).toEqual(['Consultants','Stylists','Senior staff']);
      await page.getByText('Schedule this service',{exact:true}).click();
      await page.getByLabel('Specialist consultation',{exact:true}).selectOption('2');
      await page.getByLabel('Booking date consultation',{exact:true}).fill('2030-12-20');
      await page.getByLabel('Booking time consultation',{exact:true}).fill('10:00');
      await page.getByLabel('Booking end date consultation',{exact:true}).fill('2030-12-20');
      await page.getByLabel('Booking end time consultation',{exact:true}).fill('10:45');
      await page.getByRole('checkbox',{name:/Consultation room/}).check();
      await page.getByRole('button',{name:'Use these booking details',exact:true}).click();
      await expect(page.locator('#booking')).toContainText('"employee_id":22');
      const booking = JSON.parse(await page.locator('#booking').textContent());
      expect(booking.duration_minutes).toBe(45);
      expect(booking.additional_resource_ids).toEqual([30]);
      expect(booking.starts_at).toBe('2030-12-20T10:00:00.000Z');
      await expect(page.getByRole('status').filter({hasText:'Scheduled:'})).toContainText('Employee 2');
      await page.close();
    }
    console.log('PASS optional POS consultations: multiple employees, explicit From/To interval, room and cart summary at phone and desktop widths');
  } finally {await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(error=>{console.error(error);process.exitCode=1;});
