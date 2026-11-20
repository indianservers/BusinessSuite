import {test,expect,type Page} from '../frontend/node_modules/playwright/test';
import {mkdirSync,writeFileSync,readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';

const output=resolve('../output/offerings-live-audit');mkdirSync(output,{recursive:true});
const database=resolve('../.local/offerings-browser-qa/audit.sqlite');
function dbRows(sql:string,params:unknown[]=[]){return JSON.parse(execFileSync(resolve('../backend/venv/Scripts/python.exe'),['-c',`import sqlite3,json,sys\nc=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);c.row_factory=sqlite3.Row\nprint(json.dumps([dict(r) for r in c.execute(sys.argv[2],json.loads(sys.argv[3]))]))`,database,sql,JSON.stringify(params)],{encoding:'utf8'}));}
const observed:Record<string,unknown>[]=[];
test.beforeEach(async({page},info)=>{
 const errors:string[]=[],apiFailures:string[]=[],consoleErrors:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
 page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)apiFailures.push(`${r.status()} ${new URL(r.url()).pathname}`);});
 observed.push({test:info.title,errors,apiFailures,consoleErrors});
});
test.afterEach(async({},info)=>{
 const record=observed[observed.length-1] as {errors:string[];apiFailures:string[];consoleErrors:string[];[key:string]:unknown};
 const expected=info.annotations.filter(a=>a.type==='expected-http').map(a=>a.description!);
 const unexpectedHTTP=record.apiFailures.filter(line=>!expected.some(status=>line.startsWith(status+' ')));
 const unexpectedConsole=record.consoleErrors.filter(line=>!expected.some(status=>line.includes('status of '+status)));
 Object.assign(record,{status:info.status,error:info.error?.message,expectedHTTP:expected,unexpectedHTTP,unexpectedConsole});
 if(info.status==='passed'&&(record.errors.length||unexpectedHTTP.length||unexpectedConsole.length))record.status='failed';
 writeFileSync(resolve(output,info.title.replace(/[^a-z0-9]+/gi,'-')+'-observations.json'),JSON.stringify(record,null,2));
 expect(record.errors,'No uncaught browser errors').toEqual([]);expect(unexpectedHTTP,'No unexpected API failures').toEqual([]);expect(unexpectedConsole,'No unexpected console errors').toEqual([]);
});
async function login(page:Page,email="browser-audit@example.com",company="Workflow Test Company"){
 await page.goto('/login?redirect=/srm/products-services');
 await page.getByPlaceholder('you@company.com').fill(email);
 await page.getByPlaceholder('Enter your password').fill('BrowserAudit@2026');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page).not.toHaveURL(/\/login/,{timeout:30000});
 await page.waitForFunction(()=>!location.pathname.includes('/continue')||document.querySelector('h1')?.textContent==='Choose your company');
 if(await page.getByRole('heading',{name:'Choose your company',exact:true}).isVisible())await page.getByRole('button',{name:new RegExp(`^${company}`)}).click();
 await page.waitForURL(url=>!url.pathname.includes('/continue'));
 await page.goto('/srm/products-services');
 await expect(page.getByRole('group',{name:'Catalog type',exact:true})).toBeVisible();
}
async function createOffering(page:Page,kind:string,months=1){
 const label={product:'Products',service:'Services',membership:'Memberships',subscription:'Subscriptions',bundle:'Bundles'}[kind]!;
 await page.getByRole('group',{name:'Catalog type',exact:true}).getByRole('button',{name:label,exact:true}).click();
 await page.locator('.sc-hero').getByRole('button',{name:'New item',exact:true}).click();
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 const suffix=Date.now().toString(),name=`Browser audit ${kind} ${months} ${suffix}`,code=`BQA-${kind}-${months}-${suffix}`;
 await dialog.getByLabel(`${kind[0].toUpperCase()+kind.slice(1)} name`,{exact:true}).fill(name);
 await dialog.getByLabel(kind==='product'?'SKU / Product code':kind==='service'?'Service code':'Offering code',{exact:true}).fill(code);
 await dialog.getByLabel('Base price (before tax)',{exact:true}).fill('100');
 await dialog.getByLabel('Tax %',{exact:true}).fill('18');
 if(kind==='membership'||kind==='subscription'){
  await dialog.getByText('Plan duration & activation',{exact:true}).click();
  await dialog.getByLabel('Quick duration',{exact:true}).selectOption(String(months));
  await dialog.getByText('Benefits & eligibility',{exact:true}).click();
  await dialog.getByRole('button',{name:'Add benefit',exact:true}).click();
  await dialog.getByLabel('Benefit name',{exact:true}).fill('Audit sessions');
  await dialog.getByLabel('Allowance',{exact:true}).fill('20');
 }
 if(kind==='bundle'){
  await dialog.getByText('Bundle components',{exact:true}).click();
  const component=dbRows("SELECT id,sku FROM srm_products WHERE product_type='stock' AND active=1 ORDER BY id LIMIT 1")[0];
  await addComponent(page,component.id,component.sku);
 }
 await page.screenshot({path:resolve(output,`${kind}-${months}-creation.png`),fullPage:true});
 const saved=page.waitForResponse(r=>r.url().includes('/catalog/items')&&r.request().method()==='POST');
 await dialog.locator('button[data-save-action]').click();
 const result=await saved;expect(result.status(),await result.text()).toBe(201);
 const record=await result.json();await expect(dialog).not.toBeVisible();
 const rows=dbRows('SELECT id,sku,item_name,product_type,track_inventory,metadata_json FROM srm_products WHERE sku=?',[code]);
 expect(rows).toHaveLength(1);expect(rows[0].id).toBe(record.id);
 if(['membership','subscription'].includes(kind)){expect(JSON.parse(rows[0].metadata_json).plan.duration.count).toBe(months);expect(rows[0].track_inventory).toBe(0);}
 writeFileSync(resolve(output,`${kind}-${months}-database.json`),JSON.stringify(rows,null,2));
 return record;
}
test('real browser login and isolated catalog bootstrap',async({page})=>{
 const errors:string[]=[],failures:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.url().includes('/api/')&&r.status()>=400)failures.push(`${r.status()} ${new URL(r.url()).pathname}`);});
 await login(page);
 await page.screenshot({path:resolve(output,'live-catalog-bootstrap.png'),fullPage:true});
 writeFileSync(resolve(output,'bootstrap-diagnostics.json'),JSON.stringify({errors,failures},null,2));
 expect(errors).toEqual([]);expect(failures).toEqual([]);
});

