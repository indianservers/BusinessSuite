import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "../pages/workspaceTypes";
import AssigneePicker from "./AssigneePicker";
import { type Person } from "./people/peopleTypes";

export const managementBase = "/project-management/management";
type Execution = {revision:number;blocked_reason:string;responsible_user_id:number|null;review_date:string|null;evidence_required:boolean;evidence:string};
type Detail = {id:number;title:string;project_id:number;status:string;can_edit:boolean;execution:Execution;completion:{checklist:{id:number;title:string;done:boolean}[];subtasks:{id:number;title:string;done:boolean}[];blockers:string[]};note_sources:{id:number;title:string;href:string}[]};
export default function TaskExecutionPanel({taskId,people=[],onChanged,onDirtyChange,refreshKey}:{taskId:number;people?:Person[];onChanged?:()=>void;onDirtyChange?:(dirty:boolean)=>void;refreshKey?:string}) {
 const [data,setData]=useState<Detail>();const [draft,setDraft]=useState<Execution>();const [error,setError]=useState("");const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);
 const load=async()=>{const {data}=await api.get<Detail>(`${managementBase}/tasks/${taskId}`);setData(data);setDraft(data.execution);setError("");};
 useEffect(()=>{setData(undefined);setDraft(undefined);void load().catch(e=>setError(workspaceError(e)));},[taskId]);
 useEffect(()=>{if(data&&JSON.stringify(draft)===JSON.stringify(data.execution))void load().catch(e=>setError(workspaceError(e)));},[refreshKey]);
 const dirty=!!draft&&JSON.stringify(draft)!==JSON.stringify(data?.execution);
 useEffect(()=>{onDirtyChange?.(dirty);},[dirty,onDirtyChange]);
 useEffect(()=>{const guard=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue="";}};window.addEventListener("beforeunload",guard);return()=>window.removeEventListener("beforeunload",guard);},[dirty]);
 async function save(block=false){if(!draft)return;setBusy(true);setError("");try{const {data:updated}=await api.put<Detail>(`${managementBase}/tasks/${taskId}/execution`,draft);setData(updated);setDraft(updated.execution);if(block)await api.patch(`${managementBase}/tasks/${taskId}`,{status:"Blocked"});setNotice(block?"Task marked Blocked":"Execution details saved");await load();onChanged?.();}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 async function complete(){setBusy(true);setError("");try{await api.patch(`${managementBase}/tasks/${taskId}`,{status:"Done"});setNotice("Task completed");await load();onChanged?.();}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 return <section className="space-y-4 rounded-xl border bg-card p-4" aria-label="Task execution and completion">
 <h2 className="font-semibold">Execution & completion</h2>{error&&<p role="alert" className="text-destructive">{error} <button className="underline" onClick={()=>void load().catch(e=>setError(workspaceError(e)))}>Reload</button></p>}{notice&&<p role="status">{notice}</p>}
 {draft&&data?<><p className="text-sm">{data.title} · {data.status}</p><fieldset disabled={!data.can_edit||busy} className="space-y-3">
 <label className="block text-sm">Blocked reason<textarea className="block w-full rounded border p-2" value={draft.blocked_reason||""} onChange={e=>setDraft({...draft,blocked_reason:e.target.value})}/></label>
 <div className="block text-sm">Responsible person<AssigneePicker single label="Blocking responsible person" projectId={data.project_id} people={people} value={draft.responsible_user_id?[draft.responsible_user_id]:[]} onChange={ids=>setDraft({...draft,responsible_user_id:ids.at(-1)||null})}/></div>
 <label className="block text-sm">Next review date<Input type="date" value={draft.review_date||""} onChange={e=>setDraft({...draft,review_date:e.target.value||null})}/></label>
 <label className="flex gap-2 text-sm"><input type="checkbox" checked={draft.evidence_required} onChange={e=>setDraft({...draft,evidence_required:e.target.checked})}/>Require completion evidence</label>
 <label className="block text-sm">Completion evidence<textarea className="block w-full rounded border p-2" placeholder="Evidence link or delivery details" value={draft.evidence||""} onChange={e=>setDraft({...draft,evidence:e.target.value})}/></label>
 <p role="status" className="text-sm text-muted-foreground">{dirty?"Unsaved changes":"All execution details saved"}</p>
 <div className="flex flex-wrap gap-2"><Button type="button" disabled={!dirty} onClick={()=>void save()}>Save details</Button><Button type="button" variant="outline" disabled={!draft.blocked_reason?.trim()||!draft.responsible_user_id||!draft.review_date} onClick={()=>void save(true)}>Save & mark Blocked</Button></div>
 </fieldset>{!data.can_edit&&<p className="text-sm">Your project role does not allow task updates.</p>}
 <h3 className="font-medium">Before completing</h3>{data.completion.checklist.map(c=><label className="flex gap-2 text-sm" key={c.id}><input type="checkbox" checked={c.done} disabled={!data.can_edit||busy} onChange={e=>{setBusy(true);void api.patch(`/project-management/checklist/${c.id}`,{is_completed:e.target.checked}).then(load).catch(e=>setError(workspaceError(e))).finally(()=>setBusy(false));}}/>{c.title}</label>)}
 {data.completion.subtasks.map(t=><p key={t.id} className="text-sm">{t.done?"✓":"○"} <Link className="underline" to={`/pms/tasks/${t.id}`}>{t.title}</Link></p>)}
 {!data.completion.checklist.length&&!data.completion.subtasks.length&&<p className="text-sm text-muted-foreground">No checklist items or subtasks.</p>}
 {data.completion.blockers.map(b=><p className="text-sm text-amber-700" key={b}>{b}</p>)}
 <Button type="button" disabled={!data.can_edit||busy||dirty||!!data.completion.blockers.length||data.status==="Done"} onClick={()=>void complete()}>Complete task</Button>
 {data.note_sources.map(n=><p key={n.id} className="text-sm">Original note: <Link className="underline" to={n.href}>{n.title}</Link> · visible to authorized note readers</p>)}
 </>:!error&&<p role="status">Loading execution details…</p>}</section>;
}
