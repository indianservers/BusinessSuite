const {chromium, expect} = require('../frontend/node_modules/playwright/test');
const assert = require('node:assert/strict');
const origin = process.env.CRM_GALLERY_QA_ORIGIN || 'http://127.0.0.1:5194';
const html = `<!doctype html><html><head><script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module" src="/scripts/fixtures/crm-gallery-qa.tsx"></script></body></html>`;
(async () => {
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [], saved = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/__gallery_qa', route => route.fulfill({contentType:'text/html',body:html}));
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname.endsWith('/template-studio/metadata')) return route.fulfill({json:{fields:[],can_edit:true,can_publish_email:true}});
    if (url.pathname.endsWith('/template-studio/render')) {
      const t = req.postDataJSON().template;
      return route.fulfill({json:{html:'<p>QA preview</p>',body:'<p>QA preview</p>',subject:t.subject,unresolved:[],blocks:t.design.blocks.map(b=>({id:b.id,html:'<p>Preview block</p>'}))}});
    }
    if (url.pathname.endsWith('/template-studio/templates') && req.method() === 'POST') {
      const value = {...req.postDataJSON(),id:saved.length+1}; saved.push(value); return route.fulfill({status:201,json:value});
    }
    return route.fulfill({json:{items:saved}});
  });
  try {
    await page.goto(origin+'/__gallery_qa');
    const gallery = page.getByRole('region',{name:'Email template gallery'});
    await expect(gallery.locator('article')).toHaveCount(72);
    await expect(page.getByRole('heading',{name:'Start with a design',exact:true})).toBeVisible();
    await page.screenshot({path:'outputs/crm-template-gallery-desktop.png',fullPage:false});
    await gallery.getByRole('button',{name:'Accounts 9',exact:true}).click();
    await expect(gallery.locator('article')).toHaveCount(9);
    await gallery.getByLabel('Filter gallery goal').selectOption('Renew');
    await expect(gallery.locator('article')).toHaveCount(1);
    await gallery.getByRole('button',{name:'Preview Plan the next chapter',exact:true}).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('.tg-inbox-subject')).toContainText('Planning ahead with Northstar Technologies');
    await dialog.getByRole('button',{name:'Mobile',exact:true}).click();
    await dialog.getByLabel('Show sample details').uncheck();
    await expect(dialog.locator('.tg-inbox-subject')).toContainText('Planning ahead with {{company}}');
    await dialog.getByRole('button',{name:'Customize this design',exact:false}).click();
    await expect(page.getByLabel('Template name')).toHaveValue('Plan the next chapter');
    await expect(page.getByLabel('Template module',{exact:true})).toHaveValue('account');
    await expect(page.getByLabel('Email subject')).toHaveValue('Planning ahead with {{company}}');
    await page.getByRole('button',{name:'Save template',exact:true}).click();
    await expect(page.getByText('Template saved',{exact:true})).toBeVisible();
    assert.equal(saved[0].module,'account');
    await page.getByRole('button',{name:/Library/}).click();
    await gallery.getByLabel('Search gallery').fill('nonexistent scenario');
    await expect(gallery.getByText('No matching designs')).toBeVisible();
    await gallery.getByRole('button',{name:'Reset gallery',exact:true}).click();
    await page.setViewportSize({width:390,height:844});
    await gallery.getByRole('button',{name:'Support tickets 5',exact:true}).click();
    await expect(gallery.locator('article')).toHaveCount(5);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Gallery fits mobile width');
    await page.screenshot({path:'outputs/crm-template-gallery-mobile.png',fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.route('**/api/v1/crm/template-studio/metadata', route=>route.fulfill({json:{fields:[],can_edit:false,can_publish_email:false}}));
    await page.reload();
    await expect(gallery.getByRole('button',{name:'Customize A useful first conversation',exact:true})).toBeDisabled();
    await gallery.getByRole('button',{name:'Preview A useful first conversation',exact:true}).click();
    await expect(page.getByRole('dialog').getByRole('button',{name:'Customize this design',exact:false})).toBeDisabled();
    assert.deepEqual(errors,[]);
    console.log('PASS: 72 original designs, module and goal filtering, personalized preview, mobile preview, editor selection, save, empty state, mobile width; existing starters preserved');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
