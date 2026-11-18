const fs=require('node:fs'),path=require('node:path'),{chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:20000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-pms-overlap.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Bot from'@/components/ai-agents/ActionBot';import Dock from'@/components/layout/MobileModuleDock';import MobileExperience from'@/components/mobile/MobileExperience';import'@/components/layout/mobile-workspaces.css';import Page from'@/apps/project-management/pages/WorkspacesPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'super_admin',primary_role:'super_admin',is_superuser:true,access:{managed:true,companyId:1,memberships:[1],modules:[],companyDisabledModules:[],grants:{project_management:{enabled:true,role:'Admin',scope:'organization',permissions:['pms_view','pms_admin'],actions:['view','create','edit','configure','assign']}}}}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/pms']}><div className="mobile-dock-fullscreen flex h-dvh flex-col overflow-hidden"><div className="pms-workspace-host min-h-0 flex-1 overflow-hidden"><Page/></div><Dock/></div><Bot/><MobileExperience/></MemoryRouter></QueryClientProvider>);`);
 const{createServer}=await import('vite');const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 const overlaps=(a,b)=>a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height;
 try{for(const width of[320,390,600,767,1024,1280]){
  const page=await browser.newPage({viewport:{width,height:800}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',r=>{const p=new URL(r.request().url()).pathname;
   if(p==='/api/v1/project-management/workspaces')return r.fulfill({json:[{id:1,name:'Overlap workspace',role:'Admin',member_count:1}]});
   if(p.endsWith('/overview'))return r.fulfill({json:{id:1,name:'Overlap workspace',role:'Admin',projects:[],tasks:[],members:[],invitations:[]}});
   if(p.endsWith('/access/setup'))return r.fulfill({json:{ready:true,items:[]}});
   if(p.includes('custom-fields'))return r.fulfill({json:{fields:[],items:[]}});
   if(p.endsWith('/realtime/config'))return r.fulfill({json:{transport:'database'}});
   if(p.endsWith('/realtime/events'))return r.fulfill({json:{cursor:1,events:[]}});
   return r.fulfill({json:[]});
  });
  await page.route('**/qa-pms-overlap',r=>r.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-pms-overlap.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-pms-overlap');
  await expect(page.getByRole('heading',{name:'Overlap workspace',exact:true})).toBeVisible();
  const launcher=page.getByRole('button',{name:'Open action bot',exact:true});await expect(launcher).toBeVisible();
  const content=await page.locator('.ws-content').boundingBox(),bot=await launcher.boundingBox();
  expect(overlaps(content,bot),`Workspace scroll viewport must not be covered by assistant at ${width}px`).toBe(false);
  await launcher.click();await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toBeVisible();await page.getByRole('button',{name:'Close action bot',exact:true}).click();
  if(width<768){await page.evaluate(()=>document.body.classList.add('mobile-keyboard-open'));await expect(launcher).toBeHidden();const expanded=await page.locator('.ws-content').boundingBox();expect(expanded.height).toBeGreaterThan(content.height+70);await page.evaluate(()=>document.body.classList.remove('mobile-keyboard-open'));await expect(launcher).toBeVisible();}
  expect(errors).toEqual([]);await page.unrouteAll({behavior:'wait'});await page.close();
 }console.log('PASS native PMS scroll viewport and assistant clearance at six widths');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
