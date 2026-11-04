import { useEffect, useRef, useState, type ReactNode } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

export type PipelineContext = { module:"crm"|"project_management"|"srm"|"hrms"; scope:string; kind?:"deal"|"task"|"candidate"|"sales_order" };
export type CardField = "subtitle"|"owner"|"value"|"activity"|"age"|"content";
export type PipelinePreferences = {module_filters:Record<string,string|boolean>;density:"compact"|"comfortable";fields:CardField[];queue:"all"|"mine"|"attention"|"overdue"|"unassigned";owner:string;search:string;sort:"manual"|"name"|"due"|"age"};
type View = {id:string;name:string;shared:boolean;preferences:PipelinePreferences};
export const defaultPreferences:PipelinePreferences={module_filters:{},density:"compact",fields:["subtitle","owner","value","activity","age","content"],queue:"all",owner:"",search:"",sort:"manual"};
export function normalizePreferences(value:unknown):PipelinePreferences {
 const p=(value&&typeof value==="object"?value:{}) as Partial<PipelinePreferences>;
 return {module_filters:p.module_filters&&typeof p.module_filters==="object"?Object.fromEntries(Object.entries(p.module_filters).filter(([k,v])=>k.length<=80&&(typeof v==="string"||typeof v==="boolean"))):{},density:p.density==="comfortable"?"comfortable":"compact",fields:Array.isArray(p.fields)?p.fields.filter((f):f is CardField=>defaultPreferences.fields.includes(f)):defaultPreferences.fields,queue:["all","mine","attention","overdue","unassigned"].includes(p.queue||"")?p.queue!:"all",owner:typeof p.owner==="string"?p.owner.slice(0,120):"",search:typeof p.search==="string"?p.search.slice(0,200):"",sort:["manual","name","due","age"].includes(p.sort||"")?p.sort!:"manual"};
}
export function usePipelinePreferences(context:PipelineContext|undefined,label:string,viewState?:Record<string,string|boolean>,onApply?:(filters:Record<string,string|boolean>)=>void){
  const user=useAuthStore(s=>s.user);
  const key=`pipeline-ui:${user?.access?.companyId||"default"}:${sessionStorage.getItem("suite-branch")||"all"}:${user?.id||"preview"}:${context?.module||"preview"}:${context?.scope||label}`;
  const read=()=>{try{return normalizePreferences(JSON.parse(localStorage.getItem(key)||"null"));}catch{return {...defaultPreferences};}};
  const [preferences,setPreferences]=useState<PipelinePreferences>(read),[views,setViews]=useState<View[]>([]),[canShare,setCanShare]=useState(false),[error,setError]=useState("");
  const [notice,setNotice]=useState(""),[busy,setBusy]=useState(false);const dirty=useRef(false);
  const url=context?`/pipeline-workspaces/${context.module}/${context.scope}`:undefined;
  useEffect(()=>{dirty.current=false;setPreferences(read());setViews([]);setError("");setNotice("");let active=true;
    if(url)void api.get(`${url}/views`).then(r=>{if(!active)return;setViews(r.data.views||[]);setCanShare(!!r.data.can_share);if(!dirty.current&&!localStorage.getItem(key))setPreferences(normalizePreferences(r.data.preferences));}).catch(()=>{if(active)setError("Saved team views could not be loaded. Your board is still available.");});
    return()=>{active=false;};
  },[key,url]);
  function update(patch:Partial<PipelinePreferences>){dirty.current=true;setNotice("");setPreferences(current=>{const next=normalizePreferences({...current,...patch});try{localStorage.setItem(key,JSON.stringify(next));}catch{/* Storage failure does not block record work. */}return next;});}
  async function save(){setBusy(true);setError("");try{if(url)await api.put(`${url}/preferences`,{...preferences,module_filters:viewState||preferences.module_filters});setNotice(url?"Preferences saved across devices.":"Preferences saved on this device.");}catch{setError("Could not sync preferences. Your local settings are retained.");}finally{setBusy(false);}}
  async function saveView(name:string,shared:boolean){setBusy(true);setError("");try{if(!name.trim())throw new Error("Name the view.");if(!url)throw new Error("This preview cannot publish saved views.");const result=await api.post(`${url}/views`,{name:name.trim(),shared,preferences:{...preferences,module_filters:viewState||preferences.module_filters}});setViews(v=>[...v,result.data]);setNotice("View saved.");}catch(e){setError((e as {response?:{data?:{detail?:string}};message?:string}).response?.data?.detail||(e as Error).message);}finally{setBusy(false);}}
  function applyView(view:View){update(view.preferences);onApply?.(view.preferences.module_filters||{});}
  return {preferences,update,views,applyView,canShare,error,notice,busy,save,saveView,userId:user?.id,context};
}
export function PipelineDrawer({open,onClose,title,children,wide=false}:{open:boolean;onClose:()=>void;title:string;children:ReactNode;wide?:boolean}){
  return <Dialog open={open} onOpenChange={v=>{if(!v)onClose();}}><DialogContent className="pipeline-drawer" style={{left:"auto",right:0,top:0,transform:"none",height:"100dvh",maxHeight:"100dvh",width:wide?"min(1280px,100vw)":"min(680px,100vw)",maxWidth:wide?"1280px":"680px",borderRadius:0,display:"block",overflowY:"auto"}}><DialogTitle className="text-lg font-semibold mb-5 pr-9">{title}</DialogTitle>{children}</DialogContent></Dialog>;
}
export function PipelinePreferencesPanel({state}:{state:ReturnType<typeof usePipelinePreferences>}){
  const {preferences:p,update}=state;const [name,setName]=useState(""),[shared,setShared]=useState(false);
  return <div className="pipeline-settings-panel">
    <section><h3>Display</h3><label>Card density<select value={p.density} onChange={e=>update({density:e.target.value as PipelinePreferences["density"]})}><option value="compact">Compact</option><option value="comfortable">Comfortable</option></select></label><fieldset><legend>Show on cards</legend>{defaultPreferences.fields.map(field=><label className="pipeline-check" key={field}><input type="checkbox" checked={p.fields.includes(field)} onChange={e=>update({fields:e.target.checked?[...p.fields,field]:p.fields.filter(f=>f!==field)})}/>{field=== "age"?"Time in stage":field}</label>)}</fieldset></section>
    <section><h3>Filter loaded records</h3><label>Search<input value={p.search} onChange={e=>update({search:e.target.value})}/></label><label>Work queue<select value={p.queue} onChange={e=>update({queue:e.target.value as PipelinePreferences["queue"]})}><option value="all">All records</option><option value="mine">Assigned to me</option><option value="attention">Needs attention</option><option value="overdue">Overdue activity</option><option value="unassigned">Unassigned</option></select></label><label>Owner name<input value={p.owner} onChange={e=>update({owner:e.target.value})}/></label><label>Sort cards<select value={p.sort} onChange={e=>update({sort:e.target.value as PipelinePreferences["sort"]})}><option value="manual">Manual order</option><option value="name">Name</option><option value="due">Next action date</option><option value="age">Longest time in stage</option></select></label><p>These controls filter the loaded cards. Module filters and stage totals retain their server-side definitions.</p></section>
    <section><h3>Saved views</h3>{state.views.map(view=><button type="button" className="pipeline-saved-view" key={view.id} onClick={()=>state.applyView(view)}>{view.name}<small>{view.shared?"Team":"Personal"}</small></button>)}<label>View name<input maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>{state.canShare&&<label className="pipeline-check"><input type="checkbox" checked={shared} onChange={e=>setShared(e.target.checked)}/>Share with this workspace</label>}<button type="button" disabled={state.busy||!name.trim()} onClick={()=>void state.saveView(name,shared)}>Save current view</button></section>
    {state.context&&<section><h3>Stage automation and handoffs</h3><p>Successful stage changes publish <code>pipeline.stage_entered</code> in the existing workflow engine. Configure rules against this event; approvals and record permissions still apply. Existing CRM Won handoffs and Sales confirmation flows remain authoritative.</p><a href={`/admin/control/services/workflows?module=${state.context.module}&trigger=pipeline.stage_entered`}>Open workflow builder</a></section>}
    {state.error&&<p role="alert" className="text-destructive">{state.error}</p>}{state.notice&&<p role="status">{state.notice}</p>}
    <footer><button type="button" onClick={()=>update(defaultPreferences)}>Reset display</button><button type="button" className="pipeline-primary" disabled={state.busy} onClick={()=>void state.save()}>Save preferences</button></footer>
  </div>;
}
export function PipelineHistory({context,recordId}:{context:PipelineContext;recordId:string}){
  const [items,setItems]=useState<Array<{id:number;at:string;previous_stage:string;stage:string;previous_stage_name?:string;stage_name?:string}>>(),[error,setError]=useState("");
  useEffect(()=>{let active=true;setItems(undefined);setError("");if(!context.kind)return;void api.get(`/pipeline-workspaces/${context.module}/records/${context.kind}/${recordId}/history`).then(r=>{if(active)setItems(r.data.items);}).catch(()=>{if(active)setError("Stage history is unavailable for this record.");});return()=>{active=false;};},[context.module,context.kind,recordId]);
  return <section className="pipeline-history"><h3>Recorded stage history</h3>{error?<p role="alert">{error}</p>:!items?<p>Loading history…</p>:items.length?items.map(item=><p key={item.id}><strong>{item.previous_stage_name||item.previous_stage} → {item.stage_name||item.stage}</strong><br/><time>{new Date(item.at).toLocaleString()}</time></p>):<p>No stage transitions recorded since tracking was enabled. Earlier stage durations are unknown.</p>}</section>;
}

export function useRecordedStageAges(context:PipelineContext|undefined,records:Array<{id:string;stageId:string}>){
 const [ages,setAges]=useState<Record<string,{days?:number;entered_at?:string;next_action_at?:string|null}>>({});
 const key=records.map(r=>`${r.id}:${r.stageId}`).join(",");
 useEffect(()=>{let active=true;setAges({});if(context?.kind&&records.length){const chunks:Array<string[]>=[];for(let i=0;i<records.length;i+=100)chunks.push(records.slice(i,i+100).map(r=>r.id));void Promise.all(chunks.map(ids=>api.get(`/pipeline-workspaces/${context.module}/ages`,{params:{kind:context.kind,scope:context.scope,ids:ids.join(",")}}))).then(responses=>{if(active)setAges(Object.assign({},...responses.map(r=>r.data.items||{})));}).catch(()=>{/* Unknown history remains unknown. */});}return()=>{active=false;};},[context?.module,context?.kind,context?.scope,key]);
 return ages;
}
