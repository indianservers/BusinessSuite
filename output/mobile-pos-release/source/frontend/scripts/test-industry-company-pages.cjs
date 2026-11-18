const fs=require('node:fs'),path=require('node:path');
const {chromium,expect,request}=require('playwright/test');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'output/business-profile-15-companies');
const credentials=JSON.parse(fs.readFileSync(path.join(root,'.local/industry-qa15/credentials.json'),'utf8'));
const apiOrigin=JSON.parse(fs.readFileSync(path.join(root,'.local/industry-qa15/api.json'),'utf8')).origin;
let companies=JSON.parse(fs.readFileSync(path.join(out,'companies.json'),'utf8')).companies;
const workflows=JSON.parse(fs.readFileSync(path.join(out,'workflows.json'),'utf8')).companies;
if(process.env.INDUSTRY_QA_COMPANIES)companies=companies.filter(c=>process.env.INDUSTRY_QA_COMPANIES.split(',').includes(c.industry));
const shard=process.env.INDUSTRY_QA_SHARD;if(shard!==undefined)companies=companies.filter((_,i)=>i%3===Number(shard));
const limit=Number(process.env.INDUSTRY_QA_PAGE_LIMIT||0),report=path.join(out,process.env.INDUSTRY_QA_REPORT||(limit?'browser-smoke.json':shard!==undefined?'browser-pages-shard'+shard+'.json':'browser-pages.json'));
const state=process.env.INDUSTRY_QA_RESUME&&fs.existsSync(report)?JSON.parse(fs.readFileSync(report,'utf8')):{companies:{},started_at:new Date().toISOString()};delete state.finished_at;
const save=()=>{fs.writeFileSync(report+'.tmp',JSON.stringify(state,null,2));fs.renameSync(report+'.tmp',report);};
const list=value=>Array.isArray(value)?value:value?.items||value?.employees||value?.records||[];
const cleanUrl=value=>{const u=new URL(value);for(const key of [...u.searchParams.keys()])if(/token|secret|signature|session|key/i.test(key))u.searchParams.set(key,'[redacted]');return u.pathname+u.search;};
(async()=>{
 process.chdir(path.join(root,'frontend'));
 const {createServer}=await import('vite');const server=await createServer({root:process.cwd(),cacheDir:path.join(root,'.local/industry-qa15/vite-'+process.pid),server:{host:'127.0.0.1',port:0,hmr:false,watch:null,proxy:{'/api':{target:apiOrigin,changeOrigin:true}}}});await server.listen();
 const origin=server.resolvedUrls.local[0].replace(/\/$/,'');const browser=await chromium.launch({headless:true});
 try{
  for(const company of companies){
   const previous=state.companies[company.industry];const result=state.companies[company.industry]={workspace:company.workspace,routes:previous?.routes.filter(r=>r.status==='rendered'&&r.path!=='/dashboard')||[],home:'pending'};save();
   const client=await request.newContext({baseURL:apiOrigin,extraHTTPHeaders:{'X-Suite-Tenant':company.workspace,'X-Suite-Organization':String(company.company_id),'X-Suite-Branch':String(company.branch_id)}});
   const loginResponse=await client.post('/api/v1/auth/login',{data:{email:company.email,password:credentials.password}});if(!loginResponse.ok())throw Error(company.industry+' login '+loginResponse.status());
   const auth=await loginResponse.json(),headers={Authorization:'Bearer '+auth.access_token};
   const meResponse=await client.get('/api/v1/auth/me',{headers}),accessResponse=await client.get('/api/v1/access/me',{headers});
   if(!meResponse.ok()||!accessResponse.ok())throw Error('Identity reads failed');const me=await meResponse.json(),access=await accessResponse.json();
   const user={...me,role:me.role&&typeof me.role==='object'?me.role.name:(me.role||auth.role||'employee'),access};
   const persisted={state:{accessToken:auth.access_token,refreshToken:auth.refresh_token,user,isAuthenticated:true},version:0};
   const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'Asia/Kolkata'});
   await context.addInitScript(({persisted,company})=>{sessionStorage.setItem('hrms-auth',JSON.stringify(persisted));sessionStorage.setItem('suite-tenant',company.workspace);sessionStorage.setItem('suite-organization',String(company.company_id));sessionStorage.setItem('suite-branch',String(company.branch_id));window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};},{persisted,company});
   await context.route('**/app-config.js',route=>route.fulfill({contentType:'application/javascript',body:"window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};"}));
   const page=await context.newPage();let active=null;const pending=new Set(),owners=new Map();
   page.on('pageerror',error=>{if(active)active.errors.push(error.message.slice(0,1000));});
   page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/v1/')){pending.add(r);owners.set(r,active);}});
   page.on('requestfailed',r=>pending.delete(r));page.on('requestfinished',r=>pending.delete(r));
   page.on('response',response=>{const row=owners.get(response.request());if(row&&new URL(response.url()).pathname.startsWith('/api/v1/'))row.reads.push({path:cleanUrl(response.url()),method:response.request().method(),status:response.status()});});
   try{
    active={path:'/dashboard',reads:[],errors:[]};result.routes.push(active);
    await page.goto(origin+'/dashboard',{waitUntil:'domcontentloaded'});
    await expect(page.getByRole('heading',{name:'Your work starts here.',exact:true})).toBeVisible({timeout:90000});await expect(page.locator('.launcher-card').first()).toBeVisible({timeout:60000});const profile=await client.get('/api/v1/access/settings/business-profile/effective',{headers});if(!profile.ok()||(await profile.json()).business_type!==company.industry)throw Error('Business profile does not match this company');result.home='passed';
    await page.screenshot({path:path.join(out,company.industry+'-workspace.png'),fullPage:true});
    const inventory=await page.evaluate(async()=>{const modules=await Promise.all([import('/src/apps/hrms/routes.tsx'),import('/src/apps/crm/routes.tsx'),import('/src/apps/project-management/routes.tsx'),import('/src/apps/srm/routes.tsx')]);const{canAccessRoute}=await import('/src/lib/roles.ts');const{useAuthStore}=await import('/src/store/authStore.ts');const user=useAuthStore.getState().user;return modules.flatMap(m=>Object.values(m).filter(Array.isArray).flatMap(v=>v.map(r=>r.path))).filter(p=>/^(hrms|crm|pms|srm)(\/|$)/.test(p)).map(p=>({pattern:'/'+p,allowed:canAccessRoute('/'+p,user.role,user.is_superuser)}));});
    result.inventory=[...new Map(inventory.map(row=>[row.pattern,row])).values()];
    const ids={...workflows[company.industry].records};
    for(const [key,url] of [['contact_id','/crm/contacts?per_page=1'],['deal_id','/crm/deals?per_page=1'],['invoice_id','/srm/invoices'],['order_id','/srm/sales-orders']]){const response=await client.get('/api/v1'+url,{headers});if(response.ok())ids[key]=list(await response.json())[0]?.id;}
    function resolve(pattern){
     let route=pattern;if(!route.includes(':')&&!route.includes('*'))return route;
     route=route.replace(/:projectId\b/g,String(ids.project_id)).replace(/:taskId\b/g,String(ids.task_id)).replace(/:employeeId\b/g,String(ids.employee_id));
     if(route.includes(':id')){let key=/^\/hrms\/employees?\//.test(route)?'employee_id':/^\/pms\/projects\//.test(route)?'project_id':/^\/pms\/tasks\//.test(route)?'task_id':/^\/crm\/leads\//.test(route)?'lead_id':/^\/crm\/contacts\//.test(route)?'contact_id':/^\/crm\/deals\//.test(route)?'deal_id':/\/customers\//.test(route)?'customer_id':/^\/srm\/invoices\//.test(route)?'invoice_id':/^\/srm\/sales-orders\//.test(route)?'order_id':null;if(key&&ids[key])route=route.replace(/:id\b/g,String(ids[key]));}
     return /[:*]|undefined/.test(route)?null:route;
    }
    let routes=result.inventory.filter(row=>row.allowed).map(row=>({...row,path:resolve(row.pattern)}));if(limit)routes=routes.slice(0,limit);
    active.status=active.errors.length?'failed':'rendered';save();
    for(const entry of routes){
     if(result.routes.some(row=>row.path===entry.path&&row.status==='rendered'))continue;
     if(!entry.path){result.routes.push({...entry,status:'needs_record',reads:[],errors:[]});continue;}
     const row=active={...entry,status:'pending',reads:[],errors:[]};result.routes.push(row);
     try{
      await page.evaluate(url=>{history.pushState({},'',url);window.dispatchEvent(new PopStateEvent('popstate'));},entry.path);
      await page.waitForTimeout(250);
      await expect.poll(()=>pending.size,{timeout:30000}).toBe(0);
      await page.locator('main').first().waitFor({state:'visible',timeout:20000});
      await page.waitForTimeout(150);
      row.url=cleanUrl(page.url());row.headings=await page.locator('main h1,main h2,main h3').allTextContents();
      row.text=(await page.locator('main').first().innerText()).slice(0,4000);
      const server=row.reads.find(r=>r.status>=500);if(server)throw Error('API '+server.status+' '+server.path);
      if(row.errors.length)throw Error(row.errors[0]);
      if(new URL(page.url()).pathname==='/login')throw Error('Authentication redirect');
      if(/Something went wrong|Unexpected Application Error/i.test(row.text))throw Error('Application error screen');
      if(!row.text.trim()&&!await page.locator('main canvas,main iframe').count())throw Error('Empty page content');
      row.status='rendered';
     }catch(error){row.status='failed';row.error=error.message.slice(0,1000);}
     save();console.log(company.industry+' '+row.status+' '+entry.path);
    }
   }catch(error){result.error=error.message.slice(0,1000);if(active){active.status='failed';active.error=result.error;}result.home=result.home==='passed'?'passed':'failed';save();console.log(company.industry+' failed: '+result.error);}
   finally{active=null;await context.close();await client.dispose();}
  }
 }finally{state.finished_at=new Date().toISOString();save();await browser.close();await server.close();}
 const failures=Object.values(state.companies).flatMap(c=>c.routes).filter(r=>r.status==='failed');console.log('Page failures:',failures.length);process.exitCode=failures.length||Object.values(state.companies).some(c=>c.home!=='passed'||c.error)?1:0;
})().catch(error=>{console.error(error.message);process.exitCode=1;});
