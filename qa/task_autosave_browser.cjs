// Run against a local Vite server. API responses are isolated in memory.
const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.CRM_TASK_QA_ORIGIN || 'http://127.0.0.1:5194';
const legacyKey = 'productivity:crm:7:v1';
const html = `<!DOCTYPE html><html><head><script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/crm-tasks-qa.tsx"></script></body></html>`;
(async () => {
  const browser = await chromium.launch({ headless: true });
  let rows = [], nextId = 1, failNextSave = false;
  const errors = [], reads = [];
  async function device(seed = false) {
    const context = await browser.newContext();
    if (seed) await context.addInitScript(({key}) => localStorage.setItem(key, JSON.stringify({ entries: [{id:'legacy-one',kind:'task',title:'Old browser task',content:'Keep me',status:'To Do',due:''},{id:'note-one',kind:'note',title:'Old note',content:'Keep note'}], notebooks: [{id:'inbox',name:'Inbox'}] })), { key: legacyKey });
    const page = await context.newPage();
    page.on('pageerror', error => { errors.push(error.message); console.error(error.message); });
    await page.route('**/__crm_task_qa', route => route.fulfill({contentType:'text/html',body:html}));
    await page.route('**/api/v1/**', async route => {
      const request = route.request(), url = new URL(request.url());
      const match = url.pathname.match(/\/crm\/tasks(?:\/(\d+))?$/);
      if (!match) return route.fulfill({json:{items:[]}});
      if (request.method() === 'GET') {
        reads.push(Object.fromEntries(url.searchParams));
        const search = url.searchParams.get('search') || '';
        const items = rows.filter(r => !r.deleted && r.title.toLowerCase().includes(search.toLowerCase()));
        return route.fulfill({json:{items,pages:items.length ? 1 : 0}});
      }
      if (failNextSave) { failNextSave = false; return route.fulfill({status:503,json:{detail:'Save temporarily unavailable'}}); }
      if (request.method() === 'DELETE') { rows.find(r => r.id === Number(match[1])).deleted = true; return route.fulfill({json:{message:'Deleted'}}); }
      const data = request.postDataJSON();
      let row = match[1] ? rows.find(r => r.id === Number(match[1])) : rows.find(r => data.import_key && r.import_key === data.import_key);
      if (!row) { row = {id:nextId++,ownerId:7}; rows.push(row); }
      Object.assign(row, data, {dueDate:data.due_date});
      return route.fulfill({status:request.method() === 'POST' ? 201 : 200,json:row});
    });
    await page.goto(`${origin}/__crm_task_qa`);
    await expect(page.getByRole('heading',{name:'CRM tasks',exact:true})).toBeVisible();
    return {context,page};
  }
  try {
    const {page} = await device();
    await page.getByRole('button',{name:'New task',exact:true}).click();
    await page.getByLabel('Task Title',{exact:true}).fill('Autosave test task');
    await expect(page.getByRole('status')).toContainText('automatically saved in this browser');
    assert.equal(rows.length, 0, 'Draft autosave must not create a task');
    await page.getByLabel('Task Title',{exact:true}).press('Control+s');
    await expect(page.getByRole('button',{name:'Autosave test task',exact:true})).toBeVisible();
    assert.equal(rows.length,1,'Ctrl+S creates once');
    await page.getByRole('button',{name:'Edit task Autosave test task',exact:true}).click();
    await page.getByLabel('Task Title',{exact:true}).fill('Automatically updated task');
    await expect(page.getByRole('status')).toContainText('automatically saved to CRM');
    assert.equal(rows[0].title,'Automatically updated task');
    await expect(page.getByRole('heading',{name:'Edit Task',exact:true})).toBeVisible();
    failNextSave=true;
    await page.getByLabel('Task Title',{exact:true}).fill('Retry autosave task');
    await expect(page.getByRole('alert')).toContainText('Automatic save failed');
    assert.equal(rows[0].title,'Automatically updated task');
    await page.getByLabel('Task Title',{exact:true}).press('Control+s');
    await expect(page.getByRole('button',{name:'Retry autosave task',exact:true})).toBeVisible();
    assert.equal(rows.length,1);
    assert.equal(errors.length,0,errors.join('\n'));
    await page.route('**/__save_shortcut_qa', route=>route.fulfill({contentType:'text/html',body:html.replace('/scripts/fixtures/crm-tasks-qa.tsx','/src/components/app/SaveShortcut.tsx').replace('<script type="module" src="/src/components/app/SaveShortcut.tsx"></script>', `<script type="module">import React from '/node_modules/.vite/deps/react.js'; import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js'; import SaveShortcut from '/src/components/app/SaveShortcut.tsx'; ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(SaveShortcut));</script><main><form><input aria-label="Editor"><button type="button" onclick="window.saved=(window.saved||0)+1">Save changes</button></form><button type="button" onclick="window.sent=true">Send email</button></main>`)}));
    await page.goto(`${origin}/__save_shortcut_qa`);
    await page.getByLabel('Editor').focus();
    await page.waitForTimeout(500);
    await page.keyboard.press('Control+s');
    await expect.poll(()=>page.evaluate(()=>window.saved)).toBe(1);
    assert.equal(await page.evaluate(()=>window.sent),undefined);
    console.log('PASS: automatic drafts, Ctrl+S create, CRM edit autosave, failed-save retry, no duplicate tasks');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
