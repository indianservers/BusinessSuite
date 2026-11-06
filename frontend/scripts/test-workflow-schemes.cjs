// Runs against the disposable API started by test_pms_workflow_schemes.py.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  assert.ok(process.env.WORKFLOW_TEST_ORIGIN, 'Use the disposable pytest browser runner');
  const { createServer } = await import('vite');
  const token = process.env.WORKFLOW_TEST_TOKEN;
  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script>window.__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};</script><script type="module">
    import React from 'react'; import {createRoot} from 'react-dom/client';
    import WorkflowSchemesPage from '/src/apps/project-management/pages/WorkflowSchemesPage.tsx';
    import {useAuthStore} from '/src/store/authStore.ts'; import '/src/index.css';
    useAuthStore.setState({accessToken:${JSON.stringify(token)},isAuthenticated:true,isHydrated:true});
    createRoot(document.getElementById('root')).render(React.createElement(WorkflowSchemesPage));
  </script></body></html>`;
  const server = await createServer({
    root: process.cwd(), appType: 'custom', cacheDir: process.env.WORKFLOW_TEST_CACHE,
    server: { host: '127.0.0.1', port: 0, strictPort: false, open: false, hmr: false, watch: null,
      proxy: {'/api': {target: process.env.WORKFLOW_TEST_ORIGIN, changeOrigin: true}} },
    plugins: [{name:'workflow-test-preview',configureServer(vite){
      vite.middlewares.use(async(req,res,next)=>{
        if(req.url !== '/__workflow-test.html') return next();
        try {res.setHeader('Content-Type','text/html');res.end(await vite.transformIndexHtml(req.url,html));}
        catch(error){next(error);}
      });
    }}],
  });
  let browser;
  try {
    await server.listen();
    const port = server.httpServer.address().port;
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    const errors=[]; page.on('pageerror',error=>{errors.push(error.message);console.error('Browser runtime:',error.message);});
    page.on('response',r=>{if(r.status()>=400&&r.url().includes('/api/'))console.error('API status:',r.status(),new URL(r.url()).pathname);});
    await page.goto(`http://127.0.0.1:${port}/__workflow-test.html`);
    await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(process.env.WORKFLOW_TEST_PROJECT);
    await page.getByRole('button',{name:'Add transition',exact:true}).waitFor().catch(async e=>{throw new Error(e.message+' UI: '+await page.locator('body').innerText()+' Errors: '+JSON.stringify(errors));});
    await page.getByRole('button',{name:'Add transition',exact:true}).click();
    await page.getByRole('checkbox',{name:'Assignee',exact:true}).check();
    await page.getByRole('checkbox',{name:'Enforce allowed transitions',exact:true}).check();
    assert.ok(await page.getByRole('combobox',{name:'Project',exact:true}).isDisabled());
    await page.getByRole('button',{name:'Save workflow',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Workflow saved'}).waitFor();
    await page.reload();
    await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(process.env.WORKFLOW_TEST_PROJECT);
    await page.getByRole('checkbox',{name:'Enforce allowed transitions',exact:true}).waitFor();
    assert.ok(await page.getByRole('checkbox',{name:'Assignee',exact:true}).isChecked());
    // The saved UI policy must govern real task mutations.
    const taskUrl=`${process.env.WORKFLOW_TEST_ORIGIN}/api/v1/project-management/tasks/${process.env.WORKFLOW_TEST_TASK}`;
    const headers={Authorization:`Bearer ${token}`,'Content-Type':'application/json'};
    let response=await fetch(taskUrl,{method:'PATCH',headers,body:JSON.stringify({status:'Done'})});
    assert.equal(response.status,409);
    response=await fetch(taskUrl,{method:'PATCH',headers,body:JSON.stringify({status:'In Progress'})});
    assert.equal(response.status,409);
    response=await fetch(taskUrl,{method:'PATCH',headers,body:JSON.stringify({status:'In Progress',assignee_user_ids:[Number(process.env.WORKFLOW_TEST_ASSIGNEE)]})});
    assert.equal(response.status,200,await response.text());
    await page.getByRole('button',{name:'Add transition',exact:true}).click();
    await page.getByRole('button',{name:'Discard changes and reload',exact:true}).click();
    await page.getByRole('combobox',{name:'From status 2',exact:true}).waitFor({state:'detached'});
    await page.getByRole('button',{name:'Save workflow',exact:true}).waitFor();
    assert.equal(await page.getByRole('combobox',{name:/From status/}).count(),1);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.setViewportSize({width:1280,height:900});
    await page.getByRole('combobox',{name:'Work type',exact:true}).selectOption('Bug');
    await page.getByRole('combobox',{name:'To status 1',exact:true}).selectOption('In Review');
    await page.getByRole('button',{name:'Save workflow',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Workflow saved'}).waitFor();
    await page.reload();
    await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(process.env.WORKFLOW_TEST_PROJECT);
    await page.getByRole('combobox',{name:'Work type',exact:true}).selectOption('Bug');
    assert.equal(await page.getByRole('combobox',{name:'To status 1',exact:true}).inputValue(),'In Review');
    const bugUrl=`${process.env.WORKFLOW_TEST_ORIGIN}/api/v1/project-management/tasks/${process.env.WORKFLOW_TEST_BUG_TASK}`;
    response=await fetch(bugUrl,{method:'PATCH',headers,body:JSON.stringify({status:'In Progress',assignee_user_ids:[Number(process.env.WORKFLOW_TEST_ASSIGNEE)]})});
    assert.equal(response.status,409);
    response=await fetch(bugUrl,{method:'PATCH',headers,body:JSON.stringify({status:'In Review',assignee_user_ids:[Number(process.env.WORKFLOW_TEST_ASSIGNEE)]})});
    assert.equal(response.status,200,await response.text());
    await page.getByRole('button',{name:'Use project default for this type',exact:true}).click();
    assert.equal(await page.getByRole('combobox',{name:'To status 1',exact:true}).inputValue(),'In Progress');
    await page.getByRole('button',{name:'Save workflow',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Workflow saved'}).waitFor();
    assert.deepEqual(errors,[]);
    console.log('Workflow browser: publish, reload, enforce, discard and mobile layout passed against disposable API');
  } finally {if(browser)await browser.close();await server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
