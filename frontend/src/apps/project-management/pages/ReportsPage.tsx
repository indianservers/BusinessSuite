import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { beginProgress } from "@/lib/async-progress";
import { projectsAPI, reportsAPI, sprintsAPI } from "../services/api";
import type {
  PMSCumulativeFlowReport,
  PMSCycleTimeReport,
  PMSProject,
  PMSProjectHealthReport,
  PMSSprint,
  PMSTaskDistributionReport,
  PMSTeamPerformanceReport,
  PMSTimeInStatusReport,
  ProjectVelocity,
  SprintBurndown,
} from "../types";

const colors = ["#2563eb", "#f59e0b", "#7c3aed", "#16a34a", "#dc2626", "#0891b2", "#64748b"];
const tabs = ["Distribution", "Burndown", "Velocity", "Flow", "Cycle Time", "Time in Status", "Health", "Team"] as const;
type Tab = typeof tabs[number];
const reportNames: Record<Tab, string> = { Distribution: "task-distribution", Burndown: "burndown", Velocity: "velocity", Flow: "cumulative-flow", "Cycle Time": "cycle-time", "Time in Status": "time-in-status", Health: "project-health", Team: "team-performance" };

export default function ReportsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [sprints, setSprints] = useState<PMSSprint[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(projectId || "");
  const [selectedSprintId, setSelectedSprintId] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("Distribution");
  const [distribution, setDistribution] = useState<PMSTaskDistributionReport | null>(null);
  const [burndown, setBurndown] = useState<SprintBurndown | null>(null);
  const [velocity, setVelocity] = useState<ProjectVelocity | null>(null);
  const [flow, setFlow] = useState<PMSCumulativeFlowReport | null>(null);
  const [cycle, setCycle] = useState<PMSCycleTimeReport | null>(null);
  const [timeInStatus, setTimeInStatus] = useState<PMSTimeInStatusReport | null>(null);
  const [health, setHealth] = useState<PMSProjectHealthReport | null>(null);
  const [team, setTeam] = useState<PMSTeamPerformanceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [updatedAt, setUpdatedAt] = useState("");
  const [assigneeOptions, setAssigneeOptions] = useState<PMSTaskDistributionReport["by_assignee"]>([]);
  const requestSequence = useRef(0);
  const usesSprint = activeTab === "Burndown" || activeTab === "Team";
  const usesAssignee = activeTab === "Distribution" || activeTab === "Cycle Time";
  const usesDates = ["Distribution", "Flow", "Cycle Time", "Time in Status"].includes(activeTab);

  const filters = useMemo(() => ({
    projectId: selectedProjectId,
    sprintId: usesSprint ? selectedSprintId : "",
    assigneeId: usesAssignee ? assigneeId : "",
    from: usesDates ? from : "",
    to: usesDates ? to : "",
  }), [assigneeId, from, selectedProjectId, selectedSprintId, to, usesSprint, usesAssignee, usesDates]);

  useEffect(() => {
    projectsAPI.list().then((items) => {
      setProjects(items);

    }).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (projectId) { setSelectedProjectId(projectId); setSelectedSprintId(""); setAssigneeId(""); }
  }, [projectId]);

  useEffect(() => {
    let active = true; setSprints([]); setSelectedSprintId(""); setAssigneeOptions([]);
    if (selectedProjectId) sprintsAPI.list(Number(selectedProjectId)).then(items => { if (active) setSprints(items); }).catch(() => undefined);
    return () => { active = false; };
  }, [selectedProjectId]);

  const loadReports = async () => {
    const sequence = ++requestSequence.current;
    setDistribution(null); setBurndown(null); setVelocity(null); setFlow(null); setCycle(null); setTimeInStatus(null); setHealth(null); setTeam(null); setError(null); setUpdatedAt("");
    if (usesDates && from && to && from > to) { setError("From date must be on or before To date."); setLoading(false); return; }
    setLoading(true);
    const finish = beginProgress(`Loading ${activeTab.toLowerCase()} report`);
    try {
      const read = async () => {
        switch (activeTab) {
          case "Burndown": return selectedSprintId ? reportsAPI.burndown(Number(selectedSprintId)) : null;
          case "Velocity": return selectedProjectId ? reportsAPI.velocity(Number(selectedProjectId)) : null;
          case "Flow": return reportsAPI.cumulativeFlow(filters);
          case "Cycle Time": return reportsAPI.cycleTime(filters);
          case "Time in Status": return reportsAPI.timeInStatus(filters);
          case "Health": return reportsAPI.projectHealth(filters);
          case "Team": return reportsAPI.teamPerformance(filters);
          default: return null;
        }
      };
      const [summary, detail] = await Promise.all([reportsAPI.taskDistribution(activeTab === "Distribution" ? filters : { projectId: selectedProjectId }), read()]);
      if (sequence !== requestSequence.current) { finish(); return; }
      setDistribution(summary);
      setAssigneeOptions(previous => [...new Map([...previous, ...summary.by_assignee].filter(item => item.assignee_id).map(item => [item.assignee_id, item])).values()]);
      switch (activeTab) {
        case "Burndown": setBurndown(detail as SprintBurndown | null); break;
        case "Velocity": setVelocity(detail as ProjectVelocity | null); break;
        case "Flow": setFlow(detail as PMSCumulativeFlowReport); break;
        case "Cycle Time": setCycle(detail as PMSCycleTimeReport); break;
        case "Time in Status": setTimeInStatus(detail as PMSTimeInStatusReport); break;
        case "Health": setHealth(detail as PMSProjectHealthReport); break;
        case "Team": setTeam(detail as PMSTeamPerformanceReport); break;
      }
      setUpdatedAt(new Date().toLocaleTimeString()); finish();
    } catch (err: any) { finish(false); if (sequence === requestSequence.current) setError(err?.response?.data?.detail || "Unable to load this report. Retry to refresh it."); }
    finally { if (sequence === requestSequence.current) setLoading(false); }
  };
  useEffect(() => { void loadReports(); return () => { requestSequence.current++; }; }, [filters, activeTab]);

  const exportReport = async (format: "csv" | "pdf" | "xlsx") => {
    if (exporting) return;
    setExporting(true); setError(null); const finish = beginProgress(`Exporting ${activeTab.toLowerCase()} as ${format.toUpperCase()}`);
    try {
      const report = reportNames[activeTab];
      const blob = await reportsAPI.export({ ...filters, report, format });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = `pms-${report}.${format}`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000); finish();
    } catch (err: any) { finish(false); setError(err?.response?.data?.detail || "Export failed. Please retry."); }
    finally { setExporting(false); }
  };

  const completedTasks = distribution?.by_status.filter(item => ["Done", "Completed", "Closed"].includes(item.name)).reduce((sum, item) => sum + item.tasks, 0) || 0;
  const totalTasks = distribution?.total_tasks || 0;
  const exportDisabled = loading || exporting || !distribution || !!error || (activeTab === "Burndown" && !selectedSprintId) || (activeTab === "Velocity" && !selectedProjectId);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="page-title">PMS reports</h1><div className="flex gap-4 text-sm text-violet-600"><Link to="/pms/analytics/team">Team analytics</Link><Link to="/pms/analytics/projects">Project analytics</Link></div>
          <p className="page-description">Real task, sprint, status-history, flow, cycle-time, health, and team analytics.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadReports()} disabled={loading || exporting}><RefreshCw className="h-4 w-4" />Refresh</Button>
          <Button variant="outline" disabled={exportDisabled} onClick={() => void exportReport("csv")}><Download className="h-4 w-4" />CSV</Button>
          <Button variant="outline" disabled={exportDisabled} onClick={() => void exportReport("xlsx")}><Download className="h-4 w-4" />Excel</Button>
          <Button variant="outline" disabled={exportDisabled} onClick={() => void exportReport("pdf")}><Download className="h-4 w-4" />PDF</Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-5">
          <Select label="Project" value={selectedProjectId} onChange={value => { setSelectedProjectId(value); setSelectedSprintId(""); setAssigneeId(""); }}>
            <option value="">All accessible projects</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </Select>
          {usesSprint && <Select label="Sprint" value={selectedSprintId} onChange={setSelectedSprintId}>
            <option value="">Any sprint</option>
            {sprints.map((sprint) => <option key={sprint.id} value={sprint.id}>{sprint.name}</option>)}
          </Select>}
          {usesAssignee && <Select label="Assignee" value={assigneeId} onChange={setAssigneeId}>
            <option value="">All assignees</option>
            {assigneeOptions.map((item) => <option key={item.assignee_id} value={item.assignee_id}>{item.name}</option>)}
          </Select>}
          {usesDates && <><DateInput label="From" value={from} onChange={setFrom} /><DateInput label="To" value={to} onChange={setTo} /></>}
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div> : null}

      <p role="status" className="text-sm text-muted-foreground">{loading ? "Loading selected report…" : updatedAt ? `Updated at ${updatedAt}` : "Report unavailable"} · {activeTab === "Distribution" ? "Counts reflect the selected creation dates and assignee." : "Summary counts cover the selected project scope."}{activeTab === "Team" && " Shared tasks count once for each collaborator."}{activeTab === "Health" && " Health is a current snapshot, not historical trend data."}</p>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <ReportMetric label="Tasks" value={distribution ? totalTasks : "—"} />
        <ReportMetric label="Done" value={distribution ? completedTasks : "—"} />
        <ReportMetric label="Open" value={distribution ? totalTasks - completedTasks : "—"} />
        <ReportMetric label="Completion" value={distribution ? Math.round(completedTasks / Math.max(totalTasks, 1) * 100) : "—"} suffix="%" />
      </div>

      <div role="tablist" aria-label="Report types" className="flex gap-2 overflow-x-auto" onKeyDown={event => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
        const index = buttons.indexOf(event.target as HTMLButtonElement); if (index < 0) return;
        event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus(); buttons[next].click();
      }}>
        {tabs.map((tab) => (
          <Button role="tab" id={`report-${tab}`} aria-controls="pms-report-panel" aria-selected={activeTab === tab} tabIndex={activeTab === tab ? 0 : -1} key={tab} variant={activeTab === tab ? "default" : "outline"} size="sm" onClick={() => setActiveTab(tab)}>
            {tab}
          </Button>
        ))}
      </div>

      <section id="pms-report-panel" role="tabpanel" aria-labelledby={`report-${activeTab}`} tabIndex={0}>
      {loading ? <div className="skeleton h-96 rounded-lg" /> : null}
      {!loading && activeTab === "Distribution" ? <DistributionCharts data={distribution} /> : null}
      {!loading && activeTab === "Burndown" ? <BurndownChart data={burndown} /> : null}
      {!loading && activeTab === "Velocity" ? <VelocityChart data={velocity} /> : null}
      {!loading && activeTab === "Flow" ? <FlowChart data={flow} /> : null}
      {!loading && activeTab === "Cycle Time" ? <CycleChart data={cycle} /> : null}
      {!loading && activeTab === "Time in Status" ? <TimeInStatusChart data={timeInStatus} /> : null}
      {!loading && activeTab === "Health" ? <HealthChart data={health} /> : null}
      {!loading && activeTab === "Team" ? <TeamPerformance data={team} /> : null}
      </section>
    </div>
  );
}

