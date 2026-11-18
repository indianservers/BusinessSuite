import {useEffect,useRef,useState} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {Link} from "react-router-dom";
import {Button} from "@/components/ui/button";
import {api} from "@/services/api";
import {useMobileDraftGuard} from "@/components/mobile/useMobileDraftGuard";
import {tasksAPI} from "../services/api";
import {type WorkTask,workspaceError} from "../pages/workspaceTypes";
import {taskStatusNeedsReview,type TaskStatusChoices} from "./useTaskStatusChoices";

type Review={task:WorkTask;allowed:boolean;reason:string};
export default function BulkTaskCompletion({records,canEdit,onClose,onRefresh,onNotice}:{records:WorkTask[];canEdit:boolean;onClose:(applied:boolean)=>void;onRefresh:()=>Promise<void>;onNotice:(message:string)=>void}){
 const [rows,setRows]=useState<Review[]>([]),[phase,setPhase]=useState<"loading"|"idle"|"applying">("loading"),[error,setError]=useState(""),[mustReview,setMustReview]=useState(false);
 const alive=useRef(true),generation=useRef(0),applying=useRef(false);
 const reviewAbort=useRef<AbortController|null>(null);
 const requestLeave=useMobileDraftGuard({enabled:true,guardHistory:true,dirty:false,draftKey:"bulk-completion",pending:()=>applying.current,onDiscard:()=>{},message:""});
 async function review(){
  reviewAbort.current?.abort();const controller=new AbortController();reviewAbort.current=controller;
  const current=++generation.current;setPhase("loading");setRows([]);setError("");setMustReview(false);
  if(records.length>200){setError("Select at most 200 tasks for one completion review.");setPhase("idle");return;}
  const results:Review[]=new Array(records.length);let next=0;
  // Bound concurrent reads; the API remains the authority for completion rules.
  await Promise.all(Array.from({length:Math.min(4,records.length)},async()=>{
   while(next<records.length&&alive.current&&current===generation.current&&!controller.signal.aborted){const index=next++,record=records[index];
    try{
     const task={...record,...await tasksAPI.get(record.id,true,controller.signal)};
     if(controller.signal.aborted||!alive.current||current!==generation.current)return;
     const {data}=await api.get<TaskStatusChoices>(`/project-management/tasks/${task.id}/transition-approvals`,{recordCache:false,_recordSyncBypass:true,headers:{"Cache-Control":"no-cache"},signal:controller.signal});
     const completed=["Done","Completed","Closed","Resolved"].includes(task.status);
     const allowed=!completed&&data.can_request&&data.transitions.some(item=>item.target==="Done")&&!taskStatusNeedsReview(data,"Done");
     const reason=completed?"Already completed":!data.can_request?"Completion is not permitted":!data.transitions.some(item=>item.target==="Done")?`Workflow does not allow ${task.status} → Done`:taskStatusNeedsReview(data,"Done")?"Approval required":"Done is allowed; completion checks run when applied";
     results[index]={task,allowed,reason};
    }catch(failure){results[index]={task:record,allowed:false,reason:`Could not verify task. ${workspaceError(failure)}`};}
   }
  }));
  if(alive.current&&current===generation.current&&!controller.signal.aborted){setRows(results);setPhase("idle");}
 }
 useEffect(()=>{alive.current=true;void review();return()=>{alive.current=false;generation.current++;reviewAbort.current?.abort();};},[records]);
 const allowed=rows.filter(row=>row.allowed);
 async function apply(){
  if(!canEdit||phase!=="idle"||mustReview||!allowed.length||applying.current)return;
  applying.current=true;setPhase("applying");setError("");
  try{
   const result=await tasksAPI.bulkUpdate({task_ids:allowed.map(row=>row.task.id),status:"Done",expected_updated_at_by_task:Object.fromEntries(allowed.map(row=>[row.task.id,row.task.updated_at??null]))});
   let notice=`${result.updated_count} tasks completed. ${rows.length-allowed.length} selected tasks were not included.`;
   try{await onRefresh();}catch(failure){notice+=` Collection refresh failed. Refresh page data before continuing. ${workspaceError(failure)}`;}
   if(alive.current){onNotice(notice);onClose(true);}
  }catch(failure){if(alive.current){setError(`Completion was not confirmed. ${workspaceError(failure)}`);setMustReview(true);}}
  finally{applying.current=false;if(alive.current)setPhase("idle");}
 }
 return <Dialog.Root open onOpenChange={open=>{if(!open&&requestLeave())onClose(false);}}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[1900] bg-black/40"/><Dialog.Content aria-describedby="bulk-completion-help" className="fixed left-1/2 top-1/2 z-[1901] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border bg-background p-4 shadow-xl" style={{maxHeight:"calc(100dvh - 2rem)"}} onEscapeKeyDown={event=>{if(applying.current)event.preventDefault();}}>
  <Dialog.Title className="text-lg font-semibold">Review selected task completion</Dialog.Title><Dialog.Description id="bulk-completion-help" className="mt-2 text-sm text-muted-foreground">Review the allowed subset before applying. The server rechecks completion requirements, approvals and access. Tasks without an allowed transition are left out.</Dialog.Description>
  {phase==="loading"&&<p role="status" className="my-3">Checking {records.length} selected tasks…</p>}
  {error&&<p role="alert" className="my-3 text-sm text-destructive">{error}</p>}
  {!!rows.length&&<><p role="status" className="my-3 text-sm font-medium">{allowed.length} allowed transitions · {rows.length-allowed.length} not included · {rows.length} selected</p><ul className="space-y-2">{rows.map(row=><li key={row.task.id} className="min-w-0 rounded border p-3 text-sm"><strong className="break-words">{row.task.title}</strong><p>{row.task.status} · {row.reason}</p><Link className="underline" to={`/pms/tasks/${row.task.id}`}>Review task {row.task.task_key||`#${row.task.id}`}</Link></li>)}</ul></>}
  <div className="mt-4 flex flex-wrap gap-2"><Button type="button" disabled={!canEdit||phase!=="idle"||mustReview||!allowed.length} onClick={()=>void apply()}>{phase==="applying"?"Completing…":`Complete ${allowed.length} allowed tasks`}</Button><Button type="button" variant="outline" disabled={phase!=="idle"} onClick={()=>void review()}>Review latest tasks</Button><Button type="button" variant="outline" disabled={phase==="applying"} onClick={()=>onClose(false)}>Cancel</Button></div>
 </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
