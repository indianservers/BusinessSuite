const {chromium,expect}=require('playwright/test');
const assert=require('node:assert/strict');const fs=require('node:fs');
(async()=>{
 assert(process.env.WORKFLOW_TEST_ORIGIN,'Use the disposable pytest browser runner');
 const {createServer}=await import('vite');const mode=process.env.FUNCTIONALITY_UI_MODE;const token=process.env.WORKFLOW_TEST_TOKEN;
 const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};</script><script type="module">import React from 'react';import{createRoot}from'react-dom/client';import{BrowserRouter}from'react-router-dom';import Reports from '/src/apps/crm/CRMReportBuilder.tsx';import Automation from '/src/apps/project-management/pages/AutomationAIPage.tsx';import{useAuthStore}from'/src/store/authStore.ts';import'/src/index.css';useAuthStore.setState({accessToken:${JSON.stringify(token)},isAuthenticated:true,isHydrated:true});createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement(${mode==='crm'?'Reports':'Automation'})));</script></body></html>`;
 const server=await createServer({root:process.cwd(),appType:'custom',cacheDir:process.env.WORKFLOW_TEST_CACHE,server:{host:'127.0.0.1',port:0,hmr:false,watch:null,proxy:{'/api':{target:process.env.WORKFLOW_TEST_ORIGIN,changeOrigin:true}}},plugins:[{name:'functionality-acceptance',configureServer(vite){vite.middlewares.use(async(req,res,next)=>{if(!req.url.startsWith('/__functionality.html'))return next();try{res.setHeader('Content-Type','text/html');res.end(await vite.transformIndexHtml(req.url,html));}catch(e){next(e);}});}}]});
 const headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
 async function request(path,method='GET',data){const r=await fetch(process.env.WORKFLOW_TEST_ORIGIN+'/api/v1'+path,{headers,method,body:data?JSON.stringify(data):undefined});assert(r.ok,method+' '+path+': '+r.status+' '+await r.clone().text());return r.status===204?null:r.json();}
 let browser;
 try{
  await server.listen();const origin='http://127.0.0.1:'+server.httpServer.address().port;
  // Verify each newly started preview with agent-browser before workflow tests.
  const agent='npx --yes agent-browser --session functionality-'+process.pid;
  const cli=require('node:util').promisify(require('node:child_process').exec);
  try{
   await cli(agent+' open '+origin+'/__functionality.html',{windowsHide:true,timeout:30000});
   await cli(agent+' wait --load networkidle',{windowsHide:true,timeout:30000});
   const {stdout:snapshot}=await cli(agent+' snapshot -i',{windowsHide:true,timeout:30000});
   assert(snapshot.includes((mode==='crm'?'Build a deal report':'Task automation')),'agent-browser did not render the expected UI');
  }finally{try{await cli(agent+' close',{windowsHide:true,timeout:15000});}catch{}}
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/__functionality.html');
  if(mode==='crm'){
   await page.getByRole('textbox',{name:'CRM report name',exact:true}).fill('UI currency report');
   await page.getByRole('combobox',{name:'CRM report grouping',exact:true}).selectOption('status');
   await page.getByRole('button',{name:'Save and run report',exact:true}).click();
   await expect(page.getByText('Report saved and run against your current permitted records',{exact:true})).toBeVisible();
   await expect(page.getByRole('cell',{name:'INR',exact:true})).toBeVisible();await expect(page.getByRole('cell',{name:'USD',exact:true})).toBeVisible();
   let waiting=page.waitForEvent('download');await page.getByRole('button',{name:'Export report CSV',exact:true}).click();let download=await waiting;
   const csv=fs.readFileSync(await download.path(),'utf8');assert(csv.includes('INR')&&csv.includes('USD'));assert.equal(download.suggestedFilename(),'crm-deal-report.csv');
   waiting=page.waitForEvent('download');await page.getByRole('button',{name:'Export report Excel',exact:true}).click();download=await waiting;assert.equal(fs.readFileSync(await download.path()).subarray(0,2).toString(),'PK');
   await page.reload();await expect(page.getByRole('combobox',{name:'Saved CRM report',exact:true})).toContainText('UI currency report');
   await page.getByRole('combobox',{name:'Saved CRM report',exact:true}).selectOption({label:'UI currency report'});await page.getByRole('button',{name:'Run saved report',exact:true}).click();
   await expect(page.getByRole('cell',{name:'USD',exact:true})).toBeVisible();
   await page.getByRole('textbox',{name:'CRM report currency',exact:true}).fill('USD');await expect(page.getByRole('button',{name:'Run saved report',exact:true})).toBeDisabled();
   await page.getByRole('button',{name:'Save and run report',exact:true}).click();await expect(page.getByRole('cell',{name:'USD',exact:true})).toBeVisible();await expect(page.getByRole('cell',{name:'INR',exact:true})).toHaveCount(0);
   const saved=(await request('/crm/report-builder'))[0];
   await request('/crm/report-builder/'+saved.id,'PUT',{name:'Changed in another tab',columns:saved.columns,group_by:saved.group_by,status:saved.status,currency:saved.currency,owner_user_id:saved.owner_user_id,expected_revision:saved.revision});
   await page.getByRole('button',{name:'Export report CSV',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Run it again before exporting');
   await page.getByRole('textbox',{name:'CRM report name',exact:true}).fill('Keep my report draft');await page.getByRole('button',{name:'Save and run report',exact:true}).click();
   await expect(page.getByRole('alert')).toContainText('Report changed');await expect(page.getByRole('textbox',{name:'CRM report name',exact:true})).toHaveValue('Keep my report draft');
   await page.getByRole('button',{name:'Load latest saved version',exact:true}).click();await expect(page.getByRole('textbox',{name:'CRM report name',exact:true})).toHaveValue('Changed in another tab');
   await page.getByRole('button',{name:'Restore previous draft',exact:true}).click();await expect(page.getByRole('textbox',{name:'CRM report name',exact:true})).toHaveValue('Keep my report draft');
   await page.getByRole('button',{name:'Keep draft as new report',exact:true}).click();await page.getByRole('button',{name:'Save and run report',exact:true}).click();
   await expect(page.getByText('Report saved and run against your current permitted records',{exact:true})).toBeVisible();
   assert.equal((await request('/crm/report-builder')).length,2,'Saving a copy must retain the concurrently edited original');
   page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Delete saved report',exact:true}).click();
   await expect(page.getByText('Saved definition deleted. Deal records are preserved.',{exact:true})).toBeVisible();
   assert.equal((await request('/crm/report-builder')).length,1);
   await page.getByRole('button',{name:'Restore previous draft',exact:true}).click();await page.getByRole('button',{name:'Save and run report',exact:true}).click();
   await expect(page.getByText('Report saved and run against your current permitted records',{exact:true})).toBeVisible();assert.equal((await request('/crm/report-builder')).length,2);
  }else{
   const wid=process.env.WORKFLOW_TEST_WORKSPACE,pid=Number(process.env.WORKFLOW_TEST_PROJECT);
   await page.getByRole('combobox',{name:'Automation workspace',exact:true}).selectOption(wid);
   await page.getByRole('textbox',{name:'Rule name',exact:true}).fill('UI fixed delivery date');
   await page.getByRole('combobox',{name:'Automation project',exact:true}).selectOption(String(pid));await page.getByRole('combobox',{name:'Automation action',exact:true}).selectOption('set_due_date');
   await page.getByLabel('Automation due date',{exact:true}).fill('2030-01-15');await page.getByRole('button',{name:'Save and enable rule',exact:true}).click();
   await expect(page.getByText('UI fixed delivery date',{exact:true})).toBeVisible();
   const first=await request('/project-management/projects/'+pid+'/tasks','POST',{task_key:'UI-DUE',title:'Date action from UI',start_date:'2030-01-01',due_date:'2030-01-02'});assert.equal(first.due_date,'2030-01-15');
   await request('/project-management/projects/'+pid+'/tasks','POST',{task_key:'UI-SKIP',title:'Safe skipped date',start_date:'2030-02-01',due_date:'2030-02-02'});
   await page.getByRole('button',{name:'Refresh executions',exact:true}).click();await expect(page.getByText(/1 executed · 1 skipped/)).toBeVisible();
   await page.getByRole('combobox',{name:'Execution outcome',exact:true}).selectOption('skipped');await expect(page.getByText('Due date would be before task start',{exact:true})).toBeVisible();
   await page.getByRole('button',{name:'Edit',exact:true}).click();await expect(page.getByLabel('Automation due date',{exact:true})).toHaveValue('2030-01-15');
   await page.getByLabel('Automation due date',{exact:true}).fill('2030-03-15');await page.getByRole('button',{name:'Save changes',exact:true}).click();
   await page.getByRole('button',{name:'Duplicate paused',exact:true}).click();
   await expect(page.getByText('UI fixed delivery date (copy)',{exact:true})).toBeVisible();
   const saved=await request('/project-management/workspaces/'+wid+'/automations');const copy=saved.find(r=>r.name.endsWith('(copy)'));assert.equal(copy.due_date,'2030-03-15');assert.equal(copy.enabled,false);
   await page.getByRole('button',{name:'Pause UI fixed delivery date',exact:true}).click();
   await expect(page.getByRole('button',{name:'Enable UI fixed delivery date',exact:true})).toBeVisible();
   const paused=await request('/project-management/projects/'+pid+'/tasks','POST',{task_key:'UI-PAUSED',title:'Paused rule preserved',start_date:'2030-01-01',due_date:'2030-01-02'});assert.equal(paused.due_date,'2030-01-02');
  }
  fs.mkdirSync('../.local/crm-pms-functionality',{recursive:true});await page.screenshot({path:'../.local/crm-pms-functionality/'+mode+'-1440.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:'../.local/crm-pms-functionality/'+mode+'-390.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log(mode+' real UI/API workflow and mobile passed');
 }finally{if(browser)await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
