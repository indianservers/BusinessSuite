// Run against a local Vite server. API responses are isolated in memory.
const { chromium, expect } = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.CRM_TASK_QA_ORIGIN || 'http://127.0.0.1:5194';
const legacyKey = 'productivity:crm:7:v1';
const html = `<!DOCTYPE html><html><head><script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">
import React from '/node_modules/.vite/deps/react.js';
import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
import Workspace from '/src/apps/crm/CRMTasksWorkspace.tsx';
import {useAuthStore} from '/src/store/authStore.ts';
import '/src/index.css';
useAuthStore.setState({user:{id:7,email:'me@example.test',name:'Me',is_superuser:true},accessToken:'qa',isAuthenticated:true});
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Workspace,{legacyKey:'${legacyKey}',onNotes:()=>{}}));
</script></body></html>`;
(async () => {
  const browser = await chromium.launch({ headless: true });
  let rows = [], nextId = 1, failNextSave = false;
  const errors = [];
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
    const first = await device(true), page = first.page;
    await page.getByRole('button',{name:'Save browser tasks to CRM',exact:true}).click();
    await expect(page.getByRole('button',{name:'Old browser task',exact:true})).toBeVisible();
    const old = await page.evaluate(key => JSON.parse(localStorage.getItem(key)),legacyKey);
    assert.deepEqual(old.entries.map(e=>e.kind), ['note']);
    await page.getByRole('button',{name:'New task',exact:true}).click();
    await page.getByLabel('Task Title',{exact:true}).fill('Cross-device task');
    await page.getByRole('button',{name:'Assign to me',exact:true}).click();
    failNextSave = true;
    await page.getByRole('button',{name:'Create Task',exact:true}).first().click();
    await expect(page.getByRole('alert')).toContainText('Save temporarily unavailable');
    await expect(page.getByLabel('Task Title',{exact:true})).toHaveValue('Cross-device task');
    assert.equal(rows.length,1);
    await page.getByRole('button',{name:'Create Task',exact:true}).first().click();
    await expect(page.getByRole('button',{name:'Cross-device task',exact:true})).toBeVisible();
    assert.equal(rows[1].owner_user_id,7);
    assert.deepEqual(rows[1].task_details.assignees,['me@example.test']);
    const second = await device();
    await expect(second.page.getByRole('button',{name:'Cross-device task',exact:true})).toBeVisible();
    await second.page.getByRole('button',{name:'Edit task Cross-device task',exact:true}).click();
    await second.page.getByLabel('Task Title',{exact:true}).fill('Edited from another device');
    await second.page.getByRole('button',{name:'Save changes',exact:true}).first().click();
    await expect(second.page.getByRole('button',{name:'Edited from another device',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Refresh tasks',exact:true}).click();
    await expect(page.getByRole('button',{name:'Edited from another device',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Delete task Edited from another device',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal(rows[1].deleted,undefined);
    await page.getByRole('button',{name:'Delete task Edited from another device',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Delete task',exact:true}).click();
    await expect(page.getByRole('button',{name:'Edited from another device',exact:true})).toHaveCount(0);
    await second.page.reload();
    await expect(second.page.getByRole('button',{name:'Old browser task',exact:true})).toBeVisible();
    await expect(second.page.getByRole('button',{name:'Edited from another device',exact:true})).toHaveCount(0);
    assert.deepEqual(errors,[]);
    console.log('PASS: import preserves notes, failed save retains form, self assignment, fresh-device load, edit, delete confirmation and reload');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
