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
        if(p.endsWith('/pos/catalog')){
          const items=Array.from({length:27},(_,index)=>({id:200+index,item_name:index===26?'Zero stock product':index===25?'Very long product name with multiple words and a large package size':`Product ${String(index+1).padStart(2,'0')}`,sku:`MOB${index}`,barcode:`9000${index}`,category_name:index%2?'Wellness':'Retail',product_type:index%5===0?'service':'product',sales_rate:20+index,gst_rate:0,current_quantity:index===26?0:8,track_inventory:index%5!==0,checkout_supported:true,active:true}));
          const offset=Number(url.searchParams.get('after')||0);return route.fulfill({json:{items:items.slice(offset,offset+10),next:offset+10<items.length?offset+10:null,features:{appointments_schedule:true,customers_register:false,countries:[]}}});
        }
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
      const grid=page.getByRole('region',{name:'Paginated products',exact:true});
      await expect(grid.locator('article').first()).toBeVisible();
      const fit=async()=>{
        const metrics=await page.evaluate(()=>{const panel=document.querySelector('.pos-mobile-catalogue'),grid=document.querySelector('.pos-mobile-products-grid'),footer=document.querySelector('.srm-pos-checkout');const r=grid.getBoundingClientRect();return {width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,panelHeight:panel.clientHeight,panelContent:panel.scrollHeight,gridHeight:grid.clientHeight,gridContent:grid.scrollHeight,bottom:footer.getBoundingClientRect().bottom,rows:[...grid.querySelectorAll('article')].map(el=>({top:el.getBoundingClientRect().top,bottom:el.getBoundingClientRect().bottom,scroll:el.scrollHeight,height:el.clientHeight})),gridBottom:r.bottom};});
        expect(metrics.width).toBeLessThanOrEqual(width);expect(metrics.height).toBeLessThanOrEqual(height);expect(metrics.bottom).toBeLessThanOrEqual(height+1);expect(metrics.panelContent).toBeLessThanOrEqual(metrics.panelHeight+2);expect(metrics.gridContent).toBeLessThanOrEqual(metrics.gridHeight+2);for(const row of metrics.rows){expect(row.bottom).toBeLessThanOrEqual(metrics.gridBottom+1);expect(row.scroll).toBeLessThanOrEqual(row.height+2);}
      };
      await fit();await page.screenshot({path:path.resolve('../output',`pos-mobile-products-${width}x${height}.png`),fullPage:true});
      const firstName=await grid.locator('article strong').first().textContent();
      await page.getByRole('button',{name:'Next product page',exact:true}).click();
      await expect(grid.locator('article strong').first()).not.toHaveText(firstName);
      await expect(page.getByRole('button',{name:'Previous product page',exact:true})).toBeEnabled();
      const card=grid.locator('article').first();await card.getByRole('button',{name:/to cart$/}).click();
      await expect(page.locator('.pos-cart-count')).toHaveText('1');await expect(card.getByRole('button',{name:/to cart$/})).toContainText('1');
      const favorite=card.getByRole('button',{name:/^Favorite /});await favorite.click();await expect(favorite).toHaveAttribute('aria-pressed','true');
      await page.screenshot({path:path.resolve('../output',`pos-mobile-products-page2-${width}x${height}.png`),fullPage:true});
      const search=page.getByRole('textbox',{name:'Search or scan items',exact:true});
      await search.fill('Very long product');await expect(grid.locator('article')).toHaveCount(1);await fit();await expect(page.getByRole('navigation',{name:'Product pages'})).toBeHidden();
      await search.fill('Zero stock product');await expect(grid.locator('article')).toHaveCount(1);await expect(grid.getByRole('button',{name:/to cart$/})).toBeDisabled();
      await search.fill('missing item xyz');await expect(page.getByText('No matching items',{exact:true})).toBeVisible();await fit();
      await page.getByRole('button',{name:'Clear search & filters',exact:true}).click();await expect(grid.locator('article').first()).toBeVisible();
      await page.getByRole('button',{name:'Product filters',exact:true}).click();const filters=page.getByRole('dialog',{name:'Product filters',exact:true});await expect(filters).toBeVisible();
      await filters.getByLabel('Product category',{exact:true}).selectOption('Wellness');await filters.getByLabel('Sort catalogue',{exact:true}).selectOption('price');await filters.getByRole('button',{name:/^Show /}).click();
      await expect(page.locator('.pos-mobile-catalogue-caption')).toContainText('Wellness');await expect(page.getByRole('button',{name:'Previous product page',exact:true,includeHidden:true})).toBeDisabled();await fit();
      await page.getByRole('button',{name:'Product filters',exact:true}).click();await filters.getByRole('button',{name:'Reset filters',exact:true}).click();await filters.getByRole('button',{name:/^Show /}).click();
      await page.getByRole('navigation',{name:'Catalogue filters'}).getByRole('button',{name:/^Services /}).click();await expect(grid.locator('article').first()).toHaveClass(/is-service/);await fit();
      await page.locator('.srm-pos-mobile-tabs button').last().click();await expect(page.getByRole('region',{name:'Sale items, paginated'})).toBeVisible();await expect(page.locator('.pos-cart-count')).toHaveText('1');
      await page.locator('.srm-pos-mobile-tabs button').first().click();await expect(grid).toBeVisible();await fit();expect(errors).toEqual([]);console.log(`Products ${width}x${height}: fit, pagination, search, filters and cart passed`);await page.close();
    }
  } finally {await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exit(1);});
