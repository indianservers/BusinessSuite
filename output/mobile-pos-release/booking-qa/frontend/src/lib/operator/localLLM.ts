import {api} from '@/services/api';
export type BrainRuntime = 'server';
export type BrainReply = { kind: 'ask'|'answer'|'unsupported'|'task_plan'|'project_plan'; message: string; question?: string;
  task_ids?: number[]; task_plan?: { summary: string; clarification?: null; steps: any[] }; setup_plan?: any; new_project?: boolean };
export type BrainSession = { id: number; project_id: number; revision: number; turns: { text: string; reply: BrainReply; runtime: string; model: string; at: string }[] };
export type BrainPacket = { session: BrainSession; context: Record<string, any>; instructions: string; schema: Record<string, any>; as_of: string };
export const SERVER_MODELS=[{id:'SmolLM2-135M-Instruct-server',label:'SmolLM2 135M Instruct · server local'}] as const;
export class LocalBrainError extends Error {
  constructor(public reason:'unavailable'|'unsupported'|'invalid_output'|'context_limit'|'timeout',message:string){super(message);}
}
export async function stopLocalBrain(){ /* Request AbortControllers stop waiting; generation is bounded and cannot execute actions. */ }
export async function loadServerBrain(model:string,projectId:number,progress:(message:string)=>void,signal?:AbortSignal){
  if(model!==SERVER_MODELS[0].id)throw new LocalBrainError('unavailable','Unsupported server model.');
  const result=(await api.get('/ai-operator/brain/local-runtime',{params:{project_id:projectId},signal,progress:false})).data;
  if(!result.installed||result.available===false)throw new LocalBrainError('unavailable','The server-local model is unavailable. No cloud request was sent.');
  progress('Server-local model available. Weights remain on the server.');
}
export async function reasonLocally(config:{runtime:BrainRuntime;model:string},packet:BrainPacket,text:string,timezone:string,signal?:AbortSignal,feedback?:string):Promise<BrainReply>{
  if(config.runtime!=='server'||config.model!==SERVER_MODELS[0].id)throw new LocalBrainError('unavailable','Unsupported server runtime.');
  try {
    return (await api.post(`/ai-operator/brain/sessions/${packet.session.id}/local`,{text,timezone,
      task_ids:packet.context.selected_task_ids||[],revision_id:packet.context.revision_of?.id||null,feedback:feedback||null},
      {signal,readOnlyPreview:true,progress:false,timeout:65000})).data;
  }catch(error:any){
    if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
    const code=typeof error?.response?.data?.detail==='string'?error.response.data.detail:'';
    const reason=code.includes('CONTEXT_LIMIT')?'context_limit':code.includes('TIMEOUT')?'timeout':code.includes('INVALID_OUTPUT')?'invalid_output':'unavailable';
    const messages:Record<string,string>={LOCAL_MODEL_BUSY:'The server-local model is busy. Try again.',LOCAL_MODEL_CONTEXT_LIMIT:'Narrow the selected tasks or shorten this request.',LOCAL_MODEL_TIMEOUT:'The server-local model reached its time limit.',LOCAL_MODEL_INVALID_OUTPUT:'The server-local model could not produce a valid draft.',LOCAL_MODEL_UNAVAILABLE:'The server-local model is unavailable.'};
    throw new LocalBrainError(reason,messages[code]||code||'Server-local reasoning could not finish. No cloud request was sent.');
  }
}
