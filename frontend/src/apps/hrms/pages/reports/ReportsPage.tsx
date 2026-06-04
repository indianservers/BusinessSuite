import { ReactNode, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Funnel,
  FunnelChart,
  LabelList,
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
import { BarChart3, Download, UserCheck, UserPlus, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { reportsApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

const STALE_TIME = 5 * 60 * 1000;
const TABS = ["Overview Dashboard", "Workforce Analytics", "Saved Reports"] as const;
const tooltipStyle = {
  background: "hsl(var(--background))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  boxShadow: "0 8px 24px rgb(15 23 42 / 0.12)",
  fontSize: 12,
};

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const monthLabel = (month?: string) =>
  month ? new Date(`${month}-01`).toLocaleDateString("en-IN", { month: "short", year: "numeric" }) : "";

const money = (value: unknown) => currency.format(Number(value || 0));

type ReportDefinition = {
  id: number;
  name: string;
  description?: string | null;
  module?: string | null;
  fields_json?: unknown;
};

type ReportResult = {
  columns: string[];
  rows: Record<string, unknown>[];
};

export default function ReportsPage() {
  usePageTitle("Reports & Analytics");
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("Overview Dashboard");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Reports & Analytics</h1>
        <p className="page-description">Live workforce dashboards, statutory insights, and configurable report output.</p>
      </div>

      <div className="flex flex-wrap gap-2 border-b">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Overview Dashboard" && <OverviewDashboard />}
      {activeTab === "Workforce Analytics" && <WorkforceAnalytics />}
      {activeTab === "Saved Reports" && <SavedReports />}
    </div>
  );
}

function OverviewDashboard() {
  const dashboard = useQuery({ queryKey: ["reports-dashboard"], queryFn: () => reportsApi.dashboard().then((r) => r.data), staleTime: STALE_TIME });
  const headcount = useQuery({ queryKey: ["reports-headcount-by-dept"], queryFn: () => reportsApi.headcountByDept().then((r) => r.data), staleTime: STALE_TIME });
  const attendance = useQuery({ queryKey: ["reports-attendance-trend"], queryFn: () => reportsApi.attendanceTrend().then((r) => r.data), staleTime: STALE_TIME });
  const leave = useQuery({ queryKey: ["reports-leave-trend"], queryFn: () => reportsApi.leaveTrend().then((r) => r.data), staleTime: STALE_TIME });
  const payroll = useQuery({ queryKey: ["reports-payroll-summary"], queryFn: () => reportsApi.payrollSummary().then((r) => r.data), staleTime: STALE_TIME });
  const attrition = Number(dashboard.data?.attrition_rate || 0);
  const attritionClass = attrition > 5 ? "text-red-600 bg-red-50" : attrition >= 2 ? "text-yellow-700 bg-yellow-50" : "text-green-700 bg-green-50";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi title="Total Employees" value={dashboard.data?.headcount ?? 0} icon={Users} className="bg-blue-50 text-blue-700" loading={dashboard.isLoading} />
        <Kpi title="Active Employees" value={dashboard.data?.active_count ?? 0} icon={UserCheck} className="bg-green-50 text-green-700" loading={dashboard.isLoading} />
        <Kpi title="New Hires This Month" value={dashboard.data?.new_hires_this_month ?? 0} icon={UserPlus} className="bg-purple-50 text-purple-700" loading={dashboard.isLoading} />
        <Kpi title="Attrition Rate" value={`${attrition.toFixed(1)}%`} icon={BarChart3} className={attritionClass} loading={dashboard.isLoading} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Headcount by Department" query={headcount}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={headcount.data || []} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="department_name" type="category" width={120} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Attendance Trend" query={attendance}>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={(attendance.data || []).map((row: any) => ({ ...row, label: monthLabel(row.month) }))}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Area type="monotone" stackId="1" dataKey="present_days" stroke="#16a34a" fill="#16a34a" name="Present" />
              <Area type="monotone" stackId="1" dataKey="absent_days" stroke="hsl(var(--destructive))" fill="hsl(var(--destructive))" name="Absent" />
              <Area type="monotone" stackId="1" dataKey="wfh_days" stroke="#2563eb" fill="#2563eb" name="WFH" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Leave Trend" query={leave}>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={(leave.data || []).map((row: any) => ({ ...row, label: monthLabel(row.month) }))}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Line type="monotone" dataKey="approved_count" stroke="#16a34a" strokeWidth={2} name="Approved" />
              <Line type="monotone" dataKey="pending_count" stroke="#f59e0b" strokeWidth={2} name="Pending" />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Payroll Summary" query={payroll}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={(payroll.data || []).map((row: any) => ({ ...row, label: monthLabel(row.month) }))}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={(value) => money(value)} width={92} />
              <Tooltip contentStyle={tooltipStyle} formatter={(value) => money(value)} />
              <Legend />
              <Bar dataKey="gross_pay" fill="#2563eb" name="Gross Pay" />
              <Bar dataKey="total_deductions" fill="hsl(var(--destructive))" name="Deductions" />
              <Line type="monotone" dataKey="net_pay" stroke="#16a34a" strokeWidth={2} name="Net Pay" />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

function WorkforceAnalytics() {
  const turnover = useQuery({ queryKey: ["reports-turnover"], queryFn: () => reportsApi.turnover().then((r) => r.data), staleTime: STALE_TIME });
  const funnel = useQuery({ queryKey: ["reports-recruitment-funnel"], queryFn: () => reportsApi.recruitmentFunnel().then((r) => r.data), staleTime: STALE_TIME });
  const dei = useQuery({ queryKey: ["reports-dei-analytics"], queryFn: () => reportsApi.deiAnalytics().then((r) => r.data), staleTime: STALE_TIME });
  const genderColors: Record<string, string> = {
    Male: "hsl(221 83% 53%)",
    Female: "hsl(330 81% 60%)",
    Other: "hsl(280 65% 60%)",
    "Prefer Not to Say": "hsl(280 65% 60%)",
  };

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <ChartCard title="Employee Turnover" query={turnover}>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={(turnover.data || []).map((row: any) => ({ ...row, label: monthLabel(row.month) }))}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis />
            <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => `${v}%`} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend />
            <Line dataKey="joined" stroke="#16a34a" strokeWidth={2} name="Joined" />
            <Line dataKey="exited" stroke="hsl(var(--destructive))" strokeWidth={2} name="Exited" />
            <Line yAxisId="right" dataKey="attrition_rate" stroke="#f97316" strokeDasharray="4 4" strokeWidth={2} name="Attrition %" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Recruitment Funnel" query={funnel}>
        <ResponsiveContainer width="100%" height={280}>
          <FunnelChart>
            <Tooltip contentStyle={tooltipStyle} />
            <Funnel dataKey="count" data={funnel.data || []} nameKey="stage" fill="hsl(var(--primary))">
              <LabelList position="right" fill="hsl(var(--foreground))" dataKey="stage" />
            </Funnel>
          </FunnelChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Gender Distribution" query={dei}>
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Tooltip contentStyle={tooltipStyle} />
            <Legend />
            <Pie data={dei.data?.gender_distribution || []} dataKey="count" nameKey="label" outerRadius={92} label>
              {(dei.data?.gender_distribution || []).map((row: any) => (
                <Cell key={row.label} fill={genderColors[row.label] || "hsl(280 65% 60%)"} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Department Diversity" query={dei}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={dei.data?.department_diversity || []}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="department_name" tick={{ fontSize: 11 }} />
            <YAxis />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend />
            <Bar dataKey="Male" stackId="a" fill={genderColors.Male} />
            <Bar dataKey="Female" stackId="a" fill={genderColors.Female} />
            <Bar dataKey="Other" stackId="a" fill={genderColors.Other} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Avg Gross Pay by Gender" query={dei}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={dei.data?.avg_gross_by_gender || []}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => money(v)} width={92} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => money(value)} />
            <Bar dataKey="avg_gross_pay" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

function SavedReports() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<ReportDefinition | null>(null);
  const definitions = useQuery({ queryKey: ["report-definitions"], queryFn: () => reportsApi.definitions().then((r) => r.data as ReportDefinition[]), staleTime: STALE_TIME });
  const schedules = useQuery({ queryKey: ["report-schedules"], queryFn: () => reportsApi.schedules().then((r) => r.data as Array<{ id: number; name: string; status: string; cron_expression: string; last_run_at?: string }>), staleTime: STALE_TIME });
  const runSchedule = useMutation({
    mutationFn: (id: number) => reportsApi.runSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report-schedules"] }),
  });
  const result = useQuery({
    queryKey: ["report-definition-run", selected?.id],
    queryFn: () => reportsApi.runDefinition(selected!.id).then((r) => r.data as ReportResult),
    enabled: false,
  });

  const exportCsv = () => {
    if (!result.data) return;
    const escape = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const csv = [
      result.data.columns.map(escape).join(","),
      ...result.data.rows.map((row) => result.data!.columns.map((column) => escape(row[column])).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selected?.name || "report"}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader><CardTitle className="text-base">Saved Reports</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {definitions.isLoading && <div className="h-[280px] animate-pulse rounded bg-muted" />}
          {!definitions.isLoading && !definitions.data?.length && (
            <p className="rounded-lg border p-4 text-sm text-muted-foreground">No saved reports yet. Reports can be configured by your administrator.</p>
          )}
          {(definitions.data || []).map((definition) => (
            <button
              key={definition.id}
              type="button"
              onClick={() => setSelected(definition)}
              className={cn("w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/60", selected?.id === definition.id && "border-primary bg-primary/10")}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium">{definition.name}</p>
                <ModuleBadge module={definition.module || "custom"} />
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{definition.description || "No description"}</p>
            </button>
          ))}
          <div className="border-t pt-3">
            <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Schedules</p>
            {(schedules.data || []).map((schedule) => (
              <div key={schedule.id} className="mb-2 rounded-lg border p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium">{schedule.name}</p>
                  <Badge variant="secondary">{schedule.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{schedule.cron_expression}</p>
                <Button className="mt-2 h-7 text-xs" variant="outline" onClick={() => runSchedule.mutate(schedule.id)}>Run</Button>
              </div>
            ))}
            {!schedules.isLoading && !schedules.data?.length && <p className="text-xs text-muted-foreground">No scheduled exports configured.</p>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-base">{selected ? selected.name : "Report Output"}</CardTitle>
          {selected && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => result.refetch()} disabled={result.isFetching}>Run Report</Button>
              <Button size="sm" variant="outline" onClick={exportCsv} disabled={!result.data?.rows?.length}>
                <Download className="mr-2 h-4 w-4" /> Export CSV
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {!selected && <p className="py-16 text-center text-sm text-muted-foreground">Select a report from the left to run it</p>}
          {selected && result.isFetching && <div className="h-[280px] animate-pulse rounded bg-muted" />}
          {selected && result.isError && <p className="py-10 text-center text-sm text-muted-foreground">Could not load data</p>}
          {selected && result.data && (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="bg-muted/60">
                  <tr>{result.data.columns.map((column) => <th key={column} className="px-3 py-2 text-left font-medium">{column}</th>)}</tr>
                </thead>
                <tbody>
                  {result.data.rows.map((row, index) => (
                    <tr key={index} className="border-t">
                      {result.data!.columns.map((column) => <td key={column} className="px-3 py-2">{String(row[column] ?? "")}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Kpi({ title, value, icon: Icon, className, loading }: { title: string; value: unknown; icon: any; className: string; loading: boolean }) {
  const displayValue: string | number =
    typeof value === "string" || typeof value === "number"
      ? value
      : Array.isArray(value)
        ? value.length
        : value && typeof value === "object"
          ? JSON.stringify(value)
          : value == null
            ? 0
            : String(value);

  return (
    <Card>
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          {loading ? <div className="mt-2 h-8 w-20 animate-pulse rounded bg-muted" /> : <p className="mt-2 text-2xl font-semibold">{displayValue}</p>}
        </div>
        <div className={cn("rounded-lg p-3", className)}><Icon className="h-5 w-5" /></div>
      </CardContent>
    </Card>
  );
}

function ChartCard({ title, query, children }: { title: string; query: { isLoading: boolean; isError: boolean }; children: ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        {query.isLoading ? <div className="h-[280px] animate-pulse rounded bg-muted" /> : query.isError ? (
          <p className="py-10 text-center text-sm text-muted-foreground">Could not load data</p>
        ) : children}
      </CardContent>
    </Card>
  );
}

function ModuleBadge({ module }: { module: string }) {
  const colors: Record<string, string> = {
    payroll: "bg-purple-100 text-purple-800",
    employee: "bg-blue-100 text-blue-800",
    attendance: "bg-orange-100 text-orange-800",
    leave: "bg-green-100 text-green-800",
    recruitment: "bg-pink-100 text-pink-800",
  };
  return <Badge className={cn("border-0", colors[module] || "bg-muted text-muted-foreground")}>{module}</Badge>;
}
