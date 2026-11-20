import {test,expect,type Page} from '../frontend/node_modules/playwright/test';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
const out=resolve('../output/inventory-live-audit');mkdirSync(out,{recursive:true});
const seedPath=resolve(out,'fixtures.json');
const reports=[['overview','Overview'],['summary','Stock summary'],['ledger','Stock ledger'],['valuation','Valuation'],['purchases','Purchases'],['sales','Sales movement'],['reorder','Low stock'],['aging','Stock ageing'],['expiry','Expiry & batches'],['adjustments','Adjustments'],['transfers','Transfers'],['dead-stock','Dead stock'],['reconciliation','Reconciliation']];
function dbRows(sql:string,params:unknown[]=[]){return JSON.parse(execFileSync(resolve('../backend/venv/Scripts/python.exe'),['-c',`import sqlite3,json,sys\nc=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);c.row_factory=sqlite3.Row\nprint(json.dumps([dict(r) for r in c.execute(sys.argv[2],json.loads(sys.argv[3]))]))`,resolve('../.local/offerings-browser-qa/audit.sqlite'),sql,JSON.stringify(params)],{encoding:'utf8'}));}
const records:{title:string;errors:string[];http:string[];console:string[]}[]=[];
test.beforeEach(async({page},info)=>{const r={title:info.title,errors:[] as string[],http:[] as string[],console:[] as string[]};records.push(r);page.on('pageerror',e=>r.errors.push(e.message));page.on('response',response=>{if(response.url().includes('/api/')&&response.status()>=400)r.http.push(`${response.status()} ${new URL(response.url()).pathname}`);});page.on('console',message=>{if(message.type()==='error')r.console.push(message.text());});});
test.afterEach(async({},info)=>{const r=records.at(-1)!;writeFileSync(resolve(out,info.title.replace(/[^a-z0-9]+/gi,'-')+'-observations.json'),JSON.stringify({...r,status:info.status},null,2));expect(r.errors).toEqual([]);expect(r.http).toEqual([]);expect(r.console).toEqual([]);});
async function login(page:Page){
 await page.goto('/login?redirect=/srm/products-services');await page.getByPlaceholder('you@company.com').fill('browser-audit@example.com');await page.getByPlaceholder('Enter your password').fill('BrowserAudit@2026');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).not.toHaveURL(/\/login/,{timeout:45000});await page.waitForFunction(()=>!location.pathname.includes('/continue')||document.querySelector('h1')?.textContent==='Choose your company');if(await page.getByRole('heading',{name:'Choose your company',exact:true}).isVisible())await page.getByRole('button',{name:/^Workflow Test Company/}).click();await page.waitForURL(url=>!url.pathname.includes('/continue'));
}
test('real inventory transactions establish 115 Finance and 120 Sales units',async({page})=>{
 await login(page);
 const fixtures=await page.evaluate(async()=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  const prefix='IQA-'+Date.now(),today=new Date().toISOString().slice(0,10);
  async function post(path:string,body:unknown){const r=await fetch('/api/v1'+path,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(path+': '+JSON.stringify(data));return data;}
  const group=await post('/fam/inventory/stock-groups',{group_code:prefix,group_name:'Inventory audit'});
  const unit=await post('/fam/inventory/units',{unit_code:prefix,unit_name:'Pieces',symbol:'pcs'});
  const warehouse=await post('/fam/inventory/warehouses',{warehouse_code:prefix,warehouse_name:'Inventory audit warehouse'});
  const item=await post('/fam/inventory/items',{sku:prefix,item_name:'Inventory audit controlled item',stock_group_id:group.id,unit_id:unit.id,default_warehouse_id:warehouse.id,purchase_rate:10,sales_rate:999,reorder_level:200,min_stock:50});
  await post('/fam/inventory/opening-stock',{opening_number:prefix,opening_date:today,stock_item_id:item.id,warehouse_id:warehouse.id,quantity:100,rate:10});
  for(const [index,kind,qin,qout] of [[1,'purchase_receipt',50,0],[2,'delivery_note',0,30],[3,'purchase_return',0,10],[4,'sales_return',5,0]] as const){const payload={movement_number:prefix+'-'+index,movement_date:today,movement_type:kind,lines:[{stock_item_id:item.id,warehouse_id:warehouse.id,quantity_in:qin,quantity_out:qout,rate:10}]};const draft=await post('/fam/inventory/stock-movements',payload);await post(`/fam/inventory/stock-movements/${draft.id}/post`,payload);}
  await post('/fam/inventory/reserve-stock',{stock_item_id:item.id,warehouse_id:warehouse.id,quantity:20,source_module:'srm',source_record_type:'audit',source_record_id:prefix});
  const transferItem=await post('/fam/inventory/items',{sku:prefix+'-T',item_name:'Finance transfer audit',stock_group_id:group.id,unit_id:unit.id,default_warehouse_id:warehouse.id,purchase_rate:10});
  const destination=await post('/fam/inventory/warehouses',{warehouse_code:prefix+'-T',warehouse_name:'Finance transfer destination'});
  await post('/fam/inventory/opening-stock',{opening_number:prefix+'-T',opening_date:today,stock_item_id:transferItem.id,warehouse_id:warehouse.id,quantity:100,rate:10});
  const transfer=await post('/fam/inventory/stock-transfers',{transfer_number:prefix+'-T',transfer_date:today,from_warehouse_id:warehouse.id,to_warehouse_id:destination.id,lines:[{stock_item_id:transferItem.id,quantity:20,rate:999}]});
  await post(`/fam/inventory/stock-transfers/${transfer.id}/post`,{});
  const sw=await post('/srm/inventory/warehouses',{warehouse_code:prefix,warehouse_name:'Sales audit warehouse'});
  const product=await post('/srm/inventory/items',{sku:prefix,item_name:'Sales inventory audit item',reorder_level:200});
  await post('/srm/inventory/opening-stock',{product_id:product.id,warehouse_id:sw.id,quantity:100,rate:10,movement_date:today});
  for(const [kind,quantity,rate] of [['purchase_receipt',50,10],['delivery_note',30,999]] as const)await post('/srm/inventory/stock-movements',{product_id:product.id,warehouse_id:sw.id,movement_type:kind,quantity,rate,movement_date:today});
  const salesTransfer=await post('/srm/inventory/items',{sku:prefix+'-ST',item_name:'Sales transfer audit'});
  const salesDestination=await post('/srm/inventory/warehouses',{warehouse_code:prefix+'-ST',warehouse_name:'Sales transfer destination'});
  await post('/srm/inventory/opening-stock',{product_id:salesTransfer.id,warehouse_id:sw.id,quantity:100,rate:10,movement_date:today});
  await post('/srm/inventory/stock-transfers',{product_id:salesTransfer.id,from_warehouse_id:sw.id,to_warehouse_id:salesDestination.id,quantity:20,rate:999,movement_date:today});
  return {fam:{product:item.id,warehouse:warehouse.id,sku:prefix,quantity:115,transferProduct:transferItem.id},srm:{product:product.id,warehouse:sw.id,sku:prefix,quantity:120,transferProduct:salesTransfer.id}};
 });
 writeFileSync(seedPath,JSON.stringify(fixtures,null,2));
 const fam=dbRows('SELECT current_quantity,average_cost FROM fam_stock_items WHERE id=?',[fixtures.fam.product])[0];expect(Number(fam.current_quantity)).toBe(115);expect(Number(fam.average_cost)).toBe(10);
 const srm=dbRows('SELECT quantity,average_cost FROM srm_inventory_balances WHERE product_id=? AND warehouse_id=?',[fixtures.srm.product,fixtures.srm.warehouse])[0];expect(Number(srm.quantity)).toBe(120);expect(Number(srm.average_cost)).toBe(10);
 const financeTransfer=dbRows("SELECT l.warehouse_id,SUM(l.quantity_in-l.quantity_out) AS quantity FROM fam_stock_movement_lines l JOIN fam_stock_movements m ON m.id=l.movement_id WHERE l.stock_item_id=? AND m.status='posted' GROUP BY l.warehouse_id",[fixtures.fam.transferProduct]);
 const salesTransfer=dbRows('SELECT warehouse_id,quantity,average_cost FROM srm_inventory_balances WHERE product_id=?',[fixtures.srm.transferProduct]);
 expect(financeTransfer.map((row:{quantity:number})=>Number(row.quantity)).sort((a:number,b:number)=>a-b)).toEqual([20,80]);
 expect(salesTransfer.map((row:{quantity:number})=>Number(row.quantity)).sort((a:number,b:number)=>a-b)).toEqual([20,80]);
 writeFileSync(resolve(out,'database-validation.json'),JSON.stringify({fam,srm,financeTransfer,salesTransfer},null,2));
});

