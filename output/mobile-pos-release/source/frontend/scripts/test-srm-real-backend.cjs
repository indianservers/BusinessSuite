const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {randomUUID} = require('node:crypto');
const {chromium, expect:baseExpect} = require('playwright/test');
const expect = baseExpect.configure({timeout:90000});
const root = path.resolve(__dirname,'../..');
const output = path.join(root,'.local/srm-real-backend');
fs.mkdirSync(output,{recursive:true});
const statePath = path.join(output,'state.json');
// Start the companion Vite config first; API responses are never stubbed here.
const origin = process.env.SRM_LIVE_APP || 'http://127.0.0.1:5181';
const backend = process.env.SRM_LIVE_API || 'http://127.0.0.1:1534';
if (![origin,backend].every(value => ['127.0.0.1','localhost'].includes(new URL(value).hostname))) throw Error('This QA runner requires a loopback application and backend.');
const credentials = JSON.parse(fs.readFileSync(path.join(root,'.local/industry-qa15/credentials.json'),'utf8'));
const company = JSON.parse(fs.readFileSync(path.join(root,'output/business-profile-15-companies/companies.json'),'utf8')).companies.find(row=>row.industry==='consulting');
let state = fs.existsSync(statePath) && process.env.SRM_LIVE_FRESH!=='1' ? JSON.parse(fs.readFileSync(statePath,'utf8')) : {marker:`SRM-LIVE-${Date.now()}`,company_id:company.company_id,checks:[]};
assert.equal(state.company_id,company.company_id);
const save = () => {const json=JSON.stringify(state,null,2);fs.writeFileSync(statePath,json);fs.writeFileSync(path.join(output,state.marker+'.json'),json);};
const passed = (name,data) => {state.checks=state.checks.filter(check=>check.name!==name);state.checks.push({name,...data,status:'passed'});save();console.log('PASS',name,data?JSON.stringify(data):'');};
const headers = {'Content-Type':'application/json','X-Suite-Tenant':company.workspace,'X-Suite-Organization':String(company.company_id),'X-Suite-Branch':String(company.branch_id)};
async function call(method,url,data,expected) {
  const response = await fetch(backend+'/api/v1'+url,{method,headers,body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(45000)});
  const text = await response.text();
  let body;try {body=JSON.parse(text);} catch {body=text;}
  if (expected ? response.status!==expected : !response.ok) throw Error(`${method} ${url}: ${response.status} ${JSON.stringify(body).slice(0,1500)}`);
  return body;
}
(async()=>{
  const auth = await call('POST','/auth/login',{email:company.email,password:credentials.password});
  headers.Authorization='Bearer '+auth.access_token;
  const [identity,access] = await Promise.all([call('GET','/auth/me'),call('GET','/access/me')]);
  assert.equal(access.companyId,company.company_id);
  const role = typeof identity.role==='object' ? identity.role?.name : identity.role;
  const user = {...identity,role:role||auth.role||access.grants.srm.role,access};
  passed('real backend identity and isolated QA company',{company:access.companyId,branch:company.branch_id});
  if (!state.customer_id) {
    const customer=await call('POST','/master-data/companies?source=srm',{name:state.marker+' Customer',email:state.marker.toLowerCase()+'@example.com',roles:['Customer'],tags:['srm-live-qa'],entityKind:'Company',notes:'Isolated SRM end-to-end QA record'} ,201);
    state.customer_id=customer.id;save();
  }
  if (!state.service_id) {
    const item=await call('POST','/catalog/items?source=srm',{kind:'service',name:state.marker+' Service',code:state.marker,price:1000,currency:'INR',tax:18,unit:'hour',description:'Isolated SRM full-flow QA service'},201);
    state.service_id=item.id;save();
  }
  if(!state.masters_edited) {
    const customer=await call('GET',`/master-data/companies/${state.customer_id}?source=srm`);
    const changes={name:state.marker+' Customer updated',version:customer.version,notes:'Real SRM QA customer edited and saved'};
    await call('PATCH',`/master-data/companies/${state.customer_id}?source=srm`,changes);
    assert.equal((await call('GET',`/master-data/companies/${state.customer_id}?source=srm`)).name,changes.name);
    await call('PATCH',`/master-data/companies/${state.customer_id}?source=srm`,{...changes,notes:'Stale update must not replace saved values'},409);
    const service=await call('GET',`/catalog/items/service/${state.service_id}?source=srm`);
    const updated={kind:'service',name:state.marker+' Service',code:state.marker,price:1000,currency:'INR',tax:18,unit:'hour',description:'Real SRM QA service edited and persisted',version:service.version};
    await call('PUT',`/catalog/items/service/${state.service_id}?source=srm`,updated);
    assert.equal((await call('GET',`/catalog/items/service/${state.service_id}?source=srm`)).description,updated.description);
    await call('PUT',`/catalog/items/service/${state.service_id}?source=srm`,{...updated,description:'Stale catalog update'},409);
    state.masters_edited=true;save();
    passed('customer and service create/edit persist and reject stale overwrites');
  }
  const browser=await chromium.launch();
  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata',extraHTTPHeaders:headers});
  const persisted={state:{accessToken:auth.access_token,refreshToken:auth.refresh_token,user,isAuthenticated:true},version:0};
  await context.addInitScript(({persisted,company})=>{
    sessionStorage.setItem('hrms-auth',JSON.stringify(persisted));
    sessionStorage.setItem('suite-tenant',company.workspace);
    sessionStorage.setItem('suite-organization',String(company.company_id));
    sessionStorage.setItem('suite-branch',String(company.branch_id));
  },{persisted,company});
  const page=await context.newPage(),errors=[],failures=[];
  page.setDefaultTimeout(30000);
  page.setDefaultNavigationTimeout(60000);
  page.on('pageerror',error=>errors.push(error.stack||error.message));
  page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/api/')&&response.status()>=400)failures.push({path:url.pathname,status:response.status()});});
  const go = async href => {await page.goto(origin+href,{waitUntil:'domcontentloaded'});};
  try {
    if (!state.order_id) {
      await go(`/srm/sales-orders?customer_id=${state.customer_id}#new-record`);
      const dialog=page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await dialog.getByLabel('Title',{exact:true}).fill(state.marker+' Order');
      await dialog.getByRole('textbox',{name:'Find products and services'}).fill(state.marker);
      await dialog.locator('.sc-picker-grid button').filter({hasText:state.marker+' Service'}).click();
      await dialog.getByRole('spinbutton',{name:`Quantity for ${state.marker} Service`}).fill('2');
      await dialog.getByRole('spinbutton',{name:`Discount for ${state.marker} Service`}).fill('10');
      await dialog.getByLabel('Terms',{exact:true}).fill('QA sales-to-payment verification');
      const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/sales-orders'&&r.request().method()==='POST');
      response.catch(()=>{});
      await dialog.locator('[data-smart-create-footer]').getByRole('button',{name:'Create Sales Order',exact:true}).click();
      const created=await response;assert.equal(created.status(),201,await created.text());
      const order=await created.json();state.order_id=order.id;save();
      await expect(dialog).toHaveCount(0);
      passed('create sales order through merged workspace',{id:order.id});
    }
    let order=await call('GET',`/srm/sales-orders/${state.order_id}`);
    assert.equal(Number(order.total_amount),state.order_edited?3186:2124);
    assert.equal(order.customer_id,state.customer_id);
    passed('persisted order discount, tax and customer',{total:Number(order.total_amount),customer:order.customer_id,order_status:order.status});
    await go(`/common/sales-orders/${state.order_id}?module=srm`);
    await expect(page.getByRole('heading',{name:'Sales Order Detail',exact:true})).toBeVisible();
    const controls=page.getByRole('region',{name:'Document history and actions'});
    if (!state.order_edited) {
      await controls.getByRole('button',{name:'Modify draft with reason',exact:true}).click();
      await controls.getByRole('textbox',{name:'Document Title',exact:true}).fill(state.marker+' Edited order');
      await controls.getByRole('spinbutton',{name:'Line 1 Quantity',exact:true}).fill('3');
      await controls.getByRole('spinbutton',{name:'Line 1 Discount Amount',exact:true}).fill('300');
      await controls.getByRole('spinbutton',{name:'Line 1 Tax Amount',exact:true}).fill('486');
      await controls.getByRole('textbox',{name:'Document action reason',exact:true}).fill('QA edit of quantity, discount and tax before confirmation');
      const edited=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/documents/sales-orders/${state.order_id}`&&r.request().method()==='PATCH');edited.catch(()=>{});
      await controls.getByRole('button',{name:'Save document changes',exact:true}).click();
      const response=await edited;assert.equal(response.status(),200,await response.text());
      order=await call('GET',`/srm/sales-orders/${state.order_id}`);
      assert.equal(order.title,state.marker+' Edited order');assert.equal(Number(order.total_amount),3186);
      state.order_edited=true;save();
      passed('edit order and lines through real document controls',{subtotal:Number(order.subtotal),discount:Number(order.discount_amount),tax:Number(order.tax_amount),total:Number(order.total_amount)});
      await page.reload();await expect(controls).toContainText(order.order_number);
    }
    if (order.status==='draft') order=await call('POST',`/srm/sales-orders/${state.order_id}/submit`);
    if (order.status==='pending_approval') order=await call('POST',`/srm/sales-orders/${state.order_id}/approve`);
    if (order.status==='approved') order=await call('POST',`/srm/sales-orders/${state.order_id}/confirm`);
    assert.equal(order.status,'confirmed');
    state.engagement_id=order.engagement?.id||state.engagement_id;save();
    passed('submit, approve and confirm real sales order',{status:order.status});
    if (!state.invoice_id) {
      await page.reload();
      const pending=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/invoices/draft-from-sales-order/${state.order_id}`&&r.request().method()==='POST');pending.catch(()=>{});
      await page.getByRole('button',{name:'Create invoice draft',exact:true}).click();
      const response=await pending;assert.equal(response.status(),201,await response.text());
      const invoice=await response.json();state.invoice_id=invoice.id;save();
      assert.equal(Number(invoice.total_amount),3186);
      passed('draft invoice from confirmed order in UI',{id:invoice.id,total:Number(invoice.total_amount)});
    }
    await call('POST',`/srm/invoices/draft-from-sales-order/${state.order_id}`,undefined,409);
    passed('duplicate invoice draft rejected');
    await go(`/common/invoices/${state.invoice_id}?module=srm`);
    let invoice=await call('GET',`/srm/business/invoices/${state.invoice_id}`);
    assert.equal(Number(invoice.total_amount),3186);
    if (invoice.document_status==='draft') {
      if(!state.invoice_edited) {
        const invoiceControls=page.getByRole('region',{name:'Document history and actions'});
        await invoiceControls.getByRole('button',{name:'Modify draft with reason',exact:true}).click();
        await invoiceControls.getByLabel('Document Due Date',{exact:true}).fill('2026-12-15');
        await invoiceControls.getByRole('textbox',{name:'Document action reason',exact:true}).fill('QA verifies invoice due date editing before issue');
        const edited=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/documents/invoices/${state.invoice_id}`&&r.request().method()==='PATCH');edited.catch(()=>{});
        await invoiceControls.getByRole('button',{name:'Save document changes',exact:true}).click();
        const response=await edited;assert.equal(response.status(),200,await response.text());
        const saved=await call('GET',`/srm/business/invoices/${state.invoice_id}`);assert.equal(saved.due_date,'2026-12-15');
        state.invoice_edited=true;save();passed('edit draft invoice due date through browser and verify persistence');
      }
      const pending=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/invoices/${state.invoice_id}/approve`&&r.request().method()==='POST');pending.catch(()=>{});
      await page.getByRole('button',{name:'Issue invoice',exact:true}).click();
      const response=await pending;assert.equal(response.status(),200,await response.text());
    }
    invoice=await call('GET',`/srm/business/invoices/${state.invoice_id}`);
    assert.equal(invoice.document_status,'issued');
    passed('issue invoice in browser and verify persisted identity',{id:invoice.id,total:Number(invoice.total_amount),customer:invoice.customer_id});
    const paymentPath=`/srm/business/invoices/${state.invoice_id}/payments`;
    await call('POST',paymentPath,{request_id:randomUUID(),amount:Number(invoice.balance_amount)+0.01,reference:state.marker+'-OVER'},422);
    passed('overpayment rejected by real backend');
    const issuedDocument=await call('GET',`/srm/documents/invoices/${state.invoice_id}`);
    await call('PATCH',`/srm/documents/invoices/${state.invoice_id}`,{request_id:randomUUID(),version:issuedDocument.version,reason:'QA verifies issued invoice cannot be modified',changes:{due_date:'2026-12-15'}},409);
    passed('issued invoice modification rejected');
    state.payments=state.payments||[];
    for (const [index,amount] of [[0,1000],[1,2186]]) {
      if (state.payments[index]?.receipt_id) continue;
      await page.reload();
      await page.locator('summary').filter({hasText:'Payment and collection actions'}).click();
      await page.getByLabel('Amount received',{exact:true}).fill(String(amount));
      await page.getByLabel('Bank / payment reference',{exact:true}).fill(state.marker+'-P'+(index+1));
      const request=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/v1'+paymentPath&&r.method()==='POST');request.catch(()=>{});
      const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1'+paymentPath&&r.request().method()==='POST');response.catch(()=>{});
      await page.getByRole('button',{name:'Record received payment',exact:true}).click();
      const outgoing=await request;
      state.payments[index]={payload:outgoing.postDataJSON()};save();
      const received=await response;assert.equal(received.status(),201,await received.text());
      const result=await received.json();state.payments[index].receipt_id=result.receipt_id;save();
      invoice=await call('GET',`/srm/business/invoices/${state.invoice_id}`);
      assert.equal(Number(invoice.paid_amount),index===0?1000:3186);
      assert.equal(Number(invoice.balance_amount),index===0?2186:0);
      assert.equal(invoice.payment_status,index===0?'partially_paid':'paid');
      passed(index===0?'partial payment saved and allocated through UI':'final payment saved and invoice settled through UI',{receipt_id:result.receipt_id,paid:Number(invoice.paid_amount),balance:Number(invoice.balance_amount)});
      const replay=await call('POST',paymentPath,state.payments[index].payload,201);
      assert.equal(replay.receipt_id,result.receipt_id);
      const conflict={...state.payments[index].payload,amount:amount-1};
      await call('POST',paymentPath,conflict,409);
      passed(`payment ${index+1} retry is idempotent and conflicting reuse rejected`,{receipt_id:result.receipt_id});
    }
    invoice=await call('GET',`/srm/business/invoices/${state.invoice_id}`);
    assert.equal(Number(invoice.balance_amount),0);assert.equal(Number(invoice.paid_amount),3186);
    for(const payment of state.payments) {
      const receipt=await call('GET',`/srm/receipts/${payment.receipt_id}`);
      assert.equal(receipt.status,'allocated');assert.equal(Number(receipt.unallocated_amount),0);
      assert.equal(receipt.customer_id,state.customer_id);assert.equal(receipt.currency,'INR');
      assert.equal(receipt.allocations.length,1);assert.equal(receipt.allocations[0].invoice_id,state.invoice_id);
      assert.equal(Number(receipt.allocations[0].amount),Number(payment.payload.amount));
    }
    passed('receipt ledger has exactly one allocation per payment and no unapplied cash');
    const history=await call('GET',`/srm/business/customers/${state.customer_id}/history`);
    assert(history.invoices.some(row=>row.id===state.invoice_id&&Number(row.balance_amount)===0));
    const pdfResponse=await fetch(backend+`/api/v1/srm/invoices/${state.invoice_id}/pdf`,{headers});
    assert.equal(pdfResponse.status,200);
    const pdf=Buffer.from(await pdfResponse.arrayBuffer());assert.equal(pdf.subarray(0,5).toString(),'%PDF-');assert(pdf.length>1000);
    fs.writeFileSync(path.join(output,'invoice.pdf'),pdf);
    passed('customer history reconciles paid invoice and real PDF downloads',{bytes:pdf.length});
    await page.reload();
    await expect(page.locator('#suite-main')).toContainText('Payment: paid');
    await expect(page.locator('#suite-main')).toContainText('Outstanding: 0');
    await expect(page.getByRole('button',{name:'Record received payment',exact:true})).toHaveCount(0);
    const summary=await call('GET',`/srm/dashboard-workspace/summary?period=all&customer_id=${state.customer_id}`);
    const metric=name=>Number(summary.series.find(row=>row.metric===name&&row.currency==='INR')?.amount||0);
    assert.equal(metric('invoiced'),3186);assert.equal(metric('collected'),3186);assert.equal(metric('outstanding'),0);
    passed('real sales dashboard reconciles invoice, collections and zero outstanding');
    if(!state.contract_id) {
      await go(`/srm/sales-orders?operation=%2Fsrm%2Fcontracts&customer_id=${state.customer_id}&sales_order_id=${state.order_id}#new-record`);
      const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
      await dialog.getByLabel('Title',{exact:true}).fill(state.marker+' Contract');
      await dialog.getByLabel('Contract amount',{exact:true}).fill('3186');
      const pending=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/contracts'&&r.request().method()==='POST');pending.catch(()=>{});
      await dialog.locator('[data-smart-create-footer]').getByRole('button',{name:'Create Contract',exact:true}).click();
      const response=await pending;assert.equal(response.status(),201,await response.text());
      state.contract_id=(await response.json()).id;save();passed('create contract through merged Sales workspace',{id:state.contract_id});
    }
    if(!state.contract_edited) {
      await go(`/common/contracts/${state.contract_id}?module=srm`);
      const contractControls=page.getByRole('region',{name:'Document history and actions'});
      await contractControls.getByRole('button',{name:'Modify draft with reason',exact:true}).click();
      await contractControls.getByLabel('Document Title',{exact:true}).fill(state.marker+' Contract edited');
      await contractControls.getByRole('textbox',{name:'Document action reason',exact:true}).fill('QA verifies persisted contract editing');
      const pending=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/srm/documents/contracts/${state.contract_id}`&&r.request().method()==='PATCH');pending.catch(()=>{});
      await contractControls.getByRole('button',{name:'Save document changes',exact:true}).click();
      const response=await pending;assert.equal(response.status(),200,await response.text());
      const saved=await call('GET',`/srm/contracts/${state.contract_id}`);
      assert.equal(saved.title,state.marker+' Contract edited');assert.equal(saved.customer_id,state.customer_id);assert.equal(saved.sales_order_id,state.order_id);
      state.contract_edited=true;save();passed('edit contract through browser and preserve customer/order links');
    }
    if(!state.billing_plan_id) {
      const plan=await call('POST','/srm/billing-plans',{engagement_id:state.engagement_id,name:state.marker+' Billing plan',billing_type:'fixed_fee',currency:'INR',total_amount:3186},201);
      state.billing_plan_id=plan.id;save();
    }
    await call('PATCH',`/srm/billing-plans/${state.billing_plan_id}`,{name:state.marker+' Billing plan edited'});
    const plan=await call('GET',`/srm/billing-plans/${state.billing_plan_id}`);
    assert.equal(plan.name,state.marker+' Billing plan edited');assert.equal(plan.engagement_id,state.engagement_id);
    await call('PATCH',`/srm/engagements/${state.engagement_id}`,{name:state.marker+' Engagement edited'});
    assert.equal((await call('GET',`/srm/engagements/${state.engagement_id}`)).name,state.marker+' Engagement edited');
    passed('real engagement and billing-plan create/edit retain delivery links');
    await go(`/common/invoices/${state.invoice_id}?module=srm`);
    await expect(page.locator('#suite-main')).toContainText('Payment: paid');
    await page.screenshot({path:path.join(output,'sales-order.png'),fullPage:true});
    state.browser_errors=errors;state.api_failures=failures;save();
    assert.deepEqual(errors,[]);
    assert.deepEqual(failures.filter(row=>row.path.startsWith('/api/v1/srm/')&&(row.status===404||row.status>=500)),[]);
    passed('real commercial pages open through shared SRM routing');
    delete state.last_error;state.app_origin=origin;state.api_origin=backend;state.completed_at=new Date().toISOString();save();
  } catch(error) {
    state.last_error=error.stack;state.browser_errors=errors;state.api_failures=failures;save();
    await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(output,'failure.txt'),await page.locator('body').innerText().catch(()=>''));
    throw error;
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});

