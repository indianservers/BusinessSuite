const assert=require('node:assert/strict');
const path=require('node:path');
const net=require('node:net');
const {chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:30000});
const catalog=require('../../backend/app/core/business_profiles.json');
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(error=>error?reject(error):resolve(p));});});

(async()=>{
  const root=path.resolve(__dirname,'..');process.chdir(root);
  const {createServer}=await import('vite');
  const server=await createServer({root,cacheDir:path.resolve(root,'../.local/invoice-private-vite-cache'),server:{host:'127.0.0.1',port:await freePort(),strictPort:true,hmr:false,watch:null}});
  await server.listen();
  const origin='http://127.0.0.1:'+server.httpServer.address().port;
  const browser=await chromium.launch();
  const context=await browser.newContext({viewport:{width:1440,height:1100}});
  const page=await context.newPage();
  const errors=[],unexpected=[],posts=[];
  let holdB=null,holdPayment=null,paymentSeen=false,closing=false,stage='initial';
  page.on('pageerror',error=>errors.push(error.message));
  await page.route(origin+'/**',async route=>{
    const request=route.request(),url=new URL(request.url());
    try{
      if(url.pathname.startsWith('/api/')){
        const company=request.headers()['x-suite-organization']==='2'?2:1,name=company===1?'A':'B';
        let body;
        if(request.method()==='POST'){
          posts.push({path:url.pathname,company});
          if(url.pathname==='/api/v1/srm/industry/records/101/payments'){
            paymentSeen=true;if(holdPayment)await holdPayment;
            body={receipt_id:111,invoice:{balance_amount:'987.66'}};
          }else{unexpected.push(request.method()+' '+url.pathname);body={};}
        }else if(url.pathname==='/api/v1/srm/business/invoices/3'){
          if(request.headers()['x-suite-branch']==='2')return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'Invoice not found'})});
          if(company===2&&holdB)await holdB;
          body={id:3,invoice_number:'PRIVATE-'+name+'-INVOICE',customer_id:100+company,currency:'INR',
            source_type:'industry_measurement',source_id:company*100+1,construction_measurement_id:company*100+1,
            total_amount:'1000.00',paid_amount:'0.00',balance_amount:'1000.00',document_status:'issued',payment_status:'unpaid',delivery_status:'not_sent',
            can_record_payment:true,can_issue:false,can_edit:false,context:{customer_snapshot:{name:'PRIVATE-'+name+'-CUSTOMER',address:'Actual source address'}},
            lines:[{id:1,description:'Certified work '+name,quantity:'1',unit_price:'1000.00',tax_amount:'0.00',discount_amount:'0.00',line_total:'1000.00'}],
            history:[{id:1,created_at:'2026-11-15',to_status:'approved',notes:'PRIVATE-'+name+'-HISTORY'}],deliveries:[],payments:[]};
        }else if(url.pathname==='/api/v1/access/settings/business-profile/effective')body={business_type:'construction',terms:{...catalog.terms,...catalog.profiles.find(p=>p.id==='construction').terms}};
        else{unexpected.push(request.method()+' '+url.pathname);body=[];}
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
      }
      if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/invoice-private-scope.tsx");</script>'});
      return route.continue();
    }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{});}
  });
  try{
    await page.goto(origin+'/invoice-private-scope-qa');
    await expect(page.getByRole('heading',{name:'PRIVATE-A-INVOICE',exact:true})).toBeVisible({timeout:120000});
    await page.getByText('Payment and collection actions',{exact:true}).click();
    await page.getByRole('spinbutton',{name:'Amount received',exact:true}).fill('12.34');
    await page.getByRole('textbox',{name:'Bank / payment reference',exact:true}).fill('PRIVATE-A-PAYMENT');
    let releasePayment;holdPayment=new Promise(resolve=>{releasePayment=resolve;});
    await page.getByRole('button',{name:'Record received payment',exact:true}).click();
    await expect.poll(()=>paymentSeen).toBe(true);
    stage='same-user company switch during held payment';
    let releaseB;holdB=new Promise(resolve=>{releaseB=resolve;});
    await page.evaluate(()=>window.switchInvoiceOwner('B'));
    await expect(page.getByRole('heading',{name:'PRIVATE-A-INVOICE',exact:true})).toHaveCount(0);
    await expect(page.getByText(/PRIVATE-A-HISTORY/)).toHaveCount(0);
    await expect(page.locator('input[value="PRIVATE-A-PAYMENT"]')).toHaveCount(0);
    releaseB();holdB=null;
    await expect(page.getByRole('heading',{name:'PRIVATE-B-INVOICE',exact:true})).toBeVisible();
    await page.getByText('Payment and collection actions',{exact:true}).click();
    await page.getByRole('spinbutton',{name:'Amount received',exact:true}).fill('33.00');
    await page.getByRole('textbox',{name:'Bank / payment reference',exact:true}).fill('PRIVATE-B-CURRENT');
    releasePayment();holdPayment=null;
    await expect(page.getByRole('textbox',{name:'Bank / payment reference',exact:true})).toHaveValue('PRIVATE-B-CURRENT');
    await expect(page.getByText('Receipt #111 saved and applied to this invoice.',{exact:true})).toHaveCount(0);
    stage='mobile branch reset';
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(()=>window.switchInvoiceOwner('B',2));
    await expect(page.getByRole('heading',{name:'PRIVATE-B-INVOICE',exact:true})).toHaveCount(0);
    await expect(page.getByRole('alert')).toContainText('Invoice unavailable');
    await expect(page.getByRole('textbox',{name:'Bank / payment reference',exact:true})).toHaveCount(0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.deepEqual(posts,[{path:'/api/v1/srm/industry/records/101/payments',company:1}]);
    assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
    console.log('PASS Invoice UI: same-user company/branch changes clear private data and payment drafts; late payment cannot affect new owner; create-only collector uses certified Construction endpoint; mobile layout contained.');
  }catch(error){console.error(JSON.stringify({stage,errors,unexpected,body:(await page.locator('body').innerText()).slice(0,4000)}));throw error;}
  finally{closing=true;await context.close();await browser.close();await server.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
