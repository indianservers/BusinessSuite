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
    for(const [width,height] of [[320,568],[360,640],[390,844],[426,640],[430,932],[767,1024],[430,1280]]) {
      const page=await browser.newPage({viewport:{width,height},acceptDownloads:true});
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      const posts=[];let succeed=false;
      const cap={realm:'pack',user_id:77,company_id:1,branch_id:1,context_id:11,pack_key:'hospital',pack_version:1,context_revision:1,grant_revision:1,activation_revision:1};
      const specialists=[{eligibility_id:1,eligibility_revision:1,provider_resource_id:11,employee_id:21,employee_name:'Alex Staff',provider_name:'Alex',timezone:'UTC',work_categories:['Stylists']},{eligibility_id:2,eligibility_revision:1,provider_resource_id:12,employee_id:22,employee_name:'Sam Staff',provider_name:'Sam',timezone:'UTC',work_categories:['Consultants']}];
      const policy={id:4,revision:1,booking_required:true,default_duration_minutes:30,min_duration_minutes:5,max_duration_minutes:120,allow_duration_override:true,active:true,employee_categories:['Stylists','Consultants']};
      await page.route('**/api/v1/**',async route=>{
        const request=route.request(),url=new URL(request.url()),p=url.pathname;
        if(p.endsWith('/auth/me')||p.endsWith('/access/me')){const native=await page.evaluate(()=>window.nativeIdentity());return route.fulfill({json:p.endsWith('/auth/me')?native.identity:native.access});}
        if(p.endsWith('/industry/capabilities'))return route.fulfill({json:{checkout_create:true,checkout_collect:true,operational_scope:cap}});
        if(p.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,branches:[{id:1,name:'City branch',can_write:true}]}});
        if(p.endsWith('/pos/sessions/active'))return route.fulfill({json:{session:{id:81,status:'open',opening_cash:100,session_number:'POS-81',register_name:'Front desk'},expected_cash:100}});
        if(p.endsWith('/pos/catalog'))return route.fulfill({json:{items:[{id:1,item_name:'Retail item',sku:'SKU1',barcode:'12345',unit_code:'PCS',product_type:'product',sales_rate:100,gst_rate:0,current_quantity:5,track_inventory:true,checkout_supported:true,active:true},{id:9,item_name:'Consultation service',sku:'SVC9',product_type:'service',sales_rate:45,gst_rate:0,track_inventory:false,checkout_supported:true,active:true,booking_policy:{required:true}}],next:null,features:{appointments_schedule:true,customers_register:false,countries:[]}}});
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
      for(const name of ['Retail item','Consultation service'])await page.locator('.srm-pos-catalog article').filter({hasText:name}).locator('button[data-product-id]').first().click();
      await page.locator('.srm-pos-mobile-tabs button').last().click();
      if(!await page.locator('.pos-booking-trigger').isVisible())await page.getByRole('button',{name:'Next cart page',includeHidden:true}).click();
      await page.locator('.pos-booking-trigger').click();
      await page.locator('select[aria-label^="Specialist "]').selectOption('1');
      await page.locator('input[aria-label^="Booking date "]').fill(new Date(Date.now()+2*86400000).toISOString().slice(0,10));
      await page.getByRole('button',{name:/^10:00/}).click();
      await page.getByRole('checkbox',{name:/Treatment room/}).check();
      await page.getByRole('button',{name:'Use these booking details',exact:true}).click();
      await expect(page.getByRole('dialog',{name:'Service booking',exact:true})).toBeHidden();
      await expect(page.locator('.booking-summary-lines')).toContainText('Alex Staff');
      await expect(page.locator('.pos-booking-trigger:visible')).toContainText('Edit');
      const metrics=await page.evaluate(()=>{const p=document.querySelector('.pos-cart-items'),f=document.querySelector('.srm-pos-checkout');return {width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,scrollY:scrollY,panel:p.clientHeight,content:p.scrollHeight,bottom:f.getBoundingClientRect().bottom};});
      const footer=await page.locator('.srm-pos-checkout').boundingBox(),collect=await page.getByRole('button',{name:/^Collect /}).boundingBox();expect(Math.abs(footer.width-collect.width)).toBeLessThan(2);
      console.log(width,height,metrics);
      await page.screenshot({path:path.resolve('../output',`pos-mobile-reference-${width}x${height}.png`),fullPage:true});
      expect(metrics.height).toBeLessThanOrEqual(height);expect(metrics.scrollY).toBe(0);expect(metrics.width).toBeLessThanOrEqual(width);expect(metrics.bottom).toBeLessThanOrEqual(height+1);expect(metrics.content).toBeLessThanOrEqual(metrics.panel+2);
      if(await page.locator('.pos-cart-line:visible').count()===2)await expect(page.locator('.pos-phone-pagination')).toBeHidden();
      await page.getByRole('button',{name:'Add another appointment',exact:true}).click();
      await expect(page.locator('.pos-phone-pagination')).toBeVisible();
      await expect(page.getByRole('button',{name:'Previous cart page',includeHidden:true})).toBeEnabled();
      await page.getByRole('button',{name:'Previous cart page',includeHidden:true}).click();
      await page.getByRole('button',{name:'Next cart page',includeHidden:true}).click();
      await expect(page.getByRole('button',{name:/^Collect /})).toContainText('190');
      await page.screenshot({path:path.resolve('../output',`pos-mobile-reference-cart-pages-${width}x${height}.png`),fullPage:true});
      for(const [label,title] of [['Register setup','Register session'],['Bill tools','POS actions']]){await page.getByRole('button',{name:'Add new record',exact:true}).click();await page.getByRole('menuitem',{name:new RegExp(label)}).click();await expect(page.getByRole('dialog',{name:title,exact:true})).toBeVisible();await page.getByRole('button',{name:'Close '+title,exact:true}).click();}
      await page.getByRole('button',{name:/Discounts & Coupons/}).click();await page.getByLabel('Mobile bill discount').fill('5');await page.getByRole('button',{name:'Apply & close'}).click();
      await page.locator('.pos-phone-bill-customer').click();await expect(page.getByRole('dialog',{name:'Sale customer',exact:true})).toBeVisible();
      await page.getByRole('dialog',{name:'Sale customer',exact:true}).getByRole('textbox',{name:'Search customers',exact:true}).fill('9999');await page.getByRole('dialog',{name:'Sale customer',exact:true}).getByRole('combobox',{name:'Sale customer',exact:true}).click();await page.getByRole('option',{name:/Jane Customer/}).click();await page.getByRole('button',{name:'Done',exact:true}).click();
      // Remove the only line on the last page; the page index must clamp.
      await page.locator('.pos-cart-line:visible').last().getByRole('button',{name:'Remove Consultation service',exact:true}).click();
      await page.getByRole('button',{name:'Undo removal',exact:true}).click();
      await page.getByRole('button',{name:'Clear',exact:true}).click();
      await expect(page.getByRole('dialog',{name:'Clear this bill?',exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Keep bill',exact:true}).click();
      await expect(page.locator('.pos-phone-bill')).toContainText('3 items');
      while(await page.getByRole('button',{name:'Next cart page',includeHidden:true}).isEnabled())await page.getByRole('button',{name:'Next cart page',includeHidden:true}).click();
      await page.locator('.pos-cart-line:visible').last().getByRole('button',{name:'Remove Consultation service',exact:true}).click();
      await page.getByRole('button',{name:'Dismiss',exact:true}).click();
      await page.getByRole('button',{name:/^Collect /}).click();await expect(page.getByRole('dialog',{name:'Complete Payment',exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Close Complete Payment',exact:true}).click();
      expect(errors).toEqual([]);await page.close();
    }
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exit(1);});
