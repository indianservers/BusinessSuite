const assert=require('node:assert/strict');
const path=require('node:path');
const net=require('node:net');
const {chromium,expect:base}=require('playwright/test');
const expect=base.configure({timeout:30000});
const freePort=()=>new Promise((resolve,reject)=>{const socket=net.createServer();socket.once('error',reject);socket.listen(0,'127.0.0.1',()=>{const port=socket.address().port;socket.close(error=>error?reject(error):resolve(port));});});

(async()=>{
  const root=path.resolve(__dirname,'..');
  process.chdir(root);
  const{createServer}=await import('vite');
  const server=await createServer({root,cacheDir:path.resolve(root,'../.local/leave-private-vite-cache'),server:{host:'127.0.0.1',port:await freePort(),strictPort:true,hmr:false,watch:null}});
  await server.listen();
  const origin='http://127.0.0.1:'+server.httpServer.address().port;
  const browser=await chromium.launch();
  const context=await browser.newContext({viewport:{width:1440,height:1100}});
  const page=await context.newPage();
  const errors=[],unexpected=[],posts=[];
  let holdB=null,holdCancel=null,cancelSeen=false,closing=false,stage='initial';
  page.on('pageerror',error=>errors.push(error.message));
  await page.route(origin+'/**',async route=>{
    const request=route.request(),url=new URL(request.url());
    try{
      if(url.pathname.startsWith('/api/')){
        const company=request.headers()['x-suite-organization']==='2'?2:1;
        const name=company===1?'A':'B',type={id:company,name:'Annual leave '+name};
        let body;
        if(request.method()!=='GET'){
          posts.push({path:url.pathname,company});
          if(url.pathname==='/api/v1/leave/requests/1/cancel'){
            cancelSeen=true;
            if(holdCancel)await holdCancel;
            body={id:1,status:'Cancelled'};
          }else{unexpected.push(request.method()+' '+url.pathname);body={};}
        }else if(url.pathname==='/api/v1/leave/types')body=[type];
        else if(url.pathname==='/api/v1/leave/balance'){
          if(company===2&&holdB)await holdB;
          body=[{leave_type_id:company,leave_type:type,allocated:10,used:0,pending:1,available:9}];
        }else if(url.pathname==='/api/v1/leave/my-requests'){
          if(company===2&&holdB)await holdB;
          body=[{id:company,employee_id:company,leave_type:type,from_date:'2026-11-20',to_date:'2026-11-20',days_count:1,reason:'PRIVATE-'+name+'-REQUEST',status:'Pending',applied_at:'2026-11-15T00:00:00Z'}];
        }else if(url.pathname==='/api/v1/leave/calendar')body={days:[]};
        else if(url.pathname==='/api/v1/employees/workbench/request-context')body={employee_id:company,
          employee_name:'Canonical employee '+name,department:null,branch:'Branch '+name,manager_name:null,
          approval_path:['Native reviewer '+name],routing_note:'Existing native approval routing',initial_status:'Pending'};
        else if(url.pathname==='/api/v1/hrms/leave-encashment')body=[];
        else if(url.pathname==='/api/v1/access/settings/business-profile/effective')body={business_type:'hospital',terms:{},features:{},preferences:{}};
        else {unexpected.push(request.method()+' '+url.pathname);body=[];}
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
      }
      if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/leave-private-scope.tsx");</script>'});
      return route.continue();
    }catch(error){if(!closing)errors.push(error.message);await route.abort().catch(()=>{});}
  });
  try{
    await page.goto(origin+'/leave-private-scope-qa');
    await expect(page.getByRole('heading',{name:'Leave Management',exact:true})).toBeVisible({timeout:120000});
    await expect(page.getByText('Annual leave A',{exact:true}).first()).toBeVisible();
    let releaseB;
    holdB=new Promise(resolve=>{releaseB=resolve;});
    await page.evaluate(()=>window.switchLeaveOwner('B'));
    await expect(page.getByText('Annual leave A',{exact:true})).toHaveCount(0);
    await expect(page.getByText('PRIVATE-A-REQUEST',{exact:true})).toHaveCount(0);
    releaseB();holdB=null;
    await expect(page.getByText('Annual leave B',{exact:true}).first()).toBeVisible();
    stage='first B draft';
    await page.getByRole('button',{name:'Apply Leave',exact:true}).click();
    await page.getByRole('textbox',{name:'Reason',exact:true}).fill('PRIVATE-B-DRAFT');
    await page.evaluate(()=>window.switchLeaveOwner('A'));
    await expect(page.getByRole('textbox',{name:'Reason',exact:true})).toHaveCount(0);
    await expect(page.getByText('Annual leave A',{exact:true}).first()).toBeVisible();
    let releaseCancel;
    holdCancel=new Promise(resolve=>{releaseCancel=resolve;});
    await page.getByRole('button',{name:'Cancel',exact:true}).first().click();
    await expect.poll(()=>cancelSeen).toBe(true);
    await page.evaluate(()=>window.switchLeaveOwner('B'));
    await expect(page.getByText('Annual leave A',{exact:true})).toHaveCount(0);
    await expect(page.getByText('Annual leave B',{exact:true}).first()).toBeVisible();
    stage='B draft after old cancellation';
    await page.getByRole('button',{name:'Apply Leave',exact:true}).click();
    await page.getByRole('textbox',{name:'Reason',exact:true}).fill('PRIVATE-B-CURRENT');
    releaseCancel();holdCancel=null;
    await expect(page.getByRole('textbox',{name:'Reason',exact:true})).toHaveValue('PRIVATE-B-CURRENT');
    await expect(page.getByText('Leave cancelled',{exact:true})).toHaveCount(0);
    await page.setViewportSize({width:390,height:1000});
    await page.evaluate(()=>window.switchLeaveOwner('B',2));
    await expect(page.getByRole('textbox',{name:'Reason',exact:true})).toHaveCount(0);
    await expect(page.getByRole('heading',{name:'Leave Management',exact:true})).toBeVisible();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.deepEqual(posts,[{path:'/api/v1/leave/requests/1/cancel',company:1}]);
    assert.deepEqual(unexpected,[]);
    assert.deepEqual(errors,[]);
    console.log('PASS Leave UI: held reads, identity/branch changes, private drafts and late cancellation stay with their owner; desktop/mobile layout preserved.');
  }catch(error){
    console.error(JSON.stringify({stage,unexpected,errors,body:(await page.locator('body').innerText()).slice(0,5000)}));
    throw error;
  }finally{
    closing=true;
    await context.close();await browser.close();await server.close();
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
