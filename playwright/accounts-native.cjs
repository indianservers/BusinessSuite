const path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');
const expect=base.configure({timeout:30000}),bridge=process.env.CONTROL_BRIDGE;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw Error('Disposable actual API bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');process.chdir(root);
 const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
 const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const assigned=socket.address().port;socket.close(()=>resolve(assigned));});});
 const server=await createServer({root,server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});
 const contexts=[],errors=[],trace=[];let browser,origin,current,closing=false;
 async function pageFor(role,mobile=false){
  const context=await browser.newContext({viewport:{width:mobile?390:1440,height:1000}});contexts.push(context);
  await context.addInitScript(identity=>{window.qaAuth=identity;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},{token:auth[role],branch:auth.branch,context:auth.context});
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.route(origin+'/**',async route=>{const request=route.request(),url=new URL(request.url());try{
   if(url.pathname.startsWith('/api/')){const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});trace.push({role,method:request.method(),path:url.pathname,status:response.status()});return route.fulfill({response});}
   if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/accounts-native.tsx");</script>'});
   return route.continue();
  }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{});}});
  await page.goto(origin+'/srm/accounts-periods');return page;
 }
 async function fits(page){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);}
 try{
  await server.listen();origin='http://127.0.0.1:'+server.httpServer.address().port;browser=await chromium.launch();
  current=await pageFor('manager');
  await current.getByLabel('Client engagement',{exact:true}).selectOption(String(auth.engagement));
  await current.getByLabel('Period title',{exact:true}).fill('January client accounts');
  await current.getByLabel('Period starts',{exact:true}).fill('2026-01-01');await current.getByLabel('Period ends',{exact:true}).fill('2026-01-31');await current.getByLabel('Due date',{exact:true}).fill('2026-02-10');
  await current.getByLabel('Preparer',{exact:true}).selectOption(String(auth.preparer_employee));await current.getByLabel('Independent reviewer',{exact:true}).selectOption(String(auth.reviewer_employee));
  await current.getByRole('button',{name:'Create period',exact:true}).click();await expect(current.getByRole('button',{name:'Open period',exact:true})).toHaveCount(1);await fits(current);
  await current.screenshot({path:path.resolve(root,'../.local/accounts-manager-desktop.png'),fullPage:true});
  await current.setViewportSize({width:390,height:1000});await fits(current);
  await expect(current.getByLabel('Client engagement',{exact:true})).toBeVisible();
  await current.screenshot({path:path.resolve(root,'../.local/accounts-manager-mobile.png'),fullPage:true});
  current=await pageFor('preparer',true);await expect(current.getByRole('heading',{name:'New service period',exact:true})).toHaveCount(0);
  await current.getByText('More actions',{exact:true}).click();
  await current.getByRole('button',{name:'Open period',exact:true}).click();await current.getByLabel('Updated work summary',{exact:true}).fill('Reconciled supplied documents');
  await current.getByRole('button',{name:'Save work',exact:true}).click();await expect(current.getByRole('button',{name:'Submit for review',exact:true})).toBeVisible();
  await current.getByRole('button',{name:'Submit for review',exact:true}).click();await expect(current.getByText('Status: submitted | Work revision: 1',{exact:true})).toBeVisible();
  await expect(current.getByRole('button',{name:'Approve work',exact:true})).toHaveCount(0);await fits(current);await current.screenshot({path:path.resolve(root,'../.local/accounts-preparer-mobile.png'),fullPage:true});
  current=await pageFor('reviewer',true);await current.getByText('More actions',{exact:true}).click();await current.getByRole('button',{name:'Open period',exact:true}).click();await current.getByLabel('Review notes',{exact:true}).fill('Independent review complete');
  await expect(current.getByLabel('Updated work summary',{exact:true})).toHaveCount(0);await current.getByRole('button',{name:'Approve work',exact:true}).click();
  await expect(current.getByText('Status: approved | Work revision: 1',{exact:true})).toBeVisible();await fits(current);await current.screenshot({path:path.resolve(root,'../.local/accounts-reviewer-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(trace.filter(row=>row.status>=400),[]);
  console.log(JSON.stringify({real_api:true,roles:['manager','preparer','reviewer'],viewports:[1440,390],state:'approved',requests:trace.length}));
 }catch(error){const failure={message:error.message,trace:trace.slice(-25),errors,body:current?(await current.locator('body').innerText()).slice(-4000):null};fs.writeFileSync(path.resolve(root,'../.local/accounts-browser-failure.json'),JSON.stringify(failure));if(current)await current.screenshot({path:path.resolve(root,'../.local/accounts-browser-failure.png'),fullPage:true}).catch(()=>{});console.error(JSON.stringify(failure));throw error;}
 finally{closing=true;for(const context of contexts){await Promise.all(context.pages().map(page=>page.close()));await context.unrouteAll({behavior:'wait'});await context.close();}if(browser)await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
