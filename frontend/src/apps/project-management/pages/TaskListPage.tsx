import { useCallback, useEffect, useMemo, useState, Fragment, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Columns3, RefreshCw, Save, Search, SlidersHorizontal, Star, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn, formatDate, statusColor } from "@/lib/utils";
import InlineSubtaskComposer from "../components/InlineSubtaskComposer";
import TaskViewPicker from "../components/TaskViewPicker";
import { savedViewsAPI, tasksAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";
import type { PMSSavedFilter, PMSTask, PMSTaskListItem, PMSTaskListResponse, TaskStatus } from "../types";

type SortOrder = "asc" | "desc";

type FilterState = {
  projectId: string;
  sprintId: string;
  epicId: string;
  status: string;
  priority: string;
  assigneeId: string;
  reporterId: string;
  tag: string;
  dueFrom: string;
  dueTo: string;
  createdFrom: string;
  createdTo: string;
  updatedFrom: string;
  updatedTo: string;
  storyPointsMin: string;
  storyPointsMax: string;
  search: string;
};

type ColumnKey =
  | "task"
  | "title"
  | "project"
  | "epic"
  | "sprint"
  | "status"
  | "priority"
  | "assignee"
  | "reporter"
  | "story_points"
  | "subtasks"
  | "tags"
  | "due_date"
  | "created_at"
  | "updated_at";

const defaultFilters: FilterState = {
  projectId: "",
  sprintId: "",
  epicId: "",
  status: "",
  priority: "",
  assigneeId: "",
  reporterId: "",
  tag: "",
  dueFrom: "",
  dueTo: "",
  createdFrom: "",
  createdTo: "",
  updatedFrom: "",
  updatedTo: "",
  storyPointsMin: "",
  storyPointsMax: "",
  search: "",
};

const columns: { key: ColumnKey; label: string }[] = [
  { key: "task", label: "Task key" },
  { key: "title", label: "Title" },
  { key: "project", label: "Project" },
  { key: "epic", label: "Epic" },
  { key: "sprint", label: "Sprint" },
  { key: "status", label: "Status" },
  { key: "priority", label: "Priority" },
  { key: "assignee", label: "Assignee" },
  { key: "reporter", label: "Reporter" },
  { key: "story_points", label: "Story points" },
  { key: "subtasks", label: "Sub-tasks" },
  { key: "tags", label: "Tags" },
  { key: "due_date", label: "Due date" },
  { key: "created_at", label: "Created" },
  { key: "updated_at", label: "Updated" },
];

const sortableColumns: Partial<Record<ColumnKey, string>> = {
  status: "status",
  priority: "priority",
  story_points: "storyPoints",
  due_date: "dueDate",
  created_at: "createdDate",
  updated_at: "updatedDate",
};

const taskStatuses: TaskStatus[] = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done", "Cancelled"];
const priorityOrder: Record<string, number> = { Urgent: 4, High: 3, Medium: 2, Low: 1 };

const initialVisibleColumns = columns.reduce<Record<ColumnKey, boolean>>((acc, column) => {
  acc[column.key] = ["task", "title", "project", "status", "priority", "assignee", "due_date"].includes(column.key);
  return acc;
}, {} as Record<ColumnKey, boolean>);

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
        {children}
      </select>
    </label>
  );
}

function SortButton({
  column,
  label,
  sortBy,
  sortOrder,
  onSort,
}: {
  column: ColumnKey;
  label: string;
  sortBy: string;
  sortOrder: SortOrder;
  onSort: (column: ColumnKey) => void;
}) {
  const sortKey = sortableColumns[column];
  if (!sortKey) return <span>{label}</span>;
  const active = sortBy === sortKey;
  return (
    <button type="button" onClick={() => onSort(column)} className="inline-flex items-center gap-1 font-semibold text-foreground">
      {label}
      {active && sortOrder === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : null}
      {active && sortOrder === "desc" ? <ChevronDown className="h-3.5 w-3.5" /> : null}
    </button>
  );
}

function TaskBadges({ task }: { task: PMSTaskListItem }) {
  return (
    <div className="flex flex-wrap gap-1">
      {(task.tags || []).length ? task.tags?.map((tag) => {
        const label = typeof tag === "string" ? tag : tag.name;
        return <Badge key={label} variant="outline" className="max-w-28 truncate">{label}</Badge>;
      }) : <span className="text-muted-foreground">-</span>}
    </div>
  );
}

