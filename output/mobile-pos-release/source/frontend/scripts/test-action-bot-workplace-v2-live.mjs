/** Second-batch live draft smoke test; never approves business writes. */
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
  const d=await r.json();if(!r.ok()||d.status!=='awaiting_approval')throw Error(`Unexpected draft: ${JSON.stringify(d)}`);return d;
 }
 const first=await send('Log 2 tasks for Discuss HR policy requirements; Review the regional distributor margin');
 if(first.plan.steps.length!==2||first.plan.steps.some(s=>s.tool!=='crm.create_task'))throw Error('Wrong task count/module');
 const second=await send('rename item 2 to Confirm item 1 mapping');
 if(second.plan.steps[1].payload.title!=='Confirm item 1 mapping')throw Error('Numeric rename changed supplied title');
 const priority=await send('set item 1 to critical priority');
 if(priority.plan.steps[0].payload.priority!=='Critical'||priority.plan.steps[1].payload.priority==='Critical')throw Error('Wrong priority target');
 const final=await send('move the second task to tomorrow');
 if(!final.plan.steps[1].payload.due_date||final.plan.steps[0].payload.due_date)throw Error('Wrong date target');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workplace-v2-live.png'});
 const [cancel]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${final.id}/cancel`)),page.getByRole('button',{name:'Cancel remaining work'}).click()]);
 if(!cancel.ok())throw Error('Draft cancellation failed');
 console.log('PASS: counted semicolon list, CRM routing despite HR in title, numeric rename/priority, second-only deadline, server restore and cancellation; no business writes.');
}finally{await browser.close()}
