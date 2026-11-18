const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-feature-fixture.tsx');
 fs.writeFileSync(fixture,`import React from'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Connectors from './src/shared/ConnectorCatalog';import Communication from './src/apps/communication/CommunicationHubPage';import{useAuthStore}from './src/store/authStore';import{canAccessRoute}from './src/lib/roles';import './src/index.css';const params=new URLSearchParams(location.search),connect=params.has('connectors'),allow=params.has('allow'),disabled=params.has('disabled'),noView=params.has('no-view');const grant=(enabled,permissions)=>({enabled,permissions:params.has('no-permission')?[]:permissions,actions:noView?[]:['view','create'],role:'Viewer',scope:'organization'});useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:params.has('super'),access:{managed:true,companyId:1,companyDisabledModules:disabled?['power_apps','communication']:[],memberships:[1],isAccessAdmin:true,isGlobalAdmin:false,modules:[{key:'crm',route:'/crm',label:'CRM'}],grants:{crm:grant(true,['crm_view']),power_apps:grant(allow,['power_apps_view']),communication:grant(allow,['communication_view'])}}}});const route=connect?'/crm/connectors':'/crm/emails',user=useAuthStore.getState().user;window.routeAllowed=canAccessRoute(route,user.role,user.is_superuser);createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[route]}>{connect?<Connectors/>:<Communication/>}</MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
 const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',route=>{requests.push(new URL(route.request().url()).pathname);return route.fulfill({json:{items:[],targets:{},total:0}});});
 await page.route('**/qa-feature-access*',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-feature-fixture.tsx"></script>'}));
 const base='http://127.0.0.1:'+server.httpServer.address().port+'/qa-feature-access';
 for(const kind of ['connectors','communication']){
  for(const mode of ['', '&allow&no-view','&allow&no-permission','&allow&super&disabled']){
   const before=requests.length;await page.goto(base+'?'+kind+mode);
   await expect(page.getByRole('heading',{name:(kind==='connectors'?'Connectors':'Communication tools')+' unavailable',exact:true})).toBeVisible();
   assert.equal(await page.evaluate(()=>window.routeAllowed),false);assert.equal(requests.length,before,'unavailable features must not start forbidden API calls');
  }
  await page.goto(base+'?'+kind+'&allow');assert.equal(await page.evaluate(()=>window.routeAllowed),true);
  if(kind==='connectors')await expect(page.getByRole('heading',{name:'Connectors & authorization',exact:true})).toBeVisible();else await expect(page.getByRole('heading',{name:'Compose email',exact:true})).toBeVisible();
 }
 assert(requests.some(path=>path.endsWith('/communication/email-templates')));assert(requests.some(path=>path.endsWith('/power-apps/integrations/discovery')));assert.deepEqual(errors,[]);
 console.log('PASS feature access: denied/disabled/no-view navigation and page guards, zero forbidden fetches, authorized communication and connectors load');
 }finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});

