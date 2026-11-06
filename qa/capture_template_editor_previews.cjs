const {chromium, expect} = require('../frontend/node_modules/playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const origin = process.env.TEMPLATE_STUDIO_BASE_URL || 'http://127.0.0.1:5488';
const auth = JSON.parse(fs.readFileSync(process.env.TEMPLATE_STUDIO_AUTH_FILE, 'utf8'));
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><script type="module">import RefreshRuntime from '/@react-refresh';RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body style="margin:0"><div id="root"></div><script type="module" src="/scripts/fixtures/template-studio-qa.tsx"></script></body></html>`;
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1500,height:1200}});
    await page.addInitScript(({token,user}) => {
      if (window.top !== window) return;
      window.__AI_HRMS_CONFIG__ = {apiBaseUrl:'/api/v1'};
      sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0}));
    },auth);
    await page.route('**/__template_editor_preview', route => route.fulfill({contentType:'text/html',body:html}));
    page.on('dialog',dialog=>dialog.accept());
    fs.mkdirSync(path.resolve('outputs/template-studio'),{recursive:true});
    await page.goto(origin+'/__template_editor_preview');
    await page.getByRole('button',{name:'Customize Your onboarding starts here',exact:true}).click();
    await expect(page.getByLabel('Shared template design canvas')).toBeVisible();
    await page.getByLabel('Block content',{exact:true}).fill('DSB CHARTERED');
    await page.getByLabel('Sample data',{exact:true}).check();
    await page.getByRole('button',{name:'Edit merge values & line items',exact:true}).click();
    await page.getByLabel('Value for organization.name',{exact:true}).fill('DSB Chartered');
    await page.getByRole('button',{name:'Close merge values',exact:true}).click();
    await expect(page.locator('.ts-paper')).toContainText('Ananya Rao');
    await expect(page.locator('.ts-paper')).toContainText('A clear next step');
    await page.getByRole('button',{name:'Select Heading block',exact:true}).click();
    await page.getByLabel('Canvas zoom').selectOption('100');
    await page.locator('.ts-editor').screenshot({path:path.resolve('outputs/template-studio/email-editor-preview.png')});
    await page.getByRole('button',{name:'← Library',exact:true}).click();
    await page.getByRole('button',{name:/^Business documents/}).click();
    await page.getByRole('button',{name:'Create template',exact:true}).click();
    await page.getByLabel('Sample data',{exact:true}).check();
    await page.getByLabel('Canvas zoom').selectOption('85');
    await expect(page.locator('.ts-paper')).toContainText('29,500.00');
    await page.getByRole('button',{name:'Select Heading block',exact:true}).click();
    await page.locator('.ts-editor').screenshot({path:path.resolve('outputs/template-studio/invoice-editor-preview.png')});
    console.log('Captured production email and invoice editors with the shared canvas and real rendered previews.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
