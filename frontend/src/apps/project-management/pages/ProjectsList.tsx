import { useEffect, useMemo, useRef, useState } from "react";

import { Link } from "react-router-dom";

import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Download,
  Eye,
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
};

type Filters = typeof defaults;

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

export default function ProjectsList() {
  const uid = useAuthStore((s) => s.user?.id);
  const companyId = useAuthStore((s) => s.user?.access?.companyId);
  const generation = useRef(0);

  const key = `pms-project-portfolio:${companyId}:${uid || "anonymous"}`;

  const { projects, setProjects } = useProjectStore();

  const [filters, setFilters] = useState<Filters>(() => ({
    ...defaults,
    ...read(key, {}),
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

  const preferencesBase = "/pipeline-workspaces/project_management/portfolio";

  useEffect(() => {
    let active = true;
    setPreferencesReady(false);
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
        if (values?.portfolio) {
          const f = JSON.parse(values.portfolio);
          setFilters({ ...defaults, ...f });
          setSearch(f.query || "");
        }
        if (values?.stars) setStars(JSON.parse(values.stars));
        setPreferencesReady(true);
      })
      .catch((e) => {
        if (active) setError(workspaceError(e));
      });
    return () => {
      active = false;
      generation.current++;
    };
  }, [uid, companyId]);

  useEffect(() => {
    if (!preferencesReady) return;
    const timer = setTimeout(() => {
      void api
        .put(`${preferencesBase}/preferences`, {
          module_filters: {
            portfolio: JSON.stringify(filters),
            stars: JSON.stringify(stars),
          },
        })
        .catch((e) => setError(workspaceError(e)));
    }, 650);
    return () => clearTimeout(timer);
  }, [filters, stars, preferencesReady]);

  async function saveView() {
    const name = viewName;
    if (!name?.trim()||saveViewLock.current) return;
    saveViewLock.current=true;setSavingView(true);
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
    } finally {saveViewLock.current=false;setSavingView(false);}
  }

  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");

  const [busy, setBusy] = useState(false),
    [advanced, setAdvanced] = useState(false),
    [page, setPage] = useState(0);

  const [selected, setSelected] = useState<number[]>([]),
    [previewId, setPreviewId] = useState<number>();

  const [savingView,setSavingView]=useState(false);
  const saveViewLock=useRef(false);
  const [previewWidth,setPreviewWidth]=useState(600);
  const [resizing,setResizing]=useState(false);
  useEffect(()=>{if(!resizing)return;const move=(e:PointerEvent)=>setPreviewWidth(Math.min(window.innerWidth-24,Math.max(360,window.innerWidth-e.clientX)));const end=()=>setResizing(false);window.addEventListener("pointermove",move);window.addEventListener("pointerup",end,{once:true});return()=>{window.removeEventListener("pointermove",move);window.removeEventListener("pointerup",end);};},[resizing]);
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

  async function load() {
    const request = ++generation.current;
    const rows: PMSProject[] = [];

    for (let skip = 0; ; skip += 500) {
      const batch = await projectsAPI.list(skip, 500);
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

  function filter(field: keyof Filters, value: string) {
    setFilters((f) => ({ ...f, [field]: value }));
    setPage(0);
    setSelected([]);
    if(field==="query")setSearch(value);
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
            matches(p, filters.tab) &&
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
    [projects, filters, uid, stars],
  );

  useEffect(()=>{setPage(p=>Math.min(p,Math.max(0,Math.ceil(filtered.length/30)-1)));},[filtered.length]);
  const activeFilters=Object.entries(filters).filter(([field,value])=>!["view","sort","match","tab"].includes(field)&&value!==""&&value!=="[]");
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
    setBusy(true);
    setError("");

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
      setNotice(`${p.name} updated`);
      return true;
    } catch (e) {
      setError(workspaceError(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

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
      if (!p?.can_edit_project) {
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
    if (
      !window.confirm(
        `Move ${selected.length} selected projects to Trash? They can be restored from Trash.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    const failures: string[] = [];
    let done = 0;
    for (const id of selected) {
      const p = projects.find((p) => p.id === id);
      if (!p?.can_edit_project) {
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
  }

  const progressBar = (p: PMSProject) => (
    <button
      className="portfolio-progress"
      title={`${p.completed_task_count || 0} of ${p.task_count || 0} tasks complete. ${p.completed_milestone_count || 0} of ${p.milestone_count || 0} milestones complete. Click for details.`}
      onClick={() => setPreviewId(p.id)}
    >
      <span>
        <i style={{ width: `${Math.max(0, Math.min(100, progress(p)))}%` }} />
      </span>
      <b>{progress(p)}%</b>
    </button>
  );

  const favorite = (p: PMSProject) => (
    <button
      className={`portfolio-star ${stars.includes(p.id) ? "is-starred" : ""}`}
      aria-label={`${stars.includes(p.id) ? "Unstar" : "Star"} ${p.name}`}
      aria-pressed={stars.includes(p.id)}
      onClick={() =>
        setStars((s) =>
          s.includes(p.id) ? s.filter((id) => id !== p.id) : [...s, p.id],
        )
      }
    >
      <Star size={16} />
    </button>
  );

  return (
    <main className={`project-portfolio ${advanced?"portfolio-filters-expanded":""}`}>
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
          <Button title="Export filtered projects as CSV" variant="outline" onClick={exportCSV} disabled={loading}>
            <Download size={15} />
            Export
          </Button>
          <Button variant="outline" asChild>
            <Link to="/pms/trash?type=projects">
              <Trash2 size={15} />
              Trash
            </Link>
          </Button>
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} />
            New Project
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
            onClick={() => {setFilters({...defaults,tab,view:filters.view,sort:filters.sort});setSearch("");setPage(0);setSelected([]);}}
            aria-pressed={filters.tab === tab}
          >
            <span className="kpi-icon">
              <Icon size={24} />
            </span>
            <span>
              <small>{label}</small>
              <strong>{loading ? "—" : value}</strong>
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
          <div className="portfolio-switch" aria-label="Display mode">
            {[
              { value: "list", Icon: List },
              { value: "grid", Icon: LayoutGrid },
              { value: "analytics", Icon: BarChart3 },
            ].map(({ value, Icon }) => (
              <button
                key={value}
                title={`${value} view`}
                aria-label={`${value} view`}
                aria-pressed={filters.view === value}
                className={filters.view === value ? "active" : ""}
                onClick={() => filter("view", value)}
              >
                <Icon size={18} />
              </button>
            ))}
          </div>
        </div>

        <div className="portfolio-filters">
          <label className="portfolio-search">
            <Search size={17} />
            <Input
              aria-label="Search projects"
              placeholder="Search projects, codes, clients, people…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);setSelected([]);
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
              <option key={s}>{s}</option>
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
                  const view = saved[Number(e.target.value)];
                  if (view) {
                    const f = {
                      ...defaults,
                      ...JSON.parse(
                        view.preferences.module_filters.portfolio || "{}",
                      ),
                    };
                    setFilters(f);
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

        {!!activeFilters.length&&<div className="portfolio-active-filters" aria-label="Active filters"><span>{filtered.length} matching projects</span>{activeFilters.map(([field,value])=><button key={field} onClick={()=>filter(field as keyof Filters,field==="rules"?"[]":"")} aria-label={`Clear ${field} filter`}>{field==="rules"?`${readRules(value).length} conditions`:field==="query"?`Search: ${value}`:`${field}: ${value}`} <span aria-hidden="true">×</span></button>)}<button className="portfolio-clear-filters" onClick={()=>{setFilters(f=>({...defaults,view:f.view,sort:f.sort,tab:f.tab}));setSearch("");setPage(0);setSelected([]);}}>Clear all</button></div>}
        {(error || custom.error) && (
          <p className="portfolio-error" role="alert">
            {error || custom.error}{" "}
            <button
              onClick={() => {
                setError("");custom.reload();
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
          </p>
        )}

        {!!selected.length && (
          <div className="portfolio-bulk">
            <b>{selected.length} selected</b>
            <NativeSelect
              aria-label="Bulk owner"
              value=""
              disabled={busy}
              onChange={(e) =>
                void bulk(
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
                void bulk(
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
                void bulk(
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
            <Button variant="outline" disabled={busy} onClick={exportCSV}>
              Export selected
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                if (window.confirm(`Archive ${selected.length} projects?`))
                  void bulk({ is_archived: true }, "Archived");
              }}
            >
              Archive
            </Button>
            {filters.tab === "Archived" && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void bulk(
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
              onClick={() => void deleteSelected()}
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

        {loading ? (
          <div className="p-12 text-center text-muted-foreground" role="status">
            Loading your project portfolio…
          </div>
        ) : filters.view === "analytics" ? (
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
                className="portfolio-table"
              >
                <thead>
                  <tr>
                    <th>
                      <input
                        aria-label="Select visible editable projects"
                        type="checkbox"
                        checked={
                          rows.some((p) => p.can_edit_project) &&
                          rows
                            .filter((p) => p.can_edit_project)
                            .every((p) => selected.includes(p.id))
                        }
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? rows
                                  .filter((p) => p.can_edit_project)
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
                    <tr key={p.id}>
                      <td>
                        <input
                          aria-label={`Select ${p.name}`}
                          disabled={!p.can_edit_project || busy}
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
                          <span className="portfolio-project-icon">
                            <FolderKanban size={19} />
                          </span>
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
                                <Link to={`/pms/projects/${p.id}`}>
                                  {p.name}
                                </Link>
                                {p.can_edit_project && (
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
                        {p.can_edit_project ? (
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
                            {p.owner_name || "Unassigned"}
                          </span>
                        )}
                        <div className="portfolio-avatars">
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
                        <td key={field}>
                          {p.can_edit_project ? (
                            <input
                              aria-label={`${field === "due_date" ? "Due" : "Start"} date for ${p.name}`}
                              type="date"
                              className={
                                field === "due_date" && overdue(p)
                                  ? "is-overdue"
                                  : ""
                              }
                              disabled={busy}
                              value={p[field]?.slice(0, 10) || ""}
                              onChange={(e) =>
                                void update(p, {
                                  [field]: e.target.value || null,
                                })
                              }
                            />
                          ) : (
                            formatDate(p[field] || null)
                          )}
                        </td>
                      ))}
                      <td>
                        <NativeSelect
                          aria-label={`Priority for ${p.name}`}
                          className={`portfolio-priority priority-${p.priority.toLowerCase()}`}
                          disabled={!p.can_edit_project || busy}
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
                          disabled={!p.can_edit_project || busy}
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
                            canEdit={p.can_edit_project === true}
                            record={{ ...p, title: p.name, key: p.project_key }}
                            onChanged={async () => {
                              await load();
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
                <article key={p.id} data-testid={`project-card-${p.id}`}>
                  <div className="flex items-center justify-between">
                    <small>{p.project_key}</small>
                    {favorite(p)}
                  </div>
                  <h2>
                    <Link to={`/pms/projects/${p.id}`}>{p.name}</Link>
                  </h2>
                  <p>{p.client_name || "No client linked"}</p>
                  <div className="flex justify-between">
                    <Badge className={statusColor(p.status)}>{p.status}</Badge>
                    <span className="portfolio-health">{health(p)}</span>
                  </div>
                  {progressBar(p)}
                  <footer>
                    <span>{p.owner_name || "Unassigned"}</span>
                    <span className={overdue(p) ? "is-overdue" : ""}>
                      {formatDate(p.due_date || null)}
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

      <Dialog
        open={!!preview}
        onOpenChange={(open) => {
          if (!open) setPreviewId(undefined);
        }}
      >
        <DialogContent className={`portfolio-preview ${resizing?"is-resizing":""}`} style={{width:previewWidth}}>
          <div className="portfolio-preview-resizer" role="separator" aria-orientation="vertical" aria-label="Resize project preview" aria-valuemin={360} aria-valuemax={1200} aria-valuenow={previewWidth} tabIndex={0} onPointerDown={e=>{e.preventDefault();setResizing(true);}} onKeyDown={e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();setPreviewWidth(w=>Math.min(1200,Math.max(360,w+(e.key==="ArrowLeft"?40:-40))));}}}/>

          {preview && (
            <>
              <DialogTitle>{preview.name}</DialogTitle>
              <p className="text-sm text-muted-foreground">
                {preview.project_key} ·{" "}
                {preview.client_name || "No client linked"}
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge className={statusColor(preview.status)}>
                  {preview.status}
                </Badge>
                <Badge variant="outline">{preview.priority}</Badge>
                <Badge variant="outline">{health(preview)}</Badge>
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
              <ProjectPreviewDetails key={preview.id} projectId={preview.id} />
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
                {preview.can_edit_project && (
                  <Button variant="outline" asChild>
                    <Link to={`/pms/projects/${preview.id}/edit`}>
                      Edit Project
                    </Link>
                  </Button>
                )}
                {preview.can_edit_project && (
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
          )}
        </DialogContent>
      </Dialog>

      <QuickCreateProject
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
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
