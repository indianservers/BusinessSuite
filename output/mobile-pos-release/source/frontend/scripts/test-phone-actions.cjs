const { buildSync } = require('esbuild');
const { chromium, expect } = require('playwright/test');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = `
import React from 'react';
import { createRoot } from 'react-dom/client';
import PhoneActions, {phoneLinks,isPhoneField,phoneCountryCode} from './src/components/PhoneActions';
import {Fields} from './src/components/RecordPreviewFields';
import SharedDataGrid from './src/shared/data-grid/SharedDataGrid';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
const source={key:'phone-test',load:async()=>({rows:[{id:'1',phone:'9876543210',phone_country_code:'+91'}],total:1,pageTotal:1,page:1,pageSize:50,permissions:{edit:true}})};
window.phoneHelpers={phoneLinks,isPhoneField,phoneCountryCode};
window.rowActions=0;
createRoot(document.getElementById('root')).render(<>
 <div role="grid" data-testid="event-grid" onClick={()=>window.rowActions++} onDoubleClick={()=>window.rowActions++} onPointerDown={()=>window.rowActions++} onKeyDown={()=>window.rowActions++}>
  <div role="row"><div role="gridcell"><PhoneActions value="98765 43210" record={{phone_country_code:'+91'}}/></div></div>
 </div>
 <div data-testid="hidden"><PhoneActions value="Hidden by privacy setting"/></div>
 <div data-testid="blocked"><PhoneActions value="9876543210" record={{status:'Do not contact',phone_country_code:'+91'}}/></div>
 <div data-testid="masked"><PhoneActions value="9876543210" record={{contact_masked:true,phone_country_code:'+91'}}/></div>
 <div data-testid="preview"><Fields value={{phone_number:'7700900123',phone_number_country_code:'+44'}}/></div>
 <div data-testid="local"><PhoneActions value="9876543210"/></div>
 <QueryClientProvider client={client}>{['grid','cards','kanban'].map(view=><div key={view} data-testid={'shared-'+view}><SharedDataGrid gridId={'phone-actions-'+view} columns={[{id:'phone',title:'Phone',editable:true,render:row=><span>{row.phone}</span>}]} dataSource={source} getRowId={row=>row.id} onOpen={()=>window.rowActions++} onSelectRecord={()=>window.rowActions++} initialLayout={{view}} height={300}/></div>)}</QueryClientProvider>
</>);`;
(async () => {
 const assets=buildSync({outfile:'phone-test.js',stdin:{contents:source,resolveDir:root,loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).outputFiles;
 const bundle=assets.find(file=>file.path.endsWith('.js')).text;
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  await page.setContent('<div id="root"></div>');
  await page.addStyleTag({content:assets.find(file=>file.path.endsWith('.css')).text});
  await page.addScriptTag({content:bundle});
  const call=page.getByTestId('event-grid').getByRole('link',{name:'Call +91 98765 43210',exact:true});
  await expect(call).toHaveAttribute('href','tel:+919876543210');
  const whatsapp=page.getByTestId('event-grid').getByRole('link',{name:'WhatsApp +91 98765 43210',exact:true});
  await expect(whatsapp).toHaveAttribute('href','https://wa.me/919876543210');
  await expect(whatsapp).toHaveAttribute('target','_blank');
  // Prevent external navigation while exercising the real touch and keyboard events.
  await page.evaluate(()=>document.addEventListener('click',e=>e.preventDefault(),true));
  await call.tap(); await whatsapp.tap(); await call.focus(); await call.press('Enter');
  assert.equal(await page.evaluate(()=>window.rowActions),0,'contact links must not open or select the row');
  for(const view of ['grid','cards','kanban']) {
   const shared=page.getByTestId('shared-'+view);
   const number=shared.getByRole('link',{name:'Call +91 9876543210',exact:true});
   await expect(number).toHaveAttribute('href','tel:+919876543210');
   await expect(shared.getByRole('link',{name:'WhatsApp +91 9876543210',exact:true})).toHaveAttribute('href','https://wa.me/919876543210');
   await number.tap();
  }
  await page.waitForTimeout(400);
  assert.equal(await page.evaluate(()=>window.rowActions),0,'shared grid contact taps must not open records');
  for(const testId of ['hidden','blocked','masked']) await expect(page.getByTestId(testId).getByRole('link')).toHaveCount(0);
  await expect(page.getByTestId('preview').getByRole('link',{name:'Call +44 7700900123',exact:true})).toHaveAttribute('href','tel:+447700900123');
  await expect(page.getByTestId('local').getByRole('link')).toHaveCount(1);
  const results=await page.evaluate(()=>{
   const {phoneLinks:p,isPhoneField:f}=window.phoneHelpers;
   return {international:p('+44 (7700) 900-123','+91'),prefix:p('00447700900123'),trunk:p('07700900123','+44'),masked:p('98******10'),text:p('Hidden by privacy setting'),short:p('123'),long:p('1234567890123456'),fields:['phone','phone_number','mobile','alternate_phone','emergency_contact_number','Phone'].every(f),nonPhone:['phone_country_code','phone_verified','microphone','mobile_layout'].some(f)};
  });
  for(const key of ['international','prefix','trunk']) assert.equal(results[key].whatsapp,'https://wa.me/447700900123');
  for(const key of ['masked','text','short','long']) assert.equal(results[key],null);
  assert.equal(results.fields,true); assert.equal(results.nonPhone,false);
  console.log('Phone actions: mobile taps, keyboard, row isolation, preview fields, privacy and country-code formatting passed.');
 } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
