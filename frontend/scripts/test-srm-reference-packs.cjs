const path = require('node:path');
const fs = require('node:fs');
const {chromium, expect: base} = require('playwright/test');
const expect = base.configure({timeout:15000});

(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const {createServer}=await import('vite');
  const profiles=JSON.parse(fs.readFileSync(path.resolve('../backend/app/core/business_profiles.json'),'utf8')); 
  const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();const browser=await chromium.launch();
  try {
    for(const pack of ["general","retail","hospital","pharma","salon","automotive"]) {
      const width=1586;
      const page=await browser.newPage({viewport:{width,height:1000},acceptDownloads:true});
      const errors=[];page.on('pageerror',error=>errors.push(error.message));
      const posts=[];let succeed=false;
      const cap={realm:'pack',user_id:77,company_id:1,branch_id:1,context_id:11,pack_key:pack,pack_version:1,context_revision:1,grant_revision:1,activation_revision:1};
      const specialists=[{eligibility_id:1,eligibility_revision:1,provider_resource_id:11,employee_id:21,employee_name:'Alex Staff',provider_name:'Alex',timezone:'UTC',work_categories:['Stylists']},{eligibility_id:2,eligibility_revision:1,provider_resource_id:12,employee_id:22,employee_name:'Sam Staff',provider_name:'Sam',timezone:'UTC',work_categories:['Consultants']}];
      const policy={id:4,revision:1,booking_required:true,default_duration_minutes:30,min_duration_minutes:5,max_duration_minutes:120,allow_duration_override:true,active:true,employee_categories:['Stylists','Consultants']};
      await page.route('**/api/v1/**',async route=>{
        const request=route.request(),url=new URL(request.url()),p=url.pathname;
        if(p.endsWith('/auth/me')||p.endsWith('/access/me')){const native=await page.evaluate(()=>window.nativeIdentity());return route.fulfill({json:p.endsWith('/auth/me')?native.identity:native.access});}
        if(p.endsWith('/business-profile/effective'))return route.fulfill({json:{business_type:pack,terms:{...profiles.terms,...(profiles.profiles.find(profile=>profile.id===pack)?.terms||{})}}});
        if(p.endsWith('/industry/capabilities'))return route.fulfill({json:{manage:true,billing:true,projects_enabled:false,crm_enabled:false,appointment_actions:[],checkout_create:true,checkout_collect:true,operational_scope:cap}});
        if(/\/appointments\/\d+\/billing$/.test(p)) return route.fulfill({json:{currency:'INR',total:'100',paid:p.includes('/102/')?'50':'0',advance:'0',balance:p.includes('/102/')?'50':'100',invoice:null,receipts:[]}});
        if(p.endsWith('/industry/records')) {const resources=[{id:10,title:pack==='hospital'?'Dr. Arjun Rao':'Sam',status:'active',data:{resource_type:'provider',timezone:'UTC',employee_id:21}},{id:11,title:pack==='hospital'?'Dr. Meera Shah':'Anjali',status:'active',data:{resource_type:'provider',timezone:'UTC',employee_id:22}},{id:30,title:'Room 01',status:'active',data:{resource_type:'room',timezone:'UTC'}}];const day=new Date().toISOString().slice(0,10);return route.fulfill({json:{items:url.searchParams.get('kind')==='resource'?resources:[{id:101,kind:'appointment',title:'Priya Sharma',status:'booked',revision:1,customer_id:12,created_by:77,data:{starts_at:day+'T14:00:00Z',duration_minutes:45,customer_name:'Priya Sharma',service_name:pack==='hospital'?'General Consultation':pack==='retail'?'Alterations':pack==='automotive'?'Oil Change':'Hair Styling',resource_ids:[10,30]}},{id:102,kind:'appointment',title:'Neha Iyer',status:'in_service',revision:1,customer_id:13,created_by:77,data:{starts_at:day+'T11:00:00Z',duration_minutes:60,customer_name:'Neha Iyer',service_name:'Consultation',resource_ids:[11]}}]}});}
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
      await page.route('**/pos-uix-qa*',route=>route.fulfill({contentType:'text/html',body:'<script>window.__AI_HRMS_CONFIG__={apiBaseUrl:"/api/v1"};</script><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/srm-reference.tsx");</script>'}));
      await page.goto(server.resolvedUrls.local[0]+'pos-uix-qa?mode=pos&pack='+pack);
      await expect(page.getByRole('heading',{name:pack==='hospital'?'Billing & POS':'POS Terminal'})).toBeVisible();
      await page.locator('.srm-pos-catalog article').filter({hasText:'Retail item'}).locator('button[data-product-id]').first().click();
      await page.locator('.srm-pos-catalog article').filter({hasText:'Consultation service'}).locator('button[data-product-id]').first().click();
      await expect(page.locator('.pos-booking-trigger')).toBeVisible();
      await page.getByRole('button',{name:'Change sale customer',exact:true}).click();
      await page.getByLabel('Sale customer',{exact:true}).click();
      await page.getByRole('option',{name:/Jane Customer/}).click();
      const left=await page.locator('.srm-pos-catalog').boundingBox(),right=await page.locator('.srm-pos-cart').boundingBox();
      expect(Math.abs(left.width-right.width)).toBeLessThan(1);expect(Math.abs(left.y-right.y)).toBeLessThan(1);expect(Math.abs(left.height-right.height)).toBeLessThan(1);
      await expect(page.getByRole('region',{name:'Sale items, scroll for more'})).toBeVisible();
      await expect(page.locator('.pos-compact-cart-row')).toHaveCount(2);
      await expect(page.getByText('Manage favorites',{exact:true})).toHaveCount(0);
      await expect(page.locator('.pos-filter-menu>summary')).toBeVisible();
      await page.screenshot({path:path.resolve('../output',`ux25-${pack}-pos.png`),fullPage:true});
      await page.locator('.pos-booking-trigger').click();
      await expect(page.getByRole('dialog',{name:'Service booking'})).toBeVisible();
      await page.screenshot({path:path.resolve('../output',`ux25-${pack}-booking.png`),fullPage:true});
      await page.goto(server.resolvedUrls.local[0]+'pos-uix-qa?mode=pos&pack='+pack+'&surface=appointments');
      await expect(page.getByRole('region',{name:'Appointment timeline'})).toBeVisible();
      await expect(page.getByLabel('Timeline date',{exact:true})).toHaveCount(1);
      await expect(page.getByLabel('Appointment date',{exact:true})).toHaveCount(0);
      await expect(page.locator('.appointment-payment-status').first()).toBeVisible();
      await page.getByRole('button',{name:new RegExp('^New '+(profiles.profiles.find(profile=>profile.id===pack)?.terms?.appointment?.[0]||profiles.terms.appointment[0])+'$','i')}).click();
      await expect(page.getByRole('form',{name:'Create operation'})).toBeVisible();
      await page.screenshot({path:path.resolve('../output',`ux25-${pack}-appointments.png`),fullPage:true});
      await page.close();
    }
    console.log('PASS reference pack surfaces: general, retail, hospital, pharma, salon, automotive; equal pane dimensions and booking windows');
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exit(1)});
