/** Real browser + disposable QA API. Never saves or sends a business record. */
import {chromium} from 'playwright';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
const base=process.env.WRITING_QA_URL||'http://127.0.0.1:5192';
const out='../.local/page-ai-actions';await mkdir(out,{recursive:true});
const browser=await chromium.launch();
const results=[],errors=[];let page;
const start=Number(process.env.WRITING_QA_START_INDEX||0);
if(start){const previous=JSON.parse(await readFile(out+'/results.json','utf8'));results.push(...previous.results.slice(0,start));}
try{
 page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));
 const login=await page.request.post(base+'/api/v1/auth/login',{data:{email:'admin@suiteqa.example.com',password:'SuiteQA@12345'}});
 if(!login.ok())throw Error('Disposable QA login failed: '+await login.text());
 const session=await login.json();
 const me=await page.request.get(base+'/api/v1/auth/me',{headers:{Authorization:'Bearer '+session.access_token}}),user=await me.json();
 user.role=session.role;
 const access=await page.request.get(base+'/api/v1/access/me',{headers:{Authorization:'Bearer '+session.access_token}});if(access.ok())user.access=await access.json();
 await page.addInitScript(({session,user})=>sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:session.access_token,refreshToken:session.refresh_token,user,isAuthenticated:true},version:0})),{session,user});
 const matrix=[
  ['/crm/leads','Draft client email'],['/crm/contacts','Draft follow-up'],['/crm/deals','Draft proposal'],['/crm/emails','Draft reply'],['/crm/whatsapp','Draft WhatsApp message'],
  ['/crm/meetings','Summarize meeting'],['/crm/calls','Extract action items'],['/crm/tickets','Draft support reply'],['/crm/templates','Extract key details'],
  ['/pms/tasks','Write task description'],['/pms/projects','Draft client status update'],['/pms/notes','Summarize meeting'],
  ['/srm/invoices','Draft invoice email'],['/srm/collections','Draft overdue follow-up'],['/srm/inventory/purchase-orders','Draft quotation request'],['/srm/inventory/items','Draft stock-delay update'],
  ['/fam/purchase-bills','Draft purchase-order email'],['/fam/vendors','Draft supplier enquiry'],
  ['/hrms/recruitment','Draft job description'],['/hrms/onboarding','Draft onboarding message'],['/hrms/engagement','Draft announcement'],['/hrms/helpdesk','Summarize ticket'],['/hrms/documents','Extract key details'],
 ];
 for(const [path,label] of matrix.slice(start)){
  console.log('CHECK',path,label);
  await page.goto(base+path);await page.waitForLoadState('networkidle');await page.getByRole('button',{name:label,exact:true}).first().waitFor({timeout:45000});
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/writing/draft')&&r.request().method()==='POST'),page.getByRole('button',{name:label,exact:true}).first().click()]);
  if(!response.ok())throw Error(path+': '+await response.text());
  const dialog=page.locator('[data-ai-writing][role="dialog"]');
  await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).waitFor();
  if(await dialog.locator('details').getAttribute('open')===null)await dialog.locator('summary').click();
  await dialog.getByRole('textbox',{name:'AI source details',exact:true}).fill('Renewal R-742 is pending. Maya will confirm delivery by 2030-06-20. Amount INR 12750.');
  await dialog.getByRole('textbox',{name:'AI draft recipient',exact:true}).fill('Asha');
  const [regenerated]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/writing/draft')&&r.request().method()==='POST'),dialog.getByRole('button',{name:'Regenerate',exact:true}).click()]);
  if(!regenerated.ok())throw Error(path+' regenerate failed: '+await regenerated.text());
  const draft=dialog.getByRole('textbox',{name:'AI generated draft',exact:true});
  await draft.waitFor();
  if(!(await draft.inputValue()).includes(label==='Extract action items'?'2030-06-20':'12750'))throw Error(path+' source facts were lost');
  if(await page.getByRole('dialog',{name:'Action bot',exact:true}).count())throw Error('Direct writing opened chatbot');
  results.push({path,action:label,passed:true});
  console.log('PASS',path,label);
  if(path==='/crm/leads'||path==='/hrms/recruitment')await page.screenshot({path:out+'/'+path.split('/').filter(Boolean).join('-')+'.png'});
  await dialog.getByRole('button',{name:'Close dialog',exact:true}).click();
 }
 // Verify insertion into the actual controlled email composer, including subject.
 await page.goto(base+'/crm/emails');
 await page.getByRole('heading',{name:'Compose email',exact:true}).waitFor({timeout:30000});
 const composer=page.locator('section').filter({has:page.getByRole('heading',{name:'Compose email',exact:true})}).last();
 const action=composer.getByRole('button',{name:'Draft client email',exact:true});
 await action.click();
 let dialog=page.locator('[data-ai-writing][role="dialog"]');
 await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).waitFor();
 await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).fill('Hello Asha, please review renewal R-742.');
 await dialog.getByRole('textbox',{name:'AI draft subject',exact:true}).fill('Renewal review');
 await dialog.getByRole('button',{name:'Insert into editor',exact:true}).click();
 await dialog.getByRole('button',{name:'Close dialog',exact:true}).click();
 if(await composer.getByLabel('Subject',{exact:true}).inputValue()!=='Renewal review')throw Error('Subject did not reach composer');
 if(!(await composer.locator('.cc-form textarea[maxlength="50000"]').inputValue()).includes('R-742'))throw Error('Body did not reach composer');
 await page.screenshot({path:out+'/email-insertion.png'});
 results.push({flow:'Controlled email subject and body insertion',passed:true});
 // Shared rich-text integration in an unsaved helpdesk form.
 await page.goto(base+'/hrms/helpdesk');await page.waitForLoadState('networkidle');
 await page.getByRole('button',{name:'New Ticket',exact:true}).click();
 const description=page.getByRole('textbox',{name:'Description',exact:true});
 await description.fill('Maya will review renewal R-742 by Friday. Amount INR 12750.');
 const editor=page.locator('.suite-rte').filter({has:description});
 await editor.getByRole('button',{name:'Shorten text',exact:true}).click();
 dialog=page.locator('[data-ai-writing][role="dialog"]');
 await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).waitFor();
 await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).fill('Review renewal R-742.');
 await dialog.getByRole('button',{name:'Insert into editor',exact:true}).click();
 await dialog.waitFor({state:'hidden'});
 if((await description.innerText()).trim()!=='Review renewal R-742.')throw Error('Rich text draft was not inserted through the editor');
 await page.screenshot({path:out+'/rich-editor-insertion.png'});results.push({flow:'Rich-text insertion in unsaved helpdesk form',passed:true});
 // Note writer uses its own editor and change tracking.
 await page.goto(base+'/pms/notes');await page.waitForLoadState('networkidle');
 await page.getByRole('button',{name:'New note',exact:true}).click();
 const note=page.getByRole('textbox',{name:'Note content',exact:true});await note.fill('Maya will confirm renewal R-742 by Friday.');
 await page.locator('.note-writer').getByRole('button',{name:'Extract key details',exact:true}).click();
 dialog=page.locator('[data-ai-writing][role="dialog"]');await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).waitFor();
 await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).fill('Confirm renewal R-742 by Friday.');
 await dialog.getByRole('button',{name:'Insert into editor',exact:true}).click();
 await dialog.waitFor({state:'hidden'});
 if((await note.innerText()).trim()!=='Confirm renewal R-742 by Friday.')throw Error('Note writer draft was not inserted');
 results.push({flow:'Note editor insertion without saving',passed:true});
 // Mobile layout and direct action.
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/crm/leads');
 await page.getByRole('button',{name:'Draft client email',exact:true}).first().click();
 dialog=page.locator('[data-ai-writing][role="dialog"]');await dialog.getByRole('textbox',{name:'AI generated draft',exact:true}).waitFor();
 const box=await dialog.boundingBox();if(!box||box.x<0||box.x+box.width>391)throw Error('Mobile draft dialog overflows viewport');
 await page.screenshot({path:out+'/mobile.png'});results.push({flow:'Mobile direct draft',passed:true});
 console.log(JSON.stringify({passed:results.length,errors,results},null,2));
 await writeFile(out+'/results.json',JSON.stringify({passed:results.length,errors,results},null,2));
 if(errors.length)throw Error('Browser runtime errors: '+errors.join('; '));
}catch(e){console.error(e);if(page){console.error('Failed URL:',page.url());await page.screenshot({path:out+'/failure.png'});}await writeFile(out+'/results.json',JSON.stringify({passed:results.length,errors,results,failure:String(e)},null,2));throw e;}
finally{await browser.close()}
