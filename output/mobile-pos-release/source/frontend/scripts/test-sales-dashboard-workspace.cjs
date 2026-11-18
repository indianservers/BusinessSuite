const {chromium,expect}=require('playwright/test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const base=process.env.SALES_QA_URL||'http://127.0.0.1:5125';
const sections=['summary','cash','collections','events','orders','quotations','targets'];
const ctx={business_date:'2026-11-08',timezone:'Asia/Kolkata',organization_id:1,sections,can_create:true,can_pos:true,can_plan:true,owners:[{id:9001,name:'Sales owner'}],teams:[{id:1,name:'Team A'}],customers:[{id:1,name:'Example customer'}],branches:[{id:1,name:'Main'}]};
function data(section,url){
 const common={section,context:{as_of:'2026-11-08T09:30:00Z',start_date:'2026-11-01',end_date:'2026-11-08',previous_start:'2026-10-24',previous_end:'2026-10-31'},metrics:{},series:[],rows:[],total_rows:1,notes:['Scoped values; cash, invoice cohorts, and planning scenarios are distinct.']};
 const row={id:'1',label:'INV-SALES-1',href:'/srm/invoices/1',currency:'USD',total:'1000.00',paid:'200.00',balance:'750.00',due:'2026-10-01'};
 if(section==='summary'){common.series=['invoiced','collected','outstanding','overdue'].map((metric,i)=>({metric,currency:'USD',amount:['1000','200','750','750'][i],previous:'100',collection_percent:metric==='collected'?20:null}));common.rows=[row];}
 if(section==='cash'){common.series=[{currency:'USD',cash_received:'250'}];common.metrics={cash_basis:'Confirmed receipts including unallocated cash',refunds:[{currency:'USD',amount:'10'}],adjustments:[{type:'credit_note',values:[{currency:'USD',amount:'50'}]}],unclassified_balance_reduction:[{currency:'USD',amount:'50'}]};}
 if(section==='collections'){common.rows=[{...row,owner_id:9001,owner:'Sales owner',next_action:'Call customer',risk_score:120,overdue_days:35,late_payment_rate:50,promised_date:'2026-11-07',promised_amount:'100',broken_promise:true}];common.series=[{currency:'USD',bucket:'31–60',amount:'750'}];common.metrics={forecast:[{currency:'USD',base:'750',promised:'100',scenario:'400',count:1,confidence:'Scenario only — limited evidence'}]};}
 if(section==='events')common.series=url.searchParams.get('period')==='today'?[{date:'2026-11-08',currency:'EUR',event_type:'credit_note',amount:'20'}]:[{date:'2026-11-01',currency:'USD',event_type:'invoice',amount:'1000'}];
 if(section==='orders'){common.series=[{status:'delivered',count:1}];common.rows=[{id:'2',label:'SO-SALES-1',href:'/srm/sales-orders/2',currency:'USD',amount:'1500',status:'delivered',inactive_days:20,stage_age_days:15,expected_delivery:'2026-11-01',unbilled:'500',blockers:['Delivered value not fully invoiced']}];}
 if(section==='quotations'){common.metrics={issued:2,converted:1,conversion_rate:50};common.rows=[{id:'3',label:'QUO-SALES-1',expiry:'2026-11-10',expiring:true,converted:false,currency:'USD',amount:100}];}
 if(section==='targets')common.rows=[{id:'4',label:'Sales owner',currency:'USD',target:'2000',achieved:'1000',attainment:50,from_date:'2026-11-01',to_date:'2026-11-30'}];
 return common;
}
(async()=>{const browser=await chromium.launch();const out=path.resolve(__dirname,'../../docs/qa/sales-dashboard-enhancements');fs.mkdirSync(out,{recursive:true});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));const requests=[];let fail=false,promise;
  await page.route('**/api/**',async route=>{const url=new URL(route.request().url());requests.push(url);
   if(url.pathname.endsWith('/dashboard-workspace/context'))return route.fulfill({json:ctx});
   if(url.pathname.endsWith('/commitment')){promise=route.request().postDataJSON();return route.fulfill({json:promise});}
   if(url.pathname.includes('/dashboard-workspace/')){const section=url.pathname.split('/').pop();if(fail&&section==='cash')return route.fulfill({status:503,json:{detail:'Test cash outage'}});return route.fulfill({json:data(section,url)});}
   if(url.pathname.endsWith('/branches/context'))return route.fulfill({json:{company_id:1,selected:1,all_branches:false,manage_access:false,branches:[{id:1,name:'Main',code:'MAIN',can_write:true}]}});return route.fulfill({json:[]});
  });
  await page.goto(base+'/sales-dashboard-qa.html');await expect(page.locator('.sales-dash-section')).toHaveCount(7);
  await expect(page.getByRole('link',{name:'Create order',exact:true})).toHaveAttribute('href','/srm/sales-orders#new-record');
  await expect(page.getByText('20% of gross invoiced in USD',{exact:true})).toBeVisible();
  await page.getByLabel('Salesperson',{exact:true}).selectOption('9001');await expect.poll(()=>requests.filter(u=>u.searchParams.get('owner_id')==='9001').length).toBeGreaterThanOrEqual(7);
  await page.reload();await expect(page.getByLabel('Salesperson',{exact:true})).toHaveValue('9001');
  await page.locator('.sales-dash-kpis article').filter({has:page.getByRole('heading',{name:'Overdue',exact:true})}).getByRole('link').click();await expect(page.locator('#sales-dashboard-details')).toContainText('INV-SALES-1');
  assert.ok(requests.some(u=>u.searchParams.get('metric')==='overdue'&&u.searchParams.get('currency')==='USD'&&u.searchParams.get('owner_id')==='9001'));
  await page.getByRole('button',{name:'Plan collection',exact:true}).first().click();await page.getByLabel('Promised payment date').fill('2026-11-10');await page.getByLabel('Promised amount',{exact:true}).fill('100');await page.getByLabel('Next collection action').fill('Call next Tuesday');
  await page.getByRole('button',{name:'Save payment promise',exact:true}).click();await expect.poll(()=>promise?.next_action).toBe('Call next Tuesday');
  await page.getByLabel('Reporting period',{exact:true}).selectOption('today');await expect(page.getByLabel('Event currency',{exact:true})).toHaveValue('EUR');await expect(page.getByLabel('Event type',{exact:true})).toHaveValue('credit_note');
  fail=true;await page.getByRole('button',{name:'Refresh dashboard',exact:true}).click();const cash=page.locator('.sales-dash-section').filter({has:page.getByRole('heading',{name:'Cash received & adjustments',exact:true})});await expect(cash).toContainText('Displayed values are stale');
  fail=false;await cash.getByRole('button',{name:'Retry section'}).click();await expect(cash).not.toContainText('Displayed values are stale');
  await page.getByLabel('Reporting period',{exact:true}).selectOption('custom');await page.getByLabel('Start date',{exact:true}).fill('2026-10-01');await page.getByLabel('End date',{exact:true}).fill('2026-11-08');await page.getByRole('button',{name:'Apply date range'}).click();await expect.poll(()=>requests.some(u=>u.searchParams.get('start_date')==='2026-10-01'&&u.searchParams.get('end_date')==='2026-11-08')).toBe(true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page overflow');assert.deepEqual(errors,[]);await page.screenshot({path:path.join(out,`sales-${width}.png`),fullPage:true});await page.close();console.log(`PASS ${width}: sections, currency percentages, URL filters, drilldowns, promise editor, chart reset, stale recovery, dates, layout`);
 }
 const page=await browser.newPage();await page.route('**/api/**',async route=>{const url=new URL(route.request().url());if(url.pathname.endsWith('/dashboard-workspace/context'))return route.fulfill({json:{...ctx,sections:['summary'],can_create:false,can_plan:false,can_pos:false}});if(url.pathname.includes('/dashboard-workspace/'))return route.fulfill({status:503,json:{detail:'Test unavailable'}});return route.fulfill({json:[]});});await page.goto(base+'/sales-dashboard-qa.html?readonly=1');await expect(page.locator('.sales-dash-kpis')).toContainText('Unavailable');await expect(page.getByRole('link',{name:'Open POS',exact:true})).toHaveCount(0);await expect(page.getByRole('link',{name:'Create order',exact:true})).toHaveCount(0);await page.close();console.log('PASS unavailable data and restricted actions');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
