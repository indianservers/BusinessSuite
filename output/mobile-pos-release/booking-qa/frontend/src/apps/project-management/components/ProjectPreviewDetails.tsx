import { Button } from "@/components/ui/button";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { tasksAPI, milestonesAPI, activityAPI, filesAPI } from "../services/api";
import { api } from "@/services/api";
import { savedWithUndo } from "@/components/actions/undo-feedback";
import { formatDate } from "@/lib/utils";
import { workspaceError } from "../pages/workspaceTypes";
import { blankNote, noteBase } from "../pages/notesTypes";
import type { PMSTask, PMSMilestone, PMSActivity, PMSFileAsset } from "../types";

export default function ProjectPreviewDetails({ projectId, canManage = false, onChanged }: { projectId: number; canManage?: boolean; onChanged?: () => Promise<void> }) {
  const [tab, setTab] = useState("tasks"), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const [tasks, setTasks] = useState<PMSTask[]>([]), [milestones, setMilestones] = useState<PMSMilestone[]>([]), [activity, setActivity] = useState<PMSActivity[]>([]), [files, setFiles] = useState<PMSFileAsset[]>([]);
  const [revision, setRevision] = useState(0), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [milestoneName, setMilestoneName] = useState(""), [milestoneDue, setMilestoneDue] = useState("");
  const [noteTitle, setNoteTitle] = useState(""), [noteText, setNoteText] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    async function load() {
      const allTasks: PMSTask[] = [];
      for (let skip = 0; ; skip += 100) { const rows = await tasksAPI.list(projectId, skip, 100); allTasks.push(...rows); if (rows.length < 100) break; }
      return allTasks;
    }
    async function loadMilestones() {
      const all: PMSMilestone[]=[];
      for(let skip=0;;skip+=100){const rows=await milestonesAPI.list(projectId,skip,100);all.push(...rows);if(rows.length<100)break;}
      return all;
    }
    void Promise.allSettled([load(), loadMilestones(),activityAPI.list(projectId,{limit:10}),filesAPI.list({project_id:projectId})]).then(results => {
      if (!active) return;
      const [t,m,a,f]=results;
      if(t.status === "fulfilled")setTasks(t.value);else setError(workspaceError(t.reason));
      if(m.status === "fulfilled")setMilestones(m.value);else setError(workspaceError(m.reason));
      if(a.status === "fulfilled")setActivity(a.value);else setError(workspaceError(a.reason));
      if(f.status === "fulfilled")setFiles(f.value);else setError(workspaceError(f.reason));
      setLoading(false);
    });
    return () => { active=false; };
  },[projectId,revision]);
  const today = new Date().toLocaleDateString("en-CA");
  const isOverdue = (t: PMSTask) => !!t.due_date && t.due_date.slice(0,10) < today && !["Done","Cancelled"].includes(t.status);
  const sorted = [...tasks].sort((a,b) => Number(isOverdue(b))-Number(isOverdue(a)) || (a.due_date || "9999").localeCompare(b.due_date || "9999"));
  const nextMilestone = [...milestones].filter(m => !["Completed","Cancelled"].includes(m.status)).sort((a,b)=>(a.due_date || "9999").localeCompare(b.due_date || "9999"))[0];
  async function change(run: () => Promise<unknown>, success: string) {
    if(busy)return;
    setBusy(true);setError("");
    try {await run();setNotice(success);setRevision(r=>r+1);await onChanged?.();} catch(e){setError(workspaceError(e));} finally{setBusy(false);}
  }
  return <section className="portfolio-preview-details space-y-3">
    {nextMilestone && <div className="rounded border p-3"><strong>Next milestone: {nextMilestone.name}</strong><p className="text-xs">{formatDate(nextMilestone.due_date || null)} · {nextMilestone.status}</p></div>}
    {activity[0] && <p className="text-xs text-muted-foreground">Latest update: {activity[0].summary} · {formatDate(activity[0].created_at)}</p>}
    <div className="flex flex-wrap gap-2" role="group" aria-label="Preview details">{["tasks","milestones","activity","files","note"].map(t=><button type="button" key={t} aria-pressed={tab===t} className="rounded border px-3 py-2 text-xs capitalize aria-pressed:bg-primary/10" onClick={()=>setTab(t)}>{t === "note" ? "Quick note" : t}</button>)}</div>
    {error && <p role="alert" className="text-destructive">{error} <button type="button" onClick={()=>setRevision(r=>r+1)}>Retry preview data</button></p>}
    {notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading project details…</p> : tab==="tasks" ? <><p className="text-xs text-muted-foreground">Overdue tasks first · <Link className="text-primary" to={`/pms/projects/${projectId}/board`}>View all tasks</Link></p>{sorted.slice(0,20).map(t=><div key={t.id} className="flex items-center gap-2 border-b py-2">{canManage && <input type="checkbox" aria-label={`Complete ${t.title}`} checked={t.status==="Done"} disabled={busy || t.status==="Cancelled"} onChange={e=>{const status=e.target.checked?"Done":"To Do";void change(async()=>{await tasksAPI.update(t.id,{status});savedWithUndo(`${t.title} updated`,async()=>{await tasksAPI.update(t.id,{status:t.status});setRevision(r=>r+1);await onChanged?.();});},"Task updated");}}/>}<Link className="min-w-0 flex-1 text-xs" to={`/pms/projects/${projectId}/tasks/${t.id}`}><b>{t.task_key} · {t.title}</b><span className="block">{t.status} · {formatDate(t.due_date || null)}{isOverdue(t)?" · Overdue task":""}</span></Link></div>)}{!tasks.length&&<p className="text-xs">No tasks added yet.</p>}</> : tab==="milestones" ? <>{milestones.map(m=><div key={m.id} className="border-b py-2 text-xs"><b>{m.name}</b><p>{m.status} · {formatDate(m.due_date || null)}</p></div>)}{canManage&&<SmartCreateSection title="Add milestone" size="compact"><form className="grid gap-2" onSubmit={e=>{e.preventDefault();void change(async()=>{await milestonesAPI.create(projectId,{name:milestoneName.trim(),due_date:milestoneDue||undefined,status:"Not Started"});setMilestoneName("");setMilestoneDue("");},"Milestone added");}}><label>Milestone name<input required maxLength={200} aria-label="Quick milestone name" value={milestoneName} onChange={e=>setMilestoneName(e.target.value)} className="block w-full rounded border bg-background p-2"/></label><label>Due date<input type="date" aria-label="Quick milestone deadline" value={milestoneDue} onChange={e=>setMilestoneDue(e.target.value)} className="block rounded border bg-background p-2"/></label><Button variant="default" type="submit" disabled={busy||!milestoneName.trim()} className="rounded border p-2">Add milestone</Button></form></SmartCreateSection>}</> : tab==="activity" ? <>{activity.map(a=><div key={a.id} className="border-b py-2 text-xs"><p>{a.summary}</p><small>{formatDate(a.created_at)}</small></div>)}{!activity.length&&<p>No recent activity.</p>}</> : tab==="files" ? <>{[...files].sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,10).map(f=><div key={f.id} className="flex justify-between border-b py-2 text-xs"><span>{f.original_name || f.file_name}</span><Link to={`/pms/projects/${projectId}/files`}>Open files</Link></div>)}{!files.length&&<p>No files added yet.</p>}<Link className="text-primary" to={`/pms/projects/${projectId}/files`}>All project files</Link></> : <SmartCreateSection title="Save private note" size="compact"><form className="grid gap-2" onSubmit={e=>{e.preventDefault();void change(async()=>{await api.post(noteBase,{...blankNote({kind:"project",title:"Project notes",project_id:projectId}),title:noteTitle.trim(),content:noteText});setNoteTitle("");setNoteText("");},"Private project note saved");}}><p className="text-xs text-muted-foreground">Notes are private to you.</p><input required maxLength={200} aria-label="Quick note title" placeholder="Note title" className="rounded border bg-background p-2" value={noteTitle} onChange={e=>setNoteTitle(e.target.value)}/><textarea required aria-label="Quick note text" maxLength={20000} placeholder="Write a note…" className="rounded border bg-background p-2" value={noteText} onChange={e=>setNoteText(e.target.value)}/><Button variant="outline" type="submit" disabled={busy||!noteTitle.trim()||!noteText.trim()} className="rounded border p-2">Save private note</Button><Link to={`/pms/projects/${projectId}/notes`}>Open my project notes</Link></form></SmartCreateSection>}
  </section>;
}
