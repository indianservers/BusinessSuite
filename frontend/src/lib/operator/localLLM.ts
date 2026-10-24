import type { WebWorkerMLCEngine } from '@mlc-ai/web-llm';

export type BrainRuntime = 'browser' | 'ollama';
export type BrainReply = { kind: 'ask'|'answer'|'unsupported'|'task_plan'|'project_plan'; message: string; question?: string;
  task_ids?: number[]; task_plan?: { summary: string; clarification?: null; steps: any[] }; setup_plan?: any; new_project?: boolean };
export type BrainSession = { id: number; project_id: number; revision: number; turns: { text: string; reply: BrainReply; runtime: string; model: string; at: string }[] };
export type BrainPacket = { session: BrainSession; context: Record<string, any>; instructions: string; schema: Record<string, any>; as_of: string };
export const BROWSER_MODELS = [
  { id:'Qwen2.5-1.5B-Instruct-q4f32_1-MLC', label:'Compact · 1.5B · compatible WebGPU laptops' },
  { id:'Qwen2.5-3B-Instruct-q4f16_1-MLC', label:'Balanced · 3B · shader-f16 GPU' },
  { id:'Qwen2.5-7B-Instruct-q4f16_1-MLC', label:'Desktop · 7B · larger shader-f16 GPU' },
] as const;
export class LocalBrainError extends Error {
  constructor(public reason: 'unavailable'|'unsupported'|'invalid_output'|'context_limit'|'timeout', message: string) { super(message); }
}
let engine: WebWorkerMLCEngine | undefined, worker: Worker | undefined, loadedModel = '';
let running = false;
const OLLAMA = 'http://127.0.0.1:11434';

export async function stopLocalBrain() {
  engine?.interruptGenerate();
  // Termination also stops model initialization/download work owned by this worker.
  worker?.terminate(); worker = undefined; engine = undefined; loadedModel = ''; running = false;
}
async function localFetch(path: '/api/tags'|'/api/show'|'/api/chat', body?: unknown, signal?: AbortSignal, timeout=10000) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort, { once:true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(abort, timeout);
  try {
    const result = await fetch(OLLAMA+path, { method:body ? 'POST':'GET', headers:body ? {'Content-Type':'application/json'} : {},
      body:body ? JSON.stringify(body):undefined, credentials:'omit', redirect:'error', signal:controller.signal });
    if (!result.ok) throw new LocalBrainError('unavailable', `Local Ollama returned HTTP ${result.status}.`);
    const length = Number(result.headers.get('content-length') || 0);
    if (length > 2_000_000) throw new LocalBrainError('invalid_output','Local response is too large.');
    const text = await result.text();
    if (text.length > 2_000_000) throw new LocalBrainError('invalid_output','Local response is too large.');
    return JSON.parse(text);
  } catch(e) {
    if (signal?.aborted) throw new DOMException('Cancelled','AbortError');
    if (e instanceof LocalBrainError) throw e;
    if (controller.signal.aborted) throw new LocalBrainError('timeout','The local runtime timed out.');
    throw new LocalBrainError('unavailable','Cannot reach local Ollama. Start it on loopback and allow this app origin in OLLAMA_ORIGINS.');
  } finally { clearTimeout(timer); signal?.removeEventListener('abort',abort); }
}
function remoteModel(model: any) { return !!(model.remote_host || model.remote_model || /(?:[:_-])cloud(?:$|[:_-])/i.test(model.name || '')); }
export async function ollamaModels(signal?: AbortSignal): Promise<string[]> {
  const result = await localFetch('/api/tags',undefined,signal);
  return (result.models || []).filter((m:any) => !remoteModel(m) && /^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,150}$/.test(m.name)).map((m:any) => m.name);
}
export async function loadBrowserBrain(model: string, progress: (message:string)=>void, signal?: AbortSignal) {
  if (loadedModel === model && engine) return;
  if (!BROWSER_MODELS.some(m => m.id === model)) throw new LocalBrainError('unavailable','Select a supported browser model.');
  const gpu = (navigator as any).gpu;
  if (!gpu) throw new LocalBrainError('unavailable','WebGPU is unavailable. Use local Ollama for CPU inference.');
  const adapter = await gpu.requestAdapter();
  if (!adapter) throw new LocalBrainError('unavailable','No WebGPU adapter is available. Use local Ollama.');
  if (model.includes('f16') && !adapter.features.has('shader-f16')) throw new LocalBrainError('unavailable','This GPU does not support shader-f16. Choose the compact f32 model.');
  await stopLocalBrain();
  const { CreateWebWorkerMLCEngine } = await import('@mlc-ai/web-llm');
  if (signal?.aborted) throw new DOMException('Cancelled','AbortError');
  worker = new Worker(new URL('./localLLM.worker.ts',import.meta.url),{type:'module'});
  let abort: (()=>void)|undefined;
  try {
    const cancelled = new Promise<never>((_,reject) => { abort=()=>{ void stopLocalBrain(); reject(new DOMException('Cancelled','AbortError')); }; signal?.addEventListener('abort',abort,{once:true}); });
    engine = await Promise.race([CreateWebWorkerMLCEngine(worker,model,{initProgressCallback:report=>progress(report.text)}),cancelled]);
    loadedModel = model;
    progress('Local browser model ready.');
  } catch(e) { await stopLocalBrain(); throw e; }
  finally { if (abort) signal?.removeEventListener('abort',abort); }
}

