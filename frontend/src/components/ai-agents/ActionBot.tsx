import type {FormReview} from './FormDraftReview';
import MediaFailure,{type MediaError} from './MediaFailure';
import {useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Link,useLocation} from 'react-router-dom';
import {Bot,Check,ChevronDown,ExternalLink,Loader2,Maximize2,Minimize2,Plus,RefreshCw,Send,ShieldCheck,X} from 'lucide-react';
import BotWorkspace,{type BotAttachment,type DraftChange} from './BotWorkspace';
import {api} from '@/services/api';
import {useAuthStore} from '@/store/authStore';
import {actionBotContext} from './action-bot-context';
import './action-bot.css';
import AgentMemory from './AgentMemory';
import EventMessageCitation from './EventMessageCitation';
import { FallbackChoice, FallbackAttempts } from './ProviderFallback';
import TaskRoutingBasis from './TaskRoutingBasis';

export type Run={pms_previews?:Record<string,{manual?:string[]}>;id:number;status:string;plan_hash:string;command:string;can_resume?:boolean;result_cards?:{id:string;kind:string;title:string;artifact_id?:number;body?:string;status:string;record_id?:number|string;href?:string}[];workflow_steps?:{step:number;tool:string;depends_on:number[];status:string;attempts:number}[];plan?:{summary:string;question?:string;steps:{tool:string;payload:Record<string,unknown>;record_id?:unknown;depends_on?:number[]}[]};receipts?:{step:number;tool:string;artifact_id?:number;artifact_revision?:number;record_id?:number|string;delivery_counts?:Record<string,number>}[];result?:{history_restricted?:boolean;remaining_review_prompt?:string;request?:{project_id?:number|null;module?:string};rebalance_review?:import('./WorkloadRebalanceReview').RebalanceReview;rebalance_request?:{review?:import('./WorkloadRebalanceReview').RebalanceReview};timer_changes?:Record<string,{record_id:number|string;record_name?:string;changes:{field:string;before:unknown;after:unknown}[]}>;time_changes?:Record<string,{record_id:number|string;record_name?:string;changes:{field:string;before:unknown;after:unknown}[]}>;calendar_changes?:Record<string,{record_id:number|string;record_name?:string;changes:{field:string;before:unknown;after:unknown}[]}>;form_reviews?:Record<string,FormReview>;view_changes?:Record<string,{record_id:string;record_name?:string;changes:{field:string;before:unknown;after:unknown}[]}>;media_error?:MediaError;milestone_changes?:Record<string,{record_id:number;changes:{field:string;before:unknown;after:unknown}[]}>;ticket_changes?:Record<string,{record_id:number;changes:{field:string;before:unknown;after:unknown}[]}>;profile_changes?:Record<string,{record_id:number;changes:{field:string;before:unknown;after:unknown}[]}>;recovery?:{format:string;source_run_id:number;source_plan_hash:string;targets?:{tool:string;record_id:number;changes?:{field:string;current:unknown;restore:unknown}[]}[]};feedback?:{revision:number;rating:string;correction:string};citations?:{id:string;label:string;href:string}[];checkpoint?:{retry_at?:string|null}};error_code?:string};
type Turn={key:string;role:'user'|'assistant';text:string;run?:Run};
const ROOT='/ai-operator/suite';
const active=new Set(['queued','planning','executing','waiting_pms','cancelling']);
const errorText=(error:any)=>typeof error?.response?.data?.detail==='string'?error.response.data.detail:error?.response?.status===403?'Your account does not have permission to use this assistant.':'The module service could not finish this request. Your text is preserved; retry to recover the same request.';
const reviewValue=(value:unknown):string=>value&&typeof value==='object'&&'$step' in value?`Record created by step ${String((value as any).$step)}`:typeof value==='object'?JSON.stringify(value):String(value);

