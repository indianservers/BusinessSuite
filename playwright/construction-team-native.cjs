const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');
const expect=base.configure({timeout:120000});
(async()=>{
  const qa=JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE,'utf8')),bridge=process.env.CONTROL_BRIDGE;
  assert.match(bridge,/^http:\/\/127\.0\.0\.1:\d+$/);
  const root=path.resolve(__dirname,'../frontend');process.chdir(root);
  const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
  const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const p=socket.address().port;socket.close(()=>resolve(p));});});
  const vite=await createServer({root,cacheDir:path.resolve(root,'../.local/construction-team-vite-cache'),server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});
  let browser,context,page,closing=false,stage='startup';
  const trace=[],errors=[];
  try{
    await vite.listen();const origin='http://127.0.0.1:'+vite.httpServer.address().port;
    browser=await chromium.launch();context=await browser.newContext({viewport:{width:1440,height:1100}});
    await context.addInitScript(qa=>{
      sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',qa.branch);
      sessionStorage.setItem('suite-pack-context',qa.context);sessionStorage.setItem('suite-business-pack-context',qa.context);
      sessionStorage.setItem('suite-pack-context-owner',JSON.stringify([null,'1',qa.branch]));
      sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:qa.token,refreshToken:null,user:qa.user,isAuthenticated:true},version:0}));
    },qa);
    page=await context.newPage();page.on('pageerror',error=>errors.push(error.stack||error.message));
    await page.route('**/api/**',async route=>{
      try{
        const request=route.request(),url=new URL(request.url());
        const response=await context.request.fetch(bridge+url.pathname+url.search,{method:request.method(),headers:request.headers(),data:request.postDataBuffer()||undefined});
        trace.push({method:request.method(),path:url.pathname,status:response.status()});
        await route.fulfill({response});
      }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{});}
    });
    await page.goto(origin+'/srm/construction');
    await expect(page.getByRole('heading',{name:'Construction operations',exact:true})).toBeVisible();
    await page.getByRole('combobox',{name:'Search project',exact:true}).fill('Private site');
    await page.getByRole('option',{name:'Private site',exact:true}).click();
    stage='new native site while previous picker search is active';
    await page.getByText('Define a Construction site',{exact:true}).click();
    await page.getByText('Create a native Construction workspace',{exact:true}).click();
    await page.getByLabel('Construction workspace name',{exact:true}).fill(qa.workspace_name);
    const creatingWorkspace=page.waitForResponse(response=>response.url().endsWith('/srm/industry/workspace-definitions')&&response.request().method()==='POST');
    await page.getByRole('button',{name:'Create native PMS workspace',exact:true}).click();
    const workspaceResponse=await creatingWorkspace;assert.equal(workspaceResponse.status(),201);const workspace=await workspaceResponse.json();assert.equal(workspace.role,'Owner');
    await expect(page.getByLabel('Site PMS workspace',{exact:true})).toHaveValue(String(workspace.id));
    stage='native Team Member via existing eligible account';
    await page.getByText('Native Construction workspace team',{exact:true}).click();
    await page.getByLabel('Construction team eligible account',{exact:true}).selectOption(String(qa.target_id));
    await page.getByLabel('Construction team workspace role',{exact:true}).selectOption('Member');
    const adding=page.waitForResponse(response=>response.url().endsWith(`/workspaces/${workspace.id}/member-definitions`)&&response.request().method()==='POST');
    await page.getByRole('button',{name:'Add native workspace member',exact:true}).click();
    const added=await adding;assert.equal(added.status(),201);const member=await added.json();
    assert.equal(member.user_id,qa.target_id);assert.equal(member.role,'Member');
    await expect(page.getByText('Native workspace Member membership added.',{exact:true})).toBeVisible();
    await page.screenshot({path:path.resolve(root,'../.local/construction-team-member-desktop.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    await page.getByLabel('Site project name',{exact:true}).fill(qa.site_name);
    await page.getByLabel('Site project key',{exact:true}).fill(qa.site_key);
    await page.getByLabel('Site project start',{exact:true}).fill('2026-11-16');
    await page.getByLabel('Site project due',{exact:true}).fill('2026-12-16');
    await page.getByLabel('Site estimated cost',{exact:true}).fill('1200');
    await page.getByLabel('Site estimated hours',{exact:true}).fill('32');
    const createdResponse=page.waitForResponse(response=>response.url().endsWith('/srm/industry/site-projects')&&response.request().method()==='POST');
    await page.getByRole('button',{name:'Create native PMS site',exact:true}).click();
    const created=await createdResponse;assert.equal(created.status(),201);const site=await created.json();
    // This catches the filtered ProjectPicker label losing a newly created selection.
    await expect(page.getByRole('combobox',{name:'Search project',exact:true})).toHaveValue(qa.site_name);
    await page.getByText('Project planning & handover tools',{exact:true}).click();
    assert.equal(trace.filter(item=>item.method==='POST'&&item.path.endsWith('/member-definitions')&&item.status===201).length,1);
    assert.deepEqual(trace.filter(item=>item.status>=400),[]);assert.deepEqual(errors,[]);
    fs.writeFileSync(path.resolve(root,'../.local/construction-team-browser-proof.json'),JSON.stringify({stage:'complete',workspace_id:workspace.id,site_id:site.id,member,target_id:qa.target_id,native_http_trace:trace,js_errors:errors,mocked_responses:false},null,2));
    console.log('PASS genuine Construction Team UI: native workspace, existing eligible Member, site, no failed HTTP.');
  }catch(error){if(page)console.error(JSON.stringify({stage,trace,errors,body:(await page.locator('body').innerText()).slice(0,5000)}));throw error;}
  finally{closing=true;if(context){await context.unrouteAll({behavior:'wait'});await context.close();}if(browser)await browser.close();await vite.close();}
})().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;});
