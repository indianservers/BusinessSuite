const {chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
let origin=process.env.HUB_ORIGIN;
(async()=>{
 process.chdir(require("node:path").resolve(__dirname,".."));
 let server;
 if(!origin){const {createServer}=await import('vite');server=await createServer({root:require('node:path').resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();origin=server.resolvedUrls.local[0].replace(/\/$/,'');}
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const built=process.env.HUB_BUILT==='1';
  if(built)await page.addInitScript(()=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{user:{id:1,email:'qa@example.com',role:'admin',is_superuser:true},accessToken:'local-browser-test',isAuthenticated:true},version:0}));});
  const errors=[],writes=[];let backfills=0;
  page.on('pageerror',e=>{errors.push(e.message);console.error('Browser runtime:',e.message);});
  page.on('console',message=>{if(message.type()==='error')console.error('Browser console:',message.text());});
  let rows=[{id:1,name:'Hub customer',email:'hub@example.com',phone:'9876543210',phoneCountryCode:'+91',status:'Active',tags:['Customer','Vendor','Lead','Prospect'],roles:['Customer','Vendor'],version:'1'}];
  await page.route('**/api/v1/**',async route=>{
   const request=route.request(),path=new URL(request.url()).pathname,method=request.method();let data={items:[],total:0};
   if(method!=='GET'){const body=request.postDataJSON();writes.push({path,body});
    if(path.endsWith('/backfill')){backfills++;data={linked:0,hasMore:false};}
    else if(path==='/api/v1/crm/contact-directory'){rows.push({...body,id:2,version:'1',tags:body.roles||[],status:'Active'});data=rows.at(-1);}
    else if(method==='PATCH'){rows=rows.map(row=>row.id===1?{...row,...body,version:'2'}:row);data=rows[0];}
    else if(path.endsWith('/bulk')){rows=rows.filter(row=>!body.ids.includes(row.id));data={updated:1};}
    else data={status:'queued',id:1};
   }else if(path.endsWith('/business-os/modules'))data={enabled_modules:['hrms','crm','project_management','srm','fam','ai','communication','power_apps']};
   else if(path.endsWith('/defaults/effective'))data={companyId:1,branchId:1,values:{},modules:{}};
   else if(path.endsWith('/access/setup'))data={companyId:1,ready:true,items:[],moduleItems:[],recommendations:[]};
   else if(path.endsWith('/branches/context'))data={company_id:1,selected:1,branches:[{id:1,name:'QA branch',code:'QA',can_write:true}],manage_access:true};
   else if(path==='/api/v1/crm/contact-directory')data={items:rows,total:rows.length,stats:{total:rows.length},canManage:true,canConvert:true,canExport:true,canPermanentlyDelete:true,classifications:['Lead','Prospect','Customer','Vendor']};
   else if(path==='/api/v1/crm/contact-directory/1')data={...rows[0],leads:[],related:{}};
   else if(path.includes('/master-data/'))data={items:[],total:0,customFields:[],version:'1'};
   else if(path.includes('/availability'))data={scope:'company',branchIds:[]};
   await route.fulfill({json:data});
  });
  if(!built)await page.route('**/*',route=>route.request().isNavigationRequest()?route.fulfill({contentType:'text/html',body:`<html><body><div id="root"></div><script type="module">import R from '/@react-refresh'; R.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>(type)=>type; window.__vite_plugin_react_preamble_installed__=true; await import('/scripts/setup-new-harness.tsx');</script></body></html>`}):route.fallback());
  await page.goto(origin+'/company-admin');await expect(page.getByRole('heading',{name:'Company Admin',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:/Insights · Analytics/})).toHaveAttribute('href','/analytics');await expect(page.getByRole('link',{name:/^Settings Company/})).toHaveAttribute('href','/settings');
  await page.goto(origin+'/crm/records');await expect(page.getByRole('heading',{name:'Relationship Hub'})).toBeVisible();await expect.poll(()=>backfills).toBe(1);
  if(built){
   const category=page.locator('.module-menu-category').filter({has:page.locator('.module-menu-category-name',{hasText:'Customers & leads'})});
   await expect(category.getByRole('link',{name:'Potential Clients',exact:true})).toBeVisible();
   await expect(page.locator('.module-menu-category').filter({has:page.locator('.module-menu-category-name',{hasText:/^Dashboard$/})}).getByRole('link',{name:'Potential Clients',exact:true})).toHaveCount(0);
   require('node:fs').mkdirSync('../docs/qa/relationship-hub',{recursive:true});
   await page.screenshot({path:'../docs/qa/relationship-hub/relationship-hub-5191.png',fullPage:false});
  }
  await expect(page.getByRole('button',{name:'Potential customers',exact:true})).toBeVisible();
  for(const action of ['View','Edit','Email','WhatsApp','SMS','Call','Favorite','Delete']){
   const control=page.getByRole('button',{name:action+' Hub customer',exact:true});await expect(control).toBeVisible();
   if(built)await expect(control).toBeInViewport();
  }
  await expect(page.getByRole('button',{name:'Manage tags for Hub customer',exact:true})).toBeVisible();
  for(const channel of ['Email','SMS']){
   await page.getByRole('button',{name:channel+' Hub customer',exact:true}).click();
   await expect(page.getByRole('button',{name:'Send',exact:true})).toBeVisible();
   await page.getByRole('button',{name:'Send',exact:true}).click();
   await expect(page.getByRole('button',{name:'Send',exact:true})).toHaveCount(0);
   await expect(page).toHaveURL(origin+'/crm/records');
  }
  await expect.poll(()=>writes.filter(w=>w.path.endsWith('/messages/send')).map(w=>w.body.channel).sort()).toEqual(['sms']);
  await page.getByRole('button',{name:'WhatsApp Hub customer',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('Connect your company’s WhatsApp account before sending messages.');
  await page.getByRole('button',{name:'Close dialog',exact:true}).click();
  expect(writes.find(w=>w.path.endsWith('/emails/send')).body.related_record_id).toBe(1);
  await page.getByRole('button',{name:'Edit Hub customer',exact:true}).click();await page.getByLabel('Full name *',{exact:true}).fill('Updated hub customer');await page.getByRole('button',{name:'Save contact',exact:true}).click();await expect(page.getByRole('button',{name:'Edit Updated hub customer',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Add relationship',exact:true}).click();await page.getByLabel('Full name *',{exact:true}).fill('New relationship');await page.getByRole('button',{name:'Save contact',exact:true}).click();await expect(page.getByRole('button',{name:'Edit New relationship',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Delete Updated hub customer',exact:true}).click();await page.getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByRole('button',{name:'Edit Updated hub customer',exact:true})).toHaveCount(0);
  expect(errors).toEqual([]);console.log('PASS Company Admin links, relationship linking, nine row actions, inline email/SMS, WhatsApp connection gate, create/edit/delete, no navigation or browser errors');
 }finally{await browser.close();await server?.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
