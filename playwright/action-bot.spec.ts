import {test,expect} from '../frontend/node_modules/playwright/test';
import {mkdir} from 'node:fs/promises';

test('workspace feedback is saved without approving a draft',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();await input.fill('Prepare feedback draft');await page.getByRole('button',{name:'Send bot message'}).click();
 await page.getByRole('button',{name:'Needs correction',exact:true}).click();
 await page.getByRole('textbox',{name:'Bot feedback correction'}).fill('I meant a project task.');
 await page.getByRole('button',{name:'Save feedback for review'}).click();
 await expect(page.getByText('Feedback saved · pending review',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.filter((r:any)=>r.path.endsWith('/approve'))).toHaveLength(0);
 expect(requests.filter((r:any)=>r.path.endsWith('/feedback'))).toHaveLength(1);
});

test('expanded workspace edits a server draft and requires a new approval',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('Prepare recovery');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('complementary',{name:'Bot workspace'})).toContainText('Prepare recovery');
 await page.getByRole('tab',{name:'Review & edit'}).click();await page.getByRole('textbox',{name:'Step 1 title',exact:true}).fill('Edited recovery task');
 await page.getByRole('combobox',{name:'Step 1 priority',exact:true}).selectOption('High');
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeDisabled();
 await page.getByRole('button',{name:'Save edits for new review'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeEnabled();
 await expect(page.getByRole('textbox',{name:'Step 1 title',exact:true})).toHaveValue('Edited recovery task');
 await page.getByRole('button',{name:'Approve these exact actions'}).click();
 await page.getByRole('tab',{name:'Results',exact:true}).click();
 await expect(page.getByRole('link',{name:'Open record in module'})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.find((r:any)=>r.path.endsWith('/revise')).body.changes[0].value).toBe('Edited recovery task');
 expect(requests.find((r:any)=>r.path.endsWith('/revise')).body.changes).toContainEqual({step:1,field:'priority',value:'High'});
 expect(requests.find((r:any)=>r.path.endsWith('/approve')).body.plan_hash).toBe('1'.repeat(64));
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/expanded-workspace.png'});
});

test('workspace uploads are conversation-scoped and previewed without automatic actions',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Files (0)'}).click();
 await expect(page.getByLabel('Upload bot files')).toBeEnabled();
 await page.getByLabel('Upload bot files').setInputFiles({name:'tasks.csv',mimeType:'text/csv',buffer:Buffer.from('module,title\nCRM,Uploaded review\n')});
 await expect(page.getByRole('tab',{name:'Files (1)'})).toBeVisible();
 await expect(page.getByRole('cell',{name:'Uploaded review',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')).length)).toBe(0);
 await page.getByRole('button',{name:'Prepare reviewed actions'}).click();
 await expect(page.getByRole('textbox',{name:'Message action bot'})).toHaveValue('create tasks from the uploaded spreadsheet');
 await page.getByRole('button',{name:'Send bot message'}).click();
 const commands=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')));
 expect(commands[0].body.attachment_ids).toEqual([1]);expect(commands[0].body.conversation_id).toBe(1);
 await page.getByRole('button',{name:'Remove',exact:true}).click();await expect(page.getByRole('tab',{name:'Files (0)'})).toBeVisible();
 await page.getByRole('button',{name:'Collapse bot workspace'}).click();
 await page.getByRole('link',{name:'/pms/tasks',exact:true}).click();
 await expect(page.getByRole('heading',{name:'/pms/tasks',exact:true})).toBeVisible();
 const restoredInput=page.getByRole('textbox',{name:'Message action bot'});await expect(restoredInput).toBeEnabled();
 await restoredInput.fill('Another request');await page.getByRole('button',{name:'Send bot message'}).click();
 const afterDelete=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')).at(-1));
 expect(afterDelete.body.attachment_ids).toEqual([]);
});

test('expanded mobile workspace switches between conversation and results within viewport',async({page})=>{
 await page.setViewportSize({width:360,height:760});await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await expect(page.getByRole('complementary',{name:'Bot workspace'})).toBeVisible();
 const box=await page.getByRole('dialog',{name:'Action bot'}).boundingBox();expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.y).toBeGreaterThanOrEqual(0);expect(box!.width).toBeLessThanOrEqual(360);expect(box!.y+box!.height).toBeLessThanOrEqual(760);
 await page.getByRole('button',{name:'Conversation',exact:true}).click();await expect(page.getByRole('textbox',{name:'Message action bot'})).toBeVisible();
 await page.getByRole('button',{name:'Workspace',exact:true}).click();await expect(page.getByRole('tab',{name:'Review & edit'})).toBeVisible();
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/expanded-mobile.png'});
});

test('workflow progress retains completed steps and resumes the reviewed remainder',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('workflow sample');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('list',{name:'Workflow steps'})).toContainText('After step 1');
 await expect(page.getByRole('list',{name:'Workflow steps'})).toContainText('blocked');
 await page.getByRole('button',{name:'Approve these exact actions'}).click();
 await expect(page.getByRole('button',{name:'Resume remaining reviewed actions'})).toBeVisible();
 await expect(page.getByRole('dialog',{name:'Action bot'})).toContainText('record #901');
 await expect(page.getByRole('list',{name:'Workflow steps'})).toContainText('3 attempts');
 await page.getByRole('button',{name:'Resume remaining reviewed actions'}).click();
 await expect(page.getByRole('dialog',{name:'Action bot'})).toContainText('record #903');
 const resumes=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>/\/runs\/\d+\/resume$/.test(r.path)));
 expect(resumes).toHaveLength(1);expect(resumes[0].body.plan_hash).toBe('0'.repeat(64));
 await expect(page.getByRole('list',{name:'Workflow steps'}).getByText('succeeded',{exact:true})).toHaveCount(3);
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workflow.png'});
});

