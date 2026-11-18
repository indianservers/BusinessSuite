const path = require('node:path');
const fs = require('node:fs');
const {chromium, expect: base} = require('playwright/test');
const expect = base.configure({timeout:15000});

(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const {createServer}=await import('vite');
  const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();const browser=await chromium.launch();
  try {
    for(const [width,height] of [[320,568],[360,640],[390,844],[1280,720],[1920,1080]]) {
      const page=await browser.newPage({viewport:{width,height},acceptDownloads:true});
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      const posts=[];let succeed=false;
      const cap={realm:'pack',user_id:77,company_id:1,branch_id:1,context_id:11,pack_key:'hospital',pack_version:1,context_revision:1,grant_revision:1,activation_revision:1};
      const specialists=[{eligibility_id:1,eligibility_revision:1,provider_resource_id:11,employee_id:21,employee_name:'Alex Staff',provider_name:'Alex',timezone:'UTC',work_categories:['Stylists']},{eligibility_id:2,eligibility_revision:1,provider_resource_id:12,employee_id:22,employee_name:'Sam Staff',provider_name:'Sam',timezone:'UTC',work_categories:['Consultants']}];
      const policy={id:4,revision:1,booking_required:width!==320,default_duration_minutes:30,min_duration_minutes:5,max_duration_minutes:120,allow_duration_override:true,active:true,employee_categories:['Stylists','Consultants']};
      await page.route('**/api/v1/**',async route=>{
        const request=route.request(),url=new URL(request.url()),p=url.pathname;
        if(p.endsWith('/auth/me')||p.endsWith('/access/me')){const native=await page.evaluate(()=>window.nativeIdentity());return route.fulfill({json:p.endsWith('/auth/me')?native.identity:native.access});}
        if(p.endsWith('/industry/capabilities'))return route.fulfill({json:{checkout_create:true,checkout_collect:true,operational_scope:cap}});
        if(p.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,branches:[{id:1,name:'City branch',can_write:true}]}});
        if(p.endsWith('/pos/sessions/active'))return route.fulfill({json:{session:{id:81,status:'open',opening_cash:100,session_number:'POS-81',register_name:'Front desk'},expected_cash:100}});
        if(p.endsWith('/pos/catalog'))return route.fulfill({json:{items:[{id:1,item_name:'Retail item',sku:'SKU1',barcode:'12345',unit_code:'PCS',product_type:'product',sales_rate:100,gst_rate:0,current_quantity:5,track_inventory:true,checkout_supported:true,active:true},{id:9,item_name:'Consultation service',sku:'SVC9',product_type:'service',sales_rate:45,gst_rate:0,track_inventory:false,checkout_supported:true,active:true,booking_policy:{required:policy.booking_required}}],next:null,features:{appointments_schedule:true,customers_register:false,countries:[]}}});
        if(p.endsWith('/pos/customers'))return route.fulfill({json:{items:[{id:12,name:'Jane Customer',phone:'9999999999'}],next:null}});
        if(p.endsWith('/options/availability')){const day=url.searchParams.get('day');return route.fulfill({json:{timezone:'UTC',slots:[{starts_at:`${day}T10:00:00Z`,label:'10:00'}],selection_available:url.searchParams.has('starts_at')?true:null,resources:[{id:30,available:true}]}});}
        if(p.endsWith('/service-checkout/options'))return route.fulfill({json:{policy,specialists,resources:[{id:30,name:'Treatment room',resource_type:'room'}],has_more:false}});
        if(p.endsWith('/employees/work-category-options'))return route.fulfill({json:{items:['Stylists','Consultants']}});
        if(p.endsWith('/anonymous-cash/configuration'))return route.fulfill({json:{schema_ready:true,configured:true,enabled:true}});
        if(p.endsWith('/service-checkout/501'))return route.fulfill({json:{id:501,state:'committed',revision:1,sales_order_id:601,invoice:{id:701,number:'POS-UIX-001',status:'issued',currency:'INR',total:'145.00',paid:'145.00',balance:'0.00'},lines:[],receipts:[{id:801,number:'RCPT-UIX-001',amount:'145.00',unallocated:'0.00',method:'cash',status:'allocated'}]}});
        if(p.endsWith('/service-checkout')&&request.method()==='POST'){
          const body=request.postDataJSON();posts.push(body);
          if(!succeed)return route.fulfill({status:503,json:{detail:'Confirmation interrupted'}});
          return route.fulfill({json:{id:501,state:'committed',sales_order_id:601,invoice:{id:701,number:'POS-UIX-001',status:'issued',total:body.expected_total,paid:body.expected_total,balance:'0.00'},receipts:[{id:801,number:'RCPT-UIX-001'}]}});
        }
        return route.fulfill({json:{items:[],total:0,next:null}});
      });
      await page.route('**/pos-uix-qa*',route=>route.fulfill({contentType:'text/html',body:'<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/security-scope.tsx");</script>'}));
      await page.goto(server.resolvedUrls.local[0]+'pos-uix-qa?mode=pos');

      await expect(page.getByRole('heading',{name:'Billing & POS'})).toBeVisible();
      await page.locator('.srm-pos-catalog article').filter({hasText:'Consultation service'}).locator('button[data-product-id]').first().click();
      if(width<768)await page.locator('.srm-pos-mobile-tabs button').last().click();
      const inline=page.locator('.pos-compact-booking[data-presentation=cart]');await expect(inline).toBeVisible();await expect(page.locator('.pos-booking-window')).toHaveCount(0);
      const optional=inline.getByRole('checkbox',{name:'Schedule this service',exact:true});if(width===320)await optional.check();
      async function assertCartFits(){const m=await inline.evaluate(node=>({line:node.closest('.pos-cart-line').getBoundingClientRect().height,scroll:node.closest('.pos-cart-items').scrollHeight,height:node.closest('.pos-cart-items').clientHeight}));expect(m.line).toBeLessThanOrEqual(m.height);expect(m.scroll).toBeLessThanOrEqual(m.height+1);}
      for(const tab of ['Time','Resources','Find staff','Employee']){await inline.getByRole('button',{name:tab,exact:true}).click();await page.screenshot({path:path.resolve('../output',`pos-check-${width}-${tab.replaceAll(' ','-')}.png`)});await assertCartFits();}
      const inlineMetrics=await inline.evaluate(node=>({width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height,cartHeight:node.closest('.pos-cart-items').clientHeight,lineHeight:node.closest('.pos-cart-line').getBoundingClientRect().height,cardScroll:node.closest('.pos-cart-items').scrollHeight,cardHeight:node.closest('.pos-cart-items').clientHeight}));console.log('inline',width,inlineMetrics);expect(inlineMetrics.width).toBeGreaterThan(250);expect(inlineMetrics.height).toBeLessThanOrEqual(inlineMetrics.cartHeight);expect(inlineMetrics.lineHeight).toBeLessThanOrEqual(inlineMetrics.cartHeight);expect(inlineMetrics.cardScroll).toBeLessThanOrEqual(inlineMetrics.cardHeight+1);await page.screenshot({path:path.resolve('../output',`pos-inline-booking-edit-${width}.png`)});await inline.getByRole('button',{name:'Use these booking details',exact:true}).click();await expect(page.locator('.booking-summary-lines')).toContainText('Alex Staff');
      await page.screenshot({path:path.resolve('../output',`pos-inline-booking-initial-${width}.png`)});
      async function settings(){if(width<768){await page.locator('.pos-phone-header-tools').getByRole('button',{name:'Add new record',exact:true}).click();await page.getByRole('menuitem',{name:/Bill tools/}).click();await page.getByRole('button',{name:'Register settings',exact:true}).click();}else{const session=page.getByRole('button',{name:/^Session & actions/});if(await session.isVisible()&&await session.getAttribute('aria-expanded')==='false')await session.click();const direct=page.getByRole('button',{name:'Settings',exact:true});if(!await direct.isVisible())await page.getByRole('button',{name:'More actions',exact:true}).first().click();await direct.click();}await expect(page.getByLabel('Service booking layout')).toBeVisible();}
      await settings();await expect(page.getByLabel('Service booking layout')).toHaveValue('cart');await page.getByLabel('Service booking layout').selectOption('dialog');await page.getByRole('button',{name:'Close POS Settings & Layout',exact:true}).click();
      await expect(page.locator('.pos-booking-trigger')).toBeVisible();await page.reload();if(width<768)await page.locator('.srm-pos-mobile-tabs button').last().click();await expect(page.locator('.pos-booking-trigger')).toBeVisible();
      await settings();await expect(page.getByLabel('Service booking layout')).toHaveValue('dialog');await page.getByRole('button',{name:'Close POS Settings & Layout',exact:true}).click();
      await page.locator('.pos-booking-trigger').click();const dialog=page.getByRole('dialog',{name:'Service booking',exact:true});await expect(dialog).toBeVisible();await expect(dialog.getByRole('button',{name:'Use these booking details',exact:true})).toBeEnabled();
      const metrics=await dialog.evaluate(node=>({scroll:node.scrollHeight,height:node.clientHeight,top:node.getBoundingClientRect().top,bottom:node.getBoundingClientRect().bottom}));expect(metrics.scroll).toBeLessThanOrEqual(metrics.height+1);expect(metrics.top).toBeGreaterThanOrEqual(0);expect(metrics.bottom).toBeLessThanOrEqual(height);
      await page.screenshot({path:path.resolve('../output',`pos-booking-settings-${width}.png`)});await page.getByRole('button',{name:'Close service booking',exact:true}).click();
      await settings();await page.getByLabel('Service booking layout').selectOption('cart');await page.getByRole('button',{name:'Close POS Settings & Layout',exact:true}).click();await expect(page.locator('.pos-inline-booking-edit')).toBeVisible();await expect(page.locator('.booking-summary-lines')).toContainText('Alex Staff');
      await page.screenshot({path:path.resolve('../output',`pos-inline-booking-${width}.png`)});expect(posts).toEqual([]);expect(errors).toEqual([]);await page.close();
    }
    console.log('PASS real POS integration: inline scheduling by default, settings persistence after reload, retained cart booking when switching layouts, compact dialog without vertical overflow, no checkout writes at five mobile/desktop viewports');
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
