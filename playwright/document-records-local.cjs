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
 const browser=await chromium.launch();let checks=0;
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1100}}),page=await context.newPage();
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
  const buyer=await request('POST','/master-data/companies?source=crm',{name:`QA Document Controls ${suffix}`,entityKind:'Company',roles:['Customer'],email:`qa-documents+${suffix.toLowerCase()}@example.com`,country:'IN',addresses:[{type:'Billing',line1:'QA test address',city:'Hyderabad',state:'Telangana',postalCode:'500001',country:'IN'}]});
  const quote=await request('POST','/crm/quotes',{quote_number:`QA-DOC-${suffix}`,company_id:buyer.id,currency:'INR',issue_date:today,expiry_date:expiry});
  await request('POST',`/crm/quotes/${quote.id}/lines`,{name:'QA Browser document line',quantity:2,unit_price:20,tax_rate:18});
  for(const action of ['submit','approve','send'])await request('POST',`/crm/quotes/${quote.id}/${action}`,{});
  const po=await request('POST','/srm/procurement/purchase-orders',{vendor_name:`QA Document Supplier ${suffix}`,notes:'Local browser QA only',lines:[{description:'QA Browser purchase',quantity:2,unit_price:20,tax_amount:7.2}]});
  const controls=page.getByRole('region',{name:'Document history and actions'});
  const readyControls=async()=>{
   for(let retry=0;retry<7;retry++){
    await expect.poll(async()=>await controls.getByRole('heading',{name:'Record history and actions',exact:true}).count()>0||await controls.getByRole('alert').count()>0).toBeTruthy();
    if(await controls.getByRole('heading',{name:'Record history and actions',exact:true}).count())return;
    const message=await controls.getByRole('alert').innerText();
    if(!/request limit/i.test(message))throw Error(message);
    console.log('Local QA: waiting for document controls request window');
    await page.waitForTimeout(15000);await controls.getByRole('button',{name:'Refresh document controls',exact:true}).click();
   }
   throw Error('Document controls request limit remained active');
  };
  const go=async destination=>{await page.waitForLoadState('networkidle');await page.evaluate(destination=>{const state={...history.state,idx:(history.state?.idx||0)+1,key:crypto.randomUUID()};history.pushState(state,'',destination);dispatchEvent(new PopStateEvent('popstate',{state}));},destination);};
  const open=async(kind,id,module)=>{await go(`/common/${kind}/${id}?module=${module}`);await page.waitForLoadState('networkidle');await readyControls();};
  const perform=async(mode,reason,prepare)=>{
   await readyControls();
   console.log(`Local QA action: ${mode} ${new URL(page.url()).pathname}`);
   const start={revise:'Create revision draft',edit:'Modify draft with reason',archive:'Archive draft',cancel:'Cancel with reason'}[mode];
   try{await controls.getByRole('button',{name:start,exact:true}).click();}catch(error){throw Error(error.message+' | URL: '+page.url()+' | Page: '+(await page.locator('body').innerText()).slice(-3000));}
   if(prepare)await prepare();
   await controls.getByRole('textbox',{name:'Document action reason'}).fill(reason);
   const method=mode==='edit'?'PATCH':mode==='archive'?'DELETE':'POST';
   const pending=page.waitForResponse(r=>new URL(r.url()).pathname.includes('/srm/documents/')&&r.request().method()===method);
   const submit={revise:'Create revised draft',edit:'Save document changes',archive:'Confirm archive',cancel:'Confirm cancellation'}[mode];
   await controls.getByRole('button',{name:submit,exact:true}).click();
   const r=await pending;expect(r.status()).toBe(mode==='revise'?201:200);checks++;
   const value=await r.json();
   await expect(controls.getByRole('form',{name:'Document action form'})).toHaveCount(0);
   await readyControls();
   return value;
  };
  const output=path.resolve(__dirname,'../outputs/document-records-local');fs.mkdirSync(output,{recursive:true});
  for(const module of process.env.DOCUMENT_QA_MODULE?[process.env.DOCUMENT_QA_MODULE]:['crm','srm']){
   for(const [kind,source]of [['quotations',quote],['purchase-orders',po]]){
    await open(kind,source.id,module);
    const revised=await perform('revise',`QA ${module} local browser revision`);
    await expect(page).toHaveURL(new RegExp(`/common/${kind}/${revised.record.id}\\?module=${module}`));
    await perform('edit',`QA ${module} corrected quantity with history`,()=>controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3'));
    await perform('archive',`QA ${module} unused local draft archived`);
    await controls.locator('summary').filter({hasText:/Document history/}).click();
    await expect(controls.getByText(`Reason: QA ${module} unused local draft archived`,{exact:true})).toBeVisible();checks++;
    await page.screenshot({path:path.join(output,`${module}-${kind}-history.png`),fullPage:true});
    const original=await request('GET',`/srm/documents/${kind}/${source.id}`);
    expect(original.record.status).toBe(kind==='quotations'?'Sent':'ordered');checks++;
    await go(`/common/${kind}?module=${module}`);
    const register=page.getByRole('region',{name:'Saved document register'});
    await register.getByRole('textbox',{name:'Search saved documents'}).fill(revised.number);
    await register.getByRole('checkbox',{name:'Include archived drafts'}).check();
    for(let retry=0;retry<7;retry++){
     await expect.poll(async()=>await register.getByText(revised.number,{exact:true}).isVisible()||await register.getByRole('alert').count()>0).toBeTruthy();
     if(await register.getByText(revised.number,{exact:true}).isVisible())break;
     if(await register.getByRole('alert').filter({hasText:/request limit/i}).count()){
      console.log('Local QA: respecting the request-limit retry window');
      await page.waitForTimeout(15000);await register.getByRole('button',{name:'Refresh saved documents',exact:true}).click();
     }else throw Error('Saved register failed: '+await register.getByRole('alert').innerText());
    }
    await expect(register.getByText(revised.number,{exact:true})).toBeVisible();checks++;
   }
   const invoice=await request('POST','/srm/invoices/manual',{customer_id:buyer.id,currency:'INR',lines:[{description:'QA unissued local invoice',quantity:2,unit_price:20,tax_amount:7.2}]});
   console.log(`Local QA invoice: ${invoice.id} ${invoice.status}`);
   await open('invoices',invoice.id,module);
   await perform('edit',`QA ${module} unissued invoice correction`,()=>controls.getByRole('spinbutton',{name:'Line 1 Unit Price',exact:true}).fill('30'));
   const changed=await request('GET',`/srm/documents/invoices/${invoice.id}`);expect(changed.record.total_amount).toBe(67.2);checks++;
   await perform('archive',`QA ${module} unissued invoice archived`);
  }
  for(const [kind,id]of [['quotations',quote.id],['purchase-orders',po.id]]){
   const row=await request('GET',`/srm/documents/${kind}/${id}`);
   await request('POST',`/srm/documents/${kind}/${id}/cancel`,{reason:'Local QA completed; retained for test evidence',version:row.version,request_id:crypto.randomUUID()});
  }
  console.log(`PASS: ${checks} checks in the real local app: login, CRM/Sales quotation and PO revision/edit/archive/history, saved register search, and invoice draft CRUD. No local invoice issued or external email sent.`);
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
