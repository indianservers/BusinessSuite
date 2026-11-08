import {useModuleAction} from "@/hooks/use-module-action";
import { withRecordViewHost } from "@/shared/data-grid/RecordViewHost";
import WorkspaceViewBar, { type WorkspaceView } from "@/shared/workspace/WorkspaceViewBar";
import RecordLensViews from "@/shared/workspace/RecordLensViews";
import ProjectCommunicationPage from "./ProjectCommunicationPage";
import TeamCommunicationPage from "./TeamCommunicationPage";
import { api } from "@/services/api";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import { reconcileRecordList, removedRecordIds, recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import GridTable from "@/shared/data-grid/GridTable";
import CompactActions from "@/components/actions/CompactActions";
import { useRecordView } from "@/lib/smart-cache/use-record-view";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import Sidebar from "@/components/layout/Sidebar";
import MoveBoard from "@/shared/pipeline/PipelineMoveBoard";
import { arrangeTask } from "../components/SprintMoveBoard";
import { Fragment, useEffect, useRef, useState } from "react";
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
  Menu,
  X,
  ArrowUpRight,
  Save,
  Columns3,
  PanelRightClose,
  Maximize2,
  Minimize2,
  Download,
  Settings2,
  Pencil,
} from "lucide-react";
import GlobalSearch from "@/components/app/GlobalSearch";
import SuiteNotificationBell from "@/components/suite/SuiteNotificationBell";
import PMSProfileMenu from "@/components/layout/PMSProfileMenu";
import BranchSwitcher from "@/components/suite/BranchSwitcher";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { tasksAPI, savedViewsAPI } from "../services/api";
import type {
  PMSTaskListItem,
  PMSTaskListResponse,
  PMSSavedFilter,
  PMSTaskListQuery,
} from "../types";
import CreateTaskModal from "../components/CreateTaskModal";
import RecordActions from "../components/RecordActions";
import { usePMSRealtime } from "../realtime";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { workspaceError } from "./workspaceTypes";
import "./TasksReferencePage.css";
import TaskStudioPage from "./TaskStudioPage";
import TaskWorkspacePage from "./TaskWorkspacePage";
import TaskWorkspaceViews from "../components/TaskWorkspaceViews";
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
    <span data-priority-badge data-priority={priority}
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
function TaskAssignees({ task }: { task: PMSTaskListItem }) {
  const people = task.assignees?.length ? task.assignees : [{ id: 0, name: task.assignee_name || "Unassigned", photo_url: task.assignee_photo_url }];
  const names = people.map((person) => person.name).join(", ");
  return <span className="tr-person" title={names}>
    <span className="tr-assignee-stack">{people.slice(0, 3).map((person) => <Avatar key={person.id} name={person.name} url={person.photo_url} />)}{people.length > 3 && <span>+{people.length - 3}</span>}</span>
    <span className="tr-person-name">{names}</span>
  </span>;
}

