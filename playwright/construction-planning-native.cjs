const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');
const expect=base.configure({timeout:120000});
(async()=>{
  const qa=JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE,'utf8')),bridge=process.env.CONTROL_BRIDGE;
  assert.match(bridge,/^http:\/\/127\.0\.0\.1:\d+$/);
  const root=path.resolve(__dirname,'../frontend');process.chdir(root);
  const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
  const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const p=socket.address().port;socket.close(()=>resolve(p));});});
  const vite=await createServer({root,cacheDir:path.resolve(root,'../.local/construction-planning-vite-cache'),server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});
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
    await page.getByText('Project planning & handover tools',{exact:true}).click();
    for(const [width,label] of [[1440,'desktop'],[390,'mobile']]){
      stage=label+' certified planning metrics and native client export';
      await page.setViewportSize({width,height:1100});
      // Open only the direct planning section; nested forms reuse their native controls.
      await page.locator('summary').filter({hasText:/Approved cost baseline & performance/}).click();
      await page.getByLabel('Performance cost baseline',{exact:true}).selectOption(String(qa.baseline));
      await page.getByLabel('Performance as of',{exact:true}).fill(qa.as_of);
      await page.getByRole('button',{name:'Load project performance',exact:true}).click();
      await expect(page.locator('dt',{hasText:/^BAC$/}).locator('..')).toContainText('1000');
      await expect(page.locator('dt',{hasText:/^EV$/}).locator('..')).toContainText('300');
      const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download client report CSV',exact:true}).click()]);
      const bytes=fs.readFileSync(await download.path(),'utf8');
      assert.match(bytes,/planning\.EV,300\.00/);assert.match(bytes,/planning\.BAC,1000\.00/);
      await page.screenshot({path:path.resolve(root,'../.local/construction-planning-'+label+'.png'),fullPage:true});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      await page.locator('summary').filter({hasText:/Approved cost baseline & performance/}).click();
    }
    stage='native cost-budget revision';
    await page.getByText('Canonical project cost budget',{exact:true}).click();
    await page.getByLabel('Construction estimated cost budget',{exact:true}).fill('1100');
    await page.getByLabel('Construction budget revision reason',{exact:true}).fill('Reviewed browser estimate revision');
    await page.getByRole('button',{name:'Revise native PMS budget',exact:true}).click();
    await expect(page.getByText(/Current PMS estimate: 1100/)).toBeVisible();
    assert.equal(trace.filter(item=>item.method==='POST'&&item.path.endsWith('/cost-budget')&&item.status===200).length,1);
    assert.equal(trace.filter(item=>item.path.endsWith('/client-report')&&item.status===200).length,2);
    assert.deepEqual(trace.filter(item=>item.status>=400),[]);assert.deepEqual(errors,[]);
    fs.writeFileSync(path.resolve(root,'../.local/construction-planning-browser-proof.json'),JSON.stringify({stage:'complete',native_http_trace:trace,js_errors:errors,mocked_responses:false,desktop_width:1440,mobile_width:390},null,2));
    console.log('PASS Construction planning UI: approved canonical cost baseline, certified earned value, actual CSV bytes on desktop/mobile, native cost budget revision.');
  }catch(error){if(page)console.error(JSON.stringify({stage,trace,errors,body:(await page.locator('body').innerText()).slice(0,5000)}));throw error;}
  finally{closing=true;if(context){await context.unrouteAll({behavior:'wait'});await context.close();}if(browser)await browser.close();await vite.close();}
})().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;});
