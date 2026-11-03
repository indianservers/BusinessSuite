const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const origin = process.env.PREVIEW_QA_ORIGIN || 'http://127.0.0.1:5173';
(async () => {
 const source = await (await fetch(origin+'/src/components/RecordQuickPreview.tsx')).text();
 const react = source.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1];
 const main = await (await fetch(origin+'/src/main.tsx')).text();
 const dom = main.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
 const html = `<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
 import React from '${react}';import ReactDOM from '${dom}';import Nav from '/src/components/RecordSectionNav.tsx';import Sections from '/src/components/RecordSections.tsx';import '/src/index.css';
 const groups=[{label:'Overview',sections:[{value:'overview',label:'Summary'}]},{label:'Personal',sections:[{value:'personal',label:'Identity'},{value:'contact',label:'Contact'}]},{label:'Career',sections:[{value:'job',label:'Employment'},{value:'education',label:'Education'}]},{label:'Documents',sections:[{value:'documents',label:'Files'}]}];
 function App(){const [value,setValue]=React.useState('contact');return React.createElement('main',{className:'p-4 space-y-6'},React.createElement(Nav,{groups,value,onChange:setValue,label:'Profile'}),React.createElement('p',{'data-testid':'selected'},value),React.createElement('button',{onClick:()=>setValue('education')},'Open education'),React.createElement(Sections,{label:'Record detail',sections:[{id:'overview',label:'Overview',content:React.createElement('input',{'aria-label':'Draft',defaultValue:'Original'})},{id:'activity',label:'Activity',content:React.createElement('p',null,'Activity details')},{id:'related',label:'Related',content:React.createElement('p',null,'Related details')},{id:'history',label:'History',content:React.createElement('p',null,'History details')}]}));}
 ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));</script></body></html>`;
 const browser=await chromium.launch({headless:true});
 try { const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/__sections_qa',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto(origin+'/__sections_qa');
 const nav=page.getByRole('tablist',{name:'Profile',exact:true});await expect(nav.getByRole('tab')).toHaveCount(4);
 await expect(nav.getByRole('tab',{name:'Personal',exact:true})).toHaveAttribute('aria-selected','true');
 await expect(page.getByLabel('Profile section')).toHaveValue('contact');
 await page.getByRole('button',{name:'Open education'}).click();await expect(nav.getByRole('tab',{name:'Career'})).toHaveAttribute('aria-selected','true');
 await page.getByLabel('Profile section').selectOption('job');await expect(page.getByTestId('selected')).toHaveText('job');
 await nav.getByRole('tab',{name:'Overview'}).focus();await page.keyboard.press('ArrowRight');await expect(nav.getByRole('tab',{name:'Personal'})).toBeFocused();
 await page.getByLabel('Draft').fill('Keep my changes');
 const detail=page.getByRole('tablist',{name:'Record detail',exact:true});await expect(detail.getByRole('tab')).toHaveCount(4);
 await detail.getByRole('tab',{name:'Activity'}).click();await expect(page.getByText('Activity details')).toBeVisible();await expect(page.getByLabel('Draft')).toBeHidden();
 await detail.getByRole('tab',{name:'Overview'}).click();await expect(page.getByLabel('Draft')).toHaveValue('Keep my changes');
 await page.setViewportSize({width:390,height:844});await expect(nav).toBeVisible();
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile horizontal overflow');
 if(errors.length)throw Error(errors.join('\n'));
 console.log('PASS: four tabs, section picker, direct section navigation, keyboard navigation, draft preservation, mobile fit');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
