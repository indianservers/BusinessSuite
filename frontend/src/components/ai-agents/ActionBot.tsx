import {useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Link,useLocation} from 'react-router-dom';
import {Bot,Check,ChevronDown,ExternalLink,Loader2,Maximize2,Minimize2,Plus,RefreshCw,Send,ShieldCheck,X} from 'lucide-react';
import BotWorkspace,{type BotAttachment,type DraftChange} from './BotWorkspace';
import {api} from '@/services/api';
import {useAuthStore} from '@/store/authStore';
import {actionBotContext} from './action-bot-context';
import './action-bot.css';

export type Run={id:number;status:string;plan_hash:string;command:string;can_resume?:boolean;result_cards?:{id:string;kind:string;title:string;body?:string;status:string;record_id?:number;href?:string}[];workflow_steps?:{step:number;tool:string;depends_on:number[];status:string;attempts:number}[];plan?:{summary:string;question?:string;steps:{tool:string;payload:Record<string,unknown>;record_id?:unknown;depends_on?:number[]}[]};receipts?:{step:number;tool:string;record_id?:number;delivery_counts?:Record<string,number>}[];result?:{feedback?:{revision:number;rating:string;correction:string};citations?:{id:string;label:string;href:string}[];checkpoint?:{retry_at?:string|null}};error_code?:string};
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
 const company=useRef(user?.access?.companyId);
 useEffect(()=>{const next=user?.access?.companyId;if(company.current!=null&&next!=null&&company.current!==next){setOpen(false);setOpened(false);setRevision(v=>v+1)}company.current=next},[user?.access?.companyId]);
 useEffect(()=>{const reset=()=>{setOpen(false);setOpened(false);setRevision(v=>v+1)};window.addEventListener('suite:organization-changed',reset);window.addEventListener('suite:branch-changed',reset);return()=>{window.removeEventListener('suite:organization-changed',reset);window.removeEventListener('suite:branch-changed',reset)}},[]);
 if(!user)return null;
 const scope=[user.id,revision,location.pathname,location.search].join(':');
 function close(){setOpen(false);trigger.current?.focus()}
 return createPortal(<div className="suite-action-bot">
  <button ref={trigger} type="button" className="action-bot-launcher" aria-label={open?'Minimize action bot':'Open action bot'} aria-expanded={open} aria-controls={id} title="Action bot" onClick={()=>{setOpened(true);setOpen(v=>!v)}}><Bot size={23} strokeWidth={1.8}/><span className="action-bot-dot"/></button>
  {opened&&<BotPanel key={scope} id={id} open={open} close={close} context={context}/>}
 </div>,document.body);
}

