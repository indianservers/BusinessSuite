/** Fifth-batch real authenticated UI checks; drafts only, never approved. */
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
 async function send(text,status='awaiting_approval'){
  await page.getByRole('textbox',{name:'Message action bot'}).fill(text);
  const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
  const d=await r.json();if(!r.ok()||d.status!==status)throw Error(`Unexpected response for ${text}: ${JSON.stringify(d)}`);return d;
 }
 await send('Create a customer follow-up called Review warranty due tomorrow, then add a customer follow-up called Confirm customer entitlement due today');
 const missing=await send('set "Missing title" to high priority','needs_clarification');
 if(missing.plan.steps.length)throw Error('Missing reference exposed actions');
 const high=await send('mark "Confirm customer entitlement" high priority');
 if(high.plan.steps[1].payload.priority!=='High'||high.plan.steps[0].payload.priority==='High')throw Error('Wrong priority target');
 await send('rename "Confirm customer entitlement" to Verify item 1 reference');
 await send('move "Verify item 1 reference" to tomorrow');
 await send('clear the due date of "Verify item 1 reference"');
 const final=await send('remove "Review warranty"');
 if(final.plan.steps.length!==1||final.plan.steps[0].payload.title!=='Verify item 1 reference'||final.plan.steps[0].payload.due_date)throw Error('Named edits were not preserved');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workplace-v5-live.png'});
 await send('forget this draft','cancelled');
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await send('Create tasks for Review scope, Review scope');
 const ambiguous=await send('rename "Review scope" to Guessed target','needs_clarification');
 if(ambiguous.plan.steps.length)throw Error('Duplicate reference exposed actions');
 const numeric=await send('rename item 2 to Final scope');
 if(numeric.plan.steps[0].payload.title!=='Review scope'||numeric.plan.steps[1].payload.title!=='Final scope')throw Error('Numeric clarification changed wrong item');
 await send('forget this draft','cancelled');
 console.log('PASS: exact-title edits, missing/duplicate clarification, numeric recovery, untouched fields, server restore and cancellation. No business writes.');
}finally{await browser.close()}
