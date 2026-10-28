import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, BriefcaseBusiness, CheckCircle2, Clock, FolderKanban, Milestone, TrendingUp, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatDate, statusColor } from "@/lib/utils";
import { portfolioAPI } from "../services/api";
import type { PMSPortfolioHealthTrendResponse, PMSPortfolioProject, PMSPortfolioSummary } from "../types";

const chartColors = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"];

type PortfolioFilters = {
  ownerId: string;
  clientId: string;
  status: string;
  health: string;
  teamId: string;
};

const defaultFilters: PortfolioFilters = {
  ownerId: "",
  clientId: "",
  status: "",
  health: "",
  teamId: "",
};

export default function PortfolioPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<PortfolioFilters>(defaultFilters);
  const [summary, setSummary] = useState<PMSPortfolioSummary | null>(null);
  const [projects, setProjects] = useState<PMSPortfolioProject[]>([]);
  const [trend, setTrend] = useState<PMSPortfolioHealthTrendResponse["items"]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useRefreshableEffect(() => {
    setLoading(true);
    setError(null);
    const commonFilters = {
      ownerId: filters.ownerId,
      clientId: filters.clientId,
      status: filters.status,
    };
    Promise.all([
      portfolioAPI.summary(commonFilters),
      portfolioAPI.projects({ ...commonFilters, health: filters.health }),
      portfolioAPI.healthTrend(commonFilters),
    ])
      .then(([summaryData, projectData, trendData]) => {
        setSummary(summaryData);
        setProjects(projectData.items);
        setTrend(trendData.items);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Unable to load portfolio."))
      .finally(() => setLoading(false));
  }, [filters.ownerId, filters.clientId, filters.status, filters.health, filters.teamId]);

  const setFilter = (key: keyof PortfolioFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Portfolio</h1>
        <p className="page-description">Executive view of project health, progress, delivery risk, workload, milestones, and open work.</p>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-5">
          <Filter label="Owner" value={filters.ownerId} onChange={(value) => setFilter("ownerId", value)}>
            <option value="">All owners</option>
            {summary?.filters.owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.name}</option>)}
          </Filter>
          <Filter label="Client" value={filters.clientId} onChange={(value) => setFilter("clientId", value)}>
            <option value="">All clients</option>
            {summary?.filters.clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
          </Filter>
          <Filter label="Status" value={filters.status} onChange={(value) => setFilter("status", value)}>
            <option value="">All statuses</option>
            {summary?.filters.statuses.map((item) => <option key={item}>{item}</option>)}
          </Filter>
          <Filter label="Health" value={filters.health} onChange={(value) => setFilter("health", value)}>
            <option value="">All health</option>
            {summary?.filters.health.map((item) => <option key={item}>{item}</option>)}
          </Filter>
          <Filter label="Team" value={filters.teamId} onChange={(value) => setFilter("teamId", value)}>
            <option value="">All teams</option>
          </Filter>
        </CardContent>
      </Card>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {loading ? <div className="h-96 rounded-lg skeleton" /> : null}

      {!loading && summary ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Metric icon={FolderKanban} label="Total projects" value={summary.total_projects} />
            <Metric icon={BriefcaseBusiness} label="Active projects" value={summary.active_projects} />
            <Metric icon={Clock} label="Overdue projects" value={summary.overdue_projects} tone="text-red-600" />
            <Metric icon={AlertTriangle} label="At risk" value={summary.at_risk_projects} tone="text-amber-600" />
            <Metric icon={CheckCircle2} label="Completed" value={summary.completed_projects} tone="text-emerald-600" />
            <Metric icon={TrendingUp} label="Open tasks" value={summary.total_open_tasks} />
            <Metric icon={Users} label="Avg workload" value={summary.team_workload_summary.avg_open_hours_per_assignee} suffix="h" />
            <Metric icon={Milestone} label="Upcoming milestones" value={summary.upcoming_milestones} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <ChartCard title="Project health distribution">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={summary.health_distribution} dataKey="value" nameKey="name" innerRadius={60} outerRadius={105} paddingAngle={3}>
                    {summary.health_distribution.map((_, index) => <Cell key={index} fill={chartColors[index % chartColors.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Tasks by status">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary.tasks_by_status}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Overdue trend">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="overdue_tasks" stroke="#dc2626" name="Overdue tasks" />
                  <Line type="monotone" dataKey="at_risk" stroke="#f59e0b" name="At-risk projects" />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Project progress over time">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="avg_progress" stroke="#16a34a" name="Average progress %" />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <Card>
            <CardHeader><CardTitle>Projects</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="min-w-[1120px] w-full text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    {["Project", "Owner", "Status", "Health", "Progress", "Open", "Overdue", "High risks", "Sprint", "Start", "Due", "Budget", "Client"].map((heading) => (
                      <th key={heading} className="p-3 font-semibold">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr key={project.id} className="cursor-pointer border-b hover:bg-muted/50" onClick={() => navigate(`/pms/projects/${project.id}`)}>
                      <td className="p-3">
                        <p className="font-semibold">{project.name}</p>
                        <p className="text-xs text-muted-foreground">{project.project_key}</p>
                      </td>
                      <td className="p-3">{project.owner_name || "Unassigned"}</td>
                      <td className="p-3"><Badge className={statusColor(project.status)}>{project.status}</Badge></td>
                      <td className="p-3"><Badge className={healthTone(project.health)}>{project.health}</Badge></td>
                      <td className="p-3">
                        <div className="h-2 w-28 overflow-hidden rounded-full bg-muted">
                          <div className="h-full bg-primary" style={{ width: `${Math.min(100, project.progress_percent)}%` }} />
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">{project.progress_percent}%</p>
                      </td>
                      <td className="p-3">{project.open_tasks}</td>
                      <td className="p-3">{project.overdue_tasks}</td>
                      <td className="p-3">{project.open_high_risks ?? 0}</td>
                      <td className="p-3">{project.active_sprint_name || project.sprint_status}</td>
                      <td className="p-3">{project.start_date ? formatDate(project.start_date) : "-"}</td>
                      <td className="p-3">{project.due_date ? formatDate(project.due_date) : "-"}</td>
                      <td className="p-3">{project.budget_amount ? money(project.budget_amount) : "-"}</td>
                      <td className="p-3">{project.client_name || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!projects.length ? <div className="p-8 text-center text-sm text-muted-foreground">No accessible projects match these filters.</div> : null}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, suffix, tone = "text-primary" }: { icon: typeof FolderKanban; label: string; value: number; suffix?: string; tone?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={cn("text-2xl font-semibold", tone)}>{value}{suffix || ""}</p>
        </div>
        <Icon className={cn("h-5 w-5", tone)} />
      </CardContent>
    </Card>
  );
}

function Filter({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="space-y-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select className="input" value={value} onChange={(event) => onChange(event.target.value)}>{children}</select>
    </label>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="h-80">{children}</CardContent></Card>;
}

function healthTone(health: string) {
  if (health === "Blocked") return "bg-red-100 text-red-700 hover:bg-red-100";
  if (health === "At Risk") return "bg-amber-100 text-amber-700 hover:bg-amber-100";
  return "bg-emerald-100 text-emerald-700 hover:bg-emerald-100";
}

function money(value: number) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}
