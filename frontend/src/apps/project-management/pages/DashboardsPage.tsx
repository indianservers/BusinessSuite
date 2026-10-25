import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import GridLayout from "react-grid-layout";
import { toPng } from "html-to-image";
import {
  BarChart3,
  Plus,
  SlidersHorizontal,
  Undo2,
  Redo2,
  Save,
  Star,
  Search,
  GripVertical,
  MoreHorizontal,
  Maximize2,
  Download,
  Filter,
  History,
  Share2,
  RefreshCw,
  LayoutGrid,
  List,
  ArrowLeft,
  Sparkles,
  X,
} from "lucide-react";
import {
  Folder,
  ListChecks,
  Users,
  CalendarDays,
  Clock3,
  Target,
  Activity,
  FileText,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { workspaceError } from "./workspaceTypes";
import DashboardWizard from "../dashboard/DashboardWizard";
import WidgetContent, { DataTable } from "../dashboard/WidgetContent";
import {
  Panel,
  Choice,
  FilterFields,
  WidgetSettings,
} from "../dashboard/Panels";
import {
  base,
  copy,
  emptyConfig,
  emptyFilters,
  makeWidget,
  pack,
  queryDashboard,
  exportCSV,
  widgetRows,
  download,
  type Dashboard,
  type Configuration,
  type Catalog,
  type Scope,
  type Widget,
  type Batch,
  type Row,
} from "../dashboard/model";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "../dashboard/builder.css";
class WidgetBoundary extends Component<
  { children: ReactNode; reset: string },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(previous: { reset: string }) {
    if (previous.reset !== this.props.reset && this.state.failed)
      this.setState({ failed: false });
  }
  render() {
    return this.state.failed ? (
      <p role="alert">
        This widget could not render. Open its settings or refresh the data.
      </p>
    ) : (
      this.props.children
    );
  }
}
const widgetIcons = {
  chart: BarChart3,
  tasks: ListChecks,
  projects: Folder,
  team: Users,
  calendar: CalendarDays,
  time: Clock3,
  target: Target,
  activity: Activity,
  notes: FileText,
};
function WidgetSymbol({ widget }: { widget: Widget }) {
  const kind =
    widget.icon && widget.icon !== "auto"
      ? widget.icon
      : widget.type.includes("deadline") || widget.type === "calendar"
        ? "calendar"
        : widget.type === "notes"
          ? "notes"
          : widget.type === "on_time_rate"
            ? "target"
            : widget.type.endsWith("hours")
              ? "time"
              : widget.source === "projects"
                ? "projects"
                : widget.source === "activity"
                  ? "activity"
                  : widget.source === "tasks"
                    ? "tasks"
                    : "chart";
  const Icon = widgetIcons[kind as keyof typeof widgetIcons] || BarChart3;
  return <Icon size={16} />;
}
const editable = (d: Dashboard) => ({
  name: d.name,
  description: d.description,
  visibility: d.visibility,
  shared_users: d.shared_users,
  icon: d.icon,
  accent: d.accent,
  category: d.category,
  archived: d.archived,
  configuration: d.configuration,
});
const tabs = [
  "All",
  "Mine",
  "Organization",
  "Private",
  "Shared with me",
  "Favorites",
  "Recent",
  "Archive",
  "Trash",
];
export default function DashboardsPage() {
  const { user } = useAuthStore(),
    qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("All"),
    [search, setSearch] = useState(""),
    [library, setLibrary] = useState(!params.get("dashboard")),
    [view, setView] = useState("grid"),
    [wizard, setWizard] = useState(false),
    [editing, setEditing] = useState(false),
    [draft, setDraft] = useState<Dashboard | null>(null),
    [past, setPast] = useState<Dashboard[]>([]),
    [future, setFuture] = useState<Dashboard[]>([]),
    [panel, setPanel] = useState(""),
    [widget, setWidget] = useState<Widget | null>(null),
    [gallerySearch, setGallerySearch] = useState(""),
    [category, setCategory] = useState("All"),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false),
    [width, setWidth] = useState(1100),
    [expanded, setExpanded] = useState<Widget | null>(null),
    [drill, setDrill] = useState<{
      title: string;
      rows: Row[];
      source: string;
    } | null>(null),
    [confirmation, setConfirmation] = useState<{
      title: string;
      run: () => Promise<void>;
      target?: Dashboard;
    } | null>(null),
    [confirmName, setConfirmName] = useState(""),
    [suggestion, setSuggestion] = useState<Configuration | null>(null),
    [prompt, setPrompt] = useState(""),
    [presetName, setPresetName] = useState(""),
    [presentation, setPresentation] = useState(false),
    [recover, setRecover] = useState<Dashboard | null>(null);
  const [suggestProvider, setSuggestProvider] = useState("guided"),
    [suggestMessage, setSuggestMessage] = useState("");
  const canvas = useRef<HTMLDivElement>(null);
  const key = ["pms-dashboard-builder", user?.id];
  const list = useQuery({
    queryKey: key,
    queryFn: async () => (await api.get<Dashboard[]>(base)).data,
  });
  const catalog = useQuery({
    queryKey: ["pms-dashboard-catalog"],
    queryFn: async () => (await api.get<Catalog>(base + "/catalog")).data,
    staleTime: 3600000,
  });
  const workspaces = useQuery({
    queryKey: ["dashboard-workspaces"],
    queryFn: async () =>
      (await api.get("/project-management/workspaces")).data as {
        id: number;
        name: string;
        role: string;
      }[],
  });
  const saved = list.data?.find(
    (d) => d.id === Number(params.get("dashboard")),
  );
  const active = draft?.id === saved?.id ? draft : saved;
  const dirty = !!(
    saved &&
    draft &&
    saved.can_edit &&
    JSON.stringify(editable(saved)) !== JSON.stringify(editable(draft))
  );
  const storageKey = saved ? `kf-dashboard-draft:${user?.id}:${saved.id}` : "";
  useEffect(() => {
    setDraft(saved ? copy(saved) : null);
    setPast([]);
    setFuture([]);
    setEditing(false);
    setError("");
    if (saved) {
      try {
        const value = JSON.parse(
          localStorage.getItem(`kf-dashboard-draft:${user?.id}:${saved.id}`) ||
            "null",
        );
        setRecover(value?.id === saved.id ? value : null);
      } catch {
        setRecover(null);
      }
      void api.post(`${base}/${saved.id}/visit`).catch(() => {});
    }
  }, [saved?.id, user?.id]);
  useEffect(() => {
    if (saved && !editing && !dirty) setDraft(copy(saved));
  }, [saved?.revision]);
  useEffect(() => {
    if (!dirty || !draft) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(draft));
    } catch {
      /* Server saves remain available when browser storage is full. */
    }
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, draft, storageKey]);
  useEffect(() => {
    const observer = new ResizeObserver((entries) =>
      setWidth(entries[0].contentRect.width),
    );
    if (canvas.current) observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [library, active?.id, !!catalog.data]);
  useEffect(() => {
    const keypress = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPresentation(false);
      if (
        !editing ||
        panel ||
        widget ||
        confirmation ||
        wizard ||
        /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName) ||
        !(e.ctrlKey || e.metaKey)
      )
        return;
      if (e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      }
      if (e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      }
    };
    window.addEventListener("keydown", keypress);
    return () => window.removeEventListener("keydown", keypress);
  }, [editing, past, future, draft, panel, widget, confirmation, wizard]);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      document
        .querySelectorAll<HTMLDetailsElement>(".db-menu[open]")
        .forEach((menu) => {
          if (!menu.contains(event.target as Node)) menu.open = false;
        });
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape")
        document
          .querySelectorAll<HTMLDetailsElement>(".db-menu[open]")
          .forEach((menu) => (menu.open = false));
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  const scope = useQuery({
    queryKey: ["dashboard-scope", saved?.id],
    enabled: !!saved && !library,
    queryFn: async () =>
      (await api.get<Scope>(`${base}/${saved!.id}/scope`)).data,
  });
  const members = useQuery({
    queryKey: ["dashboard-sharing", saved?.workspace_id],
    enabled: !!saved?.can_manage && panel === "manage",
    queryFn: async () =>
      (
        await api.get(
          `/project-management/workspaces/${saved!.workspace_id}/members`,
        )
      ).data as { user_id: number; email: string; role: string }[],
  });
  const history = useQuery({
    queryKey: ["dashboard-history", saved?.id, saved?.revision],
    enabled: !!saved?.can_edit && panel === "history",
    queryFn: async () =>
      (await api.get(`${base}/${saved!.id}/history`)).data as {
        id: number;
        revision: number;
        name: string;
        editor_id: number;
        saved_at: string;
        configuration: Configuration;
      }[],
  });
  const config = active?.configuration || emptyConfig();
  const [queryConfig, setQueryConfig] = useState(config);
  useEffect(() => {
    const timer = setTimeout(() => setQueryConfig(config), 350);
    return () => clearTimeout(timer);
  }, [JSON.stringify(config)]);
  const data = useQuery({
    queryKey: ["dashboard-data", saved?.id, queryConfig],
    enabled: !!saved && !library && !saved.deleted_at,
    queryFn: () => queryDashboard(saved!.id, queryConfig),
    refetchInterval: !editing ? config.refresh_seconds * 1000 : false,
  });
  function commit(next: Dashboard) {
    if (!active || JSON.stringify(next) === JSON.stringify(active)) return;
    if (saved?.can_edit) setPast((v) => [...v.slice(-39), copy(active)]);
    setFuture([]);
    setDraft(next);
  }
  function changeConfig(configuration: Configuration) {
    if (active) commit({ ...active, configuration });
  }
  function updateWidget(next: Widget) {
    const old = config.widgets.find((w) => w.id === next.id);
    if (
      old &&
      (old.w !== next.w || old.h !== next.h || (old.hidden && !next.hidden))
    )
      next = {
        ...next,
        x: 0,
        y: Math.max(
          0,
          ...config.widgets
            .filter((w) => w.id !== next.id && !w.hidden)
            .map((w) => w.y + w.h),
        ),
      };
    changeConfig({
      ...config,
      widgets: config.widgets.map((w) => (w.id === next.id ? next : w)),
    });
  }
  function undo() {
    if (!past.length || !draft) return;
    setFuture((v) => [copy(draft), ...v]);
    setDraft(past[past.length - 1]);
    setPast((v) => v.slice(0, -1));
  }
  function redo() {
    if (!future.length || !draft) return;
    setPast((v) => [...v, copy(draft)]);
    setDraft(future[0]);
    setFuture((v) => v.slice(1));
  }
  async function run(action: () => Promise<void>) {
    setPending(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(workspaceError(e));
    } finally {
      setPending(false);
    }
  }
  async function refreshList() {
    await qc.invalidateQueries({ queryKey: key });
  }
  async function save() {
    if (!saved || !draft) return;
    await run(async () => {
      const next = (
        await api.put<Dashboard>(`${base}/${saved.id}`, {
          ...editable(draft),
          revision: saved.revision,
        })
      ).data;
      qc.setQueryData<Dashboard[]>(key, (old) =>
        old?.map((d) => (d.id === next.id ? next : d)),
      );
      setDraft(next);
      setPast([]);
      setFuture([]);
      setRecover(null);
      localStorage.removeItem(storageKey);
      setEditing(false);
      await qc.invalidateQueries({ queryKey: ["dashboard-history", saved.id] });
    });
  }
  async function openDashboard(d: Dashboard) {
    if (dirty) {
      setConfirmation({
        title: "Discard unsaved changes and open another dashboard?",
        run: async () => {
          localStorage.removeItem(storageKey);
          setParams({ dashboard: String(d.id) });
          setLibrary(false);
        },
      });
      return;
    }
    setParams({ dashboard: String(d.id) });
    setLibrary(false);
  }
  async function action(d: Dashboard, name: string) {
    await run(async () => {
      if (name === "favorite")
        await api.post(`${base}/${d.id}/favorite`, { favorite: !d.favorite });
      else if (name === "duplicate") {
        const copy = (await api.post<Dashboard>(`${base}/${d.id}/duplicate`))
          .data;
        setParams({ dashboard: String(copy.id) });
        setLibrary(false);
      } else
        await api.post(`${base}/${d.id}/${name}`, { revision: d.revision });
      await refreshList();
    });
  }
  async function inspect(w: Widget, label?: string) {
    if (!saved) return;
    await run(async () => {
      const filters = copy(w.filters || config.filters);
      if (label && w.group_by === "status") filters.statuses = [label];
      if (label && w.group_by === "priority") filters.priorities = [label];
      if (label && w.group_by === "project")
        filters.project_ids = (scope.data?.projects || [])
          .filter((p) => p.name === label)
          .map((p) => p.id);
      if (label && w.group_by === "assignee")
        filters.assignee_ids = (scope.data?.people || [])
          .filter((p) => p.name === label)
          .map((p) => p.id);
      if (
        label &&
        ["day", "week", "month", "quarter", "year"].includes(w.group_by)
      ) {
        let start: Date | null = null,
          end: Date | null = null;
        if (w.group_by === "day" || w.group_by === "week") {
          start = new Date(label + "T00:00:00Z");
          end = new Date(start);
          if (w.group_by === "week") end.setUTCDate(end.getUTCDate() + 6);
        }
        if (w.group_by === "month") {
          const [year, month] = label.split("-").map(Number);
          start = new Date(Date.UTC(year, month - 1, 1));
          end = new Date(Date.UTC(year, month, 0));
        }
        if (w.group_by === "quarter") {
          const [year, quarter] = label.split("-Q").map(Number);
          start = new Date(Date.UTC(year, (quarter - 1) * 3, 1));
          end = new Date(Date.UTC(year, quarter * 3, 0));
        }
        if (w.group_by === "year") {
          start = new Date(Date.UTC(Number(label), 0, 1));
          end = new Date(Date.UTC(Number(label), 12, 0));
        }
        if (start && end && !isNaN(start.getTime()) && !isNaN(end.getTime())) {
          filters.date_from = start.toISOString().slice(0, 10);
          filters.date_to = end.toISOString().slice(0, 10);
        }
      }
      const result = await queryDashboard(saved.id, {
        ...config,
        widgets: [
          {
            ...w,
            type:
              label === "Unassigned" &&
              w.group_by === "assignee" &&
              w.source === "tasks"
                ? "unassigned"
                : w.type,
            drilldown: true,
            filters,
            limit: 100,
          },
        ],
      });
      const entry = result.widgets[w.id];
      if (entry.state !== "ready") throw new Error(entry.message);
      setDrill({
        title: w.title + (label ? ` · ${label}` : ""),
        rows: widgetRows(entry),
        source: w.source,
      });
    });
  }
  async function png() {
    if (!canvas.current || !active) return;
    await run(async () => {
      const url = await toPng(canvas.current!, {
        cacheBust: true,
        pixelRatio: 2,
        backgroundColor: getComputedStyle(canvas.current!).backgroundColor,
      });
      download(await (await fetch(url)).blob(), active.name + ".png");
    });
  }
  function add(spec: Catalog["widgets"][number]) {
    if (config.widgets.length >= 50) {
      setError("A dashboard supports up to 50 widgets.");
      return;
    }
    const next = makeWidget(spec, config.widgets);
    changeConfig({ ...config, widgets: [...config.widgets, next] });
    setPanel("");
    setWidget(next);
  }
  const filtered = (list.data || [])
    .filter((d) =>
      tab === "Trash"
        ? !!d.deleted_at
        : tab === "Archive"
          ? !d.deleted_at && d.archived
          : !d.deleted_at && !d.archived,
    )
    .filter((d) =>
      tab === "Mine"
        ? d.owner_id === user?.id
        : tab === "Organization"
          ? d.visibility === "organization"
          : tab === "Private"
            ? d.visibility === "private"
            : tab === "Shared with me"
              ? d.owner_id !== user?.id
              : tab === "Favorites"
                ? d.favorite
                : tab === "Recent"
                  ? !!d.last_viewed_at
                  : true,
    )
    .filter((d) =>
      (d.name + " " + d.description + " " + d.category)
        .toLowerCase()
        .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      String(tab === "Recent" ? b.last_viewed_at : b.updated_at).localeCompare(
        String(tab === "Recent" ? a.last_viewed_at : a.updated_at),
      ),
    );
  const visible = config.widgets.filter((w) => !w.hidden);
  let responsiveY = 0,
    responsiveX = 0,
    responsiveHeight = 0;
  const layout = visible.map((w) => {
    if (width < 1050) {
      const metric =
        catalog.data?.widgets.find((s) => s.id === w.type)?.view === "metric";
      const columns =
        width < 700 ? (metric ? 6 : 12) : metric ? 4 : w.w === 12 ? 12 : 6;
      const height = metric ? Math.max(4, w.h) : w.h;
      if (responsiveX + columns > 12) {
        responsiveX = 0;
        responsiveY += responsiveHeight;
        responsiveHeight = 0;
      }
      const item = {
        i: w.id,
        x: responsiveX,
        y: responsiveY,
        w: columns,
        h: height,
        static: true,
      };
      responsiveX += columns;
      responsiveHeight = Math.max(responsiveHeight, height);
      return item;
    }
    return {
      i: w.id,
      x: w.x,
      y: w.y,
      w: w.w,
      h: w.h,
      minW: 2,
      maxW: 12,
      minH: 3,
      maxH: 24,
      static: !editing || w.locked,
    };
  });
  const onLayout = (items: GridLayout.Layout[]) => {
    if (!editing || width < 1050) return;
    changeConfig({
      ...config,
      widgets: config.widgets.map((w) => {
        const item = items.find((i) => i.i === w.id);
        return item ? { ...w, x: item.x, y: item.y, w: item.w, h: item.h } : w;
      }),
    });
  };
  const catalogData = catalog.data;
  return (
    <main
      className={`db-page ${presentation ? "db-presentation" : ""}`}
      data-density={config.density}
    >
      <header className="db-page-heading">
        <div className="db-heading-icon">
          <BarChart3 />
        </div>
        <div>
          <small>PMS / Dashboards</small>
          <h1>{library ? "Dashboards" : active?.name || "Dashboard"}</h1>
          <p>
            {library
              ? "A complete view of your projects, teams, and progress."
              : active?.description || "Track what matters and drive results."}
          </p>
        </div>
        <div className="db-header-actions">
          {!library && (
            <Button
              variant="outline"
              onClick={() => {
                setLibrary(true);
                setEditing(false);
              }}
            >
              <ArrowLeft size={16} />
              Browse
            </Button>
          )}
          {!library && saved?.can_edit && !saved.deleted_at && (
            <Button variant="outline" onClick={() => setEditing((v) => !v)}>
              <SlidersHorizontal size={16} />
              {editing ? "Preview" : "Customize"}
            </Button>
          )}
          <Button
            disabled={!catalogData || !workspaces.data}
            onClick={() => setWizard(true)}
          >
            <Plus size={16} />
            New dashboard
          </Button>
        </div>
      </header>
      {error && (
        <div className="db-error" role="alert">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {list.isError && (
        <p role="alert">
          Dashboards could not load.{" "}
          <button onClick={() => void list.refetch()}>Retry</button>
        </p>
      )}
      {catalog.isError && (
        <p role="alert">
          Widget catalog could not load.{" "}
          <button onClick={() => void catalog.refetch()}>Retry</button>
        </p>
      )}
      {library ? (
        <>
          <div className="db-library-toolbar">
            <nav aria-label="Dashboard folders">
              {tabs.map((t) => (
                <button
                  aria-current={t === tab ? "page" : undefined}
                  className={tab === t ? "selected" : ""}
                  onClick={() => setTab(t)}
                  key={t}
                >
                  {t}
                </button>
              ))}
            </nav>
            <div className="db-search">
              <Search size={16} />
              <input
                aria-label="Search dashboards"
                placeholder="Search dashboards…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Button
              variant="outline"
              aria-label="Toggle dashboard list view"
              onClick={() => setView((v) => (v === "grid" ? "list" : "grid"))}
            >
              {view === "grid" ? <List size={17} /> : <LayoutGrid size={17} />}
            </Button>
          </div>
          {list.isPending ? (
            <p role="status">Loading dashboards…</p>
          ) : !filtered.length ? (
            <section className="db-onboarding">
              <BarChart3 size={40} />
              <h2>
                {tab === "All"
                  ? "Your next clear view starts here"
                  : "No dashboards here yet"}
              </h2>
              <p>
                Create a dashboard from 15 templates, or build your own with the
                widget library.
              </p>
              <Button onClick={() => setWizard(true)} disabled={!catalogData}>
                <Plus size={16} />
                Create your first dashboard
              </Button>
            </section>
          ) : (
            <div className={`db-library db-library-${view}`}>
              {filtered.map((d) => (
                <article key={d.id}>
                  <div className="db-library-card-top">
                    <span style={{ color: d.accent }}>
                      <BarChart3 size={23} />
                    </span>
                    <button
                      aria-label={`${d.favorite ? "Unfavorite" : "Favorite"} ${d.name}`}
                      onClick={() => void action(d, "favorite")}
                    >
                      <Star size={18} fill={d.favorite ? "#f5ab25" : "none"} />
                    </button>
                  </div>
                  <button
                    className="db-card-open"
                    onClick={() => void openDashboard(d)}
                  >
                    <h2>{d.name}</h2>
                    <p>{d.description || "Workspace dashboard"}</p>
                  </button>
                  <small>
                    {d.visibility} · {d.configuration.widgets.length} widgets ·
                    revision {d.revision}
                  </small>
                  <footer>
                    <span>{new Date(d.updated_at).toLocaleDateString()}</span>
                    <details className="db-menu">
                      <summary
                        role="button"
                        aria-label={`Options for ${d.name}`}
                      >
                        <MoreHorizontal size={19} />
                      </summary>
                      <div>
                        {!d.deleted_at && (
                          <button onClick={() => void action(d, "duplicate")}>
                            Duplicate privately
                          </button>
                        )}
                        {d.can_manage &&
                          (d.deleted_at ? (
                            <>
                              <button onClick={() => void action(d, "restore")}>
                                Restore
                              </button>
                              <button
                                onClick={() => {
                                  setConfirmName("");
                                  setConfirmation({
                                    title: "Permanently delete this dashboard?",
                                    target: d,
                                    run: async () => {},
                                  });
                                }}
                              >
                                Delete permanently
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() =>
                                setConfirmation({
                                  title: `Move “${d.name}” to trash?`,
                                  run: () => action(d, "trash"),
                                })
                              }
                            >
                              Move to trash
                            </button>
                          ))}
                      </div>
                    </details>
                  </footer>
                </article>
              ))}
            </div>
          )}
        </>
      ) : active && catalogData && !active.deleted_at ? (
        <>
          {recover && !dirty && saved?.can_edit && (
            <div className="db-info">
              A local draft is available.{" "}
              <button
                onClick={() => {
                  setDraft(recover);
                  setEditing(true);
                  setRecover(null);
                }}
              >
                Recover draft
              </button>
              <button
                onClick={() => {
                  setRecover(null);
                  localStorage.removeItem(storageKey);
                }}
              >
                Dismiss
              </button>
            </div>
          )}
          <div className="db-canvas-toolbar">
            <div>
              <span className="db-sharing">
                <Share2 size={14} />
                {active.visibility}
              </span>
              <small>
                Revision {saved?.revision} ·{" "}
                {dirty
                  ? "Unsaved changes"
                  : data.isFetching
                    ? "Refreshing…"
                    : "Saved"}
              </small>
            </div>
            <div>
              <Button variant="outline" onClick={() => setPanel("filters")}>
                <Filter size={15} />
                Filters
              </Button>
              <Button
                variant="outline"
                disabled={data.isFetching}
                onClick={() => void data.refetch()}
                aria-label="Refresh dashboard"
              >
                <RefreshCw size={16} />
              </Button>
              {saved?.can_edit && (
                <Button
                  variant="outline"
                  onClick={() => setPanel("history")}
                  aria-label="Dashboard history"
                >
                  <History size={16} />
                </Button>
              )}
              {saved?.can_manage && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditing(true);
                    setPanel("manage");
                  }}
                >
                  <Share2 size={15} />
                  Sharing & settings
                </Button>
              )}
              <details className="db-menu">
                <summary role="button" aria-label="Dashboard actions">
                  <MoreHorizontal size={20} />
                </summary>
                <div>
                  <button onClick={() => void png()}>Export PNG</button>
                  <button onClick={() => window.print()}>
                    Print / save PDF
                  </button>
                  <button
                    onClick={() =>
                      exportCSV(
                        active.name,
                        Object.entries(data.data?.widgets || {}).flatMap(
                          ([id, value]) =>
                            widgetRows(value).map((row) => ({
                              widget: config.widgets.find((w) => w.id === id)
                                ?.title,
                              ...row,
                            })),
                        ),
                      )
                    }
                  >
                    Export CSV
                  </button>
                  <button onClick={() => setPresentation(true)}>
                    Presentation mode
                  </button>
                  <button onClick={() => void action(active, "duplicate")}>
                    Duplicate privately
                  </button>
                  {saved?.can_manage && (
                    <>
                      <button
                        onClick={() => {
                          setDraft({ ...active, archived: !active.archived });
                          setEditing(true);
                        }}
                      >
                        {" "}
                        {active.archived ? "Unarchive" : "Archive"} on save
                      </button>
                      <button
                        onClick={() =>
                          setConfirmation({
                            title: "Move dashboard to trash?",
                            run: () => action(saved, "trash"),
                          })
                        }
                      >
                        Move to trash
                      </button>
                    </>
                  )}
                </div>
              </details>
            </div>
          </div>
          {editing && saved?.can_edit && (
            <div className="db-edit-toolbar">
              <strong>Build your dashboard</strong>
              <Button
                variant="outline"
                disabled={!past.length}
                aria-label="Undo dashboard change"
                onClick={undo}
              >
                <Undo2 size={16} />
              </Button>
              <Button
                variant="outline"
                disabled={!future.length}
                aria-label="Redo dashboard change"
                onClick={redo}
              >
                <Redo2 size={16} />
              </Button>
              <Button variant="outline" onClick={() => setPanel("gallery")}>
                <Plus size={16} />
                Add widget
              </Button>
              <Button variant="outline" onClick={() => setPanel("suggest")}>
                <Sparkles size={16} />
                Guided layout
              </Button>
              <Button disabled={!dirty || pending} onClick={() => void save()}>
                <Save size={16} />
                {pending ? "Saving…" : "Save dashboard"}
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  setConfirmation({
                    title: "Discard dashboard changes?",
                    run: async () => {
                      setDraft(copy(saved));
                      setEditing(false);
                      setPast([]);
                      setFuture([]);
                      localStorage.removeItem(storageKey);
                    },
                  })
                }
              >
                Discard
              </Button>
            </div>
          )}
          {data.isError && (
            <p className="db-error" role="alert">
              Dashboard data could not load.{" "}
              <button onClick={() => void data.refetch()}>Retry</button>
            </p>
          )}
          <div ref={canvas} className="db-canvas">
            <GridLayout
              width={width}
              cols={12}
              rowHeight={27}
              margin={[12, 12]}
              containerPadding={[0, 0]}
              layout={layout}
              isDraggable={editing && width >= 1050}
              isResizable={editing && width >= 1050}
              draggableHandle=".db-drag-handle"
              draggableCancel="button,details,a,input"
              onDragStop={onLayout}
              onResizeStop={onLayout}
              compactType={null}
            >
              {visible.map((w) => {
                const spec = catalogData.widgets.find((s) => s.id === w.type);
                return (
                  <section
                    key={w.id}
                    className={`db-widget ${spec?.view === "metric" ? "db-widget-metric" : ""}`}
                    style={
                      { "--widget-accent": w.color } as React.CSSProperties
                    }
                    aria-label={w.title}
                  >
                    <header>
                      <span className="db-widget-icon">
                        <WidgetSymbol widget={w} />
                      </span>
                      <h2 title={w.description}>{w.title}</h2>
                      {editing && !w.locked && (
                        <span className="db-drag-handle" title="Drag widget">
                          <GripVertical size={15} />
                        </span>
                      )}
                      <details className="db-menu">
                        <summary
                          role="button"
                          aria-label={`Options for widget ${w.title}`}
                        >
                          <MoreHorizontal size={17} />
                        </summary>
                        <div>
                          <button onClick={() => void inspect(w)}>
                            View data / drill down
                          </button>
                          <button onClick={() => setExpanded(w)}>
                            Expand widget
                          </button>
                          <button
                            onClick={() =>
                              exportCSV(
                                w.title,
                                widgetRows(
                                  data.data?.widgets[w.id] || {
                                    state: "ready",
                                    message: "",
                                  },
                                ),
                              )
                            }
                          >
                            Export widget CSV
                          </button>
                          {editing && saved?.can_edit && (
                            <>
                              <button onClick={() => setWidget(w)}>
                                Widget settings
                              </button>
                              <button
                                onClick={() => {
                                  if (config.widgets.length >= 50)
                                    return setError("Maximum 50 widgets.");
                                  const dupe = {
                                    ...copy(w),
                                    id:
                                      "w_" +
                                      crypto.randomUUID().replace(/-/g, ""),
                                    title: w.title + " copy",
                                    y: Math.max(
                                      0,
                                      ...config.widgets.map((v) => v.y + v.h),
                                    ),
                                  };
                                  changeConfig({
                                    ...config,
                                    widgets: [...config.widgets, dupe],
                                  });
                                }}
                              >
                                Duplicate widget
                              </button>
                              <button
                                onClick={() =>
                                  updateWidget({ ...w, locked: !w.locked })
                                }
                              >
                                {w.locked ? "Unlock" : "Lock"} position
                              </button>
                              <button
                                onClick={() =>
                                  updateWidget({ ...w, hidden: true })
                                }
                              >
                                Hide widget
                              </button>
                              <button
                                onClick={() => {
                                  const i = config.widgets.findIndex(
                                    (item) => item.id === w.id,
                                  );
                                  if (i > 0) {
                                    const items = [...config.widgets];
                                    [items[i - 1], items[i]] = [
                                      items[i],
                                      items[i - 1],
                                    ];
                                    changeConfig({
                                      ...config,
                                      widgets: pack(items),
                                    });
                                  }
                                }}
                              >
                                Move earlier
                              </button>
                              <button
                                onClick={() =>
                                  changeConfig({
                                    ...config,
                                    widgets: config.widgets.filter(
                                      (v) => v.id !== w.id,
                                    ),
                                  })
                                }
                              >
                                Remove widget
                              </button>
                            </>
                          )}
                        </div>
                      </details>
                    </header>
                    <div className="db-widget-content">
                      <WidgetBoundary
                        reset={JSON.stringify(w) + data.dataUpdatedAt}
                      >
                        {spec && (
                          <WidgetContent
                            widget={w}
                            spec={spec}
                            data={data.data?.widgets[w.id]}
                            onDrill={(label) => void inspect(w, label)}
                            onRetry={() =>
                              void run(async () => {
                                const result = await queryDashboard(active.id, {
                                  ...config,
                                  widgets: [w],
                                });
                                qc.setQueryData<Batch>(
                                  ["dashboard-data", saved?.id, queryConfig],
                                  (old) =>
                                    old
                                      ? {
                                          ...old,
                                          widgets: {
                                            ...old.widgets,
                                            ...result.widgets,
                                          },
                                        }
                                      : result,
                                );
                              })
                            }
                          />
                        )}
                      </WidgetBoundary>
                    </div>
                  </section>
                );
              })}
            </GridLayout>
            {!visible.length && (
              <section className="db-onboarding">
                <LayoutGrid size={38} />
                <h2>A blank canvas for your best ideas</h2>
                <p>Add metrics, charts, task lists and project insights.</p>
                {saved?.can_edit && (
                  <Button
                    onClick={() => {
                      setEditing(true);
                      setPanel("gallery");
                    }}
                  >
                    Add your first widget
                  </Button>
                )}
              </section>
            )}
          </div>
          {editing && config.widgets.some((w) => w.hidden) && (
            <div className="db-hidden-widgets">
              <strong>Hidden widgets</strong>
              {config.widgets
                .filter((w) => w.hidden)
                .map((w) => (
                  <button
                    key={w.id}
                    onClick={() => updateWidget({ ...w, hidden: false })}
                  >
                    Show {w.title}
                  </button>
                ))}
            </div>
          )}
          <small className="db-data-note">
            {data.data
              ? `Updated ${new Date(data.data.generated_at).toLocaleTimeString()} · ${data.data.scope.visible_projects} accessible projects · ${data.data.scope.time_scope}`
              : "Widget data respects your current project permissions."}
          </small>
          {presentation && (
            <Button
              className="db-exit-presentation"
              onClick={() => setPresentation(false)}
            >
              Exit presentation
            </Button>
          )}
        </>
      ) : (
        <p role="status">
          {list.isPending
            ? "Loading dashboard…"
            : active?.deleted_at
              ? "This dashboard is in Trash. Restore it from Browse → Trash to load its widgets."
              : "Choose a dashboard from Browse."}
        </p>
      )}
      {wizard && catalogData && (
        <DashboardWizard
          catalog={catalogData}
          workspaces={workspaces.data || []}
          onClose={() => setWizard(false)}
          onCreate={async (payload) => {
            const next = (await api.post<Dashboard>(base, payload)).data;
            await refreshList();
            setParams({ dashboard: String(next.id) });
            setLibrary(false);
            setWizard(false);
          }}
        />
      )}
      {widget && catalogData && (
        <WidgetSettings
          key={widget.id}
          initial={widget}
          catalog={catalogData}
          scope={scope.data}
          onApply={updateWidget}
          onClose={() => setWidget(null)}
        />
      )}
      <Panel
        open={panel === "gallery"}
        title="Widget library"
        description="100 widget types. Connected widgets use real records; unavailable data sources are explained before adding."
        onClose={() => setPanel("")}
        wide
      >
        <div className="db-search">
          <Search size={16} />
          <input
            aria-label="Search widgets"
            value={gallerySearch}
            onChange={(e) => setGallerySearch(e.target.value)}
            placeholder="Search metrics, charts, projects…"
          />
        </div>
        <nav className="db-category-tabs">
          {[
            "All",
            ...new Set(catalogData?.widgets.map((w) => w.category) || []),
          ].map((c) => (
            <button
              key={c}
              className={category === c ? "selected" : ""}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </nav>
        <div className="db-gallery">
          {catalogData?.widgets
            .filter(
              (w) =>
                (category === "All" || w.category === category) &&
                w.title.toLowerCase().includes(gallerySearch.toLowerCase()),
            )
            .map((s) => (
              <button
                key={s.id}
                disabled={config.widgets.length >= 50}
                onClick={() => add(s)}
              >
                <BarChart3 size={23} />
                <strong>{s.title}</strong>
                <small>{s.requirement || `${s.category} · ${s.source}`}</small>
                <span>
                  <Plus size={14} />
                  Add widget
                </span>
              </button>
            ))}
        </div>
      </Panel>
      <Panel
        open={panel === "filters"}
        title="Dashboard filters"
        description="Widgets inherit these filters unless they have their own override. Viewer changes are temporary."
        onClose={() => setPanel("")}
      >
        <FilterFields
          value={config.filters}
          onChange={(filters) => changeConfig({ ...config, filters })}
          scope={scope.data}
        />
        <Button
          variant="outline"
          onClick={() => changeConfig({ ...config, filters: emptyFilters() })}
        >
          Reset filters
        </Button>
        {saved?.can_edit && (
          <div className="db-field">
            <span>Save filter preset</span>
            <input
              aria-label="Filter preset name"
              maxLength={60}
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
            />
            <Button
              disabled={
                !presetName.trim() ||
                Object.keys(config.filter_presets).length >= 12
              }
              onClick={() => {
                changeConfig({
                  ...config,
                  filter_presets: {
                    ...config.filter_presets,
                    [presetName.trim()]: copy(config.filters),
                  },
                });
                setPresetName("");
                setEditing(true);
              }}
            >
              Save preset to draft
            </Button>
          </div>
        )}
        <div className="db-preset-list">
          {Object.entries(config.filter_presets).map(([name, filters]) => (
            <div key={name}>
              <button
                onClick={() =>
                  changeConfig({ ...config, filters: copy(filters) })
                }
              >
                {name}
              </button>
              {editing && (
                <button
                  aria-label={`Delete preset ${name}`}
                  onClick={() => {
                    const presets = { ...config.filter_presets };
                    delete presets[name];
                    changeConfig({ ...config, filter_presets: presets });
                  }}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      </Panel>
      <Panel
        open={panel === "manage"}
        title="Dashboard settings"
        description="Changes are applied when you save the dashboard. Only the owner can change access."
        onClose={() => setPanel("")}
      >
        {active && (
          <>
            <label className="db-field">
              <span>Dashboard name</span>
              <input
                value={active.name}
                maxLength={120}
                onChange={(e) => commit({ ...active, name: e.target.value })}
              />
            </label>
            <label className="db-field">
              <span>Description</span>
              <textarea
                value={active.description}
                maxLength={2000}
                onChange={(e) =>
                  commit({ ...active, description: e.target.value })
                }
              />
            </label>
            <Choice
              label="Visibility"
              value={active.visibility}
              onChange={(v) =>
                commit({ ...active, visibility: v as Dashboard["visibility"] })
              }
              options={["private", "selected", "workspace", "organization"].map(
                (value) => ({
                  value,
                  label:
                    value === "organization"
                      ? "Organization members only"
                      : value,
                }),
              )}
            />
            {active.visibility === "selected" && (
              <div className="db-share-members">
                {members.data
                  ?.filter((m) => m.user_id !== active.owner_id)
                  .map((m) => (
                    <div key={m.user_id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={active.shared_users.some(
                            (s) => s.user_id === m.user_id,
                          )}
                          onChange={(e) =>
                            commit({
                              ...active,
                              shared_users: e.target.checked
                                ? [
                                    ...active.shared_users,
                                    { user_id: m.user_id, role: "viewer" },
                                  ]
                                : active.shared_users.filter(
                                    (s) => s.user_id !== m.user_id,
                                  ),
                            })
                          }
                        />
                        {m.email}
                      </label>
                      {active.shared_users.some(
                        (s) => s.user_id === m.user_id,
                      ) && (
                        <Choice
                          label={`Access for ${m.email}`}
                          value={
                            active.shared_users.find(
                              (s) => s.user_id === m.user_id,
                            )!.role
                          }
                          onChange={(role) =>
                            commit({
                              ...active,
                              shared_users: active.shared_users.map((s) =>
                                s.user_id === m.user_id
                                  ? { ...s, role: role as "viewer" | "editor" }
                                  : s,
                              ),
                            })
                          }
                          options={[
                            { value: "viewer", label: "Viewer" },
                            ...(m.role !== "Guest"
                              ? [{ value: "editor", label: "Editor" }]
                              : []),
                          ]}
                        />
                      )}
                    </div>
                  ))}
              </div>
            )}
            <Choice
              label="Automatic refresh"
              value={String(config.refresh_seconds)}
              onChange={(v) =>
                changeConfig({ ...config, refresh_seconds: Number(v) })
              }
              options={[30, 60, 120, 300, 600, 3600].map((n) => ({
                value: String(n),
                label: `Every ${n} seconds`,
              }))}
            />
            <Choice
              label="Dashboard density"
              value={config.density}
              onChange={(v) =>
                changeConfig({
                  ...config,
                  density: v as Configuration["density"],
                })
              }
              options={["comfortable", "compact"].map((value) => ({
                value,
                label: value,
              }))}
            />
            <Button
              variant="outline"
              onClick={() =>
                changeConfig({ ...config, widgets: pack(config.widgets) })
              }
            >
              Reset widget positions
            </Button>
            <label className="db-check">
              <input
                type="checkbox"
                checked={active.archived}
                onChange={(e) =>
                  commit({ ...active, archived: e.target.checked })
                }
              />
              Archive this dashboard on save
            </label>
            <Choice
              label="Transfer ownership"
              value=""
              onChange={(id) => {
                if (id)
                  setConfirmation({
                    title:
                      "Transfer ownership? The new owner will control access and deletion.",
                    run: async () => {
                      await api.post(`${base}/${active.id}/transfer`, {
                        revision: saved!.revision,
                        owner_id: Number(id),
                      });
                      await refreshList();
                      setPanel("");
                      setLibrary(true);
                    },
                  });
              }}
              options={[
                { value: "", label: "Choose a workspace member" },
                ...(members.data || [])
                  .filter(
                    (m) => m.role !== "Guest" && m.user_id !== active.owner_id,
                  )
                  .map((m) => ({ value: String(m.user_id), label: m.email })),
              ]}
            />
            <p className="db-info">
              Sharing a dashboard never grants access to additional project
              data.
            </p>
          </>
        )}
      </Panel>
      <Panel
        open={panel === "history"}
        title="Dashboard history"
        description="Restore a previous configuration. Project records are never rolled back."
        onClose={() => setPanel("")}
      >
        {history.isPending ? (
          <p>Loading history…</p>
        ) : history.isError ? (
          <p role="alert">
            History could not load.{" "}
            <button onClick={() => void history.refetch()}>Retry</button>
          </p>
        ) : !history.data?.length ? (
          <p>No previous saved versions yet.</p>
        ) : (
          history.data.map((h) => (
            <article className="db-history" key={h.id}>
              <strong>
                Revision {h.revision} · {h.name}
              </strong>
              <small>
                {new Date(h.saved_at).toLocaleString()} · editor #{h.editor_id}
              </small>
              <p>
                {h.configuration.widgets.length} widgets:{" "}
                {h.configuration.widgets.map((w) => w.title).join(", ")}
              </p>
              <Button
                variant="outline"
                disabled={pending}
                onClick={() =>
                  setConfirmation({
                    title: `Restore revision ${h.revision}? Unsaved changes will be replaced.`,
                    run: async () => {
                      await api.post(
                        `${base}/${saved!.id}/history/${h.id}/restore`,
                        { revision: saved!.revision },
                      );
                      localStorage.removeItem(storageKey);
                      setEditing(false);
                      setDraft(null);
                      await refreshList();
                      setPanel("");
                    },
                  })
                }
              >
                Restore this version
              </Button>
            </article>
          ))
        )}
      </Panel>
      <Panel
        open={panel === "suggest"}
        title="Guided dashboard layout"
        description="Use guided mode or an existing configured assistant provider. Suggestions are previews; your records remain unchanged until you save."
        onClose={() => setPanel("")}
      >
        <Choice
          label="Suggestion mode"
          value={suggestProvider}
          onChange={setSuggestProvider}
          options={[
            { value: "guided", label: "Guided — no provider required" },
            { value: "openai", label: "Configured OpenAI provider" },
            { value: "claude", label: "Configured Claude provider" },
            { value: "gemini", label: "Configured Gemini provider" },
          ]}
        />
        <label className="db-field">
          <span>What do you want to track?</span>
          <textarea
            maxLength={2000}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Track sprint delivery and team workload"
          />
        </label>
        <Button
          disabled={prompt.trim().length < 3 || pending}
          onClick={() =>
            void run(async () => {
              const result = (
                await api.post(base + "/suggest", {
                  prompt,
                  workspace_id: active?.workspace_id,
                  provider:
                    suggestProvider === "guided" ? null : suggestProvider,
                })
              ).data;
              setSuggestion(result.configuration);
              setSuggestMessage(result.message);
            })
          }
        >
          Suggest layout
        </Button>
        {suggestion && (
          <section className="db-create-review">
            <h3>Layout preview</h3>
            <p>{suggestMessage}</p>
            <p>{suggestion.widgets.map((w) => w.title).join(" · ")}</p>
            <Button
              onClick={() => {
                changeConfig({ ...suggestion, filters: config.filters });
                setPanel("");
                setSuggestion(null);
              }}
            >
              Apply to draft
            </Button>
          </section>
        )}
      </Panel>
      <Panel
        open={!!expanded}
        title={expanded?.title || "Expanded widget"}
        description="Live data for your current dashboard scope."
        onClose={() => setExpanded(null)}
        wide
      >
        {expanded && catalogData && (
          <div className="db-expanded-widget">
            <WidgetContent
              widget={expanded}
              spec={catalogData.widgets.find((s) => s.id === expanded.type)!}
              data={data.data?.widgets[expanded.id]}
              onDrill={(label) => void inspect(expanded, label)}
              onRetry={() => void data.refetch()}
            />
          </div>
        )}
      </Panel>
      <Panel
        open={!!drill}
        title={drill?.title || "Widget data"}
        description="Up to 100 authorized matching records. Open a record to inspect its details."
        onClose={() => setDrill(null)}
        wide
      >
        {drill && (
          <>
            <Button
              variant="outline"
              onClick={() => exportCSV(drill.title, drill.rows)}
            >
              <Download size={15} />
              Export CSV
            </Button>
            <DataTable rows={drill.rows} source={drill.source} />
          </>
        )}
      </Panel>
      <Panel
        open={!!confirmation}
        title={confirmation?.title || "Confirm action"}
        description={
          confirmation?.target
            ? "Type the dashboard name to permanently remove its definition and history."
            : "Review this action before continuing."
        }
        onClose={() => setConfirmation(null)}
      >
        {confirmation?.target && (
          <label className="db-field">
            <span>{confirmation.target.name}</span>
            <input
              aria-label="Confirm dashboard name"
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
            />
          </label>
        )}
        <footer className="db-panel-actions">
          <Button variant="outline" onClick={() => setConfirmation(null)}>
            Cancel
          </Button>
          <Button
            disabled={
              pending ||
              (!!confirmation?.target &&
                confirmName !== confirmation.target.name)
            }
            onClick={() =>
              void run(async () => {
                if (confirmation?.target) {
                  const d = confirmation.target;
                  await api.delete(`${base}/${d.id}`, {
                    data: { revision: d.revision, name: confirmName },
                  });
                  await refreshList();
                  setLibrary(true);
                } else await confirmation?.run();
                setConfirmation(null);
              })
            }
          >
            Confirm
          </Button>
        </footer>
      </Panel>
    </main>
  );
}
