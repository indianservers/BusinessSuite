const assert=require('node:assert/strict');
const path=require('node:path');
const {build}=require('esbuild');
const {chromium,expect}=require('playwright/test');
const root=path.resolve(__dirname,'..');
const source=`import React from 'react';import {createRoot} from 'react-dom/client';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import{MemoryRouter}from'react-router-dom';import Page from './src/apps/srm/industry/IndustryOperationsPage';import{useAuthStore}from'./src/store/authStore';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','3');sessionStorage.setItem('suite-pack-context','11');useAuthStore.setState({user:{id:5,email:'doctor@example.invalid',role:'employee',access:{companyId:1,grants:{srm:{enabled:true,permissions:['srm_admin'],actions:['view','edit'],scope:'own'}}}}});const cache=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={['/srm/appointments']}><Page mode="appointments"/></MemoryRouter></QueryClientProvider>);`;
(async()=>{
 const bundle=await build({stdin:{contents:source,resolveDir:root,loader:'tsx'},tsconfig:path.join(root,'tsconfig.json'),bundle:true,write:false,format:'iife',jsx:'automatic',loader:{'.css':'empty','.svg':'dataurl'},banner:{js:'const __proofGlob = () => ({});'},define:{'import.meta.glob':'__proofGlob','process.env.NODE_ENV':'"production"','import.meta.env':'{}'}});
 const browser=await chromium.launch();const context=await browser.newContext();const page=await context.newPage();const requests=[],errors=[];let status='checked_in',revision=1;
 const row=()=>({id:20,kind:'appointment',title:'Reception-created assigned consultation',status,revision,created_by:8,data:{service_name:'Consultation',starts_at:'2026-11-15T10:15:00+00:00',duration_minutes:30,resource_ids:[4],notes:'Clinical note'}});
 try{
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('https://assigned.test/api/v1/**',async route=>{const r=route.request(),u=new URL(r.url());requests.push({method:r.method(),path:u.pathname,kind:u.searchParams.get('kind')});
 if(u.pathname.endsWith('/business-profile/effective'))return route.fulfill({json:{business_type:'hospital',terms:{customer:['Patient','Patients'],provider:['Doctor','Doctors']}}});
 if(u.pathname.endsWith('/industry/capabilities'))return route.fulfill({json:{manage:false,approve:false,invoice:false,self_approve:false,billing:false,collect:false,approve_invoice:false,projects_enabled:false,crm_enabled:false,appointment_actions:['start','complete']}});
 if(u.pathname.endsWith('/industry/records')){assert.equal(u.searchParams.get('kind'),'appointment');return route.fulfill({json:{items:[row()]}});}
 if(u.pathname.endsWith('/records/20/transition')){const body=r.postDataJSON();assert.equal(body.expected_revision,revision);assert.equal(body.status,status==='checked_in'?'in_service':'completed');status=body.status;revision++;return route.fulfill({json:row()});}
 throw Error('Unexpected clinical page request '+r.method()+' '+u.pathname);
 });
 await page.route('https://assigned.test/',route=>route.fulfill({contentType:'text/html',body:'<html><body><div id="root"></div></body></html>'}));
 await page.goto('https://assigned.test/');await page.addScriptTag({content:bundle.outputFiles[0].text});
 await expect(page.getByRole('heading',{name:'Reception-created assigned consultation'})).toBeVisible();
 await expect(page.getByRole('button',{name:'in service',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:/cancel|no.show|Create invoice|New appointment/i})).toHaveCount(0);
 await page.getByRole('button',{name:'in service',exact:true}).click();await expect(page.getByRole('button',{name:'completed',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'completed',exact:true}).click();await expect(page.getByRole('button',{name:'completed',exact:true})).toHaveCount(0);
 assert.equal(status,'completed');assert.equal(requests.filter(r=>r.method==='POST').length,2);assert.ok(!requests.some(r=>r.path.includes('/billing')||r.kind==='resource'));assert.deepEqual(errors,[]);
 console.log('Assigned clinical UI: exact start/complete actions with manage=false; no booking/billing/provider requests; transitions preserve revisions passed.');
 }catch(error){console.error({errors,requests,body:await page.locator('body').innerText()});throw error;}finally{await context.close();await browser.close();}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