test('saved server conversations resume after module navigation and can be switched',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('create a task');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByText('What title should I use?',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'/pms/tasks',exact:true}).click();
 await expect(page.getByRole('heading',{name:'/pms/tasks',exact:true})).toBeVisible();
 await expect(page.getByText('What title should I use?',{exact:true})).toBeVisible();
 await expect(input).toBeEnabled();
 await input.fill('Recovered title');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')));
 expect(requests[1].body.conversation_id).toBe(requests[0].body.conversation_id);
 expect(requests[1].body.parent_run_id).toBe(1);
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await input.fill('what are todays jobs');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByText('answered',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Saved bot conversations'}).selectOption('1');
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 expect(await page.evaluate(()=>Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k=>/conversation|bot-history/i.test(k)))).toEqual([]);
});

test('initial company hydration preserves replies and later company changes clear them',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('slow reply');await page.getByRole('button',{name:'Send bot message'}).click();
 await page.evaluate(()=>(window as any).__hydrateBotCompany(1));
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 await page.evaluate(()=>(window as any).__hydrateBotCompany(2));
 await expect(page.getByRole('dialog',{name:'Action bot'})).toHaveCount(0);
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toHaveCount(0);
});

test('robot is available across modules without requesting data before it opens',async({page})=>{
 await page.goto('/action-bot-qa.html');
 await expect(page.getByRole('button',{name:'Open action bot',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.length)).toBe(0);
 for(const path of ['/pms/people','/pms/tasks','/hrms/employee-directory','/srm/pos','/fam/vouchers','/power-apps/automations','/crm/leads']){
  await page.getByRole('link',{name:path,exact:true}).click();
  await expect(page.getByRole('button',{name:'Open action bot',exact:true})).toBeVisible();
 }
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toContainText('CRM');
 await page.getByRole('link',{name:'/hrms/employee-directory',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Action bot',exact:true})).toContainText('HRMS');
 await page.keyboard.press('Escape');
 await expect(page.getByRole('button',{name:'Open action bot',exact:true})).toBeFocused();
});

test('inline bot collects details, approves and shows receipts without navigating',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});
 await expect(input).toBeEnabled();await input.fill('create a task');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByText('What title should I use?',{exact:true})).toBeVisible();
 await input.fill('Review this customer request');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const commands=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')));
 expect(commands[1].body.parent_run_id).toBe(commands.length-1);
 expect(commands[0].body.module).toBe('CRM');expect(commands[0].body.provider).toBe('local');
 await expect(page.getByRole('dialog',{name:'Action bot'})).not.toContainText('hidden-signature');
 await page.getByRole('button',{name:'Approve these exact actions'}).click();
 await expect(page.getByRole('dialog',{name:'Action bot'})).toContainText('record #901');
 expect(page.url()).toContain('/action-bot-qa.html');
 await page.getByRole('button',{name:'Close action bot'}).click();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Action bot'})).toContainText('record #901');
 await mkdir('../.local/action-bot',{recursive:true});await page.screenshot({path:'../.local/action-bot/desktop.png',fullPage:true});
});

test('retries retain the request key and scope changes discard stale replies',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('retry safely');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('alert')).toContainText('Temporary failure');await expect(input).toHaveValue('retry safely');
 await page.getByRole('button',{name:'Send bot message'}).click();await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const commands=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')));
 expect(commands[0].body.request_key).toBe(commands[1].body.request_key);
 await page.getByRole('button',{name:'New bot conversation'}).click();await input.fill('slow reply');await page.getByRole('button',{name:'Send bot message'}).click();
 await page.evaluate(()=>window.dispatchEvent(new CustomEvent('suite:branch-changed')));
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();await expect(page.getByText('What can I help you do?',{exact:true})).toBeVisible();
 await expect(page.getByRole('dialog',{name:'Action bot'})).not.toContainText('slow reply');
});

test('mobile robot and chat stay within the viewport',async({page})=>{
 await page.setViewportSize({width:360,height:760});await page.goto('/action-bot-qa.html?path=%2Fpms%2Ftasks');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const box=await page.getByRole('dialog',{name:'Action bot'}).boundingBox();expect(box).not.toBeNull();expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(360);expect(box!.y).toBeGreaterThanOrEqual(0);
 await mkdir('../.local/action-bot',{recursive:true});await page.screenshot({path:'../.local/action-bot/mobile.png',fullPage:true});
});
