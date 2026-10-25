import { test, expect } from '../frontend/node_modules/playwright/test';
import { authenticateAi } from './ai-test-utils';

async function setup(page:any){
  await authenticateAi(page);let next=10,items:any[]=[],runs:any[]=[],previews=0,approvals=0;
  const tasks=[{id:7,project_id:1,task_key:'WEB-1',title:'Build checkout experience',status:'In Progress',priority:'High',estimated_hours:16,checklist:[],dependencies:[]},
    {id:8,project_id:1,task_key:'WEB-2',title:'Verify release readiness',status:'Blocked',priority:'Medium',checklist:[{id:4,title:'QA review',is_completed:false}],dependencies:[{id:2,source:7,target:8}]}];
  await page.route('**/api/v1/**',async(route:any)=>{
    const request=route.request(),path=new URL(request.url()).pathname,method=request.method(),body=request.postDataJSON();
    const context={project:{id:1,name:'Orion · Customer experience',project_key:'ORION',workspace_id:null},tasks,collaborators:[{id:701,name:'Alice Morgan',email:'alice@example.com'},{id:702,name:'Noah Chen',email:'noah@example.com'}],sprints:[],tasks_complete:true,collaborators_complete:true};
    if(path==='/api/v1/project-management/projects')return route.fulfill({json:[{id:1,name:context.project.name,project_key:'ORION'}]});
    if(path.endsWith('/ai-operator/local-context'))return route.fulfill({json:context});
    if(path.endsWith('/workbench/items')){
      if(method==='POST'){const row={...body,id:next++,key:`key-${next}`,revision:1};items.push(row);return route.fulfill({json:row});}
      return route.fulfill({json:{items}});
    }
    if(/\/workbench\/items\/\d+$/.test(path)){
      const id=Number(path.split('/').at(-1));if(method==='DELETE'){items=items.filter(r=>r.id!==id);return route.fulfill({json:{deleted:true}});}
      const row={...body,id,revision:body.revision+1};items=items.map(r=>r.id===id?row:r);return route.fulfill({json:row});
    }
    if(path.endsWith('/workbench/insights'))return route.fulfill({json:{project:context.project,risks:[{task_id:8,task_key:'WEB-2',title:tasks[1].title,reasons:['blocked','unassigned']}],status_counts:{'In Progress':1,Blocked:1},workload:[{user_id:701,email:'alice@example.com',allocated_hours:32,capacity_hours:40,available_hours:8,skills:['Product design'],away:false},{user_id:702,email:'noah@example.com',allocated_hours:12,capacity_hours:40,available_hours:28,skills:['QA','Accessibility'],away:false}],assumptions:'Authorized project workload.'}});
    if(path.endsWith('/workbench/metrics'))return route.fulfill({json:{providers:['openai','gemini','claude'].map(provider=>({provider,requests:0,input_tokens:0,output_tokens:0,unpriced_requests:0,priced_cost:0,average_latency_ms:0})),routing:{browser:12,cloud:2},run_status:{succeeded:4,awaiting_approval:1},evaluations:[],evaluation_passes:0}});
    if(path.endsWith('/workbench/plans/preview')){previews++;const run={id:50,project_id:1,command:body.plan.summary,status:'awaiting_approval',plan:body.plan,plan_hash:'a'.repeat(64),selection:[7],execution_mode:body.mode,revision:1,background:true,result:null};runs=[run];return route.fulfill({json:run});}
    if(path.endsWith('/ai-operator/runs/50/approve')){approvals++;runs=runs.map(r=>({...r,status:'succeeded',result:{success:true,receipts:[{step:1,tool:'update_task',task_id:7,record_id:7}]}}));return route.fulfill({json:runs[0]});}
    if(path.endsWith('/ai-operator/runs/50/events'))return route.fulfill({json:{items:[],next_cursor:0,run:runs[0]}});
    if(path.endsWith('/ai-operator/runs'))return route.fulfill({json:{items:runs}});
    if(path.endsWith('/ai-operator/providers')||path.endsWith('/brain/sessions'))return route.fulfill({json:{items:[]}});
    if(path.endsWith('/workbench/search'))return route.fulfill({json:{items:[{id:8,key:'WEB-2',title:tasks[1].title,status:'Blocked',href:'/pms/projects/1/tasks/8'}]}});
    return route.fallback();
  });
  await page.goto('/pms/assistant');
  await expect(page.getByRole('heading',{name:'Your workspace',exact:true})).toBeVisible();
  await expect(page.getByText('WEB-1',{exact:true})).toBeVisible();
  return {previews:()=>previews,approvals:()=>approvals};
}

