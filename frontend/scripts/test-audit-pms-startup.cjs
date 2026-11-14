const fs=require('node:fs'),path=require('node:path');
const{chromium,expect:base}=require('playwright/test');const expect=base.configure({timeout:20000});
(async()=>{
 const fixture=path.join(__dirname,'.audit-pms-startup.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import{Toaster}from'@/components/ui/toaster';import Page from'@/apps/project-management/pages/WorkspacesPage';import{useAuthStore}from'@/store/authStore';import'@/index.css';sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:1,email:'qa@example.test',role:'super_admin',primary_role:'super_admin',is_superuser:true,access:{managed:true,companyId:1,memberships:[1],modules:[],companyDisabledModules:[],grants:{project_management:{enabled:true,role:'Admin',scope:'organization',permissions:['pms_view','pms_admin'],actions:['view','create','edit','configure','assign']}}}}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/pms']}><Page/><Toaster/></MemoryRouter></QueryClientProvider>);`);
 const{createServer}=await import('vite');const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const width of[390,1280])for(const legacy of[false,true]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[],reads=[],provisional=[];let release;
  page.on("request",q=>{const p=new URL(q.url()).pathname;if(p.endsWith("/dashboard-workflow")||p.endsWith("/recovery/history")||p.endsWith("/workspace-invitations/mine"))provisional.push(p);});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{const u=new URL(route.request().url()),p=u.pathname;reads.push(p);
   if(p==='/api/v1/project-management/workspaces')return route.fulfill({json:[{id:1,name:'PMS startup workspace',role:'Admin',member_count:1}]});
   if(p.endsWith('/workspaces/1/overview')){expect(u.searchParams.get('include_people')).toBe('true');await new Promise(r=>release=r);return route.fulfill({json:{id:1,name:'PMS startup workspace',role:'Admin',projects:[],tasks:[],...legacy?{}:{members:[{id:1,user_id:1,email:'member@example.test',role:'Admin'}],invitations:[]}}});}
   if(p.endsWith('/members'))return route.fulfill({json:[{id:1,user_id:1,email:'member@example.test',role:'Admin'}]});
   if(p.endsWith('/realtime/config'))return route.fulfill({json:{transport:'database'}});
   if(p.endsWith('/realtime/events'))return route.fulfill({json:{cursor:1,events:[]}});
   if(p.endsWith('/access/setup'))return route.fulfill({json:{ready:true,items:[]}});
   if(p.includes('custom-fields'))return route.fulfill({json:{fields:[],items:[]}});
   return route.fulfill({json:[]});
  });
  await page.route('**/qa-pms-startup',route=>route.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-pms-startup.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-pms-startup');await expect.poll(()=>typeof release).toBe('function');await expect(page.getByRole('heading',{name:'PMS startup workspace',exact:true})).toHaveCount(0);await page.waitForTimeout(100);expect(provisional).toEqual([]);
  release();await expect(page.getByRole('heading',{name:'PMS startup workspace',exact:true})).toBeVisible();await page.waitForLoadState('networkidle');
  expect(reads.filter(p=>p.endsWith('/overview'))).toHaveLength(1);expect(provisional.filter(p=>p.endsWith('/workspace-invitations/mine'))).toHaveLength(1);expect(provisional.filter(p=>p.endsWith('/dashboard-workflow'))).toHaveLength(1);expect(provisional.filter(p=>p.endsWith('/recovery/history'))).toHaveLength(1);expect(reads.filter(p=>p.endsWith('/members'))).toHaveLength(legacy?1:0);expect(reads.filter(p=>p.endsWith('/invitations'))).toHaveLength(legacy?1:0);expect(errors).toEqual([]);await page.unrouteAll({behavior:'wait'});await page.close();
 }
 for(const width of[390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}});let fail=true;const childReads=[],inboxReads=[];
  await page.route('**/api/v1/**',r=>{const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/dashboard-workflow')||p.endsWith('/recovery/history'))childReads.push(p);
   if(p.endsWith('/workspace-invitations/mine'))inboxReads.push(p);
   if(p==='/api/v1/project-management/workspaces')return r.fulfill({json:[{id:1,name:'PMS startup workspace',role:'Admin',member_count:1}]});
   if(p.endsWith('/overview'))return r.fulfill({status:fail?403:200,json:fail?{detail:'Workspace unavailable'}:{id:1,name:'PMS startup workspace',role:'Admin',projects:[],tasks:[],members:[],invitations:[]}});
   if(p.endsWith('/realtime/config'))return r.fulfill({json:{transport:'database'}});
   if(p.endsWith('/realtime/events'))return r.fulfill({json:{cursor:1,events:[]}});
   if(p.endsWith('/access/setup'))return r.fulfill({json:{ready:true,items:[]}});
   if(p.includes('custom-fields'))return r.fulfill({json:{fields:[],items:[]}});
   return r.fulfill({json:[]});
  });
  await page.route('**/qa-pms-startup',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-pms-startup.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-pms-startup');await expect(page.getByRole('button',{name:'Retry workspace',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'PMS startup workspace',exact:true})).toHaveCount(0);expect(childReads).toEqual([]);await expect.poll(()=>inboxReads.length).toBe(1);fail=false;await page.getByRole('button',{name:'Retry workspace',exact:true}).click();await expect(page.getByRole('heading',{name:'PMS startup workspace',exact:true})).toBeVisible();await page.unrouteAll({behavior:'wait'});await page.close();
 }
 for(const width of[390,1280]){
  const page=await browser.newPage({viewport:{width,height:900}});let inboxReads=0,savedWorkspace,failSave=true,writes=0;
  await page.route('**/api/v1/**',r=>{const p=new URL(r.request().url()).pathname;
   if(p.endsWith('/workspace-invitations/mine'))inboxReads++;
   if(p==='/api/v1/project-management/workspaces'){if(r.request().method()==='POST'){writes++;if(failSave)return r.fulfill({status:503,json:{detail:'Workspace save unavailable'}});savedWorkspace={id:81,name:r.request().postDataJSON().name,role:'Owner'};return r.fulfill({status:201,json:savedWorkspace});}return r.fulfill({json:savedWorkspace?[savedWorkspace]:[]});}
   if(p.endsWith('/overview'))return r.fulfill({json:{...savedWorkspace,projects:[],tasks:[],members:[],invitations:[]}});
   if(p.endsWith('/access/setup'))return r.fulfill({json:{ready:true,items:[]}});
   return r.fulfill({json:[]});
  });
  await page.route('**/qa-pms-startup',r=>r.fulfill({contentType:'text/html',body:`<div id="root"></div><script type="module">import R from'/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/.audit-pms-startup.tsx');</script>`}));
  await page.goto(server.resolvedUrls.local[0]+'qa-pms-startup');await expect(page.getByRole('heading',{name:'Good work happens together.',exact:true})).toBeVisible();await expect.poll(()=>inboxReads).toBe(1);await page.locator('.ws-onboarding').getByRole('button',{name:'Create workspace',exact:true}).click();const dialog=page.getByRole('dialog',{name:'A home for your team.',exact:true});await expect(dialog).toBeVisible();await dialog.getByRole('textbox',{name:'Workspace name',exact:true}).fill('Feedback workspace');await dialog.getByRole('button',{name:'Create workspace',exact:true}).click();await expect.poll(()=>writes).toBe(1);await expect(page.getByText('Workspace created',{exact:true})).toHaveCount(0);await expect(dialog.getByRole('textbox',{name:'Workspace name',exact:true})).toHaveValue('Feedback workspace');failSave=false;await dialog.getByRole('button',{name:'Create workspace',exact:true}).click();await expect(dialog).toHaveCount(0);await expect(page.getByText('Workspace created',{exact:true})).toBeVisible();await page.unrouteAll({behavior:'wait'});await page.close();
 }
 console.log('PASS PMS startup: one authorized combined overview, no separate people/invitation reads, blocks until actual data; rolling old API fallback at390/1280');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});
