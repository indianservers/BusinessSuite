/** Fourth-batch authenticated draft smoke test; never approves business writes. */
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
 const initial=await send('Create a customer follow-up called Review dealer terms due tomorrow, then add a customer follow-up called Confirm customer scope due in 2 weeks');
 const both=await send('make both high priority');
 if(both.plan.steps.some(s=>s.payload.priority!=='High'))throw Error('Both priority lost');
 await send("change item 2's priority to low");
 await send('rename item 2 as Confirm customer entitlement');
 const earlier=await send('move item 2 earlier by one week');
 if(Date.parse(initial.plan.steps[1].payload.due_date)-Date.parse(earlier.plan.steps[1].payload.due_date)!==7*86400000)throw Error('Earlier moved wrong direction');
 const forward=await send('bring item 2 forward by 2 days');
 if(Date.parse(earlier.plan.steps[1].payload.due_date)-Date.parse(forward.plan.steps[1].payload.due_date)!==2*86400000)throw Error('Forward moved wrong direction');
 const final=await send('remove the due date from item 2');
 if(final.plan.steps[1].payload.title!=='Confirm customer entitlement'||final.plan.steps[1].payload.priority!=='Low'||final.plan.steps[1].payload.due_date)throw Error('Second item edits lost');
 if(final.plan.steps[0].payload.due_date!==initial.plan.steps[0].payload.due_date||final.plan.steps[0].payload.priority!=='High')throw Error('Untouched first item changed');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workplace-v4-live.png'});
 const cancelled=await send('forget this draft','cancelled');
 if(cancelled.plan?.steps?.length)throw Error('Cancellation retained actions');
 console.log('PASS: both priority, possessive edit, rename-as, earlier/forward date shifts, clearing, exact untouched fields, server restore and cancellation. No business writes.');
}finally{await browser.close()}
