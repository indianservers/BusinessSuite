import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "../pages/workspaceTypes";

type Approval = {id:number;status:string;current:boolean;target:string;steps:{id:number;assigned_to_user_id:number|null;reviewer:string;status:string;decision:string|null;reason:string|null;can_decide:boolean}[]};
type Data = {can_request:boolean;transitions:{target:string;approval_required:boolean}[];requests:Approval[]};
export default function TransitionApprovals({taskId,onChanged,disabled=false}:{taskId:number;onChanged?:()=>void;disabled?:boolean}) {
 const [data,setData] = useState<Data>();const [target,setTarget] = useState("");
 const [reason,setReason] = useState("");const [error,setError] = useState("");const [busy,setBusy] = useState(false);
 const url = `/project-management/tasks/${taskId}/transition-approvals`;
 async function load(){const response=await api.get<Data>(url);setData(response.data);setError("");}
 useEffect(()=>{let active=true;setData(undefined);setTarget("");setReason("");setError("");void api.get<Data>(url).then(r=>{if(active)setData(r.data);}).catch(e=>{if(active)setError(workspaceError(e));});return()=>{active=false;};},[taskId]);
 async function act(work:()=>Promise<unknown>){setBusy(true);setError("");try{await work();await load();setReason("");onChanged?.();}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 return <section aria-label="Transition approvals" className="space-y-3 rounded border p-3">
  <div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">Transition approvals</h3><Button variant="outline" disabled={busy} onClick={()=>void load().catch(e=>setError(workspaceError(e)))}>Refresh approvals</Button></div>
  {error&&<p role="alert" className="text-destructive">{error}</p>}
  {data&&<>
   {data.can_request&&data.transitions.some(t=>t.approval_required)&&<fieldset disabled={busy||disabled} className="flex flex-wrap items-end gap-2"><label>Requested status<NativeSelect aria-label="Requested status" value={target} onChange={e=>setTarget(e.target.value)}><option value="">Choose a transition</option>{data.transitions.filter(t=>t.approval_required).map(t=><option key={t.target}>{t.target}</option>)}</NativeSelect></label><Button disabled={!target} onClick={()=>void act(()=>api.post(url,{target}))}>Request transition approval</Button><p className="w-full text-xs text-muted-foreground">Save task edits first. Changes to the task or workflow invalidate the request. After every step is approved, apply the transition.</p></fieldset>}
   {!data.requests.length&&<p className="text-sm text-muted-foreground">No transition approval requests for this task.</p>}
   {data.requests.some(r=>r.steps.some(s=>s.can_decide))&&<label className="block text-sm">Review reason<textarea aria-label="Review reason" className="block w-full rounded border p-2" value={reason} onChange={e=>setReason(e.target.value)}/></label>}
   {data.requests.map(r=><div key={r.id} className="space-y-2 border-t pt-3"><p className="text-sm font-medium">Request #{r.id} → {r.target} · {r.status}{!r.current&&!["Applied","Rejected","Cancelled"].includes(r.status)?" · Out of date":""}</p>
    <ol className="list-inside list-decimal text-sm">{r.steps.map(s=><li key={s.id} className="py-1">{s.reviewer} · {s.decision||s.status}{s.reason&&<p>{s.reason}</p>}{s.can_decide&&<span className="ml-2 inline-flex gap-2"><Button disabled={busy||disabled} aria-label={`Approve review ${s.id}`} onClick={()=>void act(()=>api.put(`/workflow-engine/tasks/${s.id}/decision`,{decision:"approve",reason}))}>Approve</Button><Button variant="outline" disabled={busy||disabled} aria-label={`Reject review ${s.id}`} onClick={()=>void act(()=>api.put(`/workflow-engine/tasks/${s.id}/decision`,{decision:"reject",reason}))}>Reject</Button></span>}</li>)}</ol>
    {data.can_request&&r.current&&r.status==="Approved"&&<Button disabled={busy||disabled} onClick={()=>void act(()=>api.patch(`/project-management/tasks/${taskId}`,{status:r.target}))}>Apply approved transition</Button>}
   </div>)}
  </>}
 </section>;
}
