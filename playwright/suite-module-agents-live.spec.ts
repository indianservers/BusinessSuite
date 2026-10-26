import {test,expect} from '../frontend/node_modules/playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
import path from 'node:path';

test('live four-module memory controls, completed receipts and usage logs',async({page})=>{
  test.skip(process.env.SUITE_MODULE_LIVE!=='1','Opt-in: existing live QA session and completed module-agent evidence required; no model call.');
  const root=path.resolve('..'),dir=path.join(root,'docs/qa/module-agents-2026-10-26');
  const auth=JSON.parse(readFileSync(path.join(root,'.local/operator-live-qa/auth.json'),'utf8'));
  const evidence=JSON.parse(readFileSync(path.join(dir,'live-results.json'),'utf8'));
  const errors:string[]=[],failed:any[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)failed.push({url:r.url(),status:r.status()});});
  await page.addInitScript(a=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:a.token,user:{id:a.user_id,email:'admin@local.invalid',role:'super_admin',is_superuser:true},isAuthenticated:true},version:0})),auth);
  await page.setViewportSize({width:1500,height:1000});
  await page.goto('/ai-agents/operator?module=CRM&workspace=1');
  await expect(page.getByRole('heading',{name:'CRM memory',exact:true})).toBeVisible();
  const label=`Browser QA preference ${Date.now()}`;
  await page.getByLabel('Module memory text').fill(label);
  await page.getByRole('button',{name:'Save memory',exact:true}).click();
  await expect(page.getByText(label,{exact:true})).toBeVisible();
  const remembered=page.getByText(label,{exact:true}).locator('..');
  await remembered.getByRole('button',{name:'Forget memory',exact:true}).click();
  await expect(page.getByText(label,{exact:true})).toHaveCount(0);
  const completed=evidence.checks.find((c:any)=>c.name.includes('canonical receipts')).evidence.run_id;
  const summary=evidence.checks.find((c:any)=>c.name.includes('follow-up recalls')).evidence.run_id;
  const history=page.getByRole('heading',{name:'Recent requests'}).locator('..');
  await history.getByRole('button').filter({hasText:'succeeded'}).first().click();
  await expect(page.getByLabel('Suite plan review')).toContainText(`Request #${completed}`);
  for(const m of ['hrms','crm','srm','fam'])await expect(page.getByLabel('Suite plan review')).toContainText(`${m}.remember`);
  await page.getByRole('button',{name:'Usage & request logs',exact:true}).click();
  await expect(page.getByText(/input \/ .*output tokens/).first()).toBeVisible();
  await page.screenshot({path:path.join(dir,'module-agents-desktop.png'),fullPage:true});
  for(const module of ['HRMS','SRM','FAM']){
    await page.getByRole('button',{name:module,exact:true}).click();
    await expect(page.getByRole('heading',{name:`${module} memory`,exact:true})).toBeVisible();
  }
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
  await page.screenshot({path:path.join(dir,'module-agents-mobile.png'),fullPage:true});
  expect(errors).toEqual([]);expect(failed).toEqual([]);
  writeFileSync(path.join(dir,'browser-results.json'),JSON.stringify({status:'passed',completed_run_id:completed,summary_run_id:summary,errors,failed},null,2));
});
