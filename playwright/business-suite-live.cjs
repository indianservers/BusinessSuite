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
  context=await browser.newContext();const page=await context.newPage(),errors=[],failures=[],trace=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('Browser runtime:',e.message);});
  await page.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
  await page.route(origin+'/**',async route=>{
   try {
   const request=route.request(),url=new URL(request.url());
   if(url.pathname.startsWith('/api/')){
    const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});
    trace.push(request.method()+' '+url.pathname+':'+response.status());
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
  const created=await page.evaluate(async()=>{const r=await window.qaApi.post('/master-data/companies?source=crm',{name:'QA Live المشتركة 客户',legalName:'Fictional Shared Browser Customer Ltd',entityKind:'Company',country:'IN',addresses:[{type:'Billing',line1:'42 Fictional Customer Road',city:'Hyderabad',state:'Telangana',postalCode:'500001',country:'IN'}],roles:['Customer']});return r.data;});
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
  const register=await page.evaluate(async()=>{const {data}=await window.qaApi.post('/srm/pos/sessions',{branch:'Fictional QA branch',register_name:'Shared Customer Browser Counter',opening_cash:0});return data;});
  expect(Number(register.expected_cash)).toBe(0);checks++;
  await page.evaluate(()=>window.qaNavigate('/srm/pos'));
  await page.getByRole('button',{name:'Change sale customer',exact:true}).click();
  await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();
  await page.getByRole('option',{name:saved.name,exact:false}).click();
  await expect(page.locator('.pos-sale-customer')).toContainText(saved.name);checks++;
  const policyReady=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/service-checkout/options'&&response.request().method()==='GET');
  await page.locator('.srm-pos-catalog article').filter({hasText:'QA Fractional service'}).getByRole('button').first().click();
  expect((await policyReady).status()).toBe(200);
  await page.locator('.pos-booking-trigger').click();
  await expect(page.getByText('This service has no scheduling policy yet.',{exact:true})).toBeVisible();checks++;
  await page.getByRole('button',{name:'Close service booking',exact:true}).click();
  await page.getByRole('button',{name:/^Collect /}).click();
  await page.getByRole('dialog').getByRole('button',{name:'Cash',exact:true}).click();
  await expect(page.getByRole('spinbutton',{name:'Payment amount',exact:true})).toHaveValue('117.99');checks++;
  const posted=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/service-checkout'&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Complete Sale',exact:true}).click();
  const nativeResponse=await posted.catch(async error=>{console.error(JSON.stringify({phase:"native-checkout",failures,trace:trace.slice(-25),body:(await page.locator("body").innerText()).slice(-9000)}));throw error;});
  expect(nativeResponse.status()).toBe(201);
  const sent=nativeResponse.request().postDataJSON(),checkout=await nativeResponse.json();
  expect(sent.customer_id).toBe(created.id);expect(sent.buyer_mode).toBe('registered');expect(sent.pos_session_id).toBe(register.session.id);checks++;
  expect(sent.lines).toHaveLength(1);expect(sent.lines[0].line_kind).toBe('unscheduled_service');expect(sent.lines[0].booking).toBeUndefined();checks++;
  expect(checkout.state).toBe('committed');expect(checkout.invoice.status).toBe('paid');
  expect(Number(checkout.invoice.total)).toBe(117.99);expect(Number(checkout.invoice.paid)).toBe(117.99);expect(Number(checkout.invoice.balance)).toBe(0);checks++;
  expect(checkout.receipts).toHaveLength(1);expect(checkout.receipts[0].status).toBe('allocated');expect(Number(checkout.receipts[0].amount)).toBe(117.99);expect(Number(checkout.receipts[0].unallocated)).toBe(0);checks++;
  await expect(page.getByRole('region',{name:'Confirmed sale summary'})).toContainText(checkout.invoice.number);checks++;
  const collected=await page.evaluate(async()=>{const {data}=await window.qaApi.get('/srm/pos/sessions/active');return data;});
  expect(collected.session.id).toBe(register.session.id);expect(Number(collected.cash_sales)).toBe(117.99);expect(Number(collected.expected_cash)).toBe(117.99);expect(collected.unattributed_cash_count).toBe(0);checks++;
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
