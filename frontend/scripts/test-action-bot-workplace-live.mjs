/** Live authenticated draft QA only: no approval, business writes or messages. */
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
 const first=await send('Please create tasks:\n- Check the contract annexure\n- Review the trial feedback with high priority');
 if(first.plan.steps.length!==2||first.plan.steps.some(s=>s.payload.priority!=='High'))throw Error('Bulk metadata lost');
 const second=await send('set the second task to low priority');
 if(second.plan.steps[0].payload.priority!=='High'||second.plan.steps[1].payload.priority!=='Low')throw Error('Ordinal priority changed wrong task');
 const ambiguous=await send('make it high priority','needs_clarification');
 if(ambiguous.plan.steps.length)throw Error('Ambiguous pronoun exposed actions');
 await send('rename the last one to Review the signed contract');
 const final=await send('move them all to Friday');
 if(final.plan.steps[1].payload.title!=='Review the signed contract'||final.plan.steps.some(s=>!/^\d{4}-\d{2}-\d{2}$/.test(s.payload.due_date)))throw Error('Deadline or corrected title lost');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workplace-conversation-live.png'});
 const [cancel]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${final.id}/cancel`)),page.getByRole('button',{name:'Cancel remaining work'}).click()]);
 if(!cancel.ok())throw Error('Draft cancellation failed');
 console.log('PASS: workplace bullet list, bulk and ordinal priorities, ambiguous follow-up, rename, weekday deadline, server restore and cancellation. No business writes.');
}finally{await browser.close()}