function TasksReferencePage() {
  const { user } = useAuthStore();
  const canEditTask=useModuleAction("edit");
  const taskGrant=user?.access?.grants.project_management;
  const canCreateTask=!!user?.is_superuser||!!user?.access&&!user.access.managed||!!taskGrant?.enabled&&taskGrant.actions.includes("create");
  const canExportTasks=!!user?.is_superuser||!!user?.access&&!user.access.managed||!!taskGrant?.enabled&&taskGrant.actions.includes("export");
  const route = useParams();
  const routeLocation = useLocation();
  const studio = routeLocation.pathname === "/pms/tasks/new" || !!route.taskId;
  const navigate = useNavigate();
  const [params, setRouterParams] = useSearchParams();
  const pendingParams = useRef(params);
  const observedSearch = useRef(routeLocation.search);
  if (observedSearch.current !== routeLocation.search) {
    observedSearch.current = routeLocation.search;
    pendingParams.current = params;
  }
  // Router search-param callbacks do not queue like React state updates.
  // Compose rapid filter changes against the latest requested query, while
  // still accepting back/forward navigation and links as the source of truth.
  const setParams = (update: URLSearchParams | ((previous: URLSearchParams) => URLSearchParams)) => {
    const next = typeof update === "function" ? update(new URLSearchParams(pendingParams.current)) : update;
    pendingParams.current = new URLSearchParams(next);
    setRouterParams(pendingParams.current);
  };
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
  const initialLoading = useInitialLoading(loading);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [menu, setMenu] = useState(false);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [create, setCreate] = useState(false);
  const [createProject, setCreateProject] = useState("");
  const [starterTitle, setStarterTitle] = useState("");
  const [template, setTemplate] = useState<"Task" | "Story" | "Bug">("Task");
  const [selected, setSelected] = useState<number[]>([]);
  const restoredList = useRef("");
  const [expandedPanel, setExpandedPanel] = useState(false);
  const [editingTitle, setEditingTitle] = useState<number>();
  const [opened, setOpened] = useState<PMSTaskListItem>();
  const [dirty, setDirty] = useState(false);
  const [extra, setExtra] = useState(false);
  const [views, setViews] = useState<PMSSavedFilter[]>([]);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [narrowScreen, setNarrowScreen] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 560px)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(max-width: 560px)");
    const update = () => setNarrowScreen(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const [search, setSearch] = useState(params.get("search") || "");
  const page = Number(params.get("page") || 1),
    pageSize = Number(params.get("pageSize") || 16),
    layout = params.get("layout") || "list";
  const alternateView = ["board", "gantt", "timeline", "calendar", "workload", "dashboard", "activity", "team", "mindmap", "whiteboard", "channel"].includes(layout);
  const cardLayout = layout === "gallery" || (narrowScreen && layout === "list");
  const filterKeys = ["search", "taskIds", "workspaceId", "projectId", "projectIds", "assigneeId", "assigneeIds", "reporterId", "workView", "teamId", "batchId", "workType", "status", "priority", "dueFrom", "dueTo", "createdFrom", "createdTo", "updatedFrom", "updatedTo", "storyPointsMin", "storyPointsMax", "overdue", "openOnly", "sprintId", "epicId", "tag"];
  const taskQuery = new URLSearchParams([...params].filter(([key]) => [...filterKeys, "page", "pageSize", "sortBy", "sortOrder"].includes(key))).toString();
  const activeFilterCount = filterKeys.filter((key) => {
    const value = params.get(key);
    return value && value !== "false";
  }).length;
  const change = (key: string, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== "page") next.delete("page");
      if (filterKeys.includes(key)) next.delete("quick");
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
    const query = Object.fromEntries(new URLSearchParams(taskQuery)) as PMSTaskListQuery;
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
  }, [taskQuery, revision, studio]);
  useEffect(() => {
    if (studio) return;
    savedViewsAPI
      .list("task")
      .then(setViews)
      .catch(() =>
        setNotice("Saved views could not be loaded. Refresh to retry."),
      );
  }, []);
  useRecordView<PMSTaskListResponse>("/project-management/tasks", { ...Object.fromEntries(new URLSearchParams(taskQuery)), page, pageSize, referenceDate: localDay(), overdue: params.get("overdue") === "true" }, snapshot => { setData(snapshot); setSelected(ids => ids.filter(id => snapshot.items.some(row => row.id === id))); }, () => { setData(undefined); setSelected([]); }, !studio);
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
  useEffect(() => {
    const changed = (event: Event) => {
      const change=(event as CustomEvent<RecordSaved>).detail;
      const {url,method,record}=change;
      if (!/^\/project-management\/(?:task-studio\/)?(?:projects\/\d+\/tasks|tasks(?:\/\d+)?)(?:$|\/)/.test(url)) return;
      const removed=new Set(removedRecordIds(change,"/project-management/tasks").map(String));
      if(removed.size){setData(current=>{if(!current)return current;const items=current.items.filter(row=>!removed.has(String(row.id)));return {...current,items,total:Math.max(0,current.total-(current.items.length-items.length))};});setSelected(current=>current.filter(id=>!removed.has(String(id))));if(opened&&removed.has(String(opened.id)))setDirty(false);setOpened(current=>current&&removed.has(String(current.id))?undefined:current);}
      const task=(record?.task||record) as unknown as PMSTaskListItem;
      if(change.resource==="/project-management/tasks"&&!task?.id&&change.ids?.length)setData(current=>reconcileRecordList(current,change) as typeof current);
      if(!removed.size&&method!=="delete"&&task?.id&&task.title) {
        setData(current=>{
          if(!current||!current.filters.projects.some(project=>project.id===task.project_id))return current;
          const exists=current.items.some(row=>row.id===task.id);
          if(!exists&&(page!==1||filterKeys.some(key=>params.get(key))))return current;
          const row={...task,project_name:current.filters.projects.find(project=>project.id===task.project_id)?.name};
          return {...current,items:exists?current.items.map(item=>item.id===task.id?{...item,...row}:item):[row,...current.items].slice(0,pageSize),total:current.total+(exists?0:1)};
        });
      }
      setRevision(value=>value+1);
    };
    window.addEventListener(recordSavedEvent,changed);
    return () => window.removeEventListener(recordSavedEvent,changed);
  },[page,pageSize,params.toString(),opened?.id]);
  const selectedProjectId = Number(params.get("projectId")) || undefined;
  const taskViews: WorkspaceView[] = [
    {id:"list",label:"List",description:"Fast inline editing and task execution",color:"#8b5cf6"},
    {id:"table",label:"Table",icon:"table",description:"Dense rows for detailed comparisons",color:"#14b8a6"},
    {id:"board",label:"Board",description:"Move work through its workflow",color:"#6585e8"},
    {id:"gallery",label:"Gallery",description:"A clear card for every task",color:"#df79a8"},
    {id:"gantt",label:"Gantt",description:"Schedules, dates and delivery planning",category:"Plan",color:"#f07876"},
    {id:"timeline",label:"Timeline",description:"See when the work comes together",category:"Plan",color:"#dc9b46"},
    {id:"calendar",label:"Calendar",description:"Plan the month and reschedule deadlines",category:"Plan",color:"#eb9853"},
    {id:"workload",label:"Workload",description:"Understand assignment and effort",category:"Plan",color:"#14a797"},
    {id:"dashboard",label:"Dashboard",description:"Progress, risk and attention in one place",category:"Explore",color:"#a16ed3"},
    {id:"channel",label:"Channel",description:"Project conversations connected to work",category:"Collaborate",color:"#8b5cf6"},
    {id:"activity",label:"Activity",description:"Recently updated tasks in sequence",category:"Collaborate",color:"#4a9fda"},
    {id:"team",label:"Team",description:"Explore work by its owner",category:"Explore",color:"#47a7a0"},
    {id:"mindmap",label:"Mind map",icon:"mindmap",description:"Branch out by status or assignee",category:"Explore",color:"#db78a8"},
    {id:"whiteboard",label:"Whiteboard",description:"Arrange task cards on a personal canvas",category:"Explore",color:"#c5a13e"},
    {id:"docs",label:"Docs",description:"Decisions, briefs and shared knowledge",category:"Collaborate",href:"/pms/docs",color:"#479be0"},
    {id:"files",label:"Files",description:"Browse project assets and deliverables",category:"Collaborate",href:selectedProjectId ? `/pms/projects/${selectedProjectId}/files` : "/pms/files",color:"#799ac1"},
    {id:"form",label:"Forms",description:"Collect structured requests and responses",category:"Collaborate",href:"/pms/forms",color:"#9773db"},
  ];
  const editable = projects.filter((p) => p.can_manage_tasks);
  const projectId =
    editable.find((p) => p.id === Number(params.get("projectId")))?.id ||
    editable[0]?.id;
  const add = (type: "Task" | "Story" | "Bug" = "Task", title = "") => {
    setTemplate(type);
    setStarterTitle(title);
    if (!projectId || !canCreateTask) {
      setNotice(
        "Choose a project where you can manage tasks. Create or join a project first.",
      );
      return;
    }
    setCreateProject(String(projectId));
    setCreate(true);
  };
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => { if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || (event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return; if(event.key.toLowerCase() === "n" && !create && !opened) {event.preventDefault();add();} };
    window.addEventListener("keydown",shortcut); return () => window.removeEventListener("keydown",shortcut);
  }, [projectId, create, opened]);
  const openFullTask = (task: PMSTaskListItem) => {
    const from = routeLocation.pathname + routeLocation.search;
    try { sessionStorage.setItem(`pms-task-list-scroll:${from}`, String(document.querySelector(".tr-content")?.scrollTop || document.querySelector("#suite-main")?.scrollTop || window.scrollY)); } catch { /* storage unavailable */ }
    navigate(`/pms/tasks/${task.id}`, { state: { from } });
  };
  useEffect(() => {
    if (!loading && !studio) requestAnimationFrame(() => {
      const from = routeLocation.pathname + routeLocation.search;
      if (restoredList.current === from) return;
      restoredList.current = from;
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
  async function inlineUpdate(task: PMSTaskListItem, patch: Parameters<typeof tasksAPI.update>[1]) {
    if (busy||!canEditTask) return;
    const before = data;
    setBusy(true); setError("");
    setData(current => current ? { ...current, items: current.items.map(item => item.id === task.id ? { ...item, ...patch } as PMSTaskListItem : item) } : current);
    try {
      const updated = await tasksAPI.update(task.id, patch);
      setData(current => current ? { ...current, items: current.items.map(item => item.id === task.id ? { ...item, ...updated } : item) } : current);
      setNotice("Task saved.");
    } catch (error) { setData(before); setError(workspaceError(error)); }
    finally { setBusy(false); }
  }
  async function inlineProgress(task: PMSTaskListItem, progress: number) {
    if (busy || !canCreateTask || !Number.isInteger(progress) || progress < 0 || progress > 100) return;
    setBusy(true); setError("");
    try {
      const {data: workspace} = await api.get<{revision:number; progress_mode:string}>(`/project-management/task-workspace/tasks/${task.id}`, {recordCache:false});
      if (workspace.progress_mode === "checklist") { setNotice("Progress follows the checklist. Update its items in task details."); open(task); return; }
      await api.post(`/project-management/task-workspace/tasks/${task.id}/entries`, {kind:"update",body:`Progress updated to ${progress}%`,progress,revision:workspace.revision});
      setData(current => current ? {...current,items:current.items.map(item => item.id === task.id ? {...item,progress} : item)} : current);
      setNotice("Progress saved.");
    } catch (error) { setError(workspaceError(error)); reload(); } finally { setBusy(false); }
  }
  const groupBy = params.get("groupBy") || "";
  const groupLabel = (task: PMSTaskListItem) => String(task[groupBy as keyof PMSTaskListItem] || "Unassigned");
  const visibleTasks = groupBy ? [...(data?.items || [])].sort((a, b) => groupLabel(a).localeCompare(groupLabel(b))) : data?.items || [];
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
  async function bulk(field: "status" | "priority" | "assignee_user_id", value: string) {
    if (!value||!canEditTask) return;
    setBusy(true);
    try {
      const result = await tasksAPI.bulkUpdate({ task_ids: selected, [field]: field === "assignee_user_id" ? Number(value) : value });
      setNotice(`${result.updated_count} tasks updated.`);
      setSelected([]);
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
    <div className={`pms-task-reference ${studio ? "has-task-studio" : ""} ${opened ? "has-task-panel" : ""} ${expandedPanel ? "panel-expanded" : ""}`} data-density={params.get("density") || "compact"}>
      <style>{(params.get("hideColumns") || "").split(",").filter(value => /^[3-9]$/.test(value)).map(value => `.pms-task-reference .tr-table-wrap tr > :nth-child(${value}) { display: none; }`).join("\n")}</style>
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
      <Sidebar embedded open={menu} collapsed={navCollapsed} onClose={() => setMenu(false)} onToggleCollapse={() => setNavCollapsed(value => !value)} />
      <div className="tr-body">
        <header className="suite-app-bar tr-topbar">
          <button
            className="tr-mobile"
            aria-label="Open navigation"
            onClick={() => setMenu(true)}
          >
            <Menu />
          </button>
          <GlobalSearch />
          <div className="tr-header-actions">

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
                PMS workspace
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
              title="Refresh tasks"
              aria-label="Refresh tasks"
              onClick={reload}
            >
              <RefreshCw size={20} />
            </button>
            <BranchSwitcher />
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
                {routeLocation.pathname === "/crm/tasks" && <Link to="/crm/tasks/legacy">Previous CRM tasks</Link>}
              </div>
              <div className="tr-title">
                <div>
                  <h1>Task workspace<span className="tr-heading-count">{data?.total?.toLocaleString() || "0"} tasks</span></h1>
                  <p>
                    Plan, track, and manage work across all your projects in
                    Indian Servers.
                  </p>
                </div>
                <button className="tr-primary tr-add" disabled={!projectId||!canCreateTask} title={!projectId||!canCreateTask?"Task creation requires a project where you can manage tasks":undefined} onClick={() => add()}>
                  <Plus />
                  Add Task
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
                      const next = new URLSearchParams(pendingParams.current);
                      ["status", "dueFrom", "dueTo", "overdue", "openOnly", "workView", "reporterId", "page"].forEach(key => next.delete(key));
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
                      <strong>{initialLoading ? "—" : m.value}</strong>
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
                <div className="tr-quick-tabs" role="group" aria-label="Quick task filters">{[
                  {id:"all",label:"All tasks"}, {id:"mine",label:"My tasks"}, {id:"created",label:"Created by me"}, {id:"today",label:"Today"}, {id:"upcoming",label:"Upcoming"}, {id:"overdue",label:"Overdue"}, {id:"blocked",label:"Blocked"}, {id:"completed",label:"Completed"},
                ].map(tab => <button key={tab.id} aria-pressed={(params.get("quick") || "all") === tab.id} onClick={() => { const next = new URLSearchParams(pendingParams.current); ["workView", "reporterId", "dueFrom", "dueTo", "status", "overdue", "openOnly", "page"].forEach(key => next.delete(key)); if(tab.id === "mine") next.set("workView", "mine"); if(tab.id === "created") next.set("reporterId", String(user?.id || "")); if(tab.id === "today") {next.set("dueFrom", localDay()); next.set("dueTo", localDay());} if(tab.id === "upcoming") {const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate()+1); next.set("dueFrom", `${tomorrow.getFullYear()}-${String(tomorrow.getMonth()+1).padStart(2,"0")}-${String(tomorrow.getDate()).padStart(2,"0")}`);next.set("openOnly", "true");} if(tab.id === "overdue")next.set("overdue", "true");if(tab.id === "blocked")next.set("status", "Blocked");if(tab.id === "completed")next.set("workView", "completed"); next.set("quick", tab.id); setParams(next); }}>{tab.label}</button>)}</div>
                <div className="tr-viewbar">
                  <WorkspaceViewBar scope={`pms-tasks:${selectedProjectId || "all"}`} label="Task views" active={layout} views={taskViews} onChange={id => change("layout", id)} primary={["list","board","gantt","timeline","calendar","workload","dashboard","channel"]}/>
                  <div className="tr-tools">
                    <details className="tr-customize"><summary className="tr-button"><Settings2 size={15} />Customize</summary><div>
                      <label>Row density<NativeSelect aria-label="Row density" value={params.get("density") || "compact"} onChange={e => change("density", e.target.value)}><option value="compact">Compact</option><option value="comfortable">Comfortable</option><option value="spacious">Spacious</option></NativeSelect></label>
                      <fieldset className="tr-column-options"><legend>Visible columns</legend>{["Project","Priority","Assignee","Due date","Status","Progress","Labels"].map((label,index) => {const column=index+3;const hidden=(params.get("hideColumns") || "").split(",").includes(String(column));return <label key={column}><input type="checkbox" checked={!hidden} onChange={event => {const next=new Set((params.get("hideColumns") || "").split(",").filter(Boolean));if(event.target.checked)next.delete(String(column));else next.add(String(column));change("hideColumns",[...next].join(","));}}/>{label}</label>;})}</fieldset>
                      <details><summary>Task templates</summary>{[["Bug report","Bug"],["Feature request","Story"],["Client onboarding","Task"]].map(([title,type]) => <button key={title} className="tr-button" onClick={() => add(type as "Task" | "Story" | "Bug",title)}>{title}</button>)}</details>
                      <button className="tr-button" onClick={() => setSaveOpen(true)}><Save size={14} />Save current view</button>
                      <button className="tr-button" disabled={!canCreateTask} onClick={() => { setImportProject(String(projectId || "")); setImportOpen(true); }}><Upload size={14} />Import tasks</button>
                      <Link className="tr-button" to="/pms/automation"><Zap size={14} />Automations</Link>
                      <Link className="tr-button" to="/pms/custom-fields"><Settings2 size={14} />Custom fields</Link>
                      <button className="tr-button" disabled={!canExportTasks} onClick={() => { if(!canExportTasks)return;const rows = [["Task ID", "Title", "Project", "Assignee", "Priority", "Status", "Due date"], ...(data?.items || []).map(t => [t.task_key, t.title, t.project_name, t.assignee_name, t.priority, t.status, t.due_date])]; const csv = rows.map(row => row.map(cell => '"' + String(cell || "").replace(/"/g, '""').replace(/^[=+@-]/, "'$&") + '"').join(",")).join("\r\n"); const url = URL.createObjectURL(new Blob(["\ufeff" + csv], {type:"text/csv;charset=utf-8;"})); const link = document.createElement("a"); link.href = url; link.download = "tasks-current-page.csv"; link.click(); URL.revokeObjectURL(url); setNotice("Current page exported."); }}><Download size={14} />Export current page</button>
                    </div></details>
                    <NativeSelect
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
                    </NativeSelect>
                    <button
                      className={`tr-button ${layout === "gallery" ? "active" : ""}`}
                      title="Switch between task cards and list"
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
                      title="Reload task list"
                      aria-label="Reload task list"
                      onClick={reload}
                    >
                      <RefreshCw size={17} />
                    </button>
                  </div>
                </div>
                <div className="tr-filters">
                  <NativeSelect aria-label="Group tasks on this page" value={groupBy} onChange={e => change("groupBy", e.target.value)}><option value="">Group current page</option>{[["project_name", "Project"], ["milestone_id", "Milestone"], ["assignee_name", "Assignee"], ["status", "Status"], ["priority", "Priority"], ["sprint_name", "Sprint"]].map(([value, label]) => <option key={value} value={value}>Group by {label}</option>)}</NativeSelect>
                  <label className="tr-search">
                    <Search size={17} />
                    <input
                      aria-label="Search tasks"
                      placeholder="Search tasks by title, project, assignee, or keyword…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                  <NativeSelect
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
                  </NativeSelect>
                  <NativeSelect
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
                  </NativeSelect>
                  <NativeSelect
                    aria-label="Priority"
                    value={params.get("priority") || ""}
                    onChange={(e) => change("priority", e.target.value)}
                  >
                    <option value="">⚑ Priority</option>
                    {["Urgent", "High", "Medium", "Low"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </NativeSelect>
                  <NativeSelect
                    aria-label="Status"
                    value={params.get("status") || ""}
                    onChange={(e) => change("status", e.target.value)}
                  >
                    <option value="">◯ Status</option>
                    {statuses.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </NativeSelect>
                  <button
                    className="tr-button"
                    onClick={() => setExtra(!extra)}
                  >
                    <CalendarDays size={15} />
                    Due Date
                    <ChevronDown size={12} />
                  </button>
                  <NativeSelect
                    aria-label="Sort tasks"
                    value={params.get("sortBy") || "updatedDate"}
                    onChange={(e) => change("sortBy", e.target.value)}
                  >
                    <option value="updatedDate">⇄ Sort</option>
                    <option value="dueDate">Due date</option>
                    <option value="priority">Priority</option>
                    <option value="createdDate">Created</option>
                  </NativeSelect>
                  <button
                    className="tr-button tr-filter-button"
                    aria-expanded={extra}
                    onClick={() => setExtra(!extra)}
                  >
                    <SlidersHorizontal size={15} />
                    Filters{activeFilterCount > 0 && <span>{activeFilterCount}</span>}
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
                      onClick={() => setParams((previous) => {
                        const next = new URLSearchParams(previous);
                        filterKeys.forEach((key) => next.delete(key));
                        next.delete("page");
                        next.delete("quick");
                        return next;
                      })}
                    >
                      Clear filters
                    </button>
                    <Link to="/pms/tasks/advanced">Advanced navigator ↗</Link>
                  </div>
                )}
                {!!selected.length && (
                  <div className="tr-extra">
                    <strong>{selected.length} selected</strong>
                    <NativeSelect aria-label="Bulk assignee" disabled={busy||!canEditTask} value="" onChange={event => void bulk("assignee_user_id", event.target.value)}><option value="">Reassign to...</option>{data?.filters.assignees.map(person => <option value={person.id} key={person.id}>{person.name}</option>)}</NativeSelect>
                    <button className="tr-button" onClick={() => setSelected([])}>Clear selection</button>
                    <NativeSelect
                      aria-label="Bulk status"
                      disabled={busy||!canEditTask}
                      value=""
                      onChange={(e) => void bulk("status", e.target.value)}
                    >
                      <option value="">Change status</option>
                      {statuses.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </NativeSelect>
                    <NativeSelect
                      aria-label="Bulk priority"
                      disabled={busy||!canEditTask}
                      value=""
                      onChange={(e) => void bulk("priority", e.target.value)}
                    >
                      <option value="">Change priority</option>
                      {["Urgent", "High", "Medium", "Low"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </NativeSelect>
                  </div>
                )}
                {!alternateView && <details className="tr-arrange"><summary>Arrange tasks on this page</summary><MoveBoard label="Task groups" disabled={busy||loading||!canEditTask} groups={statuses.map(s=>({id:s,label:s}))} items={[...(data?.items||[])].sort((a,b)=>(a.position||0)-(b.position||0)).map(t=>({id:t.id,label:t.title,group:t.status,disabled:!editable.some(p=>p.id===t.project_id),content:<Link to={`/pms/tasks/${t.id}`} className="text-xs text-primary">{t.task_key} · {t.project_name}</Link>}))} onMove={async({item,group,beforeId})=>{const tasks=data?.items||[];const source=tasks.find(t=>t.id===item.id);const target=tasks.find(t=>t.id===beforeId);await arrangeTask(Number(item.id),{group_by:"status",status:group,before_id:target?.project_id===source?.project_id?beforeId:undefined});reload();}}/></details>}
                {layout === "channel" ? <div className="tr-channel-view">{selectedProjectId ? <ProjectCommunicationPage selectedProjectId={selectedProjectId}/> : <TeamCommunicationPage/>}</div> : ["activity","team","mindmap","whiteboard"].includes(layout) ? <RecordLensViews scope={`pms-tasks:${selectedProjectId || "all"}`} view={layout} records={visibleTasks.map(task => ({id:String(task.id),title:task.title,subtitle:task.project_name,status:task.status,owner:task.assignee_name,start:task.start_date,due:task.due_date,updated:task.updated_at,progress:(task as PMSTaskListItem & {progress?:number}).progress,tags:task.tags?.map(tag => typeof tag === "string" ? tag : tag.name)}))} onOpen={record => open(visibleTasks.find(task => String(task.id) === record.id))}/> : alternateView ? <TaskWorkspaceViews view={layout} tasks={visibleTasks} summary={data?.summary} busy={busy} canEdit={task => canEditTask&&editable.some(project => project.id === task.project_id)} onOpen={open} onUpdate={inlineUpdate} /> : <div
                  className={
                    cardLayout
                      ? "tr-gallery"
                      : layout === "table"
                        ? "tr-table-wrap tr-compact"
                        : "tr-table-wrap"
                  }
                  aria-busy={loading}
                >
                  {!cardLayout ? (
                    <GridTable variant="matrix" aria-label="Tasks" gridId="apps/project-management/pages/TasksReferencePage:table-1">
                      <thead>
                        <tr>
                          <th>
                            <input
                              type="checkbox"
                              aria-label="Select editable tasks on this page"
                              disabled={!canEditTask || busy}
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
                            "Progress",
                            "Labels",
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
                        {visibleTasks.map((task, index) => (
                          <Fragment key={task.id}>
                          {groupBy && (index === 0 || groupLabel(visibleTasks[index - 1]) !== groupLabel(task)) && <tr className="tr-group-row"><th colSpan={10} scope="rowgroup">{groupLabel(task)}</th></tr>}
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
                              <tr data-priority-row data-priority={task.priority?.trim().toLowerCase()} aria-selected={selected.includes(task.id)} onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea,[role=button]"))open(task);}}>
                                <td>
                                  <input
                                    type="checkbox"
                                    aria-label={`Select ${task.title}`}
                                    disabled={
                                      !canEditTask || !editable.some(
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
                                    className={`tr-task-title ${editingTitle === task.id ? "tr-editing" : ""}`}
                                    onClick={() => open(task)}
                                  >
                                    {task.title}
                                  </button>
                                  <button className="tr-row-edit" title="Edit task title" aria-label={`Edit title for ${task.title}`} disabled={busy || !canEditTask || !editable.some(p => p.id === task.project_id)} onClick={() => setEditingTitle(task.id)}><Pencil size={12}/></button>
                                  {editingTitle === task.id && <input data-autosave-blur autoFocus className="tr-inline-title" aria-label={`Title for ${task.task_key}`} defaultValue={task.title} maxLength={220} disabled={busy || !canEditTask} onBlur={e => { const title = e.target.value.trim(); setEditingTitle(undefined); if (title && title !== task.title) void inlineUpdate(task, { title }); }} onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") { e.currentTarget.value = task.title; e.currentTarget.blur(); } }} />}
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
                                  <NativeSelect className={`tr-inline-select tr-priority-${task.priority.toLowerCase()}`} aria-label={`Priority for ${task.title}`} disabled={busy || !canEditTask || !editable.some(p => p.id === task.project_id)} value={task.priority} onChange={e => void inlineUpdate(task, { priority: e.target.value as PMSTaskListItem["priority"] })}>{["Urgent", "High", "Medium", "Low"].map(value => <option key={value}>{value}</option>)}</NativeSelect>
                                </td>
                                <td>
                                  <NativeSelect aria-label={`Assignee for ${task.title}`} disabled={busy || !canEditTask || !editable.some(p => p.id === task.project_id)} value={task.assignee_user_id || ""} onChange={e => void inlineUpdate(task, { assignee_user_id: Number(e.target.value) || undefined, assignee_user_ids: e.target.value ? [Number(e.target.value)] : [] })}><option value="">Unassigned</option>{data?.filters.assignees.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</NativeSelect>
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
                                  <input data-autosave-blur type="date" aria-label={`Due date for ${task.title}`} disabled={busy || !canEditTask || !editable.some(p => p.id === task.project_id)} key={`${task.id}:${task.due_date || ""}`} defaultValue={task.due_date || ""} onBlur={e => {const due_date = e.currentTarget.value; if(due_date !== (task.due_date || ""))void inlineUpdate(task, { due_date: due_date || null } as Parameters<typeof tasksAPI.update>[1]);}} onKeyDown={e => {if(e.key === "Enter")e.currentTarget.blur();}} />
                                </td>
                                <td><NativeSelect className={`tr-inline-select tr-status-${task.status.toLowerCase().replace(/ /g, "-")}`} aria-label={`Status for ${task.title}`} disabled={busy || !canEditTask || !editable.some(p => p.id === task.project_id)} value={task.status} onChange={e => void inlineUpdate(task, { status: e.target.value as PMSTaskListItem["status"] })}>{Array.from(new Set([...statuses, task.status])).map(value => <option key={value}>{value}</option>)}</NativeSelect></td>
                                <td><div className="tr-progress-cell"><progress max={100} value={(task as PMSTaskListItem & {progress?:number}).progress || 0}/><input data-autosave-blur type="number" min={0} max={100} step={1} aria-label={`Progress for ${task.title}`} key={`${task.id}:${(task as PMSTaskListItem & {progress?:number}).progress || 0}`} defaultValue={(task as PMSTaskListItem & {progress?:number}).progress || 0} disabled={busy || !canCreateTask || finished(task.status) || !editable.some(p => p.id === task.project_id)} onBlur={event => {const value = Number(event.currentTarget.value); if(event.currentTarget.value !== "" && event.currentTarget.validity.valid && value !== ((task as PMSTaskListItem & {progress?:number}).progress || 0)) void inlineProgress(task,value); else event.currentTarget.value = String((task as PMSTaskListItem & {progress?:number}).progress || 0);}} onKeyDown={event => {if(event.key === "Enter")event.currentTarget.blur();}}/><span>%</span></div></td>
                                <td><div className="tr-task-labels">{task.tags?.map((tag,index) => <span key={typeof tag === "string" ? tag : tag.id || index}>{typeof tag === "string" ? tag : tag.name}</span>)}</div></td>
                                <td>{more}</td>
                              </tr>
                            )}
                          </RecordActions></Fragment>
                        ))}
                      </tbody>
                    </GridTable>
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
                          <article data-priority-row data-priority={task.priority} className="tr-task-card" onClick={event=>{if(!(event.target as HTMLElement).closest("button,a,input,select,textarea,[role=button]"))open(task);}}>
                            <div className="tr-card-top">
                              <input
                                type="checkbox"
                                aria-label={`Select ${task.title}`}
                                disabled={!canEditTask||!editable.some((p) => p.id === task.project_id)}
                                checked={selected.includes(task.id)}
                                onChange={(e) => setSelected((current) =>
                                  e.target.checked ? [...current, task.id] : current.filter((id) => id !== task.id),
                                )}
                              />
                              <span>{task.task_key}</span>
                              {more}
                            </div>
                            <button
                              className="tr-task-title"
                              onClick={() => open(task)}
                            >
                              {task.title}
                            </button><button type="button" className="tr-quick-preview" aria-label={`Quick preview ${task.title}`} onClick={e=>{e.stopPropagation();open(task);}}>Quick preview</button>
                            <p>{task.project_name}</p>
                            <div>
                              {pill(task)}
                              <PriorityBadge priority={task.priority} />
                            </div>
                            <footer>
                              <TaskAssignees task={task} />
                              <span>{task.due_date || "No due date"}</span>
                            </footer>
                          </article>
                        )}
                      </RecordActions>
                    ))
                  )}
                  {!initialLoading && !data?.items.length && (
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
                        disabled={!error&&(!projectId||!canCreateTask)}
                        onClick={() => (error ? reload() : add())}
                      >
                        {error ? "Retry" : "Add Task"}
                      </button>
                    </div>
                  )}
                </div>}
                <div className="tr-pagination">
                  <span>
                    {initialLoading
                      ? "Loading tasks…"
                      : `Showing ${data?.total ? (page - 1) * pageSize + 1 : 0} to ${Math.min(page * pageSize, data?.total || 0)} of ${data?.total || 0} tasks`}
                  </span>
                  <label>
                    Rows{" "}
                    <NativeSelect
                      aria-label="Rows per page"
                      value={pageSize}
                      onChange={(e) => change("pageSize", e.target.value)}
                    >
                      {[8, 16, 24, 48, 100].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </NativeSelect>
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
                <CompactActions className="tr-quick">
                  <button className="tr-primary" disabled={!projectId||!canCreateTask} onClick={() => add()}>
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
                </CompactActions>
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
              <NativeSelect
                value={importProject}
                onChange={(e) => setImportProject(e.target.value)}
                disabled={busy || Object.keys(importResults).length > 0}
              >
                {editable.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </NativeSelect>
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
                busy || !canCreateTask ||
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
      <CreateTaskModal isOpen={create} onClose={() => setCreate(false)} projectId={Number(createProject)} initialTitle={starterTitle} initialWorkType={template} onTaskCreated={() => { reload(); setNotice("Task created."); }} />
      <Dialog.Root modal={false}
        open={!!opened}
        onOpenChange={(v) => {
          if (!v) open(undefined);
        }}
      >
        <Dialog.Portal>
          <Dialog.Content onInteractOutside={e => e.preventDefault()} className={`tr-detail-panel ${expandedPanel ? "expanded" : ""}`}>
            <Dialog.Title className="tr-panel-heading">{opened?.task_key || "Task details"}</Dialog.Title>
            <Dialog.Description className="sr-only">Task details, checklists, comments, files, activity and time.</Dialog.Description>
            <button className="tr-panel-expand" title={expandedPanel ? "Compact panel" : "Expand panel"} aria-label={expandedPanel ? "Compact panel" : "Expand panel"} onClick={() => setExpandedPanel(value => !value)}>{expandedPanel ? <Minimize2 size={16}/> : <Maximize2 size={16}/>}</button>
            <button
              className="tr-panel-close"
              aria-label="Close task details"
              onClick={() => open(undefined)}
            >
              <PanelRightClose size={18} />
            </button>
            <div className="tr-extra tr-panel-navigation">
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
            {opened && <TaskWorkspacePage key={opened.id} embeddedTaskId={opened.id} onTaskChanged={reload} />}
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
            <CompactForm
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
            </CompactForm>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

export default withRecordViewHost(TasksReferencePage);
