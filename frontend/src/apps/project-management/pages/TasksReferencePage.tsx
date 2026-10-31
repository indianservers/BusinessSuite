import TaskThemeSwitcher from "../components/TaskThemeSwitcher";
import MoveBoard from "@/components/interaction/MoveBoard";
import { arrangeTask } from "../components/SprintMoveBoard";
import { useEffect, useState } from "react";
import {
  Link,
  useNavigate,
  useSearchParams,
  useParams,
  useLocation,
} from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Flame,
  ThumbsUp,
  Sparkles,
  LayoutGrid,
  Layers,
  Building2,
  Users,
  List,
  Box,
  CalendarDays,
  Activity,
  Search,
  SlidersHorizontal,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Plus,
  RefreshCw,
  ClipboardList,
  CircleCheck,
  CircleAlert,
  Clock3,
  BarChart3,
  FileText,
  Zap,
  Upload,
  Bug,
  Shield,
  LogOut,
  Menu,
  X,
  ArrowUpRight,
  Save,
  Columns3,
} from "lucide-react";
import GlobalSearch from "@/components/app/GlobalSearch";
import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import PMSProfileMenu from "@/components/layout/PMSProfileMenu";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { useSignOut } from "@/hooks/use-sign-out";
import { tasksAPI, savedViewsAPI } from "../services/api";
import type {
  PMSTaskListItem,
  PMSTaskListResponse,
  PMSSavedFilter,
  PMSTaskListQuery,
} from "../types";
import CreateTaskModal from "../components/CreateTaskModal";
import RecordActions from "../components/RecordActions";
import { RichTextContent } from "@/components/rich-text/LazyRichText";
import { usePMSRealtime } from "../realtime";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { workspaceError } from "./workspaceTypes";
import "./TasksReferencePage.css";
import TaskStudioPage from "./TaskStudioPage";
const statuses = [
  "Backlog",
  "To Do",
  "In Progress",
  "In Review",
  "Blocked",
  "Done",
  "Cancelled",
];
const localDay = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const finished = (s: string) =>
  ["Done", "Completed", "Closed", "Cancelled"].includes(s);