function DistributionCharts({ data }: { data: PMSTaskDistributionReport | null }) {
  if (!data) return <Empty text="No task distribution data found." />;
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <ChartCard title="Tasks by status">
        <BarChart data={data.by_status}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="tasks" fill="#2563eb" /><Bar dataKey="story_points" fill="#16a34a" /></BarChart>
      </ChartCard>
      <ChartCard title="Priority distribution">
        <PieChart><Pie data={data.by_priority} dataKey="tasks" nameKey="name" innerRadius={70} outerRadius={110}>{data.by_priority.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}</Pie><Tooltip /></PieChart>
      </ChartCard>
    </div>
  );
}

function BurndownChart({ data }: { data: SprintBurndown | null }) {
  if (!data?.points.length) return <Empty text="Start a sprint to capture burndown." />;
  return <ChartCard title="Sprint burndown"><LineChart data={data.points}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Line type="monotone" dataKey="ideal_remaining_points" stroke="#94a3b8" name="Ideal remaining" /><Line type="monotone" dataKey="actual_remaining_points" stroke="#2563eb" name="Actual remaining" /><Line type="monotone" dataKey="completed_points" stroke="#16a34a" name="Completed" /></LineChart></ChartCard>;
}

function VelocityChart({ data }: { data: ProjectVelocity | null }) {
  if (!data?.sprints.length) return <Empty text="Complete sprints to build velocity history." />;
  return <ChartCard title="Velocity tracking"><BarChart data={data.sprints}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="velocity_points" fill="#16a34a" /></BarChart></ChartCard>;
}

