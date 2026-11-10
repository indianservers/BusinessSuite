/** Development-only fixture. All action receipts are simulated. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter,Link,useLocation} from 'react-router-dom';
import ActionBot from '../../src/components/ai-agents/ActionBot';
import {api} from '../../src/services/api';
import {useAuthStore} from '../../src/store/authStore';
import '../../src/index.css';
if(!import.meta.env.DEV)throw new Error('Development fixture only');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,user:{id:7,email:'robot-fixture@example.com',role:'Super Admin',is_superuser:true}});
(window as any).__hydrateBotCompany=(companyId:number)=>{const old=useAuthStore.getState().user?.access?.companyId;if(old!=null&&old!==companyId){chats=[];chatRuns.clear()}useAuthStore.setState(s=>({user:{...s.user!,access:{...s.user?.access,companyId} as any}}))};
let run:any=null,seq=0,failed=false;const requests:any[]=[];(window as any).__botRequests=requests;
let chats:any[]=[],chatSeq=0;const chatRuns=new Map<number,any[]>();
const chatFiles=new Map<number,any[]>();let fileSeq=0;
window.addEventListener('suite:branch-changed',()=>{chats=[];chatRuns.clear()});
api.defaults.adapter=async config=>{
 const path=config.url||'',body=typeof config.data==='string'?JSON.parse(config.data):config.data;
 requests.push({path,method:config.method,body});let data:any={};
 if(path.endsWith('/tools'))data={tools:[]};
 else if(path.endsWith('/providers'))data={items:[{provider:'gemini',enabled:true,data_sharing_allowed:true}]};
 else if(path.endsWith('/conversations')){if(config.method==='post'){data={id:++chatSeq,title:body.title};chats.unshift(data);chatRuns.set(data.id,[])}else{await new Promise(resolve=>setTimeout(resolve,180));data={items:chats}}}
 else if(/\/conversations\/\d+(?:\/resume)?$/.test(path)){const id=Number(path.match(/conversations\/(\d+)/)![1]);data={...chats.find(c=>c.id===id),runs:chatRuns.get(id)||[],attachments:chatFiles.get(id)||[]}}
 else if(/\/conversations\/\d+\/attachments$/.test(path)){
  const id=Number(path.match(/conversations\/(\d+)/)![1]);const file=(config.data as FormData).get('file') as File;
  const text=await file.text();data={id:++fileSeq,name:file.name,size:file.size,format:'.csv',preview:text.trim().split('\n').map(line=>line.split(',')),row_count:1,notes:[],excerpt:text};chatFiles.set(id,[...(chatFiles.get(id)||[]),data])
 }else if(/\/conversations\/\d+\/attachments\/\d+$/.test(path)){
  const [id,file]=path.match(/conversations\/(\d+)\/attachments\/(\d+)/)!.slice(1).map(Number);chatFiles.set(id,(chatFiles.get(id)||[]).filter(f=>f.id!==file));data={deleted:true}
 }else if(/\/runs\/\d+\/revise$/.test(path)){
  const old=run;old.status='superseded';run=JSON.parse(JSON.stringify(old));run.id=++seq;run.status='awaiting_approval';run.plan_hash='1'.repeat(64);run.plan.summary='Review the edited actions.';
  body.changes.forEach((change:any)=>run.plan.steps[change.step-1].payload[change.field]=change.value);chatRuns.get(run.result.request.conversation_id)?.push(run);data=run;
 }
 else if(path.endsWith('/commands')){
  if(body.text==='retry safely'&&!failed){failed=true;throw {response:{status:503,data:{detail:'Temporary failure; retry the unchanged request.'}}}}
  if(body.text==='slow reply')await new Promise(resolve=>setTimeout(resolve,600));
  const missing=body.text==='create a task';
  run={id:++seq,command:body.text,status:missing?'needs_clarification':body.text==='what are todays jobs'?'answered':'awaiting_approval',plan_hash:'0'.repeat(64),plan:{summary:missing?'I need a title.':body.text==='what are todays jobs'?'No jobs in this development sample.':'Review this exact task.',...(missing?{question:'What title should I use?'}:{}),steps:missing||body.text==='what are todays jobs'?[]:[{tool:'crm.create_task',payload:{title:body.text,preview_token:'hidden-signature'}}]},receipts:[]};data=run;
  run.result={request:body};
  if(body.text==='workflow sample'){
   run.workflowSample=true;run.plan.steps=[{tool:'crm.create_task',payload:{title:'Customer recovery'}},{tool:'pms.create_task',record_id:22,depends_on:[1],payload:{title:'Delivery recovery'}},{tool:'hrms.create_ticket',depends_on:[2],payload:{subject:'Staffing support',description:'Reviewed request'}}];
   run.workflow_steps=run.plan.steps.map((s:any,i:number)=>({step:i+1,tool:s.tool,depends_on:s.depends_on||[],status:i?'blocked':'pending',attempts:0}));
  }
  chatRuns.get(body.conversation_id)?.push(run);
 }else if(path.endsWith('/approve')){run.status='queued';data=run}
 else if(path.endsWith('/feedback')){run.result={...run.result,feedback:{rating:body.rating,correction:body.correction,revision:(run.result.feedback?.revision||0)+1,training_approved:false}};data=run}
 else if(path.endsWith('/resume')){run.status='queued';run.can_resume=false;run.resumed=true;run.error_code=null;data=run}
 else if(path.endsWith('/cancel')){run={...run,status:'cancelled'};data=run}
 else if(/\/runs\/\d+$/.test(path)){
  if(run.workflowSample&&!run.resumed){Object.assign(run,{status:'paused',can_resume:true,error_code:'CANONICAL_STEP_503',receipts:[{step:1,tool:'crm.create_task',record_id:901}]});run.workflow_steps[0].status='succeeded';run.workflow_steps[1].status='paused';run.workflow_steps[1].attempts=3}
  else{Object.assign(run,{status:'succeeded',receipts:run.workflowSample?run.plan.steps.map((s:any,i:number)=>({step:i+1,tool:s.tool,record_id:901+i})):[{step:1,tool:'crm.create_task',record_id:901}]});if(run.workflowSample)run.workflow_steps.forEach((s:any)=>s.status='succeeded')}
  data=run
 }
 if(data.plan)data.result_cards=data.plan.steps.length?data.plan.steps.map((s:any,i:number)=>{const r=data.receipts?.find((v:any)=>v.step===i+1);return {id:`${data.id}-${i}`,title:s.payload.title||s.payload.subject||'Action',kind:r?'record':'draft',status:r?'succeeded':data.status,record_id:r?.record_id,href:r?'/crm/tasks':undefined}}):[{id:'answer',kind:'answer',title:'Answer',body:data.plan.summary,status:data.status}];
 return {data,status:200,statusText:'OK',headers:{},config};
};
function Demo(){const location=useLocation();return <div style={{minHeight:'100vh',padding:28,background:'#f8fafc'}}><p style={{fontSize:12,color:'#64748b'}}>Development QA · simulated module data and actions</p><h1 style={{fontSize:28,margin:'18px 0'}}>{location.pathname}</h1><nav style={{display:'flex',flexWrap:'wrap',gap:18}}>{['/crm/leads','/pms/people','/pms/tasks','/hrms/employee-directory','/srm/pos','/fam/vouchers','/power-apps/automations'].map(path=><Link key={path} to={path}>{path}</Link>)}</nav><ActionBot/></div>}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><MemoryRouter initialEntries={[new URLSearchParams(location.search).get('path')||'/crm/leads']}><Demo/></MemoryRouter></React.StrictMode>);
