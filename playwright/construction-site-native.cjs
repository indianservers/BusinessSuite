const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('../frontend/node_modules/playwright/test');
const expect=base.configure({timeout:120000});
(async()=>{
  const qa=JSON.parse(fs.readFileSync(process.env.SUITE_QA_AUTH_FILE,'utf8')),bridge=process.env.CONTROL_BRIDGE;
  assert.match(bridge,/^http:\/\/127\.0\.0\.1:\d+$/);
  const root=path.resolve(__dirname,'../frontend');process.chdir(root);
  const {createServer}=await import('../frontend/node_modules/vite/dist/node/index.js');
  const port=await new Promise(resolve=>{const socket=require('node:net').createServer();socket.listen(0,'127.0.0.1',()=>{const p=socket.address().port;socket.close(()=>resolve(p));});});
  const vite=await createServer({root,cacheDir:path.resolve(root,'../.local/construction-invoice-vite-cache'),server:{host:'127.0.0.1',port,strictPort:true,hmr:false,watch:null}});
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
    await expect(page.getByRole('heading',{name:'Independently approved foundation',exact:true})).toBeVisible();
    await expect(page.getByRole('region',{name:'Project commercial summary'})).toBeVisible();
    for(const [width,label] of [[1440,'desktop'],[390,'mobile']]){
      stage=label+' diary with canonical attachment';
      await page.setViewportSize({width,height:1100});
      await page.getByRole('tab',{name:'Site diary',exact:true}).click();
      await page.getByRole('button',{name:'New site diary',exact:true}).click();
      await page.getByRole('textbox',{name:'Title',exact:true}).fill(label+' site diary');
      await page.getByLabel('Entry date',{exact:true}).fill('2026-11-15');
      await page.getByLabel('Workforce count',{exact:true}).fill('12');
      await page.getByRole('textbox',{name:'Work completed',exact:true}).fill('Foundation placed with supporting evidence');
      await page.getByRole('checkbox',{name:'Site progress.jpg',exact:true}).check();
      await page.screenshot({path:path.resolve(root,'../.local/construction-site-'+label+'-form.png'),fullPage:true});
      await page.getByRole('button',{name:'Save operation',exact:true}).click();
      await expect(page.getByRole('heading',{name:label+' site diary',exact:true})).toBeVisible();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      await page.screenshot({path:path.resolve(root,'../.local/construction-site-'+label+'.png'),fullPage:true});
    }
    for(const tab of ['BOQ','Variations','Measurements','Subcontracts','Materials consumed']){
      await page.getByRole('tab',{name:tab,exact:true}).click();
      await expect(page.getByRole('tab',{name:tab,exact:true})).toHaveAttribute('aria-selected','true');
    }
    assert.equal(trace.some(item=>item.path==='/api/v1/srm/industry/records'&&item.status===200),true);
    assert.equal(trace.filter(item=>item.method==='POST'&&item.path==='/api/v1/srm/industry/site-diaries'&&item.status===201).length,2);
    await page.getByRole('tab',{name:'Site diary',exact:true}).click();
    await page.getByRole('button',{name:'New site diary',exact:true}).click();
    await page.getByRole('link',{name:'Upload photos in PMS Files',exact:true}).click();
    for(const [width,label] of [[1440,'desktop'],[390,'mobile']]){
      stage=label+' native PMS upload/download';
      await page.setViewportSize({width,height:1100});
      const filename='Native evidence '+label+'.txt';
      await expect(page.getByLabel('Upload project files',{exact:true})).toBeEnabled();
      await page.getByLabel('Upload project files',{exact:true}).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from('Construction native upload and download\n')});
      await expect(page.getByRole('heading',{name:filename,exact:true})).toBeVisible();
      const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download '+filename,exact:true}).click()]);
      assert.equal(download.suggestedFilename(),filename);
      assert.equal(fs.readFileSync(await download.path(),'utf8'),'Construction native upload and download\n');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      await page.screenshot({path:path.resolve(root,'../.local/construction-documents-'+label+'.png'),fullPage:true});
    }
    assert.equal(trace.some(item=>item.path==='/api/v1/project-management/files'&&item.status===200),true);
    assert.equal(trace.some(item=>item.path==='/api/v1/follow-ups/statistics'&&item.status===200),true);
    assert.deepEqual(trace.filter(item=>item.status>=400),[]);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.resolve(root,'../.local/construction-site-browser-proof.json'),JSON.stringify({stage:'complete',native_http_trace:trace,js_errors:errors,mocked_responses:false,desktop_width:1440,mobile_width:390},null,2));
    console.log('PASS existing Construction UI: canonical project selection, six tabs, desktop/mobile diary, native PMS binary upload/download, scoped follow-up statistics.');
  }catch(error){if(page)console.error(JSON.stringify({stage,trace,errors,body:(await page.locator('body').innerText()).slice(0,5000)}));throw error;}
  finally{closing=true;if(context){await context.unrouteAll({behavior:'wait'});await context.close();}if(browser)await browser.close();await vite.close();}
})().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;});