function relativeTime(value: string) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + "Z";
  const timestamp = new Date(normalized).getTime();
  if (!Number.isFinite(timestamp)) return "Recently";
  const seconds = Math.round((timestamp - Date.now()) / 1000);
  const format = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(seconds) < 60) return format.format(seconds, "second");
  if (Math.abs(seconds) < 3600)
    return format.format(Math.round(seconds / 60), "minute");
  if (Math.abs(seconds) < 86400)
    return format.format(Math.round(seconds / 3600), "hour");
  return format.format(Math.round(seconds / 86400), "day");
}
function PriorityBadge({ priority }: { priority: string }) {
  const high = priority === "High" || priority === "Urgent";
  const Icon = high ? Flame : priority === "Low" ? ThumbsUp : BarChart3;
  return (
    <span
      className={`tr-pill ${high ? "red" : priority === "Low" ? "green" : "orange"}`}
    >
      <Icon size={11} />
      {priority}
    </span>
  );
}
function Avatar({ name, url }: { name: string; url?: string | null }) {
  const [failed, setFailed] = useState(false);
  return url && !failed ? (
    <img
      className="tr-avatar"
      src={url}
      alt={name}
      onError={() => setFailed(true)}
    />
  ) : (
    <span className="tr-avatar tr-initials" aria-label={name}>
      {name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()}
    </span>
  );
}
export default function TasksReferencePage() {
  const { user } = useAuthStore();
  const route = useParams();
  const routeLocation = useLocation();
  const studio = routeLocation.pathname === "/pms/tasks/new" || !!route.taskId;
  const signOut = useSignOut("/login");
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [importOpen, setImportOpen] = useState(false);
  const [importBatch, setImportBatch] = useState(() =>
    crypto.randomUUID().slice(0, 12),
  );
  const [importText, setImportText] = useState("");
  const [importProject, setImportProject] = useState("");
  const [importResults, setImportResults] = useState<Record<number, string>>(
    {},
  );
  const [data, setData] = useState<PMSTaskListResponse>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [menu, setMenu] = useState(false);
  const [create, setCreate] = useState(false);
  const [starterTitle, setStarterTitle] = useState("");
  const [template, setTemplate] = useState<"Task" | "Story" | "Bug">("Task");
  const [selected, setSelected] = useState<number[]>([]);
  const [opened, setOpened] = useState<PMSTaskListItem>();
  const [dirty, setDirty] = useState(false);
  const [extra, setExtra] = useState(false);
  const [views, setViews] = useState<PMSSavedFilter[]>([]);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState(params.get("search") || "");
  const page = Number(params.get("page") || 1),
    pageSize = Number(params.get("pageSize") || 8),
    layout = params.get("layout") || "list";
  const change = (key: string, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      value ? next.set(key, value) : next.delete(key);
      if (key !== "page") next.delete("page");
      return next;
    });
    setSelected([]);
  };
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== (params.get("search") || "")) change("search", search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    setSearch(params.get("search") || "");
  }, [params.get("search")]);
  useEffect(() => {
    if (studio) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    const query = Object.fromEntries(params) as PMSTaskListQuery;
    tasksAPI
      .listAll({
        ...query,
        page,
        pageSize,
        referenceDate: localDay(),
        overdue: params.get("overdue") === "true",
      })
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [params.toString(), revision, studio]);
  useEffect(() => {
    if (studio) return;
    savedViewsAPI
      .list("task")
      .then(setViews)
      .catch(() =>
        setNotice("Saved views could not be loaded. Refresh to retry."),
      );
  }, []);
  const reload = () => setRevision((n) => n + 1);
  useRefreshableEffect(() => {
    reload();
  }, []);
  useEffect(() => {
    setSelected([]);
  }, [params.toString()]);
  usePMSRealtime({
    onEvent: (event) => {
      if (event.type.startsWith("task.") || event.type === "project.updated")
        reload();
    },
    onFallbackPoll: reload,
    showToast: false,
  });
  const allowed = (to: string) =>
    canAccessRoute(to, user?.role, user?.is_superuser);
  const projects = data?.filters.projects || [];
  const editable = projects.filter((p) => p.can_manage_tasks);
  const projectId =
    editable.find((p) => p.id === Number(params.get("projectId")))?.id ||
    editable[0]?.id;
  const add = (type: "Task" | "Story" | "Bug" = "Task", title = "") => {
    setTemplate(type);
    setStarterTitle(title);
    if (!projectId) {
      setNotice(
        "Choose a project where you can manage tasks. Create or join a project first.",
      );
      return;
    }
    setCreate(true);
  };
  const openFullTask = (task: PMSTaskListItem) => {
    const from = routeLocation.pathname + routeLocation.search;
    try { sessionStorage.setItem(`pms-task-list-scroll:${from}`, String(document.querySelector(".tr-content")?.scrollTop || document.querySelector("#suite-main")?.scrollTop || window.scrollY)); } catch { /* storage unavailable */ }
    navigate(`/pms/tasks/${task.id}`, { state: { from } });
  };
  useEffect(() => {
    if (!loading && !studio) requestAnimationFrame(() => {
      const from = routeLocation.pathname + routeLocation.search;
      let top = 0; try { top = Number(sessionStorage.getItem(`pms-task-list-scroll:${from}`)) || 0; } catch { /* storage unavailable */ }
      window.scrollTo(0, top);
      document.querySelector(".tr-content")?.scrollTo(0, top);
      document.querySelector("#suite-main")?.scrollTo(0, top);
    });
  }, [loading, studio]);
  const open = (task?: PMSTaskListItem) => {
    if (dirty && !window.confirm("Discard unsaved task changes?")) return;
    setDirty(false);
    setOpened(task);
  };
  const nav = [
    { label: "Overview", to: "/pms", icon: LayoutGrid },
    { label: "Workspace board", to: "/pms/workspaces", icon: LayoutGrid },
    { label: "Product Launch", to: "/pms/product-launch", icon: Box },
    { label: "Impact Work Hub", to: "/pms/work-hub", icon: Activity },
    { label: "Live Work", to: "/pms/live", icon: Activity },
    { label: "Issues", to: "/pms/issues", icon: CircleAlert },
    { label: "Tasks", to: "/pms/tasks", icon: SlidersHorizontal },
    { label: "Issue Navigator", to: "/pms/navigator", icon: Search },
    {
      label: "Issue Navigator Pro",
      to: "/pms/issue-navigator-pro",
      icon: ClipboardList,
    },
    { label: "Workspaces", to: "/pms/workspaces", icon: Building2 },
    { label: "People", to: "/pms/people", icon: Users },
  ];
  const summary = data?.summary;
  const metrics = [
    {
      label: "Total Tasks",
      value: summary?.total ?? data?.total ?? 0,
      icon: ClipboardList,
      color: "purple",
      caption: summary
        ? `${summary.created_last_week} added in last 7 days`
        : "All permitted tasks",
      filter: "",
    },
    {
      label: "In Progress",
      value: summary?.in_progress ?? 0,
      icon: Clock3,
      color: "blue",
      caption: "Work moving forward",
      filter: "In Progress",
    },
    {
      label: "Due Today",
      value: summary?.due_today ?? 0,
      icon: CalendarDays,
      color: "orange",
      caption: "Open tasks due today",
      filter: "today",
    },
    {
      label: "Completed",
      value: summary?.completed ?? 0,
      icon: CircleCheck,
      color: "green",
      caption: "Finished work",
      filter: "Done",
    },
    {
      label: "Overdue",
      value: summary?.overdue ?? 0,
      icon: CircleAlert,
      color: "red",
      caption: "Needs your attention",
      filter: "overdue",
    },
  ];
  async function bulk(field: "status" | "priority", value: string) {
    if (!value) return;
    setBusy(true);
    try {
      await tasksAPI.bulkUpdate({ task_ids: selected, [field]: value });
      setSelected([]);
      setNotice("Tasks updated.");
      reload();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setBusy(false);
    }
  }
  const pill = (task: PMSTaskListItem) => {
    const overdue =
      !!task.due_date && task.due_date < localDay() && !finished(task.status);
    return (
      <span
        className={`tr-pill ${overdue ? "red" : task.status === "In Progress" ? "blue" : finished(task.status) ? "green" : "gray"}`}
      >
        {overdue
          ? "◉ Overdue"
          : task.status === "Done"
            ? "✓ Completed"
            : task.status}
      </span>
    );
  };
  return (
    <div className={`pms-task-reference ${studio ? "has-task-studio" : ""}`}>
      <a className="suite-skip" href="#suite-main">
        Skip to content
      </a>
      {menu && (
        <button
          className="tr-scrim"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`tr-sidebar ${menu ? "is-open" : ""}`}>
        <Link to="/pms" className="tr-brand">
          <span>
            <Sparkles />
          </span>
          <div>
            <strong>Indian Servers</strong>
            <small>PMS 1.0.1 · Admin Console</small>
          </div>
        </Link>
        <nav aria-label="Project management">
          <Link to="/dashboard" className="tr-nav">
            <LayoutGrid />
            All applications
          </Link>
          <div className="tr-product">
            <Link to="/pms">
              <Layers />
              KaryaFlow PMS
              <ChevronDown />
            </Link>
            <Link to="/pms/workspaces">
              <Building2 />
              Indian Servers (active)
            </Link>
            {allowed("/pms/people") && (
              <Link to="/pms/people">
                <Users />
                Users & access
              </Link>
            )}
          </div>
          {nav
            .filter((n) => allowed(n.to))
            .map((n, i) => (
              <div key={`${n.label}-${i}`}>
                {i === 1 && (
                  <div className="tr-group">
                    Projects & tasks <ChevronDown size={13} />
                  </div>
                )}
                <Link
                  className={`tr-nav ${n.to === "/pms/tasks" ? "active" : ""}`}
                  to={n.to}
                >
                  <n.icon />
                  {n.label}
                </Link>
              </div>
            ))}
        </nav>
        <footer>
          <span className="tr-nav">
            <Users />
            {user?.email}
          </span>
          <Link className="tr-nav" to="/help">
            <Box />
            Help & support
          </Link>
          <button className="tr-nav tr-signout" onClick={() => void signOut()}>
            <LogOut />
            Sign out
          </button>
        </footer>
      </aside>
      <div className="tr-body">
        <header className="tr-topbar">
          <button
            className="tr-mobile"
            aria-label="Open navigation"
            onClick={() => setMenu(true)}
          >
            <Menu />
          </button>
          <GlobalSearch />
          <div className="tr-header-actions">
            {!studio && <TaskThemeSwitcher />}
            {studio && (
              <Link className="tr-primary tr-studio-new" to="/pms/tasks/new">
                <Plus size={14} />
                New
                <ChevronDown size={12} />
              </Link>
            )}
            <Link className="tr-button tr-ai" to="/pms/operator">
              <Sparkles size={17} />
              AI Operator
            </Link>
            <details className="tr-suite">
              <summary className="tr-button">
                <LayoutGrid size={16} />
                Business Suite 1.0.1 / PMS 1.0.1
                <ChevronDown size={14} />
              </summary>
              <div>
                {[
                  ["PMS", "/pms"],
                  ["HRMS", "/hrms"],
                  ["CRM", "/crm"],
                ]
                  .filter(([, to]) => allowed(to))
                  .map(([label, to]) => (
                    <Link key={to} to={to}>
                      {label}
                    </Link>
                  ))}
              </div>
            </details>
            <SuiteNotificationBell />
            <button
              className="tr-icon"
              aria-label="Refresh tasks"
              onClick={reload}
            >
              <RefreshCw size={20} />
            </button>
            <PMSProfileMenu
              onCreateTask={() => (studio ? navigate("/pms/tasks/new") : add())}
            />
          </div>
        </header>
        {studio ? (
          <TaskStudioPage key={route.taskId || `new:${routeLocation.search}`} />
        ) : (
          <div className="tr-content">
            <main id="suite-main" tabIndex={-1}>
              <div className="tr-breadcrumb">
                <Link to="/dashboard">All applications</Link>
                <ChevronRight />
                <Link to="/pms">KaryaFlow PMS</Link>
                <ChevronRight />
                <b>Tasks</b>
              </div>
              <div className="tr-title">
                <div>
                  <h1>Tasks</h1>
                  <p>
                    Plan, track, and manage work across all your projects in
                    Indian Servers.
                  </p>
                </div>
                <button className="tr-primary tr-add" onClick={() => add()}>
                  <Plus />
                  Add Task
                  <ChevronDown size={18} />
                </button>
              </div>
              <section
                className="tr-metrics"
                aria-label="Task overview for current filters"
                title="Counts reflect your current filters and permitted projects"
              >
                {metrics.map((m) => (
                  <button
                    key={m.label}
                    className={`tr-metric ${m.color}`}
                    onClick={() => {
                      const next = new URLSearchParams();
                      if (m.filter === "today") {
                        next.set("dueFrom", localDay());
                        next.set("dueTo", localDay());
                        next.set("openOnly", "true");
                      } else if (m.filter === "overdue")
                        next.set("overdue", "true");
                      else if (m.filter) next.set("status", m.filter);
                      setParams(next);
                    }}
                  >
                    <span className="tr-metric-icon">
                      <m.icon />
                    </span>
                    <div>
                      <span>{m.label}</span>
                      <strong>{loading ? "—" : m.value}</strong>
                      <small>{m.caption}</small>
                    </div>
                    <BarChart3 className="tr-chart" size={18} />
                  </button>
                ))}
              </section>
              {(notice || error) && (
                <div
                  className={`tr-feedback ${error ? "error" : ""}`}
                  role={error ? "alert" : "status"}
                >
                  {error || notice}
                  {error && <button onClick={reload}>Retry</button>}
                  <button
                    aria-label="Dismiss message"
                    onClick={() => {
                      setError("");
                      setNotice("");
                    }}
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              <section className="tr-work">
                <div className="tr-viewbar">
                  <div className="tr-tabs" role="group" aria-label="Task view">
                    {[
                      { label: "List", icon: List, value: "list" },
                      { label: "Table", icon: LayoutGrid, value: "table" },
                    ].map((v) => (
                      <button
                        key={v.value}
                        className={layout === v.value ? "active" : ""}
                        onClick={() => change("layout", v.value)}
                      >
                        <v.icon size={17} />
                        {v.label}
                      </button>
                    ))}
                    <Link
                      to={
                        projects.length
                          ? `/pms/projects/${Number(params.get("projectId")) || projects[0].id}/board`
                          : "/pms/projects"
                      }
                    >
                      <Box size={17} />
                      Board
                    </Link>
                    <Link to="/pms/calendar">
                      <CalendarDays size={17} />
                      Calendar
                    </Link>
                    <Link to="/pms/gantt">
                      <Activity size={17} />
                      Timeline
                    </Link>
                  </div>
                  <div className="tr-tools">
                    <select
                      aria-label="Saved views"
                      value=""
                      onChange={(e) => {
                        if (e.target.value === "save") setSaveOpen(true);
                        else {
                          const v = views.find(
                            (v) => v.id === Number(e.target.value),
                          );
                          if (v) {
                            const next = new URLSearchParams();
                            Object.entries(v.filters || {}).forEach(
                              ([k, val]) => {
                                if (
                                  val !== null &&
                                  val !== undefined &&
                                  val !== ""
                                )
                                  next.set(k, String(val));
                              },
                            );
                            Object.entries(v.sort || {}).forEach(
                              ([key, value]) => {
                                if (value) next.set(key, String(value));
                              },
                            );
                            setParams(next);
                          }
                        }
                      }}
                    >
                      <option value="">☷ Saved views</option>
                      {views.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                      <option value="save">+ Save current view</option>
                    </select>
                    <button
                      className={`tr-button ${layout === "gallery" ? "active" : ""}`}
                      aria-label="Cards"
                      aria-pressed={layout === "gallery"}
                      onClick={() =>
                        change(
                          "layout",
                          layout === "gallery" ? "list" : "gallery",
                        )
                      }
                    >
                      <Columns3 size={16} />
                    </button>
                    <button
                      className="tr-button"
                      aria-label="Reload task list"
                      onClick={reload}
                    >
                      <RefreshCw size={17} />
                    </button>
                  </div>
                </div>
                <div className="tr-filters">
                  <label className="tr-search">
                    <Search size={17} />
                    <input
                      aria-label="Search tasks"
                      placeholder="Search tasks by title, project, assignee, or keyword…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                  <select
                    aria-label="Project"
                    value={params.get("projectId") || ""}
                    onChange={(e) => change("projectId", e.target.value)}
                  >
                    <option value="">⚑ Project</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Assignee"
                    value={params.get("assigneeId") || ""}
                    onChange={(e) => change("assigneeId", e.target.value)}
                  >
                    <option value="">♙ Assignee</option>
                    {data?.filters.assignees.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Priority"
                    value={params.get("priority") || ""}
                    onChange={(e) => change("priority", e.target.value)}
                  >
                    <option value="">⚑ Priority</option>
                    {["Urgent", "High", "Medium", "Low"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                  <select
                    aria-label="Status"
                    value={params.get("status") || ""}
                    onChange={(e) => change("status", e.target.value)}
                  >
                    <option value="">◯ Status</option>
                    {statuses.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                  <button
                    className="tr-button"
                    onClick={() => setExtra(!extra)}
                  >
                    <CalendarDays size={15} />
                    Due Date
                    <ChevronDown size={12} />
                  </button>
                  <select
                    aria-label="Sort tasks"
                    value={params.get("sortBy") || "updatedDate"}
                    onChange={(e) => change("sortBy", e.target.value)}
                  >
                    <option value="updatedDate">⇄ Sort</option>
                    <option value="dueDate">Due date</option>
                    <option value="priority">Priority</option>
                    <option value="createdDate">Created</option>
                  </select>
                  <button
                    className="tr-button tr-filter-button"
                    aria-expanded={extra}
                    onClick={() => setExtra(!extra)}
                  >
                    <SlidersHorizontal size={15} />
                    Filters{params.size > 0 && <span>{params.size}</span>}
                  </button>
                </div>
                {extra && (
                  <div className="tr-extra">
                    <label>
                      Due from{" "}
                      <input
                        type="date"
                        value={params.get("dueFrom") || ""}
                        onChange={(e) => change("dueFrom", e.target.value)}
                      />
                    </label>
                    <label>
                      Due to{" "}
                      <input
                        type="date"
                        value={params.get("dueTo") || ""}
                        onChange={(e) => change("dueTo", e.target.value)}
                      />
                    </label>
                    <button
                      className="tr-button"
                      onClick={() =>
                        change(
                          "sortOrder",
                          params.get("sortOrder") === "asc" ? "desc" : "asc",
                        )
                      }
                    >
                      Order: {params.get("sortOrder") || "desc"}
                    </button>
                    <button
                      className="tr-button"
                      onClick={() => setParams(new URLSearchParams())}
                    >
                      Clear filters
                    </button>
                    <Link to="/pms/tasks/advanced">Advanced navigator ↗</Link>
                  </div>
                )}
                {!!selected.length && (
                  <div className="tr-extra">
                    <strong>{selected.length} selected</strong>
                    <select
                      aria-label="Bulk status"
                      disabled={busy}
                      value=""
                      onChange={(e) => void bulk("status", e.target.value)}
                    >
                      <option value="">Change status</option>
                      {statuses.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                    <select
                      aria-label="Bulk priority"
                      disabled={busy}
                      value=""
                      onChange={(e) => void bulk("priority", e.target.value)}
                    >
                      <option value="">Change priority</option>
                      {["Urgent", "High", "Medium", "Low"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                )}
                <details className="rounded-lg border bg-white p-3 mb-4"><summary>Arrange tasks on this page</summary><MoveBoard label="Task groups" disabled={busy||loading} groups={statuses.map(s=>({id:s,label:s}))} items={[...(data?.items||[])].sort((a,b)=>(a.position||0)-(b.position||0)).map(t=>({id:t.id,label:t.title,group:t.status,disabled:!editable.some(p=>p.id===t.project_id),content:<Link to={`/pms/tasks/${t.id}`} className="text-xs text-primary">{t.task_key} · {t.project_name}</Link>}))} onMove={async({item,group,beforeId})=>{const tasks=data?.items||[];const source=tasks.find(t=>t.id===item.id);const target=tasks.find(t=>t.id===beforeId);await arrangeTask(Number(item.id),{group_by:"status",status:group,before_id:target?.project_id===source?.project_id?beforeId:undefined});reload();}}/></details>
                <div
                  className={
                    layout === "gallery"
                      ? "tr-gallery"
                      : layout === "table"
                        ? "tr-table-wrap tr-compact"
                        : "tr-table-wrap"
                  }
                  aria-busy={loading}
                >
                  {layout !== "gallery" ? (
                    <table>
                      <thead>
                        <tr>
                          <th>
                            <input
                              type="checkbox"
                              aria-label="Select editable tasks on this page"
                              checked={
                                !!selected.length &&
                                selected.length ===
                                  (data?.items.filter((t) =>
                                    editable.some((p) => p.id === t.project_id),
                                  ).length || 0)
                              }
                              onChange={(e) =>
                                setSelected(
                                  e.target.checked
                                    ? data?.items
                                        .filter((t) =>
                                          editable.some(
                                            (p) => p.id === t.project_id,
                                          ),
                                        )
                                        .map((t) => t.id) || []
                                    : [],
                                )
                              }
                            />
                          </th>
                          {[
                            "Task",
                            "Project",
                            "Priority",
                            "Assignee",
                            "Due Date",
                            "Status",
                            "Actions",
                          ].map((h) => (
                            <th key={h}>
                              {["Priority", "Due Date", "Status"].includes(
                                h,
                              ) ? (
                                <button
                                  onClick={() => {
                                    const sort =
                                      h === "Priority"
                                        ? "priority"
                                        : h === "Due Date"
                                          ? "dueDate"
                                          : "status";
                                    setParams((prev) => {
                                      const next = new URLSearchParams(prev);
                                      next.set("sortBy", sort);
                                      next.set(
                                        "sortOrder",
                                        prev.get("sortBy") === sort &&
                                          prev.get("sortOrder") === "asc"
                                          ? "desc"
                                          : "asc",
                                      );
                                      next.delete("page");
                                      return next;
                                    });
                                  }}
                                >
                                  {h}
                                </button>
                              ) : (
                                h
                              )}
                              {h !== "Actions" && (
                                <span className="tr-sort-mark">⌃⌄</span>
                              )}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data?.items.map((task) => (
                          <RecordActions
                            key={task.id}
                            record={{ ...task, key: task.task_key }}
                            canEdit={editable.some(
                              (p) => p.id === task.project_id,
                            )}
                            preview={false}
                        onOpen={() => openFullTask(task)}
                            onChanged={reload}
                          >
                            {(more) => (
                              <tr onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea,[role=button]"))openFullTask(task);}}>
                                <td>
                                  <input
                                    type="checkbox"
                                    aria-label={`Select ${task.title}`}
                                    disabled={
                                      !editable.some(
                                        (p) => p.id === task.project_id,
                                      )
                                    }
                                    checked={selected.includes(task.id)}
                                    onChange={(e) =>
                                      setSelected(
                                        e.target.checked
                                          ? [...selected, task.id]
                                          : selected.filter(
                                              (id) => id !== task.id,
                                            ),
                                      )
                                    }
                                  />
                                </td>
                                <td>
                                  <button
                                    className="tr-task-title"
                                    onClick={() => openFullTask(task)}
                                  >
                                    {task.title}
                                  </button><button type="button" className="tr-quick-preview" aria-label={`Quick preview ${task.title}`} onClick={e=>{e.stopPropagation();open(task);}}>Quick preview</button>
                                  <small>#{task.task_key || task.id}</small>
                                </td>
                                <td>
                                  <span className="tr-project-name">
                                    <i
                                      style={{
                                        background: [
                                          "#8239ff",
                                          "#ed4fcb",
                                          "#09a0f4",
                                          "#20bc7d",
                                        ][task.project_id % 4],
                                      }}
                                    />
                                    {task.project_name}
                                  </span>
                                  <small>{task.is_general ? "Workspace tasks" : task.project_key || "Project"}</small>
                                </td>
                                <td>
                                  <PriorityBadge priority={task.priority} />
                                </td>
                                <td>
                                  <span className="tr-person">
                                    <Avatar
                                      name={task.assignee_name || "Unassigned"}
                                      url={task.assignee_photo_url}
                                    />
                                    {task.assignee_name || "Unassigned"}
                                  </span>
                                </td>
                                <td
                                  className={
                                    task.due_date &&
                                    task.due_date < localDay() &&
                                    !finished(task.status)
                                      ? "tr-overdue"
                                      : ""
                                  }
                                >
                                  {task.due_date
                                    ? new Date(
                                        task.due_date + "T00:00:00",
                                      ).toLocaleDateString("en-US", {
                                        month: "short",
                                        day: "numeric",
                                        year: "numeric",
                                      })
                                    : "No due date"}
                                </td>
                                <td>{pill(task)}</td>
                                <td>{more}</td>
                              </tr>
                            )}
                          </RecordActions>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    data?.items.map((task) => (
                      <RecordActions
                        key={task.id}
                        record={{ ...task, key: task.task_key }}
                        canEdit={editable.some((p) => p.id === task.project_id)}
                        preview={false}
                        onOpen={() => openFullTask(task)}
                        onChanged={reload}
                      >
                        {(more) => (
                          <article className="tr-task-card" onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea,[role=button]"))openFullTask(task);}}>
                            <div className="tr-card-top">
                              <span>{task.task_key}</span>
                              {more}
                            </div>
                            <button
                              className="tr-task-title"
                              onClick={() => openFullTask(task)}
                            >
                              {task.title}
                            </button><button type="button" className="tr-quick-preview" aria-label={`Quick preview ${task.title}`} onClick={e=>{e.stopPropagation();open(task);}}>Quick preview</button>
                            <p>{task.project_name}</p>
                            <div>
                              {pill(task)}
                              <PriorityBadge priority={task.priority} />
                            </div>
                            <footer>
                              <span className="tr-person">
                                <Avatar
                                  name={task.assignee_name || "Unassigned"}
                                  url={task.assignee_photo_url}
                                />
                                {task.assignee_name || "Unassigned"}
                              </span>
                              <span>{task.due_date || "No due date"}</span>
                            </footer>
                          </article>
                        )}
                      </RecordActions>
                    ))
                  )}
                  {!loading && !data?.items.length && (
                    <div className="tr-empty">
                      <ClipboardList />
                      <h2>
                        {error
                          ? "Tasks could not be loaded"
                          : "No tasks in this view"}
                      </h2>
                      <p>
                        {error
                          ? "Retry to load your work."
                          : "Adjust your filters or add a task to get started."}
                      </p>
                      <button
                        className="tr-primary"
                        onClick={() => (error ? reload() : add())}
                      >
                        {error ? "Retry" : "Add Task"}
                      </button>
                    </div>
                  )}
                </div>
                <div className="tr-pagination">
                  <span>
                    {loading
                      ? "Loading tasks…"
                      : `Showing ${data?.total ? (page - 1) * pageSize + 1 : 0} to ${Math.min(page * pageSize, data?.total || 0)} of ${data?.total || 0} tasks`}
                  </span>
                  <label>
                    Rows{" "}
                    <select
                      aria-label="Rows per page"
                      value={pageSize}
                      onChange={(e) => change("pageSize", e.target.value)}
                    >
                      {[8, 16, 24, 48].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="tr-button"
                    disabled={page <= 1 || loading}
                    onClick={() => change("page", String(page - 1))}
                  >
                    <ChevronLeft size={15} />
                    Previous
                  </button>
                  {Array.from(
                    { length: Math.min(3, data?.pages || 1) },
                    (_, i) =>
                      Math.max(1, Math.min(page - 1, (data?.pages || 1) - 2)) +
                      i,
                  )
                    .filter((n) => n <= (data?.pages || 1))
                    .map((n) => (
                      <button
                        className={n === page ? "tr-primary" : "tr-button"}
                        key={n}
                        onClick={() => change("page", String(n))}
                        aria-label={`Page ${n}`}
                        aria-current={n === page ? "page" : undefined}
                      >
                        {n}
                      </button>
                    ))}
                  <button
                    className="tr-button"
                    disabled={page >= (data?.pages || 1) || loading}
                    onClick={() => change("page", String(page + 1))}
                  >
                    Next
                    <ChevronRight size={15} />
                  </button>
                </div>
              </section>
            </main>
            <aside className="tr-right">
              <section>
                <h2>
                  <Sparkles size={19} />
                  Quick Actions
                </h2>
                <div className="tr-quick">
                  <button className="tr-primary" onClick={() => add()}>
                    <Plus />
                    Add Task
                  </button>
                  <Link to="/pms/workspaces">
                    <FileText />
                    Task Templates
                  </Link>
                  <Link to="/pms/automation">
                    <Zap />
                    Automation
                  </Link>
                  <button
                    title="Use the project import tools"
                    onClick={() => {
                      setImportProject(String(projectId || ""));
                      setImportOpen(true);
                    }}
                  >
                    <Upload />
                    Import Tasks
                  </button>
                </div>
              </section>
              <section>
                <h2>
                  Popular Templates<Link to="/pms/workspaces">View all</Link>
                </h2>
                {[
                  {
                    name: "Bug Report",
                    sub: "For issue tracking",
                    icon: Bug,
                    color: "red",
                    type: "Bug" as const,
                  },
                  {
                    name: "Feature Request",
                    sub: "For new features",
                    icon: Shield,
                    color: "blue",
                    type: "Story" as const,
                  },
                  {
                    name: "Server Maintenance",
                    sub: "For infrastructure tasks",
                    icon: CalendarDays,
                    color: "purple",
                    type: "Task" as const,
                  },
                  {
                    name: "Client Onboarding",
                    sub: "For new clients",
                    icon: ClipboardList,
                    color: "orange",
                    type: "Task" as const,
                  },
                ].map((t) => (
                  <button
                    className="tr-template"
                    key={t.name}
                    onClick={() => add(t.type, t.name)}
                  >
                    <span className={`tr-template-icon ${t.color}`}>
                      <t.icon size={18} />
                    </span>
                    <span>
                      <strong>{t.name}</strong>
                      <small>{t.sub}</small>
                    </span>
                  </button>
                ))}
              </section>
              <section>
                <h2>
                  <Clock3 size={15} />
                  Recent Activity<Link to="/pms/tasks/advanced">View all</Link>
                </h2>
                <div className="tr-activity">
                  {data?.activity?.map((a) => (
                    <button
                      key={a.id}
                      onClick={() =>
                        a.task_id && navigate(`/pms/tasks/${a.task_id}`)
                      }
                    >
                      <i />
                      <Avatar name={a.actor_name} url={a.photo_url} />
                      <span>
                        <strong>{a.actor_name}</strong>
                        <span>{a.summary}</span>
                        <small>{relativeTime(a.created_at)}</small>
                      </span>
                    </button>
                  ))}
                  {!data?.activity?.length && (
                    <p>Task activity will appear here as your team works.</p>
                  )}
                </div>
              </section>
            </aside>
          </div>
        )}
      </div>
      <Dialog.Root
        open={importOpen}
        onOpenChange={(v) => {
          if (!busy) setImportOpen(v);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="tr-dialog-overlay" />
          <Dialog.Content className="tr-save-dialog">
            <Dialog.Title>Import Tasks</Dialog.Title>
            <Dialog.Description>
              Paste one task title per line. Review the destination before
              creating tasks. Existing tasks are kept.
            </Dialog.Description>
            <label>
              Destination project
              <select
                value={importProject}
                onChange={(e) => setImportProject(e.target.value)}
                disabled={busy || Object.keys(importResults).length > 0}
              >
                {editable.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Task titles
              <textarea
                rows={6}
                value={importText}
                disabled={busy || Object.keys(importResults).length > 0}
                onChange={(e) => {
                  setImportText(e.target.value);
                  setImportResults({});
                }}
              />
            </label>
            <p>
              Scope:{" "}
              {editable.find((p) => p.id === Number(importProject))?.name ||
                "Choose a project"}{" "}
              · {importText.split(/\r?\n/).filter((t) => t.trim()).length} tasks
            </p>
            <ol className="tr-import-preview">
              {importText
                .split(/\r?\n/)
                .filter((t) => t.trim())
                .map((title, i) => (
                  <li key={i}>
                    {title} — {importResults[i] || "Ready"}
                  </li>
                ))}
            </ol>
            <button
              className="tr-primary"
              disabled={
                busy ||
                !importProject ||
                !importText.trim() ||
                importText.split(/\r?\n/).filter((t) => t.trim()).length > 100
              }
              onClick={async () => {
                setBusy(true);
                const titles = importText
                  .split(/\r?\n/)
                  .filter((t) => t.trim());
                for (let i = 0; i < titles.length; i++) {
                  if (importResults[i] === "Created") continue;
                  try {
                    await tasksAPI.create(Number(importProject), {
                      title: titles[i].trim(),
                      task_key: `IMPORT-${importBatch}-${i}`,
                      work_type: "Task",
                    });
                    setImportResults((r) => ({ ...r, [i]: "Created" }));
                  } catch (e) {
                    setImportResults((r) => ({ ...r, [i]: workspaceError(e) }));
                  }
                }
                setBusy(false);
                reload();
              }}
            >
              {busy
                ? "Importing…"
                : Object.keys(importResults).length
                  ? "Retry failed items"
                  : "Create tasks"}
            </button>
            <button
              className="tr-button"
              disabled={busy}
              onClick={() => {
                setImportResults({});
                setImportText("");
                setImportBatch(crypto.randomUUID().slice(0, 12));
              }}
            >
              New import
            </button>
            <Dialog.Close disabled={busy} className="tr-button">
              Close
            </Dialog.Close>
            <p>
              Maximum 100 titles. Successfully created rows are skipped when
              retrying.
            </p>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <CreateTaskModal
        isOpen={create}
        onClose={() => setCreate(false)}
        projectId={projectId || 0}
        projects={editable}
        initialWorkType={template}
        initialTitle={starterTitle}
        onTaskCreated={(_, another) => {
          reload();
          setNotice("Task created.");
          if (!another) setCreate(false);
        }}
      />
      <Dialog.Root
        open={!!opened}
        onOpenChange={(v) => {
          if (!v) open(undefined);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="tr-dialog-overlay" />
          <Dialog.Content className="tr-detail-panel">
            <Dialog.Title>{opened?.title}</Dialog.Title>
            <Dialog.Description>
              Quick summary. Open the full task to manage work and collaborate.
            </Dialog.Description>
            <button
              className="tr-panel-close"
              aria-label="Close task details"
              onClick={() => open(undefined)}
            >
              <X />
            </button>
            <div className="tr-extra">
              <button
                className="tr-button"
                disabled={!opened || data?.items[0]?.id === opened.id}
                onClick={() =>
                  open(
                    data?.items[
                      (data.items.findIndex((t) => t.id === opened?.id) || 0) -
                        1
                    ],
                  )
                }
              >
                Previous
              </button>
              <button
                className="tr-button"
                disabled={!opened || data?.items.at(-1)?.id === opened.id}
                onClick={() =>
                  open(
                    data?.items[
                      (data.items.findIndex((t) => t.id === opened?.id) || 0) +
                        1
                    ],
                  )
                }
              >
                Next
              </button>
              <Link
                to={`/pms/tasks/${opened?.id}`}
                onClick={(event) => {
                  if (dirty && !window.confirm("Discard unsaved task changes?"))
                    event.preventDefault();
                }}
              >
                Full details <ArrowUpRight size={14} />
              </Link>
            </div>
            {opened && <section className="tr-preview-summary"><p>{opened.status} · {opened.priority} priority</p><p>{opened.project_name} · Due {opened.due_date || "not set"}</p><p>Assignee: {opened.assignee_name || "Unassigned"}</p><RichTextContent value={opened.description || "No description yet."}/><Link className="tr-primary" to={`/pms/tasks/${opened.id}`} state={{from:routeLocation.pathname+routeLocation.search}}>Open Full Task <ArrowUpRight size={14}/></Link></section>}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={saveOpen} onOpenChange={setSaveOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="tr-dialog-overlay" />
          <Dialog.Content className="tr-save-dialog">
            <Dialog.Title>Save this task view</Dialog.Title>
            <Dialog.Description>
              Keep the current filters in your personal saved views.
            </Dialog.Description>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  const view = await savedViewsAPI.create({
                    name: viewName,
                    entity_type: "task",
                    view_type: "task_list",
                    filters: Object.fromEntries(params),
                    visibility: "private",
                  });
                  setViews((v) => [...v, view]);
                  setSaveOpen(false);
                  setViewName("");
                  setNotice("Personal view saved.");
                } catch (e) {
                  setError(workspaceError(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                View name
                <input
                  required
                  value={viewName}
                  onChange={(e) => setViewName(e.target.value)}
                />
              </label>
              <button className="tr-primary" disabled={busy}>
                <Save size={16} />
                Save view
              </button>
              <Dialog.Close className="tr-button" type="button">
                Cancel
              </Dialog.Close>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
