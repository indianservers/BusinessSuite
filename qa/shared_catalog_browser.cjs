// Isolated browser checks against local Vite; no deployed API is contacted.
const {chromium, expect: baseExpect} = require('../frontend/node_modules/playwright/test');
const expect = baseExpect.configure({timeout:15000});
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = process.env.CATALOG_QA_ORIGIN || 'http://127.0.0.1:5194';
const viteHash = JSON.parse(fs.readFileSync('frontend/node_modules/.vite/deps/_metadata.json')).browserHash;
const html = `<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '/node_modules/.vite/deps/react.js?v=${viteHash}';import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js?v=${viteHash}';
import {MemoryRouter} from '/node_modules/.vite/deps/react-router-dom.js?v=${viteHash}';import Page from '/src/shared/catalog/CatalogPage.tsx';import {CatalogLinesEditor} from '/src/shared/catalog/CatalogLinesEditor.tsx';import '/src/index.css';
const query=new URLSearchParams(location.search),source=query.get('source')||'pms';
function Capture(){const[lines,setLines]=React.useState([]);window.qaLines=lines;return React.createElement('div',{style:{padding:20}},React.createElement(CatalogLinesEditor,{value:lines,onChange:setLines,currency:'INR'}));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(MemoryRouter,{initialEntries:['/'+source+'/products-services']},query.has('selector')?React.createElement(Capture):React.createElement(Page,{source})));
</script></body></html>`;
(async()=>{
  const browser=await chromium.launch({headless:true});const errors=[];let next=1;const rows=[];
  try{
    const context=await browser.newContext({viewport:{width:1440,height:1100}});
    await context.route('**/__catalog_qa?*',r=>r.fulfill({contentType:'text/html',body:html}));
    await context.route('**/api/v1/**',async route=>{
      const request=route.request(),url=new URL(request.url()),path=url.pathname;
      if(path.endsWith('/project-management/workspaces'))return route.fulfill({json:[]});
      if(path.endsWith('/catalog/items')&&request.method()==='GET'){
        const search=url.searchParams.get('search')||'',kind=url.searchParams.get('kind'),status=url.searchParams.get('status')||'Active';
        const items=rows.filter(r=>(status==='all'||r.status===status)&&(!kind||r.kind===kind)&&(`${r.name} ${r.code}`.toLowerCase().includes(search.toLowerCase())));
        return route.fulfill({json:{items,total:items.length,pages:items.length?1:0,permissions:{product:true,service:true}}});
      }
      if(path.endsWith('/catalog/items')&&request.method()==='POST'){const row={...request.postDataJSON(),id:next++,version:1};rows.push(row);return route.fulfill({status:201,json:row});}
      const match=path.match(/\/catalog\/items\/(product|service)\/(\d+)(?:\/(archive|duplicate))?$/);
      if(match){const row=rows.find(r=>r.kind===match[1]&&r.id===Number(match[2]));
        if(match[3]==='duplicate'){const copy={...row,id:next++,name:row.name+' (copy)',code:row.code+'-COPY'};rows.push(copy);return route.fulfill({status:201,json:copy});}
        if(match[3]==='archive'){row.status='Archived';row.version++;return route.fulfill({json:row});}
        if(request.method()==='PUT')Object.assign(row,request.postDataJSON(),{version:row.version+1});return route.fulfill({json:row});
      }
      return route.fulfill({json:{items:[]}});
    });
    async function page(source,selector=false){const page=await context.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});await page.goto(`${origin}/__catalog_qa?source=${source}${selector?'&selector=1':''}`);return page;}
    const pms=await page('pms'),crm=await page('crm');
    await expect(pms.getByRole('heading',{name:'Products & services',exact:true})).toBeVisible();
    await pms.getByRole('button',{name:'New item',exact:true}).click();
    const dialog=pms.getByRole('dialog');await dialog.getByLabel('Name',{exact:true}).fill('Enterprise workspace');await dialog.getByLabel('SKU / Code',{exact:true}).fill('ENT-100');await dialog.getByLabel('Base price',{exact:true}).fill('1200');await dialog.getByLabel('Description',{exact:true}).fill('A shared offering for customer teams and project delivery.');
    await dialog.getByRole('button',{name:'Add price',exact:true}).click();await dialog.getByLabel('Price name',{exact:true}).fill('Annual support');await dialog.getByLabel('Amount',{exact:true}).fill('10000');await dialog.locator('.sc-price-row select').selectOption('year');
    await dialog.getByRole('button',{name:'Save item',exact:true}).click();await expect(pms.getByRole('button',{name:'Enterprise workspace',exact:true})).toBeVisible();
    await expect(crm.getByRole('button',{name:'Enterprise workspace',exact:true})).toBeVisible();
    await crm.getByRole('button',{name:'Edit Enterprise workspace',exact:true}).click();await crm.getByRole('dialog').getByLabel('Name',{exact:true}).fill('Enterprise suite');await crm.getByRole('button',{name:'Save item',exact:true}).click();await expect(pms.getByRole('button',{name:'Enterprise suite',exact:true})).toBeVisible();
    await crm.getByRole('button',{name:'New item',exact:true}).click();const form=crm.getByRole('dialog');await form.getByLabel('Type',{exact:true}).selectOption('service');await form.getByLabel('Name',{exact:true}).fill('Implementation');await form.getByLabel('SKU / Code',{exact:true}).fill('SVC-100');await form.getByLabel('Base price',{exact:true}).fill('500');await form.getByRole('button',{name:'Save item',exact:true}).click();await expect(pms.getByRole('button',{name:'Implementation',exact:true})).toBeVisible();
    const selector=await page('crm',true);await selector.getByRole('button',{name:/Enterprise suite ENT-100/}).click();await selector.getByRole('button',{name:/Implementation SVC-100/}).click();assert.equal(await selector.evaluate(()=>window.qaLines.length),2);
    await selector.getByLabel('Quantity for Enterprise suite',{exact:true}).fill('3');await selector.getByLabel('Discount for Enterprise suite',{exact:true}).fill('10');await selector.getByLabel('Pricing for Enterprise suite',{exact:true}).selectOption({label:'Annual support · ₹10,000.00 / year'}).catch(async()=>selector.getByLabel('Pricing for Enterprise suite',{exact:true}).selectOption(await selector.getByLabel('Pricing for Enterprise suite',{exact:true}).locator('option').nth(1).getAttribute('value')));
    assert.equal(await selector.evaluate(()=>window.qaLines[0].unit_price),10000);
    await selector.getByRole('button',{name:'Quick create',exact:true}).click();await selector.getByRole('dialog').getByLabel('Name',{exact:true}).fill('Quick service');await selector.getByRole('dialog').getByLabel('SKU / Code',{exact:true}).fill('QUICK-1');await selector.getByRole('button',{name:'Save item',exact:true}).click();assert.equal(await selector.evaluate(()=>window.qaLines.length),3);
    await pms.getByRole('button',{name:'Preview Enterprise suite',exact:true}).click();await expect(pms.getByRole('dialog')).toContainText('Annual support');await pms.getByRole('button',{name:'Close preview',exact:true}).click();
    fs.mkdirSync('docs/qa/shared-catalog',{recursive:true});await pms.screenshot({path:'docs/qa/shared-catalog/desktop.png',fullPage:true});
    await pms.setViewportSize({width:390,height:844});await pms.screenshot({path:'docs/qa/shared-catalog/mobile.png',fullPage:true});assert.ok(await pms.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile page must not overflow horizontally');
    await crm.getByRole('button',{name:'Archive Implementation',exact:true}).click();await crm.getByRole('dialog').getByRole('button',{name:'Archive item',exact:true}).click();await expect(pms.getByRole('button',{name:'Implementation',exact:true})).toHaveCount(0);
    await pms.getByLabel('Filter status',{exact:true}).selectOption('Archived');await expect(pms.getByRole('button',{name:'Implementation',exact:true})).toBeVisible();assert.deepEqual(errors,[]);
    console.log('PASS: PMS/CRM live synchronization, create/edit/archive, pricing, multi-select, quick-create, previews and mobile layout');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
