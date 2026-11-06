import { useEffect, useState } from "react";

export type TaskView = { queue: string; status: string; priority: string; mine: boolean; sort: string; search: string };
type SavedView = { name: string; filters: TaskView };

export default function TaskSavedViews({ scope, filters, onApply }: { scope: string; filters: TaskView; onApply: (view: TaskView) => void }) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [name, setName] = useState("");
  const [notice, setNotice] = useState("");
  const key = `crm.task-views.v1:${scope}`;
  useEffect(() => {
    setName(""); setNotice("");
    try {
      const data: unknown = JSON.parse(localStorage.getItem(key) || "[]");
      setViews(Array.isArray(data) ? data.filter((item): item is SavedView => !!item && typeof item.name === "string" && !!item.filters &&
        typeof item.filters.search === "string" && typeof item.filters.mine === "boolean" &&
        ["all", "open", "completed", "overdue", "today", "week", "unscheduled"].includes(item.filters.queue) &&
        typeof item.filters.status === "string" && typeof item.filters.priority === "string" &&
        ["due_date:asc", "due_date:desc", "created_at:desc", "title:asc"].includes(item.filters.sort)).slice(0, 20) : []);
    } catch { setViews([]); }
  }, [key]);
  function persist(next: SavedView[]) {
    try { localStorage.setItem(key, JSON.stringify(next)); setViews(next); return true; }
    catch { setNotice("Browser storage is unavailable. View was not saved."); return false; }
  }
  return <div className="space-y-2 rounded-md border p-3">
    <div className="flex flex-wrap items-center gap-2">
      <label className="text-sm">Saved view <select className="rounded border bg-background p-2" aria-label="Apply saved task view" value="" onChange={e => { const view = views.find(v => v.name === e.target.value); if (view) { onApply(view.filters); setName(view.name); setNotice(`Applied “${view.name}”.`); } }}><option value="">Choose a view…</option>{views.map(view => <option key={view.name}>{view.name}</option>)}</select></label>
      <input className="min-w-0 rounded border bg-background p-2 text-sm" aria-label="Task view name" placeholder="Name this view" maxLength={60} value={name} onChange={e => setName(e.target.value)}/>
      <button className="rounded border px-3 py-2 text-sm" disabled={!name.trim() || (views.length >= 20 && !views.some(v => v.name === name.trim()))} onClick={() => { const title = name.trim(); if (persist([...views.filter(v => v.name !== title), {name: title, filters}])) setNotice(`Saved “${title}” in this browser.`); }}>Save view</button>
      {views.some(v => v.name === name.trim()) && <button className="px-3 py-2 text-sm underline" onClick={() => { if (persist(views.filter(v => v.name !== name.trim()))) { setName(""); setNotice("Saved view removed. Tasks are unchanged."); } }}>Remove saved view</button>}
    </div>
    <p className="text-xs text-muted-foreground">Personal views are saved in this browser for your account and company. Up to 20 views.</p>
    {notice && <p role="status" className="text-sm">{notice}</p>}
  </div>;
}
