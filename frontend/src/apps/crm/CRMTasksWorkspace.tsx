import { useInitialLoading } from "@/hooks/use-initial-loading";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
import CrmRecordFields, { useCrmFieldForm, CrmFieldsReadOnly } from "@/shared/custom-fields/CrmRecordFields";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useEffect, useRef, useState } from "react";
import { FileText, ListChecks, Pencil, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import TaskCreationForm, { type TaskCreationDraft } from "@/shared/productivity/TaskCreationForm";
import { richTextPlainText } from "@/components/rich-text/content";

type Task = { id: number; title: string; description?: string; status: string; priority: string; dueDate?: string; ownerId?: number; task_details?: Partial<TaskCreationDraft> };
type LegacyTask = { id: string; kind: string; title: string; content: string; status: string; due: string; taskDetails?: Partial<TaskCreationDraft> };
const defaults = (): TaskCreationDraft => ({ title: "", description: "", location: "General / workspace task", relatedRecord: "", parentId: "", workType: "Task", assignees: [], assignmentMode: "People", executionMode: "Shared task", reviewer: "", owner: "", priority: "Medium", status: "To Do", start: "", due: "", estimatedHours: "", acceptance: "", subtasks: [], attachments: [] });
const toDraft = (task: Task): TaskCreationDraft => ({ ...defaults(), ...task.task_details, title: task.title, description: task.description || "", status: task.status, priority: task.priority, due: task.dueDate?.slice(0, 10) || "" });
function errorMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Could not reach CRM. Your changes have not been saved. Please try again.";
}

