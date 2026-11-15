const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const path=require('node:path');
const expect=baseExpect.configure({timeout:20000});
const bridge=process.env.CONTROL_BRIDGE;
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(bridge||''))throw new Error('Disposable API bridge required');
(async()=>{
 const auth=JSON.parse(process.env.SUITE_QA_AUTH),root=path.resolve(__dirname,'../frontend'),source=auth.module||'crm';
 const {build}=require('../frontend/node_modules/esbuild');
 const bundle=await build({entryPoints:[path.join(root,'scripts/fixtures/common-commercial-live.tsx')],bundle:true,write:false,format:'iife',platform:'browser',alias:{'@':path.join(root,'src')},define:{'import.meta.env':'{}','import.meta.glob':'__qaGlob'},banner:{js:'const __qaGlob=()=>({});'},loader:{'.css':'empty','.svg':'dataurl','.png':'dataurl','.jpg':'dataurl','.webp':'dataurl'},plugins:[{name:'vite-url-assets',setup(build){build.onResolve({filter:/\?url$/},args=>({path:args.path,namespace:'qa-url'}));build.onLoad({filter:/.*/,namespace:'qa-url'},()=>({contents:'export default "data:text/javascript,"',loader:'js'}));}}]});
 const origin='https://commercial.test';
 const browser=await chromium.launch();let checks=0,closing=false;
 try{
  const context=await browser.newContext(),page=await context.newPage(),errors=[],failures=[],trace=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(auth=>{window.qaAuth=auth;window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},auth);
  await page.route(origin+'/**',async route=>{
   try{
    const request=route.request(),url=new URL(request.url());
    if(url.pathname.startsWith('/api/')){
     const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});
     trace.push(request.method()+' '+url.pathname+':'+response.status());
     if(response.status()>=400)failures.push(url.pathname+':'+response.status());
     await route.fulfill({response});
    }else if(url.pathname==='/qa.js')await route.fulfill({contentType:'application/javascript',body:bundle.outputFiles[0].text});
    else if(request.isNavigationRequest())await route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script src="/qa.js"></script>'});else await route.abort();
   }catch(error){if(!closing)failures.push(error.message.split('\n')[0]);await route.abort().catch(()=>{});}
  });
  const navigate=async href=>{await page.evaluate(href=>window.qaNavigate(href),href);};
  const changed=async(action,click)=>{
   const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(action)&&r.request().method()==='POST');
   response.catch(()=>{});
   await click();const r=await response;expect(r.status()).toBe(action==='/lines'?201:200);checks++;return r.json();
  };
  try{
   await page.goto(origin+'/'+source);
   await expect(page.getByRole('navigation',{name:'Commercial documents'}).getByRole('link',{name:'Quotations',exact:true})).toBeVisible();
   const quote=await page.evaluate(async auth=>{
    const today=new Date().toISOString().slice(0,10),expiry=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
    return (await window.qaApi.post('/crm/quotes',{quote_number:'COMMON-BROWSER',company_id:101,deal_id:auth.deal_id,currency:'INR',issue_date:today,expiry_date:expiry})).data;
   },auth);
   await page.getByRole('navigation',{name:'Commercial documents'}).getByRole('link',{name:'Quotations',exact:true}).click();
   await expect(page).toHaveURL(new RegExp(`/common/quotations\\?module=${source}`));
   await expect(page.getByText('COMMON-BROWSER',{exact:true}).first()).toBeVisible();checks++;
   await navigate(`/common/quotations/${quote.id}?module=${source}`);
   await page.getByRole('link',{name:'Open quote builder',exact:true}).click();
   await expect(page).toHaveURL(new RegExp(`/common/quotations/${quote.id}/builder\\?module=${source}`));
   await expect(page.getByRole('heading',{name:'Quote Builder',exact:true})).toBeVisible();checks++;
   const inputs=page.getByPlaceholder('Line item').locator('..').locator('input');
   await inputs.nth(0).fill('Shared browser implementation');await inputs.nth(1).fill('2');await inputs.nth(2).fill('1000');await inputs.nth(3).fill('200');await inputs.nth(4).fill('18');
   await changed('/lines',()=>page.getByRole('button',{name:'Add',exact:true}).click());
   await expect(page.getByText('Shared browser implementation',{exact:true}).first()).toBeVisible();
   await changed('/submit',()=>page.getByRole('button',{name:'Submit for approval',exact:true}).click());
   await page.getByRole('button',{name:'Approve',exact:true}).click();
   await changed('/approve',()=>page.getByRole('alertdialog').getByRole('button',{name:'Approve quote',exact:true}).click());
   await changed('/send',()=>page.getByRole('button',{name:'Send',exact:true}).click());
   await page.getByRole('button',{name:'Accept and convert to SRM',exact:true}).click();
   const accepted=await changed('/accept',()=>page.getByRole('alertdialog').getByRole('button',{name:'Accept and convert',exact:true}).click());
   const orderId=accepted.srmConversion.conversionLog.srm_sales_order_id;
   await page.getByRole('link',{name:'Open sales order',exact:true}).click();
   await expect(page).toHaveURL(new RegExp(`/common/sales-orders/${orderId}\\?module=${source}`));
   await expect(page.getByRole('heading',{name:'Sales Order Detail',exact:true})).toBeVisible();checks++;
   const drafted=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/draft-from-sales-order/${orderId}`)&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Create invoice draft',exact:true}).click();
   const response=await drafted;expect(response.status()).toBe(201);const invoice=await response.json();expect(invoice.total_amount).toBe(2124);checks++;
   await page.getByRole('link',{name:'Open invoice',exact:true}).click();
   await expect(page).toHaveURL(new RegExp(`/common/invoices/${invoice.id}\\?module=${source}`));
   await expect(page.getByRole('heading',{name:invoice.invoice_number,exact:true})).toBeVisible();checks++;
   await changed('/approve',()=>page.getByRole('button',{name:'Issue invoice',exact:true}).click());
   await expect(page.getByText('Invoice issued.',{exact:true})).toBeVisible();
   const managers=[['quotations','Quotations'],['contracts','Contracts'],['purchase-orders','Purchase orders'],['sales-orders','Sales orders'],['invoices','Invoices'],['invoice-drafts','Invoice drafts'],['billing-plans','Billing plans'],['collections','Collections'],['engagements','Engagements'],['payment-requests','Payment requests']];
   const headings={};
   for(const module of ['crm','srm']){
    await navigate('/'+module);
    const menu=page.getByRole('navigation',{name:'Commercial documents'});
    for(const [entity,label]of managers){
     await menu.getByRole('link',{name:label,exact:true}).click();
     await expect(page).toHaveURL(new RegExp(`/common/${entity}\\?module=${module}`));
     await expect(page.getByRole('navigation',{name:'Shared page breadcrumbs'})).toContainText(label);
     const title=entity==='quotations'?'Quotes':label;
     await expect(page.getByRole('heading',{name:new RegExp(`^${title}$`,'i')}).first()).toBeVisible();
     const titles=await page.getByRole('heading',{level:1}).allTextContents();
     if(module==='crm')headings[entity]=titles;else expect(titles).toEqual(headings[entity]);checks++;
    }
    for(const [entity,id,title]of [['quotations',quote.id,'COMMON-BROWSER'],['sales-orders',orderId,'Sales Order Detail'],['contracts',accepted.srmConversion.conversionLog.srm_contract_id,'Contract Detail'],['invoices',invoice.id,invoice.invoice_number]]){
     await navigate(`/common/${entity}/${id}?module=${module}`);
     await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();checks++;
     await page.reload();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();checks++;
    }
    await page.getByRole('link',{name:'← Sales invoices',exact:true}).click();
    await expect(page).toHaveURL(new RegExp(`/common/invoices\\?module=${module}`));checks++;
   }
   await page.setViewportSize({width:390,height:844});
   await navigate(`/common/quotations/${quote.id}/builder?module=srm`);
   await expect(page.getByRole('heading',{name:'Quote Builder',exact:true})).toBeVisible();
   await expect(page.getByRole('link',{name:'Open sales order',exact:true})).toHaveAttribute('href',`/common/sales-orders/${orderId}?module=srm`);checks++;
   await page.setViewportSize({width:1440,height:1000});
   const controls=page.getByRole('region',{name:'Document history and actions'});
   const perform=async(kind,id,module,operation,reason,prepare)=>{
    await navigate(`/common/${kind}/${id}?module=${module}`);
    const start={send:'Send / resend document',revise:'Create revision draft',edit:'Modify draft with reason',archive:'Archive draft',cancel:'Cancel with reason',issue:'Issue purchase order'}[operation];
    await controls.getByRole('button',{name:start,exact:true}).click();
    if(prepare)await prepare();
    await controls.getByRole('textbox',{name:'Document action reason',exact:true}).fill(reason);
    const method=operation==='edit'?'PATCH':operation==='archive'?'DELETE':'POST';
    const suffix=operation==='edit'||operation==='archive'?'':`/${operation}`;
    const pending=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/documents/${kind}/${id}${suffix}`&&r.request().method()===method);
    const submit={send:'Send document',revise:'Create revised draft',edit:'Save document changes',archive:'Confirm archive',cancel:'Confirm cancellation',issue:'Confirm issue'}[operation];
    await controls.getByRole('button',{name:submit,exact:true}).click();
    const response=await pending;expect(response.status()).toBe(operation==='revise'?201:200);checks++;
    const result=await response.json();
    if(operation==='revise')await expect(page).toHaveURL(new RegExp(`/common/${kind}/${result.record.id}\\?module=${module}`));
    else await expect(controls.getByRole('form',{name:'Document action form'})).toHaveCount(0);
    await expect(controls.getByRole('button',{name:'Refresh document controls',exact:true})).toBeEnabled();
    return result;
   };
   for(const module of ['crm','srm']){
    const quoteSend=await perform('quotations',quote.id,module,'send',`QA ${module} recipient requested a copy`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill('billing@example.com'));
    expect(quoteSend.status).toBe('sent');checks++;
    const quoteRevision=await perform('quotations',quote.id,module,'revise',`QA ${module} quotation correction`);
    await perform('quotations',quoteRevision.record.id,module,'edit',`QA ${module} corrected quotation quantity`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
    await perform('quotations',quoteRevision.record.id,module,'archive',`QA ${module} unused revision removed`);
    await controls.locator('summary').filter({hasText:/Document history/}).click();
    await expect(controls.getByText(`Reason: QA ${module} unused revision removed`,{exact:true})).toBeVisible();checks++;
    await navigate(`/common/quotations?module=${module}`);
    const register=page.getByRole('region',{name:'Saved document register'});
    await register.getByRole('textbox',{name:'Search saved documents'}).fill(quoteRevision.number);
    await expect(register.getByText(quoteRevision.number,{exact:true})).toHaveCount(0);
    await register.getByRole('checkbox',{name:'Include archived drafts'}).check();
    await expect(register.getByText(quoteRevision.number,{exact:true})).toBeVisible();checks++;
    const po=await page.evaluate(async()=> (await window.qaApi.post('/srm/procurement/purchase-orders',{vendor_name:'QA Browser supplier',lines:[{description:'QA Browser supplies',quantity:2,unit_price:100,tax_amount:36}]})).data);
    const poSend=await perform('purchase-orders',po.id,module,'send',`QA ${module} supplier requested PO copy`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill('billing@example.com'));
    expect(poSend.status).toBe('sent');checks++;
    const poRevision=await perform('purchase-orders',po.id,module,'revise',`QA ${module} revised supplier schedule`);
    await perform('purchase-orders',poRevision.record.id,module,'edit',`QA ${module} changed supplier quantity`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
    await perform('purchase-orders',poRevision.record.id,module,'issue',`QA ${module} supplier order approved`);
    await perform('purchase-orders',poRevision.record.id,module,'cancel',`QA ${module} supplier order withdrawn`);
    const invoiceSend=await perform('invoices',invoice.id,module,'send',`QA ${module} invoice copy requested`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill('billing@example.com'));
    expect(invoiceSend.status).toBe('sent');checks++;
    const invoiceRevision=await perform('invoices',invoice.id,module,'revise',`QA ${module} corrected invoice draft`);
    await perform('invoices',invoiceRevision.record.id,module,'edit',`QA ${module} invoice quantity corrected`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
    await perform('invoices',invoiceRevision.record.id,module,'archive',`QA ${module} invoice correction not required`);
   }
   expect(errors).toEqual([]);expect(failures).toEqual([]);
   console.log(`PASS (${source}): ${checks} live commercial scenarios; quotation approval, conversion, invoice issue, 10 identical managers in CRM/Sales, detail IDs, refresh and mobile links`);
  }catch(error){console.error(JSON.stringify({errors,failures,trace:trace.slice(-35),body:(await page.locator('body').innerText()).slice(-9000)}));throw error;}
 }finally{closing=true;await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
