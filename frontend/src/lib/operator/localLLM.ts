export type BrainRuntime = 'browser';
export type BrainReply = { kind: 'ask'|'answer'|'unsupported'|'task_plan'|'project_plan'; message: string; question?: string;
  task_ids?: number[]; task_plan?: { summary: string; clarification?: null; steps: any[] }; setup_plan?: any; new_project?: boolean };
export type BrainSession = { id: number; project_id: number; revision: number; turns: { text: string; reply: BrainReply; runtime: string; model: string; at: string }[] };
export type BrainPacket = { session: BrainSession; context: Record<string, any>; instructions: string; schema: Record<string, any>; as_of: string };
export const BROWSER_MODELS = [{id:'SmolLM2-135M-Instruct-tfjs',label:'SmolLM2 135M Instruct · TensorFlow.js WebGL / WASM / CPU'}] as const;
export class LocalBrainError extends Error {
  constructor(public reason:'unavailable'|'unsupported'|'invalid_output'|'context_limit'|'timeout',message:string){super(message);}
}
let worker:Worker|undefined,loadedModel='',running=false,nextId=0;
const pending=new Map<number,{resolve:(value:any)=>void;reject:(error:Error)=>void;progress?:(message:string)=>void}>();
export async function stopLocalBrain() {
  worker?.terminate();worker=undefined;loadedModel='';running=false;
  for(const call of pending.values())call.reject(new LocalBrainError('unavailable','Local model unloaded.'));
  pending.clear();
}
function request(type:string,payload:Record<string,unknown>,signal?:AbortSignal,progress?:(message:string)=>void):Promise<any> {
  if(!worker)return Promise.reject(new LocalBrainError('unavailable','Load the TensorFlow.js model first.'));
  return new Promise((resolve,reject)=>{
    const id=++nextId;
    const abort=()=>{pending.get(id)?.reject(new DOMException('Cancelled','AbortError'));void stopLocalBrain();};
    const timer=setTimeout(()=>{pending.get(id)?.reject(new LocalBrainError('timeout','Local inference timed out.'));void stopLocalBrain();},type==='load'?300000:120000);
    const cleanup=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort);pending.delete(id);};
    pending.set(id,{resolve:value=>{cleanup();resolve(value);},reject:error=>{cleanup();reject(error);},progress});
    signal?.addEventListener('abort',abort,{once:true});
    if(signal?.aborted){abort();return;}
    worker!.postMessage({id,type,...payload});
  });
}
export async function loadBrowserBrain(model:string,progress:(message:string)=>void,signal?:AbortSignal) {
  if(loadedModel===model && worker)return;
  if(!BROWSER_MODELS.some(m=>m.id===model))throw new LocalBrainError('unavailable','Unsupported TensorFlow.js model.');
  await stopLocalBrain();
  worker=new Worker(new URL('./localLLM.worker.ts',import.meta.url),{type:'module'});
  worker.onmessage=event=>{
    const {id,result,error,reason,progress:message}=event.data,call=pending.get(id);
    if(!call)return;
    if(message)call.progress?.(message);
    else if(error)call.reject(new LocalBrainError(reason || 'invalid_output',error));
    else call.resolve(result);
  };
  worker.onerror=()=>{void stopLocalBrain();};
  try {const result=await request('load',{},signal,progress);loadedModel=model;progress(`TensorFlow.js ready · ${result.backend}`);}
  catch(e){await stopLocalBrain();throw e;}
}

export function makeBrainMessages(packet: BrainPacket, text: string, timezone: string, _runtime: BrainRuntime, feedback?: string) {
  const context = { ...packet.context };
  // Preserve selected task details first. Explicit truncation is exposed to the
  // model; absent facts must trigger a question rather than an invented record.
  context.tasks = (context.tasks || []).slice(0,12);
  context.tasks_complete = !!packet.context.tasks_complete && context.tasks.length === (packet.context.tasks || []).length;
  context.collaborators = (context.collaborators || []).slice(0,30);
  context.collaborators_complete = !!packet.context.collaborators_complete && context.collaborators.length === (packet.context.collaborators || []).length;
  context.execution_history = (context.execution_history || []).slice(0,3);
  const memories=(context.project_memory || []) as {text:string;category?:string}[];
  const words=text.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) || [];
  const ranked=memories.map((memory,index)=>({memory,index,score:words.filter(w=>memory.text.toLowerCase().includes(w)).length})).sort((a,b)=>b.score-a.score||a.index-b.index);
  context.project_memory=ranked.slice(0,5).map(({memory})=>({...memory,text:memory.text.slice(0,600)}));
  context.memory_complete=memories.length<=5&&memories.every(m=>m.text.length<=600);
  const turns=packet.session.turns;
  const remembered=turns.length>6?[turns[0],...turns.slice(-5)]:turns;
  const history = remembered.map(t => ({user:t.text,assistant:t.reply,execution:'draft_only'}));
  const payload = { current_date:new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),
    timezone, authorized_context:context, conversation:history, history_truncated:turns.length>6, command:text, ...(feedback ? {validation_feedback:feedback, instruction:'Repair the invalid draft or ask a focused clarification. Never invent new IDs.'} : {}) };
  const content = JSON.stringify(payload);
  const budget = 14000;
  if (content.length+packet.instructions.length > budget) throw new LocalBrainError('context_limit','This local model context is too large. Clear older memory or narrow the task selection.');
  return [{role:'system' as const,content:packet.instructions},{role:'user' as const,content}];
}

export async function reasonLocally(config:{runtime:BrainRuntime;model:string},packet:BrainPacket,text:string,timezone:string,signal?:AbortSignal,feedback?:string):Promise<BrainReply> {
  if(running)throw new LocalBrainError('unavailable','The local model is busy.');
  if(loadedModel!==config.model || !worker)throw new LocalBrainError('unavailable','Load the TensorFlow.js model first.');
  const messages=makeBrainMessages(packet,text,timezone,config.runtime,feedback);
  running=true;
  try {
    const result=await request('generate',{messages},signal);
    if(!result.stopped)throw new LocalBrainError('invalid_output','Local generation did not finish within its token limit.');
    const parsed=JSON.parse(result.content);
    if(!parsed || typeof parsed!=='object' || typeof parsed.kind!=='string' || typeof parsed.message!=='string')throw new Error('Invalid envelope');
    return parsed;
  }catch(e){
    if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
    if(e instanceof LocalBrainError)throw e;
    throw new LocalBrainError('invalid_output','Local output was not a valid PMS draft.');
  }finally {running=false;}
}
