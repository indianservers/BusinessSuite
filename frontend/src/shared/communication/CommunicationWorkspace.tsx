import { useCommunicationScope } from "./scope";
import { ContextualChat } from "./adapters";
import { RichTextField, RichTextContent, richTextPlainText } from "@/components/rich-text/LazyRichText";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { useRealtimeStore } from "@/apps/project-management/realtime";
import { workspaceError, type WorkspaceMember } from "@/apps/project-management/pages/workspaceTypes";
import "@/apps/project-management/pages/Messaging.css";
import "./communication.css";
import { CollaborationDetails, MessageActions, useCollaboration } from "./collaboration";
import { appendRichMarkdown } from "@/components/rich-text/content";
import { usePresence } from "./usePresence";
import { useCommunicationEvents } from "./useCommunicationEvents";
import { useCommunicationDraft } from "./useCommunicationDraft";
import type { CommunicationWorkspaceProps } from "./types";
type FileInfo = { id: number; name: string; size: number; mime: string };
type Msg = {
  id: number;
  client_id?: string;
  body: string;
  author_id: number;
  parent_id: number | null;
  root_preview?: string | null;
  created_at: string;
  deleted_at: string | null;
  edited_at: string | null;
  reply_count: number;
  latest_reply: string | null;
  attachments: FileInfo[];
  conversation_id?: number;
  conversation_name?: string;
};
type Room = {
  id: number;
  name: string;
  description: string;
  kind: string;
  visibility: string;
  owner_id: number;
  joined: boolean;
  archived: boolean;
  favorite?: boolean;
  has_draft?: boolean;
  last_message?: string;
  last_message_at?: string;
  muted: boolean;
  unread: number;
  participants: { id: number; email: string }[];
};
type History = {
  messages: Msg[];
  root: Msg | null;
  before: number | null;
  read_through: number;
  thread_id?: number | null;
};
const base = "/collaboration/workspaces";
const instant = (value: string) =>
  new Date(/(Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
function WorkspaceCore({ module = "PMS", workspaceId, features = {} }: CommunicationWorkspaceProps) {
  useCommunicationEvents();
  const scope=useCommunicationScope();
  const { user } = useAuthStore(),
    qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [selectedWorkspace, setWorkspace] = useState(
    workspaceId || Number(params.get("workspace")) || 0,
  );
  const workspaces = useQuery({
    queryKey: ["messaging-workspaces", scope],
    queryFn: async () =>
      (await api.get<{ id: number; name: string; role: string }[]>(base)).data,
  });
  const wid = selectedWorkspace || workspaces.data?.[0]?.id || 0,
    rid = Number(params.get("conversation")) || 0,
    thread = Number(params.get("thread")) || 0,
    target = Number(params.get("message")) || 0,
    url = `${base}/${wid}/chat`,
    context = `${scope}:${wid}:${rid}:${thread}`;
  const timelineRef=useRef<HTMLDivElement>(null);
  const stickToBottom=useRef(true);
  const current = useRef(context);
  current.current = context;
  const connected = useRealtimeStore(s => s.connected);
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [conversationFilter, setConversationFilter] = useState("");
  const [inboxFilter, setInboxFilter] = useState("all");
  const [activeTab, setActiveTab] = useState("chat");
  const inbox = useQuery({
    queryKey: ["chat-inbox", scope, wid],
    enabled: !!wid,
    queryFn: async () =>
      (
        await api.get<{ conversations: Room[]; can_send: boolean }>(
          `${url}/conversations`, { progress:false },
        )
      ).data,
    refetchInterval: connected ? false : 45000,
  });
  const people = useQuery({
    queryKey: ["chat-people", scope, wid],
    enabled: !!wid,
    queryFn: async () =>
      (await api.get<WorkspaceMember[]>(`${base}/${wid}/members`)).data,
  });
  const room = inbox.data?.conversations.find((r) => r.id === rid),
    canWrite = !!room?.joined && !room.archived && inbox.data?.can_send;
  const presence = usePresence(wid,rid,!!room?.joined);
  const collaboration = useCollaboration(wid, rid, !!room?.joined);
  const history = useInfiniteQuery({
    queryKey: ["chat-history", context, target],
    enabled: !!room?.joined,
    initialPageParam: null as number | null,
    maxPages: 5,
    queryFn: async ({ pageParam, signal }) =>
      (
        await api.get<History>(`${url}/conversations/${rid}/messages`, {
          signal,
          progress: false,
          params: {
            parent_id: thread || undefined,
            before: pageParam || undefined,
            around: !pageParam ? target || undefined : undefined,
          },
        })
      ).data,
    getNextPageParam: (p) => p.before || undefined,
    refetchInterval: connected ? false : 45000,
  });
  const messages = [
    ...new Map(
      history.data?.pages.flatMap((p) => p.messages).map((m) => [m.id, m]) ||
        [],
    ).values(),
  ].sort((a, b) => a.id - b.id);
  const [drafts, setDrafts] = useState<Record<string, string>>(() => {
      try {
        return JSON.parse(
          sessionStorage.getItem(`pms-chat-drafts-${user?.id}`) || "{}",
        );
      } catch {
        return {};
      }
    }),
    [uploads, setUploads] = useState<Record<string, FileInfo[]>>({});
  const [enterSends, setEnterSends] = useState(() => localStorage.getItem("communication-enter-sends") !== "false");
  const draft = drafts[context] || "",
    files = uploads[context] || [],
    requests = useRef<
      Record<string, { id: string; body: string; files: string }>
    >({}),
    controller = useRef<AbortController | null>(null);
  useCommunicationDraft({ wid, rid, thread, context, enabled: !!canWrite, draft: drafts[context], setDraft: (value) => setDrafts(d => ({ ...d, [context]: value })) });
  const [pendingSend, setPendingSend] = useState<{
    context: string;
    client_id: string;
    body: string;
  } | null>(null);
  const [busy, setBusy] = useState(false),
    [progress, setProgress] = useState<number | null>(null),
    [error, setError] = useState("");
  const [dialog, setDialog] = useState<
      "create" | "details" | "edit" | "delete" | null
    >(null),
    [kind, setKind] = useState(features.directMessages !== false ? "dm" : features.groupChats !== false ? "group" : "channel"),
    [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [visibility, setVisibility] = useState("private"),
    [participants, setParticipants] = useState<number[]>([]),
    [editMsg, setEditMsg] = useState<Msg | null>(null),
    [body, setBody] = useState(""),
    [fileId, setFileId] = useState("");
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState<string | null>(null),
    [within, setWithin] = useState(false),
    [author, setAuthor] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [hasFiles, setHasFiles] = useState(false);
  const results = useInfiniteQuery({
    queryKey: [
      "chat-search",
      scope,
      wid,
      search,
      within ? rid : 0,
      author,
      from,
      to,
      hasFiles,
    ],
    enabled: !!wid && search !== null,
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam, signal }) =>
      (
        await api.get<{ results: Msg[]; before: number | null }>(
          `${url}/search`,
          {
            signal,
            params: {
              q: search,
              conversation_id: within ? rid || undefined : undefined,
              author_id: author || undefined,
              date_from: from ? `${from}T00:00:00` : undefined,
              date_to: to ? `${to}T23:59:59.999` : undefined,
              attachments: hasFiles,
              before: pageParam || undefined,
            },
          },
        )
      ).data,
    getNextPageParam: (p) => p.before || undefined,
  });
  const projectFiles = useInfiniteQuery({
    queryKey: ["chat-project-files", scope, wid],
    enabled: !!wid && dialog === "details" && !!canWrite,
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam, signal }) =>
      (
        await api.get<{
          items: { id: number; name: string; size: number }[];
          before: number | null;
        }>(`${url}/project-files`, {
          signal,
          progress: false,
          params: { before: pageParam || undefined },
        })
      ).data,
    getNextPageParam: (p) => p.before || undefined,
  });
  const event = useRealtimeStore((s) => s.events[0]);
  useEffect(() => {
    if (event?.type === "chat.invalidate" || event?.type.startsWith("task.")) {
      void qc.invalidateQueries({ queryKey: ["chat-inbox"] });
      void qc.invalidateQueries({ queryKey: ["chat-history"] });
      void qc.invalidateQueries({ queryKey: ["chat-search"] });
      void qc.invalidateQueries({ queryKey: ["communication-collaboration"] });
      void qc.invalidateQueries({ queryKey: ["communication-discussions"] });
      void qc.invalidateQueries({ queryKey: ["communication-files"] });
      void qc.invalidateQueries({ queryKey: ["communication-meetings"] });
    }
  }, [event, qc]);
  useEffect(() => {
    setError("");
    setActiveTab("chat");
    closeDialog();
    controller.current?.abort();
    setProgress(null);
  }, [context]);
  useEffect(() => {
    try {
      sessionStorage.setItem(
        `pms-chat-drafts-${user?.id}`,
        JSON.stringify(
          Object.fromEntries(
            Object.entries(drafts).filter(([key]) =>
              key.startsWith(`${user?.id}:`),
            ),
          ),
        ),
      );
    } catch {
      /* Draft remains in memory. */
    }
  }, [drafts, user?.id]);
  useEffect(()=>{stickToBottom.current=true;},[context]);
  useEffect(()=>{
    if(target || !stickToBottom.current)return;
    const frame=requestAnimationFrame(()=>{if(timelineRef.current)timelineRef.current.scrollTop=timelineRef.current.scrollHeight;});
    return()=>cancelAnimationFrame(frame);
  },[context,messages[messages.length-1]?.id,pendingSend?.client_id,target]);
  useEffect(() => {
    if (target && history.data)
      requestAnimationFrame(() =>
        document
          .getElementById(`chat-${target}`)
          ?.scrollIntoView({ block: "center" }),
      );
  }, [target, history.data]);
  function closeDialog() {
    if (current.current === context) setDialog(null);
  }
  useEffect(() => {
    const parent = history.data?.pages[0]?.thread_id;
    if (target && parent && thread !== parent)
      setParams(
        {
          workspace: String(wid),
          conversation: String(rid),
          thread: String(parent),
          message: String(target),
        },
        { replace: true },
      );
  }, [target, thread, wid, rid, history.data, setParams]);
  const manager =
    !!inbox.data?.can_send &&
    room &&
    (room.owner_id === user?.id ||
      (["Owner", "Admin"].includes(
        workspaces.data?.find((w) => w.id === wid)?.role || "",
      ) &&
        ["channel", "general"].includes(room.kind)));
  const title = (r: Room) =>
    r.kind === "dm"
      ? r.participants.find((p) => p.id !== user?.id)?.email || r.name
      : r.name;
  function select(id: number, root = 0, message = 0) {
    if (current.current !== context) return;
    setSearch(null);
    setParams({
      workspace: String(wid),
      conversation: String(id),
      ...(root ? { thread: String(root) } : {}),
      ...(message ? { message: String(message) } : {}),
    });
  }
  async function refresh() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["chat-inbox"] }),
      qc.invalidateQueries({ queryKey: ["chat-history"] }),
      qc.invalidateQueries({ queryKey: ["chat-search"] }),
      qc.invalidateQueries({ queryKey: ["communication-collaboration"] }),
    ]);
  }
  async function action(fn: () => Promise<unknown>) {
    if (busy) return;
    const key = context;
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      if (current.current === key) setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    const key = context,
      ids = files.map((f) => f.id).sort((a, b) => a - b);
    let req = requests.current[key];
    if (!req || req.body !== draft.trim() || req.files !== ids.join(",")) {
      req = {
        id: crypto.randomUUID(),
        body: draft.trim(),
        files: ids.join(","),
      };
      requests.current[key] = req;
    }
    stickToBottom.current=true;
    setPendingSend({ context: key, client_id: req.id, body: req.body });
    await action(async () => {
      await api.post(`${url}/conversations/${rid}/messages`, {
        body: req.body,
        client_id: req.id,
        parent_id: thread || null,
        attachment_ids: ids,
      });
      setDrafts((d) => (d[key]?.trim() === req.body ? { ...d, [key]: "" } : d));
      setUploads((d) => ({
        ...d,
        [key]: (d[key] || []).filter((f) => !ids.includes(f.id)),
      }));
      delete requests.current[key];
    });
    setPendingSend(null);
  }
  async function upload(input: FileList | File[]) {
    if (!canWrite || busy || progress !== null) return;
    const key = context;
    controller.current = new AbortController();
    setProgress(0);
    setError("");
    try {
      for (const file of Array.from(input)) {
        const form = new FormData();
        form.append("file", file);
        const { data } = await api.post<FileInfo>(
          `${url}/conversations/${rid}/attachments`,
          form,
          {
            signal: controller.current.signal,
            onUploadProgress: (e) => {
              if (current.current === key)
                setProgress(
                  e.total ? Math.round((e.loaded / e.total) * 100) : 0,
                );
            },
          },
        );
        setUploads((v) => ({ ...v, [key]: [...(v[key] || []), data] }));
      }
    } catch (e) {
      if (current.current === key) setError(workspaceError(e));
    } finally {
      if (current.current === key) setProgress(null);
    }
  }
  async function download(f: FileInfo) {
    await action(async () => {
      const { data } = await api.get(
        `${url}/conversations/${rid}/attachments/${f.id}`,
        { responseType: "blob" },
      );
      const object = URL.createObjectURL(data),
        link = document.createElement("a");
      link.href = object;
      link.download = f.name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(object), 1000);
    });
  }
  function highlight(text: string) {
    const terms = (search || "")
      .split(/\s+/)
      .filter(Boolean)
      .map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    return !terms.length
      ? text
      : text
          .split(new RegExp(`(${terms.join("|")})`, "gi"))
          .map((part, i) =>
            new RegExp(`^(${terms.join("|")})$`, "i").test(part) ? (
              <mark key={i}>{part}</mark>
            ) : (
              part
            ),
          );
  }
  function render(m: Msg) {
    return (
      <article
        id={`chat-${m.id}`}
        key={m.id}
        data-context-record={`Message ${m.id}`}
        onContextMenu={e => { const menu = e.currentTarget.querySelector<HTMLDetailsElement>("details[data-message-actions]"); if (menu) { e.preventDefault(); e.stopPropagation(); menu.open = true; } }}
        className={target === m.id ? "target" : ""}
      >
        <header>
          <span className="ce-avatar" aria-hidden="true">{(room?.participants.find(p => p.id === m.author_id)?.email || "?").slice(0, 1).toUpperCase()}</span>
          <strong>
            {m.author_id === user?.id
              ? "You"
              : room?.participants.find((p) => p.id === m.author_id)?.email ||
                "Former participant"}
          </strong>
          <time>{instant(m.created_at).toLocaleString()}</time>
          {m.edited_at && <small>edited</small>}
          {m.author_id === user?.id && !!collaboration.data?.read_states?.filter(r=>r.user_id!==user?.id&&r.read_id>=m.id&&r.history_after<m.id).length && <small>Seen by {collaboration.data?.read_states?.filter(r=>r.user_id!==user?.id&&r.read_id>=m.id&&r.history_after<m.id).length}</small>}
        </header>
        <div><RichTextContent value={m.deleted_at ? "Message deleted" : m.body}/></div>
        {m.attachments.map((f) => (
          <ChatFile
            key={f.id}
            file={f}
            url={`${url}/conversations/${rid}/attachments/${f.id}`}
            onDownload={() => void download(f)}
          />
        ))}
        {!m.deleted_at && <MessageActions wid={wid} rid={rid} message={m} data={collaboration.data} canWrite={!!canWrite} manager={!!manager} participants={room?.participants || []} allowFollowUps={features.followUps !== false} />}
        <footer>
          {!thread && features.threads !== false && (
            <button onClick={() => select(rid, m.id)}>
              Reply in thread · {m.reply_count}
            </button>
          )}
          {m.latest_reply && <small>{richTextPlainText(m.latest_reply)}</small>}
          {canWrite && m.author_id === user?.id && !m.deleted_at && (
            <>
              <button
                onClick={() => {
                  setEditMsg(m);
                  setBody(m.body);
                  setDialog("edit");
                }}
              >
                Edit
              </button>
              <button
                onClick={() => {
                  setEditMsg(m);
                  setDialog("delete");
                }}
              >
                Delete
              </button>
            </>
          )}
        </footer>
      </article>
    );
  }
  return (
    <div className={`pms-messaging ce-workspace ${rid ? "ce-active" : ""} ${detailsOpen ? "ce-details-open" : ""}`} data-communication-module={module}>
      <header>
        <div>
          <h1>Messages</h1>
          <p>{module} · BusinessSuite Communication Engine</p>
        </div>
        <select
          aria-label="Messaging workspace"
          value={wid}
          onChange={(e) => {
            setWorkspace(Number(e.target.value));
            setParams({ workspace: e.target.value });
            setSearch(null);
          }}
        >
          {workspaces.data?.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <Link to={`/pms?workspace=${wid}`}>Workspace ↗</Link>
      </header>
      {error && <p role="alert">{error}</p>}
      {workspaces.isError && (
        <p role="alert">
          {workspaceError(workspaces.error)}{" "}
          <button onClick={() => workspaces.refetch()}>Retry</button>
        </p>
      )}
      {!wid && !workspaces.isPending && (
        <p>Join a workspace to use Messages.</p>
      )}
      {!!wid && (
        <>
          <form
            className="chat-search ce-message-search"
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(query);
            }}
          >
            <input
              aria-label="Search messages"
              placeholder="Search up to 12 words in text or filenames…"
              maxLength={200}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button>Search</button>
            <label>
              <input
                type="checkbox"
                checked={within}
                onChange={(e) => setWithin(e.target.checked)}
              />
              This conversation
            </label>
            <select
              aria-label="Search author"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
            >
              <option value="">Any author</option>
              {people.data?.map((p) => (
                <option key={p.user_id} value={p.user_id}>
                  {p.email}
                </option>
              ))}
            </select>
            <input
              aria-label="Search from date (UTC)"
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
            <input
              aria-label="Search to date (UTC)"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={hasFiles}
                onChange={(e) => setHasFiles(e.target.checked)}
              />
              Attachments
            </label>
          </form>
          <div className="chat-layout">
            <aside aria-label="Channels and direct messages">
              <h2 className="ce-inbox-title">Messages</h2>
              <input aria-label="Find conversations" placeholder="Search conversations…" value={conversationFilter} onChange={e => setConversationFilter(e.target.value)} />
              <div className="ce-inbox-filters" aria-label="Conversation filters">{[["all", "All"], ["unread", "Unread"], ["pinned", "Pinned"], ["drafts", "Drafts"], ["archived", "Archived"]].map(([key,label]) => <button key={key} aria-pressed={inboxFilter === key} onClick={() => setInboxFilter(key)}>{label}</button>)}</div>
              <button
                disabled={!inbox.data?.can_send || (features.channels === false && features.directMessages === false && features.groupChats === false)}
                onClick={() => {
                  setDialog("create");
                  setName("");
                  setDescription("");
                  setParticipants([]);
                }}
              >
                + New conversation
              </button>
              <button
                onClick={() => void action(() => api.post(`${url}/read-all`))}
              >
                Mark all read
              </button>
              {inbox.isPending && <p>Loading…</p>}
              {inbox.isError && (
                <p role="alert">
                  {workspaceError(inbox.error)}{" "}
                  <button onClick={() => inbox.refetch()}>Retry</button>
                </p>
              )}
              {["general", "channel", "dm", "group"].filter(k => k !== "dm" || features.directMessages !== false).filter(k => k !== "group" || features.groupChats !== false).filter(k => !["general", "channel"].includes(k) || features.channels !== false).map((k) => (
                <section key={k}>
                  <h3>
                    {
                      (
                        {
                          general: "Workspace chat",
                          channel: "Channels",
                          dm: "Direct messages",
                          group: "Groups",
                        } as Record<string, string>
                      )[k]
                    }
                  </h3>
                  {inbox.data?.conversations
                    .filter((r) => r.kind === k && title(r).toLowerCase().includes(conversationFilter.toLowerCase()) && (inboxFilter === "archived" ? r.archived : !r.archived) && (inboxFilter !== "unread" || r.unread > 0) && (inboxFilter !== "pinned" || r.favorite) && (inboxFilter !== "drafts" || r.has_draft || Object.keys(drafts).some(key => key.startsWith(`${scope}:${wid}:${r.id}:`) && drafts[key]?.trim())))
                    .map((r) => (
                      <button
                        key={r.id}
                        aria-current={rid === r.id ? "page" : undefined}
                        onClick={() => select(r.id)}
                      >
                        <span>
                          {r.visibility === "private" ? "Private · " : "# "}
                          {title(r)}
                          {r.archived ? " (archived)" : ""}
                          {!r.joined ? " · Join" : ""}
                          <small className="ce-conversation-preview">{r.last_message || r.description || (r.kind === "dm" ? "Direct conversation" : "Team conversation")}</small>
                        </span>
                        {r.unread > 0 && (
                          <b aria-label={`${r.unread} unread`}>{r.unread}</b>
                        )}
                      </button>
                    ))}
                </section>
              ))}
            </aside>
            <main>
              {search !== null ? (
                <section className="chat-results">
                  <header>
                    <h2>Search results</h2>
                    <button onClick={() => setSearch(null)}>
                      Close search
                    </button>
                  </header>
                  <p>
                    All words must match. Only accessible history is searched.
                  </p>
                  {results.isPending && <p>Searching…</p>}
                  {results.isError && (
                    <p role="alert">{workspaceError(results.error)}</p>
                  )}
                  {results.data?.pages
                    .flatMap((p) => p.results)
                    .map((m) => (
                      <button
                        key={m.id}
                        onClick={() =>
                          select(m.conversation_id!, m.parent_id || 0, m.id)
                        }
                      >
                        <strong>{m.conversation_name}</strong>
                        <div>{highlight(richTextPlainText(m.body).slice(0, 600))}</div>
                        {m.parent_id && (
                          <small>
                            Thread reply ·{" "}
                            {m.root_preview || `root ${m.parent_id}`}
                          </small>
                        )}
                        {m.attachments.map((a) => (
                          <small key={a.id}>{highlight(a.name)}</small>
                        ))}
                      </button>
                    ))}
                  {results.data &&
                    !results.data.pages.some((p) => p.results.length) && (
                      <p>No accessible messages match.</p>
                    )}
                  {results.hasNextPage && (
                    <button onClick={() => results.fetchNextPage()}>
                      More results
                    </button>
                  )}
                </section>
              ) : !room ? (
                <div className="ce-empty"><h2>Your team, in one place.</h2><p>Choose a channel or start a direct conversation to discuss work, share files and keep follow-ups connected.</p></div>
              ) : (
                <>
                  <header className="chat-room-header">
                    <div>
                      <h2><span className="ce-room-icon">{room.kind === "dm" ? "@" : "#"}</span>{title(room)}</h2>
                      <div><RichTextContent value={room.description}/></div>
                      <small>
                        {room.participants.length} participants · {presence.users.length} recently active ·{" "}
                        {room.archived
                          ? "Archived, read-only"
                          : room.visibility}
                      </small>
                    </div>
                    {room.joined ? (
                      <>
                        <button
                          onClick={() => {
                            setName(room.name);
                            setDescription(room.description);
                            setDialog("details");
                          }}
                        >
                          Members & details
                        </button>
                        <button
                          onClick={() =>
                            void action(() =>
                              api.put(`${url}/conversations/${rid}/mute`, {
                                muted: !room.muted,
                              }),
                            )
                          }
                        >
                          {room.muted ? "Unmute" : "Mute"}
                        </button>
                        <button
                          onClick={() =>
                            void action(() =>
                              api.put(`${url}/conversations/${rid}/read`, {
                                message_id:
                                  history.data?.pages[0]?.read_through || 0,
                              }),
                            )
                          }
                        >
                          Mark read
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() =>
                          void action(() =>
                            api.post(`${url}/conversations/${rid}/join`),
                          )
                        }
                      >
                        Join channel
                      </button>
                    )}
                  </header>
                  <div className="ce-tabs" role="tablist" aria-label="Conversation views">{["chat", ...(features.threads !== false ? ["threads"] : []), ...(features.followUps !== false ? ["followups"] : []), ...(features.files !== false ? ["files"] : []), "saved"].map(tab => <button key={tab} role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>{tab === "followups" ? "Follow-ups" : tab[0].toUpperCase() + tab.slice(1)}{tab === "followups" && collaboration.data && <small>{collaboration.data.followups.length}</small>}</button>)}<button onClick={() => setDetailsOpen(v => !v)} aria-expanded={detailsOpen}>Details</button><button className="ce-mobile-back" onClick={() => setParams({ workspace: String(wid) })}>Conversations</button></div>
                  {activeTab !== "chat" && <CollaborationDetails canWrite={!!canWrite} wid={wid} rid={rid} data={collaboration.data} error={collaboration.error} participants={room.participants} description={room.description} onJump={id => { setActiveTab("chat"); select(rid, 0, id); }} onDownload={download} messages={messages} onThread={id => select(rid,id)} view={activeTab} features={features} />}
                  {activeTab === "chat" && collaboration.data?.pins[0] && <button className="ce-pinned-banner" onClick={() => select(rid,0,collaboration.data!.pins[0].id)}><strong>Pinned message</strong><span>{richTextPlainText(collaboration.data.pins[0].body).slice(0,180)}</span></button>}
                  {(target > 0 || (history.data?.pages.length || 0) > 1) && (
                    <button onClick={() => { void qc.resetQueries({ queryKey: ["chat-history", context, target] }); select(rid, thread); }}>
                      Jump to latest
                    </button>
                  )}
                  {room.joined && (
                    <>
                      {!!thread && (
                        <div className="chat-thread">
                          <button onClick={() => select(rid)}>
                            ← Conversation
                          </button>
                          <h3>Thread</h3>
                          <blockquote>
                            <RichTextContent value={history.data?.pages[0]?.root?.body || "Original message"}/>
                          </blockquote>
                        </div>
                      )}
                      {history.isError && (
                        <p role="alert">
                          {workspaceError(history.error)}{" "}
                          <button onClick={() => history.refetch()}>
                            Retry
                          </button>
                        </p>
                      )}
                      {history.isPending && (
                        <p role="status">Loading history…</p>
                      )}
                      {history.hasNextPage && (
                        <button onClick={() => history.fetchNextPage()}>
                          Load earlier messages
                        </button>
                      )}
                      <div
                        ref={timelineRef}
                        onScroll={e=>{const el=e.currentTarget;stickToBottom.current=el.scrollHeight-el.scrollTop-el.clientHeight<100;}}
                        className="chat-timeline"
                        aria-label="Message history"
                        hidden={activeTab !== "chat"}
                      >
                        {messages.map((m, i) => (
                          <div key={m.id}>
                            {(!i ||
                              instant(m.created_at).toDateString() !==
                                instant(
                                  messages[i - 1].created_at,
                                ).toDateString()) && (
                              <div className="chat-date">
                                {instant(m.created_at).toLocaleDateString()}
                              </div>
                            )}
                            {render(m)}
                          </div>
                        ))}
                        {!messages.length && !history.isPending && (
                          <p>No messages yet.</p>
                        )}
                        {pendingSend?.context === context && !messages.some(m => m.client_id === pendingSend.client_id) && (
                          <article aria-label="Pending message">
                            <strong>You · Sending…</strong>
                            <div><RichTextContent value={pendingSend.body || "Attachments"}/></div>
                          </article>
                        )}
                      </div>
                      {presence.users.some(p => p.typing && p.id !== user?.id) && <p className="ce-typing" role="status">A teammate is typing…</p>}
                      {canWrite && activeTab === "chat" && (
                        <form
                          className="chat-composer"
                          onPaste={e => { const images = Array.from(e.clipboardData.files).filter(f => f.type.startsWith("image/")); if (features.files !== false && images.length) { e.preventDefault(); void upload(images); } }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            if(features.files !== false) void upload(e.dataTransfer.files);
                          }}
                          onSubmit={(e) => {
                            e.preventDefault();
                            void send();
                          }}
                        >
                          <RichTextField data-legacy-format="markdown"
                            aria-label={thread ? "Reply to thread" : "Message"}
                            maxLength={20000}
                            value={draft}
                            placeholder={
                              thread
                                ? "Reply to this thread…"
                                : "Write a message or drop files here…"
                            }
                            onChange={(e) => { presence.typing(); setDrafts(v => ({ ...v, [context]:e.target.value })); }}
                            onKeyDown={(e) => {
                              if (
                                e.key === "Enter" &&
                                !e.nativeEvent.isComposing &&
                                (e.ctrlKey || e.metaKey || (enterSends && !e.shiftKey))
                              ) {
                                e.preventDefault();
                                if (!busy && (draft.trim() || files.length))
                                  void send();
                              }
                            }}
                          />
                          {files.map((f) => (
                            <span className="chat-upload" key={f.id}>
                              {f.name}
                              <button
                                type="button"
                                aria-label={`Remove ${f.name}`}
                                onClick={() =>
                                  void action(async () => {
                                    await api.delete(
                                      `${url}/conversations/${rid}/attachments/${f.id}`,
                                    );
                                    setUploads((v) => ({
                                      ...v,
                                      [context]: files.filter(
                                        (a) => a.id !== f.id,
                                      ),
                                    }));
                                  })
                                }
                              >
                                ×
                              </button>
                            </span>
                          ))}
                          <div className="ce-composer-tools"><details><summary aria-label="Insert emoji">☺</summary><div>{["👍","❤️","🎉","✅","🙏","💡","🚀"].map(emoji => <button type="button" key={emoji} onClick={() => setDrafts(d => ({...d,[context]:appendRichMarkdown(d[context] || "", emoji)}))}>{emoji}</button>)}</div></details><select aria-label="Mention conversation member" value="" onChange={e => { if(e.target.value) setDrafts(d=>({...d,[context]:appendRichMarkdown(d[context] || "", "@" + e.target.value)})); }}><option value="">@ Mention</option>{room.participants.map(p=><option key={p.id} value={p.email}>{p.email}</option>)}</select></div>
                          <footer>
                            {features.files !== false && <label>
                              Attach files
                              <input
                                aria-label="Chat attachments"
                                type="file"
                                multiple
                                disabled={busy || progress !== null}
                                onChange={(e) => {
                                  if (e.target.files)
                                    void upload(Array.from(e.target.files));
                                  e.target.value = "";
                                }}
                              />
                            </label>}
                            {progress !== null && (
                              <>
                                <progress
                                  aria-label="Upload progress"
                                  max={100}
                                  value={progress}
                                />
                                <button
                                  type="button"
                                  onClick={() => controller.current?.abort()}
                                >
                                  Cancel upload
                                </button>
                              </>
                            )}
                            <button
                              disabled={
                                busy ||
                                progress !== null ||
                                (!draft.trim() && !files.length) ||
                                files.length > 10
                              }
                            >
                              {busy ? "Sending…" : "Send"}
                            </button>
                          </footer>
                          <small>
                            <label className="ce-send-setting"><input type="checkbox" checked={enterSends} onChange={e => { setEnterSends(e.target.checked); localStorage.setItem("communication-enter-sends", String(e.target.checked)); }}/>Enter sends · Shift+Enter for a new line</label>
                          </small>
                        </form>
                      )}
                    </>
                  )}
                </>
              )}
            </main>
            {room?.joined && detailsOpen && <aside className="ce-context" aria-label="Conversation details"><button className="ce-context-close" onClick={() => setDetailsOpen(false)}>Close details</button><CollaborationDetails canWrite={!!canWrite} wid={wid} rid={rid} data={collaboration.data} error={collaboration.error} participants={room.participants} description={room.description} onJump={id => select(rid,0,id)} onDownload={download} messages={messages} onThread={id => select(rid,id)} view="details" features={features} /></aside>}
          </div>
        </>
      )}
      <Dialog.Root
        open={dialog !== null}
        onOpenChange={(v) => {
          if (!v && !busy) closeDialog();
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="chat-overlay" />
          <Dialog.Content className="chat-dialog">
            <Dialog.Title>
              {dialog === "create"
                ? "New conversation"
                : dialog === "details"
                  ? "Conversation details"
                  : dialog === "edit"
                    ? "Edit message"
                    : "Delete message?"}
            </Dialog.Title>
            <Dialog.Description>
              Workspace members only. New invited group/channel members see
              messages sent after joining. Project-file permissions remain
              unchanged.
            </Dialog.Description>
            {dialog === "create" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void action(async () => {
                    const { data } = await api.post<Room>(
                      `${url}/conversations`,
                      { kind, name, description, visibility, participants },
                    );
                    if (current.current === context) {
                      closeDialog();
                      select(data.id);
                    }
                  });
                }}
              >
                <label>
                  Type
                  <select
                    value={kind}
                    onChange={(e) => setKind(e.target.value)}
                  >
                    {features.directMessages !== false && <option value="dm">One-to-one</option>}
                    {features.groupChats !== false && <option value="group">Group</option>}
                    {features.channels !== false && <option value="channel">Channel (workspace admins)</option>}
                  </select>
                </label>
                {kind !== "dm" && (
                  <>
                    <label>
                      Name
                      <input
                        value={name}
                        maxLength={120}
                        required={kind === "channel"}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </label>
                    <label>
                      Description
                      <RichTextField data-legacy-format="markdown"
                        value={description}
                        maxLength={1000}
                        onChange={(e) => setDescription(e.target.value)}
                      />
                    </label>
                  </>
                )}
                {kind === "channel" && (
                  <label>
                    Visibility
                    <select
                      value={visibility}
                      onChange={(e) => setVisibility(e.target.value)}
                    >
                      <option value="private">Private, invited members</option>
                      <option value="public">Public, workspace only</option>
                    </select>
                  </label>
                )}
                <fieldset>
                  <legend>Participants</legend>
                  {people.data
                    ?.filter(
                      (p) => p.role !== "Guest" && p.user_id !== user?.id,
                    )
                    .map((p) => (
                      <label key={p.user_id}>
                        <input
                          type="checkbox"
                          checked={participants.includes(p.user_id)}
                          onChange={(e) =>
                            setParticipants((v) =>
                              e.target.checked
                                ? [...v, p.user_id]
                                : v.filter((id) => id !== p.user_id),
                            )
                          }
                        />
                        {p.email}
                      </label>
                    ))}
                </fieldset>
                <button disabled={busy}>Create conversation</button>
              </form>
            )}
            {dialog === "details" && room && (
              <>
                <p>{room.participants.map((p) => p.email).join(", ")}</p>
                {manager && room.kind !== "dm" && (
                  <>
                    <label>
                      Name
                      <input
                        value={name}
                        maxLength={120}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </label>
                    <label>
                      Description
                      <RichTextField data-legacy-format="markdown"
                        value={description}
                        maxLength={1000}
                        onChange={(e) => setDescription(e.target.value)}
                      />
                    </label>
                    <button
                      disabled={busy || !name.trim()}
                      onClick={() =>
                        void action(() =>
                          api.put(`${url}/conversations/${rid}`, {
                            name,
                            description,
                            archived: room.archived,
                          }),
                        )
                      }
                    >
                      Save details
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          api.put(`${url}/conversations/${rid}`, {
                            name: room.name,
                            description: room.description,
                            archived: !room.archived,
                          }),
                        )
                      }
                    >
                      {room.archived ? "Unarchive" : "Archive"}
                    </button>
                    {!room.archived && (
                      <label>
                        Add participant
                        <select
                          aria-label="Add conversation participant"
                          value=""
                          onChange={(e) =>
                            e.target.value &&
                            void action(() =>
                              api.post(`${url}/conversations/${rid}/members`, {
                                user_id: Number(e.target.value),
                              }),
                            )
                          }
                        >
                          <option value="">Choose collaborator</option>
                          {people.data
                            ?.filter(
                              (p) =>
                                p.role !== "Guest" &&
                                !room.participants.some(
                                  (m) => m.id === p.user_id,
                                ),
                            )
                            .map((p) => (
                              <option key={p.user_id} value={p.user_id}>
                                {p.email}
                              </option>
                            ))}
                        </select>
                      </label>
                    )}
                    {room.participants
                      .filter((p) => p.id !== room.owner_id)
                      .map((p) => (
                        <button
                          key={p.id}
                          disabled={busy}
                          onClick={() =>
                            void action(() =>
                              api.delete(
                                `${url}/conversations/${rid}/members/${p.id}`,
                              ),
                            )
                          }
                        >
                          Remove {p.email}
                        </button>
                      ))}
                  </>
                )}
                {!["dm", "general"].includes(room.kind) &&
                  (room.owner_id !== user?.id || room.kind === "group") && (
                    <button
                      onClick={() =>
                        void action(async () => {
                          await api.delete(
                            `${url}/conversations/${rid}/members/${user?.id}`,
                          );
                          closeDialog();
                          select(0);
                        })
                      }
                    >
                      Leave conversation (group ownership transfers)
                    </button>
                  )}
                {canWrite && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      const key = context;
                      void action(async () => {
                        const { data } = await api.post<FileInfo>(
                          `${url}/conversations/${rid}/project-file`,
                          { file_id: Number(fileId) },
                        );
                        setUploads((v) => ({
                          ...v,
                          [key]: [...(v[key] || []), data],
                        }));
                        if (current.current === key) setFileId("");
                      });
                    }}
                  >
                    <label>
                      Share an existing project file
                      <select
                        aria-label="Choose project file"
                        required
                        value={fileId}
                        onChange={(e) => setFileId(e.target.value)}
                      >
                        <option value="">
                          Choose an accessible workspace file
                        </option>
                        {projectFiles.data?.pages
                          .flatMap((p) => p.items)
                          .map((f) => (
                            <option key={f.id} value={f.id}>
                              {f.name} · {Math.ceil(f.size / 1024)} KB
                            </option>
                          ))}
                      </select>
                    </label>
                    {projectFiles.isPending && <p>Loading project files…</p>}
                    {projectFiles.isError && (
                      <p role="alert">
                        {workspaceError(projectFiles.error)}{" "}
                        <button
                          type="button"
                          onClick={() => projectFiles.refetch()}
                        >
                          Retry
                        </button>
                      </p>
                    )}
                    {projectFiles.hasNextPage && (
                      <button
                        type="button"
                        onClick={() => projectFiles.fetchNextPage()}
                      >
                        More project files
                      </button>
                    )}
                    <button disabled={busy}>Attach project file</button>
                  </form>
                )}
              </>
            )}
            {dialog === "edit" && (
              <>
                <RichTextField data-legacy-format="markdown"
                  aria-label="Edit message text"
                  value={body}
                  maxLength={20000}
                  onChange={(e) => setBody(e.target.value)}
                />
                <button
                  disabled={busy || !body.trim()}
                  onClick={() =>
                    void action(async () => {
                      await api.patch(
                        `${url}/conversations/${rid}/messages/${editMsg?.id}`,
                        { body },
                      );
                      closeDialog();
                    })
                  }
                >
                  Save edit
                </button>
              </>
            )}
            {dialog === "delete" && (
              <>
                <p>
                  The message becomes a tombstone; its replies stay attached.
                  Its files become inaccessible.
                </p>
                <button
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await api.delete(
                        `${url}/conversations/${rid}/messages/${editMsg?.id}`,
                      );
                      closeDialog();
                    })
                  }
                >
                  Delete message
                </button>
              </>
            )}
            {error && <p role="alert">{error}</p>}
            <button disabled={busy} onClick={() => setDialog(null)}>
              Close
            </button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function ChatFile({
  file,
  url,
  onDownload,
}: {
  file: FileInfo;
  url: string;
  onDownload: () => void;
}) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      request.current?.abort();
    },
    [],
  );
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  return (
    <div>
      <button onClick={onDownload}>
        {file.name} · {Math.ceil(file.size / 1024)} KB ↓
      </button>
      <small>{file.mime}</small>
      {["image/png", "image/jpeg", "image/webp"].includes(file.mime) && (
        <button
          disabled={loading}
          onClick={async () => {
            if (preview) {
              setPreview("");
              return;
            }
            setLoading(true);
            setError("");
            request.current = new AbortController();
            try {
              const { data } = await api.get(url, {
                responseType: "blob",
                signal: request.current.signal,
              });
              setPreview(URL.createObjectURL(data));
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setLoading(false);
            }
          }}
        >
          {preview ? "Hide image" : "Preview image"}
        </button>
      )}
      {preview && (
        <img
          src={preview}
          alt={file.name}
          style={{
            maxWidth: "100%",
            maxHeight: 300,
            objectFit: "contain",
            display: "block",
          }}
        />
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

export default function CommunicationWorkspace(props:CommunicationWorkspaceProps) {
  return props.context ? <ContextualChat {...props}/> : <WorkspaceCore {...props}/>;
}
