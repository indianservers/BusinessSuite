const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch();try{
 const page=await browser.newPage({viewport:{width:1536,height:1000}}),errors=[],requests=[],sends=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:'mock',isAuthenticated:true,user:{id:1,email:'sandbox@example.test',role:'admin',is_superuser:true}},version:0})));
 const item={key:'whatsapp:1',id:1,kind:'whatsapp',name:'Audit Customer',phone:'+919999999999',branchId:1,entityType:'contact',entityId:4,status:'open',canManage:true,handoverNote:'',lastMessage:'Audit inbound',lastAt:new Date().toISOString(),unread:1,needsMatch:false,whatsappReadId:0,emailReadId:0};
 let failure=409;
 await page.route('**/api/v1/**',async route=>{const req=route.request(),u=new URL(req.url());let data={items:[]},status=200;
  if(u.pathname.endsWith('/status'))data={configured:true,canAdmin:true,webhookConfigured:true,connection:{status:'connected'}};
  else if(u.pathname.endsWith('/engagement/inbox')){requests.push(u.search);data={items:[item],serverFiltered:true,userId:1};}
  else if(u.pathname.endsWith('/conversations/whatsapp/1'))data={conversation:{...item,whatsappContact:{id:1,recipient:'919999999999',entityType:'contact',entityId:4,name:'Audit Customer',consent:'opted_in',serviceWindowOpen:true}},events:[],historyLimitPerSource:300};
  else if(u.pathname.endsWith('/conversations/1/context'))data={profile:{email:'audit@example.test',lifecycle:'Customer',tags:'Customer, VIP'},notes:[{id:7,body:'Internal audit note '+ 'long-reference-'.repeat(20),at:new Date().toISOString(),authorId:1}],linked:true,record:{entity:'contacts',id:4,name:'Audit Customer'},canFollowUp:false,canViewFinance:false,sections:{},deals:[],quotations:[],invoices:[],followUps:[]};
  else if(u.pathname.endsWith('/matches'))data={status:'linked',candidates:[]};
  else if(u.pathname.endsWith('/assignees')||u.pathname.endsWith('/crm/teams'))data={items:[{id:1,name:'Audit team member'}]};
  else if(u.pathname.endsWith('/whatsapp/messages')&&req.method()==='POST'){sends.push(req.postDataJSON());status=failure;data={detail:failure===409?'Reply window closed':'Provider outcome unknown'};}
  else if(u.pathname.includes('/messages/by-request/')){status=404;data={detail:'No recorded send found for this request'};}
  await route.fulfill({status,json:data});
 });
 await page.goto((process.env.WHATSAPP_QA_ORIGIN||'http://127.0.0.1:5191')+'/crm/whatsapp?conversation=1');await expect(page.getByRole('heading',{name:'Audit Customer',exact:true})).toBeVisible();
 await page.getByLabel('Message',{exact:true}).fill('Retain this rejected draft');await page.getByRole('button',{name:'Send reply',exact:true}).click();
 await expect(page.getByLabel('Message',{exact:true})).toBeEnabled();await expect(page.getByLabel('Message',{exact:true})).toHaveValue('Retain this rejected draft');assert.equal(sends.length,1);
 await page.getByLabel('Choose emoji',{exact:true}).click();await page.getByRole('button',{name:'Insert 👍',exact:true}).click();await expect(page.getByLabel('Message',{exact:true})).toHaveValue('Retain this rejected draft👍');
 await page.getByRole('button',{name:'Follow-ups',exact:true}).click();await expect.poll(()=>requests.some(q=>q.includes('queue=followups'))).toBe(true);
 await page.locator('.wa-inbox-filter-box>summary').click();await page.getByLabel('Inbox owner filter',{exact:true}).selectOption('1');await page.getByLabel('Inbox team filter',{exact:true}).selectOption('1');await page.getByLabel('Inbox contact type',{exact:true}).selectOption('customer');await page.getByLabel('Inbox message status',{exact:true}).selectOption('sent');await page.getByLabel('Inbox activity from',{exact:true}).fill('2026-01-01');
 await expect.poll(()=>requests.some(q=>q.includes('owner=1')&&q.includes('team=1')&&q.includes('contact_type=customer')&&q.includes('message_status=sent')&&q.includes('since='))).toBe(true);
 failure=503;await page.getByRole('button',{name:'Send reply',exact:true}).click();await expect(page.getByRole('button',{name:'Check original send',exact:true})).toBeVisible();await expect(page.getByLabel('Message',{exact:true})).toBeDisabled();assert.equal(sends.length,2);assert.notEqual(sends[0].requestId,sends[1].requestId);
 await page.reload();await expect(page.getByRole('button',{name:'Check original send',exact:true})).toBeVisible();await page.getByRole('button',{name:'Check original send',exact:true}).click();await expect.poll(()=>sends.length).toBe(3);assert.equal(sends[1].requestId,sends[2].requestId);await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Show customer details',exact:true}).click();await expect(page.getByText('Internal audit note',{exact:false})).toBeVisible();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('button',{name:'Manage linked products / services',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Manage linked products / services',exact:true});await expect(dialog).toBeVisible();assert.ok(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));await page.screenshot({path:'docs/qa/whatsapp-hub-audit-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
 console.log('PASS: conclusive rejection unlocks preserved draft; unknown outcome stays locked; reload/reconcile retains request ID; emoji and server queue/owner/team/type/status/date filters. All APIs mocked.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
