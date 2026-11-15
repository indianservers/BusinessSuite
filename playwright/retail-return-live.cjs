const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const path=require('node:path');const expect=baseExpect.configure({timeout:30000});
const bridge=process.env.CONTROL_BRIDGE;if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw Error('Disposable native bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');process.chdir(root);
 const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const origin='http://127.0.0.1:'+server.httpServer.address().port,browser=await chromium.launch();let context,closing=false;const failures=[],errors=[],trace=[];
 try {
  context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
  await page.route(origin+'/**',async route=>{try{const request=route.request(),url=new URL(request.url());
   if(url.pathname.startsWith('/api/')) {
    const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined,timeout:90000});
    trace.push(request.method()+' '+url.pathname+':'+response.status());if(response.status()>=400)failures.push(url.pathname+':'+response.status());await route.fulfill({response});
   } else if(request.isNavigationRequest())await route.fulfill({contentType:'text/html',body:`<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/pos-selected-live.tsx');</script>`});
   else await route.continue();
  }catch(error){if(!closing)failures.push('bridge: '+error.message.split('\n')[0]);await route.abort().catch(()=>{});}});
  await page.goto(origin+'/srm/pos');
  await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();await page.getByRole('option',{name:'Synthetic customer 101',exact:false}).click();
  const item=page.locator('.srm-pos-catalog article').filter({hasText:'QA-STOCK'}).getByRole('button').first();await item.click();await item.click();
  await page.getByRole('button',{name:'Payment [F7]',exact:true}).click();
  const posted=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/service-checkout'&&response.request().method()==='POST',{timeout:90000});
  await page.getByRole('button',{name:'Complete Sale',exact:true}).click();const sale=await posted;expect(sale.status(),await sale.text()).toBe(201);const checkout=await sale.json();
  expect(Number(checkout.invoice.paid)).toBe(236);expect(checkout.lines).toHaveLength(1);
  await page.getByText('Return physical items and refund',{exact:true}).click();
  if(auth.already_posted) {
   await page.getByLabel('Retail return item',{exact:true}).selectOption(String(checkout.lines[0].id));
   await page.getByLabel('Retail return quantity',{exact:true}).fill('1');await page.getByLabel('Retail return reason',{exact:true}).fill('Unopened item returned');
   const refund=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/srm/retail/returns'&&response.request().method()==='POST',{timeout:90000});
   const drawer=page.waitForResponse(async response=>new URL(response.url()).pathname==='/api/v1/srm/pos/sessions/active'&&response.request().method()==='GET'&&response.status()===200&&Number((await response.json()).expected_cash)===118,{timeout:90000});
   await page.getByRole('button',{name:'Return items and refund',exact:true}).click();const response=await refund;expect(response.status(),await response.text()).toBe(201);const result=await response.json();
   expect(Number(result.refund_amount)).toBe(118);await expect(page.getByText('Refund completed: 118.00 INR',{exact:true})).toBeVisible();
   expect(result.accounting.credit_note.number).toMatch(/^CN-/);expect(result.accounting.refund.number).toMatch(/^PV-/);
   await drawer;await expect(page.getByText('Expected cash',{exact:true}).locator('..')).toContainText('₹118');
  } else {
   await expect(page.getByText('Post the original invoice and collected receipts in Accounting before refunding.',{exact:true})).toBeVisible();
   await expect(page.getByRole('button',{name:'Return items and refund',exact:true})).toBeDisabled();
   expect(trace.filter(row=>row.startsWith('POST /api/v1/srm/retail/returns:'))).toHaveLength(0);
  }
  await page.waitForTimeout(300);
  expect(failures).toEqual([]);expect(errors).toEqual([]);
  await page.screenshot({path:path.resolve(root,auth.already_posted?'../.local/retail-return-posted-browser.png':'../.local/retail-return-unposted-browser.png'),fullPage:true});
  console.log(JSON.stringify({status:'passed',source:'Actual POS React + native auth/API/stock/FAM',explicit_accounting_posting_fixture:auth.already_posted,checkout_id:checkout.id,failures,trace}));
 }catch(error){console.error(JSON.stringify({errors,failures,trace}));throw error;}finally{closing=true;if(context)await context.close();await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
