// Real full-app acceptance checks. No intercepted requests or component fixtures.
const {chromium,expect:baseExpect}=require('../frontend/node_modules/playwright/test');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const expect=baseExpect.configure({timeout:45000});
const origin='http://127.0.0.1:5198',root='http://127.0.0.1:1534/api/v1';
const output=path.resolve('docs/qa/custom-fields-live');fs.mkdirSync(output,{recursive:true});
const statePath=path.resolve('.tmp/custom-fields-live-state.json');
let state=fs.existsSync(statePath)?JSON.parse(fs.readFileSync(statePath,'utf8')):{run:'CFQA'+Date.now().toString().slice(-8),fields:{},records:{},checks:[],snapshots:{}};
function persist(){if(fs.existsSync(statePath)){const disk=JSON.parse(fs.readFileSync(statePath,"utf8"));if(disk.run===state.run){state.fields={...disk.fields,...state.fields};state.records={...disk.records,...state.records};state.snapshots={...disk.snapshots,...state.snapshots};state.checks=Array.from(new Map([...(disk.checks||[]),...state.checks].map(c=>[c.name,c])).values());}}fs.writeFileSync(statePath,JSON.stringify(state,null,2));fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(state,null,2));}
async function auth(){const source=fs.readFileSync('backend/app/db/init_db.py','utf8'),password=source.match(/"email": "admin@aihrms.com",\s*"password": "([^"]+)"/)[1];const r=await fetch(root+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'admin@aihrms.com',password})});assert.equal(r.status,200);const login=await r.json();const headers={Authorization:'Bearer '+login.access_token,'Content-Type':'application/json','X-Suite-Organization':'1','X-Suite-Branch':'6'};async function api(p,method='GET',body){const r=await fetch(root+p,{method,headers,body:body===undefined?undefined:JSON.stringify(body)});const d=r.status===204?null:await r.json();if(!r.ok)throw new Error(`${method} ${p}: ${r.status} ${JSON.stringify(d)}`);return d;}return {login,api,actor:await api('/auth/me'),access:await api('/access/me')};}
function fname(entity,place){return `${state.run} ${entity} ${place}`;}
const places=['create','edit','quick_create','detail'];
async function seed(api){
 for(const entity of ['leads','contacts','companies','deals','quotations','tasks']){
  if(state.fields[entity])continue;
  const before=await api('/crm/custom-fields?entityType='+entity);state.snapshots[entity]=before.items;
  state.fields[entity]={};persist();
  for(const [i,place] of places.entries()){
   const field=await api('/crm/custom-fields','POST',{entityType:entity,fieldName:fname(entity,place),fieldKey:`${state.run.toLowerCase()}_${entity}_${place}`,fieldType:i===0?'radio':i===1?'combobox':'text',options:{values:i<2?['Audit','Tax']:[],ui:{places:[place],section:state.run}},isRequired:false,isVisible:true});state.fields[entity][place]=field;persist();
  }
 }
 if(!state.records.company){state.records.company=await api('/master-data/companies','POST',{name:state.run+' Company',roles:['Prospect']});persist();}
 if(!state.records.contact){state.records.contact=await api('/crm/contact-directory','POST',{name:state.run+' Contact',companyId:state.records.company.id});persist();}
 if(!state.records.lead){state.records.lead=await api('/crm/lead-management/leads','POST',{values:{full_name:state.run+' Lead',company_name:state.run+' Company'}});persist();}
 if(!state.records.pipeline){state.records.pipeline=await api('/crm/pipelines','POST',{name:state.run+' Pipeline'});persist();}
 if(!state.records.stage){state.records.stage=await api(`/crm/pipelines/${state.records.pipeline.id}/stages`,'POST',{name:state.run+' Discovery',probability:10});persist();}
 if(!state.records.deal){state.records.deal=await api('/crm/deals','POST',{name:state.run+' Deal',company_id:state.records.company.id,contact_id:state.records.contact.id,pipeline_id:state.records.pipeline.id,stage_id:state.records.stage.id,amount:1000});persist();}
 if(!state.records.task){state.records.task=await api('/crm/tasks','POST',{title:state.run+' CRM task',status:'To Do',priority:'Medium'});persist();}
 if(!state.records.quote){state.records.quote=await api('/crm/quotations','POST',{quote_number:state.run+'-Q1',company_id:state.records.company.id,deal_id:state.records.deal.id,status:'Draft',issue_date:'2026-11-04',expiry_date:'2026-12-04'});persist();}
 for(const [entity,key] of [['leads','lead'],['contacts','contact'],['companies','company'],['deals','deal'],['quotations','quote'],['tasks','task']]){
  if(state.records[key].seeded)continue;
  const values=Object.fromEntries(places.map((place,i)=>[state.fields[entity][place].fieldKey,i<2?'Tax':state.run+' saved '+place]));
  await api(`/crm/${entity}/${state.records[key].id}`,'PATCH',{customFields:values});state.records[key].seeded=true;persist();
 }
}
async function browserContext(a){const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1480,height:1080}});await context.addInitScript(({login,actor,access})=>{sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','6');sessionStorage.setItem('hrms-auth',JSON.stringify({state:{accessToken:login.access_token,refreshToken:login.refresh_token,isAuthenticated:true,user:{...actor,role:actor.role?.name||'super_admin',access}},version:0}));},{login:a.login,actor:a.actor,access:a.access});const page=await context.newPage();page.setDefaultTimeout(45000);page.on('dialog',d=>d.accept());if(process.env.CF_NETWORK){const started=new Map();page.on('request',r=>{if(r.url().includes('/api/'))started.set(r,Date.now());});page.on('requestfinished',r=>{if(started.has(r)){const ms=Date.now()-started.get(r);if(ms>3000)console.log('API',ms,r.url());started.delete(r);}});page.on('requestfailed',r=>console.log('REQUEST FAILED',r.url(),r.failure()));}const errors=[];page.on('pageerror',e=>errors.push(e.message));return {browser,context,page,errors};}
async function inspect(page,route){await page.goto(origin+route);await page.waitForLoadState('networkidle',{timeout:15000}).catch(()=>{});console.log(route,(await page.locator('body').innerText()).slice(-7000));await page.screenshot({path:path.join(output,'inspect-'+route.replace(/[^a-z0-9]/gi,'-')+'.png'),fullPage:true});}
async function check(page,name,entity,place,action){if(process.env.CF_CHECK_FILTER&&!new RegExp(process.env.CF_CHECK_FILTER).test(name))return;state.checks=state.checks.filter(c=>c.name!==name);try{await action();const modal=page.getByRole("dialog").last();const surface=await modal.count()?modal:page;for(const p of places){const control=surface.getByText(fname(entity,p),{exact:true}).first();if(p===place)await expect(control).toBeVisible();else await expect(control).not.toBeVisible();}state.checks.push({name,entity,place,status:'pass'});console.log('PASS',name);await page.screenshot({path:path.join(output,'pass-'+name.replace(/[^a-z0-9]/gi,'-')+'.png'),fullPage:true});}catch(e){state.checks.push({name,entity,place,status:'fail',error:e.message});console.log('FAIL',name,e.message.split('\n').slice(0,4).join(' '));await page.screenshot({path:path.join(output,'failure-'+name.replace(/[^a-z0-9]/gi,'-')+'.png'),fullPage:true});}persist();}
async function main(){const a=await auth();const mode=process.argv[2]||'inspect';if(mode==='seed'){await seed(a.api);console.log('Seeded',state.run,Object.keys(state.fields));return;}
 const b=await browserContext(a);try{if(mode==='inspect'){await inspect(b.page,process.argv[3]||'/crm/leads');}else if(mode==='crm'){
 const p=b.page;
 await check(p,'Lead create','leads','create',async()=>{await p.goto(origin+'/crm/leads');await p.getByRole('button',{name:/Add lead|New lead|Create lead/i}).first().click();});
 await check(p,'Contact create','contacts','create',async()=>{await p.goto(origin+'/crm/contacts');await p.getByRole('button',{name:'Create contact',exact:true}).click();const radio=p.getByRole('radiogroup',{name:fname('contacts','create'),exact:true}).getByRole('radio',{name:'Audit',exact:true});await radio.check();await expect(radio).toBeChecked();});
 await check(p,'Company create','companies','create',async()=>{await p.goto(origin+'/crm/companies');await p.getByRole('button',{name:'Create company',exact:true}).click();});
 for(const [entity,key,url] of [['leads','lead','leads'],['contacts','contact','contacts'],['companies','company','companies'],['deals','deal','deals'],['quotations','quote','quotations']])await check(p,entity+' detail',entity,'detail',async()=>{await p.goto(`${origin}/crm/${url}/${state.records[key].id}`); if(entity!=='deals'){await p.getByRole("heading",{name:new RegExp(state.run)}).first().waitFor({timeout:45000});const summary=p.locator('summary').filter({hasText:'Details & related records'});if(entity!=="quotations"){await summary.first().waitFor({timeout:45000});await summary.first().click();}const tab=p.getByRole('tab',{name:'Details',exact:true});await tab.first().waitFor({timeout:45000});await tab.first().click();}});
 console.log('BROWSER ERRORS',JSON.stringify(b.errors));
 }}finally{await b.browser.close();}}
module.exports={auth,state,persist,places,fname,browserContext,check,inspect,origin,root,output};
if(require.main===module)main().catch(e=>{console.error(e.message);persist();process.exitCode=1;});
