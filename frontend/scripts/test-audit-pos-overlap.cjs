const fs=require('node:fs'),path=require('node:path'),{chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:20000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-pos-overlap.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import POS from'@/apps/srm/pages/SRMPOSPage';import MobileExperience from'@/components/mobile/MobileExperience';import Team from'@/components/app/WorkspaceEnhancements';import Bot from'@/components/ai-agents/ActionBot';import Back from'@/components/app/BackToTop';import Dock from'@/components/layout/MobileModuleDock';import{useAuthStore}from'@/store/authStore';import'@/index.css';import'@/components/layout/mobile-workspaces.css';useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});localStorage.setItem('business-suite-srm-pos-cart',JSON.stringify([{id:51,name:'Audit product',sku:'QA-51',barcode:'51',category:'General',rate:10,mrp:10,taxRate:0,stock:100,reorderLevel:1,trackInventory:true,kind:'product',lineId:'qa-line',qty:1,discount:0,note:''}]));sessionStorage.setItem('suite-branch','1');createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/srm/pos']}><div className="product-shell product-srm flex h-screen"><div className="flex min-w-0 flex-1 flex-col overflow-hidden"><header style={{height:64,flexShrink:0}}>Application bar</header><main id="suite-main" className="kf-main suite-page-surface min-w-0 flex-1 overflow-auto animate-fade-in"><Team/><POS/></main><Back/></div></div><Bot/><Dock/><MobileExperience/></MemoryRouter></QueryClientProvider>);`);
 const{createServer}=await import('vite');const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 const overlaps=(a,b)=>a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height;
 try{for(const width of[320,390,600,767,1024,1280]){
  const page=await browser.newPage({viewport:{width,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',r=>{const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/business/customers'))return r.fulfill({json:{items:[],next:null}});
   if(p.endsWith('/inventory/items'))return r.fulfill({json:{items:[],total:0}});
   if(p.endsWith('/follow-ups/options'))return r.fulfill({json:{users:[],customers:[]}});
   if(p.endsWith('/realtime/config'))return r.fulfill({json:{transport:'database'}});
   if(p.endsWith('/realtime/events'))return r.fulfill({json:{cursor:1,events:[]}});
   return r.fulfill({json:[]});
  });
  await page.route('**/qa-pos-overlap',r=>r.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-pos-overlap.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-pos-overlap');
  const payment=page.locator('.srm-pos-checkout').getByRole('button',{name:'Payment',exact:true});await payment.scrollIntoViewIfNeeded();await expect(payment).toBeVisible();
  const targets=[page.locator('.srm-pos-checkout'),page.getByRole('button',{name:'Open action bot',exact:true}),...(width<768?[page.getByRole('button',{name:'Workspace tools',exact:true})]:[])];
  const boxes=[];for(const target of targets){await expect(target).toBeVisible();const b=await target.boundingBox();expect(b.x).toBeGreaterThanOrEqual(0);expect(b.x+b.width).toBeLessThanOrEqual(width+1);expect(b.y).toBeGreaterThanOrEqual(0);expect(b.y+b.height).toBeLessThanOrEqual(801);boxes.push(b);}
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)expect(overlaps(boxes[i],boxes[j])).toBe(false);
  await payment.click();await expect(page.getByRole('heading',{name:'Complete Payment',exact:true})).toBeVisible();const amount=page.getByRole('spinbutton',{name:'Payment amount',exact:true});await amount.scrollIntoViewIfNeeded();await expect(amount).toHaveValue('10');const amountBox=await amount.boundingBox();expect(amountBox.x).toBeGreaterThanOrEqual(0);expect(amountBox.x+amountBox.width).toBeLessThanOrEqual(width+1);expect(errors).toEqual([]);await page.unrouteAll({behavior:'wait'});await page.close();
 }console.log('PASS actual POS checkout and utility control geometry at six widths');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
