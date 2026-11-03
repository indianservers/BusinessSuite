const {chromium,expect}=require('../frontend/node_modules/playwright/test');const fs=require('node:fs'),path=require('node:path');
const origin=process.env.PREVIEW_QA_ORIGIN || 'http://127.0.0.1:5198';const output=path.resolve('docs/qa/record-preview-responsive');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const source=await(await fetch(origin+'/src/components/RecordQuickPreview.tsx')).text();const main=await(await fetch(origin+'/src/main.tsx')).text();
 const react=source.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1],router=source.match(/"([^"\n]*\/react-router-dom\.js\?v=[^"\n]+)"/)[1],dom=main.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
 const html=`<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
 import React from '${react}';import ReactDOM from '${dom}';import {BrowserRouter} from '${router}';import Preview,{recordPreviewProps} from '/src/components/RecordQuickPreview.tsx';import '/src/index.css';
 const modules=[['CRM','/crm/contacts'],['HRMS','/hrms/employees'],['PMS','/pms/tasks'],['Finance','/fam/vouchers'],['SRM','/srm/sales-orders']];
 const record={id:7,name:'Ananya Rao — customer success and delivery operations',title:'Customer workflow review',email:'ananya@example.test',phone:'+919876543210',project_id:1,task_key:'QA-7',description:'Very long reference '+ 'a'.repeat(300),nested:{city:'Hyderabad',password:'NEVER SHOW THIS'},tags:['Customer','Delivery'],password:'NEVER SHOW THIS',owner_user_id:1};
 ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement('main',{className:'space-y-3 p-5'},React.createElement('h1',null,'Record preview QA'),...modules.map(([name,path])=>React.createElement('button',{key:name,...recordPreviewProps(record,path),className:'block rounded border p-3'},'Preview '+name))),React.createElement(Preview)));
 </script></body></html>`;
 const b=await chromium.launch({headless:true});const results=[],errors=[];
 try{
  for(const [width,height] of [[1440,1000],[390,844],[320,740],[844,390]]){
   const c=await b.newContext({viewport:{width,height},hasTouch:true});await c.route('**/__preview_responsive',r=>r.fulfill({body:html,contentType:'text/html'}));
   await c.route('**/api/v1/**',r=>r.fulfill({json:r.request().url().endsWith('/related')?{deals:[{name:'Related customer opportunity'}]}:{description:'Loaded full record details',notes:'Complete delivery plan'}}));
   const p=await c.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto(origin+'/__preview_responsive');
   for(const module of ['CRM','HRMS','PMS','Finance','SRM']){
    const opener=p.getByRole('button',{name:'Preview '+module,exact:true});await opener.dblclick();const dialog=p.getByRole('dialog');await expect(dialog).toBeVisible();await expect(dialog).not.toContainText('NEVER SHOW THIS');
    for(const tab of ['Overview','Contact','Details','Related']){const trigger=dialog.getByRole('tab',{name:new RegExp('^'+tab)});await trigger.click();await expect(trigger).toHaveAttribute('aria-selected','true');}
    await dialog.getByLabel('Search record fields').fill('Hyderabad');await expect(dialog).toContainText('Hyderabad');await dialog.getByRole('button',{name:'Clear search'}).click();
    await dialog.getByRole('button',{name:'Expand preview',exact:true}).click();await expect(dialog.getByRole('button',{name:'Restore preview size'})).toBeVisible();await dialog.getByRole('button',{name:'Restore preview size'}).click();
    const bounds=await dialog.boundingBox();expect(bounds.x).toBeGreaterThanOrEqual(0);expect(bounds.y).toBeGreaterThanOrEqual(0);expect(bounds.x+bounds.width).toBeLessThanOrEqual(width+1);expect(bounds.y+bounds.height).toBeLessThanOrEqual(height+1);
    const close=dialog.getByRole('button',{name:'Close preview',exact:true});const cb=await close.boundingBox();expect(cb.y+cb.height).toBeLessThanOrEqual(height);expect(cb.height).toBeGreaterThanOrEqual(44);
    await close.tap();await expect(dialog).toHaveCount(0);await expect(opener).toBeFocused();
    await opener.dblclick();await expect(dialog).toBeVisible();await p.waitForTimeout(100);await p.keyboard.press('Escape');await expect(dialog).toHaveCount(0);
    await opener.dblclick();await expect(dialog).toBeVisible();await p.waitForTimeout(100);await dialog.getByRole('button',{name:'Close dialog',exact:true}).tap();await expect(dialog).toHaveCount(0);
    await opener.dblclick();await expect(dialog).toBeVisible();await p.waitForTimeout(100);await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await p.mouse.click(2,2);await expect(dialog).toHaveCount(0);
    results.push({module,width,height,passed:true});
   }
   await p.getByRole('button',{name:'Preview CRM',exact:true}).dblclick();await p.getByRole('dialog').getByRole('tab',{name:/^Contact/}).click();await p.screenshot({path:path.join(output,`preview-${width}x${height}.png`)});
   await p.getByRole('dialog').getByRole('button',{name:'Close preview',exact:true}).tap();
   const opener=p.getByRole('button',{name:'Preview CRM',exact:true});const box=await opener.boundingBox();await p.touchscreen.tap(box.x+box.width/2,box.y+box.height/2);await p.touchscreen.tap(box.x+box.width/2,box.y+box.height/2);await expect(p.getByRole('dialog')).toBeVisible();await p.keyboard.press('Escape');
   await c.close();console.log('PASS preview',width,height,'all modules, tabs, four close paths, double tap, focus return');
  }
  expect(errors).toEqual([]);fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({results,errors},null,2));
 }finally{await b.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
