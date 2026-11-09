const path=require('node:path'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('playwright/test');const expect=base.configure({timeout:20000});
(async()=>{
 process.chdir(process.env.TASK_ACCESS_ROOT||path.resolve(__dirname,'..'));
 const {createServer}=await import('vite');const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage(),writes=[],errors=[];let scenario='empty',held,hold=true;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{
   const r=route.request(),u=new URL(r.url()),p=u.pathname;let data={items:[],fields:[],types:[]};
   if(p.endsWith('/task-studio/projects'))data=scenario==='empty'?[]:[{id:86,name:'Read only',can_manage_tasks:false},{id:87,name:'Editable',can_manage_tasks:true}];
   else if(p.endsWith('/workspaces'))data=[{id:3,name:'QA workspace'}];
   else if(p.endsWith('/general-scope'))data={id:90,name:'General tasks',workspace_id:3,is_task_collection:true,can_manage_tasks:true};
   else if(p.endsWith('/task-studio/options')){if(hold)await new Promise(resolve=>held=resolve);data={people:[{id:1,name:'Current Person',email:'self@example.test'}],teams:[],batches:[],reviewers:[],can_edit:u.searchParams.get('project_id')!=='86',can_add_existing:false};}
   else if(r.method()==='POST'&&/task-studio\/projects\/\d+\/tasks$/.test(p)){writes.push({path:p,...r.postDataJSON()});data={task:{id:501,project_id:Number(p.match(/projects\/(\d+)/)[1]),...r.postDataJSON().task},can_edit:true,protected_ids:[],assignment:r.postDataJSON().assignment,version:1};}
   await route.fulfill({json:data});
  });
  await page.route('**/assignment-qa*',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/task-assignment-qa.tsx");</script>'}));
  const url='http://127.0.0.1:'+server.httpServer.address().port+'/assignment-qa?no-project&compact-modal';
  await page.goto(url);const title=page.getByLabel('Task Title',{exact:true}),location=page.getByLabel('Task location',{exact:true});
  const create=()=>page.locator('[data-smart-create-footer]').getByRole('button',{name:'Create Task',exact:true});
  await expect(location).toBeEnabled();await expect(title).toBeEnabled();await expect(page.getByText(/Your project role allows viewing/)).toHaveCount(0);
  await location.selectOption('general');await page.getByLabel('General task workspace').selectOption('3');await expect.poll(()=>!!held).toBe(true);
  await title.fill('Admin general task');await expect(create()).toBeDisabled();await expect(location).toBeEnabled();hold=false;held();held=null;
  await expect(create()).toBeEnabled();await create().click();await expect.poll(()=>writes.length).toBe(1);assert.match(writes[0].path,/projects\/90\/tasks$/);
  scenario='permissions';await page.goto(url);await expect(page.getByLabel('Project',{exact:true})).toHaveValue('87');await expect(create()).toBeEnabled();
  await page.getByLabel('Project',{exact:true}).selectOption('86');await expect(page.getByText(/Your project role allows viewing/)).toBeVisible();await expect(create()).toBeDisabled();await expect(page.getByLabel('Project',{exact:true})).toBeEnabled();
  hold=true;await page.getByLabel('Project',{exact:true}).selectOption('87');await expect.poll(()=>!!held).toBe(true);await expect(create()).toBeDisabled();
  await title.fill('Allowed project task');hold=false;held();held=null;await expect(create()).toBeEnabled();await create().click();await expect.poll(()=>writes.length).toBe(2);assert.match(writes[1].path,/projects\/87\/tasks$/);assert.deepEqual(errors,[]);
  console.log('PASS: empty/loading scopes stay usable; admin creates general/project tasks; real denial blocks save while allowing project switching; stale options cannot enable submission.');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
