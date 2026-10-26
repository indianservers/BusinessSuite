import {test,expect} from '../frontend/node_modules/playwright/test';
import {authenticateAi} from './ai-test-utils';

for(const module of ['HRMS','CRM','SRM','FAM']){
test(`${module} agent memory, follow-up, approval and receipts`,async({page})=>{
  await authenticateAi(page,'crm_org_admin');
  let memories:any[]=[];const commands:any[]=[];
  await page.route('**/api/v1/project-management/projects*',r=>r.fulfill({json:[]}));
  await page.route('**/api/v1/project-management/workspaces',r=>r.fulfill({json:[]}));
  await page.route('**/api/v1/ai-operator/providers*',r=>r.fulfill({json:{items:[{provider:'gemini',enabled:true,data_sharing_allowed:true,model:'test'}]}}));
  await page.route('**/api/v1/ai-operator/suite/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path.endsWith('/tools'))return route.fulfill({json:{tools:[]}});
    if(path.endsWith('/memories')){
      if(req.method()==='POST')memories=[{id:10,...req.postDataJSON()}];
      return route.fulfill({json:req.method()==='POST'?memories[0]:{items:memories}});
    }
    if(path.endsWith('/memories/10')){memories=[];return route.fulfill({json:{forgotten:true}});}
    const plan={summary:'Remember the review preference',steps:[{tool:module.toLowerCase()+'.remember',payload:{text:'Review every Friday'}}]};
    if(path.endsWith('/commands')){
      const body=req.postDataJSON();commands.push(body);
      return route.fulfill({json:{id:commands.length,command:body.text,status:commands.length===1?'needs_clarification':'awaiting_approval',
        plan_hash:'a'.repeat(64),result:{request:{module}},receipts:[],plan:commands.length===1?{summary:'One detail needed',question:'Which review day?',steps:[]}:plan}});
    }
    if(path.endsWith('/approve'))return route.fulfill({json:{id:2,status:'succeeded',plan_hash:'a'.repeat(64),plan,receipts:[{step:1,tool:module.toLowerCase()+'.remember',record_id:10,status:'succeeded'}]}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto(`/ai-agents/operator?module=${module}`);
  await expect(page.getByRole('heading',{name:`${module} memory`,exact:true})).toBeVisible();
  await page.getByLabel('Module memory text').fill('Use weekly reviews');
  await page.getByRole('button',{name:'Save memory',exact:true}).click();
  await expect(page.getByText('Use weekly reviews',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Forget memory',exact:true}).click();
  await expect(page.getByText('Use weekly reviews',{exact:true})).toHaveCount(0);
  await page.getByLabel('Suite command').fill('Remember my review day');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect(page.getByText('Which review day?',{exact:true})).toBeVisible();
  expect(commands[0]).toMatchObject({module,provider:'gemini'});
  await page.getByLabel('Suite command').fill('Friday');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect(page.getByRole('button',{name:'Approve these exact actions',exact:true})).toBeVisible();
  expect(commands[1]).toMatchObject({module,provider:'gemini',parent_run_id:1,context:[]});
  await page.getByRole('button',{name:'Approve these exact actions',exact:true}).click();
  await expect(page.getByLabel('Suite plan review')).toContainText('saved record #10');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
});
}
