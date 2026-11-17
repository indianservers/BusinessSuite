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
    for(const width of [1440,390]) {
      const page=await browser.newPage({viewport:{width,height:1000},acceptDownloads:true});
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
      await expect(page.getByText('City branch / Front desk',{exact:false})).toBeVisible();
      await expect(page.getByRole('button',{name:'Print Last',exact:true,includeHidden:true})).toBeDisabled();
      await expect(page.getByRole('button',{name:/^Collect /})).toHaveCount(1);
      await page.getByRole('button',{name:'Favorite Retail item',exact:true}).click();
      await page.locator('.pos-filter-menu>summary').click();
      await page.getByRole('button',{name:'Favorites (1)',exact:true}).click();
      await page.locator('.pos-filter-menu>summary').click();
      await expect(page.locator('.srm-pos-catalog article')).toHaveCount(1);
      await page.getByRole('button',{name:'All (2)',exact:true}).click();
      const search=page.getByRole('textbox',{name:'Search or scan items'});
      await search.fill('12345');await search.press('Enter');
      await expect(page.getByRole('button',{name:/^Collect /})).toContainText('100');
      if(width<1280)await page.getByRole('button',{name:/^Cart \(/}).click();
      await page.getByRole('button',{name:'Remove Retail item',exact:true}).click();
      await page.getByRole('button',{name:'Undo removal',exact:true}).click();
      await page.getByRole('button',{name:'Clear',exact:true}).click();
      await expect(page.getByRole('dialog',{name:'Clear this bill?'})).toBeVisible();
      await page.getByRole('button',{name:'Clear bill',exact:true}).click();
      await page.getByRole('button',{name:'Undo removal',exact:true}).click();
      if(width<1280)await page.getByRole('button',{name:'Products',exact:true}).click();
      await page.locator('.srm-pos-catalog article').filter({hasText:'Consultation service'}).locator('button[data-product-id]').first().click();
      if(width<1280)await page.getByRole('button',{name:/^Cart \(/}).click();
      await page.getByRole('button',{name:/^Collect /}).click();
      await expect(page.getByRole('region',{name:'Checkout readiness'})).toContainText('appointment');
      await page.locator('.pos-booking-trigger').click();
      await page.getByText('Filter eligible staff',{exact:true}).click();
      await page.getByRole('checkbox',{name:'Stylists',exact:true}).check();
      await expect(page.locator('select[aria-label^="Specialist "] option').filter({hasText:'Sam Staff'})).toHaveCount(0);
      await page.locator('select[aria-label^="Specialist "]').selectOption('1');
      const day=new Date(Date.now()+2*86400000).toISOString().slice(0,10);
      await page.locator('input[aria-label^="Booking date "]').fill(day);
      await page.getByRole('button',{name:/^10:00/}).click();
      await page.getByRole('checkbox',{name:/Treatment room/}).check();
      await page.getByRole('button',{name:'Use these booking details',exact:true}).click();
      await expect(page.locator('.booking-summary-lines')).toContainText('Alex Staff');
      await expect(page.locator('.booking-summary-lines')).toContainText('Treatment room');
      await expect(page.locator('.pos-booking-trigger')).toBeFocused();
      await page.getByRole('button',{name:'Add another appointment',exact:true}).click();
      const serviceRows=page.locator('.pos-cart-line').filter({hasText:'Consultation service'});
      await expect(serviceRows).toHaveCount(2);
      await serviceRows.last().getByRole('button',{name:'Remove Consultation service',exact:true}).click();
      await page.getByRole('button',{name:'Dismiss',exact:true}).click();
      if(width<1280)await page.getByRole('button',{name:/^Cart \(/}).click();await page.getByRole('button',{name:'Change sale customer',exact:true}).click();
      await page.getByRole('textbox',{name:'Search customers',exact:true}).fill('9999');
      await page.getByLabel('Sale customer',{exact:true}).click();
      await page.getByRole('option',{name:/Jane Customer/}).click();
      await expect(page.getByRole('button',{name:'Change sale customer',exact:true})).toBeFocused();
      if(width>=1280){const left=await page.locator('.srm-pos-catalog').boundingBox(),right=await page.locator('.srm-pos-cart').boundingBox();expect(Math.abs(left.width-right.width)).toBeLessThan(1);expect(Math.abs(left.y-right.y)).toBeLessThan(1);expect(Math.abs(left.height-right.height)).toBeLessThan(1);}
      if(width>=1280){
        for(let i=0;i<5;i++)await page.getByRole('button',{name:'Add another appointment',exact:true}).first().click();
        const scroll=page.getByRole('region',{name:'Sale items, scroll for more'});
        await expect.poll(()=>scroll.evaluate(el=>el.scrollHeight>el.clientHeight+2)).toBe(true);
        await expect(page.getByText('Scroll for more sale items ↓',{exact:true})).toBeVisible();
        await scroll.focus();await page.keyboard.press('End');
        await expect.poll(()=>scroll.evaluate(el=>el.scrollTop+el.clientHeight>=el.scrollHeight-3)).toBe(true);
        const last=await page.locator('.pos-cart-line').last().boundingBox(),box=await scroll.boundingBox();expect(last.y+last.height).toBeLessThanOrEqual(box.y+box.height+2);
        for(let i=0;i<5;i++)await page.locator('.pos-cart-line').last().getByRole('button',{name:'Remove Consultation service',exact:true}).click();
        await scroll.evaluate(el=>el.scrollTop=0);
        await expect.poll(async()=>{const row=await page.locator('.pos-cart-line').last().boundingBox(),box=await scroll.boundingBox();return row.y+row.height<=box.y+box.height+2;}).toBe(true).catch(async error=>{console.error('CART METRICS',await scroll.evaluate(el=>({client:el.clientHeight,height:el.scrollHeight,top:el.scrollTop,rows:[...el.querySelectorAll('.pos-cart-line')].map(r=>r.getBoundingClientRect().height),cart:getComputedStyle(el.parentElement).gridTemplateRows,main:el.closest('.srm-pos').style.cssText})));await page.screenshot({path:path.resolve('../output','ux25-cart-debug.png'),fullPage:true});throw error;});
      }else{
        await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
        const bounds=await page.locator('.pos-bill-summary').boundingBox(),footer=await page.locator('.srm-pos-checkout').boundingBox();
        expect(bounds.y+bounds.height).toBeLessThanOrEqual(footer.y+2);
        const fixed=await page.locator('.srm-pos-checkout').evaluate(el=>getComputedStyle(el).position==='fixed');if(fixed){const reserved=await page.locator('.srm-pos').evaluate(el=>parseFloat(getComputedStyle(el).paddingBottom));expect(reserved).toBeGreaterThanOrEqual(footer.height);}else expect(footer.y+footer.height).toBeLessThanOrEqual(1002);
      }
      await page.screenshot({path:path.resolve('../output',`ux25-filled-${width}.png`),fullPage:true});
      await page.getByRole('button',{name:/^Collect /}).click();
      const payment=page.getByRole('dialog',{name:'Complete Payment'});
      await expect(payment).toBeVisible();
      await payment.getByRole('button',{name:'Split',exact:true}).click();
      await page.getByLabel('Payment amount',{exact:true}).fill('100');
      await payment.getByRole('button',{name:'Add payment mode',exact:true}).click();
      await payment.getByRole('combobox',{name:'Payment method',exact:true}).last().click();
      await page.getByRole('option',{name:'Card',exact:true}).click();
      await page.getByLabel('Payment amount',{exact:true}).last().fill('45');
      await page.screenshot({path:path.resolve('../output',`srm-reference-payment-${width}.png`),fullPage:true});
      await payment.getByRole('button',{name:'Complete Sale',exact:true}).click();
      await expect(page.getByRole('region',{name:'Unresolved POS checkout'})).toBeVisible();
      await expect.poll(()=>posts.length).toBe(1);
      expect(posts[0].lines.find(line=>line.booking).booking.employee_id).toBe(21);
      expect(posts[0].lines.find(line=>line.booking).booking.additional_resource_ids).toEqual([30]);
      succeed=true;
      await page.getByRole('button',{name:'Retry same checkout',exact:true}).click();
      await expect(page.getByRole('button',{name:'Download receipt',exact:true})).toBeVisible();
      await expect(page.getByRole('region',{name:'Confirmed sale summary'})).toContainText('RCPT-UIX-001');
      await expect(page.getByRole('region',{name:'Confirmed sale summary'})).toContainText('Remaining balance');
      expect(posts).toHaveLength(2);expect(posts[1]).toEqual(posts[0]);
      const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download receipt',exact:true}).click()]).catch(async error=>{console.error('Receipt diagnostics:',errors,await page.locator('body').innerText());throw error;});
      expect(download.suggestedFilename()).toBe('POS-UIX-001-receipt.txt');
      await page.evaluate(()=>{window.print=()=>{window.printed=true;};});
      await page.getByRole('button',{name:'Print Receipt',exact:true}).click();
      await expect.poll(()=>page.evaluate(()=>window.printed)).toBe(true);
      await page.emulateMedia({media:'print'});await expect(page.getByRole('article',{name:'Confirmed receipt'})).toBeVisible();
      await expect(page.getByRole('article',{name:'Confirmed receipt'})).toContainText('POS-UIX-001');
      await page.emulateMedia({media:'screen'});
      await page.getByRole('button',{name:'New Sale',exact:true}).click();
      if(width<1280)await page.getByRole('button',{name:/^Cart \(/}).click();
      await expect(page.getByText('Ready for first scan',{exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:'Undo removal',exact:true})).toHaveCount(0);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1)).toBe(true);
      expect(errors).toEqual([]);
      await page.screenshot({path:path.resolve('../output',`srm-reference-pos-${width}.png`),fullPage:true});
      await page.close();
    }
    console.log('PASS full POS UX at desktop/mobile: favorites, scanner, undo/clear, HRMS categories, slots/resources, duplicate booking, readiness, split payment, exact recovery, download/print and new sale');
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
