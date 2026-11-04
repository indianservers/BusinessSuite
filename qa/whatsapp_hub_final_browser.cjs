const {chromium,expect}=require('../frontend/node_modules/playwright/test');
const assert=require('node:assert/strict');
const origin=process.env.WHATSAPP_QA_ORIGIN||'http://127.0.0.1:5191';
(async()=>{const browser=await chromium.launch();try{
 const page=await browser.newPage({viewport:{width:1536,height:1050}}),errors=[],sends=[],writes=[],filters=[];
 page.setDefaultTimeout(12000);page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR:',e.stack);});page.on('dialog',d=>d.accept());
 await page.addInitScript(()=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:'mock',refreshToken:'mock',isAuthenticated:true,user:{id:1,email:'mock@example.test',role:'admin',is_superuser:true}},version:0})));
 const contact={id:1,recipient:'919999999999',name:'Alex Morgan',entityType:'contact',entityId:4,consent:'opted_in',serviceWindowOpen:true};
 const item={key:'whatsapp:1',kind:'whatsapp',id:1,name:'Alex Morgan',phone:'+919999999999',branchId:1,entityType:'contact',entityId:4,companyName:'Acme',status:'open',handoverNote:'',whatsappReadId:0,emailReadId:0,unread:1,needsMatch:false,canManage:true,lastMessage:'Please prepare a proposal',lastAt:new Date().toISOString()};
 const business={linked:true,record:{entity:'contacts',id:4,name:'Alex Morgan'},creation:{personId:4,companyId:5,dealId:null,canDeal:true,canQuotation:true,canInvoice:true,canTask:true},canFollowUp:true,canViewFinance:true,sections:{},followUps:[],deals:[],quotations:[],invoices:[]};
 const person={id:4,name:'Alex Morgan',full_name:'Alex Morgan',first_name:'Alex',company_id:5};
 await page.route('**/api/v1/**',async route=>{const req=route.request(),url=new URL(req.url()),path=url.pathname;let data={items:[],pages:1,total:0,fields:[]};
  if(path.endsWith('/defaults/effective'))data={values:{},modules:{},companyId:1,branchId:1};
  else if(path.endsWith('/access/me'))data={managed:false,companyId:1,grants:{},modules:[],organizations:[],memberships:[]};
  else if(path.endsWith('/status'))data={configured:true,canAdmin:true,webhookConfigured:true,connection:{businessName:'Demo business',displayNumber:'+919000000000',status:'connected'}};
  else if(path.endsWith('/engagement/inbox')){filters.push(url.search);data={items:[item],userId:1};}
  else if(path.endsWith('/conversations/whatsapp/1'))data={conversation:{...item,whatsappContact:contact},events:[{key:'wa:1',id:1,providerMessageId:'wamid.original',channel:'whatsapp',direction:'inbound',body:'Please prepare a proposal',status:'received',createdAt:new Date().toISOString()},...sends.map((s,i)=>({key:'wa:'+String(100+i),id:100+i,providerMessageId:'wamid.out'+i,channel:'whatsapp',direction:'outbound',body:s.body,status:'accepted',createdAt:new Date().toISOString(),replyTo:s.replyTo?{id:1,body:'Please prepare a proposal',direction:'inbound'}:null}))],historyLimitPerSource:300};
  else if(path.endsWith('/conversations/1/context'))data=business;
  else if(path.endsWith('/whatsapp/messages')&&req.method()==='POST'){sends.push(req.postDataJSON());data={id:100,status:'accepted',body:sends.at(-1).body,direction:'outbound',kind:'text',createdAt:new Date().toISOString()};}
  else if(path.endsWith('/matches'))data={status:'linked',candidates:[]};
  else if(path.endsWith('/assignees'))data={items:[{id:1,name:'Sam'}],pages:1};
  else if(path.endsWith('/crm/deal-workspace/permissions'))data={can_manual_probability:true};
  else if(path.endsWith('/crm/deal-workspace/pipelines'))data={items:[{id:7,name:'Sales'}],pages:1};
  else if(path.endsWith('/crm/deal-workspace/pipeline-stages'))data={items:[{id:8,pipeline_id:7,name:'New',stage_type:'open'}],pages:1};
  else if(path.endsWith('/master-data/companies/5'))data={id:5,name:'Acme'};
  else if(path.endsWith('/master-data/companies'))data={items:[{id:5,name:'Acme'}],total:1};
  else if(path.endsWith('/crm/contacts'))data={items:[person],pages:1};
  else if(path.endsWith('/crm/companies'))data={items:[{id:5,name:'Acme'}],pages:1};
  else if(path.endsWith('/crm/deals')&&req.method()==='POST'){const body=req.postDataJSON();writes.push({kind:'deal',body});data={id:70,...body};business.deals=[{id:70,name:body.name,status:'Open',amount:body.amount||0,currency:'INR',url:'/crm/deals/70'}];}
  else if(path.endsWith('/crm/quotations')&&req.method()==='POST'){const body=req.postDataJSON();writes.push({kind:'quotation',body});data={id:80,...body};business.quotations=[{id:80,name:body.quote_number,status:'Draft',amount:0,currency:'INR',url:'/crm/quotations/80'}];}
  else if(path.endsWith('/srm/invoices/manual')&&req.method()==='POST'){const body=req.postDataJSON();writes.push({kind:'invoice',body});data={id:90,invoice_number:'INV-90',status:'draft'};business.invoices=[{id:90,name:'INV-90',status:'draft',amount:100,balance:100,currency:'INR',url:'/srm/invoices/90'}];}
  else if(path.endsWith('/project-management/task-studio/projects'))data=[{id:10,name:'Delivery',project_key:'DEL',workspace_id:2,can_manage_tasks:true}];
  else if(path.endsWith('/project-management/task-studio/options'))data={people:[{id:1,name:'Sam',email:'sam@example.com'}],teams:[],batches:[],reviewers:[1],can_edit:true,can_add_existing:true,batch_reason:''};
  else if(path.endsWith('/project-management/workspaces'))data=[{id:2,name:'Delivery workspace'}];
  else if(path.endsWith('/project-management/tasks'))data={items:[],total:0};
  else if(path.endsWith('/project-management/task-studio/projects/10/tasks')&&req.method()==='POST'){const body=req.postDataJSON();writes.push({kind:'task',body});data={task:{id:1000,project_id:10,...body.task},assignment:body.assignment,can_edit:true,protected_ids:[],version:'v1'};}
  else if(path.endsWith('/project-management/task-workspace/tasks/1000/crm-links')&&req.method()==='POST'){writes.push({kind:'task-link',body:req.postDataJSON()});data={id:1,kind:'contact',record_id:4};}
  else if(path.includes('/catalog/items'))data={items:[{id:11,kind:'product',name:'CRM License',code:'CRM-1',price:100,currency:'INR'}],pages:1};
  else if(path.includes('/custom-fields'))data={items:[],fields:[],pages:1};
  else if(path.includes('/task-types'))data={types:[]};
  await route.fulfill({json:data});
 });
 await page.goto(origin+'/crm/whatsapp?conversation=1');await expect(page.getByRole('heading',{name:'Alex Morgan',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Reply',exact:true}).click();await expect(page.getByRole('button',{name:'Cancel quoted reply',exact:true})).toBeVisible();
 await page.getByLabel('Message',{exact:true}).fill('I will prepare your proposal');await page.getByRole('button',{name:'Send reply',exact:true}).click();
 await expect.poll(()=>sends.length).toBe(1);assert.equal(sends[0].replyTo,1);await expect(page.locator('.wa-quoted-message')).toContainText('Please prepare a proposal');
 console.log('Quoted reply verified');
 await page.getByRole('button',{name:'Create deal',exact:true}).click();let deal=page.getByRole('dialog',{name:'Create deal',exact:true});await expect(deal.getByRole('heading',{name:'Create deal',exact:true})).toBeVisible({timeout:20000});
 await deal.getByRole('combobox',{name:'Pipeline',exact:true}).selectOption('7');await deal.getByRole('combobox',{name:/Stage/}).selectOption('8');
 await deal.getByRole('button',{name:'Create Deal',exact:true}).click();await expect(deal).toHaveCount(0);await expect.poll(()=>writes.filter(w=>w.kind==='deal').length).toBe(1);
 assert.equal(Number(writes.find(w=>w.kind==='deal').body.contact_id||writes.find(w=>w.kind==='deal').body.contactId),4);
 console.log('Deal creation verified');
 await page.getByRole('button',{name:'Create quotation',exact:true}).click();const quote=page.getByRole('dialog',{name:'Create Quotation',exact:true});await expect(quote).toBeVisible();await quote.getByRole('button',{name:'Save',exact:true}).click();await expect(quote).toHaveCount(0);assert.equal(writes.find(w=>w.kind==='quotation').body.contact_id,4);
 console.log('Quotation creation verified');
 await page.getByRole('button',{name:'Create invoice',exact:true}).click();let dialog=page.getByRole('dialog',{name:/Create invoice/});await expect(dialog.getByLabel('Line description',{exact:true})).toBeVisible({timeout:20000});await dialog.getByLabel('Line description',{exact:true}).fill('Proposal preparation');await dialog.getByLabel('Unit price',{exact:true}).fill('100');await dialog.getByRole('button',{name:'Create Invoice',exact:true}).click();await expect(dialog).toHaveCount(0);assert.equal(writes.find(w=>w.kind==='invoice').body.customer_id,5);assert.equal(writes.find(w=>w.kind==='invoice').body.contact_id,4);
 console.log('Invoice creation verified');
 await page.getByRole('button',{name:'Create PMS task',exact:true}).click();dialog=page.getByRole('dialog',{name:/Create PMS task/});await expect(dialog.getByRole('heading',{name:'Create Task',exact:true})).toBeVisible({timeout:20000});await expect(dialog.getByRole('button',{name:'Create Task',exact:true}).first()).toBeEnabled();await dialog.getByRole('button',{name:'Create Task',exact:true}).first().click();await expect(dialog).toHaveCount(0);assert.deepEqual(writes.find(w=>w.kind==='task-link').body,{kind:'contact',record_id:4});assert.equal(writes.filter(w=>w.kind==='task').length,1);assert.ok(page.url().includes('/crm/whatsapp'));
 await page.locator('.wa-inbox-filter-box>summary').click();await page.getByLabel('CRM tag filter',{exact:true}).fill('VIP');await page.getByLabel('CRM priority filter',{exact:true}).selectOption('High');
 await page.locator('.wa-inbox-filter-box').getByText('Filter by product or service',{exact:true}).click();await page.locator('.wa-inbox-filter-box').getByRole('button',{name:/CRM License.*CRM-1/}).click();await expect.poll(()=>filters.some(value=>value.includes('offerings=')&&value.includes('tag=VIP')&&value.includes('priority=High'))).toBe(true);
 await page.screenshot({path:'docs/qa/whatsapp-hub-final-desktop.png',fullPage:true});await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.getByRole('button',{name:'Show customer details',exact:true}).click();await page.getByRole('button',{name:'Create invoice',exact:true}).click();await expect(page.getByRole('dialog',{name:/Create invoice/})).toBeVisible();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));for(const close of await page.getByRole('button',{name:'Close notification',exact:true}).all())if(await close.isVisible())await close.click();assert.ok(await page.getByRole('dialog',{name:/Create invoice/}).evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Invoice dialog content must fit');await page.screenshot({path:'docs/qa/whatsapp-hub-create-mobile.png',fullPage:true});assert.deepEqual(errors,[]);
 console.log('PASS: quoted reply payload/rendering, product/tag/priority filtering, four shared creation forms, canonical task link, staying in chat, desktop/mobile. All APIs mocked; no live sends.');
 }finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
