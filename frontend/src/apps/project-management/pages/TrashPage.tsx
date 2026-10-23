import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "./workspaceTypes";

type DeletedTask = { id: number; title: string; task_key: string; project_name: string; deleted_at: string };
export default function TrashPage() {
  const [items, setItems] = useState<DeletedTask[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [restored, setRestored] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    api.get<DeletedTask[]>("/project-management/trash/tasks").then(({ data }) => { if (active) setItems(data); })
      .catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function restore(task: DeletedTask) {
    setBusy(task.id); setError("");
    try {
      await api.post(`/project-management/trash/tasks/${task.id}/restore`);
      setItems(current => current.filter(item => item.id !== task.id)); setRestored(task.id);
    } catch (error) { setError(workspaceError(error)); } finally { setBusy(null); }
  }
  const visible = items.filter(item => `${item.title} ${item.task_key} ${item.project_name}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <div className="mx-auto max-w-5xl space-y-5">
    <header><h1 className="page-title">Task trash</h1><p className="page-description">Recover deleted tasks from projects you can access. Restoring requires permission to manage project tasks.</p></header>
    <Link className="text-primary underline" to="/pms/tasks">Back to tasks</Link>
    <Input aria-label="Search deleted tasks" placeholder="Search task names, keys or projects…" value={search} onChange={event => setSearch(event.target.value)} />
    {error && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{error}</p>}
    {restored !== null && <p role="status">Task restored. <Link className="text-primary underline" to={`/pms/tasks/${restored}`}>Open task</Link></p>}
    {loading ? <p role="status">Loading deleted tasks…</p> : <><p className="text-sm text-muted-foreground">{visible.length} deleted tasks shown</p>{!visible.length && !error && <p className="rounded-lg border border-dashed p-8 text-center">{items.length ? "No deleted tasks match your search." : "No deleted tasks in accessible projects."}</p>}
      <div className="space-y-3">{visible.map(task => <article key={task.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div className="min-w-0"><h2 className="break-words font-semibold">{task.title}</h2><p className="text-sm text-muted-foreground">{task.task_key} · {task.project_name}</p><p className="text-xs text-muted-foreground">Deleted {new Date(/(Z|[+-]\d{2}:\d{2})$/.test(task.deleted_at) ? task.deleted_at : `${task.deleted_at}Z`).toLocaleString()}</p></div><Button variant="outline" disabled={busy !== null} onClick={() => void restore(task)}>{busy === task.id ? "Restoring…" : "Restore"}</Button></article>)}</div></>}
  </div>;
}
