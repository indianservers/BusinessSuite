const { chromium, expect: baseExpect } = require('playwright/test');
const base = process.env.BRANCH_QA_BASE_URL || 'http://127.0.0.1:5191';
const expect = baseExpect.configure({timeout:30000});
(async () => {
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport:{width,height:950}});
      page.on('pageerror', error => console.error(error.message));
      let fail = true;
      const branches = [{id:1,name:'Main',code:'MAIN',can_write:true,is_active:true}];
      await page.route('**/branch-settings-qa', r => r.fulfill({contentType:'text/html', body:`<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/fixtures/branch-settings-qa.tsx');</script>`}));
      await page.route('**/api/v1/**', async r => {
        const path = new URL(r.request().url()).pathname;
        if (path.endsWith('/branches/access/users')) return r.fulfill({json:[]});
        if (path.endsWith('/branches/ownership/inventory')) return r.fulfill({json:{tables:[]}});
        if (r.request().method() === 'POST' && path.endsWith('/branches')) {
          if (fail) return r.fulfill({status:409,json:{detail:'Branch code already exists'}});
          const branch = {id:2,...r.request().postDataJSON(),can_write:true,is_active:true};
          branches.push(branch);
          return r.fulfill({status:201,json:branch});
        }
        return r.fulfill({json:path.endsWith('/branches/context') ? {company_id:1,selected:null,all_branches:true,manage_access:true,branches} : {items:[],branches:[]}});
      });
      await page.goto(base+'/branch-settings-qa');
      await expect(page.getByRole('combobox',{name:'Current branch'})).toHaveValue('all');
      await page.getByRole('button',{name:'Create branch',exact:true}).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel('Branch name *').fill('Chennai');
      await dialog.getByLabel('Branch code *').fill('CHN');
      await dialog.getByLabel('Reason for creating branch *').fill('New Chennai office');
      await dialog.locator('[data-smart-create-footer]').getByRole('button',{name:'Create branch',exact:true}).click();
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole('alert')).toContainText('Branch code already exists');
      fail = false;
      await dialog.locator('[data-smart-create-footer]').getByRole('button',{name:'Create branch',exact:true}).click();
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('status').filter({hasText:'Chennai created'})).toBeVisible();
      await page.getByRole('button',{name:'Create branch',exact:true}).click();
      await expect(page.getByRole('dialog').getByLabel('Branch name *')).toHaveValue('');
      await page.close();
      console.log(`Branch creation failure, retry, closure, reset and aggregate selector passed (${width}px)`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
