// Run against the real local app. Credentials are supplied only through the environment.
const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const fs=require('node:fs'),path=require('node:path');
const expect=baseExpect.configure({timeout:30000});
const origin=process.env.DOCUMENT_QA_BASE||'http://127.0.0.1:5173';
if(!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin))throw Error('Local app required');
const password=process.env.DOCUMENT_QA_PASSWORD;
if(!password)throw Error('Set DOCUMENT_QA_PASSWORD for the local test account');
const saved=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../backend/.tmp-crm-local-auth.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch();let checks=0,qaPage;
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1100}}),page=await context.newPage();qaPage=page;
  page.on('pageerror',error=>console.error('Local browser runtime:',error.message));
  page.on('response',async response=>{const url=new URL(response.url());if(url.pathname==='/api/v1/srm/documents/purchase-orders'&&url.searchParams.get('search')){try{const value=await response.json();console.log('Local PO register:',response.status(),url.search,JSON.stringify((value.items||[]).map(row=>({id:row.id,number:row.number,status:row.status}))));}catch{}}});
  let credentials;
  if(process.env.DOCUMENT_QA_REUSE_SESSION==='1'){
   const session=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../backend/.tmp-document-local-auth.json'),'utf8'));
   const authenticated={Authorization:'Bearer '+session.token};
   const [identity,access]=await Promise.all([context.request.get(origin+'/api/v1/auth/me',{headers:authenticated}),context.request.get(origin+'/api/v1/access/me',{headers:authenticated})]);
   expect(identity.status()).toBe(200);expect(access.status()).toBe(200);checks++;
   const user=await identity.json(),grants=await access.json(),role=typeof user.role==='string'?user.role:user.role?.name;
   await page.addInitScript(({token,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{user,accessToken:token,refreshToken:null,isAuthenticated:true},version:0})),{token:session.token,user:{...user,role,primary_role:role,access:grants}});
   credentials={access_token:session.token};
   await page.goto(origin+'/crm');
  }else{
   await page.goto(origin+'/crm/login');
   try{await page.getByLabel('Email address',{exact:true}).fill(saved.user.email);}catch(error){throw Error(error.message+' | Login page: '+(await page.locator('body').innerText()).slice(0,1400));}
   await page.getByLabel('Password',{exact:true}).fill(password);
   const login=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/auth/login'&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Sign in',exact:true}).click();
   const response=await login;expect(response.status()).toBe(200);checks++;
   credentials=await response.json();
   fs.writeFileSync(path.resolve(__dirname,'../backend/.tmp-document-local-auth.json'),JSON.stringify({token:credentials.access_token}));
  }
  const headers={Authorization:'Bearer '+credentials.access_token,'X-Suite-Organization':'1'};
  const request=async(method,endpoint,data)=>{
   for(let attempt=0;attempt<8;attempt++){
    const r=await context.request.fetch(origin+'/api/v1'+endpoint,{method,headers,data});
    if(r.status()===429){await page.waitForTimeout(Math.min(30,Math.max(2,Number(r.headers()['retry-after'])||10))*1000);continue;}
    if(!r.ok())throw Error(`${method} ${endpoint}: ${r.status()} ${(await r.text()).slice(0,250)}`);
    return r.json();
   }
   throw Error('Local request limit remained active; wait for the current window to expire');
  };
  const branches=await request('GET','/branches/context');
  const branch=branches.branches.find(row=>row.can_write&&row.is_active);
  if(!branch)throw Error('No writable local branch for QA');
  headers['X-Suite-Branch']=String(branch.id);
  await page.waitForFunction(()=>!!JSON.parse(sessionStorage.getItem('hrms-auth')||'{}').state?.accessToken);
  await page.evaluate(branch=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',String(branch));},branch.id);
  const suffix=Date.now().toString(36).toUpperCase(),today=new Date().toISOString().slice(0,10),expiry=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
  const buyer=await request('POST','/master-data/companies?source=crm',{name:`QA Document Controls ${suffix}`,entityKind:'Company',roles:['Customer','Vendor'],email:`qa-documents+${suffix.toLowerCase()}@example.com`,country:'IN',addresses:[{type:'Billing',line1:'QA test address',city:'Hyderabad',state:'Telangana',postalCode:'500001',country:'IN'}]});
  const pipeline=await request('POST','/crm/pipelines',{name:`QA MAIN documents ${suffix}`});
  const stage=await request('POST',`/crm/pipelines/${pipeline.id}/stages`,{name:'QA open',probability:10,is_won:false,is_lost:false});
  const controls=page.getByRole('region',{name:'Document history and actions'});
  const readyControls=async()=>{
   for(let retry=0;retry<9;retry++){
    await expect.poll(async()=>await controls.getByRole('heading',{name:'Record history and actions',exact:true}).count()>0 && !await controls.locator('fieldset').first().evaluate(el=>el.disabled)||await controls.getByRole('alert').count()>0,{timeout:120000}).toBeTruthy();
    if(await controls.getByRole('heading',{name:'Record history and actions',exact:true}).count())return;
    const message=await controls.getByRole('alert').innerText();
    if(!/request limit/i.test(message))throw Error(message);
    console.log('Local QA: waiting for document controls request window');
    await page.waitForTimeout(15000);await controls.getByRole('button',{name:'Refresh document controls',exact:true}).click();
   }
   throw Error('Document controls request limit remained active');
  };
  const go=async destination=>{await page.waitForTimeout(2500);await page.waitForLoadState('networkidle');await page.evaluate(destination=>{const state={...history.state,idx:(history.state?.idx||0)+1,key:crypto.randomUUID()};history.pushState(state,'',destination);dispatchEvent(new PopStateEvent('popstate',{state}));},destination);};
  const open=async(kind,id,module)=>{await go(`/common/${kind}/${id}?module=${module}`);await page.waitForLoadState('networkidle');await readyControls();};
  const perform=async(mode,reason,prepare)=>{
   await readyControls();
   console.log(`Local QA action: ${mode} ${new URL(page.url()).pathname}`);
   const start={revise:'Create revision draft',edit:'Modify draft with reason',archive:'Archive draft',cancel:'Cancel with reason',send:'Send / resend document',issue:'Issue purchase order'}[mode];
   try{await controls.getByRole('button',{name:start,exact:true}).click();}catch(error){throw Error(error.message+' | URL: '+page.url()+' | Page: '+(await page.locator('body').innerText()).slice(-3000));}
   if(prepare)await prepare();
   await controls.getByRole('textbox',{name:'Document action reason'}).fill(reason);
   const method=mode==='edit'?'PATCH':mode==='archive'?'DELETE':'POST';
   const submit={revise:'Create revised draft',edit:'Save document changes',archive:'Confirm archive',cancel:'Confirm cancellation',send:'Send document',issue:'Confirm issue'}[mode];
   let r;
   for(let retry=0;retry<8;retry++){
    const pending=page.waitForResponse(r=>new URL(r.url()).pathname.includes('/srm/documents/')&&r.request().method()===method);
    await controls.getByRole('button',{name:submit,exact:true}).click();r=await pending;
    if(r.status()!==429)break;
    const delay=Math.min(30,Math.max(5,Number(r.headers()['retry-after'])||15));console.log(`Respecting local write request limit: ${delay}s`);await page.waitForTimeout(delay*1000);
   }
   if(r.status()!==(mode==='revise'?201:200))throw Error(`Action ${mode}: ${r.status()} ${await r.text()}`);checks++;
   const value=await r.json();
   await expect(controls.getByRole('form',{name:'Document action form'})).toHaveCount(0);
   await readyControls();await page.waitForTimeout(2000);
   return value;
  };
  const output=path.resolve(__dirname,'../outputs/document-records-local');fs.mkdirSync(output,{recursive:true});
  const cooldown=async()=>{console.log('Local QA: allowing the request window to reset');await page.waitForTimeout(45000);};
  const postClick=async(endpoint,click,status=200)=>{
   console.log('Local native action:',endpoint);
   for(let retry=0;retry<5;retry++){const button=page.getByRole('button',{name:'Retry loading record',exact:true});if(!await button.isVisible())break;await page.waitForTimeout(15000);await button.click();await page.waitForLoadState('networkidle');}
   let response;
   for(let retry=0;retry<8;retry++){
    const pending=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(endpoint)&&r.request().method()==='POST',{timeout:120000});pending.catch(()=>{});
    await click();response=await pending;
    if(response.status()!==429)break;
    await page.waitForTimeout(Math.min(30,Math.max(5,Number(response.headers()['retry-after'])||15))*1000);
   }
   if(response.status()!==status)throw Error(`${endpoint}: ${response.status()} ${await response.text()}`);
   checks++;return response.json();
  };
  const selectCompany=async name=>{
   await page.getByRole('combobox',{name:`Search ${name.toLowerCase()}`,exact:true}).fill(buyer.name);
   await page.getByRole('option').filter({hasText:buyer.name}).click();
  };
  const evidence=[];
  const saveEvidence=()=>fs.writeFileSync(path.join(output,'main-app-progress.json'),JSON.stringify({origin,checks,records:evidence},null,2));
  for(const module of process.env.DOCUMENT_QA_MODULE?[process.env.DOCUMENT_QA_MODULE]:['crm','srm']){
   console.log('MAIN APP module:',module);
   let quote,revised,orderId,contractId,invoice,po;
   if((process.env.DOCUMENT_QA_RESUME_AFTER_INVOICE==='1'||process.env.DOCUMENT_QA_RESUME_AFTER_CORE==='1') && module==='crm'){
    const prior=JSON.parse(fs.readFileSync(path.join(output,'main-app-progress.json'),'utf8'));
    const id=kind=>prior.records.find(row=>row.module===module&&row.kind===kind).id;
    quote=await request('GET',`/crm/quotes/${id('quotations')}`);orderId=id('sales-orders');contractId=id('contracts');
    const source=await request('GET',`/srm/documents/quotations/${quote.id}`);
    const revisionId=source.history.find(row=>row.action==='revision_created'&&row.reason===`QA ${module} main quotation revision`).after.record.id;
    revised=await request('GET',`/srm/documents/quotations/${revisionId}`);
    const savedInvoice=await request('GET',`/srm/documents/invoices/${id('invoices')}`);invoice=savedInvoice.record;
    expect(savedInvoice.record.status).toBe('cancelled');expect(revised.removed).toBe(true);checks+=2+prior.checks;
    evidence.push(...prior.records.filter(row=>row.module===module));
    await open('invoices',invoice.id,module);await controls.locator('summary').filter({hasText:/Document history/}).click();
    await expect(controls.getByText(`Reason: QA ${module} main invoice test completed`,{exact:true}).first()).toBeVisible();checks++;
    await page.screenshot({path:path.join(output,`${module}-main-invoice-history.png`),fullPage:true});
   }else{
   const deal=await request('POST','/crm/deals',{name:`QA MAIN deal ${module} ${suffix}`,company_id:buyer.id,pipeline_id:pipeline.id,stage_id:stage.id,status:'Open',amount:40,currency:'INR'});
   await go(`/common/quotations?module=${module}`);
   await page.getByRole('button',{name:'Create Quote',exact:true}).click();
   const dialog=page.getByRole('dialog');
   await dialog.getByPlaceholder('QT-2026-001',{exact:true}).fill(`QA-MAIN-${module}-${suffix}`);
   await selectCompany('Customer');
   await dialog.getByLabel('Linked deal',{exact:true}).selectOption(String(deal.id));
   await dialog.locator('input[type=date]').nth(0).fill(today);
   await dialog.locator('input[type=date]').nth(1).fill(expiry);
   quote=await postClick('/crm/quotations',()=>dialog.getByRole('button',{name:'Create',exact:true}).click(),201);
   evidence.push({module,kind:'quotations',id:quote.id});
   saveEvidence();
   await open('quotations',quote.id,module);
   await page.getByRole('link',{name:'Open quote builder',exact:true}).click();
   const inputs=page.getByPlaceholder('Line item').locator('..').locator('input');
   for(const [i,value] of ['QA main app service','2','20','0','18'].entries())await inputs.nth(i).fill(value);
   await postClick(`/crm/quotes/${quote.id}/lines`,()=>page.getByRole('button',{name:'Add',exact:true}).click(),201);
   await postClick(`/crm/quotes/${quote.id}/submit`,()=>page.getByRole('button',{name:'Submit for approval',exact:true}).click());
   await page.getByRole('button',{name:'Approve',exact:true}).click();
   await postClick(`/crm/quotes/${quote.id}/approve`,()=>page.getByRole('alertdialog').getByRole('button',{name:'Approve quote',exact:true}).click());
   await postClick(`/crm/quotes/${quote.id}/send`,()=>page.getByRole('button',{name:'Send',exact:true}).click());
   await open('quotations',quote.id,module);
   const sent=await perform('send',`QA ${module} main resend`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill(buyer.email));
   expect(sent.status).toBe('sent');checks++;
   revised=await perform('revise',`QA ${module} main quotation revision`);
   await perform('edit',`QA ${module} main quotation correction`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
   await perform('archive',`QA ${module} main quotation archived`);
   await controls.locator('summary').filter({hasText:/Document history/}).click();
   await expect(controls.getByText(`Reason: QA ${module} main quotation correction`,{exact:true}).first()).toBeVisible();checks++;
   await page.screenshot({path:path.join(output,`${module}-main-quotation-history.png`),fullPage:true});await cooldown();
   await open('quotations',quote.id,module);await page.getByRole('link',{name:'Open quote builder',exact:true}).click();
   await page.getByRole('button',{name:'Accept and convert to SRM',exact:true}).click();
   const accepted=await postClick(`/crm/quotes/${quote.id}/accept`,()=>page.getByRole('alertdialog').getByRole('button',{name:'Accept and convert',exact:true}).click());
   orderId=accepted.srmConversion.conversionLog.srm_sales_order_id;contractId=accepted.srmConversion.conversionLog.srm_contract_id;
   evidence.push({module,kind:'sales-orders',id:orderId},{module,kind:'contracts',id:contractId});
   await page.getByRole('link',{name:'Open sales order',exact:true}).click();
   await postClick(`/srm/sales-orders/${orderId}/submit`,()=>page.getByRole('button',{name:'Submit order for approval',exact:true}).click());
   await postClick(`/srm/sales-orders/${orderId}/confirm`,()=>page.getByRole('button',{name:'Confirm sales order',exact:true}).click());
   invoice=await postClick(`/draft-from-sales-order/${orderId}`,()=>page.getByRole('button',{name:'Create invoice draft',exact:true}).click(),201);
   expect(invoice.total_amount).toBe(47.2);checks++;
   evidence.push({module,kind:'invoices',id:invoice.id});saveEvidence();
   await page.getByRole('link',{name:'Open invoice',exact:true}).click();
   await perform('edit',`QA ${module} main invoice date correction`,()=>controls.getByLabel('Document Due Date',{exact:true}).fill(expiry));
   await postClick(`/srm/invoices/${invoice.id}/approve`,()=>page.getByRole('button',{name:'Issue invoice',exact:true}).click());
   await open('invoices',invoice.id,module);
   const delivery=await perform('send',`QA ${module} main invoice resend`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill(buyer.email));expect(delivery.status).toBe('sent');checks++;
   await perform('revise',`QA ${module} main invoice revision`);
   await perform('edit',`QA ${module} main invoice amount correction`,()=>controls.getByRole('spinbutton',{name:'Line 1 Unit Price',exact:true}).fill('30'));
   await perform('archive',`QA ${module} main invoice draft archived`);
   await open('invoices',invoice.id,module);await perform('cancel',`QA ${module} main invoice test completed`);
   await controls.locator('summary').filter({hasText:/Document history/}).click();
   await expect(controls.getByText(`Reason: QA ${module} main invoice test completed`,{exact:true}).first()).toBeVisible();checks++;
   await page.screenshot({path:path.join(output,`${module}-main-invoice-history.png`),fullPage:true});await cooldown();
   }
   if(process.env.DOCUMENT_QA_RESUME_AFTER_CORE==='1' && module==='crm'){
    const prior=JSON.parse(fs.readFileSync(path.join(output,'main-app-progress.json'),'utf8'));
    const id=prior.records.find(row=>row.module===module&&row.kind==='purchase-orders').id;
    po=(await request('GET',`/srm/documents/purchase-orders/${id}`)).record;
    expect(po.status).toBe('cancelled');checks++;
   }else{
   await go(`/common/purchase-orders?module=${module}`);
   await page.getByRole('button',{name:'Create purchase order',exact:true}).click();await selectCompany('Vendor');
   for(const label of ['Purchase product','Purchase warehouse']){
    const select=page.getByLabel(label,{exact:true});await expect.poll(()=>select.locator('option').count()).toBeGreaterThan(1);
    await select.selectOption(await select.locator('option').nth(1).getAttribute('value'));
   }
   await page.getByLabel('Order quantity',{exact:true}).fill('2');await page.getByLabel('Order unit price',{exact:true}).fill('20');
   po=await postClick('/srm/procurement/purchase-orders',()=>page.getByRole('button',{name:'Create PO',exact:true}).first().click(),201);
   evidence.push({module,kind:'purchase-orders',id:po.id});saveEvidence();
   await open('purchase-orders',po.id,module);
   const poSend=await perform('send',`QA ${module} main PO resend`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill(buyer.email));expect(poSend.status).toBe('sent');checks++;
   await perform('revise',`QA ${module} main PO revision`);
   await perform('edit',`QA ${module} main PO correction`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
   await perform('archive',`QA ${module} main PO draft archived`);
   await open('purchase-orders',po.id,module);await perform('cancel',`QA ${module} main PO test completed`);await cooldown();
   for(const [kind,id] of [['sales-orders',orderId],['contracts',contractId]]){
    await open(kind,id,module);
    if(kind==='contracts')await postClick(`/srm/contracts/${id}/activate`,()=>page.getByRole('button',{name:'Activate contract',exact:true}).click());
    await readyControls();const row=await request('GET',`/srm/documents/${kind}/${id}`);
    if(!row.editable){const send=await perform('send',`QA ${module} main ${kind} resend`,()=>controls.getByRole('textbox',{name:'Document recipient email'}).fill(buyer.email));expect(send.status).toBe('sent');checks++;}
    await perform('revise',`QA ${module} main ${kind} revision`);
    await perform('edit',`QA ${module} main ${kind} correction`,()=>controls.getByRole('textbox',{name:'Document Title',exact:true}).fill(`QA main ${kind} corrected`));
    await perform('archive',`QA ${module} main ${kind} draft archived`);
    await open(kind,id,module); // Converted records retain their delivery dependencies.
   if(!row.editable){
    await controls.getByRole('button',{name:'Cancel with reason',exact:true}).click();
    await controls.getByRole('textbox',{name:'Document action reason'}).fill('QA validate linked delivery cancellation guard');
    const blocked=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/documents/${kind}/${id}/cancel`));
    await controls.getByRole('button',{name:'Confirm cancellation',exact:true}).click();expect((await blocked).status()).toBe(409);checks++;
    await controls.getByRole('button',{name:'Close action form',exact:true}).click();
   }
    await controls.locator('summary').filter({hasText:/Document history/}).click();
    await expect(controls.getByText(`Reason: QA ${module} main ${kind} revision`,{exact:true}).first()).toBeVisible();checks++;await cooldown();
   }
   }
   // Unstarted confirmation scaffolding is retained and cancelled with the order.
   for(const [kind,id] of [['quotations',quote.id],['sales-orders',orderId],['contracts',contractId]]){
    await open(kind,id,module);const revision=await perform('revise',`QA ${module} cancellation specimen ${kind}`);
    if(kind==='quotations'){
     await page.getByRole('link',{name:'Open quote builder',exact:true}).click();
     await postClick(`/crm/quotes/${revision.record.id}/submit`,()=>page.getByRole('button',{name:'Submit for approval',exact:true}).click());
     await page.getByRole('button',{name:'Approve',exact:true}).click();
     await postClick(`/crm/quotes/${revision.record.id}/approve`,()=>page.getByRole('alertdialog').getByRole('button',{name:'Approve quote',exact:true}).click());
     await postClick(`/crm/quotes/${revision.record.id}/send`,()=>page.getByRole('button',{name:'Send',exact:true}).click());
    }else if(kind==='sales-orders'){
     await postClick(`/srm/sales-orders/${revision.record.id}/submit`,()=>page.getByRole('button',{name:'Submit order for approval',exact:true}).click());
     await postClick(`/srm/sales-orders/${revision.record.id}/confirm`,()=>page.getByRole('button',{name:'Confirm sales order',exact:true}).click());
    }else await postClick(`/srm/contracts/${revision.record.id}/activate`,()=>page.getByRole('button',{name:'Activate contract',exact:true}).click());
    await open(kind,revision.record.id,module);await perform('cancel',`QA ${module} ${kind} cancellation completed`);
    await controls.locator('summary').filter({hasText:/Document history/}).click();
    await expect(controls.getByText(`Reason: QA ${module} ${kind} cancellation completed`,{exact:true}).first()).toBeVisible();checks++;await cooldown();
   }
   for(const [kind,id] of [['quotations',quote.id],['purchase-orders',po.id],['invoices',invoice.id],['sales-orders',orderId],['contracts',contractId]]){
    const before=await request('GET',`/srm/documents/${kind}/${id}`);await open(kind,id,module==='crm'?'srm':'crm');
    await controls.locator('summary').filter({hasText:/Document history/}).click();await expect(controls).toContainText(before.number);expect(before.history.length).toBeGreaterThan(0);checks++;
   }
   await open('quotations',revised.record.id,module);await page.reload();await readyControls();checks++;
   await go(`/common/quotations?module=${module}`);const register=page.getByRole('region',{name:'Saved document register'});
   await register.getByRole('textbox',{name:'Search saved documents'}).fill(revised.number);await register.getByRole('checkbox',{name:'Include archived drafts'}).check();
   await expect(register.getByText(revised.number,{exact:true})).toBeVisible();checks++;
  }
  fs.writeFileSync(path.join(output,'main-app-results.json'),JSON.stringify({origin,checks,delivery:'development stub; no external mail',records:evidence},null,2));
  console.log(`PASS: ${checks} MAIN app checks on ${origin}; browser creation, quote to order to invoice, reasoned modification, resend, cancel, archive and common history from both modules. Development test delivery.`);
 }catch(error){await qaPage?.screenshot({path:path.resolve(__dirname,'../outputs/document-records-local/main-failure.png'),fullPage:true});throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
