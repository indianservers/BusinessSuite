/** Third workplace batch: real authenticated UI drafts, never approved. */
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
 const initial=await send('Create tasks:\n1. Review reseller terms, pricing and approval\n2. Confirm regional service coverage');
 if(initial.plan.steps.length!==2||initial.plan.steps[0].payload.title!=='Review reseller terms, pricing and approval')throw Error('Numbered list split a title');
 const missing=await send('push item 2 back by two days','needs_clarification');
 if(missing.plan.steps.length)throw Error('Missing base date exposed actions');
 const dated=await send('set the due date of item 2 to day after tomorrow');
 const shifted=await send('push item 2 back by two days');
 if(Date.parse(shifted.plan.steps[1].payload.due_date)-Date.parse(dated.plan.steps[1].payload.due_date)!==2*86400000)throw Error('Shift did not use existing deadline');
 const cleared=await send('clear the due date of item 2');
 if(cleared.plan.steps[1].payload.due_date)throw Error('Deadline was not cleared');
 const final=await send('set the priority of all tasks to low');
 if(final.plan.steps.some(s=>s.payload.priority!=='Low'))throw Error('Priority edit lost');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workplace-v3-live.png'});
 const cancelled=await send('forget this draft','cancelled');
 if(cancelled.plan?.steps?.length)throw Error('Conversational cancellation retained actions');
 console.log('PASS: literal numbered titles, missing-base clarification, exact relative shift, deadline clearing, field-first priority edit, restore and cancellation. No business writes.');
}finally{await browser.close()}
