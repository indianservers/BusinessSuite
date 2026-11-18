const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
 assert.ok(process.env.WORKFLOW_TEST_ORIGIN,'Use the disposable pytest browser runner');
 const {createServer} = await import('vite');
 const actors = JSON.parse(process.env.WORKFLOW_TEST_ACTORS);
 const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="editor"></div><div id="reviews"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};</script><script type="module">
 import React from 'react';import {createRoot} from 'react-dom/client';
 import Editor from '/src/apps/project-management/pages/WorkflowSchemesPage.tsx';
 import Reviews from '/src/apps/project-management/components/TransitionApprovals.tsx';
 import {useAuthStore} from '/src/store/authStore.ts';import '/src/index.css';
 const actors=${JSON.stringify(actors)};const root=createRoot(document.getElementById('reviews'));
 function as(name){const a=actors[name];useAuthStore.setState({accessToken:a.token,user:{id:a.id},isAuthenticated:true,isHydrated:true});}
 as('owner');createRoot(document.getElementById('editor')).render(React.createElement(Editor));
 window.workflowReviewAs=name=>{as(name);root.render(React.createElement(Reviews,{key:name+Date.now(),taskId:${Number(process.env.WORKFLOW_TEST_TASK)}}));};
 </script></body></html>`;
 const server=await createServer({root:process.cwd(),appType:'custom',cacheDir:process.env.WORKFLOW_TEST_CACHE,server:{host:'127.0.0.1',port:0,strictPort:false,open:false,hmr:false,watch:null,proxy:{'/api':{target:process.env.WORKFLOW_TEST_ORIGIN,changeOrigin:true}}},
  plugins:[{name:'approval-browser',configureServer(vite){vite.middlewares.use(async(req,res,next)=>{if(req.url!=='/__approval-test.html')return next();try{res.setHeader('Content-Type','text/html');res.end(await vite.transformIndexHtml(req.url,html));}catch(e){next(e);}});}}]});
 let browser;
 try{
  await server.listen();browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/__approval-test.html`);
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(process.env.WORKFLOW_TEST_PROJECT);
  await page.getByRole('button',{name:'Add transition',exact:true}).click();
  await page.getByRole('combobox',{name:'To status 1',exact:true}).selectOption('Done');
  await page.getByRole('button',{name:'Add approval step',exact:true}).click();
  await page.getByRole('combobox',{name:'Approver for transition 1 step 1',exact:true}).selectOption(String(actors.reviewer.id));
  await page.getByRole('checkbox',{name:'Enforce allowed transitions',exact:true}).check();
  await page.getByRole('button',{name:'Save workflow',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Workflow saved'}).waitFor();
  await page.reload();
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(process.env.WORKFLOW_TEST_PROJECT);
  assert.equal(await page.getByRole('combobox',{name:'Approver for transition 1 step 1',exact:true}).inputValue(),String(actors.reviewer.id));
  await page.evaluate(()=>window.workflowReviewAs('requester'));
  await page.getByRole('combobox',{name:'Requested status',exact:true}).selectOption('Done');
  await page.getByRole('button',{name:'Request transition approval',exact:true}).click();
  await page.getByText(/Request #.*Pending/).waitFor();
  await page.evaluate(()=>window.workflowReviewAs('reviewer'));
  await page.getByRole('button',{name:/Reject review/}).waitFor();
  await page.getByRole('textbox',{name:'Review reason',exact:true}).fill('Please revise the delivery');
  await page.getByRole('button',{name:/Reject review/}).click();
  await page.getByText(/Request #.*Rejected/).waitFor();
  await page.evaluate(()=>window.workflowReviewAs('requester'));
  await page.getByRole('combobox',{name:'Requested status',exact:true}).selectOption('Done');
  await page.getByRole('button',{name:'Request transition approval',exact:true}).click();
  await page.getByText(/Request #.*Pending/).waitFor();
  await page.evaluate(()=>window.workflowReviewAs('reviewer'));
  await page.getByRole('button',{name:/Approve review/}).click();
  await page.getByText(/Request #.*Approved/).waitFor();
  await page.evaluate(()=>window.workflowReviewAs('requester'));
  await page.getByRole('button',{name:'Apply approved transition',exact:true}).click();
  await page.getByText(/Request #.*Applied/).waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('Approval browser: configure, persist, request, reject, retry, approve, apply and mobile checks passed');
 }finally{if(browser)await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
