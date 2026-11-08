const {chromium,expect}=require('playwright/test');
const path=require('node:path');
const fs=require('node:fs');
process.chdir(path.resolve(__dirname,'..'));
(async()=>{
 const {createServer}=await import('vite');
 const server=await createServer({root:path.resolve(__dirname,'..'),server:{host:'127.0.0.1',port:0}});
 await server.listen();const port=server.httpServer.address().port;
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});let fail=true;const errors=[];const requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/v1/accounting-sync/**',route=>route.fulfill({json:route.request().url().includes('/customer-360/')?{links:[],invoices:[],payments:[],balances:[] }:{items:[]}}));
 await page.route('**/api/v1/record-360/**',async route=>{
  const url=new URL(route.request().url()),id=Number(url.pathname.match(/company\/(\d+)/)?.[1]||1);
  requests.push({path:url.pathname,cursor:url.searchParams.get("cursor"),mode:url.searchParams.get("cursor_mode")});
  let data;
  if(url.pathname.endsWith('/queue/items'))data={items:[{id:'pms_followup:7',source:'pms_followup',title:url.searchParams.get('view')==='overdue'?'Overdue follow-up':url.searchParams.get('cursor')?'Second commitment':'Confirm delivery',status:'Scheduled',url:'/pms/tasks/1?tab=followups'}],total:null,has_more:!url.searchParams.get('cursor'),next_cursor:url.searchParams.get('cursor')?null:'work-next',page:1,per_page:25,sections:{pms:'ready'}};
  else if(url.pathname.endsWith('/work'))data={items:[{id:'pms_task:1',source:'pms_task',title:'Prepare proposal',status:'To Do',url:'/pms/tasks/1'}],total:1,page:1,per_page:25,sections:{pms:'ready'}};
  else if(url.pathname.endsWith('/events')){
   if(fail){fail=false;return route.fulfill({status:500,json:{detail:'History temporarily unavailable'}});}
   const filter=url.searchParams.get('event_type');
   data=filter==='file'?{items:[],total:null,has_more:false,next_cursor:null,page:1,per_page:25,sections:{}}:{items:[{id:'note:'+url.searchParams.get('page'),type:'note',title:filter==='note'?'Filtered note':'Customer note',body:'Private saved content',occurred_at:'2026-11-04T09:00:00Z',source:'crm_note'}],total:null,has_more:!url.searchParams.get('cursor'),next_cursor:url.searchParams.get('cursor')?null:'history-next',page:1,per_page:25,sections:{}};
  } else data={id,kind:'company',name:route.request().headers()['x-suite-branch']==='2'?'Branch two customer':id===1?'Axiom Telecom':'Second customer',status:'Active',fields:{email:'customer@example.test',industry:'Telecom',external_reference:'EnterpriseReferenceWithoutSpaces01234567890123456789012345678901234567890'},projects:[],sections:{}};
  await route.fulfill({json:data});
 });
 await page.goto(`http://127.0.0.1:${port}/record-360-qa.html`);
 await expect(page.getByRole('heading',{name:'Axiom Telecom'})).toBeVisible();
 await expect(page.getByText('Prepare proposal',{exact:true})).toBeVisible();
 await expect(page.getByRole('alert')).toContainText('History temporarily unavailable');
 await page.getByRole('button',{name:'Retry',exact:true}).click();
 await expect(page.getByText('Customer note',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'History event type'}).selectOption('note');
 await expect(page.getByText('Filtered note',{exact:true})).toBeVisible();
 await page.getByLabel('Expand all').check();
 await expect(page.getByText('Private saved content',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Next',exact:true}).click();
 await expect(page.getByText('Page 2',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'History event type'}).selectOption('file');
 await expect(page.getByText('No recorded history for this filter.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Notes',exact:true}).click();
 await expect(page.getByLabel('Selected action')).toHaveText('note');
 await page.getByText('Details & related records',{exact:true}).click();
 await expect(page.getByText('Existing customer editor')).toBeVisible();
 const out=path.resolve(__dirname,'../../docs/qa/record-360');fs.mkdirSync(out,{recursive:true});
 await page.screenshot({path:path.join(out,'customer-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Switch customer'}).click();
 await expect(page.getByRole('heading',{name:'Second customer'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Axiom Telecom'})).toHaveCount(0);
 await page.evaluate(()=>{sessionStorage.setItem('suite-branch','2');window.dispatchEvent(new Event('suite:branch-changed'));});
 await expect(page.getByRole('heading',{name:'Branch two customer'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Second customer'})).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('heading',{name:'Focus',exact:true})).toBeVisible();
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
 expect(overflow).toBe(false);
 await page.screenshot({path:path.join(out,'customer-mobile.png'),fullPage:true});
 await expect(page.getByText('No accounting customer linked.',{exact:false})).toBeVisible();
 const mobileOut=path.resolve(__dirname,'../../outputs/mobile-ux');fs.mkdirSync(mobileOut,{recursive:true});
 for(const width of [320,360,375,390,414,430,480]){
  await page.setViewportSize({width,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
  await expect(page.getByText('EnterpriseReferenceWithoutSpaces01234567890123456789012345678901234567890',{exact:true})).toBeVisible();
  for(const control of await page.locator('.r360-composer button,.r360-actions button,.r360-pager button').all())if(await control.isVisible())expect(await control.evaluate(el=>el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
  await page.getByRole('combobox',{name:'History event type'}).selectOption('note');await expect(page.getByText('Filtered note',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Call',exact:true}).click();await expect(page.getByLabel('Selected action')).toHaveText('call');
 }
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(mobileOut,'record-detail-390.png'),fullPage:true});
 await page.addStyleTag({content:'.r360 *{transition:none!important;animation:none!important}'});await page.mouse.move(0,0);
 for(const width of [768,1024,1440]){
  await page.setViewportSize({width,height:1000});
  const style=page.locator('style[data-vite-dev-id$="/record-360-mobile.css"]');await expect(style).toHaveCount(1);
  const capture=()=>page.locator('.r360 *').evaluateAll(nodes=>nodes.map(el=>{if(!el.checkVisibility())return [el.tagName,'not painted'];const s=getComputedStyle(el),r=el.getBoundingClientRect();return [el.tagName,s.fontSize,s.display,s.padding,s.margin,s.color,r.width,r.height]}));
  const before=await capture();await style.evaluate(el=>el.media='not all');expect(await capture()).toEqual(before);await style.evaluate(el=>el.media='');
 }
 await page.setViewportSize({width:390,height:844});
 await page.goto(`http://127.0.0.1:${port}/record-360-qa.html?queue=1`);
 await expect(page.getByRole('heading',{name:'Tasks & Follow-ups'})).toBeVisible();
 await expect(page.getByText('Confirm delivery',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'Open',exact:true})).toHaveAttribute('href','/pms/tasks/1?tab=followups');
 await page.getByRole('button',{name:'Next',exact:true}).click();
 await expect(page.getByText('Second commitment',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Previous',exact:true}).click();
 await expect(page.getByText('Confirm delivery',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Work queue view'}).selectOption('overdue');
 await expect(page.getByText('Overdue follow-up',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Work source',exact:true}).selectOption('pms_followup');
 await page.getByRole('textbox',{name:'Search tasks and follow-ups'}).fill('delivery');
 await expect(page.getByRole('link',{name:'Schedule customer follow-up'})).toHaveAttribute('href','/pms/follow-ups?new=1');
 await page.screenshot({path:path.join(out,'pms-queue-mobile.png'),fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)).toBe(false);
 expect(requests.some(r=>r.cursor==='history-next')).toBe(true);
 expect(requests.some(r=>r.cursor==='work-next')).toBe(true);
 expect(requests.every(r=>r.path.endsWith('/work')||r.path.endsWith('/events')||r.path.endsWith('/items')?r.mode==='true':true)).toBe(true);
 await page.route('**/api/v1/crm/companies/1**',route=>route.fulfill({json:{id:1,name:'Axiom Telecom'}}));
 await page.goto(`http://127.0.0.1:${port}/record-360-qa.html?preview=1`);
 await page.getByRole('button',{name:'Preview customer',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Record 360',exact:true})).toBeVisible();
 await expect(page.getByRole('region',{name:'company 360 view'}).getByRole('heading',{name:'Branch two customer'})).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.getByRole('dialog',{name:'Record 360',exact:true})).toHaveCount(0);
 expect(errors).toEqual([]);
 console.log('Record 360 and PMS queue: source work/links, history errors/retry, filters, expansion, pagination, existing editor/actions, record switching, queue views/source/search; seven mobile widths, long values, touch targets, activity callback and unchanged tablet/desktop detail styles passed.');
 }finally{await browser.close();await server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