export default function TaskListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<PMSTaskListResponse | null>(null);
  const [filters, setFilters] = useState<FilterState>({ ...defaultFilters, projectId: searchParams.get("projectId") || "" });
  const [sortBy, setSortBy] = useState("updatedDate");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [columnSearch, setColumnSearch] = useState("");
  const layout = searchParams.get("layout") || "list";
  const [groupByStatus, setGroupByStatus] = useState(searchParams.get("layout") !== "table");
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([]);
  const [visibleColumns, setVisibleColumns] = useState<Record<ColumnKey, boolean>>(() => {
    try { return { ...initialVisibleColumns, ...JSON.parse(localStorage.getItem("pms.task-columns.v1") || "{}"), title: true }; }
    catch { return initialVisibleColumns; }
  });
  useEffect(() => { try { localStorage.setItem("pms.task-columns.v1", JSON.stringify(visibleColumns)); } catch { /* Saved views still work when storage is unavailable. */ } }, [visibleColumns]);
  useEffect(() => { setGroupByStatus(layout !== "table"); }, [layout]);
  useEffect(() => {
    const projectId = searchParams.get("projectId");
    if (projectId !== null) setFilters(current => ({ ...current, projectId }));
  }, [searchParams]);
  const [inlineParent, setInlineParent] = useState<number | null>(null);
  const [createdChildren, setCreatedChildren] = useState<Record<number, PMSTask[]>>({});
  const [inlineNotice, setInlineNotice] = useState("");
  function subtaskCreated(parent: PMSTaskListItem, child: PMSTask) {
    setCreatedChildren(current => ({ ...current, [parent.id]: [...(current[parent.id] || []), child] }));
    setData(current => current ? { ...current, items: current.items.map(item => item.id === parent.id ? { ...item, subtask_count: (item.subtask_count || 0) + 1 } : item) } : current);
    setInlineParent(null); setInlineNotice(`Created ${child.task_key}: ${child.title}`);
  }
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([]);
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkPriority, setBulkPriority] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingTaskId, setUpdatingTaskId] = useState<number | null>(null);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [savedViews, setSavedViews] = useState<PMSSavedFilter[]>([]);
  const [selectedViewId, setSelectedViewId] = useState(searchParams.get("view") || "");
  const [savePanelOpen, setSavePanelOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [viewVisibility, setViewVisibility] = useState<"private" | "team" | "workspace">("private");
  const [viewDefault, setViewDefault] = useState(false);
  const [viewSaving, setViewSaving] = useState(false);
  const [viewsLoaded, setViewsLoaded] = useState(false);
  const [appliedUrlView, setAppliedUrlView] = useState(false);

  const loadTasks = useCallback((active = true) => {
    setLoading(true);
    setError(null);
    tasksAPI
      .listAll({ ...filters, sortBy, sortOrder, page, pageSize })
      .then((response) => {
        if (active) setData(response);
      })
      .catch((err) => {
        if (active) setError(err?.response?.data?.detail || "Unable to load tasks.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
  }, [filters, page, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    let active = true;
    loadTasks(active);
    return () => {
      active = false;
    };
  }, [loadTasks]);

  usePMSRealtime({
    onEvent: (event) => {
      if (event.type.startsWith("task.") || event.type === "sprint.updated" || event.type === "project.updated") {
        loadTasks(true);
      }
    },
    onFallbackPoll: () => loadTasks(true),
    showToast: false,
  });

  useEffect(() => {
    let active = true;
    savedViewsAPI
      .list("task")
      .then((views) => {
        if (!active) return;
        setSavedViews(views);
        setViewsLoaded(true);
      })
      .catch(() => {
        if (active) setViewsLoaded(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const taskGroups = useMemo(() => {
    const items = data?.items || [];
    if (!groupByStatus) return [{ status: "All tasks", items }];
    return [...taskStatuses, ...new Set(items.map(task => task.status).filter(status => !taskStatuses.includes(status)))].map(status => ({ status, items: items.filter(task => task.status === status) })).filter(group => group.items.length);
  }, [data?.items, groupByStatus]);
  const toggleGroup = (status: string) => {
    setCollapsedGroups(current => current.includes(status)
      ? current.filter(item => item !== status)
      : [...current, status]);
  };
  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  const visibleColumnList = useMemo(() => columns.filter((column) => column.key === "title" || visibleColumns[column.key]), [visibleColumns]);
  const currentPageTaskIds = useMemo(() => data?.items.map((task) => task.id) || [], [data?.items]);
  const selectedTasks = useMemo(() => data?.items.filter((task) => selectedTaskIds.includes(task.id)) || [], [data?.items, selectedTaskIds]);
  const allPageTasksSelected = Boolean(currentPageTaskIds.length) && currentPageTaskIds.every((id) => selectedTaskIds.includes(id));
  const totalPages = Math.max(data?.pages || 1, 1);
  const firstResult = data?.total ? (page - 1) * pageSize + 1 : 0;
  const lastResult = data?.total ? Math.min(page * pageSize, data.total) : 0;

  useEffect(() => {
    setSelectedTaskIds((current) => current.filter((id) => currentPageTaskIds.includes(id)));
  }, [currentPageTaskIds]);

  useEffect(() => {
    if (!viewsLoaded || selectedViewId) return;
    const defaultView = savedViews.find((view) => view.is_default);
    if (defaultView) applySavedView(defaultView, false);
  }, [viewsLoaded, savedViews, selectedViewId]);

  useEffect(() => {
    if (!viewsLoaded || appliedUrlView || !selectedViewId) return;
    const view = savedViews.find((item) => item.id === Number(selectedViewId));
    if (view) {
      applySavedView(view, false);
      setAppliedUrlView(true);
    }
  }, [viewsLoaded, savedViews, selectedViewId, appliedUrlView]);

  const setFilter = (key: keyof FilterState, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters(defaultFilters);
    setSelectedViewId("");
    setSearchParams({});
    setPage(1);
  };

  const applySavedView = (view: PMSSavedFilter, updateUrl = true) => {
    const nextFilters = { ...defaultFilters, ...(view.filters || {}) } as FilterState;
    const nextSort = (view.sort || {}) as { sortBy?: string; sortOrder?: SortOrder };
    const nextColumns = view.columns as Partial<Record<ColumnKey, boolean>> | ColumnKey[] | undefined;
    setFilters(nextFilters);
    setSortBy(nextSort.sortBy || "updatedDate");
    setSortOrder(nextSort.sortOrder || "desc");
    if (Array.isArray(nextColumns)) {
      setVisibleColumns(columns.reduce<Record<ColumnKey, boolean>>((acc, column) => {
        acc[column.key] = nextColumns.includes(column.key);
        return acc;
      }, {} as Record<ColumnKey, boolean>));
    } else if (nextColumns && typeof nextColumns === "object") {
      setVisibleColumns({ ...initialVisibleColumns, ...nextColumns });
    }
    setSelectedViewId(String(view.id));
    setViewName(view.name);
    setViewVisibility((view.visibility as "private" | "team" | "workspace") || (view.is_shared ? "workspace" : "private"));
    setViewDefault(Boolean(view.is_default));
    setPage(1);
    if (updateUrl) setSearchParams({ view: String(view.id) });
  };

  const reloadSavedViews = () => savedViewsAPI.list("task").then(setSavedViews).catch(() => undefined);

  const currentViewPayload = () => ({
    entity_type: "task",
    view_type: "task_list",
    filters,
    sort: { sortBy, sortOrder },
    columns: visibleColumns,
    visibility: viewVisibility,
    is_default: viewDefault,
    is_shared: viewVisibility !== "private",
  });

  const saveCurrentView = async () => {
    if (!viewName.trim()) {
      setError("Give this view a name before saving.");
      return;
    }
    setViewSaving(true);
    setError(null);
    try {
      const saved = await savedViewsAPI.create({ ...currentViewPayload(), name: viewName.trim() });
      await reloadSavedViews();
      setSelectedViewId(String(saved.id));
      setSearchParams({ view: String(saved.id) });
      setSavePanelOpen(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save view.");
    } finally {
      setViewSaving(false);
    }
  };

  const updateSelectedView = async () => {
    const viewId = Number(selectedViewId);
    if (!viewId) return;
    setViewSaving(true);
    setError(null);
    try {
      const updated = await savedViewsAPI.update(viewId, { ...currentViewPayload(), name: viewName.trim() || "Untitled view" });
      setSavedViews((items) => items.map((item) => item.id === updated.id ? updated : item));
      setSavePanelOpen(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to update view.");
    } finally {
      setViewSaving(false);
    }
  };

  const deleteSelectedView = async () => {
    const viewId = Number(selectedViewId);
    if (!viewId) return;
    setViewSaving(true);
    setError(null);
    try {
      await savedViewsAPI.delete(viewId);
      setSavedViews((items) => items.filter((item) => item.id !== viewId));
      setSelectedViewId("");
      setSearchParams({});
      setSavePanelOpen(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to delete view.");
    } finally {
      setViewSaving(false);
    }
  };

  const handleViewSelect = (viewId: string) => {
    if (!viewId) {
      setSelectedViewId("");
      setSearchParams({});
      return;
    }
    const view = savedViews.find((item) => item.id === Number(viewId));
    if (view) applySavedView(view);
  };

  const handleSort = (column: ColumnKey) => {
    const nextSortBy = sortableColumns[column];
    if (!nextSortBy) return;
    if (sortBy === nextSortBy) {
      setSortOrder((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(nextSortBy);
      setSortOrder("desc");
    }
    setPage(1);
  };

  const openTask = (task: PMSTaskListItem) => {
    navigate(`/pms/tasks/${task.id}`);
  };

  const toggleTaskSelection = (taskId: number, checked: boolean) => {
    setSelectedTaskIds((current) => checked ? [...new Set([...current, taskId])] : current.filter((id) => id !== taskId));
  };

  const togglePageSelection = (checked: boolean) => {
    setSelectedTaskIds(checked ? currentPageTaskIds : []);
  };

  const updateStatus = async (task: PMSTaskListItem, status: TaskStatus) => {
    const previousStatus = task.status;
    setUpdatingTaskId(task.id);
    setData((current) => current ? {
      ...current,
      items: current.items.map((item) => item.id === task.id ? { ...item, status } : item),
    } : current);
    try {
      await tasksAPI.updateStatus(task.id, status);
    } catch (err: any) {
      setData((current) => current ? {
        ...current,
        items: current.items.map((item) => item.id === task.id ? { ...item, status: previousStatus } : item),
      } : current);
      setError(err?.response?.data?.detail || "Unable to update task status.");
    } finally {
      setUpdatingTaskId(null);
    }
  };

  const applyBulkUpdate = async () => {
    if (!selectedTaskIds.length || (!bulkStatus && !bulkPriority)) return;
    const previousItems = data?.items || [];
    const payload = {
      task_ids: selectedTaskIds,
      ...(bulkStatus ? { status: bulkStatus } : {}),
      ...(bulkPriority ? { priority: bulkPriority } : {}),
    };
    setBulkSaving(true);
    setError(null);
    setData((current) => current ? {
      ...current,
      items: current.items.map((item) => selectedTaskIds.includes(item.id) ? {
        ...item,
        ...(bulkStatus ? { status: bulkStatus as TaskStatus } : {}),
        ...(bulkPriority ? { priority: bulkPriority as PMSTaskListItem["priority"] } : {}),
      } : item),
    } : current);
    try {
      await tasksAPI.bulkUpdate(payload);
      setSelectedTaskIds([]);
      setBulkStatus("");
      setBulkPriority("");
    } catch (err: any) {
      setData((current) => current ? { ...current, items: previousItems } : current);
      setError(err?.response?.data?.detail || "Unable to update selected tasks.");
    } finally {
      setBulkSaving(false);
    }
  };

  const renderCell = (task: PMSTaskListItem, column: ColumnKey) => {
    switch (column) {
      case "task":
        return <span className="font-semibold text-primary">{task.task_key || task.id}</span>;
      case "title":
        return <div className="flex min-w-56 items-center gap-2"><span className="line-clamp-2 font-medium">{task.title}</span><Button type="button" size="sm" variant="ghost" title="Add subtask" aria-label={`Add subtask to ${task.title}`} onClick={event => { event.stopPropagation(); setInlineParent(task.id); setInlineNotice(""); }}>+</Button></div>;
      case "project":
        return <span>{task.project_name || task.project_key || "-"}</span>;
      case "epic":
        return <span>{task.epic_name || task.epic_key || "-"}</span>;
      case "sprint":
        return <span>{task.sprint_name || "-"}</span>;
      case "status":
        return (
          <select
            value={task.status}
            disabled={updatingTaskId === task.id}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
            onChange={(event) => updateStatus(task, event.target.value as TaskStatus)}
            className="h-9 min-w-32 rounded-md border bg-background px-2 text-sm"
          >
            {taskStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        );
      case "priority":
        return <Badge className={statusColor(task.priority)}>{task.priority}</Badge>;
      case "assignee":
        return <span>{task.assignee_name || "Unassigned"}</span>;
      case "reporter":
        return <span>{task.reporter_name || "-"}</span>;
      case "story_points":
        return <span>{task.story_points ?? "-"}</span>;
      case "subtasks":
        return task.subtask_count ? <span>{task.completed_subtask_count || 0}/{task.subtask_count}</span> : <span className="text-muted-foreground">-</span>;
      case "tags":
        return <TaskBadges task={task} />;
      case "due_date":
        return <span className={cn(task.due_date && task.status !== "Done" && task.status !== "Cancelled" && task.due_date.slice(0, 10) < new Date().toLocaleDateString("en-CA") ? "font-medium text-red-600" : "")}>{formatDate(task.due_date || null)}</span>;
      case "created_at":
        return <span>{formatDate(task.created_at || null)}</span>;
      case "updated_at":
        return <span>{formatDate(task.updated_at || null)}</span>;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      <TaskViewPicker projectId={Number(filters.projectId) || undefined} />
      {inlineNotice && <p role="status" className="rounded-md border p-3 text-sm">{inlineNotice}</p>}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Tasks</h1>
          <p className="page-description">Search, filter, sort, and update work across every project you can access.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/pms/trash" className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm"><Trash2 className="h-4 w-4" />Trash</Link>
          <select value={selectedViewId} onChange={(event) => handleViewSelect(event.target.value)} className="h-10 min-w-52 rounded-md border bg-background px-3 text-sm">
            <option value="">Unsaved task view</option>
            {savedViews.map((view) => (
              <option key={view.id} value={view.id}>{view.is_default ? "* " : ""}{view.name}</option>
            ))}
          </select>
          <Button variant="outline" onClick={() => {
            const current = savedViews.find((view) => view.id === Number(selectedViewId));
            setViewName(current?.name || "");
            setViewVisibility((current?.visibility as "private" | "team" | "workspace") || "private");
            setViewDefault(Boolean(current?.is_default));
            setSavePanelOpen((open) => !open);
          }}>
            <SlidersHorizontal className="h-4 w-4" />Saved views
          </Button>
          <Button variant="outline" onClick={() => setFilters((current) => ({ ...current }))}>
            <RefreshCw className="h-4 w-4" />Refresh
          </Button>
        </div>
      </div>

      {savePanelOpen ? (
        <Card>
          <CardContent className="grid gap-3 p-4 lg:grid-cols-[1fr_180px_auto_auto_auto] lg:items-end">
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">View name</span>
              <Input value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="My open high priority tasks" />
            </label>
            <SelectField label="Visibility" value={viewVisibility} onChange={(value) => setViewVisibility(value as "private" | "team" | "workspace")}>
              <option value="private">Private</option>
              <option value="team">Team</option>
              <option value="workspace">Workspace</option>
            </SelectField>
            <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm">
              <input type="checkbox" checked={viewDefault} onChange={(event) => setViewDefault(event.target.checked)} />
              <Star className="h-4 w-4" />Default
            </label>
            <div className="flex gap-2">
              <Button onClick={saveCurrentView} disabled={viewSaving}>
                <Save className="h-4 w-4" />{viewSaving ? "Saving..." : "Save new"}
              </Button>
              <Button variant="outline" onClick={updateSelectedView} disabled={viewSaving || !selectedViewId}>
                Update
              </Button>
            </div>
            <Button variant="ghost" onClick={deleteSelectedView} disabled={viewSaving || !selectedViewId}>
              <Trash2 className="h-4 w-4" />Delete
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle className="flex items-center gap-2 text-base"><Search className="h-5 w-5" />Task filters</CardTitle>
          <div className="flex gap-2"><Button variant="ghost" size="sm" onClick={clearFilters}>Clear</Button><Button variant="outline" size="sm" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(open => !open)}>{filtersOpen ? "Hide filters" : `Filters${activeFilterCount ? ` (${activeFilterCount})` : ""}`}<ChevronDown className={cn("h-4 w-4 transition-transform", filtersOpen && "rotate-180")} /></Button></div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3 rounded-md border bg-background px-3 py-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input value={filters.search} onChange={(event) => setFilter("search", event.target.value)} placeholder="Search by task key, title, project, epic, component, or release" className="border-0 shadow-none focus-visible:ring-0" />
          </div>
          <div hidden={!filtersOpen} className={cn("gap-3 md:grid-cols-2 xl:grid-cols-4", filtersOpen && "grid")}>
            <SelectField label="Project" value={filters.projectId} onChange={(value) => setFilter("projectId", value)}>
              <option value="">All projects</option>
              {data?.filters.projects.map((project) => <option key={project.id} value={project.id}>{project.project_key ? `${project.project_key} - ${project.name}` : project.name}</option>)}
            </SelectField>
            <SelectField label="Sprint" value={filters.sprintId} onChange={(value) => setFilter("sprintId", value)}>
              <option value="">All sprints</option>
              {data?.filters.sprints.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}
            </SelectField>
            <SelectField label="Epic" value={filters.epicId} onChange={(value) => setFilter("epicId", value)}>
              <option value="">All epics</option>
              {data?.filters.epics.map((epic) => <option key={epic.id} value={epic.id}>{epic.epic_key ? `${epic.epic_key} - ${epic.name}` : epic.name}</option>)}
            </SelectField>
            <SelectField label="Status" value={filters.status} onChange={(value) => setFilter("status", value)}>
              <option value="">All statuses</option>
              {(data?.filters.statuses.length ? data.filters.statuses : taskStatuses).map((status) => <option key={status} value={status}>{status}</option>)}
            </SelectField>
            <SelectField label="Priority" value={filters.priority} onChange={(value) => setFilter("priority", value)}>
              <option value="">All priorities</option>
              {(data?.filters.priorities.length ? [...data.filters.priorities].sort((a, b) => (priorityOrder[b] || 0) - (priorityOrder[a] || 0)) : ["Urgent", "High", "Medium", "Low"]).map((priority) => <option key={priority} value={priority}>{priority}</option>)}
            </SelectField>
            <SelectField label="Assignee" value={filters.assigneeId} onChange={(value) => setFilter("assigneeId", value)}>
              <option value="">All assignees</option>
              {data?.filters.assignees.map((assignee) => <option key={assignee.id} value={assignee.id}>{assignee.name}</option>)}
            </SelectField>
            <SelectField label="Reporter" value={filters.reporterId} onChange={(value) => setFilter("reporterId", value)}>
              <option value="">All reporters</option>
              {data?.filters.reporters.map((reporter) => <option key={reporter.id} value={reporter.id}>{reporter.name}</option>)}
            </SelectField>
            <SelectField label="Tag" value={filters.tag} onChange={(value) => setFilter("tag", value)}>
              <option value="">All tags</option>
              {data?.filters.tags.map((tag) => <option key={tag} value={tag}>{tag}</option>)}
            </SelectField>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Due from</span>
              <Input type="date" value={filters.dueFrom} onChange={(event) => setFilter("dueFrom", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Due to</span>
              <Input type="date" value={filters.dueTo} onChange={(event) => setFilter("dueTo", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Created from</span>
              <Input type="date" value={filters.createdFrom} onChange={(event) => setFilter("createdFrom", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Created to</span>
              <Input type="date" value={filters.createdTo} onChange={(event) => setFilter("createdTo", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Updated from</span>
              <Input type="date" value={filters.updatedFrom} onChange={(event) => setFilter("updatedFrom", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Updated to</span>
              <Input type="date" value={filters.updatedTo} onChange={(event) => setFilter("updatedTo", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Story points min</span>
              <Input type="number" min="0" value={filters.storyPointsMin} onChange={(event) => setFilter("storyPointsMin", event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-muted-foreground">Story points max</span>
              <Input type="number" min="0" value={filters.storyPointsMax} onChange={(event) => setFilter("storyPointsMax", event.target.value)} />
            </label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2"><Button variant={groupByStatus ? "secondary" : "outline"} size="sm" aria-pressed={groupByStatus} onClick={() => setGroupByStatus(value => !value)}>Group: {groupByStatus ? "Status" : "None"}</Button>{groupByStatus && <Button variant="ghost" size="sm" onClick={() => setCollapsedGroups(collapsedGroups.length ? [] : taskGroups.map(group => group.status))}>{collapsedGroups.length ? "Expand all" : "Collapse all"}</Button>}<Button variant="outline" size="sm" aria-expanded={columnsOpen} onClick={() => setColumnsOpen(open => !open)}><Columns3 className="h-4 w-4" />Columns</Button></div>
          <p className="text-sm text-muted-foreground">{firstResult}-{lastResult} of {data?.total || 0}</p>
        </CardHeader>
        <CardContent hidden={!columnsOpen}>
          <section aria-label="Task field chooser" className="space-y-3">
            <div className="flex flex-wrap items-center gap-2"><Input aria-label="Search task fields" placeholder="Search task fields" value={columnSearch} onChange={event => setColumnSearch(event.target.value)} /><Button variant="outline" size="sm" onClick={() => setVisibleColumns(initialVisibleColumns)}>Reset columns</Button><Button variant="outline" size="sm" onClick={() => setVisibleColumns(Object.fromEntries(columns.map(column => [column.key, true])) as Record<ColumnKey, boolean>)}>Show all fields</Button><Link className="text-sm text-primary underline" to="/pms/custom-fields">Create custom field</Link></div>
            {[true, false].map(shown => <div key={String(shown)}><h3 className="mb-2 text-sm font-medium">{shown ? "Shown" : "Available properties"} ({columns.filter(column => Boolean(column.key === "title" || visibleColumns[column.key]) === shown).length})</h3><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{columns.filter(column => Boolean(column.key === "title" || visibleColumns[column.key]) === shown && column.label.toLowerCase().includes(columnSearch.toLowerCase())).map(column => <label key={column.key} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm"><span>{column.label}{column.key === "title" && " (required)"}</span><input aria-label={`Show ${column.label} column`} type="checkbox" disabled={column.key === "title"} checked={column.key === "title" || visibleColumns[column.key]} onChange={event => setVisibleColumns(current => ({ ...current, [column.key]: event.target.checked }))} /></label>)}</div></div>)}
            {!columns.some(column => column.label.toLowerCase().includes(columnSearch.toLowerCase())) && <p className="text-sm text-muted-foreground">No matching field.</p>}
            <p className="text-xs text-muted-foreground">Selections persist in this browser. Save a view to reuse them with its filters across devices. Custom fields are managed separately.</p>
          </section>
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      {selectedTaskIds.length ? (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="text-sm font-medium">{selectedTaskIds.length} task{selectedTaskIds.length === 1 ? "" : "s"} selected</div>
            <div className="grid gap-2 sm:grid-cols-[180px_180px_auto_auto]">
              <select value={bulkStatus} onChange={(event) => setBulkStatus(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option value="">Keep status</option>
                {taskStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
              <select value={bulkPriority} onChange={(event) => setBulkPriority(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option value="">Keep priority</option>
                {["Urgent", "High", "Medium", "Low"].map((priority) => <option key={priority} value={priority}>{priority}</option>)}
              </select>
              <Button onClick={applyBulkUpdate} disabled={bulkSaving || (!bulkStatus && !bulkPriority)}>
                {bulkSaving ? "Saving..." : "Apply"}
              </Button>
              <Button variant="ghost" onClick={() => setSelectedTaskIds([])} disabled={bulkSaving}>Clear</Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-0">
          {loading ? <div className="m-4 h-48 rounded-lg skeleton" /> : null}
          {!loading && !data?.items.length ? (
            <div className="p-10 text-center">
              <h2 className="text-lg font-semibold">No tasks found</h2>
              <p className="mt-1 text-sm text-muted-foreground">Adjust filters or create tasks from a project board.</p>
            </div>
          ) : null}

          {!loading && data?.items.length ? (
            <>
              <div className={cn("overflow-x-auto", layout === "gallery" ? "hidden" : "hidden lg:block")}>
                <table className="min-w-[1180px] w-full text-sm">
                  <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="w-12 px-4 py-3">
                        <input
                          type="checkbox"
                          checked={allPageTasksSelected}
                          onChange={(event) => togglePageSelection(event.target.checked)}
                          aria-label="Select all tasks on this page"
                        />
                      </th>
                      {visibleColumnList.map((column) => (
                        <th key={column.key} className="whitespace-nowrap px-4 py-3">
                          <SortButton column={column.key} label={column.label} sortBy={sortBy} sortOrder={sortOrder} onSort={handleSort} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {taskGroups.map(group => <Fragment key={group.status}>
                    {groupByStatus && <tr className="border-b bg-muted/25"><td colSpan={visibleColumnList.length + 1} className="px-4 py-2"><button type="button" className="flex w-full items-center gap-2 py-1 text-left font-semibold" aria-expanded={!collapsedGroups.includes(group.status)} onClick={() => toggleGroup(group.status)}><ChevronDown className={cn("h-4 w-4 transition-transform", collapsedGroups.includes(group.status) && "-rotate-90")} /><Badge className={statusColor(group.status)}>{group.status}</Badge><span className="text-xs font-normal text-muted-foreground">{group.items.length} on this page</span></button></td></tr>}
                    {(!groupByStatus || !collapsedGroups.includes(group.status)) && group.items.map((task) => (
                      <Fragment key={task.id}><tr
                        tabIndex={0}
                        onClick={() => openTask(task)}
                        onKeyDown={(event) => {
                          if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); openTask(task); }
                        }}
                        className={cn("cursor-pointer border-b transition hover:bg-muted/40 focus:bg-muted/40 focus:outline-none", selectedTaskIds.includes(task.id) ? "bg-primary/5" : "")}
                      >
                        <td className="px-4 py-3 align-middle">
                          <input
                            type="checkbox"
                            checked={selectedTaskIds.includes(task.id)}
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) => toggleTaskSelection(task.id, event.target.checked)}
                            aria-label={`Select ${task.task_key || task.title}`}
                          />
                        </td>
                        {visibleColumnList.map((column) => (
                          <td key={column.key} className="max-w-72 px-4 py-3 align-middle">
                            {renderCell(task, column.key)}
                          </td>
                        ))}
                      </tr>
                      {createdChildren[task.id]?.map(child => <tr key={`child-${child.id}`} className="border-b bg-muted/20"><td /><td colSpan={visibleColumnList.length} className="px-6 py-2"><Link className="text-sm text-primary underline" to={`/pms/tasks/${child.id}`}>↳ {child.task_key} · {child.title}</Link><Badge className="ml-2">{child.status}</Badge></td></tr>)}
                      {inlineParent === task.id && <tr><td /><td colSpan={visibleColumnList.length} className="p-3"><InlineSubtaskComposer key={task.id} parent={task} onCreated={child => subtaskCreated(task, child)} onCancel={() => setInlineParent(null)} /></td></tr>}
                      </Fragment>
                    ))}</Fragment>)}
                  </tbody>
                </table>
              </div>

              <div className={layout === "gallery" ? "grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3 p-4 lg:hidden"}>
                {taskGroups.map(group => <Fragment key={group.status}>
                  {groupByStatus && <button type="button" className="col-span-full flex w-full items-center gap-2 py-2 text-left font-semibold" aria-expanded={!collapsedGroups.includes(group.status)} onClick={() => toggleGroup(group.status)}><ChevronDown className={cn("h-4 w-4", collapsedGroups.includes(group.status) && "-rotate-90")} /><Badge className={statusColor(group.status)}>{group.status}</Badge><span className="text-xs text-muted-foreground">{group.items.length} on this page</span></button>}
                  {(!groupByStatus || !collapsedGroups.includes(group.status)) && group.items.map((task) => (
                  <div role="button" tabIndex={0} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); openTask(task); } }} key={task.id} onClick={() => openTask(task)} className="w-full rounded-lg border bg-background p-4 text-left shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 gap-3">
                        <input
                          type="checkbox"
                          checked={selectedTaskIds.includes(task.id)}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => toggleTaskSelection(task.id, event.target.checked)}
                          aria-label={`Select ${task.task_key || task.title}`}
                        />
                        <div className="min-w-0">
                        <p className="text-xs font-semibold text-primary">{task.task_key || task.id}</p>
                        <h2 className="mt-1 line-clamp-2 font-semibold">{task.title}</h2>
                        </div>
                      </div>
                      <Badge className={statusColor(task.priority)}>{task.priority}</Badge>
                    </div>
                    <div className="mt-3 space-y-2 text-sm">{visibleColumnList.filter(column => !["task", "title", "tags"].includes(column.key)).map(column => <div key={column.key} className="flex flex-wrap items-center justify-between gap-2"><span className="text-muted-foreground">{column.label}</span><span>{renderCell(task, column.key)}</span></div>)}</div>
                    <div className="mt-3"><TaskBadges task={task} /></div>
                    <Button className="mt-3" type="button" variant="outline" size="sm" aria-label={`Add subtask to ${task.title}`} onClick={event => { event.stopPropagation(); setInlineParent(task.id); setInlineNotice(""); }}>+ Add subtask</Button>
                    <div className="mt-3 space-y-2" onClick={event => event.stopPropagation()}>{createdChildren[task.id]?.map(child => <Link key={child.id} className="block text-sm text-primary underline" to={`/pms/tasks/${child.id}`}>↳ {child.task_key} · {child.title}</Link>)}{inlineParent === task.id && <InlineSubtaskComposer key={task.id} parent={task} onCreated={child => subtaskCreated(task, child)} onCancel={() => setInlineParent(null)} />}</div>
                  </div>
                ))}</Fragment>)}
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Rows</span>
          <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} className="h-9 rounded-md border bg-background px-2">
            {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </div>
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
            <ChevronLeft className="h-4 w-4" />Previous
          </Button>
          <span className="min-w-28 text-center text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>
            Next<ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
