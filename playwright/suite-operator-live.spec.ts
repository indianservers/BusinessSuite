import {test,expect} from '../frontend/node_modules/playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import path from 'node:path';

test('live suite operator: inherited Gemini, multi-module summary, receipts, logs and mobile layout',async({page})=>{
  test.skip(process.env.PMS_SUITE_LIVE!=='1','Opt-in: configured live backend, QA workspace and Gemini usage required.');
  test.setTimeout(150000);
  const root=path.resolve('..'),dir=path.join(root,'docs/qa/suite-operator-2026-10-24');mkdirSync(dir,{recursive:true});
  const auth=JSON.parse(readFileSync(path.join(root,'.local/operator-live-qa/auth.json'),'utf8'));
  const evidence=JSON.parse(readFileSync(path.join(root,'.local/operator-live-qa/suite-results.json'),'utf8'));
  const errors:string[]=[],failed:any[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)failed.push({url:r.url(),status:r.status()});});
  await page.addInitScript(a=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:a.token,user:{id:a.user_id,email:'admin@local.invalid',role:'admin',is_superuser:true},isAuthenticated:true},version:0})),auth);
  await page.setViewportSize({width:1600,height:1050});
  await page.goto(`/ai-agents/operator?workspace=${evidence.workspace_id}`);
  await expect(page.getByRole('heading',{name:'One request. Connected work.'})).toBeVisible();
  await expect(page.getByText(/inherited configuration/)).toBeVisible();
  await page.getByLabel('Suite request type').selectOption('summary');
  await page.getByRole('button',{name:'CRM',exact:true}).click();
  await page.getByRole('checkbox').filter({visible:true}).last().check(); // CRM tasks
  await page.getByRole('button',{name:'FAM',exact:true}).click();
  await page.getByRole('checkbox').filter({visible:true}).first().check(); // FAM dashboard
  await page.getByLabel('Suite command').fill('Summarize the selected CRM task sample and finance totals in three short bullets. Mention empty data. Do not propose actions or ask questions.');
  const result=page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  const run=await (await result).json();expect(run.status,JSON.stringify({error:run.error_code,id:run.id})).toBe('answered');
  await expect(page.getByLabel('Suite plan review')).toContainText('answered');
  await page.screenshot({path:path.join(dir,'suite-desktop.png'),fullPage:true});
  const completed=evidence.checks.find((c:any)=>c.name.includes('four-module')).evidence.run_id;
  // Load the already completed run through its visible history entry.
  const history=page.getByRole('heading',{name:'Recent requests'}).locator('..');
  await history.getByRole('button').last().click();
  await expect(page.getByLabel('Suite plan review')).toContainText('succeeded');
  await page.getByRole('button',{name:'Usage & request logs',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Usage & request logs',exact:true})).toBeVisible();
  await expect(page.getByText(/input \/ .*output tokens/).first()).toBeVisible();
  await page.screenshot({path:path.join(dir,'suite-receipts-logs.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'One request. Connected work.'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
  await page.screenshot({path:path.join(dir,'suite-mobile.png'),fullPage:true});
  expect(errors).toEqual([]);expect(failed).toEqual([]);
  writeFileSync(path.join(dir,'browser-results.json'),JSON.stringify({status:'passed',summary_run_id:run.id,completed_run_id:completed,workspace_id:evidence.workspace_id,errors,failed},null,2));
});
