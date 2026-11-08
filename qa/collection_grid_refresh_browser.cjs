const {chromium,request}=require('../frontend/node_modules/playwright');
const appBase=process.env.SUITE_LIST_APP_URL||'http://localhost:5174';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve('outputs/collection-grid-refresh');fs.mkdirSync(out,{recursive:true});
 const api=await request.newContext();const response=await api.post('http://127.0.0.1:1582/api/v1/auth/login',{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});assert(response.ok(),'QA login failed');const auth=await response.json();const responseCache=new Map();
 const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(s=>sessionStorage.setItem('hrms-auth',JSON.stringify(s)),{state:{accessToken:auth.access_token,refreshToken:auth.refresh_token,user:{id:auth.user_id,email:auth.email,role:auth.role,is_superuser:auth.is_superuser},isAuthenticated:true},version:0});
 await context.route('**/api/**',async route=>{try{const u=new URL(route.request().url());const key=u.pathname+u.search,options={method:route.request().method(),headers:{...route.request().headers(),host:'127.0.0.1:1582'},data:route.request().postData()||undefined,timeout:120000};if(options.method==='GET'){if(!responseCache.has(key))responseCache.set(key,(async()=>{const result=await api.fetch('http://127.0.0.1:1582'+key,options);const cached={status:result.status(),headers:result.headers(),body:await result.body()};await result.dispose();if(cached.status!==200)responseCache.delete(key);return cached;})().catch(error=>{responseCache.delete(key);throw error;}));await route.fulfill(await responseCache.get(key));}else{const result=await api.fetch('http://127.0.0.1:1582'+key,options);await route.fulfill({response:result});}}catch{await route.abort();}});
 const page=await context.newPage(),checks=[],errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',message=>{if(message.type()==='error'&&/Error:|TypeError|ReferenceError|dynamically imported|Minified React/i.test(message.text()))console.log(message.text());});
 try{
 for(const [name,url] of [['PMS','/pms/projects?projectId=87'],['CRM','/crm/leads'],['HRMS','/hrms/employees'],['Sales','/srm/sales-orders'],['Finance','/fam/ledgers'],['Inventory','/srm/inventory/items']]){
 await page.goto(appBase+url,{waitUntil:'domcontentloaded'});
 await page.locator('.native-column-heading,.udg-th .udg-sort-button,.sc-page,.suite-grouped-records').first().waitFor({timeout:120000});
 await page.waitForFunction(()=>!document.querySelector('[data-source-table] .skeleton,[data-source-table] .animate-pulse'),{},{timeout:120000});
 if(name==='HRMS')await page.getByText('Acceptance admin',{exact:true}).first().waitFor({timeout:120000});
 await page.waitForTimeout(300);
 const headings=page.locator('.native-column-heading,.udg-th .udg-sort-button,.udg-th .udg-legacy-heading');
 if(await headings.count())assert(await headings.evaluateAll(els=>els.every(el=>el.querySelector('svg,input[type=checkbox]'))),name+' missing heading icon');
 const columns=page.getByText(/Columns \d+\/\d+/).first();if(await columns.count())checks.push(name+': visible/total column count');
 await page.screenshot({path:path.join(out,name+'.png'),fullPage:false});checks.push(name+': collection rendered');
 }
 await page.goto(appBase+'/pms/projects',{waitUntil:'domcontentloaded'});
 await page.locator('.native-column-heading').first().waitFor({timeout:120000});const clear=page.getByRole('button',{name:'Clear all filters',exact:true}).first();if(await clear.isVisible())await clear.click();await page.locator('.portfolio-table tbody > tr:not(.native-group-row):not(.native-group-create)').first().waitFor({timeout:120000});
 const candidate=page.getByRole('separator',{name:/Resize .* column/}).nth(1);await candidate.waitFor({timeout:120000});const resize=page.getByRole('separator',{name:await candidate.getAttribute('aria-label'),exact:true});const before=Number(await resize.getAttribute('aria-valuenow'));await resize.focus();await page.keyboard.press('ArrowRight');assert(Number(await resize.getAttribute('aria-valuenow'))>before,'Keyboard resize failed');checks.push('Editable grid keyboard resize');
 const summary=page.locator('.native-layout-menu summary').first();await summary.click();const pin=page.getByRole('button',{name:/Pin .* column/}).nth(1);await pin.click();assert.equal(await pin.getAttribute('aria-pressed'),'true');checks.push('Editable grid pinning');
 await page.reload({waitUntil:'domcontentloaded'});await resize.waitFor({timeout:120000});const persisted=Number(await resize.getAttribute('aria-valuenow'));if(persisted<=before)console.log(JSON.stringify({before,persisted,layouts:await page.evaluate(()=>Object.entries(localStorage).filter(([key])=>key.startsWith('native-table-layout:')).map(([key,value])=>({key,layout:JSON.parse(value)})))}));assert(persisted>before,'Width not persisted');checks.push('Saved column width after reload');
 await page.locator('.native-layout-menu summary').first().click();await page.getByRole('button',{name:'Reset table layout',exact:true}).click();checks.push('Reset layout');
 await page.locator('.native-layout-menu summary').first().click();
 const headingsBefore=await page.locator('.native-column-label').allTextContents();
 await page.getByRole('button',{name:'Drag Project column',exact:true}).dragTo(page.locator('.native-column-label').filter({hasText:/^Client$/}).locator('..'));
 const headingsAfter=await page.locator('.native-column-label').allTextContents();
 assert.notDeepEqual(headingsAfter,headingsBefore,'Header drag did not reorder columns');checks.push('Editable header drag reordering');
 const group=page.getByLabel('Group loaded rows by',{exact:true});await group.selectOption('Status');
 await page.getByRole('button',{name:'Collapse all groups',exact:true}).click();assert.equal(await page.locator('.portfolio-table tbody > tr:not(.native-group-row):not(.native-group-create)').count(),0);await page.getByRole('button',{name:'Expand all groups',exact:true}).click();checks.push('Status grouping expand/collapse');
 await page.locator('.native-layout-menu summary').first().click();await page.getByRole('button',{name:'Reset table layout',exact:true}).click();
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png')});
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({passed:true,checks,errors},null,2));console.log(JSON.stringify({passed:true,checks}));
 }catch(e){await page.screenshot({path:path.join(out,'failure.png')});fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({passed:false,checks,errors,error:e.message},null,2));throw e;}
 finally{await browser.close();await api.dispose();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
