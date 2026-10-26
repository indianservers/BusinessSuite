import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Link } from "react-router-dom";
import { CheckSquare, X } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { PMSProject } from "../types";
import { workspaceError } from "../pages/workspaceTypes";
type CreatedTask = { id: number; task_key: string; title: string; project_id: number; status: string };
type Props = { noteId: number; title: string; selection: string; projectId: number | null; projects: PMSProject[]; readOnly: boolean };
export default function NoteTaskActions({ noteId, title, selection, projectId, projects, readOnly }: Props) {
  const [open, setOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [description, setDescription] = useState("");
  const [project, setProject] = useState("");
  const [due, setDue] = useState("");
  const [priority, setPriority] = useState("Medium");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tasks, setTasks] = useState<CreatedTask[]>([]);
  const [notice, setNotice] = useState("");
  const requestKey = useRef("");
  const sending = useRef(false);
  const base = `/project-management/notes/${noteId}/tasks`;
  useEffect(() => { const abort = new AbortController(); void api.get<CreatedTask[]>(base, { signal: abort.signal }).then(({ data }) => setTasks(data)).catch(e => { if (!abort.signal.aborted) setError(workspaceError(e)); }); return () => abort.abort(); }, [base]);
  function begin() {
    setTaskTitle((selection.trim().split("\n")[0] || title || "New task").slice(0, 220)); setDescription(""); setProject(projectId ? String(projectId) : ""); setDue(""); setPriority("Medium"); setConfirmed(false); setError(""); setNotice(""); requestKey.current = crypto.randomUUID(); setOpen(true);
  }
  async function create() {
    if (sending.current || !confirmed || !project || !taskTitle.trim()) return;
    sending.current = true; setBusy(true); setError("");
    try {
      const { data } = await api.post<CreatedTask>(base, { title: taskTitle, description, project_id: Number(project), due_date: due || null, priority, publish_to_project: true, request_key: requestKey.current });
      setTasks(current => [data, ...current.filter(t => t.id !== data.id)]); setNotice(`Created ${data.task_key}. Your note and attachments remain private.`); setOpen(false);
    } catch (e) { setError(workspaceError(e)); } finally { sending.current = false; setBusy(false); }
  }
  // Changing the reviewed payload represents a new request; retries of identical data reuse the key.
  function changed() { requestKey.current = crypto.randomUUID(); setConfirmed(false); }
  return <section className="note-task-actions" aria-label="Tasks from this note"><header><h2><CheckSquare size={15} />Tasks from this note</h2>{!readOnly && <Button size="sm" variant="outline" onClick={begin}>{selection.trim() ? "Create task from selection" : "Create task"}</Button>}</header>
    <p className="notes-attachment-help">Create a project task from reviewed text. Your original note and its files stay private.</p>
    {notice && <p role="status" className="note-task-notice">{notice}</p>}
    {!open && error && <p role="alert" className="text-destructive text-sm">{error}</p>}
    {tasks.map(task => <Link className="note-created-task" key={task.id} to={`/pms/tasks/${task.id}`}><strong>{task.task_key}</strong><span>{task.title}</span><small>{task.status}</small></Link>)}
    <Dialog.Root open={open} onOpenChange={value => { if (!busy) setOpen(value); }}><Dialog.Portal><Dialog.Overlay className="notes-modal-overlay" /><Dialog.Content className="notes-modal"><Dialog.Title>Create a project task</Dialog.Title><Dialog.Description>Review exactly what will be published. The task is visible to people with access to its destination project. Your private note and attachments are not shared.</Dialog.Description><Dialog.Close asChild><Button className="notes-modal-close" disabled={busy} variant="ghost" aria-label="Close task creation"><X size={18} /></Button></Dialog.Close>
      <form onSubmit={e => { e.preventDefault(); void create(); }}>
        <label>Destination project<select aria-label="Task destination project" required disabled={busy} value={project} onChange={e => { setProject(e.target.value); changed(); }}><option value="" disabled>Choose a work project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label>Task title<Input aria-label="New task title" required maxLength={220} disabled={busy} value={taskTitle} onChange={e => { setTaskTitle(e.target.value); changed(); }} /></label>
        <label>Task description<RichTextField data-legacy-format="plain" aria-label="New task description" maxLength={10000} disabled={busy} value={description} placeholder="Only text entered here will be copied." onChange={e => { setDescription(e.target.value); changed(); }} /></label>
        {selection.trim() && <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => { setDescription(selection.slice(0, 10000)); changed(); }}>Copy selected text into description</Button>}
        <div className="notes-metadata"><label>Due date<Input type="date" aria-label="New task due date" disabled={busy} value={due} onChange={e => { setDue(e.target.value); changed(); }} onInput={e => { setDue(e.currentTarget.value); changed(); }} /></label><label>Priority<select aria-label="New task priority" disabled={busy} value={priority} onChange={e => { setPriority(e.target.value); changed(); }}>{["Low", "Medium", "High", "Urgent"].map(p => <option key={p}>{p}</option>)}</select></label></div>
        <label className="notes-publish-confirm"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I understand that this task title and description will be visible in the selected project.</label>
        {error && <p role="alert" className="text-destructive text-sm">{error}</p>}
        <div className="notes-task-submit"><Button type="button" variant="outline" disabled={busy} onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" disabled={busy || !confirmed || !project || !taskTitle.trim()}>{busy ? "Creating…" : "Create project task"}</Button></div>
      </form>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </section>;
}

