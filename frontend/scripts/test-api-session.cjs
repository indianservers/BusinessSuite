const assert = require('node:assert/strict');
const path = require('node:path');
const {buildSync} = require('esbuild');
const axios = require('axios');
// Compile the real interceptor; stub only its browser/UI dependencies.
const source = require('node:fs').readFileSync(path.join(__dirname,'../src/services/api.ts'),'utf8')
 .replace(/import \{ useAuthStore \}[^;]+;/,'const useAuthStore = {getState: () => globalThis.__sessionTestState};')
 .replace(/import \{ getApiBaseUrl \}[^;]+;/,'const getApiBaseUrl = () => "https://suite.test/api/v1";')
 .replace(/import \{ beginProgress \}[^;]+;/,'const beginProgress = () => () => {};')
 .replace(/import \{ trackPageRefreshRead \}[^;]+;/,'const trackPageRefreshRead = () => () => {};')
 .replace(/import \{ selectedBranch \}[^;]+;/,'const selectedBranch = () => null;');
const code = buildSync({stdin:{contents:source,resolveDir:path.join(__dirname,'..'),loader:'ts'},bundle:true,platform:'node',format:'cjs',external:['axios'],define:{'import.meta.env':'{}'},write:false}).outputFiles[0].text;
global.sessionStorage = {getItem:()=>null};
global.window = {location:{search:""},dispatchEvent:()=>{}};
function load(adapter) {
 let loggedOut=0;
 const state=global.__sessionTestState={accessToken:'expired',refreshToken:'refresh-old',setTokens(a,r){state.accessToken=a;state.refreshToken=r;},logout(){loggedOut++;state.accessToken=null;state.refreshToken=null;}};
 axios.defaults.adapter=adapter;
 const mod={exports:{}}; new Function('module','exports','require',code)(mod,mod.exports,require);
 return {api:mod.exports.api,state,loggedOut:()=>loggedOut};
}
function failure(config,status) {
 const response=status ? {status,data:{detail:'test failure'},headers:{},config,statusText:'test'} : undefined;
 return Promise.reject(new axios.AxiosError('test failure',status?'ERR_BAD_RESPONSE':'ERR_NETWORK',config,undefined,response));
}
function ok(config,data) {return Promise.resolve({status:200,data,headers:{},config,statusText:'OK'});}
(async()=>{
 for (const status of [undefined,429,500,503]) {
  const app=load(c=>failure(c,c.url.endsWith('/auth/refresh')?status:401));
  await assert.rejects(app.api.get('/probe')); assert.equal(app.loggedOut(),0); assert.equal(app.state.refreshToken,'refresh-old');
 }
 for (const status of [401,403]) {
  const app=load(c=>failure(c,c.url.endsWith('/auth/refresh')?status:401));
  await assert.rejects(app.api.get('/probe')); assert.equal(app.loggedOut(),1);
 }
 let refreshes=0;
 const app=load(async c=>{
  if(c.url.endsWith('/auth/refresh')) {refreshes++;await new Promise(r=>setTimeout(r,10));return ok(c,{access_token:'new',refresh_token:'refresh-new'});}
  return c.headers.Authorization==='Bearer new'?ok(c,{loaded:true}):failure(c,401);
 });
 const results=await Promise.all([app.api.get('/one'),app.api.get('/two')]);
 assert.equal(refreshes,1);assert(results.every(r=>r.data.loaded));assert.equal(app.state.refreshToken,'refresh-new');
 let resolveRefresh;
 const race=load(c=> c.url.endsWith('/auth/refresh')?new Promise(r=>{resolveRefresh=()=>r({status:200,data:{access_token:'stale',refresh_token:'stale-refresh'},headers:{},config:c});}):failure(c,401));
 const pending=race.api.get('/probe');
 while(!resolveRefresh) await new Promise(r=>setImmediate(r));
 race.state.logout();resolveRefresh();await assert.rejects(pending);assert.equal(race.state.accessToken,null);
 console.log('Session checks passed: transient failures, revocation, concurrent refresh, sign-out race.');
})().catch(e=>{console.error(e);process.exitCode=1;});
