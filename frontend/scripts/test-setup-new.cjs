const {chromium,expect}=require('playwright/test');
const origin=process.env.SETUP_NEW_ORIGIN||'http://localhost:5198';
(async()=>{
 const browser=await chromium.launch();
 try {
  const page=await browser.newPage();page.setDefaultTimeout(15000);
  const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
  let missing=false;
  const item=(id,module,ready,required=true)=>({id,module,ready,required,title:id,description:id,destination:id==='custom-fields'?'/settings/crm':'/settings/'+id,canRepair:true});
  await page.route('**/api/v1/**',route=>{
   const path=new URL(route.request().url()).pathname;
   let data=[];
   if(path.endsWith('/access/setup'))data={companyId:1,ready:true,items:[item('company','company',true)],moduleItems:['crm','srm','hrms','fam','project_management'].map(m=>item(m,m,!missing)),recommendations:[item('custom-fields','crm',false,false)]};
   else if(path.endsWith('/permissions'))data={can_manual_probability:false};
   else if(path.endsWith('/workspaces'))data=[{id:1,name:'QA workspace',role:'Owner'}];
   else if(path.includes('/master-data/'))data={items:[],total:0,customFields:[]};
   else if(path.includes('/crm/'))data={items:[],total:0,pages:1};
   return route.fulfill({json:data});
  });
  await page.route('**/*',async(route)=>{
   if(route.request().isNavigationRequest())return route.fulfill({contentType:'text/html',body:`<html><body><div id="root"></div><script type="module">import R from '/@react-refresh'; R.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>(type)=>type; window.__vite_plugin_react_preamble_installed__=true; await import('/scripts/setup-new-harness.tsx');</script></body></html>`});
   return route.fallback();
  });
  for(const path of ['/crm','/srm','/hrms','/fam','/pms','/settings','/settings/crm']){
   await page.goto(origin+path);await expect(page.getByLabel('Potential clients category')).toHaveText('Customers & leads');
   await expect.poll(()=>page.evaluate(()=>document.querySelector('[aria-label="Workspace setup guide"]')===null)).toBe(true);
   await expect(page.getByRole('region',{name:'Mandatory setup requirements'})).toHaveCount(0);
  }
  missing=true;
  for(const path of ['/crm','/srm','/hrms','/fam','/pms']){
   await page.goto(origin+path);const guide=page.getByRole('region',{name:'Workspace setup guide'});
   await expect(guide).toBeVisible();await expect(guide.getByRole('status')).toContainText('1 mandatory item');
   missing=false;await guide.getByRole('button',{name:'Check again'}).click();await expect(guide).toHaveCount(0);missing=true;
  }
  missing=false;await page.goto(origin+'/crm');
  const trigger=page.getByRole('button',{name:'New',exact:true});
  for(const kind of ['Deal','Task','Contact','Company','Activity','Reminder']){
   console.log('Testing CRM',kind);await trigger.click();await expect(page.getByRole('menuitem')).toHaveCount(12);
   await page.getByRole('menuitem',{name:new RegExp('^'+kind+'\\s+Quick capture')}).click();
   const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
   
   if(kind==='Deal')await page.getByRole('button',{name:'Close deal form'}).click();
   else await page.getByRole('button',{name:'Close dialog',exact:true}).click();
   await expect(dialog).toHaveCount(0);
   await trigger.click();await expect(page.getByRole('menu')).toBeVisible();await expect(dialog).toHaveCount(0);await expect(page.getByRole('menuitem')).toHaveCount(12);
   await page.getByRole('button',{name:'New',exact:true}).click();await expect(page.getByRole('menu')).toHaveCount(0);
  }
  for(const [path,count] of [['/srm',5],['/fam',5],['/hrms',4],['/pms',7]]){
   await page.goto(origin+path);const newButton=page.getByRole('button',{name:'New',exact:true});await expect(newButton).toBeEnabled();
   for(let n=0;n<2;n++){await newButton.click();await expect(page.getByRole('menuitem')).toHaveCount(count);await page.getByRole('button',{name:'New',exact:true}).click();await expect(page.getByRole('menu')).toHaveCount(0);}
  }
  expect(errors).toEqual([]);console.log('PASS: mandatory-only guides across five modules, optional CRM fields, refresh hides completed guides, Potential Clients grouping, CRM close/reopen for six types, all module New menus');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