function FlowChart({ data }: { data: PMSCumulativeFlowReport | null }) {
  if (!data?.points.length) return <Empty text="No cumulative flow data for this range." />;
  return <ChartCard title="Cumulative flow diagram"><LineChart data={data.points}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis allowDecimals={false} /><Tooltip /><Legend />{data.statuses.map((status, index) => <Line key={status} type="monotone" dataKey={status} stroke={colors[index % colors.length]} dot={false} />)}</LineChart></ChartCard>;
}

function CycleChart({ data }: { data: PMSCycleTimeReport | null }) {
  if (!data?.items.length) return <Empty text="No completed tasks found for cycle-time analysis." />;
  return <ChartCard title="Cycle time / lead time"><BarChart data={data.items.slice(0, 25)}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="task_key" /><YAxis /><Tooltip /><Legend /><Bar dataKey="lead_time_hours" fill="#7c3aed" name="Lead hours" /><Bar dataKey="cycle_time_hours" fill="#2563eb" name="Cycle hours" /></BarChart></ChartCard>;
}

function TimeInStatusChart({ data }: { data: PMSTimeInStatusReport | null }) {
  if (!data?.statuses.length) return <Empty text="No status history found for this range." />;
  return <ChartCard title="Time in status"><BarChart data={data.statuses}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="status" /><YAxis /><Tooltip /><Bar dataKey="days" fill="#f59e0b" /></BarChart></ChartCard>;
}

