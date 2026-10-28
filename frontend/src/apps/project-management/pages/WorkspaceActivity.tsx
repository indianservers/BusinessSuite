import { useRefreshableEffect } from "@/lib/page-refresh";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import { usePMSRealtime } from "../realtime";
import { workspaceBase, workspaceError } from "./workspaceTypes";

type Event = { id: number; action: string; summary: string; actor: string; task_id?: number; created_at: string };
export default function WorkspaceActivity({ workspaceId, onOpen }: { workspaceId: number; onOpen: (id: number) => void }) {
  const [items, setItems] = useState<Event[]>([]);
  const [before, setBefore] = useState<number>();
  const [next, setNext] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setError("");
    try {
      const { data } = await api.get<{ items: Event[]; next_cursor: number | null }>(`${workspaceBase}/workspaces/${workspaceId}/activity`, { params: { before, action } });
      setItems(data.items); setNext(data.next_cursor);
    } catch (e) { setItems([]); setError(workspaceError(e)); }
    finally { setLoading(false); }
  }, [workspaceId, before, action]);
  useRefreshableEffect(() => { setLoading(true); void load(); }, [load]);
  usePMSRealtime({ showToast: false, onEvent: () => { if (!before) void load(); }, onFallbackPoll: () => { if (!before) void load(); } });
  const csv = ["Time,Actor,Action,Summary", ...items.map(e => [e.created_at, e.actor, e.action, e.summary].map(v => `"${String(v).replace(/"/g, '""').replace(/^\s*[=+@-]/, "'$&")}"`).join(","))].join("\r\n");
  return <section className="ws-planning" aria-label="Workspace activity"><header><h2>Activity & export</h2><button className="ws-button ws-outline" onClick={() => { void load(); }}>Refresh</button></header>
    <p>Persistent project and task activity for this workspace. Available to workspace owners and administrators. This is an operational history, not a tamper-proof compliance archive.</p>
    <form className="ws-calendar-controls" onSubmit={e => { e.preventDefault(); setBefore(undefined); setAction(query.trim()); }}><input aria-label="Filter activity action" value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter action, e.g. assignee or dependency" /><button>Apply filter</button>{!!items.length && <a href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`} download="workspace-activity.csv">Export displayed events ({items.length})</a>}</form>
    {error && <p role="alert">{error}</p>}{loading ? <p role="status">Loading activity…</p> : <div className="ws-planning-tasks">{items.map(e => <article key={e.id} className="ws-activity-event"><strong>{e.summary}</strong><p>{e.actor} · {e.action} · {new Date(e.created_at.endsWith("Z") || /[+-]\d\d:\d\d$/.test(e.created_at) ? e.created_at : e.created_at + "Z").toLocaleString()}</p>{e.task_id && <button onClick={() => onOpen(e.task_id!)}>Open task</button>}</article>)}{!items.length && !error && <p>No matching project or task activity.</p>}</div>}
    <div className="ws-calendar-controls">{before && <button onClick={() => setBefore(undefined)}>Return to recent activity</button>}{next && <button onClick={() => setBefore(next)}>Older activity</button>}</div>
  </section>;
}
