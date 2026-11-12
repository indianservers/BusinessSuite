import {useState} from "react";
import {Link} from "react-router-dom";
import {api} from "@/services/api";
import {useRefreshableEffect} from "@/lib/page-refresh";
import {NativeSelect} from "@/components/ui/native-select";
import {workspaceError} from "../pages/workspaceTypes";

type Choices={can_request:boolean;transitions:{target:string;approval_required:boolean}[];requests:{target:string;current:boolean;status:string}[]};
/** Reuses the workflow engine's permitted destinations and approval projection. */
export default function TaskStatusControl({taskId,value,version,disabled,onSave,approvalHref}:{taskId:number;value:string;version?:string|null;disabled?:boolean;onSave:(status:string)=>unknown;approvalHref?:string}){
 const [data,setData]=useState<Choices>(),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[retry,setRetry]=useState(0);
 useRefreshableEffect(()=>{
  let active=true;setLoading(true);setError("");setData(undefined);
  void api.get<Choices>(`/project-management/tasks/${taskId}/transition-approvals`).then(response=>{if(active)setData(response.data);}).catch(e=>{if(active)setError(workspaceError(e));}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[taskId,value,version,retry]);
 const needsReview=(target:string)=>!!data?.transitions.find(item=>item.target===target)?.approval_required&&!data.requests.some(request=>request.target===target&&request.current&&request.status==="Approved");
 const locked=disabled||loading||busy||!!error||!data?.can_request;
 return <div className="min-w-0 space-y-1">
  <NativeSelect aria-label="Task status" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} disabled={locked} onChange={async event=>{
   const next=event.target.value;
   if(locked||next===value||needsReview(next)||!data?.transitions.some(item=>item.target===next))return;
   setBusy(true);try{await onSave(next);}catch(e){setError(workspaceError(e));}finally{setBusy(false);}
  }}><option value={value}>{value}</option>{data?.transitions.filter(item=>item.target!==value).map(item=><option key={item.target} value={item.target} disabled={needsReview(item.target)}>{item.target}{needsReview(item.target)?" · approval required":""}</option>)}</NativeSelect>
  {loading&&<p role="status" className="text-xs text-muted-foreground">Loading allowed statuses…</p>}
  {error&&<div role="alert" className="text-xs text-destructive">Status choices could not be loaded. {error} <button type="button" className="underline" onClick={()=>setRetry(current=>current+1)}>Retry status choices</button></div>}
  {data?.can_request&&data.transitions.some(item=>needsReview(item.target))&&<p className="text-xs text-muted-foreground">{approvalHref?<Link className="underline" to={approvalHref}>Open full task details for transition approvals</Link>:"Use Transition approvals below to request a review."}</p>}
 </div>;
}
