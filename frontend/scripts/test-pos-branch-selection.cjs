const fs = require('node:fs'), path = require('node:path');
const {chromium, expect} = require('playwright/test');
(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const fixture = path.resolve('scripts',`.pos-branch-${process.pid}.tsx`);
  fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from '@/apps/srm/components/POSBranchSelection';import{useAuthStore}from'@/store/authStore';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','all');useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,role:'super_admin',is_superuser:true,access:{companyId:1,modules:[],grants:{}}}});createRoot(document.getElementById('root')).render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><Page/></QueryClientProvider></MemoryRouter>);`);
  const {createServer}=await import('vite');
  const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();const browser=await chromium.launch();
  try {
    for(const width of [390,1280]) {
      const page=await browser.newPage({viewport:{width,height:850}});
      let denied=true, destination;
      await page.route('**/api/v1/**',route=>{
        const request=route.request(),url=new URL(request.url());
        if(url.pathname.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,all_branches:true,selected:null,branches:[{id:2,name:'Main branch',can_write:true},{id:3,name:'Other branch',can_write:true},{id:4,name:'Read only',can_write:false},{id:5,name:'Archived',can_write:true,is_active:false}]}});
        if(url.pathname.endsWith('/access/me')){destination=request.headers();return denied?route.fulfill({status:403,json:{detail:'Branch access denied'}}):route.fulfill({json:{companyId:1,modules:[],grants:{}}});}
        return route.fulfill({json:{}});
      });
      await page.route('**/branch-qa',route=>route.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/${path.basename(fixture)}');</script>`}));
      await page.route('**/srm/pos/terminal',route=>route.fulfill({contentType:'text/html',body:'<h1>Selected branch terminal</h1>'}));
      await page.goto(server.resolvedUrls.local[0]+'branch-qa');
      await expect(page.getByRole('button',{name:'Open POS',exact:true})).toBeDisabled();
      await expect(page.getByRole('option',{name:'Read only',exact:true})).toHaveCount(0);
      await expect(page.getByRole('option',{name:'Archived',exact:true})).toHaveCount(0);
      await page.getByLabel('POS branch',{exact:true}).selectOption('2');
      await page.getByRole('button',{name:'Open POS',exact:true}).click();
      await expect(page.getByRole('alert')).toContainText('Branch access denied');
      expect(await page.evaluate(()=>sessionStorage.getItem('suite-branch'))).toBe('all');
      denied=false;
      await page.getByRole('button',{name:'Open POS',exact:true}).click();
      await expect(page.getByRole('heading',{name:'Selected branch terminal'})).toBeVisible();
      expect(destination['x-suite-branch']).toBe('2');
      expect(destination['x-suite-organization']).toBe('1');
      expect(await page.evaluate(()=>sessionStorage.getItem('suite-branch'))).toBe('2');
      await page.close();
    }
    console.log('PASS POS branch selection: phone/desktop, valid writable branches, denied switch preserves All branches, verified switch opens POS');
  } finally {await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(error=>{console.error(error);process.exitCode=1;});
