const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-ledger-fixture.tsx');
 fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from './src/apps/fam/FAMWorkspacePage';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/fam/ledgers']}><Page kind="ledgers"/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();
 try{
 const page=await browser.newPage(),errors=[],writes=[];let groupsFail=true;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.pathname.endsWith('/ledger-groups'))return route.fulfill({status:groupsFail?503:200,json:groupsFail?{detail:'Groups unavailable'}:{items:[{id:73,group_name:'Office expenses',nature:'expense'}]}});
  if(url.pathname.endsWith('/ledgers')&&req.method()==='POST'){const body=req.postDataJSON();writes.push(body);return route.fulfill({status:201,json:{...body,id:90}});}
  return route.fulfill({json:{items:[]}});
 });
 await page.route('**/qa-audit-ledger',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-ledger-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-ledger');
 await page.getByRole('button',{name:'Create ledger',exact:true}).click();
 const dialog=page.getByRole('dialog');
 await expect(dialog.getByRole('button',{name:'Retry ledger groups'})).toBeVisible();
 groupsFail=false;await dialog.getByRole('button',{name:'Retry ledger groups'}).click();
 await expect(dialog.getByLabel('Ledger group').locator('option')).toHaveText(['Choose ledger group','Office expenses']);
 await dialog.locator('form').getByRole('button',{name:'Create',exact:true}).click();assert.equal(writes.length,0);
 await dialog.getByLabel('ledger code',{exact:true}).fill('QA-LEDGER');
 await dialog.getByLabel('ledger name',{exact:true}).fill('Audit office expenses');
 await dialog.getByLabel('Ledger group',{exact:true}).selectOption('73');
 await expect(dialog.getByLabel('nature',{exact:true})).toHaveValue('expense');
 await dialog.getByLabel('ledger type',{exact:true}).selectOption('general');
 await dialog.locator('form').getByRole('button',{name:'Create',exact:true}).click();
 await expect.poll(()=>writes.length).toBe(1);
 assert.deepEqual(writes[0],{ledger_code:'QA-LEDGER',ledger_name:'Audit office expenses',ledger_group_id:73,nature:'expense',ledger_type:'general'});
 assert.deepEqual(errors,[]);console.log('PASS ledger: failed group lookup/retry, required validation, real group ID, inherited nature, enum type, create payload');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

