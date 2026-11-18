const assert = require('node:assert/strict');
const {build} = require('esbuild');
const {chromium} = require('playwright');
const path = require('node:path');
(async () => {
  const root = path.resolve(__dirname, '..');
  const source = `
    import React,{useState,useEffect} from 'react';
    import {createRoot} from 'react-dom/client';
    import {MemoryRouter} from 'react-router-dom';
    import {QueryClient,QueryClientProvider,useQuery} from '@tanstack/react-query';
    import {useRefreshableEffect} from './src/lib/page-refresh';
    import {installRecordListRefresh,recordSavedEvent,affectsResource} from './src/lib/record-changes';
    const client=new QueryClient(); installRecordListRefresh(client);
    window.reads={tasks:0,contacts:0,effect:0}; window.mounts=0;
    window.changed=url=>window.dispatchEvent(new CustomEvent(recordSavedEvent,{detail:{url,method:'post',record:{id:1}}}));
    window.matches=affectsResource;
    function App(){
      const [value,setValue]=useState(0);
      useEffect(()=>{window.mounts++},[]);
      useRefreshableEffect(()=>{setValue(++window.reads.effect)},[]);
      const tasks=useQuery({queryKey:['crm-tasks'],queryFn:async()=>++window.reads.tasks,staleTime:Infinity});
      useQuery({queryKey:['crm-contacts'],queryFn:async()=>++window.reads.contacts,staleTime:Infinity});
      return <main><input aria-label="Keep draft"/><select aria-label="Keep filter"><option>A</option><option>B</option></select><p id="tasks">{tasks.data}</p><p>{value}</p></main>;
    }
    createRoot(document.getElementById('root')).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/crm/tasks']}><App/></MemoryRouter></QueryClientProvider>);
  `;
  const built=await build({stdin:{contents:source,loader:'tsx',resolveDir:root},bundle:true,write:false,format:'iife',platform:'browser',alias:{'@':path.join(root,'src')}});
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.route('http://records.test/**',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
    await page.goto('http://records.test');
    await page.addScriptTag({content:built.outputFiles[0].text});
    await page.waitForFunction(()=>document.getElementById('tasks')?.textContent==='1');
    await page.getByLabel('Keep draft').fill('Keep my work');
    await page.getByLabel('Keep filter').selectOption('B');
    await page.evaluate(()=>window.changed('/crm/tasks/1'));
    await page.waitForFunction(()=>document.getElementById('tasks')?.textContent==='2');
    assert.deepEqual(await page.evaluate(()=>window.reads),{tasks:2,contacts:1,effect:2});
    assert.equal(await page.getByLabel('Keep draft').inputValue(),'Keep my work');
    assert.equal(await page.getByLabel('Keep filter').inputValue(),'B');
    assert.equal(await page.evaluate(()=>window.mounts),1);
    assert.equal(await page.evaluate(()=>window.matches('/pms/tasks','/project-management/tasks/1')),true);
    assert.equal(await page.evaluate(()=>window.matches('/hrms/employees','/employees/1')),true);
    assert.equal(await page.evaluate(()=>window.matches('/crm/tasks','/crm/task-settings')),false);
    await page.evaluate(()=>window.changed('/crm/contacts/2'));
    await page.waitForFunction(()=>window.reads.contacts===2);
    assert.deepEqual(await page.evaluate(()=>window.reads),{tasks:2,contacts:2,effect:2});
    console.log('PASS: targeted query and read-effect refresh, unrelated lists untouched, drafts/filters/DOM retained, route aliases');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
