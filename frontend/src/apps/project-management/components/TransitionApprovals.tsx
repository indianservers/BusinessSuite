import { useEffect, useRef, useState } from "react";
import { syncScope } from "@/shared/record-sync/store";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { useMobile } from "@/components/mobile/useMobile";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "../pages/workspaceTypes";
import "./transition-approval-controls-mobile.css";

type Approval = {id:number;status:string;current:boolean;target:string;steps:{id:number;assigned_to_user_id:number|null;reviewer:string;status:string;decision:string|null;reason:string|null;can_decide:boolean}[]};
type Data = {can_request:boolean;transitions:{target:string;approval_required:boolean}[];requests:Approval[]};
type Props={taskId:number;onChanged?:()=>void;disabled?:boolean;registerLeaveGuard?:(guard:(()=>boolean)|undefined)=>void};
export default function TransitionApprovals(props:Props){
 const scope=useMobileContext();
 return <ApprovalContents key={scope} {...props}/>;
}
function ApprovalContents({taskId,onChanged,disabled=false,registerLeaveGuard}:Props) {
 const phone=useMobile(480),pending=useRef(false),reading=useRef(false);
 const mounted=useRef(true),currentTask=useRef(taskId),saved=useRef(false);
 currentTask.current=taskId;
 const [awaitingRefresh,setAwaitingRefresh]=useState(false);
 const [dirty,setDirty]=useState(false);
 const leave=()=>{
  if(!phone)return true;
  if(pending.current)return false;
  if(dirty&&!window.confirm("Discard unsaved transition review changes?"))return false;
  setDirty(false);return true;
 };
 useEffect(()=>{
  registerLeaveGuard?.(leave);
  if(!phone)return()=>registerLeaveGuard?.(undefined);
  const unload=(event:BeforeUnloadEvent)=>{if(dirty||pending.current){event.preventDefault();event.returnValue="";}};
  const click=(event:MouseEvent)=>{
   if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
   const link=(event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement|null;
   if(!link||link.hasAttribute("download")||link.target&&link.target!=="_self")return;
   const next=new URL(link.href,location.href);
   if(next.origin===location.origin&&next.pathname===location.pathname&&next.search===location.search)return;
   if(!leave()){event.preventDefault();event.stopPropagation();}
  };
  window.addEventListener("beforeunload",unload);document.addEventListener("click",click,true);
  return()=>{registerLeaveGuard?.(undefined);window.removeEventListener("beforeunload",unload);document.removeEventListener("click",click,true);};
 },[phone,dirty,registerLeaveGuard]);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const [loading,setLoading]=useState(true);
 const [data,setData] = useState<Data>();const [target,setTarget] = useState("");
 const [reason,setReason] = useState("");const [error,setError] = useState("");const [busy,setBusy] = useState(false);
 const url = `/project-management/tasks/${taskId}/transition-approvals`;
 function owns(owned:boolean,scope:string,task:number){return !owned||mounted.current&&scope===syncScope()&&task===currentTask.current;}
 async function load(){
  if(phone&&reading.current)return;
  const owned=phone,scope=syncScope(),task=taskId;
  if(owned){reading.current=true;setLoading(true);}
  try{const response=await api.get<Data>(url);if(!owns(owned,scope,task))return;setData(response.data);setError("");
   if(owned&&saved.current){saved.current=false;setAwaitingRefresh(false);setReason("");setDirty(false);onChanged?.();}
  }catch(e){if(owns(owned,scope,task))throw e;}
  finally{if(owns(owned,scope,task)){reading.current=false;setLoading(false);}}
 }
 useEffect(()=>{let active=true;const owned=phone,scope=syncScope(),task=taskId;setData(undefined);setTarget("");setReason("");setError("");if(owned)setDirty(false);if(owned){pending.current=false;saved.current=false;setBusy(false);setAwaitingRefresh(false);}reading.current=true;setLoading(true);void api.get<Data>(url).then(r=>{if(active&&owns(owned,scope,task))setData(r.data);}).catch(e=>{if(active&&owns(owned,scope,task))setError(workspaceError(e));}).finally(()=>{if(active&&owns(owned,scope,task)){reading.current=false;setLoading(false);}});return()=>{active=false;};},[taskId]);
 async function act(work:()=>Promise<unknown>){
  if(phone&&(pending.current||reading.current||disabled||saved.current))return;
  const owned=phone,scope=syncScope(),task=taskId;
  if(owned)pending.current=true;setBusy(true);setError("");
  try{await work();if(!owns(owned,scope,task))return;
   if(owned){saved.current=true;setAwaitingRefresh(true);setDirty(false);}
   await load();if(!owns(owned,scope,task))return;
   if(!owned){setReason("");onChanged?.();}
  }catch(e){if(owns(owned,scope,task))setError(workspaceError(e));}
  finally{if(owns(owned,scope,task)){pending.current=false;setBusy(false);}}
 }
 return <section aria-label="Transition approvals" className="transition-approval-controls space-y-3 rounded border p-3" aria-busy={phone ? busy||loading : undefined}>
  <div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">Transition approvals</h3><Button variant="outline" disabled={busy||phone&&loading} onClick={()=>void load().catch(e=>setError(workspaceError(e)))}>Refresh approvals</Button></div>
  {phone&&(busy||loading)&&<p role="status">{busy?"Saving transition review…":data?"Refreshing approvals…":"Loading approvals…"}</p>}
  {phone&&awaitingRefresh&&!busy&&<p role="status">Saved. Refresh approvals to load the latest state before another action.</p>}
  {phone&&!awaitingRefresh&&error&&data&&<p role="status">Showing last loaded approvals. Refresh approvals to try again.</p>}
  {error&&<p role="alert" className="text-destructive">{error}</p>}
  {data&&<>
   {data.can_request&&data.transitions.some(t=>t.approval_required)&&<fieldset disabled={busy||disabled||phone&&(loading||awaitingRefresh)} className="flex flex-wrap items-end gap-2"><label>Requested status<NativeSelect aria-label="Requested status" value={target} onChange={e=>{setTarget(e.target.value);if(phone)setDirty(true);}}><option value="">Choose a transition</option>{data.transitions.filter(t=>t.approval_required).map(t=><option key={t.target}>{t.target}</option>)}</NativeSelect></label><Button disabled={!target} onClick={()=>void act(()=>api.post(url,{target}))}>Request transition approval</Button><p className="w-full text-xs text-muted-foreground">Save task edits first. Changes to the task or workflow invalidate the request. After every step is approved, apply the transition.</p></fieldset>}
   {!data.requests.length&&<p className="text-sm text-muted-foreground">No transition approval requests for this task.</p>}
   {data.requests.some(r=>r.steps.some(s=>s.can_decide))&&<label className="block text-sm">Review reason<textarea aria-label="Review reason" className="block w-full rounded border p-2" value={reason} disabled={phone&&(busy||disabled||loading||awaitingRefresh)} onChange={e=>{setReason(e.target.value);if(phone)setDirty(true);}}/></label>}
   {data.requests.map(r=><div key={r.id} className="space-y-2 border-t pt-3"><p className="text-sm font-medium">Request #{r.id} → {r.target} · {r.status}{!r.current&&!["Applied","Rejected","Cancelled"].includes(r.status)?" · Out of date":""}</p>
    <ol className="list-inside list-decimal text-sm">{r.steps.map(s=><li key={s.id} className="py-1">{s.reviewer} · {s.decision||s.status}{s.reason&&<p>{s.reason}</p>}{s.can_decide&&<span className="ml-2 inline-flex gap-2"><Button disabled={busy||disabled||phone&&(loading||awaitingRefresh)} aria-label={`Approve review ${s.id}`} onClick={()=>void act(()=>api.put(`${url}/${r.id}/steps/${s.id}/decision`,{decision:"approve",reason}))}>Approve</Button><Button variant="outline" disabled={busy||disabled||phone&&(loading||awaitingRefresh)} aria-label={`Reject review ${s.id}`} onClick={()=>void act(()=>api.put(`${url}/${r.id}/steps/${s.id}/decision`,{decision:"reject",reason}))}>Reject</Button></span>}</li>)}</ol>
    {data.can_request&&r.current&&r.status==="Approved"&&<Button disabled={busy||disabled||phone&&(loading||awaitingRefresh)} onClick={()=>void act(()=>api.patch(`/project-management/tasks/${taskId}`,{status:r.target}))}>Apply approved transition</Button>}
   </div>)}
  </>}
 </section>;
}