function HealthChart({ data }: { data: PMSProjectHealthReport | null }) {
  if (!data?.points.length) return <Empty text="No project health data found." />;
  return <ChartCard title="Current project health"><BarChart data={["Good", "At Risk", "Blocked", "Completed"].map(name => ({ name, projects: data.points[0][name as keyof typeof data.points[0]] }))}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="projects" fill="#7c3aed" /></BarChart></ChartCard>;
}

function TeamPerformance({ data }: { data: PMSTeamPerformanceReport | null }) {
  if (!data?.items.length) return <Empty text="No team performance data found." />;
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_26rem]">
      <ChartCard title="Individual velocity"><BarChart data={data.items}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Bar dataKey="completed_points" fill="#16a34a" /><Bar dataKey="assigned_points" fill="#94a3b8" /></BarChart></ChartCard>
      <Card><CardHeader><CardTitle>Team table</CardTitle></CardHeader><CardContent className="space-y-3">{data.items.map((item) => <div key={item.name} className="rounded-md border p-3 text-sm"><div className="flex justify-between font-medium"><span>{item.name}</span><span>{item.completion_rate}%</span></div><p className="text-muted-foreground">{item.completed_tasks}/{item.assigned_tasks} tasks, {item.completed_points}/{item.assigned_points} pts</p></div>)}</CardContent></Card>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="h-96"><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></CardContent></Card>;
}

function ReportMetric({ label, value, suffix }: { label: string; value: number | string; suffix?: string }) {
  return <Card><CardContent className="p-5"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-semibold">{value}{suffix ? ` ${suffix}` : ""}</p></CardContent></Card>;
}

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return <label className="space-y-1 text-sm"><span className="font-medium text-muted-foreground">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-11 w-full rounded-md border bg-background px-3 text-sm">{children}</select></label>;
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="space-y-1 text-sm"><span className="font-medium text-muted-foreground">{label}</span><input type="date" value={value} onChange={(event) => onChange(event.target.value)} className="h-11 w-full rounded-md border bg-background px-3 text-sm" /></label>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">{text}</div>;
}
