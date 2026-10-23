import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Link2, RefreshCw, Trash2, ZoomIn } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { beginProgress } from "@/lib/async-progress";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatDate, statusColor } from "@/lib/utils";
import { usePMSRealtime } from "../realtime";
import { ganttAPI } from "../services/api";
import type { PMSGanttResponse, PMSTaskDependency, PMSTaskListItem } from "../types";

type ZoomLevel = "day" | "week" | "month";
type DragMode = "move" | "start" | "end";

type FilterState = {
  projectId: string;
  sprintId: string;
  assigneeId: string;
  epicId: string;
  status: string;
};

type DragState = {
  taskId: number;
  mode: DragMode;
  startX: number;
  originalStart: Date;
  originalEnd: Date;
};

const rowHeight = 52;
const desktopLabelWidth = 288;
const zoomConfig: Record<ZoomLevel, { columnWidth: number; daysPerColumn: number }> = {
  day: { columnWidth: 44, daysPerColumn: 1 },
  week: { columnWidth: 104, daysPerColumn: 7 },
  month: { columnWidth: 132, daysPerColumn: 30 },
};
const dependencyTypes = ["Finish To Start", "Start To Start", "Finish To Finish", "Start To Finish"];
const defaultFilters: FilterState = { projectId: "", sprintId: "", assigneeId: "", epicId: "", status: "" };

