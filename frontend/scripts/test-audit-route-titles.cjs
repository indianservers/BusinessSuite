const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-title-fixture.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter,Routes,Route,useNavigate}from'react-router-dom';import RouteTitle from './src/components/app/RouteTitle';import{usePageTitle}from './src/hooks/use-page-title';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});function Contacts(){usePageTitle('Custom contacts');return <h1>Contacts</h1>};function App(){window.navigate=useNavigate();return <><RouteTitle/><Routes><Route path="/crm/contacts" element={<Contacts/>}/><Route path="/crm/customers" element={<h1>Customers</h1>}/><Route path="/srm/sales-orders" element={<h1>Sales orders</h1>}/><Route path="/dashboard" element={<h1>Applications</h1>}/></Routes></>};createRoot(document.getElementById('root')).render(<MemoryRouter initialEntries={['/crm/contacts']}><App/></MemoryRouter>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/qa-route-title',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-title-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-route-title');await expect(page).toHaveTitle('Custom contacts - VyaparaCRM');
 await page.evaluate(()=>window.navigate('/crm/customers'));await expect(page).toHaveTitle(/Customers.*VyaparaCRM/);
 await page.evaluate(()=>window.navigate('/srm/sales-orders'));await expect(page).toHaveTitle(/Sales Orders.*Sales|Sales Orders.*Inventory/i);
 await page.evaluate(()=>window.navigate('/dashboard'));await expect(page).toHaveTitle('Applications - Business Suite');
 await page.evaluate(()=>window.navigate(-1));await expect(page).toHaveTitle(/Sales Orders.*Sales|Sales Orders.*Inventory/i);
 await page.evaluate(()=>window.navigate('/crm/contacts'));await expect(page).toHaveTitle('Custom contacts - VyaparaCRM');
 assert.deepEqual(errors,[]);console.log('PASS route titles: custom titles, pages without hooks, app switching, launcher and browser Back');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
