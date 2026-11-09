import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, Bell, Check, Download, FileText, ListChecks, MessageCircle, Plus, Search, Send, Smile, Users, X } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useCommunicationScope } from "@/shared/communication/scope";
import { useCommunicationEvents } from "@/shared/communication/useCommunicationEvents";
import { RichTextContent } from "@/components/rich-text/RichTextContent";
import { formatDate } from "@/lib/utils";
import { personName, workspaceError } from "../pages/workspaceTypes";
import type { PMSProject, PMSTask } from "../types";
import "./ProjectCommunication.css";

type Attachment = { id: number; name: string; size: number };
type Message = { id: number; author_id: number; body: string; created_at: string; deleted_at: string | null; attachments: Attachment[] };
type Room = { id: number; joined: boolean; archived: boolean; participants: { id: number; email: string }[] };
type History = { messages: Message[]; before: number | null; read_through: number };
const instant = (value: string) => new Date(/(Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);

export default function ProjectCommunication(props: { project: PMSProject; tasks: PMSTask[] }) {
  const scope = useCommunicationScope();
  return <ProjectChat key={`${scope}:${props.project.id}`} {...props} scope={scope} />;
}

function ProjectChat({ project, tasks, scope }: { project: PMSProject; tasks: PMSTask[]; scope: string }) {
  useCommunicationEvents();
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const wid = project.workspace_id;
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [search, setSearch] = useState("");
  const [mobileChat, setMobileChat] = useState(false);
  const [taskPicker, setTaskPicker] = useState<"share" | "remind" | null>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const timeline = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const request = useRef<{ body: string; ids: string; client_id: string }>();
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    const input = inputRef.current;
    if (input) { input.style.height = "42px"; input.style.height = `${Math.min(input.scrollHeight, 110)}px`; }
  }, [draft]);
  const lookupKey = ["communication-project-room", scope, wid, project.id];
  const lookup = useQuery({ queryKey: lookupKey, enabled: !!wid, queryFn: async ({ signal }) => (await api.get<{ conversation_id: number | null }>("/collaboration/contexts/lookup", { signal, params: { workspace_id: wid, module: "project_management", entity_type: "project", entity_id: project.id } })).data });
  const rid = lookup.data?.conversation_id;
  const base = `/collaboration/workspaces/${wid}/chat`;
  const roomUrl = `${base}/conversations/${rid}`;
  const inbox = useQuery({ queryKey: ["chat-inbox", scope, wid], enabled: !!wid && !!rid, queryFn: async ({ signal }) => (await api.get<{ conversations: Room[]; can_send: boolean }>(`${base}/conversations`, { signal })).data, refetchInterval: 15000 });
  const room = inbox.data?.conversations.find(r => r.id === rid);
  const canWrite = !!room?.joined && !room.archived && !!inbox.data?.can_send && !inbox.isError;
  const history = useInfiniteQuery({ queryKey: ["chat-history", "project", scope, wid, rid], enabled: !!room?.joined, initialPageParam: null as number | null, queryFn: async ({ pageParam, signal }) => (await api.get<History>(`${roomUrl}/messages`, { signal, progress: false, params: { before: pageParam || undefined } })).data, getNextPageParam: page => page.before || undefined, refetchInterval: 15000 });
  const historyDenied = !!history.error && [401, 403, 404].includes((history.error as { response?: { status?: number } }).response?.status || 0);
  const messages = room?.joined && !inbox.isError && !historyDenied ? [...new Map(history.data?.pages.flatMap(p => p.messages).map(m => [m.id, m]) || []).values()].sort((a, b) => a.id - b.id) : [];
  const latest = messages[messages.length - 1]?.id;
  useEffect(() => { if (stick.current) bottom.current?.scrollIntoView({ block: "nearest" }); }, [latest]);
  const readThrough = history.data?.pages[0]?.read_through;
  useEffect(() => {
    if (!rid || !readThrough || document.hidden || !timeline.current?.getClientRects().length) return;
    void api.put(`${roomUrl}/read`, { message_id: readThrough }, { progress: false }).catch(() => {});
  }, [rid, roomUrl, readThrough, mobileChat]);

  async function action(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError("");
    try { await fn(); } catch (e) { if (active.current) setError(workspaceError(e)); }
    finally { if (active.current) setBusy(false); }
  }
  async function start() {
    await action(async () => {
      const { data } = await api.post<{ conversation_id: number }>("/collaboration/context-conversations", { workspace_id: wid, module: "project_management", entity_type: "project", entity_id: project.id });
      qc.setQueryData(lookupKey, data);
      await qc.invalidateQueries({ queryKey: ["chat-inbox", scope, wid] });
    });
  }
  async function send() {
    if (!canWrite || busy || (!draft.trim() && !files.length)) return;
    const body = draft.trim(), ids = files.map(f => f.id);
    if (!request.current || request.current.body !== body || request.current.ids !== ids.join(",")) request.current = { body, ids: ids.join(","), client_id: crypto.randomUUID() };
    const client_id = request.current.client_id;
    await action(async () => {
      await api.post(`${roomUrl}/messages`, { body, client_id, attachment_ids: ids, parent_id: null });
      if (!active.current) return;
      setDraft(""); setFiles([]); request.current = undefined; stick.current = true;
      await qc.invalidateQueries({ queryKey: ["chat-history", "project", scope, wid, rid] });
      await qc.invalidateQueries({ queryKey: ["chat-inbox", scope, wid] });
      inputRef.current?.focus();
    });
  }
  function upload(file: File) {
    if (!canWrite) return;
    void action(async () => {
      const form = new FormData(); form.append("file", file);
      const { data } = await api.post<Attachment>(`${roomUrl}/attachments`, form);
      if (active.current) setFiles(old => [...old, data]);
    });
  }
  function download(file: Attachment) {
    void action(async () => {
      const { data } = await api.get(`${roomUrl}/attachments/${file.id}`, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(data), link = document.createElement("a");
      link.href = objectUrl; link.download = file.name; link.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    });
  }
  function chooseTask(task: PMSTask) {
    const link = `${window.location.origin}/pms/tasks/${task.id}`;
    const text = taskPicker === "remind" ? `Reminder: ${task.title}${task.assignee_name ? ` — ${task.assignee_name}` : ""}${task.due_date ? `\nDue: ${formatDate(task.due_date)}` : ""}\nPlease share your progress or let us know if you need help.\n${link}` : `${task.task_key}: ${task.title}\nStatus: ${task.status}${task.due_date ? ` · Due: ${formatDate(task.due_date)}` : ""}\n${link}`;
    setDraft(old => old ? `${old}\n\n${text}` : text); setTaskPicker(null); inputRef.current?.focus();
  }
  const loadError = lookup.error || inbox.error || history.error;
  const participants = room?.participants || [];
  const openTasks = tasks.filter(t => !["Done", "Completed", "Cancelled", "Closed"].includes(t.status));
  return <section className={`project-comms ${mobileChat ? "project-comms--chat" : ""}`} aria-label="Project communication">
    <aside className="pc-sidebar">
      <h2>Conversations <MessageCircle size={20} /></h2>
      <label className="pc-search"><Search size={17} /><input aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={e => setSearch(e.target.value)} /></label>
      {"project team".includes(search.toLowerCase()) && <button className="pc-conversation" onClick={() => setMobileChat(true)} aria-current="true"><span className="pc-avatar"><Users size={23} /></span><span><strong>Project Team</strong><small>{participants.length ? `${participants.length} conversation member${participants.length === 1 ? "" : "s"}` : project.name}</small><small>Project discussion</small></span></button>}
      {search && !"project team".includes(search.toLowerCase()) && <p className="pc-muted">No matching conversations.</p>}
      <div className="pc-side-note"><Users size={18} /><p>Keep project updates, files, and task discussions together.</p></div>
      <Link className="pc-manage" to={`/pms/messages?workspace=${wid || ""}${rid ? `&conversation=${rid}` : ""}`}>Manage conversations & members →</Link>
      <div className="pc-connection"><span />Internal project chat</div>
    </aside>
    <div className="pc-main">
      <header className="pc-header"><button className="pc-back pc-icon" aria-label="Back to conversations" onClick={() => setMobileChat(false)}><ArrowLeft size={20} /></button><span className="pc-avatar"><Users size={23} /></span><div><h3>Project Team</h3><p>{room?.archived ? "Archived · Read only" : `${project.name} · Internal discussion`}</p></div><Link className="pc-header-link" to={`/pms/messages?workspace=${wid || ""}${rid ? `&conversation=${rid}` : ""}`}>Details</Link></header>
      {(error || loadError) && <div role="alert" className="pc-error">{error || workspaceError(loadError)}{loadError && <Button type="submit" variant="outline" onClick={() => { void lookup.refetch(); void inbox.refetch(); void history.refetch(); }}>Retry</Button>}</div>}
      <div className="pc-timeline" ref={timeline} role="log" aria-label="Project messages" onScroll={() => { const el = timeline.current; if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }}>
        {!wid ? <div className="pc-empty"><MessageCircle size={36} /><h3>A workspace is required</h3><p>Assign this project to a workspace to use project communication.</p></div> : lookup.isPending || (!!rid && (inbox.isPending || (!!room?.joined && history.isPending))) ? <p className="pc-empty" role="status">Loading project conversation…</p> : !rid && !lookup.isError ? <div className="pc-empty"><MessageCircle size={40} /><h3>Start the project conversation</h3><p>Share updates, discuss tasks, and keep files with this project.</p><button className="pc-primary" disabled={busy} onClick={() => void start()}>Start conversation</button><p className="pc-muted">Invite teammates using conversation details after creating the chat.</p></div> : rid && !inbox.isPending && !room && !inbox.isError ? <div className="pc-empty">This conversation is unavailable. Check your membership in Messages.</div> : room && !room.joined ? <div className="pc-empty">Join this conversation from Messages to view its history.</div> : !loadError && !messages.length ? <div className="pc-empty"><MessageCircle size={40} /><h3>Your project conversation starts here</h3><p>Send an update or share a task with the conversation members.</p></div> : null}
        {history.hasNextPage && <button className="pc-older" disabled={history.isFetchingNextPage} onClick={() => { stick.current = false; const el = timeline.current; const height = el?.scrollHeight || 0; void history.fetchNextPage().then(() => requestAnimationFrame(() => { if (el) el.scrollTop += el.scrollHeight - height; })); }}>{history.isFetchingNextPage ? "Loading…" : "Load earlier messages"}</button>}
        {messages.map((message, index) => {
          const date = instant(message.created_at), mine = message.author_id === user?.id;
          const sender = participants.find(p => p.id === message.author_id);
          const showDate = index === 0 || date.toDateString() !== instant(messages[index - 1].created_at).toDateString();
          return <div key={message.id}>{showDate && <div className="pc-date"><span>{date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</span></div>}<article className={`pc-bubble ${mine ? "pc-bubble--mine" : ""}`}><strong className="pc-sender">{mine ? "You" : sender ? personName(sender.email) : "Project member"}</strong>{message.deleted_at ? <p className="pc-muted">This message was deleted.</p> : <><RichTextContent value={message.body} />{message.attachments.map(file => <button className="pc-file" key={file.id} disabled={busy} onClick={() => download(file)}><FileText size={27} /><span><strong>{file.name}</strong><small>{Math.max(1, Math.round(file.size / 1024))} KB</small></span><Download size={18} /></button>)}</>}<time className="pc-time" dateTime={date.toISOString()}>{date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}{mine && <Check size={14} aria-label="Saved" />}</time></article></div>;
        })}<div ref={bottom} />
      </div>
      <div className="pc-compose">
        {taskPicker && <div className="pc-task-picker"><div><strong>{taskPicker === "remind" ? "Choose a task to remind the team" : "Share a project task"}</strong><button className="pc-icon" aria-label="Close task picker" onClick={() => setTaskPicker(null)}><X size={18} /></button></div>{(taskPicker === "remind" ? openTasks : tasks).map(task => <button key={task.id} onClick={() => chooseTask(task)}><ListChecks size={18} /><span>{task.title}<small>{task.status}{task.due_date ? ` · Due ${formatDate(task.due_date)}` : ""}</small></span></button>)}{!(taskPicker === "remind" ? openTasks : tasks).length && <p>No tasks available.</p>}</div>}
        <div className="pc-quick"><button disabled={!canWrite || busy} onClick={() => setTaskPicker(taskPicker === "remind" ? null : "remind")}><Bell size={16} />Send reminder</button><button disabled={!canWrite || busy} onClick={() => setTaskPicker(taskPicker === "share" ? null : "share")}><ListChecks size={16} />Share task</button></div>
        {files.length > 0 && <div className="pc-uploads">{files.map(file => <span key={file.id}><FileText size={15} />{file.name}<button aria-label={`Remove ${file.name}`} disabled={busy} onClick={() => void action(async () => { await api.delete(`${roomUrl}/attachments/${file.id}`); if (active.current) setFiles(old => old.filter(f => f.id !== file.id)); })}><X size={14} /></button></span>)}</div>}
        {emojiOpen && <div className="pc-emojis">{["😀", "👍", "✅", "🙏", "🎉", "👋"].map(emoji => <button key={emoji} aria-label={`Insert ${emoji}`} onClick={() => { setDraft(old => old + emoji); setEmojiOpen(false); inputRef.current?.focus(); }}>{emoji}</button>)}</div>}
        <form className="pc-input-row" onSubmit={e => { e.preventDefault(); void send(); }}><input ref={uploadRef} type="file" className="sr-only" tabIndex={-1} aria-label="Attach a file" onChange={e => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = ""; }} /><button type="button" className="pc-icon" aria-label="Attach file" disabled={!canWrite || busy || files.length >= 10} onClick={() => uploadRef.current?.click()}><Plus size={24} /></button><button type="button" className="pc-icon" aria-label="Choose emoji" aria-expanded={emojiOpen} disabled={!canWrite || busy} onClick={() => setEmojiOpen(!emojiOpen)}><Smile size={22} /></button><textarea ref={inputRef} rows={1} aria-label="Message" placeholder={canWrite ? "Type a message…" : "Open an active conversation to send a message"} value={draft} maxLength={20000} disabled={!canWrite || busy} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} /><button type="submit" className="pc-send" aria-label="Send message" disabled={!canWrite || busy || (!draft.trim() && !files.length)}><Send size={21} /></button></form>
        {busy && <small role="status">Saving…</small>}
      </div>
    </div>
  </section>;
}
