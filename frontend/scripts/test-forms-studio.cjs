const {chromium}=require('../node_modules/playwright');
const fs=require('fs'); const hash=JSON.parse(fs.readFileSync(require('path').join(__dirname,'../node_modules/.vite/deps/_metadata.json'),'utf8')).browserHash;
(async()=>{
 const browser=await chromium.launch({headless:true}); const page=await browser.newPage({viewport:{width:1500,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',r=>r.fulfill({json:r.request().url().includes('/forms/options')?{projects:[]}:[]}));
 await page.route('**/pms/forms**', r=>r.request().resourceType()==='document'?r.fulfill({contentType:'text/html',body:`<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="root"></div><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;</script><script type="module">import React from '/node_modules/.vite/deps/react.js?v=${hash}';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${hash}';import {BrowserRouter} from '/node_modules/.vite/deps/react-router-dom.js?v=${hash}';import Forms from '/src/features/forms/FormsPage.tsx';import '/src/index.css';ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement(Forms)));</script></body></html>`}):r.continue());
 await page.goto('http://localhost:5182/pms/forms');
 await page.getByRole('heading',{name:'Create a new form'}).waitFor();
 if(await page.locator('.forms-template-card').count()!==6)throw Error('gallery');
 fs.mkdirSync('../outputs/forms-studio',{recursive:true});await page.screenshot({path:'../outputs/forms-studio/templates.png',fullPage:true});
 await page.locator('.forms-template-card').filter({hasText:'Feedback Form'}).click();
 await page.getByLabel('Form name',{exact:true}).waitFor();
 if(await page.getByLabel('Form name',{exact:true}).inputValue()!=='Feedback Form') throw Error('template');
 await page.getByRole('button',{name:/Short text$/}).click();
 if(await page.locator('.form-live-field').count()!==6)throw Error('add field'); await page.getByRole('button',{name:'Undo',exact:true}).click(); if(await page.locator('.form-live-field').count()!==5)throw Error('undo'); await page.getByRole('button',{name:'Redo',exact:true}).click();if(await page.locator('.form-live-field').count()!==6)throw Error('redo');
 // Resize two adjacent fields directly on the canvas and verify their rendered row.
 async function half(label) {
   const field = page.locator('.form-live-field').filter({has:page.getByRole('button',{name:`Resize ${label}`,exact:true})});
   await field.hover(); const box=await field.boundingBox();
   const handle=await page.getByRole('button',{name:`Resize ${label}`,exact:true}).boundingBox();
   await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();
   await page.mouse.move(handle.x+handle.width/2-box.width/2,handle.y+handle.height/2+30,{steps:12});await page.mouse.up();
 }
 await half('Your name');await half('Email address');
 const first=await page.locator('.form-live-field').nth(0).boundingBox();const second=await page.locator('.form-live-field').nth(1).boundingBox();
 if(Math.abs(first.y-second.y)>2 || second.x<=first.x)throw Error('fields must share a row');
 if(first.height<90)throw Error('vertical resize');
 // Pointer sorting in the visual editor, without switching to Arrange fields.
 const before=await page.locator('.form-live-field').evaluateAll(nodes=>nodes.map(n=>n.dataset.fieldId));
 const grip=await page.getByRole('button',{name:'Drag Your name',exact:true}).boundingBox();
 const target=await page.locator('.form-live-field').nth(2).boundingBox();
 await page.mouse.move(grip.x+grip.width/2,grip.y+grip.height/2);await page.mouse.down();await page.mouse.move(grip.x+10,grip.y+12,{steps:3});
 await page.mouse.move(target.x+target.width/2,target.y+target.height/2,{steps:20});await page.waitForTimeout(200);await page.mouse.up();
 const after=await page.locator('.form-live-field').evaluateAll(nodes=>nodes.map(n=>n.dataset.fieldId));
 if(before.join()===after.join())throw Error('visual pointer drag did not reorder');
 await page.getByRole('button',{name:'Undo',exact:true}).click();
 await page.getByLabel('Canvas zoom').selectOption('75');
 await half('What could we improve?');

 await page.screenshot({path:'../outputs/forms-studio/editor.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.getByLabel('Canvas zoom').selectOption('100');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('mobile overflow');
 await page.screenshot({path:'../outputs/forms-studio/mobile.png',fullPage:true});
 await page.goto('http://localhost:5182/pms/forms/new?template=blank');await page.getByLabel('Form name',{exact:true}).waitFor();await page.getByRole('button',{name:'Add question',exact:false}).click();
 if(errors.length)throw Error(errors.join('\n'));console.log('PASS: gallery, template, undo/redo, zoom, blank canvas, direct resize, side-by-side layout, visual pointer sorting, zoomed resize, mobile; no runtime errors');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});