export default function GanttPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const user = useAuthStore(state => state.user);
  const [data, setData] = useState<PMSGanttResponse | null>(null);
  const [tasks, setTasks] = useState<PMSTaskListItem[]>([]);
  const [dependencies, setDependencies] = useState<PMSTaskDependency[]>([]);
  const [filters, setFilters] = useState<FilterState>({ ...defaultFilters, projectId: projectId || "" });
  const [zoom, setZoom] = useState<ZoomLevel>("week");
  const [drag, setDrag] = useState<DragState | null>(null);
  const [sourceTaskId, setSourceTaskId] = useState("");
  const [targetTaskId, setTargetTaskId] = useState("");
  const [dependencyType, setDependencyType] = useState("Finish To Start");
  const [lagDays, setLagDays] = useState("0");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [editor, setEditor] = useState<PMSTaskListItem | null>(null);
  const [dates, setDates] = useState({ start: "", due: "" });
  const [compact, setCompact] = useState(window.innerWidth < 640);
  const requestSequence = useRef(0);
  const inFlight = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const labelWidth = compact ? 176 : desktopLabelWidth;
  useEffect(() => { const resize = () => setCompact(window.innerWidth < 640); window.addEventListener("resize", resize); return () => window.removeEventListener("resize", resize); }, []);
  const openEditor = (task: PMSTaskListItem) => { setError(null); setDates({ start: task.start_date || "", due: task.due_date || "" }); setEditor(task); };
  const saveSchedule = async () => {
    if (!editor || saving || !canEditProject(editor.project_id)) return;
    if (dates.start && dates.due && dates.start > dates.due) { setError("Due date must be on or after start date."); return; }
    setSaving(true); setError(null); const finish = beginProgress("Saving task schedule");
    try { const result = await ganttAPI.updateSchedule(editor.id, { start_date: dates.start || null, due_date: dates.due || null }); setTasks(items => items.map(task => task.id === editor.id ? { ...task, ...result.task } : task)); setNotice("Schedule saved"); setEditor(null); await load(true); finish(); }
    catch (err: any) { finish(false); setError(err?.response?.data?.detail || "Unable to save this schedule."); }
    finally { setSaving(false); }
  };

  const canEditProject = (id?: number) => !!data?.filters.projects.find(p => p.id === id)?.can_manage_tasks;
  const readOnly = filters.projectId ? !canEditProject(Number(filters.projectId)) : !data?.filters.projects.some(p => p.can_manage_tasks);
  const load = async (background = false) => {
    if (background && inFlight.current) return;
    inFlight.current = true;
    const sequence = ++requestSequence.current;
    if (!background) setLoading(true);
    setError(null);
    try {
      const response = await ganttAPI.get({ ...filters, includeUnscheduled: true });
      if (sequence !== requestSequence.current) return;
      setData(response);
      setTasks(response.tasks);
      setDependencies(response.dependencies);
    } catch (err: any) {
      if (sequence === requestSequence.current) setError(err?.response?.data?.detail || "Unable to load Gantt timeline.");
    } finally {
      if (sequence === requestSequence.current) { inFlight.current = false; setLoading(false); }
    }
  };

  useEffect(() => {
    setFilters((current) => ({ ...current, projectId: projectId || current.projectId }));
  }, [projectId]);

  useEffect(() => {
    void load();
    return () => { requestSequence.current++; };
  }, [filters.projectId, filters.sprintId, filters.assigneeId, filters.epicId, filters.status]);

  useEffect(() => {
    if (!drag) return undefined;
    const onMove = (event: MouseEvent) => {
      const dayDelta = Math.round((event.clientX - drag.startX) / pixelsPerDay(zoom));
      setTasks((items) => items.map((task) => {
        if (task.id !== drag.taskId) return task;
        const next = calculateDraggedDates(drag, dayDelta);
        return { ...task, start_date: toIsoDate(next.start), due_date: toIsoDate(next.end) };
      }));
    };
    const onUp = async (event: MouseEvent) => {
      const current = drag;
      setDrag(null);
      const dayDelta = Math.round((event.clientX - current.startX) / pixelsPerDay(zoom));
      if (!dayDelta) return;
      const next = calculateDraggedDates(current, dayDelta);
      const finish = beginProgress("Moving task schedule"); setSaving(true);
      try {
        const result = await ganttAPI.updateSchedule(current.taskId, { start_date: toIsoDate(next.start), due_date: toIsoDate(next.end) });
        setTasks((items) => items.map((task) => task.id === current.taskId ? { ...task, ...result.task } : task));
        if (data) setData({ ...data, warnings: result.warnings });
        finish(); setNotice("Schedule saved");
      } catch (err: any) {
        finish(false); await load(); setError(err?.response?.data?.detail || "Unable to update schedule.");
      }
      finally { setSaving(false); }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [drag, zoom, data]);

  const timeline = useMemo(() => buildTimeline(tasks, zoom), [tasks, zoom]);
  const rows = useMemo(() => tasks.map((task, index) => ({ task, index, schedule: taskSchedule(task) })), [tasks]);
  const taskById = useMemo(() => new Map(tasks.map((task) => [task.id, task])), [tasks]);
  const warningByTask = useMemo(() => {
    const map = new Map<number, string[]>();
    (data?.warnings || []).forEach((warning) => {
      map.set(warning.source_task_id, [...(map.get(warning.source_task_id) || []), warning.message]);
      map.set(warning.target_task_id, [...(map.get(warning.target_task_id) || []), warning.message]);
    });
    return map;
  }, [data?.warnings]);
  const scheduleFocus = useMemo(() => buildScheduleFocus(tasks, dependencies, warningByTask), [tasks, dependencies, warningByTask]);

  usePMSRealtime({ enabled: !loading && !drag && !editor && !saving, projectId: Number(filters.projectId) || undefined, onEvent: () => { void load(true); }, onFallbackPoll: () => { void load(true); }, showToast: false });

  const createDependency = async () => {
    if (saving) return;
    if (!Number.isInteger(Number(lagDays || 0))) { setError("Lag must be a whole number of days."); return; }
    if (!sourceTaskId || !targetTaskId || sourceTaskId === targetTaskId) return;
    setError(null); setSaving(true); const finish = beginProgress("Saving dependency");
    try {
      const created = await ganttAPI.createDependency({
        source_task_id: Number(sourceTaskId),
        target_task_id: Number(targetTaskId),
        dependency_type: dependencyType,
        lag_days: Number(lagDays || 0),
      });
      setDependencies((items) => [...items, created]);
      setSourceTaskId("");
      setTargetTaskId("");
      await load(); finish(); setNotice("Dependency saved");
    } catch (err: any) { finish(false);
      setError(err?.response?.data?.detail || "Unable to create dependency.");
    } finally { setSaving(false); }
  };

  const deleteDependency = async (dependencyId: number) => {
    if (saving) return;
    setSaving(true); const finish = beginProgress("Removing dependency");
    setDependencies((items) => items.filter((item) => item.id !== dependencyId));
    try {
      await ganttAPI.deleteDependency(dependencyId);
      await load(); finish(); setNotice("Dependency removed");
    } catch (err: any) { finish(false);
      await load(); setError(err?.response?.data?.detail || "Unable to delete dependency.");
    } finally { setSaving(false); }
  };

  const selectedProjectId = filters.projectId || data?.filters.projects[0]?.id;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="page-title">Gantt</h1>
          <p className="page-description">Timeline planning with dependency arrows, schedule edits, filters, and zoomable dates.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {selectedProjectId && canAccessRoute(`/pms/projects/${selectedProjectId}/board`, user?.role, user?.is_superuser) ? <Button asChild variant="outline"><Link to={`/pms/projects/${selectedProjectId}/board`}>Open board</Link></Button> : null}
          <Button variant="outline" disabled={loading || saving} onClick={() => { setZoom(daysBetween(timeline.start, timeline.end) <= 21 ? "day" : daysBetween(timeline.start, timeline.end) <= 180 ? "week" : "month"); scrollRef.current?.scrollTo({ left: 0 }); }}>Fit dates</Button>
          <Button variant="outline" disabled={loading || daysBetween(timeline.start, new Date()) < 0 || new Date() > timeline.end} onClick={() => scrollRef.current?.scrollTo({ left: Math.max(0, daysBetween(timeline.start, new Date()) * pixelsPerDay(zoom) - 80) })}>Today</Button>
          <Button variant="outline" disabled={loading || saving} onClick={() => { void load(); }}><RefreshCw className="h-4 w-4" />Refresh</Button>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <SelectFilter label="Project" value={filters.projectId} onChange={(value) => setFilters((current) => ({ ...current, projectId: value, sprintId: "", epicId: "" }))}>
              <option value="">All projects</option>
              {data?.filters.projects.map((item) => <option key={item.id} value={item.id}>{item.project_key || item.name}</option>)}
            </SelectFilter>
            <SelectFilter label="Sprint" value={filters.sprintId} onChange={(value) => setFilters((current) => ({ ...current, sprintId: value }))}>
              <option value="">All sprints</option>
              {data?.filters.sprints.filter((item) => !filters.projectId || String(item.project_id) === filters.projectId).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </SelectFilter>
            <SelectFilter label="Epic" value={filters.epicId} onChange={(value) => setFilters((current) => ({ ...current, epicId: value }))}>
              <option value="">All epics</option>
              {data?.filters.epics.filter((item) => !filters.projectId || String(item.project_id) === filters.projectId).map((item) => <option key={item.id} value={item.id}>{item.epic_key || item.name}</option>)}
            </SelectFilter>
            <SelectFilter label="Assignee" value={filters.assigneeId} onChange={(value) => setFilters((current) => ({ ...current, assigneeId: value }))}>
              <option value="">All assignees</option>
              {data?.filters.assignees.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </SelectFilter>
            <SelectFilter label="Status" value={filters.status} onChange={(value) => setFilters((current) => ({ ...current, status: value }))}>
              <option value="">All statuses</option>
              {data?.filters.statuses.map((item) => <option key={item}>{item}</option>)}
            </SelectFilter>
            <SelectFilter label="Zoom" value={zoom} onChange={(value) => setZoom(value as ZoomLevel)}>
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
            </SelectFilter>
          </div>
        </CardContent>
      </Card>

      {notice && <p role="status" className="text-sm text-primary">{notice}</p>}
      <p className="text-sm text-muted-foreground">{tasks.filter(task => task.start_date || task.due_date).length} scheduled · {tasks.filter(task => !task.start_date && !task.due_date).length} unscheduled. Select a task name to edit dates using keyboard or touch.</p>
      {error ? <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <Card>
        <CardContent ref={scrollRef} className="max-w-full overflow-auto p-0" aria-label="Scrollable task timeline">
          {loading ? <div className="skeleton m-5 h-96 rounded-lg" /> : null}
          {!loading && !rows.length ? <div className="m-5 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">Add task start or due dates to populate the Gantt timeline.</div> : null}
          {!loading && rows.length ? (
            <div className="min-w-full" style={{ width: labelWidth + timeline.width }}>
              <div className="sticky top-0 z-20 grid bg-background" style={{ gridTemplateColumns: `${labelWidth}px ${timeline.width}px` }}>
                <div className="sticky left-0 z-30 border-b border-r bg-background p-3 text-xs font-semibold uppercase text-muted-foreground">Task</div>
                <div className="relative border-b" style={{ height: 44 }}>
                  {timeline.columns.map((column) => (
                    <div key={column.key} className="absolute top-0 flex h-11 items-center border-r px-2 text-xs font-medium text-muted-foreground" style={{ left: column.x, width: column.width }}>
                      {column.label}
                    </div>
                  ))}
                </div>
              </div>
              <div className="relative grid" style={{ gridTemplateColumns: `${labelWidth}px ${timeline.width}px`, minHeight: rows.length * rowHeight }}>
                <div className="sticky left-0 z-20 bg-background">
                  {rows.map(({ task }) => (
                    <button key={task.id} type="button" aria-label={`Edit schedule for ${task.title}`} onClick={() => openEditor(task)} className="flex h-[52px] w-full items-center gap-2 border-b border-r px-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-semibold">{task.task_key}</span>
                          {task.is_blocking ? <Badge variant="outline" className="border-red-200 text-red-700">Blocks other tasks</Badge> : null}
                        </div>
                        <p className="truncate text-xs text-muted-foreground">{task.title}</p>{!task.start_date && !task.due_date && <span className="text-xs text-amber-700">Unscheduled</span>}
                      </div>
                    </button>
                  ))}
                </div>
                <div className="relative overflow-hidden">
                  {daysBetween(timeline.start, new Date()) >= 0 && new Date() <= timeline.end && <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 z-10 border-l-2 border-violet-500" style={{ left: daysBetween(timeline.start, new Date()) * pixelsPerDay(zoom) }} />}
                  <TimelineGrid rows={rows.length} timeline={timeline} />
                  <DependencyArrows dependencies={dependencies} rows={rows} timelineStart={timeline.start} zoom={zoom} />
                  {rows.filter(({ task }) => task.start_date || task.due_date).map(({ task, index, schedule }) => (
                    <TaskBar
                      key={task.id}
                      readOnly={!canEditProject(task.project_id)}
                      onEdit={() => openEditor(task)}
                      task={task}
                      index={index}
                      schedule={schedule}
                      timelineStart={timeline.start}
                      zoom={zoom}
                      warnings={warningByTask.get(task.id) || []}
                      onDragStart={(mode, event) => {
                        if (!canEditProject(task.project_id)) return;
                        event.preventDefault();
                        setDrag({ taskId: task.id, mode, startX: event.clientX, originalStart: schedule.start, originalEnd: schedule.end });
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Dialog.Root open={!!editor} onOpenChange={open => { if (!open && !saving) setEditor(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><Dialog.Content onEscapeKeyDown={event => { if (saving) event.preventDefault(); }} onInteractOutside={event => event.preventDefault()} className="fixed left-1/2 top-1/2 z-50 max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border bg-background p-5 shadow-xl"><Dialog.Title className="text-lg font-semibold">Schedule · {editor?.title}</Dialog.Title><Dialog.Description>Choose dates or leave both blank to unschedule. Dependency warnings are checked after saving.</Dialog.Description>{error && <p role="alert" className="my-3 text-destructive">{error}</p>}<form className="mt-4 space-y-4" onSubmit={event => { event.preventDefault(); void saveSchedule(); }}><fieldset disabled={saving || !canEditProject(editor?.project_id)} className="grid gap-4 sm:grid-cols-2"><label>Start date<input aria-label="Schedule start date" className="mt-1 h-11 w-full rounded border bg-background px-3" type="date" value={dates.start} onChange={event => setDates({ ...dates, start: event.target.value })} /></label><label>Due date<input aria-label="Schedule due date" className="mt-1 h-11 w-full rounded border bg-background px-3" type="date" value={dates.due} onChange={event => setDates({ ...dates, due: event.target.value })} /></label></fieldset>{!canEditProject(editor?.project_id) && <p>You have read-only access.</p>}<div className="flex flex-wrap justify-end gap-3">{canEditProject(editor?.project_id) && <Button type="button" variant="outline" disabled={saving} onClick={() => setDates({ start: "", due: "" })}>Clear dates</Button>}<Button type="button" variant="outline" disabled={saving} onClick={() => setEditor(null)}>Close</Button>{canEditProject(editor?.project_id) && <Button disabled={saving}>{saving ? "Saving…" : "Save schedule"}</Button>}</div></form></Dialog.Content></Dialog.Portal></Dialog.Root>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="h-5 w-5" />Dependencies</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <form onSubmit={event => { event.preventDefault(); void createDependency(); }}><fieldset disabled={readOnly || saving} className="grid gap-2 md:grid-cols-[1fr_1fr_11rem_6rem_auto]">
              <select aria-label="Source task" value={sourceTaskId} onChange={(event) => { setSourceTaskId(event.target.value); setTargetTaskId(""); }} className="h-11 rounded-md border bg-background px-3 text-sm">
                <option value="">Source task</option>
                {tasks.filter(task => canEditProject(task.project_id)).map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
              </select>
              <select aria-label="Target task" value={targetTaskId} onChange={(event) => setTargetTaskId(event.target.value)} className="h-11 rounded-md border bg-background px-3 text-sm">
                <option value="">Target task</option>
                {tasks.filter(task => canEditProject(task.project_id) && task.id !== Number(sourceTaskId) && task.project_id === tasks.find(source => source.id === Number(sourceTaskId))?.project_id).map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
              </select>
              <select aria-label="Dependency type" value={dependencyType} onChange={(event) => setDependencyType(event.target.value)} className="h-11 rounded-md border bg-background px-3 text-sm">
                {dependencyTypes.map((item) => <option key={item}>{item}</option>)}
              </select>
              <input aria-label="Lag days" type="number" step="1" value={lagDays} onChange={(event) => setLagDays(event.target.value)} className="h-11 rounded-md border bg-background px-3 text-sm" placeholder="Lag" />
              <Button type="submit" disabled={saving || !sourceTaskId || !targetTaskId}>Add dependency</Button>
            </fieldset></form>{readOnly && <p className="text-sm text-muted-foreground">You have read-only access to this timeline.</p>}
            <div className="space-y-2">
              {dependencies.map((dependency) => <DependencyRow key={dependency.id} dependency={dependency} canEdit={!saving && canEditProject(tasks.find(t => t.id === (dependency.source_task_id ?? dependency.depends_on_task_id))?.project_id)} onDelete={() => deleteDependency(dependency.id)} />)}
              {!dependencies.length ? <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">No dependencies for the visible tasks.</p> : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5" />Schedule Checks</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {(data?.warnings || []).map((warning) => (
              <div key={`${warning.dependency_id}-${warning.message}`} className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {warning.message}
              </div>
            ))}
            <div className="rounded-md border p-3 text-sm">
              <div className="flex items-center gap-2 font-medium text-foreground"><ZoomIn className="h-4 w-4" />Schedule focus</div>
              <p className="mt-1 text-xs text-muted-foreground">Prioritized from blocked status, dependency pressure, warnings, and due dates.</p>
              <div className="mt-3 space-y-2">
                {scheduleFocus.map((item) => (
                  <button key={item.task.id} type="button" onClick={() => openEditor(item.task)} className="block w-full rounded-md border p-2 text-left hover:bg-muted/50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{item.task.task_key} - {item.task.title}</p>
                        <p className="text-xs text-muted-foreground">{item.reason}</p>
                      </div>
                      <Badge className={statusColor(item.task.status)}>{item.task.status}</Badge>
                    </div>
                  </button>
                ))}
                {!scheduleFocus.length ? <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">No blocked, warning, or dependency-heavy tasks in the current view.</p> : null}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function buildScheduleFocus(tasks: PMSTaskListItem[], dependencies: PMSTaskDependency[], warningByTask: Map<number, string[]>) {
  const dependencyCount = new Map<number, number>();
  dependencies.forEach((dependency) => {
    const sourceId = dependency.source_task_id ?? dependency.depends_on_task_id;
    const targetId = dependency.target_task_id ?? dependency.task_id;
    if (sourceId) dependencyCount.set(sourceId, (dependencyCount.get(sourceId) || 0) + 1);
    if (targetId) dependencyCount.set(targetId, (dependencyCount.get(targetId) || 0) + 1);
  });
  const today = startOfDay(new Date()).getTime();
  return tasks
    .map((task) => {
      const warnings = warningByTask.get(task.id) || [];
      const deps = dependencyCount.get(task.id) || 0;
      const due = task.due_date ? startOfDay(new Date(task.due_date)).getTime() : Number.POSITIVE_INFINITY;
      const daysToDue = Number.isFinite(due) ? Math.ceil((due - today) / 86400000) : 999;
      const blocked = task.status === "Blocked";
      const overdue = daysToDue < 0 && !["Done", "Cancelled"].includes(task.status);
      const score = (blocked ? 100 : 0) + (overdue ? 90 : 0) + warnings.length * 30 + deps * 8 + (daysToDue <= 7 ? 10 : 0);
      const reason = [
        blocked ? "Blocked" : null,
        overdue ? `${Math.abs(daysToDue)} day${Math.abs(daysToDue) === 1 ? "" : "s"} overdue` : null,
        warnings.length ? `${warnings.length} schedule warning${warnings.length === 1 ? "" : "s"}` : null,
        deps ? `${deps} linked dependenc${deps === 1 ? "y" : "ies"}` : null,
        !overdue && Number.isFinite(due) ? `Due ${formatDate(task.due_date || null)}` : null,
      ].filter(Boolean).join(" / ");
      return { task, score, reason: reason || "On schedule" };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
}

function SelectFilter({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-11 w-full rounded-md border bg-background px-3 text-sm">
        {children}
      </select>
    </label>
  );
}

function TaskBar({
  task,
  index,
  schedule,
  timelineStart,
  zoom,
  warnings,
  onDragStart,
  onEdit,
  readOnly,
}: {
  task: PMSTaskListItem;
  index: number;
  schedule: { start: Date; end: Date };
  timelineStart: Date;
  zoom: ZoomLevel;
  warnings: string[];
  onEdit: () => void;
  readOnly: boolean;
  onDragStart: (mode: DragMode, event: ReactMouseEvent) => void;
}) {
  const left = daysBetween(timelineStart, schedule.start) * pixelsPerDay(zoom);
  const width = Math.max((daysBetween(schedule.start, schedule.end) + 1) * pixelsPerDay(zoom), 22);
  const overdue = task.due_date && new Date(task.due_date) < startOfDay(new Date()) && task.status !== "Done";
  const risky = overdue || task.is_blocking || warnings.length > 0;
  return (
    <div
      className={cn("absolute z-10 h-8 rounded-md border shadow-sm", risky ? "border-red-400 bg-red-500" : "border-primary/80 bg-primary")}
      style={{ top: index * rowHeight + 10, left, width }}
      title={`${task.task_key}: ${formatDate(task.start_date || null)} - ${formatDate(task.due_date || null)}${warnings.length ? ` / ${warnings[0]}` : ""}`}
    >
      <button type="button" disabled={readOnly} aria-label={`Resize start date for ${task.task_key}`} onMouseDown={(event) => onDragStart("start", event)} className="absolute left-0 top-0 h-full w-2 cursor-ew-resize rounded-l-md bg-black/15" />
      <button type="button" onDoubleClick={onEdit} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onEdit(); } }} onMouseDown={(event) => onDragStart("move", event)} className="h-full w-full cursor-grab truncate px-3 text-left text-xs font-semibold text-white">
        {task.task_key} {task.title}
      </button>
      <button type="button" disabled={readOnly} aria-label={`Resize end date for ${task.task_key}`} onMouseDown={(event) => onDragStart("end", event)} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize rounded-r-md bg-black/15" />
    </div>
  );
}

function TimelineGrid({ rows, timeline }: { rows: number; timeline: Timeline }) {
  return (
    <div className="absolute inset-0">
      {timeline.columns.map((column) => <div key={column.key} className="absolute top-0 border-r" style={{ left: column.x, width: column.width, height: rows * rowHeight }} />)}
      {Array.from({ length: rows }).map((_, index) => <div key={index} className="absolute left-0 right-0 border-b" style={{ top: index * rowHeight + rowHeight - 1 }} />)}
    </div>
  );
}

function DependencyArrows({ dependencies, rows, timelineStart, zoom }: { dependencies: PMSTaskDependency[]; rows: Array<{ task: PMSTaskListItem; index: number; schedule: { start: Date; end: Date } }>; timelineStart: Date; zoom: ZoomLevel }) {
  const rowByTaskId = new Map(rows.map((row) => [row.task.id, row]));
  const paths = dependencies.map((dependency) => {
    const source = rowByTaskId.get(dependency.source_task_id || dependency.depends_on_task_id);
    const target = rowByTaskId.get(dependency.target_task_id || dependency.task_id);
    if (!source || !target || (!source.task.start_date && !source.task.due_date) || (!target.task.start_date && !target.task.due_date)) return null;
    const anchors = dependencyAnchors(dependency.dependency_type, source.schedule, target.schedule, timelineStart, zoom);
    const sourceY = source.index * rowHeight + 26;
    const targetY = target.index * rowHeight + 26;
    const midX = Math.max(anchors.sourceX, anchors.targetX) + 18;
    return `M ${anchors.sourceX} ${sourceY} L ${midX} ${sourceY} L ${midX} ${targetY} L ${anchors.targetX} ${targetY}`;
  }).filter(Boolean) as string[];
  return (
    <svg className="pointer-events-none absolute inset-0 z-0" width="100%" height={rows.length * rowHeight}>
      <defs>
        <marker id="gantt-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#64748b" />
        </marker>
      </defs>
      {paths.map((path, index) => <path key={index} d={path} fill="none" stroke="#64748b" strokeWidth="1.5" markerEnd="url(#gantt-arrow)" />)}
    </svg>
  );
}

function DependencyRow({ dependency, onDelete, canEdit }: { dependency: PMSTaskDependency; onDelete: () => void; canEdit: boolean }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3 text-sm md:flex-row md:items-center md:justify-between">
      <div>
        <p className="font-medium">{dependency.source_task_key || dependency.depends_on_task_key} &rarr; {dependency.target_task_key || dependency.task_key}</p>
        <p className="text-xs text-muted-foreground">{dependency.dependency_type} / Lag {dependency.lag_days || 0} days</p>
      </div>
      <Button disabled={!canEdit} type="button" size="sm" variant="ghost" onClick={onDelete} aria-label="Delete dependency"><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}

type Timeline = {
  start: Date;
  end: Date;
  width: number;
  columns: Array<{ key: string; label: string; x: number; width: number }>;
};

function buildTimeline(tasks: PMSTaskListItem[], zoom: ZoomLevel): Timeline {
  const schedules = tasks.filter(task => task.start_date || task.due_date).map(taskSchedule);
  const min = schedules.length ? new Date(Math.min(...schedules.map((item) => item.start.getTime()))) : new Date();
  const max = schedules.length ? new Date(Math.max(...schedules.map((item) => item.end.getTime()))) : addDays(new Date(), 28);
  const start = addDays(startOfDay(min), zoom === "month" ? -15 : zoom === "week" ? -7 : -2);
  const end = addDays(startOfDay(max), zoom === "month" ? 45 : zoom === "week" ? 14 : 5);
  const { columnWidth, daysPerColumn } = zoomConfig[zoom];
  const count = Math.max(Math.ceil((daysBetween(start, end) + 1) / daysPerColumn), 1);
  const columns = Array.from({ length: count }).map((_, index) => {
    const date = addDays(start, index * daysPerColumn);
    return {
      key: `${zoom}-${date.toISOString()}`,
      label: zoom === "month" ? date.toLocaleDateString([], { month: "short", year: "numeric" }) : zoom === "week" ? `Week of ${formatDate(toIsoDate(date))}` : date.toLocaleDateString([], { month: "short", day: "numeric" }),
      x: index * columnWidth,
      width: columnWidth,
    };
  });
  return { start, end, width: count * columnWidth, columns };
}

function taskSchedule(task: PMSTaskListItem) {
  const start = parseDate(task.start_date || task.due_date) || startOfDay(new Date());
  const end = parseDate(task.due_date || task.start_date) || start;
  return end < start ? { start: end, end: start } : { start, end };
}

function calculateDraggedDates(drag: DragState, dayDelta: number) {
  if (drag.mode === "move") {
    return { start: addDays(drag.originalStart, dayDelta), end: addDays(drag.originalEnd, dayDelta) };
  }
  if (drag.mode === "start") {
    const nextStart = addDays(drag.originalStart, dayDelta);
    return { start: nextStart <= drag.originalEnd ? nextStart : drag.originalEnd, end: drag.originalEnd };
  }
  const nextEnd = addDays(drag.originalEnd, dayDelta);
  return { start: drag.originalStart, end: nextEnd >= drag.originalStart ? nextEnd : drag.originalStart };
}

function dependencyAnchors(type: string, source: { start: Date; end: Date }, target: { start: Date; end: Date }, timelineStart: Date, zoom: ZoomLevel) {
  const sourceUsesStart = type === "Start To Start" || type === "Start To Finish";
  const targetUsesEnd = type === "Finish To Finish" || type === "Start To Finish";
  return {
    sourceX: daysBetween(timelineStart, sourceUsesStart ? source.start : source.end) * pixelsPerDay(zoom),
    targetX: daysBetween(timelineStart, targetUsesEnd ? target.end : target.start) * pixelsPerDay(zoom),
  };
}

function pixelsPerDay(zoom: ZoomLevel) {
  const config = zoomConfig[zoom];
  return config.columnWidth / config.daysPerColumn;
}

function parseDate(value?: string | null) {
  if (!value) return null;
  const [year, month, day] = value.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function toIsoDate(value: Date) {
  const date = startOfDay(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return startOfDay(next);
}

function daysBetween(start: Date, end: Date) {
  return Math.round((startOfDay(end).getTime() - startOfDay(start).getTime()) / 86_400_000);
}
