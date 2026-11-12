import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import {NativeSelect} from "@/components/ui/native-select";
import {workspaceError} from "../pages/workspaceTypes";
import {useTaskStatusChoices,taskStatusNeedsReview} from "./useTaskStatusChoices";

/** Reuses the workflow engine's permitted destinations and approval projection. */
export default function TaskStatusControl({taskId,value,version,disabled,onSave,approvalHref,refreshKey}:{taskId:number;value:string;version?:string|null;disabled?:boolean;onSave:(status:string)=>unknown;approvalHref?:string;refreshKey?:number}){
 const {data,loading,error,retry}=useTaskStatusChoices({taskId,value,version,refreshKey});
 const [busy,setBusy]=useState(false),[saveError,setSaveError]=useState("");
 useEffect(()=>setSaveError(""),[taskId,value,version,refreshKey]);
 const needsReview=(target:string)=>taskStatusNeedsReview(data,target);
 const locked=disabled||loading||busy||!!error||!data?.can_request;
 return <div className="min-w-0 space-y-1">
  <NativeSelect aria-label="Task status" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} disabled={locked} onChange={async event=>{
   const next=event.target.value;
   if(locked||next===value||needsReview(next)||!data?.transitions.some(item=>item.target===next))return;
   setBusy(true);setSaveError("");try{await onSave(next);}catch(e){setSaveError(workspaceError(e));}finally{setBusy(false);}
  }}><option value={value}>{value}</option>{data?.transitions.filter(item=>item.target!==value).map(item=><option key={item.target} value={item.target} disabled={needsReview(item.target)}>{item.target}{needsReview(item.target)?" · approval required":""}</option>)}</NativeSelect>
  {loading&&<p role="status" className="text-xs text-muted-foreground">Loading allowed statuses…</p>}
  {error&&<div role="alert" className="text-xs text-destructive">Status choices could not be loaded. {error} <button type="button" className="underline" onClick={retry}>Retry status choices</button></div>}
  {saveError&&<p role="alert" className="text-xs text-destructive">Status change was not confirmed. {saveError}</p>}
  {data?.can_request&&data.transitions.some(item=>needsReview(item.target))&&<p className="text-xs text-muted-foreground">{approvalHref?<Link className="underline" to={approvalHref}>Open full task details for transition approvals</Link>:"Use Transition approvals below to request a review."}</p>}
 </div>;
}
