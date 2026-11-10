/** Development-only visual fixture; no real credentials or provider calls. */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import SuiteOperatorPage from '../../src/pages/ai-agents/SuiteOperatorPage';
import { api } from '../../src/services/api';
import '../../src/index.css';

if (!import.meta.env.DEV) throw new Error('Development fixture only');
let artifacts:any[]=[];
(window as any).__assistantQaCommands=[];
let reviewedRun:any=null;
let qaDialogueRuns:any[]=[];
let qaReminders:any[]=[];let qaCommitments:any[]=[];
(window as any).__qaReminderApprovals=0;
(window as any).__qaOperationalRules=[];
const today=new Date().toISOString().slice(0,10);
function dateOffset(days:number){const d=new Date(`${today}T12:00:00Z`);d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
const tasks=[
 {id:1,task_key:'VAT-01',title:'Review filing documents',status:'In Progress',priority:'High',due_date:dateOffset(-3),days_remaining:-3,bucket:'overdue',project_id:1},
 {id:2,task_key:'VAT-02',title:'Confirm client approval',status:'To Do',priority:'High',due_date:today,days_remaining:0,bucket:'today',project_id:1},
 {id:3,task_key:'VAT-03',title:'Submit quarterly return',status:'To Do',priority:'Medium',due_date:dateOffset(5),days_remaining:5,bucket:'upcoming',project_id:1},
 {id:4,task_key:'VAT-04',title:'Schedule next client review',status:'To Do',priority:'Low',due_date:null,days_remaining:null,bucket:'undated',project_id:1}
];
api.defaults.adapter=async config=>{
 const path=config.url||'';const body=config.data?JSON.parse(config.data):{};let data:any={};
 if(path.endsWith('/users/search'))data={items:[{id:7,displayName:'QA teammate',email:'qa@example.test'}]};
 else if(path.endsWith('/crm/tasks'))data={items:tasks};
 else if(path.endsWith('/reminders/preview')){data={id:1,status:'preview',preview_hash:'a'.repeat(64),spec:body,recipients:[{id:7,email:'qa@example.test'}],email_preview:{subject:'BusinessSuite reminder',body:'A reviewed reminder is due. Sign in: https://example.test/pms/tasks/1'},receipts:[],next_at:body.scheduled_at};qaReminders=[data];}
 else if(path.endsWith('/reminders/1/approve')){(window as any).__qaReminderApprovals++;data={...qaReminders[0],status:'active'};qaReminders=[data];}
 else if(path.endsWith('/reminders/1/cancel')){data={...qaReminders[0],status:'cancelled'};qaReminders=[data];}
 else if(path.endsWith('/reminders/1/receipts'))data={items:[]};
 else if(path.endsWith('/reminders'))data={items:qaReminders};
 else if(path.endsWith('/commitments/extract')){data={id:1,status:'draft',module:body.module,project_id:body.project_id,source_status:'verified',revision:1,source:{kind:'transcript',label:'QA meeting',author:body.author,occurred_at:body.occurred_at,verified:false},candidates:[{id:1,title:'Send proposal',quote:body.text,due_date:'2030-01-10',owner_user_id:null,status:'draft',ambiguities:['owner']}]};qaCommitments=[data];}
 else if(path.endsWith('/candidates/1/confirm')){data={...qaCommitments[0],revision:2,status:'confirmed',candidates:[{...qaCommitments[0].candidates[0],...body,status:'confirmed',ambiguities:[]}]};qaCommitments=[data];}
 else if(path.endsWith('/candidates/1/task-draft'))data={summary:'Create the reviewed commitment task',module:'CRM',workspace_id:null,commitment_id:1,candidate_id:1,steps:[{tool:'crm.create_task',payload:{title:qaCommitments[0].candidates[0].title,owner_user_id:7,due_date:'2030-01-10'}}]};
 else if(path.endsWith('/commitments'))data={items:qaCommitments};
 else if(path.endsWith('/source-connections'))data={items:[{connector:'gmail',label:'Google Gmail',oauth_configured:true,accounts:[]},{connector:'outlook',label:'Microsoft Outlook',oauth_configured:false,accounts:[]},{connector:'google_calendar',label:'Google Calendar',oauth_configured:true,accounts:[]},{connector:'microsoft_calendar',label:'Microsoft Calendar',oauth_configured:false,accounts:[]}]};
 else if(path.endsWith('/local-model')){const module=config.params?.module||'CRM';data={modules:Object.fromEntries(['CRM','PMS','Sales','HRMS'].map(name=>[name,{commands:120,intent_families:20}])),examples:[{module,intent:'leads.message',text:`${module}: send a message to all leads`},{module,intent:'jobs.today',text:`${module}: what are todays jobs`},{module,intent:'reminders.today',text:`${module}: check todays reminder`}]};}
 else if(path.endsWith('/operations/delivery'))data={nodes:[{kind:'project',id:1,label:'Client compliance',source:{href:'/pms/projects/1'}},{kind:'customer',id:7,label:'Acme QA customer',source:{href:'/crm/companies'}}],edges:[{from:'customer:7',to:'project:1',basis:'ProjectCommercial.customer_id'}],delivery_signals:[{reason:'Overdue',source:{label:tasks[0].title,href:'/pms/tasks/1'}}],gaps:['Deal link missing or unavailable under current access'],invoice_totals:[{currency:'INR',amount:'120.00'}],coverage:[{source:'tasks',status:'available'}],retrieved_at:new Date().toISOString(),task_coverage:'bounded_sample',invoice_coverage:'bounded_to_200',note:'Explicit commercial links only.'};
 else if(path.endsWith('/operations/capacity-scenario'))data={week_start:body.week_start,omitted_people:0,items:[{user_id:7,allocated_hours:20,additional_hours:body.additional_hours?.['7']||0,available_hours:40,overload_hours:Math.max(0,20+(body.additional_hours?.['7']||0)-40),unscheduled_tasks:1}],assumptions:['Projection only; no writes.']};
 else if(path.endsWith('/operations/health'))data={scope:'Current owner, company, branch and workspace',retrieved_at:new Date().toISOString(),run_counts:{awaiting_approval:2},attention:[],providers:[{provider:'gemini',model:'QA mock',calls:5,successes:4,mean_duration_ms:100,known_cost:'0',priced_calls:0,quality:'not_evaluated'}],note:'Missing costs are not zero.'};
 else if(path.endsWith('/projects'))data=[{id:1,name:'Client compliance · QA data',workspace_id:null}];
 else if(path.endsWith('/workspaces'))data=[];
 else if(path.endsWith('/local-context'))data={tasks,collaborators:[{id:7,email:'qa@example.test',name:'QA teammate'}]};
 else if(path.endsWith('/tools'))data={tools:[{name:'pms.tasks',module:'PMS',description:'Read authorized project tasks',approval_required:false,record_id_required:true}]};
 else if(path.endsWith('/providers'))data={items:['gemini','openai'].map(provider=>({provider,model:'QA provider (mock)',enabled:true,data_sharing_allowed:true}))};
 else if(path.endsWith('/briefing')){const source={id:'s1:1',tool:'pms.tasks',record_id:1,label:tasks[0].title,href:'/pms/tasks/1',retrieved_at:new Date().toISOString()};const item={module:'PMS',record_id:1,title:tasks[0].title,reasons:['Overdue'],due_date:tasks[0].due_date,project_id:1,client_id:4,source};data={today,generated_at:source.retrieved_at,priorities:config.params.module==='CRM'?[]:[item],delivery_risks:config.params.module==='CRM'?[]:[item],coverage:[{tool:config.params.module==='CRM'?'crm.tasks':'pms.tasks',status:'ok',sampled:4}],limited:false,note:'Development sample only.'};}
 else if(path.includes('/suite/reports/'))data=config.params?.format==='csv'?'status,count,coverage\nTo Do,2,complete\n':{groups:[{status:config.params?.status||'To Do',count:2}],sources:[],complete:true,matched_records:2,scanned_records:2,date_basis:'due_date',retrieved_at:new Date().toISOString(),note:'Development fixture report.'};
 else if(path.endsWith('/companies'))data={items:[{id:7,name:'Acme QA customer'}]};
 else if(path.endsWith('/types'))data=[{id:2,name:'Annual leave'}];
 else if(path.endsWith('/categories'))data=[{id:1,name:'General support'}];
 else if(path.endsWith('/runs'))data={items:qaDialogueRuns};
 else if(path.endsWith('/memories'))data={items:[]};
 else if(path.endsWith('/deadline-radar'))data={today,through:dateOffset(config.params.horizon_days),generated_at:new Date().toISOString(),source:'QA fixture tasks',project:{id:1,name:'Client compliance · QA data'},config:config.params,counts:{overdue:1,today:1,upcoming:1,undated:1,later:0,completed:0},items:tasks,coverage:{scanned:4,complete:true,limit:2000}};
 else if(path.includes('/workbench/items')){if(config.method==='post'){data={id:1,...body,revision:1};artifacts=[data];if(body.kind==='rule')(window as any).__qaOperationalRules.push(body);}else if(config.method==='put'){data={...body,id:1,revision:body.revision+1};artifacts=[data];}else if(config.method==='delete'){artifacts=[];data={deleted:true};}else data={items:artifacts.length?artifacts:[{id:88,kind:'playbook',title:'Review delivery blockers',revision:1,payload:{plan:{summary:'Review priority',steps:[]}}}]};}
 else if(path.endsWith('/catalog'))data={items:[{id:'gmail',name:'Gmail',category:'Email',actions:[{name:'Search mail'}]},{id:'google_calendar',name:'Google Calendar',category:'Calendars',actions:[{name:'List events'}]}]};
 else if(path.endsWith('/connections'))data={items:[{id:1,connector_id:'gmail',name:'QA mailbox'}]};
 else if(path.endsWith('/commands')&&body.provider==='local'&&(body.text==='CRM: create a conversation task'||body.parent_run_id>=1000)){
  (window as any).__assistantQaCommands.push(body);
  const needsTitle=!body.parent_run_id||/^(yes|okay|what are my choices\??)$/i.test(body.text);
  reviewedRun={id:1000+qaDialogueRuns.length,command:body.text,status:needsTitle?'needs_clarification':'awaiting_approval',plan_hash:'0'.repeat(64),
   plan:{summary:needsTitle?'I need a title before preparing this task.':'Review the exact task before execution.',steps:needsTitle?[]:[{tool:'crm.create_task',payload:{title:body.text}}],...(needsTitle?{question:body.parent_run_id?'Please provide a short task title. This reply has not approved or executed anything.':'What title should I use?'}:{})},
   result:{request:{module:'CRM',parent_run_id:body.parent_run_id},local_nlp:{module:'CRM',intent:'tasks.create',cloud_calls:0,slots:needsTitle?{_awaiting:'title'}:{title:body.text}}},receipts:[]};
  qaDialogueRuns=[reviewedRun,...qaDialogueRuns];data=reviewedRun;
 }
 else if(path.endsWith('/commands')&&body.provider==='local'&&/all leads|todays reminder|todays jobs/i.test(body.text)){
  (window as any).__assistantQaCommands.push(body);const message=/all leads/i.test(body.text),complete=message&&body.text.includes('subject');const intent=message?'leads.message':body.text.includes('reminder')?'reminders.today':'jobs.today';
  const local:any={module:'CRM',intent,cloud_calls:0,kind:complete?'message_preview':intent==='reminders.today'?'reminders':'jobs',items:[]};
  if(complete){local.draft={channel:'email',subject:'Check-in',body:'Hello {{name}}',recipients:[{entity:'leads',id:1}]};local.preview={eligible:1,blocked:1,items:[{key:'leads:1',id:1,entity:'leads',name:'QA allowed lead',destination:'qa@example.com',eligible:true},{key:'leads:2',id:2,entity:'leads',name:'QA opted out lead',destination:'optout@example.com',eligible:false,reason:'Customer has opted out of this channel'}],channel_note:'Development simulation; no customer messages.'};}
  reviewedRun={id:1,command:body.text,status:message&&!complete?'needs_clarification':complete?'awaiting_approval':'answered',plan_hash:'0'.repeat(64),plan:{summary:complete?'No message was sent. Review the lead draft.':'Local command processed using authorized sample.',steps:complete?[{tool:'crm.send_lead_message',payload:{channel:'email',subject:'Check-in',body:'Hello {{name}}',preview_token:'private-preview-token',request_id:'private-request-id'}}]:[],...(message&&!complete?{question:'Which channel: email, WhatsApp or SMS? Supply the exact subject and message body.'}:{})},result:{request:{module:'CRM'},local_nlp:local,citations:[]},receipts:[]};data=reviewedRun;
 }
 else if(path.endsWith('/commands')){(window as any).__assistantQaCommands.push(body);const draft=!!body.local_plan?.steps?.length||body.text.startsWith('Create CRM task:');reviewedRun={id:1,command:body.text,status:draft?'awaiting_approval':'answered',plan_hash:'0'.repeat(64),plan:{summary:draft?'Review this task before execution.':`QA ${body.provider}: source-backed project summary.`,steps:body.local_plan?.steps||(draft?[{tool:'crm.create_task',payload:{title:body.text.split(':').slice(1).join(':').trim()}}]:[])},result:{citations:[{id:'s1:1',tool:'pms.tasks',record_id:1,label:tasks[0].title,href:'/pms/tasks/1',retrieved_at:new Date().toISOString()}]},receipts:[]};data=reviewedRun;}
 else if(path.endsWith('/approve')){(window as any).__qaSuiteApprovals=((window as any).__qaSuiteApprovals||0)+1;reviewedRun={...reviewedRun,status:'succeeded',receipts:[{step:1,tool:'crm.create_task',record_id:15,status:'succeeded'}]};data=reviewedRun;}
 return {data,status:200,statusText:'OK',headers:{},config};
};
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><div style={{padding:24,maxWidth:1500,margin:'0 auto'}}><p style={{marginBottom:16}}>Development QA · all records and provider responses are sample data</p><MemoryRouter initialEntries={['/ai-agents/operator?module=PMS&project=1']}><SuiteOperatorPage/></MemoryRouter></div></React.StrictMode>);
