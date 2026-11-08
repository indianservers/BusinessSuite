const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { build } = require('esbuild');
const crypto = require('node:crypto');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = `
import axios, {AxiosHeaders, AxiosError} from 'axios';
import {QueryClient, QueryObserver} from '@tanstack/react-query';
import {installRecordCache} from './src/lib/smart-cache/integration';
import {useAuthStore} from './src/store/authStore';
import * as model from './src/lib/smart-cache/model';
import * as disk from './src/lib/smart-cache/storage';
import {shareRecordReferences} from './src/lib/smart-cache/structural-sharing';
window.testOnline=true;
Object.defineProperty(navigator,'onLine',{get:()=>window.testOnline});
const user=(id=1)=>{useAuthStore.setState({isAuthenticated:true,user:{id,email:'user'+id+'@test.invalid',role:'manager',is_superuser:false},accessToken:'e30.'+btoa(JSON.stringify({sid:id}))+'.sig',refreshToken:'test'});};
user();
const api=axios.create({baseURL:'/api/v1',adapter:async config=>{
 const wire=await window.syncServer({url:config.url,params:config.params,headers:config.headers.toJSON(),actor:useAuthStore.getState().user?.id});
 const response={data:wire.data,status:wire.status,statusText:'OK',headers:new AxiosHeaders(wire.headers),config};
 if(wire.status>=400)throw new AxiosError('Request rejected','ERR_BAD_RESPONSE',config,undefined,response);
 return response;
}});
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
const manager=installRecordCache(api,client);
const changes=[];
window.addEventListener('suite:records-updated',event=>changes.push(event.detail));
let revoked=0;
window.addEventListener('suite:record-access-changed',()=>revoked++);
const counts=async()=>new Promise((resolve,reject)=>{const r=indexedDB.open('suite-record-cache-v1',1);r.onsuccess=()=>{const db=r.result;const tx=db.transaction(['views','records']);const v=tx.objectStore('views').count(),records=tx.objectStore('records').count();tx.oncomplete=()=>{resolve({views:v.result,records:records.result});db.close();};};r.onerror=()=>reject(r.error);});
const age=async()=>{for(const e of manager.memory.values())e.checked=Date.now()-46000;await new Promise((resolve,reject)=>{const r=indexedDB.open('suite-record-cache-v1');r.onsuccess=()=>{const db=r.result;const tx=db.transaction('views','readwrite');const cursor=tx.objectStore('views').openCursor();cursor.onsuccess=()=>{const c=cursor.result;if(c){c.update({...c.value,checked:Date.now()-46000});c.continue();}};tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};});};
window.h={api,client,manager,user,model,disk,changes,counts,age,shareRecordReferences,get revoked(){return revoked},QueryObserver};
`;
(async()=>{
 const built=await build({stdin:{contents:source,resolveDir:root,loader:'ts'},bundle:true,format:'iife',platform:'browser',write:false,alias:{'@':path.join(root,'src')},define:{'import.meta.env.DEV':'true'}});
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext();
 const server={calls:0,rows:Array.from({length:100},(_,id)=>({id:id+1,name:'Person '+id,phone:'123',version:1,description:'x'.repeat(100)})),scope:'permissions1',mode:'normal',delay:0,snapshots:new Map()};
 await context.exposeFunction('syncServer',async request=>{
   server.calls++;
   if(server.delay)await new Promise(r=>setTimeout(r,server.delay));
   if(server.mode==='failure')throw Error('Offline transport');
   if(server.mode==='denied')return {status:403,data:{detail:'Forbidden'},headers:{'cache-control':'no-store'}};
   const rows=structuredClone(server.rows),data={items:rows,total:rows.length};
   if(server.mode==='secret')data.items[0].bank_account='must never persist';
   const headers={'x-suite-cache':'persist','x-suite-sync-scope':`${request.actor}:${server.scope}`,'cache-control':server.mode==='no-store'?'no-store':'private, max-age=0, must-revalidate'};
   const etag='"'+crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex')+'"';
   const old=server.snapshots.get(request.headers['X-Suite-Sync-Cursor']);
   const cursor=crypto.randomUUID();
   server.snapshots.set(cursor,{rows,actor:request.actor,scope:server.scope});
   Object.assign(headers,{etag,'x-suite-sync-cursor':cursor,'x-suite-sync-mode':'full'});
   if(old&&old.actor===request.actor&&old.scope===server.scope){
     const oldEtag='"'+crypto.createHash('sha256').update(JSON.stringify({items:old.rows,total:old.rows.length})).digest('hex')+'"';
     if(etag===oldEtag&&request.headers['If-None-Match']===etag)return {status:304,data:'',headers:{...headers,'x-suite-sync-mode':'unchanged'}};
     headers['x-suite-sync-mode']='delta';
     return {status:200,headers,data:{schema:1,key:'items',meta:{total:rows.length},order:rows.map(r=>String(r.id)),upserts:rows.filter(r=>JSON.stringify(r)!==JSON.stringify(old.rows.find(o=>o.id===r.id))),removed:old.rows.filter(o=>!rows.some(r=>r.id===o.id)).map(r=>String(r.id))}};
   }
   return {status:200,data,headers};
 });
 await context.route('https://cache.test/**',route=>route.fulfill({contentType:'text/html',body:'<html><body>Cache tests</body></html>'}));
 const newPage=async()=>{const p=await context.newPage();await p.goto('https://cache.test/');await p.addScriptTag({content:built.outputFiles[0].text});return p;};
 const page=await newPage();
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  const first=await page.evaluate(async()=>{const start=performance.now();const r=await h.api.get('/crm/leads');return {count:r.data.items.length,ms:performance.now()-start};});
  assert.equal(first.count,100);assert.equal(server.calls,1);
  const repeat=await page.evaluate(async()=>{const start=performance.now();await h.api.get('/crm/leads');return performance.now()-start;});
  assert.equal(server.calls,1,'repeat read avoids network');
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:1,records:100});
  assert.equal(await page.evaluate(()=>[...h.manager.configs.values()].every(c=>!c.headers.has('Authorization'))),true);
  // A real QueryObserver verifies query dependencies and stable row references.
  await page.evaluate(async()=>{window.observer=new h.QueryObserver(h.client,{queryKey:['leads'],queryFn:()=>h.api.get('/crm/leads').then(r=>r.data)});window.unsubscribe=observer.subscribe(()=>{});await observer.refetch();window.unchangedRow=h.client.getQueryData(['leads']).items[1];});
  server.rows[0].phone='987';server.rows.splice(9,1);server.rows.unshift({id:1001,name:'New',phone:'456',version:1,description:'new'});
  await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));
  assert.deepEqual(await page.evaluate(()=>{const d=h.client.getQueryData(['leads']);return {phone:d.items.find(r=>r.id===1).phone,removed:!d.items.some(r=>r.id===10),inserted:d.items[0].id,stable:d.items.find(r=>r.id===2)===unchangedRow};}),{phone:'987',removed:true,inserted:1001,stable:true});
  assert.equal(server.calls,2);
  await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));assert.equal(server.calls,3,'304 check');
  const second=await newPage();
  const beforeReload=server.calls;
  assert.equal(await second.evaluate(async()=>(await h.api.get('/crm/leads')).data.items[0].id),1001);
  assert.equal(server.calls,beforeReload,'new tab renders IndexedDB without another download');
  await page.evaluate(()=>h.age());await second.evaluate(()=>h.age());
  const beforeTabs=server.calls;
  await Promise.all([page.evaluate(()=>h.manager.syncModuleChanges()),second.evaluate(()=>h.manager.syncModuleChanges())]);
  assert.equal(server.calls,beforeTabs+1,'Web Lock deduplicates background synchronization');
  await second.close();
  // Offline reads, transport failure, and reconnect.
  await page.evaluate(()=>{window.testOnline=false;});
  const offlineCalls=server.calls;
  assert.equal(await page.evaluate(async()=>(await h.api.get('/crm/leads')).data.total),100);assert.equal(server.calls,offlineCalls);
  await page.evaluate(()=>{window.testOnline=true;});server.mode='failure';
  await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));
  assert.equal(await page.evaluate(()=>h.manager.getSyncStatus().health),'error');
  server.mode='normal';await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));
  assert.equal(await page.evaluate(()=>h.manager.getSyncStatus().health),'idle');
  // Safe optimistic edit rolls back a version conflict; approval edits wait for confirmation.
  const optimistic=await page.evaluate(async()=>{const before=(await h.manager.getCachedRecord('lead',1)).phone;let fail;const request=new Promise((_,reject)=>fail=reject);const pending=h.manager.optimisticEdit('lead',1,{phone:'optimistic'},1,()=>request).catch(()=>{});await new Promise(r=>setTimeout(r,0));const shown=(await h.manager.getCachedRecord('lead',1)).phone;fail(Error('HTTP 409 version conflict'));await pending;return {before,shown,after:(await h.manager.getCachedRecord('lead',1)).phone};});
  assert.equal(optimistic.shown,'optimistic');assert.equal(optimistic.before,optimistic.after);
  const risky=await page.evaluate(async()=>{let finish;const request=new Promise(resolve=>finish=resolve);const n=h.changes.length;const pending=h.manager.optimisticEdit('lead',1,{status:'Approved'},1,()=>request);await new Promise(r=>setTimeout(r,0));const emitted=h.changes.length-n;finish({data:{}});await pending;return emitted;});assert.equal(risky,0);
  // Role/scope changes and HTTP denial clear persisted and visible data.
  await page.evaluate(()=>{unsubscribe();h.client.removeQueries();});server.scope='permissions2';await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));
  assert.equal(await page.evaluate(()=>h.manager.getSyncStatus().views),0);
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  await page.evaluate(()=>h.api.get('/crm/leads'));
  await page.evaluate(async()=>{window.deniedObserver=new h.QueryObserver(h.client,{queryKey:['denial'],queryFn:()=>h.api.get('/crm/leads').then(r=>r.data)});window.stopDenied=deniedObserver.subscribe(()=>{});await deniedObserver.refetch();});const beforeDenied=server.calls;server.mode='denied';await page.evaluate(()=>h.manager.syncModuleChanges(undefined,true));
  assert.equal(await page.evaluate(()=>h.manager.getSyncStatus().views),0);
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  await page.waitForTimeout(60);assert.equal(server.calls,beforeDenied+1,'denied active queries must not refetch in a loop');assert.equal(await page.evaluate(()=>h.client.getQueryData(['denial'])===undefined),true);await page.evaluate(()=>{stopDenied();h.client.removeQueries();});
  server.mode='normal';await page.evaluate(()=>h.api.get('/crm/leads'));
  await page.evaluate(()=>{h.user(2);h.manager.contextChanged();});
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  const beforeUser=server.calls;await page.evaluate(()=>h.api.get('/crm/leads'));assert.equal(server.calls,beforeUser+1,'different user must fetch own data');
  // Logout while an authorized response is in flight cannot restore old records.
  await page.evaluate(()=>h.manager.clear());server.delay=150;
  const flight=page.evaluate(()=>h.api.get('/crm/leads').then(()=>false,()=>true));
  await new Promise(r=>setTimeout(r,40));await page.evaluate(()=>{h.user(3);h.manager.contextChanged();});
  assert.equal(await flight,true);server.delay=0;
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  server.mode='secret';await page.evaluate(()=>h.api.get('/crm/leads'));
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  server.mode='no-store';await page.evaluate(()=>h.api.get('/crm/leads'));
  assert.deepEqual(await page.evaluate(()=>h.counts()),{views:0,records:0});
  server.mode='normal';await page.evaluate(()=>h.manager.clear());
  const beforeConcurrent=server.calls;await page.evaluate(()=>Promise.all(Array.from({length:8},()=>h.api.get('/crm/leads'))));assert.equal(server.calls,beforeConcurrent+1,'concurrent reads deduplicated');
  const beforeObserved=server.calls;
  await page.evaluate(async()=>{window.stopObserved=h.manager.observeView('/crm/leads');for(const entry of h.manager.memory.values())entry.accessed=Date.now()-180000;await h.age();await h.manager.syncModuleChanges();stopObserved();});
  assert.equal(server.calls,beforeObserved+1,'mounted state-based grids keep synchronizing after the recent-use window');
  // Filter isolation and bounded storage eviction.
  await page.evaluate(async()=>{const base=[...h.manager.memory.values()][0];for(let i=0;i<103;i++){await h.disk.saveCachedRecords({...base,key:base.scope+':filter'+i,url:'/crm/leads?page='+i,accessed:Date.now()+i});}});
  assert.ok((await page.evaluate(()=>h.counts())).views<=100);
  assert.equal(await page.evaluate(()=>h.model.splitView(Array.from({length:501},(_,id)=>({id})))===undefined),true);
  const large=await page.evaluate(()=>{const old=Array.from({length:10000},(_,id)=>({id,name:'Row '+id}));const next=old.map(row=>({...row}));next[500].name='Changed';const start=performance.now();const shared=h.shareRecordReferences(old,next);return {ms:performance.now()-start,retained:shared.filter((row,i)=>row===old[i]).length};});assert.equal(large.retained,9999);
  console.log(`BENCHMARK 10,000-row structural comparison: ${large.ms.toFixed(1)}ms; 9,999 unchanged row references retained. Browser storage still accepts only requested pages up to 500 rows.`);
  assert.equal(await page.evaluate(()=>{try{h.model.applyChangedRecords({items:[{id:1}]},{schema:1,key:'items',meta:{},order:['2'],upserts:[],removed:[]});return false;}catch{return true;}}),true);
  await page.evaluate(()=>h.manager.clear());
  const diskless=await newPage();await diskless.evaluate(()=>{indexedDB.open=()=>{throw Error('Storage disabled');};});
  assert.equal(await diskless.evaluate(async()=>(await h.api.get('/crm/leads')).data.items.length),100);await diskless.close();
  // A confirmed HRMS edit reconciles the PMS projection of the same person.
  await page.evaluate(async()=>{await h.manager.clear();await h.api.get('/employees/');await h.api.get('/project-management/people-workspace/people');});
  const beforeUnrelatedMutation=server.calls;
  await page.evaluate(()=>h.manager.afterMutation('/crm/tasks'));
  assert.equal(server.calls,beforeUnrelatedMutation,'uncached task writes must not reload unrelated cached lists');
  server.rows[0].phone='cross-module-change';
  await page.evaluate(()=>h.manager.afterMutation('/employees/1001'));
  assert.deepEqual(await page.evaluate(async()=>[(await h.api.get('/employees/')).data.items[0].phone,(await h.api.get('/project-management/people-workspace/people')).data.items[0].phone]),['cross-module-change','cross-module-change']);
  // Product and service IDs may overlap; source-specific projections stay isolated.
  assert.equal(await page.evaluate(()=>h.model.splitView({items:[{id:1,kind:'product'},{id:1,kind:'service'}]}).rows.length),2);
  await page.evaluate(async()=>{await h.manager.clear();await h.api.get('/catalog/items',{params:{source:'crm'}});await h.api.get('/catalog/items',{params:{source:'srm'}});});
  assert.equal(await page.evaluate(()=>new Set([...h.manager.memory.values()].map(e=>e.projection)).size),2);
  assert.deepEqual(errors,[]);
  console.log('PASS: persistent reload, instant repeat reads, delta updates/inserts/deletes, 304, stable query row references, cross-tab locks, offline/reconnect/backoff, optimistic rollback/conflicts, risky-action gating, permission/scope/user changes, logout race, no-store/secrets, deduplication, eviction, stale delta and storage failure.');
  console.log(`BENCHMARK fixture: first=${first.ms.toFixed(1)}ms, memory repeat=${repeat.toFixed(1)}ms; 8 simultaneous reads -> 1 request; repeat view -> 0 requests. These are local fixture results, not production latency claims.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
