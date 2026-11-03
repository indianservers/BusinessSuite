const {chromium, expect} = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.CRM_QA_ORIGIN || 'http://127.0.0.1:5173';
(async () => {
  const preview = await (await fetch(origin + '/src/components/RecordQuickPreview.tsx')).text();
  const main = await (await fetch(origin + '/src/main.tsx')).text();
  const react = preview.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1];
  const router = preview.match(/"([^"\n]*\/react-router-dom\.js\?v=[^"\n]+)"/)[1];
  const dom = main.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
  const html = `<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '${react}';import ReactDOM from '${dom}';import {BrowserRouter} from '${router}';import Records from '/src/apps/crm/CRMRecordsPage.tsx';import '/src/index.css';window.previews=[];window.addEventListener('suite:record-preview',e=>window.previews.push(e.detail));ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement(Records)));
</script></body></html>`;
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  const errors = [], mutations = [];
  const rows = Object.fromEntries(['contacts','leads','deals','companies'].map((entity,i)=>[entity,[{id:i+1,full_name:entity==='contacts'||entity==='leads'?`${entity} Person`:undefined,name:`${entity} Business`,email:`${entity}@example.com`,status:'Active',updated_at:'2026-11-03T10:00:00Z',deleted_at:null}]]));
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/__records_qa*',route=>route.fulfill({contentType:'text/html',body:html}));
  await page.route('**/api/v1/**',async route=>{
    const request = route.request(), url = new URL(request.url());
    const match = url.pathname.match(/\/crm\/(contacts|leads|deals|companies)(?:\/(\d+))?(\/restore)?$/);
    if (!match) return route.fulfill({json:{items:[],total:0}});
    const [,entity,id,restore] = match;
    if (request.method()==='DELETE') {rows[entity].find(row=>row.id===+id).deleted_at='2026-11-03T11:00:00Z';mutations.push(['delete',entity,+id]);return route.fulfill({json:{message:'Deleted'}});}
    if (restore) {rows[entity].find(row=>row.id===+id).deleted_at=null;mutations.push(['restore',entity,+id]);return route.fulfill({json:rows[entity].find(row=>row.id===+id)});}
    const deleted = url.searchParams.get('deleted_only')==='true', search = url.searchParams.get('search')||'';
    const items = rows[entity].filter(row=>Boolean(row.deleted_at)===deleted&&JSON.stringify(row).toLowerCase().includes(search.toLowerCase()));
    return route.fulfill({json:{items,total:items.length,page:1,pages:1,per_page:25}});
  });
  try {
    await page.goto(origin+'/__records_qa');
    await expect(page.getByRole('heading',{name:'Records management'})).toBeVisible();
    await expect(page.getByRole('link',{name:'Create contact',exact:true})).toHaveAttribute('href','/crm/contacts?new=contacts');
    await page.getByRole('row').filter({hasText:'contacts Person'}).dblclick({position:{x:220,y:20}});
    assert.equal((await page.evaluate(()=>window.previews))[0].path,'/crm/contacts');
    await page.getByRole('button',{name:'Delete contacts Person',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal(mutations.length,0);
    await page.getByRole('button',{name:'Delete contacts Person',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Delete record',exact:true}).click();
    await expect(page.getByText('No contacts yet.',{exact:false})).toBeVisible();
    await page.getByRole('button',{name:'Recycle bin',exact:true}).click();
    await page.getByRole('button',{name:'Restore contacts Person',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Restore record',exact:true}).click();
    await expect(page.getByText('Recycle bin is empty.',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Active records',exact:true}).click();
    await expect(page.getByRole('link',{name:'contacts Person',exact:true})).toBeVisible();
    for (const [entity,label,singular] of [['leads','Leads','lead'],['deals','Deals','deal'],['companies','Companies','company']]) {
      await page.getByRole('button',{name:label,exact:true}).click();
      await expect(page.getByRole('link',{name:`Create ${singular}`,exact:true})).toHaveAttribute('href',`/crm/${entity}?new=${entity}`);
      await expect(page.getByRole('link',{name:'Manage metadata',exact:true})).toHaveAttribute('href',`/crm/record-metadata?entity=${entity}`);
      await expect(page.getByRole('row').filter({hasText:`${entity}@example.com`})).toBeVisible();
    }
    await page.getByRole('textbox',{name:'Search records'}).fill('missing');
    await expect(page.getByText('No records match this search.',{exact:true})).toBeVisible();
    await page.getByRole('textbox',{name:'Search records'}).fill('');
    await expect(page.getByRole('link',{name:'companies Business',exact:true})).toBeVisible();
    await page.setViewportSize({width:390,height:844});
    await expect(page.getByRole('link',{name:'Create company',exact:true})).toBeInViewport();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.deepEqual(mutations,[['delete','contacts',1],['restore','contacts',1]]);
    assert.deepEqual(errors,[]);
    console.log('PASS: four record types, create/edit/metadata navigation, delete confirmation, recycle and restore, search, preview context and mobile layout');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
