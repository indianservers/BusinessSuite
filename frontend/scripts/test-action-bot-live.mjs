/** Read-only local smoke test. Credentials/tokens arrive only through process memory. */
import {chromium} from 'playwright';
import {mkdir} from 'node:fs/promises';
const token=process.env.ACTION_BOT_TEST_TOKEN,user=JSON.parse(process.env.ACTION_BOT_TEST_USER||'null');
if(!token||!user)throw new Error('Supply a local test session');
const browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',error=>console.log('Browser error:',error.message));
 page.on('response',response=>{if(response.url().includes('/suite/commands'))console.log('Live command response:',response.status())});
 await page.addInitScript(({token,user})=>{sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:token,refreshToken:null,user,isAuthenticated:true},version:0}));if(user.access?.companyId)sessionStorage.setItem('suite-organization',String(user.access.companyId))},{token,user});
 await page.goto('http://127.0.0.1:5186/crm/leads');
 await page.getByRole('button',{name:'Open action bot',exact:true}).waitFor({timeout:30000});
 await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Message action bot'});await input.waitFor();
 async function sendRead(text){
  await input.fill(text);
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/suite/commands')&&r.request().method()==='POST'),page.getByRole('button',{name:'Send bot message'}).click()]);
  const result=await response.json();if(!response.ok()||result.status!=='answered')throw Error('Read did not return an answered run');
  await page.waitForFunction(()=>document.querySelector('textarea[aria-label="Message action bot"]')?.value==='');
 }
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await sendRead('what are todays jobs');
 try{await page.getByText('answered',{exact:true}).waitFor({timeout:30000})}catch(error){await mkdir('../.local/action-bot',{recursive:true});await page.screenshot({path:'../.local/action-bot/live-debug.png'});console.log('Bot visible:',await page.getByRole('dialog',{name:'Action bot'}).isVisible());console.log('Bot error:',await page.getByRole('dialog',{name:'Action bot'}).getByRole('alert').allTextContents());throw error}
 const error=await page.getByRole('dialog',{name:'Action bot'}).getByRole('alert').count();if(error)throw Error('Bot returned an error');
 await mkdir('../.local/action-bot',{recursive:true});await page.getByRole('dialog',{name:'Action bot'}).screenshot({path:'../.local/action-bot/live-crm.png'});
 console.log('PASS: real module login, robot launcher and local CRM read returned answered. No actions approved.');
 const saved=await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue();
 console.log('Saved conversation ID:',saved);
 if(!saved)throw Error('Conversation was not saved on server');
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByText('answered',{exact:true}).waitFor();
 const restored=await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue();console.log('Restored conversation ID:',restored);
 if(restored!==saved)throw Error('Wrong conversation restored');
 await sendRead('what changed?');
 await page.getByText('No completed action receipts are recorded in this conversation.',{exact:true}).waitFor();
 console.log('PASS: full page reload restored server transcript and accepted a follow-up.');
 await page.getByRole('button',{name:'New bot conversation'}).click();
 await sendRead('what are todays jobs');
 await page.getByText('answered',{exact:true}).waitFor();
 await page.getByRole('combobox',{name:'Saved bot conversations'}).selectOption(saved);
 await page.getByText('No completed action receipts are recorded in this conversation.',{exact:true}).waitFor();
 await page.reload();await page.getByRole('button',{name:'Open action bot',exact:true}).click();
 await page.getByText('No completed action receipts are recorded in this conversation.',{exact:true}).waitFor();
 if(await page.getByRole('combobox',{name:'Saved bot conversations'}).inputValue()!==saved)throw Error('Selected conversation was not remembered on server');
 console.log('PASS: selecting an older conversation persisted on server across reload.');
}finally{await browser.close()}
