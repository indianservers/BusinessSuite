const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {chromium,expect}=require('playwright/test');
(async()=>{
 const root=path.resolve(__dirname,'..'),fixture=path.join(root,'.tmp-audit-sales-fixture.tsx');
 fs.writeFileSync(fixture,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import './src/index.css';import{CommercialCreateCard}from './src/apps/srm/pages/SRMWorkspacePage';import{useAuthStore}from './src/store/authStore';useAuthStore.setState({isHydrated:true,isAuthenticated:true,user:{id:1,email:'qa@example.test',role:'admin',is_superuser:true}});createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/srm/sales-orders']}><CommercialCreateCard kind="salesOrders" onSaved={()=>{window.saved=true}}/></MemoryRouter></QueryClientProvider>);`);
 const {createServer}=await import('vite');const server=await createServer({root,server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();let page;
 try{
 page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],writes=[];let release,fail=true;
 const customer={id:73,name:'Audit customer',roles:['Customer'],entityKind:'Company'};
 const item=(id,kind,name,price,tax)=>({id,kind,name,price,tax,code:'QA-'+id,currency:'INR',pricing_options:[],images:[],custom_fields:{},version:1,status:'Active',unit:'Nos',workspace_id:null});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.pathname.endsWith('/master-data/companies'))return route.fulfill({json:{items:[customer],total:1,canCreate:false}});
  if(url.pathname.endsWith('/master-data/companies/73'))return route.fulfill({json:customer});
  if(url.pathname.endsWith('/catalog/items'))return route.fulfill({json:{items:[item(4,'product','Audit product',250,18),item(5,'service','Audit service',100,5)],pages:1,total:2,permissions:{}}});
  if(url.pathname.endsWith('/srm/sales-orders')&&req.method()==='POST'){
   writes.push(req.postDataJSON());await new Promise(resolve=>{release=resolve});
   return route.fulfill({status:fail?422:201,json:fail?{detail:'Order cannot be saved right now'}:{...writes.at(-1),id:42}});
  }
  return route.fulfill({json:{items:[],fields:[]}});
 });
 await page.route('**/qa-audit-sales',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module" src="/.tmp-audit-sales-fixture.tsx"></script>'}));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/qa-audit-sales');
 await page.getByRole('button',{name:'Create Sales Order',exact:true}).click();
 const dialog=page.getByRole('dialog'),form=dialog.locator('form');
 const reveal=async locator=>{if(await locator.isVisible())return;for(const tab of await dialog.getByRole('tab').all()){await tab.click();if(await locator.isVisible())return;}};
 const title=form.getByLabel('Title',{exact:true});await reveal(title);await title.fill('QA_TEST_2026_SO_001');
 await dialog.getByRole('button',{name:'Create Sales Order',exact:true}).click();
 await expect(dialog.getByText('Choose a customer before creating the sales order.',{exact:true})).toBeVisible();assert.equal(writes.length,0);
 const search=form.getByRole('combobox',{name:'Search shared customer'});await reveal(search);await search.fill('Audit');
 await dialog.getByRole('option').filter({hasText:'Audit customer'}).click();
 const product=dialog.getByRole('button').filter({hasText:'Audit product'}).first();await reveal(product);await product.click();
 await dialog.getByRole('button').filter({hasText:'Audit service'}).first().click();
 const qty=form.getByLabel('Quantity for Audit product',{exact:true});await qty.fill('0');
 await dialog.getByRole('button',{name:'Create Sales Order',exact:true}).click();assert.equal(writes.length,0);
 await qty.fill('2');await form.getByLabel('Discount for Audit product',{exact:true}).fill('10');
 const unitPrice=form.getByLabel('Price for Audit product',{exact:true});await unitPrice.fill('');await unitPrice.pressSequentially('-250');await expect(unitPrice).toHaveValue('-250');
 await dialog.getByRole('button',{name:'Create Sales Order',exact:true}).click();assert.equal(writes.length,0);await unitPrice.fill('250');
 await expect(dialog.getByText(/Order total \(including tax\):/)).toContainText('636.00');
 await form.getByLabel('Tax for Audit service',{exact:true}).fill('10');await expect(dialog.getByText(/Order total \(including tax\):/)).toContainText('641.00');
 await form.getByLabel('Tax for Audit service',{exact:true}).fill('5');
 for(const width of [390,1280]){await page.setViewportSize({width,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);}
 await dialog.getByRole('button',{name:'Create Sales Order',exact:true}).click();await expect.poll(()=>writes.length).toBe(1);
 await expect(dialog.getByRole('button',{name:'Saving...',exact:true})).toBeVisible();await expect(dialog).toBeVisible();
 assert.equal(await page.evaluate(()=>window.saved),undefined);release();
 await expect(dialog.getByText('Order cannot be saved right now',{exact:true})).toBeVisible();
 assert.equal((await title.inputValue()),'QA_TEST_2026_SO_001');
 fail=false;await dialog.getByRole('button',{name:'Create Sales Order',exact:true}).click();await expect.poll(()=>writes.length).toBe(2);release();
 await expect.poll(()=>page.evaluate(()=>window.saved)).toBe(true);
 assert.equal(writes[1].customer_id,73);assert.equal(writes[1].title,'QA_TEST_2026_SO_001');assert.equal(writes[1].lines.length,2);assert.equal(writes[1].total_amount,636);
 assert.deepEqual(errors,[]);console.log('PASS sales-order UI: customer/item lookups, multiline totals, quantity validation, visible pending modal, failed save/retry, title preservation');
 }catch(e){if(page)console.error((await page.locator('body').innerText()).slice(-5000));throw e;}finally{await browser.close();await server.close();fs.unlinkSync(fixture);}
})().catch(e=>{console.error(e);process.exitCode=1});


