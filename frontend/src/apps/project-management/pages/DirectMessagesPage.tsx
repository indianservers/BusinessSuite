import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError, type WorkspaceMember } from "./workspaceTypes";
type Conversation = { id: number; participants: { id: number; email: string }[] };
type Message = { id: number; author_id: number; body: string; created_at: string };
type Inbox = { conversations: Conversation[]; can_send: boolean; user_id: number };
type History = { messages: Message[]; has_more: boolean };
const base = "/project-management/workspaces";
const merge = (left: Message[], right: Message[]) => [...new Map([...left, ...right].map(row => [row.id, row])).values()].sort((a, b) => a.id - b.id);
export default function DirectMessagesPage() {
  const [params] = useSearchParams();
  const [workspaces, setWorkspaces] = useState<{ id: number; name: string }[]>([]);
  const [workspace, setWorkspace] = useState(0);
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [people, setPeople] = useState<WorkspaceMember[]>([]);
  const [conversation, setConversation] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [target, setTarget] = useState("");
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sync, setSync] = useState("");
  const context = `${workspace}:${conversation}`;
  const contextRef = useRef(context); contextRef.current = context;
  const requestRef = useRef<{ context: string; body: string; id: string } | null>(null);
  const selected = inbox?.conversations.find(row => row.id === conversation);
  const peer = (row: Conversation) => row.participants.find(person => person.id !== inbox?.user_id)?.email || "Conversation";
  useEffect(() => {
    let active = true;
    api.get<{ id: number; name: string }[]>(base).then(({ data }) => { if (active) { setWorkspaces(data); setWorkspace(data.find(row => row.id === Number(params.get("workspace")))?.id || data[0]?.id || 0); if (!data.length) setLoading(false); } }).catch(error => { if (active) { setError(workspaceError(error)); setLoading(false); } });
    return () => { active = false; };
  }, [params]);
  useEffect(() => {
    if (!workspace) return;
    let active = true; setInbox(null); setConversation(0); setPeople([]); setMessages([]); setError(""); setLoading(true);
    Promise.all([api.get<Inbox>(`${base}/${workspace}/direct-conversations`), api.get<WorkspaceMember[]>(`${base}/${workspace}/members`)]).then(([library, members]) => {
      if (active) { setInbox(library.data); setPeople(members.data.filter(person => person.role !== "Guest" && person.user_id !== library.data.user_id)); }
    }).catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [workspace]);
  useEffect(() => {
    if (!conversation) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    setMessages([]); setHasMore(false); setError(""); setSync("Loading messages…");
    async function refresh(first = false) {
      try {
        const { data } = await api.get<History>(`${base}/${workspace}/direct-conversations/${conversation}/messages`);
        if (active) { setMessages(current => merge(current, data.messages)); if (first) setHasMore(data.has_more); setSync("Updated just now"); }
      } catch (error) { if (active) { setSync("Unable to refresh messages"); setError(workspaceError(error)); } }
      finally { if (active) timer = setTimeout(() => void refresh(), 8000); }
    }
    void refresh(true);
    return () => { active = false; clearTimeout(timer); };
  }, [workspace, conversation]);
  async function start() {
    if (busy || !target) return; setBusy(true); setError("");
    try { const { data } = await api.post<Conversation>(`${base}/${workspace}/direct-conversations`, { user_id: Number(target) }); setInbox(current => current ? { ...current, conversations: [data, ...current.conversations.filter(row => row.id !== data.id)] } : current); setConversation(data.id); setTarget(""); }
    catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  async function send() {
    const body = drafts[context]?.trim(); if (busy || !body) return;
    setBusy(true); setError("");
    if (requestRef.current?.context !== context || requestRef.current.body !== body) requestRef.current = { context, body, id: crypto.randomUUID() };
    try {
      const { data } = await api.post<Message>(`${base}/${workspace}/direct-conversations/${conversation}/messages`, { body, client_id: requestRef.current.id });
      if (contextRef.current === context) setMessages(current => merge(current, [data]));
      setDrafts(current => ({ ...current, [context]: "" })); requestRef.current = null;
    } catch (error) { setError(workspaceError(error)); } finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-6xl space-y-4">
    <header><h1 className="page-title">Direct messages</h1><p className="page-description">Conversations are visible only to their participants while they belong to this workspace.</p></header>
    <Link className="text-primary underline" to={`/pms/workspaces?workspace=${workspace}`}>Back to workspace</Link>
    <select aria-label="Messaging workspace" disabled={busy} value={workspace} onChange={event => setWorkspace(Number(event.target.value))} className="block max-w-full rounded-md border bg-background p-2"><option value={0} disabled>Choose workspace</option>{workspaces.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {loading ? <p role="status">Loading conversations…</p> : !workspace ? <p>Create or join a workspace first.</p> : <div className="grid gap-4 md:grid-cols-[260px_minmax(0,1fr)]">
      <aside className="space-y-3 rounded-lg border p-4"><h2 className="font-semibold">Conversations</h2><Input aria-label="Search conversations" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search people…" />
        {inbox?.conversations.filter(row => peer(row).toLowerCase().includes(search.toLowerCase())).map(row => <button type="button" key={row.id} disabled={busy} aria-pressed={row.id === conversation} className={`w-full break-all rounded-md border p-3 text-left text-sm ${row.id === conversation ? "bg-muted" : ""}`} onClick={() => setConversation(row.id)}>{peer(row)}</button>)}
        {!inbox?.conversations.length && <p className="text-sm text-muted-foreground">No conversations yet.</p>}
        {inbox?.can_send && <form className="space-y-2 border-t pt-3" onSubmit={event => { event.preventDefault(); void start(); }}><label className="block text-sm">New conversation<select required aria-label="Message collaborator" disabled={busy} value={target} onChange={event => setTarget(event.target.value)} className="mt-1 w-full rounded-md border bg-background p-2"><option value="" disabled>Choose collaborator</option>{people.map(person => <option key={person.id} value={person.user_id}>{person.email}</option>)}</select></label><Button disabled={busy || !target}>Open conversation</Button></form>}
      </aside>
      <section className="min-w-0 space-y-4 rounded-lg border p-4" aria-label="Private conversation">
        {!selected ? <p>Choose a conversation or start one with a collaborator.</p> : <><h2 className="break-all font-semibold">{peer(selected)}</h2><p role="status" className="text-xs text-muted-foreground">{sync}</p>
          {hasMore && <Button variant="outline" disabled={busy || !messages.length} onClick={() => {
            setBusy(true); setError(""); const before = messages[0].id;
            void api.get<History>(`${base}/${workspace}/direct-conversations/${conversation}/messages?before=${before}`).then(({ data }) => { if (contextRef.current === context) { setMessages(current => merge(data.messages, current)); setHasMore(data.has_more); } }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
          }}>Load earlier messages</Button>}
          <div className="max-h-[55vh] space-y-3 overflow-y-auto" aria-label="Message history">{messages.map(message => <article key={message.id} className="rounded-md bg-muted/40 p-3"><header className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground"><strong>{message.author_id === inbox?.user_id ? "You" : peer(selected)}</strong><time dateTime={message.created_at}>{new Date(/(Z|[+-]\d{2}:\d{2})$/.test(message.created_at) ? message.created_at : `${message.created_at}Z`).toLocaleString()}</time></header><p className="mt-2 whitespace-pre-wrap break-words text-sm">{message.body}</p></article>)}</div>
          {inbox?.can_send && <form className="space-y-2 border-t pt-3" onSubmit={event => { event.preventDefault(); void send(); }}><textarea aria-label="Private message" disabled={busy} maxLength={20000} className="min-h-24 w-full rounded-md border bg-background p-3 text-sm" placeholder="Write a private message…" value={drafts[context] || ""} onChange={event => setDrafts(current => ({ ...current, [context]: event.target.value }))} /><Button disabled={busy || !drafts[context]?.trim()}>{busy ? "Working…" : "Send message"}</Button></form>}
        </>}
      </section>
    </div>}
  </main>;
}
