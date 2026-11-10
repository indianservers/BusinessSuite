import { useEffect,useRef,useState, type ReactNode } from 'react';
import { Link,useSearchParams } from 'react-router-dom';
import { Database,BrainCircuit,MessageSquare } from 'lucide-react';
import { api } from '@/services/api';
import { NativeSelect } from '@/components/ui/native-select';

export const TRAIN='/ai-operator/suite/training';
export const field='rounded-lg border bg-background px-3 py-2 text-sm';
export function errorMessage(error:any){const value=error?.response?.data?.detail;return typeof value==='string'?value:value?.message || 'Unable to complete this operation. Check permissions, branch and training runtime.';}
export function useLive(){const live=useRef(true);useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);return live;}
export function useTrainingScope(){
 const [params,setParams]=useSearchParams(),[revision,setRevision]=useState(0),[workspaces,setWorkspaces]=useState<any[]>([]);
 const workspace=params.get('workspace') || '';
 useEffect(()=>{const reset=()=>{setWorkspaces([]);setRevision(x=>x+1);setParams({});};window.addEventListener('suite:organization-changed',reset);window.addEventListener('suite:branch-changed',reset);return()=>{window.removeEventListener('suite:organization-changed',reset);window.removeEventListener('suite:branch-changed',reset);};},[setParams]);
 useEffect(()=>{let active=true;api.get('/project-management/workspaces').then(r=>{if(active)setWorkspaces(Array.isArray(r.data)?r.data:r.data.items || []);}).catch(()=>{});return()=>{active=false;};},[revision]);
 return {workspace,workspaces,key:`${revision}:${workspace}`,change:(value:string)=>setParams(value?{workspace:value}:{})};
}
export function TrainingShell({page,workspace,workspaces,change,children}:{page:'datasets'|'models';workspace:string;workspaces:any[];change:(value:string)=>void;children:ReactNode}){
 const query=workspace?`?workspace=${workspace}`:'';
 return <main className="mx-auto max-w-7xl space-y-6 p-4 md:p-6"><header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Local intelligence</p><h1 className="mt-1 text-2xl font-semibold">{page==='datasets'?'Datasets & user queries':'Training & models'}</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">Train with your approved examples. Model files and training stay on your server/local machine; the browser shows controls and results.</p></div><label className="text-sm">Workspace<NativeSelect aria-label="Training workspace" className={`${field} mt-1 block`} value={workspace} onChange={e=>change(e.target.value)}><option value="">Company / current branch</option>{workspaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</NativeSelect></label></header>
 <nav className="flex flex-wrap gap-2 border-b pb-3" aria-label="NLP training pages"><Link className={`${field} flex items-center gap-2 ${page==='datasets'?'bg-primary text-primary-foreground':''}`} to={`/ai-agents/nlp-datasets${query}`}><Database size={16}/>1. Datasets & queries</Link><Link className={`${field} flex items-center gap-2 ${page==='models'?'bg-primary text-primary-foreground':''}`} to={`/ai-agents/nlp-training${query}`}><BrainCircuit size={16}/>2. Training & models</Link><Link className={`${field} flex items-center gap-2`} to={`/ai-agents/operator${query}`}><MessageSquare size={16}/>Test the bot</Link></nav>{children}</main>;
}
export async function downloadFile(url:string,name:string,params:any,live:{current:boolean}){const response=await api.get(url,{params,responseType:'blob'});if(!live.current)return;const target=URL.createObjectURL(response.data);const link=document.createElement('a');link.href=target;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(target),1000);}
