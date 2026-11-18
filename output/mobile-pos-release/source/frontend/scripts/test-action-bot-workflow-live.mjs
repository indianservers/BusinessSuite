/** Local live smoke test: save/clarify/cancel a workflow; never approve writes. */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
const token=process.env.ACTION_BOT_TEST_TOKEN,user=JSON.parse(process.env.ACTION_BOT_TEST_USER||'null');
if(!token||!user)throw Error('Supply a local test session');
const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.addInitScript(({token,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0})),{token,user});
 await page.goto('http://127.0.0.1:5186/crm/leads');
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await page.getByRole('button',{name:'Create a CRM → PMS → HRMS workflow'}).click();
 const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
 const draft=await response.json();
 if(!response.ok()||draft.status!=='needs_clarification'||draft.result.workflow.intents.length!==3)throw Error('Workflow was not staged safely');
 await page.getByText(draft.plan.question,{exact:true}).waitFor();
 if(await page.getByRole('button',{name:'Approve these exact actions'}).count())throw Error('Incomplete workflow exposed approval');
 const chat=await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue();
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByText(draft.plan.question,{exact:true}).waitFor();
 if(await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue()!==chat)throw Error('Workflow conversation did not restore');
 await mkdir('../.local/action-bot',{recursive:true});
 await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/workflow-live-draft.png'});
 const [cancel]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${draft.id}/cancel`)),page.getByRole('button',{name:'Cancel remaining work'}).click()]);
 if(!cancel.ok()||(await cancel.json()).status!=='cancelled')throw Error('Draft cancellation failed');
 console.log('PASS: real local three-module workflow asks for its project, persists across reload, and cancels without approval or business writes.');
}finally{await browser.close()}
