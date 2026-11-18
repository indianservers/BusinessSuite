const {chromium,expect:baseExpect}=require('playwright/test');
const expect=baseExpect.configure({timeout:30000});
const base=process.env.ADMIN_QA_BASE_URL||'http://127.0.0.1:5192';
const html=`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/admin-discovery-qa.tsx');</script>`;
(async()=>{const browser=await chromium.launch();try{
 for(const action of ['branch','workspace','denied','company']){
  const page=await browser.newPage();const switches=[];let navigations=0;
  await page.route('**/hrms*',r=>r.fulfill({contentType:'text/html',body:navigations++===0?html:'Destination'}));
  await page.route('**/pms/workspaces*',r=>r.fulfill({contentType:'text/html',body:'Destination'}));
  await page.route('**/api/v1/**',r=>{
   const url=new URL(r.request().url());
   if(url.pathname.endsWith('/access/me')){switches.push(r.request().headers());return r.fulfill(action==='denied'?{status:403,json:{detail:'Company denied'}}:{json:{companyId:2,managed:false,grants:{},modules:[],memberships:[1,2],isAccessAdmin:true,isGlobalAdmin:true}})}
   if(url.pathname.endsWith('/branches/context'))return r.fulfill({json:{company_id:1,selected:null,all_branches:true,manage_access:true,branches:[{id:1,name:'Local branch',can_write:true}],...(action==='company'?{}:{platform_branches:[{id:1,name:'Local branch',company_id:1,company_name:'Local company',can_write:true},{id:9,name:'Foreign branch',company_id:2,company_name:'Other company',can_write:true}]})}});
   if(url.pathname.endsWith('/branches/workspaces'))return r.fulfill({json:{items:[{id:'local',key:'1:hrms:local',module:'hrms',name:'Archived local',company_id:1,company_name:'Local company',branch_id:1,branch_name:'Local branch',status:'Archived'},...(action==='company'?[]:[{id:'foreign',key:'2:pms:foreign',module:'pms',name:'Foreign PMS',company_id:2,company_name:'Other company',branch_id:9,branch_name:'Foreign branch',status:'Active'}])]}});
   return r.fulfill({json:{items:[]}});
  });
  await page.goto(base+'/hrms'+(action==='company'?'?company=1':''));
  if(action==='branch'){
   await expect(page.locator('select[aria-label="Current branch"] option').filter({hasText:'Other company · Foreign branch'})).toHaveCount(1);
   await page.getByRole('combobox',{name:'Current branch'}).selectOption('9');
   await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.getByRole('button',{name:'Switch branch',exact:true}).click()]);await expect.poll(()=>switches.length).toBe(1);
   expect(await page.evaluate(()=>sessionStorage.getItem('suite-organization'))).toBe('2');
  }else{
   await page.getByRole('button',{name:'Open workspace switcher'}).click();
   await expect(page.getByRole('link',{name:/Archived local/})).toBeVisible();
   if(action==='company'){
    await expect(page.getByRole('link',{name:/Foreign PMS/})).toHaveCount(0);
    await expect(page.locator('select[aria-label="Current branch"] option').filter({hasText:'Foreign branch'})).toHaveCount(0);
   }else{
    await page.getByRole('link',{name:/Foreign PMS/}).click();
    await expect.poll(()=>switches.length).toBe(1);
    if(action==='denied'){
     await expect(page.getByRole('alert')).toContainText('current company and branch have been preserved');
     expect(await page.evaluate(()=>sessionStorage.getItem('suite-organization'))).toBe('1');
     expect(await page.evaluate(()=>sessionStorage.getItem('suite-branch'))).toBe('all');
    }else{await expect(page).toHaveURL(/\/pms\/workspaces\?space=foreign/);}
   }
  }
  if(switches.length){expect(switches[0]['x-suite-organization']).toBe('2');expect(switches[0]['x-suite-branch']).toBe('9');}
  await page.close();console.log('Admin navigation passed:',action);
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
