const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.PREVIEW_QA_ORIGIN || 'http://127.0.0.1:5173';
(async () => {
  const module = await (await fetch(origin + '/src/components/RecordQuickPreview.tsx')).text();
  const react = module.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1];
  const router = module.match(/"([^"\n]*\/react-router-dom\.js\?v=[^"\n]+)"/)[1];
  const gridModule = await (await fetch(origin + '/src/shared/data-grid/SharedDataGrid.tsx')).text();
  const query = gridModule.match(/"([^"\n]*\/@tanstack_react-query\.js\?v=[^"\n]+)"/)[1];
  const domModule = await (await fetch(origin + '/src/main.tsx')).text();
  const dom = domModule.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
  const html = `<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '${react}';import ReactDOM from '${dom}';import {BrowserRouter} from '${router}';import {QueryClient,QueryClientProvider} from '${query}';import Preview,{recordPreviewProps} from '/src/components/RecordQuickPreview.tsx';import Grid from '/src/shared/data-grid/SharedDataGrid.tsx';import '/src/index.css';
const record={id:7,name:'Preview Contact',email:'contact@example.com',hidden_detail:'Beyond visible columns',nested:{city:'Hyderabad'},tags:['Customer'],password:'DO NOT DISPLAY'};
const source={key:'preview-qa',load:async()=>({rows:[record],total:1,page:1,pageSize:50,groups:[],aggregates:[]})};
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient()},React.createElement(BrowserRouter,null,React.createElement('table',null,React.createElement('tbody',null,React.createElement('tr',{...recordPreviewProps(record),'data-testid':'native-row'},React.createElement('td',null,'Contact row'),React.createElement('td',null,React.createElement('input',{'aria-label':'Editable value',defaultValue:'Edit me'}))))),React.createElement(Grid,{gridId:'preview-qa',title:'Preview grid',columns:[{id:'name',title:'Name'}],dataSource:source,getRowId:r=>String(r.id),height:300}),React.createElement(Preview))));
</script></body></html>`;
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage(); const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/__preview_qa',route=>route.fulfill({contentType:'text/html',body:html}));
    await page.goto(origin+'/__preview_qa');
    await page.getByTestId('native-row').getByText('Contact row').dblclick();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('dialog')).toContainText('Beyond visible columns');
    await expect(page.getByRole('dialog')).toContainText('Hyderabad');
    await expect(page.getByRole('dialog')).not.toContainText('DO NOT DISPLAY');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByLabel('Editable value').dblclick();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.locator('.udg-row').first().dblclick();
    await expect(page.getByRole('dialog')).toContainText('Beyond visible columns');
    await page.getByRole('button',{name:'Close dialog',exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.route('**/crm/contacts/7', route => route.fulfill({json:{id:7,name:'Full contact',description:'Loaded from detail endpoint'}}));
    await page.route('**/crm/contacts/7/related', route => route.fulfill({json:{deals:[{name:'Related opportunity'}]}}));
    await page.evaluate(() => history.replaceState({}, '', '/crm/contacts'));
    await page.getByTestId('native-row').getByText('Contact row').dblclick();
    await expect(page.getByRole('dialog')).toContainText('Loaded from detail endpoint');
    await expect(page.getByRole('dialog')).toContainText('Related opportunity');
    await page.getByRole('button',{name:'Close dialog',exact:true}).click();
    await page.route('**/crm/contacts/7', route => route.fulfill({status:403,json:{detail:'Forbidden'}}));
    await page.getByTestId('native-row').getByText('Contact row').dblclick();
    await expect(page.getByRole('dialog')).toContainText('Some additional details could not be loaded');
    await expect(page.getByRole('dialog')).toContainText('Beyond visible columns');
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:390,height:844});
    await page.getByTestId('native-row').getByText('Contact row').dblclick();
    const bounds = await page.getByRole('dialog').boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= 390 && bounds.height <= 844, 'Preview must fit narrow screens');
    await page.getByRole('button',{name:'Close dialog',exact:true}).click();
    assert.deepEqual(errors,[]);
    console.log('PASS: table and shared grid previews, hidden/nested fields, secret exclusion, Escape, close button, editable inputs');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});


