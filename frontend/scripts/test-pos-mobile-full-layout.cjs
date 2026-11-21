const path=require('node:path');
const {chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:15000});
(async()=>{
 process.chdir(path.resolve(__dirname,'..'));const {createServer}=await import('vite');const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{
  for(const [width,height] of [[320,568],[390,844],[430,932]]){
   let registerOpen=true,openedRegisters=0;const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.route('**/api/v1/**',async route=>{const url=new URL(route.request().url()),p=url.pathname;
    if(p.endsWith('/auth/me')||p.endsWith('/access/me')){const user=await page.evaluate(()=>window.srmQaIdentity());return route.fulfill({json:p.endsWith('/auth/me')?user.identity:user.access});}
    if(p.includes('/dashboard-workspace/context'))return route.fulfill({json:{business_date:'2026-11-17',timezone:'UTC',organization_id:1,sections:['summary','cash','collections','orders','quotations'],can_create:true,can_pos:true,can_plan:false,owners:[],customers:[],teams:[],branches:[]}});
    if(p.includes('/dashboard-workspace/'))return route.fulfill({json:{section:p.split('/').pop(),context:{as_of:'2026-11-17',start_date:'2026-11-01',end_date:'2026-11-17',previous_start:null,previous_end:null},metrics:{},series:[],rows:[],total_rows:0,notes:[]}});
    if(p.endsWith('/industry/capabilities'))return route.fulfill({json:{appointments_view:true,appointments_schedule:true,checkout_create:true,checkout_collect:true,operational_scope:{realm:'pack',user_id:77,company_id:1,branch_id:1,context_id:11,pack_key:'hospital',pack_version:1,context_revision:1,grant_revision:1,activation_revision:1}}});
    if(p.endsWith('/srm/business/related-projects')||p.endsWith('/srm/business/teams')||p.endsWith('/collaboration/workspaces')||p.endsWith('/activity')||/^\/api\/v1\/imports\/srm\/(catalog|history)$/.test(p))return route.fulfill({json:[]});
    if(p.startsWith('/api/v1/profiles/')||p.startsWith('/api/v1/record-360/'))return route.fulfill({status:403,json:{detail:'Private profile unavailable in this read-only UI fixture'}});
    if(p.startsWith('/api/v1/scheduling/'))return route.fulfill({json:{revision:1,records:{},dependencies:[]}});
    if(p.endsWith('/access/settings/defaults/effective'))return route.fulfill({json:{values:{timezone:'UTC',currency:'INR'},modules:{},companyId:1,branchId:1}});
    if(p.endsWith('/pos/sessions/active'))return route.fulfill({json:{session:registerOpen?{id:81,status:'open',opening_cash:100,session_number:'POS-81',register_name:'Front desk'}:null,expected_cash:100}});
    if(p.endsWith('/pos/sessions')&&route.request().method()==='POST'){registerOpen=true;openedRegisters++;return route.fulfill({json:{id:81,status:'open'}});}
    if(p.endsWith('/pos/catalog'))return route.fulfill({json:{items:Array.from({length:8},(_,index)=>({id:index+1,item_name:`Retail item ${index+1}`,sku:`SKU${index+1}`,barcode:`10${index}`,unit_code:'PCS',product_type:'product',sales_rate:25,gst_rate:0,current_quantity:10,track_inventory:true,checkout_supported:true,active:true})),next:null,features:{appointments_schedule:true,customers_register:false,countries:[]}}});
    if(p.endsWith('/pos/customers'))return route.fulfill({json:{items:[],next:null}});
    if(p.endsWith('/anonymous-cash/configuration'))return route.fulfill({json:{schema_ready:true,configured:true,enabled:true}});
    if(p.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,branches:[{id:1,name:'City branch',can_write:true}]}});
    return route.fulfill({json:{items:[],rows:[],total:0,pageTotal:0,page:1,per_page:10,next:null,sections:[],metrics:{},series:[],employees:[],resources:[],specialists:[],canCreate:true,context:{canCreate:true},permissions:{create:true,view:true}}});
   });
   await page.route('**/*',route=>route.request().resourceType()==='document'?route.fulfill({contentType:'text/html',body:'<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/srm-mobile-workspace.tsx");</script>'}):route.fallback());
   await page.goto(server.resolvedUrls.local[0]+'srm/pos/terminal?qa-layout=1');
   await expect(page.getByRole('heading',{name:'Billing & POS',exact:true})).toBeVisible();
   await expect(page.getByRole('navigation',{name:'SRM mobile navigation',includeHidden:true})).toBeHidden();
   await expect(page.getByRole('button',{name:'Open navigation',exact:true})).toHaveCount(0);
   await expect(page.getByRole('button',{name:'Page actions',exact:true})).toHaveCount(0);
   await expect(page.locator('.action-bot-launcher')).toBeHidden();
   const grid=page.getByRole('region',{name:'Catalogue items',exact:true});await expect(grid.locator('article').first()).toBeVisible();
   for(let i=1;i<=3;i++){await page.getByRole('textbox',{name:'Search or scan items',exact:true}).fill(`Retail item ${i}`);await grid.getByRole('button',{name:`Add Retail item ${i} to cart`,exact:true}).click();}
   await page.getByRole('textbox',{name:'Search or scan items',exact:true}).fill('');
   const cart=page.getByRole('complementary',{name:'Current sale'});
   const details=cart.getByRole('region',{name:'Sale details'});
   await expect(cart.locator('.pos-phone-bill')).toContainText('3 items');
   await expect(grid).toBeInViewport();
   await expect(details).toBeInViewport();
   await expect(cart.getByRole('button',{name:/^Collect/})).toBeInViewport({ratio:0.95});
   const lastItem=details.getByText('Retail item 3',{exact:true});
   await lastItem.scrollIntoViewIfNeeded();
   await expect(lastItem).toBeInViewport();
   await expect(grid).toBeInViewport();
   const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight);
   expect(fits).toBe(true);
   await page.screenshot({path:path.resolve('../output',`pos-full-layout-mobile-${width}x${height}.png`),fullPage:true});
   registerOpen=false;await page.reload();await expect(page.getByRole('heading',{name:'Billing & POS',exact:true})).toBeVisible();await expect(page.locator('.pos-guidance')).toBeHidden();await page.getByRole('button',{name:'Open register',exact:true}).click();const session=page.getByRole('dialog',{name:'Register session',exact:true});await expect(session).toBeVisible();await session.getByLabel('Mobile POS opening cash',{exact:true}).fill('100');await session.getByRole('button',{name:'Open POS register',exact:true}).click();await expect(session).toBeHidden();expect(openedRegisters).toBe(1);await expect(page.locator('.pos-guidance')).toBeHidden();
   await page.goto(server.resolvedUrls.local[0]+'srm/customers?qa-navigation=1');await expect(page.getByRole('navigation',{name:'Primary Sales action',exact:true})).toBeVisible();await expect(page.locator('.module-menu').getByRole('link').first()).toHaveText(/POS/);await page.getByRole('searchbox',{name:'Search menu items',exact:true}).fill('customer');await expect(page.getByRole('navigation',{name:'Primary Sales action',exact:true}).getByRole('link',{name:'POS',exact:true})).toBeVisible();
   await expect(page.getByRole('navigation',{name:'SRM mobile navigation',exact:true}).getByRole('link').first()).toHaveText(/POS/);
   await page.getByRole('button',{name:'Add new record',exact:true}).click();const create=page.getByRole('dialog',{name:'Create something new',exact:true});await expect(create).toBeVisible();await expect(create.locator('.mobile-create-list button').first()).toContainText('POS');await create.press('Escape');
   await page.evaluate(()=>window.srmQaReadonly());await page.getByRole('button',{name:'Create',exact:true}).click();await expect(page.getByRole('menuitem').first()).toContainText('POS');await expect(page.getByRole('menuitem',{name:/Sales order/})).toHaveCount(0);await page.getByRole('menu').press('Escape');
   expect(errors).toEqual([]);console.log(`POS ${width}x${height}: full app shell fit, independent catalogue and cart scrolling, compact session setup, POS-first sidebar/dock/+ menu and read-only navigation passed`);await page.close();
  }
 }finally{await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exit(1);});
