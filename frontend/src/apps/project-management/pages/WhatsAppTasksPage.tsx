import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Plus,
  Search,
  ListTodo,
  UserRound,
  Users,
  Star,
  ArrowLeft,
  PanelRight,
  X,
  Send,
  Paperclip,
  CalendarDays,
  Flag,
  MessageCircle,
  ExternalLink,
  Folder,
  RefreshCw,
  Bell,
  CheckCheck,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import {
  RichTextContent,
  richTextPlainText,
} from "@/components/rich-text/LazyRichText";
import TaskThemeSwitcher from "../components/TaskThemeSwitcher";
import TaskAssignmentPanel, {
  AssignmentAvatar,
} from "../components/TaskAssignmentPanel";
import { tasksAPI, commentsAPI, filesAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";
import { MentionMarkdownTextarea, FilesTab } from "./TaskDetail";
import { workspaceError } from "./workspaceTypes";
import type { Workspace, Entry } from "./TaskWorkspacePage";
import type { PMSComment, PMSMentionUser, PMSTaskListItem } from "../types";
import "./WhatsAppTasksPage.css";
const base = "/project-management/task-workspace";
const date = (v?: string) =>
  v
    ? new Date(
        v.length === 10
          ? `${v}T12:00:00`
          : /(?:Z|[+-]\d{2}:\d{2})$/.test(v)
            ? v
            : v + "Z",
      ).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : "No due date";
const time = (v: string) =>
  new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(v) ? v : v + "Z").toLocaleTimeString(
    undefined,
    { hour: "2-digit", minute: "2-digit" },
  );
const done = (s: string) =>
  ["Done", "Completed", "Closed", "Resolved"].includes(s);
const tone = (s: string) =>
  done(s)
    ? "done"
    : s === "Blocked"
      ? "blocked"
      : s === "In Review"
        ? "review"
        : s === "In Progress"
          ? "progress"
          : "todo";
