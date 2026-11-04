const { chromium } = require('../frontend/node_modules/playwright');
const { auth } = require('./custom_fields_live.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
 const a = await auth(), browser = await chromium.launch({headless:true});
 try {
  const context = await browser.newContext();
  await context.addInitScript(({login,actor,access}) => {
   sessionStorage.setItem('suite-organization','1'); sessionStorage.setItem('suite-branch','6');
   sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{...actor,role:actor.role?.name||'super_admin',access}},version:0}));
  },a);
  const page=await context.newPage(), requests=[], errors=[];
  page.on('request',r=>{if(r.url().includes('/api/'))requests.push(new URL(r.url()).pathname);});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://localhost:5173/hrms/payroll');
  await page.getByRole('button',{name:'Guided Payroll',exact:true}).waitFor();
  await page.waitForTimeout(4000);
  assert(!requests.some(p=>/lwp-feed|statutory\/challans|tax-cycles/.test(p)), 'Inactive payroll tabs fetched data');
  const results=[];
  for(const [tab,pattern] of [['Inputs',/lwp/],['Statutory',/challans/],['Payslip Viewer',/employees/],['Payroll Tools',/components|salary-advances|payslip-queries/]]) {
   const start=requests.length;
   await page.getByRole('button',{name:tab,exact:true}).click();
   await page.waitForTimeout(3500);
   assert(requests.slice(start).some(p=>pattern.test(p)), `${tab} did not load its data`);
   results.push({tab,requests:requests.slice(start)});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync('docs/qa/local-performance/payroll-tabs.json',JSON.stringify({passed:true,results,errors},null,2));
  console.log('PASS payroll lazy tabs and native data loading');
 } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
