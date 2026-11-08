const { chromium } = require('../frontend/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({headless:true});
 try {
 for (const count of [1,2]) {
 const page = await browser.newPage();
 await page.route('**/api/**', async route => {
  const url = new URL(route.request().url());
  let data = {};
  if(url.pathname.endsWith('/access/me')) {
   const selected = Number(route.request().headers()['x-suite-organization'] || 1);
   data = {companyId:selected, companyName:selected===1?'Alpha':'Beta', organizations: [{id:1,name:'Alpha'}, ...(count===2?[{id:2,name:'Beta'}]:[])], memberships:count===2?[1,2]:[1], grants:{}, modules:[], managed:false,isGlobalAdmin:true,isAccessAdmin:true};
  } else if(url.pathname.endsWith('/auth/login')) data = {access_token:'test-token',refresh_token:'test-refresh',user_id:1,email:'user@example.com',role:'admin',is_superuser:true};
  else if(url.pathname.endsWith('/auth/firebase/config')) data={enabled:true,modules:['srm'],firebase_config:{apiKey:'test',projectId:'test',authDomain:'test.firebaseapp.com'}};
  else if(url.pathname.includes('sso')) data=[];
  await route.fulfill({json:data});
 });
 await page.goto(`${process.env.LOGIN_TEST_URL || 'http://127.0.0.1:5206'}/login?next=%2Fsrm%2Finvoices%2F1`);
 await page.getByLabel('Email address',{exact:true}).fill('user@example.com');
 assert.equal(await page.getByLabel('Company workspace',{exact:true}).count(),0);
 await page.getByRole('button',{name:'Continue with Google',exact:true}).waitFor();
 await page.getByRole('button',{name:'Continue with Microsoft / Outlook',exact:true}).waitFor();
 await page.getByLabel('Password',{exact:true}).fill('password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 if(count===2) {
  await page.getByRole('heading',{name:'Choose your company'}).waitFor();
  await page.getByRole('button',{name:'Beta',exact:true}).click();
 }
 await page.waitForURL('**/srm/invoices/1');
 const company = await page.evaluate(()=>sessionStorage.getItem('suite-organization'));
 assert.equal(company,count===2?'2':null);
 console.log(`PASS: ${count} company sign-in, workspace field removed, invoice destination preserved`);
 await page.close();
 }
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
