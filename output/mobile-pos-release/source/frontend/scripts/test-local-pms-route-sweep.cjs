// Explicit local acceptance probe. Credentials come from its private Python launcher.
const fs=require('node:fs'),path=require('node:path');const{chromium}=require('playwright');
const origin=process.env.LOCAL_AUDIT_ORIGIN,backend=process.env.LOCAL_AUDIT_BACKEND;
if(!origin||!backend||![origin,backend].every(url=>new URL(url).hostname==='127.0.0.1'))throw new Error('Explicit loopback test targets required');
const sanitize=value=>{let text=String(value);for(const secret of [process.env.LOCAL_AUDIT_EMAIL,process.env.LOCAL_AUDIT_PASSWORD])if(secret)text=text.split(secret).join('[private]');return text.replace(/Bearer [A-Za-z0-9._-]+/g,'Bearer [private]').replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[private token]');};
(async()=>{const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1280,height:672}});page.setDefaultTimeout(30000);
 const report={target:'audit-owned BusinessSuite development frontend and configured local backend',viewport:{width:1280,height:672},read_only_business_data:true,startup_bundles:[],steps:[],requests:[],blockedWrites:[],externalOrigins:[],pageErrors:[],consoleErrors:[]};let stage='initial';const pending=new Set(),byRequest=new Map();
 const allowedOrigins=new Set([new URL(origin).origin,new URL(backend).origin]);
 await page.route('**/*',async route=>{const request=route.request(),url=new URL(request.url()),method=request.method();if(!allowedOrigins.has(url.origin)){report.externalOrigins.push(url.origin);return route.abort();}
  if(url.pathname.startsWith('/api/v1/')&&!['GET','HEAD','OPTIONS'].includes(method)&&!['/api/v1/auth/login','/api/v1/auth/refresh','/api/v1/project-management/custom-fields/records'].includes(url.pathname)){
   // Server-side grid queries and personal preferences have no business write effect.
   if(!url.pathname.endsWith('/query')&&!url.pathname.includes('/preferences')&&!url.pathname.includes('/view-preferences')){report.blockedWrites.push({stage,method,path:url.pathname});return route.fulfill({status:409,json:{detail:'Read-only local audit: mutation not performed'}});}
  }return route.continue();});
 page.on('console',message=>{if(message.type()==='error')report.consoleErrors.push({stage,text:sanitize(message.text())});});
 page.on('request',request=>{const url=new URL(request.url());if(!url.pathname.startsWith('/api/v1/'))return;const row={stage,method:request.method(),path:url.pathname,started:Date.now()};byRequest.set(request,row);if(['xhr','fetch'].includes(request.resourceType())&&!/stream|events/.test(url.pathname))pending.add(request);});
 page.on('response',response=>{const row=byRequest.get(response.request());if(row){row.status=response.status();row.ttfb_ms=Date.now()-row.started;}const url=new URL(response.url());if(url.pathname.endsWith('/overview')&&url.searchParams.get('include_people')==='true'&&response.status()===200)void response.json().then(data=>report.startup_bundles.push({members:Array.isArray(data.members),invitations:Array.isArray(data.invitations),invitation_tokens_absent:Array.isArray(data.invitations)&&data.invitations.every(row=>!('token' in row))})).catch(()=>{});});
 const finished=request=>{pending.delete(request);const row=byRequest.get(request);if(row){row.elapsed_ms=Date.now()-row.started;const timing=request.timing();if(timing.requestStart>=0&&timing.responseStart>=0)row.server_wait_ms=Math.round(timing.responseStart-timing.requestStart);if(timing.requestStart>=0)row.before_request_ms=Math.round(timing.requestStart);delete row.started;report.requests.push(row);byRequest.delete(request);}};page.on('requestfinished',finished);page.on('requestfailed',finished);page.on('pageerror',error=>report.pageErrors.push(sanitize(error.message)));
 async function quiet(limit=15000){const start=Date.now();let idleAt=0;while(Date.now()-start<limit){if(pending.size===0){if(!idleAt)idleAt=Date.now();if(Date.now()-idleAt>=350)return true;}else idleAt=0;await new Promise(resolve=>setTimeout(resolve,100));}return false;}
 try{
  let start=Date.now();await page.goto(origin+(process.env.LOCAL_AUDIT_START_PATH||'/crm'),{waitUntil:'domcontentloaded',timeout:60000});await page.getByLabel('Email address',{exact:true}).waitFor();report.steps.push({name:'cold_login_form',ui_ready_ms:Date.now()-start,path:new URL(page.url()).pathname});
  stage='login';await page.getByLabel('Email address',{exact:true}).fill(process.env.LOCAL_AUDIT_EMAIL);await page.getByLabel('Password',{exact:true}).fill(process.env.LOCAL_AUDIT_PASSWORD);start=Date.now();await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL(url=>!['/login','/post-login'].includes(url.pathname),{timeout:60000});await page.locator('h1:visible').first().waitFor({timeout:60000});const loginReady=Date.now()-start;const loginQuiet=await quiet();report.steps.push({name:'login_to_workspace',ui_ready_ms:loginReady,data_settled_ms:Date.now()-start,api_quiet:loginQuiet,path:new URL(page.url()).pathname});
  const routes=JSON.parse(fs.readFileSync(process.env.LOCAL_AUDIT_ROUTES,'utf8'));
  for(const target of routes){
    stage=target;const before=report.requests.length;start=Date.now();
    await page.evaluate(target=>{history.pushState({},'',target);window.dispatchEvent(new PopStateEvent('popstate'));},target);
    await page.waitForTimeout(300);const settled=await quiet(20000);
    const heading=await page.locator('h1:visible,h2:visible').first().textContent().catch(()=>null);
    const stageReads=report.requests.filter(row=>row.stage===stage);
    report.steps.push({name:target,path:new URL(page.url()).pathname,heading:sanitize(heading),visible_alerts:await page.locator('[role="alert"]:visible').allTextContents(),visible_statuses:await page.locator('[role="status"]:visible').allTextContents(),body_excerpt:heading?undefined:sanitize((await page.locator("body").innerText()).slice(-1800)),data_settled_ms:Date.now()-start,api_quiet:settled,workspace_reads:stageReads.filter(row=>row.path==='/api/v1/project-management/workspaces').length,api_errors:stageReads.filter(row=>row.status>=400).map(row=>({path:row.path,status:row.status}))});
    fs.writeFileSync(process.env.LOCAL_AUDIT_OUTPUT,JSON.stringify(report,null,2));
    await page.waitForTimeout(Math.max(500,stageReads.length*900-(Date.now()-start)));
  }
  report.completed=true;
 }catch(error){report.completed=false;report.error=sanitize(error.stack||error);}
 finally{report.remainingApiReads=pending.size;report.requestCounts=Object.fromEntries([...new Set(report.requests.map(row=>row.path))].map(key=>[key,report.requests.filter(row=>row.path===key).length]));const output=process.env.LOCAL_AUDIT_OUTPUT;if(output)fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify({completed:report.completed,steps:report.steps,errors:report.pageErrors,error:report.error}));if(!report.completed)process.exitCode=1;await page.unrouteAll({behavior:'wait'});await browser.close();}
 console.log(JSON.stringify({completed:report.completed,steps:report.steps,api_errors:report.requests.filter(row=>row.status>=400),blockedWrites:report.blockedWrites,page_error_count:report.pageErrors.length,error:report.error}));if(!report.completed)process.exitCode=1;
})().catch(error=>{console.error(sanitize(error.stack||error));process.exitCode=1});
