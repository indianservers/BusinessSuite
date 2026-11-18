const {build}=require('esbuild');
const {chromium}=require('playwright/test');
const assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
(async()=>{
 const source=`import {cachedFormDefaults,cacheFormDefaults} from './src/lib/form-defaults';import{useAuthStore}from './src/store/authStore';sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');useAuthStore.setState({isAuthenticated:true,user:{id:1,role:'employee',primary_role:'employee',is_superuser:false,access:{companyId:1,grants:{}}}});window.probe={cachedFormDefaults,cacheFormDefaults,store:useAuthStore};`;
 const bundle=await build({stdin:{contents:source,resolveDir:root,loader:'tsx'},tsconfig:path.join(root,'tsconfig.json'),bundle:true,write:false,format:'iife',define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}});
 const browser=await chromium.launch();try{
  const page=await browser.newPage();await page.route('http://preferences.test/**',r=>r.fulfill({contentType:'text/html',body:'Preferences cache fixture'}));
  const boot=async()=>{await page.goto('http://preferences.test/');await page.addScriptTag({content:bundle.outputFiles[0].text});};
  await boot();assert.equal(await page.evaluate(()=>!!window.probe.cachedFormDefaults()),false);
  await page.evaluate(()=>window.probe.cacheFormDefaults({values:{currency:'USD'},modules:{},companyId:1,branchId:1}));
  await boot();assert.equal(await page.evaluate(()=>window.probe.cachedFormDefaults()?.payload.values.currency),'USD');
  assert.equal(await page.evaluate(()=>{sessionStorage.setItem('suite-branch','2');return !!window.probe.cachedFormDefaults();}),false);
  await boot();assert.equal(await page.evaluate(()=>{const s=window.probe.store;s.setState({user:{...s.getState().user,primary_role:'viewer'}});return !!window.probe.cachedFormDefaults();}),false);
  await boot();assert.equal(await page.evaluate(()=>{const entries=JSON.parse(localStorage.getItem('suite-workspace-preferences-v1'));entries[0].savedAt=Date.now()-16*60_000;localStorage.setItem('suite-workspace-preferences-v1',JSON.stringify(entries));return !!window.probe.cachedFormDefaults();}),false);
  await page.evaluate(()=>window.probe.cacheFormDefaults({values:{currency:'INR'},modules:{},companyId:1,branchId:1}));
  assert.equal(await page.evaluate(()=>{window.probe.store.getState().logout();return localStorage.getItem('suite-workspace-preferences-v1');}),null);
  await boot();assert.equal(await page.evaluate(()=>{localStorage.setItem('suite-workspace-preferences-v1','broken JSON');return !!window.probe.cachedFormDefaults();}),false);
  console.log('PASS preferences persist across reload, isolate branch/authority, expire, clear on logout and tolerate corrupt storage');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
