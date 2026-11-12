import {test,expect} from '../frontend/node_modules/playwright/test';
import {mkdir} from 'node:fs/promises';

test('conversational agent event design saves an inactive preview and requires separate activation',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('combobox',{name:'Agent builder intelligence',exact:true}).selectOption('local');await page.getByRole('textbox',{name:'Agent builder message',exact:true}).fill('Create a CRM sales assistant that reviews opportunities when a deal changes stage');await page.getByRole('button',{name:'Prepare agent configuration',exact:true}).click();
 await expect(page.getByRole('region',{name:'Proposed agent event trigger',exact:true})).toContainText('Deal entered a pipeline stage');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/activate')).length)).toBe(0);
 await page.getByRole('button',{name:'Save this reviewed agent',exact:true}).click();const review=page.getByRole('article',{name:'Builder event intake review',exact:true});await expect(review).toContainText('Event intake · preview');await expect(review).toContainText('5 preparations per UTC day');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/activate')).length)).toBe(0);
 await review.getByRole('button',{name:'Activate reviewed agent event intake',exact:true}).click();await expect(review).toContainText('Event intake · active');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/approve')).length)).toBe(0);
 await page.getByRole('button',{name:'New agent design',exact:true}).click();await page.getByRole('combobox',{name:'Saved agent designs',exact:true}).selectOption('81');await expect(page.getByRole('article',{name:'Builder event intake review',exact:true})).toContainText('Event intake · active');
});

test('event-driven agents require exact activation and reviewed intake resume',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('textbox',{name:'Agent name',exact:true}).fill('Event review agent');await page.getByRole('textbox',{name:'Agent instructions',exact:true}).fill('Prepare reviewed customer followups.');await page.getByRole('checkbox',{name:'crm.create_task · reviewed action',exact:true}).check();await page.getByRole('button',{name:'Save agent',exact:true}).click();await page.getByRole('tab',{name:'Schedules',exact:true}).click();
 const area=page.getByRole('region',{name:'Event-driven agents',exact:true});await area.getByRole('combobox',{name:'Event trigger agent',exact:true}).selectOption('71');await area.getByRole('combobox',{name:'Event trigger source',exact:true}).selectOption('crm.deal_stage');await area.getByRole('textbox',{name:'Event trigger instructions',exact:true}).fill('Review the opportunity and prepare followups.');await area.getByLabel('Event trigger expiry',{exact:true}).fill('2027-01-01T09:00');await area.getByRole('button',{name:'Preview event trigger',exact:true}).click();
 const preview=page.getByRole('article',{name:'Event trigger preview',exact:true});await expect(preview).toContainText('Deal entered a pipeline stage');await expect(preview).toContainText('5 preparations per UTC day');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/401/activate')).length)).toBe(0);
 await preview.getByRole('button',{name:'Activate this exact event trigger',exact:true}).click();const trigger=page.getByRole('article',{name:'Event trigger 401',exact:true});await expect(trigger).toContainText('active');await trigger.getByRole('button',{name:'Pause event intake #401',exact:true}).click();await expect(trigger).toContainText('paused');await trigger.getByRole('button',{name:'Review event resume #401',exact:true}).click();await expect(page.getByRole('region',{name:'Event intake resume review',exact:true})).toContainText('skip events received while paused');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/401/resume')).length)).toBe(0);
 await page.getByRole('button',{name:'Resume this exact event intake',exact:true}).click();await trigger.getByRole('button',{name:'Cancel event intake #401',exact:true}).click();await expect(trigger).toContainText('cancelled');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/approve')).length)).toBe(0);
});

test('organization policies require exact audience review and stay separate from private memory',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Knowledge',exact:true}).click();
 const area=page.getByRole('region',{name:'Organization memory',exact:true});const text='Delivery commitments require owner review.';
 await area.getByRole('textbox',{name:'Organization memory title',exact:true}).fill('Delivery review policy');await area.getByRole('textbox',{name:'Organization memory text',exact:true}).fill(text);await area.getByRole('combobox',{name:'Organization memory module',exact:true}).selectOption('CRM');await area.getByRole('combobox',{name:'Organization memory audience',exact:true}).selectOption('members');await area.getByRole('checkbox',{name:'Policy member robot-fixture@example.com',exact:true}).check();await area.getByRole('button',{name:'Preview organization memory',exact:true}).click();
 const review=page.getByRole('article',{name:'Organization memory publication preview',exact:true});await expect(review).toContainText(text);await expect(review).toContainText('robot-fixture@example.com');expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/702/publish')).length)).toBe(0);
 await review.getByRole('button',{name:'Publish this exact organization memory',exact:true}).click();await expect(area).toContainText('active · revision 1');
 await area.getByRole('button',{name:'Policy versions #702',exact:true}).click();await expect(page.getByRole('region',{name:'Organization memory versions',exact:true})).toContainText(text);
 const knowledge=page.getByLabel('knowledge',{exact:true});await knowledge.getByText('Private agent memory',{exact:true}).click();await expect(knowledge.getByText('No active memories in this context.',{exact:true})).toBeVisible();
 await area.getByRole('button',{name:'Revoke policy #702',exact:true}).click();await expect(area).toContainText('revoked · revision 2');await area.getByText('Forget stored policy text',{exact:true}).click();await area.getByRole('button',{name:'Forget policy #702',exact:true}).click();await expect(area).toContainText('forgotten · revision 3');await expect(area).not.toContainText(text);
});