test('studio editor prepares real steps and requires a separate approval',async({page})=>{
  const calls=await setup(page);
  await page.getByRole('button',{name:'Plan builder',exact:true}).click();
  await page.getByRole('button',{name:'Add action',exact:true}).click();
  await page.getByRole('button',{name:'Validate & prepare approval'}).click();
  await expect(page.getByRole('button',{name:'Approve this exact plan'})).toBeVisible();
  expect(calls.previews()).toBe(1);expect(calls.approvals()).toBe(0);
  await page.getByRole('button',{name:'Approve this exact plan'}).click();
  await expect(page.getByRole('button',{name:'Prepare undo'})).toBeVisible();expect(calls.approvals()).toBe(1);
});

test('project memory can be added, corrected and forgotten',async({page})=>{
  await setup(page);await page.getByRole('button',{name:'Project memory',exact:true}).click();
  await page.getByLabel('Project memory text').fill('Orion means the mobile release.');await page.getByRole('button',{name:'Remember this',exact:true}).click();
  await expect(page.getByText('Orion means the mobile release.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:/Edit memory/}).click();await page.getByLabel('Project memory text').fill('Orion means the customer release.');
  await page.getByRole('button',{name:'Save memory correction'}).click();await expect(page.getByText('Orion means the customer release.',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:/Forget memory/}).click();await expect(page.getByText('Orion means the customer release.',{exact:true})).toHaveCount(0);
});

test('studio uses the local command model and collects follow-ups without a provider',async({page})=>{
  const calls=await setup(page);
  await page.getByRole('button',{name:'Conversation',exact:true}).click();
  await page.getByLabel('Assistant studio message').fill('create task');
  await page.getByRole('button',{name:'Send studio message',exact:true}).click();
  await expect(page.getByText('What should the task be called?',{exact:false})).toBeVisible();
  await page.getByLabel('Assistant studio message').fill('Fix the release checklist');
  await page.getByRole('button',{name:'Send studio message',exact:true}).click();
  await expect(page.getByText('What unique key should I use?',{exact:false})).toBeVisible();
  expect(calls.previews()).toBe(0);
});

test('this-task scheduling keeps the selected task on the local route',async({page})=>{
  await setup(page);
  await page.getByRole('checkbox',{name:/WEB-1/}).check();
  await page.getByRole('button',{name:'Conversation',exact:true}).click();
  await page.getByLabel('Assistant studio message').fill('schedule this task for next Monday');
  const preview=page.waitForRequest(r=>r.url().endsWith('/workbench/plans/preview'));
  await page.getByRole('button',{name:'Send studio message',exact:true}).click();
  const body=(await preview).postDataJSON();
  expect(body.plan.steps).toHaveLength(1);
  expect(body.plan.steps[0]).toMatchObject({tool:'schedule_task',task_id:7});
  expect(body.plan.steps[0].due_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByRole('button',{name:'Approve this exact plan'})).toBeVisible();
});

test('voice transcripts stay editable and preserve voice provenance in local plans',async({page})=>{
  await page.addInitScript(()=>{
    (window as any).SpeechRecognition=class{
      onresult:any;onend:any;onerror:any;
      start(){this.onresult?.({results:[[{transcript:'set priority to high'}]]});this.onend?.();}
      stop(){this.onend?.();}abort(){}
    };
  });
  const calls=await setup(page);
  await page.getByRole('checkbox',{name:/WEB-1/}).check();
  await page.getByRole('button',{name:'Conversation',exact:true}).click();
  await page.getByRole('button',{name:'Start voice input',exact:true}).click();
  await expect(page.getByLabel('Assistant studio message')).toHaveValue('set priority to high');
  expect(calls.previews()).toBe(0);
  const request=page.waitForRequest(r=>r.url().endsWith('/workbench/plans/preview'));
  await page.getByRole('button',{name:'Send studio message',exact:true}).click();
  expect((await request).postDataJSON().input_mode).toBe('voice');
  await expect(page.getByRole('button',{name:'Approve this exact plan'})).toBeVisible();
  expect(calls.approvals()).toBe(0);
});

test('studio desktop and mobile layouts expose connected context without overflow',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.setViewportSize({width:1600,height:1050});await setup(page);
  await page.screenshot({path:'../docs/qa/assistant-studio-desktop.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Delivery insights',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Who has room to help?'})).toBeVisible();
  await page.screenshot({path:'../docs/qa/assistant-studio-insights.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Conversation',exact:true}).click();
  await page.screenshot({path:'../docs/qa/assistant-studio-chat.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Switch to dark theme',exact:true}).click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.screenshot({path:'../docs/qa/assistant-studio-dark.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'Switch to light theme',exact:true}).click();
  await page.getByRole('button',{name:'Delivery insights',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'Ask your project'})).toBeVisible();
  await expect.poll(async()=>page.locator('.assistant-studio').evaluate(el=>el.getBoundingClientRect().width)).toBeGreaterThan(330);
  await page.screenshot({path:'../docs/qa/assistant-studio-mobile.png',fullPage:true,animations:'disabled'});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);expect(overflow).toBe(false);
});
