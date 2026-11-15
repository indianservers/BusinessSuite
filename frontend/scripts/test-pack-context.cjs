const assert = require('node:assert/strict');
const {build} = require('esbuild');
const {chromium} = require('playwright');
const path = require('node:path');
(async () => {
 const source = `
 import React,{useEffect} from 'react';import{createRoot}from'react-dom/client';
 import{AxiosHeaders}from'axios';import{api}from'./src/services/api';
 import{setPackContext,selectedPackContext,clearPackContext}from'./src/lib/pack-context';
 import{recordScope}from'./src/lib/record-scope';import{syncScope}from'./src/shared/record-sync/store';
 import{useRecordScopeOwner}from'./src/hooks/use-record-scope-owner';
 import{useAuthStore}from'./src/store/authStore';import{installRecordCache}from'./src/lib/smart-cache/integration';import{QueryClient}from'@tanstack/react-query';
 sessionStorage.setItem('suite-tenant','w');sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');
 useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:1,email:'qa@test.invalid',role:'manager',is_superuser:false},accessToken:'e30.'+btoa(JSON.stringify({sid:1,tenant:'w'}))+'.sig'});
 window.requests=[];window.savedEvents=0;window.addEventListener('suite:record-saved',()=>window.savedEvents++);
 api.defaults.adapter=async config=>{window.requests.push({pack:config.headers.get('X-Suite-Pack-Context')??null,company:config.headers.get('X-Suite-Organization'),tenant:config.headers.get('X-Suite-Tenant')});if(config.url==='/hold')await new Promise(resolve=>window.release=resolve);return{data:{items:[{id:1,pack:config.headers.get('X-Suite-Pack-Context')??null}]},status:200,statusText:'OK',headers:new AxiosHeaders({'x-suite-cache':'memory','x-suite-sync-mode':'full','x-suite-sync-scope':'test'}),config}};
 const client=new QueryClient();installRecordCache(api,client);
 function Owner(){const owns=useRecordScopeOwner();useEffect(()=>{window.owns=owns},[owns]);return null}createRoot(document.getElementById('root')).render(React.createElement(Owner));
 window.h={client,api,setPackContext,selectedPackContext,clearPackContext,scope:()=>recordScope(useAuthStore.getState().user),syncScope};
 `;
 const result = await build({stdin:{contents:source,resolveDir:path.resolve(__dirname,'..'),loader:'tsx'},bundle:true,write:false,format:'iife',platform:'browser',define:{'import.meta.env':'{}','process.env.NODE_ENV':'"test"'},tsconfig:path.resolve(__dirname,'../tsconfig.json')});
 const browser=await chromium.launch();try{const page=await browser.newPage();await page.route('http://localhost:47991/**',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));await page.goto('http://localhost:47991');await page.addScriptTag({content:result.outputFiles[0].text});await page.waitForFunction(()=>window.owns);
 const outcome=await page.evaluate(async()=>{
  const h=window.h;h.client.setQueryData(['unscoped'],{oldPack:true});h.setPackContext('11');await new Promise(resolve=>setTimeout(resolve,0));const queryCleared=h.client.getQueryData(['unscoped'])===undefined;const a=h.scope(),s=h.syncScope();await h.api.get('/catalog/items',{progress:false});await h.api.get('/catalog/items',{progress:false});const repeated=window.requests.length;
  h.setPackContext('22');const different=a!==h.scope()&&s!==h.syncScope();const owns=window.owns();await h.api.get('/catalog/items',{progress:false});
  await h.api.get('/other',{headers:{'X-Suite-Organization':'2','X-Suite-Branch':'3'},progress:false});const destination=window.requests.at(-1).pack;
  await h.api.get('/other',{headers:{'X-Suite-Pack-Context':null},progress:false});const omitted=window.requests.at(-1).pack;
  await h.api.get('/other',{headers:{'X-Suite-Tenant':'other','X-Suite-Organization':'2','X-Suite-Branch':'3','X-Suite-Pack-Context':'99'},_recordSyncBackground:true,progress:false});const explicit=window.requests.at(-1),tenant=sessionStorage.getItem('suite-tenant');
  sessionStorage.setItem('suite-business-pack-context','33');await h.api.get('/other',{progress:false});const conflict=window.requests.at(-1).pack;
  sessionStorage.setItem('suite-pack-context','invalid');sessionStorage.setItem('suite-business-pack-context','invalid');await h.api.get('/other',{progress:false});const invalid=window.requests.at(-1).pack;
  h.setPackContext('11');sessionStorage.setItem('suite-branch','2');const cleared=h.selectedPackContext();
  sessionStorage.setItem('suite-branch','1');h.setPackContext('11');const pending=h.api.post('/hold',{title:'test'},{recordSync:false,progress:false});await new Promise(resolve=>setTimeout(resolve,20));h.setPackContext('22');window.release();let canceled=false;try{await pending}catch(error){canceled=error.code==='ERR_CANCELED'};
  return{queryCleared,repeated,different,owns,destination,omitted,explicit,tenant,conflict,invalid,cleared,savedEvents:window.savedEvents,canceled};
 });
 assert.equal(outcome.queryCleared,true);assert.equal(outcome.repeated,1);assert.equal(outcome.different,true);assert.equal(outcome.owns,false);assert.equal(outcome.destination,null);assert.equal(outcome.omitted,null);assert.equal(outcome.explicit.pack,'99');assert.equal(outcome.tenant,'w');assert.equal(outcome.conflict,'!conflicting-pack-context');assert.equal(outcome.invalid,'invalid');assert.equal(outcome.cleared,null);assert.equal(outcome.savedEvents,0);assert.equal(outcome.canceled,true);
 console.log('PASS pack selector: namespaced cache/sync/async owners, explicit and invalid headers, destination/background isolation, alias conflicts, branch reset and stale mutation callback suppression');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
