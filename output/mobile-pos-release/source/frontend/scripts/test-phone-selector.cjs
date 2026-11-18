const { buildSync } = require('esbuild');
const { chromium, expect } = require('playwright/test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '..');
const source = `
import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import * as Dialog from '@radix-ui/react-dialog';
import {PhoneInput} from './src/lib/validation/PhoneInput';
import {installFormDefaults} from './src/lib/form-defaults';
if(location.hash==='#custom')installFormDefaults({values:{phone_country_code:'+971'},modules:{},companyId:1,branchId:null});
function Fields(){
 const [values,set]=useState({first:'',second:'',firstCode:'',secondCode:''});
 const [submits,S]=useState(0);
 return <form onSubmit={e=>{e.preventDefault();S(submits+1)}}>
 {['first','second'].map(key=><PhoneInput key={key} label={key} name={key} value={values[key]} countryCode={values[key+'Code']} onChange={v=>set(c=>({...c,[key]:v}))} onCountryCodeChange={v=>set(c=>({...c,[key+'Code']:v}))}/>)}
 <PhoneInput label="Read only" value="" countryCode="+44" disabled onChange={()=>{}} onCountryCodeChange={()=>{throw Error('Read only mutated')}}/>
 <output data-testid="state">{JSON.stringify(values)}</output><output data-testid="submits">{submits}</output><button type="button">Outside</button></form>
}
function App(){return location.hash==='#dialog'?<Dialog.Root defaultOpen><Dialog.Portal><Dialog.Overlay/><Dialog.Content aria-describedby={undefined} style={{position:'fixed',left:24,top:24,width:280,height:100,overflow:'hidden',transform:'translateX(5px)'}}><Dialog.Title>Phone dialog</Dialog.Title><Fields/></Dialog.Content></Dialog.Portal></Dialog.Root>:<div style={{height:100,overflow:'hidden',width:280}}><Fields/></div>}
createRoot(document.getElementById('root')).render(<App/>);`;
(async()=>{
 const flagDirectory=path.join(root,'node_modules/country-flag-icons/3x2');
 const flagAssets=Object.fromEntries(fs.readdirSync(flagDirectory).filter(name=>name.endsWith('.svg')).map(name=>['/node_modules/country-flag-icons/3x2/'+name,'data:image/svg+xml;base64,'+fs.readFileSync(path.join(flagDirectory,name)).toString('base64')]));
 const bundle=buildSync({stdin:{contents:source,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"','import.meta.glob':'flagGlob'},banner:{js:'function flagGlob(){return '+JSON.stringify(flagAssets)+';}'}}).outputFiles[0].text;
 const browser=await chromium.launch({headless:true});
 try{
 for(const mode of ['form','dialog']){
 const page=await browser.newPage({viewport:{width:390,height:700}});
 await page.setContent('<div id="root"></div>');
 await page.evaluate(mode=>{location.hash=mode==='dialog'?'dialog':''},mode);
 await page.addScriptTag({content:bundle});
 await expect(page.getByTestId('state')).toContainText('"firstCode":"+91","secondCode":"+91"');
 const trigger=page.getByRole('button',{name:/^first country calling code/});
 await expect(trigger).toHaveText('+91▾');assert.ok((await trigger.boundingBox()).width<=112);
 await trigger.click();const search=page.getByRole('combobox');await expect(search).toBeFocused();
 assert.equal(await page.locator('[popover]').evaluate(e=>e.matches(':popover-open')),true);
 await search.fill('India');await expect(page.getByRole('option',{name:/IN \+91/})).toBeVisible();
 await search.fill('GB');await search.press('Enter');await expect(trigger).toHaveText('+44▾');await expect(trigger).toBeFocused();
 await trigger.click();await search.fill('+93');await search.press('Enter');await expect(trigger).toHaveText('+93▾');
 await trigger.click();await search.fill('zzzzzzz');await expect(page.getByText('No countries found')).toBeVisible();await search.press('Escape');await expect(trigger).toHaveAttribute('aria-expanded','false');
 if(mode==='dialog')await expect(page.getByRole('dialog')).toBeVisible();
 await trigger.click();await search.fill('India');await search.press('ArrowDown');await search.press('ArrowUp');await search.press('Enter');
 await trigger.click();await search.fill('Canada');await page.getByRole('option',{name:/CA \+1/}).click();await expect(trigger).toHaveAttribute('aria-label',/Canada/);
 await trigger.click();await search.fill('United States');await search.press('Enter');await expect(trigger).toHaveAttribute('aria-label',/United States/);
 await expect(page.getByTestId('submits')).toHaveText('0');
 // Hit-test an option outside the clipped ancestor to prove it remains clickable.
 await trigger.click();await search.fill('India');const option=page.getByRole('option',{name:/IN \+91/});const box=await option.boundingBox();assert.ok(box.y>100);assert.ok(box.x>=0&&box.x+box.width<=390);
 assert.equal(await option.evaluate(e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+10,r.y+r.height/2))}),true);
 await option.click();await expect(trigger).toHaveText('+91▾');
 await trigger.click();await page.getByRole('button',{name:'Outside',exact:true}).dispatchEvent('pointerdown');await expect(trigger).toHaveAttribute('aria-expanded','false');
 await trigger.click();await search.press('Tab');await expect(page.getByRole('textbox',{name:'first',exact:true})).toBeFocused();
 await expect(page.getByRole('button',{name:/^Read only country/})).toBeDisabled();
 await page.getByRole('textbox',{name:'first',exact:true}).fill('9876543210');
 await expect(page.getByTestId('state')).toContainText('"first":"9876543210"');
 await page.setViewportSize({width:320,height:300});await trigger.click();
 const popup=await page.locator('[popover]').boundingBox();assert.ok(popup.x>=0&&popup.x+popup.width<=320&&popup.y>=0&&popup.y+popup.height<=300);
 await page.close();console.log(mode+': default codes, compact width, search, mouse/keyboard selection, shared codes, clipping and focus passed');
 }
 const customPage=await browser.newPage();await customPage.setContent('<div id="root"></div>');await customPage.evaluate(()=>{location.hash='custom'});await customPage.addScriptTag({content:bundle});await expect(customPage.getByTestId('state')).toContainText('"firstCode":"+971","secondCode":"+971"');await customPage.close();console.log('Configured phone code applies to new fields');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
