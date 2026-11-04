// Live HTTP acceptance checks against the configured local PostgreSQL app. No mocks.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {auth}=require('./custom_fields_live.cjs');
const out=path.resolve('docs/qa/record-360/live');fs.mkdirSync(out,{recursive:true});
const stateFile=path.join(out,'results.json');
const state=fs.existsSync(stateFile)?JSON.parse(fs.readFileSync(stateFile,'utf8')):{run:'R360QA'+Date.now().toString().slice(-8),records:{},checks:[]};
function save(){fs.writeFileSync(stateFile,JSON.stringify(state,null,2));}
async function main(){
 const {api,login}=await auth(),r=state.records;
 async function record(key,fn){if(!r[key]){r[key]=await fn();save();}return r[key];}
 if(process.argv[2]==='seed'){
  await record('company',()=>api('/master-data/companies','POST',{name:state.run+' Customer',roles:['Prospect']}));
  await record('contact',()=>api('/crm/contact-directory','POST',{name:state.run+' Contact',companyId:r.company.id}));
  await record('lead',()=>api('/crm/lead-management/leads','POST',{values:{full_name:state.run+' Lead'}}));
  await record('project',()=>api('/project-management/projects','POST',{name:state.run+' Delivery',project_key:state.run,branch_id:6,manager_user_id:1,owner_user_id:1,status:'Active'}));
  await record('task',()=>api(`/project-management/projects/${r.project.id}/tasks`,'POST',{title:state.run+' Acceptance task',task_key:state.run+'-1',due_date:'2026-11-05',assignee_user_id:1}));
  console.log('QA records',Object.fromEntries(Object.entries(r).map(([k,v])=>[k,v.id])));return;
 }
 async function check(name,fn){await fn();state.checks=state.checks.filter(c=>c.name!==name);state.checks.push({name,status:'pass',at:new Date().toISOString()});save();console.log('PASS',name);}
 const base=`/project-management/task-workspace/tasks/${r.task.id}`;
 async function allWork(kind,id,source){let cursor='',items=[];do{const d=await api(`/record-360/${kind}/${id}/work?source=${source}&cursor_mode=true${cursor?'&cursor='+encodeURIComponent(cursor):''}`);items.push(...d.items);cursor=d.next_cursor;assert(items.length<1000);}while(cursor);return items;}
 if(process.argv[2]==='populate'){
  for(const kind of ['contact','lead'])await record(kind+'Link',()=>api(base+'/crm-links','POST',{kind,record_id:r[kind].id}));
  state.entryCount=state.entryCount||0;
  while(state.entryCount<28){const t=await api(base);await api(base+'/entries','POST',{kind:'followup',body:`${state.run} Follow-up ${String(state.entryCount+1).padStart(2,'0')}`,follow_up_date:'2026-11-05',revision:t.revision});state.entryCount++;save();}
 }
 await check('Direct contact and lead links are visible and idempotent',async()=>{
  for(const kind of ['contact','lead']){const linked=await api(base+'/crm-links','POST',{kind,record_id:r[kind].id});const repeated=await api(base+'/crm-links','POST',{kind,record_id:r[kind].id});assert.equal(linked.id,repeated.id);}
  const links=await api(base+'/crm-links');assert.equal(links.can_manage,true);assert.equal(links.items.length,2);
 });
 await check('CRM PMS SRM customer summary and linked work',async()=>{
  for(const source of ['crm','project_management','srm']){
   const summary=await api(`/record-360/company/${r.company.id}?source=${source}`);assert.equal(summary.id,r.company.id);
   const work=await allWork('company',r.company.id,source);assert(work.some(x=>x.source==='pms_task'&&x.source_id===r.task.id),source+' customer task');console.log('Customer source verified',source,work.length);
  }
  for(const kind of ['contact','lead']){const work=await allWork(kind,r[kind].id,'crm');assert(work.some(x=>x.source==='pms_task'&&x.source_id===r.task.id),kind+' task');assert(work.some(x=>x.source==='pms_followup'));console.log('CRM record verified',kind,work.length);}
 });
 await check('Live PostgreSQL work and history cursors have no duplicate or missing items',async()=>{
  for(const suffix of ['work','events']){
   let cursor='',ids=[],pages=0;
   do {const d=await api(`/record-360/task/${r.task.id}/${suffix}?source=project_management&cursor_mode=true&per_page=5${cursor?'&cursor='+encodeURIComponent(cursor):''}`);assert.equal(d.total,null);assert(d.items.length<=5);ids.push(...d.items.map(x=>x.id));cursor=d.next_cursor;pages++;assert(pages<100);}while(cursor);
   assert.equal(new Set(ids).size,ids.length);assert(ids.length>=28);assert(pages>1);state[suffix+'Paging']={pages,items:ids.length};save();
  }
 });
 await check('Queue paging and filter scope rejection',async()=>{
  const url='/record-360/work/queue/items?view=all&source_filter=pms_task&cursor_mode=true&per_page=5';const a=await api(url);assert(a.next_cursor);const b=await api(url+'&cursor='+encodeURIComponent(a.next_cursor));assert(!a.items.some(x=>b.items.some(y=>x.id===y.id)));
  let rejected=false;try{await api(url+'&search=changed&cursor='+encodeURIComponent(a.next_cursor));}catch(e){rejected=/422/.test(e.message);}assert(rejected);
  const replay=await fetch('http://127.0.0.1:1534/api/v1'+url+'&cursor='+encodeURIComponent(a.next_cursor),{headers:{Authorization:'Bearer '+login.access_token,'X-Suite-Organization':'1','X-Suite-Branch':'1'}});assert.equal(replay.status,422);
 });
 console.log('Live checks complete',state.run);
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
