import { useEffect, useRef, useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Copy,
  Play,
  Plus,
  AlertTriangle,
  Send,
  CheckCheck,
  MessageSquare,
  ListChecks,
  Paperclip,
  History,
  FileText,
  Users,
  Clock3,
  X,
  Trash2,
  Pencil,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import {
  RichTextContent,
  richTextPlainText,
} from "@/components/rich-text/LazyRichText";
import { tasksAPI, commentsAPI, filesAPI, projectsAPI } from "../services/api";
import type {
  PMSTask,
  PMSComment,
  PMSMentionUser,
  PMSChecklistItem,
  PMSProject,
} from "../types";
import TaskAssignmentPanel, {
  AssignmentAvatar,
  type AssignmentPerson,
  type AssignmentGroup,
} from "../components/TaskAssignmentPanel";
import { FilesTab, MentionMarkdownTextarea } from "./TaskDetail";
import WorkReviewPanel from "../components/WorkReviewPanel";
import RunningTimer from "../components/RunningTimer";
import { usePMSRealtime, useRealtimeStore } from "../realtime";
import { workspaceError } from "./workspaceTypes";
import "./TaskWorkspacePage.css";

export type Entry = {
  id: number;
  kind: string;
  body: string;
  progress: number | null;
  minutes: number;
  author: AssignmentPerson;
  created_at: string;
  revision: number;
  can_edit: boolean;
  can_resolve: boolean;
  resolved: boolean;
  follow_up_date?: string;
  category?: string;
  severity?: string;
  responsible?: AssignmentPerson;
  assistance?: string;
  file_ids: number[];
};
export type Workspace = {
  unread_comments: number;
  is_watching: boolean;
  watcher_count: number;
  task: PMSTask;
  project: {
    id: number;
    name: string;
    workspace_id: number | null;
    is_general: boolean;
  };
  progress: number;
  progress_mode: string;
  revision: number;
  version: string;
  source_managed?: boolean;
  can_work: boolean;
  can_manage: boolean;
  can_review: boolean;
  assignees: AssignmentPerson[];
  groups: AssignmentGroup[];
  manager: AssignmentPerson;
  creator: AssignmentPerson;
  blockers: Entry[];
  minutes: number;
};
const base = "/project-management/task-workspace";
const tabs = [
  ["updates", "Updates & Work Logs", FileText],
  ["discussion", "Discussion", MessageSquare],
  ["followups", "Follow-ups", Clock3],
  ["checklist", "Checklist & Subtasks", ListChecks],
  ["files", "Attachments", Paperclip],
  ["history", "Activity History", History],
  ["review", "Reviews", CheckCheck],
  ["overview", "Overview", FileText],
] as const;
const stamp = (v: string) =>
  new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(v) ? v : v + "Z").toLocaleString();
