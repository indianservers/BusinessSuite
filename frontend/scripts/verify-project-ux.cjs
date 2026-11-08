const {chromium,request}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
const base=process.env.UX_BASE_URL||'http://127.0.0.1:1582';
const groups={
 PMS:['projects','tasks','my-work','my-assignments','time-tracking','risks','files','notes','clients','portfolio'].map(x=>'/pms/'+x),
 CRM:['leads','contacts','companies','deals','follow-ups','pipeline','tickets','quotations','campaigns','products-services'].map(x=>'/crm/'+x),
 HRMS:['employees','attendance','leave','payroll','recruitment','performance','assets','expenses','documents','timesheets'].map(x=>'/hrms/'+x),
 Sales:['sales-orders','contracts','engagements','billing-plans','invoice-drafts','invoices','collections','revenue-recognition','profitability','customer-360'].map(x=>'/srm/'+x),
 Finance:['chart-of-accounts','ledger-groups','ledgers','opening-balances','vouchers','journal','day-book','ledger-entries','parties','banking'].map(x=>'/fam/'+x),
 Inventory:['dashboard','items','stock-groups','units','warehouses','opening-stock','stock-in','stock-out','stock-transfers','stock-adjustments'].map(x=>'/srm/inventory/'+x),
 AI:['','/config','/approvals','/analytics','/usage','/security','/security/permissions','/feedback','/handoff','/logs'].map(x=>'/ai-agents'+x),
 PowerApps:['calendar','notes','tasks','workflow-automation','automations','approvals','forms','tables','app-builder','notifications'].map(x=>'/power-apps/'+x),
 Communication:['/crm/communication-hub','/crm/whatsapp','/crm/whatsapp/inbox','/crm/whatsapp/sent','/crm/whatsapp/templates','/crm/whatsapp/profile','/crm/whatsapp/settings','/crm/communication-timeline','/crm/messages','/pms/messages'],
 Portals:['/portal/customer','/portal/customer/quotes','/portal/customer/invoices','/portal/customer/projects','/portal/customer/profile','/portal/partner','/portal/partner/leads','/portal/partner/commissions','/portal/partner/profile','/portal/customer/login','/portal/partner/login'],
 Analytics:['','/report-builder','/reports','/dashboards','/scheduled-reports','/exports','/funnel','/forecast','/profitability','/collections'].map(x=>'/analytics'+x),
 Administration:['/admin/customization/entities','/admin/customization/fields','/admin/customization/layouts','/admin/customization/views','/admin/customization/kanban','/admin/customization/validation-rules','/admin/customization/buttons','/admin/customization/related-lists','/admin/customization/picklists','/admin/customization/formulas']
};
const output=path.resolve(__dirname,'../../outputs/project-ux-20261107');fs.mkdirSync(output,{recursive:true});const reportFile=process.env.UX_SAMPLE?'final-pages.json':'pages.json';
(async()=>{
 const api=await request.newContext();const login=await api.post(base+'/api/v1/auth/login',{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});if(!login.ok())throw Error('Disposable QA login failed: '+login.status());const auth=await login.json();
 const state={state:{accessToken:auth.access_token,refreshToken:auth.refresh_token,user:{id:auth.user_id,email:auth.email,role:auth.role,is_superuser:auth.is_superuser,employee_id:auth.employee_id},isAuthenticated:true},version:0};
 const browser=await chromium.launch({headless:true});
 const previous=process.env.UX_RETRY ? JSON.parse(fs.readFileSync(path.join(output,reportFile),'utf8')) : [];
 const results=previous.filter(r=>r.status==='passed');
 const queue=Object.entries(groups).map(([module,routes])=>[module,(process.env.UX_SAMPLE?routes.slice(0,1):routes).filter(route=>!results.some(r=>r.module===module&&r.route===route))]).filter(([,routes])=>routes.length);
 async function worker(){
  const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']});
  await context.addInitScript(s=>{sessionStorage.setItem('hrms-auth',JSON.stringify(s));localStorage.setItem('portalSessionToken','qa-no-public-access');},state);
  const page=await context.newPage();
  while(queue.length){const [module,routes]=queue.shift();for(const route of routes){
   const row={module,route,status:'failed',checks:[],pageErrors:[],alerts:[]};const handler=e=>row.pageErrors.push(e.message);page.on('pageerror',handler);
   try{
    await page.goto(base+route,{waitUntil:'domcontentloaded',timeout:30000});
    const tools=page.locator('[data-page-work-tools] > button');
    if(route.endsWith('/login')&&route.startsWith('/portal/')){
     await page.getByLabel('Portal session token',{exact:true}).waitFor({timeout:10000});
     if(await page.getByLabel('Portal session token',{exact:true}).getAttribute('type')!=='password')throw Error('Token is not hidden');
     if(!await page.getByRole('button',{name:'Open portal',exact:false}).isDisabled())throw Error('Empty token accepted');
     row.checks=['accessible token label','hidden token input','empty-token guard'];
    }else{
     await tools.waitFor({state:'visible',timeout:45000});
     await tools.click();const dialog=page.getByRole('dialog',{name:'Page actions',exact:true});await dialog.waitFor({timeout:5000});
     await dialog.getByRole('textbox',{name:'Find page action',exact:true}).fill('Copy page');
     await dialog.getByRole('button',{name:'Copy page link',exact:true}).click();
     await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
     row.checks=['shared page tools','action sheet opens','action search','copy-page-link action','Escape closes sheet'];
    }
    row.url=new URL(page.url()).pathname+new URL(page.url()).search;row.headings=await page.locator('h1,h2').allTextContents();row.alerts=(await page.locator('[role=alert]').allTextContents()).map(s=>s.trim()).filter(Boolean);
    if(row.url!==route && !row.url.startsWith('/settings/') && !(row.url.startsWith('/'+route.split('/')[1]+'/') && !row.url.includes('/login')))throw Error('Unexpected redirect: '+row.url);
    if(row.pageErrors.length)throw Error('Page runtime error: '+row.pageErrors[0]);
    row.status='passed';
    if(routes.indexOf(route)===0)await page.screenshot({path:path.join(output,module+'.png'),fullPage:false});
   }catch(e){row.error=e.message.slice(0,600);await page.screenshot({path:path.join(output,module+'-'+routes.indexOf(route)+'-failure.png')}).catch(()=>{});}
   page.off('pageerror',handler);results.push(row);fs.writeFileSync(path.join(output,reportFile),JSON.stringify(results,null,2));
  }console.log(module+': '+results.filter(r=>r.module===module&&r.status==='passed').length+' shared UX checks passed');}
  await context.close();
 }
 await Promise.all(Array.from({length:Number(process.env.UX_WORKERS)||2},()=>worker()));await browser.close();await api.dispose();
 console.log(JSON.stringify({pages:results.length,passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').map(r=>({module:r.module,route:r.route,error:r.error}))},null,2));
 process.exitCode=results.some(r=>r.status==='failed')?1:0;
})().catch(e=>{console.error(e.message);process.exitCode=1;});
