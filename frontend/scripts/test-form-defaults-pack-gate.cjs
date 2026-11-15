const assert = require('node:assert/strict');
const path = require('node:path');
const {build} = require('esbuild');
const {chromium, expect} = require('playwright/test');
const root = path.resolve(__dirname, '..');
const source = `
import React,{useState} from 'react';import{createRoot}from'react-dom/client';
import{QueryClient,QueryClientProvider}from'@tanstack/react-query';
import Gate from './src/components/forms/FormDefaultsGate';
import{defaultText}from'./src/lib/form-defaults';import{setPackContext}from'./src/lib/pack-context';
import{useAuthStore}from'./src/store/authStore';
sessionStorage.setItem('suite-tenant','defaults-pack-proof');sessionStorage.setItem('suite-organization','41');sessionStorage.setItem('suite-branch','3');
useAuthStore.setState({user:{id:11,email:'gate@example.invalid',role:'manager',access:{companyId:41}}});
function Form(){const[currency]=useState(()=>defaultText('currency'));return <output data-testid="currency">{currency}</output>}
createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><button onClick={()=>setPackContext('11')}>First pack</button><button onClick={()=>setPackContext('22')}>Second pack</button><Gate><Form/></Gate></QueryClientProvider>);
`;
(async()=>{
 const bundle=await build({stdin:{contents:source,resolveDir:root,loader:'tsx'},tsconfig:path.join(root,'tsconfig.json'),bundle:true,write:false,format:'iife',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}});
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage();let release,delay=false;const calls=[],errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/access/settings/defaults/effective',async route=>{
   const pack=route.request().headers()['x-suite-pack-context']||'';calls.push(pack);
   if(pack==='11'&&delay)await new Promise(resolve=>{release=resolve});
   await route.fulfill({json:{companyId:41,branchId:3,values:{currency:pack==='11'?'USD':pack==='22'?'EUR':'INR'},modules:{}}}).catch(()=>{});
  });
  await page.route('http://pack-defaults.test/',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
  await page.goto('http://pack-defaults.test/');await page.addScriptTag({content:bundle.outputFiles[0].text});
  await expect(page.getByTestId('currency')).toHaveText('INR');
  await page.getByRole('button',{name:'First pack'}).click();await expect(page.getByTestId('currency')).toHaveText('USD');
  await page.getByRole('button',{name:'Second pack'}).click();await expect(page.getByTestId('currency')).toHaveText('EUR');
  // A fresh page avoids reusing the already cached first-pack success.
  await page.reload();delay=true;await page.addScriptTag({content:bundle.outputFiles[0].text});
  await expect(page.getByTestId('currency')).toHaveText('EUR');
  await page.getByRole('button',{name:'First pack'}).click();await expect.poll(()=>typeof release).toBe('function');
  await page.getByRole('button',{name:'Second pack'}).click();await expect(page.getByTestId('currency')).toHaveText('EUR');
  release();await page.waitForLoadState('networkidle');await expect(page.getByTestId('currency')).toHaveText('EUR');
  assert.deepEqual(errors,[]);assert(calls.includes('11')&&calls.includes('22'));
  console.log('PASS actual defaults gate: pack selection reloads starting values; delayed previous-pack response never installs into the current form');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
