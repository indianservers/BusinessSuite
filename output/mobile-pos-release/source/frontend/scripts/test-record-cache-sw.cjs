const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
(async()=>{
 const origin='https://suite.test', handlers={}, entries=new Map(), deleted=[];
 let requests=0, offline=false, quota=false, storageDenied=false;
 const key=value=>new URL(typeof value==='string'?value:value.url,origin).href;
 const cache={
  match:async request=>entries.get(key(request))?.clone(),
  put:async(request,response)=>{if(quota)throw Error('QuotaExceeded');entries.set(key(request),response.clone());},
  keys:async()=>[...entries.keys()].map(url=>new Request(url)),
  delete:async request=>entries.delete(key(request)),
 };
 const caches={open:async()=>{if(storageDenied)throw Error('Storage disabled');return cache;},keys:async()=>['business-suite-shell-v3','another-app-cache','business-suite-shell-v4','business-suite-shell-v5'],delete:async name=>{deleted.push(name);return true;},match:cache.match};
 const fetch=async request=>{requests++;if(offline)throw Error('Offline');const url=new URL(key(request));return new Response(url.pathname==='/'?'shell':'asset',{headers:{'cache-control':url.pathname.includes('app-config')||url.pathname.includes('private')?'no-store':'public, max-age=0'}});};
 const sandbox={self:{location:{origin},addEventListener:(name,fn)=>handlers[name]=fn,skipWaiting(){},clients:{claim(){}}},caches,fetch,URL,Response};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../public/sw.js'),'utf8'),sandbox);
 const lifecycle=async name=>{let promise;handlers[name]({waitUntil:p=>promise=p});await promise;};
 const read=async(url,mode='cors')=>{let response;handlers.fetch({request:{method:'GET',url:origin+url,mode},respondWith:p=>response=p});return response===undefined?undefined:await response;};
 await lifecycle('install');
 assert.ok(entries.has(origin+'/'),'offline shell is eligible');
 assert.ok(!entries.has(origin+'/app-config.js'),'no-store shell responses must not persist');
 await lifecycle('activate');assert.deepEqual(deleted,['business-suite-shell-v3','business-suite-shell-v4','business-suite-shell-v5'],'other apps caches are preserved');
 let warming;
 handlers.message({source:{url:origin+'/pms/tasks'},data:{type:'CACHE_VISITED_ASSETS',urls:[origin+'/assets/first-load.js',origin+'/api/v1/auth/me',origin+'/uploads/private.pdf','https://other.test/assets/app.js']},waitUntil:p=>warming=p});
 await warming;
 assert.ok(entries.has(origin+'/assets/first-load.js'),'first page assets loaded before worker control are warmed');
 assert.ok(!entries.has(origin+'/api/v1/auth/me')&&!entries.has(origin+'/uploads/private.pdf'),'private data never enters the public asset cache');
 for(let i=0;i<150;i++)await read('/assets/module-'+i+'.js');
 assert.ok(entries.has(origin+'/assets/first-load.js'),'visiting more modules does not evict the first page at the old 100 asset limit');
 const beforeApi=requests;assert.equal(await read('/api/v1/employees'),undefined);assert.equal(requests,beforeApi,'authenticated API responses bypass service worker cache');
 const beforeAsset=requests;assert.equal(await (await read('/assets/app-hash.js')).text(),'asset');assert.equal(await (await read('/assets/app-hash.js')).text(),'asset');assert.equal(requests,beforeAsset+1,'hashed assets reuse cache');
 const beforePrivate=requests;await read('/assets/private-hash.js');await read('/assets/private-hash.js');assert.equal(requests,beforePrivate+2,'no-store asset responses are not cached');
 quota=true;assert.equal(await (await read('/assets/quota-hash.js')).text(),'asset','quota failure preserves network success');quota=false;
 storageDenied=true;assert.equal(await (await read('/assets/storage-disabled.js')).text(),'asset','disabled cache storage preserves network success');storageDenied=false;
 offline=true;assert.equal(await (await read('/crm/leads','navigate')).text(),'shell','offline navigation uses only the public shell');
 console.log('PASS: service-worker API exclusion, no-store policies, immutable asset reuse, offline shell, quota/storage fallback and scoped cache cleanup.');
})().catch(error=>{console.error(error);process.exit(1);});
