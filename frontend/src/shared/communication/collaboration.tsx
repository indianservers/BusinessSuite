import { communicationActor, useCommunicationScope } from "./scope";
import { MeetingPanel } from "./MeetingPanel";
import { createPortal } from "react-dom";
import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { useQuery, useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Bookmark, CheckCheck, FileText, Flag, MessageSquare, MoreHorizontal, Pin, Plus, Send, Smile, Sparkles, Users, X } from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { workspaceError } from "@/apps/project-management/pages/workspaceTypes";
import type { Collaboration, CommunicationFeatures, CommunicationFile, Message, Participant } from "./types";

const root = (wid: number, rid: number) => `/collaboration/workspaces/${wid}/chat/conversations/${rid}`;
export function useCollaboration(wid: number, rid: number, enabled: boolean) {
  const actor=useCommunicationScope();
  return useQuery({ queryKey: ["communication-collaboration", actor, wid, rid], enabled: !!wid && !!rid && enabled,
    queryFn: async ({ signal }) => (await api.get<Collaboration>(`${root(wid,rid)}/collaboration`, { signal, progress:false })).data });
}

export function MessageActions({ wid, rid, message, data, canWrite, manager, participants, allowFollowUps }: { wid: number; rid: number; message: Message; data?: Collaboration; canWrite: boolean; manager: boolean; participants: Participant[]; allowFollowUps: boolean }) {
  const qc = useQueryClient();
  const user = useAuthStore(s => s.user);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [followup, setFollowup] = useState(false);
  const menuRef=useRef<HTMLDetailsElement>(null);
  const popupRef=useRef<HTMLDivElement>(null);
  const [position,setPosition]=useState<{left:number;top:number}|null>(null);
  useEffect(()=>{if(!position)return;const close=(e:Event)=>{if(popupRef.current?.contains(e.target as Node)||menuRef.current?.contains(e.target as Node))return;if(menuRef.current)menuRef.current.open=false;setPosition(null);};const key=(e:KeyboardEvent)=>{if(e.key==="Escape"){if(menuRef.current)menuRef.current.open=false;setPosition(null);menuRef.current?.querySelector("summary")?.focus();}};document.addEventListener("pointerdown",close);document.addEventListener("keydown",key);return()=>{document.removeEventListener("pointerdown",close);document.removeEventListener("keydown",key);};},[position]);
  const [convert, setConvert] = useState(false);
  async function flag(path: string, enabled: boolean) {
    setBusy(true); setError("");
    try { await api.put(`${root(wid,rid)}/messages/${message.id}/${path}`, { enabled }); await qc.invalidateQueries({ queryKey: ["communication-collaboration", communicationActor(user), wid, rid] }); }
    catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  }
  const saved = !!data?.saved_ids.includes(message.id), pinned = !!data?.pins.some(p => p.id === message.id);
  return <div className="ce-message-actions">
    <div className="ce-reactions">{data?.reactions.filter(r => r.message_id === message.id).map(r => <button type="button" key={r.emoji} aria-label={`${r.emoji} ${r.count} reactions`} aria-pressed={r.mine} disabled={!canWrite || busy} onClick={() => void flag(`reactions/${encodeURIComponent(r.emoji)}`, !r.mine)}>{r.emoji} <span>{r.count}</span></button>)}</div>
    <details ref={menuRef} data-message-actions onToggle={e=>{if(!e.currentTarget.open){setPosition(null);return;}const rect=e.currentTarget.getBoundingClientRect();setPosition({left:Math.max(8,Math.min(rect.left,window.innerWidth-240)),top:rect.top>300?rect.top-285:rect.bottom+5});}}><summary aria-label="Message actions"><MoreHorizontal size={16}/></summary></details>{position && createPortal(<div ref={popupRef} className="ce-action-popover ce-portal-menu" style={{position:"fixed",left:position.left,top:position.top,bottom:"auto",zIndex:220}} aria-label="Message actions menu">
      {canWrite && <div className="ce-emoji" aria-label="Add reaction">{["👍", "❤️", "🎉", "👀", "✅", "🙏", "💡", "🚀"].map(emoji => <button type="button" key={emoji} aria-label={`React ${emoji}`} disabled={busy} onClick={() => void flag(`reactions/${encodeURIComponent(emoji)}`, !data?.reactions.some(r => r.message_id === message.id && r.emoji === emoji && r.mine))}>{emoji}</button>)}</div>}
      <button type="button" disabled={busy} onClick={() => void flag("saved", !saved)}><Bookmark size={14}/>{saved ? "Unsave message" : "Save message"}</button>
      {canWrite && manager && <button type="button" disabled={busy} onClick={() => void flag("pin", !pinned)}><Pin size={14}/>{pinned ? "Unpin message" : "Pin message"}</button>}
      {canWrite && allowFollowUps && <><button type="button" onClick={() => { if(menuRef.current)menuRef.current.open=false; setPosition(null); setConvert(false); setFollowup(true); }}><Flag size={14}/>Create follow-up</button><button type="button" onClick={() => { if(menuRef.current)menuRef.current.open=false; setPosition(null); setConvert(true); setFollowup(true); }}><CheckCheck size={14}/>Convert to PMS task</button></>}
    </div>,document.body)}
    {pinned && <small><Pin size={12}/> Pinned</small>}{saved && <small><Bookmark size={12}/> Saved</small>}
    {error && <p role="alert">{error}</p>}
    <FollowUpDialog open={followup} onClose={() => setFollowup(false)} wid={wid} rid={rid} message={message} participants={manager ? participants : participants.filter(p => p.id === user?.id)} convert={convert}/>
  </div>;
}

