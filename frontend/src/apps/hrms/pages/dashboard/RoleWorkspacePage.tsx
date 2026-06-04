import { Link } from "react-router-dom";
import type { ElementType } from "react";
import {
  BarChart3,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardCheck,
  Clock,
  DollarSign,
  FileCheck2,
  FileText,
  Gauge,
  GitBranch,
  HelpCircle,
  Landmark,
  LayoutDashboard,
  Megaphone,
  Network,
  Package,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  UserRound,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/use-page-title";
import { useAuthStore } from "@/store/authStore";
import { getRoleKey, getRoleLabel, type RoleKey } from "@/lib/roles";
import { cn } from "@/lib/utils";

type WorkspaceAction = {
  label: string;
  description: string;
  href: string;
  icon: ElementType;
  badge?: string;
};

type WorkspaceConfig = {
  title: string;
  subtitle: string;
  primaryAction: WorkspaceAction;
  stats: Array<{ label: string; value: string; tone: string }>;
  sections: Array<{ title: string; items: WorkspaceAction[] }>;
};

const workspaceConfig: Record<RoleKey, WorkspaceConfig> = {
  admin: {
    title: "Admin Home",
    subtitle: "Configure the HRMS platform, security, workflows, organization data, and enterprise controls.",
    primaryAction: { label: "Open System Settings", description: "Company defaults, access, and HRMS configuration", href: "/hrms/settings", icon: Settings },
    stats: [
      { label: "Access Control", value: "RBAC", tone: "bg-slate-900 text-white" },
      { label: "Audit Trail", value: "Logs", tone: "bg-blue-50 text-blue-700" },
      { label: "Platform", value: "Ready", tone: "bg-emerald-50 text-emerald-700" },
    ],
    sections: [
      {
        title: "Platform Setup",
        items: [
          { label: "Company Settings", description: "Company profile, org defaults, fiscal and payroll settings", href: "/hrms/company", icon: Building2 },
          { label: "Workflows", description: "Approval chains, inbox rules, escalations, and designer", href: "/hrms/workflow-designer", icon: GitBranch },
          { label: "Custom Fields", description: "Extend employee and HR records without code changes", href: "/hrms/custom-fields", icon: SlidersHorizontal },
          { label: "Enterprise Controls", description: "Tenant, security, integration, and governance controls", href: "/hrms/enterprise", icon: Network },
        ],
      },
      {
        title: "Security & Monitoring",
        items: [
          { label: "Audit Logs", description: "Track admin actions and sensitive HRMS activity", href: "/hrms/logs", icon: FileText },
          { label: "AI Permissions", description: "Control AI agent access to HRMS data and actions", href: "/ai-agents/security/permissions", icon: ShieldCheck, badge: "AI" },
          { label: "WhatsApp ESS", description: "Employee self-service channel configuration", href: "/hrms/whatsapp-ess", icon: Megaphone },
        ],
      },
    ],
  },
  hr: {
    title: "HR Home",
    subtitle: "Run everyday HR operations across hiring, employee lifecycle, attendance, payroll, and compliance.",
    primaryAction: { label: "Open Employee Operations", description: "Employee records, onboarding, probation, and lifecycle work", href: "/hrms/employees", icon: Users },
    stats: [
      { label: "Lifecycle", value: "Hire to Exit", tone: "bg-indigo-50 text-indigo-700" },
      { label: "Payroll", value: "Monthly", tone: "bg-emerald-50 text-emerald-700" },
      { label: "Compliance", value: "India", tone: "bg-amber-50 text-amber-700" },
    ],
    sections: [
      {
        title: "Core HR",
        items: [
          { label: "Employees", description: "Profiles, org assignment, salary info, and lifecycle state", href: "/hrms/employees", icon: Users },
          { label: "Onboarding", description: "Templates, joining checklists, and task completion", href: "/hrms/onboarding", icon: ClipboardCheck },
          { label: "Attendance", description: "Punches, summaries, shifts, holidays, and regularization", href: "/hrms/attendance", icon: Clock },
          { label: "Shift Roster", description: "Assign shifts, weekly offs, and publish rosters", href: "/hrms/attendance/shift-roster", icon: CalendarDays },
          { label: "Leave", description: "Balances, requests, team calendars, and approvals", href: "/hrms/leave", icon: CalendarDays },
        ],
      },
      {
        title: "Talent & Pay",
        items: [
          { label: "Recruitment", description: "Jobs, candidates, interviews, offers, and ATS pipeline", href: "/hrms/recruitment", icon: Briefcase },
          { label: "Payroll", description: "Salary setup, payroll runs, payslips, tax, and statutory work", href: "/hrms/payroll", icon: DollarSign },
          { label: "Performance", description: "Cycles, goals, reviews, ratings, and appraisal history", href: "/hrms/performance", icon: Target },
          { label: "Reports", description: "Headcount, attendance, leave, payroll, and attrition outputs", href: "/hrms/reports", icon: BarChart3 },
        ],
      },
      {
        title: "Employee Services",
        items: [
          { label: "Documents", description: "Letters, templates, certificates, and employee files", href: "/hrms/documents", icon: FileText },
          { label: "Assets", description: "Asset issue, return, condition, and custody tracking", href: "/hrms/assets", icon: Package },
          { label: "Helpdesk", description: "HR tickets, SLA, assignments, and resolutions", href: "/hrms/helpdesk", icon: HelpCircle },
          { label: "Exit", description: "Resignation, clearance, interviews, and offboarding", href: "/hrms/exit", icon: UserRound },
        ],
      },
    ],
  },
  manager: {
    title: "Manager Workspace",
    subtitle: "Approve requests, track team attendance, manage goals, and keep coverage visible.",
    primaryAction: { label: "Open Manager Hub", description: "Team calendar, approvals, pending work, and direct reports", href: "/hrms/manager-dashboard", icon: LayoutDashboard },
    stats: [
      { label: "Scope", value: "Team", tone: "bg-blue-50 text-blue-700" },
      { label: "Approvals", value: "Live", tone: "bg-amber-50 text-amber-700" },
      { label: "Reviews", value: "Active", tone: "bg-violet-50 text-violet-700" },
    ],
    sections: [
      {
        title: "Team Operations",
        items: [
          { label: "Manager Hub", description: "Coverage, birthdays, reports, and team snapshots", href: "/hrms/manager-dashboard", icon: LayoutDashboard },
          { label: "Leave Approvals", description: "Approve leave, view team leave calendar, and coverage", href: "/hrms/leave", icon: CalendarDays },
          { label: "Attendance", description: "Review team attendance and regularization requests", href: "/hrms/attendance", icon: Clock },
          { label: "Shift Roster", description: "Review roster coverage and published shifts", href: "/hrms/attendance/shift-roster", icon: CalendarDays },
          { label: "Assets", description: "View assets issued to team members", href: "/hrms/assets", icon: Package },
        ],
      },
      {
        title: "People Growth",
        items: [
          { label: "Performance", description: "Goals, manager reviews, feedback, and appraisal actions", href: "/hrms/performance", icon: Target },
          { label: "Recruitment", description: "Open roles, candidates, interview feedback, and offers", href: "/hrms/recruitment", icon: Briefcase },
          { label: "Reports", description: "Team attendance, leave, payroll visibility, and workforce reports", href: "/hrms/reports", icon: BarChart3 },
        ],
      },
    ],
  },
  employee: {
    title: "Employee Self Service",
    subtitle: "View your profile, attendance, leave, payslips, documents, and HR requests.",
    primaryAction: { label: "Open ESS Portal", description: "Your profile, leave, documents, payslips, and requests", href: "/hrms/ess", icon: UserRound },
    stats: [
      { label: "Attendance", value: "Punch", tone: "bg-blue-50 text-blue-700" },
      { label: "Leave", value: "Apply", tone: "bg-emerald-50 text-emerald-700" },
      { label: "Pay", value: "Payslip", tone: "bg-amber-50 text-amber-700" },
    ],
    sections: [
      {
        title: "Self Service",
        items: [
          { label: "My Attendance", description: "View your attendance, hours, overtime, and monthly summary", href: "/hrms/my-attendance", icon: Clock },
          { label: "Leave", description: "Apply leave, check balances, and view team calendar", href: "/hrms/leave", icon: CalendarDays },
          { label: "Profile", description: "Personal, job, bank, tax, and emergency information", href: "/hrms/profile", icon: UserRound },
          { label: "My Requests", description: "Track leave, attendance, document, and HR requests", href: "/hrms/workflow", icon: HelpCircle },
        ],
      },
      {
        title: "Pay And Documents",
        items: [
          { label: "My Payslips", description: "View published payslips, component lines, YTD, and PDF download", href: "/hrms/my-payslips", icon: DollarSign },
          { label: "Documents", description: "Letters, certificates, policy docs, and employee files", href: "/hrms/documents", icon: FileText },
          { label: "My Roster", description: "View assigned shifts and weekly offs", href: "/hrms/my-roster", icon: CalendarDays },
        ],
      },
    ],
  },
  ceo: {
    title: "Executive Home",
    subtitle: "See workforce health, payroll cost, hiring pipeline, performance, compliance, and analytics.",
    primaryAction: { label: "Open Advanced Analytics", description: "Leadership KPIs, trends, risks, and AI insights", href: "/hrms/advanced-analytics", icon: Gauge },
    stats: [
      { label: "Workforce", value: "360", tone: "bg-slate-900 text-white" },
      { label: "Cost", value: "Payroll", tone: "bg-emerald-50 text-emerald-700" },
      { label: "Insights", value: "AI", tone: "bg-violet-50 text-violet-700" },
    ],
    sections: [
      {
        title: "Leadership View",
        items: [
          { label: "Reports", description: "Headcount, attrition, salary, leave, attendance, and hiring reports", href: "/hrms/reports", icon: BarChart3 },
          { label: "Advanced Analytics", description: "Executive trends, predictive signals, and workforce insights", href: "/hrms/advanced-analytics", icon: Gauge, badge: "AI" },
          { label: "Payroll Cost", description: "Salary register, budget vs actual, arrears, and cost trends", href: "/hrms/payroll", icon: DollarSign },
          { label: "Org Chart", description: "Organization structure, reporting lines, and spans of control", href: "/hrms/org-chart", icon: GitBranch },
        ],
      },
      {
        title: "Strategic People Areas",
        items: [
          { label: "Employees", description: "Workforce records, movement, probation, and lifecycle data", href: "/hrms/employees", icon: Users },
          { label: "Performance", description: "Cycle outcomes, ratings, goals, and review completion", href: "/hrms/performance", icon: Target },
          { label: "Company", description: "Legal profile, fiscal defaults, working days, and HR settings", href: "/hrms/company", icon: Building2 },
          { label: "AI Assistant", description: "Ask HRMS questions across workforce and operations", href: "/hrms/ai-assistant", icon: Sparkles, badge: "AI" },
        ],
      },
    ],
  },
};

export default function RoleWorkspacePage() {
  const user = useAuthStore((state) => state.user);
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const config = workspaceConfig[roleKey];
  const roleLabel = getRoleLabel(user?.role, user?.is_superuser);

  usePageTitle(config.title);

  return (
    <main className="space-y-6">
      <section className="rounded-lg border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <Badge variant="outline" className="w-fit">{roleLabel}</Badge>
            <div>
              <h1 className="text-2xl font-semibold tracking-normal text-foreground">{config.title}</h1>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{config.subtitle}</p>
            </div>
          </div>
          <Button asChild className="h-11 shrink-0">
            <Link to={config.primaryAction.href}>
              <config.primaryAction.icon className="mr-2 h-4 w-4" />
              {config.primaryAction.label}
            </Link>
          </Button>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {config.stats.map((stat) => (
            <div key={stat.label} className="rounded-md border bg-background p-4">
              <p className="text-xs font-medium uppercase text-muted-foreground">{stat.label}</p>
              <span className={cn("mt-3 inline-flex rounded-md px-2.5 py-1 text-sm font-semibold", stat.tone)}>{stat.value}</span>
            </div>
          ))}
        </div>
      </section>

      {config.sections.map((section) => (
        <section key={section.title} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">{section.title}</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {section.items.map((item) => (
              <Card key={item.href} className="transition-colors hover:border-primary/40">
                <CardHeader className="space-y-0 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-foreground">
                      <item.icon className="h-5 w-5" />
                    </div>
                    {item.badge && <Badge variant="secondary">{item.badge}</Badge>}
                  </div>
                  <CardTitle className="pt-4 text-base">{item.label}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="min-h-12 text-sm leading-6 text-muted-foreground">{item.description}</p>
                  <Button asChild variant="outline" size="sm">
                    <Link to={item.href}>Open</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
