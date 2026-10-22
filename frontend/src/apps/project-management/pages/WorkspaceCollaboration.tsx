import { useEffect, useRef, useState } from "react";
import { MessageSquare, StickyNote, Send } from "lucide-react";
import { api } from "@/services/api";
import { personName, workspaceBase, workspaceError, type WorkTask } from "./workspaceTypes";

type Entry = { id: number; kind: "note" | "chat"; body: string; task_id: number | null; author: string; created_at: string };
export default function WorkspaceCollaboration({ workspaceId, canEdit, tasks, onOpen }: { workspaceId: number; canEdit: boolean; tasks: WorkTask[]; onOpen: (id: number) => void }) {
  const [tab, setTab] = useState<"note" | "chat">("chat");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [drafts, setDrafts] = useState({ note: "", chat: "" });
  const [taskId, setTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sync, setSync] = useState("Connecting…");
  const mounted = useRef(true);
  const end = useRef<HTMLDivElement>(null);
  const url = `${workspaceBase}/workspaces/${workspaceId}/entries`;
  useEffect(() => {
    mounted.current = true;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const { data } = await api.get<Entry[]>(url);
        if (active) { setEntries(data); setSync("Updated just now"); }
      } catch { if (active) setSync("Reconnecting…"); }
      finally { if (active) timer = setTimeout(refresh, document.hidden ? 15000 : 3000); }
    };
    void refresh();
    return () => { active = false; mounted.current = false; clearTimeout(timer); };
  }, [url]);
  useEffect(() => { if (tab === "chat") end.current?.scrollIntoView({ block: "nearest" }); }, [entries.length, tab]);
  async function send() {
    if (busy || !drafts[tab].trim()) return;
    const kind = tab;
    const body = drafts[kind];
    setBusy(true); setError("");
    try {
      await api.post(url, { kind, body, task_id: taskId ? Number(taskId) : null });
      if (!mounted.current) return;
      setDrafts(current => ({ ...current, [kind]: "" }));
      const { data } = await api.get<Entry[]>(url);
      if (mounted.current) setEntries(data);
    } catch (e) { if (mounted.current) setError(workspaceError(e)); }
    finally { if (mounted.current) setBusy(false); }
  }
  return <aside className="ws-collaboration" aria-label="Team collaboration">
    <div className="ws-collab-tabs" role="tablist" aria-label="Collaboration views">
      <button role="tab" aria-selected={tab === "chat"} onClick={() => setTab("chat")}><MessageSquare size={16} />Team chat</button>
      <button role="tab" aria-selected={tab === "note"} onClick={() => setTab("note")}><StickyNote size={16} />Quick notes</button>
    </div>
    <p className="ws-collab-sync" role="status">{sync} · Shared with this workspace</p>
    <div className="ws-collab-feed" role="tabpanel" aria-label={tab === "chat" ? "Team chat" : "Quick notes"}>
      {!entries.some(e => e.kind === tab) && <p className="ws-collab-empty">{tab === "chat" ? "Start a conversation with your team." : "Capture ideas, decisions, or a meeting checklist."}</p>}
      {entries.filter(e => e.kind === tab).map(e => <article key={e.id} className={tab === "note" ? "ws-note" : "ws-message"}>
        <header><strong>{personName(e.author)}</strong><time dateTime={e.created_at}>{new Date(e.created_at.endsWith("Z") ? e.created_at : `${e.created_at}Z`).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></header>
        <p>{e.body}</p>
        {e.task_id && <button className="ws-collab-task" onClick={() => onOpen(e.task_id!)}>↗ {tasks.find(t => t.id === e.task_id)?.title || "Open linked task"}</button>}
      </article>)}<div ref={end} />
    </div>
    {error && <p role="alert" className="ws-alert">{error}</p>}
    {canEdit ? <form className="ws-collab-compose" onSubmit={e => { e.preventDefault(); void send(); }}>
      <select aria-label="Link to task" value={taskId} onChange={e => setTaskId(e.target.value)}><option value="">Link a task (optional)</option>{tasks.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select>
      <textarea aria-label={tab === "chat" ? "Message your team" : "Write a quick note"} placeholder={tab === "chat" ? "Share an update or ask a question…" : "Write a note…"} value={drafts[tab]} maxLength={20000} onChange={e => setDrafts(current => ({ ...current, [tab]: e.target.value }))} />
      <button className="ws-button ws-primary" disabled={busy || !drafts[tab].trim()}><Send size={14} />{busy ? "Saving…" : tab === "chat" ? "Send message" : "Save note"}</button>
    </form> : <p className="ws-collab-sync">You have read-only access.</p>}
  </aside>;
}
