const {chromium,expect}=require('playwright/test');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const fixture=path.join(__dirname,'.audit-customer-access.tsx');
 fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from '@/shared/master-data/CompaniesPage';import{useAuthStore}from'@/store/authStore';import '@/index.css';
 const mode=location.search.slice(1);const grant={enabled:true,role:'manager',scope:'company',permissions:['crm_accounts_manage'],actions:mode==='deny'?['view']:['view','create']};
 useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:mode==='super',...(mode==='legacy'?{}:{access:{managed:true,companyId:1,grants:{crm:grant},modules:[],memberships:[1],isAccessAdmin:false,isGlobalAdmin:false}})}});sessionStorage.setItem('suite-branch','1');
 createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Page role="Customer"/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();
 try{for(const mode of ['super','allow','deny','legacy']){
  const page=await browser.newPage();let release;const held=new Promise(resolve=>release=resolve);let gridStarted=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{const url=new URL(route.request().url());if(url.pathname.endsWith('/company-directory/query')){gridStarted=true;await held;return route.fulfill({json:{rows:[],groups:[],total:0,pageTotal:0,page:1,pageSize:40,permissions:{},context:{canCreate:false}}});}return route.fulfill({json:{items:[],total:0,values:{},modules:{}}});});
  await page.route('**/customer-access?*',route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-customer-access.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'customer-access?'+mode);
  // Start the request assertion after the unbundled Vite fixture has mounted.
  await expect(page.getByRole('heading',{name:'Customers',exact:true})).toBeVisible({timeout:30000});
  await expect.poll(()=>gridStarted).toBe(true);
  const button=page.getByRole('button',{name:'Create customer',exact:true});
  if(['super','allow'].includes(mode)){await expect(button).toBeVisible();await button.click();await expect(page.getByRole('dialog')).toBeVisible();}
  else await expect(button).toHaveCount(0);
  release();await expect(button).toHaveCount(0);await expect(page.getByRole('dialog')).toHaveCount(0);expect(errors).toEqual([]);await page.close();
 }console.log('PASS customer create: known grants open before grid response; denied/unknown access waits; server denial removes action and form');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
