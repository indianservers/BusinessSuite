const fs=require('node:fs'),path=require('node:path'),{chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-access-loading.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'@/features/access/UsersAccessPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});sessionStorage.setItem('suite-branch','1');createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/admin/access']}><Page embedded/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();let release;const held=new Promise(resolve=>release=resolve);const reads={catalog:0,users:0,templates:0};const errors=[];
 try{const page=await browser.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.route('**/api/v1/**',async route=>{const p=new URL(route.request().url()).pathname;let body={items:[]};
 if(p.endsWith('/access/catalog')){reads.catalog++;body={modules:[{key:'crm',label:'CRM',installed:true,permissions:[]}],roles:[{id:1,name:'Sales manager'}],legacyRoles:[],presets:{},scopes:[],actions:[],companies:[{id:1,name:'QA company'}]};}
 if(p.endsWith('/access/users')){reads.users++;body={items:[{id:3,name:'QA access user',email:'access@example.test',companyId:1,status:'active',grants:{},moduleCount:0,role:'Sales manager',accountType:'User'}],total:1,page:1,perPage:100,pages:1,summary:{registered:1,loginEnabled:1,invited:0,suspended:0,modules:1,admins:0},filters:{branches:[],departments:[]},stats:{byModule:{},byRole:{},byDepartment:{},dormant:[]}};}
 if(p.endsWith('/access/templates')){reads.templates++;await held;if(reads.templates===1)return route.fulfill({status:503,json:{detail:'Templates temporarily unavailable'}});}
 if(p.endsWith('/branches/context'))body={manage_access:true,branches:[]};
 await route.fulfill({json:body});});
 await page.route('**/access-loading-qa',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-access-loading.tsx');</script>`}));
 await page.goto(server.resolvedUrls.local[0]+'access-loading-qa');await expect(page.getByText('access@example.test',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Filter module')).toContainText('CRM');await expect(page.getByLabel('Filter role')).toContainText('Sales manager');
 const before=reads.users;await page.getByLabel('Search users').fill('QA');await expect.poll(()=>reads.users).toBeGreaterThan(before);expect(reads.catalog).toBe(1);expect(reads.templates).toBe(1);
 release();await expect(page.getByRole('button',{name:'Retry permission templates',exact:true})).toBeVisible();await expect(page.getByText('access@example.test',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Retry permission templates',exact:true}).click();await expect(page.getByRole('button',{name:'Retry permission templates',exact:true})).toHaveCount(0);expect(errors).toEqual([]);
 console.log('PASS access loading: users/filters render despite stalled or failed templates; search does not reload catalog/templates; independent retry works');
 }finally{release();await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