export default function ActionBot(){
 const user=useAuthStore(s=>s.user);const location=useLocation();
 const [open,setOpen]=useState(false),[opened,setOpened]=useState(false),[revision,setRevision]=useState(0);
 const trigger=useRef<HTMLButtonElement>(null);const id=useId();
 const context=actionBotContext(location.pathname,location.search);
 const requestedConversation=Number(new URLSearchParams(location.search).get('bot_conversation'));
 const initialConversation=Number.isSafeInteger(requestedConversation)&&requestedConversation>0?requestedConversation:undefined;
 useEffect(()=>{if(initialConversation){setOpened(true);setOpen(true)}},[initialConversation]);
 const company=useRef(user?.access?.companyId);
 useEffect(()=>{const next=user?.access?.companyId;if(company.current!=null&&next!=null&&company.current!==next){setOpen(false);setOpened(false);setRevision(v=>v+1)}company.current=next},[user?.access?.companyId]);
 useEffect(()=>{const reset=()=>{setOpen(false);setOpened(false);setRevision(v=>v+1)};window.addEventListener('suite:organization-changed',reset);window.addEventListener('suite:branch-changed',reset);return()=>{window.removeEventListener('suite:organization-changed',reset);window.removeEventListener('suite:branch-changed',reset)}},[]);
 if(!user)return null;
 const scope=[user.id,revision,location.pathname,location.search].join(':');
 function close(){setOpen(false);trigger.current?.focus()}
 return createPortal(<div className="suite-action-bot">
  <button ref={trigger} type="button" className="action-bot-launcher" aria-label={open?'Minimize action bot':'Open action bot'} aria-expanded={open} aria-controls={id} title="Action bot" onClick={()=>{setOpened(true);setOpen(v=>!v)}}><Bot size={23} strokeWidth={1.8}/><span className="action-bot-dot"/></button>
  {opened&&<BotPanel key={scope} id={id} open={open} close={close} context={context} initialConversation={initialConversation}/>}
 </div>,document.body);
}

