// Real UI and disposable API. Invoked only by the pytest fixture runner.
const {chromium,expect}=require('playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 assert(process.env.WORKFLOW_TEST_ORIGIN,'Run through the disposable backend fixture');
 const {createServer}=await import('vite');const token=process.env.WORKFLOW_TEST_TOKEN;const pid=Number(process.env.WORKFLOW_TEST_PROJECT);
 const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};</script><script type="module">import React from 'react';import{createRoot}from'react-dom/client';import Panel from '/src/apps/project-management/components/AdvancedSchedulingPanel.tsx';import{useAuthStore}from'/src/store/authStore.ts';import'/src/index.css';useAuthStore.setState({accessToken:${JSON.stringify(token)},isAuthenticated:true,isHydrated:true});createRoot(document.getElementById('root')).render(React.createElement(Panel,{projectId:${pid},canManage:true,onApplied:()=>{}}));</script></body></html>`;
 const server=await createServer({root:process.cwd(),appType:'custom',cacheDir:process.env.WORKFLOW_TEST_CACHE,server:{host:'127.0.0.1',port:0,hmr:false,watch:null,proxy:{'/api':{target:process.env.WORKFLOW_TEST_ORIGIN,changeOrigin:true}}},plugins:[{name:'schedule-acceptance',configureServer(vite){vite.middlewares.use(async(req,res,next)=>{if(req.url!=='/__scheduling.html')return next();try{res.setHeader('Content-Type','text/html');res.end(await vite.transformIndexHtml(req.url,html));}catch(e){next(e);}});}}]});
 let browser;
 try{
  await server.listen();const origin='http://127.0.0.1:'+server.httpServer.address().port;
  console.log('Disposable scheduling UI server started');
  // Verify each newly started preview with agent-browser before workflow tests.
  const agent='npx --yes agent-browser --session functionality-'+process.pid;
  const cli=require('node:util').promisify(require('node:child_process').exec);
  try{
   await cli(agent+' open '+origin+'/__scheduling.html',{windowsHide:true,timeout:30000});
   await cli(agent+' wait --load networkidle',{windowsHide:true,timeout:30000});
   const {stdout:snapshot}=await cli(agent+' snapshot -i',{windowsHide:true,timeout:30000});
   assert(snapshot.includes('Advanced scheduling'),'agent-browser did not render the expected UI');
  }finally{try{await cli(agent+' close',{windowsHide:true,timeout:15000});}catch{}}
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/__scheduling.html');await expect(page.getByText('Critical',{exact:true}).first()).toBeVisible();
  await page.getByRole('textbox',{name:'Baseline name',exact:true}).fill('UI accepted baseline');await page.getByRole('button',{name:'Capture baseline',exact:true}).click();
  await expect(page.getByText('Baseline captured. Previous baselines are retained.',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Move scheduled task',exact:true}).selectOption(process.env.WORKFLOW_TEST_TASK);
  await page.getByLabel('Planned start date',{exact:true}).fill('2026-11-12');await page.getByLabel('Planned due date',{exact:true}).fill('2026-11-13');
  await page.getByRole('textbox',{name:'Project holidays',exact:true}).fill('2026-11-16');await page.getByRole('button',{name:'Preview dependency plan',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Impact preview · 2 tasks change',exact:true})).toBeVisible();
  await expect(page.getByText(/UI-B:.*2026-11-17/)).toBeVisible();
  await page.getByRole('button',{name:'Apply dependency plan',exact:true}).click();await expect(page.getByText('2 task schedules updated',{exact:true})).toBeVisible();
  const headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
  const get=async()=>{const r=await fetch(process.env.WORKFLOW_TEST_ORIGIN+'/api/v1/project-management/projects/'+pid+'/schedule-analysis',{headers});assert.equal(r.status,200);return r.json();};
  const data=await get();assert.equal(data.variance.find(t=>t.task_key==='UI-B').due_variance_days,6);
  await page.reload();await expect(page.getByRole('combobox',{name:'Compare schedule baseline',exact:true})).toContainText('UI accepted baseline');
  await page.getByRole('textbox',{name:'Baseline name',exact:true}).fill('Keep this draft');
  const moved=await fetch(process.env.WORKFLOW_TEST_ORIGIN+'/api/v1/project-management/tasks/'+process.env.WORKFLOW_TEST_TASK+'/schedule',{method:'PATCH',headers,body:JSON.stringify({start_date:'2026-11-11',due_date:'2026-11-12'})});assert.equal(moved.status,200,await moved.text());
  await page.getByRole('button',{name:'Capture baseline',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Schedule changed');
  await expect(page.getByRole('textbox',{name:'Baseline name',exact:true})).toHaveValue('Keep this draft');
  await page.getByRole('button',{name:'Reload schedule analysis',exact:true}).click();await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Capture baseline',exact:true})).toBeEnabled();await page.getByRole('button',{name:'Capture baseline',exact:true}).click();
  await expect(page.getByText('Baseline captured. Previous baselines are retained.',{exact:true})).toBeVisible();
  assert.equal((await get()).baselines.length,2,'The retry must preserve the first baseline');
  const fs=require('node:fs');fs.mkdirSync('../.local/crm-pms-functionality',{recursive:true});await page.screenshot({path:'../.local/crm-pms-functionality/scheduling-1440.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:'../.local/crm-pms-functionality/scheduling-390.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('Scheduling UI/API: baseline, calendar, preview, atomic apply, persisted variance, stale rejection/draft retention and mobile passed');
 }finally{if(browser)await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
