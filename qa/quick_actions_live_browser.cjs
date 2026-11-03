// Start backend/scripts/serve_ux_qa.py and Vite :5200 proxied to :1562.
// No mocked business endpoints; all writes target that disposable SQLite fixture.
const {chromium, expect: baseExpect} = require('../frontend/node_modules/playwright/test');
const expect = baseExpect.configure({timeout: 30000});
const assert = require('node:assert/strict');
const origin = 'http://127.0.0.1:5200', root = 'http://127.0.0.1:1562/api/v1';
(async () => {
  const loginResponse = await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@suiteqa.example.com',password:'SuiteQA@12345'})});
  assert.equal(loginResponse.status,200); const login=await loginResponse.json();
  const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'1'};
  const api=async(path,method='GET',body)=>{const response=await fetch(root+path,{method,headers,body:body?JSON.stringify(body):undefined});const data=await response.json();assert.ok(response.ok,`${method} ${path}: ${JSON.stringify(data)}`);return data;};
  const access=await api('/access/me'), actor=await api('/auth/me'), suffix=Date.now();
  const workspace=await api('/project-management/workspaces','POST',{name:'UX browser '+suffix});
  const project=await api('/project-management/projects','POST',{name:'UX browser project',project_key:'UX'+suffix,workspace_id:workspace.id});
  const created=await api(`/project-management/task-studio/projects/${project.id}/tasks`,'POST',{task:{title:'UX browser task',task_key:'UX-'+suffix},assignment:{people:[actor.id]}});
  const taskId=created.task.id;
  const pipeline=await api('/crm/pipelines','POST',{name:'UX pipeline '+suffix});
  const stage=await api('/crm/pipeline-stages','POST',{name:'Qualified',pipeline_id:pipeline.id});
  const deal=await api('/crm/deals','POST',{name:'UX deal '+suffix,pipeline_id:pipeline.id,stage_id:stage.id,amount:100,status:'Open'});
  const quote=await api('/crm/quotes','POST',{dealId:deal.id,quoteNumber:'UX-Q-'+suffix,issueDate:'2026-11-03',expiryDate:'2026-12-03'});
  await api(`/crm/quotes/${quote.id}/lines`,'POST',{item_type:'service',name:'QA delivery',quantity:1,unit_price:100,discount_type:'amount',discount_value:0,tax_rate:0,estimated_cost:25,billing_type:'fixed'});
  await api('/fam/dashboard');const types=(await api('/fam/voucher-types')).items,ledgers=(await api('/fam/ledgers')).items;
  const voucher=await api('/fam/vouchers','POST',{voucher_type_id:types[0].id,voucher_date:'2026-11-03',reference_number:'UX-'+suffix,narration:'UX acceptance voucher',source_module:'fam',lines:[{ledger_id:ledgers[0].id,debit_amount:100,credit_amount:0},{ledger_id:ledgers[1].id,debit_amount:0,credit_amount:100}]});
  const browser=await chromium.launch();
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{id:actor.id,email:actor.email,role:'admin',is_superuser:true,access}},version:0}));},{login,actor,access});
    const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(15000);
    page.on('response',async response=>{if(response.status()>=400&&response.url().includes('/api/v1/'))console.error(response.status(),new URL(response.url()).pathname,await response.text());});
    page.on('response',async response=>{if(response.request().method()==='POST'&&response.url().includes('/actions')){const result=await response.json();console.log('ACTION',response.status(),new URL(response.url()).pathname,result.task?.status||result.detail||result.status);}});
    async function operation(group,name){const button=group.getByRole('button',{name,exact:true});if(await button.isVisible())return button.click();await group.getByRole('button',{name:'More actions',exact:true}).click();await page.getByRole('menuitem',{name,exact:true}).click();}
    if (!process.argv.includes('--follow-up-only')) {
    await page.goto(origin+`/pms/tasks/${taskId}`);
    await operation(page.getByRole('group',{name:'Task workflow actions',exact:true}),'Start Work');
    await expect.poll(async()=> (await api(`/project-management/task-workspace/tasks/${taskId}`)).task.status).toBe('In Progress').catch(async error=>{console.error('Task UI diagnostic',await page.locator('.tw-error,[role="alert"]').allTextContents(),await page.evaluate(()=>import('/src/config/runtime.ts').then(m=>m.getApiBaseUrl())));throw error;});
    await page.getByRole('button',{name:'Add Update',exact:true}).click();
    await page.locator('[contenteditable="true"]').first().fill('Verified delivery with real API persistence.');
    await page.getByLabel('Update progress',{exact:true}).fill('50');
    await page.getByRole('button',{name:'Post Update',exact:true}).click();
    await page.reload();await expect(page.locator('.tw-entry.update')).toHaveCount(1);
    await operation(page.getByRole('group',{name:'Task workflow actions',exact:true}),'Submit for Review');
    await page.getByRole('tab',{name:'Overview',exact:true}).click();
    await page.getByLabel('Task workspace sections section',{exact:true}).selectOption('review');
    await page.getByRole('button',{name:'Approve & complete',exact:true}).click();
    await expect.poll(async()=> (await api(`/project-management/task-workspace/tasks/${taskId}`)).task.status).toBe('Done');
    await page.reload();await expect(page.getByRole('button',{name:'Submit for Review',exact:true})).toHaveCount(0);
    console.log('PASS live task: start, update, reload, submit, approve, terminal actions hidden');

    await page.goto(origin+`/crm/quotes/${quote.id}/builder`);
    let actions=page.getByRole('group',{name:'Quote actions',exact:true});
    await actions.getByRole('button',{name:'Submit for approval',exact:true}).click();
    await expect.poll(async()=> (await api(`/crm/quotes/${quote.id}`)).status).toBe('Pending Approval');
    await actions.getByRole('button',{name:'Approve',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal((await api(`/crm/quotes/${quote.id}`)).status,'Pending Approval');
    await actions.getByRole('button',{name:'Approve',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Approve quote',exact:true}).click();
    await actions.getByRole('button',{name:'Send',exact:true}).click();
    await expect.poll(async()=> (await api(`/crm/quotes/${quote.id}`)).status).toBe('Sent');
    await actions.getByRole('button',{name:'Accept and convert to SRM',exact:true}).click();
    const acceptedResponse=page.waitForResponse(response=>response.url().endsWith(`/crm/quotes/${quote.id}/accept`)&&response.request().method()==='POST');
    await page.getByRole('alertdialog').getByRole('button',{name:'Accept and convert',exact:true}).click();
    assert.equal((await acceptedResponse).status(),200);
    await expect.poll(async()=> (await api(`/crm/quotes/${quote.id}`)).status).toBe('Accepted');
    assert.ok((await api(`/crm/quotes/${quote.id}`)).converted_srm_sales_order_id || (await api(`/crm/quotes/${quote.id}`)).convertedSrmSalesOrderId);
    await page.reload();await expect(actions.getByRole('button',{name:'Submit for approval',exact:true})).toHaveCount(0);
    console.log('PASS live quote: submit, cancel review, approve, send, accept and convert, reload');

    await page.goto(origin+`/fam/vouchers/${voucher.id}`);
    await page.getByLabel('Reference Number',{exact:true}).fill('EDITED-'+suffix);
    actions=page.getByRole('group',{name:'Voucher actions',exact:true});
    await actions.getByRole('button',{name:'Save draft',exact:true}).click();
    await expect.poll(async()=> (await api(`/fam/vouchers/${voucher.id}`)).reference_number).toBe('EDITED-'+suffix);
    await actions.getByRole('button',{name:'Post voucher',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal((await api(`/fam/vouchers/${voucher.id}`)).status,'draft');
    await actions.getByRole('button',{name:'Post voucher',exact:true}).click();
    await page.getByRole('alertdialog').getByRole('button',{name:'Post voucher',exact:true}).click();
    await expect.poll(async()=> (await api(`/fam/vouchers/${voucher.id}`)).status).toBe('posted');
    await operation(actions,'Reverse voucher');
    await page.getByRole('alertdialog').getByRole('button',{name:'Reverse voucher',exact:true}).click();
    await expect.poll(async()=> (await api(`/fam/vouchers/${voucher.id}`)).status).toBe('reversed');
    await page.reload();await expect(actions.getByRole('button',{name:'Post voucher',exact:true})).toHaveCount(0);
    await page.goto(origin+'/fam/integrations/srm');
    await expect(page.getByRole('button',{name:'Post SRM invoice',exact:true})).toBeDisabled();
    console.log('PASS live accounting: edit/save, cancel review, post, reverse, reload, empty posting guarded');
    }
    const leadName='UX follow-up '+suffix;
    const lead=await api('/crm/lead-management/leads','POST',{values:{full_name:leadName,owner_user_id:actor.id}});
    await page.goto(origin+'/crm/leads?search='+encodeURIComponent(leadName));
    await page.getByRole('button',{name:'Follow up',exact:true}).click();
    await expect(page.getByLabel('Follow-up type',{exact:true})).toBeHidden();
    await page.getByRole('button',{name:'Tomorrow',exact:true}).click();
    await page.getByRole('button',{name:'Save follow-up',exact:true}).click();
    await expect.poll(async()=> (await api(`/crm/lead-management/leads/${lead.id}`)).activities.filter(activity=>activity.status==='Pending').length).toBe(1);
    const activity=(await api(`/crm/lead-management/leads/${lead.id}`)).activities.find(activity=>activity.status==='Pending');
    await page.reload();
    await page.getByRole('button',{name:'Follow up',exact:true}).click();
    await page.getByRole('button',{name:'Next week',exact:true}).click();
    await page.getByLabel('Reason for rescheduling').fill('Customer requested a later call');
    await page.getByRole('button',{name:'Save follow-up',exact:true}).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    const scheduled=(await api(`/crm/lead-management/leads/${lead.id}`)).activities.filter(item=>item.status==='Pending');
    assert.equal(scheduled.length,1); assert.equal(scheduled[0].id,activity.id);
    assert.notEqual(scheduled[0].due_date,activity.due_date);
    console.log('PASS live CRM follow-up: defaults, create, reload, reschedule existing activity without duplication');
    for(const width of [390,320]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
