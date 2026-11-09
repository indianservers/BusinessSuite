const path=require('node:path');
const {chromium,expect}=require('playwright/test');
(async()=>{
 process.chdir(process.env.TASK_ENTER_ROOT||path.resolve(__dirname,'..'));
 const {createServer}=await import('vite');
 const server=await createServer({server:{host:'127.0.0.1',port:0,hmr:false,watch:null}});await server.listen();
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage();
  await page.route('**/task-enter-qa',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div><script type="module">import R from "/@react-refresh";R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;await import("/scripts/fixtures/task-enter-qa.tsx");</script>'}));
  const url='http://127.0.0.1:'+server.httpServer.address().port+'/task-enter-qa';
  await page.goto(url);const dialog=page.getByRole('dialog',{name:'Create Task',exact:true});
  const title=page.getByLabel('Task heading'),description=page.getByLabel('Description',{exact:true});
  await title.fill('Keep this task open');await title.press('Enter');await title.press('Control+Enter');
  await expect(dialog).toBeVisible();await expect(page.getByLabel('Tasks saved')).toHaveText('0');
  await description.fill('First line');await description.press('End');await description.press('Enter');await description.pressSequentially('Second line');
  await expect(description).toHaveValue('First line\nSecond line');await description.press('Control+Enter');
  const rich=page.getByRole('textbox',{name:'Rich description'});await rich.fill('Rich first line');await rich.press('End');await rich.press('Enter');await rich.pressSequentially('Rich second line');
  await expect(rich).toContainText('Rich second line');await expect(dialog).toBeVisible();await expect(page.getByLabel('Tasks saved')).toHaveText('0');
  await title.press('Escape');await expect(page.getByRole('alertdialog')).toBeVisible();await page.getByRole('button',{name:'Continue Editing'}).click();await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('button',{name:'Discard Changes'}).click();await expect(dialog).toHaveCount(0);await expect(page.getByLabel('Tasks saved')).toHaveText('0');
  await page.goto(url);await title.fill('Explicit creation');await dialog.locator('[data-smart-create-footer]').getByRole('button',{name:'Create Task',exact:true}).click();await expect(page.getByLabel('Tasks saved')).toHaveText('1');await expect(dialog).toHaveCount(0);
  console.log('PASS: task Enter/Ctrl+Enter stay open; textarea/rich text newlines, Escape, Cancel and explicit Create work.');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
