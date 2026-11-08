import {test,expect} from '../frontend/node_modules/playwright/test';
for(const definition of [false,true])for(const width of [1440,390])test(`shared ${definition?'definition':'record'} edit/delete and failure at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900});let failed=true,rows=[{id:1,name:'First record'},{id:2,name:'Keep record'}];const prompts:string[]=[];
 page.on('dialog',async d=>{prompts.push(d.message());await d.dismiss();});
 await page.route('**/__record_edit_qa*',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/record-edit-qa.tsx"></script></body></html>`}));
 await page.route('**/__qa_list',async route=>{await new Promise(r=>setTimeout(r,2500));await route.fulfill({json:{items:rows,total:rows.length}});});
 await page.route('**/api/v1/**',route=>{
  if(failed)return route.fulfill({status:409,json:{detail:'Protected record; your edits are retained.'}});
  const req=route.request();if(req.method()==='DELETE'){rows=rows.filter(r=>r.id!==1);return route.fulfill({status:204});}
  rows=rows.map(r=>r.id===1?{...r,...req.postDataJSON()}:r);return route.fulfill({json:rows[0]});
 });
 await page.goto(`/__record_edit_qa${definition?'?definition=1':''}`);
 const heading=await page.getByRole('heading',{name:'Shared record list'}).elementHandle();
 await page.getByLabel('Keep filter').fill('Preserve selection');
 await page.getByRole('button',{name:`${definition?'Rename':'Edit'} First record`,exact:true}).click();
 const d=page.getByRole('dialog');const field=d.getByLabel(definition?'Definition name':'Record name');await field.fill('Updated record');
 const save=d.getByRole('button',{name:definition?'Save name':'Save record',exact:true});await expect(save).toBeInViewport();await save.click();
 await expect(d.getByRole('alert')).toContainText('Protected record');await expect(field).toHaveValue('Updated record');
 failed=false;await save.click();await expect(d).toHaveCount(0,{timeout:1200});
 await expect(page.getByRole('article').filter({hasText:'Updated record'})).toBeVisible({timeout:1200});
 await page.getByRole('button',{name:'Delete Updated record',exact:true}).click();
 failed=true;await d.getByRole('button',{name:definition?'Confirm delete':'Confirm delete record',exact:true}).click();await expect(d.getByRole('alert')).toContainText('Protected record');
 await expect(page.getByRole('article',{includeHidden:true}).filter({hasText:'Updated record'})).toHaveCount(1);
 failed=false;await d.getByRole('button',{name:definition?'Confirm delete':'Confirm delete record',exact:true}).click();
 await expect(d).toHaveCount(0,{timeout:1200});await expect(page.getByRole('article')).toHaveCount(1,{timeout:1200});await expect(page.getByText('Keep record',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Keep filter')).toHaveValue('Preserve selection');expect(await heading!.evaluate(el=>el.isConnected)).toBe(true);expect(prompts).toEqual([]);
});
