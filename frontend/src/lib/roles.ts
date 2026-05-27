import {
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardCheck,
  Clock,
  Inbox,
  Timer,
  DollarSign,
  FileText,
  FileCheck2,
  GitBranch,
  GitMerge,
  Globe2,
  GraduationCap,
  Gauge,
  HelpCircle,
  HeartPulse,
  Landmark,
  LayoutDashboard,
  LogOut,
  Megaphone,
  MessageCircle,
  Network,
  Package,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Upload,
  UserRound,
  Users,
} from "lucide-react";
import { getInstalledAppKeys } from "@/appRegistry";

export type RoleKey = "admin" | "ceo" | "hr" | "manager" | "employee";

export type RoleNavItem = {
  label: string;
  icon: React.ElementType;
  to: string;
  badge?: string;
  group?: string;
  exact?: boolean;
};

export function getRoleKey(role?: string | null, isSuperuser = false): RoleKey {
  const value = (role || "").toLowerCase().replace(/\s+/g, "_");
  if (isSuperuser || ["super_admin", "admin"].includes(value)) return "admin";
  if (["hr_manager", "hr_admin", "hr"].includes(value)) return "hr";
  if (["ceo", "founder", "director", "executive"].includes(value)) return "ceo";
  if (["manager", "team_lead", "department_head"].includes(value)) return "manager";
  return "employee";
}

export function getRoleLabel(role?: string | null, isSuperuser = false) {
  const normalizedRole = normalizeRole(role);
  const crmLabels: Record<string, string> = {
    crm_super_admin: "CRM Super Admin",
    crm_org_admin: "CRM Admin",
    crm_sales_manager: "Sales Manager",
    crm_sales_executive: "Sales Executive",
    crm_support_agent: "Support Agent",
    crm_marketing_user: "Marketing User",
    crm_viewer: "CRM Viewer",
  };
  const projectLabels: Record<string, string> = {
    pms_super_admin: "PM Super Admin",
    pms_org_admin: "PM Admin",
    pms_project_manager: "Project Manager",
    pms_team_member: "Team Member",
    pms_client: "Client Portal",
    pms_viewer: "Project Viewer",
  };
  if (crmLabels[normalizedRole]) return crmLabels[normalizedRole];
  if (projectLabels[normalizedRole]) return projectLabels[normalizedRole];

  const key = getRoleKey(role, isSuperuser);
  const labels: Record<RoleKey, string> = {
    admin: "Admin Console",
    ceo: "CEO Console",
    hr: "HR Admin Console",
    manager: "Manager Workspace",
    employee: "Employee Self Service",
  };
  return labels[key];
}

function normalizeRole(role?: string | null) {
  return (role || "").toLowerCase().replace(/\s+/g, "_");
}

function isHrmsRole(role?: string | null, isSuperuser = false) {
  const value = normalizeRole(role);
  return isSuperuser || ["super_admin", "admin", "hr_manager", "hr_admin", "hr", "ceo", "founder", "director", "executive", "manager", "team_lead", "department_head", "employee"].includes(value);
}

function isCrmRole(role?: string | null) {
  return [
    "crm_super_admin",
    "crm_org_admin",
    "crm_sales_manager",
    "crm_sales_executive",
    "crm_support_agent",
    "crm_marketing_user",
    "crm_viewer",
  ].includes(normalizeRole(role));
}

function isProjectManagementRole(role?: string | null) {
  return [
    "pms_super_admin",
    "pms_org_admin",
    "pms_project_manager",
    "pms_team_member",
    "pms_client",
    "pms_viewer",
  ].includes(normalizeRole(role));
}

