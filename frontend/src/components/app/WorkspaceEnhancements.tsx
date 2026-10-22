import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, MessageSquare, Plus, X } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { usePMSRealtime } from "@/apps/project-management/realtime";
import { tasksAPI } from "@/apps/project-management/services/api";
import WorkspaceCollaboration from "@/apps/project-management/pages/WorkspaceCollaboration";
import { TaskDrawer } from "@/apps/project-management/pages/WorkspaceWork";
import { type WorkTask, type WorkspaceMember, type WorkspaceProject, workspaceError } from "@/apps/project-management/pages/workspaceTypes";
import "@/apps/project-management/pages/workspaces.css";

type Workspace = { id: number; name: string; role: string };
const base = "/project-management";
export default function WorkspaceEnhancements({ terminal = false }: { terminal?: boolean }) {
  const [open, setOpen] = useState(false);
  const userId = useAuthStore(s => s.user?.id);
  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger asChild><button className={`fixed ${terminal ? "top-20 right-4" : "bottom-5 right-5"} z-40 inline-flex items-center gap-2 rounded-full border bg-background px-4 py-3 text-sm font-medium shadow-md hover:bg-accent`}><MessageSquare size={17} />Team workspace</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/30" /><Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col overflow-y-auto border-l bg-background p-5 shadow-xl">
      <header className="mb-4 flex items-start justify-between gap-4"><div><Dialog.Title className="text-lg font-semibold">Team workspace</Dialog.Title><Dialog.Description className="mt-1 text-xs text-muted-foreground">Shared tasks, quick notes, and conversations. Available from every module.</Dialog.Description></div><Dialog.Close aria-label="Close team workspace" className="rounded-md p-2 hover:bg-muted"><X size={18} /></Dialog.Close></header>
      {open && <TeamWork key={userId} />}
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>;
}
function TeamWork() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState(0);
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const [tasks, setTasks] = useState<WorkTask[]>([]);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [project, setProject] = useState("");
  const [busy, setBusy] = useState(false);
  const [openedTask, setOpenedTask] = useState<number | null>(null);
  const workspace = workspaces.find(w => w.id === selected);
  const canEdit = !!workspace && workspace.role !== "Guest";
  useEffect(() => {
    let active = true;
    void api.get<Workspace[]>(`${base}/workspaces`).then(({ data }) => { if (active) { setWorkspaces(data); setSelected(data[0]?.id || 0); } }).catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const refresh = useCallback(async () => {
    if (!selected) return;
    const [overview, people] = await Promise.all([
      api.get<{ tasks: WorkTask[]; projects: WorkspaceProject[]; role: string }>(`${base}/workspaces/${selected}/overview`),
      api.get<WorkspaceMember[]>(`${base}/workspaces/${selected}/members`),
    ]);
    if (selectedRef.current !== selected) return;
    setTasks(overview.data.tasks); setProjects(overview.data.projects); setMembers(people.data);
    setWorkspaces(current => current.map(w => w.id === selected ? { ...w, role: overview.data.role } : w));
  }, [selected]);
  useEffect(() => {
    setTasks([]); setProjects([]); setMembers([]); setProject(""); setTitle(""); setOpenedTask(null); setError("");
    let active = true;
    void refresh().catch(e => { if (active) setError(workspaceError(e)); });
    return () => { active = false; };
  }, [refresh]);
  usePMSRealtime({ enabled: !!selected, onEvent: () => { void refresh().catch(() => undefined); }, onFallbackPoll: () => { void refresh().catch(() => undefined); }, showToast: false });
  async function updateTask(task: WorkTask, changes: Partial<WorkTask>) {
    try { await api.patch(`${base}/tasks/${task.id}`, changes); await refresh(); return true; }
    catch (e) { setError(workspaceError(e)); return false; }
  }
  if (loading) return <p className="flex items-center gap-2 text-sm"><Loader2 size={16} className="animate-spin" />Loading workspaces…</p>;
  return <div className="shared-team-workspace space-y-4">
    {error && <p role="alert" className="rounded border border-destructive/30 p-3 text-sm text-destructive">{error}</p>}
    {!workspaces.length ? <div className="rounded-lg border p-5 text-sm"><p>Create or join a workspace to collaborate with your team.</p><Link to="/pms/workspaces" className="mt-3 inline-block text-primary underline">Open workspaces</Link></div> : <>
      <label className="block text-xs font-medium">Workspace<select aria-label="Workspace" className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm" value={selected} onChange={e => setSelected(Number(e.target.value))}>{workspaces.map(w => <option key={w.id} value={w.id}>{w.name} · {w.role}</option>)}</select></label>
      <section className="rounded-lg border p-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Tasks</h2><Link to="/pms/workspaces" className="text-xs text-primary underline">Open full workspace</Link></div>
        <div className="max-h-56 divide-y overflow-y-auto">{tasks.filter(t => t.status !== "Done").map(t => <button key={t.id} className="flex w-full items-center justify-between gap-3 py-3 text-left text-sm hover:text-primary" onClick={() => setOpenedTask(t.id)}><span>{t.title}</span><span className="shrink-0 text-xs text-muted-foreground">{t.status}</span></button>)}{!tasks.some(t => t.status !== "Done") && <p className="py-3 text-sm text-muted-foreground">No open tasks.</p>}</div>
        {canEdit && !!projects.length && <form className="mt-3 flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); if (!title.trim() || busy) return; const id = selected; setBusy(true); setError(""); void tasksAPI.create(Number(project) || projects[0].id, { task_key: "", title: title.trim(), status: "To Do", priority: "Medium" }).then(async () => { if (selectedRef.current === id) { setTitle(""); await refresh(); } }).catch(e => { if (selectedRef.current === id) setError(workspaceError(e)); }).finally(() => setBusy(false)); }}><input aria-label="New shared task" required maxLength={255} placeholder="Add a task…" className="h-9 min-w-0 flex-1 rounded border bg-background px-3 text-sm" value={title} onChange={e => setTitle(e.target.value)} /><select aria-label="Task project" className="h-9 max-w-40 rounded border bg-background px-2 text-xs" value={project || projects[0].id} onChange={e => setProject(e.target.value)}>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><button aria-label="Create shared task" disabled={busy || !title.trim()} className="rounded bg-primary px-3 text-primary-foreground disabled:opacity-50"><Plus size={16} /></button></form>}
      </section>
      <WorkspaceCollaboration key={selected} workspaceId={selected} canEdit={canEdit} tasks={tasks} onOpen={setOpenedTask} />
      <TaskDrawer error={error} task={tasks.find(t => t.id === openedTask)} members={members} canEdit={canEdit} onClose={() => setOpenedTask(null)} onUpdate={updateTask} onRefresh={refresh} onError={setError} />
    </>}
  </div>;
}
