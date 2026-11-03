const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const assert=require('node:assert/strict');
const origin=process.env.CRM_QA_ORIGIN||'http://127.0.0.1:5173';
(async()=>{
 const module=await(await fetch(origin+'/src/components/RecordQuickPreview.tsx')).text();
 const react=module.match(/"([^"\n]*\/react\.js\?v=[^"\n]+)"/)[1],router=module.match(/"([^"\n]*\/react-router-dom\.js\?v=[^"\n]+)"/)[1];
 const main=await(await fetch(origin+'/src/main.tsx')).text(),dom=main.match(/"([^"\n]*\/react-dom_client\.js\?v=[^"\n]+)"/)[1];
 const grid=await(await fetch(origin+'/src/shared/data-grid/SharedDataGrid.tsx')).text(),query=grid.match(/"([^"\n]*\/@tanstack_react-query\.js\?v=[^"\n]+)"/)[1];
 const html=`<!doctype html><html><head><script type="module">import R from '/@react-refresh';R.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;</script></head><body><div id="root"></div><script type="module">import React from '${react}';import ReactDOM from '${dom}';import {BrowserRouter,useLocation} from '${router}';import {QueryClient,QueryClientProvider} from '${query}';import Growth from '/src/apps/crm/GrowthWorkspace.tsx';import '/src/index.css';import '/src/design-system/premium.css';function Harness(){const loc=useLocation();const mode=loc.pathname.endsWith('/greetings')?'greetings':loc.pathname.endsWith('/customer-follow-ups')?'followups':new URLSearchParams(loc.search).get('mode')||'audience';return React.createElement(Growth,{key:mode,mode});}ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(QueryClientProvider,{client:new QueryClient()},React.createElement(BrowserRouter,null,React.createElement(Harness))));</script></body></html>`;
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
 const rows=[{entity:'leads',id:1,key:'leads:1',name:'Asha lead',email:'asha@example.com',phone:'9000012345',phone_country_code:'+91',status:'New',due:null,can_edit:true,url:'/crm/leads/1'},{entity:'contacts',id:2,key:'contacts:2',name:'Ravi customer',email:'ravi@example.com',phone:'9000012346',phone_country_code:'+91',status:'Active',due:null,can_edit:true,url:'/crm/contacts/2'},{entity:'companies',id:3,key:'companies:3',name:'Acme company',email:'acme@example.com',status:'Active',due:null,can_edit:true,url:'/crm/companies/3'},{entity:'deals',id:4,key:'deals:4',name:'Implementation deal',email:'deal@example.com',status:'Open',due:null,can_edit:true,url:'/crm/deals/4'}];let pending=[];
 const catalog=Array.from({length:300},(_,i)=>({id:i+1,kind:i%2?'service':'product',name:(i%2?'Service ':'Product ')+(i+1),code:'ITEM-'+(i+1),price:100,currency:'INR',tax:0,status:'Active',pricing_options:[],description:'Offering',category:'General',version:1}));
 await page.route('**/__growth_qa*',r=>r.fulfill({contentType:'text/html',body:html}));
 await page.route('**/api/v1/**',async route=>{const req=route.request(),url=new URL(req.url()),body=req.postDataJSON();requests.push({path:url.pathname,body});
 if(url.pathname.endsWith('/catalog/items')){let items=catalog;const q=(url.searchParams.get('search')||'').toLowerCase(),kind=url.searchParams.get('kind');if(q)items=items.filter(r=>r.name.toLowerCase().includes(q)||r.code.toLowerCase().includes(q));if(kind)items=items.filter(r=>r.kind===kind);const p=Number(url.searchParams.get('page')||1),size=Number(url.searchParams.get('per_page')||12);return route.fulfill({json:{items:items.slice((p-1)*size,p*size),pages:Math.ceil(items.length/size),total:items.length,permissions:{}}});}
 if(url.pathname.endsWith('/growth/records')){let items=[...rows];const entity=url.searchParams.get('entity'),bucket=url.searchParams.get('bucket'),q=(url.searchParams.get('search')||'').toLowerCase();if(entity&&entity!=='all')items=items.filter(r=>r.entity===entity);if(q)items=items.filter(r=>r.name.toLowerCase().includes(q)||r.email.includes(q));if(url.searchParams.get('item_id'))items=items.filter(r=>r.id<=2);if(bucket==='missing')items=items.filter(r=>!r.due);if(bucket==='upcoming')items=items.filter(r=>r.due);return route.fulfill({json:{items,total:items.length,pages:1,counts:{leads:1,contacts:1,companies:1,deals:1},buckets:{today:0,overdue:0,upcoming:rows.filter(r=>r.due).length,missing:rows.filter(r=>!r.due).length}}});}
 if(url.pathname.includes('/growth/pending/'))return route.fulfill({json:{items:pending}});
 if(url.pathname.endsWith('/growth/follow-up')){const row=rows.find(r=>r.entity===body.entity&&r.id===body.record_id);row.due=body.due_at;if(body.action==='complete')pending=[];else pending=[{id:101,title:body.title,due_at:body.due_at,channel:body.channel}];return route.fulfill({json:{message:'Saved',activity_id:101}});}
 if(url.pathname.endsWith('/greetings/preview')){const items=body.recipients.map(target=>{const row=rows.find(r=>r.entity===target.entity&&r.id===target.id);const render=text=>text.replaceAll('{{name}}',row.name).replaceAll('{{sender}}','Sales team').replaceAll('{{product}}',body.product_name||'');const message=render(body.body);return {...row,body:message,subject:render(body.subject),eligible:true,reason:'',destination:body.channel==='email'?row.email:'+91'+row.phone,compose_url:body.channel==='whatsapp'?'https://wa.me/91'+row.phone+'?text='+encodeURIComponent(message):'sms:+91'+row.phone+'?body='+encodeURIComponent(message)};});return route.fulfill({json:{items,eligible:items.length,blocked:0,preview_token:'review-token',can_send:body.channel==='email',channel_note:body.channel==='email'?'Connected email provider':'Open each personalized draft. Opening a draft is not delivery.'}});}
 if(url.pathname.endsWith('/greetings/send'))return route.fulfill({json:{results:body.recipients.map(r=>({key:r.entity+':'+r.id,status:'sent',reason:''})),replayed:false}});
 return route.fulfill({json:{items:[]}});});
 await page.goto(origin+'/__growth_qa?mode=audience');
 await expect(page.getByRole('heading',{name:'Customers & pipeline by product / service',exact:true})).toBeVisible();
 await expect(page.getByRole('table')).toContainText('Implementation deal');
 await page.getByText('Filter by product or service',{exact:true}).click();
 await page.getByLabel('Search products and services',{exact:true}).fill('ITEM-257');
 await page.getByRole('button',{name:/Product 257 product/}).click();
 await expect(page).toHaveURL(/item_id=257/);
 await expect(page.getByRole('table')).not.toContainText('Implementation deal');
 await page.getByLabel('Select this page of recipients',{exact:true}).check();
 await page.getByRole('link',{name:'Greet selected',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Customer greetings',exact:true})).toBeVisible();
 await page.getByLabel('Greeting occasion',{exact:true}).selectOption('Birthday');
 await page.getByRole('button',{name:'Preview greetings for 2 selected',exact:true}).click();
 await expect(page.getByText('Happy birthday, Asha lead!',{exact:true})).toBeVisible();
 if(process.env.CRM_GROWTH_SCREENSHOT) await page.screenshot({path:process.env.CRM_GROWTH_SCREENSHOT,fullPage:true});
 await page.getByRole('button',{name:'Confirm send 2 individual emails',exact:true}).click();
 await expect(page.getByRole('button',{name:'Batch processed',exact:true})).toBeDisabled();
 assert.equal(requests.findLast(r=>r.path.endsWith('/greetings/send')).body.recipients.length,2);
 await page.getByLabel('Greeting channel',{exact:true}).selectOption('whatsapp');
 await page.getByRole('button',{name:'Preview greetings for 2 selected',exact:true}).click();
 await expect(page.getByRole('link',{name:'Open WhatsApp draft',exact:true})).toHaveCount(2);
 assert.ok((await page.getByRole('link',{name:'Open WhatsApp draft'}).first().getAttribute('href')).startsWith('https://wa.me/'));
 await expect(page.getByRole('button',{name:/Confirm send/})).toHaveCount(0);
 await page.getByRole('link',{name:'Lead & customer follow-ups',exact:true}).click();
 await page.getByRole('row').filter({hasText:'Ravi customer'}).getByRole('button',{name:'Follow up',exact:true}).click();
 const due=new Date(Date.now()+86400000*2);await page.getByLabel('Next follow-up time',{exact:true}).fill(due.toISOString().slice(0,16));
 await page.getByRole('button',{name:'Save follow-up',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByRole('status').filter({hasText:'Follow-up saved'})).toContainText('Follow-up saved');
 await page.getByRole('button',{name:'Upcoming (1)',exact:true}).click();
 await expect(page.getByRole('table')).toContainText('Ravi customer');
 await expect(page.getByRole('table')).not.toContainText('Asha lead');
 await page.getByRole('row').filter({hasText:'Ravi customer'}).getByRole('button',{name:'Follow up',exact:true}).click();
 await page.getByLabel('Follow-up action',{exact:true}).selectOption('complete');
 await page.getByLabel('Existing follow-up',{exact:true}).selectOption('101');
 await page.getByRole('button',{name:'Save outcome & next step',exact:true}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('navigation',{name:'CRM customer growth'}).first()).toBeVisible();
 const width=await page.evaluate(()=>({body:document.body.scrollWidth,viewport:innerWidth}));assert.ok(width.body<=width.viewport,'Mobile layout must not overflow the page');
 assert.deepEqual(errors,[]);
 console.log('PASS: 300-item product search; product audience filtering; transfer selected recipients; personalized email review and send; honest WhatsApp drafts; follow-up schedule/complete; navigation and mobile layout');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});


