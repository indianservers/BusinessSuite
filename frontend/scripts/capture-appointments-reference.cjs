const fs=require('node:fs'),path=require('node:path');
const {chromium,expect}=require('playwright/test');
const fixtureData=require('./fixtures/appointments-reference-data.cjs');

(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const fixture=path.resolve('scripts',`.appointments-screenshot-${process.pid}.tsx`);
  fs.writeFileSync(fixture,`import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import '@/index.css';import Page from '@/apps/srm/industry/IndustryOperationsPage';import {useAuthStore} from '@/store/authStore';sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('suite-organization','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:${JSON.stringify(fixtureData.profile)}});const scenario=new URLSearchParams(location.search).get('screen');createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/srm/appointments'+(scenario==='resources'?'?resources=1':'')]}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><Page mode="appointments"/></QueryClientProvider></MemoryRouter>);`);
  const {createServer}=await import('vite'),{default:react}=await import('@vitejs/plugin-react');
  const server=await createServer({configFile:false,plugins:[react()],resolve:{alias:{'@':path.resolve('src')}},cacheDir:path.resolve('node_modules/.vite-appointments-images'),optimizeDeps:{entries:[fixture]},server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();const browser=await chromium.launch();
  try{
    for(const screen of ['schedule','resources','booking']){
      const page=await browser.newPage({viewport:{width:1586,height:992},timezoneId:'Asia/Kolkata',deviceScaleFactor:1});
      await page.clock.setFixedTime(new Date('2026-11-17T06:00:00Z'));
      const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
      const resources=screen==='booking'?fixtureData.bookingResources:fixtureData.resources;
      await page.route('**/api/v1/**',async route=>{
        const request=route.request(),url=new URL(request.url()),p=url.pathname;
        let json={items:[],total:0,pages:1};
        if(request.method()!=='GET')writes.push({path:p,method:request.method()});
        if(p.endsWith('/industry/capabilities'))json={manage:true,billing:false,projects_enabled:true,crm_enabled:true};
        else if(p.endsWith('/industry/records'))json={items:url.searchParams.get('kind')==='resource'?resources:screen==='resources'?fixtureData.resourceBookings:screen==='booking'?fixtureData.bookingRows:fixtureData.schedule};
        else if(p.endsWith('/branches/context'))json={company_id:1,selected:1,branches:[{id:1,name:screen==='booking'?'South Delhi (Main)':'Indian Servers - Main',can_write:true,is_active:true}]};
        else if(p.endsWith('/master-data/companies/8'))json=fixtureData.customer;
        else if(p.endsWith('/master-data/companies'))json={items:[fixtureData.customer],total:1,canCreate:true};
        else if(p.endsWith('/catalog/items/service/9'))json=fixtureData.service;
        else if(p.endsWith('/catalog/items'))json={items:[fixtureData.service],pages:1,total:1,facets:{categories:['Hair'],tags:[]}};
        else if(p.endsWith('/service-checkout/options'))json={policy:{id:1,revision:1,active:true,booking_required:true,default_duration_minutes:60,min_duration_minutes:15,max_duration_minutes:120,allow_duration_override:true,required_resource_types:['chair']},specialists:[{eligibility_id:2,eligibility_revision:1,provider_resource_id:1,employee_id:21,employee_name:'Anita Rao',avatar_url:'/images/scheduling/portrait-woman.png',provider_name:'Anita Rao',timezone:'Asia/Kolkata',work_categories:['Stylist']}],resources:resources.filter(r=>r.id>=10&&r.status==='active').map(r=>({id:r.id,name:r.title,...r.data})),has_more:false,branch_timezone:'Asia/Kolkata'};
        else if(p.endsWith('/options/availability'))json={selection_available:true,conflicts:[],resources:[{id:10,available:true}],slots:['12:00','12:30','14:00','14:30','15:00'].map(t=>({starts_at:fixtureData.at(t),label:t})),booked_intervals:[{starts_at:fixtureData.at('13:00'),ends_at:fixtureData.at('13:30')},{starts_at:fixtureData.at('15:00'),ends_at:fixtureData.at('16:00')}]};
        else if(p.includes('/customer-context/'))json={recent:[],suggestions:[]};
        else if(p.endsWith('/notifications/summary'))json={groups:[{module:'srm',url:'/srm/appointments',count:1}]};
        await route.fulfill({json});
      });
      await page.route('**/appointments-image?*',r=>r.fulfill({contentType:'text/html',body:`<meta charset="utf-8"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}')</script>`}));
      await page.goto(server.resolvedUrls.local[0]+`appointments-image?screen=${screen}`);
      if(screen==='resources'){
        await expect(page.getByRole('heading',{name:'Available resources',exact:true})).toBeVisible({timeout:120000});
        await page.getByRole('button',{name:'Edit Treatment Room 01',exact:true}).click();
        await page.getByLabel('Actions for Treatment Room 01').click();
        await expect(page.locator('.resource-action-menu').filter({visible:true})).toBeVisible();
      }else{
        await expect(page.getByRole('heading',{name:'Upcoming appointments'})).toBeVisible({timeout:120000});
        if(screen==='booking'){
          await page.getByRole('button',{name:'Calendar',exact:true}).click();
          await page.getByRole('button',{name:'New appointment',exact:true}).click();
          const modal=page.getByRole('dialog',{name:'Prebooking editor'});
          await modal.getByRole('combobox',{name:'Search customer',exact:true}).fill('Meera');
          await page.getByRole('listbox').getByRole('option').filter({hasText:'Meera Nair'}).click();
          await modal.getByRole('combobox',{name:'Search service',exact:true}).click();
          await page.getByRole('listbox').getByRole('option').filter({hasText:'Hair styling'}).click();
          await modal.getByLabel('Prebooking employee',{exact:true}).selectOption('2');
          await modal.getByLabel('Prebooking resource',{exact:true}).selectOption('10');
          await modal.getByLabel('Prebooking date',{exact:true}).fill('2026-11-17');
          await modal.locator('.reference-start-times').getByRole('button',{name:'2:00 PM',exact:true}).click();
          await expect(modal.getByRole('button',{name:'Confirm appointment',exact:true})).toBeEnabled();
          await expect(modal.getByRole('complementary',{name:'Booking summary'})).toContainText('Chair 01');
        }
      }
      await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(image=>image.complete?Promise.resolve():new Promise(resolve=>{image.onload=resolve;image.onerror=resolve;})));if(document.activeElement instanceof HTMLElement)document.activeElement.blur();for(const node of document.querySelectorAll('.appointment-reference-body,.prebooking-reference-modal'))node.scrollTop=0;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
      await page.screenshot({path:`../output/appointments-reference-${screen}-1586.png`,animations:'disabled',fullPage:false});
      const geometry=await page.evaluate(()=>Object.fromEntries(['.appointment-reference-sidebar','.appointment-reference-topbar','.appointment-gantt-scroll','.appointment-reference-upcoming','.resource-table-scroll','.resource-editor','.prebooking-reference-modal','.booking-reference-summary'].map(s=>{const r=document.querySelector(s)?.getBoundingClientRect();const node=document.querySelector(s);return [s,r?{x:r.x,y:r.y,width:r.width,height:r.height,font:getComputedStyle(node).font,color:getComputedStyle(node).color}:null];})));
      fs.writeFileSync(`../output/appointments-reference-${screen}-geometry.json`,JSON.stringify(geometry,null,2));
      expect(writes).toEqual([]);expect(errors).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.close();
    }
    console.log('PASS three screenshot-state captures: same reference records/assets, 1586×992, no writes, no browser exceptions');
  }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(error=>{console.error(error);process.exitCode=1;});
