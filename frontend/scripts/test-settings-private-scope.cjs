const assert=require('node:assert/strict');
const path=require('node:path');
const net=require('node:net');
const{chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:30000});
const freePort=()=>new Promise((resolve,reject)=>{const socket=net.createServer();socket.once('error',reject);socket.listen(0,'127.0.0.1',()=>{const port=socket.address().port;socket.close(error=>error?reject(error):resolve(port));});});
(async()=>{
 const root=path.resolve(__dirname,'..');process.chdir(root);
 const{createServer}=await import('vite');
 const server=await createServer({root,cacheDir:path.resolve(root,'../.local/settings-private-vite-cache'),server:{host:'127.0.0.1',port:await freePort(),strictPort:true,hmr:false,watch:null}});
 await server.listen();const origin='http://127.0.0.1:'+server.httpServer.address().port;
 const browser=await chromium.launch(),context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const errors=[],unexpected=[];let releaseA,releaseB,revoked=false,closing=false;
 const oldSelection=new Promise(resolve=>{releaseA=resolve;});
 let newCatalog=new Promise(resolve=>{releaseB=resolve;});
 page.on('pageerror',error=>errors.push(error.message));
 await page.route(origin+'/**',async route=>{const request=route.request(),url=new URL(request.url());try{
  if(url.pathname.startsWith('/api/')){
   const company=request.headers()['x-suite-organization']==='2'?2:1,name=company===1?'A':'B';
   const option={id:'scope-check',title:'PRIVATE-'+name+'-SETTING',group:'Company & access',description:'Native authorized setting '+name,destination:'/workspace-'+name,scope:'organization',editable:true};
   let body;
   if(url.pathname==='/api/v1/access/settings'){
    if(company===2&&newCatalog)await newCatalog;
    body={companyId:company,companyName:'PRIVATE-'+name+'-COMPANY',options:revoked?[]:[option]};
   }else if(url.pathname==='/api/v1/access/settings/options/scope-check'){
    if(company===1)await oldSelection;
    body=option;
   }else if(url.pathname==='/api/v1/access/me'){
    const permissions=revoked?[]:['employee_view','leave_apply'];
    body={companyId:company,managed:true,isAccessAdmin:false,isGlobalAdmin:false,permissions,modules:[],
     grants:{hrms:{enabled:true,permissions,actions:revoked?['view']:['view','create','edit'],scope:'own'}},
     businessPacks:{state:'ready',contexts:[],selectedContextId:null,selectionState:'none',hasMore:false,selectorRequired:false}};
   }else if(url.pathname==='/api/v1/branches/context')body={company_id:company,selected:'1',all_branches:false,can_manage:false,branches:[{id:1,company_id:company,name:'Branch '+name,writable:true}]};
   else{unexpected.push(request.method()+' '+url.pathname);body=[];}
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  }
  if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/leave-private-scope.tsx");</script>'});
  return route.continue();
 }catch(error){if(!closing&&request.failure()?.errorText!=='net::ERR_ABORTED')errors.push(error.message);await route.abort().catch(()=>{});}});
 try{
  await page.goto(origin+'/private-settings-qa?mode=settings');
  await expect(page.getByRole('heading',{name:'PRIVATE-A-SETTING',exact:true})).toBeVisible({timeout:120000});
  await expect(page.getByText('Checking access…',{exact:true})).toBeVisible();
  await page.evaluate(()=>window.switchLeaveOwner('B'));
  await expect(page.getByText('PRIVATE-A-COMPANY',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'PRIVATE-A-SETTING',exact:true})).toHaveCount(0);
  releaseB();newCatalog=null;
  await expect(page.getByRole('link',{name:'Open PRIVATE-B-SETTING',exact:true})).toBeVisible();
  releaseA();
  await expect(page.getByRole('link',{name:'Open PRIVATE-A-SETTING',exact:true})).toHaveCount(0);
  revoked=true;await page.evaluate(()=>window.revokeScopeOwner());
  await expect(page.getByRole('heading',{name:'Setting unavailable',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Open PRIVATE-B-SETTING',exact:true})).toHaveCount(0);
  await page.setViewportSize({width:390,height:1000});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
  console.log('PASS Settings: held old option replies cannot restore another company or revoked access; original desktop/mobile shell preserved.');
 }catch(error){console.error(JSON.stringify({unexpected,errors,body:(await page.locator('body').innerText()).slice(0,3000)}));throw error;}
 finally{releaseA();releaseB();closing=true;await context.close();await browser.close();await server.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
