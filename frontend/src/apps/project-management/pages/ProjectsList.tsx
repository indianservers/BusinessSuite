import { LoadingState } from "@/components/ui/state";
import {useModuleAction} from "@/hooks/use-module-action";
import { removedRecordIds, recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import { useInitialLoading } from "@/hooks/use-initial-loading";
import { withRecordViewHost } from "@/shared/data-grid/RecordViewHost";
import { savedWithUndo } from "@/components/actions/undo-feedback";
import GridRecordPane from "@/shared/data-grid/GridRecordPane";
import WorkspaceViewBar, { type WorkspaceView } from "@/shared/workspace/WorkspaceViewBar";
import RecordLensViews from "@/shared/workspace/RecordLensViews";
import { useEffect, useMemo, useRef, useState } from "react";

import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Download,
  Eye,
  ExternalLink,
  FolderKanban,
  LayoutGrid,
  List,
  PauseCircle,
  PlayCircle,
  Plus,
  Search,
  SlidersHorizontal,
  Star,
  Trash2,
  Upload,
} from "lucide-react";

import { csvText, downloadBlob } from "@/shared/data-transfer/transfer";
import GridTable from "@/shared/data-grid/GridTable";
import { RecordStatusIcon } from "@/shared/data-grid/GroupLabel";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import { Badge } from "@/components/ui/badge";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

import { NativeSelect } from "@/components/ui/native-select";

import { RichTextContent } from "@/components/rich-text/RichTextContent";

import { useRefreshableEffect } from "@/lib/page-refresh";

import { formatDate, statusColor } from "@/lib/utils";

import { useAuthStore } from "@/store/authStore";

import { api } from "@/services/api";

import { projectsAPI } from "../services/api";

import { useProjectStore } from "../store";

import type { PMSProject, CreateProjectInput } from "../types";

import {
  CustomFieldCell,
  useCustomFieldRecords,
  type CustomField,
} from "../components/CustomFields";

import RecordActions from "../components/RecordActions";

import InlineProjectDate from "../components/InlineProjectDate";
import ProjectPreviewDetails from "../components/ProjectPreviewDetails";
import PortfolioRules, {
  readRules,
  matchesRules,
} from "../components/PortfolioRules";
import QuickCreateProject from "../components/QuickCreateProject";
import DuplicateProjectDialog from "../components/DuplicateProjectDialog";

import { workspaceError } from "./workspaceTypes";

import "./ProjectsList.css";

const statuses = [
  "Draft",
  "Planned",
  "Active",
  "On Hold",
  "Completed",
  "Cancelled",
  "Archived",
];

const priorities = ["Low", "Medium", "High", "Critical"];
const attention = (p: PMSProject) => !p.is_archived && !["Completed","Cancelled","Archived"].includes(p.status) && (health(p) !== "On Track" || !p.owner_user_id && !p.manager_user_id || !p.due_date);
const endOfWeek = () => {const date=new Date();date.setDate(date.getDate()+(7-date.getDay())%7);return date.toLocaleDateString("en-CA");};

const progress = (p: PMSProject) =>
  p.calculated_progress ?? p.progress_percent ?? 0;

const today = () => new Date().toLocaleDateString("en-CA");

const overdue = (p: PMSProject) =>
  !!p.due_date &&
  p.due_date.slice(0, 10) < today() &&
  !["Completed", "Cancelled", "Archived"].includes(p.status) &&
  !p.is_archived;

const health = (p: PMSProject) =>
  p.blocked_task_count || p.health === "Blocked"
    ? "Blocked"
    : overdue(p)
      ? "Off Track"
      : p.overdue_task_count || ["At Risk", "Critical"].includes(p.health)
        ? "At Risk"
        : "On Track";

const projectLenses = ["board","timeline","gantt","calendar","workload","team","activity","mindmap","whiteboard"];
const projectViews: WorkspaceView[] = [
 {id:"list",label:"List",description:"Compare projects and edit inline",color:"#8b5cf6"},
 {id:"grid",label:"Gallery",icon:"gallery",description:"A beautiful overview of every project",color:"#d980ac"},
 {id:"board",label:"Board",description:"See projects by delivery status",color:"#6b8ee8"},
 {id:"gantt",label:"Gantt",description:"Project schedules and delivery windows",category:"Plan",color:"#ed8475"},
 {id:"timeline",label:"Timeline",description:"See your portfolio across time",category:"Plan",color:"#d7a350"},
 {id:"calendar",label:"Calendar",description:"Project deadlines in a monthly view",category:"Plan",color:"#e79c60"},
 {id:"workload",label:"Workload",description:"Project ownership and distribution",category:"Plan",color:"#24a595"},
 {id:"analytics",label:"Dashboard",icon:"dashboard",description:"Delivery health and portfolio insights",category:"Explore",color:"#9b70d0"},
 {id:"team",label:"Team",description:"Projects organised around their owners",category:"Explore",color:"#54a99c"},
 {id:"mindmap",label:"Mind map",description:"Explore portfolio relationships",category:"Explore",color:"#d476ac"},
 {id:"whiteboard",label:"Whiteboard",description:"Arrange project cards on a personal canvas",category:"Explore",color:"#bd9b4a"},
 {id:"activity",label:"Activity",description:"Recently updated projects",category:"Collaborate",color:"#4d9fe0"},
 {id:"channel",label:"Channel",description:"Conversations tied to project work",category:"Collaborate",href:"/pms/team-communication",color:"#8b5cf6"},
 {id:"docs",label:"Docs",description:"Project briefs and shared knowledge",category:"Collaborate",href:"/pms/docs",color:"#479ddd"},
 {id:"files",label:"Files",description:"Deliverables and project assets",category:"Collaborate",href:"/pms/files",color:"#7898b9"},
 {id:"form",label:"Forms",description:"Collect structured project requests",category:"Collaborate",href:"/pms/forms",color:"#9a76d7"},
];
const defaults = {
  tab: "All Projects",
  query: "",
  status: "",
  priority: "",
  client: "",
  owner: "",
  health: "",
  due: "",
  sort: "updated",
  view: "list",
  rules: "[]",
  match: "all",
  focus: "",
};

type Filters = typeof defaults;
function restoreFilters(value: unknown): Filters {
  try {
    const object = typeof value === "string" ? JSON.parse(value) : value;
    return Object.fromEntries(
      Object.entries(defaults).map(([key, fallback]) => [
        key,
        object && typeof object[key] === "string" ? object[key] : fallback,
      ]),
    ) as Filters;
  } catch {
    return { ...defaults };
  }
}

const read = <T,>(key: string, fallback: T): T => {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
};

const tabs = [
  "All Projects",
  "My Projects",
  "In Progress",
  "Completed",
  "On Hold",
  "Overdue",
  "Starred",
  "Archived",
];

