const assert = require('node:assert/strict');
const path = require('node:path');
const {build} = require('esbuild');
const {chromium} = require('playwright');
(async () => {
 const source = `
 import{useAuthStore}from'./src/store/authStore';
 import{defaultsScope,installFormDefaults,defaultText,leadSourceOptions}from'./src/lib/form-defaults';
 import{setPackContext,selectedPackContext}from'./src/lib/pack-context';
 useAuthStore.setState({user:{id:1,email:'qa@example.invalid',role:'manager',is_superuser:false,access:{companyId:1}}});
 sessionStorage.setItem('suite-tenant','one');sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','10');
 window.h={defaultsScope,defaultText,leadSourceOptions,setPackContext,selectedPackContext,install:(currency)=>installFormDefaults({values:{currency},modules:{},companyId:1,branchId:10,leadSources:['Pack-specific source']})};
 `;
 const result = await build({stdin:{contents:source,resolveDir:path.resolve(__dirname,'..'),loader:'ts'},bundle:true,write:false,format:'iife',platform:'browser',define:{'import.meta.env':'{}','process.env.NODE_ENV':'"test"'},tsconfig:path.resolve(__dirname,'../tsconfig.json')});
 const browser = await chromium.launch();
 try {
  const page=await browser.newPage();await page.route('http://defaults-scope.test/**',route=>route.fulfill({contentType:'text/html',body:'Defaults scope proof'}));await page.goto('http://defaults-scope.test');await page.addScriptTag({content:result.outputFiles[0].text});
  const proof=await page.evaluate(()=>{
   const h=window.h;h.setPackContext('11');h.install('USD');const first=h.defaultsScope(),draft=h.defaultText('currency');
   h.setPackContext('22');const second=h.defaultsScope(),fallback=h.defaultText('currency'),sources=h.leadSourceOptions();h.install('EUR');const next=h.defaultText('currency');
   sessionStorage.setItem('suite-tenant','two');const tenant=h.defaultsScope(),tenantFallback=h.defaultText('currency'),cleared=h.selectedPackContext();
   sessionStorage.setItem('suite-tenant','one');h.setPackContext('11');h.install('USD');sessionStorage.setItem('suite-business-pack-context','22');const conflict=h.defaultsScope(),conflictFallback=h.defaultText('currency');
   return{first,second,tenant,draft,fallback,sources,next,tenantFallback,cleared,conflict,conflictFallback};
  });
  assert.notEqual(proof.first,proof.second);assert.notEqual(proof.second,proof.tenant);assert.notEqual(proof.first,proof.conflict);
  assert.equal(proof.draft,'USD');assert.equal(proof.fallback,'INR');assert.equal(proof.next,'EUR');assert.equal(proof.tenantFallback,'INR');assert.equal(proof.cleared,null);assert.equal(proof.conflictFallback,'INR');assert.equal(proof.sources.includes('Pack-specific source'),false);
  console.log('PASS form defaults: tenant/pack/alias-conflict namespaces isolate defaults and lead sources while existing draft values remain unchanged');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
