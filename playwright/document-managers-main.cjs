// Main application shell smoke test; uses the temporary authenticated local QA session.
const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const expect=baseExpect.configure({timeout:60000});
const fs=require('node:fs'),path=require('node:path');
const origin=process.env.DOCUMENT_QA_BASE||'http://127.0.0.1:5173';
if(!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(origin))throw Error('Local app required');
(async()=>{
 const browser=await chromium.launch();let qaPage;
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const session=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../backend/.tmp-document-local-auth.json'),'utf8'));
  const headers={Authorization:'Bearer '+session.token,'X-Suite-Organization':'1'};
  const read=async endpoint=>{for(let i=0;i<8;i++){const response=await context.request.get(origin+'/api/v1'+endpoint,{headers});if(response.status()===429){await new Promise(resolve=>setTimeout(resolve,Math.min(30,Math.max(5,Number(response.headers()['retry-after'])||15))*1000));continue;}expect(response.status()).toBe(200);return response.json();}throw Error('Local request window remained busy');};
  const user=await read('/auth/me');
  const access=await read('/access/me');
  const role=typeof user.role==='string'?user.role:user.role?.name;
  const branches=await read('/branches/context');
  const branch=branches.branches.find(row=>row.is_active&&row.can_write);
  await context.addInitScript(({token,user,branch})=>{sessionStorage.setItem('hrms-auth',JSON.stringify({state:{user,accessToken:token,isAuthenticated:true},version:0}));sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',String(branch));},{token:session.token,user:{...user,role,primary_role:role,access},branch:branch.id});
  const page=await context.newPage();qaPage=page;page.on('pageerror',error=>console.error('Main manager runtime:',error.message));page.on('response',r=>{if(r.status()>=400&&new URL(r.url()).pathname.startsWith('/assets/'))console.error('Main asset:',r.status(),new URL(r.url()).pathname);});await page.goto(origin+'/crm');
  await expect(page.getByRole('navigation',{name:'Module navigation'})).toBeVisible({timeout:60000});
  const go=async destination=>{await page.waitForTimeout(3500);await page.evaluate(destination=>{const state={...history.state,idx:(history.state?.idx||0)+1,key:crypto.randomUUID()};history.pushState(state,'',destination);dispatchEvent(new PopStateEvent('popstate',{state}));},destination);};
  const titles={},results=[];
  const managers=[['quotations','Quotations'],['contracts','Contracts'],['purchase-orders','Purchase orders'],['sales-orders','Sales orders'],['invoices','Invoices'],['invoice-drafts','Invoice drafts'],['billing-plans','Billing plans'],['collections','Collections'],['engagements','Engagements'],['payment-requests','Payment requests']];
  for(const module of ['crm','srm']){
   await go('/'+module);
   for(const [entity,label]of managers){
    const menu=page.getByRole('navigation',{name:'Module navigation'});
    await menu.getByRole('textbox',{name:'Find a page in this application',exact:true}).fill(label);
    await menu.getByRole('link',{name:new RegExp(`^${label}$`,'i')}).first().click();
    await expect(page).toHaveURL(new RegExp(`/common/${entity}\\?module=${module}`));
    await expect(page.getByRole('navigation',{name:'Shared page breadcrumbs'})).toContainText(label);
    await expect(page.getByRole('heading',{name:new RegExp(`^${entity==='quotations'?'Quotes':label}$`,'i')}).first()).toBeVisible();
    await page.waitForTimeout(3500);
    const headings=await page.getByRole('heading',{level:1}).allTextContents();
    expect(headings.length).toBeGreaterThan(0);
    if(module==='crm')titles[entity]=headings;else expect(headings).toEqual(titles[entity]);
    results.push({module,entity,url:page.url(),headings});
    console.log('PASS main manager',module,entity);
   }
  }
  // A native create must refresh the common register immediately, before its cache expires.
  for(const module of ['crm','srm']){
   await page.waitForTimeout(30000);await go(`/common/quotations?module=${module}`);
   const number=`QA-REGISTER-${module}-${Date.now()}`;
   await page.getByRole('button',{name:'Create Quote',exact:true}).click();
   const dialog=page.getByRole('dialog');await dialog.getByPlaceholder('QT-2026-001',{exact:true}).fill(number);
   const created=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/crm/quotations'&&r.request().method()==='POST');
   await dialog.getByRole('button',{name:'Create',exact:true}).click();const response=await created;expect(response.status()).toBe(201);const quote=await response.json();
   const register=page.getByRole('region',{name:'Saved document register'});
   await expect(register.getByText(number,{exact:true})).toBeVisible({timeout:60000});
   await register.getByRole('row').filter({hasText:number}).getByRole('link',{name:'Open record',exact:true}).click();
   await expect(page).toHaveURL(new RegExp(`/common/quotations/${quote.id}\\?module=${module}`));
   const controls=page.getByRole('region',{name:'Document history and actions'});
   await controls.getByRole('button',{name:'Modify draft with reason',exact:true}).click();
   await controls.getByLabel('Document Notes',{exact:true}).fill('QA register refresh verification');
   await controls.getByLabel('Document action reason',{exact:true}).fill(`QA ${module} register correction`);
   const edited=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/documents/quotations/${quote.id}`)&&r.request().method()==='PATCH');
   await controls.getByRole('button',{name:'Save document changes',exact:true}).click();expect((await edited).status()).toBe(200);
   await expect(controls.getByRole('form')).toHaveCount(0);
   await controls.getByRole('button',{name:'Archive draft',exact:true}).click();
   await controls.getByLabel('Document action reason',{exact:true}).fill(`QA ${module} register draft archived`);
   const archived=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/documents/quotations/${quote.id}`)&&r.request().method()==='DELETE');
   await controls.getByRole('button',{name:'Confirm archive',exact:true}).click();expect((await archived).status()).toBe(200);
   await expect(controls.getByRole('form')).toHaveCount(0);await controls.locator('summary').filter({hasText:/Document history/}).click();
   await expect(controls.getByText(`Reason: QA ${module} register draft archived`,{exact:true})).toBeVisible();
   results.push({module,entity:'quotations',check:'create-refresh-edit-reason-archive-history',id:quote.id});
   console.log('PASS final main register CRUD',module);
  }
  if(process.env.DOCUMENT_QA_EXPECT_MAIL_BLOCKED==='1'){
   await page.waitForTimeout(30000);
   const prior=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../outputs/document-records-local/main-app-results.json'),'utf8'));
   const quote=prior.records.find(row=>row.kind==='quotations');
   await go(`/common/quotations/${quote.id}?module=crm`);
   const controls=page.getByRole('region',{name:'Document history and actions'});
   await controls.getByRole('button',{name:'Send / resend document',exact:true}).click();
   await controls.getByLabel('Document recipient email',{exact:true}).fill('qa-main-verification@example.com');
   await controls.getByLabel('Document action reason',{exact:true}).fill('QA verify missing SMTP is reported and retained');
   const delivery=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/documents/quotations/${quote.id}/send`)&&r.request().method()==='POST');
   await controls.getByRole('button',{name:'Send document',exact:true}).click();const response=await delivery;expect(response.status()).toBe(200);expect((await response.json()).status).toBe('blocked');
   await expect(controls.getByText(/Delivery blocked/)).toBeVisible();
   results.push({module:'crm',entity:'quotations',check:'unconfigured SMTP visibly blocks delivery'});
   console.log('PASS unconfigured SMTP feedback on main app');
  }
  fs.writeFileSync(path.resolve(__dirname,'../outputs/document-records-local/main-manager-results.json'),JSON.stringify({origin,checks:results.length,results},null,2));
 }catch(error){if(qaPage){console.error('Main manager page:',qaPage.url(),(await qaPage.locator('body').innerText()).slice(-5000));await qaPage.screenshot({path:path.resolve(__dirname,'../outputs/document-records-local/main-managers-failure.png'),fullPage:true});}throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
