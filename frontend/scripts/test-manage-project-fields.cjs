const path=require('node:path'),assert=require('node:assert/strict');
const {chromium,expect:base}=require('playwright/test');const expect=base.configure({timeout:20000});
(async()=>{
 process.chdir(process.env.CUSTOM_FIELDS_QA_ROOT||path.resolve(__dirname,'..'));
 const {createServer}=await import('vite');const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();const browser=await chromium.launch();
 try{for(const entity of ['project','task']){
  const context=await browser.newContext(),page=await context.newPage(),writes=[],errors=[];let fields=[],deny=true;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{const r=route.request(),p=new URL(r.url()).pathname;let data={types:[]};
   if(p.endsWith('/custom-fields')){if(r.method()==='POST'){writes.push(r.postDataJSON());if(deny)return route.fulfill({status:403,json:{detail:'Field creation denied'}});const field={...r.postDataJSON(),id:42,can_manage:true};fields=[field];data=field;}else data={fields,projects:[],can_manage_shared:true};}
   await route.fulfill({json:data});
  });
  await page.route('**/manage-fields-qa*',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/manage-project-fields.tsx");</script>'}));
  await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/manage-fields-qa?'+entity);
  await page.getByLabel('Record name').fill('Unsaved '+entity);await page.getByLabel('Record key').fill('KEEP42');
  const manage=page.getByRole('button',{name:`Manage ${entity} custom fields`,exact:true});await manage.click();
  const library=page.getByRole('dialog',{name:`Manage ${entity} custom fields`,exact:true});await expect(library).toBeVisible();
  assert.equal(context.pages().length,1,'Management must stay in authenticated tab');
  await library.getByRole('button',{name:'New custom field',exact:true}).click();const form=page.getByRole('dialog',{name:'Create custom field',exact:true});
  await expect(form.getByLabel('Field applies to')).toHaveValue(entity);await form.getByLabel('Field name').fill('QA reference');
  await form.getByRole('button',{name:'Create field',exact:true}).click();await expect(form.getByRole('alert')).toContainText('Field creation denied');await expect(form.getByLabel('Field name')).toHaveValue('QA reference');
  deny=false;await form.getByRole('button',{name:'Create field',exact:true}).click();await expect(form).toHaveCount(0);await expect(library).toBeVisible();
  await library.getByRole('button',{name:'Done',exact:true}).click();await expect(library).toHaveCount(0);
  await expect(page.getByLabel('Record name')).toHaveValue('Unsaved '+entity);await expect(page.getByLabel('Record key')).toHaveValue('KEEP42');
  await expect(page.getByLabel('QA reference',{exact:true})).toBeVisible();await page.getByLabel('QA reference',{exact:true}).fill('Draft field value');
  await manage.click();await library.getByRole('button',{name:'Done',exact:true}).click();await expect(page.getByLabel('QA reference',{exact:true})).toHaveValue('Draft field value');
  assert.equal(writes.length,2);assert.equal(writes[1].entity_type,entity);assert.deepEqual(errors,[]);await context.close();
  console.log('PASS',entity,'Manage opens in same tab; nested field save/error recovery; record draft and values preserved; field list refreshes.');
 }}finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
