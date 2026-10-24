import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/store/authStore';
import { operatorApi, type OperatorProviderName, type OperatorRun } from '@/services/aiOperatorApi';
import { BROWSER_MODELS, LocalBrainError, loadBrowserBrain, ollamaModels, reasonLocally, stopLocalBrain,
  type BrainPacket, type BrainReply, type BrainRuntime, type BrainSession } from '@/lib/operator/localLLM';

export type LocalBrainHandle = { plan(text:string):Promise<boolean> };
type Props = { projectId:number; workspaceId?:number|null; provider:OperatorProviderName; cloudEnabled:boolean; allowCloud:boolean;
  selected:number[]; onRun:(run:OperatorRun)=>void; onSetup:(proposal:any)=>void };
const root='/ai-operator/brain';
const detail = (e:any) => typeof e?.response?.data?.detail==='string' ? e.response.data.detail : e?.message || 'Local reasoning could not finish.';

export const LocalBrainPanel = forwardRef<LocalBrainHandle,Props>(function LocalBrainPanel(props,ref) {
  const uid=useAuthStore(s=>s.user?.id);
  const [runtime,setRuntime]=useState<BrainRuntime>('ollama');
  const [browserModel,setBrowserModel]=useState<string>(BROWSER_MODELS[0].id);
  const [models,setModels]=useState<string[]>([]),[ollamaModel,setOllamaModel]=useState('');
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[text,setText]=useState(''),[status,setStatus]=useState('Load a browser model or connect local Ollama to enable local reasoning.');
  const [error,setError]=useState(''),[session,setSession]=useState<BrainSession|null>(null),[cloudFallback,setCloudFallback]=useState(true);
  const [sessions,setSessions]=useState<BrainSession[]>([]);
  const controller=useRef<AbortController>(), sessionRef=useRef<BrainSession|null>(null),busyRef=useRef(false),sequence=useRef(0);
  const selectedModel=runtime==='browser'?browserModel:ollamaModel;
  const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
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
  },[props.projectId,uid]);
  useEffect(()=>()=>{void stopLocalBrain();},[uid]);
  async function connect() {
    if(busyRef.current)return;busyRef.current=true;setBusy(true);setError('');setReady(false);
    const abort=new AbortController();controller.current=abort;
    try {
      if(runtime==='browser')await loadBrowserBrain(browserModel,setStatus,abort.signal);
      else {
        const available=await ollamaModels(abort.signal);setModels(available);setOllamaModel(m=>available.includes(m)?m:available[0] || '');
        if(!available.length)throw new LocalBrainError('unavailable','No installed local models found. Pull a model in Ollama first; remote/cloud aliases are excluded.');
        setStatus('Ollama connected on this device. CPU/GPU placement is managed by Ollama.');
      }
      if(!abort.signal.aborted)setReady(true);
    }catch(e){if(!abort.signal.aborted)setError(detail(e));}
    finally {busyRef.current=false;setBusy(false);}
  }
  async function run(command:string) {
    if(busyRef.current)return true;
    if(!props.projectId){setError('Choose a project to give the local brain scoped context and memory.');return true;}
    busyRef.current=true;setBusy(true);setError('');const current=++sequence.current;
    const abort=new AbortController();controller.current=abort;
    const key=crypto.randomUUID();
    try {
      let active=sessionRef.current;
      if(!active){active=(await api.post(`${root}/sessions`,{project_id:props.projectId},{signal:abort.signal})).data;updateSession(active);}
      const packet:BrainPacket=(await api.get(`${root}/sessions/${active!.id}/context`,{params:{task_ids:props.selected.join(',')},signal:abort.signal})).data;
      active=packet.session;updateSession(active);
      let reply:BrainReply, source:'browser'|'ollama'|'cloud'=runtime, model=selectedModel;
      let failure:LocalBrainError|undefined;
      try {
        if(!ready)throw new LocalBrainError('unavailable','The local model is not loaded or connected.');
        setStatus(`Reasoning locally with ${selectedModel}…`);
        reply=await reasonLocally({runtime,model:selectedModel},packet,command,timezone,abort.signal);
        if(reply.kind==='unsupported')throw new LocalBrainError('unsupported',reply.message);
        // One bounded local repair attempt. Domain validation, not the model's
        // confidence or self-evaluation, decides whether a draft is acceptable.
        try {reply=(await api.post(`${root}/sessions/${active.id}/validate`,{reply},{signal:abort.signal})).data;}
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
          throw new LocalBrainError(failure.reason,`${failure.message} No LLM provider request was sent. Enable a configured fallback or refine the request.`);
        setStatus(`Local fallback (${failure.reason}): using ${props.provider}.`);
        reply=(await api.post(`${root}/sessions/${active.id}/cloud`,{text:command,provider:props.provider,timezone,fallback_reason:failure.reason},{signal:abort.signal,timeout:65000})).data;
        source='cloud';model=props.provider;
      }
      if(abort.signal.aborted || current!==sequence.current)return true;
      if(reply.kind==='task_plan' && props.selected.length && reply.task_ids?.some(id=>!props.selected.includes(id)))
        throw new LocalBrainError('invalid_output','The model proposed targets outside your selected tasks. Clear or change the selection and request a fresh plan.');
      const saved=(await api.post(`${root}/sessions/${active.id}/turns`,{request_key:key,revision:active.revision,text:command,reply,runtime:source,model:model || 'unknown'},{signal:abort.signal})).data;
      updateSession(saved);setText('');
      if(reply.kind==='task_plan') {
        const result=await operatorApi.command({project_id:props.projectId,task_ids:reply.task_ids!,command,provider:props.provider,request_key:key,
          input_mode:'text',background:true,execution_mode:'atomic',timezone,local_plan:reply.task_plan as any});
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
  useImperativeHandle(ref,()=>({plan:async(command:string)=>{
    if(!ready)return false;
    return run(command);
  }}));
  return <section className="rounded-lg border p-4 space-y-3" aria-label="Local LLM brain">
    <h2 className="text-lg font-semibold">Local reasoning assistant</h2>
    <p className="text-sm">A pretrained language model plans from authorized PMS context, private conversation memory and execution receipts. Model replies are drafts; actions require the approval below.</p>
    <div className="flex flex-wrap gap-3"><label>Runtime<select aria-label="Local brain runtime" disabled={busy} className="ml-2 rounded border bg-background p-2" value={runtime} onChange={e=>{setRuntime(e.target.value as BrainRuntime);setReady(false);void stopLocalBrain();}}><option value="ollama">Ollama · CPU or GPU on this device</option><option value="browser">Browser WebGPU</option></select></label>
      {runtime==='browser'?<label>Model<select aria-label="Browser brain model" disabled={busy} className="ml-2 rounded border bg-background p-2" value={browserModel} onChange={e=>{setBrowserModel(e.target.value);setReady(false);void stopLocalBrain();}}>{BROWSER_MODELS.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>:
        <label>Installed local model<select aria-label="Ollama brain model" disabled={busy} className="ml-2 rounded border bg-background p-2" value={ollamaModel} onChange={e=>setOllamaModel(e.target.value)}><option value="">Connect to discover local models</option>{models.map(m=><option key={m}>{m}</option>)}</select></label>}
      <Button variant="outline" disabled={busy} onClick={()=>void connect()}>{runtime==='browser'?'Download / load browser model':'Connect local Ollama'}</Button>
      <Button variant="outline" disabled={busy} onClick={()=>{setReady(false);void stopLocalBrain();setStatus('Local model unloaded. Cached public model files may remain in browser storage.');}}>Unload model</Button>
    </div>
    <p className="text-sm text-muted-foreground">Browser models download pretrained weights from Hugging Face/MLC and may require gigabytes of storage and GPU memory. Downloads start only with the load button. Ollama uses fixed loopback 127.0.0.1:11434; start it with this app origin in OLLAMA_ORIGINS and OLLAMA_NO_CLOUD=1.</p>
    <label className="block text-sm"><input type="checkbox" disabled={busy || !props.allowCloud} checked={cloudFallback && props.allowCloud} onChange={e=>setCloudFallback(e.target.checked)} /> Use {props.provider} only when local reasoning is unavailable, unsupported or fails validation</label>
    <p aria-live="polite" className="text-sm">{status}</p>{error && <p role="alert" className="text-destructive">{error}</p>}
    <label className="block">Private memory<select aria-label="Local brain conversation" className="ml-2 rounded border bg-background p-2" disabled={busy} value={session?.id || ''} onChange={e=>updateSession(sessions.find(s=>s.id===Number(e.target.value)) || null)}><option value="">New private conversation</option>{[session,...sessions].filter((s,i,all):s is BrainSession=>!!s && all.findIndex(v=>v?.id===s.id)===i).map(s=><option key={s.id} value={s.id}>Conversation #{s.id} · {s.turns.length} remembered turns</option>)}</select></label>
    <p className="text-sm text-muted-foreground">Memory is stored privately in your PMS account for this project, up to 24 turns. It is supplied to a cloud provider only if cloud fallback is used. Stored drafts are not proof that actions executed.</p>
    {session?.turns.length ? <div className="max-h-72 overflow-auto space-y-3">{session.turns.map((turn,i)=><div key={i}><p className="text-sm"><strong>You:</strong> {turn.text}</p><p className="whitespace-pre-wrap"><strong>{turn.runtime==='cloud'?'Cloud fallback':'Local model'}:</strong> {turn.reply.message}</p>{turn.reply.question && <p className="font-medium">{turn.reply.question}</p>}</div>)}</div>:null}
    <textarea aria-label="Local brain message" className="min-h-24 w-full rounded border bg-background p-3" maxLength={4000} value={text} disabled={busy} onChange={e=>setText(e.target.value)} placeholder="Prepare our website launch. Ask me what you need, then build a reviewed plan."/>
    <div className="flex gap-3"><Button disabled={busy || !text.trim() || !props.projectId} onClick={()=>void run(text)}>Ask local brain</Button>
      {busy && <Button variant="outline" onClick={()=>{controller.current?.abort();void stopLocalBrain();setReady(false);setStatus('Cancelled. No approval was given. Any existing reviewed run remains visible below.');}}>Cancel reasoning</Button>}
      <Button variant="outline" disabled={busy || !session} onClick={async()=>{if(session){try{updateSession((await api.delete(`${root}/sessions/${session.id}/memory`)).data);}catch(e){setError(detail(e));}}}}>Clear private memory</Button>
    </div>
  </section>;
});
