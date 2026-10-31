import MoveBoard from "@/components/interaction/MoveBoard";
import { api } from "@/services/api";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, CalendarDays, Gauge, RefreshCw, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { reportsAPI } from "../services/api";
import type { PMSWorkloadHeatmapResponse } from "../types";

type WorkloadBasis = "hours" | "story_points" | "task_count";

type WorkloadFilters = {
  projectId: string;
  sprintId: string;
  teamId: string;
  from: string;
  to: string;
  basis: WorkloadBasis;
};

const initialFilters: WorkloadFilters = {
  projectId: "",
  sprintId: "",
  teamId: "",
  from: startOfWeek(new Date()).toISOString().slice(0, 10),
  to: addDays(startOfWeek(new Date()), 55).toISOString().slice(0, 10),
  basis: "hours",
};

export default function WorkloadPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<WorkloadFilters>(initialFilters);
  const [data, setData] = useState<PMSWorkloadHeatmapResponse | null>(null);
  const [selectedCell, setSelectedCell] = useState<{ userName: string; week: string; cell: PMSWorkloadHeatmapResponse["rows"][number]["cells"][number] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    reportsAPI
      .workloadHeatmap(filters)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || "Unable to load workload."))
      .finally(() => setLoading(false));
  };

  useRefreshableEffect(() => {
    load();
  }, [filters.projectId, filters.sprintId, filters.teamId, filters.from, filters.to, filters.basis]);

  const visibleSprints = useMemo(() => {
    const sprints = data?.sprints || [];
    return filters.projectId ? sprints.filter((sprint) => String(sprint.project_id) === filters.projectId) : sprints;
  }, [data?.sprints, filters.projectId]);

  const setFilter = (key: keyof WorkloadFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="page-title">Workload</h1>
          <p className="page-description">Compare weekly assignment load against working hours, dated capacity, holidays and approved leave.</p>
        </div>
        <Button variant="outline" asChild><Link to="/pms/management">Manage dated capacity & working schedules</Link></Button>
        <Button variant="outline" onClick={load}>
          <RefreshCw className="h-4 w-4" />Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={Users} label="People" value={data?.rows.length || 0} />
        <Metric icon={AlertTriangle} label="Over capacity weeks" value={data?.summary.over_capacity || 0} tone="text-red-600" />
        <Metric icon={Gauge} label="Near capacity weeks" value={data?.summary.near_capacity || 0} tone="text-amber-600" />
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarDays className="h-5 w-5" />Filters</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <Field label="Project">
            <select className="input" value={filters.projectId} onChange={(event) => setFilter("projectId", event.target.value)}>
              <option value="">All projects</option>
              {data?.projects.map((project) => <option key={project.id} value={project.id}>{project.project_key ? `${project.project_key} - ${project.name}` : project.name}</option>)}
            </select>
          </Field>
          <Field label="Sprint">
            <select className="input" value={filters.sprintId} onChange={(event) => setFilter("sprintId", event.target.value)}>
              <option value="">All sprints</option>
              {visibleSprints.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}
            </select>
          </Field>
          <Field label="Team">
            <select className="input" value={filters.teamId} onChange={(event) => setFilter("teamId", event.target.value)}>
              <option value="">All teams</option>
            </select>
          </Field>
          <Field label="Basis">
            <select className="input" value={filters.basis} onChange={(event) => setFilter("basis", event.target.value as WorkloadBasis)}>
              <option value="hours">Hours</option>
              <option value="story_points">Story points</option>
              <option value="task_count">Task count</option>
            </select>
          </Field>
          <Field label="From"><Input type="date" value={filters.from} onChange={(event) => setFilter("from", event.target.value)} /></Field>
          <Field label="To"><Input type="date" value={filters.to} onChange={(event) => setFilter("to", event.target.value)} /></Field>
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <Card>
        <CardContent className="p-0">
          {loading ? <div className="m-4 h-80 rounded-lg skeleton" /> : null}
          {!loading && !data?.rows.length ? (
            <div className="p-10 text-center">
              <h2 className="text-lg font-semibold">No workload found</h2>
              <p className="mt-1 text-sm text-muted-foreground">Assign tasks to team members or adjust the date range.</p>
            </div>
          ) : null}
          {!loading && data?.rows.length ? (
            <div className="overflow-x-auto">
              <div className="min-w-[980px]">
                <div className="grid border-b bg-muted/30" style={{ gridTemplateColumns: `260px repeat(${data.weeks.length}, minmax(132px, 1fr)) 150px` }}>
                  <div className="border-r p-3 text-xs font-semibold uppercase text-muted-foreground">Assignee</div>
                  {data.weeks.map((week) => <div key={week.week_start} className="border-r p-3 text-xs font-semibold uppercase text-muted-foreground">{week.label}</div>)}
                  <div className="p-3 text-xs font-semibold uppercase text-muted-foreground">Total</div>
                </div>
                {data.rows.map((row) => (
                  <div key={row.user_id} className="grid border-b" style={{ gridTemplateColumns: `260px repeat(${data.weeks.length}, minmax(132px, 1fr)) 150px` }}>
                    <div className="border-r p-3">
                      <p className="font-semibold">{row.user_name}</p>
                      <p className="truncate text-xs text-muted-foreground">{row.email || "Team member"}</p>
                    </div>
                    {row.cells.map((cell) => (
                      <button
                        key={cell.week_start}
                        type="button"
                        className={cn("border-r p-3 text-left transition hover:bg-muted/60", cellTone(cell.status))}
                        onClick={() => setSelectedCell({ userName: row.user_name, week: cell.week_start, cell })}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold">{cell.load_value} {cell.load_unit}</span>
                          <Badge variant="outline">{cell.utilization_percent}%</Badge>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">{cell.planned_hours}h / {cell.capacity_hours}h</p>
                        <p className="text-xs text-muted-foreground">{cell.story_points} pts / {cell.task_count} tasks</p>
                      </button>
                    ))}
                    <div className="p-3">
                      <p className="font-semibold">{row.totals.utilization_percent}%</p>
                      <p className="text-xs text-muted-foreground">{row.totals.planned_hours}h planned</p>
                      <p className="text-xs text-muted-foreground">{row.totals.capacity_hours}h capacity</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {data && <Card><CardHeader><CardTitle>Reassign work</CardTitle></CardHeader><CardContent><MoveBoard label="Resource assignments" reorder={false} groups={data.rows.map(r => ({ id: String(r.user_id), label: r.user_name }))} items={data.rows.flatMap(r => [...new Map(r.cells.flatMap(c => c.tasks).map(t => [t.id, t])).values()].map(t => ({ id: `${r.user_id}:${t.id}`, label: t.title, group: String(r.user_id), content: <span className="text-xs text-muted-foreground">{t.task_key} · {t.status}</span> })))} onMove={async ({ item, group }) => {
        if (item.group === group) return;
        const [source, taskId] = String(item.id).split(":").map(Number);
        const { data: current } = await api.get(`/project-management/my-work/tasks/${taskId}/assignment`);
        await api.put(`/project-management/my-work/tasks/${taskId}/assignment`, { version: current.version, people: [...new Set([...current.assignment.people.filter((id: number) => id !== source), Number(group)])], teams: current.group_targets.filter((g: {kind: string}) => g.kind === "teams").map((g: {id: number}) => g.id), batches: current.group_targets.filter((g: {kind: string}) => g.kind === "batches").map((g: {id: number}) => g.id), notify: true });
        load();
      }} /></CardContent></Card>}

      {selectedCell ? (
        <div className="fixed inset-0 z-50 flex items-end justify-end bg-black/20 p-4" onClick={() => setSelectedCell(null)}>
          <div className="w-full max-w-xl rounded-lg border bg-background shadow-xl" onClick={(event) => event.stopPropagation()}>
            <div className="border-b p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{selectedCell.userName}</h2>
                  <p className="text-sm text-muted-foreground">Week of {formatDate(selectedCell.week)}</p>
                </div>
                <Badge className={selectedCell.cell.status === "over" ? "bg-red-100 text-red-700" : selectedCell.cell.status === "near" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}>
                  {selectedCell.cell.utilization_percent}% utilized
                </Badge>
              </div>
            </div>
            <div className="max-h-[65vh] space-y-3 overflow-auto p-4">
              <div className="grid grid-cols-4 gap-2 text-sm">
                <MiniStat label="Hours" value={`${selectedCell.cell.planned_hours}/${selectedCell.cell.capacity_hours}`} />
                <MiniStat label="Points" value={selectedCell.cell.story_points} />
                <MiniStat label="Tasks" value={selectedCell.cell.task_count} />
                <MiniStat label="Basis" value={selectedCell.cell.load_unit} />
              </div>
              {selectedCell.cell.tasks.map((task) => (
                <button key={task.id} type="button" className="w-full rounded-md border p-3 text-left hover:bg-muted/50" onClick={() => navigate(`/pms/tasks/${task.id}`)}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-semibold text-primary">{task.task_key}</p>
                      <h3 className="font-medium">{task.title}</h3>
                    </div>
                    <Badge variant="outline">{task.priority}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{task.status} / {task.planned_hours}h / {task.story_points} pts</p>
                </button>
              ))}
              {!selectedCell.cell.tasks.length ? <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">No assigned tasks in this week.</p> : null}
            </div>
            <div className="border-t p-4 text-right"><Button variant="outline" onClick={() => setSelectedCell(null)}>Close</Button></div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone = "text-primary" }: { icon: typeof Users; label: string; value: number; tone?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={cn("text-2xl font-semibold", tone)}>{value}</p>
        </div>
        <Icon className={cn("h-5 w-5", tone)} />
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-muted/50 p-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}

function cellTone(status: string) {
  if (status === "over") return "bg-red-50";
  if (status === "near") return "bg-amber-50";
  return "bg-emerald-50/50";
}

function startOfWeek(day: Date) {
  const copy = new Date(day);
  const diff = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - diff);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(day: Date, amount: number) {
  const copy = new Date(day);
  copy.setDate(copy.getDate() + amount);
  return copy;
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