function ProjectsList() {
  const navigate = useNavigate();
  const [urlParams] = useSearchParams();
  const workspaceScope = urlParams.get("workspace") || "all";
  const previewTimer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(previewTimer.current), []);
  function openProject(id: number) {
    clearTimeout(previewTimer.current);
    setPreviewId(undefined);
    navigate(`/pms/projects/${id}`);
  }
  function queuePreview(id: number) {
    clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => setPreviewId(id), 350);
  }
  const surfaceInteraction = (id: number) => ({
    onClick: (event: React.MouseEvent<HTMLElement>) => {
      if ((event.target as HTMLElement).closest("a,button,input,select,textarea,[role=button],[contenteditable=true]")) return;
      queuePreview(id);
    },
    onDoubleClick: (event: React.MouseEvent<HTMLElement>) => {
      if ((event.target as HTMLElement).closest("a,button,input,select,textarea,[role=button],[contenteditable=true]")) return;
      event.preventDefault();
      openProject(id);
    },
  });
  const projectName = (p: PMSProject) => (
    <button type="button" className="portfolio-project-name"
      aria-label={`Preview ${p.name}; double-click to open project`}
      onClick={(event) => { if (event.detail === 0) setPreviewId(p.id); else queuePreview(p.id); }}
      onDoubleClick={() => openProject(p.id)}
      onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); openProject(p.id); } }}
    >{p.name}</button>
  );
  const quickActions = (p: PMSProject) => (
    <div className="portfolio-quick-actions" role="group" aria-label={`Quick actions for ${p.name}`}>
      {actionChoices.includes("open") && <Link to={`/pms/projects/${p.id}`}>Open</Link>}
      {actionChoices.includes("task") && canCreateProject && p.can_manage_tasks && <Link to={`/pms/tasks/new?projectId=${p.id}`}>+ Add task</Link>}
      {actionChoices.includes("board") && <Link to={`/pms/projects/${p.id}/board`}>Task board</Link>}
      {actionChoices.includes("copy") && <button type="button" onClick={() => void navigator.clipboard.writeText(`${window.location.origin}/pms/projects/${p.id}`).then(() => setNotice("Project link copied"), () => setError("Could not copy project link"))}>Copy link</button>}
      {actionChoices.includes("duplicate") && canCreateProject && p.can_edit_project && <button type="button" onClick={() => setDuplicate(p)}>Duplicate</button>}
    </div>
  );
  const uid = useAuthStore((s) => s.user?.id);
  const actor=useAuthStore(s=>s.user),moduleGrant=actor?.access?.grants.project_management;
  const canEditProject=useModuleAction("edit");
  const canCreateProject=!!actor?.is_superuser||!!actor?.access&&!actor.access.managed||!!moduleGrant?.enabled&&moduleGrant.actions.includes("create");
  const canExportProject=!!actor?.is_superuser||!!actor?.access&&!actor.access.managed||!!moduleGrant?.enabled&&moduleGrant.actions.includes("export");
  const companyId = useAuthStore((s) => s.user?.access?.companyId);
  const generation = useRef(0);

  const key = `pms-project-portfolio:${companyId}:${uid || "anonymous"}:${workspaceScope}`;

  const { projects: allProjects, setProjects } = useProjectStore();
  const projects = useMemo(() => workspaceScope === "all" ? allProjects : allProjects.filter(project => String(project.workspace_id) === workspaceScope), [allProjects, workspaceScope]);

  const [filters, setFilters] = useState<Filters>(() => ({
    ...restoreFilters(read(key, {})),
  }));

  const [stars, setStars] = useState<number[]>(() => read(`${key}:stars`, []));

  const [saved, setSaved] = useState<
    {
      id: string;
      name: string;
      shared?: boolean;
      preferences: { module_filters: Record<string, string> };
    }[]
  >([]);

  const [canShare, setCanShare] = useState(false),
    [shareView, setShareView] = useState(false),
    [preferencesReady, setPreferencesReady] = useState(false);

  const preferencesModified = useRef<number>(read(`${key}:modified`, 0));
  const preferencesBase = "/pipeline-workspaces/project_management/portfolio";

  useEffect(() => {
    let active = true;
    setPreferencesReady(false);
    const local = restoreFilters(read(key, {}));
    setFilters({ ...defaults, ...local });
    setSearch(typeof local.query === "string" ? local.query : "");
    setStars(read<number[]>(`${key}:stars`, []));
    void api
      .get<{
        preferences: { module_filters: Record<string, string> };
        views: typeof saved;
        can_share: boolean;
      }>(`${preferencesBase}/views`)
      .then(({ data }) => {
        if (!active) return;
        setSaved(data.views);
        setCanShare(data.can_share);
        const values = data.preferences.module_filters;
        const preferLocal =
          read<number>(`${key}:modified`, 0) > Number(values?.modified || 0);
        if (values?.[`portfolio:${workspaceScope}`] && !preferLocal) {
          const f = restoreFilters(values[`portfolio:${workspaceScope}`]);
          setFilters({ ...defaults, ...f });
          setSearch(f.query || "");
        }
        if (values?.stars && !preferLocal) setStars(JSON.parse(values.stars));
        setPreferencesReady(true);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
      generation.current++;
    };
  }, [uid, companyId, workspaceScope]);

  useEffect(() => {
    if (!preferencesReady) return;
    preferencesModified.current = Date.now();
    try {
      localStorage.setItem(
        `${key}:modified`,
        String(preferencesModified.current),
      );
    } catch {
      /* Optional local cache. */
    }
    const timer = setTimeout(() => {
      void api
        .put(
          `${preferencesBase}/preferences`,
          {
            module_filters: {
              [`portfolio:${workspaceScope}`]: JSON.stringify(filters),
              stars: JSON.stringify(stars),
              modified: String(preferencesModified.current),
            },
          },
          { progress: false },
        )
        .catch((e) => setError(workspaceError(e)));
    }, 300);
    return () => clearTimeout(timer);
  }, [filters, stars, preferencesReady, workspaceScope]);

  async function saveView() {
    const name = viewName;
    if (!name?.trim() || saveViewLock.current) return;
    saveViewLock.current = true;
    setSavingView(true);
    try {
      const { data } = await api.post(`${preferencesBase}/views`, {
        name: name.trim(),
        shared: shareView,
        preferences: { module_filters: { portfolio: JSON.stringify(filters) } },
      });
      setSaved((v) => [...v, data]);
      setNotice("Project view saved");
      setViewName("");
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      saveViewLock.current = false;
      setSavingView(false);
    }
  }

  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const initialLoading = useInitialLoading(loading);

  const [busy, setBusy] = useState(false),
    [advanced, setAdvanced] = useState(false),
    [page, setPage] = useState(0);

  const [selected, setSelected] = useState<number[]>([]),
    [previewId, setPreviewId] = useState<number>();

  const [confirmation, setConfirmation] = useState<"archive" | "trash">();
  const [savingView, setSavingView] = useState(false);
  const saveViewLock = useRef(false);
  const preferenceContext = useRef(key);
  const [previewWidth, setPreviewWidth] = useState(() => read<number>(`${key}:preview-width`, 600));
  const [pinnedPreview, setPinnedPreview] = useState(false);
  const [recentProjects, setRecentProjects] = useState<number[]>(() => read(`${key}:recent`, []));
  const [editedProjects, setEditedProjects] = useState<number[]>(() => read(`${key}:edited`, []));
  const [pendingBulk, setPendingBulk] = useState<{patch: Parameters<typeof projectsAPI.update>[1]; message: string}>();
  const [bulkDue, setBulkDue] = useState("");
  const [retryEdit, setRetryEdit] = useState<{project: PMSProject; patch: Parameters<typeof projectsAPI.update>[1]}>();
  const [createStatus, setCreateStatus] = useState<PMSProject["status"]>("Active");
  const [actionChoices, setActionChoices] = useState<string[]>(() => read(`${key}:actions`, ["open", "task", "board", "copy", "duplicate"]));
  useEffect(() => { if(preferenceContext.current !== key)return; try { localStorage.setItem(`${key}:preview-width`, JSON.stringify(previewWidth)); localStorage.setItem(`${key}:actions`, JSON.stringify(actionChoices)); } catch {} }, [key, previewWidth, actionChoices]);
  useEffect(() => { if (!previewId || preferenceContext.current !== key) return; setRecentProjects(current => { const next = [previewId, ...current.filter(id => id !== previewId)].slice(0,20); try { localStorage.setItem(`${key}:recent`, JSON.stringify(next)); } catch {} return next; }); }, [previewId, key]);
  useEffect(() => { setPreviewWidth(read(`${key}:preview-width`,600)); setActionChoices(read(`${key}:actions`,["open","task","board","copy","duplicate"])); setRecentProjects(read(`${key}:recent`,[])); setEditedProjects(read(`${key}:edited`,[])); setPreviewId(undefined); preferenceContext.current=key; }, [key]);
  const [resizing, setResizing] = useState(false);
  useEffect(() => {
    if (!resizing) return;
    const move = (e: PointerEvent) =>
      setPreviewWidth(
        Math.min(
          window.innerWidth - 24,
          Math.max(360, window.innerWidth - e.clientX),
        ),
      );
    const end = () => setResizing(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
  }, [resizing]);
  const [viewName, setViewName] = useState("");
  const [renaming, setRenaming] = useState<number>();
  const [renameDraft, setRenameDraft] = useState("");
  const [creating, setCreating] = useState(false);
  const [duplicate, setDuplicate] = useState<PMSProject>();

  const [customFields, setCustomFields] = useState<CustomField[]>([]);

  const [hidden, setHidden] = useState<number[]>(() =>
    read(`${key}:columns`, []),
  );

  const shownFields = customFields.filter((f) => !hidden.includes(f.id));

  const [search, setSearch] = useState(filters.query);

  useEffect(() => {
    const timer = setTimeout(
      () => setFilters((f) => ({ ...f, query: search })),
      180,
    );
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(filters));
      localStorage.setItem(`${key}:stars`, JSON.stringify(stars));
      localStorage.setItem(`${key}:columns`, JSON.stringify(hidden));
    } catch {
      /* Browser storage can be disabled. */
    }
  }, [key, filters, stars, saved, hidden]);

  useEffect(()=>{
    const changed=(event:Event)=>{
      const change=(event as CustomEvent<RecordSaved>).detail;
      const {url,method,record}=change;
      if(!/^\/project-management\/projects(?:\/\d+)?$/.test(url))return;
      const removed=new Set(removedRecordIds(change,"/project-management/projects").map(String));
      if(removed.size){generation.current+=1;setProjects(useProjectStore.getState().projects.filter(row=>!removed.has(String(row.id))));setPreviewId(current=>current&&removed.has(String(current))?undefined:current);setSelected(current=>current.filter(id=>!removed.has(String(id))));return;}
      if(method==="delete"||!record?.id)return;
      const project=record as unknown as PMSProject;
      generation.current+=1;
      setProjects([project,...useProjectStore.getState().projects.filter(row=>row.id!==project.id)]);
    };
    window.addEventListener(recordSavedEvent,changed);
    return()=>window.removeEventListener(recordSavedEvent,changed);
  },[setProjects]);

  async function load() {
    const request = ++generation.current;
    const rows: PMSProject[] = [];

    for (let skip = 0; ; skip += 500) {
      const batch = await projectsAPI.list(skip, 500, undefined, true);
      rows.push(...batch);
      if (batch.length < 500) break;
    }

    if (request === generation.current) setProjects(rows);
  }

  useRefreshableEffect(() => {
    let active = true;
    setLoading(true);
    void load()
      .catch((e) => {
        if (active) setError(workspaceError(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    void api
      .get<{ fields: CustomField[] }>("/project-management/custom-fields")
      .then(({ data }) => {
        if (active)
          setCustomFields(data.fields.filter((f) => f.entity_type !== "task"));
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
      generation.current++;
    };
  }, [uid, companyId]);

  function markPreferenceChange() {
    preferencesModified.current = Date.now();
    try {
      localStorage.setItem(
        `${key}:modified`,
        String(preferencesModified.current),
      );
    } catch {
      /* Optional local cache. */
    }
  }
  function filter(field: keyof Filters, value: string) {
    markPreferenceChange();
    setFilters((f) => ({ ...f, [field]: value }));
    setPage(0);
    setSelected([]);
    if (field === "query") setSearch(value);
  }

  function matches(p: PMSProject, tab: string) {
    if (tab === "Archived") return p.is_archived || p.status === "Archived";

    if (p.is_archived || p.status === "Archived") return false;

    return tab === "My Projects"
      ? p.owner_user_id === uid ||
          p.manager_user_id === uid ||
          p.team?.some((m) => m.id === uid)
      : tab === "In Progress"
        ? p.status === "Active"
        : tab === "Overdue"
          ? overdue(p)
          : tab === "Starred"
            ? stars.includes(p.id)
            : tab === "All Projects" || p.status === tab;
  }

  const filtered = useMemo(
    () =>
      projects
        .filter(
          (p) =>
            (!workspaceScope || workspaceScope === "all" || String(p.workspace_id) === workspaceScope) &&
            matches(p, filters.tab) &&
            (!filters.focus || (filters.focus === "attention" ? attention(p) : filters.focus === "week" ? !!p.due_date && !["Completed","Cancelled","Archived"].includes(p.status) && p.due_date.slice(0,10) >= today() && p.due_date.slice(0,10) <= endOfWeek() : filters.focus === "recent" ? recentProjects.includes(p.id) : editedProjects.includes(p.id))) &&
            matchesRules(p, readRules(filters.rules), filters.match) &&
            (!filters.status || p.status === filters.status) &&
            (!filters.priority || p.priority === filters.priority) &&
            (!filters.client || String(p.client_id) === filters.client) &&
            (!filters.owner ||
              String(p.owner_user_id || p.manager_user_id) === filters.owner) &&
            (!filters.health || health(p) === filters.health) &&
            (!filters.due ||
              (!!p.due_date && p.due_date.slice(0, 10) <= filters.due)) &&
            `${p.name} ${p.project_key} ${p.description || ""} ${p.client_name || ""} ${p.owner_name || ""} ${(p.team || []).map((m) => m.name).join(" ")}`
              .toLowerCase()
              .includes(filters.query.toLowerCase()),
        )
        .sort((a, b) =>
          filters.sort === "name"
            ? a.name.localeCompare(b.name)
            : filters.sort === "due"
              ? (a.due_date || "9999").localeCompare(b.due_date || "9999")
              : filters.sort === "progress"
                ? progress(b) - progress(a)
                : (b.updated_at || b.created_at).localeCompare(
                    a.updated_at || a.created_at,
                  ),
        ),
    [projects, filters, uid, stars, workspaceScope, recentProjects, editedProjects],
  );

  useEffect(() => {
    setPage((p) =>
      Math.min(p, Math.max(0, Math.ceil(filtered.length / 30) - 1)),
    );
  }, [filtered.length]);
  const activeFilters = Object.entries(filters).filter(
    ([field, value]) =>
      !["view", "sort", "match", "tab"].includes(field) &&
      value !== "" &&
      value !== "[]",
  );
  const rows = filtered.slice(page * 30, page * 30 + 30);

  const custom = useCustomFieldRecords(
    "project",
    rows.map((p) => p.id),
  );

  const preview = projects.find((p) => p.id === previewId);

  const active = projects.filter(
    (p) => !p.is_archived && p.status !== "Archived",
  );

  const taskTotal = active.reduce((n, p) => n + (p.task_count || 0), 0);

  const overall = taskTotal
    ? Math.round(
        (100 * active.reduce((n, p) => n + (p.completed_task_count || 0), 0)) /
          taskTotal,
      )
    : null;

  async function update(
    p: PMSProject,
    patch: Parameters<typeof projectsAPI.update>[1],
  ) {
    if (busy || !(canEditProject&&p.can_edit_project)) return false;
    setBusy(true);
    setError("");
    setNotice(`Saving ${p.name}…`);

    try {
      const updated = await projectsAPI.update(p.id, patch);
      setProjects(
        useProjectStore.getState().projects.map((row) =>
          row.id === p.id
            ? {
                ...row,
                ...patch,
                owner_user_id:
                  patch.owner_user_id === null
                    ? undefined
                    : (patch.owner_user_id ?? row.owner_user_id),
                ...(patch.owner_user_id !== undefined
                  ? {
                      owner_name:
                        p.team?.find((m) => m.id === patch.owner_user_id)
                          ?.name || null,
                    }
                  : {}),
                status: updated.status,
                priority: updated.priority,
                start_date:
                  patch.start_date === null
                    ? undefined
                    : (patch.start_date ?? row.start_date),
                due_date:
                  patch.due_date === null
                    ? undefined
                    : (patch.due_date ?? row.due_date),
                updated_at: new Date().toISOString(),
              }
            : row,
        ),
      );
      setRetryEdit(undefined);
      setEditedProjects(current => { const next = [...new Set([p.id, ...current])]; try { localStorage.setItem(`${key}:edited`, JSON.stringify(next)); } catch {} return next; });
      if (patch.status !== undefined || patch.owner_user_id !== undefined) {
        const inverse = { ...(patch.status !== undefined ? {status: p.status} : {}), ...(patch.owner_user_id !== undefined ? {owner_user_id: p.owner_user_id ?? p.manager_user_id ?? null} : {}) };
        savedWithUndo(`${p.name} updated`, async () => { await projectsAPI.update(p.id, inverse); await load(); });
      }
      setNotice(`${p.name} updated`);
      return true;
    } catch (e) {
      setRetryEdit({project:p, patch});
      setNotice("Save failed. Your edit is kept for retry.");
      setError(workspaceError(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  function setPendingBulkAction(patch: Parameters<typeof projectsAPI.update>[1], message: string) { setPendingBulk({patch, message}); }
  async function bulk(
    patch: Parameters<typeof projectsAPI.update>[1],
    message: string,
  ) {
    setBusy(true);
    setError("");
    const failures: string[] = [];
    let done = 0;

    for (const id of selected) {
      const p = projects.find((row) => row.id === id);
      if (!(canEditProject&&p?.can_edit_project)) {
        failures.push(`${p?.name || id}: no edit permission`);
        continue;
      }
      try {
        await projectsAPI.update(id, patch);
        setProjects(
          useProjectStore.getState().projects.map((row) =>
            row.id === id
              ? {
                  ...row,
                  ...patch,
                  ...(patch.owner_user_id !== undefined
                    ? {
                        owner_name:
                          p.team?.find((m) => m.id === patch.owner_user_id)
                            ?.name || null,
                      }
                    : {}),
                  owner_user_id:
                    patch.owner_user_id === null
                      ? undefined
                      : (patch.owner_user_id ?? row.owner_user_id),
                  start_date:
                    patch.start_date === null
                      ? undefined
                      : (patch.start_date ?? row.start_date),
                  due_date:
                    patch.due_date === null
                      ? undefined
                      : (patch.due_date ?? row.due_date),
                  updated_at: new Date().toISOString(),
                }
              : row,
          ),
        );
        done++;
      } catch (e) {
        failures.push(`${p.name}: ${workspaceError(e)}`);
      }
    }

    setNotice(`${message}: ${done} of ${selected.length} saved.`);
    setError(failures.join("; "));
    setSelected([]);
    setBusy(false);
  }

  async function deleteSelected() {
    setBusy(true);
    setError("");
    const failures: string[] = [];
    let done = 0;
    for (const id of selected) {
      const p = projects.find((p) => p.id === id);
      if (!(canEditProject&&p?.can_edit_project)) {
        failures.push(`${p?.name || id}: no edit permission`);
        continue;
      }
      try {
        await projectsAPI.delete(id);
        setProjects(
          useProjectStore.getState().projects.filter((p) => p.id !== id),
        );
        done++;
      } catch (e) {
        failures.push(`${p.name}: ${workspaceError(e)}`);
      }
    }
    setNotice(`${done} of ${selected.length} moved to Trash`);
    setError(failures.join("; "));
    setSelected([]);
    setBusy(false);
  }
  async function exportCSV() {
    if(!canExportProject)return;
    setError("");

    const fields = [
      "project_key",
      "name",
      "client_name",
      "owner_name",
      "status",
      "priority",
      "start_date",
      "due_date",
    ] as const;

    const data = filtered.filter(
      (p) => !selected.length || selected.includes(p.id),
    );

    let values = custom.records;

    if (shownFields.length) {
      try {
        values = {};

        for (let offset = 0; offset < data.length; offset += 100) {
          const response = await api.post<{ records: typeof values }>(
            "/project-management/custom-fields/records",
            {
              entity: "project",
              ids: data.slice(offset, offset + 100).map((p) => p.id),
            },
          );

          Object.assign(values, response.data.records);
        }
      } catch (e) {
        setError(workspaceError(e));
        return;
      }
    }

    const exportFields = [
      ...fields,
      "progress",
      "health",
      ...shownFields.map((f) => `${f.name} (${f.id})`),
    ];
    const exportRows = data.map((p) => ({
      ...Object.fromEntries(fields.map((f) => [f, p[f]])),
      progress: progress(p),
      health: health(p),
      ...Object.fromEntries(
        shownFields.map((f) => [
          `${f.name} (${f.id})`,
          values[p.id]?.fields.find((v) => v.id === f.id)?.value ?? "",
        ]),
      ),
    }));
    downloadBlob(
      new Blob(["\uFEFF", csvText(exportRows, exportFields, true)], {
        type: "text/csv;charset=utf-8",
      }),
      "projects.csv",
    );
    setNotice(`${data.length} projects exported to projects.csv.`);
  }

  const progressBar = (p: PMSProject) => (
    <button
      className="portfolio-progress"
      title={`${p.completed_task_count || 0} of ${p.task_count || 0} tasks complete. ${p.completed_milestone_count || 0} of ${p.milestone_count || 0} milestones complete. Click for details.`}
      onClick={() => setPreviewId(p.id)}
    >
      <span>
        <i
          style={{
            width: `${Math.max(0, Math.min(100, progress(p)))}%`,
            background: progress(p) >= 80 ? "#16a34a" : undefined,
          }}
        />
      </span>
      <b>{progress(p)}%</b>
    </button>
  );

  const favorite = (p: PMSProject) => (
    <button
      className={`portfolio-star ${stars.includes(p.id) ? "is-starred" : ""}`}
      aria-label={`${stars.includes(p.id) ? "Unstar" : "Star"} ${p.name}`}
      aria-pressed={stars.includes(p.id)}
      onClick={() => {
        markPreferenceChange();
        setStars((s) =>
          s.includes(p.id) ? s.filter((id) => id !== p.id) : [...s, p.id],
        );
      }}
    >
      <Star size={16} />
    </button>
  );

  const previewContent = preview && (
            <>
              <h2 className="text-lg font-semibold">{preview.name}</h2>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Preview navigation">
                <Button variant="outline" disabled={filtered.findIndex(p => p.id === preview.id) <= 0} onClick={() => setPreviewId(filtered[filtered.findIndex(p => p.id === preview.id)-1]?.id)}>Previous project</Button>
                <Button variant="outline" disabled={filtered.findIndex(p => p.id === preview.id) < 0 || filtered.findIndex(p => p.id === preview.id) >= filtered.length-1} onClick={() => setPreviewId(filtered[filtered.findIndex(p => p.id === preview.id)+1]?.id)}>Next project</Button>
                <Button variant="outline" onClick={() => setPinnedPreview(p => !p)}>{pinnedPreview ? "Use modal preview" : "Keep preview open"}</Button>
              </div>
              {(canEditProject&&preview.can_edit_project) && <div className="flex flex-wrap gap-2">
                <label>Status <NativeSelect aria-label="Preview status" disabled={busy} value={preview.status} onChange={e => void update(preview,{status:e.target.value as PMSProject["status"]})}>{statuses.map(v => <option key={v}>{v}</option>)}</NativeSelect></label>
                <label>Priority <NativeSelect aria-label="Preview priority" disabled={busy} value={preview.priority} onChange={e => void update(preview,{priority:e.target.value as PMSProject["priority"]})}>{priorities.map(v => <option key={v}>{v}</option>)}</NativeSelect></label>
                <label>Owner <NativeSelect aria-label="Preview owner" disabled={busy} value={preview.owner_user_id || preview.manager_user_id || ""} onChange={e => void update(preview,{owner_user_id:Number(e.target.value)||null})}><option value="">Unassigned</option>{preview.team?.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</NativeSelect></label>
                <InlineProjectDate label="Preview deadline" value={preview.due_date} disabled={busy} overdue={overdue(preview)} onSave={value => update(preview,{due_date:value})}/>
              </div>}
              <p className="text-sm text-muted-foreground">
                {preview.project_key} ·{" "}
                {preview.client_name || "No client linked"}
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge className={statusColor(preview.status)}>
                  {preview.status}
                </Badge>
                <Badge data-priority-badge data-priority={preview.priority} variant="outline">{preview.priority}</Badge>
                <Badge variant="outline">{health(preview)}</Badge>
                <p className="text-xs text-muted-foreground">{preview.blocked_task_count ? `${preview.blocked_task_count} blocked tasks` : overdue(preview) ? "Project deadline has passed" : preview.overdue_task_count ? `${preview.overdue_task_count} overdue tasks` : ["At Risk","Critical","Blocked"].includes(preview.health) ? `Reported health: ${preview.health}` : "No delivery warnings"}</p>
              </div>
              <RichTextContent
                value={preview.description || "No description added yet."}
              />
              {progressBar(preview)}
              <dl className="portfolio-preview-facts">
                <div>
                  <dt>Owner</dt>
                  <dd>{preview.owner_name || "Unassigned"}</dd>
                </div>
                <div>
                  <dt>Timeline</dt>
                  <dd>
                    {formatDate(preview.start_date || null)} →{" "}
                    {formatDate(preview.due_date || null)}
                  </dd>
                </div>
                <div>
                  <dt>Tasks</dt>
                  <dd>
                    {preview.completed_task_count || 0} complete /{" "}
                    {preview.task_count || 0} total
                  </dd>
                </div>
                <div>
                  <dt>Delivery issues</dt>
                  <dd>
                    {preview.overdue_task_count || 0} overdue ·{" "}
                    {preview.blocked_task_count || 0} blocked
                  </dd>
                </div>
                <div>
                  <dt>Milestones</dt>
                  <dd>
                    {preview.completed_milestone_count || 0} complete /{" "}
                    {preview.milestone_count || 0} total
                  </dd>
                </div>
                <div>
                  <dt>Team</dt>
                  <dd>
                    {preview.team
                      ?.map((m) => `${m.name} (${m.role})`)
                      .join(", ") || "No members assigned"}
                  </dd>
                </div>
              </dl>
              <ProjectPreviewDetails key={preview.id} projectId={preview.id} canManage={!!preview.can_manage_tasks} onChanged={load} />
              <div className="flex flex-wrap gap-2">
                {preview.can_manage_tasks && (
                  <Button variant="outline" asChild>
                    <Link to={`/pms/tasks/new?projectId=${preview.id}`}>
                      Add Task
                    </Link>
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={() => {
                    void navigator.clipboard
                      .writeText(
                        `${window.location.origin}/pms/projects/${preview.id}`,
                      )
                      .then(() =>
                        setNotice(
                          "Project link copied. Recipients still need project access.",
                        ),
                      )
                      .catch(() => setError("Unable to copy project link."));
                  }}
                >
                  Copy link
                </Button>
                <Button variant="outline" asChild>
                  <Link to={`/pms/projects/${preview.id}/billing`}>
                    Financials
                  </Link>
                </Button>
                <Button asChild>
                  <Link to={`/pms/projects/${preview.id}`}>Open Project</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link to={`/pms/projects/${preview.id}/board`}>
                    Task board
                  </Link>
                </Button>
                {(canEditProject&&preview.can_edit_project) && (
                  <Button variant="outline" asChild>
                    <Link to={`/pms/projects/${preview.id}/edit`}>
                      Edit Project
                    </Link>
                  </Button>
                )}
                {(canEditProject&&preview.can_edit_project) && (
                  <Button
                    variant="outline"
                    onClick={() => setDuplicate(preview)}
                  >
                    Duplicate
                  </Button>
                )}
                <Button variant="outline" asChild>
                  <Link to={`/pms/projects/${preview.id}/members`}>Team</Link>
                </Button>
              </div>
            </>
          );

  return (
    <main
      className={`project-portfolio ${advanced ? "portfolio-filters-expanded" : ""}`}
    >

      <header className="portfolio-header">
        <div className="portfolio-heading">
          <span className="portfolio-logo">
            <FolderKanban size={25} />
          </span>
          <div>
            <h1>Projects</h1>
            <p>
              Manage projects, teams, deadlines, milestones, and delivery risk.
            </p>
          </div>
        </div>
        <div className="portfolio-actions">
          <Button variant="outline" asChild>
            <Link to="/pms/import-data">
              <Upload size={15} />
              Import
            </Link>
          </Button>
          <Button
            title="Export filtered projects as CSV"
            variant="outline"
            onClick={exportCSV}
            disabled={!canExportProject||loading}
          >
            <Download size={15} />
            Export
          </Button>
          <Button variant="outline" asChild>
            <Link to="/pms/trash?type=projects">
              <Trash2 size={15} />
              Trash
            </Link>
          </Button>
          <Button aria-label="New Project" disabled={!canCreateProject} onClick={() => {setCreateStatus("Active");setCreating(true);}}>
            <Plus size={16} />
            <span className="portfolio-new-desktop">New Project</span>
            <span className="portfolio-new-mobile" aria-hidden="true">
              New
            </span>
          </Button>
        </div>
      </header>

      <section className="portfolio-kpis" aria-label="Portfolio summary">
        {[
          {
            label: "Total Projects",
            value: active.length,
            tab: "All Projects",
            Icon: FolderKanban,
            tone: "violet",
          },

          {
            label: "In Progress",
            value: active.filter((p) => p.status === "Active").length,
            tab: "In Progress",
            Icon: PlayCircle,
            tone: "blue",
          },

          {
            label: "Completed",
            value: active.filter((p) => p.status === "Completed").length,
            tab: "Completed",
            Icon: CheckCircle2,
            tone: "green",
          },

          {
            label: "On Hold",
            value: active.filter((p) => p.status === "On Hold").length,
            tab: "On Hold",
            Icon: PauseCircle,
            tone: "amber",
          },

          {
            label: "Overdue",
            value: active.filter(overdue).length,
            tab: "Overdue",
            Icon: AlertCircle,
            tone: "red",
          },
        ].map(({ label, value, tab, Icon, tone }) => (
          <button
            key={label}
            className={`portfolio-kpi ${tone}`}
            onClick={() => {
              setFilters({
                ...defaults,
                tab,
                view: filters.view,
                sort: filters.sort,
              });
              setSearch("");
              setPage(0);
              setSelected([]);
            }}
            aria-pressed={filters.tab === tab}
          >
            <span className="kpi-icon">
              <Icon size={24} />
            </span>
            <span>
              <small>{label}</small>
              <strong>{initialLoading ? "—" : value}</strong>
            </span>
          </button>
        ))}
        <button
          className="portfolio-kpi"
          onClick={() => {
            filter("view", "analytics");
          }}
          title="Completed tasks / all tasks, weighted by task count. Projects without tasks are excluded."
        >
          <span
            className="portfolio-ring"
            style={{
              background: `conic-gradient(#16a34a ${(overall || 0) * 3.6}deg, var(--portfolio-soft) 0deg)`,
            }}
          >
            <b>{overall === null ? "—" : `${overall}%`}</b>
          </span>
          <span>
            <small>Overall Progress</small>
            <em>{taskTotal} tasks across portfolio</em>
          </span>
        </button>
      </section>

      <section className="portfolio-workspace">
        <div className="portfolio-viewbar">
          <nav aria-label="Project views">
            {tabs.map((tab) => (
              <button
                key={tab}
                className={filters.tab === tab ? "active" : ""}
                onClick={() => filter("tab", tab)}
              >
                {tab}
                <span>{projects.filter((p) => matches(p, tab)).length}</span>
              </button>
            ))}
          </nav>

        </div>

        <WorkspaceViewBar scope="pms-projects" label="Portfolio views" active={filters.view} views={projectViews} onChange={view => filter("view", view)} primary={["list","grid","board","gantt","timeline","calendar","analytics"]}/>
        <div className="portfolio-filters">
          <label className="portfolio-search">
            <Search size={17} />
            <Input
              aria-label="Search projects"
              placeholder="Search projects, codes, clients, people…"
              value={search}
              onChange={(e) => {
                markPreferenceChange();
                setSearch(e.target.value);
                setPage(0);
                setSelected([]);
              }}
            />
          </label>
          <NativeSelect
            aria-label="Filter status"
            value={filters.status}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="">Status</option>
            {statuses.map((s) => (
              <option key={s} value={s}>{s} ({projects.filter(p => p.status === s).length})</option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Filter owner"
            value={filters.owner}
            onChange={(e) => filter("owner", e.target.value)}
          >
            <option value="">Owner</option>
            {Array.from(
              new Map(
                projects
                  .filter((p) => p.owner_user_id || p.manager_user_id)
                  .map((p) => [
                    p.owner_user_id || p.manager_user_id,
                    p.owner_name ||
                      `User #${p.owner_user_id || p.manager_user_id}`,
                  ]),
              ).entries(),
            ).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Filter priority"
            value={filters.priority}
            onChange={(e) => filter("priority", e.target.value)}
          >
            <option value="">Priority</option>
            {priorities.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="Filter client"
            value={filters.client}
            onChange={(e) => filter("client", e.target.value)}
          >
            <option value="">Client</option>
            {Array.from(
              new Map(
                projects
                  .filter((p) => p.client_id)
                  .map((p) => [
                    p.client_id,
                    p.client_name || `Client #${p.client_id}`,
                  ]),
              ).entries(),
            ).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </NativeSelect>
          <Button
            variant="outline"
            onClick={() => setAdvanced((v) => !v)}
            aria-expanded={advanced}
          >
            <SlidersHorizontal size={15} />
            More filters
          </Button>
          <NativeSelect
            aria-label="Sort projects"
            value={filters.sort}
            onChange={(e) => filter("sort", e.target.value)}
          >
            <option value="updated">Last updated</option>
            <option value="name">Project name</option>
            <option value="due">Due date</option>
            <option value="progress">Progress</option>
          </NativeSelect>
          <details className="portfolio-view-options"><summary><SlidersHorizontal size={14}/>View options</summary><div className="portfolio-shortcuts flex flex-wrap items-center gap-2 py-2">
          <label>Focus <NativeSelect aria-label="Project focus" value={filters.focus} onChange={e => filter("focus", e.target.value)}>
            <option value="">All projects</option><option value="attention">Needs attention ({projects.filter(attention).length})</option><option value="week">Due this week</option><option value="recent">Recently viewed ({recentProjects.length})</option><option value="edited">Updated by me in this browser ({editedProjects.length})</option>
          </NativeSelect></label>
          <details><summary>Quick action buttons</summary><div className="flex flex-wrap gap-3 p-2">{["open","task","board","copy","duplicate"].map(action => <label key={action}><input type="checkbox" checked={actionChoices.includes(action)} onChange={e => setActionChoices(current => e.target.checked ? [...current,action] : current.filter(a => a !== action))}/> {action}</label>)}</div></details>
          {!!saved.length && <div role="group" aria-label="Saved view shortcuts">{saved.slice(0,5).map(view => <button type="button" key={view.id} className="rounded border px-2 py-1" onClick={() => {const f=restoreFilters(view.preferences.module_filters.portfolio);setFilters(f);setSearch(f.query);setPage(0);setSelected([]);}}>{view.name}</button>)}</div>}
        </div></details>
        </div>

        {advanced && (
          <div className="portfolio-advanced">
            <label>
              Health
              <NativeSelect
                aria-label="Project health"
                value={filters.health}
                onChange={(e) => filter("health", e.target.value)}
              >
                <option value="">All health</option>
                {["On Track", "At Risk", "Off Track", "Blocked"].map((h) => (
                  <option key={h}>{h}</option>
                ))}
              </NativeSelect>
            </label>
            <label>
              Due on or before
              <Input
                type="date"
                aria-label="Due on or before"
                value={filters.due}
                onChange={(e) => filter("due", e.target.value)}
              />
            </label>
            <label>
              Personal views
              <NativeSelect
                value=""
                aria-label="Saved project views"
                onChange={(e) => {
                  if (!e.target.value) return;
                  markPreferenceChange();
                  const view = saved[Number(e.target.value)];
                  if (view) {
                    const f = {
                      ...defaults,
                      ...restoreFilters(
                        view.preferences.module_filters.portfolio,
                      ),
                    };
                    setFilters(f);
                    setNotice(`Loaded view: ${view.name}`);
                    setSearch(f.query);
                    setPage(0);
                  }
                }}
              >
                <option value="">Load saved view</option>
                {saved.map((s, i) => (
                  <option key={i} value={i}>
                    {s.name}
                    {s.shared ? " · Team" : ""}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <Input
              aria-label="Saved view name"
              className="max-w-44"
              placeholder="Name this view"
              maxLength={80}
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
            />
            <Button
              variant="outline"
              onClick={() => void saveView()}
              disabled={!preferencesReady || !viewName.trim() || savingView}
            >
              Save view
            </Button>
            {canShare && (
              <label>
                <input
                  type="checkbox"
                  checked={shareView}
                  onChange={(e) => setShareView(e.target.checked)}
                />
                Share with team
              </label>
            )}
            <Button
              variant="ghost"
              onClick={() => {
                setFilters(defaults);
                setSearch("");
                setPage(0);
                setSelected([]);
              }}
            >
              Reset to default
            </Button>
            <Link
              className="text-sm text-primary underline"
              to="/pms/management?view=projects"
            >
              Advanced team management
            </Link>
            <PortfolioRules
              rules={readRules(filters.rules)}
              mode={filters.match}
              onChange={(rules) => filter("rules", JSON.stringify(rules))}
              onMode={(mode) => filter("match", mode)}
            />
            <details>
              <summary>Custom columns</summary>
              <div className="flex flex-wrap gap-3 py-2">
                {customFields.map((f) => (
                  <label key={f.id}>
                    <input
                      type="checkbox"
                      checked={!hidden.includes(f.id)}
                      onChange={(e) =>
                        setHidden((v) =>
                          e.target.checked
                            ? v.filter((id) => id !== f.id)
                            : [...v, f.id],
                        )
                      }
                    />
                    {f.name}
                  </label>
                ))}
                <Link to="/pms/custom-fields?entity=project&create=1">
                  Add custom column
                </Link>
              </div>
            </details>
          </div>
        )}

        {!!activeFilters.length && (
          <div className="portfolio-active-filters" aria-label="Active filters">
            <span>{filtered.length} matching projects</span>
            {activeFilters.map(([field, value]) => (
              <button
                key={field}
                onClick={() =>
                  filter(field as keyof Filters, field === "rules" ? "[]" : "")
                }
                aria-label={`Clear ${field} filter`}
              >
                {field === "rules"
                  ? `${readRules(value).length} conditions`
                  : field === "query"
                    ? `Search: ${value}`
                    : `${field}: ${value}`}{" "}
                <span aria-hidden="true">×</span>
              </button>
            ))}
            <button
              className="portfolio-clear-filters"
              onClick={() => {
                setFilters((f) => ({
                  ...defaults,
                  view: f.view,
                  sort: f.sort,
                  tab: f.tab,
                }));
                setSearch("");
                setPage(0);
                setSelected([]);
              }}
            >
              Clear all
            </button>
          </div>
        )}
        {(error || custom.error) && (
          <p className="portfolio-error" role="alert">
            {error || custom.error}{" "}
            <button
              onClick={() => {
                setError("");
                custom.reload();
                void load().catch((e) => setError(workspaceError(e)));
              }}
            >
              Retry
            </button>
          </p>
        )}
        {notice && (
          <p className="portfolio-notice" role="status">
            {notice}
            {retryEdit && <button type="button" disabled={busy} onClick={() => void update(retryEdit.project,retryEdit.patch)}>Retry saved edit</button>}
          </p>
        )}

        {!!selected.length && (
          <div className="portfolio-bulk">
            <b>{selected.length} selected</b>
            <label>New deadline <Input aria-label="Bulk deadline" type="date" value={bulkDue} onChange={e => setBulkDue(e.target.value)}/></label><Button variant="outline" disabled={busy || !bulkDue} onClick={() => setPendingBulk({patch:{due_date:bulkDue},message:"Deadline updated"})}>Review deadline change</Button>
            <NativeSelect
              aria-label="Bulk owner"
              value=""
              disabled={busy}
              onChange={(e) =>
                setPendingBulkAction(
                  { owner_user_id: Number(e.target.value) },
                  "Owner updated",
                )
              }
            >
              <option value="">Change owner…</option>
              {Array.from(
                new Map(
                  projects.flatMap((p) =>
                    (p.team || []).map((m) => [m.id, m.name] as const),
                  ),
                ).entries(),
              ).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Bulk status"
              disabled={busy}
              value=""
              onChange={(e) =>
                setPendingBulkAction(
                  { status: e.target.value as CreateProjectInput["status"] },
                  "Status updated",
                )
              }
            >
              <option value="">Change status…</option>
              {statuses
                .filter((s) => s !== "Archived")
                .map((s) => (
                  <option key={s}>{s}</option>
                ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Bulk priority"
              value=""
              disabled={busy}
              onChange={(e) =>
                setPendingBulkAction(
                  {
                    priority: e.target.value as CreateProjectInput["priority"],
                  },
                  "Priority updated",
                )
              }
            >
              <option value="">Change priority…</option>
              {priorities.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </NativeSelect>
            <Button variant="outline" disabled={!canExportProject||busy} onClick={exportCSV}>
              Export selected
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirmation("archive")}
            >
              Archive
            </Button>
            {filters.tab === "Archived" && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  setPendingBulkAction(
                    { is_archived: false, status: "Active" },
                    "Restored",
                  )
                }
              >
                Restore
              </Button>
            )}
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirmation("trash")}
            >
              Move to Trash
            </Button>
            <Button
              variant="ghost"
              onClick={() => setSelected([])}
              disabled={busy}
            >
              Clear selection
            </Button>
          </div>
        )}

        {initialLoading ? (
          <LoadingState label="Loading Projects" variant="cards"/>
        ) : projectLenses.includes(filters.view) ? <RecordLensViews scope="pms-projects" view={filters.view} records={filtered.map(project => ({id:String(project.id),title:project.name,subtitle:project.client_name || "Internal project",status:project.status,owner:project.owner_name || "Unassigned",progress:progress(project),start:project.start_date,due:project.due_date,updated:project.updated_at,tags:[health(project),project.priority]}))} statuses={statuses} canMove={record => canEditProject && !busy && !!filtered.find(project => String(project.id) === record.id)?.can_edit_project} onMove={(record,status) => {const project=filtered.find(project => String(project.id) === record.id);if(project?.can_edit_project && !busy)void update(project,{status:status as PMSProject["status"]});}} onOpen={record => setPreviewId(Number(record.id))}/> : filters.view === "analytics" ? (
          <div className="portfolio-analytics">
            <div>
              <h2>Projects by status</h2>
              {statuses.map((s) => {
                const count = filtered.filter((p) => p.status === s).length;
                return (
                  <button
                    key={s}
                    onClick={() => {
                      filter("status", s);
                      filter("view", "list");
                    }}
                  >
                    <span>{s}</span>
                    <i
                      style={{
                        width: `${filtered.length ? (count / filtered.length) * 100 : 0}%`,
                      }}
                    />
                    <b>{count}</b>
                  </button>
                );
              })}
            </div>
            <div>
              <h2>Delivery health</h2>
              {["On Track", "At Risk", "Off Track", "Blocked"].map((h) => (
                <button
                  key={h}
                  onClick={() => {
                    filter("health", h);
                    filter("view", "list");
                  }}
                >
                  <span>{h}</span>
                  <b>{filtered.filter((p) => health(p) === h).length}</b>
                </button>
              ))}
              <p>
                Health uses blocked tasks, overdue project and task dates, and
                recorded project health. Progress follows task-count completion;
                projects without tasks retain their recorded progress.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div
              className={
                filters.view === "list" ? "portfolio-table-wrap" : "hidden"
              }
            >
              <GridTable
                gridId="pms-project-portfolio"
                variant="matrix"
                defaultGroupBy="Status"
                defaultHiddenColumns={["Start date","Health"]}
                groupCreate={canShare ? {field:"Status",label:"Add project",onCreate:value => {setCreateStatus(value as PMSProject["status"]);setCreating(true);}} : undefined}
                className="portfolio-table"
              >
                <thead>
                  <tr>
                    <th>
                      <input
                        aria-label="Select visible editable projects"
                        type="checkbox"
                        checked={
                          rows.some((p) => (canEditProject&&p.can_edit_project)) &&
                          rows
                            .filter((p) => (canEditProject&&p.can_edit_project))
                            .every((p) => selected.includes(p.id))
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? rows
                                  .filter((p) => (canEditProject&&p.can_edit_project))
                                  .map((p) => p.id)
                              : [],
                          )
                        }
                      />
                    </th>
                    <th>Project</th>
                    <th>Client</th>
                    <th>Owner / Team</th>
                    <th>Progress</th>
                    <th>Start date</th>
                    <th>Due date</th>
                    <th>Priority</th>
                    <th>Health</th>
                    <th>Status</th>
                    {shownFields.map((f) => (
                      <th key={f.id}>{f.name}</th>
                    ))}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr data-priority-row data-priority={p.priority}
                      key={p.id}
                      className={selected.includes(p.id) ? "is-selected" : ""}
                      {...surfaceInteraction(p.id)}
                    >
                      <td>
                        <input
                          aria-label={`Select ${p.name}`}
                          title={!(canEditProject&&p.can_edit_project) ? "You do not have permission to edit this project" : busy ? "Wait for the current save" : "Select project for bulk changes"}
                          disabled={!(canEditProject&&p.can_edit_project) || busy}
                          type="checkbox"
                          checked={selected.includes(p.id)}
                          onChange={(e) =>
                            setSelected((v) =>
                              e.target.checked
                                ? [...v, p.id]
                                : v.filter((id) => id !== p.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        <div className="portfolio-project-cell">
                          <span aria-hidden="true"><RecordStatusIcon label={p.status} field="Status"/></span>
                          <div>
                            {renaming === p.id ? (
                              <form
                                className="flex items-center gap-1"
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  if (renameDraft.trim())
                                    void update(p, {
                                      name: renameDraft.trim(),
                                    }).then((saved) => {
                                      if (saved) setRenaming(undefined);
                                    });
                                }}
                              >
                                <Input
                                  autoFocus
                                  aria-label={`New name for ${p.name}`}
                                  maxLength={180}
                                  value={renameDraft}
                                  onChange={(e) =>
                                    setRenameDraft(e.target.value)
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === "Escape")
                                      setRenaming(undefined);
                                  }}
                                />
                                <Button
                                  size="sm"
                                  disabled={busy || !renameDraft.trim()}
                                >
                                  Save
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setRenaming(undefined)}
                                >
                                  Cancel
                                </Button>
                              </form>
                            ) : (
                              <>
                                {projectName(p)}
                                {(canEditProject&&p.can_edit_project) && (
                                  <button
                                    className="portfolio-rename"
                                    title="Rename project"
                                    onClick={() => {
                                      setRenaming(p.id);
                                      setRenameDraft(p.name);
                                    }}
                                  >
                                    Rename
                                  </button>
                                )}
                              </>
                            )}
                            <small>{p.project_key}</small>
                          </div>
                        </div>
                      </td>
                      <td>{p.client_name || "—"}</td>
                      <td>
                        <div className="portfolio-owner-assignment"><span className="portfolio-owner-avatar" aria-hidden="true" title={p.owner_name || "Unassigned"}>{(p.owner_name || "?").slice(0,1).toUpperCase()}</span>
                        {(canEditProject&&p.can_edit_project) ? (
                          <NativeSelect
                            className="portfolio-owner"
                            aria-label={`Owner for ${p.name}`}
                            disabled={busy}
                            value={p.owner_user_id || p.manager_user_id || ""}
                            onChange={(e) =>
                              void update(p, {
                                owner_user_id: Number(e.target.value) || null,
                              })
                            }
                          >
                            <option value="">Unassigned</option>
                            {Array.from(
                              new Map([
                                ...(p.team || []).map(
                                  (m) => [m.id, m.name] as const,
                                ),
                                ...(p.owner_user_id || p.manager_user_id
                                  ? [
                                      [
                                        p.owner_user_id || p.manager_user_id,
                                        p.owner_name || "Current owner",
                                      ] as const,
                                    ]
                                  : []),
                              ]).entries(),
                            ).map(([id, name]) => (
                              <option key={id} value={id}>
                                {name}
                              </option>
                            ))}
                          </NativeSelect>
                        ) : (
                          <span className="portfolio-owner">
                            {p.owner_name || "Unassigned · owner needed"}
                          </span>
                        )}
                        </div>
                        <div className="portfolio-avatars" aria-hidden="true">
                          {p.team?.slice(0, 3).map((m) => (
                            <Link
                              key={m.id}
                              to={`/pms/projects/${p.id}/members`}
                              title={`${m.name} · ${m.role}`}
                            >
                              {m.name.slice(0, 1).toUpperCase()}
                            </Link>
                          ))}
                          {(p.team?.length || 0) > 3 && (
                            <span
                              title={p.team
                                ?.slice(3)
                                .map((m) => m.name)
                                .join(", ")}
                            >
                              +{p.team!.length - 3}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>{progressBar(p)}</td>
                      {(["start_date", "due_date"] as const).map((field) => (
                        <td key={field} title={!p[field] ? field === "due_date" ? "No deadline set" : "No start date set" : undefined}>
                          {(canEditProject&&p.can_edit_project) ? (
                            <InlineProjectDate
                              label={`${field === "due_date" ? "Due" : "Start"} date for ${p.name}`}
                              value={p[field]}
                              disabled={busy}
                              overdue={field === "due_date" && overdue(p)}
                              onSave={(value) => update(p, { [field]: value })}
                            />
                          ) : (
                            formatDate(p[field] || null)
                          )}
                          {field === "due_date" && !!p.overdue_task_count && <small className="portfolio-date-warning" title={`${p.overdue_task_count} overdue tasks`}>{p.overdue_task_count} overdue</small>}
                        </td>
                      ))}
                      <td>
                        <NativeSelect
                          aria-label={`Priority for ${p.name}`}
                          className={`portfolio-priority priority-${p.priority.toLowerCase()}`}
                          disabled={!(canEditProject&&p.can_edit_project) || busy}
                          title={!(canEditProject&&p.can_edit_project) ? "Project editing permission required" : busy ? "Saving project" : "Set project priority"}
                          value={p.priority}
                          onChange={(e) =>
                            void update(p, {
                              priority: e.target
                                .value as PMSProject["priority"],
                            })
                          }
                        >
                          {priorities.map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </NativeSelect>
                      </td>
                      <td>
                        <span
                          title={p.blocked_task_count ? `${p.blocked_task_count} blocked tasks` : overdue(p) ? "Project deadline has passed" : p.overdue_task_count ? `${p.overdue_task_count} overdue tasks` : `Reported health: ${p.health}`}
                          className={`portfolio-health health-${health(p).toLowerCase().replace(" ", "-")}`}
                        >
                          {health(p)}
                        </span>
                      </td>
                      <td>
                        <NativeSelect
                          aria-label={`Status for ${p.name}`}
                          className={`portfolio-status ${statusColor(p.status)}`}
                          value={p.status}
                          disabled={!(canEditProject&&p.can_edit_project) || busy}
                          title={!(canEditProject&&p.can_edit_project) ? "Project editing permission required" : busy ? "Saving project" : "Set project status"}
                          onChange={(e) =>
                            void update(p, {
                              status: e.target.value as PMSProject["status"],
                            })
                          }
                        >
                          {statuses.map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </NativeSelect>
                      </td>
                      {shownFields.map((f) => {
                        const record = custom.records[p.id];
                        const field = record?.fields.find((v) => v.id === f.id);
                        return (
                          <td key={f.id}>
                            {field ? (
                              <CustomFieldCell
                                entity="project"
                                id={p.id}
                                field={field}
                                canEdit={record.can_edit}
                                onSaved={custom.reload}
                              />
                            ) : (
                              "—"
                            )}
                          </td>
                        );
                      })}
                      <td>
                        <div className="portfolio-row-actions">
                          <Link className="portfolio-open-icon" to={`/pms/projects/${p.id}`} title="Open project" aria-label={`Open ${p.name}`}><ExternalLink size={14}/></Link>
                          {favorite(p)}
                          <button
                            title="Preview project"
                            aria-label={`Preview ${p.name}`}
                            onClick={() => setPreviewId(p.id)}
                          >
                            <Eye size={16} />
                          </button>
                          <RecordActions
                            kind="project"
                            extraActions={[
                              ...(actionChoices.includes("task") && canCreateProject && p.can_manage_tasks ? [{label:"Add task",run:()=>navigate(`/pms/tasks/new?projectId=${p.id}`)}] : []),
                              ...(actionChoices.includes("duplicate") && canCreateProject && p.can_edit_project ? [{label:"Duplicate project",run:()=>setDuplicate(p)}] : []),
                            ]}
                            canEdit={p.can_edit_project === true}
                            record={{ ...p, title: p.name, key: p.project_key }}
                            onChanged={async (deleted) => {
                              if (deleted) setProjects(useProjectStore.getState().projects.filter(project => project.id !== p.id));
                              await load();
                              if (deleted) setProjects(useProjectStore.getState().projects.filter(project => project.id !== p.id));
                            }}
                          >
                            {(menu) => <span>{menu}</span>}
                          </RecordActions>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </GridTable>
            </div>

            <div
              className={
                filters.view === "grid"
                  ? "portfolio-cards"
                  : "portfolio-mobile-cards"
              }
            >
              {rows.map((p) => (
                <article key={p.id} data-testid={`project-card-${p.id}`} {...surfaceInteraction(p.id)}>
                  <div className="flex items-center justify-between">
                    <div className="portfolio-card-identity">
                      {(canEditProject&&p.can_edit_project) && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${p.name}`}
                          disabled={busy}
                          checked={selected.includes(p.id)}
                          onChange={(e) =>
                            setSelected((v) =>
                              e.target.checked
                                ? [...v, p.id]
                                : v.filter((id) => id !== p.id),
                            )
                          }
                        />
                      )}
                      <small>{p.project_key}</small>
                    </div>
                    {favorite(p)}
                  </div>
                  <h2>
                    {projectName(p)}
                  </h2>
                  <p>{p.client_name || "No client linked"}</p>
                  <div className="flex justify-between">
                    <Badge className={statusColor(p.status)}>{p.status}</Badge>
                    <span
                      title={p.blocked_task_count ? `${p.blocked_task_count} blocked tasks` : overdue(p) ? "Project deadline has passed" : p.overdue_task_count ? `${p.overdue_task_count} overdue tasks` : `Reported health: ${p.health}`}
                          className={`portfolio-health health-${health(p).toLowerCase().replace(" ", "-")}`}
                    >
                      {health(p)}
                    </span>
                  </div>
                  {progressBar(p)}
                  {quickActions(p)}
                  <RecordActions kind="project" canEdit={p.can_edit_project === true} record={{...p,title:p.name,key:p.project_key}} onChanged={load}>{menu => <div className="portfolio-mobile-more" aria-label={`More actions for ${p.name}`}>{menu}</div>}</RecordActions>
                  <footer>
                    <span>{p.owner_name || "Unassigned · owner needed"}</span>
                    <span className={overdue(p) ? "is-overdue" : ""}>
                      {p.due_date ? `${formatDate(p.due_date)} · ${Math.ceil((new Date(p.due_date.slice(0,10) + "T00:00:00").getTime() - new Date(today() + "T00:00:00").getTime()) / 86400000)} days` : "No deadline"}
                    </span>
                  </footer>
                  <button
                    className="portfolio-card-preview"
                    onClick={() => setPreviewId(p.id)}
                  >
                    <Eye size={15} />
                    Preview · {p.completed_task_count || 0}/{p.task_count || 0}{" "}
                    tasks
                  </button>
                </article>
              ))}
            </div>
          </>
        )}

        {!loading && !filtered.length && (
          <div className="portfolio-empty">
            <FolderKanban size={32} />
            <h2>No projects match this view</h2>
            <p>Adjust your search or filters to find your work.</p>
            <Button
              variant="outline"
              onClick={() => {
                setFilters(defaults);
                setSearch("");
              }}
            >
              Clear all filters
            </Button>
          </div>
        )}

        <footer className="portfolio-pagination">
          <span>
            {filtered.length
              ? `${page * 30 + 1}–${Math.min((page + 1) * 30, filtered.length)} of ${filtered.length} projects`
              : "0 projects"}
          </span>
          <div>
            <Button
              size="sm"
              variant="ghost"
              disabled={!page}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={(page + 1) * 30 >= filtered.length}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </footer>
      </section>

      {preview && pinnedPreview && <div className="portfolio-pinned-preview" style={{width:previewWidth,maxWidth:"100%"}}><GridRecordPane title={preview.name} close={() => setPreviewId(undefined)} expand={() => openProject(preview.id)}>{previewContent}</GridRecordPane></div>}
      <Dialog open={!!pendingBulk} onOpenChange={v => {if(!v && !busy)setPendingBulk(undefined);}}><DialogContent><DialogTitle>Review bulk change</DialogTitle><p>{pendingBulk?.message} for {selected.length} selected projects.</p><ul>{projects.filter(p => selected.includes(p.id)).map(p => <li key={p.id}>{p.name} · {Object.entries(pendingBulk?.patch || {}).map(([field,value]) => `${field}: ${String(p[field as keyof PMSProject] ?? "unset")} → ${String(value)}`).join(", ")}</li>)}</ul><Button disabled={busy} onClick={() => {if(pendingBulk)void bulk(pendingBulk.patch,pendingBulk.message).then(() => setPendingBulk(undefined));}}>Apply changes</Button><Button variant="outline" disabled={busy} onClick={() => setPendingBulk(undefined)}>Cancel</Button></DialogContent></Dialog>
      <Dialog
        open={!!preview && !pinnedPreview}
        onOpenChange={(open) => {
          if (!open) setPreviewId(undefined);
        }}
      >
        <DialogContent
          className={`portfolio-preview ${resizing ? "is-resizing" : ""}`}
          style={{ width: previewWidth }}
        >
          <div
            className="portfolio-preview-resizer"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize project preview"
            aria-valuemin={360}
            aria-valuemax={1200}
            aria-valuenow={previewWidth}
            tabIndex={0}
            onPointerDown={(e) => {
              e.preventDefault();
              setResizing(true);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                setPreviewWidth((w) =>
                  Math.min(
                    1200,
                    Math.max(360, w + (e.key === "ArrowLeft" ? 40 : -40)),
                  ),
                );
              }
            }}
          />

          <DialogTitle className="sr-only">{preview?.name}</DialogTitle>
          {previewContent}
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!confirmation}
        onOpenChange={(open) => {
          if (!open && !busy) setConfirmation(undefined);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {confirmation === "archive"
              ? "Archive selected projects?"
              : "Move selected projects to Trash?"}
          </DialogTitle>
          <p className="text-sm text-muted-foreground">
            {selected.length} selected projects will{" "}
            {confirmation === "archive"
              ? "leave active portfolio views. You can restore them from Archived."
              : "move to Trash with their tasks and files preserved. You can restore them from Trash."}
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setConfirmation(undefined)}
            >
              Cancel
            </Button>
            <Button
              disabled={busy}
              onClick={() => {
                void (
                  confirmation === "archive"
                    ? bulk({ is_archived: true }, "Archived")
                    : deleteSelected()
                ).finally(() => setConfirmation(undefined));
              }}
            >
              {busy
                ? "Applying…"
                : confirmation === "archive"
                  ? "Archive projects"
                  : "Move to Trash"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <QuickCreateProject
        open={creating}
        initialStatus={createStatus}
        initialWorkspace={workspaceScope === "all" ? undefined : Number(workspaceScope)}
        onClose={() => setCreating(false)}
        onCreated={(project) => {
          generation.current += 1;
          setProjects([project,...allProjects.filter(row=>row.id!==project.id)]);
          void load().catch((e) => setError(workspaceError(e)));
          setNotice("Project created");
        }}
      />
      <DuplicateProjectDialog
        project={duplicate}
        onClose={() => setDuplicate(undefined)}
        onCreated={() => {
          void load().catch((e) => setError(workspaceError(e)));
        }}
      />
    </main>
  );
}

export default withRecordViewHost(ProjectsList);
