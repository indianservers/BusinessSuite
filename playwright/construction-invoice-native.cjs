const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');
const expect=base.configure({timeout:120000});
(async()=>{
  const qa=JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE,'utf8')),bridge=process.env.CONTROL_BRIDGE;
  assert.match(bridge,/^http:\/\/127\.0\.0\.1:\d+$/);
  const root=path.resolve(__dirname,'../frontend');process.chdir(root);
  const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
  const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const p=socket.address().port;socket.close(()=>resolve(p));});});
  const vite=await createServer({root,cacheDir:path.resolve(root,'../.local/construction-invoice-vite-cache'),server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});
  let browser,context,page,closing=false,stage='startup';
  const trace=[],errors=[],paymentBodies=[];let droppedPayment=false;
  try{
    await vite.listen();const origin='http://127.0.0.1:'+vite.httpServer.address().port;
    browser=await chromium.launch();context=await browser.newContext({viewport:{width:1440,height:1100}});
    await context.addInitScript(qa=>{
      sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',qa.branch);
      if(qa.context){sessionStorage.setItem('suite-pack-context',qa.context);sessionStorage.setItem('suite-business-pack-context',qa.context);}
      sessionStorage.setItem('suite-pack-context-owner',JSON.stringify([null,'1',qa.branch]));
      sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:qa.token,refreshToken:null,user:qa.user,isAuthenticated:true},version:0}));
    },qa);
    page=await context.newPage();page.on('pageerror',error=>errors.push(error.stack||error.message));
    await page.route('**/api/**',async route=>{
      try{
        const request=route.request(),url=new URL(request.url());
        const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});
        trace.push({method:request.method(),path:url.pathname,status:response.status(),...(response.status()===403?{detail:await response.text(),organization:request.headers()['x-suite-organization'],branch:request.headers()['x-suite-branch'],pack:request.headers()['x-suite-pack-context']}:{})});
        if(request.method()==='POST' && url.pathname.endsWith('/payments')) {
          paymentBodies.push(request.postDataJSON());
          if(response.status()===201 && !droppedPayment) {droppedPayment=true;await route.abort('failed');return;}
        }
        await route.fulfill({response});
      }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{});}
    });
    await page.goto(origin+`/srm/invoices/${qa.invoice}`);
    await expect(page.getByRole('heading',{name:qa.invoice_number,exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Issue invoice',exact:true})).toHaveCount(0);
    const first=qa.first_amount||'2000.00',final=qa.final_amount||'5080.00';
    stage='desktop first installment';
    await page.getByText('Payment and collection actions',{exact:true}).click();
    await page.getByRole('spinbutton',{name:'Amount received',exact:true}).fill(first);
    await page.getByRole('textbox',{name:'Bank / payment reference',exact:true}).fill('Actual browser installment');
    await page.getByRole('button',{name:'Record received payment',exact:true}).click();
    await expect(page.getByRole('button',{name:'Retry same payment',exact:true})).toBeEnabled();
    await expect(page.getByRole('spinbutton',{name:'Amount received',exact:true})).toBeDisabled();
    await page.reload();
    await page.getByText('Payment and collection actions',{exact:true}).click();
    await expect(page.getByRole('spinbutton',{name:'Amount received',exact:true})).toHaveValue(first);
    await expect(page.getByRole('spinbutton',{name:'Amount received',exact:true})).toBeDisabled();
    await page.getByRole('button',{name:'Retry same payment',exact:true}).click();
    await expect(page.getByText(`Outstanding: ${Number(final)}`,{exact:true})).toBeVisible();
    await expect(page.getByText(new RegExp('Payment '+Number(first)+' .*Receipt #\\d+'))).toBeVisible();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    await page.screenshot({path:path.resolve(root,'../.local/construction-invoice-desktop.png'),fullPage:true});
    stage='mobile final installment';
    await page.setViewportSize({width:390,height:1000});
    const paymentSummary=page.getByText('Payment and collection actions',{exact:true});
    if(await paymentSummary.locator('..').getAttribute('open')===null)await paymentSummary.click();
    await page.getByRole('spinbutton',{name:'Amount received',exact:true}).fill(final);
    await page.getByRole('textbox',{name:'Bank / payment reference',exact:true}).fill('Actual browser final installment');
    await page.getByRole('button',{name:'Record received payment',exact:true}).click();
    await expect(page.getByText('Outstanding: 0',{exact:true})).toBeVisible();
    await expect(page.getByRole('spinbutton',{name:'Amount received',exact:true})).toHaveCount(0);
    await expect(page.getByText('Payment: paid',{exact:true})).toBeVisible();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    await page.screenshot({path:path.resolve(root,'../.local/construction-invoice-mobile.png'),fullPage:true});
    const money=trace.filter(item=>item.method==='POST'&&item.path.includes('/payments'));
    assert.deepEqual(money.map(item=>[item.path,item.status]),Array.from({length:3},()=>[qa.measurement?`/api/v1/srm/industry/records/${qa.measurement}/payments`:`/api/v1/srm/business/invoices/${qa.invoice}/payments`,201]));
    assert.deepEqual(paymentBodies[0],paymentBodies[1]);
    assert.equal(trace.some(item=>item.path===`/api/v1/srm/business/invoices/${qa.invoice}`&&item.status===200),true);
    assert.equal(trace.some(item=>item.path===`/api/v1/srm/documents/invoices/${qa.invoice}`&&item.status===200),true);
    await expect(page.getByText(/^Document controls unavailable\./)).toHaveCount(0);
    for(const suffix of ['/access/enterprise/branding','/notifications/summary','/business-os/modules'])assert.equal(trace.some(item=>item.path==='/api/v1'+suffix&&item.status===200),true,suffix);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.resolve(root,'../.local/construction-invoice-browser-proof.json'),JSON.stringify({stage:'complete',native_http_trace:trace,js_errors:errors,mocked_responses:false,initial_width:qa.width||1440,final_width:390,collection_only_without_invoice_issue:!!qa.measurement,unreviewed_controls:trace.filter(item=>item.status>=400)},null,2));
    console.log('PASS actual App '+(qa.measurement?'Construction':'standard')+' invoice: native ledger, lost committed response, reload, exact retry and installments '+first+'+'+final+', mobile/desktop.');
  }catch(error){if(page)console.error(JSON.stringify({stage,trace,errors,body:(await page.locator('body').innerText()).slice(0,5000)}));throw error;}
  finally{closing=true;if(context){await context.unrouteAll({behavior:'wait'});await context.close();}if(browser)await browser.close();await vite.close();}
})().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;});
