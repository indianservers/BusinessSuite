const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const path=require('node:path');const expect=baseExpect.configure({timeout:30000});
const bridge=process.env.CONTROL_BRIDGE;if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw Error('Disposable native bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');process.chdir(root);
 const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const origin='http://127.0.0.1:'+server.httpServer.address().port;const browser=await chromium.launch();let context,closing=false;const errors=[],failures=[],trace=[];
 try{
 context=await browser.newContext({viewport:{width:auth.width||1440,height:1000}});const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
 await page.route(origin+'/**',async route=>{try{const request=route.request(),url=new URL(request.url());
  if(url.pathname.startsWith('/api/')){const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined,timeout:60000});trace.push(request.method()+' '+url.pathname+':'+response.status());if(response.status()>=400)failures.push(url.pathname+':'+response.status());await route.fulfill({response});}
  else if(request.isNavigationRequest())await route.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/pos-selected-live.tsx');</script>`});else await route.continue();
 }catch(error){if(!closing)failures.push('bridge transport: '+error.message.split('\n')[0]);await route.abort().catch(()=>{});}});
 await page.goto(origin+'/srm/pos');
 const cashier=auth.mode==='cashier';
 const mobile=(auth.width||1440)<768;
 await page.getByRole('button',{name:'Change sale customer',exact:true}).click();
 const customerPanel=page.getByRole('dialog',{name:'Sale customer',exact:true});
 if(cashier){
  if(mobile){await expect(customerPanel.getByRole('button',{name:'New customer',exact:true})).toBeDisabled();await customerPanel.getByRole('button',{name:'Change sale customer',exact:true}).click();}
  await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();await page.getByRole('option',{name:'Synthetic customer 101',exact:false}).click();
  if(mobile)await customerPanel.getByRole('button',{name:'Done',exact:true}).click();
 } else {
  if(mobile)await customerPanel.getByRole('button',{name:'New customer',exact:true}).click();
  else {await page.keyboard.press('Escape');await page.locator('.pos-sale-customer').getByRole('button',{name:/^New /}).click();}
  await page.getByLabel('POS customer name',{exact:true}).fill('Native POS selected customer');
  await page.getByLabel('POS customer address',{exact:true}).fill('Actual customer supplied billing address');
  await page.getByLabel('POS customer state',{exact:true}).fill('Telangana');await page.getByLabel('POS customer country',{exact:true}).selectOption('IN');
  if(auth.custom_fields){await page.getByLabel('POS field Customer reference',{exact:true}).fill('Browser supplied reference');await page.getByLabel('POS field Consent answer',{exact:true}).selectOption('false');await page.getByLabel('POS field Initial counter',{exact:true}).fill('0');}
  await page.getByRole('button',{name:'Save customer',exact:true}).click();await expect(page.getByRole('dialog',{name:/^New /})).toHaveCount(0);
 }
 await page.locator('.srm-pos-catalog article').filter({hasText:'QA-STOCK'}).locator('button[data-product-id]').first().click();
 if(cashier){await page.locator('.srm-pos-catalog article').filter({hasText:'QA-SERVICE'}).locator('button[data-product-id]').first().click();await expect(page.locator('section[aria-label^="Service scheduling "]')).toHaveCount(0);}
 for(let index=0;index<(cashier?0:2);index++){
  await page.locator('.srm-pos-catalog article').filter({hasText:'QA-SERVICE'}).locator('button[data-product-id]').first().click();
  if(mobile)await page.getByRole('button',{name:/^Cart/}).click();
  const trigger=page.locator('.pos-booking-trigger').last();await trigger.click();
  const section=page.getByRole('region',{name:/^Service scheduling /});
  const key=(await section.getAttribute('aria-label')).replace('Service scheduling ','');
  await section.getByLabel('Specialist '+key,{exact:true}).selectOption({index:1});
  await section.getByLabel('Booking date '+key,{exact:true}).fill(auth.date);await section.getByLabel('Booking time '+key,{exact:true}).fill(index?'11:00':'10:00');
  await section.getByRole('button',{name:'Use these booking details',exact:true}).click();
  if(mobile)await page.getByRole('button',{name:'Products',exact:true}).click();
 }
 await page.getByRole('button',{name:/^Collect /}).click();const dialog=page.getByRole('dialog');
 await dialog.getByRole('button',{name:'Split',exact:true}).click();await dialog.getByRole('spinbutton',{name:'Payment amount',exact:true}).fill('100');
 await dialog.getByRole('button',{name:'Add payment mode',exact:true}).click();
 await dialog.getByRole('combobox').nth(1).click();await page.getByRole('option',{name:'Card',exact:true}).click();
 await dialog.getByRole('spinbutton',{name:'Payment amount',exact:true}).nth(1).fill(cashier?'136':'254');await dialog.getByRole('textbox',{name:'Payment reference',exact:true}).nth(1).fill('Synthetic terminal receipt');
 const posted=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/service-checkout'&&response.request().method()==='POST',{timeout:60000});
 await page.getByRole('button',{name:'Complete Sale',exact:true}).click();const response=await posted;expect(response.status(),await response.text()).toBe(201);const checkout=await response.json();
 expect(checkout.lines).toHaveLength(cashier?2:3);expect(checkout.lines.filter(line=>line.appointment_id)).toHaveLength(cashier?0:2);expect(checkout.receipts).toHaveLength(2);expect(Number(checkout.invoice.balance)).toBe(0);
 await expect(page.getByRole('region',{name:'Confirmed sale summary'})).toContainText(checkout.invoice.number);
 expect(trace.some(row=>row.includes('/follow-ups/options'))).toBe(false);expect(trace.some(row=>row.includes('/pos/held-bills'))).toBe(false);expect(trace.some(row=>row.includes('/master-data/'))).toBe(false);
 if(cashier)expect(trace.some(row=>row.includes('/service-checkout/options'))).toBe(false);
 expect(failures).toEqual([]);expect(errors).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:path.resolve(root,`../.local/pos-selected-${auth.role||'cashier'}-${auth.width||1440}.png`),fullPage:true});
 console.log(JSON.stringify({status:'passed',source:'real selected POS React + production native FastAPI authentication',invoice_id:checkout.invoice.id,checkout_id:checkout.id,bookings:cashier?0:2,native_receipts:2,stock_lines:1,failures,trace}));
 }catch(error){console.error(JSON.stringify({trace,failures,errors}));throw error;}finally{closing=true;if(context)await context.close();await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
