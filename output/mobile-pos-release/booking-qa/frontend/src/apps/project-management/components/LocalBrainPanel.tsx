import { NativeSelect } from "@/components/ui/native-select";
import { Link } from 'react-router-dom';
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/store/authStore';
import { operatorApi, type OperatorProviderName, type OperatorRun } from '@/services/aiOperatorApi';
import { SERVER_MODELS, LocalBrainError, loadServerBrain, reasonLocally, stopLocalBrain,
  type BrainPacket, type BrainReply, type BrainRuntime, type BrainSession } from '@/lib/operator/localLLM';
export type LocalBrainHandle = { plan(text:string,inputMode?:'text'|'voice',revision?:OperatorRun):Promise<boolean>; hasPendingQuestion():boolean };
type Props = { compact?:boolean; onReply?:(reply:BrainReply)=>void; onBusyChange?:(busy:boolean)=>void; projectId:number; workspaceId?:number|null; provider:OperatorProviderName; cloudEnabled:boolean; allowCloud:boolean; executionMode:'atomic'|'checkpointed';
  selected:number[]; onRun:(run:OperatorRun)=>void; onSetup:(proposal:any)=>void };
const root='/ai-operator/brain';
const detail = (e:any) => typeof e?.response?.data?.detail==='string' ? e.response.data.detail : e?.message || 'Local reasoning could not finish.';
export const LocalBrainPanel = forwardRef<LocalBrainHandle,Props>(function LocalBrainPanel(props,ref) {
  const uid=useAuthStore(s=>s.user?.id),company=useAuthStore(s=>s.user?.access?.companyId);
  const runtime:BrainRuntime='server';
  const [browserModel,setBrowserModel]=useState<string>(SERVER_MODELS[0].id);
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[text,setText]=useState(''),[status,setStatus]=useState('Check the server-local model to enable local reasoning.');
  const [error,setError]=useState(''),[session,setSession]=useState<BrainSession|null>(null),[cloudFallback,setCloudFallback]=useState(true);
  const [sessions,setSessions]=useState<BrainSession[]>([]);
  const controller=useRef<AbortController>(), sessionRef=useRef<BrainSession|null>(null),busyRef=useRef(false),sequence=useRef(0);
  const selectedModel=browserModel;
  const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
  useEffect(()=>{props.onBusyChange?.(busy);},[busy,props.onBusyChange]);
  function updateSession(value:BrainSession|null) {sessionRef.current=value;setSession(value);}
  useEffect(()=>{
    sequence.current++;controller.current?.abort();updateSession(null);setError('');setBusy(false);busyRef.current=false;setSessions([]);
    if(!props.projectId)return;
    const abort=new AbortController();
    api.get(`${root}/sessions`,{params:{project_id:props.projectId},signal:abort.signal}).then(r=>{
      if(abort.signal.aborted)return;setSessions(r.data.items);
      if(!sessionRef.current && r.data.items[0])updateSession(r.data.items[0]);
    }).catch(()=>{if(!abort.signal.aborted)setStatus('Private memory will reconnect when you send a message.');});
    return()=>{abort.abort();controller.current?.abort();sequence.current++;};
  },[props.projectId,uid,company]);
  useEffect(()=>{const changed=()=>{sequence.current++;controller.current?.abort();updateSession(null);setSessions([]);setReady(false);setBusy(false);busyRef.current=false;setError('');setStatus('Scope changed. Reconnect the server model in the current project.');};window.addEventListener('suite:organization-changed',changed);window.addEventListener('suite:branch-changed',changed);return()=>{window.removeEventListener('suite:organization-changed',changed);window.removeEventListener('suite:branch-changed',changed);};},[]);
  async function connect() {
    if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');setReady(false);
    const abort=new AbortController();controller.current=abort;
    try {
      await loadServerBrain(browserModel,props.projectId,setStatus,abort.signal);
      if(!abort.signal.aborted)setReady(true);
    }catch(e){if(!abort.signal.aborted)setError(detail(e));}
    finally {busyRef.current=false;setBusy(false);}
  }
  async function run(command:string,inputMode:'text'|'voice'='text',revision?:OperatorRun) {
    if(busyRef.current)return true;
    if(!props.projectId){setError('Choose a project to give the local brain scoped context and memory.');return true;}
    busyRef.current=true;setBusy(true);setError('');const current=++sequence.current;
    const abort=new AbortController();controller.current=abort;
    const key=crypto.randomUUID();
    try {
      if(!ready && (!props.allowCloud || !cloudFallback || !props.cloudEnabled))
        throw new LocalBrainError('unavailable','Connect the server-local model to reason locally. No LLM request was sent.');
      let active=sessionRef.current;
      if(!active){active=(await api.post(`${root}/sessions`,{project_id:props.projectId},{signal:abort.signal})).data;if(abort.signal.aborted||current!==sequence.current)return true;updateSession(active);}
      const packet:BrainPacket=(await api.get(`${root}/sessions/${active!.id}/context`,{params:{task_ids:props.selected.join(',')},signal:abort.signal})).data;
      if(revision)packet.context.revision_of={id:revision.id,selection:revision.selection,plan:revision.plan,result:revision.result,
        instruction:'Return a complete replacement of pending steps for these frozen targets only. Exclude committed receipt steps. Project setup cannot revise an existing task run.'};
      if(abort.signal.aborted||current!==sequence.current)return true;
      active=packet.session;updateSession(active);
      let reply:BrainReply, source:'server'|'cloud'=runtime, model=selectedModel;
      let failure:LocalBrainError|undefined;
      try {
        if(!ready)throw new LocalBrainError('unavailable','The local model is not loaded or connected.');
        setStatus(`Reasoning locally with ${selectedModel}…`);
        reply=await reasonLocally({runtime,model:selectedModel},packet,command,timezone,abort.signal);
        if(reply.kind==='unsupported')throw new LocalBrainError('unsupported',reply.message);
        // One bounded local repair attempt. Domain validation, not the model's
        // confidence or self-evaluation, decides whether a draft is acceptable.
        try {
          if(revision && (reply.kind==='project_plan' || (reply.kind==='task_plan' && reply.task_ids?.some(id=>!revision.selection.includes(id)))))throw new Error('Revision must use the frozen task selection.');
          reply=(await api.post(`${root}/sessions/${active.id}/validate`,{reply},{signal:abort.signal})).data;
        }
        catch(e) {
          if(abort.signal.aborted)throw e;
          setStatus('Repairing the local draft after validation…');
          reply=await reasonLocally({runtime,model:selectedModel},packet,command,timezone,abort.signal,detail(e));
          reply=(await api.post(`${root}/sessions/${active.id}/validate`,{reply},{signal:abort.signal})).data;
          if(reply.kind==='unsupported')throw new LocalBrainError('unsupported',reply.message);
        }
      }catch(e) {
        if(abort.signal.aborted)throw e;
        failure=e instanceof LocalBrainError?e:new LocalBrainError('invalid_output',detail(e));
        if(!props.allowCloud || !cloudFallback || !props.cloudEnabled)
          throw new LocalBrainError(failure.reason,`${failure.message} No LLM request was sent. Enable a configured fallback or refine the request.`);
        if(revision){
          const result=await operatorApi.revise(revision,command,key,inputMode);
          if(!abort.signal.aborted && current===sequence.current)props.onRun(result.data);
          setStatus(`Local revision fallback (${failure.reason}) used ${props.provider}. Review the new run before approval.`);
          return true;
        }
        setStatus(`Local fallback (${failure.reason}): using ${props.provider}.`);
        reply=(await api.post(`${root}/sessions/${active.id}/cloud`,{text:command,provider:props.provider,timezone,task_ids:props.selected,fallback_reason:failure.reason},{signal:abort.signal,timeout:65000})).data;
        source='cloud';model=props.provider;
      }
      if(abort.signal.aborted || current!==sequence.current)return true;
      if(reply.kind==='task_plan' && props.selected.length && reply.task_ids?.some(id=>!props.selected.includes(id)))
        throw new LocalBrainError('invalid_output','The model proposed targets outside your selected tasks. Clear or change the selection and request a fresh plan.');
      if(revision && (reply.kind==='project_plan' || (reply.kind==='task_plan' && reply.task_ids?.some(id=>!revision.selection.includes(id)))))
        throw new LocalBrainError('invalid_output','The revised draft must stay within the frozen task selection.');
      const saved=(await api.post(`${root}/sessions/${active.id}/turns`,{request_key:key,revision:active.revision,text:command,reply,runtime:source,model:model || 'unknown',fallback_reason:failure?.reason || null},{signal:abort.signal})).data;
      if(abort.signal.aborted||current!==sequence.current)return true;
      updateSession(saved);setText('');
      props.onReply?.(reply);
      if(reply.kind==='task_plan') {
        const result=await operatorApi.command({project_id:props.projectId,task_ids:revision?revision.selection:reply.task_ids!,command,provider:props.provider,request_key:key,
          input_mode:inputMode,background:true,execution_mode:props.executionMode,timezone,local_plan:reply.task_plan as any,
          ...(revision?{parent_run_id:revision.id,parent_plan_hash:revision.plan_hash}:{})});
        if(!abort.signal.aborted && current===sequence.current)props.onRun(result.data);
      }else if(reply.kind==='project_plan') {
        const result=await api.post('/ai-operator/setup/preview',{brief:command,provider:props.provider,request_key:key,workspace_id:props.workspaceId || null,
          project_id:reply.new_project?null:props.projectId,local_plan:reply.setup_plan});
        if(!abort.signal.aborted && current===sequence.current)props.onSetup(result.data);
      }
      setStatus(source==='cloud'?`Cloud fallback · ${props.provider} · ${failure?.reason}. Review any proposed work before approval.`:
        `Local LLM · ${selectedModel} · no Gemini/OpenAI/Claude call. ${reply.kind.endsWith('plan')?'Draft ready for review.':''}`);
    }catch(e){if(!abort.signal.aborted && current===sequence.current)setError(detail(e));}
    finally {if(current===sequence.current){busyRef.current=false;setBusy(false);}}
    return true;
  }
  useImperativeHandle(ref,()=>({hasPendingQuestion:()=>sessionRef.current?.turns.at(-1)?.reply.kind==='ask',plan:async(command:string,inputMode?:'text'|'voice',revision?:OperatorRun)=>{
    return run(command,inputMode,revision);
  }}));
  const controls=<>
    <div className="flex flex-wrap gap-3"><label>Model<NativeSelect aria-label="Server brain model" disabled={busy} className="ml-2 rounded border bg-background p-2" value={browserModel} onChange={e=>{setBrowserModel(e.target.value);setReady(false);void stopLocalBrain();}}>{SERVER_MODELS.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</NativeSelect></label>
      <Button variant="outline" disabled={busy} onClick={()=>void connect()}>Check server model</Button>
      <Button variant="outline" disabled={busy} onClick={()=>{setReady(false);void stopLocalBrain();setStatus('Local connection reset.');}}>Reset connection</Button>
    </div>
    <p className="text-sm text-muted-foreground">Model weights and generation stay on the server. This small model may need a configured cloud provider for complex plans; fallback requires the choice below.</p>
    <label className="block text-sm"><input type="checkbox" disabled={busy || !props.allowCloud} checked={cloudFallback && props.allowCloud} onChange={e=>setCloudFallback(e.target.checked)} /> Use {props.provider} only when local reasoning is unavailable, unsupported or fails validation</label>
    <label className="block">Private memory<NativeSelect aria-label="Local brain conversation" className="ml-2 rounded border bg-background p-2" disabled={busy} value={session?.id || ''} onChange={e=>updateSession(sessions.find(s=>s.id===Number(e.target.value)) || null)}><option value="">New private conversation</option>{[session,...sessions].filter((s,i,all):s is BrainSession=>!!s && all.findIndex(v=>v?.id===s.id)===i).map(s=><option key={s.id} value={s.id}>Conversation #{s.id} · {s.turns.length} remembered turns</option>)}</NativeSelect></label>
    <Link className="block text-sm text-primary underline" to={`/ai-agents/operator?module=PMS&project=${props.projectId}${props.workspaceId?`&workspace=${props.workspaceId}`:''}`}>Connected AI agent: calendar planning, playbooks, monitors and recovery</Link>
    <p className="text-sm text-muted-foreground">Memory is stored privately in your PMS account for this project, up to 24 turns. It is supplied to a cloud provider only if cloud fallback is used. Stored drafts are not proof that actions executed.</p>
  </>;
  return <section className={`rounded-lg border p-4 space-y-3 ${props.compact?'local-brain-compact':''}`} aria-label="Local LLM brain">
    {!props.compact && <><h2 className="text-lg font-semibold">Local reasoning assistant</h2>
    <p className="text-sm">A pretrained language model plans from authorized PMS context, private conversation memory and execution receipts. Model replies are drafts; actions require the approval below.</p></>}
    {props.compact ? <div className="brain-model-strip"><span><i/>{ready?'Server model available':'Server model not connected'}</span><Button variant="outline" disabled={busy} onClick={()=>{if(ready){setReady(false);void stopLocalBrain();}else void connect();}}>{ready?'Reset connection':'Connect server model'}</Button><details><summary>Model & conversation settings</summary>{controls}</details></div>:controls}
    <p aria-live="polite" className="text-sm">{status}</p>{error && <p role="alert" className="text-destructive">{error}</p>}
    {session?.turns.length ? <div className="max-h-72 overflow-auto space-y-3">{session.turns.map((turn,i)=><div key={i}><p className="text-sm"><strong>You:</strong> {turn.text}</p><p className="whitespace-pre-wrap"><strong>{turn.runtime==='cloud'?'Cloud fallback':'Local model'}:</strong> {turn.reply.message}</p>{turn.reply.question && <p className="font-medium">{turn.reply.question}</p>}</div>)}</div>:null}
    {!props.compact && <textarea aria-label="Local brain message" className="min-h-24 w-full rounded border bg-background p-3" maxLength={4000} value={text} disabled={busy} onChange={e=>setText(e.target.value)} placeholder="Prepare our website launch. Ask me what you need, then build a reviewed plan."/>}
    <div className="flex gap-3">{!props.compact && <Button disabled={busy || !text.trim() || !props.projectId} onClick={()=>void run(text)}>Ask local brain</Button>}
      {busy && <Button variant="outline" onClick={()=>{controller.current?.abort();void stopLocalBrain();setReady(false);setStatus('Stopped waiting. No approval was given. Any existing reviewed run remains visible below.');}}>Stop waiting</Button>}
      <Button variant="outline" disabled={busy || !session} onClick={async()=>{if(session){try{updateSession((await api.delete(`${root}/sessions/${session.id}/memory`)).data);}catch(e){setError(detail(e));}}}}>{props.compact?'Clear conversation':'Clear private memory'}</Button>
    </div>
  </section>;
});
