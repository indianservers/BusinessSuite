const assert=require('node:assert/strict');
const {buildSync}=require('esbuild');
const {AxiosHeaders,AxiosError}=require('axios');
const code=buildSync({entryPoints:['src/lib/identity-read-transport.ts'],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
const mod={exports:{}};new Function('module','exports','require',code)(mod,mod.exports,require);
const {identityReadTransport}=mod.exports;
const request=(headers={},extra={})=>({url:'/access/me',method:'get',headers:new AxiosHeaders({Authorization:'Bearer test-A','X-Suite-Organization':'1','X-Suite-Branch':'1',...headers}),...extra});
const uri=c=>`${c.baseURL||''}${c.url}?${JSON.stringify(c.params||{})}`;
(async()=>{
 let calls=0;
 const wrapped=identityReadTransport(async config=>{calls++;await new Promise(r=>setTimeout(r,5));return {data:{fresh:true},status:200,statusText:'OK',headers:{},config};},uri);
 const a=request({'X-Request-ID':'one'}),b=request({'X-Request-ID':'two'});
 const [ra,rb]=await Promise.all([wrapped(a),wrapped(b)]);
 assert.equal(calls,1);assert.equal(ra.config,a);assert.equal(rb.config,b);
 await wrapped(a);assert.equal(calls,2,'settled identity is never cached');
 for(const headers of [{Authorization:'Bearer test-B'},{'X-Suite-Organization':'2'},{'X-Suite-Branch':'2'},{'X-Suite-Tenant':'another'},{'X-Suite-Pack-Context':'2'},{'X-Suite-Expected-Pack-Realm':'pack'}]){
  let before=calls;await Promise.all([wrapped(a),wrapped(request(headers))]);assert.equal(calls-before,2,'identity boundaries cannot share a request');
 }
 for(const extra of [{method:'post'},{url:'/srm/reports'},{signal:new AbortController().signal}]){
  let before=calls;await Promise.all([wrapped(request({},extra)),wrapped(request({},extra))]);assert.equal(calls-before,2);
 }
 let failures=0;
 const failed=identityReadTransport(async config=>{failures++;await new Promise(r=>setTimeout(r,5));throw new AxiosError('Expired','ERR_BAD_RESPONSE',config,null,{status:401,data:{},config});},uri);
 const errors=await Promise.allSettled([failed(a),failed(b)]);
 assert.equal(failures,1);assert.equal(errors[0].reason.config,a);assert.equal(errors[1].reason.config,b);
 assert.equal(errors[1].reason.response.config,b);
 await assert.rejects(failed(a));assert.equal(failures,2,'failed reads must leave no stored result');
 console.log('Identity transport: concurrent sharing, fresh retries, six scope boundaries, cancellation and errors passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
