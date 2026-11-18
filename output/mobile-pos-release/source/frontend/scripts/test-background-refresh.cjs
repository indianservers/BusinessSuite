const assert = require('node:assert/strict');
const {build} = require('esbuild');
const {chromium} = require('playwright');
const path = require('node:path');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const source=`
 import React,{useState,useEffect} from 'react';
 import {createRoot} from 'react-dom/client';
 import {MemoryRouter,useNavigate} from 'react-router-dom';
 import {QueryClient} from '@tanstack/react-query';
 import {useInitialLoading} from './src/hooks/use-initial-loading';
 import {usePageRefresh,refreshPageData} from './src/lib/page-refresh';
 import {NativeSelect} from './src/components/ui/native-select';
 const client=new QueryClient();window.mounts=0;
 function Content({value}) {useEffect(()=>{window.mounts++},[]);return <div><input id="draft"/><span id="value">{value}</span></div>}
 function App(){
 const [loading,setLoading]=useState(true),[value,setValue]=useState('original');
 const initial=useInitialLoading(loading),navigate=useNavigate();
 window.initial=()=>setLoading(false);
 window.navigate=()=>{navigate('/other');setLoading(true)};
 usePageRefresh(()=>new Promise((resolve,reject)=>{setLoading(true);window.finish=(fail=false)=>{setLoading(false);if(fail)reject(Error('failed'));else{setValue('updated');resolve()}}}));
 window.refresh=()=>{window.done='';refreshPageData(client).then(()=>window.done='ok',()=>window.done='failed')};
 return <><p id="busy">{String(loading)}</p>{initial?<p id="initial">Loading</p>:<Content value={value}/>}<NativeSelect aria-label="Choices" loading={loading} searchable><option value="">Choose</option><option value="a">Alpha</option><option value="b">Beta</option></NativeSelect></>;
 }
 createRoot(document.getElementById('root')).render(<MemoryRouter><App/></MemoryRouter>);`;
 const built=await build({stdin:{contents:source,loader:'tsx',resolveDir:root},bundle:true,write:false,format:'iife',platform:'browser',alias:{'@':path.join(root,'src')},define:{'import.meta.env.DEV':'false'}});
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage();
 await page.route('http://smooth.test/**',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
 await page.goto('http://smooth.test');await page.addScriptTag({content:built.outputFiles[0].text});await page.waitForSelector('#initial');
 await page.evaluate(()=>window.initial());await page.locator('#draft').fill('Unsaved draft');
 await page.locator('select[aria-label="Choices"]').selectOption('b');
 for(const fail of [false,true]){
 await page.evaluate(()=>window.refresh());await page.waitForFunction(()=>document.querySelector('#busy').textContent==='true');
 assert.equal(await page.locator('#initial').count(),0);
 assert.equal(await page.locator('#draft').inputValue(),'Unsaved draft');
 assert.equal(await page.locator('select[aria-label="Choices"] option[value=""]').textContent(),'Choose');
 assert.equal(await page.locator('select[aria-label="Choices"]').inputValue(),'b');
 await page.locator('select[aria-label="Choices"]').selectOption('a');
 await page.locator('select[aria-label="Choices"]').selectOption('b');
 await page.evaluate(f=>window.finish(f),fail);await page.waitForFunction(()=>!!window.done);
 assert.equal(await page.evaluate(()=>window.done),fail?'failed':'ok');
 assert.equal(await page.locator('#value').textContent(),'updated');
 assert.equal(await page.evaluate(()=>window.mounts),1);
 }
 await page.evaluate(()=>window.navigate());await page.waitForSelector('#initial');
 console.log('PASS: initial and route loading, background success/failure, retained draft/DOM, usable dropdown choices');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
