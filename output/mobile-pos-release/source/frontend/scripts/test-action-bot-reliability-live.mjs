/** Live UI reliability regression: unapproved drafts and a synthetic CSV only. */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
const token=process.env.ACTION_BOT_TEST_TOKEN,user=JSON.parse(process.env.ACTION_BOT_TEST_USER||'null');
if(!token||!user)throw Error('Supply an authorized local session');
const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.addInitScript(({token,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0})),{token,user});
 await page.goto('http://127.0.0.1:5186/crm/leads');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 async function send(text){
  await page.getByRole('textbox',{name:'Message action bot'}).fill(text);
  const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
  const d=await r.json();if(!r.ok()||d.status!=='awaiting_approval')throw Error(`Unexpected reply for ${text}: ${JSON.stringify(d)}`);return d;
 }
 await send('Create tasks for Review warranty, Confirm coverage');
 await page.getByRole('tab',{name:'Review & edit'}).click();
 await page.getByRole('textbox',{name:'Step 2 title',exact:true}).fill('Review revised coverage');
 await page.getByRole('textbox',{name:'Step 2 due_date',exact:true}).fill('2030-06-20');
 await page.getByRole('combobox',{name:'Step 2 priority',exact:true}).selectOption('High');
 const [revision]=await Promise.all([page.waitForResponse(r=>/\/suite\/runs\/\d+\/revise$/.test(r.url())&&r.request().method()==='POST'),page.getByRole('button',{name:'Save edits for new review'}).click()]);
 if(!revision.ok())throw Error('Inline revision failed');
 const shifted=await send('push "Review revised coverage" back by one day');
 if(shifted.plan.steps[1].payload.due_date!=='2030-06-21'||shifted.plan.steps[1].payload.priority!=='High')throw Error('Inline edits lost in conversation');
 const history=await send('what changed');
 if(history.plan.steps.length!==2)throw Error('History question erased pending draft');
 const final=await send('make them all low priority');
 if(final.plan.steps[1].payload.due_date!=='2030-06-21')throw Error('History question erased collected fields');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/reliability-live.png'});
 await page.getByRole('button',{name:'Cancel remaining work'}).click();
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await page.getByRole('tab',{name:/^Files/}).click();
 const [uploaded]=await Promise.all([page.waitForResponse(r=>/\/attachments$/.test(r.url())&&r.request().method()==='POST'),page.getByLabel('Upload bot files').setInputFiles({name:'reliability-actions.csv',mimeType:'text/csv',buffer:Buffer.from('module,title,description\nCRM,Confirm renewal,Retain agreed scope\n')})]);
 if(!uploaded.ok())throw Error('Synthetic CSV upload failed');
 await send('create tasks from uploaded spreadsheet');
 await page.getByRole('tab',{name:/^Files/}).click();
 await page.getByRole('checkbox',{name:'Use reliability-actions.csv in next request'}).uncheck();
 const edited=await send('make it high priority');
 if(edited.plan.steps[0].payload.description!=='Retain agreed scope'||edited.result.request.attachment_ids.length!==1)throw Error('Upload fields or provenance lost');
 await page.getByRole('button',{name:'Cancel remaining work'}).click();
 console.log('PASS: inline edit -> named follow-up -> history -> edit -> reload, plus CSV fields/provenance after unselecting context. No business writes.');
}finally{await browser.close()}
