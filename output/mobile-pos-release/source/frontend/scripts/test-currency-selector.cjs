const { buildSync } = require('esbuild');
const { chromium, expect } = require('playwright/test');
const path = require('node:path');
(async()=>{
const content=buildSync({stdin:{contents:`import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {CurrencySelect} from './src/lib/validation/CurrencySelect';function App(){const [v,S]=useState('USD');return <><CurrencySelect value={v} onChange={S}/><output>{v}</output></>}createRoot(document.getElementById('root')).render(<App/>);`,resolveDir:path.resolve(__dirname,'..'),loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}}).outputFiles[0].text;
const browser=await chromium.launch();try{
const page=await browser.newPage({viewport:{width:390,height:700}});await page.setContent('<div id="root"></div>');await page.addScriptTag({content});
const trigger=page.getByRole('button',{name:'Currency',exact:true});if((await trigger.boundingBox()).width>132)throw Error('Picker too wide');
await trigger.click();await expect(page.getByRole('option').first()).toContainText('INR');await expect(page.getByRole('option').first()).toContainText('\u20b9');
const search=page.getByRole('combobox');await expect(search).toBeFocused();await search.fill('rupee');await expect(page.getByRole('option',{name:/INR/})).toBeVisible();
await search.fill('\u20b9');await expect(page.getByRole('option')).toHaveCount(1);await search.press('Enter');await expect(page.locator('output')).toHaveText('INR');await expect(trigger).toBeFocused();
await trigger.click();await search.fill('EUR');await search.press('Enter');await expect(trigger).toContainText('\u20ac');
await trigger.click();await search.fill('no-such-currency');await expect(page.locator('p[role=status]')).toHaveText('No currencies found');await search.press('Escape');await expect(trigger).toHaveAttribute('aria-expanded','false');console.log('Currency selector browser checks passed');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});

