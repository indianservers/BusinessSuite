import {test,expect} from '../frontend/node_modules/playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test.skip(!process.env.TEMPLATE_STUDIO_AUTH_FILE,'Requires isolated seeded record API.');
test('choose templates at all five native record pages and export actual data',async({page},info)=>{
  const auth=JSON.parse(fs.readFileSync(process.env.TEMPLATE_STUDIO_AUTH_FILE!,'utf8'));
  await page.addInitScript(({token,user,branch_id,records})=>{
    if(window.top!==window)return;
    (window as any).__AI_HRMS_CONFIG__={apiBaseUrl:'/api/v1'};
    (window as any).__TEMPLATE_RECORDS__=records;
    sessionStorage.setItem('suite-branch',String(branch_id));
    sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0}));
  },auth);
  const html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><script type="module">import RefreshRuntime from "/@react-refresh";RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body style="margin:0"><div id="root"></div><script type="module" src="/scripts/fixtures/record-templates-qa.tsx"></script></body></html>';
  await page.route('**/__record_template_qa',route=>route.fulfill({contentType:'text/html',body:html}));
  const apiHeaders={Authorization:`Bearer ${auth.token}`,'X-Suite-Branch':String(auth.branch_id)};
  const suffix=Date.now();
  for(const entity of ['lead','contact','account','deal']){
    const response=await page.request.post('/api/v1/crm/template-studio/templates',{headers:apiHeaders,data:{name:`Native ${entity} ${suffix}`,category:'email',document_type:'email',module:entity,status:'ready',subject:'Hello {{name}}',design:{blocks:[{id:'text',type:'text',text:'{{name}} · {{company}} · {{email}} · {{organization.name}}'+(entity==='deal'?' · {{deal.name}} · {{deal.amount}}':'')}]}}});
    expect(response.ok(),await response.text()).toBeTruthy();
  }
  await page.goto('/__record_template_qa');
  fs.mkdirSync(path.resolve('../outputs/template-studio'),{recursive:true});
  const nav=page.getByRole('navigation',{name:'Template QA records'});
  for(const [entity,label,name] of [['lead','Leads','Actual Lead'],['contact','Contacts','Actual Contact'],['account','Accounts','Actual Account'],['deal','Deals','Actual Contact']]){
    await nav.getByRole('link',{name:label,exact:true}).click();
    await page.getByRole('button',{name:'Use template',exact:true}).first().click();
    const dialog=page.getByRole('dialog').filter({has:page.getByRole('heading',{name:'Choose a template',exact:true})});
    await dialog.getByRole('button',{name:new RegExp(`Native ${entity} ${suffix}`)}).click();
    const frame=dialog.frameLocator('iframe[title="Record template preview"]');
    await expect(frame.getByText(name,{exact:false})).toBeVisible();
    await expect(frame.getByText('Actual Seller Limited',{exact:false})).toBeVisible();
    if(entity==='deal')await expect(frame.getByText('1,234.50',{exact:false})).toBeVisible();
    await expect(dialog.getByRole('button',{name:'Export HTML',exact:true})).toBeEnabled();
    const download=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'Export HTML',exact:true}).click();
    const content=fs.readFileSync((await(await download).path())!,'utf8');
    expect(content).toContain(name);expect(content).not.toContain('{{');
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  }
  await nav.getByRole('link',{name:'Invoices',exact:true}).click();
  await page.getByRole('button',{name:'Use template',exact:true}).click();
  const dialog=page.getByRole('dialog').filter({has:page.getByRole('heading',{name:'Choose a template',exact:true})});
  await dialog.getByRole('button',{name:/Invoice · Modern/}).click();
  await expect(dialog.frameLocator('iframe[title="Record template preview"]').getByText('ACTUAL-INV-42',{exact:false})).toBeVisible();
  await expect(dialog.frameLocator('iframe[title="Record template preview"]').getByText('224.20',{exact:false})).toBeVisible();
  await expect(dialog.frameLocator('iframe[title="Record template preview"]').getByText('DRAFT · Not issued',{exact:true})).toBeVisible();
  for(const input of await dialog.locator('.record-template-missing input').all()) {
    const label=await input.getAttribute('aria-label');
    await input.fill(label==='Fill document.terms'?'Payment due within 14 days.':label==='Fill sender_title'?'Account manager':'+91 98765 43210');
  }
  await expect(dialog.getByRole('button',{name:'Export HTML',exact:true})).toBeEnabled();
  const download=page.waitForEvent('download');await dialog.getByRole('button',{name:'Export HTML',exact:true}).click();
  const content=fs.readFileSync((await(await download).path())!,'utf8');
  expect(content).toContain('Actual consulting');expect(content).toContain('224.20');expect(content).not.toContain('{{');
  await dialog.screenshot({path:path.resolve(`../outputs/template-studio/record-invoice-${info.project.name}.png`)});
});
