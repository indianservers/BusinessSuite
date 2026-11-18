const path=require('node:path'),assert=require('node:assert/strict');
const {chromium,expect}=require('playwright/test');
(async()=>{
  process.chdir(path.resolve(__dirname,'..'));
  const {createServer}=await import('vite');
  const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});
  await server.listen();const origin=server.resolvedUrls.local[0],browser=await chromium.launch();
  try{
    for(const source of ['crm','project_management']){
      const page=await browser.newPage({viewport:{width:390,height:900}}),writes=[],errors=[];
      let empty=false,failed=false,consent='connected',extraAccount=null,connectCalls=0;
      page.on('pageerror',e=>errors.push(e.message));
      await page.context().route('**/api/v1/**',async route=>{
        const request=route.request(),url=new URL(request.url());
        if(url.pathname.endsWith('/notes/options'))return route.fulfill({json:{accounts:empty?[]:[{id:1,provider:'google_drive',account:'my-google@example.test'},{id:2,provider:'onedrive',account:'my-microsoft@example.test'},...(extraAccount?[extraAccount]:[])]}});
        if(url.pathname.endsWith('/notes/connect')){
          const payload=request.postDataJSON();assert.equal(payload.source,source);connectCalls++;
          return route.fulfill({json:{authorize_url:origin+'notes-oauth-fixture?provider='+payload.provider,request_id:'fixture-request-'+connectCalls,callback_origin:new URL(origin).origin}});
        }
        if(url.pathname.endsWith('/folders'))return route.fulfill({json:{items:url.searchParams.get('parent')==='root'?[{id:'notes-folder',name:'My note copies'}]:[],cursor:null}});
        if(url.pathname.endsWith('/notes/save')){
          writes.push(request.postDataJSON());
          return route.fulfill(failed?{status:503,json:{detail:'Cloud provider unavailable. Original note is unchanged.'}}:{json:{saved:true,filename:'Private meeting.html'}});
        }
        return route.fulfill({json:{}});
      });
      await page.context().route('**/notes-oauth-fixture?*',route=>{
        const provider=new URL(route.request().url()).searchParams.get('provider');
        if(consent==='connected'){empty=false;extraAccount={id:3,provider,account:'new-personal@example.test'};}
        const message={type:'suite-note-storage',request_id:'fixture-request-'+connectCalls,status:consent,connection_id:3};
        const script=consent==='close'?'window.close()':`window.opener.postMessage(${JSON.stringify({...message,request_id:'wrong-request'})},location.origin);window.opener.postMessage(${JSON.stringify(message)},location.origin);window.close()`;
        return route.fulfill({contentType:'text/html',body:'<!doctype html><p>Simulated provider consent</p><script>'+script+'</script>'});
      });
      await page.goto(origin+'scripts/fixtures/note-cloud.html?source='+source);
      await page.getByRole('button',{name:'Save to cloud'}).click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await expect(page.getByLabel('Note storage account')).toHaveValue('1');
      await expect(page.getByRole('button',{name:'Google Drive: Connected',exact:true})).toBeVisible();
      await page.getByRole('button',{name:'OneDrive: Connected',exact:true}).click();
      await expect(page.getByLabel('Note storage account')).toHaveValue('2');
      assert.equal(connectCalls,0);
      await page.getByRole('button',{name:'Google Drive: Connected',exact:true}).click();
      await page.getByRole('button',{name:'My note copies',exact:true}).click();
      await expect(page.getByText('My files / My note copies',{exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:'Save copy to Google Drive',exact:true})).toBeEnabled();
      await page.getByRole('button',{name:'Save copy to Google Drive',exact:true}).click();
      await expect(page.getByRole('status').filter({hasText:'Saved Private meeting'})).toBeVisible();
      assert.equal(writes[0].folder_id,'notes-folder');assert.equal(writes[0].connection_id,1);assert.equal(writes[0].source,source);
      if(source==='crm')await page.screenshot({path:path.join(process.env.TEMP||require('node:os').tmpdir(),'notes-cloud-copy-preview.png'),fullPage:true});
      if(source==='crm')assert.equal(writes[0].content,'Original content');
      else {assert.equal(writes[0].note_id,7);assert.equal(writes[0].note_version,5);assert.equal(writes[0].content,undefined);}
      await page.getByLabel('Note storage provider').selectOption('onedrive');
      await expect(page.getByLabel('Note storage account')).toHaveValue('2');
      await page.getByLabel('Cloud note format').selectOption('txt');
      await expect(page.getByRole('button',{name:'Save copy to OneDrive',exact:true})).toBeEnabled();
      failed=true;await page.getByRole('button',{name:'Save copy to OneDrive',exact:true}).click();
      await expect(page.getByRole('alert')).toHaveText('Cloud provider unavailable. Original note is unchanged.');
      assert.equal(writes[1].format,'txt');assert.equal(writes[1].connection_id,2);assert.equal(writes[1].folder_id,'root');
      await expect(page.locator('h1')).toHaveText('Original private note');
      empty=true;await page.getByRole('button',{name:'Refresh accounts',exact:true}).click();
      await expect(page.getByText('No OneDrive account connected by you.',{exact:false})).toBeVisible();
      await expect(page.getByRole('button',{name:'Save copy to OneDrive',exact:true})).toBeDisabled();
      await expect(page.getByRole('link',{name:/Settings|Manage connected/})).toHaveCount(0);
      await page.getByRole('button',{name:'Google Drive: Connect',exact:true}).click();
      await expect(page.getByRole('status').filter({hasText:'Google Drive connected.'})).toBeVisible();
      await expect(page.getByLabel('Note storage account')).toHaveValue('3');
      await expect(page.getByLabel('Note storage provider')).toHaveValue('google_drive');
      await expect(page.locator('h1')).toHaveText('Original private note');
      await expect(page.getByRole('button',{name:'Google Drive: Connected',exact:true})).toBeVisible();
      empty=true;await page.getByRole('button',{name:'Refresh accounts',exact:true}).click();
      await expect(page.getByRole('button',{name:'Google Drive: Connect',exact:true})).toBeEnabled();
      consent='denied';await page.getByRole('button',{name:'OneDrive: Connect',exact:true}).click();
      await expect(page.getByRole('alert')).toContainText('canceled or denied');
      consent='close';await page.getByRole('button',{name:'Google Drive: Connect',exact:true}).click();
      await expect(page.getByRole('alert')).toContainText('Connection canceled. Your note is still open.');
      await page.evaluate(()=>{window.open=()=>null;});
      await page.getByRole('button',{name:'OneDrive: Connect',exact:true}).click();
      await expect(page.getByRole('alert')).toContainText('Allow the connection popup');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);await page.close();
      console.log('PASS '+source+': cloud copies, in-Notes OAuth popup, new account selection, forged message ignored, denial, cancellation, popup blocking, draft preservation and mobile layout');
    }
  }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
