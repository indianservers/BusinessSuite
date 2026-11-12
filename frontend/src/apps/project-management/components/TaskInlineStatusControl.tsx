import {useState} from "react";
import {Link} from "react-router-dom";
import * as Popover from "@radix-ui/react-popover";
import {ChevronDown} from "lucide-react";
import {statusTone} from "@/design-system/components";
import TaskStatusControl from "./TaskStatusControl";
import {type WorkTask,workspaceError} from "../pages/workspaceTypes";

/** Load the existing workflow choices only while an inline editor is open. */
export default function TaskInlineStatusControl({task,disabled,onSave}:{task:WorkTask;disabled?:boolean;onSave:(status:string)=>Promise<boolean>}){
 const [open,setOpen]=useState(false),[error,setError]=useState("");
 const href=`/pms/tasks/${task.id}`;
 return <Popover.Root open={open} onOpenChange={next=>{setOpen(next);if(next)setError("");}}>
  <Popover.Trigger role="combobox" aria-label={`Status for ${task.title}`} className="kf-status" data-tone={statusTone(task.status)} disabled={disabled}>
   <i aria-hidden="true"/>{task.status}<ChevronDown size={13}/>
  </Popover.Trigger>
  <Popover.Portal><Popover.Content aria-label={`Status options for ${task.title}`} align="start" sideOffset={5} className="z-[1000] w-72 max-w-[calc(100vw-2rem)] rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg">
   <TaskStatusControl taskId={task.id} value={task.status} version={task.updated_at} disabled={disabled} approvalHref={href} onSave={async status=>{
    setError("");
    try{if(await onSave(status))setOpen(false);else setError("Change was not saved. Open task details to review the latest values before retrying.");}
    catch(failure){setError(workspaceError(failure));}
   }}/>
   {error&&<div role="alert" className="mt-2 text-xs text-destructive">{error} <Link className="underline" to={href}>Open task details</Link></div>}
  </Popover.Content></Popover.Portal>
 </Popover.Root>;
}
