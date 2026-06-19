import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Link2, RefreshCw, Trash2, ZoomIn } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatDate, statusColor } from "@/lib/utils";
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
const labelWidth = 288;
const zoomConfig: Record<ZoomLevel, { columnWidth: number; daysPerColumn: number }> = {
  day: { columnWidth: 44, daysPerColumn: 1 },
  week: { columnWidth: 104, daysPerColumn: 7 },
  month: { columnWidth: 132, daysPerColumn: 30 },
};
const dependencyTypes = ["Finish To Start", "Start To Start", "Finish To Finish", "Start To Finish"];
const defaultFilters: FilterState = { projectId: "", sprintId: "", assigneeId: "", epicId: "", status: "" };

export default function GanttPage() {
  const { projectId } = useParams<{ projectId: string }>();
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

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await ganttAPI.get(filters);
      setData(response);
      setTasks(response.tasks);
      setDependencies(response.dependencies);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load Gantt timeline.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setFilters((current) => ({ ...current, projectId: projectId || current.projectId }));
  }, [projectId]);

  useEffect(() => {
    load();
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
      const next = calculateDraggedDates(current, dayDelta);
      try {
        const result = await ganttAPI.updateSchedule(current.taskId, { start_date: toIsoDate(next.start), due_date: toIsoDate(next.end) });
        setTasks((items) => items.map((task) => task.id === current.taskId ? { ...task, ...result.task } : task));
        if (data) setData({ ...data, warnings: result.warnings });
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Unable to update schedule.");
        load();
      }
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

  const createDependency = async () => {
    if (!sourceTaskId || !targetTaskId || sourceTaskId === targetTaskId) return;
    setError(null);
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
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to create dependency.");
    }
  };

  const deleteDependency = async (dependencyId: number) => {
    setDependencies((items) => items.filter((item) => item.id !== dependencyId));
    try {
      await ganttAPI.deleteDependency(dependencyId);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to delete dependency.");
      await load();
    }
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
          {selectedProjectId ? <Button asChild variant="outline"><Link to={`/pms/projects/${selectedProjectId}/board`}>Open board</Link></Button> : null}
          <Button variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button>
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

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <Card>
        <CardContent className="overflow-auto p-0">
          {loading ? <div className="skeleton m-5 h-96 rounded-lg" /> : null}
          {!loading && !rows.length ? <div className="m-5 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">Add task start or due dates to populate the Gantt timeline.</div> : null}
          {!loading && rows.length ? (
            <div className="min-w-full" style={{ width: labelWidth + timeline.width }}>
              <div className="sticky top-0 z-20 grid bg-background" style={{ gridTemplateColumns: `${labelWidth}px ${timeline.width}px` }}>
                <div className="border-b border-r p-3 text-xs font-semibold uppercase text-muted-foreground">Task</div>
                <div className="relative border-b" style={{ height: 44 }}>
                  {timeline.columns.map((column) => (
                    <div key={column.key} className="absolute top-0 flex h-11 items-center border-r px-2 text-xs font-medium text-muted-foreground" style={{ left: column.x, width: column.width }}>
                      {column.label}
                    </div>
                  ))}
                </div>
              </div>
              <div className="relative grid" style={{ gridTemplateColumns: `${labelWidth}px ${timeline.width}px`, minHeight: rows.length * rowHeight }}>
                <div>
                  {rows.map(({ task }) => (
                    <div key={task.id} className="flex h-[52px] items-center gap-2 border-b border-r px-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-semibold">{task.task_key}</span>
                          {task.is_blocking ? <Badge variant="outline" className="border-red-200 text-red-700">Blocked</Badge> : null}
                        </div>
                        <p className="truncate text-xs text-muted-foreground">{task.title}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="relative overflow-hidden">
                  <TimelineGrid rows={rows.length} timeline={timeline} />
                  <DependencyArrows dependencies={dependencies} rows={rows} timelineStart={timeline.start} zoom={zoom} />
                  {rows.map(({ task, index, schedule }) => (
                    <TaskBar
                      key={task.id}
                      task={task}
                      index={index}
                      schedule={schedule}
                      timelineStart={timeline.start}
                      zoom={zoom}
                      warnings={warningByTask.get(task.id) || []}
                      onDragStart={(mode, event) => {
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

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="h-5 w-5" />Dependencies</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[1fr_1fr_11rem_6rem_auto]">
              <select value={sourceTaskId} onChange={(event) => setSourceTaskId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option value="">Source task</option>
                {tasks.map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
              </select>
              <select value={targetTaskId} onChange={(event) => setTargetTaskId(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                <option value="">Target task</option>
                {tasks.map((task) => <option key={task.id} value={task.id}>{task.task_key} - {task.title}</option>)}
              </select>
              <select value={dependencyType} onChange={(event) => setDependencyType(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm">
                {dependencyTypes.map((item) => <option key={item}>{item}</option>)}
              </select>
              <input type="number" value={lagDays} onChange={(event) => setLagDays(event.target.value)} className="h-10 rounded-md border bg-background px-3 text-sm" placeholder="Lag" />
              <Button type="button" onClick={createDependency}>Add</Button>
            </div>
            <div className="space-y-2">
              {dependencies.map((dependency) => <DependencyRow key={dependency.id} dependency={dependency} onDelete={() => deleteDependency(dependency.id)} />)}
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
                  <Link key={item.task.id} to={`/pms/tasks/${item.task.id}`} className="block rounded-md border p-2 hover:bg-muted/50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{item.task.task_key} - {item.task.title}</p>
                        <p className="text-xs text-muted-foreground">{item.reason}</p>
                      </div>
                      <Badge className={statusColor(item.task.status)}>{item.task.status}</Badge>
                    </div>
                  </Link>
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
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
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
}: {
  task: PMSTaskListItem;
  index: number;
  schedule: { start: Date; end: Date };
  timelineStart: Date;
  zoom: ZoomLevel;
  warnings: string[];
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
      <button type="button" aria-label="Resize start date" onMouseDown={(event) => onDragStart("start", event)} className="absolute left-0 top-0 h-full w-2 cursor-ew-resize rounded-l-md bg-black/15" />
      <button type="button" onMouseDown={(event) => onDragStart("move", event)} className="h-full w-full cursor-grab truncate px-3 text-left text-xs font-semibold text-white">
        {task.task_key} {task.title}
      </button>
      <button type="button" aria-label="Resize end date" onMouseDown={(event) => onDragStart("end", event)} className="absolute right-0 top-0 h-full w-2 cursor-ew-resize rounded-r-md bg-black/15" />
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
    if (!source || !target) return null;
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

function DependencyRow({ dependency, onDelete }: { dependency: PMSTaskDependency; onDelete: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3 text-sm md:flex-row md:items-center md:justify-between">
      <div>
        <p className="font-medium">{dependency.source_task_key || dependency.depends_on_task_key} &rarr; {dependency.target_task_key || dependency.task_key}</p>
        <p className="text-xs text-muted-foreground">{dependency.dependency_type} / Lag {dependency.lag_days || 0} days</p>
      </div>
      <Button type="button" size="sm" variant="ghost" onClick={onDelete} aria-label="Delete dependency"><Trash2 className="h-4 w-4" /></Button>
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
  const schedules = tasks.map(taskSchedule);
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
