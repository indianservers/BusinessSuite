import { test, expect, type Page } from '../frontend/node_modules/playwright/test';
import { authenticateAi } from './ai-test-utils';

const makeRun=(id:number,status='answered')=>({id,command:`Customer request ${id}`,status,plan_hash:'a'.repeat(64),plan:{summary:`Review ${id}`,steps:[]},receipts:[],result:{request:{module:'CRM',provider:'local'}}});
async function setup(page:Page,history:any[],handle?:(route:any,path:string)=>Promise<boolean>){
  await authenticateAi(page);
  await page.route('**/api/v1/project-management/workspaces',route=>route.fulfill({json:[]}));
  await page.route('**/api/v1/project-management/projects*',route=>route.fulfill({json:[]}));
  await page.route('**/api/v1/ai-operator/suite/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    if(handle&&await handle(route,path))return;
    if(path.endsWith('/runs')){
      const search=(url.searchParams.get('search')||'').toLowerCase(),status=url.searchParams.get('status');
      const before=Number(url.searchParams.get('before_id')||Infinity),limit=Number(url.searchParams.get('limit')||50);
      const rows=history.filter(row=>row.id<before&&(!status||row.status===status)&&(!search||row.command.toLowerCase().includes(search))).sort((a,b)=>b.id-a.id);
      return route.fulfill({json:{items:rows.slice(0,limit),has_more:rows.length>limit,next_before_id:rows.length>limit?rows[limit-1].id:null}});
    }
    if(path.endsWith('/tools'))return route.fulfill({json:{tools:[]}});
    if(path.endsWith('/briefing'))return route.fulfill({json:{today:'2026-11-17',generated_at:'2026-11-17T00:00:00Z',priorities:[],delivery_risks:[],coverage:[],limited:true,note:'Test sample'}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/ai-agents/operator');
}

test('request history searches, filters and loads older pages',async({page})=>{
  const rows=Array.from({length:14},(_,index)=>({...makeRun(index+1,index%2?'answered':'succeeded'),command:index%2?'Customer follow up':'Inventory check'}));
  await setup(page,rows);
  const history=page.getByLabel('Request history');
  await expect(history.getByRole('button',{name:/Review /})).toHaveCount(12);
  await history.getByRole('button',{name:'Load older requests'}).click();
  await expect(history.getByRole('button',{name:/Review /})).toHaveCount(14);
  await expect(history.getByRole('button',{name:'Load older requests'})).toHaveCount(0);
  await history.getByLabel('Search request history').fill('CUSTOMER');
  await history.getByLabel('Request status filter').selectOption('answered');
  await expect(history.getByRole('button',{name:/Review /})).toHaveCount(7);
  await history.getByLabel('Request status filter').selectOption('failed');
  await expect(history.getByText('No matching requests.')).toBeVisible();
});

test('planning retries recover lost responses without reusing an approval',async({page})=>{
  const failed={...makeRun(44,'failed'),plan:null,command:'Failed planning',error_code:'PROVIDER_TIMEOUT',result:{can_retry_planning:true,planning_issue:'Provider unavailable',request:{module:'CRM',provider:'gemini'}}};
  const retries:any[]=[];
  await setup(page,[failed],async(route,path)=>{
    if(!path.endsWith('/retry-planning'))return false;
    retries.push(route.request().postDataJSON());
    if(retries.length===1){await route.abort('failed');return true;}
    await route.fulfill({json:{...makeRun(45,'awaiting_approval'),plan:{summary:'Fresh review',steps:[{tool:'crm.create_task',payload:{title:'Reviewed new task'}}]}}});return true;
  });
  await page.getByLabel('Request history').getByRole('button',{name:/Failed planning/}).click();
  await page.getByRole('button',{name:'Retry planning',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'Retry the unchanged message'})).toBeVisible();
  await page.getByRole('button',{name:'Retry planning',exact:true}).click();
  await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
  expect(retries).toHaveLength(2);expect(retries[0]).toEqual(retries[1]);
  expect(retries[0].provider).toBe('original');
});

test('safe checkpoints resume and confirmed receipts download',async({page})=>{
  const paused={...makeRun(43,'paused'),can_resume:true,plan:{summary:'Resume safe checkpoint',steps:[{tool:'crm.create_task',payload:{title:'Second task'}}]},receipts:[{step:1,tool:'crm.create_task',record_id:9,status:'succeeded'}]};
  const resumed:any[]=[];
  await setup(page,[paused],async(route,path)=>{
    if(path.endsWith('/resume')){resumed.push(route.request().postDataJSON());await route.fulfill({json:{...paused,status:'succeeded'}});return true;}
    if(path.endsWith('/receipt')){await route.fulfill({json:{version:'action-agent-receipt-v1',id:43,receipts:paused.receipts}});return true;}
    return false;
  });
  await page.getByLabel('Request history').getByRole('button',{name:/Resume safe checkpoint/}).click();
  await page.getByRole('button',{name:'Resume from checkpoint'}).click();
  await expect(page.getByLabel('Suite plan review')).toContainText('succeeded');
  expect(resumed).toEqual([{plan_hash:'a'.repeat(64)}]);
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download execution receipt'}).click();
  expect((await downloaded).suggestedFilename()).toBe('action-agent-receipt-43.json');
});

test('an uncertain checkpoint without a server grant cannot resume',async({page})=>{
  const paused={...makeRun(43,'needs_reconciliation'),can_resume:false};
  await setup(page,[paused]);
  await page.getByLabel('Request history').getByRole('button',{name:/Review 43/}).click();
  await expect(page.getByLabel('Suite plan review')).toContainText('needs reconciliation');
  await expect(page.getByRole('button',{name:'Resume from checkpoint'})).toHaveCount(0);
});
