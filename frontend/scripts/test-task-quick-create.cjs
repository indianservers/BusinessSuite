const path=require('node:path');

const fs=require('node:fs/promises');

const assert=require('node:assert/strict');

const {chromium}=require('playwright');



(async()=>{

  const {createServer}=await import('vite');

  const react=(await import('@vitejs/plugin-react')).default;

  const root=path.resolve(__dirname,'..');

  const server=await createServer({configFile:false,root,cacheDir:path.join(root,"node_modules/.vite-pipeline-qa"),plugins:[react(),{name:"pipeline-qa-entry",configureServer(server){server.middlewares.use(async(req,res,next)=>{if(req.url.startsWith('/pipeline-ui-qa')){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml(req.url,'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"/></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/pipeline-ui-qa.tsx"></script></body></html>'));}else next();});}}],resolve:{alias:{'@':path.join(root,'src')},dedupe:['react','react-dom']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/*']}},optimizeDeps:{entries:['scripts/fixtures/pipeline-ui-qa.tsx'],include:['react','react-dom/client','react/jsx-runtime','@dnd-kit/core','@dnd-kit/sortable','@dnd-kit/utilities','react-router-dom','lucide-react','@radix-ui/react-dialog','@tanstack/react-query','react-hook-form','@hookform/resolvers/zod']}});

  await server.listen();

  const base=`http://127.0.0.1:${server.httpServer.address().port}`;

  const browser=await chromium.launch({headless:true});

  const page=await browser.newPage({viewport:{width:1440,height:900}});

  const errors=[];page.on('pageerror',e=>errors.push(e.message));

  const output=path.resolve(root,'../docs/qa/pipeline-ui');await fs.mkdir(output,{recursive:true});

  async function open(query=''){await page.goto(`${base}/pipeline-ui-qa${query}`);if(query.includes('editor'))await page.getByLabel('Pipeline name',{exact:true}).waitFor();else await page.getByRole('heading',{name:query.includes('sales')?'Draft':'Qualified',exact:true}).waitFor();}

  async function move(title,destination){const card=page.locator('.pipeline-card').filter({has:page.getByRole('button',{name:title,exact:true})});await card.locator('summary').click();await card.getByLabel(`Destination for ${title}`,{exact:true}).selectOption(destination);}

  try {

    const calls=[];const savedViews=[];let savedPreferences;let namedBoards=[{id:1,name:"Delivery board"},{id:2,name:"QA named pipeline"}];

    let taskStatus="To Do",candidateStatus="Applied";

    await page.route('**/api/v1/**',async route=>{

      const request=route.request(),url=new URL(request.url()),p=url.pathname.replace('/api/v1','');

      const method=request.method();calls.push({path:p,query:url.search,method,body:request.postDataJSON?.()});

      const pipeline={id:1,name:"Sales pipeline",is_default:true};

      const stages=[{id:1,pipeline_id:1,name:"Qualified",position:1,probability:20,color:"#278a48"},{id:2,pipeline_id:1,name:"Proposal",position:2,probability:60,color:"#9963aa"}];

      let data=[];

      if(p.startsWith('/pipeline-workspaces/')&&p.endsWith('/views')){if(method==='POST'){const body=request.postDataJSON();const view={...body,id:String(savedViews.length+1)};savedViews.push(view);data=view;}else data={preferences:savedPreferences,views:savedViews,can_share:true};}
      else if(p.startsWith('/pipeline-workspaces/')&&p.endsWith('/preferences')){savedPreferences=request.postDataJSON();data=savedPreferences;}
      else if(p.startsWith('/pipeline-workspaces/')&&p.endsWith('/history'))data={items:[]};
      else if(p.startsWith('/pipeline-workspaces/')&&p.endsWith('/ages'))data={items:{}};
      else if(p==='/project-management/projects/1/boards'){if(method==='POST'){data={id:2,name:request.postDataJSON().name};namedBoards.push(data);}else data={items:namedBoards};}
      else if(p==='/crm/deal-workspace/pipelines')data={items:[pipeline],total:1,page:1,pages:1};

      else if(p==='/crm/deal-workspace/pipeline-stages')data={items:stages,total:2,page:1,pages:1};

      else if(p==='/crm/deal-workspace/grid/query')data={rows:[{id:10,name:"CRM adapter deal",stage_id:1,pipeline_id:1,amount:25000,currency:"INR",company_name:"Acme",owner_name:"QA Owner"}],total:1,page:1,pageTotal:1,pageSize:100,permissions:{edit:true},context:{summary:{stages:[{stage_id:1,currency:"INR",count:1,amount:25000}]}}};

      else if(p==='/crm/productivity/deals/10/stages')data={version:1,current_stage_id:1,values:{},stages:stages.map(s=>({...s,required:[],is_won:false,is_lost:false,missing:[]}))};

      else if(p==='/crm/productivity/deals/10/transition')data={success:true};

      else if(p==='/project-management/projects/1')data={id:1,name:"Delivery",project_key:"DEL",can_manage_tasks:true,can_edit_project:true};

      else if(p==='/project-management/projects/1/board')data={id:Number(url.searchParams.get("board_id")||1),project_id:1,name:url.searchParams.get("board_id")==="2"?"QA named pipeline":"Delivery board",columns:[{id:1,board_id:1,name:"To Do",status_key:"TODO",position:0,tasks:taskStatus==='To Do'?[{id:11,title:"PMS adapter task",task_key:"DEL-1",status:taskStatus,priority:"High",column_id:1,position:0}]:[],task_count:taskStatus==='To Do'?1:0},{id:2,board_id:1,name:"Done",status_key:"DONE",position:1,tasks:taskStatus==='Done'?[{id:11,title:"PMS adapter task",task_key:"DEL-1",status:taskStatus,priority:"High",column_id:2,position:0}]:[],task_count:taskStatus==='Done'?1:0}]};

      else if(p==='/project-management/task-studio/options')data={people:[{id:7,name:'Project member'}],can_edit:true};
      else if(p==='/project-management/task-studio/tasks/11')data={version:"qa-v1"};

      else if(p==='/project-management/my-work/tasks/11/arrange'){taskStatus=request.postDataJSON().status;data={id:11,version:"qa-v2"};}

      else if(p==='/recruitment/jobs')data=[{id:1,title:"Engineer",status:"Open",openings:1}];

      else if(p==='/recruitment/candidates')data=[{id:12,name:"HRMS adapter candidate",email:"candidate@example.test",status:candidateStatus,job:{title:"Engineer"}}];

      else if(p==='/recruitment/candidates/12/status'){candidateStatus=url.searchParams.get('status');data={message:"Updated"};}

      else if(p==='/srm/sales-orders')data=[{id:13,order_number:"SO-ADAPTER",status:"draft",total_amount:10000,currency:"INR"}];

      else if(p.includes('deal-workspace/'))data={items:[],total:0,page:1,pages:1};

      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});

    });

    await page.goto(`${base}/pipeline-ui-qa?integration=pms`);await page.getByRole('button',{name:'PMS adapter task',exact:true}).waitFor();

    await move('PMS adapter task','2');await page.locator('.pipeline-lane').filter({has:page.getByRole('heading',{name:'Done',exact:true})}).getByRole('button',{name:'PMS adapter task',exact:true}).waitFor();

    assert.ok(calls.some(c=>c.path==='/project-management/my-work/tasks/11/arrange'&&c.body?.version==='qa-v1'&&c.body?.status==='Done'));

    await page.getByLabel('Project pipeline',{exact:true}).selectOption('2');await page.getByLabel('Customize project pipeline',{exact:true}).click();await page.getByRole('dialog').getByLabel('Pipeline name',{exact:true}).waitFor();assert.equal(await page.getByRole('dialog').getByLabel('Pipeline name',{exact:true}).inputValue(),'QA named pipeline');assert.ok(calls.some(c=>c.path==='/project-management/projects/1/board'&&c.query.includes('board_id=2')));await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();
    await page.getByRole('button',{name:'Task',exact:true}).click();
    const quick=page.getByRole('dialog');
    await quick.getByLabel('Task title *',{exact:true}).fill('Complete quick task');
    await quick.getByLabel('Description',{exact:true}).fill('Acceptance criteria');
    await quick.getByLabel('Priority',{exact:true}).selectOption('High');
    await quick.getByLabel('Assignee',{exact:true}).selectOption('7');
    await quick.getByLabel('Task type',{exact:true}).selectOption('Bug');
    await quick.getByLabel('Start date',{exact:true}).fill('2026-11-04');
    await quick.getByLabel('Due date',{exact:true}).fill('2026-11-10');
    await quick.getByLabel('Estimate (hours)',{exact:true}).fill('2.5');
    await quick.getByLabel('Story points',{exact:true}).fill('3');
    await quick.getByRole('button',{name:'Create task',exact:true}).click();
    await quick.waitFor({state:'detached'});
    const created=calls.find(c=>c.path==='/project-management/projects/1/tasks'&&c.method==='POST');
    assert.equal(created.body.title,'Complete quick task');assert.equal(created.body.assignee_user_id,7);assert.equal(created.body.priority,'High');assert.equal(created.body.work_type,'Bug');assert.equal(created.body.estimated_hours,2.5);assert.equal(created.body.story_points,3);assert.equal(created.body.due_date,'2026-11-10');
    await page.screenshot({path:path.join(output,'pms-integration.png'),fullPage:true});

    console.log('Quick create task fields and native payload passed');
  } finally { await browser.close(); await server.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
