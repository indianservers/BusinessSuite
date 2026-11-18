const { build } = require('esbuild');
const { chromium, expect } = require('playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const fields = JSON.parse(fs.readFileSync(path.resolve(root, '../backend/app/core/form_defaults.json'), 'utf8'));
const base = Object.fromEntries(fields.map(f => [f.key, f.default]));
const mock = `import {installFormDefaults} from '@/lib/form-defaults';
const fields=${JSON.stringify(fields)},base=${JSON.stringify(base)};
const store={};const choices={branches:[{value:1,label:'Head office'},{value:2,label:'Mumbai'}],departments:[],cost_centers:[],accounting_cost_centers:[],pipelines:[],stages:[],users:[],shifts:[],leave_types:[],price_books:[],bank_accounts:[],payment_modes:[]};
const key=p=>(p?.module||'')+':'+(p?.branch_id||'');
const effective=()=>({values:{...base,...store[':']?.values},modules:{crm:{...base,...store[':']?.values,...store['crm:']?.values}},companyId:1,branchId:1});
export const api={get:async(url,config)=>{if(url.includes('/effective'))return {data:effective()};const row=store[key(config?.params)]||{values:{},version:0};return {data:{fields,choices,overrides:row.values,version:row.version,inherited:{...base,...(key(config?.params)!==':'?store[':']?.values:{})},effective:base,companyId:1}};},put:async(url,data,config)=>{const k=key(config?.params);store[k]={values:JSON.parse(JSON.stringify(data.values)),version:data.version+1};globalThis.__saved=store;return {data:{saved:true,version:data.version+1}}}};`;
const source = `import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import DefaultsSettings from './src/pages/settings/DefaultsSettings';import FormDefaultsGate from './src/components/forms/FormDefaultsGate';import {defaultText,defaultNumber,defaultOwner,displayDate,displayTime,installFormDefaults} from './src/lib/form-defaults';import {useAuthStore} from './src/store/authStore';
useAuthStore.getState().setUser({id:1,email:'test@example.invalid',is_superuser:true,role:'super_admin',access:{companyId:1}});
function Draft(){const [currency]=useState(()=>defaultText('currency','crm'));return <output data-testid='draft'>{currency}</output>}
function App(){const [revision,S]=useState(0);return <><a href="/leave">Leave settings</a><button onClick={()=>S(x=>x+1)}>New form</button><Draft key={revision}/><DefaultsSettings/></>}
createRoot(document.getElementById('root')).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><FormDefaultsGate><App/></FormDefaultsGate></QueryClientProvider>);`;
(async()=>{
const result=await build({stdin:{contents:source,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',loader:{'.css':'empty'},define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'},plugins:[{name:'mock-api',setup(build){build.onLoad({filter:/[\\/]services[\\/]api\.ts$/},()=>({contents:mock,loader:'ts',resolveDir:path.join(root,'src/services')}));}}]});
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('http://defaults.test/**',route=>route.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));await page.goto('http://defaults.test/');
 await page.addStyleTag({content:fs.readFileSync(path.join(root,'src/pages/settings/defaults-settings.css'),'utf8')+' body{font-family:Arial;margin:24px} :root{--border:214 32% 91%;--background:0 0% 100%;--muted:210 40% 96%;--muted-foreground:215 16% 47%} button,input,select{font:inherit}'});
 await page.addScriptTag({content:result.outputFiles[0].text});
 await expect(page.getByRole('heading',{name:'General',exact:true})).toBeVisible();
 await expect(page.getByTestId('draft')).toHaveText('INR');
 await expect(page.getByRole('button',{name:'Currency',exact:true})).toBeDisabled();
 await page.getByRole('checkbox',{name:'Custom currency',exact:true}).check();
 const cancelLeave=dialog=>dialog.dismiss();page.once('dialog',cancelLeave);await page.getByRole('link',{name:'Leave settings'}).click();await expect(page).toHaveURL('http://defaults.test/');
 const trigger=page.getByRole('button',{name:'Currency',exact:true});assert.ok((await trigger.boundingBox()).width<=132);await trigger.click();
 const search=page.getByRole('combobox',{name:'Search currency',exact:true});await search.fill('USD');await search.press('Enter');
 await page.getByRole('button',{name:'Save defaults',exact:true}).click();await expect(page.getByText('Defaults saved. New forms will use these values.')).toBeVisible();
 await expect(page.getByTestId('draft')).toHaveText('INR');await page.getByRole('button',{name:'New form',exact:true}).click();await expect(page.getByTestId('draft')).toHaveText('USD');
 await expect.poll(()=>page.evaluate(()=>globalThis.__saved[':'].values.currency)).toBe('USD');
 await page.getByRole('textbox',{name:'Search defaults'}).fill('priority');await expect(page.getByRole('heading',{name:'General',exact:true})).toHaveCount(0);await expect(page.getByRole('checkbox',{name:'Custom task priority'})).toBeVisible();
 await page.getByRole('textbox',{name:'Search defaults'}).fill('');
 // Scope changes preserve inheritance and let individual values be reset.
 await page.getByLabel('Defaults application',{exact:true}).selectOption('crm');
 await expect(page.getByRole('button',{name:'Currency',exact:true})).toContainText('USD');
 await page.getByRole('button',{name:'CRM & tasks',exact:true}).click();await page.getByRole('checkbox',{name:'Custom task priority'}).check();await page.getByLabel('Task priority',{exact:true}).selectOption('High');await page.getByRole('button',{name:'Save defaults',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>globalThis.__saved['crm:'].values.task_priority)).toBe('High');
 await page.getByRole('checkbox',{name:'Custom task priority'}).uncheck();await page.getByRole('button',{name:'Save defaults',exact:true}).click();await expect.poll(()=>page.evaluate(()=>globalThis.__saved['crm:'].values.task_priority)).toBe(undefined);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.resolve(root,'../outputs/defaults-settings-mobile.png'),fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile layout overflows');
 assert.deepEqual(errors,[]);console.log('Defaults editor, inheritance, persistence, mobile layout, and draft preservation checks passed');
}finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
