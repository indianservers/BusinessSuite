/** Local QA: private upload, reviewed draft revision and reload. Never approves actions. */
import {chromium} from 'playwright';
import {mkdir,readFile} from 'node:fs/promises';
const token=process.env.ACTION_BOT_TEST_TOKEN,user=JSON.parse(process.env.ACTION_BOT_TEST_USER||'null');
if(!token||!user)throw Error('Supply a local test session');
const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
 page.on('pageerror',e=>console.log('Browser error:',e.message));
 await page.addInitScript(({token,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0})),{token,user});
 await page.goto('http://127.0.0.1:5186/crm/leads');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'New bot conversation'}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Files (0)'}).click();
 const csv='module,title,priority\nCRM,Local workspace QA task,High\n';
 const upload=page.getByLabel('Upload bot files');
 const [response]=await Promise.all([page.waitForResponse(r=>/\/conversations\/\d+\/attachments$/.test(r.url())&&r.request().method()==='POST'),upload.setInputFiles({name:'workspace-qa.csv',mimeType:'text/csv',buffer:Buffer.from(csv)})]);
 if(!response.ok())throw Error('CSV upload failed: '+response.status());
 await page.getByRole('cell',{name:'Local workspace QA task',exact:true}).waitFor();
 const [document]=await Promise.all([page.waitForResponse(r=>/\/conversations\/\d+\/attachments$/.test(r.url())&&r.request().method()==='POST'),upload.setInputFiles({name:'workspace-qa-notes.txt',mimeType:'text/plain',buffer:Buffer.from('Private delivery notes. Uploading does not execute anything.')})]);
 if(!document.ok())throw Error('Document upload failed');
 await page.getByRole('tab',{name:'Files (2)'}).waitFor();
 await page.getByRole('button',{name:'Prepare reviewed actions'}).click();
 const [draftResponse]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
 const draft=await draftResponse.json();if(draft.status!=='awaiting_approval')throw Error('Upload did not produce a reviewed draft');
 await page.getByRole('tab',{name:'Review & edit'}).click();
 await page.getByRole('textbox',{name:'Step 1 title',exact:true}).fill('Edited local workspace QA task');
 if(!await page.getByRole('button',{name:'Approve these exact actions'}).isDisabled())throw Error('Unsaved edits allowed approval');
 const [revisionResponse]=await Promise.all([page.waitForResponse(r=>/\/runs\/\d+\/revise$/.test(r.url())),page.getByRole('button',{name:'Save edits for new review'}).click()]);
 const revised=await revisionResponse.json();if(revised.status!=='awaiting_approval'||revised.plan_hash===draft.plan_hash)throw Error('Revision did not require fresh review');
 await page.getByRole('textbox',{name:'Step 1 title',exact:true}).waitFor();
 const saved=await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue();
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('tab',{name:'Review & edit'}).click();
 await page.getByRole('textbox',{name:'Step 1 title',exact:true}).waitFor();
 if(await page.getByRole('textbox',{name:'Step 1 title',exact:true}).inputValue()!=='Edited local workspace QA task')throw Error('Edited server draft did not restore');
 if(await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue()!==saved)throw Error('Wrong conversation restored');
 await mkdir('../.local/action-bot',{recursive:true});await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workspace-live-review.png'});
 await page.getByRole('tab',{name:'Files (2)'}).click();
 const csvCard=page.locator('.bot-file-card').filter({hasText:'workspace-qa.csv'});
 const [download]=await Promise.all([page.waitForEvent('download'),csvCard.getByRole('button',{name:'Download',exact:true}).click()]);
 if((await readFile(await download.path(),'utf8'))!==csv)throw Error('Downloaded bytes differ from original');
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workspace-live-files.png'});
 const [cancel]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${revised.id}/cancel`)),page.getByRole('button',{name:'Cancel remaining work'}).click()]);
 if(!cancel.ok())throw Error('Could not cancel QA draft');
 for(let i=0;i<2;i++){const [removed]=await Promise.all([page.waitForResponse(r=>r.request().method()==='DELETE'&&r.url().includes('/attachments/')),page.getByRole('button',{name:'Remove',exact:true}).first().click()]);if(!removed.ok())throw Error('QA file cleanup failed')}
 console.log('PASS: real server CSV/TXT uploads, table preview, draft preparation, inline revision, refresh restore, authenticated original download and cleanup. No business actions approved.');
}finally{await browser.close()}
