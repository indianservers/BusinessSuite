import {useEffect,useState} from "react";
import {Link} from "react-router-dom";
import * as Popover from "@radix-ui/react-popover";
import {ChevronDown} from "lucide-react";
import {statusTone} from "@/design-system/components";
import TaskStatusControl from "./TaskStatusControl";
import TaskEditReview from "./TaskEditReview";
import {tasksAPI} from "../services/api";
import {useMobileDraftGuard} from "@/components/mobile/useMobileDraftGuard";
import UnsavedTaskDialog from "./UnsavedTaskDialog";
import {useInlineTaskEditState} from "./InlineTaskEditState";
import {type WorkTask,workspaceError} from "../pages/workspaceTypes";

/** Load the existing workflow choices only while an inline editor is open. */
export default function TaskInlineStatusControl({task,disabled,onSave,onRefresh}:{task:WorkTask;disabled?:boolean;onSave:(status:string,reviewed:WorkTask)=>Promise<boolean>;onRefresh:()=>Promise<void>}){
 const [open,setOpen]=useState(false),[error,setError]=useState("");
 const [snapshot,setSnapshot]=useState(task);
 const {failed,setFailed,busy,setBusy}=useInlineTaskEditState(task);
 useEffect(()=>{if(failed||busy)setOpen(true);},[failed,busy]);
 const [discardAction,setDiscardAction]=useState<(()=>void)|null>(null);
 const requestLeave=useMobileDraftGuard({guardHistory:true,enabled:open||!!failed||busy,dirty:!!failed,draftKey:JSON.stringify([task.id,failed?.status]),pending:()=>busy,onDiscard:()=>{setFailed(null);setError("");},message:"Discard your unsaved status change?",confirmDiscard:confirm=>setDiscardAction(()=>confirm)});
 const href=`/pms/tasks/${task.id}`;
 const save=async(status:string,reviewed:WorkTask)=>{
  if(disabled||busy)return;
  setBusy(true);setError("");
  try{if(await onSave(status,reviewed)){setFailed(null);setOpen(false);}else setFailed({status});}
  catch(failure){setFailed({status});setError(workspaceError(failure));}
  finally{setBusy(false);}
 };
 const review=async(discard=false)=>{
  setBusy(true);setError("");setFailed(current=>current?{status:current.status}:null);
  try{
   const latest={...task,...await tasksAPI.get(task.id)};
   if(discard){await onRefresh();setSnapshot(latest);setFailed(null);setOpen(false);}
   else setFailed(current=>current?{...current,latest}:null);
  }catch(failure){setError(workspaceError(failure));}
  finally{setBusy(false);}
 };
 return <><UnsavedTaskDialog abovePopover description="Your unsaved status change will be discarded if you leave. Changes already saved will stay saved." onDiscard={discardAction} onKeep={()=>setDiscardAction(null)}/><Popover.Root modal open={open} onOpenChange={next=>{if(busy||discardAction)return;if(!next&&!requestLeave(()=>setOpen(false)))return;setOpen(next);if(next&&!failed){setSnapshot(task);setError("");}}}>
  <Popover.Trigger role="combobox" aria-label={`Status for ${task.title}`} className="kf-status" data-tone={statusTone(task.status)} disabled={disabled}>
   <i aria-hidden="true"/>{task.status}{failed&&<span className="text-xs"> · Unsaved change</span>}<ChevronDown size={13}/>
  </Popover.Trigger>
  <Popover.Portal><Popover.Content aria-label={`Status options for ${task.title}`} align="start" sideOffset={5} collisionPadding={12} style={{maxHeight:"min(70dvh, var(--radix-popover-content-available-height))"}} className="z-[1000] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg">
   <TaskStatusControl taskId={task.id} value={snapshot.status} version={snapshot.updated_at} disabled={disabled||busy||!!failed} approvalHref={href} onSave={status=>save(status,snapshot)}/>
   {failed&&<TaskEditReview changes={{status:failed.status}} latest={failed.latest} busy={busy} canEdit={!disabled} people={[]} onReview={()=>void review()} onApply={()=>{if(failed.latest)void save(failed.status,failed.latest);}} onDiscard={()=>void review(true)}/>}
   {error&&<div role="alert" className="mt-2 text-xs text-destructive">{error} <Link className="underline" to={href}>Open task details</Link></div>}
  </Popover.Content></Popover.Portal>
 </Popover.Root></>;
}