for(const source of ['fam','srm'])test(`real ${source} all inventory reports, filters, exports and traceable quantities`,async({page})=>{
 await login(page);const fixture=JSON.parse(readFileSync(seedPath,'utf8'))[source];
 for(const [report,label] of reports){
  const loaded=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/${source}/inventory/reports`&&new URL(r.url()).searchParams.get('report')===report&&r.request().method()==='GET');
  await page.goto(`/${source}/inventory/reports?report=${report}&product_id=${report==='transfers'?fixture.transferProduct:fixture.product}`);
  const response=await loaded;expect(response.status(),await response.text()).toBe(200);const data=await response.json();
  const workspace=page.getByRole('region',{name:'Inventory report workspace'}).or(page.locator('section[aria-label="Inventory report workspace"]'));
  await expect(workspace.getByRole('button',{name:label,exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.getByText('Loading inventory report…',{exact:true})).toHaveCount(0);
  if(report==='summary'){expect(data.items[0].quantity).toBe(fixture.quantity);if(source==='fam')expect(data.items[0].available_quantity).toBe(95);await expect(workspace).toContainText(fixture.sku);}
  if(report==='valuation')expect(data.items[0].stock_value).toBe(fixture.quantity*10);
  if(report==='ledger'){expect(data.items.at(-1).closing_quantity).toBe(fixture.quantity);expect(data.items[0].opening_quantity).toBe(0);}
  if(report==='reconciliation')expect(data.total).toBe(0);
  if(report==='transfers'){expect(data.items.reduce((sum:number,row:{quantity_in:number})=>sum+Number(row.quantity_in),0)).toBe(20);expect(data.items.reduce((sum:number,row:{quantity_out:number})=>sum+Number(row.quantity_out),0)).toBe(20);}
  writeFileSync(resolve(out,`${source}-${report}-response.json`),JSON.stringify(data,null,2));
  await page.screenshot({path:resolve(out,`${source}-${report}.png`),fullPage:true});
  for(const [button,extension] of [['Export Excel','xlsx'],['Export PDF','pdf']]){const download=page.waitForEvent('download');await workspace.getByRole('button',{name:button,exact:true}).click();await (await download).saveAs(resolve(out,`${source}-${report}.${extension}`));}
 }
});

test('real inventory filter and drill-down preserve dates and server ledger pagination',async({page})=>{
 await login(page);const fixture=JSON.parse(readFileSync(seedPath,'utf8')).fam,today=new Date().toISOString().slice(0,10);
 await page.goto(`/fam/inventory/reports?report=summary&product_id=${fixture.product}&start_date=${today}&end_date=${today}`);
 await page.getByLabel('Search',{exact:true}).fill(fixture.sku);const filtered=page.waitForResponse(r=>r.url().includes('/fam/inventory/reports')&&new URL(r.url()).searchParams.get('search')===fixture.sku);await page.getByRole('button',{name:'Apply filters',exact:true}).click();await filtered;
 await page.getByRole('link',{name:'Ledger',exact:true}).first().click();await expect(page).toHaveURL(new RegExp(`start_date=${today}`));await expect(page).toHaveURL(/report=ledger/);await expect(page).toHaveURL(new RegExp(`warehouse_id=${fixture.warehouse}`));
 await page.goto(`/fam/inventory/reports?report=ledger&product_id=${fixture.product}&per_page=1&page=2`);
 await expect(page.getByRole('navigation',{name:'Inventory report pagination'})).toContainText('Page 2');
 await expect(page.getByRole('table').last()).toContainText('150');
 await page.getByRole('button',{name:'Next page',exact:true}).click();await expect(page).toHaveURL(/page=3/);
});

for(const [width,height] of [[1920,1080],[1366,768],[768,1024],[390,844]])test(`real inventory reports responsive ${width}x${height}`,async({page})=>{
 await page.setViewportSize({width,height});await login(page);const fixture=JSON.parse(readFileSync(seedPath,'utf8')).fam;
 await page.goto(`/fam/inventory/reports?report=summary&product_id=${fixture.product}`);await expect(page.getByText('Loading inventory report…',{exact:true})).toHaveCount(0);await expect(page.locator('section[aria-label="Inventory report workspace"]')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
 if(width<768){
  await page.getByLabel('Inventory report',{exact:true}).selectOption('ledger');
  await page.getByText('Report filters',{exact:true}).click();
  await page.getByLabel('Search',{exact:true}).fill(fixture.sku);
  await page.getByRole('button',{name:'Apply filters',exact:true}).click();
  await expect(page.getByText('Loading inventory report…',{exact:true})).toHaveCount(0);
  await page.getByRole('table').last().scrollIntoViewIfNeeded();
  await expect(page.getByRole('table').last()).toContainText(fixture.sku);
 }
 await page.screenshot({path:resolve(out,`responsive-${width}.png`),fullPage:true});
});

test('real batch expiry reports reconcile persisted available quantity and cost',async({page})=>{
 await login(page);const fixture=JSON.parse(readFileSync(seedPath,'utf8')).srm;
 const batch=await page.evaluate(async fixture=>{
  const token=JSON.parse(sessionStorage.getItem('hrms-auth')!).state.accessToken;
  const expiry=new Date(Date.now()+30*86400000).toISOString().slice(0,10);
  const existing=await fetch(`/api/v1/srm/inventory/batches?product_id=${fixture.product}`,{headers:{Authorization:`Bearer ${token}`,'X-Suite-Organization':'1','X-Suite-Branch':'1'}});
  const found=(await existing.json()).items?.find((row:{batch_number:string})=>row.batch_number===fixture.sku+'-BATCH');
  if(found)return found;
  const response=await fetch('/api/v1/srm/inventory/batches',{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'},body:JSON.stringify({product_id:fixture.product,warehouse_id:fixture.warehouse,batch_number:fixture.sku+'-BATCH',quantity:120,available_quantity:120,unit_cost:10,expiry_date:expiry})});
  const data=await response.json();if(!response.ok)throw Error(JSON.stringify(data));return data;
 },fixture);
 const loaded=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/srm/inventory/reports'&&new URL(r.url()).searchParams.get('report')==='expiry');
 await page.goto(`/srm/inventory/reports?report=expiry&product_id=${fixture.product}`);const data=await (await loaded).json();
 writeFileSync(resolve(out,'srm-expiry-response.json'),JSON.stringify(data,null,2));
 expect(data.items[0].quantity).toBe(120);expect(data.items[0].stock_value).toBe(1200);
 expect(data.items[0].days_until_expiry).toBe(Math.round((Date.parse(data.items[0].expiry_date)-Date.parse(data.as_of))/86400000));
 expect(Number(dbRows('SELECT available_quantity FROM srm_inventory_batches WHERE id=?',[batch.id])[0].available_quantity)).toBe(120);
 await expect(page.locator('section[aria-label="Inventory report workspace"]')).toContainText(batch.batch_number);
 await page.screenshot({path:resolve(out,'srm-expiry.png'),fullPage:true});
 for(const [button,extension] of [['Export Excel','xlsx'],['Export PDF','pdf']]){const download=page.waitForEvent('download');await page.getByRole('button',{name:button,exact:true}).click();await (await download).saveAs(resolve(out,`srm-expiry.${extension}`));}
});

test('real classic inventory report routes reuse the corrected paginated reports',async({page})=>{
 await login(page);const fixtures=JSON.parse(readFileSync(seedPath,'utf8'));
 for(const source of ['fam','srm']){
  const fixture=fixtures[source];
  const routes=[['stock-summary','summary'],['warehouse-stock','summary'],['stock-aging','aging'],['reorder-report','reorder'],['dead-stock','dead-stock'],['valuation','valuation'],['reorder-alerts','reorder']];
  if(source==='fam')routes.push([`item-ledger/${fixture.product}`,'ledger']);
  for(const [path,report] of routes){
   const loaded=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/${source}/inventory/reports`&&new URL(r.url()).searchParams.get('report')===report);
   await page.goto(`/${source}/inventory/${path}?product_id=${fixture.product}`);
   const response=await loaded;expect(response.status(),await response.text()).toBe(200);const data=await response.json();
   expect(data.report).toBe(report);expect(data.filters.product_id).toBe(fixture.product);
   await expect(page.locator('section[aria-label="Inventory report workspace"]')).toBeVisible();
   await expect(page.getByRole('navigation',{name:'Inventory report pagination'})).toBeVisible();
   if(data.items.length)await expect(page.getByRole('table').last()).toContainText(fixture.sku);
   await page.screenshot({path:resolve(out,`classic-${source}-${path.replace(/\//g,'-')}.png`),fullPage:true});
  }
 }
});
