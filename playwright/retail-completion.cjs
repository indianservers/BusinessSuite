const path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');const expect=base.configure({timeout:30000});
const bridge=process.env.CONTROL_BRIDGE;if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw Error('Disposable real API bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend');process.chdir(root);
 const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
 const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const port=socket.address().port;socket.close(()=>resolve(port));});});
 const server=await createServer({root,server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});await server.listen();
 const origin='http://127.0.0.1:'+port,browser=await chromium.launch();let context,closing=false,drop=true;const trace=[],errors=[],bodies=[],pictures=[];
 const revealMobileDetails=async(page,number)=>{const records=page.locator('article').filter(number?{hasText:number}:{});await expect(records.first()).toBeVisible();const buttons=records.getByRole('button',{name:'More details',exact:true});while(await buttons.count())await buttons.first().click();};
 const navigate=async(page,url)=>{await page.evaluate(url=>window.qaNavigate(url),url);await page.waitForURL('**'+url);};
 try{
  context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await context.route(origin+'/**',async route=>{const req=route.request(),url=new URL(req.url());try{
   if(url.pathname.startsWith('/api/')){
    const response=await context.request.fetch(bridge+url.pathname+url.search,{method:req.method(),headers:req.headers(),data:req.postDataBuffer()||undefined});
    trace.push({method:req.method(),path:url.pathname,status:response.status()});
    if(req.method()==='POST'&&url.pathname==='/api/v1/srm/retail/stock-receipts'){
     bodies.push(JSON.parse(req.postData()));
     if(drop){drop=false;assert.equal(response.status(),201,await response.text());return route.abort('connectionreset');}
    }
    return route.fulfill({response});
   }
   if(req.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/retail-completion.tsx");</script>'});
   return route.continue();
  }catch(error){if(!closing)errors.push('Bridge: '+error.message);await route.abort().catch(()=>{});}});
  if(auth.legacy){await page.goto(origin+'/legacy-reports-boundary');await expect(page.getByText('Native report fallback mounted',{exact:true})).toBeVisible();assert(!trace.some(row=>row.path==='/api/v1/srm/industry/capabilities'||row.path.startsWith('/api/v1/srm/retail/')));assert.deepEqual(errors,[]);console.log(JSON.stringify({status:'passed',legacy:true,branch:auth.branch,trace}));return;}
  await page.goto(origin+'/srm/inventory/stock-in');
  const preMounted=await context.newPage();preMounted.on('pageerror',error=>errors.push(error.message));await preMounted.goto(origin+'/srm/inventory/stock-in');
  const secondForm=preMounted.getByRole('form',{name:'Retail stock receipt'});await expect(secondForm.getByLabel('Item',{exact:true})).toBeEnabled();
  await secondForm.getByLabel('Item',{exact:true}).selectOption(String(auth.product));await secondForm.getByLabel('Warehouse',{exact:true}).selectOption(String(auth.warehouse));await secondForm.getByLabel('Quantity',{exact:true}).fill('9');
  for(const [index,width] of [1440,390].entries()){
   await page.setViewportSize({width,height:1000});
   if(index)await navigate(page,'/srm/inventory/purchase-receipts');
   const form=page.getByRole('form',{name:'Retail stock receipt'});
   await expect(form.getByLabel('Item',{exact:true})).toBeEnabled();
   await form.getByLabel('Item',{exact:true}).selectOption(String(auth.product));
   await form.getByLabel('Warehouse',{exact:true}).selectOption(String(auth.warehouse));
   await form.getByLabel('Quantity',{exact:true}).fill(index?'1.25':'2.50');await form.getByLabel('Rate',{exact:true}).fill('20');
   await form.getByLabel('Reference',{exact:true}).fill('VISIBLE-'+width);await form.getByLabel('Notes',{exact:true}).fill('Counted on arrival');
   const posted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/retail/stock-receipts'&&r.request().method()==='POST').catch(()=>null);
   await form.getByRole('button',{name:'Post movement',exact:true}).click();
   if(!index){
    await expect(form.getByRole('button',{name:'Retry same receipt',exact:true})).toBeVisible();
    await expect(form.getByRole('alert')).toBeVisible();
    await page.reload();
    const recovered=page.getByRole('form',{name:'Retail stock receipt'});
    await expect(recovered.getByLabel('Quantity',{exact:true})).toHaveValue('2.50');
    await expect(recovered.getByLabel('Quantity',{exact:true})).toBeDisabled();
    await secondForm.getByRole('button',{name:'Post movement',exact:true}).click();await expect(preMounted.getByText(/Stock receipt posted: RGRN-/)).toBeVisible();
    assert.deepEqual(bodies[0],bodies[1]);await preMounted.close();
    const retry=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/retail/stock-receipts'&&r.request().method()==='POST');
    await recovered.getByRole('button',{name:'Retry same receipt',exact:true}).click();assert.equal((await retry).status(),201);
    assert.deepEqual(bodies[0],bodies[2]);
   }else{const response=await posted;assert(response);assert.equal(response.status(),201,await response.text());}
   await expect(page.getByText(/Stock receipt posted: RGRN-/)).toBeVisible();
   const receiptNumber=(await page.getByText(/Stock receipt posted: RGRN-/).innerText()).split(': ')[1];
   if(index)await revealMobileDetails(page,receiptNumber);await expect(page.getByText('VISIBLE-'+width,{exact:true})).toBeVisible();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Stock screen overflows viewport');
   const picture=path.resolve(root,`../.local/retail-stock-${auth.implicit?'implicit':'explicit'}-${width}.png`);await page.screenshot({path:picture,fullPage:true});pictures.push(picture);
   const refreshed=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/retail/stock'&&r.status()===200);await page.getByRole('button',{name:'Refresh',exact:true}).click();await refreshed;
   await navigate(page,'/srm/inventory/stock-summary');await expect(page.getByText('QA-STOCK',{exact:false}).first()).toBeVisible();
   await navigate(page,'/srm/inventory/warehouse-stock');await expect(page.getByText('QA-STOCK',{exact:false}).first()).toBeVisible();
   await navigate(page,'/srm/inventory/grn');if(index)await revealMobileDetails(page,receiptNumber);await expect(page.getByText('VISIBLE-'+width,{exact:true})).toBeVisible();
   await navigate(page,'/srm/pos');
   await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();await page.getByRole('option',{name:'Synthetic customer 101',exact:false}).click();
   await page.locator('.srm-pos-catalog article').filter({hasText:'QA-STOCK'}).getByRole('button').first().click();
   await page.getByRole('button',{name:'Payment [F7]',exact:true}).click();
   if(index)await page.getByRole('dialog').getByRole('button',{name:'Card',exact:true}).click();
   const sale=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/service-checkout'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Complete Sale',exact:true}).click();const result=await sale;assert.equal(result.status(),201,await result.text());
   const data=await result.json();assert.equal(data.invoice.paid,'118.00');assert.equal(data.receipts[0].method,index?'card':'cash');
   const daily=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/retail/reports/daily'&&r.status()===200);
   await navigate(page,'/srm/reports');const dailyData=await (await daily).json();assert.equal(dailyData.sales[0].count,index+1);assert.equal(Number(dailyData.sales[0].gross),118*(index+1));await expect(page.getByText('Daily registers',{exact:true})).toBeVisible();
   await expect(page.getByRole('heading',{name:'Sales',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Collections',exact:true})).toBeVisible();
   const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV',exact:true}).click();assert((await download).suggestedFilename().includes('retail-Sales'));
   await page.getByRole('heading',{name:'Daily registers',exact:true}).locator('../..').getByRole('button',{name:'View details',exact:true}).click();if(index){await revealMobileDetails(page);await expect(page.locator('.udg-record-field small').filter({hasText:/^lifetime expected cash$/i})).toBeVisible();}else{await page.getByRole('columnheader',{name:/lifetime expected cash/i}).scrollIntoViewIfNeeded();await expect(page.getByRole('columnheader',{name:/lifetime expected cash/i})).toBeVisible();}
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),JSON.stringify(await page.evaluate(()=>({message:'Report screen overflows viewport',width:innerWidth,overflow:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).slice(0,15).map(el=>({tag:el.tagName,class:el.className,width:el.getBoundingClientRect().width}))}))));
   const report=path.resolve(root,`../.local/retail-report-${auth.implicit?'implicit':'explicit'}-${width}.png`);await page.screenshot({path:report,fullPage:true});pictures.push(report);
   await navigate(page,'/srm/inventory/reports');await expect(page.getByText('Daily registers',{exact:true})).toBeVisible();
  }
  const failures=trace.filter(row=>row.status>=400);assert.deepEqual(failures,[]);assert.deepEqual(errors,[]);
  assert(!trace.some(row=>/^\/api\/v1\/srm\/(inventory\/|procurement\/|reports$)/.test(row.path)),'Retail mounted a blocked generic endpoint');
  if(auth.implicit)assert.equal(await page.evaluate(()=>sessionStorage.getItem('suite-pack-context')),null);
  const evidence={status:'passed',widths:[1440,390],implicit:auth.implicit,receipt_posts:bodies.length,lost_response_replayed_exactly:true,pre_mounted_tab_reused_pending_body:true,failures,errors,pictures,trace};
  fs.writeFileSync(path.resolve(root,`../.local/retail-browser-${auth.implicit?'implicit':'explicit'}.json`),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
 }catch(error){console.error(JSON.stringify({errors,trace,pictures}));throw error;}finally{closing=true;if(context)await context.close();await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