export default function CRMTasksWorkspace({ legacyKey, onNotes }: { legacyKey: string; onNotes: () => void }) {
  const user = useAuthStore(s => s.user);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const initialLoading = useInitialLoading(loading);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [queue, setQueue] = useState("all");
  const [taskStatus, setTaskStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [mine, setMine] = useState(false);
  const [sort, setSort] = useState("due_date:asc");
  const [total, setTotal] = useState(0);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const customFieldForm=useCrmFieldForm("tasks",editing&&editing!=="new"?"edit":"create",editing&&editing!=="new"?editing.id:undefined);
  const [detailTask,setDetailTask]=useState<Task|null>(null);
  const [deleting, setDeleting] = useState<Task | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [legacy, setLegacy] = useState<LegacyTask[]>(() => {
    try { const entries = JSON.parse(localStorage.getItem(legacyKey) || "null")?.entries; return Array.isArray(entries) ? entries.filter((e: LegacyTask) => e.kind === "task" && typeof e.id === "string" && typeof e.title === "string") : []; }
    catch { return []; }
  });
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    api.get<{ items: Task[]; pages: number; total: number }>("/crm/tasks", { params: { page, per_page: 25, search, task_queue: queue, timezone, status: taskStatus, priority, owner_id: mine ? user?.id : undefined, sort_by: sort.split(":")[0], sort_order: sort.split(":")[1] } })
      .then(({ data }) => { if (active) { setTasks(data.items); setTotal(data.total ?? data.items.length); setPages(data.pages); if (page > Math.max(1, data.pages)) setPage(Math.max(1, data.pages)); } })
      .catch(e => { if (active) setError(errorMessage(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, search, refresh, queue, timezone, taskStatus, priority, mine, sort, user?.id]);
  function filterChange(update: () => void) { update(); setPage(1); }
  async function complete(task: Task) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    try {
      await api.patch(`/crm/tasks/${task.id}`, { status: "Done", task_details: { ...task.task_details, status: "Done" } });
      setMessage(`Completed “${task.title}”.`); setRefresh(v => v + 1);
    } catch (e) { setError(errorMessage(e)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  function payload(draft: TaskCreationDraft) {
    return { ...(user && draft.assignees.some(person => person === user.email || person === user.name) ? { owner_user_id: user.id } : {}), title: draft.title, description: draft.description, status: draft.status, priority: draft.priority, due_date: draft.due ? `${draft.due}T12:00:00Z` : null, task_details: draft };
  }
  async function save(draft: TaskCreationDraft, another: boolean) {
    const data = {...payload(draft),customFields:customFieldForm.validate()};
    if (editing && editing !== "new") await api.patch(`/crm/tasks/${editing.id}`, data);
    else { await api.post("/crm/tasks", data); customFieldForm.setValues({}); setPage(1); setSearch(""); }
    setMessage("Task saved to CRM."); setRefresh(v => v + 1);
    if (!another) setEditing(null);
  }
  async function remove() {
    if (!deleting || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    try { await api.delete(`/crm/tasks/${deleting.id}`); setDeleting(null); setMessage("Task deleted."); setRefresh(v => v + 1); }
    catch (e) { setError(errorMessage(e)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function importLegacy() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    try {
      for (const entry of legacy) {
        // Remove only confirmed saves from the old snapshot; preserve notes and failed tasks.
        const draft = { ...defaults(), ...entry.taskDetails, title: entry.title || "Untitled task", description: entry.content || "", status: entry.status || "To Do", due: entry.due || "" };
        await api.post("/crm/tasks", { ...payload(draft), import_key: entry.id });
        const snapshot = JSON.parse(localStorage.getItem(legacyKey) || "null");
        if (Array.isArray(snapshot?.entries)) { snapshot.entries = snapshot.entries.filter((e: LegacyTask) => e.id !== entry.id); localStorage.setItem(legacyKey, JSON.stringify(snapshot)); }
        setLegacy(items => items.filter(e => e.id !== entry.id));
      }
      setMessage("Browser tasks saved to CRM.");
    } catch (e) { setError(errorMessage(e)); }
    finally { setRefresh(v => v + 1); busyRef.current = false; setBusy(false); }
  }
  if (editing) return <TaskCreationForm additionalFields={<CrmRecordFields state={customFieldForm}/>}  key={editing === "new" ? "new" : editing.id} databaseBacked draftKey={`${legacyKey}:task-draft${editing === "new" ? "" : `:${editing.id}`}`} initialDraft={editing === "new" ? undefined : toDraft(editing)} tasks={tasks.filter(t => editing === "new" || t.id !== editing.id).map(t => ({ id: String(t.id), title: t.title, content: t.description || "" }))} onCreate={save} onCancel={() => setEditing(null)}/>;
  return <section className="space-y-4" aria-label="CRM tasks workspace">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">CRM tasks</h1><p className="text-sm text-muted-foreground">Saved to CRM. Access your tasks from any device.</p></div><button className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-primary-foreground" onClick={() => setEditing("new")}><Plus size={16}/>New task</button></header>
    <div className="flex gap-2"><button className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-primary-foreground" aria-pressed="true"><ListChecks size={16}/>Tasks</button><button className="inline-flex items-center gap-2 rounded-md border px-3 py-2" onClick={onNotes}><FileText size={16}/>Notes</button></div>
    {!!legacy.length && <div className="rounded-md border p-3">{legacy.length} tasks are still saved only in this browser. <button className="underline" disabled={busy} onClick={() => void importLegacy()}>{busy ? "Importing…" : "Save browser tasks to CRM"}</button></div>}
    {error && <p role="alert" className="text-red-600">{error} <button onClick={() => setRefresh(v => v + 1)} className="underline">Retry</button></p>}
    {message && <p role="status">{message}</p>}
    <nav aria-label="Task queues" className="flex flex-wrap gap-2">{[["all", "All tasks"], ["open", "Open"], ["overdue", "Overdue"], ["today", "Due today"], ["week", "Next 7 days"], ["unscheduled", "Unscheduled"], ["completed", "Completed"]].map(([value, label]) => <button key={value} aria-pressed={queue === value} className={`rounded-md border px-3 py-2 text-sm ${queue === value ? "bg-primary text-primary-foreground" : "bg-background"}`} onClick={() => filterChange(() => setQueue(value))}>{label}</button>)}</nav>
    <div className="flex flex-wrap items-center gap-3 rounded-md border p-3">
      <label className="text-sm">Status <select aria-label="Filter task status" className="rounded border bg-background p-2" value={taskStatus} onChange={e => filterChange(() => setTaskStatus(e.target.value))}>{["all", "To Do", "In Progress", "Done", "Not Started", "Deferred", "Completed"].map(value => <option key={value} value={value}>{value === "all" ? "All statuses" : value}</option>)}</select></label>
      <label className="text-sm">Priority <select aria-label="Filter task priority" className="rounded border bg-background p-2" value={priority} onChange={e => filterChange(() => setPriority(e.target.value))}>{["all", "Low", "Medium", "High", "Urgent", "Highest"].map(value => <option key={value} value={value}>{value === "all" ? "All priorities" : value}</option>)}</select></label>
      <label className="text-sm">Sort <select aria-label="Sort tasks" className="rounded border bg-background p-2" value={sort} onChange={e => filterChange(() => setSort(e.target.value))}>{[["due_date:asc", "Due soonest"], ["due_date:desc", "Due latest"], ["created_at:desc", "Newest first"], ["title:asc", "Title A–Z"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={mine} onChange={e => filterChange(() => setMine(e.target.checked))}/>Assigned to me</label>
      <button className="text-sm underline" onClick={() => filterChange(() => { setQueue("all"); setTaskStatus("all"); setPriority("all"); setMine(false); setSearch(""); setSort("due_date:asc"); })}>Reset filters</button>
    </div>
    <p className="text-sm text-muted-foreground" aria-live="polite">{loading ? "Updating tasks…" : `${total} matching tasks`} · Dates use {timezone}</p>
    <div className="flex items-center gap-2"><label className="flex flex-1 items-center gap-2 rounded-md border px-3 py-2"><Search size={16}/><input className="w-full bg-transparent outline-none" aria-label="Search CRM tasks" placeholder="Search tasks…" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}/></label><button className="rounded-md border p-2" aria-label="Refresh tasks" onClick={() => setRefresh(v => v + 1)}><RefreshCw size={18}/></button></div>
    {initialLoading ? <p role="status">Loading tasks…</p> : <div className="space-y-2">{!tasks.length && !error && <p className="rounded-md border p-6">No tasks found. Create a task to get started.</p>}{tasks.map(task => <article key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-4"><div className="min-w-0 flex-1"><button className="text-left font-semibold" onClick={() => setEditing(task)}>{task.title}</button><p className="line-clamp-2 text-sm text-muted-foreground">{richTextPlainText(task.description || "")}</p><p className="mt-2 text-sm">{task.status} · {task.priority}{task.dueDate ? ` · Due ${task.dueDate.slice(0, 10)}` : ""}{task.ownerId === user?.id ? " · Assigned to me" : ""}</p></div><div className="flex gap-2"><button type="button" className="rounded-md border px-3 py-2 text-sm" aria-label={`View task details ${task.title}`} onClick={()=>setDetailTask(task)}>Details</button><button className="inline-flex items-center gap-1 rounded-md border px-3 py-2" aria-label={`Edit task ${task.title}`} onClick={() => setEditing(task)}><Pencil size={14}/>Edit</button><button className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-red-600" aria-label={`Delete task ${task.title}`} onClick={() => setDeleting(task)}><Trash2 size={14}/>Delete</button></div></article>)}</div>}
    <div className="flex items-center justify-end gap-3"><button disabled={loading || page <= 1} onClick={() => setPage(v => v - 1)}>Previous</button><span>Page {page} of {Math.max(1, pages)}</span><button disabled={loading || page >= pages} onClick={() => setPage(v => v + 1)}>Next</button></div>
    <Dialog open={!!detailTask} onOpenChange={open=>{if(!open)setDetailTask(null);}}><DialogContent className="max-h-[90vh] overflow-y-auto"><DialogTitle>{detailTask?.title||"Task details"}</DialogTitle>{detailTask&&<><p className="text-sm text-muted-foreground">{detailTask.status} · {detailTask.priority}</p><CrmFieldsReadOnly entity="tasks" recordId={detailTask.id}/></>}</DialogContent></Dialog>
    <AlertDialog.Root open={!!deleting} onOpenChange={open => { if (!open && !busy) setDeleting(null); }}><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/40"/><AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-lg bg-background p-6 shadow-lg"><AlertDialog.Title className="text-lg font-semibold">Delete task?</AlertDialog.Title><AlertDialog.Description>Delete “{deleting?.title}” from CRM?</AlertDialog.Description><div className="flex justify-end gap-3"><AlertDialog.Cancel asChild><button disabled={busy}>Cancel</button></AlertDialog.Cancel><AlertDialog.Action asChild><button className="rounded-md bg-red-600 px-3 py-2 text-white" disabled={busy} onClick={event => { event.preventDefault(); void remove(); }}>{busy ? "Deleting…" : "Delete task"}</button></AlertDialog.Action></div>{error && <p role="alert" className="text-red-600">{error}</p>}</AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
  </section>;
}
