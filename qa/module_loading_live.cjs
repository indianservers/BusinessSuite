// Full-app route audit against real local APIs. No intercepted/mock responses.
const {chromium}=require('../frontend/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const {auth}=require('./custom_fields_live.cjs');
const output=path.resolve('docs/qa/local-performance');fs.mkdirSync(output,{recursive:true});
const routes=(process.env.SPEED_ROUTES||'/dashboard,/crm,/crm/leads,/crm/contacts,/crm/deals,/pms,/pms/projects,/pms/tasks,/pms/tasks-follow-ups,/pms/people,/pms/messages,/hrms,/hrms/employees,/hrms/attendance,/hrms/payroll,/srm,/srm/customer-360,/srm/inventory,/srm/pos,/fam,/fam/ledgers,/fam/inventory/reports,/power-apps,/power-apps/connectors,/power-apps/automations,/power-apps/approvals,/crm/communication-hub,/ai-agents,/settings,/settings/branches,/portal/customer/login,/portal/partner/login').split(',');
const origin=process.env.SPEED_ORIGIN||'http://localhost:5173';
const report=path.join(output,process.env.SPEED_REPORT||'module-loading.json');
async function main(){
 for(let attempt=0;attempt<30;attempt++){try{const ready=await fetch('http://127.0.0.1:1534/health');if(ready.ok)break;}catch{}await new Promise(resolve=>setTimeout(resolve,1000));}
 const a=await auth(),browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1480,height:1000}});
 await context.addInitScript(({login,actor,access})=>{
  sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','6');
  sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{...actor,role:actor.role?.name||'super_admin',access}},version:0}));
 },a);
 const page=await context.newPage();let current;
 const pending=new Map(),assets=new Map(),apiTimes=[];
 page.on('pageerror',error=>{if(current)current.errors.push(error.message);});
 page.on('request',request=>{
  if(current&&['script','stylesheet'].includes(request.resourceType()))assets.set(request,current);
  if(!current||!request.url().includes('/api/'))return;
  apiTimes.push(Date.now());
  const item={owner:current,path:new URL(request.url()).pathname,method:request.method(),start:Date.now()};
  if(/\/stream(?:\?|$)|\/realtime(?:\/|$)|\/ws(?:\?|$)/.test(request.url()))return;
  pending.set(request,item);
 });
 page.on('response',response=>{const item=pending.get(response.request());if(item){item.status=response.status();if((response.headers()['content-type']||'').includes('text/event-stream'))pending.delete(response.request());}});
 page.on('requestfinished',request=>{assets.delete(request);const item=pending.get(request);if(item){item.owner.api.push({path:item.path,method:item.method,status:item.status,ms:Date.now()-item.start});pending.delete(request);}});
 page.on('requestfailed',request=>{assets.delete(request);const item=pending.get(request);if(item){item.owner.api.push({path:item.path,method:item.method,status:0,ms:Date.now()-item.start,failure:request.failure()?.errorText});pending.delete(request);}});
 const result={origin,at:new Date().toISOString(),pages:[]};
 try{
  for(const route of routes){
   const recent=apiTimes.filter(time=>Date.now()-time<60000);
   if(recent.length>=60){const wait=Math.max(0,61000-(Date.now()-recent[recent.length-60]));console.log(`Pacing route audit for ${Math.round(wait/1000)}s to preserve request budget.`);await page.waitForTimeout(wait);}
   current={route,errors:[],api:[]};result.pages.push(current);const started=Date.now();let quiet;
   try{
    if(result.pages.length===1||process.env.SPEED_COLD==='1')await page.goto(origin+route,{waitUntil:'domcontentloaded',timeout:30000});
    else await page.evaluate(route=>{history.pushState({...history.state,idx:(history.state?.idx||0)+1},'',route);window.dispatchEvent(new PopStateEvent('popstate'));},route);
    while(Date.now()-started<20000){
     const ready=await page.evaluate(()=>{const el=document.querySelector('#suite-main')||document.querySelector('main')||document.querySelector('#root');if(!el)return false;const text=el.textContent?.trim()||'';return text.length>45&&!/^Loading (page data|your workspace|data|task workspace)[.…]*$/.test(text)&&!text.startsWith('Loading workspace ·');});
     const active=[...pending.values()].some(item=>item.owner===current)||[...assets.values()].includes(current);
     if(ready&&!active){quiet??=Date.now();if(Date.now()-quiet>=400)break;}else quiet=undefined;
     await page.waitForTimeout(100);
    }
    current.readyMs=Date.now()-started;
    current.pending=[...pending.values()].filter(item=>item.owner===current).map(item=>item.path);
    current.headings=await page.locator('main h1,main h2').allTextContents();
    current.url=new URL(page.url()).pathname;
    current.alerts=(await page.locator('[role="alert"]').allTextContents()).map(text=>text.slice(0,160));
    if(current.errors.length||current.readyMs>5000||current.alerts.length)await page.screenshot({path:path.join(output,route.replace(/[^a-z0-9]/gi,'-')+'.png'),fullPage:false});
   }catch(error){current.error=error.message.split('\n')[0];current.readyMs=Date.now()-started;}
   current.slowApi=current.api.filter(item=>item.ms>750||item.status>=400).sort((a,b)=>b.ms-a.ms);
   fs.writeFileSync(report,JSON.stringify(result,null,2));
   console.log(JSON.stringify({route,ms:current.readyMs,headings:current.headings,errors:current.errors,slow:current.slowApi.slice(0,3)}));
   // Respect the real user's normal request budget; do not disable throttles.
   if(current.api.some(item=>item.status===429)){console.log('Rate limit reached; waiting for the next request window.');await page.waitForTimeout(60000-Date.now()%60000+1000);}
   await page.waitForTimeout(1000);
  }
 }finally{await browser.close();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