test('saved skills can prepare a test conversation without approving writes',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Skills',exact:true}).click();
 await page.getByRole('textbox',{name:'Library skill name',exact:true}).fill('Delivery test');await page.getByRole('textbox',{name:'Library skill instructions',exact:true}).fill('Prepare delivery followup drafts.');await page.getByRole('checkbox',{name:'CRM · create task · Reviewed action',exact:true}).check();await page.getByRole('button',{name:'Save library skill',exact:true}).click();
 await page.getByRole('button',{name:'Test skill #11',exact:true}).click();const panel=page.getByRole('region',{name:'Skill testing',exact:true});await expect(panel).toContainText('cannot be approved');
 await panel.getByRole('textbox',{name:'Skill test message',exact:true}).fill('Create CRM task called Delivery test');await panel.getByRole('button',{name:'Prepare skill test',exact:true}).click();await expect(page.getByRole('article',{name:'Skill test result',exact:true})).toContainText('awaiting_approval');
 await expect(panel.getByRole('link',{name:'Open test conversation and follow up',exact:true})).toHaveAttribute('href',/bot_conversation=1/);
 const commands=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')));expect(commands).toHaveLength(1);expect(commands[0].body.test_skill_id).toBe(11);expect(commands[0].body.test_skill_revision).toBe(1);
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('skill builder refines a procedure through conversation and saves only after review',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Skills',exact:true}).click();
 await page.getByRole('combobox',{name:'Skill builder intelligence',exact:true}).selectOption('local');
 await page.getByRole('textbox',{name:'Skill builder message',exact:true}).fill('Create a CRM delivery skill');await page.getByRole('button',{name:'Prepare skill configuration',exact:true}).click();
 await page.getByRole('textbox',{name:'Skill builder message',exact:true}).fill('Procedure: Check delivery dates and responsible owners.');await page.getByRole('button',{name:'Prepare skill configuration',exact:true}).click();
 const review=page.getByRole('article',{name:'Skill configuration preview',exact:true});await review.getByText('Instructions',{exact:true}).click();await expect(review).toContainText('Check delivery dates and responsible owners.');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/apply')).length)).toBe(0);
 await page.getByRole('button',{name:'Save this reviewed skill',exact:true}).click();await expect(page.getByRole('status')).toContainText('Skill saved.');await expect(page.getByRole('button',{name:'Edit skill #13',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/activate')).length)).toBe(0);
});

test('skill JSON uses a server review before saving and server export before downloading',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();await page.getByRole('tab',{name:'Skills',exact:true}).click();
 const value={format:'businesssuite-agent-skill-v1',name:'Imported delivery checks',instructions:'Review delivery dates before preparing tasks.',tools:['crm.create_task']};
 await page.getByLabel('Import agent skill',{exact:true}).setInputFiles({name:'procedure.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(value))});
 const review=page.getByRole('article',{name:'Skill import review',exact:true});await expect(review).toContainText(value.instructions);await expect(review).toContainText('crm.create_task');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/confirm')).length)).toBe(0);
 await review.getByRole('button',{name:'Import this exact skill',exact:true}).click();await expect(page.getByRole('status')).toContainText('Private skill #12 imported');
 const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Export skill #12',exact:true}).click();expect((await downloaded).suggestedFilename()).toBe('agent-skill-12.json');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/skills/12/export')).length)).toBe(1);
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/approve')).length)).toBe(0);
});

test('organization library requires publication and install reviews without starting an agent',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('textbox',{name:'Agent name',exact:true}).fill('Shared recovery helper');await page.getByRole('textbox',{name:'Agent instructions',exact:true}).fill('Prepare clear recovery followups.');await page.getByRole('textbox',{name:'Agent memory',exact:true}).fill('My private writing preference.');
 await page.getByRole('checkbox',{name:'crm.create_task · reviewed action',exact:true}).check();await page.getByRole('button',{name:'Save agent',exact:true}).click();
 await page.getByRole('combobox',{name:'Library agent source',exact:true}).selectOption('71');
 await page.getByRole('combobox',{name:'Library agent audience',exact:true}).selectOption('members');await page.getByRole('checkbox',{name:'robot-fixture@example.com',exact:true}).check();
 await page.getByRole('button',{name:'Preview agent publication',exact:true}).click();
 const review=page.getByRole('article',{name:'Shared definition publication preview',exact:true});await expect(review).toContainText('1 private memory entries');await expect(review).not.toContainText('My private writing preference.');await expect(review).toContainText('robot-fixture@example.com');await expect(page.getByRole('combobox',{name:'Library agent audience',exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/publish')).length)).toBe(0);
 await page.getByRole('button',{name:'Publish this exact definition',exact:true}).click();
 const asset=page.getByRole('article',{name:'Shared agent 901',exact:true});await asset.getByText('Review shared definition',{exact:true}).click();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/install')).length)).toBe(0);
 await asset.getByRole('button',{name:'Install private agent',exact:true}).click();await expect(page.getByRole('status')).toContainText('Private agent #971 installed');
 await asset.getByRole('button',{name:'Versions of shared agent #901',exact:true}).click();await expect(page.getByRole('region',{name:'Shared definition versions',exact:true})).toContainText('Revision 1');
 await asset.getByRole('button',{name:'Revoke shared agent #901',exact:true}).click();await expect(asset).toContainText('revoked');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/approve')).length)).toBe(0);
});

test('coordinator preserves followups and creates an inactive reviewed workflow',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Workflows',exact:true}).click();
 await page.getByRole('combobox',{name:'Coordinator intelligence',exact:true}).selectOption('local');
 await page.getByRole('textbox',{name:'Coordinator message',exact:true}).fill('Delivery coordinator: create a customer recovery task');await page.getByRole('button',{name:'Propose specialist workflow',exact:true}).click();
 await expect(page.getByRole('article',{name:'Coordinator design',exact:true})).toContainText('revision 1');
 await page.getByRole('textbox',{name:'Coordinator message',exact:true}).fill('Call it Delivery recovery');await page.getByRole('button',{name:'Propose specialist workflow',exact:true}).click();
 await expect(page.getByRole('article',{name:'Coordinator design',exact:true})).toContainText('Delivery recovery · revision 2');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/start')).length)).toBe(0);
 await page.getByRole('button',{name:'Create reviewed workflow preview',exact:true}).click();
 await expect(page.getByRole('article',{name:'Agent workflow preview',exact:true})).toContainText('Delivery recovery');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/start')).length)).toBe(0);
 await page.getByRole('button',{name:'Start this exact workflow',exact:true}).click();
 await page.getByRole('button',{name:'Review combined results #301',exact:true}).click();
 await expect(page.getByRole('region',{name:'Combined specialist results',exact:true})).toContainText('awaiting approval');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('knowledge conversation returns citations and keeps a read-only followup',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await expect(page.getByRole('textbox',{name:'Message action bot'})).toBeEnabled();
 await page.getByRole('tab',{name:'Files (0)',exact:true}).click();
 await page.getByLabel('Upload bot files',{exact:true}).setInputFiles({name:'policy.txt',mimeType:'text/plain',buffer:Buffer.from('Escalation owners review stalled commitments.')});
 await expect(page.getByRole('tab',{name:'Files (1)',exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Bot intelligence',exact:true}).selectOption('local');
 const input=page.getByRole('textbox',{name:'Message action bot'});await input.fill('Search knowledge for: escalation owners');await page.getByRole('button',{name:'Send bot message',exact:true}).click();
 await expect(page.getByRole('button',{name:'policy.txt',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'policy.txt',exact:true}).click();await expect(page.getByRole('tab',{name:'Files (1)',exact:true})).toHaveAttribute('aria-selected','true');
 await input.fill('What about stalled commitments?');await page.getByRole('button',{name:'Send bot message',exact:true}).click();
 await expect(page.getByRole('button',{name:'policy.txt',exact:true})).toHaveCount(2);
 await expect(page.getByRole('button',{name:'Approve these exact actions',exact:true})).toHaveCount(0);
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('unified workspace manages skills finds cited file excerpts and shows activity',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 for(const label of ['Chats','Agents','Skills','Tools','Connections','Knowledge','Schedules','Artifacts','Activity'])await expect(page.getByRole('tab',{name:label,exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Skills',exact:true}).click();
 await page.getByRole('textbox',{name:'Library skill name',exact:true}).fill('Delivery checks');await page.getByRole('textbox',{name:'Library skill instructions',exact:true}).fill('Review customer delivery dates before preparing tasks.');
 await page.getByRole('checkbox',{name:'CRM · create task · Reviewed action',exact:true}).check();await page.getByRole('button',{name:'Save library skill',exact:true}).click();
 await page.getByRole('button',{name:'Edit skill #11',exact:true}).click();await page.getByRole('textbox',{name:'Library skill instructions',exact:true}).fill('Review delivery dates and owners.');await page.getByRole('button',{name:'Save new skill revision',exact:true}).click();
 await page.getByRole('button',{name:'Versions of skill #11',exact:true}).click();await expect(page.getByRole('region',{name:'Skill version history',exact:true})).toContainText('Revision 1');
 await page.getByRole('tab',{name:'Tools',exact:true}).click();await page.getByRole('textbox',{name:'Search workspace tools',exact:true}).fill('CRM task');await expect(page.getByText('Create a CRM task after review.',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Connections',exact:true}).click();await expect(page.getByText('No authorized connections in this environment.',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Files (0)',exact:true}).click();await page.getByLabel('Upload bot files',{exact:true}).setInputFiles({name:'delivery.csv',mimeType:'text/csv',buffer:Buffer.from('Policy,Escalation\nDelivery,Review stalled commitments')});await expect(page.getByLabel('files',{exact:true}).getByText('delivery.csv',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Knowledge',exact:true}).click();await page.getByRole('textbox',{name:'Knowledge file query',exact:true}).fill('Escalation');await page.getByRole('button',{name:'Search authorized knowledge',exact:true}).click();await expect(page.getByText('Characters 0–',{exact:false})).toBeVisible();await page.getByRole('button',{name:'Open source file',exact:true}).click();await expect(page.getByRole('tab',{name:'Files (1)',exact:true})).toHaveAttribute('aria-selected','true');
 await page.getByRole('tab',{name:'Activity',exact:true}).click();await expect(page.getByRole('heading',{name:'Activity',exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Knowledge',exact:true}).click();
 await page.getByRole('combobox',{name:'Knowledge sources',exact:true}).selectOption('CRM');
 await page.getByRole('combobox',{name:'Knowledge matching',exact:true}).selectOption('lexical');
 await page.getByRole('textbox',{name:'Knowledge file query',exact:true}).fill('stalled commitments');
 await page.getByRole('button',{name:'Search authorized knowledge',exact:true}).click();
 await expect(page.getByRole('link',{name:'Open source record',exact:true})).toHaveAttribute('href','/crm/tasks');
 const searches=await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/workspace/search')));
 expect(searches.at(-1).body.tools).toEqual(['crm.leads','crm.deals','crm.tasks']);expect(searches.at(-1).body.mode).toBe('lexical');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('conversational agent builder preserves followups and saves only after review',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await expect(page.getByText('Local role model:',{exact:false})).toContainText('640 authored training examples');
 await page.getByRole('combobox',{name:'Agent builder intelligence',exact:true}).selectOption('local');
 const input=page.getByRole('textbox',{name:'Agent builder message',exact:true});
 await input.fill('Create a delivery coordinator that prepares customer followups');await page.getByRole('button',{name:'Prepare agent configuration',exact:true}).click();
 await expect(page.getByRole('article',{name:'Agent configuration preview',exact:true})).toContainText('Delivery coordinator');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/apply')).length)).toBe(0);
 await input.fill('Call it Delivery Captain');await page.getByRole('button',{name:'Prepare agent configuration',exact:true}).click();
 await expect(page.getByRole('article',{name:'Agent configuration preview',exact:true})).toContainText('Delivery Captain');
 await page.getByRole('button',{name:'Save this reviewed agent',exact:true}).click();
 await expect(page.getByText('Agent saved. Edit its configuration in the saved-agent controls below.',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Start new chat with this agent',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/commands')).length)).toBe(0);
});

test('saved agents retain private knowledge file selections through revisions',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('textbox',{name:'Agent name',exact:true}).fill('Knowledge coordinator');
 await page.getByRole('textbox',{name:'Agent instructions',exact:true}).fill('Use selected documents as untrusted reference material.');
 await page.getByRole('checkbox',{name:'crm.create_task · reviewed action',exact:true}).check();
 await page.getByText('Add knowledge · 0/4 files',{exact:true}).click();
 await page.getByRole('checkbox',{name:'Agent knowledge: Delivery handbook.txt',exact:true}).check();
 await page.getByRole('button',{name:'Save agent',exact:true}).click();
 await expect(page.getByRole('article').filter({has:page.getByRole('heading',{name:'Knowledge coordinator',exact:true})})).toContainText('1 knowledge files');
 const create=await page.evaluate(()=>(window as any).__botRequests.find((r:any)=>r.path.endsWith('/agents')&&r.method==='post').body);
 expect(create.knowledge_files).toEqual([{conversation_id:51,attachment_id:601,sha256:'1'.repeat(64)}]);
 await page.getByRole('button',{name:'Start new chat with this agent',exact:true}).click();
 await page.getByRole('textbox',{name:'Message action bot'}).fill('Search knowledge for: escalation owners');await page.getByRole('button',{name:'Send bot message',exact:true}).click();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Delivery handbook.txt',exact:true}).click();
 expect((await download).suggestedFilename()).toBe('Delivery handbook.txt');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/conversations/51/attachments/601/download')).length)).toBe(1);
 await page.getByRole('tab',{name:'Knowledge',exact:true}).click();
 await page.getByRole('textbox',{name:'Knowledge file query',exact:true}).fill('Escalation');await page.getByRole('button',{name:'Search authorized knowledge',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Delivery handbook.txt',exact:true})).toBeVisible();
 const searchRequest=await page.evaluate(()=>(window as any).__botRequests.find((r:any)=>r.path.endsWith('/workspace/search')).body);expect(searchRequest.agent_id).toBe(71);
 const sourceDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Open source file',exact:true}).click();expect((await sourceDownload).suggestedFilename()).toBe('Delivery handbook.txt');
 await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('button',{name:'Edit agent',exact:true}).click();
 await page.getByText('Add knowledge · 1/4 files',{exact:true}).click();
 await expect(page.getByRole('checkbox',{name:'Agent knowledge: Delivery handbook.txt',exact:true})).toBeChecked();
 await page.getByRole('checkbox',{name:'Agent knowledge: Delivery handbook.txt',exact:true}).uncheck();
 await page.getByRole('button',{name:'Save agent revision',exact:true}).click();
 await expect(page.getByRole('article').filter({has:page.getByRole('heading',{name:'Knowledge coordinator',exact:true})})).toContainText('0 knowledge files');
 const update=await page.evaluate(()=>(window as any).__botRequests.find((r:any)=>r.path.endsWith('/agents/71')&&r.method==='put').body);
 expect(update.knowledge_files).toEqual([]);expect(update.revision).toBe(1);
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('saved agents expose reviewed tools skills MCP and schedules',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Agents',exact:true}).click();
 await page.getByRole('textbox',{name:'Agent name',exact:true}).fill('Delivery coordinator');
 await page.getByRole('textbox',{name:'Agent instructions',exact:true}).fill('Prepare a reviewed customer followup.');
 await page.getByRole('checkbox',{name:'crm.create_task · reviewed action',exact:true}).check();
 await page.getByRole('button',{name:'Save agent',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Delivery coordinator',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Start new chat with this agent',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'Message action bot'})).toHaveValue('');
 await page.getByRole('tab',{name:'Schedules',exact:true}).click();
 await expect(page.getByText('No saved reminder schedules.',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Scheduled agent',exact:true}).selectOption('71');
 await page.getByRole('textbox',{name:'Scheduled agent instructions',exact:true}).fill('Prepare delivery followup tasks');
 await page.getByLabel('Agent schedule first run',{exact:true}).fill('2027-01-01T09:00');
 await page.getByLabel('Agent schedule expiry',{exact:true}).fill('2027-01-31T09:00');
 await page.getByLabel('Agent schedule frequency',{exact:true}).selectOption('custom');await page.getByLabel('Agent schedule interval',{exact:true}).fill('3');await page.getByLabel('Agent schedule interval unit',{exact:true}).selectOption('weeks');
 await page.getByRole('button',{name:'Preview scheduled agent',exact:true}).click();
 await expect(page.getByRole('article',{name:'Agent schedule preview',exact:true})).toContainText('Reads and drafts only');
 await expect(page.getByRole('article',{name:'Agent schedule preview',exact:true})).toContainText('Every 3 weeks');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/activate')).length)).toBe(0);
 await page.getByRole('button',{name:'Activate this exact schedule',exact:true}).click();
 await expect(page.getByText('Agent · active',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Pause agent schedule',exact:true}).click();await expect(page.getByText('Agent · paused',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Review resume',exact:true}).click();
 const resumeReview=page.getByRole('region',{name:'Resume agent schedule review',exact:true});await expect(resumeReview).toContainText('Proposed changes still need separate review');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/resume')).length)).toBe(0);
 await resumeReview.getByRole('button',{name:'Keep paused',exact:true}).click();await expect(resumeReview).toHaveCount(0);
 await page.getByRole('button',{name:'Review resume',exact:true}).click();await page.getByRole('button',{name:'Resume this exact schedule',exact:true}).click();await expect(page.getByText('Agent · active',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Cancel agent schedule',exact:true}).click();
 await expect(page.getByText('Agent · cancelled',{exact:true})).toBeVisible();
 await page.getByRole('tab',{name:'Workflows',exact:true}).click();
 await page.getByRole('textbox',{name:'Agent workflow name',exact:true}).fill('Delivery handoff');
 await page.getByRole('combobox',{name:'Agent planning concurrency',exact:true}).selectOption('3');
 await page.getByRole('combobox',{name:'Workflow step 1 agent',exact:true}).selectOption('71');
 await page.getByRole('textbox',{name:'Workflow step 1 instructions',exact:true}).fill('Create a CRM followup draft');
 await page.getByRole('button',{name:'Add agent step',exact:true}).click();
 await page.getByRole('combobox',{name:'Workflow step 2 agent',exact:true}).selectOption('71');
 await page.getByRole('textbox',{name:'Workflow step 2 instructions',exact:true}).fill('Prepare the next followup');
 await page.getByRole('button',{name:'Preview agent workflow',exact:true}).click();
 await expect(page.getByRole('article',{name:'Agent workflow preview',exact:true})).toContainText('After step 1');
 await expect(page.getByRole('article',{name:'Agent workflow preview',exact:true})).toContainText('At most 3 independent planning calls at once');
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/301/start')).length)).toBe(0);
 await page.getByRole('button',{name:'Start this exact workflow',exact:true}).click();
 await expect(page.getByRole('list',{name:'Delivery handoff progress',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Stop remaining workflow',exact:true}).click();
 await expect(page.getByText('Workflow #301 · cancelled',{exact:true})).toBeVisible();
});

test('scheduled conversation link restores the requested private conversation without executing it',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});
 await expect(input).toBeEnabled();await input.fill('Scheduled delivery review');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 await page.getByRole('button',{name:'New bot conversation',exact:true}).click();
 await input.fill('Second unrelated task');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('combobox',{name:'Saved bot conversations'})).toHaveValue('2');
 await page.getByRole('link',{name:'Open scheduled conversation fixture',exact:true}).click();
 await expect(page.getByRole('combobox',{name:'Saved bot conversations'})).toHaveValue('1');
 await expect(page.getByRole('textbox',{name:'Message action bot'})).toBeEnabled();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
});

test('artifact charts preview server calculations save reviewed configuration and filter snapshots',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('textbox',{name:'Message action bot'}).fill('create chart sample');await page.getByRole('button',{name:'Send bot message'}).click();await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 const preview=page.getByRole('region',{name:'Unsaved chart preview',exact:true});await expect(preview.getByRole('article',{name:'Chart unit USD',exact:true})).toContainText('Sum 300');await expect(preview.getByRole('article',{name:'Chart unit INR',exact:true})).toContainText('Sum 50');
 await page.getByRole('combobox',{name:'Step 1 chart type',exact:true}).selectOption('line');await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
 const change=await page.evaluate(()=>(window as any).__botRequests.find((r:any)=>r.path.endsWith('/revise')).body.changes[0]);expect(change.field).toBe('chart');expect(change.value.kind).toBe('line');
 await page.getByRole('button',{name:'Approve these exact actions'}).click();await page.getByRole('tab',{name:'Results',exact:true}).click();
 const analysis=page.getByRole('region',{name:'Artifact 501 data analysis',exact:true});await expect(analysis.getByRole('article',{name:'Chart unit USD',exact:true})).toContainText('Sum 300');
 await analysis.getByRole('textbox',{name:'Chart category filter',exact:true}).fill('North');await expect(analysis.getByRole('article',{name:'Chart unit USD',exact:true})).toContainText('Sum 100');
 await analysis.getByRole('combobox',{name:'Chart view type',exact:true}).selectOption('bar');await expect(analysis.locator('.recharts-bar')).not.toHaveCount(0);
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(1);
 const artifact=page.getByRole('article',{name:'Artifact 501',exact:true});for(const format of ['PDF','Excel']){const download=page.waitForEvent('download');await artifact.getByRole('button',{name:`Download ${format}`,exact:true}).click();expect((await download).suggestedFilename()).toBe(`artifact-501-v1.${format==='PDF'?'pdf':'xlsx'}`)}
});

test('private artifact templates restore exact reviews version updates and collect values in chat',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await input.fill('create artifact sample');await page.getByRole('button',{name:'Send bot message'}).click();await page.getByRole('button',{name:'Approve these exact actions'}).click();
 await expect(page.getByRole('article',{name:'Artifact 501',exact:true})).toBeVisible();await page.getByRole('tab',{name:'Artifacts',exact:true}).click();
 await page.getByRole('button',{name:'Save as template',exact:true}).click();
 await page.getByRole('textbox',{name:'Artifact template name',exact:true}).fill('Monthly customer report');
 await page.getByRole('textbox',{name:'Template artifact title',exact:true}).fill('Review for {{customer}}');await page.getByRole('textbox',{name:'Template content',exact:true}).fill('Report for {{customer}}.');
 await page.getByRole('button',{name:'Preview private template',exact:true}).click();
 await expect(page.getByRole('region',{name:'Exact artifact template review',exact:true})).toContainText('Variables: customer');
 await page.getByRole('textbox',{name:'Artifact template name',exact:true}).fill('Changed form name');await expect(page.getByRole('button',{name:'Save this exact private template',exact:true})).toBeDisabled();
 await page.getByRole('textbox',{name:'Artifact template name',exact:true}).fill('Monthly customer report');await expect(page.getByRole('button',{name:'Save this exact private template',exact:true})).toBeEnabled();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>/artifact-templates\/reviews\/\d+\/confirm$/.test(r.path)).length)).toBe(0);
 await page.getByRole('tab',{name:'Results',exact:true}).click();await page.getByRole('tab',{name:'Artifacts',exact:true}).click();
 await page.getByRole('button',{name:'Resume template review #811',exact:true}).click();
 await page.getByRole('button',{name:'Save this exact private template',exact:true}).click();
 await page.getByRole('button',{name:'Edit template #611',exact:true}).click();
 await page.getByRole('textbox',{name:'Template content',exact:true}).fill('Updated report for {{customer}}.');await page.getByRole('button',{name:'Preview private template',exact:true}).click();await page.getByRole('button',{name:'Save this exact private template',exact:true}).click();
 await page.getByRole('button',{name:'Template #611 versions',exact:true}).click();await page.getByRole('button',{name:'View template #611 revision 1',exact:true}).click();
 await expect(page.getByRole('region',{name:'Historical artifact template',exact:true})).toContainText('Report for {{customer}}.');
 await page.getByRole('button',{name:'Use template #611',exact:true}).click();await expect(input).toHaveValue('Use template #611 version 2');
 await page.getByRole('button',{name:'Send bot message'}).click();await expect(page.getByText('What value should I use for customer?',{exact:true})).toBeVisible();
 await input.fill('Acme');await page.getByRole('button',{name:'Send bot message'}).click();await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(1);
});

test('presentations show slide previews inline edits and reviewed PDF PowerPoint downloads',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('textbox',{name:'Message action bot'}).fill('create presentation sample');await page.getByRole('button',{name:'Send bot message'}).click();
 await page.getByRole('tab',{name:'Review & edit',exact:true}).click();
 const preview=page.getByRole('region',{name:'Step 1',exact:true});await expect(preview).toContainText('Scope agreed.');
 await page.getByRole('textbox',{name:'Step 1 slide 1 point 1',exact:true}).fill('Revised agreed scope.');
 await preview.getByRole('button',{name:'Next slide',exact:true}).click();await expect(preview).toContainText('Confirm dates.');
 await page.getByRole('button',{name:'Save edits for new review',exact:true}).click();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
 const change=await page.evaluate(()=>(window as any).__botRequests.find((r:any)=>/\/revise$/.test(r.path)).body.changes[0]);
 expect(change.field).toBe('slides');expect(change.value).toEqual([{title:'Overview',bullets:['Revised agreed scope.']},{title:'Next steps',bullets:['Confirm dates.']}]);
 await page.getByRole('button',{name:'Approve these exact actions'}).click();await page.getByRole('tab',{name:'Results',exact:true}).click();
 const artifact=page.getByRole('article',{name:'Artifact 501',exact:true});await expect(artifact).toContainText('Revised agreed scope.');
 for(const format of ['PDF','PowerPoint']){const download=page.waitForEvent('download');await artifact.getByRole('button',{name:`Download ${format}`,exact:true}).click();expect((await download).suggestedFilename()).toBe(`artifact-501-v1.${format==='PDF'?'pdf':'pptx'}`)}
 await expect(artifact.getByRole('button',{name:'Download Excel',exact:true})).toHaveCount(0);
});

test('artifacts use reviewed saves and conversation edits with immutable versions',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();await input.fill('create artifact sample');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__botRequests.filter((r:any)=>r.path.endsWith('/approve')).length)).toBe(0);
 await page.getByRole('button',{name:'Approve these exact actions'}).click();
 const artifact=page.getByRole('article',{name:'Artifact 501',exact:true});await expect(artifact).toContainText('Original proposal.');
 await artifact.getByRole('button',{name:'Edit through conversation'}).click();await expect(input).toHaveValue('Edit artifact #501: ');
 await input.fill('Edit artifact #501: add a timeline');await page.getByRole('button',{name:'Send bot message'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).click();
 await expect(artifact).toContainText('Original proposal. Added timeline.');
 await artifact.getByRole('combobox',{name:'Artifact 501 version'}).selectOption('1');await expect(artifact).toContainText('Original proposal.');await expect(artifact).not.toContainText('Added timeline.');
 await page.getByRole('tab',{name:'Artifacts',exact:true}).click();await expect(page.getByRole('combobox',{name:'Saved artifacts'})).toContainText('Customer proposal');
});

test('private memory controls save edit and forget on the server',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByText('Private agent memory',{exact:true}).click();
 await page.getByRole('combobox',{name:'Memory scope'}).selectOption('user');
 await page.getByRole('combobox',{name:'Memory category'}).selectOption('decision');
 await page.getByRole('textbox',{name:'Memory text'}).fill('Prefer brief summaries');
 await page.getByLabel('Memory expiry UTC',{exact:true}).fill('2030-01-01T12:00');
 await page.getByRole('button',{name:'Save memory',exact:true}).click();
 await expect(page.getByText('Prefer brief summaries',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Edit memory 1',exact:true}).click();
 await page.getByRole('textbox',{name:'Memory text'}).fill('Prefer detailed summaries');
 await page.getByRole('button',{name:'Update memory',exact:true}).click();
 await expect(page.getByText('Prefer detailed summaries',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Forget memory 1',exact:true}).click();
 await expect(page.getByText('Prefer detailed summaries',{exact:true})).toHaveCount(0);
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.find((r:any)=>r.path.endsWith('/memory')&&r.method==='post').body.level).toBe('user');
 expect(requests.find((r:any)=>r.path.endsWith('/memory')&&r.method==='post').body).toMatchObject({category:'decision',expires_at:'2030-01-01T12:00:00.000Z'});
 expect(requests.filter((r:any)=>r.path.endsWith('/memory/module/1')&&r.method==='delete')).toHaveLength(1);
 expect(requests.filter((r:any)=>r.path.endsWith('/commands')||r.path.endsWith('/approve'))).toHaveLength(0);
});

test('server default exposes separate health and saves module preferences',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const intelligence=page.getByRole('combobox',{name:'Bot intelligence'});
 await expect(intelligence).toHaveValue('preferred');
 await page.getByText('Provider health · gemini',{exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Action bot'})).toContainText('Connectivity: success · Planning: success');
 await intelligence.selectOption('local');await expect(intelligence).toHaveValue('local');
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.find((r:any)=>r.path.endsWith('/intelligence')&&r.method==='put').body).toMatchObject({provider:'local',module:'CRM'});
});

test('failed provider planning retains the request and recovers only to a reviewed draft',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 await input.fill('provider failure sample');await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByText('Your original message and selected sources are saved on the server.')).toBeVisible();
 await page.getByRole('button',{name:'Retry planning',exact:true}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.filter((r:any)=>r.path.endsWith('/retry-planning'))).toHaveLength(1);
 expect(requests.filter((r:any)=>r.path.endsWith('/approve'))).toHaveLength(0);
});

test('multiline workplace message creates a valid single-line conversation title',async({page})=>{
 await page.goto('/action-bot-qa.html');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'New bot conversation'}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await expect(input).toBeEnabled();
 const message='Create tasks:\n- Check contract\n- Review trial feedback';
 await input.fill(message);await page.getByRole('button',{name:'Send bot message'}).click();
 await expect(page.getByRole('button',{name:'Approve these exact actions'})).toBeVisible();
 const requests=await page.evaluate(()=>(window as any).__botRequests);
 expect(requests.find((r:any)=>r.path.endsWith('/conversations')&&r.method==='post').body.title).toBe('Create tasks: - Check contract - Review trial feedback');
 expect(requests.find((r:any)=>r.path.endsWith('/commands')).body.text).toBe(message);
});

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
 expect(commands[0].body.module).toBe('CRM');expect(commands[0].body.provider).toBe('preferred');
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