const hrNav: RoleNavItem[] = [
  { label: "HR Home", icon: LayoutDashboard, to: "/hr-home", group: "Core HR", exact: true },
  { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Probation", icon: Timer, to: "/probation", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Workflow Designer", icon: GitBranch, to: "/workflow-designer", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Timesheets", icon: Timer, to: "/timesheets", group: "Core HR" },
  { label: "Leave", icon: CalendarDays, to: "/leave", group: "Core HR" },
  { label: "Payroll", icon: DollarSign, to: "/payroll", group: "Payroll & Finance" },
  { label: "Investment Declaration", icon: FileCheck2, to: "/investment-declaration", group: "Payroll & Finance" },
  { label: "F&F Settlement", icon: FileText, to: "/fnf-settlements", group: "Payroll & Finance" },
  { label: "Benefits", icon: HeartPulse, to: "/benefits", group: "Payroll & Finance" },
  { label: "Recruitment", icon: Briefcase, to: "/recruitment", group: "Talent" },
  { label: "Performance", icon: Target, to: "/performance", group: "Talent" },
  { label: "LMS", icon: GraduationCap, to: "/lms", group: "Talent" },
  { label: "Engagement", icon: Megaphone, to: "/engagement", group: "Talent" },
  { label: "Statutory Compliance", icon: Landmark, to: "/statutory-compliance", group: "Compliance" },
  { label: "BGV", icon: ShieldCheck, to: "/background-verification", group: "Compliance" },
  { label: "Helpdesk", icon: HelpCircle, to: "/helpdesk", group: "Compliance" },
  { label: "Reports", icon: BarChart3, to: "/reports", group: "Platform" },
  { label: "Advanced Analytics", icon: Gauge, to: "/advanced-analytics", group: "Platform", badge: "AI" },
  { label: "Company", icon: Building2, to: "/company", group: "Platform" },
  { label: "Org Chart", icon: GitBranch, to: "/org-chart", group: "Platform" },
  { label: "Onboarding", icon: ClipboardCheck, to: "/onboarding", group: "Platform" },
  { label: "Documents", icon: FileText, to: "/documents", group: "Platform" },
  { label: "Assets", icon: Package, to: "/assets", group: "Platform" },
  { label: "Exit", icon: LogOut, to: "/exit", group: "Platform" },
  { label: "WhatsApp ESS", icon: MessageCircle, to: "/whatsapp-ess", group: "Platform" },
  { label: "Custom Fields", icon: SlidersHorizontal, to: "/custom-fields", group: "Platform" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Platform" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Platform" },
];

const adminNav: RoleNavItem[] = [
  { label: "Admin Home", icon: ShieldCheck, to: "/admin-home", group: "Core HR", exact: true },
  { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Workflow Designer", icon: GitBranch, to: "/workflow-designer", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Probation", icon: Timer, to: "/probation", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Timesheets", icon: Timer, to: "/timesheets", group: "Core HR" },
  { label: "Leave", icon: CalendarDays, to: "/leave", group: "Core HR" },
  { label: "Payroll", icon: DollarSign, to: "/payroll", group: "Payroll & Finance" },
  { label: "Investment Declaration", icon: FileCheck2, to: "/investment-declaration", group: "Payroll & Finance" },
  { label: "F&F Settlement", icon: FileText, to: "/fnf-settlements", group: "Payroll & Finance" },
  { label: "Benefits", icon: HeartPulse, to: "/benefits", group: "Payroll & Finance" },
  { label: "Recruitment", icon: Briefcase, to: "/recruitment", group: "Talent" },
  { label: "Performance", icon: Target, to: "/performance", group: "Talent" },
  { label: "LMS", icon: GraduationCap, to: "/lms", group: "Talent" },
  { label: "Engagement", icon: Megaphone, to: "/engagement", group: "Talent" },
  { label: "Statutory Compliance", icon: Landmark, to: "/statutory-compliance", group: "Compliance" },
  { label: "BGV", icon: ShieldCheck, to: "/background-verification", group: "Compliance" },
  { label: "Helpdesk", icon: HelpCircle, to: "/helpdesk", group: "Compliance" },
  { label: "Company", icon: Building2, to: "/company", group: "Platform" },
  { label: "Org Chart", icon: GitBranch, to: "/org-chart", group: "Platform" },
  { label: "Settings", icon: Settings, to: "/settings", group: "Platform" },
  { label: "Logs", icon: ScrollText, to: "/logs", group: "Platform" },
  { label: "WhatsApp ESS", icon: MessageCircle, to: "/whatsapp-ess", group: "Platform" },
  { label: "Custom Fields", icon: SlidersHorizontal, to: "/custom-fields", group: "Platform" },
  { label: "Enterprise", icon: Network, to: "/enterprise", group: "Platform" },
  { label: "Reports", icon: BarChart3, to: "/reports", group: "Platform" },
  { label: "Advanced Analytics", icon: Gauge, to: "/advanced-analytics", group: "Platform", badge: "AI" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Platform" },
  { label: "Onboarding", icon: ClipboardCheck, to: "/onboarding", group: "Platform" },
  { label: "Documents", icon: FileText, to: "/documents", group: "Platform" },
  { label: "Assets", icon: Package, to: "/assets", group: "Platform" },
  { label: "Exit", icon: LogOut, to: "/exit", group: "Platform" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Platform" },
];

const ceoNav: RoleNavItem[] = [
  { label: "Executive Home", icon: LayoutDashboard, to: "/executive-home", group: "Core HR", exact: true },
  { label: "Executive Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Reports", icon: BarChart3, to: "/reports", group: "Finance" },
  { label: "Advanced Analytics", icon: Gauge, to: "/advanced-analytics", group: "Finance", badge: "AI" },
  { label: "Payroll", icon: DollarSign, to: "/payroll", group: "Finance" },
  { label: "Investment Declaration", icon: FileCheck2, to: "/investment-declaration", group: "Finance" },
  { label: "F&F Settlement", icon: FileText, to: "/fnf-settlements", group: "Finance" },
  { label: "Benefits", icon: HeartPulse, to: "/benefits", group: "Finance" },
  { label: "Performance", icon: Target, to: "/performance", group: "Talent" },
  { label: "LMS", icon: GraduationCap, to: "/lms", group: "Talent" },
  { label: "Engagement", icon: Megaphone, to: "/engagement", group: "Talent" },
  { label: "Employees", icon: Users, to: "/employees", group: "Organisation" },
  { label: "Probation", icon: Timer, to: "/probation", group: "Organisation" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Organisation" },
  { label: "Company", icon: Building2, to: "/company", group: "Organisation" },
  { label: "Org Chart", icon: GitBranch, to: "/org-chart", group: "Organisation" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Insights" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Insights" },
];

const managerNav: RoleNavItem[] = [
  { label: "Team Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Manager Hub", icon: Users, to: "/manager-dashboard", group: "Core HR", exact: true },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Timesheets", icon: Timer, to: "/timesheets", group: "Core HR" },
  { label: "Leave Approvals", icon: CalendarDays, to: "/leave", group: "Core HR" },
  { label: "Recruitment", icon: Briefcase, to: "/recruitment", group: "Core HR" },
  { label: "Assets", icon: Package, to: "/assets", group: "Core HR" },
  { label: "Performance", icon: Target, to: "/performance", group: "Talent" },
  { label: "LMS", icon: GraduationCap, to: "/lms", group: "Talent" },
  { label: "Engagement", icon: Megaphone, to: "/engagement", group: "Talent" },
  { label: "Helpdesk", icon: HelpCircle, to: "/helpdesk", group: "Insights" },
  { label: "Reports", icon: BarChart3, to: "/reports", group: "Insights" },
  { label: "Advanced Analytics", icon: Gauge, to: "/advanced-analytics", group: "Insights", badge: "AI" },
  { label: "Org Chart", icon: GitBranch, to: "/org-chart", group: "Insights" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Insights" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Insights" },
];

const employeeNav: RoleNavItem[] = [
  { label: "My Home", icon: LayoutDashboard, to: "/dashboard", group: "Home", exact: true },
  { label: "ESS Portal", icon: UserRound, to: "/ess", group: "Home", exact: true },
  { label: "Employee Directory", icon: Users, to: "/employee-directory", group: "Home" },
  { label: "My Requests", icon: Inbox, to: "/workflow", group: "Home" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Home" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Daily" },
  { label: "Timesheets", icon: Timer, to: "/timesheets", group: "Daily" },
  { label: "Leave", icon: CalendarDays, to: "/leave", group: "Daily" },
  { label: "Payslip", icon: DollarSign, to: "/payroll", group: "My Pay" },
  { label: "Investment Declaration", icon: FileCheck2, to: "/investment-declaration", group: "My Pay" },
  { label: "Benefits", icon: HeartPulse, to: "/benefits", group: "My Pay" },
  { label: "My Assets", icon: Package, to: "/assets", group: "My Pay" },
  { label: "Reviews", icon: Target, to: "/performance", group: "Growth" },
  { label: "Learning", icon: GraduationCap, to: "/lms", group: "Growth" },
  { label: "Engagement", icon: Megaphone, to: "/engagement", group: "Growth" },
  { label: "Helpdesk", icon: HelpCircle, to: "/helpdesk", group: "Support" },
  { label: "Documents", icon: FileText, to: "/documents", group: "Support" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Support" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Support" },
];

const crmNav: RoleNavItem[] = [
  { label: "CRM Dashboard", icon: LayoutDashboard, to: "/crm", group: "CRM", exact: true },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", group: "AI Agents", badge: "AI" },
  { label: "Leads", icon: Users, to: "/crm/leads", group: "CRM" },
  { label: "Contacts", icon: UserRound, to: "/crm/contacts", group: "CRM" },
  { label: "Companies", icon: Building2, to: "/crm/companies", group: "CRM" },
  { label: "Deals", icon: DollarSign, to: "/crm/deals", group: "Sales" },
  { label: "Pipeline", icon: GitBranch, to: "/crm/pipeline", group: "Sales", badge: "Drag" },
  { label: "Lead-to-Cash", icon: GitBranch, to: "/crm/lead-to-cash", group: "Sales", badge: "Flow" },
  { label: "Forecasting", icon: BarChart3, to: "/crm/forecasting", group: "Sales", badge: "Quota" },
  { label: "Activities", icon: Clock, to: "/crm/activities", group: "Sales" },
  { label: "Tasks", icon: ClipboardCheck, to: "/crm/tasks", group: "Sales" },
  { label: "Calendar", icon: CalendarDays, to: "/crm/calendar", group: "Sales" },
  { label: "Calendar Integrations", icon: CalendarDays, to: "/crm/calendar-integrations", group: "Sales" },
  { label: "Campaigns", icon: Megaphone, to: "/crm/campaigns", group: "Growth" },
  { label: "Products", icon: Package, to: "/crm/products", group: "Growth" },
  { label: "Quotations", icon: FileText, to: "/crm/quotations", group: "Growth" },
  { label: "My Approvals", icon: FileCheck2, to: "/crm/my-approvals", group: "Growth" },
  { label: "Lead Scoring", icon: Gauge, to: "/crm/lead-scoring", group: "Growth" },
  { label: "Duplicates", icon: GitMerge, to: "/crm/duplicates", group: "Growth" },
  { label: "Territories", icon: Globe2, to: "/crm/territories", group: "Growth" },
  { label: "Tickets", icon: HelpCircle, to: "/crm/tickets", group: "Support" },
  { label: "Files", icon: FileText, to: "/crm/files", group: "Support" },
  { label: "Customer 360", icon: Users, to: "/crm/customer-360", group: "Support", badge: "360" },
  { label: "Reports", icon: BarChart3, to: "/crm/reports", group: "Insights" },
  { label: "Automation", icon: Sparkles, to: "/crm/automation", group: "Insights" },
  { label: "Import & Export", icon: Upload, to: "/crm/import-export", group: "Insights" },
  { label: "Custom Fields", icon: SlidersHorizontal, to: "/crm/settings", group: "Insights" },
  { label: "Approval Settings", icon: FileCheck2, to: "/crm/approval-settings", group: "Insights" },
  { label: "Webhooks", icon: MessageCircle, to: "/crm/webhooks", group: "Insights" },
  { label: "Feature Checklist", icon: ClipboardCheck, to: "/crm/feature-checklist", group: "Insights" },
  { label: "CRM Admin", icon: ShieldCheck, to: "/crm/admin", group: "Insights" },
];

const projectManagementNav: RoleNavItem[] = [
  { label: "PM Dashboard", icon: LayoutDashboard, to: "/pms", group: "Project Management", exact: true },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", group: "AI Agents", badge: "AI" },
  { label: "Command Center", icon: Globe2, to: "/pms/command-center", group: "Project Management", badge: "New" },
  { label: "Enterprise Engine", icon: ShieldCheck, to: "/pms/enterprise-engine", group: "Project Management", badge: "Pro" },
  { label: "Product Launch", icon: Package, to: "/pms/product-launch", group: "Project Management", badge: "Launch" },
  { label: "Dependency Management", icon: Network, to: "/pms/dependency-management", group: "Project Management", badge: "Path" },
  { label: "Resource Planning", icon: Users, to: "/pms/resource-planning", group: "Project Management", badge: "Load" },
  { label: "Agile Execution", icon: Timer, to: "/pms/agile-execution", group: "Project Management", badge: "Sprint" },
  { label: "Project Financials", icon: DollarSign, to: "/pms/project-financials", group: "Project Management", badge: "Cost" },
  { label: "Risk Register", icon: ShieldCheck, to: "/pms/risk-register", group: "Project Management", badge: "RAID" },
  { label: "Impact Work Hub", icon: Target, to: "/pms/work-hub", group: "Project Management", badge: "AI" },
  { label: "AI Planner", icon: Sparkles, to: "/pms/ai-planner", group: "Project Management" },
  { label: "Live Work", icon: Sparkles, to: "/pms/live", group: "Project Management", badge: "Realtime" },
  { label: "Software Delivery", icon: GitBranch, to: "/pms/software", group: "Project Management", badge: "Agile" },
  { label: "Backlog", icon: Inbox, to: "/pms/backlog", group: "Project Management", badge: "Drag" },
  { label: "Backlog Grooming", icon: ClipboardCheck, to: "/pms/backlog-grooming", group: "Project Management" },
  { label: "Issues", icon: ClipboardCheck, to: "/pms/issues", group: "Project Management" },
  { label: "Tasks", icon: ClipboardCheck, to: "/pms/tasks", group: "Project Management" },
  { label: "Issue Navigator", icon: Search, to: "/pms/navigator", group: "Project Management" },
  { label: "Issue Navigator Pro", icon: Search, to: "/pms/issue-navigator-pro", group: "Project Management" },
  { label: "Dashboards", icon: BarChart3, to: "/pms/dashboards", group: "Project Management" },
  { label: "Projects", icon: Target, to: "/pms/projects", group: "Project Management" },
  { label: "Kanban", icon: GitBranch, to: "/pms/projects", group: "Project Management" },
  { label: "Goals", icon: Target, to: "/pms/goals", group: "Project Planning" },
  { label: "Roadmap", icon: CalendarDays, to: "/pms/roadmap", group: "Project Planning" },
  { label: "Timeline Plus", icon: CalendarDays, to: "/pms/timeline-plus", group: "Project Planning", badge: "Deps" },
  { label: "Dependencies", icon: Network, to: "/pms/dependencies", group: "Project Planning" },
  { label: "Plans", icon: Network, to: "/pms/plans", group: "Project Planning", badge: "Scale" },
  { label: "Releases", icon: Package, to: "/pms/releases", group: "Project Planning" },
  { label: "Forms", icon: FileText, to: "/pms/forms", group: "Project Planning" },
  { label: "Templates", icon: ClipboardCheck, to: "/pms/templates", group: "Project Planning" },
  { label: "Calendar", icon: CalendarDays, to: "/pms/calendar", group: "Project Planning" },
  { label: "Gantt", icon: BarChart3, to: "/pms/gantt", group: "Project Planning" },
  { label: "Sprints", icon: Timer, to: "/pms/sprints", group: "Project Planning" },
  { label: "Sprint Lifecycle", icon: Timer, to: "/pms/sprint-lifecycle", group: "Project Planning" },
  { label: "Components", icon: Package, to: "/pms/components", group: "Project Admin" },
  { label: "Workflows", icon: GitBranch, to: "/pms/workflows", group: "Project Admin" },
  { label: "Blueprints", icon: GitBranch, to: "/pms/blueprints", group: "Project Admin" },
  { label: "Resource Utilization", icon: Users, to: "/pms/resource-utilization", group: "Project Admin" },
  { label: "Apps & Integrations", icon: Network, to: "/pms/apps", group: "Project Admin" },
  { label: "Teams Live", icon: Users, to: "/pms/teams-live", group: "Project Admin", badge: "Drag" },
  { label: "Files", icon: FileText, to: "/pms/files", group: "Project Collaboration" },
  { label: "Time Tracking", icon: Clock, to: "/pms/time-tracking", group: "Project Collaboration" },
  { label: "Reports", icon: BarChart3, to: "/pms/reports", group: "Project Collaboration" },
  { label: "Automation AI", icon: Sparkles, to: "/pms/automation", group: "Project Collaboration", badge: "AI" },
  { label: "Client Portal", icon: Users, to: "/pms/client-portal", group: "Project Collaboration" },
  { label: "PM Settings", icon: Settings, to: "/pms/settings", group: "Project Admin" },
  { label: "Security", icon: ShieldCheck, to: "/pms/security", group: "Project Admin" },
  { label: "PM Admin", icon: ShieldCheck, to: "/pms/admin", group: "Project Admin" },
];

const aiAgentsNav: RoleNavItem[] = [
  { label: "Dashboard", icon: Sparkles, to: "/ai-agents", group: "AI Agents", exact: true },
  { label: "Chat", icon: MessageCircle, to: "/ai-agents", group: "AI Agents" },
  { label: "Approvals", icon: FileCheck2, to: "/ai-agents/approvals", group: "AI Agents" },
  { label: "Analytics", icon: BarChart3, to: "/ai-agents/analytics", group: "AI Agents" },
  { label: "Usage", icon: Gauge, to: "/ai-agents/usage", group: "AI Agents" },
  { label: "Security", icon: ShieldCheck, to: "/ai-agents/security", group: "AI Agents" },
  { label: "Permissions", icon: SlidersHorizontal, to: "/ai-agents/security/permissions", group: "AI Agents" },
  { label: "Feedback", icon: HeartPulse, to: "/ai-agents/feedback", group: "AI Agents" },
  { label: "Handoff Notes", icon: Inbox, to: "/ai-agents/handoff", group: "AI Agents" },
  { label: "Configuration", icon: Settings, to: "/ai-agents/config", group: "AI Agents" },
  { label: "Logs", icon: ScrollText, to: "/ai-agents/logs", group: "AI Agents" },
  { label: "CRM", icon: Briefcase, to: "/crm", group: "Applications", exact: true },
  { label: "PMS", icon: Target, to: "/pms", group: "Applications", exact: true },
  { label: "HRMS", icon: Building2, to: "/hrms", group: "Applications", exact: true },
];

function withPrefix(items: RoleNavItem[], prefix: string) {
  return items.map((item) => ({
    ...item,
    to: item.to.startsWith("/ai-agents") ? item.to : `${prefix}${item.to}`,
  }));
}

export function getActiveModule(pathname: string) {
  if (pathname === "/" || pathname === "") return "suite";
  if (pathname.startsWith("/ai-agents")) return "ai_agents";
  if (pathname.startsWith("/crm")) return "crm";
  if (pathname.startsWith("/pms")) return "project_management";
  return "hrms";
}

function getHrmsNavForRole(key: RoleKey) {
  if (key === "admin") return adminNav;
  if (key === "ceo") return ceoNav;
  if (key === "manager") return managerNav;
  if (key === "employee") return employeeNav;
  return hrNav;
}

export function getRoleNav(role?: string | null, isSuperuser = false, pathname = window.location.pathname) {
  const installedApps = getInstalledAppKeys();
  const key = getRoleKey(role, isSuperuser);
  const activeModule = getActiveModule(pathname);

  if (activeModule === "crm") {
    return installedApps.includes("crm") && isCrmRole(role) ? crmNav : [];
  }

  if (activeModule === "project_management") {
    return installedApps.includes("project_management") && isProjectManagementRole(role) ? projectManagementNav : [];
  }

  if (activeModule === "ai_agents") {
    return aiAgentsNav;
  }

  if (activeModule === "suite") {
    const suiteNav: RoleNavItem[] = [];
    if (installedApps.includes("hrms") && isHrmsRole(role, isSuperuser)) {
      suiteNav.push({ label: "AI HRMS", icon: Building2, to: "/hrms", group: "Applications", exact: true });
    }
    if (installedApps.includes("crm") && isCrmRole(role)) {
      suiteNav.push({ label: "VyaparaCRM", icon: Briefcase, to: "/crm", group: "Applications", exact: true });
    }
    if (installedApps.includes("project_management") && isProjectManagementRole(role)) {
      suiteNav.push({ label: "KaryaFlow", icon: Target, to: "/pms", group: "Applications", exact: true });
    }
    suiteNav.push({ label: "AI Agents", icon: Sparkles, to: "/ai-agents", group: "Applications", badge: "AI", exact: true });
    return suiteNav;
  }

  return installedApps.includes("hrms") && isHrmsRole(role, isSuperuser) ? withPrefix(getHrmsNavForRole(key), "/hrms") : [];
}

const routeAccess: Record<string, RoleKey[]> = {
  "/role-home": ["admin", "ceo", "hr", "manager", "employee"],
  "/admin-home": ["admin"],
  "/hr-home": ["admin", "hr"],
  "/executive-home": ["admin", "ceo"],
  "/dashboard": ["admin", "ceo", "hr", "manager", "employee"],
  "/manager-dashboard": ["admin", "hr", "manager"],
  "/ess": ["admin", "ceo", "hr", "manager", "employee"],
  "/profile": ["admin", "ceo", "hr", "manager", "employee"],
  "/workflow": ["admin", "ceo", "hr", "manager", "employee"],
  "/workflow-designer": ["admin", "hr"],
  "/notifications": ["admin", "ceo", "hr", "manager", "employee"],
  "/attendance": ["admin", "hr", "manager", "employee"],
  "/timesheets": ["admin", "ceo", "hr", "manager", "employee"],
  "/leave": ["admin", "hr", "manager", "employee"],
  "/payroll": ["admin", "ceo", "hr", "employee"],
  "/investment-declaration": ["admin", "ceo", "hr", "employee"],
  "/fnf-settlements": ["admin", "ceo", "hr"],
  "/benefits": ["admin", "ceo", "hr", "employee"],
  "/performance": ["admin", "ceo", "hr", "manager", "employee"],
  "/lms": ["admin", "ceo", "hr", "manager", "employee"],
  "/statutory-compliance": ["admin", "ceo", "hr"],
  "/background-verification": ["admin", "hr"],
  "/whatsapp-ess": ["admin", "hr"],
  "/custom-fields": ["admin", "hr"],
  "/enterprise": ["admin"],
  "/engagement": ["admin", "ceo", "hr", "manager", "employee"],
  "/helpdesk": ["admin", "hr", "manager", "employee"],
  "/documents": ["admin", "hr", "employee"],
  "/employee-directory": ["admin", "ceo", "hr", "manager", "employee"],
  "/employees": ["admin", "ceo", "hr", "manager"],
  "/probation": ["admin", "ceo", "hr", "manager"],
  "/reports": ["admin", "ceo", "hr", "manager"],
  "/advanced-analytics": ["admin", "ceo", "hr", "manager"],
  "/logs": ["admin"],
  "/recruitment": ["admin", "hr", "manager"],
  "/company": ["admin", "ceo", "hr"],
  "/org-chart": ["admin", "ceo", "hr", "manager"],
  "/settings": ["admin"],
  "/assets": ["admin", "hr", "manager", "employee"],
  "/onboarding": ["admin", "hr"],
  "/exit": ["admin", "hr"],
  "/ai-assistant": ["admin", "ceo", "hr", "manager", "employee"],
  "/ai-agents": ["admin", "ceo", "hr", "manager", "employee"],
  "/crm": ["admin", "ceo", "hr", "manager"],
  "/pms": ["admin", "ceo", "hr", "manager", "employee"],
};

export function canAccessRoute(pathname: string, role?: string | null, isSuperuser = false) {
  if (pathname === "/") return true;
  if (pathname.startsWith("/ai-agents")) return true;
  if (pathname === "/hrms") return isHrmsRole(role, isSuperuser);
  if (pathname.startsWith("/crm")) return isCrmRole(role);
  if (pathname.startsWith("/pms")) return isProjectManagementRole(role);
  if (pathname.startsWith("/hrms/") && !isHrmsRole(role, isSuperuser)) return false;
  const normalizedPathname = pathname.startsWith("/hrms/")
    ? pathname.replace(/^\/hrms/, "")
    : pathname;
  const key = getRoleKey(role, isSuperuser);
  const match = Object.keys(routeAccess)
    .sort((a, b) => b.length - a.length)
    .find((path) => normalizedPathname === path || normalizedPathname.startsWith(`${path}/`));
  if (!match) return key === "admin" || isSuperuser;
  return routeAccess[match].includes(key);
}

export function getSearchPlaceholder(role?: string | null, isSuperuser = false) {
  const key = getRoleKey(role, isSuperuser);
  if (key === "ceo") return "Search KPIs, payroll, reports...";
  if (key === "manager") return "Search team, leave, goals...";
  if (key === "employee") return "Search payslips, policies, tickets...";
  return "Search employees, documents, payroll...";
}

