// Real profile component and real API/database. Run through test_employee_profile_records.py.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async () => {
 const browser = await chromium.launch();
 try { for(const width of [1440,390]) {
  const page = await browser.newPage({viewport:{width,height:1000}}), errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  let apiQueue=Promise.resolve();await page.route('**/api/v1/**', route => { apiQueue=apiQueue.then(async()=>{
   const incoming = new URL(route.request().url());
   const response = await route.fetch({url:process.env.PROFILE_API+incoming.pathname+incoming.search,headers:{...route.request().headers(),'X-Suite-Organization':process.env.PROFILE_COMPANY,'X-Suite-Branch':process.env.PROFILE_BRANCH}});
   if(response.status()>=400)console.log('API ERROR',incoming.pathname,response.status(),await response.text());await route.fulfill({response});
  });return apiQueue;});
  await page.route(/\/profile-records-qa\?/, route=>route.fulfill({contentType:'text/html', body:`<html><meta charset="utf-8"><body><div id="root"></div><script>window.__PROFILE_QA__=${JSON.stringify({employeeId:Number(process.env.PROFILE_EMPLOYEE),token:process.env.PROFILE_TOKEN})}</script><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>(type)=>type;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/employee-profile-harness.tsx');</script></body></html>`}));
  const goto = tab=>page.goto(`http://127.0.0.1:5198/profile-records-qa?tab=${tab}`, {waitUntil:"networkidle"});
  await goto('job');await page.getByRole('button',{name:'Edit',exact:true}).click();
  await page.getByLabel('Designation / Job Role',{exact:true}).selectOption(process.env.PROFILE_DESIGNATION);
  await page.getByRole('button',{name:'Save Changes',exact:true}).click();await page.getByRole('button',{name:'Edit',exact:true}).waitFor();
  await goto('job');await page.getByText('Profile QA Designation',{exact:true}).waitFor();
  console.log(`PASS ${width} designation persisted after reload`);
  for(const [tab,kind,fields,primary] of [
   ['education','Education',{'Degree *':'B.Tech','Institution':'QA College','Board / University':'QA University','Pass Year':'2020','Percentage / CGPA':'8.75'},'Degree *'],
   ['experience','Experience',{'Company Name *':'Previous Corp','Designation':'Engineer','From Date':'2020-01-01','To Date':'2024-01-01','Responsibilities':'Built systems'},'Company Name *'],
   ['skills','Skill',{'Skill Name *':'TypeScript','Proficiency':'Advanced','Years Experience':'3.5'},'Skill Name *'],
   ['certifications','Certification',{'Certification Name *':'Cloud Architect','Issuing Body':'Cloud Provider','Certificate Number':'CERT-007','Issue Date':'2025-01-01','Expiry Date':'2028-01-01','Score / Grade':'Pass','Verification URL':'https://example.com/verify'},'Certification Name *']
  ]) {
   await goto(tab);await page.getByRole('button',{name:'Edit',exact:true}).click();
   for(const [label,value] of Object.entries(fields)) {
    const field=page.getByLabel(label,{exact:true});
    if(!await field.isVisible()) {
     const group=await field.evaluate(element=>element.closest('[data-form-section]')?.getAttribute('data-form-section'));
     assert(group!==null,`No form section for ${label}`);
     await field.locator('xpath=ancestor::form').getByRole('navigation',{name:'Form sections',exact:true}).getByRole('button').nth(Number(group)).click();
    }
    await field.fill(value);
   }
   if(tab==='certifications')await page.getByLabel('Renewable',{exact:true}).check();
   await page.getByRole('button',{name:`Add ${kind}`,exact:true}).click();await page.getByRole('button',{name:'Edit record',exact:true}).waitFor();
   await goto(tab);await page.getByRole('button',{name:'Edit record',exact:true}).waitFor();
   if(tab==='education'){await page.getByText('QA University',{exact:true}).waitFor();assert(!(await page.locator('body').innerText()).includes('8.75%'));}
   if(tab==='skills')await page.getByText('3.5 years of experience',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Edit record',exact:true}).click();
   const updated=fields[primary]+' Updated';await page.getByLabel(primary,{exact:true}).fill(updated);
   await page.getByRole('button',{name:`Save ${kind}`,exact:true}).click();await page.getByRole('button',{name:`Add ${kind}`,exact:true}).waitFor();
   await goto(tab);await page.getByText(updated,{exact:false}).last().waitFor();
   fs.mkdirSync('../outputs/employee-profile-records',{recursive:true});await page.screenshot({path:path.resolve('../outputs/employee-profile-records',`${tab}-${width}.png`),fullPage:true});
   page.once('dialog',dialog=>dialog.dismiss());await page.getByRole('button',{name:'Delete record',exact:true}).click();await page.getByText(updated,{exact:false}).last().waitFor();
   page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Delete record',exact:true}).click();await page.getByRole('button',{name:'Delete record',exact:true}).waitFor({state:'detached'});
   await goto(tab);await page.getByRole('button',{name:'Edit',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Edit record',exact:true}).count(),0);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
   console.log(`PASS ${width} ${tab}: add, reload, edit, reload, cancel deletion, delete, reload`);
  }
  assert.deepEqual(errors,[]);await page.close();
 }} finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