const readDraft = (key: string) => {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
};
export default function TaskWorkspacePage() {
  const { taskId } = useParams();
  const id = Number(taskId);
  const qc = useQueryClient();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const contextKey = JSON.stringify([
    user?.id,
    user?.access?.companyId,
    user?.access?.grants,
  ]);
  const connected = useRealtimeStore((s) => s.connected);
  const tab = params.get("tab") || "updates";
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [assign, setAssign] = useState(false);
  const [blocker, setBlocker] = useState(false);
  const [timer, setTimer] = useState(false);
  const draftKey = `pms-task-update:${contextKey}:${id}`;
  const [body, setBody] = useState(() => readDraft(draftKey));
  const [progress, setProgress] = useState("");
  const [minutes, setMinutes] = useState("");
  const [followDate, setFollowDate] = useState("");
  const [category, setCategory] = useState("Other");
  const [severity, setSeverity] = useState("Medium");
  const [responsible, setResponsible] = useState("");
  const [assistance, setAssistance] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [mentions, setMentions] = useState<PMSMentionUser[]>([]);
  const [editing, setEditing] = useState<Entry>();
  const [feedback, setFeedback] = useState("");
  const composer = useRef<HTMLDivElement>(null);
  const [comment, setComment] = useState("");
  const [reply, setReply] = useState<PMSComment>();
  const [editingComment, setEditingComment] = useState<PMSComment>();
  const [commentMentions, setCommentMentions] = useState<PMSMentionUser[]>([]);
  const [checkTitle, setCheckTitle] = useState("");
  const detail = useQuery({
    queryKey: ["task-workspace", id, contextKey],
    queryFn: () =>
      api.get<Workspace>(`${base}/tasks/${id}`).then((r) => r.data),
    enabled: !!id,
  });
  const data = detail.data;
  const task = data?.task;
  const updates = useQuery({
    queryKey: ["task-workspace-entries", id, page, tab, contextKey],
    queryFn: () =>
      api
        .get<{
          items: Entry[];
          pages: number;
          total: number;
        }>(`${base}/tasks/${id}/entries`, {
          params: { page, kind: tab === "followups" ? "followup" : "all" },
        })
        .then((r) => r.data),
    enabled:
      !!data && (tab === "updates" || tab === "review" || tab === "followups"),
  });
  const comments = useQuery({
    queryKey: ["task-workspace-comments", id, page, contextKey],
    queryFn: () => commentsAPI.listForTask(id, (page - 1) * 30, 30),
    enabled: !!data && tab === "discussion",
  });
  useEffect(() => {
    if (tab === "discussion" && comments.data && data?.unread_comments)
      void api
        .post(`${base}/tasks/${id}/read`)
        .then(() =>
          qc.invalidateQueries({
            queryKey: ["task-workspace", id, contextKey],
          }),
        )
        .catch((e) => setError(workspaceError(e)));
  }, [tab, comments.data, data?.unread_comments, id, contextKey, qc]);
  const checks = useQuery({
    queryKey: ["task-workspace-checks", id, contextKey],
    queryFn: () => tasksAPI.listChecklists(id),
    enabled: !!data && tab === "checklist",
  });
  const children = useQuery({
    queryKey: ["task-workspace-children", id, contextKey],
    queryFn: () => tasksAPI.listSubtasks(id),
    enabled: !!data && tab === "checklist",
  });
  const attachments = useQuery({
    queryKey: ["task-workspace-files", id, contextKey],
    queryFn: () => tasksAPI.listAttachments(id),
    enabled: !!data && (tab === "files" || tab === "updates"),
  });
  const history = useQuery({
    queryKey: ["task-workspace-history", id, page, contextKey],
    queryFn: () =>
      api
        .get<{
          items: {
            id: number;
            summary: string;
            actor: AssignmentPerson;
            created_at: string;
          }[];
          pages: number;
        }>(`${base}/tasks/${id}/history`, { params: { page } })
        .then((r) => r.data),
    enabled: !!data && tab === "history",
  });
  const project = useQuery({
    queryKey: ["task-workspace-project", task?.project_id, contextKey],
    queryFn: () => projectsAPI.get(task!.project_id),
    enabled: !!task && timer,
  });
  const refresh = () => {
    void qc.invalidateQueries({
      predicate: (q) =>
        String(q.queryKey[0]).startsWith("task-workspace") &&
        q.queryKey[1] === id,
    });
  };
  usePMSRealtime({
    taskId: id,
    projectId: task?.project_id,
    onEvent: (e) => {
      if (e.taskId === id) refresh();
    },
    showToast: false,
  });
  useEffect(() => {
    setBody(readDraft(draftKey));
    setEditing(undefined);
    setFiles([]);
    setComment("");
    setReply(undefined);
    setEditingComment(undefined);
    setCommentMentions([]);
    setFeedback("");
    setResponsible("");
    setFollowDate("");
    setBlocker(false);
    setAssign(false);
    setPage(1);
  }, [draftKey]);
  useEffect(() => {
    if (!editing) {
      const timer = setTimeout(() => {
        try {
          if (body) localStorage.setItem(draftKey, body);
          else localStorage.removeItem(draftKey);
        } catch {
          /* Browser storage unavailable */
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [body, draftKey, editing]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => {
      if (files.length || editing) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [files, editing]);
  async function run(work: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    try {
      await work();
      setNotice(message);
      refresh();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  async function action(action: string) {
    if (!data) return;
    await run(
      () =>
        api.post(`${base}/tasks/${id}/actions`, {
          action,
          version: data.version,
          feedback,
          progress_mode:
            data.progress_mode === "manual" ? "checklist" : "manual",
        }),
      "Task updated",
    );
  }
  function chooseTab(next: string) {
    setPage(1);
    setParams({ tab: next }, { replace: true, state: location.state });
  }
  async function postUpdate() {
    if (!data) return;
    await run(async () => {
      if (editing) {
        await api.patch(`${base}/entries/${editing.id}`, {
          revision: editing.revision,
          body,
        });
      } else {
        const uploaded = [];
        for (const file of files)
          uploaded.push((await filesAPI.uploadToTask(id, file)).id);
        await api.post(`${base}/tasks/${id}/entries`, {
          kind:
            tab === "followups" ? "followup" : blocker ? "blocker" : "update",
          follow_up_date: tab === "followups" ? followDate || null : null,
          body,
          progress: progress === "" ? null : Number(progress),
          minutes: Number(minutes) || 0,
          category,
          severity,
          responsible_user_id: Number(responsible) || null,
          assistance,
          file_ids: uploaded,
          mentioned_user_ids: mentions.map((p) => p.id),
          revision: data.revision,
        });
      }
      setBody("");
      setEditing(undefined);
      setFiles([]);
      setMinutes("");
      setProgress("");
      setBlocker(false);
      setMentions([]);
      try {
        localStorage.removeItem(draftKey);
      } catch {
        /* storage unavailable */
      }
    }, "Update posted");
  }
  async function upload(list: FileList | File[]) {
    await run(async () => {
      for (const f of Array.from(list)) await filesAPI.uploadToTask(id, f);
    }, "Attachments uploaded");
  }
  const back = (location.state as { from?: string } | null)?.from;
  const backTo =
    back?.startsWith("/pms/") && !back.startsWith("//") ? back : "/pms/tasks";
  if (detail.isLoading)
    return (
      <div className="tw-loading" role="status">
        Loading task workspace…
      </div>
    );
  if (detail.error || !data || !task)
    return (
      <div role="alert" className="tw-error">
        {detail.error ? workspaceError(detail.error) : "Task unavailable"}
        <button onClick={() => void detail.refetch()}>Retry</button>
      </div>
    );
  const renderEntry = (entry: Entry) => (
    <article className={`tw-entry ${entry.kind}`} key={entry.id}>
      <AssignmentAvatar person={entry.author} />
      <div>
        <header>
          <strong>{entry.author.name}</strong>
          <time>{stamp(entry.created_at)}</time>
          <span className="tw-tag">
            {entry.kind}
            {entry.kind === "blocker"
              ? entry.resolved
                ? " · Resolved"
                : " · Open"
              : ""}
          </span>
          {entry.progress !== null && (
            <span className="tw-tag">{entry.progress}%</span>
          )}
          {entry.minutes > 0 && <small>{entry.minutes} minutes logged</small>}
        </header>
        <RichTextContent value={entry.body} />
        {entry.kind === "followup" && (
          <p className="tw-follow-date">
            Follow up {entry.follow_up_date} ·{" "}
            {entry.responsible?.name || "Task assignees"} ·{" "}
            {entry.resolved ? "Completed" : "Pending"}
          </p>
        )}
        {entry.kind === "blocker" && (
          <p className="tw-muted">
            {entry.category} · {entry.severity} ·{" "}
            {entry.responsible?.name || "No responsible person selected"}
            {entry.assistance ? ` · ${entry.assistance}` : ""}
          </p>
        )}
        {!!entry.file_ids.length && (
          <div className="tw-file-links">
            {entry.file_ids.map((fileId) => (
              <button
                key={fileId}
                onClick={() => {
                  chooseTab("files");
                }}
              >
                Attachment:{" "}
                {attachments.data?.find((f) => f.id === fileId)
                  ?.original_name || "View task files"}
              </button>
            ))}
          </div>
        )}
        {entry.can_edit && entry.kind !== "review" && (
          <footer>
            <button
              disabled={busy}
              onClick={() => {
                setEditing(entry);
                setBody(entry.body);
                chooseTab("updates");
                composer.current?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              <Pencil size={13} /> Edit
            </button>
            {entry.kind === "blocker" || entry.kind === "followup" ? (
              <button
                disabled={busy}
                onClick={() =>
                  void run(
                    () =>
                      api.patch(`${base}/entries/${entry.id}`, {
                        revision: entry.revision,
                        resolved: !entry.resolved,
                      }),
                    entry.resolved ? "Blocker reopened" : "Blocker resolved",
                  )
                }
              >
                {entry.resolved
                  ? "Reopen"
                  : entry.kind === "followup"
                    ? "Mark follow-up done"
                    : "Resolve blocker"}
              </button>
            ) : null}
            <button
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "Delete this update? Logged time and audit history are retained.",
                  )
                )
                  void run(
                    () =>
                      api.patch(`${base}/entries/${entry.id}`, {
                        revision: entry.revision,
                        delete: true,
                      }),
                    "Update removed",
                  );
              }}
            >
              <Trash2 size={13} /> Delete
            </button>
          </footer>
        )}
        {entry.can_resolve &&
          !entry.can_edit &&
          ["blocker", "followup"].includes(entry.kind) && (
            <button
              disabled={busy}
              onClick={() =>
                void run(
                  () =>
                    api.patch(`${base}/entries/${entry.id}`, {
                      revision: entry.revision,
                      resolved: !entry.resolved,
                    }),
                  "Follow-up updated",
                )
              }
            >
              {entry.resolved ? "Reopen" : "Mark done"}
            </button>
          )}
      </div>
    </article>
  );
  return (
    <main className="tw-page">
      <div className="tw-topline">
        <Link to={backTo}>
          <ArrowLeft size={15} /> Back to tasks
        </Link>
        <span>
          {connected ? "Live updates connected" : "Live updates reconnecting"}
        </span>
      </div>
      <header className="tw-title">
        <div>
          <small>
            {data.project.is_general ? "Workspace tasks" : data.project.name} /{" "}
            {task.task_key}
          </small>
          <h1 className="sr-only">{task.title}</h1>
          <input
            aria-label="Task title"
            defaultValue={task.title}
            key={`${id}:${task.title}`}
            disabled={!data.can_manage || busy}
            onBlur={(e) => {
              if (e.target.value.trim() && e.target.value !== task.title)
                void run(
                  () => tasksAPI.update(id, { title: e.target.value.trim() }),
                  "Title saved",
                );
            }}
          />
          <div className="tw-heading-tags">
            <span
              className={`tw-tag tw-priority-${task.priority.toLowerCase()}`}
            >
              {task.priority} priority
            </span>
            <span className="tw-tag">{task.work_type}</span>
            {data.groups.map((g) => (
              <span className="tw-tag" key={(g.kind || "group") + String(g.id)}>
                {g.name}
              </span>
            ))}
          </div>
        </div>
        <div className="tw-buttons">
          <button
            onClick={() =>
              void navigator.clipboard
                .writeText(window.location.origin + `/pms/tasks/${id}`)
                .then(() => setNotice("Task link copied"))
                .catch(() =>
                  setError("Clipboard unavailable. Copy this page's address."),
                )
            }
          >
            <Copy size={15} />
            {task.task_key}
          </button>
          <Link to={`/pms/tasks/${id}/edit`}>Edit details</Link>
        </div>
      </header>
      {error && (
        <p role="alert" className="tw-error">
          {error}
          <button
            onClick={() => {
              setError("");
              refresh();
            }}
          >
            Refresh
          </button>
        </p>
      )}
      {notice && (
        <p role="status" className="tw-notice">
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={14} />
          </button>
        </p>
      )}
      <div className="tw-facts">
        <div>
          <small>Assignees</small>
          <button disabled={!data.can_manage} onClick={() => setAssign(true)}>
            {data.assignees.slice(0, 3).map((p) => (
              <AssignmentAvatar key={p.id} person={p} />
            ))}
            {data.assignees.length
              ? data.assignees
                  .slice(0, 2)
                  .map((p) => p.name)
                  .join(", ")
              : "Assign people"}
            {data.assignees.length > 2 ? ` +${data.assignees.length - 2}` : ""}
          </button>
        </div>
        <div>
          <small>{data.project.is_general ? "Location" : "Project"}</small>
          <strong>
            {data.project.is_general ? "General tasks" : data.project.name}
          </strong>
        </div>
        <div>
          <small>Due date</small>
          <strong>{task.due_date || "No due date"}</strong>
        </div>
        <div>
          <small>Time logged</small>
          <strong>
            {Math.floor(data.minutes / 60)}h {data.minutes % 60}m
          </strong>
        </div>
        <div>
          <small>Status</small>
          <strong>{task.status}</strong>
        </div>
      </div>
      <div className="tw-actionbar">
        <div className="tw-progress">
          <span>Progress</span>
          <progress max={100} value={data.progress} />
          <strong>{data.progress}%</strong>
        </div>
        <div className="tw-buttons">
          <button
            disabled={
              !data.can_work ||
              busy ||
              task.status === "In Progress" ||
              task.status === "Done"
            }
            onClick={() => void action("start")}
          >
            <Play size={15} /> Start Work
          </button>
          <button
            className="tw-primary"
            onClick={() => {
              chooseTab("updates");
              setBlocker(false);
              composer.current?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            <Plus size={16} /> Add Update
          </button>
          <button
            disabled={!data.can_work}
            onClick={() => {
              chooseTab("updates");
              setBlocker(true);
              setEditing(undefined);
            }}
          >
            <AlertTriangle size={15} /> Report Blocker
          </button>
          <button
            disabled={!data.can_work}
            onClick={() => {
              chooseTab("followups");
              setBlocker(false);
              setEditing(undefined);
            }}
          >
            <Clock3 size={15} /> Add Follow-up
          </button>
          <button
            className="tw-submit"
            disabled={
              !data.can_work ||
              busy ||
              task.status === "In Review" ||
              task.status === "Done" ||
              !!data.blockers.length
            }
            onClick={() => void action("submit")}
          >
            <Send size={15} /> Submit for Review
          </button>
        </div>
      </div>
      {!!data.blockers.length && (
        <section className="tw-blockers">
          <strong>
            <AlertTriangle size={16} /> {data.blockers.length} unresolved
            blocker{data.blockers.length > 1 ? "s" : ""}
          </strong>
          {data.blockers.map((b) => (
            <button
              key={b.id}
              onClick={() => {
                chooseTab("updates");
                setPage(1);
              }}
            >
              {richTextPlainText(b.body).slice(0, 160)} · {b.severity}
            </button>
          ))}
        </section>
      )}
      <div className="tw-layout">
        <section className="tw-main">
          <nav className="tw-tabs" aria-label="Task workspace sections">
            {tabs.map(([key, label, Icon]) => (
              <button
                key={key}
                aria-pressed={tab === key}
                onClick={() => chooseTab(key)}
              >
                <Icon size={15} />
                {label}
                {key === "discussion" && data.unread_comments > 0 && (
                  <span className="tw-unread">{data.unread_comments}</span>
                )}
              </button>
            ))}
          </nav>
          {(tab === "updates" || tab === "followups") && (
            <>
              <section className="tw-box" ref={composer}>
                <h2>
                  {editing
                    ? "Edit update"
                    : blocker
                      ? "Report a blocker"
                      : tab === "followups"
                        ? "Schedule a follow-up"
                        : "Progress Updates"}
                </h2>
                <p className="tw-muted">
                  Share accomplishments, pending work and next steps. Draft text
                  saves on this browser.
                </p>
                <fieldset disabled={busy || !data.can_work}>
                  <div className="tw-template">
                    <label>
                      Template{" "}
                      <select
                        aria-label="Update template"
                        defaultValue=""
                        onChange={(e) => {
                          if (e.target.value)
                            setBody(
                              e.target.value === "qa"
                                ? "Tested:\nExpected:\nActual:\nEvidence:\nNext steps:"
                                : "Accomplished:\nPending:\nIssues:\nNext steps:",
                            );
                        }}
                      >
                        <option value="">Blank update</option>
                        <option value="daily">Daily work note</option>
                        <option value="qa">QA test report</option>
                      </select>
                    </label>
                  </div>
                  <MentionMarkdownTextarea
                    taskId={id}
                    projectId={task.project_id}
                    value={body}
                    onChange={setBody}
                    mentions={mentions}
                    onMentionsChange={setMentions}
                  />
                  {!editing && (
                    <div className="tw-composer-fields">
                      <label>
                        Progress %
                        <input
                          aria-label="Update progress"
                          disabled={data.progress_mode === "checklist"}
                          type="number"
                          min={0}
                          max={100}
                          value={progress}
                          onChange={(e) => setProgress(e.target.value)}
                        />
                      </label>
                      <label>
                        Time spent (minutes)
                        <input
                          aria-label="Update minutes"
                          type="number"
                          min={0}
                          max={1440}
                          value={minutes}
                          onChange={(e) => setMinutes(e.target.value)}
                        />
                      </label>
                      <label className="tw-upload">
                        <Paperclip size={14} /> Attach files
                        <input
                          aria-label="Attach update files"
                          multiple
                          type="file"
                          onChange={(e) =>
                            setFiles(Array.from(e.target.files || []))
                          }
                        />
                      </label>
                    </div>
                  )}
                  {(blocker || tab === "followups") && !editing && (
                    <div className="tw-blocker-fields">
                      {tab === "followups" && (
                        <label>
                          Follow-up date
                          <input
                            aria-label="Follow-up date"
                            required
                            type="date"
                            value={followDate}
                            onChange={(e) => setFollowDate(e.target.value)}
                          />
                        </label>
                      )}
                      <label>
                        Category
                        <select
                          value={category}
                          onChange={(e) => setCategory(e.target.value)}
                        >
                          {[
                            "Other",
                            "Technical",
                            "Access",
                            "Dependency",
                            "Requirements",
                          ].map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Severity
                        <select
                          value={severity}
                          onChange={(e) => setSeverity(e.target.value)}
                        >
                          {["Low", "Medium", "High", "Critical"].map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Responsible person
                        <select
                          aria-label="Blocker responsible person"
                          value={responsible}
                          onChange={(e) => setResponsible(e.target.value)}
                        >
                          <option value="">Choose person</option>
                          {[
                            ...new Map(
                              [
                                ...data.assignees,
                                ...(data.manager.id ? [data.manager] : []),
                              ].map((p) => [p.id, p]),
                            ).values(),
                          ].map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Assistance required
                        <input
                          value={assistance}
                          maxLength={4000}
                          onChange={(e) => setAssistance(e.target.value)}
                        />
                      </label>
                    </div>
                  )}
                  {!!files.length && (
                    <div className="tw-file-links">
                      {files.map((file, index) => (
                        <button
                          key={index}
                          onClick={() =>
                            setFiles((fs) => fs.filter((_, i) => i !== index))
                          }
                        >
                          {file.name}
                          <X size={12} />
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="tw-buttons">
                    {editing && (
                      <button
                        onClick={() => {
                          setEditing(undefined);
                          setBody(readDraft(draftKey));
                        }}
                      >
                        Cancel edit
                      </button>
                    )}
                    <button
                      className="tw-primary"
                      disabled={!richTextPlainText(body).trim() || busy}
                      onClick={() => void postUpdate()}
                    >
                      {busy
                        ? "Saving…"
                        : editing
                          ? "Save update"
                          : blocker
                            ? "Report Blocker"
                            : tab === "followups"
                              ? "Schedule Follow-up"
                              : "Post Update"}
                    </button>
                  </div>
                </fieldset>
              </section>
              {updates.error && (
                <p role="alert">{workspaceError(updates.error)}</p>
              )}
              {updates.isLoading && <p role="status">Loading updates…</p>}
              {updates.data?.items.map(renderEntry)}
              {updates.data && !updates.data.items.length && (
                <p className="tw-empty">
                  No updates yet. Share the first progress note.
                </p>
              )}
            </>
          )}
          {tab === "overview" && (
            <section className="tw-box">
              <h2>Overview</h2>
              <RichTextContent
                value={task.description || "No description yet."}
              />
              <Link to={`/pms/tasks/${id}/edit`}>
                Edit description, dates and task details
              </Link>
              <p>Created by {data.creator.name}</p>
              {task.parent_task_id && (
                <Link to={`/pms/tasks/${task.parent_task_id}`}>
                  Open parent task
                </Link>
              )}
            </section>
          )}
          {tab === "discussion" && (
            <section className="tw-box">
              <h2>Discussion</h2>
              {reply && (
                <p>
                  Replying to {reply.author?.name || "comment"}
                  <button onClick={() => setReply(undefined)}>
                    Cancel reply
                  </button>
                </p>
              )}
              <MentionMarkdownTextarea
                taskId={id}
                projectId={task.project_id}
                value={comment}
                onChange={setComment}
                mentions={commentMentions}
                onMentionsChange={setCommentMentions}
              />
              <button
                className="tw-primary"
                disabled={busy || !richTextPlainText(comment).trim()}
                onClick={() =>
                  void run(async () => {
                    if (editingComment)
                      await commentsAPI.update(editingComment.id, {
                        body: comment,
                        mentioned_user_ids: commentMentions.map((p) => p.id),
                      });
                    else
                      await commentsAPI.addToTask(id, {
                        body: comment,
                        body_format: "markdown",
                        parent_comment_id: reply?.id,
                        mentioned_user_ids: commentMentions.map((p) => p.id),
                      });
                    setComment("");
                    setEditingComment(undefined);
                    setReply(undefined);
                    setCommentMentions([]);
                  }, "Comment posted")
                }
              >
                {editingComment ? "Save comment" : "Post comment"}
              </button>
              {editingComment && (
                <button
                  onClick={() => {
                    setEditingComment(undefined);
                    setComment("");
                  }}
                >
                  Cancel edit
                </button>
              )}
              {comments.error && (
                <p role="alert">{workspaceError(comments.error)}</p>
              )}
              {comments.data?.map((c) => (
                <article
                  className={`tw-comment ${c.parent_comment_id ? "reply" : ""}`}
                  key={c.id}
                >
                  <strong>{c.author?.name || "Collaborator"}</strong>
                  <time>{stamp(c.created_at)}</time>
                  {c.parent_comment_id && (
                    <small>
                      Reply to{" "}
                      {comments.data.find((p) => p.id === c.parent_comment_id)
                        ?.author?.name || "earlier comment"}
                    </small>
                  )}
                  <RichTextContent value={c.body} />
                  <button onClick={() => setReply(c)}>Reply</button>
                  <div className="tw-reactions">
                    {["like", "celebrate", "seen"].map((reaction) => (
                      <button
                        key={reaction}
                        aria-pressed={
                          c.reactions?.find((r) => r.emoji === reaction)
                            ?.mine || false
                        }
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () =>
                              api.post(`${base}/comments/${c.id}/actions`, {
                                emoji: reaction,
                              }),
                            "Reaction updated",
                          )
                        }
                      >
                        {reaction === "like"
                          ? "Like"
                          : reaction === "celebrate"
                            ? "Celebrate"
                            : "Seen"}{" "}
                        {c.reactions?.find((r) => r.emoji === reaction)
                          ?.count || ""}
                      </button>
                    ))}
                    {(c.author_user_id === user?.id || data.can_review) && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () =>
                              api.post(`${base}/comments/${c.id}/actions`, {
                                resolved: !c.is_resolved,
                              }),
                            "Discussion updated",
                          )
                        }
                      >
                        {c.is_resolved
                          ? "Reopen discussion"
                          : "Resolve discussion"}
                      </button>
                    )}
                    {c.is_resolved && <span className="tw-tag">Resolved</span>}
                  </div>
                  {c.author_user_id === user?.id && (
                    <button
                      onClick={() => {
                        setEditingComment(c);
                        setComment(c.body);
                        setReply(undefined);
                      }}
                    >
                      Edit
                    </button>
                  )}
                  {(c.author_user_id === user?.id || data.can_review) && (
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (window.confirm("Delete comment?"))
                          void run(
                            () => commentsAPI.delete(c.id),
                            "Comment deleted",
                          );
                      }}
                    >
                      Delete
                    </button>
                  )}
                </article>
              ))}
              {comments.data && !comments.data.length && (
                <p className="tw-empty">
                  Start a discussion with your collaborators.
                </p>
              )}
            </section>
          )}
          {tab === "checklist" && (
            <section className="tw-box">
              <h2>Checklist & Subtasks</h2>
              <div className="tw-buttons">
                <input
                  aria-label="New checklist item"
                  value={checkTitle}
                  maxLength={220}
                  onChange={(e) => setCheckTitle(e.target.value)}
                  placeholder="Add a checklist item…"
                />
                <button
                  disabled={!data.can_manage || busy || !checkTitle.trim()}
                  onClick={() =>
                    void run(async () => {
                      await tasksAPI.addChecklistItem(id, {
                        title: checkTitle.trim(),
                      });
                      setCheckTitle("");
                    }, "Checklist item added")
                  }
                >
                  <Plus size={15} /> Add
                </button>
              </div>
              {checks.data?.map((c: PMSChecklistItem, index) => (
                <div className="tw-check" key={c.id}>
                  <input
                    aria-label={`Complete ${c.title}`}
                    type="checkbox"
                    checked={c.is_completed}
                    disabled={!data.can_manage || busy}
                    onChange={(e) =>
                      void run(
                        () =>
                          tasksAPI.updateChecklistItem(c.id, {
                            is_completed: e.target.checked,
                          }),
                        "Checklist saved",
                      )
                    }
                  />
                  <input
                    aria-label={`Checklist title ${c.id}`}
                    defaultValue={c.title}
                    key={c.title}
                    disabled={!data.can_manage || busy}
                    onBlur={(e) => {
                      if (e.target.value.trim() && e.target.value !== c.title)
                        void run(
                          () =>
                            tasksAPI.updateChecklistItem(c.id, {
                              title: e.target.value.trim(),
                            }),
                          "Checklist saved",
                        );
                    }}
                  />
                  <button
                    aria-label={`Move ${c.title} up`}
                    disabled={!index || busy || !data.can_manage}
                    onClick={() => {
                      const ids = checks.data!.map((row) => row.id);
                      [ids[index - 1], ids[index]] = [
                        ids[index],
                        ids[index - 1],
                      ];
                      void run(
                        () => tasksAPI.reorderChecklist(id, ids),
                        "Checklist reordered",
                      );
                    }}
                  >
                    ↑
                  </button>
                  <button
                    aria-label={`Delete ${c.title}`}
                    disabled={busy || !data.can_manage}
                    onClick={() =>
                      void run(
                        () => tasksAPI.deleteChecklistItem(c.id),
                        "Checklist item deleted",
                      )
                    }
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              {checks.error && (
                <p role="alert">{workspaceError(checks.error)}</p>
              )}
              <h3>Subtasks</h3>
              {children.data?.map((c) => (
                <Link
                  className="tw-subtask"
                  key={c.id}
                  to={`/pms/tasks/${c.id}`}
                >
                  <span>{c.title}</span>
                  <span>{c.status}</span>
                </Link>
              ))}
              {data.can_manage && (
                <Link
                  className="tw-link-button"
                  to={`/pms/tasks/new?projectId=${task.project_id}&parentTaskId=${id}&workType=Sub-task`}
                >
                  <Plus size={15} /> Create subtask
                </Link>
              )}
            </section>
          )}
          {tab === "files" && (
            <section className="tw-box">
              <h2>Attachments & Evidence</h2>
              {attachments.error && (
                <p role="alert">{workspaceError(attachments.error)}</p>
              )}
              <FilesTab
                canManage={data.can_manage}
                files={attachments.data || []}
                uploading={busy}
                dragActive={false}
                setDragActive={() => {}}
                error={error || null}
                uploadAttachments={(list) => {
                  if (data.can_manage) void upload(list);
                  else setError("Your role does not allow uploads");
                }}
                deleteAttachment={(file) => {
                  if (window.confirm("Delete attachment?"))
                    void run(
                      () => filesAPI.deleteAttachment(file.id),
                      "Attachment deleted",
                    );
                }}
              />
            </section>
          )}
          {tab === "history" && (
            <section className="tw-box">
              <h2>Activity History</h2>
              {history.error && (
                <p role="alert">{workspaceError(history.error)}</p>
              )}
              {history.data?.items.map((a) => (
                <article className="tw-history" key={a.id}>
                  <AssignmentAvatar person={a.actor} />
                  <div>
                    <strong>{a.summary}</strong>
                    <small>
                      {a.actor.name} · {stamp(a.created_at)}
                    </small>
                  </div>
                </article>
              ))}
            </section>
          )}
          {tab === "review" && (
            <section className="tw-box">
              <h2>Review & Approval</h2>
              <p>
                Current status: {task.status}. Open blockers and required
                completion checks must be resolved.
              </p>
              {data.can_review && task.status === "In Review" && (
                <>
                  <label>
                    Review feedback
                    <textarea
                      aria-label="Review feedback"
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                    />
                  </label>
                  <div className="tw-buttons">
                    <button
                      className="tw-submit"
                      disabled={busy}
                      onClick={() => void action("approve")}
                    >
                      Approve & complete
                    </button>
                    <button
                      disabled={busy || !feedback.trim()}
                      onClick={() => void action("rework")}
                    >
                      Request rework
                    </button>
                  </div>
                </>
              )}
              {updates.data?.items
                .filter((entry) => entry.kind === "review")
                .map(renderEntry)}
              {data.source_managed && (
                <WorkReviewPanel taskId={id} onReviewed={refresh} />
              )}
            </section>
          )}
          {timer && (
            <section className="tw-box">
              <button onClick={() => setTimer(false)}>Hide timer</button>
              <RunningTimer
                projects={project.data ? [project.data as PMSProject] : []}
                fixedTask={task}
                onSaved={refresh}
              />
            </section>
          )}
          {(tab === "updates" ||
            tab === "history" ||
            tab === "followups" ||
            tab === "discussion") && (
            <div className="tw-pager">
              <button
                aria-label="Previous history page"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft size={16} />
              </button>
              <span>Page {page}</span>
              <button
                aria-label="Next history page"
                disabled={
                  page >=
                  (tab === "discussion"
                    ? comments.data?.length === 30
                      ? page + 1
                      : page
                    : tab === "history"
                      ? history.data?.pages || 1
                      : updates.data?.pages || 1)
                }
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </section>
        <aside className="tw-sidebar">
          <section className="tw-box">
            <h2>Task Status & Actions</h2>
            <select
              className="tw-status-select"
              aria-label="Task status"
              value={task.status}
              disabled={!data.can_work || busy}
              onChange={(e) =>
                void run(
                  () =>
                    api.post(`${base}/tasks/${id}/actions`, {
                      action: "status",
                      status: e.target.value,
                      version: data.version,
                    }),
                  "Status updated",
                )
              }
            >
              {[
                "Backlog",
                "To Do",
                "In Progress",
                "In Review",
                ...(task.status === "Blocked" ? ["Blocked"] : []),
                "Done",
                "Cancelled",
              ].map((status) => (
                <option
                  key={status}
                  disabled={status === "Done" && !data.can_review}
                  value={status}
                >
                  {status === "Done" ? "Completed" : status}
                </option>
              ))}
            </select>
            {["To Do", "In Progress", "In Review", "Done"].map((s) => (
              <div
                className={`tw-step ${task.status === s ? "active" : ""}`}
                key={s}
              >
                <i />
                {s === "Done" ? "Completed" : s}
              </div>
            ))}
            <button
              disabled={!data.can_work}
              onClick={() => setTimer((t) => !t)}
            >
              <Clock3 size={15} /> {timer ? "Hide timer" : "Start timer"}
            </button>
          </section>
          <section className="tw-box">
            <h2>Progress</h2>
            <strong>{data.progress}%</strong>
            <progress max={100} value={data.progress} />
            <p className="tw-muted">
              {data.progress_mode === "checklist"
                ? "Calculated from checklist items"
                : "Reported through work updates"}
            </p>
            <button
              disabled={!data.can_work || busy}
              onClick={() => void action("progress_mode")}
            >
              Use {data.progress_mode === "manual" ? "checklist" : "manual"}{" "}
              progress
            </button>
          </section>
          <section className="tw-box">
            <h2>People & Relationships</h2>
            <button
              disabled={busy}
              onClick={() =>
                void run(
                  () => api.post(`${base}/tasks/${id}/watch`),
                  "Watch preference saved",
                )
              }
            >
              {data.is_watching ? "Unwatch task" : "Watch task"} ·{" "}
              {data.watcher_count}
            </button>
            <small>Manager</small>
            <p>
              {data.manager.id
                ? data.manager.name
                : "No project manager appointed"}
            </p>
            <small>Created by</small>
            <p>{data.creator.name}</p>
            <small>Assignees</small>
            {data.assignees.map((p) => (
              <div className="tw-person" key={p.id}>
                <AssignmentAvatar person={p} />
                {p.name}
              </div>
            ))}
            <button disabled={!data.can_manage} onClick={() => setAssign(true)}>
              <Users size={15} /> Manage assignments
            </button>
          </section>
          <section className="tw-box">
            <h2>Dates & Priority</h2>
            <small>Start date</small>
            <p>{task.start_date || "Not set"}</p>
            <small>Due date</small>
            <p>{task.due_date || "Not set"}</p>
            <small>Priority</small>
            <p>{task.priority}</p>
            <Link to={`/pms/tasks/${id}/edit`}>Edit schedule and priority</Link>
          </section>
        </aside>
      </div>
      {assign && (
        <TaskAssignmentPanel
          tasks={[task]}
          onClose={() => setAssign(false)}
          onSaved={refresh}
        />
      )}
    </main>
  );
}
