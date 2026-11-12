import {useState} from "react";
import {Link} from "react-router-dom";
import * as Popover from "@radix-ui/react-popover";
import {ChevronDown} from "lucide-react";
import {statusTone} from "@/design-system/components";
import TaskStatusControl from "./TaskStatusControl";
import TaskEditReview from "./TaskEditReview";
import {tasksAPI} from "../services/api";
import {type WorkTask,workspaceError} from "../pages/workspaceTypes";

/** Load the existing workflow choices only while an inline editor is open. */
export default function TaskInlineStatusControl({task,disabled,onSave,onRefresh}:{task:WorkTask;disabled?:boolean;onSave:(status:string,reviewed:WorkTask)=>Promise<boolean>;onRefresh:()=>Promise<void>}){
 const [open,setOpen]=useState(false),[error,setError]=useState("");
 const [snapshot,setSnapshot]=useState(task),[busy,setBusy]=useState(false);
 const [failed,setFailed]=useState<{status:string;latest?:WorkTask}|null>(null);
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
 return <Popover.Root open={open} onOpenChange={next=>{if(busy)return;setOpen(next);if(next&&!failed){setSnapshot(task);setError("");}}}>
  <Popover.Trigger role="combobox" aria-label={`Status for ${task.title}`} className="kf-status" data-tone={statusTone(task.status)} disabled={disabled}>
   <i aria-hidden="true"/>{task.status}{failed&&<span className="text-xs"> · Unsaved change</span>}<ChevronDown size={13}/>
  </Popover.Trigger>
  <Popover.Portal><Popover.Content aria-label={`Status options for ${task.title}`} align="start" sideOffset={5} collisionPadding={12} style={{maxHeight:"min(70dvh, var(--radix-popover-content-available-height))"}} className="z-[1000] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg">
   <TaskStatusControl taskId={task.id} value={snapshot.status} version={snapshot.updated_at} disabled={disabled||busy||!!failed} approvalHref={href} onSave={status=>save(status,snapshot)}/>
   {failed&&<TaskEditReview changes={{status:failed.status}} latest={failed.latest} busy={busy} canEdit={!disabled} people={[]} onReview={()=>void review()} onApply={()=>{if(failed.latest)void save(failed.status,failed.latest);}} onDiscard={()=>void review(true)}/>}
   {error&&<div role="alert" className="mt-2 text-xs text-destructive">{error} <Link className="underline" to={href}>Open task details</Link></div>}
  </Popover.Content></Popover.Portal>
 </Popover.Root>;
}