export function makeBrainMessages(packet: BrainPacket, text: string, timezone: string, runtime: BrainRuntime, feedback?: string) {
  const context = { ...packet.context };
  // Preserve selected task details first. Explicit truncation is exposed to the
  // model; absent facts must trigger a question rather than an invented record.
  context.tasks = (context.tasks || []).slice(0,runtime==='browser'?12:30);
  context.tasks_complete = !!packet.context.tasks_complete && context.tasks.length === (packet.context.tasks || []).length;
  context.collaborators = (context.collaborators || []).slice(0,30);
  context.collaborators_complete = !!packet.context.collaborators_complete && context.collaborators.length === (packet.context.collaborators || []).length;
  context.execution_history = (context.execution_history || []).slice(0,3);
  const history = packet.session.turns.slice(-6).map(t => ({user:t.text,assistant:t.reply,execution:'draft_only'}));
  const payload = { current_date:new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),
    timezone, authorized_context:context, conversation:history, command:text, ...(feedback ? {validation_feedback:feedback, instruction:'Repair the invalid draft or ask a focused clarification. Never invent new IDs.'} : {}) };
  const content = JSON.stringify(payload);
  const budget = runtime==='browser'?9500:23000;
  if (content.length+packet.instructions.length > budget) throw new LocalBrainError('context_limit','This local model context is too large. Clear older memory or narrow the task selection.');
  return [{role:'system' as const,content:packet.instructions},{role:'user' as const,content}];
}

export async function reasonLocally(config:{runtime:BrainRuntime;model:string},packet:BrainPacket,text:string,timezone:string,signal?:AbortSignal,feedback?:string):Promise<BrainReply> {
  if (running) throw new LocalBrainError('unavailable','The local model is busy with another request.');
  if (!config.model) throw new LocalBrainError('unavailable','Select a local model first.');
  const messages = makeBrainMessages(packet,text,timezone,config.runtime,feedback);
  running = true;
  try {
    let content: string;
    if (config.runtime==='ollama') {
      // Refresh the inventory immediately before sending private data, and reject
      // cloud aliases/remote manifests rather than relying on a localhost URL.
      if (!(await ollamaModels(signal)).includes(config.model)) throw new LocalBrainError('unavailable','Select an installed local model; cloud aliases are excluded.');
      const manifest = await localFetch('/api/show',{model:config.model},signal);
      if (remoteModel({...manifest,name:config.model})) throw new LocalBrainError('unavailable','Remote Ollama models are not allowed as a local brain.');
      const result = await localFetch('/api/chat',{model:config.model,messages,stream:false,format:packet.schema,
        options:{temperature:0.1,num_ctx:8192,num_predict:2000},keep_alive:'5m'},signal,180000);
      if (!result.done || result.done_reason==='length') throw new LocalBrainError('invalid_output','Local generation was incomplete.');
      content = result.message?.content || '';
    } else {
      if (!engine || loadedModel!==config.model) throw new LocalBrainError('unavailable','Download/load the browser model before using local reasoning.');
      const active = engine;
      let abort: (()=>void)|undefined;
      const timer = setTimeout(()=>{active.interruptGenerate();},120000);
      try {
        if (signal?.aborted) throw new DOMException('Cancelled','AbortError');
        abort=()=>active.interruptGenerate(); signal?.addEventListener('abort',abort,{once:true});
        await active.resetChat();
        const result = await active.chat.completions.create({messages,temperature:0.1,max_tokens:1100,response_format:{type:'json_object'}});
        if (signal?.aborted) throw new DOMException('Cancelled','AbortError');
        if (result.choices[0]?.finish_reason!=='stop') throw new LocalBrainError('invalid_output','Browser generation stopped before a complete plan.');
        content = result.choices[0].message.content || '';
      } finally { clearTimeout(timer); if(abort) signal?.removeEventListener('abort',abort); }
    }
    if (content.length>150000) throw new LocalBrainError('invalid_output','Local response exceeded the draft limit.');
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed!=='object' || typeof parsed.kind!=='string' || typeof parsed.message!=='string') throw new Error('Invalid envelope');
    return parsed;
  } catch(e) {
    if(signal?.aborted) throw new DOMException('Cancelled','AbortError');
    if(e instanceof LocalBrainError) throw e;
    throw new LocalBrainError('invalid_output','The local model could not produce a valid draft.');
  } finally { running=false; }
}
