const fs=require('node:fs'),path=require('node:path'),{chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-lead-kpis.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/apps/crm/leads/LeadManagementPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});sessionStorage.setItem('suite-branch','1');createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/crm/leads']}><Page/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 let release;const held=new Promise(resolve=>release=resolve);let reads=0;const errors=[];
 try{const page=await browser.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/v1/**',async route=>{const p=new URL(route.request().url()).pathname;let body={items:[],fields:[],customFields:[]};
 if(p.endsWith('/lead-management/settings'))body={settings:{stages:[{name:'New',required:[],allowedNext:[]}],assignment:{mode:'manual',rules:[]},sources:[],sequences:[],workflows:[]},owners:[],userId:1,canManage:true,canAdmin:true};
 if(p.endsWith('/lead-management/leads')){reads++;if(reads>1)await held;body={items:[],total:0,page:1,perPage:40,summary:{total:reads>1?2:0,active:reads>1?2:0,overdue:0,slaBreached:0,stale:0},byStage:{},bySource:{},convertedBySource:{},lostReasons:{}};}
 await route.fulfill({json:body}).catch(()=>{});});
 await page.route('**/lead-kpi-qa',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-lead-kpis.tsx');</script>`}));
 await page.goto(server.resolvedUrls.local[0]+'lead-kpi-qa');const metric=page.getByRole('region',{name:'Lead health'}).getByRole('button',{name:/Active leads/});
 await expect(metric.locator('strong')).toHaveText('0');
 await page.evaluate(()=>window.dispatchEvent(new CustomEvent('suite:record-saved',{detail:{url:'/crm/lead-management/leads',method:'post',record:{id:12,full_name:'QA KPI lead',status:'New',source:'Referral',details:{recordType:'Lead'},signals:{active:true,overdue:false,slaBreached:false,stale:false,priority:0,nextAction:'Follow up',ageDays:0}}}})));
 await expect(metric.locator('strong')).toHaveText('1');await expect.poll(()=>reads).toBeGreaterThan(1);release();await expect(metric.locator('strong')).toHaveText('2');expect(errors).toEqual([]);
 console.log('PASS lead KPI event: immediate summary update and server refetch across page/API route mismatch');
 }finally{release();await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