function BotPanel({id,open,close,context}:{id:string;open:boolean;close:()=>void;context:ReturnType<typeof actionBotContext>}){
 const [turns,setTurns]=useState<Turn[]>([]),[current,setCurrent]=useState<Run|null>(null),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [access,setAccess]=useState<'checking'|'allowed'|'denied'>('checking');
 const [provider,setProvider]=useState(context.module==='FAM'?'gemini':'local');
 const [providers,setProviders]=useState<any[]>([]);
 const [expanded,setExpanded]=useState(false),[mobilePane,setMobilePane]=useState<'chat'|'workspace'>('chat'),[dirty,setDirty]=useState(false);
 const [attachments,setAttachments]=useState<BotAttachment[]>([]),[selectedAttachments,setSelectedAttachments]=useState<number[]>([]);
 const revisionRequest=useRef<{signature:string;key:string}|null>(null);
 const [openFilesRequest,setOpenFilesRequest]=useState(0);
 const [conversationId,setConversationId]=useState<number|null>(null),[conversations,setConversations]=useState<{id:number;title:string}[]>([]),[loadingHistory,setLoadingHistory]=useState(true);
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
  const last=runs.at(-1)||null;latest.current=last;setCurrent(last);setText('');setError('');pending.current=null;
  const files:BotAttachment[]=data.attachments||[];
  setAttachments(files);setSelectedAttachments(((last?.result as any)?.request?.attachment_ids||[]).filter((id:number)=>files.some(file=>file.id===id)));setDirty(false);revisionRequest.current=null;
  const savedProvider=(last?.result as any)?.request?.provider;if(['local','gemini','openai'].includes(savedProvider))setProvider(savedProvider);
 }
 async function loadConversation(id:number){setBusy(true);setError('');try{const r=await api.post(`${ROOT}/conversations/${id}/resume`);if(live.current)restore(r.data)}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 useEffect(()=>{live.current=true;const abort=new AbortController();
  api.get(ROOT+'/tools',{signal:abort.signal}).then(()=>{if(live.current)setAccess('allowed')}).catch(e=>{if(!abort.signal.aborted&&live.current){setAccess('denied');setError(errorText(e))}});
  api.get('/ai-operator/providers',{params:{workspace_id:context.workspace_id},signal:abort.signal}).then(r=>{if(live.current)setProviders(r.data.items||[])}).catch(()=>{});
  api.get(ROOT+'/conversations',{params:{workspace_id:context.workspace_id},signal:abort.signal}).then(async r=>{if(!live.current||abort.signal.aborted)return;const items=r.data.items||[];setConversations(items);if(items.length){const response=await api.get(`${ROOT}/conversations/${items[0].id}`,{signal:abort.signal});if(live.current&&!abort.signal.aborted)restore(response.data)}}).catch(e=>{if(!abort.signal.aborted&&live.current)setError(errorText(e))}).finally(()=>{if(live.current&&!abort.signal.aborted)setLoadingHistory(false)});
  return()=>{live.current=false;abort.abort()};
 },[]);
 useEffect(()=>{if(open&&access==='allowed'&&!busy)input.current?.focus();const escape=(e:KeyboardEvent)=>{if(open&&e.key==='Escape'){e.stopPropagation();close()}};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape)},[open,access,busy]);
 useEffect(()=>{if(open)end.current?.scrollIntoView({block:'nearest'})},[open,turns.length,current?.status,busy]);
 function update(run:Run){latest.current=run;setCurrent(run);setTurns(old=>old.map(t=>t.run?.id===run.id?{...t,run}:t))}
 useEffect(()=>{if(!open||!current||!active.has(current.status))return;const ident=current.id;let mounted=true;
  const poll=()=>api.get(`${ROOT}/runs/${ident}`,{progress:false}).then(r=>{if(mounted&&live.current&&latest.current?.id===ident)update(r.data)}).catch(e=>{if(mounted&&live.current)setError(errorText(e))});
  void poll();const timer=setInterval(poll,2000);return()=>{mounted=false;clearInterval(timer)};
 },[open,current?.id,current?.status]);
 function fresh(){setTurns([]);setCurrent(null);latest.current=null;chatId.current=null;setConversationId(null);setAttachments([]);setSelectedAttachments([]);setDirty(false);setText('');setError('');pending.current=null;revisionRequest.current=null;input.current?.focus()}
 async function ensureChat(title:string){
  if(chatId.current)return chatId.current;
  const created=await api.post(ROOT+'/conversations',{title:title.replace(/\s+/g,' ').trim().slice(0,160)||'New conversation',workspace_id:context.workspace_id||null});
  if(!live.current)return null;
  chatId.current=created.data.id;setConversationId(created.data.id);setConversations(old=>[created.data,...old]);return created.data.id;
 }
 async function uploadFiles(list:FileList|null){
  const files=Array.from(list||[]);if(!files.length||busy||loadingHistory)return;setBusy(true);setError('');
  try{const id=await ensureChat(files[0].name);if(!id)return;
   for(const file of files){const form=new FormData();form.append('file',file);const r=await api.post(`${ROOT}/conversations/${id}/attachments`,form,{headers:{'Content-Type':'multipart/form-data'},timeout:90000});if(!live.current)return;setAttachments(old=>[...old.filter(a=>a.id!==r.data.id),r.data]);setSelectedAttachments(old=>Array.from(new Set([...old,r.data.id])))}
  }catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}
 }
 async function deleteFile(id:number){if(!chatId.current||busy)return;setBusy(true);setError('');try{await api.delete(`${ROOT}/conversations/${chatId.current}/attachments/${id}`);if(live.current){setAttachments(old=>old.filter(a=>a.id!==id));setSelectedAttachments(old=>old.filter(n=>n!==id))}}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
 async function downloadFile(file:BotAttachment){if(!chatId.current||busy)return;setBusy(true);setError('');try{const r=await api.get(`${ROOT}/conversations/${chatId.current}/attachments/${file.id}/download`,{responseType:'blob'});if(!live.current)return;const url=URL.createObjectURL(r.data);const a=document.createElement('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}}
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
  const value=text.trim();if(!value||busy||dirty||loadingHistory||access!=='allowed'||current&&active.has(current.status))return;
  if(/^(?:please\s+)?(?:(?:start|begin|open)\s+(?:a\s+)?(?:new|fresh|separate)|new)\s+(?:conversation|chat|request)[.!? ]*$/i.test(value)){fresh();return}
  if(current?.status==='awaiting_approval'&&/^(?:yes|approve|confirm|go ahead|do it|yes proceed|please go ahead|approve this action)[.! ]*$/i.test(value)){const approved=await act('approve');if(approved&&live.current)setText('');return}
  if(current?.can_resume&&/^(?:please\s+)?(?:resume|retry|continue)(?:\s+(?:the\s+)?(?:workflow|remaining (?:steps|actions)|paused workflow))?[.! ]*$/i.test(value)){const resumed=await act('resume');if(resumed&&live.current)setText('');return}
  if(provider==='local'&&/^FAM\s*:/i.test(value)){setError('Finance requires an enabled connected provider. Choose Gemini or OpenAI for this request.');return}
  const following=current&&chatId.current;
  const pendingModule=current&&['needs_clarification','awaiting_approval'].includes(current.status)?(current.result as any)?.request?.module:undefined;
  const body={text:value,provider,module:pendingModule||context.module,attachment_ids:selectedAttachments,workspace_id:context.workspace_id||null,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,mode:'auto',...(following?{parent_run_id:current.id}:{project_id:context.project_id||null})};
  const signature=JSON.stringify(body);if(pending.current?.signature!==signature)pending.current={signature,key:crypto.randomUUID()};
  setBusy(true);setError('');
  try{
   if(!await ensureChat(value))return;
   const {data}=await api.post<Run>(ROOT+'/commands',{...body,conversation_id:chatId.current,request_key:pending.current.key},{timeout:90000});if(!live.current)return;
   setTurns(old=>[...old,{key:crypto.randomUUID(),role:'user',text:value},{key:crypto.randomUUID(),role:'assistant',text:data.plan?.summary||'Request received.',run:data}]);
   latest.current=data;setCurrent(data);setText('');pending.current=null;
  }catch(e){if(live.current)setError(errorText(e))}finally{if(live.current)setBusy(false)}
 }
 const readyProvider=provider==='local'||providers.some(p=>p.provider===provider&&p.enabled&&p.data_sharing_allowed);
 const disabled=busy||dirty||loadingHistory||access!=='allowed'||!readyProvider||!!current&&active.has(current.status);
 const prompts=context.module==='PMS'?['What are today’s project jobs?','Create a project called Customer launch with tasks Design, Build and Test','Create a project task called Release with subtasks Build, Review and Deploy']:context.module==='HRMS'?['Show my leave balance','Apply for leave','Create an HR ticket']:context.module==='SRM'?['Show unpaid invoices','Show invoices due today','Summarize sales records']:context.module==='FAM'?['Summarize financial records','Prepare a voucher draft']:['What are todays jobs?','Create tasks for Call customer, Review quote and Confirm delivery','Send a message to all leads'];
 return <section id={id} hidden={!open} role="dialog" aria-modal="false" aria-labelledby={id+'-title'} className={`action-bot-panel ${expanded?'action-bot-expanded':''}`}>
  <header><span className="action-bot-avatar"><Bot size={23}/></span><div><h2 id={id+'-title'}>Action bot</h2><span>{label}{context.project_id?` · Project #${context.project_id}`:''}</span></div><button type="button" aria-label={expanded?'Collapse bot workspace':'Expand bot workspace'} disabled={dirty} onClick={()=>{setExpanded(v=>!v);setMobilePane('workspace')}}>{expanded?<Minimize2 size={18}/>:<Maximize2 size={18}/>}</button><button type="button" aria-label="New bot conversation" title="New conversation" onClick={fresh} disabled={busy||dirty||loadingHistory}><Plus size={18}/></button><button type="button" aria-label="Close action bot" onClick={close}><X size={18}/></button></header>
  <div className="action-bot-toolbar"><ShieldCheck size={14}/><span>Actions need your review</span><label><span className="sr-only">Bot intelligence</span><select aria-label="Bot intelligence" disabled={busy||!!current} value={provider} onChange={e=>setProvider(e.target.value)}>{context.module!=='FAM'&&<option value="local">Local intelligence</option>}<option value="gemini">Gemini API</option><option value="openai">OpenAI API</option></select><ChevronDown size={12}/></label></div>
  <div className="action-bot-toolbar"><label htmlFor={id+'-history'}>Conversations</label><select id={id+'-history'} aria-label="Saved bot conversations" value={conversationId||''} disabled={busy||dirty||loadingHistory} onChange={e=>e.target.value?void loadConversation(Number(e.target.value)):fresh()}><option value="">New conversation</option>{conversations.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>{conversationId&&<button type="button" aria-label="Reload saved conversation" title="Reload latest reply" disabled={busy||loadingHistory} onClick={()=>void loadConversation(conversationId)}><RefreshCw size={13}/></button>}</div>
  {expanded&&<div className="bot-mobile-tabs"><button type="button" aria-pressed={mobilePane==='chat'} onClick={()=>setMobilePane('chat')}>Conversation</button><button type="button" aria-pressed={mobilePane==='workspace'} onClick={()=>setMobilePane('workspace')}>Workspace</button></div>}
  <div className={`action-bot-body mobile-${mobilePane}`}><div className="action-bot-chat">
  <div className="action-bot-messages" aria-live="polite" aria-relevant="additions text">
   {!turns.length&&<div className="action-bot-welcome"><span className="action-bot-welcome-icon"><Bot size={30}/></span><h3>What can I help you do?</h3><p>Ask a question or describe an action. I’ll ask for missing details and show the exact changes before execution.</p><div>{prompts.map(prompt=><button type="button" key={prompt} onClick={()=>{setText(prompt);input.current?.focus()}}>{prompt}<span>↗</span></button>)}{(!context.module||['CRM','PMS','HRMS'].includes(context.module))&&<button type="button" onClick={()=>{setText('Create a customer follow-up called Customer follow-up, then add a project task called Delivery recovery, then raise an HR ticket called Staffing support');input.current?.focus()}}>Create a CRM → PMS → HRMS workflow<span>↗</span></button>}</div></div>}
   {turns.map(turn=><div key={turn.key} className={'action-bot-message '+turn.role}><small>{turn.role==='user'?'You':'Action bot'}</small><p>{turn.run?.status==='succeeded'?'Reviewed action processing completed. See the receipts below.':turn.text}</p>{turn.run?.plan?.question&&<p className="action-bot-question">{turn.run.plan.question}</p>}{turn.run?.result?.citations?.length?<div className="action-bot-citations">{turn.run.result.citations.slice(0,5).map(source=>source.href.startsWith('#bot-attachment-')?<button type="button" key={source.id} disabled={dirty} onClick={()=>{setExpanded(true);setMobilePane('workspace');setOpenFilesRequest(n=>n+1)}}>{source.label}<ExternalLink size={11}/></button>:<Link key={source.id} to={source.href}>{source.label}<ExternalLink size={11}/></Link>)}</div>:null}</div>)}
   {!!current?.workflow_steps?.length&&current.workflow_steps.length>1&&<div className="action-bot-workflow"><strong>Workflow progress</strong><ol aria-label="Workflow steps">{current.workflow_steps.map(step=><li key={step.step}><div><span>{step.step}. {step.tool.replace(/[._]/g,' ')}</span><b>{step.status.replace(/_/g,' ')}</b></div><small>{step.depends_on.length?`After step ${step.depends_on.join(', ')}`:'Ready first'}{step.attempts?` · ${step.attempts} attempt${step.attempts===1?'':'s'}`:''}</small></li>)}</ol></div>}
   {current?.result?.checkpoint?.retry_at&&<p role="status">Waiting to retry a read before dispatch. Completed actions will not repeat.</p>}
   {current?.can_resume&&<button type="button" className="action-bot-approve" disabled={busy} onClick={()=>void act('resume')}><RefreshCw size={16}/>Resume remaining reviewed actions</button>}
   {current?.plan?.steps?.length?<div className="action-bot-review"><strong>Review {current.plan.steps.length===1?'this action':'these actions'}</strong>{current.plan.steps.map((step,i)=><div key={i}><span>{step.tool.replace(/[._]/g,' ')}</span>{step.record_id!=null&&<small>Record {reviewValue(step.record_id)}</small>}<dl>{Object.entries(step.payload).filter(([k])=>!['preview_token','request_key','request_id'].includes(k)).map(([k,v])=><div key={k}><dt>{k.replace(/_/g,' ')}</dt><dd>{reviewValue(v)}</dd></div>)}</dl></div>)}{current.status==='awaiting_approval'&&<button type="button" className="action-bot-approve" disabled={busy||dirty} onClick={()=>void act('approve')}><Check size={16}/>Approve these exact actions</button>}</div>:null}
   {current?.receipts?.map(receipt=><p className="action-bot-receipt" key={receipt.step}><Check size={14}/>{receipt.tool.replace(/[._]/g,' ')} · {receipt.delivery_counts?Object.entries(receipt.delivery_counts).map(([s,n])=>`${n} ${s}`).join(', '):receipt.record_id?`record #${receipt.record_id}`:'Processed'}</p>)}
   {current&&<div className="action-bot-status">{current.status.replace(/_/g,' ')}{(['needs_clarification','awaiting_approval','paused',...active].includes(current.status))&&<button disabled={busy} type="button" onClick={()=>void act('cancel')}>Cancel remaining work</button>}</div>}
   {current?.error_code&&<p role="alert">{(current.result as any)?.planning_issue||current.error_code}. Completed receipts are retained; uncertain work will not be repeated automatically.</p>}
   {busy&&<p className="action-bot-thinking" role="status"><Loader2 size={15} className="animate-spin"/>Checking your request…</p>}<div ref={end}/>
  </div>
  {error&&<p role="alert" className="action-bot-error">{error}</p>}
  {!readyProvider&&<p className="action-bot-error">This provider is not enabled for this workspace. Choose a connected provider in the assistant settings.</p>}
  <form className="action-bot-compose" onSubmit={e=>{e.preventDefault();void send()}}><textarea ref={input} aria-label="Message action bot" rows={2} maxLength={6000} disabled={disabled} value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void send()}}} placeholder={access==='checking'?'Checking access…':'Ask or tell me what to do…'}/><button type="submit" aria-label="Send bot message" disabled={disabled||!text.trim()}><Send size={18}/></button></form>
  <footer><span>{provider==='local'?'Runs on your server':'Connected API'} · {label}</span><Link to={'/ai-agents/operator'+(query?'?'+query:'')}>Advanced controls <ExternalLink size={12}/></Link></footer>
 </div>{expanded&&<BotWorkspace onUpdate={update} openFilesRequest={openFilesRequest} run={current} attachments={attachments} selected={selectedAttachments} onSelect={id=>setSelectedAttachments(old=>old.includes(id)?old.filter(n=>n!==id):[...old,id])} busy={busy||loadingHistory||access!=='allowed'} onDirty={setDirty} onRevise={revise} onUpload={files=>void uploadFiles(files)} onDelete={id=>void deleteFile(id)} onDownload={file=>void downloadFile(file)} onPrepare={id=>{setSelectedAttachments([id]);setText('create tasks from the uploaded spreadsheet');setMobilePane('chat');input.current?.focus()}}/>}</div>
 </section>
}
