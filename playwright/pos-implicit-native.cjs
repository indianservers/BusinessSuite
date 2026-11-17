const path=require('node:path'),assert=require('node:assert/strict');
const{chromium,expect:base}=require('../frontend/node_modules/playwright/test');const expect=base.configure({timeout:30000});
const bridge=process.env.CONTROL_BRIDGE;if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw Error('Disposable real API bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');process.chdir(root);
 const{createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const origin='http://127.0.0.1:'+server.httpServer.address().port,browser=await chromium.launch();const trace=[],attempts=[],errors=[];let context,page,closing=false,drop=auth.case==='swap';
 try{
  context=await browser.newContext({viewport:{width:1440,height:1100}});await context.addInitScript(value=>{window.qaAuth=value;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'}},auth);page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.route(origin+'/**',async route=>{const req=route.request(),url=new URL(req.url());try{
   if(url.pathname.startsWith('/api/')){
    if(drop&&url.pathname==='/api/v1/srm/service-checkout'&&req.method()==='POST'){
    const admin={Authorization:'Bearer '+auth.admin_token,'X-Suite-Organization':'1','X-Suite-Branch':auth.branch};
    let result=await context.request.put(bridge+`/api/v1/access/settings/business-packs/contexts/${auth.context}/grants/${auth.user_id}`,{headers:admin,data:{context_revision:1,role:'hospital_manager',active:false,expected_revision:1,reason:'Native POS context A revocation race proof'}});assert.equal(result.status(),200,await result.text());
    result=await context.request.put(bridge+`/api/v1/access/settings/business-packs/contexts/${auth.other_context}/grants/${auth.user_id}`,{headers:admin,data:{context_revision:1,role:'restaurant_manager',active:true,expected_revision:0,reason:'Native POS sole context B race proof'}});assert.equal(result.status(),200,await result.text());
    }
    const response=await context.request.fetch(bridge+url.pathname+url.search,{method:req.method(),headers:req.headers(),data:req.postDataBuffer()||undefined});
    trace.push({method:req.method(),path:url.pathname,status:response.status(),pack:req.headers()['x-suite-pack-context']||null,realm:req.headers()['x-suite-expected-pack-realm']||null});
    if(url.pathname==='/api/v1/srm/service-checkout'&&req.method()==='POST'){
      attempts.push({payload:req.postDataJSON(),pack:req.headers()['x-suite-pack-context'],status:response.status()});
      if(drop){drop=false;assert.equal(response.status(),403,await response.text());return route.abort('failed');}
    }
    return route.fulfill({response});
   }
   if(req.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/catalog-service-native.tsx");</script>'});
   return route.continue();
  }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{})}});
  await page.goto(origin+'/srm/pos');await page.getByRole('button',{name:'Change sale customer',exact:true}).click();await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();await page.getByRole('option',{name:auth.customer_name,exact:false}).click();
  const selector=await page.evaluate(()=>[sessionStorage.getItem('suite-pack-context'),sessionStorage.getItem('suite-business-pack-context')]);assert.deepEqual(selector,[null,null]);
  const firstCap=trace.find(row=>row.path.endsWith('/industry/capabilities'));assert.ok(firstCap);assert.equal(firstCap.pack,null);
  await expect.poll(()=>trace.some(row=>row.path==='/api/v1/srm/pos/catalog'&&row.status===200)).toBe(true);
  const catalog=trace.find(row=>row.path==='/api/v1/srm/pos/catalog');assert.equal(catalog.pack,auth.context);assert.equal(catalog.realm,'pack');
  await page.getByPlaceholder('Search or scan product, SKU, barcode [F2]').fill(auth.service_name);const service=page.locator('.srm-pos-catalog article').filter({hasText:auth.service_name});await expect(service).toBeVisible();await service.getByRole('button',{name:'Add',exact:true}).click();
  await page.locator('.pos-booking-trigger').click();const scheduling=page.getByRole('region',{name:/Service scheduling/});const key=(await scheduling.getAttribute('aria-label')).replace('Service scheduling ','');
  const options=await page.evaluate(async id=>(await window.qaApi.get('/srm/service-checkout/options',{params:{service_id:id}})).data,auth.service_id);
  await scheduling.getByLabel('Specialist '+key,{exact:true}).selectOption(String(options.specialists[0].eligibility_id));
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:options.specialists[0].timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(auth.starts_at));const part=name=>parts.find(value=>value.type===name).value;
  await scheduling.getByLabel('Booking date '+key,{exact:true}).fill(`${part('year')}-${part('month')}-${part('day')}`);await scheduling.getByLabel('Booking time '+key,{exact:true}).fill(`${part('hour')}:${part('minute')}`);await scheduling.getByRole('button',{name:'Use these booking details',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'Service booking'})).toHaveCount(0);await page.getByRole('button',{name:/^All \(\d+\)$/}).click();await page.getByRole('textbox',{name:'Search or scan items',exact:true}).fill('');await page.getByRole('textbox',{name:'Search or scan items',exact:true}).fill(auth.product_name);const product=page.locator('.srm-pos-catalog article').filter({hasText:auth.product_name});await expect(product).toBeVisible();await product.getByRole('button',{name:'Add',exact:true}).click();
  await page.locator('.pos-extra-bill>summary').click();await page.getByPlaceholder('Bill note / delivery instruction').fill('PRIVATE-CONTEXT-A-NOTE');await page.getByRole('button',{name:/^Collect /}).click();const dialog=page.getByRole('dialog');await dialog.getByRole('button',{name:'Split',exact:true}).click();await dialog.getByLabel('Payment amount',{exact:true}).fill('100');await dialog.getByRole('button',{name:'Add payment mode',exact:true}).click();await dialog.getByRole('combobox').last().click();await page.getByRole('option',{name:'Card',exact:true}).click();await dialog.getByLabel('Payment amount',{exact:true}).nth(1).fill('136');
  const posted=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/service-checkout'&&response.request().method()==='POST').catch(()=>null);
  await dialog.getByRole('button',{name:'Complete Sale',exact:true}).click();
  if(auth.case==='sale'){
    const response=await posted;assert.ok(response);assert.equal(response.status(),201,await response.text());const result=await response.json();assert.equal(result.lines.length,2);assert.equal(result.receipts.length,2);assert.equal(Number(result.invoice.total),236);assert.equal(Number(result.invoice.balance),0);assert.equal(attempts.length,1);assert.equal(attempts[0].pack,auth.context);
    await expect(page.getByRole('region',{name:'Confirmed sale summary',exact:true})).toContainText(result.receipts[0].number);const register=await page.evaluate(async()=>(await window.qaApi.get('/srm/pos/sessions/active')).data);assert.equal(Number(register.expected_cash),100);assert.deepEqual(trace.filter(row=>row.status>=400),[]);
  }else{
    await expect(page.getByRole('button',{name:'Retry same checkout',exact:true})).toBeVisible();assert.equal(attempts.length,1);assert.equal(attempts[0].pack,auth.context);const original=attempts[0].payload;
    await page.getByRole('button',{name:'Retry same checkout',exact:true}).click();
    await expect.poll(()=>trace.some(row=>row.path.endsWith('/industry/capabilities')&&row.status===403)).toBe(true);
    await expect(page.getByRole('button',{name:'Retry same checkout',exact:true})).toBeDisabled();assert.equal(attempts.length,1);
    await page.reload();await expect(page.getByRole('button',{name:'Change sale customer',exact:true})).toBeVisible();await expect(page.getByPlaceholder('Bill note / delivery instruction')).toHaveValue('');assert.equal(await page.getByText('PRIVATE-CONTEXT-A-NOTE',{exact:false}).count(),0);
    await expect.poll(()=>trace.some(row=>row.path==='/api/v1/srm/pos/catalog'&&row.pack===auth.other_context&&row.status===200)).toBe(true);
    const retained=await page.evaluate(uuid=>Object.values(localStorage).some(value=>value.includes(uuid)),original.request_id);assert.equal(retained,true);assert.ok(trace.some(row=>row.path==='/api/v1/srm/pos/catalog'&&row.pack===auth.other_context&&row.status===200));assert.ok(attempts.every(row=>row.pack===auth.context&&row.status===403));
  }
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('suite-pack-context')),null);assert.equal(await page.evaluate(()=>sessionStorage.getItem('suite-business-pack-context')),null);assert.deepEqual(trace.filter(row=>/inventory\/items|business\/customers|held-bills|follow-ups\/options/.test(row.path)),[]);
  if(auth.case==='sale')await page.getByRole('button',{name:'New Sale',exact:true}).click();await page.setViewportSize({width:390,height:1000});await expect(page.getByRole('button',{name:'Change sale customer',exact:true})).toBeVisible();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.screenshot({path:path.resolve(root,'../.local/pack-pos-implicit-'+auth.case+'-mobile.png'),fullPage:true});assert.deepEqual(errors,[]);console.log(JSON.stringify({real_api:true,case:auth.case,initial_selector:null,pinned_context:auth.context,attempts:attempts.length,stable_uuid:new Set(attempts.map(row=>row.payload.request_id)).size===1,viewports:[1440,390]}));
 }catch(error){console.error(JSON.stringify({trace:trace.slice(-35),errors,body:page?(await page.locator('body').innerText()).slice(-4000):null}));throw error}finally{closing=true;if(context){await Promise.all(context.pages().map(item=>item.close()));await context.unrouteAll({behavior:'wait'});await context.close()}await browser.close();await server.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
