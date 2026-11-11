import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { listAllProjects, sprintsAPI, tasksAPI } from "../services/api";
import type { PMSProject, PMSSprint, PMSTask } from "../types";
import { syncScope } from "@/shared/record-sync/store";
import { announceCreated } from "@/shared/creation/CreationOutcome";
const templates = { blank: "", review: "Review criteria:\n- Scope\n- Quality\n- Acceptance\n", bug: "Steps to reproduce:\n\nExpected result:\n\nActual result:\n", delivery: "Deliverable:\n\nAcceptance criteria:\n\nDependencies:\n" };
export default function QuickTaskCapture({ close, subtask = false }: { close: () => void; subtask?: boolean }) {
  const location = useLocation(), navigate = useNavigate(), user = useAuthStore(s => s.user);
  const params = new URLSearchParams(location.search), ownerScope = useRef(syncScope()), lock = useRef(false);
  const projectId = location.pathname.match(/^\/pms\/projects\/(\d+)/)?.[1] || params.get("projectId") || params.get("project") || "";
  const parentId = location.pathname.match(/^\/pms\/(?:projects\/\d+\/)?tasks\/(\d+)/)?.[1] || params.get("parentTaskId") || "";
  const [form, setForm] = useState({ title: "", description: "", projectId, parentId: subtask ? parentId : "", owner: params.get("assignee_id") || String(user?.id || ""), sprint: params.get("sprintId") || params.get("sprint_id") || "", due: "", template: "blank" });
  const [projects, setProjects] = useState<PMSProject[]>([]), [parents, setParents] = useState<PMSTask[]>([]), [sprints, setSprints] = useState<PMSSprint[]>([]), [people, setPeople] = useState<{ id: number; name: string }[]>([]);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [optionsReady, setOptionsReady] = useState(false), [error, setError] = useState(""), [another, setAnother] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const draft = useRecordDraft(`pms:quick-${subtask ? "subtask" : "task"}:${projectId}:${parentId}`, form, setForm, true);
  const owns = () => ownerScope.current === syncScope();
  useEffect(() => { let active = true; Promise.all([listAllProjects(), subtask && parentId && !projectId ? tasksAPI.get(Number(parentId)) : Promise.resolve(undefined)]).then(([rows, parent]) => { if (active && owns()) { const available = rows.filter(project => project.can_manage_tasks && (!location.pathname.startsWith("/pms") || !params.get("workspace") || String(project.workspace_id) === params.get("workspace"))); setProjects(available); if (parent && available.some(project => project.id === parent.project_id)) setForm(current => current.projectId ? current : { ...current, projectId: String(parent.project_id) }); } }).catch(() => { if (active) setError("Projects or the parent task could not load. Close and retry."); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  useEffect(() => { let active = true; setOptionsReady(false); setPeople([]); setParents([]); setSprints([]); if (!form.projectId) return;
    Promise.all([api.get<{ people: { id: number; name: string }[]; can_edit: boolean }>("/project-management/task-studio/options", { params: { project_id: form.projectId } }), sprintsAPI.list(Number(form.projectId)), subtask ? tasksAPI.list(Number(form.projectId)) : Promise.resolve([])]).then(([options, sprintRows, taskRows]) => { if (active && owns()) { setPeople(options.data.people); setOptionsReady(options.data.can_edit); setSprints(sprintRows.filter(sprint => sprint.status !== "Completed" && sprint.status !== "Cancelled")); setParents(taskRows.filter(task => !task.parent_task_id)); } }).catch(() => { if (active) setError("Project options could not load. Select the project again to retry, or use the full editor."); });
    return () => { active = false; };
  }, [form.projectId, subtask]);
  function update(key: keyof typeof form, value: string) { setForm(current => ({ ...current, [key]: value })); }
  async function save(event: React.FormEvent) {
    event.preventDefault(); if (lock.current || !owns()) return;
    if (!projects.some(project => project.id === Number(form.projectId)) || !optionsReady || subtask && !parents.some(parent => parent.id === Number(form.parentId))) { setError("Choose an accessible project and parent task before saving."); return; }
    lock.current = true; setBusy(true); setError("");
    try {
      const task = await tasksAPI.create(Number(form.projectId), { title: form.title.trim(), task_key: `TSK-${crypto.randomUUID().slice(0, 12)}`, description: form.description, work_type: subtask ? "Sub-task" : "Task", status: "To Do", priority: "Medium", assignee_user_id: form.owner ? Number(form.owner) : undefined, due_date: form.due || undefined, sprint_id: form.sprint ? Number(form.sprint) : undefined, parent_task_id: subtask ? Number(form.parentId) : undefined });
      if (!owns()) return;
      draft();
      if (contentRef.current) contentRef.current.dataset.smartCreateDirty = "false";
      announceCreated({ title: `Created ${task.title}`, href: `/pms/tasks/${task.id}`, status: task.status, undo: () => tasksAPI.delete(task.id) });
      if (another) { const next = { ...form, title: "", description: templates[form.template as keyof typeof templates] || "" }; setForm(next); draft.persist(next); } else close();
    } catch (failure) { if (owns()) setError((failure as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Task could not save. Your draft is preserved. Use the full editor if required fields are missing."); }
    finally { lock.current = false; if (owns()) setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent ref={contentRef}><DialogTitle>{subtask ? "Create subtask" : "Create quick task"}</DialogTitle><form className="space-y-3" onSubmit={save} aria-busy={busy}><fieldset disabled={busy || loading} className="space-y-3">
    <label className="block text-sm">Project<NativeSelect aria-label="Quick task project" required value={form.projectId} onChange={event => { setForm(current => ({ ...current, projectId: event.target.value, parentId: "", sprint: "", owner: "" })); setError(""); }}><option value="">Choose project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</NativeSelect></label>
    {subtask && <label className="block text-sm">Parent task<NativeSelect aria-label="Parent task" required value={form.parentId} onChange={event => update("parentId", event.target.value)}><option value="">Choose parent task</option>{parents.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</NativeSelect></label>}
    <label className="block text-sm">Title<Input autoFocus required maxLength={220} value={form.title} onChange={event => update("title", event.target.value)}/></label>
    <div className="grid grid-cols-2 gap-3"><label className="text-sm">Assignee<NativeSelect aria-label="Quick task assignee" value={form.owner} onChange={event => update("owner", event.target.value)}><option value="">Unassigned</option>{people.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</NativeSelect></label><label className="text-sm">Due date<Input type="date" value={form.due} onChange={event => update("due", event.target.value)}/></label></div>
    <label className="block text-sm">Sprint<NativeSelect aria-label="Quick task sprint" value={form.sprint} onChange={event => update("sprint", event.target.value)}><option value="">No sprint</option>{sprints.map(sprint => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}</NativeSelect></label>
    <label className="block text-sm">Task template<NativeSelect aria-label="Task template" value={form.template} onChange={event => { const template = event.target.value as keyof typeof templates; if (form.description.trim() && form.description !== templates[form.template as keyof typeof templates]) { setError("Clear the description before switching templates."); return; } setForm(current => ({ ...current, template, description: templates[template] })); }}><option value="blank">Blank task</option><option value="review">Review checklist</option><option value="bug">Bug report</option><option value="delivery">Delivery brief</option></NativeSelect></label>
    <details><summary>Description</summary><textarea aria-label="Quick task description" className="w-full rounded border p-2" maxLength={10000} value={form.description} onChange={event => update("description", event.target.value)}/></details>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={another} onChange={event => setAnother(event.target.checked)}/>Create another with these defaults</label>
  </fieldset>{loading && <p role="status">Loading projects…</p>}{error && <p role="alert" className="text-sm text-destructive">{String(error)}</p>}<p role="status" className="text-xs text-muted-foreground">{draft.status === "restored" ? "Restored your unfinished draft." : draft.status === "unavailable" ? "Draft storage unavailable; keep this window open." : "Draft saved in this browser session."}</p><div className="flex flex-wrap gap-2"><Button disabled={busy || !optionsReady || !form.title.trim()}>{busy ? "Creating…" : subtask ? "Create subtask" : "Create task"}</Button><Button type="button" variant="outline" disabled={busy} onClick={() => { const target = new URLSearchParams({ projectId: form.projectId, title: form.title, description: form.description, people: form.owner, ...(subtask && form.parentId ? { parentTaskId: form.parentId, workType: "Sub-task" } : {}) }); close(); navigate(`/pms/tasks/new?${target}`); }}>Full editor</Button></div></form></DialogContent></Dialog>;
}
