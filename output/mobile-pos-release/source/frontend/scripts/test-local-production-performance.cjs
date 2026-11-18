// Benchmarks a dedicated local production build. Never records credentials/storage.
const fs=require('node:fs');const{chromium}=require('playwright');
const backend=process.env.LOCAL_AUDIT_BACKEND;
const hardSamples=Number(process.env.LOCAL_AUDIT_HARD_SAMPLES||20),switchSamples=Number(process.env.LOCAL_AUDIT_SWITCH_SAMPLES||21);
if(!Number.isInteger(hardSamples)||hardSamples<1||hardSamples>20||!Number.isInteger(switchSamples)||switchSamples<0||switchSamples>21)throw new Error('Invalid bounded sample count');
if(!backend||new URL(backend).hostname!=='127.0.0.1')throw new Error('Explicit loopback API required');
const clean=v=>{let s=String(v);for(const k of['LOCAL_AUDIT_EMAIL','LOCAL_AUDIT_PASSWORD'])if(process.env[k])s=s.split(process.env[k]).join('[private]');return s.replace(/Bearer [A-Za-z0-9._-]+/g,'Bearer [private]').replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,'[private token]');};
const percentile=(values,p)=>{const a=[...values].sort((a,b)=>a-b);return a[Math.ceil(a.length*p)-1];};
(async()=>{
 const{preview}=await import('vite');
 const server=await preview({build:{outDir:'../.tmp/industry-performance-build'},preview:{host:'127.0.0.1',port:0,proxy:{'/api':{target:backend,changeOrigin:true},'/uploads':{target:backend,changeOrigin:true}}}});
 const origin='http://127.0.0.1:'+server.httpServer.address().port,browser=await chromium.launch({headless:true});
 const report={target:'Dedicated local production bundle, configured loopback API; read-only business data',started_at:new Date().toISOString(),hard_loads:[],switches:[],requests:[],errors:[],blocked_writes:[],external:[]};
 function save(){if(process.env.LOCAL_AUDIT_OUTPUT)fs.writeFileSync(process.env.LOCAL_AUDIT_OUTPUT,JSON.stringify(report,null,2));}
 async function observe(page,stage){
  const pending=new Set(),requests=new Map();
  await page.route('**/*',route=>{const q=route.request(),u=new URL(q.url());if(![origin,backend].includes(u.origin)){report.external.push(u.origin);return route.abort();}if(u.pathname.startsWith('/api/v1/')&&!['GET','HEAD','OPTIONS'].includes(q.method())&&!['/api/v1/auth/login','/api/v1/auth/refresh','/api/v1/project-management/custom-fields/records'].includes(u.pathname)&&!u.pathname.endsWith('/query')&&!u.pathname.includes('/preferences')&&!u.pathname.includes('/view-preferences')){report.blocked_writes.push({stage:stage(),path:u.pathname,method:q.method()});return route.fulfill({status:409,json:{detail:'Read-only performance probe'}});}return route.continue();});
  page.on('pageerror',e=>report.errors.push(clean(e.message)));
  page.on('request',q=>{const u=new URL(q.url());if(!u.pathname.startsWith('/api/v1/'))return;requests.set(q,{stage:stage(),path:u.pathname,method:q.method(),started:Date.now()});if(['fetch','xhr'].includes(q.resourceType())&&!/stream|events/.test(u.pathname))pending.add(q);});
  page.on('response',r=>{const row=requests.get(r.request());if(row){row.status=r.status();row.ttfb_ms=Date.now()-row.started;}});
  const finish=q=>{pending.delete(q);const row=requests.get(q);if(row){row.elapsed_ms=Date.now()-row.started;const t=q.timing();row.timing={request_start_ms:t.requestStart,response_start_ms:t.responseStart,response_end_ms:t.responseEnd,server_wait_ms:t.responseStart>=0&&t.requestStart>=0?t.responseStart-t.requestStart:null};if(q.failure())row.failure=q.failure().errorText;delete row.started;report.requests.push(row);requests.delete(q);}};page.on('requestfinished',finish);page.on('requestfailed',finish);
  return async()=>{const start=Date.now();let idle=0;while(Date.now()-start<15000){if(!pending.size){if(!idle)idle=Date.now();if(Date.now()-idle>=300)return true;}else idle=0;await new Promise(r=>setTimeout(r,40));}return false;};
 }
 const runtime=()=>{window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1',uploadsBaseUrl:'/uploads'};};
 const selectors={'/crm':'.crm-ref-heading h1','/srm':'.sales-dash-heading h1','/pms':'.wb-work-header h1'};
 let liveContext,switchSettle;
 try{
  let stage='login';const initial=await browser.newContext({viewport:{width:1280,height:672}});await initial.addInitScript(runtime);const first=await initial.newPage(),quiet=await observe(first,()=>stage);
  await first.goto(origin+'/crm',{waitUntil:'domcontentloaded'});await first.getByLabel('Email address',{exact:true}).fill(process.env.LOCAL_AUDIT_EMAIL);await first.getByLabel('Password',{exact:true}).fill(process.env.LOCAL_AUDIT_PASSWORD);await first.getByRole('button',{name:'Sign in',exact:true}).click();await first.locator(selectors['/crm']).waitFor({state:'visible',timeout:60000});await quiet();
  const storage=await initial.storageState(),sessions=await first.evaluate(()=>Object.fromEntries(Object.entries(sessionStorage)));await initial.close();
  for(let i=0;i<hardSamples;i++){
   stage='hard-'+i;const context=await browser.newContext({storageState:storage,viewport:{width:1280,height:672}});await context.addInitScript(runtime);await context.addInitScript(values=>{for(const[k,v]of Object.entries(values))sessionStorage.setItem(k,v);},sessions);const page=await context.newPage(),settle=await observe(page,()=>stage);
   const start=Date.now();await page.goto(origin+'/crm',{waitUntil:'domcontentloaded'});await page.locator(selectors['/crm']).waitFor({state:'visible',timeout:30000});const ui=Date.now()-start;
   await page.waitForFunction(()=>document.querySelector('.crm-ref-live')?.textContent?.trim()==='Updated',null,{timeout:30000});const content=Date.now()-start;const idle=await settle();const rows=report.requests.filter(r=>r.stage===stage);
   report.hard_loads.push({sample:i,cold_browser_cache:true,ui_ready_ms:ui,content_ready_ms:content,data_settled_ms:Date.now()-start,api_quiet:idle,requests:rows.length,workspace_reads:rows.filter(r=>r.path==='/api/v1/project-management/workspaces').length,forecast_reads:rows.filter(r=>r.path.startsWith('/api/v1/crm/forecast')).length});save();
   if(rows.some(r=>r.status>=400))throw new Error('Hard-load API error; inspect status records');
   if(i===hardSamples-1){liveContext=context;switchSettle=settle;break;}await context.close();
   // Leave headroom below native shared limits, including login/bootstrap requests.
   await new Promise(r=>setTimeout(r,Math.max(3000,rows.length*850-(Date.now()-start))));
  }
  const page=liveContext.pages()[0],settle=switchSettle;
  for(let i=0;i<switchSamples;i++){
   const target=['/srm','/pms','/crm'][i%3];stage='switch-'+i;const select=page.locator('select[aria-label="Switch business module"]:visible').first();
   // PMS must have its native work data, not a provisional heading that can flash
   // before the selected workspace has loaded. Background panels settle below.
   const overview=target==='/pms'?page.waitForResponse(r=>/\/api\/v1\/project-management\/workspaces\/\d+\/overview$/.test(new URL(r.url()).pathname)&&r.status()===200,{timeout:30000}):null;
   const start=Date.now();await select.selectOption(target);await page.waitForURL(u=>u.pathname===target||u.pathname.startsWith(target+'/'));await page.locator(selectors[target]).waitFor({state:'visible',timeout:30000});const headingReady=Date.now()-start;
   if(overview){const data=await(await overview).json();if(!Array.isArray(data.projects)||!Array.isArray(data.tasks)||!Array.isArray(data.members))throw new Error('PMS startup data was not verified');await page.locator(selectors[target]).waitFor({state:'visible',timeout:30000});}
   if(target==='/crm')await page.waitForFunction(()=>document.querySelector('.crm-ref-live')?.textContent?.trim()==='Updated',null,{timeout:30000});
   if(target==='/srm')await page.waitForFunction(()=>{const p=document.querySelector('.sales-dash-kpis');return p&&!p.querySelector('[role="status"],[role="alert"]')&&![...p.querySelectorAll('p')].some(n=>n.textContent?.trim()==='Unavailable');},null,{timeout:30000});
   const ui=Date.now()-start;const idle=await settle();const rows=report.requests.filter(r=>r.stage===stage);
   report.switches.push({sample:i,module:target,heading_ready_ms:headingReady,ui_ready_ms:ui,data_settled_ms:Date.now()-start,api_quiet:idle,requests:rows.length,workspace_reads:rows.filter(r=>r.path==='/api/v1/project-management/workspaces').length,forecast_reads:rows.filter(r=>r.path.startsWith('/api/v1/crm/forecast')).length});save();
   if(rows.some(r=>r.status>=400))throw new Error('Module-switch API error; inspect status records');
   await new Promise(r=>setTimeout(r,Math.max(3000,rows.length*850-(Date.now()-start))));
  }
  report.summary={hard_load_samples:hardSamples,hard_ui_p95_ms:percentile(report.hard_loads.map(r=>r.ui_ready_ms),.95),hard_content_p95_ms:percentile(report.hard_loads.map(r=>r.content_ready_ms),.95),hard_data_p95_ms:percentile(report.hard_loads.map(r=>r.data_settled_ms),.95),switch_samples:switchSamples,switch_ui_p95_ms:percentile(report.switches.map(r=>r.ui_ready_ms),.95),switch_data_p95_ms:percentile(report.switches.map(r=>r.data_settled_ms),.95),api_errors:report.requests.filter(r=>r.status>=400).length,page_errors:report.errors.length,unused_forecast_reads:report.requests.filter(r=>r.path.startsWith('/api/v1/crm/forecast')).length};
  report.summary.switch_ui_max_ms=Math.max(0,...report.switches.map(r=>r.ui_ready_ms));
  report.summary.by_module=Object.fromEntries(['/crm','/srm','/pms'].map(module=>{const rows=report.switches.filter(r=>r.module===module);return[module,{samples:rows.length,ui_p95_ms:percentile(rows.map(r=>r.ui_ready_ms),.95),ui_max_ms:Math.max(0,...rows.map(r=>r.ui_ready_ms)),data_p95_ms:percentile(rows.map(r=>r.data_settled_ms),.95)}];}));
  report.acceptance={hard_content_under_3s:report.summary.hard_content_p95_ms<3000,switch_ui_under_1s:report.summary.switch_ui_max_ms<1000,no_unused_forecast:report.summary.unused_forecast_reads===0,no_errors:report.summary.api_errors===0&&report.errors.length===0&&report.blocked_writes.length===0,all_native_reads_finished:[...report.hard_loads,...report.switches].every(row=>row.api_quiet)};report.completed=true;
 }catch(e){report.completed=false;report.error=clean(e.stack||e);}
 finally{report.finished_at=new Date().toISOString();save();console.log(JSON.stringify({completed:report.completed,summary:report.summary,acceptance:report.acceptance,error:report.error}));process.exitCode=!report.completed?1:Object.values(report.acceptance).some(value=>value===false)?2:0;await browser.close();await new Promise(resolve=>server.httpServer.close(resolve));}
})().catch(e=>{console.error(clean(e.stack||e));process.exitCode=1});
