// Browser acceptance against an actual frontend and API; opens drafts without writing notes.
const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const expect=baseExpect.configure({timeout:45000});
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve('.local/shared-notes-release'),origin=process.env.NOTES_QA_ORIGIN||'http://127.0.0.1:5208';
(async()=>{
 const s=JSON.parse(fs.readFileSync(process.env.NOTES_QA_SESSION_FILE || path.join(root,'session.json'))),browser=await chromium.launch();
 const context=await browser.newContext({viewport:{width:1480,height:1080},serviceWorkers:'block'});
 await context.addInitScript(s=>{if(!sessionStorage.getItem('hrms-auth'))sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:s.token,refreshToken:s.refreshToken,isAuthenticated:true,user:{...s.actor,role:s.actor.role?.name||s.actor.role||'super_admin',access:s.access}},version:0}));},s);
 const page=await context.newPage();page.setDefaultTimeout(45000);const errors=[],failed=[],writes=[];let reads=0,documents=0;
 page.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});page.on('response',async r=>{if(r.url().includes('/api/')&&r.status()>=400)console.log('HTTP',new URL(r.url()).pathname,r.status(),(await r.text()).slice(0,160));if(r.url().includes('/api/')&&r.status()>=500)failed.push({path:new URL(r.url()).pathname,status:r.status()})});
 page.on('request',r=>{if(r.isNavigationRequest()&&r.frame()===page.mainFrame())documents++;if(r.url().includes('/api/')){if(r.method()==='GET')reads++;else if(/project-management\/(notes|note-folders)/.test(r.url()))writes.push({method:r.method(),path:new URL(r.url()).pathname})}});
 const results=[];
 async function stable(name){const url=page.url(),start=reads,docs=documents;await page.waitForTimeout(3000);assert.equal(page.url(),url,'URL must settle');assert.equal(documents,docs,'No document reload loop');assert.ok(reads-start<15,'No request storm');assert.deepEqual(errors,[],'No JavaScript exceptions');results.push({name,status:'pass',url:new URL(url).pathname+new URL(url).search});console.log('PASS',name)}
 try{
  for(const module of ['fam','hrms','crm','power-apps','srm','pms']){
   console.log('OPEN',module);await page.goto(origin+'/'+module);
   const search=page.getByRole('textbox',{name:'Find a page in this application'});await expect(search).toBeVisible();await search.fill('Notes');
   const link=page.locator('.module-menu').getByRole('link',{name:'Notes',exact:true}).first();await expect(link).toBeVisible();assert.equal(await link.getAttribute('href'),'/pms/notes');await link.click();console.log('CLICKED NOTES',module,page.url());
   await expect(page.getByRole('textbox',{name:'Search notes',exact:true})).toBeVisible();await expect(page.getByRole('textbox',{name:'Note title',exact:true})).toBeVisible();await stable(module+' menu → shared Notes');
   console.log('OPEN',module);await page.goto(origin+'/'+module);
   if(module==='pms'){await page.getByRole('textbox',{name:'Find a page in this application'}).fill('Notes');await page.getByRole('button',{name:'Create Private note',exact:true}).click();}
   else if(module==='power-apps'){
    await expect(page.locator('.pa-create-menu summary')).toBeVisible();await page.locator('.pa-create-menu summary').click();await page.locator('.pa-create-menu').getByRole('button',{name:'Note',exact:true}).click();
   }else{await page.getByRole('button',{name:'New',exact:true}).first().click();await page.getByRole('menuitem',{name:/^(?:Private )?Note\b/i}).click();}
   await expect(page).toHaveURL(/\/pms\/notes\?new=1$/);await expect(page.getByRole('textbox',{name:'Note title',exact:true})).toHaveValue('');await expect(page.getByRole('textbox',{name:'Note content',exact:true})).toBeVisible();assert.equal(await page.locator('.notes-workspace').count(),1,'Reuse a single Notes workspace');await stable(module+' Create → Note');
   await page.screenshot({path:path.join(root,module+'-create-note.png')});
  }
  for(const route of ['/crm/tasks?workspaceView=notes','/power-apps/notes']){await page.goto(origin+route);await expect(page).toHaveURL(/\/pms\/notes(?:\?note=\d+)?$/);await expect(page.getByRole('textbox',{name:'Search notes',exact:true})).toBeVisible();await expect(page.getByRole('textbox',{name:'Note title',exact:true})).toBeVisible();await stable(route+' legacy redirect')}
  const data=await (await context.request.get(origin+'/api/v1/project-management/notes',{headers:{Authorization:'Bearer '+s.token}})).json();assert.ok(data.length,'Existing note required for reload verification');await page.goto(origin+'/pms/notes?note='+data[0].id);await expect(page.getByRole('textbox',{name:'Note title',exact:true})).toBeVisible();await stable('Direct note deep link');
  await page.reload();await expect(page.getByRole('textbox',{name:'Note title',exact:true})).toBeVisible();await stable('Reload note deep link');
  assert.deepEqual(writes,[],'Checking creation links must not create or update saved notes');assert.deepEqual(failed,[],'All API responses must avoid server errors');
  fs.writeFileSync(path.join(root,origin.startsWith('https:')?'live-results.json':'preview-results.json'),JSON.stringify({origin,results,errors,failed,writes,reads,documents},null,2));console.log('ALL PASS',results.length,'checks; no note writes; no loops or API failures');
 }catch(e){await page.screenshot({path:path.join(root,'failed.png')}).catch(()=>{});console.log('FAILED URL',new URL(page.url()).pathname);console.log('JS ERRORS',JSON.stringify(errors));console.log('SERVER ERRORS',JSON.stringify(failed));throw e;}finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
