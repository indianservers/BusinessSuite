/** Local live learning QA: read, private feedback, owner release dashboard. No activation/actions. */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
const token=process.env.ACTION_BOT_TEST_TOKEN,user=JSON.parse(process.env.ACTION_BOT_TEST_USER||'null'),platform=process.env.ACTION_BOT_PLATFORM_TOKEN;
if(!token||!user||!platform)throw Error('Supply local business and platform test sessions');
const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.addInitScript(({token,user,platform})=>{sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,user,isAuthenticated:true},version:0}));sessionStorage.setItem('indian-servers-platform-token',platform)},{token,user,platform});
 await page.goto('http://127.0.0.1:5186/crm/leads');await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByRole('button',{name:'New bot conversation'}).click();await page.getByRole('button',{name:'Expand bot workspace'}).click();
 await page.getByRole('textbox',{name:'Message action bot'}).fill('what are todays jobs');
 const [read]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
 const run=await read.json();if(run.status!=='answered')throw Error('Local read failed');
 if(run.result.local_nlp.release.job_id!==218)throw Error('Active baseline unexpectedly changed');
 await page.getByRole('button',{name:'Needs correction',exact:true}).click();await page.getByRole('textbox',{name:'Bot feedback correction'}).fill('Please clarify which module I meant. QA contact: private@example.test');
 const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(`/suite/runs/${run.id}/feedback`)),page.getByRole('button',{name:'Save feedback for review'}).click()]);
 const feedback=(await response.json()).result.feedback;
 if(!response.ok()||feedback.training_approved||!feedback.needs_review||feedback.correction.includes('private@example.test'))throw Error('Feedback privacy/review boundary failed');
 await page.getByText('Feedback saved · pending review',{exact:true}).waitFor();
 await mkdir('../.local/action-bot',{recursive:true});await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/phase4-feedback-live.png'});
 await page.goto('http://127.0.0.1:5186/platform/nlp-training');await page.getByRole('heading',{name:'NLP training',exact:true}).waitFor();
 await page.getByRole('region',{name:'Release gates for run 220'}).waitFor();
 if(!await page.getByRole('button',{name:'Activate model #220',exact:true}).isEnabled())throw Error('Verified candidate did not become reviewable');
 await page.getByText('Active model: run #218.',{exact:false}).waitFor();
 await page.screenshot({path:'../.local/action-bot/phase4-learning-admin-live.png',fullPage:true});
 console.log('PASS: active run 218 retained, private redacted feedback stored without training approval, and owner dashboard shows gated candidate 220. No model activation or business actions performed.');
}finally{await browser.close()}
