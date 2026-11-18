const {chromium, expect}=require('playwright/test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const base=process.env.LAUNCHER_QA_URL || 'http://localhost:5125';
const access={managed:false,companyId:1,companyName:'QA Workspace',memberships:[1,2],organizations:[{id:1,name:'QA Workspace'},{id:2,name:'Second workspace'}],grants:{},modules:[],isAccessAdmin:true,isGlobalAdmin:true};
(async()=>{
 const browser=await chromium.launch({headless:true});
 const output=path.resolve(__dirname,'../../docs/qa/launcher-enhancements');fs.mkdirSync(output,{recursive:true});
 let saved=null, writes=0, failSync=false, failAccess=false, delayAccess=false;
 async function pageFor(width){
  const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/**',async route=>{
   const url=new URL(route.request().url()).pathname;let body={};
   if(url.endsWith('/access/me')){if(delayAccess)await new Promise(r=>setTimeout(r,1500));if(failAccess)return route.fulfill({status:503,json:{detail:'Test access outage'}});body=access;}
   else if(url.endsWith('/access/launcher-preferences')){
    if(failSync)return route.fulfill({status:503,json:{detail:'Test sync outage'}});
    if(route.request().method()==='PUT'){saved=route.request().postDataJSON().favorites;writes++;}body={favorites:saved};
   }
   else if(url.endsWith('/notifications/summary'))body={groups:[]};
   else if(url.endsWith('/branches/context'))body={company_id:1,selected:1,all_branches:false,manage_access:false,branches:[{id:1,name:'Main',code:'MAIN',can_write:true}]};
   else if(url.endsWith('/auth/branding'))body={company_name:'QA Workspace'};
   else if(url.endsWith('/homepage-banner'))body={image:'',mobile_image:'',x:70,y:50,mobile_x:75,mobile_y:50,zoom:1,overlay:'#eeedff',opacity:.15};
   else if(url.endsWith('/imports/sample-data/status'))return route.fulfill({status:204,body:''});
   return route.fulfill({json:body});
  });
  await page.goto(base+'/launcher-enhancements-qa.html');return {page,context,errors};
 }
 try{
  for(const width of [1440,390]){
   saved=null;failSync=false;delayAccess=true;
   const {page,context,errors}=await pageFor(width);
   await expect(page.getByRole('status',{name:'Loading applications',exact:true})).toBeVisible();delayAccess=false;
   await expect(page.locator('.launcher-card')).toHaveCount(6);
   await expect(page.locator('.launcher-stats')).toContainText('2');
   const crm=page.getByRole('button',{name:'Add to favorites: VyaparaCRM',exact:true});
   const box=await crm.boundingBox();assert.ok(box.width>=44 && box.height>=44);assert.equal(await crm.evaluate(el=>getComputedStyle(el).opacity),'1');
   await crm.click();await expect(page.getByRole('button',{name:'Remove from favorites: VyaparaCRM',exact:true})).toHaveAttribute('aria-pressed','true');
   assert.equal(await page.locator('.launcher-crm .launcher-favorite svg').evaluate(el=>getComputedStyle(el).fill),'rgb(250, 204, 21)');
   await expect(page.locator('.launcher-feedback')).toContainText('added to favorites');
   await page.getByRole('button',{name:'Add to favorites: AI HRMS',exact:true}).click();
   await page.getByRole('button',{name:'Move AI HRMS earlier',exact:true}).click();
   await expect(page.locator('.launcher-card').first()).toHaveAttribute('aria-label','AI HRMS');
   await page.getByRole('button',{name:'Remove from favorites: AI HRMS',exact:true}).click();
   await page.getByRole('button',{name:'Undo',exact:true}).click();
   await expect(page.locator('.launcher-card').first()).toHaveAttribute('aria-label','AI HRMS');
   await page.getByRole('button',{name:'Favorites (2)',exact:true}).click();await expect(page.locator('.launcher-card')).toHaveCount(2);
   const search=page.getByRole('combobox',{name:'Search applications'});await search.fill('crm');await expect(page.locator('.launcher-card')).toHaveCount(1);
   await expect(page.locator('.launcher-card mark')).toHaveCount(1);
   await page.reload();await expect(page.locator('.launcher-card')).toHaveCount(1);await expect(search).toHaveValue('crm');
   await page.getByRole('button',{name:'Clear application search'}).click();await expect(page.locator('.launcher-card')).toHaveCount(2);
   await page.getByRole('button',{name:'All applications',exact:true}).click();await expect(page.locator('.launcher-card')).toHaveCount(6);
   await page.getByText('About VyaparaCRM',{exact:true}).click();await expect(page.locator('.launcher-crm .launcher-description-details p')).toBeVisible();
   await search.fill('no-such-app');await expect(page.getByRole('heading',{name:'No matching applications',exact:true})).toBeVisible();
   await page.getByRole('button',{name:'Show all applications',exact:true}).click();await expect(page.locator('.launcher-card')).toHaveCount(6);
   await expect.poll(()=>saved).toEqual(['hrms','crm']);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'horizontal overflow');
   await page.screenshot({path:path.join(output,`dashboard-${width}.png`),fullPage:true});assert.deepEqual(errors,[]);await context.close();console.log(`PASS ${width}: favorites, reorder, Undo, persistence, search, description, mobile layout`);
  }
  const {page,context,errors}=await pageFor(1440);await expect(page.locator('.launcher-card')).toHaveCount(6);
  await expect(page.getByRole('button',{name:'Remove from favorites: AI HRMS',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Remove from favorites: AI HRMS',exact:true}).click();
  failSync=true;await expect(page.getByRole('button',{name:'Retry sync',exact:true})).toBeVisible();failSync=false;
  await page.getByRole('button',{name:'Retry sync',exact:true}).click();await expect.poll(()=>saved).toEqual(['crm']);
  assert.deepEqual(errors,[]);await context.close();console.log('PASS cross-device hydration and failed-save retry');
  failAccess=true;const failure=await pageFor(390);await expect(failure.page.getByRole('button',{name:'Try again',exact:true})).toBeVisible();
  await expect(failure.page.getByText('No applications assigned yet.',{exact:false})).toHaveCount(0);
  failAccess=false;await failure.page.getByRole('button',{name:'Try again',exact:true}).click();await expect(failure.page.locator('.launcher-card')).toHaveCount(6);
  assert.deepEqual(failure.errors,[]);await failure.context.close();console.log('PASS access failure and retry');
  const keyboard=await pageFor(1440);await expect(keyboard.page.locator('.launcher-card')).toHaveCount(6);
  await keyboard.page.keyboard.press('Control+k');
  await expect(keyboard.page.getByRole('combobox',{name:'Search applications'})).toBeFocused();
  await keyboard.page.getByRole('combobox',{name:'Search applications'}).fill('pms');
  await expect(keyboard.page.locator('#launcher-search-results').getByRole('option')).toHaveCount(1);
  await keyboard.page.keyboard.press('Escape');await expect(keyboard.page.getByRole('listbox')).toHaveCount(0);
  await keyboard.page.evaluate(()=>{
    const stored=JSON.parse(localStorage.getItem('suite-navigation-preferences-v1'));
    stored.state.contexts['9001:1'].recent=['/crm'];stored.state.contexts['9001:1'].recentVisitedAt={'/crm':'2026-11-08T10:00:00Z'};
    localStorage.setItem('suite-navigation-preferences-v1',JSON.stringify(stored));
  });
  await keyboard.page.reload();await expect(keyboard.page.locator('.launcher-recents time')).toHaveAttribute('datetime','2026-11-08T10:00:00Z');
  await keyboard.page.getByRole('button',{name:'Clear recent pages'}).click();await expect(keyboard.page.locator('.launcher-recents')).toHaveCount(0);
  await keyboard.page.getByRole('combobox',{name:'Search applications'}).focus();await keyboard.page.keyboard.press('Enter');await expect(keyboard.page).toHaveURL(/\/pms$/);
  assert.deepEqual(keyboard.errors,[]);await keyboard.context.close();console.log('PASS keyboard shortcuts, acronym search, navigation and recent timestamps');
  console.log(`PASS ${writes} favorites API writes`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
