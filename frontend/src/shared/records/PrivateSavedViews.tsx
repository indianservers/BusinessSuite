import {Button} from '@/components/ui/button';
import {useEffect,useRef,useState} from 'react';
import {useSearchParams} from 'react-router-dom';
import {api} from '@/services/api';

type SavedView<T>={id:string;name:string;filters:T};
type LegacyView<T>=Omit<SavedView<T>,'id'>;
function failure(error:any){return typeof error.response?.data?.detail==='string'?error.response.data.detail:'Could not save task views. Reload and check your current access.'}

export default function PrivateSavedViews<T>({scope,filters,onApply,endpoint:ROOT,title,itemLabel='task',recordLabel='Tasks',legacyPrefix,validLegacy}:{scope:string;filters:T;onApply:(view:T)=>void;endpoint:string;title:string;itemLabel?:string;recordLabel?:string;legacyPrefix?:string;validLegacy?:(value:any)=>boolean}){
 const [views,setViews]=useState<SavedView<T>[]>([]),[revision,setRevision]=useState(0),[limit,setLimit]=useState(30);
 const [name,setName]=useState(''),[notice,setNotice]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
 const [legacy,setLegacy]=useState<LegacyView<T>[]>([]),[legacyIssue,setLegacyIssue]=useState('');
 const [reload,setReload]=useState(0),[params]=useSearchParams();const requested=params.get('view')||'';
 const active=useRef(scope),applied=useRef(''),apply=useRef(onApply);active.current=scope;apply.current=onApply;
 const requestScope={headers:{'X-Task-View-User':scope.split(':')[0],'X-Task-View-Company':scope.split(':')[1]}};
 const ready=/^[1-9]\d*:[1-9]\d*$/.test(scope);const legacyKey=legacyPrefix?`${legacyPrefix}:${scope}`:'';
 useEffect(()=>{setViews([]);setRevision(0);setName('');setNotice('');setError('');setBusy(false);setLegacy([]);setLegacyIssue('');applied.current='';
  if(!ready||!legacyKey||!validLegacy)return;
  try{const raw=JSON.parse(localStorage.getItem(legacyKey)||'[]');if(!Array.isArray(raw)||raw.length>20||!raw.every(validLegacy)){setLegacyIssue('Some browser views use an unsupported format. The browser copy is retained.');return}setLegacy(raw)}catch{setLegacyIssue('The previous browser copy could not be read and has been retained.')}
 },[scope,ready,legacyKey,validLegacy]);
 useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');if(!ready){setLoading(false);return()=>controller.abort()}
  api.get(ROOT,{...requestScope,signal:controller.signal,progress:false}).then(({data})=>{if(!controller.signal.aborted){setViews(data.items);setRevision(data.revision);setLimit(data.limit);setError('')}}).catch(e=>{if(!controller.signal.aborted){setViews([]);setError(failure(e))}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>controller.abort();
 },[scope,ready,requested,reload,ROOT]);
 useEffect(()=>{if(!requested||loading||error||applied.current===`${scope}:${requested}`)return;const view=views.find(v=>v.id===requested);if(!view){setNotice('This saved view is unavailable in your current account and company.');return}applied.current=`${scope}:${requested}`;apply.current(view.filters);setName(view.name);setNotice(`Applied “${view.name}” from the server.`)},[requested,loading,error,scope,views]);
 function update(data:any){setViews(data.items);setRevision(data.revision);setLimit(data.limit)}
 async function action(work:()=>Promise<void>){if(busy||loading||!ready)return;const started=scope;setBusy(true);setError('');try{await work()}catch(e){if(active.current===started)setError(failure(e))}finally{if(active.current===started)setBusy(false)}}
 async function save(){const started=scope,title=name.trim(),existing=views.find(v=>v.name.toLocaleLowerCase()===title.toLocaleLowerCase());
  await action(async()=>{const {data}=existing?await api.put(`${ROOT}/${existing.id}`,{name:title,filters,revision},requestScope):await api.post(ROOT,{name:title,filters},requestScope);if(active.current!==started)return;update(data);setNotice(`Saved “${title}” privately on the server.`)})}
 async function remove(){const started=scope,view=views.find(v=>v.name.toLocaleLowerCase()===name.trim().toLocaleLowerCase());if(!view)return;
  await action(async()=>{const {data}=await api.delete(`${ROOT}/${view.id}`,{...requestScope,params:{revision}});if(active.current!==started)return;update(data);setName('');setNotice(`Saved view removed. ${recordLabel} are unchanged.`)})}
 async function importBrowser(){const started=scope;
  await action(async()=>{const {data}=await api.post(`${ROOT}/import-browser`,{views:legacy},requestScope);if(active.current!==started)return;update(data);setLegacy([]);setNotice(`Imported ${data.imported} browser views; retained ${data.retained} matching server views.`);try{localStorage.removeItem(legacyKey)}catch{setLegacyIssue('The import succeeded, but the browser copy could not be removed.')}})}
 const selected=views.some(v=>v.name.toLocaleLowerCase()===name.trim().toLocaleLowerCase());
 return <section className="space-y-2 rounded-md border p-3" aria-label={title}><div className="flex flex-wrap items-center gap-2">
  <label className="text-sm">Saved view <select className="rounded border bg-background p-2" aria-label={`Apply saved ${itemLabel} view`} value="" disabled={busy||loading||!ready} onChange={e=>{const view=views.find(v=>v.id===e.target.value);if(view){onApply(view.filters);setName(view.name);setNotice(`Applied “${view.name}”.`)}}}><option value="">Choose a view…</option>{views.map(view=><option key={view.id} value={view.id}>{view.name}</option>)}</select></label>
  <input className="min-w-0 rounded border bg-background p-2 text-sm" aria-label={`${itemLabel==='task'?'Task':'Ticket'} view name`} placeholder="Name this view" maxLength={60} disabled={busy||loading||!ready} value={name} onChange={e=>setName(e.target.value)}/>
  <Button type="button" variant="outline" disabled={busy||loading||!ready||!name.trim()||views.length>=limit&&!selected} onClick={()=>void save()}>Save view</Button>
  {selected&&<button type="button" disabled={busy||loading} className="px-3 py-2 text-sm underline" onClick={()=>void remove()}>Remove saved view</button>}
  <button type="button" disabled={busy||loading||!ready} onClick={()=>setReload(n=>n+1)}>Reload saved views</button>
 </div><p className="text-xs text-muted-foreground">Private views are stored on the server for your account and company. Up to {limit} views. Record permissions still apply.</p>
 {legacy.length>0&&<details><summary>{legacy.length} browser views available to import</summary><p>Review these names and filters before copying them to your private server views. Records are unchanged.</p>{legacy.map((view,index)=><div key={index}><label>Browser view {index+1} name<input aria-label={`Browser view ${index+1} name`} maxLength={60} disabled={busy} value={view.name} onChange={e=>setLegacy(old=>old.map((v,i)=>i===index?{...v,name:e.target.value}:v))}/></label><pre className="whitespace-pre-wrap">{JSON.stringify(view.filters)}</pre></div>)}<button type="button" disabled={busy||loading||!!legacyIssue||legacy.some(view=>!view.name.trim())} onClick={()=>void importBrowser()}>Import browser views to server</button></details>}
 {!ready&&<p role="status">Select a company to manage saved views.</p>}{legacyIssue&&<p role="alert">{legacyIssue}</p>}{loading&&<p role="status">Loading server views…</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}</section>
}
