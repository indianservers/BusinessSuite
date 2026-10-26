import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "./workspaceTypes";

type DeletedRecord = { id: number; title: string; task_key?: string; project_key?: string; project_name?: string; deleted_at: string; can_restore?: boolean };
export default function TrashPage() {
  const [params, setParams] = useSearchParams();
  const kind = params.get("type") === "projects" ? "projects" : "tasks";
  const [items, setItems] = useState<DeletedRecord[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [restored, setRestored] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setItems([]); setRestored(null);
    api.get<DeletedRecord[]>(`/project-management/trash/${kind}`).then(({ data }) => { if (active) setItems(data); })
      .catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [kind]);
  async function restore(record: DeletedRecord) {
    setBusy(record.id); setError("");
    try {
      await api.post(`/project-management/trash/${kind}/${record.id}/restore`);
      setItems(current => current.filter(item => item.id !== record.id)); setRestored(record.id);
    } catch (error) { setError(workspaceError(error)); } finally { setBusy(null); }
  }
  const visible = items.filter(item => `${item.title} ${item.task_key || item.project_key || ""} ${item.project_name || ""}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <div className="mx-auto max-w-5xl space-y-5">
    <header><h1 className="page-title">Trash</h1><p className="page-description">Recover deleted projects and tasks you can access. Restoring requires permission to manage the record.</p></header>
    <nav aria-label="Trash categories" className="flex gap-2">{(["tasks", "projects"] as const).map(type=><Button key={type} variant={kind===type ? "default" : "outline"} disabled={busy!==null} onClick={()=>setParams(type==="projects" ? {type} : {})}>{type==="projects" ? "Projects" : "Tasks"}</Button>)}</nav>
    <Link className="text-primary underline" to={`/pms/${kind}`}>Back to {kind}</Link>
    <Input aria-label={`Search deleted ${kind}`} placeholder="Search names, keys or projects…" value={search} onChange={event => setSearch(event.target.value)} />
    {error && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{error}</p>}
    {restored !== null && <p role="status">{kind==="projects" ? "Project" : "Task"} restored. <Link className="text-primary underline" to={`/pms/${kind}/${restored}`}>Open {kind==="projects" ? "project" : "task"}</Link></p>}
    {loading ? <p role="status">Loading deleted {kind}…</p> : <><p className="text-sm text-muted-foreground">{visible.length} deleted {kind} shown</p>{!visible.length && !error && <p className="rounded-lg border border-dashed p-8 text-center">{items.length ? "No deleted records match your search." : `No deleted ${kind} you can access.`}</p>}
      <div className="space-y-3">{visible.map(record => <article key={record.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div className="min-w-0"><h2 className="break-words font-semibold">{record.title}</h2><p className="text-sm text-muted-foreground">{record.task_key || record.project_key}{record.project_name && ` · ${record.project_name}`}</p><p className="text-xs text-muted-foreground">Deleted {new Date(/(Z|[+-]\d{2}:\d{2})$/.test(record.deleted_at) ? record.deleted_at : `${record.deleted_at}Z`).toLocaleString()}</p></div><Button variant="outline" disabled={busy !== null || record.can_restore===false} onClick={() => void restore(record)}>{busy === record.id ? "Restoring…" : "Restore"}</Button></article>)}</div></>}
  </div>;
}
