/** Real server draft/revision smoke test. Never approves business writes. */
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
 async function send(text,count){
  await page.getByRole('textbox',{name:'Message action bot'}).fill(text);
  const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
  const d=await r.json();
  if(!r.ok()||d.status!=='awaiting_approval'||d.plan.steps.length!==count)throw Error(`Unexpected draft for ${text}: ${JSON.stringify(d)}`);
  return d;
 }
 await send('Create a project called Conversational QA launch with tasks Design, Build and Test',4);
 await send('make them all high priority',4);
 await send('rename the second one to Design prototype',4);
 const draft=await send('add another project task called QA review',5);
 if(draft.plan.steps[1].payload.title!=='Design prototype')throw Error('Ordinal revision lost');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('button',{name:'Approve these exact actions'}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/natural-conversation-live.png'});
 const [cancel]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${draft.id}/cancel`)),page.getByRole('button',{name:'Cancel remaining work'}).click()]);
 if(!cancel.ok())throw Error('Draft cancellation failed');
 console.log('PASS: natural project/tasks, priority, ordinal rename, extra task, server restore and cancellation; no business writes.');
}finally{await browser.close()}
