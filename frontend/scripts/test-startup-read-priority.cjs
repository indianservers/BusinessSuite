const assert=require('node:assert/strict'),{buildSync}=require('esbuild'),{AxiosHeaders}=require('axios');
const code=buildSync({entryPoints:['src/lib/startup-read-priority.ts'],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
const mod={exports:{}};new Function('module','exports','require',code)(mod,mod.exports,require);const {startupReadPriority}=mod.exports;
const config=(url,extra={})=>({url,method:'get',headers:new AxiosHeaders(),...extra});
(async()=>{
 for(const [route,url]of [['/srm/pos/terminal','/srm/industry/capabilities'],['/srm/appointments','/srm/industry/capabilities'],['/srm/service-scheduling','/employees/planned-services'],['/srm/inventory/products','/branches/context']]){
  const calls=[];const wrapped=startupReadPriority(async c=>{calls.push(c.url);return {data:{fresh:true},status:200,config:c};},()=>({route,scope:'A'}),1000,0);
  const waiting=['/notifications/summary','/access/setup','/access/enterprise/branding'].map(u=>wrapped(config(u)));
  await Promise.resolve();assert.deepEqual(calls,[]);await wrapped(config('/auth/me'));assert.deepEqual(calls,['/auth/me']);await wrapped(config(url));await Promise.all(waiting);assert.equal(calls.length,5);
  await wrapped(config('/access/setup'));assert.equal(calls.length,6,'settled results are never cached');
 }
 let context={route:'/srm/pos/terminal',scope:'A'},calls=[];
 const wrapped=startupReadPriority(async c=>{calls.push(c.url);if(c.url.endsWith('capabilities'))throw Error('revoked');return {status:200,config:c};},()=>context,25,0);
 const controller=new AbortController();const canceled=wrapped(config('/notifications/summary',{signal:controller.signal}));const rejected=assert.rejects(canceled,e=>e.code==='ERR_CANCELED');controller.abort();await rejected;assert.deepEqual(calls,[]);
 const setup=wrapped(config('/access/setup'));await assert.rejects(wrapped(config('/srm/industry/capabilities')));await setup;assert.equal(calls.filter(u=>u==='/access/setup').length,1,'errors release informational setup');
 context={...context,scope:'B'};const old=wrapped(config('/access/setup'));const changed=assert.rejects(old,e=>e.code==='ERR_CANCELED');context={...context,scope:'C'};await changed;assert.equal(calls.filter(u=>u==='/access/setup').length,1,'old authority must not reach transport');
 const bounded=wrapped(config('/access/setup'));await bounded;assert.equal(calls.filter(u=>u==='/access/setup').length,2,'bounded timeout always releases metadata');
 context={...context,scope:'D'};const deferred=wrapped(config('/access/setup'));await wrapped(config('/srm/sales',{method:'post'}));await deferred;
 context=null;await wrapped(config('/access/setup'));
 console.log('PASS startup priority: four destinations, immediate fresh identity, bounded delay, cancellation, scope change, error, user action and no response caching.');
})().catch(e=>{console.error(e);process.exitCode=1});