function BotPanel({id,open,close,context,initialConversation}:{initialConversation?:number;id:string;open:boolean;close:()=>void;context:ReturnType<typeof actionBotContext>}){
 const [turns,setTurns]=useState<Turn[]>([]),[current,setCurrent]=useState<Run|null>(null),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [access,setAccess]=useState<'checking'|'allowed'|'denied'>('checking');
 const [provider,setProvider]=useState('preferred');
 const [fallbackProvider,setFallbackProvider]=useState('');
 const pendingFallback=!!current&&['needs_clarification','awaiting_approval'].includes(current.status);
 const fallbackChoice=pendingFallback?((current?.result as any)?.request?.fallback_provider||''):fallbackProvider;
 const [providers,setProviders]=useState<any[]>([]);
 const [agentId,setAgentId]=useState<number|null>(null);
 const [intelligence,setIntelligence]=useState<any>(null);
 const planningRetry=useRef<{id:number;provider:string;key:string}|null>(null);
 const [expanded,setExpanded]=useState(!!initialConversation),[mobilePane,setMobilePane]=useState<'chat'|'workspace'>('chat'),[dirty,setDirty]=useState(false);
 const [attachments,setAttachments]=useState<BotAttachment[]>([]),[selectedAttachments,setSelectedAttachments]=useState<number[]>([]);
 const revisionRequest=useRef<{signature:string;key:string}|null>(null);
 const [openFilesRequest,setOpenFilesRequest]=useState(0);
 const [openResultsRequest,setOpenResultsRequest]=useState(0);
 const [artifactCitation,setArtifactCitation]=useState<{id:number;revision?:number}|null>(null);
 const [sharedCitation,setSharedCitation]=useState<{id:number;edition:number}|null>(null);
 const [conversationId,setConversationId]=useState<number|null>(null),[conversations,setConversations]=useState<{id:number;title:string}[]>([]),[loadingHistory,setLoadingHistory]=useState(true);
 useEffect(()=>{setArtifactCitation(null);setSharedCitation(null)},[conversationId,current?.id]);
 const chatId=useRef<number|null>(null);
 const input=useRef<HTMLTextAreaElement>(null),end=useRef<HTMLDivElement>(null),live=useRef(true),latest=useRef<Run|null>(null);
 const pending=useRef<{signature:string;key:string}|null>(null);
 const focusedModule=current&&['needs_clarification','awaiting_approval'].includes(current.status)?(current.result as any)?.request?.module||context.module:context.module;
 const label=focusedModule==='SRM'?'Sales':focusedModule||'Business Suite';
 const query=new URLSearchParams({...(context.module?{module:context.module}:{}),...(context.workspace_id?{workspace:String(context.workspace_id)}:{}),...(context.project_id?{project:String(context.project_id)}:{})}).toString();
 function restore(data:any){
  chatId.current=data.id;setConversationId(data.id);
  const runs:Run[]=data.runs||[];
  setTurns(runs.flatMap(run=>[{key:`${run.id}-user`,role:'user' as const,text:run.command},{key:`${run.id}-assistant`,role:'assistant' as const,text:run.plan?.summary||'Request received.',run}]));
  const last=runs.at(-1)||null;setAgentId((last?.result as any)?.request?.agent_id||null);latest.current=last;setCurrent(last);setText('');setError('');pending.current=null;
  const files:BotAttachment[]=data.attachments||[];
  setAttachments(files);setSelectedAttachments(((last?.result as any)?.request?.attachment_ids||[]).filter((id:number)=>files.some(file=>file.id===id&&!file.media)));setDirty(false);revisionRequest.current=null;
  const savedProvider=(last?.result as any)?.request?.requested_provider||(last?.result as any)?.request?.provider;if(['preferred','local','gemini','openai','claude'].includes(savedProvider))setProvider(savedProvider);
 }
 async function loadConversation(id:number){setBusy(true);setError('');try{const r=await api.post(`${ROOT}/conversations/${id}/resume`);if(live.current)restore(r.data)}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 useEffect(()=>{live.current=true;const abort=new AbortController();
  async function load(url:string,params?:Record<string,unknown>){
   for(let attempt=0;;attempt++){
    try{return await api.get(url,{params,signal:abort.signal})}catch(e:any){
     const delay=Number(e?.response?.headers?.['retry-after']??1);
     if(abort.signal.aborted||e?.response?.status!==429||attempt>=2||!Number.isFinite(delay)||delay<0||delay>10)throw e;
     await new Promise<void>((resolve,reject)=>{
      const cancel=()=>{clearTimeout(timer);reject(new Error('Bot initialization cancelled'))};
      const timer=setTimeout(()=>{abort.signal.removeEventListener('abort',cancel);resolve()},delay*1000);
      abort.signal.addEventListener('abort',cancel,{once:true});
     });
    }
   }
  }
  load(ROOT+'/tools').then(()=>{if(live.current)setAccess('allowed')}).catch(e=>{if(!abort.signal.aborted&&live.current){setAccess('denied');setError(errorText(e))}});
  load(ROOT+'/intelligence',{module:context.module,workspace_id:context.workspace_id}).then(r=>{if(live.current)setIntelligence(r.data)}).catch(()=>{});
  load(ROOT+'/providers',{workspace_id:context.workspace_id}).then(r=>{if(live.current)setProviders(r.data.items||[])}).catch(()=>{});
  load(ROOT+'/conversations',{workspace_id:context.workspace_id}).then(async r=>{if(!live.current||abort.signal.aborted)return;const items=r.data.items||[];setConversations(items);if(initialConversation||items.length){const response=await load(`${ROOT}/conversations/${initialConversation||items[0].id}`);if(live.current&&!abort.signal.aborted)restore(response.data)}}).catch(e=>{if(!abort.signal.aborted&&live.current)setError(errorText(e))}).finally(()=>{if(live.current&&!abort.signal.aborted)setLoadingHistory(false)});
  return()=>{live.current=false;abort.abort()};
 },[]);
 useEffect(()=>{if(open&&access==='allowed'&&!busy)input.current?.focus();const escape=(e:KeyboardEvent)=>{if(open&&e.key==='Escape'){e.stopPropagation();close()}};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape)},[open,access,busy]);
 useEffect(()=>{if(open)end.current?.scrollIntoView({block:'nearest'})},[open,turns.length,current?.status,busy]);
 function update(run:Run){latest.current=run;setCurrent(run);setTurns(old=>old.map(t=>t.run?.id===run.id?{...t,run}:t))}
 useEffect(()=>{if(!open||!current||!active.has(current.status))return;const ident=current.id;let mounted=true;
  const poll=()=>api.get(`${ROOT}/runs/${ident}`,{progress:false}).then(r=>{if(mounted&&live.current&&latest.current?.id===ident)update(r.data)}).catch(e=>{if(mounted&&live.current)setError(errorText(e))});
  void poll();const timer=setInterval(poll,2000);return()=>{mounted=false;clearInterval(timer)};
 },[open,current?.id,current?.status]);
 function fresh(){setFallbackProvider('');setAgentId(null);setProvider('preferred');setTurns([]);setCurrent(null);latest.current=null;chatId.current=null;setConversationId(null);setAttachments([]);setSelectedAttachments([]);setDirty(false);setText('');setError('');pending.current=null;revisionRequest.current=null;input.current?.focus()}
 async function ensureChat(title:string){
  if(chatId.current)return chatId.current;
  const created=await api.post(ROOT+'/conversations',{title:title.replace(/\s+/g,' ').trim().slice(0,160)||'New conversation',workspace_id:context.workspace_id||null});
  if(!live.current)return null;
  chatId.current=created.data.id;setConversationId(created.data.id);setConversations(old=>[created.data,...old]);return created.data.id;
 }
 async function uploadFiles(list:FileList|null){
  const files=Array.from(list||[]);if(!files.length||busy||loadingHistory)return;setBusy(true);setError('');
  try{const id=await ensureChat(files[0].name);if(!id)return;
   for(const file of files){const form=new FormData();form.append('file',file);const r=await api.post(`${ROOT}/conversations/${id}/attachments`,form,{headers:{'Content-Type':'multipart/form-data'},timeout:90000});if(!live.current)return;setAttachments(old=>[...old.filter(a=>a.id!==r.data.id),r.data]);setSelectedAttachments(old=>r.data.media?old.filter(id=>id!==r.data.id):Array.from(new Set([...old,r.data.id])))}
  }catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}
 }
 async function deleteFile(id:number){if(!chatId.current||busy)return;setBusy(true);setError('');try{await api.delete(`${ROOT}/conversations/${chatId.current}/attachments/${id}`);if(live.current){setAttachments(old=>old.filter(a=>a.id!==id));setSelectedAttachments(old=>old.filter(n=>n!==id))}}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 async function downloadFile(file:Pick<BotAttachment,'id'|'name'>,sourceConversationId?:number){const ownerConversation=sourceConversationId||chatId.current;if(!ownerConversation||busy)return;setBusy(true);setError('');try{const r=await api.get(`${ROOT}/conversations/${ownerConversation}/attachments/${file.id}/download`,{responseType:'blob'});if(!live.current)return;const url=URL.createObjectURL(r.data);const a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 async function revise(changes:DraftChange[]){
  if(!current||busy)return false;const ident=current.id;const signature=JSON.stringify({ident,plan_hash:current.plan_hash,changes});
  if(revisionRequest.current?.signature!==signature)revisionRequest.current={signature,key:crypto.randomUUID()};
  setBusy(true);setError('');try{const {data}=await api.post<Run>(`${ROOT}/runs/${ident}/revise`,{request_key:revisionRequest.current.key,plan_hash:current.plan_hash,changes},{timeout:90000});if(!live.current)return false;
   setTurns(old=>[...old,{key:crypto.randomUUID(),role:'assistant',text:data.plan?.summary||'Edited draft prepared.',run:data}]);latest.current=data;setCurrent(data);revisionRequest.current=null;setDirty(false);return data.status==='awaiting_approval';
  }catch(e){if(live.current)setError(errorText(e));return false}finally{if(live.current)setBusy(false)}
 }
 async function act(action:'approve'|'cancel'|'resume'){
  if(!current||busy||dirty)return false;const ident=current.id;setBusy(true);setError('');
  try{const r=await api.post(`${ROOT}/runs/${ident}/${action}`,action==='cancel'?undefined:{plan_hash:current.plan_hash});if(live.current)update(r.data);return true}catch(e){if(live.current)setError(errorText(e));return false}finally{if(live.current)setBusy(false)}
 }
 async function send(){
  if(current?.result?.history_restricted){setError("Start a new conversation for further work. This view contains confirmed execution details only.");return}
  const value=text.trim();if(!value||busy||dirty||loadingHistory||access!=='allowed'||current&&active.has(current.status))return;
  if(/^(?:please\s+)?(?:(?:start|begin|open)\s+(?:a\s+)?(?:new|fresh|separate)|new)\s+(?:conversation|chat|request)[.!? ]*$/i.test(value)){fresh();return}
  if(current?.status==='awaiting_approval'&&/^(?:yes|approve|confirm|go ahead|do it|yes proceed|please go ahead|approve this action)[.! ]*$/i.test(value)){const approved=await act('approve');if(approved&&live.current)setText('');return}
  if(current?.can_resume&&/^(?:please\s+)?(?:resume|retry|continue)(?:\s+(?:the\s+)?(?:workflow|remaining (?:steps|actions)|paused workflow))?[.! ]*$/i.test(value)){const resumed=await act('resume');if(resumed&&live.current)setText('');return}
  if(provider==='local'&&/^FAM\s*:/i.test(value)){setError('Finance requires an enabled connected provider. Choose Gemini or OpenAI for this request.');return}
  const following=current&&chatId.current;
  const pendingModule=current&&['needs_clarification','awaiting_approval'].includes(current.status)?(current.result as any)?.request?.module:undefined;
  const body={text:value,provider,...(provider!=='local'&&fallbackChoice?{fallback_provider:fallbackChoice}:{}),agent_id:agentId,module:pendingModule||context.module,attachment_ids:selectedAttachments,workspace_id:context.workspace_id||null,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,mode:'auto',...(following?{parent_run_id:current.id}:{project_id:context.project_id||null})};
  const signature=JSON.stringify(body);if(pending.current?.signature!==signature)pending.current={signature,key:crypto.randomUUID()};
  setBusy(true);setError('');
  try{
   if(!await ensureChat(value))return;
   const {data}=await api.post<Run>(ROOT+'/commands',{...body,conversation_id:chatId.current,request_key:pending.current.key},{timeout:90000});if(!live.current)return;
   setTurns(old=>[...old,{key:crypto.randomUUID(),role:'user',text:value},{key:crypto.randomUUID(),role:'assistant',text:data.plan?.summary||'Request received.',run:data}]);
   latest.current=data;setCurrent(data);setText('');pending.current=null;
  }catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}
 }
 async function chooseIntelligence(value:string){setError('');try{const r=await api.put(ROOT+'/intelligence',{provider:value,module:context.module||null,workspace_id:context.workspace_id||null});if(live.current){setIntelligence(r.data);setProvider(value);setFallbackProvider('')}}catch(e){if(live.current)setError(errorText(e))}}
 async function retryPlanning(fallback=false){if(!current||busy)return;const choice=fallback?'local':'original';if(planningRetry.current?.id!==current.id||planningRetry.current.provider!==choice)planningRetry.current={id:current.id,provider:choice,key:crypto.randomUUID()};setBusy(true);setError('');try{const {data}=await api.post<Run>(`${ROOT}/runs/${current.id}/retry-planning`,{request_key:planningRetry.current.key,provider:choice},{timeout:90000});if(!live.current)return;setTurns(old=>[...old,{key:crypto.randomUUID(),role:'assistant',text:data.plan?.summary||'Planning attempt saved.',run:data}]);latest.current=data;setCurrent(data);setProvider((data.result as any)?.request?.provider||provider);setText('');planningRetry.current=null}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 useEffect(()=>{if(!current)return;let mounted=true;api.get(ROOT+'/intelligence',{params:{module:context.module,workspace_id:context.workspace_id}}).then(r=>{if(mounted&&live.current)setIntelligence(r.data)}).catch(()=>{});return()=>{mounted=false}},[current?.id,current?.status]);
 const resolvedProvider=provider==='preferred'?intelligence?.selected_provider:provider;
 const health=intelligence?.items?.find((p:any)=>p.provider===resolvedProvider);
 const readyProvider=provider==='preferred'?!!intelligence?.selected_provider:provider==='local'||providers.some(p=>p.provider===provider&&p.enabled&&p.data_sharing_allowed);
 function reviewRemaining(prompt:string){fresh();setProvider('local');setText(prompt);setMobilePane('chat');input.current?.focus()}
 const remainingPrompt=current?.result?.history_restricted&&current.status==='paused'&&(context.project_id==null||context.project_id===current.result.request?.project_id)?current.result.remaining_review_prompt:undefined;
 const disabled=busy||dirty||loadingHistory||access!=='allowed'||!readyProvider||!!current?.result?.history_restricted||!!current&&active.has(current.status);
 const prompts=context.module==='PMS'?['What are today’s project jobs?','Create a project called Customer launch with tasks Design, Build and Test','Create a project task called Release with subtasks Build, Review and Deploy']:context.module==='HRMS'?['Show my leave balance','Apply for leave','Create an HR ticket']:context.module==='SRM'?['Show unpaid invoices','Show invoices due today','Summarize sales records']:context.module==='FAM'?['Summarize financial records','Prepare a voucher draft']:['What are todays jobs?','Create tasks for Call customer, Review quote and Confirm delivery','Send a message to all leads'];
 return <section id={id} hidden={!open} role="dialog" aria-modal="false" aria-labelledby={id+'-title'} className={`action-bot-panel ${expanded?'action-bot-expanded':''}`}>
  <header><span className="action-bot-avatar"><Bot size={23}/></span><div><h2 id={id+'-title'}>Action bot</h2><span>{label}{context.project_id?` · Project #${context.project_id}`:''}</span></div><button type="button" aria-label={expanded?'Collapse bot workspace':'Expand bot workspace'} disabled={dirty} onClick={()=>{setExpanded(v=>!v);setMobilePane('workspace')}}>{expanded?<Minimize2 size={18}/>:<Maximize2 size={18}/>}</button><button type="button" aria-label="New bot conversation" title="New conversation" onClick={fresh} disabled={busy||dirty||loadingHistory}><Plus size={18}/></button><button type="button" aria-label="Close action bot" onClick={close}><X size={18}/></button></header>
  <div className="action-bot-toolbar"><ShieldCheck size={14}/><span>{agentId?`Agent #${agentId} · Review required`:'Actions need your review'}</span><label><span className="sr-only">Bot intelligence</span><select aria-label="Bot intelligence" disabled={busy||!!current} value={provider} onChange={e=>void chooseIntelligence(e.target.value)}><option value="preferred">Server default{intelligence?.selected_provider?` · ${intelligence.selected_provider}`:''}</option>{context.module!=='FAM'&&<option value="local">Local intelligence</option>}<option value="gemini">Gemini API</option><option value="openai">OpenAI API</option><option value="claude">Claude API</option></select><ChevronDown size={12}/></label></div>
  <FallbackChoice primary={resolvedProvider||provider} value={fallbackChoice} providers={providers} disabled={busy||pendingFallback} onChange={setFallbackProvider}/>
  <FallbackAttempts value={(current?.result as any)?.provider_routing}/>
  <TaskRoutingBasis value={(current?.result as any)?.routing} fallbackUsed={(current?.result as any)?.provider_routing?.fallback_used}/>
  {health&&<details className="action-bot-toolbar"><summary>Provider health · {health.provider}</summary><span>Model: {health.model} · Connectivity: {health.connectivity.status} · Planning: {health.planning.status}. Tests and planning are measured separately.</span></details>}
  <div className="action-bot-toolbar"><label htmlFor={id+'-history'}>Conversations</label><select id={id+'-history'} aria-label="Saved bot conversations" value={conversationId||''} disabled={busy||dirty||loadingHistory} onChange={e=>e.target.value?void loadConversation(Number(e.target.value)):fresh()}><option value="">New conversation</option>{conversations.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>{conversationId&&<button type="button" aria-label="Reload saved conversation" title="Reload latest reply" disabled={busy||loadingHistory} onClick={()=>void loadConversation(conversationId)}><RefreshCw size={13}/></button>}</div>
  {expanded&&<div className="bot-mobile-tabs"><button type="button" aria-pressed={mobilePane==='chat'} onClick={()=>setMobilePane('chat')}>Conversation</button><button type="button" aria-pressed={mobilePane==='workspace'} onClick={()=>setMobilePane('workspace')}>Workspace</button></div>}
  <div className={`action-bot-body mobile-${mobilePane}`}><div className="action-bot-chat">
  <div className="action-bot-messages" aria-live="polite" aria-relevant="additions text">
  <AgentMemory module={focusedModule} workspaceId={context.workspace_id} projectId={focusedModule==='PMS'?((current?.result as any)?.request?.project_id||context.project_id):undefined} revision={current?.id}/>
   {!turns.length&&<div className="action-bot-welcome"><span className="action-bot-welcome-icon"><Bot size={30}/></span><h3>What can I help you do?</h3><p>Ask a question or describe an action. I’ll ask for missing details and show the exact changes before execution.</p><div>{prompts.map(prompt=><button type="button" key={prompt} onClick={()=>{setText(prompt);input.current?.focus()}}>{prompt}<span>↗</span></button>)}{(!context.module||['CRM','PMS','HRMS'].includes(context.module))&&<button type="button" onClick={()=>{setText('Create a customer follow-up called Customer follow-up, then add a project task called Delivery recovery, then raise an HR ticket called Staffing support');input.current?.focus()}}>Create a CRM → PMS → HRMS workflow<span>↗</span></button>}</div></div>}
   {turns.map(turn=><div key={turn.key} className={'action-bot-message '+turn.role}><small>{turn.role==='user'?'You':'Action bot'}</small><p>{turn.run?.status==='succeeded'?'Reviewed action processing completed. See the receipts below.':turn.text}</p>{turn.run?.plan?.question&&<p className="action-bot-question">{turn.run.plan.question}</p>}{turn.run?.result?.citations?.length?<div className="action-bot-citations">{turn.run.result.citations.slice(0,5).map(source=>{const bound=source.href.match(/^\/api\/v1\/ai-operator\/suite\/conversations\/([1-9]\d*)\/attachments\/([1-9]\d*)\/download$/);return source.href.startsWith('#bot-event-message:')?<EventMessageCitation key={source.id} source={source} disabled={dirty||busy}/>:bound?<button type="button" key={source.id} disabled={dirty||busy} onClick={()=>void downloadFile({id:Number(bound[2]),name:source.label},Number(bound[1]))}>{source.label}<ExternalLink size={11}/></button>:source.href.startsWith('#bot-shared-artifact-')?<button type="button" key={source.id} disabled={dirty} onClick={()=>{const match=source.id.match(/(?:^|:)shared-artifact:([1-9]\d*):e([1-9]\d*)(?::p([1-6]))?$/);if(match){setSharedCitation({id:Number(match[1]),edition:Number(match[2])});setArtifactCitation(null);setExpanded(true);setMobilePane('workspace');setOpenResultsRequest(n=>n+1)}}}>{source.label}<ExternalLink size={11}/></button>:source.href.startsWith('#bot-artifact-')?<button type="button" key={source.id} disabled={dirty} onClick={()=>{setSharedCitation(null);const match=source.id.match(/(?:^|:)artifact:([1-9]\d*):v([1-9]\d*)$/);const fallback=source.href.match(/^#bot-artifact-([1-9]\d*)$/);if(match||fallback)setArtifactCitation({id:Number(match?.[1]||fallback?.[1]),revision:match?Number(match[2]):undefined});setExpanded(true);setMobilePane('workspace');setOpenResultsRequest(n=>n+1)}}>{source.label}<ExternalLink size={11}/></button>:source.href.startsWith('#bot-attachment-')?<button type="button" key={source.id} disabled={dirty} onClick={()=>{setExpanded(true);setMobilePane('workspace');setOpenFilesRequest(n=>n+1)}}>{source.label}<ExternalLink size={11}/></button>:<Link key={source.id} to={source.href}>{source.label}<ExternalLink size={11}/></Link>})}</div>:null}</div>)}
   {current?.status==='answered'&&(current.result as any)?.message_read_query&&((current.result as any)?.message_action_options||((current.result as any)?.message_task_available?[{module:'source',label:'Draft task from this message',prompt:'Create a task from this message'}]:[])).map((option:{module:string;label:string;prompt:string})=><button key={option.module} type="button" className="action-bot-review" disabled={disabled} onClick={()=>{setText(option.prompt);input.current?.focus()}}>{option.label}</button>)}
   {!!current?.workflow_steps?.length&&current.workflow_steps.length>1&&<div className="action-bot-workflow"><strong>Workflow progress</strong><ol aria-label="Workflow steps">{current.workflow_steps.map(step=><li key={step.step}><div><span>{step.step}. {step.tool.replace(/[._]/g,' ')}</span><b>{step.status.replace(/_/g,' ')}</b></div><small>{step.depends_on.length?`After step ${step.depends_on.join(', ')}`:'Ready first'}{step.attempts?` · ${step.attempts} attempt${step.attempts===1?'':'s'}`:''}</small></li>)}</ol></div>}
   {current?.result?.checkpoint?.retry_at&&<p role="status">Waiting to retry a read before dispatch. Completed actions will not repeat.</p>}
   {current?.result?.media_error&&<MediaFailure error={current.result.media_error}/>}
   {current?.can_resume&&!current.result?.history_restricted&&<button type="button" className="action-bot-approve" disabled={busy} onClick={()=>void act('resume')}><RefreshCw size={16}/>Resume remaining reviewed actions</button>}
   {current?.plan?.steps?.length?<div className="action-bot-review"><strong>Review {current.plan.steps.length===1?'this action':'these actions'}</strong>{current.plan.steps.map((step,i)=><div key={i}><span>{step.tool.replace(/[._]/g,' ')}</span>{step.record_id!=null&&<small>Record {reviewValue(step.record_id)}</small>}<dl>{Object.entries(step.payload).filter(([k])=>!['preview_token','request_key','request_id','expected_version','expected_revision','media_policy_sha256'].includes(k)).map(([k,v])=><div key={k}><dt>{k.replace(/_/g,' ')}</dt><dd>{reviewValue(v)}</dd></div>)}</dl></div>)}{current.status==='awaiting_approval'&&<button type="button" className="action-bot-approve" disabled={busy||dirty} onClick={()=>void act('approve')}><Check size={16}/>Approve these exact actions</button>}</div>:null}
   {current?.receipts?.map(receipt=><p className="action-bot-receipt" key={receipt.step}><Check size={14}/>{receipt.tool.replace(/[._]/g,' ')} · {receipt.delivery_counts?Object.entries(receipt.delivery_counts).map(([s,n])=>`${n} ${s}`).join(', '):receipt.record_id?`record #${receipt.record_id}`:'Processed'}</p>)}
   {current&&<div className="action-bot-status">{current.status.replace(/_/g,' ')}{(!current.result?.history_restricted&&['needs_clarification','awaiting_approval','paused',...active].includes(current.status))&&<button disabled={busy} type="button" onClick={()=>void act('cancel')}>Cancel remaining work</button>}</div>}
   {current?.result?.history_restricted&&<section className="action-bot-review" aria-label="Restricted conversation history"><p>Only confirmed execution details are available. Start a new conversation for further work.</p><p>Workflow #{current.id}</p>{remainingPrompt&&<><p>Prepare a fresh request for the remaining tasks. Send it and review the actions before approving.</p><button type="button" className="action-bot-approve" disabled={busy||dirty} onClick={()=>reviewRemaining(remainingPrompt)}>Review remaining tasks</button></>}<button type="button" className="action-bot-approve" disabled={busy||dirty||active.has(current.status)} onClick={fresh}>Start new conversation</button></section>}
   {current?.error_code&&<p role="alert">{(current.result as any)?.planning_issue||current.error_code}. Completed receipts are retained; uncertain work will not be repeated automatically.</p>}
   {(current?.result as any)?.can_retry_planning&&current?.status==='failed'&&<div className="action-bot-review"><p>Your original message and selected sources are saved on the server.</p><button type="button" disabled={busy} onClick={()=>void retryPlanning()}>Retry planning</button>{(current.result as any)?.request?.module!=='FAM'&&(current.result as any)?.request?.provider!=='local'&&<button type="button" disabled={busy} onClick={()=>void retryPlanning(true)}>Try local intelligence</button>}</div>}
   {busy&&<p className="action-bot-thinking" role="status"><Loader2 size={15} className="animate-spin"/>Checking your request…</p>}<div ref={end}/>
  </div>
  {error&&<p role="alert" className="action-bot-error">{error}</p>}
  {!readyProvider&&<p className="action-bot-error">This provider is not enabled for this workspace. Choose a connected provider in the assistant settings.</p>}
  <form className="action-bot-compose" onSubmit={e=>{e.preventDefault();void send()}}><textarea ref={input} aria-label="Message action bot" rows={2} maxLength={6000} disabled={disabled} value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void send()}}} placeholder={access==='checking'?'Checking access…':'Ask or tell me what to do…'}/><button type="submit" aria-label="Send bot message" disabled={disabled||!text.trim()}><Send size={18}/></button></form>
  <footer><span>{(current?.result as any)?.intelligence?.engine==='server'?'Server workflow':resolvedProvider==='local'?'Runs on your server':`${(current?.result as any)?.intelligence?.provider||resolvedProvider||'Checking intelligence'} API${(current?.result as any)?.intelligence?.model?`  /  ${(current?.result as any).intelligence.model}`:''}`} · {label}</span><Link to={'/ai-agents/operator'+(query?'?'+query:'')}>Advanced controls <ExternalLink size={12}/></Link></footer>
 </div>{expanded&&<BotWorkspace onReviewRemaining={reviewRemaining} sharedCitation={sharedCitation} onAskShared={(id,position)=>{setText(position?`Analyze panel ${position} of shared artifact #${id}`:`Analyze shared artifact #${id}`);setMobilePane('chat');input.current?.focus()}} artifactCitation={artifactCitation} onAskDashboard={(id,position)=>{setText(`Analyze panel ${position} of dashboard #${id}`);setMobilePane('chat');input.current?.focus()}} agentId={agentId} onDownloadSource={source=>{const match=source.href.match(/^\/api\/v1\/ai-operator\/suite\/conversations\/([1-9]\d*)\/attachments\/([1-9]\d*)\/download$/);if(match)void downloadFile({id:Number(match[2]),name:source.label},Number(match[1]))}} conversationId={conversationId} conversations={conversations} onOpenConversation={id=>{setMobilePane('chat');void loadConversation(id)}} projectId={context.project_id} onUseTemplate={(id,revision)=>{const selectedAgent=agentId;fresh();setAgentId(selectedAgent);setText(`Use template #${id} version ${revision}`);setMobilePane('chat');input.current?.focus()}} onUseAgent={id=>{fresh();setAgentId(id);setMobilePane('chat');setText('');input.current?.focus()}} module={focusedModule} workspaceId={context.workspace_id} onEditArtifact={id=>{setText(`Edit artifact #${id}: `);setMobilePane('chat');input.current?.focus()}} onUpdate={update} openFilesRequest={openFilesRequest} openResultsRequest={openResultsRequest} run={current} attachments={attachments} selected={selectedAttachments} onSelect={id=>setSelectedAttachments(old=>old.includes(id)?old.filter(n=>n!==id):[...old,id])} busy={busy||loadingHistory||access!=='allowed'} onDirty={setDirty} onRevise={revise} onUpload={files=>void uploadFiles(files)} onDelete={id=>void deleteFile(id)} onDownload={file=>void downloadFile(file)} onImportImage={id=>{setSelectedAttachments([]);setText(`Import image file #${id}`);setMobilePane('chat');input.current?.focus()}} onImageReference={id=>{setSelectedAttachments([]);setText(`Create image from file #${id}: `);setMobilePane('chat');input.current?.focus()}} onTranscribe={id=>{setSelectedAttachments([]);setText(`Transcribe audio file #${id}`);setMobilePane('chat');input.current?.focus()}} onPrepare={id=>{setSelectedAttachments([id]);setText('create tasks from the uploaded spreadsheet');setMobilePane('chat');input.current?.focus()}}/>}</div>
 </section>
}