for(const kind of ['product','service','membership','subscription','bundle'])test(`real ${kind} create, view and shared master persistence`,async({page})=>{
 await login(page);const record=await createOffering(page,kind);
 await page.getByLabel('Search catalog',{exact:true}).fill(record.code);
 const card=page.locator('.sc-card').filter({has:page.getByRole('button',{name:record.name,exact:true})});
 await expect(card).toBeVisible();await card.getByRole('button',{name:record.name,exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText(record.name);
 await page.screenshot({path:resolve(output,`${kind}-detail.png`),fullPage:true});
});
for(const months of [3,6,12])test(`real membership ${months}-month preset persists`,async({page})=>{await login(page);await createOffering(page,'membership',months);});

test('real customer membership assignment, pause, resume, renewal and history',async({page})=>{
 await login(page);
 const offering=dbRows("SELECT id,item_name FROM srm_products WHERE product_type='membership' AND active=1 ORDER BY id LIMIT 1")[0];
 expect(offering).toBeTruthy();
 await page.goto('/crm/customer-360?customer=101');
 await page.getByText('Memberships & subscriptions',{exact:true}).click();
 await page.getByRole('button',{name:'Assign plan',exact:true}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByLabel('Customer plan',{exact:true}).selectOption(String(offering.id));
 const issued=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/customer-plans'&&r.request().method()==='POST');
 await dialog.getByRole('button',{name:'Assign plan',exact:true}).click();
 const result=await issued;expect(result.status(),await result.text()).toBe(201);
 const plan=await result.json();
 await expect(page.getByRole('region',{name:'Selected customer plan'})).toBeVisible();
 expect(dbRows('SELECT status FROM catalog_customer_plans WHERE id=?',[plan.id])[0].status).toBe('active');
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 await expect(page.getByRole('button',{name:'Resume',exact:true})).toBeVisible();
 expect(dbRows('SELECT status FROM catalog_customer_plans WHERE id=?',[plan.id])[0].status).toBe('paused');
 await page.getByRole('button',{name:'Resume',exact:true}).click();
 await expect(page.getByRole('button',{name:'Pause',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Renew',exact:true}).click();
 await page.getByRole('dialog').getByLabel('New expiry date',{exact:true}).fill('2028-12-31');
 const renewed=page.waitForResponse(r=>r.url().includes(`/customer-plans/${plan.id}/lifecycle`)&&r.request().method()==='POST');
 await page.getByRole('dialog').getByRole('button',{name:'Renew membership',exact:true}).click();
 expect((await renewed).status()).toBe(200);
 expect(dbRows('SELECT end_date FROM catalog_customer_plans WHERE id=?',[plan.id])[0].end_date).toBe('2028-12-31');
 await page.getByRole('button',{name:'History',exact:true}).click();
 await expect(page.getByRole('region',{name:'Selected customer plan'})).toContainText('renew');
 await page.screenshot({path:resolve(output,'customer-membership-history.png'),fullPage:true});
 const history=dbRows('SELECT action,before,after FROM catalog_plan_events WHERE plan_id=? ORDER BY id',[plan.id]);
 expect(history.map((e:{action:string})=>e.action)).toEqual(['issue','pause','resume','renew']);
 writeFileSync(resolve(output,'customer-lifecycle-database.json'),JSON.stringify(history,null,2));
});

async function openPOS(page:Page){
 await login(page);await page.goto('/srm/pos/terminal');
 const branch=page.getByLabel('POS branch',{exact:true});
 await expect(branch).toBeVisible();await branch.selectOption('1');await page.getByRole('button',{name:'Open POS',exact:true}).click();
 await expect(page.getByLabel('Search or scan items',{exact:true})).toBeVisible();
 await expect(page.locator('[aria-label="Loading products and services"]')).toBeHidden({timeout:30000});
}

test('real POS recognizes and filters all five offering types',async({page})=>{
 await openPOS(page);
 const filters=page.getByLabel('Catalogue filters',{exact:true});
 for(const [kind,label] of [['stock','Products'],['service','Services'],['membership','Memberships'],['subscription','Subscriptions'],['bundle','Bundles']]){
  const record=dbRows('SELECT id,item_name,sku FROM srm_products WHERE product_type=? AND active=1 ORDER BY id LIMIT 1',[kind])[0];
  await filters.getByRole('button',{name:new RegExp(`^${label} \\(`)}).click();
  await page.getByLabel('Search or scan items',{exact:true}).fill(record.sku);
  await expect(page.locator(`button[data-product-id="${record.id}"]`).first()).toBeVisible();
  if(kind!=='stock'&&kind!=='service')await expect(page.locator('.srm-pos-catalog')).toContainText(label.slice(0,-1));
  await page.getByLabel('Search or scan items',{exact:true}).fill('');
 }
 await page.screenshot({path:resolve(output,'pos-all-offering-types.png'),fullPage:true});
});

test('real POS paid membership creates invoice, payment and one customer plan',async({page})=>{
 const registerLoaded=page.waitForResponse(r=>r.url().includes('/srm/pos/sessions/active'),{timeout:60000});
 await openPOS(page);
 const register=await (await registerLoaded).json();
 await page.getByRole('button',{name:/Session & actions/}).click();
 const openRegister=page.getByRole('button',{name:'Open POS register',exact:true});
 if(!register?.session?.id){await openRegister.click();await expect(page.getByText(/POS-[0-9]+/)).toBeVisible();}
 const record=dbRows("SELECT id,item_name,sku FROM srm_products WHERE product_type='membership' AND active=1 ORDER BY id LIMIT 1")[0];
 await page.getByRole('button',{name:'Change sale customer',exact:true}).click();
 await page.getByRole('combobox',{name:'Sale customer',exact:true}).click();
 await page.getByRole('option').filter({hasText:'Synthetic customer 101'}).click();
 await page.getByLabel('Search or scan items',{exact:true}).fill(record.sku);
 await page.locator(`button[data-product-id="${record.id}"]`).first().click();
 await expect(page.locator('#pos-checkout-reason')).toContainText('Ready to collect payment');
 await page.getByRole('button',{name:/^Collect /}).click();
 const payment=page.getByRole('dialog');
 await payment.getByLabel('Follow-up customer',{exact:true}).selectOption('101');
 const print=payment.getByLabel('Print receipt after checkout',{exact:true});
 if(await print.first().isChecked())await print.first().uncheck();
 await page.screenshot({path:resolve(output,'pos-membership-checkout.png'),fullPage:true});
 const paid=page.waitForResponse(r=>r.url().includes('/srm/service-checkout')&&r.request().method()==='POST');
 await payment.getByRole('button',{name:'Complete Sale',exact:true}).first().click();
 const response=await paid;expect(response.status(),await response.text()).toBeLessThan(300);
 const result=await response.json();
 writeFileSync(resolve(output,'pos-paid-request.json'),JSON.stringify(response.request().postDataJSON(),null,2));
 const invoices=dbRows('SELECT id,total_amount,paid_amount,balance_amount,status FROM srm_invoices WHERE id=?',[result.invoice.id]);
 expect(invoices[0].status).toBe('paid');expect(Number(invoices[0].total_amount)).toBe(118);expect(Number(invoices[0].paid_amount)).toBe(118);
 const plans=dbRows("SELECT id,status,source_key,offering_id FROM catalog_customer_plans WHERE source_key LIKE ?",[`sales-order:${result.sales_order_id}:line:%`]);
 expect(plans).toHaveLength(1);expect(plans[0].status).toBe('active');
 await page.screenshot({path:resolve(output,'pos-membership-paid.png'),fullPage:true});
 writeFileSync(resolve(output,'pos-paid-database.json'),JSON.stringify({invoices,plans},null,2));
});

async function settleLayout(page:Page){await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));}
async function revealSection(page:Page,target:ReturnType<Page['locator']>){
 await expect(async()=>{
 await settleLayout(page);
 for(let step=0;step<40&&!await target.isVisible();step++){const previous=page.getByRole('button',{name:'Previous section',exact:true});if(!await previous.isVisible()||!await previous.isEnabled())break;await previous.click();await settleLayout(page);}
 for(let step=0;step<40&&!await target.isVisible();step++){
  const next=page.getByRole('button',{name:'Next section',exact:true});
  if(!await next.isVisible()||!await next.isEnabled())break;
  await next.click();await settleLayout(page);
 }
 await expect(target).toBeVisible();
 }).toPass({timeout:30000});
}
for(const [width,height] of [[1920,1080],[1366,768],[768,1024],[390,844]])test(`real responsive catalog and editors ${width}x${height}`,async({page})=>{
 await page.setViewportSize({width,height});await login(page);
 const signatures=[];
 for(const [kind,stored] of [['product','stock'],['service','service'],['membership','membership'],['subscription','subscription'],['bundle','bundle']]){
  const record=dbRows('SELECT id,item_name,sku FROM srm_products WHERE product_type=? AND active=1 ORDER BY id LIMIT 1',[stored])[0];
  await page.goto(`/srm/products-services?kind=${kind}`);
  await expect(page.getByRole('group',{name:'Catalog type',exact:true}).getByRole('button',{name:{product:'Products',service:'Services',membership:'Memberships',subscription:'Subscriptions',bundle:'Bundles'}[kind]!,exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('.sc-loading')).toBeHidden();await settleLayout(page);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Catalog must not scroll horizontally').toBeTruthy();
  await revealSection(page,page.getByLabel('Search catalog',{exact:true}));
  const searched=page.waitForResponse(r=>r.url().includes('/catalog/items')&&new URL(r.url()).searchParams.get('search')===record.sku);
  await page.getByLabel('Search catalog',{exact:true}).fill(record.sku);
  await searched;
  const card=page.locator('.sc-card').filter({has:page.getByRole('button',{name:record.item_name,exact:true})});
  await revealSection(page,card);
  await page.screenshot({path:resolve(output,`${width}-${kind}-listing.png`),fullPage:true});
  await card.getByRole('button',{name:record.item_name,exact:true}).click();
  const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'Edit item',exact:true}).click();
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Loading categories…',{exact:true})).toHaveCount(0);
  const bounds=await dialog.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(-1);expect(bounds!.y).toBeGreaterThanOrEqual(-1);
  expect(bounds!.width).toBeLessThanOrEqual(width+1);expect(bounds!.height).toBeLessThanOrEqual(height+1);
  signatures.push(await dialog.evaluate(el=>{const s=getComputedStyle(el);return [s.fontFamily,s.fontSize,s.borderRadius].join('|');}));
  await page.screenshot({path:resolve(output,`${width}-${kind}-editor.png`),fullPage:true});
  await dialog.getByRole('button',{name:'Close catalog editor',exact:true}).click();
 }
 expect(new Set(signatures).size,'All five editor shells must share typography and radius').toBe(1);
});

test('real read-only role cannot mutate or read a private workspace offering',async({page},info)=>{
 info.annotations.push({type:'expected-http',description:'403'},{type:'expected-http',description:'404'});
 await login(page,'browser-reader@example.com');
 await expect(page.locator('.sc-hero').getByRole('button',{name:'New item',exact:true})).toHaveCount(0);
 await page.getByLabel('Search catalog',{exact:true}).fill('BQA-PRIVATE-WORKSPACE');
 await expect(page.getByText('No matching offerings',{exact:true})).toBeVisible();
 const privateRecord=dbRows("SELECT id FROM srm_products WHERE sku='BQA-PRIVATE-WORKSPACE'")[0];
 const status=await page.evaluate(async id=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  const response=await fetch(`/api/v1/catalog/items/membership/${id}?source=srm`,{headers:{Authorization:`Bearer ${token}`,'X-Suite-Organization':'1'}});
  return response.status;
 },privateRecord.id);
 expect([403,404]).toContain(status);
 const count=dbRows('SELECT COUNT(*) AS n FROM srm_products')[0].n;
 const write=await page.evaluate(async()=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  return (await fetch('/api/v1/catalog/items?source=srm',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1'},body:JSON.stringify({kind:'product',name:'Forbidden browser write',code:'BQA-FORBIDDEN',price:1})})).status;
 });
 expect(write).toBe(403);expect(dbRows('SELECT COUNT(*) AS n FROM srm_products')[0].n).toBe(count);
});

test('real second-company browser cannot read the first company catalog',async({page},info)=>{
 info.annotations.push({type:'expected-http',description:'404'});
 await login(page,'browser-foreign@example.com','Browser QA foreign company');
 await expect(page.locator('.sc-card')).toHaveCount(0);
 await expect(page.getByText('Your catalog is ready for its first item',{exact:true})).toBeVisible();
 const target=dbRows("SELECT id FROM srm_products WHERE product_type='membership' AND organization_id=1 LIMIT 1")[0];
 const status=await page.evaluate(async id=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  return (await fetch(`/api/v1/catalog/items/membership/${id}?source=srm`,{headers:{Authorization:`Bearer ${token}`,'X-Suite-Organization':'2'}})).status;
 },target.id);
 expect(status).toBe(404);
});

test('real membership edit, archive, status filter and record preservation',async({page})=>{
 await login(page);const record=await createOffering(page,'membership',3);
 await page.getByLabel('Search catalog',{exact:true}).fill(record.code);
 const card=page.locator('.sc-card').filter({has:page.getByRole('button',{name:record.name,exact:true})});
 await card.getByRole('button',{name:`Edit ${record.name}`,exact:true}).click();
 const revised=record.name+' revised';await page.getByRole('dialog').getByLabel('Membership name',{exact:true}).fill(revised);
 await page.getByRole('dialog').locator('button[data-save-action]').click();
 await expect(page.getByRole('dialog')).not.toBeVisible();
 expect(dbRows('SELECT item_name FROM srm_products WHERE id=?',[record.id])[0].item_name).toBe(revised);
 const updated=page.locator('.sc-card').filter({has:page.getByRole('button',{name:revised,exact:true})});
 await updated.getByRole('button',{name:`More actions for ${revised}`,exact:true}).click();
 await page.getByRole('menuitem',{name:'Archive item',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'Archive item',exact:true}).click();
 await expect(updated).not.toBeVisible();
 await page.getByLabel('Filter status',{exact:true}).selectOption('Archived');
 await expect(updated).toBeVisible();
 expect(dbRows('SELECT active,deleted_at FROM srm_products WHERE id=?',[record.id])[0]).toEqual({active:0,deleted_at:null});
 expect(dbRows('SELECT COUNT(*) AS n FROM shared_catalog_details WHERE product_id=?',[record.id])[0].n).toBe(1);
 await page.screenshot({path:resolve(output,'membership-archived-filter.png'),fullPage:true});
});

test('real fixed subscription and independent monthly recurring configuration',async({page})=>{
 await login(page);const record=await createOffering(page,'subscription',6);
 await page.getByLabel('Search catalog',{exact:true}).fill(record.code);
 await page.locator('.sc-card').filter({has:page.getByRole('button',{name:record.name,exact:true})}).getByRole('button',{name:`Edit ${record.name}`,exact:true}).click();
 const dialog=page.getByRole('dialog');await dialog.getByText('Renewal & billing',{exact:true}).click();
 await dialog.getByLabel('Recurring contract',{exact:true}).check();
 await dialog.getByRole('combobox',{name:'Renewal',exact:true}).selectOption('automatic');
 await dialog.getByLabel('Billing interval',{exact:true}).fill('1');
 await dialog.getByRole('combobox',{name:'Billing unit',exact:true}).selectOption('month');
 await page.screenshot({path:resolve(output,'subscription-recurring-configuration.png'),fullPage:true});
 await dialog.locator('button[data-save-action]').click();await expect(dialog).not.toBeVisible();
 const configuration=JSON.parse(dbRows('SELECT metadata_json FROM srm_products WHERE id=?',[record.id])[0].metadata_json).plan;
 expect(configuration.duration.count).toBe(6);expect(configuration.billing.interval_count).toBe(1);
 expect(configuration.billing.recurring).toBe(true);expect(configuration.billing.automation).toBe(false);expect(configuration.renewal.mode).toBe('automatic');
 writeFileSync(resolve(output,'subscription-configuration-database.json'),JSON.stringify(configuration,null,2));
});

test('real CRM and PMS catalogs reference the same master offerings',async({page})=>{
 await login(page);
 const before=dbRows('SELECT COUNT(*) AS n FROM srm_products')[0].n;
 for(const source of ['crm','pms'])for(const kind of ['membership','subscription','bundle']){
  const row=dbRows('SELECT id,item_name,sku FROM srm_products WHERE product_type=? AND active=1 AND sku LIKE ? ORDER BY id LIMIT 1',[kind,'BQA-%'])[0];
  await page.goto(`/${source}/products-services?kind=${kind}`);
  await page.getByLabel('Search catalog',{exact:true}).fill(row.sku);
  const card=page.locator('.sc-card').filter({has:page.getByRole('button',{name:row.item_name,exact:true})});
  await expect(card).toBeVisible();await card.getByRole('button',{name:row.item_name,exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText(row.sku);
  await page.screenshot({path:resolve(output,`${source}-${kind}-master-reference.png`),fullPage:true});
 }
 expect(dbRows('SELECT COUNT(*) AS n FROM srm_products')[0].n).toBe(before);
});

test('real invalid renewal date leaves plan and audit unchanged',async({page})=>{
 await login(page);const plan=dbRows("SELECT id,number,end_date FROM catalog_customer_plans WHERE customer_id=101 AND status='active' AND end_date IS NOT NULL ORDER BY id DESC LIMIT 1")[0];
 const before=dbRows('SELECT COUNT(*) AS n FROM catalog_plan_events WHERE plan_id=?',[plan.id])[0].n;
 await page.goto('/crm/customer-360?customer=101');await page.getByText('Memberships & subscriptions',{exact:true}).click();
 await page.locator('.r360-work-item').filter({hasText:plan.number}).getByRole('button',{name:'View',exact:true}).click();
 await page.getByRole('button',{name:'Renew',exact:true}).click();
 await page.getByRole('dialog').getByLabel('New expiry date',{exact:true}).fill(plan.end_date);
 await expect(page.getByRole('dialog').getByRole('button',{name:/^Renew (membership|subscription)$/})).toBeDisabled();
 expect(dbRows('SELECT end_date FROM catalog_customer_plans WHERE id=?',[plan.id])[0].end_date).toBe(plan.end_date);
 expect(dbRows('SELECT COUNT(*) AS n FROM catalog_plan_events WHERE plan_id=?',[plan.id])[0].n).toBe(before);
});

async function editBundle(page:Page,record:{id:number;name:string;code:string}){
 await page.goto('/srm/products-services?kind=bundle');
 await page.getByLabel('Search catalog',{exact:true}).fill(record.code);
 await page.locator('.sc-card').filter({has:page.getByRole('button',{name:record.name,exact:true})}).getByRole('button',{name:`Edit ${record.name}`,exact:true}).click();
 await page.getByRole('dialog').getByText('Bundle components',{exact:true}).click();
}
async function addComponent(page:Page,id:number,code:string){
 const dialog=page.getByRole('dialog');await dialog.getByLabel('Find component',{exact:true}).fill(code);
 await dialog.getByLabel('Add component',{exact:true}).selectOption(String(id));
}
test('real mixed bundle preserves all component types, quantities and options',async({page})=>{
 await login(page);const bundle=await createOffering(page,'bundle');await editBundle(page,bundle);
 const components=dbRows("SELECT MIN(id) AS id,product_type FROM srm_products WHERE product_type IN ('service','membership','subscription','bundle') AND active=1 AND id!=? GROUP BY product_type",[bundle.id]);
 for(const component of components){const row=dbRows('SELECT sku FROM srm_products WHERE id=?',[component.id])[0];await addComponent(page,component.id,row.sku);}
 const dialog=page.getByRole('dialog');await dialog.getByLabel('Optional',{exact:true}).last().check();
 await dialog.getByLabel('Quantity',{exact:true}).last().fill('2');
 await page.screenshot({path:resolve(output,'bundle-mixed-components.png'),fullPage:true});
 await dialog.locator('button[data-save-action]').click();await expect(dialog).not.toBeVisible();
 const saved=JSON.parse(dbRows('SELECT metadata_json FROM srm_products WHERE id=?',[bundle.id])[0].metadata_json).bundle;
 expect(saved.components).toHaveLength(5);expect(saved.components.filter((c:{optional:boolean})=>c.optional)).toHaveLength(1);
 expect(Number(saved.components[saved.components.length-1].quantity)).toBe(2);
 writeFileSync(resolve(output,'mixed-bundle-database.json'),JSON.stringify(saved,null,2));
});

test('real circular bundle edit is rejected without changing its definition',async({page},info)=>{
 info.annotations.push({type:'expected-http',description:'422'});
 await login(page);const first=await createOffering(page,'bundle');const second=await createOffering(page,'bundle');
 await editBundle(page,second);await addComponent(page,first.id,first.code);
 await page.getByRole('dialog').locator('button[data-save-action]').click();await expect(page.getByRole('dialog')).not.toBeVisible();
 const before=dbRows('SELECT metadata_json FROM srm_products WHERE id=?',[first.id])[0].metadata_json;
 await editBundle(page,first);await addComponent(page,second.id,second.code);
 const rejected=page.waitForResponse(r=>r.url().includes(`/catalog/items/bundle/${first.id}`)&&r.request().method()==='PUT');
 await page.getByRole('dialog').locator('button[data-save-action]').click();expect((await rejected).status()).toBe(422);
 await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Circular bundle');
 expect(dbRows('SELECT metadata_json FROM srm_products WHERE id=?',[first.id])[0].metadata_json).toBe(before);
});

test('real catalog search, type filtering and pagination use persisted records',async({page})=>{
 await login(page);await page.getByLabel('Search catalog',{exact:true}).fill('BQA-');
 await page.getByLabel('Catalog rows per page',{exact:true}).selectOption('12');
 await expect(page.locator('.sc-card')).toHaveCount(12);
 const first=await page.locator('.sc-card-title').allTextContents();
 await page.locator('.sc-pagination').getByRole('button',{name:'Next',exact:true}).click();
 await expect(page.locator('.sc-pagination')).toContainText('Page 2');
 await expect.poll(()=>page.locator('.sc-card-title').allTextContents()).not.toEqual(first);
 await page.locator('.sc-pagination').getByRole('button',{name:'Previous',exact:true}).click();
 await expect(page.locator('.sc-pagination')).toContainText('Page 1');
 await page.getByRole('group',{name:'Catalog type',exact:true}).getByRole('button',{name:'Subscriptions',exact:true}).click();
 await expect(page.locator('.sc-loading')).toBeHidden();
 const expected=dbRows("SELECT COUNT(*) AS n FROM srm_products WHERE product_type='subscription' AND active=1 AND sku LIKE 'BQA-%'")[0].n;
 await expect(page.locator('.sc-card')).toHaveCount(expected);
});

test('real customer subscription assignment and cancellation preserves history',async({page})=>{
 await login(page);const offering=dbRows("SELECT id FROM srm_products WHERE product_type='subscription' AND active=1 ORDER BY id LIMIT 1")[0];
 await page.goto('/crm/customer-360?customer=101');await page.getByText('Memberships & subscriptions',{exact:true}).click();
 await page.getByRole('button',{name:'Assign plan',exact:true}).click();
 const dialog=page.getByRole('dialog');await dialog.getByLabel('Plan type',{exact:true}).selectOption('subscription');
 await dialog.getByLabel('Customer plan',{exact:true}).selectOption(String(offering.id));
 const issued=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/customer-plans'&&r.request().method()==='POST');
 await dialog.getByRole('button',{name:'Assign plan',exact:true}).click();const plan=await (await issued).json();
 await page.getByRole('button',{name:'Cancel plan',exact:true}).click();
 const cancelled=page.waitForResponse(r=>r.url().includes(`/customer-plans/${plan.id}/lifecycle`)&&r.request().method()==='POST');
 await page.getByRole('dialog').getByRole('button',{name:'Cancel subscription',exact:true}).click();expect((await cancelled).status()).toBe(200);
 expect(dbRows('SELECT status FROM catalog_customer_plans WHERE id=?',[plan.id])[0].status).toBe('cancelled');
 expect(dbRows('SELECT action FROM catalog_plan_events WHERE plan_id=? ORDER BY id',[plan.id]).map((r:{action:string})=>r.action)).toEqual(['issue','cancel']);
 await page.getByRole('button',{name:'History',exact:true}).click();await page.screenshot({path:resolve(output,'subscription-cancellation-history.png'),fullPage:true});
});

test('real Active Plans excludes cancelled plans while History preserves them',async({page})=>{
 await login(page);const cancelled=dbRows("SELECT number FROM catalog_customer_plans WHERE customer_id=101 AND status='cancelled' ORDER BY id DESC LIMIT 1")[0];
 expect(cancelled).toBeTruthy();await page.goto('/crm/customer-360?customer=101');
 await page.getByText('Memberships & subscriptions',{exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Loading customer plans'})).toHaveCount(0);
 await expect(page.locator('.r360-work-item').filter({hasText:cancelled.number})).toHaveCount(0);
 await page.getByRole('button',{name:'History',exact:true}).click();
 await expect(page.locator('.r360-work-item').filter({hasText:cancelled.number})).toBeVisible();
});

for(const [label,path] of [
 ['appointments','/srm/appointments'],['service scheduling','/srm/service-scheduling'],
 ['HRMS employee benefits','/hrms/benefits'],['PMS delivery projects','/pms/projects'],
 ['finance invoices','/srm/invoices'],['sales reporting','/srm/reports'],
])test(`real cross-module regression: ${label}`,async({page})=>{
 await login(page);await page.goto(path);
 if(label==='appointments'){
  await expect(page.getByRole('status').filter({hasText:'Select one branch to use industry operations.'})).toBeVisible();
  await page.locator('select[aria-label="Current branch"]:visible').first().selectOption('1');
  await page.getByRole('dialog').getByRole('button',{name:'Switch branch',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Select one branch to use industry operations.'})).toHaveCount(0);
  await expect(page.getByRole('status').filter({hasText:'Loading operations'})).toHaveCount(0);
 }
 await expect(page.locator('main').first()).toBeVisible();
 await expect(page.getByText('Loading workspace',{exact:false})).toHaveCount(0,{timeout:30000});
 await expect(page.locator('body')).not.toContainText(/Something went wrong|Internal Server Error|403 Access Denied/);
 await page.screenshot({path:resolve(output,`cross-module-${label.replace(/ /g,'-')}.png`),fullPage:true});
 if(label==='finance invoices'){
  const number=dbRows('SELECT invoice_number FROM srm_invoices ORDER BY id DESC LIMIT 1')[0].invoice_number;
  await expect(page.locator('body')).toContainText(number);
 }
});

test('real browser retries the same checkout without duplicate invoices, payments or plans',async({page})=>{
 await login(page);const payload=JSON.parse(readFileSync(resolve(output,'pos-paid-request.json'),'utf8'));
 const before=dbRows('SELECT (SELECT COUNT(*) FROM srm_invoices) AS invoices,(SELECT COUNT(*) FROM srm_receipts) AS receipts,(SELECT COUNT(*) FROM catalog_customer_plans) AS plans')[0];
 const replay=await page.evaluate(async payload=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  const response=await fetch('/api/v1/srm/service-checkout',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'},body:JSON.stringify(payload)});
  return {status:response.status,data:await response.json()};
 },payload);
 expect(replay.status).toBeLessThan(300);expect(replay.data.state).toBe('committed');
 const after=dbRows('SELECT (SELECT COUNT(*) FROM srm_invoices) AS invoices,(SELECT COUNT(*) FROM srm_receipts) AS receipts,(SELECT COUNT(*) FROM catalog_customer_plans) AS plans')[0];
 expect(after).toEqual(before);writeFileSync(resolve(output,'checkout-replay-database.json'),JSON.stringify({before,after,checkout_id:replay.data.id},null,2));
});

test('real unsupported bundle checkout is disclosed and cannot write a partial sale',async({page},info)=>{
 info.annotations.push({type:'expected-http',description:'503'});
 await openPOS(page);const bundle=dbRows("SELECT id,item_name,sku FROM srm_products WHERE product_type='bundle' AND active=1 ORDER BY id LIMIT 1")[0];
 await page.getByLabel('Search or scan items',{exact:true}).fill(bundle.sku);
 await expect(page.locator(`button[data-product-id="${bundle.id}"]`).first()).toBeDisabled();
 await expect(page.locator('.srm-pos-catalog')).toContainText('This bundle is not available for checkout.');
 const before=dbRows('SELECT COUNT(*) AS n FROM srm_sales_orders')[0].n;
 const status=await page.evaluate(async id=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  const response=await fetch('/api/v1/srm/sales-orders',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'},body:JSON.stringify({title:'Browser audit blocked bundle',order_number:'BQA-BLOCKED-'+crypto.randomUUID(),customer_id:101,currency:'INR',metadata_json:{source:'pos',pos_sale_id:crypto.randomUUID()},lines:[{product_id:id,quantity:1,unit_price:100}]})});
  return response.status;
 },bundle.id);
 expect(status).toBe(503);expect(dbRows('SELECT COUNT(*) AS n FROM srm_sales_orders')[0].n).toBe(before);
 await page.screenshot({path:resolve(output,'bundle-checkout-blocked.png'),fullPage:true});
});
