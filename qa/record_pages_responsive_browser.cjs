const {chromium,expect:raw}=require('../frontend/node_modules/playwright/test');
const fs=require('node:fs');const path=require('node:path');const expect=raw.configure({timeout:20000});
const origin=process.env.QA_ORIGIN || 'http://127.0.0.1:5198',apiRoot='http://127.0.0.1:1534/api/v1';
const output=path.resolve(process.env.QA_OUTPUT || 'docs/qa/record-pages-responsive');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const fixtures=process.env.QA_FIXTURES==='1' ? require('./record_pages_fixtures.cjs') : null;
 let login,access,first;
 if(fixtures){({login,access,first}=fixtures);}else{
 const response=await fetch(apiRoot+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@aihrms.com',password:'Admin@123456'})});if(!response.ok)throw Error('Local QA login failed: '+response.status);login=await response.json();
 const headers={Authorization:'Bearer '+login.access_token,'X-Suite-Organization':'1','X-Suite-Branch':'6'};
 async function get(url){const r=await fetch(apiRoot+url,{headers});if(!r.ok)throw Error(url+': '+r.status);return r.json();}
 access=await get('/access/me');
 first=async url=>{const d=await get(url);return (Array.isArray(d)?d:d.items||d.tasks||d.employees||d.data||[])[0];};
 }
 const [lead,contact,company,deal,employee,task,order,engagement,voucher,quote]=await Promise.all(['/crm/leads?per_page=1','/crm/contacts?per_page=1','/crm/companies?per_page=1','/crm/deal-workspace/query?per_page=1','/employees?per_page=1','/project-management/tasks?per_page=1','/srm/sales-orders','/srm/engagements','/fam/vouchers','/crm/quotations?per_page=1'].map(first));
 const cases=[
 ['crm-lead',`/crm/leads/${lead.id}`,'CRM record information'],['crm-contact',`/crm/contacts/${contact.id}`,'CRM record information'],['crm-company',`/crm/companies/${company.id}`,'CRM record information'],
 ['crm-deal',`/crm/deals/${deal.id}`,'Deal information'],
 ...(quote?[['crm-quotation',`/crm/quotations/${quote.id}`,'CRM record information']]:[]),
 ['employee',`/hrms/employees/${employee.id}`,'Employee information'],
 ['profile','/hrms/profile','Profile sections'],
 ['task-classic',`/pms/tasks/${task.id}/classic`,'Task information'],
 ['task-workspace',`/pms/tasks/${task.id}`,'Task workspace sections'],
 ['voucher',`/fam/vouchers/${voucher.id}`,'Voucher information'],['voucher-new','/fam/vouchers/new','Voucher information'],
 ['sales-order',`/srm/sales-orders/${order.id}`,'Commercial record information'],['engagement',`/srm/engagements/${engagement.id}`,'Commercial record information'],
 ['contract','/srm/contracts/999999','Commercial record information'],['billing-plan','/srm/billing-plans/999999','Commercial record information'],
 ['whatsapp','/crm/whatsapp','WhatsApp workspace'],
 ];
 const browser=await chromium.launch({headless:true});const results=[];const issues=[];
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata',hasTouch:true});
  await context.addInitScript(({login,access})=>{performance.setResourceTimingBufferSize(10000);sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','6');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:login.user_id,email:login.email,role:'admin',is_superuser:true,access}},version:0}));},{login,access});
  if(fixtures)await context.route('**/api/v1/**',async route=>{if(route.request().method()!=='GET'){return route.fulfill({status:405,json:{detail:'Read-only layout QA'}});}await route.fulfill({json:fixtures.response(new URL(route.request().url()).pathname)});});
  await context.route('**/api/v1/srm/contracts/999999',r=>r.fulfill({json:{id:999999,contract_number:'QA Contract',title:'Read-only layout fixture',contract_value:12000,status:'draft'}}));
  await context.route('**/api/v1/srm/billing-plans/999999',r=>r.fulfill({json:{id:999999,name:'QA Billing Plan',title:'Read-only layout fixture',budget_amount:12000,status:'draft'}}));
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>{issues.push({page:page.url(),error:e.message});console.log('PAGE ERROR',e.message);});
  async function layout(name,width){
   const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('main *,[role="dialog"] *')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0&&b.right>innerWidth+2&&getComputedStyle(e).position!=='fixed'&&!e.closest('.overflow-x-auto, .overflow-auto, .overflow-x-scroll, [data-radix-scroll-area-viewport]');}).slice(0,8).map(e=>({tag:e.tagName,class:e.className,text:e.textContent?.slice(0,60)}))}));
   if(overflow.scroll>width+1)issues.push({name,width,type:'page-overflow',...overflow});
   const mainOverflow=await page.locator('#suite-main').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));if(mainOverflow.scroll>mainOverflow.width+2)issues.push({name,width,type:'main-overflow',...mainOverflow});
   const clipped=await page.getByRole('tablist').evaluateAll(lists=>lists.filter(e=>e.getBoundingClientRect().width>0).flatMap(list=>[...list.querySelectorAll('[role="tab"]')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>({label:e.textContent,scroll:e.scrollWidth,width:e.clientWidth}))));
   if(clipped.length)issues.push({name,width,type:'tab-label-overflow',clipped});
  }
  async function exercise(name,label,width){
   const nav=page.getByRole('tablist',{name:label,exact:true});await expect(nav).toBeVisible();const count=await nav.getByRole('tab').count();expect(count).toBeLessThanOrEqual(4);
   for(let i=0;i<count;i++){
    const tab=nav.getByRole('tab').nth(i);await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');
    const selector=page.getByRole('combobox',{name:label+' section',exact:true});
    if(await selector.count()) {const values=await selector.locator('option').evaluateAll(items=>items.map(e=>e.value));for(const value of values){await selector.selectOption(value);await expect(selector).toHaveValue(value);await layout(name,width);}}
    await layout(name,width);
   }
   await nav.getByRole('tab').first().click();await nav.getByRole('tab').first().focus();if(count>1){await page.keyboard.press('ArrowRight');await expect(nav.getByRole('tab').nth(1)).toBeFocused();}
  }
  for(const width of (process.env.QA_WIDTHS || '390,320,1440').split(',').map(Number)){
   await page.setViewportSize({width,height:width===1440?1000:844});
   for(const [name,url,label] of cases.filter(([name])=>!process.env.QA_PAGES || process.env.QA_PAGES.split(',').includes(name))){
    try{
     await page.goto(origin+url);await exercise(name,label,width);
     if(name==='employee'){
      await page.getByRole('tablist',{name:'Employee information',exact:true}).getByRole('tab',{name:'Overview',exact:true}).click();
      await page.getByLabel('Employee information section',{exact:true}).selectOption('360');await exercise('employee-360','Employee overview sections',width);
     }
     if(name==='task-classic')await exercise('task-execution','Task execution sections',width);
     await page.mouse.move(0,0);await page.keyboard.press("Escape");
     await page.screenshot({path:path.join(output,`${name}-${width}.png`),fullPage:true});
     results.push({name,width,passed:true});fs.writeFileSync(path.join(output,'progress.json'),JSON.stringify({results,issues},null,2));console.log('PASS',name,width);
    }catch(e){results.push({name,width,passed:false,error:e.message.slice(0,700)});fs.writeFileSync(path.join(output,'progress.json'),JSON.stringify({results,issues},null,2));console.log('FAIL',name,width,e.message.slice(0,240));await page.screenshot({path:path.join(output,`${name}-${width}-failure.png`),fullPage:true}).catch(()=>{});}
   }
   // Person-management drawer runs in the real app and reads an existing user.
   try{await page.goto(origin+'/crm/leads/'+lead.id);await page.getByRole('tablist',{name:'CRM record information',exact:true}).waitFor();await page.evaluate(async()=>{const resource=performance.getEntriesByType('resource').map(r=>r.name).filter(name=>name.includes('/people/peopleTypes.ts')).at(-1);const {openPerson}=await import(resource || '/src/apps/project-management/components/people/peopleTypes.ts');openPerson({userId:1,compactMemberships:false});});await exercise('person-management','Person management sections',width);await page.screenshot({path:path.join(output,`person-management-${width}.png`),fullPage:true});await expect(page.getByRole('dialog').getByRole('button',{name:'Close preview',exact:true})).toBeInViewport();await page.getByRole('dialog').getByRole('button',{name:'Close preview',exact:true}).tap();await expect(page.getByRole('dialog')).toHaveCount(0);results.push({name:'person-management',width,passed:true});console.log('PASS person-management',width);}catch(e){results.push({name:'person-management',width,passed:false,error:e.message.slice(0,700)});console.log('FAIL person-management',width,e.message.slice(0,180));}
  }
  const report={results,issues,fixtures:fixtures?'all API responses (isolated layout verification)':['contract','billing-plan'],viewports:[1440,390,320],note:'Read-only real local API except explicitly listed record fixtures. No record mutations.'};fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log('RESULT',JSON.stringify({passed:results.filter(x=>x.passed).length,failed:results.filter(x=>!x.passed).length,issues:issues.length}));if(results.some(x=>!x.passed)||issues.length)process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