function FollowUpDialog({ open, onClose, wid, rid, message, participants, convert }: { open: boolean; onClose: () => void; wid: number; rid: number; message: Message; participants: Participant[]; convert: boolean }) {
  const user = useAuthStore(s => s.user), qc = useQueryClient();
  const [title, setTitle] = useState(""); const [description, setDescription] = useState("");
  const [assignee, setAssignee] = useState(user?.id || 0); const [due, setDue] = useState("");
  const [priority, setPriority] = useState("Medium"), [project, setProject] = useState("");
  const [requestId, setRequestId] = useState(""); const [error, setError] = useState(""); const [busy,setBusy] = useState(false);
  useEffect(() => { if(open) { setTitle(richTextPlainText(message.body).slice(0, 180)); setDescription(""); setRequestId(crypto.randomUUID()); setError(""); setAssignee(user?.id || 0); } }, [open, message.id, user?.id]);
  const projects = useQuery({ queryKey: ["communication-projects", communicationActor(user), wid], enabled: open && convert, queryFn: async () => (await api.get<{id:number;name:string}[]>(`/collaboration/workspaces/${wid}/projects`)).data });
  return <Dialog.Root open={open} onOpenChange={value => { if(!value && !busy) onClose(); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[210] bg-black/40"/><Dialog.Content className="ce-dialog fixed left-1/2 top-1/2 z-[211] w-[min(94vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-background p-6 shadow-xl"><Dialog.Title>{convert ? "Convert message to PMS task" : "Create follow-up"}</Dialog.Title><Dialog.Description>Linked to message #{message.id}. Review the assignment before creating it.</Dialog.Description>
    <form onSubmit={e => { e.preventDefault(); if(busy) return; setBusy(true); setError(""); void api.post(`${root(wid,rid)}/followups`, { client_id:requestId, message_id:message.id, title, description, assignee_id:assignee, priority, due_at:due ? new Date(due).toISOString() : null, project_id:convert ? Number(project) : null }).then(async () => { await qc.invalidateQueries({queryKey:["communication-collaboration",communicationActor(user),wid,rid]}); onClose(); }).catch(e => setError(workspaceError(e))).finally(() => setBusy(false)); }}><fieldset disabled={busy}>
      <label>Title<input required maxLength={220} value={title} onChange={e => setTitle(e.target.value)}/></label>
      <label>Description<textarea value={description} maxLength={10000} onChange={e => setDescription(e.target.value)}/></label>
      <label>Responsible person<select value={assignee} onChange={e => setAssignee(Number(e.target.value))}>{participants.map(p => <option key={p.id} value={p.id}>{p.email}</option>)}</select></label>
      <div className="ce-form-row"><label>Due date & time<input type="datetime-local" value={due} onChange={e => setDue(e.target.value)}/></label><label>Priority<select value={priority} onChange={e => setPriority(e.target.value)}>{["Low","Medium","High","Urgent"].map(p => <option key={p}>{p}</option>)}</select></label></div>
      {convert && <label>PMS project<select required value={project} onChange={e => setProject(e.target.value)}><option value="">Choose authorized project</option>{projects.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>{projects.isError && <p role="alert">{workspaceError(projects.error)}</p>}</label>}
      {error && <p role="alert">{error}</p>}<footer><button type="button" onClick={onClose}>Cancel</button><button type="submit" disabled={busy || (convert && !project)}>{busy ? "Creating…" : convert ? "Create PMS task" : "Create follow-up"}</button></footer>
    </fieldset></form></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function CollaborationDetails({ wid,rid,data,error,participants,description,onJump,onDownload,messages,onThread,view,features,canWrite=false }: {wid:number;rid:number;data?:Collaboration;error:unknown;participants:Participant[];description:string;onJump:(id:number)=>void;onDownload:(file:CommunicationFile)=>Promise<void>;messages:Message[];onThread:(id:number)=>void;view:string;features:CommunicationFeatures;canWrite?:boolean}) {
  const user = useAuthStore(s=>s.user), qc = useQueryClient(); const [failure,setFailure] = useState(""); const [pending,setPending] = useState<number|null>(null);
  const [ai,setAI]=useState(""); const [thinking,setThinking]=useState(false);
  const savedThreads=useInfiniteQuery({queryKey:["communication-discussions",communicationActor(user),wid,rid,view],enabled:view==="threads"||view==="saved",initialPageParam:null as number|null,queryFn:async({pageParam})=>(await api.get<{messages:Message[];before:number|null}>(`${root(wid,rid)}/${view}`,{params:{before:pageParam||undefined}})).data,getNextPageParam:p=>p.before||undefined,maxPages:5});
  const filePages=useInfiniteQuery({queryKey:["communication-files",communicationActor(user),wid,rid],enabled:view==="files",initialPageParam:null as number|null,queryFn:async({pageParam})=>(await api.get<{files:CommunicationFile[];before:number|null}>(`${root(wid,rid)}/files`,{params:{before:pageParam||undefined},progress:false})).data,getNextPageParam:p=>p.before||undefined,maxPages:5});
  const sharedFiles=view==="files" ? filePages.data?.pages.flatMap(p=>p.files)||[] : data?.files||[];
  const discussions=savedThreads.data?.pages.flatMap(p=>p.messages)||[];
  return <div className="ce-details-content">
    {!!error && <p role="alert">{workspaceError(error)}</p>}
    {view === "details" && <><section><h3>About this conversation</h3><RichTextContent value={description || "A place to discuss work with your team."}/></section><section><h3><Users size={14}/>Participants · {participants.length}</h3><div className="ce-participants">{participants.slice(0,12).map(p=><span key={p.id} className="ce-avatar" title={p.email}>{p.email.slice(0,1).toUpperCase()}</span>)}</div>{participants.length > 12 && <small>+{participants.length-12} more</small>}</section></>}
    {data && (view === "details" || view === "chat") && data.pins.length > 0 && <section><h3><Pin size={14}/>Pinned messages</h3>{data.pins.map(p=><button key={p.id} onClick={()=>onJump(p.id)} className="ce-pin-card">{richTextPlainText(p.body).slice(0,180)}</button>)}</section>}
    {features.followUps !== false && (view === "followups" || view === "details") && <section><h3><Flag size={14}/>Follow-ups & tasks <span>{data?.followups.length || 0}</span></h3>{!data?.followups.length && <p>No follow-ups yet. Use a message’s actions to create one.</p>}{data?.followups.map(f=><article key={f.id} className="ce-followup" data-context-record={f.title}><button onClick={()=>onJump(f.message_id)}>{f.title}</button><small>{participants.find(p=>p.id===f.assignee_id)?.email || "Conversation member"} · {f.priority}</small>{f.due_at && <time>{new Date(f.due_at+(/Z$/.test(f.due_at)?"":"Z")).toLocaleString()}</time>}{f.task_id ? <Link to={`/pms/tasks/${f.task_id}`}>{f.task_key} · {f.status} ↗</Link> : <select aria-label={`Status for ${f.title}`} value={f.status} disabled={!canWrite || pending === f.id || (user?.id !== f.assignee_id && user?.id !== f.created_by)} onChange={e=>{setPending(f.id);setFailure("");void api.patch(`${root(wid,rid)}/followups/${f.id}`,{status:e.target.value}).then(()=>qc.invalidateQueries({queryKey:["communication-collaboration",communicationActor(user),wid,rid]})).catch(e=>setFailure(workspaceError(e))).finally(()=>setPending(null));}}>{["Open","In Progress","Waiting","Completed","Cancelled"].map(s=><option key={s}>{s}</option>)}</select>}</article>)}{data?.before && <button onClick={()=>{setFailure("");void api.get<Collaboration>(`${root(wid,rid)}/collaboration`,{params:{before:data.before}}).then(({data:next})=>qc.setQueryData<Collaboration>(["communication-collaboration",communicationActor(user),wid,rid],old=>old?{...old,followups:[...old.followups,...next.followups],before:next.before}:next)).catch(e=>setFailure(workspaceError(e)));}}>Earlier follow-ups</button>}{failure && <p role="alert">{failure}</p>}</section>}
    {features.files !== false && (view === "files" || view === "details") && <section><h3><FileText size={14}/>Shared files</h3>{!sharedFiles.length && <p>No files shared yet.</p>}{sharedFiles.map(f=><button className="ce-shared-file" key={f.id} onClick={()=>void onDownload(f)}><FileText size={23}/><span>{f.name}<small>{Math.ceil(f.size/1024)} KB · {f.mime}</small></span></button>)}</section>}
    {(view === "threads" || view === "saved") && <section><h3><MessageSquare size={14}/>{view === "threads" ? "Threads" : "Saved messages"}</h3>{savedThreads.isPending && <p role="status">Loading…</p>}{savedThreads.isError && <p role="alert">{workspaceError(savedThreads.error)}</p>}{discussions.map(m=><button key={m.id} className="ce-pin-card" onClick={()=>view === "threads" ? onThread(m.id) : onJump(m.id)}>{richTextPlainText(m.body).slice(0,160)}{view === "threads" && <small>{m.reply_count} replies</small>}</button>)}{!savedThreads.isPending&&!discussions.length&&<p>{view === "threads" ? "No threads yet. Reply to a message to start one." : "No saved messages in this conversation."}</p>}{savedThreads.hasNextPage&&<button onClick={()=>savedThreads.fetchNextPage()}>Load earlier</button>}</section>}
    {view === "details" && data?.contexts.map(c=><section key={`${c.module}:${c.entity_type}:${c.entity_id}`}><h3>Related record</h3><p>{c.module} · {c.entity_type} #{c.entity_id}</p></section>)}
    {view === "details" && features.meetings !== false && <MeetingPanel wid={wid} rid={rid} canSchedule={canWrite}/>}
    {view === "details" && <ConversationPreferences wid={wid} rid={rid}/>}
    {view === "details" && features.aiAssistant !== false && <section><h3><Sparkles size={14}/>AI conversation assistance</h3><p>Summaries use only messages you can read. Suggested actions require your review.</p><div className="ce-ai-actions">{[["summary","Summarize"],["actions","Find action items"],["questions","Unresolved questions"],["draft","Draft a reply"]].map(([action,label])=><button disabled={thinking} key={action} onClick={()=>{setThinking(true);setAI("");void api.post<{summary:string}>(`${root(wid,rid)}/ai`,{action}).then(({data})=>setAI(data.summary)).catch(e=>setAI(workspaceError(e))).finally(()=>setThinking(false));}}>{label}</button>)}</div>{thinking && <p role="status">Reading authorized messages…</p>}{ai && <p className="ce-ai-result">{ai}</p>}</section>}
  </div>;
}

export function ConversationPreferences({wid,rid}:{wid:number;rid:number}) {
  const qc=useQueryClient(),[error,setError]=useState("");
  const actor=useCommunicationScope();
  const query=useQuery({queryKey:["communication-preferences",actor,wid,rid],queryFn:async()=>(await api.get<{mode:string;favorite:boolean;dnd_until:string|null}>(`${root(wid,rid)}/preferences`)).data});
  const [busy,setBusy]=useState(false);
  function update(values:Record<string,unknown>){if(!query.data)return;setBusy(true);setError("");void api.put(`${root(wid,rid)}/preferences`,{...query.data,...values}).then(()=>Promise.all([qc.invalidateQueries({queryKey:["communication-preferences",actor,wid,rid]}),qc.invalidateQueries({queryKey:["chat-inbox"]})])).catch(e=>setError(workspaceError(e))).finally(()=>setBusy(false));}
  return <section><h3>Conversation preferences</h3>{query.data&&<><label>Notify me<select aria-label="Conversation notifications" value={query.data.mode} disabled={busy} onChange={e=>update({mode:e.target.value})}><option value="all">All messages</option><option value="mentions">Mentions only</option><option value="none">No notifications</option></select></label><button disabled={busy} onClick={()=>update({favorite:!query.data?.favorite})}>{query.data.favorite?"Unpin conversation":"Pin conversation"}</button><button disabled={busy} onClick={()=>update({dnd_until:query.data?.dnd_until?null:new Date(Date.now()+3600000).toISOString()})}>{query.data.dnd_until?"Turn off Do Not Disturb":"Do Not Disturb for 1 hour"}</button></>}{(error||query.isError)&&<p role="alert">{error||workspaceError(query.error)}</p>}</section>;
}