function Badge({ value }: { value: string }) {
  return (
    <span className={`wa-badge ${tone(value)}`}>
      <i />
      {value}
    </span>
  );
}
function stored<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
export default function WhatsAppTasksPage() {
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const scope = JSON.stringify([
    user?.id,
    user?.access?.companyId,
    user?.access?.grants,
  ]);
  const [search, setSearch] = useState(params.get("search") || "");
  const [debounced, setDebounced] = useState(params.get("search") || "");
  const [view, setView] = useState("all");
  const [status, setStatus] = useState("");
  const [project, setProject] = useState("");
  const [page, setPage] = useState(1);
  const starKey = `pms-task-stars:${user?.id}`;
  const [stars, setStars] = useState<number[]>(() => stored(starKey, []));
  useEffect(() => {
    setStars(stored(starKey, []));
  }, [starKey]);
  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [search]);
  const query = useQuery({
    queryKey: [
      "wa-tasks",
      scope,
      debounced,
      view,
      status,
      project,
      page,
      view === "starred" ? stars.join(",") : "",
    ],
    queryFn: () =>
      tasksAPI.listAll({
        search: debounced,
        taskIds: view === "starred" ? stars.join(",") || "0" : undefined,
        assigneeId: view === "mine" ? user?.id : undefined,
        projectId: project,
        status: status || undefined,
        page,
        pageSize: 30,
        sortBy: "updatedDate",
        sortOrder: "desc",
      }),
  });
  const id = Number(params.get("task")) || 0;
  const choose = (task: number) => {
    const next = new URLSearchParams(params);
    if (task) next.set("task", String(task));
    else next.delete("task");
    setParams(next);
  };
  const items = (query.data?.items || []).filter(
    (t) => view !== "starred" || stars.includes(t.id),
  );
  const star = (task: number) =>
    setStars((old) => {
      const next = old.includes(task)
        ? old.filter((i) => i !== task)
        : [...old, task].slice(-100);
      try {
        localStorage.setItem(starKey, JSON.stringify(next));
      } catch {
        /* browser preference only */
      }
      return next;
    });
  usePMSRealtime({
    taskId: id || undefined,
    showToast: false,
    onEvent: () => {
      void qc.invalidateQueries({ queryKey: ["wa-tasks", scope] });
    },
    onFallbackPoll: () => {
      void qc.invalidateQueries({ queryKey: ["wa-tasks", scope] });
    },
  });
  const nav = (next: string) => {
    setView(next);
    setPage(1);
  };
  return (
    <div className={`wa-app ${id ? "wa-selected" : ""}`}>
      <aside className="wa-nav">
        <Link className="wa-brand" to="/pms">
          <span>
            <Check size={24} />
          </span>
          <strong>
            Indian Servers<small>Task workspace</small>
          </strong>
        </Link>
        <Link className="wa-new" to="/pms/tasks/new">
          <Plus size={19} />
          New Task
        </Link>
        <nav aria-label="Task views">
          {[
            ["all", "All Tasks", ListTodo],
            ["mine", "My Tasks", UserRound],
            ["starred", "Starred", Star],
          ].map(([key, label, Icon]) => (
            <button
              key={String(key)}
              className={view === key ? "active" : ""}
              onClick={() => nav(String(key))}
            >
              <Icon size={18} />
              {String(label)}
              {key === "all" && <span>{query.data?.total ?? ""}</span>}
            </button>
          ))}
          <Link to="/pms/my-work">
            <Users size={18} />
            Team Tasks
          </Link>
          <Link to="/pms/my-notices">
            <Bell size={18} />
            Mentions & Updates
          </Link>
        </nav>
        <div className="wa-project-heading">
          Projects
          <Link to="/pms/projects" aria-label="All projects">
            <Plus size={17} />
          </Link>
        </div>
        <button
          className={`wa-project ${!project ? "active" : ""}`}
          onClick={() => {
            setProject("");
            setPage(1);
          }}
        >
          <Folder size={17} />
          All projects
        </button>
        <div className="wa-projects">
          {query.data?.filters.projects.map((p) => (
            <button
              key={p.id}
              className={`wa-project ${project === String(p.id) ? "active" : ""}`}
              onClick={() => {
                setProject(String(p.id));
                setPage(1);
              }}
            >
              <Folder size={17} />
              <span>{p.name}</span>
            </button>
          ))}
        </div>
        <footer>
          <Link to="/pms/recovery">
            Archived & Trash
            <ExternalLink size={14} />
          </Link>
          <div className="wa-profile">
            <AssignmentAvatar
              person={{
                id: user?.id || 0,
                name: user?.email?.split("@")[0] || "You",
              }}
            />
            <span>
              {user?.email}
              <small>Business Suite</small>
            </span>
          </div>
        </footer>
      </aside>
      <section className="wa-list" aria-label="Task conversations">
        <div className="wa-search">
          <Search size={18} />
          <input
            aria-label="Search tasks"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            aria-label="Refresh tasks"
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <div className="wa-list-heading">
          <span className="wa-project-icon">
            <CheckCheck />
          </span>
          <div>
            <h2>
              {project
                ? query.data?.filters.projects.find(
                    (p) => String(p.id) === project,
                  )?.name || "Project"
                : "Your work"}
            </h2>
            <p>{query.data?.total ?? 0} accessible tasks</p>
          </div>
        </div>
        <div className="wa-list-filters">
          <button
            className={!status ? "active" : ""}
            onClick={() => {
              setStatus("");
              setPage(1);
            }}
          >
            All
          </button>
          <select
            aria-label="Filter status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {query.data?.filters.statuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          {view === "starred" && <small>Starred on this browser</small>}
        </div>
        <div className="wa-task-scroll">
          {query.isPending && (
            <p className="wa-empty" role="status">
              Loading tasks…
            </p>
          )}
          {query.isError && (
            <div className="wa-empty" role="alert">
              {workspaceError(query.error)}
              <button onClick={() => void query.refetch()}>Retry</button>
            </div>
          )}
          {!query.isPending && !query.isError && !items.length && (
            <p className="wa-empty">No tasks match this view.</p>
          )}
          {items.map((t) => (
            <button
              key={t.id}
              className={`wa-task ${id === t.id ? "active" : ""}`}
              onClick={() => choose(t.id)}
            >
              <AssignmentAvatar
                person={{
                  id: t.assignee_user_id || 0,
                  name: t.assignee_name || "Unassigned",
                  photo_url: t.assignee_photo_url,
                }}
              />
              <div>
                <div className="wa-task-title">
                  <strong>{t.title}</strong>
                  {stars.includes(t.id) && (
                    <Star size={12} fill="currentColor" />
                  )}
                </div>
                <p>
                  {query.data?.activity?.find((a) => a.task_id === t.id)
                    ?.summary ||
                    t.project_name ||
                    "General work"}{" "}
                  · {t.assignee_name || "Unassigned"}
                </p>
                <div className="wa-task-meta">
                  <span>
                    <Flag size={12} />
                    {t.priority}
                  </span>
                  <span>
                    <CalendarDays size={12} />
                    {date(t.due_date)}
                  </span>
                </div>
                <Badge value={t.status} />
              </div>
            </button>
          ))}
        </div>
        {(query.data?.pages || 0) > 1 && (
          <div className="wa-pagination">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span>
              {page} / {query.data?.pages}
            </span>
            <button
              disabled={page >= (query.data?.pages || 1)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </section>
      <main className="wa-main">
        <div className="wa-theme-top">
          <span>
            <MessageCircle size={16} /> Conversations
          </span>
          <TaskThemeSwitcher />
        </div>
        {id ? (
          <Conversation
            key={`${scope}:${id}`}
            id={id}
            scope={scope}
            starred={stars.includes(id)}
            onStar={() => star(id)}
            onBack={() => choose(0)}
          />
        ) : (
          <div className="wa-welcome">
            <div>
              <MessageCircle size={46} />
            </div>
            <h1>Keep work in the conversation</h1>
            <p>
              Select a task to discuss ideas, share progress,
              <br />
              and keep everyone moving together.
            </p>
            <small>Your existing tasks. A fresh way to work.</small>
          </div>
        )}
      </main>
    </div>
  );
}
function Conversation({
  id,
  scope,
  starred,
  onStar,
  onBack,
}: {
  id: number;
  scope: string;
  starred: boolean;
  onStar: () => void;
  onBack: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [details, setDetails] = useState(() => window.innerWidth > 1400);
  const [tab, setTab] = useState("details");
  const [feed, setFeed] = useState("discussion");
  const [commentPage, setCommentPage] = useState(0);
  const [entryPage, setEntryPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [assign, setAssign] = useState(false);
  const draftKey = `pms-wa-draft:${scope}:${id}`;
  const [body, setBody] = useState<string>(() => stored(draftKey, ""));
  const [mentions, setMentions] = useState<PMSMentionUser[]>([]);
  const [reply, setReply] = useState<PMSComment>();
  const [kind, setKind] = useState("discussion");
  const [progress, setProgress] = useState("");
  const [followDate, setFollowDate] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploaded, setUploaded] = useState<number[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const [checkTitle, setCheckTitle] = useState("");
  const detail = useQuery({
    queryKey: ["task-workspace", id, scope],
    queryFn: () =>
      api.get<Workspace>(`${base}/tasks/${id}`).then((r) => r.data),
  });
  const data = detail.data;
  const task = data?.task;
  const comments = useQuery({
    queryKey: ["wa-comments", id, scope, commentPage],
    queryFn: () => commentsAPI.listForTask(id, commentPage * 30, 30),
    enabled: feed === "discussion",
  });
  const entries = useQuery({
    queryKey: ["wa-entries", id, scope, entryPage, feed],
    queryFn: () =>
      api
        .get<{
          items: Entry[];
          pages: number;
        }>(`${base}/tasks/${id}/entries`, {
          params: {
            page: entryPage,
            kind: feed === "followups" ? "followup" : "all",
          },
        })
        .then((r) => r.data),
    enabled: feed !== "discussion",
  });
  const attachments = useQuery({
    queryKey: ["wa-files", id, scope],
    queryFn: () => filesAPI.list({ task_id: id }),
    enabled: details && tab === "files",
  });
  const checks = useQuery({
    queryKey: ["wa-checks", id, scope],
    queryFn: () => tasksAPI.listChecklists(id),
    enabled: details,
  });
  const children = useQuery({
    queryKey: ["wa-children", id, scope],
    queryFn: () => tasksAPI.listSubtasks(id),
    enabled: details,
  });
  const history = useQuery({
    queryKey: ["wa-history", id, scope],
    queryFn: () =>
      api
        .get<{
          items: { id: number; summary: string; created_at: string }[];
        }>(`${base}/tasks/${id}/history`)
        .then((r) => r.data),
    enabled: details && tab === "activity",
  });
  useEffect(() => {
    try {
      localStorage.setItem(draftKey, JSON.stringify(body));
    } catch {
      /* draft remains in memory */
    }
  }, [draftKey, body]);
  const refresh = () => {
    void qc.invalidateQueries({
      predicate: (q) =>
        (String(q.queryKey[0]).startsWith("wa-") ||
          String(q.queryKey[0]).startsWith("task-workspace")) &&
        q.queryKey[1] === id,
    });
    void qc.invalidateQueries({ queryKey: ["wa-tasks", scope] });
  };
  usePMSRealtime({
    taskId: id,
    projectId: task?.project_id,
    showToast: false,
    onEvent: (e) => {
      if (e.taskId === id) refresh();
    },
    onFallbackPoll: refresh,
  });
  useEffect(() => {
    if (data?.unread_comments && feed === "discussion" && comments.isSuccess)
      void api.post(`${base}/tasks/${id}/read`).catch(() => {});
  }, [id, data?.unread_comments, feed, comments.isSuccess]);
  async function run(work: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      refresh();
      setNotice(message);
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    if (!data) return;
    await run(async () => {
      if (kind === "discussion")
        await commentsAPI.addToTask(id, {
          body,
          body_format: "markdown",
          parent_comment_id: reply?.id,
          mentioned_user_ids: mentions.map((p) => p.id),
        });
      else {
        const ids = [...uploaded];
        for (let i = ids.length; i < files.length; i++) {
          ids.push((await filesAPI.uploadToTask(id, files[i])).id);
          setUploaded([...ids]);
        }
        await api.post(`${base}/tasks/${id}/entries`, {
          kind,
          body,
          progress: progress === "" ? null : Number(progress),
          minutes: 0,
          follow_up_date: followDate || null,
          file_ids: ids,
          mentioned_user_ids: mentions.map((p) => p.id),
          revision: data.revision,
        });
      }
      setFeed(
        kind === "discussion"
          ? "discussion"
          : kind === "followup"
            ? "followups"
            : "updates",
      );
      setCommentPage(0);
      setEntryPage(1);
      setBody("");
      setMentions([]);
      setReply(undefined);
      setProgress("");
      setFollowDate("");
      setFiles([]);
      setUploaded([]);
    }, "Posted to task");
  }
  const openDetails = (next = "details") => {
    setDetails(true);
    setTab(next);
  };
  if (detail.isPending)
    return (
      <p className="wa-empty" role="status">
        Loading conversation…
      </p>
    );
  if (detail.isError || !data || !task)
    return (
      <div className="wa-empty" role="alert">
        {workspaceError(detail.error)}
        <button onClick={() => void detail.refetch()}>Retry</button>
      </div>
    );
  const canPost = data.can_work || data.can_manage;
  return (
    <div className={`wa-workspace ${details ? "wa-details-open" : ""}`}>
      <section className="wa-conversation">
        <header className="wa-conversation-header">
          <div className="wa-heading-row">
            <button
              className="wa-mobile-back"
              aria-label="Back to tasks"
              onClick={onBack}
            >
              <ArrowLeft />
            </button>
            <h1>{task.title}</h1>
            <button
              title="Star on this browser"
              aria-label="Star task"
              aria-pressed={starred}
              onClick={onStar}
            >
              <Star size={20} fill={starred ? "currentColor" : "none"} />
            </button>
            <button
              className="wa-details-toggle"
              onClick={() => setDetails(!details)}
              aria-expanded={details}
              aria-label="Task details"
            >
              <PanelRight size={20} />
            </button>
          </div>
          <div className="wa-heading-meta">
            <Badge value={task.status} />
            <span className="wa-priority">
              <Flag size={13} />
              {task.priority} priority
            </span>
            <span>
              <Folder size={13} />
              {data.project.name}
            </span>
            <span>
              <CalendarDays size={13} />
              {date(task.due_date)}
            </span>
          </div>
          <div className="wa-avatars">
            {data.assignees.slice(0, 5).map((p) => (
              <AssignmentAvatar key={p.id} person={p} />
            ))}
            <button onClick={() => openDetails()}>
              {data.assignees.length
                ? `${data.assignees.length} assignees`
                : "Unassigned"}
            </button>
            <Link
              to={`/pms/tasks/${id}`}
              state={{ from: `/pms/tasks?theme=whatsapp&task=${id}` }}
              title="Open full task workspace"
            >
              <ExternalLink size={15} />
              Full task
            </Link>
          </div>
        </header>
        <nav className="wa-feed-tabs" aria-label="Conversation type">
          {[
            ["discussion", "Discussion"],
            ["updates", "Updates"],
            ["followups", "Follow-ups"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={feed === key ? "active" : ""}
              onClick={() => {
                setFeed(key);
                setKind(
                  key === "discussion"
                    ? "discussion"
                    : key === "followups"
                      ? "followup"
                      : "update",
                );
                setReply(undefined);
              }}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="wa-messages" aria-label="Task messages">
          <div className="wa-conversation-start">
            {feed === "discussion"
              ? "Task discussion"
              : feed === "followups"
                ? "Follow-ups & reminders"
                : "Progress & work updates"}
          </div>
          {(feed === "discussion" ? comments.isPending : entries.isPending) && (
            <p role="status">Loading messages…</p>
          )}
          {(feed === "discussion" ? comments.isError : entries.isError) && (
            <p role="alert">
              {workspaceError(
                feed === "discussion" ? comments.error : entries.error,
              )}
            </p>
          )}
          {feed === "discussion" && (
            <>
              {commentPage > 0 && (
                <button onClick={() => setCommentPage((p) => p - 1)}>
                  Newer messages
                </button>
              )}
              {comments.data?.length === 0 && (
                <p className="wa-empty">
                  Start the conversation. Share a question or an update with
                  your team.
                </p>
              )}
              {[...(comments.data || [])]
                .sort((a, b) => a.id - b.id)
                .map((c) => (
                  <article
                    className={`wa-message ${c.author_user_id === user?.id ? "mine" : ""}`}
                    key={c.id}
                  >
                    <AssignmentAvatar
                      person={{
                        id: c.author_user_id || 0,
                        name: c.author?.name || "Collaborator",
                        photo_url: c.author?.avatar_url,
                      }}
                    />
                    <div>
                      <div className="wa-message-by">
                        <strong>{c.author?.name || "Collaborator"}</strong>
                        <time title={c.created_at}>
                          {date(c.created_at)} · {time(c.created_at)}
                        </time>
                      </div>
                      <div className="wa-bubble">
                        {c.parent_comment_id && (
                          <small className="wa-reply-ref">
                            Reply to an earlier message
                          </small>
                        )}
                        <RichTextContent value={c.body} />
                        {c.is_edited && <small>Edited</small>}
                        {c.is_resolved && <small>Resolved</small>}
                      </div>
                      <div className="wa-message-actions">
                        <button
                          onClick={() => {
                            setReply(c);
                            setKind("discussion");
                          }}
                        >
                          Reply
                        </button>
                        {[
                          ["like", "👍"],
                          ["celebrate", "🎉"],
                          ["seen", "✓"],
                        ].map(([emoji, label]) => (
                          <button
                            key={emoji}
                            disabled={busy}
                            aria-label={emoji}
                            aria-pressed={
                              c.reactions?.some(
                                (r) => r.emoji === emoji && r.mine,
                              ) || false
                            }
                            onClick={() =>
                              void run(
                                () =>
                                  api.post(`${base}/comments/${c.id}/actions`, {
                                    emoji,
                                  }),
                                "Reaction saved",
                              )
                            }
                          >
                            {label}{" "}
                            {c.reactions?.find((r) => r.emoji === emoji)
                              ?.count || ""}
                          </button>
                        ))}
                      </div>
                    </div>
                  </article>
                ))}
              {comments.data?.length === 30 && (
                <button onClick={() => setCommentPage((p) => p + 1)}>
                  Older messages
                </button>
              )}
            </>
          )}
          {feed !== "discussion" && (
            <>
              {entryPage < (entries.data?.pages || 1) && (
                <button onClick={() => setEntryPage((p) => p + 1)}>
                  Older updates
                </button>
              )}
              {entries.data?.items.length === 0 && (
                <p className="wa-empty">
                  No {feed === "followups" ? "follow-ups" : "updates"} yet.
                </p>
              )}
              {[...(entries.data?.items || [])].reverse().map((e) => (
                <article
                  className={`wa-message ${e.author.id === user?.id ? "mine" : ""}`}
                  key={e.id}
                >
                  <AssignmentAvatar person={e.author} />
                  <div>
                    <div className="wa-message-by">
                      <strong>{e.author.name}</strong>
                      <time>
                        {date(e.created_at)} · {time(e.created_at)}
                      </time>
                    </div>
                    <div className="wa-bubble">
                      <small className="wa-entry-kind">
                        {e.kind}
                        {e.resolved ? " · Resolved" : ""}
                      </small>
                      <RichTextContent value={e.body} />
                      {e.progress !== null && (
                        <div className="wa-inline-progress">
                          <progress max={100} value={e.progress} />
                          {e.progress}%
                        </div>
                      )}
                      {e.follow_up_date && (
                        <small>Follow up {date(e.follow_up_date)}</small>
                      )}
                      {e.file_ids.length > 0 && (
                        <button onClick={() => openDetails("files")}>
                          <Paperclip size={13} />
                          {e.file_ids.length} attachment(s)
                        </button>
                      )}
                    </div>
                    {e.can_resolve && !e.resolved && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () =>
                              api.patch(`${base}/entries/${e.id}`, {
                                revision: e.revision,
                                resolved: true,
                              }),
                            "Resolved",
                          )
                        }
                      >
                        Mark resolved
                      </button>
                    )}
                  </div>
                </article>
              ))}
              {entryPage > 1 && (
                <button onClick={() => setEntryPage((p) => p - 1)}>
                  Newer updates
                </button>
              )}
            </>
          )}
        </div>
        {error && (
          <div className="wa-alert" role="alert">
            {error}
            <button onClick={() => setError("")} aria-label="Dismiss error">
              <X size={15} />
            </button>
          </div>
        )}
        {notice && (
          <div className="wa-notice" role="status">
            {notice}
          </div>
        )}
        <div className="wa-composer">
          {reply && (
            <div className="wa-reply-ref">
              Replying to {reply.author?.name || "Collaborator"}
              <button
                onClick={() => setReply(undefined)}
                aria-label="Cancel reply"
              >
                <X size={14} />
              </button>
            </div>
          )}
          <div className="wa-composer-tools">
            <select
              aria-label="Message type"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setReply(undefined);
              }}
            >
              <option value="discussion">Discussion</option>
              <option value="update">Progress update</option>
              <option value="followup">Follow-up</option>
              <option value="blocker">Blocker</option>
            </select>
            {kind !== "discussion" && (
              <>
                <input
                  aria-label="Progress percent"
                  disabled={data.progress_mode !== "manual"}
                  type="number"
                  min={0}
                  max={100}
                  placeholder="Progress %"
                  value={progress}
                  onChange={(e) => setProgress(e.target.value)}
                />
                {kind === "followup" && (
                  <input
                    aria-label="Follow-up date"
                    type="date"
                    value={followDate}
                    onChange={(e) => setFollowDate(e.target.value)}
                  />
                )}
                <button
                  onClick={() => input.current?.click()}
                  disabled={busy || !canPost}
                >
                  <Paperclip size={16} />
                  Attach
                </button>
                <input
                  ref={input}
                  type="file"
                  multiple
                  hidden
                  onChange={(e) => {
                    setFiles((old) => [
                      ...old,
                      ...Array.from(e.target.files || []),
                    ]);
                    e.target.value = "";
                  }}
                />
              </>
            )}
          </div>
          {files.length > 0 && (
            <small>
              {files.map((f) => f.name).join(", ")}{" "}
              <button
                disabled={busy}
                onClick={() => {
                  setFiles([]);
                  setUploaded([]);
                }}
              >
                Clear
              </button>
            </small>
          )}
          {canPost ? (
            <>
              <MentionMarkdownTextarea
                taskId={id}
                projectId={task.project_id}
                value={body}
                onChange={setBody}
                mentions={mentions}
                onMentionsChange={setMentions}
              />
              <div className="wa-composer-bottom">
                <small>
                  Share an update, mention a teammate, keep work moving.
                </small>
                <button
                  className="wa-send"
                  aria-label="Send message"
                  disabled={
                    busy ||
                    !richTextPlainText(body).trim() ||
                    (kind === "followup" && !followDate)
                  }
                  onClick={() => void send()}
                >
                  <Send size={18} />
                  {busy ? "Sending…" : "Send"}
                </button>
              </div>
            </>
          ) : (
            <p>You can view this task. Posting requires task work access.</p>
          )}
        </div>
      </section>
      {details && (
        <aside className="wa-details" aria-label="Task details panel">
          <nav>
            {[
              ["details", "Task Details"],
              ["subtasks", "Subtasks"],
              ["files", "Files"],
              ["activity", "Activity"],
            ].map(([key, label]) => (
              <button
                key={key}
                className={tab === key ? "active" : ""}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
            <button
              aria-label="Close details"
              onClick={() => setDetails(false)}
            >
              <X size={17} />
            </button>
          </nav>
          <div className="wa-details-body">
            {tab === "details" && (
              <>
                <label>
                  Title<strong>{task.title}</strong>
                </label>
                <label>
                  Description
                  <div className="wa-description">
                    <RichTextContent
                      value={task.description || "No description yet."}
                    />
                  </div>
                </label>
                <div className="wa-detail-grid">
                  <label>
                    Status
                    <select
                      aria-label="Task status"
                      disabled={busy || !canPost || data.source_managed}
                      value={task.status}
                      onChange={(e) =>
                        void run(
                          () =>
                            api.post(`${base}/tasks/${id}/actions`, {
                              action: "status",
                              status: e.target.value,
                              version: data.version,
                            }),
                          "Status saved",
                        )
                      }
                    >
                      {[
                        "Backlog",
                        "To Do",
                        "In Progress",
                        "In Review",
                        ...(data.can_review ? ["Done"] : []),
                        "Blocked",
                        "Cancelled",
                      ].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Priority
                    <span className="wa-priority">
                      <Flag size={14} />
                      {task.priority}
                    </span>
                  </label>
                  <label>
                    Due date<span>{date(task.due_date)}</span>
                  </label>
                  <label>
                    Project<span>{data.project.name}</span>
                  </label>
                </div>
                <label>
                  Assignees
                  <div className="wa-person-list">
                    {data.assignees.map((p) => (
                      <div key={p.id}>
                        <AssignmentAvatar person={p} />
                        <span>{p.name}</span>
                      </div>
                    ))}
                    {!data.assignees.length && <span>Unassigned</span>}
                  </div>
                </label>
                <button
                  disabled={!data.can_manage}
                  onClick={() => setAssign(true)}
                >
                  <Users size={15} />
                  Manage assignment
                </button>
                <section>
                  <h3>
                    Progress <span>{data.progress}%</span>
                  </h3>
                  <progress value={data.progress} max={100} />
                  <small>
                    {data.progress_mode === "manual"
                      ? "Updated through work updates"
                      : "Calculated from checklist"}{" "}
                    · {data.minutes} minutes logged
                  </small>
                </section>
                <section>
                  <h3>Following this task</h3>
                  <p>{data.watcher_count} watcher(s)</p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void run(
                        () => api.post(`${base}/tasks/${id}/watch`),
                        "Watch preference saved",
                      )
                    }
                  >
                    {data.is_watching ? "Stop watching" : "Watch task"}
                  </button>
                </section>
                <Link
                  className="wa-edit-link"
                  to={`/pms/tasks/${id}`}
                  state={{ from: `/pms/tasks?theme=whatsapp&task=${id}` }}
                >
                  Status, review & full details
                  <ExternalLink size={14} />
                </Link>
              </>
            )}
            {tab === "subtasks" && (
              <>
                <h3>Subtasks</h3>
                {children.isPending && <p>Loading subtasks…</p>}
                {children.isError && (
                  <p role="alert">{workspaceError(children.error)}</p>
                )}
                {children.data?.map((t) => (
                  <Link
                    className="wa-subtask"
                    key={t.id}
                    to={`/pms/tasks/${t.id}`}
                  >
                    <CheckCheck size={16} />
                    <span>{t.title}</span>
                    <Badge value={t.status} />
                  </Link>
                ))}
                {!children.data?.length && !children.isPending && (
                  <p>No subtasks yet.</p>
                )}
                <Link to={`/pms/tasks/${id}`}>
                  Manage subtasks
                  <ExternalLink size={13} />
                </Link>
                <h3>Checklist</h3>
                {checks.isError && (
                  <p role="alert">{workspaceError(checks.error)}</p>
                )}
                {checks.data?.map((c) => (
                  <label key={c.id} className="wa-check">
                    <input
                      type="checkbox"
                      checked={c.is_completed}
                      disabled={busy || !canPost}
                      onChange={() =>
                        void run(
                          () =>
                            tasksAPI.updateChecklistItem(c.id, {
                              is_completed: !c.is_completed,
                            }),
                          "Checklist saved",
                        )
                      }
                    />
                    <span>{c.title}</span>
                  </label>
                ))}
                {data.can_manage && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void run(async () => {
                        await tasksAPI.addChecklistItem(id, {
                          title: checkTitle,
                        });
                        setCheckTitle("");
                      }, "Checklist item added");
                    }}
                  >
                    <input
                      aria-label="Checklist item"
                      placeholder="Add a checklist item…"
                      value={checkTitle}
                      onChange={(e) => setCheckTitle(e.target.value)}
                    />
                    <button disabled={busy || !checkTitle.trim()}>
                      <Plus size={15} />
                      Add
                    </button>
                  </form>
                )}
              </>
            )}
            {tab === "files" && (
              <>
                {attachments.isPending ? (
                  <p>Loading files…</p>
                ) : attachments.isError ? (
                  <p role="alert">{workspaceError(attachments.error)}</p>
                ) : (
                  <FilesTab
                    files={attachments.data || []}
                    canManage={data.can_manage}
                    uploading={busy}
                    dragActive={false}
                    setDragActive={() => {}}
                    error=""
                    uploadAttachments={(list) =>
                      void run(async () => {
                        for (const f of Array.from(list))
                          await filesAPI.uploadToTask(id, f);
                      }, "Files uploaded")
                    }
                    deleteAttachment={(fileId) =>
                      void run(
                        () => filesAPI.deleteAttachment(fileId.id),
                        "File removed",
                      )
                    }
                  />
                )}
              </>
            )}
            {tab === "activity" && (
              <>
                {history.isPending && <p>Loading activity…</p>}
                {history.isError && (
                  <p role="alert">{workspaceError(history.error)}</p>
                )}
                {history.data?.items.map((e) => (
                  <article className="wa-activity" key={e.id}>
                    <small>
                      {date(e.created_at)} · {time(e.created_at)}
                    </small>
                    <p>{e.summary}</p>
                  </article>
                ))}
                <Link to={`/pms/tasks/${id}?tab=history`}>
                  View full activity history
                </Link>
              </>
            )}
          </div>
        </aside>
      )}
      {assign && (
        <TaskAssignmentPanel
          tasks={[{ id, project_id: task.project_id, title: task.title }]}
          onClose={() => setAssign(false)}
          onSaved={() => {
            setAssign(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}
