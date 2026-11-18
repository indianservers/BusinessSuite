/** Development-only review fixture; no account, provider or approval calls. */
import React,{useState} from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import BotWorkspace from '../../src/components/ai-agents/BotWorkspace';
import {fresh} from '../../src/features/forms/formsTypes';
import '../../src/index.css';
import '../../src/components/ai-agents/action-bot.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
const id='abcdefabcdefabcdefabcdefabcdefab';
function Demo(){const [changes,setChanges]=useState<any[]>([]);
 const props:any={module:'CRM',run:{id:1,status:'awaiting_approval',plan_hash:'a'.repeat(64),command:'Synthetic view change',plan:{summary:'Review private view update',steps:[{tool:'crm.update_saved_view',payload:{view_id:id,revision:4,name:'Focus',filters:{priority:'Low'}}}]},result:{view_changes:{'1':{record_id:id,record_name:'Focus',changes:[{field:'priority',before:'High',after:'Low'}]}}}},attachments:[],selected:[],conversations:[],busy:false,openFilesRequest:0,openResultsRequest:0};
 if(new URLSearchParams(location.search).has('chain')){
  props.run.plan.steps.push({tool:'crm.update_saved_view',payload:{view_id:id,revision:4,name:'Final focus',filters:{priority:'Medium'}},depends_on:[1]});
  props.run.result.view_changes['2']={record_id:id,record_name:'Focus',changes:[{field:'name',before:'Focus',after:'Final focus'},{field:'priority',before:'Low',after:'Medium'}]};
  props.run.workflow_steps=[{step:1,tool:'crm.update_saved_view',depends_on:[],status:'pending',attempts:0},{step:2,tool:'crm.update_saved_view',depends_on:[1],status:'blocked',attempts:0}];
 }
 const formMode=new URLSearchParams(location.search).get('form');
 if(new URLSearchParams(location.search).has('restricted')){
  props.module='PMS';props.run.status=new URLSearchParams(location.search).has('waiting')?'waiting_pms':'succeeded';
  props.run.plan={summary:'Confirmed task execution; historical chat is restricted.',steps:[]};
  props.run.result={history_restricted:true};
  if(new URLSearchParams(location.search).has('remaining')){
   props.run.status='paused';props.run.result.remaining_review_prompt=`Review remaining PMS workflow #${props.run.id}`;
   props.run.result.request={module:'PMS',project_id:7};
   props.projectId=new URLSearchParams(location.search).has('differentProject')?8:7;
   props.onReviewRemaining=(prompt:string)=>setChanges([{prompt}]);
  }
  props.run.result_cards=[{id:'receipt-only',kind:'task',title:'Native task execution confirmed',body:'One native task step confirmed.',status:'succeeded',record_id:7,href:'/pms/projects/7/tasks'}];
 }
 if(new URLSearchParams(location.search).has('rebalance')){
  props.module='PMS';
  props.run.plan.steps=[{tool:'pms.task_plan',record_id:7,payload:{mode:'atomic',workload_guard:{source_sha256:'d'.repeat(64),start:'2026-11-16',weeks:1,scope:'workspace'},plan:{summary:'Review assignment change',steps:[{tool:'update_task',task_id:42,changes:{assignee_user_ids:[3]}}]}}}];
  props.run.result={rebalance_request:{review:{project_id:7,source_sha256:'d'.repeat(64),limitations:['Visible workload only; this is not a capacity reservation.'],changes:[{task_id:42,before_assignee_user_ids:[2],after_assignee_user_ids:[3],weeks:[{week_start:'2026-11-16',moved_hours:10,source_before_hours:30,source_after_hours:20,target_before_hours:5,target_after_hours:15,target_snapshot_capacity_hours:40}]}]}}};
  if(new URLSearchParams(location.search).has('stale'))props.run.result.rebalance_request.review.source_sha256='e'.repeat(64);
  if(new URLSearchParams(location.search).has('provider')){
   props.run.result.rebalance_review=props.run.result.rebalance_request.review;
   delete props.run.result.rebalance_request;
  }
 }
 if(new URLSearchParams(location.search).has('timerStart')){
  props.module='PMS';props.run.plan.steps=[{tool:'pms.start_timer',record_id:7,payload:{session_key:'11111111-1111-4111-8111-111111111111',source_sha256:'c'.repeat(64),task_id:null,timezone:'UTC',description:'Synthetic timer intention',is_billable:false}}];
  props.run.result={timer_changes:{'1':{record_id:'synthetic-session',record_name:'Your native timer',changes:[{field:'timer',before:null,after:{task_id:null,timezone:'UTC',description:'Synthetic timer intention',is_billable:false}},{field:'effect',before:null,after:'Starts when executed on the server. Running time is not recorded until a reviewed stop.'}]}}};
 }
 if(new URLSearchParams(location.search).has('timer')){
  props.module='PMS';props.run.plan.steps=[{tool:'pms.discard_timer',record_id:7,payload:{session_key:'b'.repeat(32),source_sha256:'c'.repeat(64)}}];
  props.run.result={timer_changes:{'1':{record_id:'synthetic-session',record_name:'Your native timer',changes:[{field:'timer',before:{active:true,task_id:42},after:{active:false}},{field:'effect',before:null,after:'Stops this session without creating a time entry; unrecorded elapsed time is discarded.'}]}}};
 }
 if(new URLSearchParams(location.search).has('time')){
  props.module='PMS';props.run.plan.steps=[{tool:'pms.edit_time_log',record_id:7,payload:{log_id:42,source_sha256:'b'.repeat(64),log_date:'2026-05-04',duration_minutes:90,description:'Synthetic work',is_billable:false,task_id:null}}];
  props.run.result={time_changes:{'1':{record_id:42,record_name:'Personal manual time entry',changes:[{field:'duration_minutes',before:45,after:90},{field:'owner',before:null,after:'Current user only'},{field:'approval_status',before:'Pending',after:'Pending; this does not approve a timesheet or invoice the customer'}]}}};
 }
 if(new URLSearchParams(location.search).has('calendar')){
  props.module='PMS';props.run.plan.steps=[{tool:'pms.edit_calendar_event',payload:{event_id:42,revision:1,source_sha256:'b'.repeat(64),sync_policy_sha256:'c'.repeat(64),title:'Synthetic meeting',start_at:'2026-12-01T10:00:00Z',end_at:'2026-12-01T11:00:00Z',timezone:'UTC',kind:'meeting',description:'Synthetic agenda',visibility:'private'}}];
  props.run.result={calendar_changes:{'1':{record_id:42,record_name:'Synthetic meeting',changes:[{field:'start_at',before:'2026-12-01T09:00:00Z',after:'2026-12-01T10:00:00Z'},{field:'audience',before:null,after:'Owner private calendar'},{field:'calendar_sync',before:null,after:'Existing calendar sync may propagate changes. Google calendar connection #7'}]}}};
 }
 if(new URLSearchParams(location.search).has('pms')){
  props.module='PMS';props.run.plan.steps=[{tool:'pms.update_saved_view',payload:{project_id:7,view_id:42,source_sha256:'b'.repeat(64),name:'Focus',filters:{priority:'Low'}}}];
  props.run.result.view_changes['1'].record_id=42;
 }
 if(formMode){const definition=fresh();definition.name='Customer intake';definition.settings!.public=true;
  props.run.plan.steps=[{tool:'crm.'+(formMode==='publish'?'publish':'create')+'_form',payload:formMode==='publish'?{form_id:42,expected_revision:3,source_sha256:'b'.repeat(64)}:definition}];
  props.run.result={form_reviews:{'1':{operation:formMode,definition,audience:'Anyone with the public link',form_id:formMode==='publish'?42:null,effect:formMode==='publish'?'Publish this exact draft and open intake for the stated audience':'Save a closed, unpublished native draft',changes:[]}}};
 }
 for(const name of ['onDownloadSource','onUseAgent','onUseTemplate','onOpenConversation','onEditArtifact','onAskDashboard','onAskShared','onUpdate','onSelect','onDirty','onUpload','onDelete','onDownload','onPrepare','onTranscribe','onImageReference'])props[name]=()=>{};
 props.onRevise=async(value:any[])=>{setChanges(value);return true};
 return <><BotWorkspace {...props}/><pre data-testid="saved-revision">{JSON.stringify(changes)}</pre></>;
}
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter><Demo/></MemoryRouter>);
