import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  Users, Clock, CalendarDays, Briefcase, TrendingUp, TrendingDown,
  CheckCircle2, AlertCircle, Building2, DollarSign, ShieldCheck, Target,
  FileText, HelpCircle, Award, UserCheck, ArrowRight, BarChart3, Sparkles
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { attendanceApi, documentsApi, employeeApi, engagementApi, leaveApi, payrollApi, reportsApi } from "@/services/api";
import { formatCurrency } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey, getRoleLabel } from "@/lib/roles";
import { usePageTitle } from "@/hooks/use-page-title";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";

const COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"];

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = "blue",
  href,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: { value: number; label: string };
  color?: string;
  href?: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
    green: "bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400",
    yellow: "bg-yellow-50 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400",
    red: "bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400",
    purple: "bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400",
  };

  const content = (
    <Card className="stat-card">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold tracking-tight">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
            {trend && (
              <div className="flex items-center gap-1 text-xs">
                {trend.value >= 0 ? (
                  <TrendingUp className="h-3 w-3 text-green-500" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-500" />
                )}
                <span className={trend.value >= 0 ? "text-green-600" : "text-red-600"}>
                  {Math.abs(trend.value)}% {trend.label}
                </span>
              </div>
            )}
          </div>
          <div className={`rounded-xl p-3 ${colorMap[color]}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
  return href ? <Link to={href} className="block transition-transform hover:-translate-y-1">{content}</Link> : content;
}

function SkeletonCard() {
  return (
    <Card className="stat-card">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <div className="h-4 w-24 skeleton rounded" />
            <div className="h-8 w-16 skeleton rounded" />
            <div className="h-3 w-20 skeleton rounded" />
          </div>
          <div className="h-12 w-12 skeleton rounded-xl" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  usePageTitle("Dashboard");
  const { user } = useAuthStore();
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ["hrms", "dashboard"],
    queryFn: () => reportsApi.dashboard().then((r) => r.data),
    refetchInterval: 5 * 60 * 1000,
  });

  const { data: headcount, isLoading: loadingHeadcount } = useQuery({
    queryKey: ["dashboard-headcount"],
    queryFn: () => employeeApi.count().then((r) => r.data),
  });

  const { data: pendingLeave } = useQuery({
    queryKey: ["dashboard-pending-leave"],
    queryFn: () => leaveApi.pendingCount().then((r) => r.data),
    retry: false,
  });

  const { data: lastRun } = useQuery({
    queryKey: ["dashboard-last-payroll-run"],
    queryFn: () => payrollApi.lastRun().then((r) => r.data),
    retry: false,
  });

  const { data: todaySummary } = useQuery({
    queryKey: ["dashboard-attendance-today-summary"],
    queryFn: () => attendanceApi.todaySummary().then((r) => r.data),
    retry: false,
  });

  const { data: leaveBalances } = useQuery({
    queryKey: ["dashboard-leave-balances"],
    queryFn: () => leaveApi.balance(currentYear).then((r) => r.data),
    retry: false,
  });

  const { data: certificates } = useQuery({
    queryKey: ["dashboard-certificates"],
    queryFn: () => documentsApi.certificates().then((r) => r.data),
    retry: false,
  });

  const { data: recognitions } = useQuery({
    queryKey: ["dashboard-recognitions"],
    queryFn: () => engagementApi.recognitions().then((r) => r.data),
    retry: false,
  });

  const { data: deptData } = useQuery({
    queryKey: ["headcount-by-dept"],
    queryFn: () => reportsApi.headcountByDept().then((r) => r.data),
  });

  const { data: payrollData } = useQuery({
    queryKey: ["payroll-summary", currentYear],
    queryFn: () => reportsApi.payrollSummary(currentYear).then((r) => r.data),
  });

  const employeeActions = [
    { label: "Check Attendance", detail: "Clock in, clock out, regularize", icon: Clock, href: "/hrms/attendance" },
    { label: "Apply Leave", detail: "Balances and leave requests", icon: CalendarDays, href: "/hrms/leave" },
    { label: "Download Payslip", detail: "Monthly salary slip", icon: DollarSign, href: "/hrms/payroll" },
    { label: "Raise Ticket", detail: "HR helpdesk support", icon: HelpCircle, href: "/hrms/helpdesk" },
  ];

  const managerActions = [
    { label: "Leave Approvals", detail: `${pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0} requests pending`, icon: CalendarDays, href: "/hrms/leave" },
    { label: "Team Performance", detail: "Goals, reviews, feedback", icon: Target, href: "/hrms/performance" },
    { label: "Team Attendance", detail: "Monthly presence trends", icon: Clock, href: "/hrms/attendance" },
    { label: "Open Helpdesk", detail: "Resolve employee issues", icon: HelpCircle, href: "/hrms/helpdesk" },
  ];

  const ceoMetrics = [
    { label: "Active Workforce", value: headcount?.active ?? dashboard?.headcount?.active ?? 0, icon: Users, tone: "text-blue-600" },
    { label: "Last Payroll", value: lastRun ? `${String(lastRun.month).padStart(2, "0")}/${lastRun.year}` : "No run", icon: DollarSign, tone: "text-emerald-600" },
    { label: "Open Roles", value: dashboard?.recruitment?.open_positions ?? 0, icon: Briefcase, tone: "text-violet-600" },
    { label: "Pending Decisions", value: pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0, icon: ShieldCheck, tone: "text-amber-600" },
  ];
  const totalLeaveBalance = (leaveBalances || []).reduce(
    (sum: number, row: { available?: number | string; balance?: number | string }) =>
      sum + Number(row.available ?? row.balance ?? 0),
    0
  );
  const totalEmployees = headcount?.total ?? dashboard?.headcount?.total ?? 0;
  const activeEmployees = headcount?.active ?? dashboard?.headcount?.active ?? 0;
  const presentToday = todaySummary?.present ?? dashboard?.attendance?.present_today ?? 0;
  const absentToday = todaySummary?.absent ?? dashboard?.attendance?.absent_today ?? 0;
  const attendanceBase = presentToday + absentToday;
  const attendanceRate = attendanceBase ? Math.round((presentToday / attendanceBase) * 100) : 0;
  const pendingApprovals = pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0;
  const payrollGrossYtd = (payrollData || []).reduce((sum: number, row: { gross?: number | string }) => sum + Number(row.gross ?? 0), 0);
  const payrollNetYtd = (payrollData || []).reduce((sum: number, row: { net?: number | string }) => sum + Number(row.net ?? 0), 0);
  const departmentCount = deptData?.length ?? 0;
  const certificateCount = certificates?.length ?? 0;
  const recognitionCount = recognitions?.length ?? 0;

  if (roleKey === "employee") {
    return (
      <div className="space-y-5">
        <div className="rounded-lg border bg-card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{roleLabel}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">My HR workspace</h1>
          <p className="mt-1 text-sm text-muted-foreground">Attendance, leave, payslips, documents, and support in one place.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {employeeActions.map((item) => (
            <Link key={item.label} to={item.href} className="group rounded-lg border bg-card p-4 shadow-sm transition hover:border-primary/50 hover:shadow-md">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <item.icon className="h-5 w-5" />
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-1 group-hover:text-primary" />
              </div>
              <p className="mt-4 font-medium">{item.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>
            </Link>
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">My Week</CardTitle>
              <CardDescription>Quick personal summary</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              {[
                ["Present", todaySummary?.present ?? dashboard?.attendance?.present_today ?? 0, UserCheck],
                ["Leave Balance", totalLeaveBalance, CalendarDays],
                ["Certificates", certificates?.length ?? 0, FileText],
              ].map(([label, value, Icon]) => (
                <div key={label as string} className="rounded-lg border p-4">
                  <Icon className="mb-3 h-5 w-5 text-primary" />
                  <p className="text-xl font-semibold">{value as string}</p>
                  <p className="text-xs text-muted-foreground">{label as string}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recognition</CardTitle>
              <CardDescription>Praise and culture moments</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(recognitions || []).slice(0, 3).map((item: { id: number; badge?: string; title?: string; to_employee_name?: string; points?: number }) => (
                <div key={item.id} className="flex items-center gap-3 rounded-lg border p-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                    <Award className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{item.badge || item.title || "Recognition"}</p>
                    <p className="text-xs text-muted-foreground">{item.to_employee_name || "Employee"}{item.points ? ` - ${item.points} points` : ""}</p>
                  </div>
                </div>
              ))}
              {!recognitions?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No public recognition activity yet.</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (roleKey === "manager") {
    return (
      <div className="space-y-5">
        <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{roleLabel}</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Team command center</h1>
            <p className="mt-1 text-sm text-muted-foreground">Approvals, team attendance, goals, and employee issues.</p>
          </div>
          <Badge variant="outline">{pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0} approvals pending</Badge>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {managerActions.map((item) => (
            <Link key={item.label} to={item.href} className="rounded-lg border bg-card p-4 shadow-sm transition hover:border-primary/50 hover:shadow-md">
              <item.icon className="mb-4 h-5 w-5 text-primary" />
              <p className="font-medium">{item.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>
            </Link>
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Headcount by Department</CardTitle>
              <CardDescription>Team distribution and capacity</CardDescription>
            </CardHeader>
          <CardContent>
            {deptData?.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={deptData || []} margin={{ top: 0, right: 0, left: -10, bottom: 28 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="department" tick={{ fontSize: 11 }} angle={-35} textAnchor="end" tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <ChartEmptyState label="Department headcount will appear here once employees are assigned." />
            )}
          </CardContent>
        </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Team Snapshot</CardTitle>
              <CardDescription>Operational highlights for managers</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border p-4">
                <p className="text-2xl font-semibold">{headcount?.active ?? dashboard?.headcount?.active ?? 0}</p>
                <p className="text-xs text-muted-foreground">Active team members</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-2xl font-semibold">{pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0}</p>
                <p className="text-xs text-muted-foreground">Approvals waiting</p>
              </div>
              <Link to="/hrms/leave" className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50">
                <span className="text-sm font-medium">Review leave queue</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </Link>
              <Link to="/hrms/attendance" className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50">
                <span className="text-sm font-medium">Check attendance trends</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (roleKey === "ceo") {
    return (
      <div className="space-y-5">
        <div className="rounded-lg border bg-card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{roleLabel}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Executive people dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">Workforce health, payroll exposure, hiring movement, and operating priorities.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {ceoMetrics.map((metric) => (
            <Card key={metric.label}>
              <CardContent className="p-5">
                <metric.icon className={`mb-4 h-5 w-5 ${metric.tone}`} />
                <p className="text-2xl font-semibold">{metric.value}</p>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{metric.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Payroll Trend</CardTitle>
              <CardDescription>Gross vs net salary comparison</CardDescription>
            </CardHeader>
          <CardContent>
            {payrollData?.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={payrollData || []} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="month" tickFormatter={(m) => new Date(currentYear, m - 1).toLocaleString("en", { month: "short" })} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => `INR ${(v / 1000).toFixed(0)}K`} />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                  <Legend />
                  <Bar dataKey="gross" name="Gross" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="net" name="Net" fill="#059669" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <ChartEmptyState label="Payroll history will appear after the first completed run." />
            )}
          </CardContent>
        </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Board Pack</CardTitle>
              <CardDescription>High-signal HR views</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                ["Reports & Analytics", "/hrms/reports", BarChart3],
                ["Company Setup", "/hrms/company", Building2],
                ["AI Workforce Notes", "/hrms/ai-assistant", Sparkles],
              ].map(([label, href, Icon]) => (
                <Link key={label as string} to={href as string} className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50">
                  <span className="flex items-center gap-3 text-sm font-medium">
                    <Icon className="h-4 w-4 text-primary" />
                    {label as string}
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-description">
          Welcome back! Here's your HR overview for today.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading || loadingHeadcount ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              title="Total Employees"
              value={headcount?.total ?? dashboard?.headcount?.total ?? 0}
              subtitle={`${headcount?.active ?? dashboard?.headcount?.active ?? 0} active`}
              icon={Users}
              color="blue"
              href="/hrms/employees"
            />
            <StatCard
              title="Present Today"
              value={todaySummary?.present ?? dashboard?.attendance?.present_today ?? 0}
              subtitle={`${todaySummary?.absent ?? dashboard?.attendance?.absent_today ?? 0} absent`}
              icon={Clock}
              color="green"
              href="/hrms/attendance"
            />
            <StatCard
              title="Pending Leaves"
              value={pendingLeave?.pending ?? dashboard?.leaves?.pending_approvals ?? 0}
              subtitle="Awaiting approval"
              icon={CalendarDays}
              color="yellow"
              href="/hrms/leave"
            />
            <StatCard
              title="Last Payroll"
              value={lastRun ? `${String(lastRun.month).padStart(2, "0")}/${lastRun.year}` : "No run"}
              subtitle={lastRun ? `${lastRun.status} payroll` : "Awaiting first run"}
              icon={DollarSign}
              color="purple"
              href="/hrms/payroll"
            />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Headcount by Department */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Headcount by Department</CardTitle>
            <CardDescription>Employee distribution across departments</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={deptData || []} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis
                  dataKey="department"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Payroll trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Monthly Payroll ({currentYear})</CardTitle>
            <CardDescription>Gross vs net salary comparison</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart
                data={payrollData || []}
                margin={{ top: 0, right: 0, left: -10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m) =>
                    new Date(currentYear, m - 1).toLocaleString("en", { month: "short" })
                  }
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `INR ${(v / 1000).toFixed(0)}K`}
                />
                <Tooltip
                  formatter={(v: number) => formatCurrency(v)}
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <Legend />
                <Bar dataKey="gross" name="Gross" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="net" name="Net" fill="#10B981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Add Employee", icon: Users, href: "/hrms/employees/new", color: "bg-blue-600 hover:bg-blue-700" },
          { label: "Run Payroll", icon: DollarSign, href: "/hrms/payroll", color: "bg-green-600 hover:bg-green-700" },
          { label: "Leave Approvals", icon: CalendarDays, href: "/hrms/leave", color: "bg-yellow-600 hover:bg-yellow-700" },
          { label: "View Reports", icon: TrendingUp, href: "/hrms/reports", color: "bg-purple-600 hover:bg-purple-700" },
        ].map((action) => (
          <a
            key={action.label}
            href={action.href}
            className={`flex flex-col items-center gap-2 p-4 rounded-xl text-white text-sm font-medium transition-transform hover:scale-105 ${action.color}`}
          >
            <action.icon className="h-6 w-6" />
            {action.label}
          </a>
        ))}
      </div>

      <DashboardStatistics
        totalEmployees={totalEmployees}
        activeEmployees={activeEmployees}
        presentToday={presentToday}
        absentToday={absentToday}
        attendanceRate={attendanceRate}
        pendingApprovals={pendingApprovals}
        leaveBalance={totalLeaveBalance}
        payrollGrossYtd={payrollGrossYtd}
        payrollNetYtd={payrollNetYtd}
        departmentCount={departmentCount}
        certificateCount={certificateCount}
        recognitionCount={recognitionCount}
        lastPayroll={lastRun ? `${String(lastRun.month).padStart(2, "0")}/${lastRun.year}` : "No run"}
      />
    </div>
  );
}

function DashboardStatistics({
  totalEmployees,
  activeEmployees,
  presentToday,
  absentToday,
  attendanceRate,
  pendingApprovals,
  leaveBalance,
  payrollGrossYtd,
  payrollNetYtd,
  departmentCount,
  certificateCount,
  recognitionCount,
  lastPayroll,
}: {
  totalEmployees: number;
  activeEmployees: number;
  presentToday: number;
  absentToday: number;
  attendanceRate: number;
  pendingApprovals: number;
  leaveBalance: number;
  payrollGrossYtd: number;
  payrollNetYtd: number;
  departmentCount: number;
  certificateCount: number;
  recognitionCount: number;
  lastPayroll: string;
}) {
  const workforceRows = [
    { label: "Active employees", value: activeEmployees, max: Math.max(totalEmployees, 1), tone: "bg-blue-500" },
    { label: "Present today", value: presentToday, max: Math.max(presentToday + absentToday, 1), tone: "bg-emerald-500" },
    { label: "Absent today", value: absentToday, max: Math.max(presentToday + absentToday, 1), tone: "bg-red-500" },
    { label: "Pending approvals", value: pendingApprovals, max: Math.max(pendingApprovals + presentToday, 1), tone: "bg-amber-500" },
  ];
  const cards = [
    { label: "Attendance rate", value: `${attendanceRate}%`, detail: `${presentToday} present / ${absentToday} absent`, Icon: CheckCircle2 },
    { label: "Leave liability", value: leaveBalance, detail: "Available leave days across current balances", Icon: CalendarDays },
    { label: "Payroll YTD", value: formatCurrency(payrollNetYtd), detail: `${formatCurrency(payrollGrossYtd)} gross`, Icon: DollarSign },
    { label: "Last payroll", value: lastPayroll, detail: "Most recent payroll run", Icon: Briefcase },
  ];
  const operatingRows = [
    { label: "Departments", value: departmentCount, note: "Active workforce groups" },
    { label: "Certificates", value: certificateCount, note: "Employee documents tracked" },
    { label: "Recognitions", value: recognitionCount, note: "Culture moments recorded" },
  ];

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Dashboard Statistics</h2>
        <p className="text-sm text-muted-foreground">Live HRMS indicators calculated from workforce, attendance, leave, payroll, and document data.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map(({ label, value, detail, Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="rounded-lg bg-blue-500/10 p-2 text-blue-700">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-2xl font-semibold">{value}</p>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{detail}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Workforce pulse</CardTitle>
            <CardDescription>Operational counts for today</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workforceRows.map((row) => {
              const width = row.value > 0 ? Math.max(6, Math.round((row.value / row.max) * 100)) : 0;
              return (
                <div key={row.label} className="space-y-2">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium">{row.label}</span>
                    <span className="text-muted-foreground">{row.value}</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                    <div className={`h-full rounded-full ${row.tone}`} style={{ width: `${width}%` }} />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>HR operations</CardTitle>
            <CardDescription>Coverage and governance signals</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {operatingRows.map((row) => (
              <div key={row.label} className="rounded-md border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{row.label}</span>
                  <span className="text-lg font-semibold">{row.value}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{row.note}</p>
              </div>
            ))}
            {pendingApprovals > 0 ? (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <AlertCircle className="h-4 w-4" />
                {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"} need review.
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function ChartEmptyState({ label }: { label: string }) {
  return (
    <div className="flex h-[250px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 text-center">
      <BarChart3 className="mb-3 h-8 w-8 text-muted-foreground/50" />
      <p className="text-sm font-medium">No data yet</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
