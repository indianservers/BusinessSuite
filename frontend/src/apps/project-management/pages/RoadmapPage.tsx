import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, ChevronDown, ChevronRight, GitBranch, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn, statusColor } from "@/lib/utils";
import { planningAPI } from "../services/api";
import type { PMSEpic, PMSRoadmapResponse, PMSTaskListItem } from "../types";

type ZoomLevel = "month" | "week";

type RoadmapFilters = {
  projectId: string;
  ownerId: string;
  status: string;
  from: string;
  to: string;
};

const defaultFilters: RoadmapFilters = {
  projectId: "",
  ownerId: "",
  status: "",
  from: startOfMonth(addMonths(new Date(), -1)).toISOString().slice(0, 10),
  to: endOfMonth(addMonths(new Date(), 5)).toISOString().slice(0, 10),
};

const zoomConfig: Record<ZoomLevel, { columnWidth: number; daysPerColumn: number }> = {
  week: { columnWidth: 112, daysPerColumn: 7 },
  month: { columnWidth: 148, daysPerColumn: 30 },
};

export default function RoadmapPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<PMSRoadmapResponse | null>(null);
  const [filters, setFilters] = useState<RoadmapFilters>(defaultFilters);
  const [zoom, setZoom] = useState<ZoomLevel>("month");
  const [expandedEpicIds, setExpandedEpicIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingEpicId, setSavingEpicId] = useState<number | null>(null);

  const loadRoadmap = () => {
    setLoading(true);
    setError(null);
    planningAPI
      .getRoadmap(filters)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || "Unable to load roadmap."))
      .finally(() => setLoading(false));
  };

  useRefreshableEffect(() => {
    loadRoadmap();
  }, [filters.projectId, filters.ownerId, filters.status, filters.from, filters.to]);

  const timeline = useMemo(() => buildTimeline(filters.from, filters.to, zoom), [filters.from, filters.to, zoom]);
  const scheduledEpics = useMemo(() => (data?.epics || []).filter((epic) => epic.start_date && (epic.end_date || epic.target_date)), [data?.epics]);
  const unscheduledEpics = useMemo(() => (data?.epics || []).filter((epic) => !epic.start_date || !(epic.end_date || epic.target_date)), [data?.epics]);

  const setFilter = (key: keyof RoadmapFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const toggleEpic = (epicId: number) => {
    setExpandedEpicIds((current) => current.includes(epicId) ? current.filter((id) => id !== epicId) : [...current, epicId]);
  };

  const updateEpicDates = async (epic: PMSEpic, startDate: Date, endDate: Date) => {
    setSavingEpicId(epic.id);
    setError(null);
    try {
      const updated = await planningAPI.updateEpicSchedule(epic.id, {
        start_date: toISODate(startDate),
        end_date: toISODate(endDate),
      });
      setData((current) => current ? {
        ...current,
        epics: current.epics.map((item) => item.id === epic.id ? { ...item, ...updated } : item),
      } : current);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to update epic schedule.");
    } finally {
      setSavingEpicId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Roadmap</h1>
          <p className="page-description">Plan epics across projects and sprints with progress, ownership, dependencies, and schedule changes.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="inline-flex rounded-md border p-1">
            {(["month", "week"] as ZoomLevel[]).map((item) => (
              <Button key={item} type="button" size="sm" variant={zoom === item ? "default" : "ghost"} onClick={() => setZoom(item)}>
                {item === "month" ? "Month" : "Week"}
              </Button>
            ))}
          </div>
          <Button variant="outline" onClick={loadRoadmap}>
            <RefreshCw className="h-4 w-4" />Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarDays className="h-5 w-5" />Roadmap filters</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <SelectField label="Project" value={filters.projectId} onChange={(value) => setFilter("projectId", value)}>
            <option value="">All projects</option>
            {data?.projects.map((project) => <option key={project.id} value={project.id}>{project.project_key ? `${project.project_key} - ${project.name}` : project.name}</option>)}
          </SelectField>
          <SelectField label="Owner" value={filters.ownerId} onChange={(value) => setFilter("ownerId", value)}>
            <option value="">All owners</option>
            {data?.owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.name}</option>)}
          </SelectField>
          <SelectField label="Status" value={filters.status} onChange={(value) => setFilter("status", value)}>
            <option value="">All statuses</option>
            {data?.statuses.map((status) => <option key={status}>{status}</option>)}
          </SelectField>
          <label className="space-y-1 text-sm">
            <span className="font-medium text-muted-foreground">From</span>
            <Input type="date" value={filters.from} onChange={(event) => setFilter("from", event.target.value)} />
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-medium text-muted-foreground">To</span>
            <Input type="date" value={filters.to} onChange={(event) => setFilter("to", event.target.value)} />
          </label>
          <div className="rounded-md bg-muted/40 p-3 text-sm">
            <p className="font-medium">{data?.epics.length || 0} epics</p>
            <p className="text-xs text-muted-foreground">{unscheduledEpics.length} unscheduled</p>
          </div>
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <Card>
        <CardContent className="p-0">
          {loading ? <div className="m-4 h-80 rounded-lg skeleton" /> : null}
          {!loading && !scheduledEpics.length && !unscheduledEpics.length ? (
            <div className="p-10 text-center">
              <h2 className="text-lg font-semibold">No roadmap epics found</h2>
              <p className="mt-1 text-sm text-muted-foreground">Adjust the date range or create epics from a project planning page.</p>
            </div>
          ) : null}
          {!loading && scheduledEpics.length ? (
            <div className="overflow-x-auto">
              <div className="min-w-[980px]" style={{ width: timeline.width + 360 }}>
                <div className="sticky top-0 z-10 grid border-b bg-background" style={{ gridTemplateColumns: `360px ${timeline.width}px` }}>
                  <div className="border-r p-3 text-xs font-semibold uppercase text-muted-foreground">Epic</div>
                  <div className="relative h-12">
                    {timeline.columns.map((column) => (
                      <div key={column.key} className="absolute top-0 flex h-12 items-center border-r px-2 text-xs font-medium text-muted-foreground" style={{ left: column.x, width: column.width }}>
                        {column.label}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  {scheduledEpics.map((epic) => (
                    <EpicRoadmapRow
                      key={epic.id}
                      epic={epic}
                      expanded={expandedEpicIds.includes(epic.id)}
                      saving={savingEpicId === epic.id}
                      timeline={timeline}
                      zoom={zoom}
                      sprints={data?.sprints || []}
                      onToggle={() => toggleEpic(epic.id)}
                      onTaskOpen={(task) => navigate(`/pms/tasks/${task.id}`)}
                      onDateChange={updateEpicDates}
                    />
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {!loading && unscheduledEpics.length ? (
        <Card>
          <CardHeader><CardTitle className="text-base">Unscheduled epics</CardTitle></CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {unscheduledEpics.map((epic) => (
              <div key={epic.id} className="rounded-md border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold text-primary">{epic.epic_key}</p>
                    <h2 className="mt-1 font-semibold">{epic.name}</h2>
                  </div>
                  <Badge className={statusColor(epic.status)}>{epic.status}</Badge>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{epic.project_name || epic.project_key || "Project"} - {epic.owner_name || "No owner"}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Input type="date" onChange={(event) => {
                    const start = parseDate(event.target.value);
                    const end = addDays(start, 14);
                    updateEpicDates(epic, start, end);
                  }} />
                  <Button variant="outline" disabled={savingEpicId === epic.id}>Schedule</Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function EpicRoadmapRow({
  epic,
  expanded,
  saving,
  timeline,
  zoom,
  sprints,
  onToggle,
  onTaskOpen,
  onDateChange,
}: {
  epic: PMSEpic;
  expanded: boolean;
  saving: boolean;
  timeline: ReturnType<typeof buildTimeline>;
  zoom: ZoomLevel;
  sprints: PMSRoadmapResponse["sprints"];
  onToggle: () => void;
  onTaskOpen: (task: PMSTaskListItem) => void;
  onDateChange: (epic: PMSEpic, startDate: Date, endDate: Date) => void;
}) {
  const start = parseDate(epic.start_date || timeline.start);
  const end = parseDate(epic.end_date || epic.target_date || epic.start_date || timeline.start);
  const left = Math.max(0, daysBetween(timeline.startDate, start) * timeline.dayWidth);
  const width = Math.max(28, (daysBetween(start, end) + 1) * timeline.dayWidth);
  const progress = Math.min(100, Math.max(0, epic.progress_percent || 0));
  const rowHeight = expanded ? 92 + (epic.tasks?.length || 0) * 42 : 92;

  const [drag, setDrag] = useState<{ x: number; days: number; mode: "move" | "start" | "end" } | null>(null);
  const begin = (event: ReactPointerEvent<HTMLDivElement>, mode: "move" | "start" | "end" = "move") => {
    if (saving || event.button !== 0) return;
    event.preventDefault(); event.stopPropagation();event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ x: event.clientX, days: 0, mode });
  };
  const movedStart = drag && drag.mode !== "end" ? addDays(start, drag.days) : start;
  const movedEnd = drag && drag.mode !== "start" ? addDays(end, drag.days) : end;
  const previewLeft = drag ? Math.max(0, daysBetween(timeline.startDate, movedStart) * timeline.dayWidth) : left;
  const previewWidth = drag ? Math.max(28, (daysBetween(movedStart, movedEnd) + 1) * timeline.dayWidth) : width;
  const finish = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (drag.days && movedEnd >= movedStart) onDateChange(epic, movedStart, movedEnd);
    setDrag(null);
  };

  return (
    <div className="grid border-b" style={{ gridTemplateColumns: `360px ${timeline.width}px`, minHeight: rowHeight }}>
      <div className="border-r p-3">
        <button type="button" onClick={onToggle} className="flex w-full items-start gap-2 text-left">
          {expanded ? <ChevronDown className="mt-0.5 h-4 w-4" /> : <ChevronRight className="mt-0.5 h-4 w-4" />}
          <div className="min-w-0">
            <p className="text-xs font-semibold text-primary">{epic.epic_key} - {epic.project_key || epic.project_name}</p>
            <h2 className="truncate font-semibold">{epic.name}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{epic.owner_name || "No owner"} - {epic.completed_task_count || 0}/{epic.task_count || 0} tasks - {epic.completed_story_points || 0}/{epic.story_points || 0} pts</p>
          </div>
        </button>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge className={statusColor(epic.status)}>{epic.status}</Badge>
          {epic.dependencies?.length ? <Badge variant="outline"><GitBranch className="h-3 w-3" />{epic.dependencies.length} deps</Badge> : null}
        </div>
      </div>
      <div className="relative">
        <TimelineGrid timeline={timeline} sprints={sprints} />
        <div
          role="button"
          tabIndex={0}
          title="Drag to reschedule; drag an edge to resize. Arrow keys move one day, Shift + arrows move one week."
          aria-label={`Reschedule ${epic.name}`}
          onPointerDown={e => begin(e)}
          onPointerMove={e => { if (drag) setDrag({ ...drag, days: Math.round((e.clientX - drag.x) / timeline.dayWidth) }); }}
          onPointerUp={finish}
          onPointerCancel={() => setDrag(null)}
          onKeyDown={e => { if (saving || !["ArrowLeft", "ArrowRight"].includes(e.key)) return; e.preventDefault(); const days = (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 7 : 1); onDateChange(epic, addDays(start,days), addDays(end,days)); }}
          className={cn("absolute top-5 h-9 cursor-grab overflow-hidden rounded-md border text-white shadow-sm active:cursor-grabbing", saving ? "opacity-60" : "")}
          style={{ left: previewLeft, width: previewWidth, backgroundColor: epic.color || "#2563eb", touchAction: "none" }}
        >
          <span className="absolute inset-y-0 left-0 z-20 w-2 cursor-ew-resize bg-black/10" onPointerDown={e=>begin(e as unknown as ReactPointerEvent<HTMLDivElement>,"start")} />
          <span className="absolute inset-y-0 right-0 z-20 w-2 cursor-ew-resize bg-black/10" onPointerDown={e=>begin(e as unknown as ReactPointerEvent<HTMLDivElement>,"end")} />
          <div className="absolute inset-y-0 left-0 bg-white/25" style={{ width: `${progress}%` }} />
          <div className="relative flex h-full items-center justify-between gap-2 px-3 text-xs font-semibold">
            <span className="truncate">{epic.name}</span>
            <span>{progress}%</span>
          </div>
        </div>
        {expanded ? (
          <div className="absolute left-0 right-0 top-16 space-y-1 px-3">
            {(epic.tasks || []).map((task) => (
              <button key={task.id} type="button" onClick={() => onTaskOpen(task)} className="grid h-9 w-full grid-cols-[120px_1fr_90px_70px] items-center gap-2 rounded-md border bg-background px-2 text-left text-xs hover:bg-muted/40">
                <span className="font-semibold text-primary">{task.task_key}</span>
                <span className="truncate">{task.title}</span>
                <span>{task.assignee_name || "Unassigned"}</span>
                <Badge className={statusColor(task.status)}>{task.status}</Badge>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TimelineGrid({ timeline, sprints }: { timeline: ReturnType<typeof buildTimeline>; sprints: PMSRoadmapResponse["sprints"] }) {
  return (
    <div className="absolute inset-0">
      {timeline.columns.map((column) => <div key={column.key} className="absolute inset-y-0 border-r bg-muted/10" style={{ left: column.x, width: column.width }} />)}
      {sprints.map((sprint) => {
        const start = parseDate(sprint.start_date);
        const end = parseDate(sprint.end_date);
        if (end < timeline.startDate || start > timeline.endDate) return null;
        const left = Math.max(0, daysBetween(timeline.startDate, start) * timeline.dayWidth);
        const width = Math.max(16, (daysBetween(start, end) + 1) * timeline.dayWidth);
        return (
          <div key={sprint.id} className="absolute top-0 h-full border-l border-dashed border-sky-400/80 bg-sky-500/5" style={{ left, width }}>
            <span className="absolute left-1 top-1 max-w-28 truncate text-[10px] font-medium text-sky-700">{sprint.name}</span>
          </div>
        );
      })}
    </div>
  );
}

function SelectField({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
        {children}
      </select>
    </label>
  );
}

function buildTimeline(from: string, to: string, zoom: ZoomLevel) {
  const startDate = parseDate(from);
  const endDate = parseDate(to);
  const config = zoomConfig[zoom];
  const totalDays = Math.max(1, daysBetween(startDate, endDate) + 1);
  const dayWidth = config.columnWidth / config.daysPerColumn;
  const count = Math.ceil(totalDays / config.daysPerColumn);
  const columns = Array.from({ length: count }).map((_, index) => {
    const date = addDays(startDate, index * config.daysPerColumn);
    return {
      key: toISODate(date),
      label: zoom === "month" ? date.toLocaleDateString([], { month: "short", year: "numeric" }) : `Week ${date.toLocaleDateString([], { month: "short", day: "numeric" })}`,
      x: index * config.columnWidth,
      width: config.columnWidth,
    };
  });
  return { start: from, to, startDate, endDate, width: count * config.columnWidth, columns, dayWidth };
}

function parseDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function toISODate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,"0")}-${String(value.getDate()).padStart(2,"0")}`;
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function addMonths(value: Date, months: number) {
  const next = new Date(value);
  next.setMonth(next.getMonth() + months);
  return next;
}

function startOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

function endOfMonth(value: Date) {
  return new Date(value.getFullYear(), value.getMonth() + 1, 0);
}

function daysBetween(start: Date, end: Date) {
  const ms = new Date(end.getFullYear(), end.getMonth(), end.getDate()).getTime() - new Date(start.getFullYear(), start.getMonth(), start.getDate()).getTime();
  return Math.round(ms / 86_400_000);
}
