const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-deal-groups.tsx');
 fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Deals from './src/apps/crm/deals/DealsDataGrid';import{useAuthStore}from './src/store/authStore';import './src/index.css';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/crm/deals']}><Deals base={{}} refreshKey={0} initialQuery={{grouping:['stage_id']}} selected={[]} onSelection={()=>{}} onResult={()=>{}} onQueryChange={()=>{}} edit={()=>{}} move={()=>{}} owners={[]}/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();let page;
 try{
 page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],states=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{
  const url=new URL(route.request().url());
  if(url.pathname.endsWith('/crm/deal-workspace/grid/query')){
   const state=JSON.parse(url.searchParams.get('state')||'{}');states.push(state);
   const branch=state.path?.length>0;
   return route.fulfill({json:{total:1,pageTotal:1,page:1,pageSize:25,permissions:{},rows:branch?[{id:4,name:'QA_TEST_2026_DEAL_001',stage_id:3,stage_name:'Qualification',status:'Open',currency:'INR',amount:150000,probability:20,weighted:30000}]:[],groups:branch?[]:[{field:'stage_id',value:3,label:'Qualification',count:1,aggregates:[{currency:'INR',sum:150000,count:1}],path:[{field:'stage_id',value:3}]}]}});
  }
  return route.fulfill({json:{items:[]}});
 });
 await page.route('**/qa-audit-deals',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-deal-groups.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-deals');
 const row=page.getByRole('checkbox',{name:'Select row QA_TEST_2026_DEAL_001',exact:true});await expect(row).toBeVisible({timeout:20000});
 const text=await page.locator('body').innerText();assert(text.includes(new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(150000)));assert(!text.includes(new Intl.NumberFormat('en-US',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(150000)),'deal cells and grouped totals must not mix INR locales');
 assert(states.some(state=>state.path?.[0]?.field==='stage_id'&&state.path[0].value===3),'expanded stage must request its actual records');
 assert.deepEqual(errors,[]);console.log('PASS grouped Deals: stage group automatically loads and displays its deal row');
 }catch(e){if(page)console.error((await page.locator('body').innerText()).slice(-3500));throw e;}finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
