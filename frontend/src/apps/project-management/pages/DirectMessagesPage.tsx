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
import { useRealtimeStore } from "../realtime";
import { workspaceError, type WorkspaceMember } from "./workspaceTypes";
import "./Messaging.css";
type FileInfo = { id: number; name: string; size: number; mime: string };
type Msg = {
  id: number;
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
const base = "/project-management/workspaces";
const instant = (value: string) =>
  new Date(/(Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
export default function DirectMessagesPage() {
  const { user } = useAuthStore(),
    qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [selectedWorkspace, setWorkspace] = useState(
    Number(params.get("workspace")) || 0,
  );
  const workspaces = useQuery({
    queryKey: ["messaging-workspaces", user?.id],
    queryFn: async () =>
      (await api.get<{ id: number; name: string; role: string }[]>(base)).data,
  });
  const wid = selectedWorkspace || workspaces.data?.[0]?.id || 0,
    rid = Number(params.get("conversation")) || 0,
    thread = Number(params.get("thread")) || 0,
    target = Number(params.get("message")) || 0,
    url = `${base}/${wid}/chat`,
    context = `${user?.id}:${wid}:${rid}:${thread}`;
  const current = useRef(context);
  current.current = context;
  const inbox = useQuery({
    queryKey: ["chat-inbox", user?.id, wid],
    enabled: !!wid,
    queryFn: async () =>
      (
        await api.get<{ conversations: Room[]; can_send: boolean }>(
          `${url}/conversations`,
        )
      ).data,
    refetchInterval: 10000,
  });
  const people = useQuery({
    queryKey: ["chat-people", user?.id, wid],
    enabled: !!wid,
    queryFn: async () =>
      (await api.get<WorkspaceMember[]>(`${base}/${wid}/members`)).data,
  });
  const room = inbox.data?.conversations.find((r) => r.id === rid),
    canWrite = !!room?.joined && !room.archived && inbox.data?.can_send;
  const history = useInfiniteQuery({
    queryKey: ["chat-history", context, target],
    enabled: !!room?.joined,
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam, signal }) =>
      (
        await api.get<History>(`${url}/conversations/${rid}/messages`, {
          signal,
          params: {
            parent_id: thread || undefined,
            before: pageParam || undefined,
            around: !pageParam ? target || undefined : undefined,
          },
        })
      ).data,
    getNextPageParam: (p) => p.before || undefined,
    refetchInterval: 10000,
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
  const draft = drafts[context] || "",
    files = uploads[context] || [],
    requests = useRef<
      Record<string, { id: string; body: string; files: string }>
    >({}),
    controller = useRef<AbortController | null>(null);
  const [pendingSend, setPendingSend] = useState<{
    context: string;
    body: string;
  } | null>(null);
  const [busy, setBusy] = useState(false),
    [progress, setProgress] = useState<number | null>(null),
    [error, setError] = useState("");
  const [dialog, setDialog] = useState<
      "create" | "details" | "edit" | "delete" | null
    >(null),
    [kind, setKind] = useState("dm"),
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
      user?.id,
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
    queryKey: ["chat-project-files", user?.id, wid],
    enabled: !!wid && dialog === "details" && !!canWrite,
    initialPageParam: null as number | null,
    queryFn: async ({ pageParam, signal }) =>
      (
        await api.get<{
          items: { id: number; name: string; size: number }[];
          before: number | null;
        }>(`${url}/project-files`, {
          signal,
          params: { before: pageParam || undefined },
        })
      ).data,
    getNextPageParam: (p) => p.before || undefined,
  });
  const event = useRealtimeStore((s) => s.events[0]);
  useEffect(() => {
    if (event?.type === "chat.invalidate") {
      void qc.invalidateQueries({ queryKey: ["chat-inbox"] });
      void qc.invalidateQueries({ queryKey: ["chat-history"] });
      void qc.invalidateQueries({ queryKey: ["chat-search"] });
    }
  }, [event, qc]);
  useEffect(() => {
    setError("");
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
    setPendingSend({ context: key, body: req.body });
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
        className={target === m.id ? "target" : ""}
      >
        <header>
          <strong>
            {m.author_id === user?.id
              ? "You"
              : room?.participants.find((p) => p.id === m.author_id)?.email ||
                "Former participant"}
          </strong>
          <time>{instant(m.created_at).toLocaleString()}</time>
          {m.edited_at && <small>edited</small>}
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
        <footer>
          {!thread && (
            <button onClick={() => select(rid, m.id)}>
              Reply in thread · {m.reply_count}
            </button>
          )}
          {m.latest_reply && <small>{m.latest_reply}</small>}
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
    <div className="pms-messaging">
      <header>
        <div>
          <h1>Messages</h1>
          <p>Channels, direct messages, and threads</p>
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
            className="chat-search"
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
              <button
                disabled={!inbox.data?.can_send}
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
              {["general", "channel", "dm", "group"].map((k) => (
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
                    .filter((r) => r.kind === k)
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
                <p>Choose a conversation.</p>
              ) : (
                <>
                  <header className="chat-room-header">
                    <div>
                      <h2>{title(room)}</h2>
                      <div><RichTextContent value={room.description}/></div>
                      <small>
                        {room.participants.length} participants ·{" "}
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
                  {target > 0 && (
                    <button onClick={() => select(rid, thread)}>
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
                            {history.data?.pages[0]?.root?.body ||
                              "Original message"}
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
                        className="chat-timeline"
                        aria-label="Message history"
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
                        {pendingSend?.context === context && (
                          <article aria-label="Pending message">
                            <strong>You · Sending…</strong>
                            <div><RichTextContent value={pendingSend.body || "Attachments"}/></div>
                          </article>
                        )}
                      </div>
                      {canWrite && (
                        <form
                          className="chat-composer"
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            void upload(e.dataTransfer.files);
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
                            onChange={(e) =>
                              setDrafts((v) => ({
                                ...v,
                                [context]: e.target.value,
                              }))
                            }
                            onKeyDown={(e) => {
                              if (
                                e.key === "Enter" &&
                                (e.ctrlKey || e.metaKey)
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
                          <footer>
                            <label>
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
                            </label>
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
                            Ctrl/⌘+Enter to send. Thread replies count as
                            conversation unread messages.
                          </small>
                        </form>
                      )}
                    </>
                  )}
                </>
              )}
            </main>
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
                    <option value="dm">One-to-one</option>
                    <option value="group">Group</option>
                    <option value="channel">Channel (workspace admins)</option>
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
