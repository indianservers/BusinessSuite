const fs=require('node:fs'),path=require('node:path'),{chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-deal-kpis.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/apps/crm/deals/EnterpriseDealsPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});sessionStorage.setItem('suite-branch','1');createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/crm/deals']}><Page/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();let reads=0,created=false;const errors=[];
 try{const page=await browser.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/v1/**',async route=>{const p=new URL(route.request().url()).pathname;let body={items:[],total:0};
 if(p.endsWith('/deal-workspace/grid/query')){reads++;const count=created?1:0;body={rows:created?[{id:12,name:'QA KPI deal',status:'Open',stage_id:1,currency:'INR',amount:100}]:[],groups:[],total:count,pageTotal:count,page:1,pageSize:25,permissions:{},context:{summary:{counts:{open:count,overdue:0,closing_month:0},stages:[],currencies:[],forecast:[],breakdowns:{}}}};}
 await route.fulfill({json:body});});
 await page.route('**/deal-kpi-qa',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-deal-kpis.tsx');</script>`}));
 await page.goto(server.resolvedUrls.local[0]+'deal-kpi-qa');const overview=page.locator('.ed-sales-overview > summary');await expect(overview).toContainText('0 open');const before=reads;created=true;
 await page.evaluate(()=>window.dispatchEvent(new CustomEvent('suite:record-saved',{detail:{url:'/crm/deals',method:'post',record:{id:12,name:'QA KPI deal',status:'Open',stage_id:1,currency:'INR',amount:100}}})));
 await expect(overview).toContainText('1 open');await expect.poll(()=>reads).toBeGreaterThan(before);await expect(page.getByRole('checkbox',{name:'Select row QA KPI deal',exact:true})).toBeVisible();expect(errors).toEqual([]);
 console.log('PASS deal KPI event: create refreshes grid rows and server summary without manual reload');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
