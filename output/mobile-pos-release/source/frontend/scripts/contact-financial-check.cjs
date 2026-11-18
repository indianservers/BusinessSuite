// Run against local Vite: node frontend/scripts/contact-financial-check.cjs
const {chromium, expect} = require('playwright/test');
(async () => {
  const browser = await chromium.launch();
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      const errors = [], writes = [];
      let profile = {gstNumber: '', bankAccounts: [], upiIds: [], version: 0};
      const transactions = [];
      page.on('pageerror', e => errors.push(e.message));
      const contact = {id: 1, name: 'Test Contact', tags: ['Customer', 'Vendor'], status: 'Active', version: '1'};
      await page.route('**/api/v1/**', async route => {
        const req = route.request(), p = new URL(req.url()).pathname;
        if (req.method() !== 'GET') {
          const body = req.postDataJSON(); writes.push({p, body});
          if (p.includes('/financial-transactions')) {
            if(req.method()==='POST') transactions.push({...body, id: transactions.length+1, version: 1, status: 'recorded'});
            else { const row=transactions.find(x=>x.id===Number(p.split('/').at(-1))); if(req.method()==='PATCH') Object.assign(row,body,{version:row.version+1}); else Object.assign(row,{status:'void',voidReason:body.reason,version:row.version+1}); }
            return route.fulfill({json: transactions.at(-1)});
          }
          if (body.financialData) profile = {...body.financialData, version: profile.version+1};
          return route.fulfill({json: contact});
        }
        let data = {items: []};
        if (p.endsWith('/contact-directory')) data = {items: [{...contact, gstNumber: profile.gstNumber, bankAccountCount: profile.bankAccounts.length, upiCount: profile.upiIds.length}], total: 1, stats: {}, canManage: true, classifications: ['Customer', 'Vendor']};
        if (p.endsWith('/contact-directory/1')) data = {...contact, leads: [], related: {}};
        if (p.endsWith('/financial-data')) data = profile;
        if (p.endsWith('/financial-transactions')) data = {items: transactions, total: transactions.length};
        if (p.endsWith('/channels')) data = {items: [], version: '1'};
        await route.fulfill({json: data});
      });
      await page.route('**/contact-financial-qa', route => route.fulfill({contentType: 'text/html', body: `<div id="root"></div><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>t=>t;window.__vite_plugin_react_preamble_installed__=true;await import('/scripts/contact-editor-harness.tsx');</script>`}));
      await page.goto('http://localhost:5173/contact-financial-qa');
      const edit = async () => {
        await page.getByRole('button', {name: 'More actions for Test Contact', exact: true}).click();
        await page.getByRole('menuitem', {name: 'Edit', exact: true}).click();
        await page.getByRole('button', {name: 'Financial data', exact: true}).click();
      };
      await edit();
      await page.getByRole('textbox', {name: 'Company GST number', exact: true}).fill('27ABCDE1234F1Z5');
      for (const [index, number] of [[1, '001234567890'], [2, '009876543210']]) {
        await page.getByRole('button', {name: 'Add bank account', exact: true}).click();
        await page.getByRole('textbox', {name: `Account number ${index}`, exact: true}).fill(number);
        await page.getByRole('textbox', {name: `IFSC ${index}`, exact: true}).fill('SBIN0001234');
        await page.getByRole('textbox', {name: `MICR ${index}`, exact: true}).fill('400002001');
      }
      for (const [index, upi] of [[1, 'test@bank'], [2, 'business@bank']]) {
        await page.getByRole('button', {name: 'Add UPI', exact: true}).click();
        await page.getByRole('textbox', {name: `UPI ID ${index}`, exact: true}).fill(upi);
        await page.getByRole('textbox', {name: `UPI mobile ${index}`, exact: true}).fill('+919876543210');
      }
      // Switching tabs must preserve the complete unsaved financial draft.
      await page.getByRole('button', {name: 'Basic details', exact: true}).click();
      await page.getByRole('button', {name: 'Financial data', exact: true}).click();
      await expect(page.getByRole('textbox', {name: 'Account number 1', exact: true})).toHaveValue('001234567890');
      await page.getByRole('button', {name: 'Save contact', exact: true}).click();
      await expect(page.getByRole('dialog')).toHaveCount(0);
      expect(writes.at(-1).body.financialData.bankAccounts).toHaveLength(2);
      expect(writes.at(-1).body.financialData.upiIds).toHaveLength(2);
      await edit();
      await expect(page.getByRole('textbox', {name: 'UPI ID 2', exact: true})).toHaveValue('business@bank');
      await page.getByRole('button', {name: 'Record transaction', exact: true}).click();
      await page.getByRole('spinbutton', {name: 'Transaction amount', exact: true}).fill('123.45');
      await page.getByLabel('Transaction reference', {exact: true}).fill('UTR123');
      await page.getByRole('button', {name: 'Save transaction', exact: true}).click();
      await expect(page.getByText('Received INR 123.45', {exact: true})).toBeVisible();
      await page.getByRole('button',{name:'Correct transaction',exact:true}).click();
      await page.getByRole('spinbutton',{name:'Transaction amount',exact:true}).fill('125.50');
      await page.getByLabel('Transaction correction reason',{exact:true}).fill('Fix original amount');
      await page.getByRole('button',{name:'Save correction',exact:true}).click();
      await expect(page.getByText('Received INR 125.50',{exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Void transaction',exact:true}).click();
      await page.getByLabel('Transaction void reason',{exact:true}).fill('Duplicate entry');
      await page.getByRole('button',{name:'Confirm void',exact:true}).click();
      await expect(page.getByText(/^Void .*Duplicate entry$/, {exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Remove bank account 2',exact:true}).click();
      await page.getByRole('button',{name:'Remove UPI 2',exact:true}).click();
      await page.getByRole('button',{name:'Save contact',exact:true}).click();
      expect(profile.bankAccounts).toHaveLength(1); expect(profile.upiIds).toHaveLength(1);
      await edit();
      await page.getByRole('button', {name: 'Cancel', exact: true}).click();
      await page.getByRole('button', {name: 'View Test Contact', exact: true}).click();
      await page.getByRole('tab', {name: 'Financial data', exact: true}).click();
      await expect(page.getByRole('textbox', {name: 'Company GST number', exact: true})).toHaveValue('27ABCDE1234F1Z5');
      await expect(page.getByRole('button', {name: 'Record transaction', exact: true})).toHaveCount(0);
      expect(errors).toEqual([]);
      console.log(`Financial profile, multiple banks/UPIs, save/reopen, transaction and read-only preview passed at ${width}px`);
      await page.close();
    }
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exit(1);});
