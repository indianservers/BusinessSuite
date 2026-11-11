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
let memories:any[]=[];let memorySeq=0;
const artifactVersions:any[]=[];
let savedAgents:any[]=[];
let agentSchedules:any[]=[];
let agentWorkflows:any[]=[];
let builder:any=null;const builderMessages:any[]=[];
let coordinator:any=null;const coordinatorMessages:any[]=[];
let librarySkills:any[]=[];const libraryVersions=new Map<number,any[]>();
const chatFiles=new Map<number,any[]>();let fileSeq=0;
window.addEventListener('suite:branch-changed',()=>{chats=[];chatRuns.clear()});
api.defaults.adapter=async config=>{
 const path=config.url||'',body=typeof config.data==='string'?JSON.parse(config.data):config.data;
 requests.push({path,method:config.method,body});let data:any={};
 if(path.endsWith('/builder/model-status'))data={active:true,tensorflow_version:'2.20.0',training_commands:640};
 else if(path.endsWith('/agents/coordinator'))data={items:coordinator?[coordinator]:[]};
 else if(path.endsWith('/coordinator/messages')){coordinator={context_id:82,revision:(coordinator?.revision||0)+1,draft:{name:body.text.startsWith('Call it ')?body.text.slice(8):'Customer recovery',nodes:[{agent_id:71,instructions:'Create CRM task called Customer recovery',depends_on:[]}]},agents:{'71':{name:'Delivery coordinator'}},preview_hash:'d'.repeat(64),provider:'local'};coordinatorMessages.push({text:body.text});data=coordinator}
 else if(path.endsWith('/coordinator/82/apply')){const flow={id:301,name:coordinator.draft.name,status:'preview',spec:{nodes:coordinator.draft.nodes},agents:coordinator.agents,nodes:[{step:1,state:'pending'}],preview_hash:'b'.repeat(64)};agentWorkflows.push(flow);coordinator={...coordinator,workflow_id:301};data={...coordinator,workflow_preview:flow}}
 else if(path.endsWith('/coordinator/82'))data={...coordinator,messages:coordinatorMessages};
 else if(path.endsWith('/workflows/301/results'))data={workflow_id:301,name:agentWorkflows[0].name,status:'waiting',complete:false,summary:'0/1 specialist steps completed. The remaining step needs review.',aggregation:'Server-authorized specialist answers and confirmed receipts.',items:[{step:1,agent_name:'Delivery coordinator',status:'awaiting_approval',summary:'Review this exact task before execution.',citations:[],receipts:[]}]};
 else if(path.endsWith('/agents/builder'))data={items:builder?[builder]:[]};
 else if(path.endsWith('/builder/messages')){const name=body.text.startsWith('Call it ')?body.text.slice(8):'Delivery coordinator';builder={context_id:81,revision:(builder?.revision||0)+1,config:{name,instructions:'Prepare reviewed customer followups.',modules:['CRM'],tools:['crm.create_task'],memory:[],provider:'preferred'},draft:{name},provider:'local',question:null,preview_hash:'c'.repeat(64),knowledge:[],schedule:null};builderMessages.push({text:body.text,proposal:{question:null}});data=builder}
 else if(path.endsWith('/builder/81/apply')){const agent={id:71,...builder.config,revision:1,skill_ids:[],connection_ids:[],mcp_ids:[]};savedAgents.push(agent);builder={...builder,agent_id:71};data={...builder,agent,schedule_preview:null}}
 else if(path.endsWith('/builder/81'))data={...builder,messages:builderMessages};
 else if(path.endsWith('/agents')){if(config.method==='post'){data={id:71,...body,revision:1};savedAgents.push(data)}else data={items:savedAgents,tools:[{name:'crm.create_task',module:'CRM',write:true}]}}
 else if(path.endsWith('/agents/workflows'))data={items:agentWorkflows};
 else if(path.endsWith('/agents/workflows/preview')){data={id:301,name:body.name,status:'preview',spec:body,preview_hash:'b'.repeat(64),agents:Object.fromEntries(savedAgents.map(a=>[String(a.id),a])),nodes:body.nodes.map((_:any,i:number)=>({step:i+1,state:'pending'}))};agentWorkflows.push(data)}
 else if(path.endsWith('/agents/workflows/301/start')){agentWorkflows[0].status='waiting';agentWorkflows[0].nodes[0].state='review';data=agentWorkflows[0]}
 else if(path.endsWith('/agents/workflows/301/stop')){agentWorkflows[0].status='cancelled';data={...agentWorkflows[0],cancel_errors:[]}}
 else if(path.endsWith('/agents/schedules'))data={items:agentSchedules};
 else if(path.endsWith('/agents/schedules/preview')){data={id:91,status:'preview',spec:body,agent_name:'Delivery coordinator',agent_revision:1,preview_hash:'a'.repeat(64),occurrences:[]};agentSchedules.push(data)}
 else if(path.endsWith('/agents/schedules/91/activate')){agentSchedules[0].status='active';data=agentSchedules[0]}
 else if(path.endsWith('/agents/schedules/91/cancel')){agentSchedules[0].status='cancelled';data=agentSchedules[0]}
 else if(path.endsWith('/catalog/skills')){if(config.method==='post'){data={id:11,...body,revision:1};librarySkills.push(data);libraryVersions.set(11,[{...data}])}else data={items:librarySkills}}
 else if(path.endsWith('/catalog/skills/11/versions'))data={items:[...(libraryVersions.get(11)||[])].reverse(),current_revision:librarySkills[0]?.revision};
 else if(path.endsWith('/catalog/skills/11')){if(config.method==='delete'){librarySkills=[];data={archived:true}}else{data={...librarySkills[0],...body,revision:librarySkills[0].revision+1};librarySkills[0]=data;libraryVersions.get(11)?.push({...data})}}
 else if(path.endsWith('/agents/mcp'))data={items:[]};
 else if(path.endsWith('/agents/connectors'))data={connections:[],catalog:[]};
 else if(path.endsWith('/reminders'))data={items:[]};
 else if(path.endsWith('/tools'))data={tools:[{name:'crm.create_task',module:'CRM',description:'Create a CRM task after review.',approval_required:true,fields:['title']}]};
 else if(path.endsWith('/runs'))data={items:[...chatRuns.values()].flat().slice().reverse()};
 else if((path.endsWith('/workspace/file-search')||path.endsWith('/workspace/search'))){const files=chatFiles.get(body.conversation_id)||[];const records=(body.tools||[]).includes('crm.tasks')?[{id:'crm.tasks:42',kind:'record',record_id:42,tool:'crm.tasks',label:'Stalled customer onboarding',excerpt:'Review the stalled delivery commitment.',href:'/crm/tasks'}]:[];data={files_searched:files.length,candidates_searched:files.length+records.length,semantic_used:body.mode!=='lexical',records:records.length?[{tool:'crm.tasks',records_searched:1,complete:false}]:[],coverage:'Bounded current authorized API snapshots and parsed conversation uploads.',items:[...records,...files.filter(f=>f.excerpt.toLowerCase().includes(body.query.toLowerCase())).map(f=>({id:`upload:${f.id}:0`,kind:'upload',file_id:f.id,label:f.name,excerpt:f.excerpt,start:0,end:f.excerpt.length,href:`#bot-attachment-${f.id}`}))]}}

 else if(path.endsWith('/artifacts'))data={items:artifactVersions.length?[artifactVersions.at(-1)]:[]};
 else if(/\/artifacts\/501\/versions$/.test(path))data={items:[...artifactVersions].reverse(),current_revision:artifactVersions.length};
 else if(/\/artifacts\/501$/.test(path))data={...(config.params?.revision?artifactVersions[Number(config.params.revision)-1]:artifactVersions.at(-1)),current_revision:artifactVersions.length};
 else if(path.endsWith('/memory')){if(config.method==='post'){data={...body,id:++memorySeq,key:`module:${memorySeq}`,revision:1};memories.push(data)}else data={items:memories}}
 else if(/\/memory\/module\/\d+$/.test(path)){const id=Number(path.split('/').at(-1));if(config.method==='delete'){memories=memories.filter(m=>m.id!==id);data={forgotten:true}}else{const old=memories.find(m=>m.id===id);Object.assign(old,body,{revision:old.revision+1});data=old}}
 else if(path.endsWith('/intelligence'))data={preference:body?.provider||'preferred',selected_provider:body?.provider==='local'?'local':'gemini',model:'fixture-model',items:[{provider:'gemini',model:'fixture-model',connectivity:{status:'success'},planning:{status:'success'}}]};
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
 else if(/\/runs\/\d+\/retry-planning$/.test(path)){
  const source=chatRuns.get(run.result.request.conversation_id)?.find(r=>r.id===Number(path.match(/runs\/(\d+)/)![1]));
  run={...source,id:++seq,status:'awaiting_approval',error_code:null,plan:{summary:'Recovered draft for review',steps:[{tool:'crm.create_task',payload:{title:'Recovered task'}}]},result:{request:source.result.request}};
  chatRuns.get(run.result.request.conversation_id)?.push(run);data=run;
 }
 else if(path.endsWith('/commands')){
  if(body.text==='retry safely'&&!failed){failed=true;throw {response:{status:503,data:{detail:'Temporary failure; retry the unchanged request.'}}}}
  if(body.text==='slow reply')await new Promise(resolve=>setTimeout(resolve,600));
  const missing=body.text==='create a task';
  run={id:++seq,command:body.text,status:missing?'needs_clarification':body.text==='what are todays jobs'?'answered':'awaiting_approval',plan_hash:'0'.repeat(64),plan:{summary:missing?'I need a title.':body.text==='what are todays jobs'?'No jobs in this development sample.':'Review this exact task.',...(missing?{question:'What title should I use?'}:{}),steps:missing||body.text==='what are todays jobs'?[]:[{tool:'crm.create_task',payload:{title:body.text,preview_token:'hidden-signature'}}]},receipts:[]};data=run;
  run.result={request:body};
  if(/^Search knowledge for:|^What about /i.test(body.text)){
   const file=(chatFiles.get(body.conversation_id)||[])[0];run.status='answered';run.plan={summary:file?'Retrieved source excerpts: Escalation owners review stalled commitments.':'No matching excerpts were found.',steps:[]};
   run.result.citations=file?[{id:`upload:${file.id}:0`,file_id:file.id,label:file.name,href:`#bot-attachment-${file.id}`}]:[];
  }
  if(body.text==='create artifact sample'||/^Edit artifact #501:/.test(body.text)){
   const editing=body.text!=='create artifact sample';run.plan={summary:'Review this artifact draft.',steps:[{tool:editing?'crm.edit_artifact':'crm.create_artifact',payload:{title:'Customer proposal',kind:'document',content:editing?'Original proposal. Added timeline.':'Original proposal.',columns:[],rows:[],...(editing?{artifact_id:501,expected_revision:artifactVersions.length}:{})}}]};run.artifactSample=true;
  }
  if(body.text==='provider failure sample'){run.status='failed';run.plan={summary:'Planning failed',steps:[]};run.error_code='AI_POLICY_HTTP_502';run.result.can_retry_planning=true;run.result.planning_issue='Provider temporarily unavailable; original request saved.'}
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
  if(run.artifactSample){if(!run.artifactSaved){artifactVersions.push({id:501,module:'CRM',...run.plan.steps[0].payload,revision:artifactVersions.length+1,provenance:{note:'Reviewed generated content.',citations:[]}});run.artifactSaved=true}Object.assign(run,{status:'succeeded',receipts:[{step:1,tool:run.plan.steps[0].tool,record_id:501,artifact_id:501,artifact_revision:artifactVersions.length}]})}
  else if(run.workflowSample&&!run.resumed){Object.assign(run,{status:'paused',can_resume:true,error_code:'CANONICAL_STEP_503',receipts:[{step:1,tool:'crm.create_task',record_id:901}]});run.workflow_steps[0].status='succeeded';run.workflow_steps[1].status='paused';run.workflow_steps[1].attempts=3}
  else{Object.assign(run,{status:'succeeded',receipts:run.workflowSample?run.plan.steps.map((s:any,i:number)=>({step:i+1,tool:s.tool,record_id:901+i})):[{step:1,tool:'crm.create_task',record_id:901}]});if(run.workflowSample)run.workflow_steps.forEach((s:any)=>s.status='succeeded')}
  data=run
 }
 if(data.plan)data.result_cards=data.plan.steps.length?data.plan.steps.map((s:any,i:number)=>{const r=data.receipts?.find((v:any)=>v.step===i+1);return {id:`${data.id}-${i}`,title:s.payload.title||s.payload.subject||'Action',kind:r?'record':'draft',status:r?'succeeded':data.status,record_id:r?.record_id,artifact_id:r?.artifact_id,href:r?'/crm/tasks':undefined}}):[{id:'answer',kind:'answer',title:'Answer',body:data.plan.summary,status:data.status}];
 return {data,status:200,statusText:'OK',headers:{},config};
};
function Demo(){const location=useLocation();return <div style={{minHeight:'100vh',padding:28,background:'#f8fafc'}}><p style={{fontSize:12,color:'#64748b'}}>Development QA · simulated module data and actions</p><h1 style={{fontSize:28,margin:'18px 0'}}>{location.pathname}</h1><nav style={{display:'flex',flexWrap:'wrap',gap:18}}>{['/crm/leads','/pms/people','/pms/tasks','/hrms/employee-directory','/srm/pos','/fam/vouchers','/power-apps/automations'].map(path=><Link key={path} to={path}>{path}</Link>)}</nav><Link to="/crm/leads?bot_conversation=1">Open scheduled conversation fixture</Link><ActionBot/></div>}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><MemoryRouter initialEntries={[new URLSearchParams(location.search).get('path')||'/crm/leads']}><Demo/></MemoryRouter></React.StrictMode>);
