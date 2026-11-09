const {chromium,expect}=require('playwright/test');const fs=require('node:fs'),path=require('node:path');
(async()=>{const browser=await chromium.launch();try{
 const login=await fetch('http://127.0.0.1:1582/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})});if(!login.ok)throw Error('QA login failed');const auth=await login.json();
 const context=await browser.newContext({viewport:{width:1680,height:1050}});
 await context.addInitScript(a=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:a.access_token,refreshToken:a.refresh_token,isAuthenticated:true,user:{id:a.user_id,email:a.email,role:a.role,is_superuser:a.is_superuser}},version:0})),auth);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));const output=path.resolve('outputs/action-presentation');fs.mkdirSync(output,{recursive:true});
 const results=[];
 for(const route of ['/pms/projects','/crm/leads','/hrms/employees','/fam/vouchers','/srm/sales-orders','/crm/communication-hub']){
  await page.goto('http://127.0.0.1:5188'+route);const choice=page.getByRole('button',{name:'Indian Servers (Default)',exact:true});if(await choice.isVisible().catch(()=>false))await choice.click();
  await page.locator('h1').first().waitFor({timeout:30000});await page.waitForTimeout(6000);
  if(page.url().includes('/login'))throw Error('Login redirect '+route);
  const name=route.slice(1).replaceAll('/','-');await page.screenshot({path:path.join(output,name+'.png')});
  results.push({route,url:new URL(page.url()).pathname,buttons:await page.locator('.kf-button').count(),semanticActions:await page.locator('[data-action-tone]').count(),menus:await page.locator('[aria-haspopup=menu]').count()});
 }
 fs.writeFileSync(path.join(output,'smoke.json'),JSON.stringify({results,errors},null,2));expect(errors).toEqual([]);console.log(JSON.stringify(results));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});

