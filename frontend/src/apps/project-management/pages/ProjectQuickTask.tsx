import {useRecordDraft} from "@/hooks/use-record-autosave";
import {useModuleAction} from "@/hooks/use-module-action";
import {useEffect,useState} from "react";
import {api} from "@/services/api";
import {workspaceError} from "./workspaceTypes";
type Props={initialTitle?:string;initialWorkType?:string;compact?:boolean;projectId:number;projectName:string;initialStatus:string;statuses:string[];onBusy:(v:boolean)=>void;onCreated:()=>Promise<void>;onFullForm:(p:URLSearchParams)=>void};
export default function ProjectQuickTask({initialTitle="",initialWorkType="Task",compact=false,projectId,projectName,initialStatus,statuses,onBusy,onCreated,onFullForm}:Props){
 const canCreate=useModuleAction("create");
 const [d,setD]=useState({title:initialTitle,description:"",status:initialStatus,priority:"Medium",work_type:initialWorkType,assignee:"",start_date:"",due_date:"",story_points:"",estimated_hours:""});
 const [people,setPeople]=useState<Array<{id:number;name:string}>>([]),[ready,setReady]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const set=(k:keyof typeof d,v:string)=>setD(x=>({...x,[k]:v}));
 useEffect(()=>{let active=true;api.get("/project-management/task-studio/options",{params:{project_id:projectId,compact:true}}).then(({data})=>{if(active){setPeople(data.people||[]);setReady(true);}}).catch(e=>{if(active)setError(workspaceError(e));});return()=>{active=false;};},[projectId]);
 const clearDraft=useRecordDraft(`project-task:${projectId}:${initialWorkType}`,d,setD,ready);
 const select=(label:string,k:keyof typeof d,choices:string[])=><label>{label}<select aria-label={label} value={d[k]} onChange={e=>set(k,e.target.value)}>{choices.map(v=><option key={v}>{v}</option>)}</select></label>;
 return <form className="pipeline-settings-panel" onSubmit={async e=>{e.preventDefault();if(busy||!canCreate)return;setBusy(true);onBusy(true);setError("");try{await api.post(`/project-management/projects/${projectId}/tasks`,{title:d.title.trim(),description:d.description||null,status:d.status,priority:d.priority,work_type:d.work_type,assignee_user_id:d.assignee?Number(d.assignee):null,start_date:d.start_date||null,due_date:d.due_date||null,story_points:d.story_points?Number(d.story_points):null,estimated_hours:d.estimated_hours?Number(d.estimated_hours):null,task_key:`TASK-${crypto.randomUUID().slice(0,12)}`});clearDraft();await onCreated();}catch(e){setError(workspaceError(e));}finally{setBusy(false);onBusy(false);}}}>
 <p className="text-sm text-muted-foreground">{projectName} · Only the task title is required. Other fields have sensible defaults.</p>
 <fieldset disabled={busy||!canCreate} className="space-y-4 border-0 p-0 m-0 min-w-0">
 <label>Task title *<input autoFocus required maxLength={255} placeholder="What needs to be done?" value={d.title} onChange={e=>set("title",e.target.value)}/></label>
 <details open={!compact}><summary>More task details</summary>
 <label>Description<textarea rows={3} maxLength={20000} placeholder="Context and acceptance criteria" value={d.description} onChange={e=>set("description",e.target.value)} className="w-full rounded-md border bg-background p-2 text-sm"/></label>
 <div className="grid grid-cols-2 gap-3">{select("Stage","status",[...new Set([initialStatus,...statuses])])}{select("Priority","priority",["Low","Medium","High","Urgent"])}</div>
 <label>Assignee<select aria-label="Assignee" disabled={!ready} value={d.assignee} onChange={e=>set("assignee",e.target.value)}><option value="">{ready?"Unassigned":"Loading project members…"}</option>{people.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
 {select("Task type","work_type",["Task","Bug","Story","Improvement"])}
 <div className="grid grid-cols-2 gap-3">
 <label>Start date<input type="date" max={d.due_date||undefined} value={d.start_date} onChange={e=>set("start_date",e.target.value)}/></label>
 <label>Due date<input type="date" min={d.start_date||undefined} value={d.due_date} onChange={e=>set("due_date",e.target.value)}/></label>
 <label>Estimate (hours)<input type="number" min="0" step="0.25" placeholder="Not estimated" value={d.estimated_hours} onChange={e=>set("estimated_hours",e.target.value)}/></label>
 <label>Story points<input type="number" min="0" step="1" placeholder="Not estimated" value={d.story_points} onChange={e=>set("story_points",e.target.value)}/></label>
 </div></details></fieldset>
 {error&&<p role="alert" className="pipeline-error">{error}</p>}
 <footer className="pipeline-quick-task-footer"><button type="submit" data-save-action className="pipeline-primary" disabled={busy||!canCreate||!d.title.trim()}>{busy?"Creating…":"Create task"}</button>
 <button type="button" disabled={busy} onClick={()=>onFullForm(new URLSearchParams({projectId:String(projectId),...d,people:d.assignee}))}>Open full task form</button></footer>
 </form>;
}
