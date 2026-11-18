const path=require('node:path');
const {chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:15000});
(async()=>{
 process.chdir(path.resolve(__dirname,'..'));const {createServer}=await import('vite');const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
  for(const [width,height] of [[390,844]]){
   const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.route('**/api/v1/**',async route=>{const url=new URL(route.request().url()),p=url.pathname;
    if(p.endsWith('/auth/me')||p.endsWith('/access/me')){const user=await page.evaluate(()=>window.srmQaIdentity());return route.fulfill({json:p.endsWith('/auth/me')?user.identity:user.access});}
    if(p.includes('/dashboard-workspace/context'))return route.fulfill({json:{business_date:'2026-11-17',timezone:'UTC',organization_id:1,sections:['summary','cash','collections','orders','quotations'],can_create:true,can_pos:true,can_plan:false,owners:[],customers:[],teams:[],branches:[]}});
    if(p.includes('/dashboard-workspace/'))return route.fulfill({json:{section:p.split('/').pop(),context:{as_of:'2026-11-17',start_date:'2026-11-01',end_date:'2026-11-17',previous_start:null,previous_end:null},metrics:{},series:[],rows:[],total_rows:0,notes:[]}});
    if(p.endsWith('/industry/capabilities'))return route.fulfill({json:{appointments_view:true,appointments_schedule:true,checkout_create:true,checkout_collect:true,operational_scope:{realm:'pack',user_id:77,company_id:1,branch_id:1,context_id:11,pack_key:'hospital',pack_version:1,context_revision:1,grant_revision:1,activation_revision:1}}});
    if(p.endsWith('/srm/business/related-projects')||p.endsWith('/srm/business/teams')||p.endsWith('/collaboration/workspaces')||p.endsWith('/activity')||/^\/api\/v1\/imports\/srm\/(catalog|history)$/.test(p))return route.fulfill({json:[]});
    if(p.startsWith('/api/v1/profiles/')||p.startsWith('/api/v1/record-360/'))return route.fulfill({status:403,json:{detail:'Private profile unavailable in this read-only UI fixture'}});
    if(p.startsWith('/api/v1/scheduling/'))return route.fulfill({json:{revision:1,records:{},dependencies:[]}});
    if(p.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,branches:[{id:1,name:'City branch',can_write:true}]}});
    return route.fulfill({json:{items:[],rows:[],total:0,pageTotal:0,page:1,per_page:10,next:null,sections:[],metrics:{},series:[],employees:[],resources:[],specialists:[],canCreate:true,context:{canCreate:true},permissions:{create:true,view:true}}});
   });
   await page.route('**/*',route=>route.request().resourceType()==='document'?route.fulfill({contentType:'text/html',body:'<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/srm-mobile-workspace.tsx");</script>'}):route.fallback());
   await page.goto(server.resolvedUrls.local[0]+'srm/qa-short');await expect(page.locator('.srm-mobile-screen')).toBeVisible();
   const registered=await page.evaluate(()=>window.srmQaRoutes);
   const nativePaths=[...registered.filter(value=>!value.includes(':')&&!['/srm/pos','/srm/pos/terminal','/srm/settings','/srm/suppliers'].includes(value)),'/srm/sales-orders/10','/srm/contracts/10','/srm/customers/10/360'];
   const failures=[];
   for(const nativePath of nativePaths){
    errors.length=0;try{
     await page.goto(server.resolvedUrls.local[0]+nativePath.slice(1));await expect(page.locator('.srm-mobile-screen')).toBeVisible();await expect(page.getByText('Loading Sales page',{exact:true})).toBeHidden();await page.waitForTimeout(220);
     const routeCount=await page.evaluate(()=>window.srmQaRoutes.length);
     const metrics=await page.evaluate(()=>{const view=document.querySelector('.srm-mobile-viewport'),root=document.querySelector('.srm-mobile-document');return {width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,view:view.clientHeight,content:view.scrollHeight,units:root.querySelectorAll('[data-srm-page-unit]').length,title:document.querySelector('.srm-mobile-header h1').textContent};});
     expect(metrics.width).toBeLessThanOrEqual(width);expect(metrics.height).toBeLessThanOrEqual(height);expect(metrics.content).toBeLessThanOrEqual(metrics.view+2);expect(metrics.units).toBeGreaterThan(0);expect(errors).toEqual([]);
     console.log('PASS',nativePath,metrics.title,'registered routes',routeCount);
     if(['/srm','/srm/sales-orders','/srm/customers','/srm/inventory/products','/srm/appointments'].includes(nativePath))await page.screenshot({path:path.resolve('../output',`srm-native-${nativePath.replaceAll('/','-')}-${width}.png`),fullPage:true});
    }catch(error){failures.push({path:nativePath,error:error.message,errors:[...errors]});console.log('FAIL',nativePath,error.message.slice(0,250),errors);await page.screenshot({path:path.resolve('../output',`srm-native-failure-${nativePath.replaceAll('/','-')}.png`),fullPage:true}).catch(()=>{});}
   }
   for(const terminal of ['/srm/pos','/srm/pos/terminal']){await page.goto(server.resolvedUrls.local[0]+terminal.slice(1));await expect(page.locator('.srm-pos')).toBeVisible();await expect(page.locator('.srm-mobile-screen')).toHaveCount(0);console.log('PASS existing POS host',terminal);}
   console.log(`Checked ${nativePaths.length} native route hosts from ${registered.length} registered SRM routes`);console.log('NATIVE FAILURES',JSON.stringify(failures));expect(failures).toEqual([]);await page.close();
  }
 }finally{await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exit(1);});
