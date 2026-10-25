import {test,expect} from '../frontend/node_modules/playwright/test';
import {authenticateAi} from './ai-test-utils';

for(const role of ['crm_org_admin','employee'] as const){
test(`suite retries recover the same request after a lost response (${role})`,async({page})=>{
  await authenticateAi(page,role);
  const keys:string[]=[];
  await page.route('**/api/v1/ai-operator/suite/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/tools'))return route.fulfill({json:{tools:[]}});
    if(path.endsWith('/runs'))return route.fulfill({json:{items:[]}});
    if(path.endsWith('/commands')){
      const body=route.request().postDataJSON();keys.push(body.request_key);
      if(keys.length===1)return route.abort('failed');
      return route.fulfill({json:{id:1,status:'answered',command:body.text,plan:{summary:'Recovered original result.',steps:[]},receipts:[]}});
    }
    return route.fulfill({json:{items:[]}});
  });
  await page.route('**/api/v1/ai-operator/providers*',route=>route.fulfill({json:{items:[{provider:'gemini',enabled:true,data_sharing_allowed:true,model:'test'}]}}));
  await page.route('**/api/v1/project-management/workspaces',route=>route.fulfill({json:[]}));
  await page.goto('/ai-agents/operator');
  await page.getByLabel('Suite command').fill('Summarize selected work');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Retry the unchanged message');
  await expect(page.getByLabel('Suite command')).toHaveValue('Summarize selected work');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect(page.getByText('Recovered original result.',{exact:true})).toBeVisible();
  expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
});
}

test('agent preserves selected-task context, editable voice and follow-up identity',async({page})=>{
  await authenticateAi(page,'crm_org_admin');
  await page.addInitScript(()=>{(window as any).SpeechRecognition=class {onresult:any;onend:any;start(){this.onresult({results:[[{transcript:'Set this task priority to high'}]]});this.onend();}stop(){this.onend();}abort(){}};});
  const commands:any[]=[];
  await page.route('**/api/v1/project-management/projects*',r=>r.fulfill({json:[{id:42,name:'Agent QA',workspace_id:null}]}));
  await page.route('**/api/v1/project-management/workspaces',r=>r.fulfill({json:[]}));
  await page.route('**/api/v1/ai-operator/local-context*',r=>r.fulfill({json:{tasks:[{id:7,task_key:'QA-7',title:'Review'}]}}));
  await page.route('**/api/v1/ai-operator/providers*',r=>r.fulfill({json:{items:[{provider:'gemini',enabled:true,data_sharing_allowed:true,model:'test'}]}}));
  await page.route('**/api/v1/ai-operator/suite/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/tools'))return route.fulfill({json:{tools:[]}});
    if(path.endsWith('/commands')){
      const body=route.request().postDataJSON();commands.push(body);
      return route.fulfill({json:{id:commands.length,status:commands.length===1?'needs_clarification':'awaiting_approval',command:body.text,plan_hash:'a'.repeat(64),
        plan:{summary:'Review the task change',question:commands.length===1?'Which priority?':null,steps:[]},receipts:[]}});
    }
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/ai-agents/operator');
  await page.getByLabel('Agent project').selectOption('42');
  await page.getByLabel('Select QA-7').check();
  await page.getByRole('button',{name:'Voice command',exact:true}).click();
  await expect(page.getByLabel('Suite command')).toHaveValue('Set this task priority to high');
  await page.getByLabel('Suite command').fill('Change this task priority');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect(page.getByText('Which priority?',{exact:true})).toBeVisible();
  expect(commands[0]).toMatchObject({project_id:42,task_ids:[7],input_mode:'voice',provider:'gemini'});
  await page.getByLabel('Suite command').fill('High please');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect.poll(()=>commands.length).toBe(2);
  expect(commands[1]).toMatchObject({parent_run_id:1,text:'High please',input_mode:'text'});
  await page.getByRole('button',{name:'Revise plan',exact:true}).click();
  await page.getByLabel('Suite command').fill('Use urgent priority instead');
  await page.getByRole('button',{name:'Ask Gemini',exact:true}).click();
  await expect.poll(()=>commands.length).toBe(3);
  expect(commands[2]).toMatchObject({parent_run_id:2,text:'Use urgent priority instead'});
});
