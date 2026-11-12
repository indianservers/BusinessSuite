const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const path=require('node:path');
const expect=baseExpect.configure({timeout:20000});
const bridge=process.env.CONTROL_BRIDGE;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw new Error('Disposable API bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');
 process.chdir(root);
 const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
 const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const origin='http://127.0.0.1:'+server.httpServer.address().port;
 const browser=await chromium.launch();let checks=0,context,closing=false;
 try{
  context=await browser.newContext();const page=await context.newPage(),errors=[],failures=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('Browser runtime:',e.message);});
  await page.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
  await page.route(origin+'/**',async route=>{
   try {
   const request=route.request(),url=new URL(request.url());
   if(url.pathname.startsWith('/api/')){
    const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});
    if(response.status()>=400)failures.push(url.pathname+':'+response.status());
    await route.fulfill({response});
   }else if(request.isNavigationRequest())await route.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from '/@react-refresh'; R.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/business-suite-live.tsx');</script>`});else await route.continue();
   } catch(error) {
    if(!closing) { failures.push('bridge transport failure');console.error('Bridge transport failed:',error.message.split('\n')[0]); }
    await route.abort().catch(()=>{});
   }
  });
  const load=async module=>{
   await page.goto(origin+'/common/customers?module='+module);
   await expect(page.getByRole('heading',{name:'Customers',exact:true})).toBeVisible();checks++;
  };
  await load('crm');
  const created=await page.evaluate(async()=>{const r=await window.qaApi.post('/master-data/companies?source=crm',{name:'QA Live المشتركة 客户',roles:['Customer']});return r.data;});
  await page.getByRole('button',{name:'Refresh directory',exact:true}).click();
  await expect(page.getByText(created.name,{exact:true}).first()).toBeVisible();checks++;
  await page.evaluate(()=>window.qaNavigate('/common/customers?module=srm'));
  await expect(page.getByText(created.name,{exact:true}).first()).toBeVisible();checks++;
  const saved=await page.evaluate(async id=>{
   const {data:r}=await window.qaApi.get('/master-data/companies/'+id+'?source=srm');
   const {data}=await window.qaApi.patch('/master-data/companies/'+id+'?source=srm',{name:'QA Sales edited المشتركة 客户',roles:['Customer'],version:r.version});return data;
  },created.id);
  expect(saved.id).toBe(created.id);checks++;
  await page.getByRole('button',{name:'Refresh directory',exact:true}).click();
  await expect(page.getByText(saved.name,{exact:true}).first()).toBeVisible();checks++;
  await page.evaluate(()=>window.qaNavigate('/common/customers?module=crm'));
  await expect(page.getByText(saved.name,{exact:true}).first()).toBeVisible();checks++;
  await page.goBack();await expect(page).toHaveURL(/module=srm/);checks++;
  for(const width of [390,768,1440]){
   await page.setViewportSize({width,height:900});await load('crm');
   await expect(page.getByText(saved.name,{exact:true}).first()).toBeVisible();checks++;
   await expect(page.getByRole('navigation',{name:'Shared page breadcrumbs'})).toContainText('CRM');checks++;
  }
  const identity=await page.evaluate(async id=>{const {data}=await window.qaApi.get('/master-data/companies?source=srm&search=QA%20Sales%20edited');return data.items.map(row=>row.id);},created.id);
  expect(identity).toEqual([created.id]);checks++;
  await page.evaluate(async()=>window.qaApi.post('/srm/inventory/items',{sku:'QA-LIVE-SERVICE',item_name:'QA Fractional service',product_type:'service',track_inventory:false,sales_rate:99.99,gst_rate:18}));
  await page.evaluate(()=>window.qaNavigate('/srm/pos'));
  await page.getByRole('button',{name:/QA Fractional service/}).first().click();
  await expect(page.getByText('Amount payable',{exact:true}).locator('..').locator('strong')).toContainText('117.99');checks++;
  await page.getByRole('button',{name:'Pay',exact:true}).click();
  await expect(page.getByRole('spinbutton',{name:'Payment amount',exact:true})).toHaveValue('117.99');checks++;
  const posted=page.waitForResponse(response=>response.url().includes('/srm/sales-orders')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Complete Sale',exact:true}).click();
  const order=await (await posted).json();
  expect(Number(order.total_amount)).toBe(117.99);checks++;
  await page.waitForLoadState('networkidle');
  const analytics=page.waitForResponse(response=>response.url().includes('/project-management/analytics/overview')&&response.request().method()==='GET');
  await page.evaluate(()=>window.qaNavigate('/qa/analytics'));
  const reportResponse=await analytics,report=await reportResponse.json();
  expect(report.timezone).toBe('Asia/Kolkata');checks++;
  expect(new URL(reportResponse.url()).searchParams.has('end_date')).toBe(false);checks++;
  await expect(page.getByLabel('Through',{exact:true})).toHaveValue(report.end_date);checks++;
  await expect(page.getByLabel('From',{exact:true})).toHaveValue(report.start_date);checks++;
  await expect(page.getByText(/Dates and charts use Asia\/Kolkata/)).toBeVisible();checks++;
  await page.setViewportSize({width:390,height:900});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);checks++;
  await page.waitForLoadState('networkidle');
  expect(errors).toEqual([]);expect(failures).toEqual([]);checks++;
  console.log(JSON.stringify({checks,canonical_customer_id:created.id,real_api:true,viewports:[390,768,1440]}));
 }finally{closing=true;if(context){await Promise.all(context.pages().map(page=>page.close()));await context.unrouteAll({behavior:'wait'});await context.close();}await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
