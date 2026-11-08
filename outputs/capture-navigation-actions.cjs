const {chromium,request}=require('../frontend/node_modules/playwright');const fs=require('fs');
(async()=>{const out='outputs/navigation-actions';fs.mkdirSync(out,{recursive:true});const api=await request.newContext();const response=await api.post('http://127.0.0.1:1582/api/v1/auth/login',{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});if(!response.ok())throw Error('QA login failed');const a=await response.json();const browser=await chromium.launch();const context=await browser.newContext({viewport:{width:1600,height:1100}});await context.addInitScript(a=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:a.access_token,refreshToken:a.refresh_token,user:{id:a.user_id,email:a.email,role:a.role,is_superuser:a.is_superuser},isAuthenticated:true},version:0})),a);await context.route('**/api/**',async route=>{try{const url=new URL(route.request().url());const r=await api.fetch('http://127.0.0.1:1582'+url.pathname+url.search,{method:route.request().method(),headers:route.request().headers(),data:route.request().postData()||undefined});await route.fulfill({response:r});}catch{await route.abort();}});const page=await context.newPage();

for(const [name,url,label] of [['CRM','/crm/leads','Leads'],['PMS','/pms/projects','Projects'],['Sales','/srm/sales-orders','Sales Orders']]) {
 await page.goto('http://localhost:5196'+url);
 const navigation=page.locator('.module-menu').first();
 await navigation.getByRole('textbox',{name:'Find a page in this application'}).waitFor({timeout:60000});
 await page.getByRole('heading',{name:name==='CRM'?'Lead workbench':name==='PMS'?'Projects':'Sales Orders',exact:true}).waitFor({timeout:60000});await page.getByText(/Loading (lead records|your project portfolio)/i).first().waitFor({state:'hidden',timeout:90000});await page.waitForTimeout(1200);await navigation.getByRole('button',{name:'Expand all menu categories',exact:true}).click();
 const more=navigation.getByRole('button',{name:'More options for '+label,exact:true}).first();
 await more.scrollIntoViewIfNeeded();await more.click();
 await page.getByRole('menuitem',{name:'Copy link',exact:true}).waitFor();
 await page.waitForTimeout(800);await page.screenshot({path:out+'/'+name+'-menu.png'});
 if(name==='CRM') {const create=page.getByRole('menuitem',{name:'Create new',exact:true});if(await create.count()){await create.hover();await page.getByRole('menuitem',{name:'Add Lead',exact:true}).waitFor();await page.screenshot({path:out+'/CRM-create-submenu.png'});}}
 await page.keyboard.press('Escape');await page.keyboard.press('Escape');console.log(name+': menu captured');
}
await browser.close();await api.dispose();})().catch(e=>{console.error(e.message.split('\n')[0]);process.exitCode=1;});
