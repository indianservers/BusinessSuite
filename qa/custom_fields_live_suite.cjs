const q=require('./custom_fields_live.cjs');
const {expect:raw}=require('../frontend/node_modules/playwright/test');
const expect=raw.configure({timeout:45000}),assert=require('node:assert/strict'),path=require('node:path');
async function main(){
 const a=await q.auth(),b=await q.browserContext(a),p=b.page;
 const route=async url=>{await p.goto(q.origin+url);};
 const check=(name,entity,place,action)=>q.check(p,name,entity,place,action);
 const quick=async(label)=>{await route('/crm/companies');await p.getByRole('button',{name:'New',exact:true}).click();await p.getByRole('menuitem').filter({hasText:label}).first().click();};
 const group=()=>p.getByRole('dialog').last();
 try{
 const mode=process.argv[2]||'quick';
 if(mode==='quick'){
  for(const [entity,label] of [['contacts','Contact'],['companies','Company'],['leads','Add Lead'],['deals','Deal'],['tasks','Task']])await check('Global quick-add '+entity,entity,'quick_create',()=>quick(label));
 }else if(mode==='hr-pms'){
  await check('Employee full create','employees','create',()=>route('/hrms/employees/new'));
  await check('Employee quick-add','employees','quick_create',async()=>{await route('/hrms/employees');await p.getByRole('button',{name:'Quick Add Employee',exact:true}).click();});
  await check('Employee edit','employees','edit',()=>route(`/hrms/employees/${q.state.records.employee.id}?edit=true`));
  await check('Employee detail','employees','detail',()=>route(`/hrms/employees/${q.state.records.employee.id}`));
  await check('Project full create','pms_project','create',()=>route(`/pms/projects/new?workspace_id=${q.state.records.workspace.id}`));
  await check('Project edit','pms_project','edit',()=>route(`/pms/projects/${q.state.records.project.id}/edit`));
  await check('Project detail','pms_project','detail',()=>route(`/pms/projects/${q.state.records.project.id}`));
  await check('Project quick-add','pms_project','quick_create',async()=>{await route(`/pms/workspaces?workspace=${q.state.records.workspace.id}`);await p.getByRole('button',{name:'New',exact:true}).click();await p.getByRole('menuitem').filter({hasText:'Project'}).click();});
  await check('PMS task full create','pms_task','create',async()=>{await route(`/pms/tasks/new?projectId=${q.state.records.project.id}`);await p.getByRole('button',{name:'More details',exact:true}).click();});
  await check('PMS task edit','pms_task','edit',async()=>{await route(`/pms/tasks/${q.state.records.pmsTask.id}/edit`);await p.getByRole('button',{name:'More details',exact:true}).click();});
  await check('PMS task detail','pms_task','detail',()=>route(`/pms/tasks/${q.state.records.pmsTask.id}`));
  await check('PMS task inline quick-add','pms_task','quick_create',async()=>{await route(`/pms/workspaces?workspace=${q.state.records.workspace.id}&project=${q.state.records.project.id}`);const board=p.getByRole('tab',{name:'Board',exact:true});await board.click();await p.getByRole('button',{name:/Add task|Add a task|Create task/i}).first().click();});
 }else if(mode==='edit'){
  await check('Contact edit','contacts','edit',async()=>{await route('/crm/contacts');await p.getByPlaceholder('Search contacts...',{exact:true}).fill(q.state.run+' Contact');const row=p.getByRole('row').filter({hasText:q.state.run+' Contact'}).first();await row.getByRole('button',{name:/^Edit /}).click();});
  await group().getByRole('combobox',{name:q.fname('contacts','edit'),exact:true}).click();await p.getByRole('textbox',{name:'Search '+q.fname('contacts','edit'),exact:true}).fill('Aud');await expect(p.getByRole('option',{name:'Tax',exact:true})).toHaveCount(0);await p.getByRole('option',{name:'Audit',exact:true}).click();
  const saved=p.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.endsWith('/crm/contacts/'+q.state.records.contact.id));await group().getByRole('button',{name:'Save changes',exact:true}).click();assert.equal((await saved).status(),200);await expect(group()).toHaveCount(0);
  const contact=await a.api('/crm/contacts/'+q.state.records.contact.id);const values=Object.fromEntries(contact.customFields.map(f=>[f.fieldKey,f.value]));for(const [place,field] of Object.entries(q.state.fields.contacts))assert.equal(values[field.fieldKey],place==='edit'?'Audit':place==='create'?'Tax':q.state.run+' saved '+place);q.state.checks.push({name:'Contact edit preserves hidden values',status:'pass'});q.persist();
  await check('Company edit','companies','edit',async()=>{await route('/crm/companies');const search=p.getByPlaceholder(/Search companies|Search.*company|Search records|Search all records/i).first();await search.fill(q.state.run+' Company');const row=p.getByRole('row').filter({hasText:q.state.run+' Company'}).first();await row.getByRole('button',{name:/Edit/i}).first().click();});
  await check('Deal full create','deals','create',async()=>{await route('/crm/deals');await p.getByRole('button',{name:/Add deal|New deal|Create deal/i}).first().click();});
  await check('Deal edit','deals','edit',async()=>{await route('/crm/deals/'+q.state.records.deal.id);await p.getByRole('button',{name:/Edit/i}).first().click();});
  await check('CRM task full create','tasks','create',async()=>{await route('/crm/tasks');await p.getByRole('button',{name:'New task',exact:true}).click();});
  await check('CRM task edit','tasks','edit',async()=>{await route('/crm/tasks');await p.getByPlaceholder(/Search tasks/).fill(q.state.run);const card=p.locator('article').filter({hasText:q.state.run+' CRM task'});await card.getByRole('button',{name:/Edit task/}).click();});
  await check('Quote create','quotations','create',async()=>{await route('/crm/quotes');await p.getByRole('button',{name:/Create quote|Create quotation|Add quote/i}).first().click();});
  await check('Quote builder edit','quotations','edit',()=>route('/crm/quotes/'+q.state.records.quote.id));
 }else if(mode==='additional'){
  await check('Lead drawer edit','leads','edit',async()=>{await route('/crm/leads?lead='+q.state.records.lead.id);await p.locator('summary').filter({hasText:'Lead qualification & editing'}).click();await p.getByRole('button',{name:'Edit custom fields',exact:true}).click();});
  await check('Classic lead create','leads','create',async()=>{await route('/crm/leads/classic');await p.getByRole('button',{name:/Create lead|Add lead/i}).first().click();});
  await check('Classic lead edit','leads','edit',async()=>{await route('/crm/leads/classic');await p.locator('aside').getByRole('button',{name:'Edit',exact:true}).click();});
  await check('CRM task detail','tasks','detail',async()=>{await route('/crm/tasks');await p.getByPlaceholder(/Search tasks/).fill(q.state.run);await p.getByRole('button',{name:'View task details '+q.state.run+' CRM task',exact:true}).click();});
 }else if(mode==='settings'){
  await route('/crm/record-metadata?entity=contacts');const article=p.locator('article').filter({hasText:q.fname('contacts','detail')});await article.getByRole('button',{name:'Edit',exact:true}).click();await group().getByLabel('Edit form',{exact:true}).check();await group().getByLabel('Record detail view',{exact:true}).uncheck();await group().getByRole('button',{name:'Save field',exact:true}).click();await expect(p.getByRole('dialog')).toHaveCount(0);
  const field=q.state.fields.contacts.detail;const current=(await a.api('/crm/custom-fields?entityType=contacts')).items.find(f=>f.id===field.id);assert.deepEqual(current.options.ui.places,['edit']);
  await route('/crm/contacts/'+q.state.records.contact.id);await expect(p.getByRole('heading',{name:new RegExp(q.state.run)}).first()).toBeVisible();await expect(p.getByText(q.fname('contacts','detail'),{exact:true})).toHaveCount(0);
  const detail=await a.api('/crm/contacts/'+q.state.records.contact.id);assert.equal(detail.customFields.find(f=>f.id===field.id).value,q.state.run+' saved detail');
  await a.api('/crm/custom-fields/'+field.id,'PATCH',{options:field.options});
  q.state.checks.push({name:'Settings UI changes placement without deleting stored value',status:'pass'});q.persist();
 }
 await p.screenshot({path:path.join(q.output,mode+'-final.png'),fullPage:true});
 console.log('Browser errors:',JSON.stringify(b.errors));assert.deepEqual(b.errors,[]);
 }catch(e){await p.screenshot({path:path.join(q.output,(process.argv[2]||'quick')+'-fatal.png'),fullPage:true});console.error((await p.locator('body').innerText()).slice(-3500));throw e;}finally{if(process.argv[2]==='settings'){const field=q.state.fields.contacts.detail;await a.api('/crm/custom-fields/'+field.id,'PATCH',{options:field.options});}await b.browser.close();}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
