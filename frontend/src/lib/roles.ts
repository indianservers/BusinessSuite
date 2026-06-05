import {
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
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
  Receipt,
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
  if (["hr_manager", "hr_admin", "hr", "hr_company_admin", "hr_workflow_admin", "hr_custom_field_admin"].includes(value)) return "hr";
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
  const srmLabels: Record<string, string> = {
    srm_admin: "SRM Admin",
    srm_sales_manager: "SRM Sales Manager",
    srm_sales_executive: "SRM Sales Executive",
    srm_finance_manager: "Finance Manager",
    srm_revenue_manager: "Revenue Manager",
    srm_collection_executive: "Collection Executive",
    srm_business_owner: "Business Owner",
    srm_viewer: "SRM Viewer",
  };
  if (srmLabels[normalizedRole]) return srmLabels[normalizedRole];

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
  return isSuperuser || [
    "super_admin",
    "admin",
    "hr_manager",
    "hr_admin",
    "hr",
    "hr_company_admin",
    "hr_workflow_admin",
    "hr_custom_field_admin",
    "ceo",
    "founder",
    "director",
    "executive",
    "manager",
    "team_lead",
    "department_head",
    "employee",
  ].includes(value);
}

function hasOptionalHrPermission(role: string | null | undefined, permission: "hr.company_admin" | "hr.workflow_admin" | "hr.custom_field_admin") {
  const value = normalizeRole(role);
  const permissionRoles: Record<string, string[]> = {
    "hr.company_admin": ["hr_company_admin"],
    "hr.workflow_admin": ["hr_workflow_admin"],
    "hr.custom_field_admin": ["hr_custom_field_admin"],
  };
  return permissionRoles[permission].includes(value);
}

function isCrmRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
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

function isCrmAdminRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
  return ["super_admin", "admin", "crm_super_admin", "crm_org_admin"].includes(normalizeRole(role));
}

function isCrmManagerRole(role?: string | null, isSuperuser = false) {
  if (isCrmAdminRole(role, isSuperuser)) return true;
  return normalizeRole(role) === "crm_sales_manager";
}

const crmAdminOnlyPaths = [
  "/crm/admin",
  "/crm/settings",
  "/crm/approval-settings",
  "/crm/webhooks",
  "/crm/feature-checklist",
];

const crmManagerOnlyPaths = [
  "/crm/import-export",
  "/crm/lead-scoring",
  "/crm/pipeline-settings",
  "/crm/territories",
];

function canAccessCrmPath(pathname: string, role?: string | null, isSuperuser = false) {
  if (!isCrmRole(role, isSuperuser)) return false;
  const normalizedPath = pathname.replace(/\/+$/, "") || "/crm";
  if (crmAdminOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isCrmAdminRole(role, isSuperuser);
  }
  if (crmManagerOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isCrmManagerRole(role, isSuperuser);
  }
  return true;
}

function getCrmNavForRole(role?: string | null, isSuperuser = false) {
  return crmNav.filter((item) => !item.to.startsWith("/crm") || canAccessCrmPath(item.to, role, isSuperuser));
}

function isProjectManagementRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
  return [
    "pms_super_admin",
    "pms_org_admin",
    "pms_project_manager",
    "pms_team_member",
    "pms_client",
    "pms_viewer",
  ].includes(normalizeRole(role));
}

function isPmsAdminRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
  return ["super_admin", "admin", "pms_super_admin", "pms_org_admin"].includes(normalizeRole(role));
}

function isPmsManagerRole(role?: string | null, isSuperuser = false) {
  if (isPmsAdminRole(role, isSuperuser)) return true;
  return normalizeRole(role) === "pms_project_manager";
}

function isPmsDeliveryRole(role?: string | null, isSuperuser = false) {
  if (isPmsManagerRole(role, isSuperuser)) return true;
  return normalizeRole(role) === "pms_team_member";
}

const pmsAdminOnlyPaths = [
  "/pms/admin",
  "/pms/settings",
  "/pms/security",
  "/pms/apps",
  "/pms/workflows",
  "/pms/blueprints",
  "/pms/components",
  "/pms/templates",
  "/pms/forms",
  "/pms/plans",
];

const pmsManagerOnlyPaths = [
  "/pms/projects/new",
  "/pms/command-center",
  "/pms/enterprise-engine",
  "/pms/product-launch",
  "/pms/portfolio",
  "/pms/dependency-management",
  "/pms/resource-planning",
  "/pms/agile-execution",
  "/pms/project-financials",
  "/pms/resource-utilization",
  "/pms/reports",
  "/pms/dashboards",
];

const pmsDeliveryOnlyPaths = [
  "/pms/backlog",
  "/pms/backlog-grooming",
  "/pms/issues",
  "/pms/tasks",
  "/pms/navigator",
  "/pms/issue-navigator-pro",
  "/pms/risk-register",
  "/pms/risks",
  "/pms/goals",
  "/pms/roadmap",
  "/pms/timeline-plus",
  "/pms/dependencies",
  "/pms/releases",
  "/pms/calendar",
  "/pms/gantt",
  "/pms/sprints",
  "/pms/sprint-lifecycle",
  "/pms/files",
  "/pms/time-tracking",
  "/pms/timesheets",
  "/pms/workload",
  "/pms/capacity",
  "/pms/automation",
  "/pms/automation-ai",
  "/pms/software",
  "/pms/live",
  "/pms/teams-live",
  "/pms/work-hub",
  "/pms/ai-planner",
  "/pms/projects",
];

function canAccessPmsPath(pathname: string, role?: string | null, isSuperuser = false) {
  if (!isProjectManagementRole(role, isSuperuser)) return false;
  const normalizedPath = pathname.replace(/\/+$/, "") || "/pms";
  const normalizedRole = normalizeRole(role);

  if (normalizedPath === "/pms" || normalizedPath === "/pms/profile") return true;
  if (normalizedPath === "/pms/client-portal" || normalizedPath.startsWith("/pms/client-portal/")) {
    return true;
  }
  if (normalizedRole === "pms_client") return false;

  if (pmsAdminOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isPmsAdminRole(role, isSuperuser);
  }
  if (pmsManagerOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isPmsManagerRole(role, isSuperuser);
  }
  if (pmsDeliveryOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isPmsDeliveryRole(role, isSuperuser) || normalizedRole === "pms_viewer";
  }
  return isPmsManagerRole(role, isSuperuser);
}

function getPmsNavForRole(role?: string | null, isSuperuser = false) {
  return projectManagementNav.filter((item) => !item.to.startsWith("/pms") || canAccessPmsPath(item.to, role, isSuperuser));
}

function isSrmRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
  return [
    "srm_admin",
    "srm_sales_manager",
    "srm_sales_executive",
    "srm_finance_manager",
    "srm_revenue_manager",
    "srm_collection_executive",
    "srm_business_owner",
    "srm_viewer",
  ].includes(normalizeRole(role));
}

function isSrmAdminRole(role?: string | null, isSuperuser = false) {
  if (isSuperuser) return true;
  return ["super_admin", "admin", "srm_admin"].includes(normalizeRole(role));
}

function isSrmFinanceRole(role?: string | null, isSuperuser = false) {
  if (isSrmAdminRole(role, isSuperuser)) return true;
  return ["srm_finance_manager", "srm_revenue_manager", "srm_business_owner"].includes(normalizeRole(role));
}

function isSrmCollectionRole(role?: string | null, isSuperuser = false) {
  if (isSrmAdminRole(role, isSuperuser)) return true;
  return ["srm_collection_executive", "srm_finance_manager", "srm_business_owner"].includes(normalizeRole(role));
}

function isSrmSalesRole(role?: string | null, isSuperuser = false) {
  if (isSrmAdminRole(role, isSuperuser)) return true;
  return ["srm_sales_manager", "srm_sales_executive", "srm_business_owner"].includes(normalizeRole(role));
}

const srmFinanceOnlyPaths = ["/srm/invoice-drafts", "/srm/invoices", "/srm/revenue-recognition", "/srm/profitability", "/srm/reports"];
const srmCollectionOnlyPaths = ["/srm/collections"];
const srmSalesOnlyPaths = ["/srm/sales-orders", "/srm/contracts", "/srm/engagements", "/srm/billing-plans", "/srm/customer-360"];

function canAccessSrmPath(pathname: string, role?: string | null, isSuperuser = false) {
  if (!isSrmRole(role, isSuperuser)) return false;
  const normalizedPath = pathname.replace(/\/+$/, "") || "/srm";
  const normalizedRole = normalizeRole(role);
  if (normalizedPath === "/srm" || normalizedPath === "/srm/dashboard" || normalizedPath === "/srm/profile") return true;
  if (normalizedPath === "/srm/settings") return true;
  if (normalizedPath === "/srm/reports") return isSrmFinanceRole(role, isSuperuser) || normalizedRole === "srm_viewer";
  if (srmCollectionOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isSrmCollectionRole(role, isSuperuser);
  }
  if (srmFinanceOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isSrmFinanceRole(role, isSuperuser);
  }
  if (srmSalesOnlyPaths.some((path) => normalizedPath === path || normalizedPath.startsWith(`${path}/`))) {
    return isSrmSalesRole(role, isSuperuser) || normalizedRole === "srm_viewer";
  }
  return isSrmAdminRole(role, isSuperuser);
}

function getSrmNavForRole(role?: string | null, isSuperuser = false) {
  return srmNav.filter((item) => !item.to.startsWith("/srm") || canAccessSrmPath(item.to, role, isSuperuser));
}

const hrNav: RoleNavItem[] = [
  { label: "HR Home", icon: LayoutDashboard, to: "/hr-home", group: "Core HR", exact: true },
  { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Probation", icon: Timer, to: "/probation", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Approval OS", icon: FileCheck2, to: "/approval-os", group: "Core HR" },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Shift Roster", icon: CalendarDays, to: "/attendance/shift-roster", group: "Core HR" },
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
  { label: "Org Chart", icon: GitBranch, to: "/org-chart", group: "Platform" },
  { label: "Onboarding", icon: ClipboardCheck, to: "/onboarding", group: "Platform" },
  { label: "Documents", icon: FileText, to: "/documents", group: "Platform" },
  { label: "Assets", icon: Package, to: "/assets", group: "Platform" },
  { label: "Exit", icon: LogOut, to: "/exit", group: "Platform" },
  { label: "WhatsApp ESS", icon: MessageCircle, to: "/whatsapp-ess", group: "Platform" },
  { label: "AI Agents", icon: Sparkles, to: "/ai-agents", badge: "AI", group: "Platform" },
  { label: "AI Assistant", icon: Sparkles, to: "/ai-assistant", badge: "AI", group: "Platform" },
];

const adminNav: RoleNavItem[] = [
  { label: "Admin Home", icon: ShieldCheck, to: "/admin-home", group: "Core HR", exact: true },
  { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", group: "Core HR", exact: true },
  { label: "Approval OS", icon: FileCheck2, to: "/approval-os", group: "Core HR" },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Workflow Designer", icon: GitBranch, to: "/workflow-designer", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Probation", icon: Timer, to: "/probation", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Shift Roster", icon: CalendarDays, to: "/attendance/shift-roster", group: "Core HR" },
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
  { label: "Approval OS", icon: FileCheck2, to: "/approval-os", group: "Core HR" },
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
  { label: "Approval OS", icon: FileCheck2, to: "/approval-os", group: "Core HR" },
  { label: "Inbox", icon: Inbox, to: "/workflow", group: "Core HR" },
  { label: "Notifications", icon: Bell, to: "/notifications", group: "Core HR" },
  { label: "Employees", icon: Users, to: "/employees", group: "Core HR" },
  { label: "Employee Directory", icon: UserRound, to: "/employee-directory", group: "Core HR" },
  { label: "Attendance", icon: Clock, to: "/attendance", group: "Core HR" },
  { label: "Shift Roster", icon: CalendarDays, to: "/attendance/shift-roster", group: "Core HR" },
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
  { label: "ESS Dashboard", icon: LayoutDashboard, to: "/ess", group: "Self Service", exact: true },
  { label: "My Profile", icon: UserRound, to: "/profile", group: "Self Service" },
  { label: "My Attendance", icon: Clock, to: "/my-attendance", group: "Self Service" },
  { label: "My Leave", icon: CalendarDays, to: "/leave", group: "Self Service" },
  { label: "My Payslips", icon: DollarSign, to: "/my-payslips", group: "Self Service" },
  { label: "My Documents", icon: FileText, to: "/documents", group: "Self Service" },
  { label: "My Approvals", icon: FileCheck2, to: "/approval-os", group: "Home" },
  { label: "My Requests", icon: Inbox, to: "/workflow", group: "Home" },
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

const srmNav: RoleNavItem[] = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/srm/dashboard", group: "Sales & Revenue", exact: true },
  { label: "Sales Orders", icon: Receipt, to: "/srm/sales-orders", group: "Sales & Revenue" },
  { label: "Contracts", icon: FileCheck2, to: "/srm/contracts", group: "Sales & Revenue" },
  { label: "Engagements", icon: Briefcase, to: "/srm/engagements", group: "Sales & Revenue" },
  { label: "Billing Plans", icon: CalendarDays, to: "/srm/billing-plans", group: "Billing" },
  { label: "Invoice Drafts", icon: FileText, to: "/srm/invoice-drafts", group: "Billing" },
  { label: "Invoices", icon: DollarSign, to: "/srm/invoices", group: "Billing" },
  { label: "Collections", icon: Landmark, to: "/srm/collections", group: "Collections" },
  { label: "Revenue Recognition", icon: CheckCircle2, to: "/srm/revenue-recognition", group: "Revenue" },
  { label: "Profitability", icon: BarChart3, to: "/srm/profitability", group: "Revenue" },
  { label: "Customer 360", icon: Users, to: "/srm/customer-360", group: "Revenue" },
  { label: "Reports", icon: BarChart3, to: "/srm/reports", group: "Insights" },
  { label: "Settings", icon: Settings, to: "/srm/settings", group: "Admin" },
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
  { label: "SRM", icon: Receipt, to: "/srm", group: "Applications", exact: true },
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
  if (pathname.startsWith("/srm")) return "srm";
  return "hrms";
}

function getHrmsNavForRole(key: RoleKey) {
  if (key === "admin") return adminNav;
  if (key === "ceo") return ceoNav;
  if (key === "manager") return managerNav;
  if (key === "employee") return employeeNav;
  return hrNav;
}

function getDelegatedHrNav(role?: string | null): RoleNavItem[] {
  const items: RoleNavItem[] = [];
  if (hasOptionalHrPermission(role, "hr.company_admin")) {
    items.push({ label: "Company", icon: Building2, to: "/company", group: "Delegated Admin" });
  }
  if (hasOptionalHrPermission(role, "hr.workflow_admin")) {
    items.push({ label: "Workflow Designer", icon: GitBranch, to: "/workflow-designer", group: "Delegated Admin" });
  }
  if (hasOptionalHrPermission(role, "hr.custom_field_admin")) {
    items.push({ label: "Custom Fields", icon: SlidersHorizontal, to: "/custom-fields", group: "Delegated Admin" });
  }
  return items;
}

export function getRoleNav(role?: string | null, isSuperuser = false, pathname = window.location.pathname) {
  const installedApps = getInstalledAppKeys();
  const key = getRoleKey(role, isSuperuser);
  const activeModule = getActiveModule(pathname);

  if (activeModule === "crm") {
    return installedApps.includes("crm") && isCrmRole(role, isSuperuser) ? getCrmNavForRole(role, isSuperuser) : [];
  }

  if (activeModule === "project_management") {
    return installedApps.includes("project_management") && isProjectManagementRole(role, isSuperuser) ? getPmsNavForRole(role, isSuperuser) : [];
  }

  if (activeModule === "srm") {
    return installedApps.includes("srm") && isSrmRole(role, isSuperuser) ? getSrmNavForRole(role, isSuperuser) : [];
  }

  if (activeModule === "ai_agents") {
    return key === "employee" ? [] : aiAgentsNav;
  }

  if (activeModule === "suite") {
    const suiteNav: RoleNavItem[] = [];
    if (installedApps.includes("hrms") && isHrmsRole(role, isSuperuser)) {
      suiteNav.push({ label: "AI HRMS", icon: Building2, to: "/hrms", group: "Applications", exact: true });
    }
    if (installedApps.includes("crm") && isCrmRole(role, isSuperuser)) {
      suiteNav.push({ label: "VyaparaCRM", icon: Briefcase, to: "/crm", group: "Applications", exact: true });
    }
    if (installedApps.includes("project_management") && isProjectManagementRole(role, isSuperuser)) {
      suiteNav.push({ label: "KaryaFlow", icon: Target, to: "/pms", group: "Applications", exact: true });
    }
    if (installedApps.includes("srm") && isSrmRole(role, isSuperuser)) {
      suiteNav.push({ label: "RevenueFlow", icon: Receipt, to: "/srm", group: "Applications", exact: true });
    }
    if (key !== "employee") {
      suiteNav.push({ label: "AI Agents", icon: Sparkles, to: "/ai-agents", group: "Applications", badge: "AI", exact: true });
    }
    return suiteNav;
  }

  if (!installedApps.includes("hrms") || !isHrmsRole(role, isSuperuser)) return [];
  const nav = key === "hr" ? [...getHrmsNavForRole(key), ...getDelegatedHrNav(role)] : getHrmsNavForRole(key);
  return withPrefix(nav, "/hrms");
}

const routeAccess: Record<string, RoleKey[]> = {
  "/role-home": ["admin", "ceo", "hr", "manager"],
  "/admin-home": ["admin"],
  "/hr-home": ["admin", "hr"],
  "/executive-home": ["admin", "ceo"],
  "/dashboard": ["admin", "ceo", "hr", "manager"],
  "/manager-dashboard": ["admin", "hr", "manager"],
  "/ess": ["admin", "ceo", "hr", "manager", "employee"],
  "/profile": ["admin", "ceo", "hr", "manager", "employee"],
  "/workflow/admin": ["admin", "hr", "manager"],
  "/approval-os": ["admin", "ceo", "hr", "manager", "employee"],
  "/workflow": ["admin", "ceo", "hr", "manager", "employee"],
  "/workflow-designer": ["admin"],
  "/notifications": ["admin", "ceo", "hr", "manager"],
  "/attendance/shift-roster": ["admin", "hr", "manager"],
  "/attendance": ["admin", "hr", "manager"],
  "/my-attendance": ["admin", "hr", "manager", "employee"],
  "/my-roster": ["admin", "hr", "manager", "employee"],
  "/timesheets": ["admin", "ceo", "hr", "manager"],
  "/leave": ["admin", "hr", "manager", "employee"],
  "/payroll": ["admin", "ceo", "hr"],
  "/my-payslips": ["admin", "hr", "employee"],
  "/investment-declaration": ["admin", "ceo", "hr"],
  "/fnf-settlements": ["admin", "ceo", "hr"],
  "/benefits": ["admin", "ceo", "hr"],
  "/performance": ["admin", "ceo", "hr", "manager"],
  "/lms": ["admin", "ceo", "hr", "manager"],
  "/statutory-compliance": ["admin", "ceo", "hr"],
  "/background-verification": ["admin", "hr"],
  "/whatsapp-ess": ["admin", "hr"],
  "/custom-fields": ["admin"],
  "/enterprise": ["admin"],
  "/engagement": ["admin", "ceo", "hr", "manager"],
  "/helpdesk": ["admin", "hr", "manager"],
  "/documents": ["admin", "hr", "employee"],
  "/employee-directory": ["admin", "ceo", "hr", "manager"],
  "/employees": ["admin", "ceo", "hr", "manager"],
  "/probation": ["admin", "ceo", "hr", "manager"],
  "/reports": ["admin", "ceo", "hr", "manager"],
  "/advanced-analytics": ["admin", "ceo", "hr", "manager"],
  "/logs": ["admin"],
  "/recruitment": ["admin", "hr", "manager"],
  "/company": ["admin", "ceo"],
  "/org-chart": ["admin", "ceo", "hr", "manager"],
  "/settings": ["admin"],
  "/assets": ["admin", "hr", "manager"],
  "/onboarding": ["admin", "hr"],
  "/exit": ["admin", "hr"],
  "/ai-assistant": ["admin", "ceo", "hr", "manager"],
  "/ai-agents": ["admin", "ceo", "hr", "manager"],
  "/crm": ["admin", "ceo", "hr", "manager"],
  "/pms": ["admin", "ceo", "hr", "manager", "employee"],
  "/srm": ["admin", "ceo", "hr", "manager"],
};

export function canAccessRoute(pathname: string, role?: string | null, isSuperuser = false) {
  if (pathname === "/") return true;
  if (pathname.startsWith("/ai-agents")) return getRoleKey(role, isSuperuser) !== "employee";
  if (pathname === "/hrms") return isHrmsRole(role, isSuperuser);
  if (pathname.startsWith("/crm")) return canAccessCrmPath(pathname, role, isSuperuser);
  if (pathname.startsWith("/pms")) return canAccessPmsPath(pathname, role, isSuperuser);
  if (pathname.startsWith("/srm")) return canAccessSrmPath(pathname, role, isSuperuser);
  if (pathname.startsWith("/hrms/") && !isHrmsRole(role, isSuperuser)) return false;
  const normalizedPathname = pathname.startsWith("/hrms/")
    ? pathname.replace(/^\/hrms/, "")
    : pathname;
  const key = getRoleKey(role, isSuperuser);
  const match = Object.keys(routeAccess)
    .sort((a, b) => b.length - a.length)
    .find((path) => normalizedPathname === path || normalizedPathname.startsWith(`${path}/`));
  if (!match) return key === "admin" || isSuperuser;
  if (key === "hr") {
    if (match === "/company") return hasOptionalHrPermission(role, "hr.company_admin");
    if (match === "/workflow-designer") return hasOptionalHrPermission(role, "hr.workflow_admin");
    if (match === "/custom-fields") return hasOptionalHrPermission(role, "hr.custom_field_admin");
  }
  return routeAccess[match].includes(key);
}

export function getRequiredPermissionForPath(pathname: string) {
  const normalizedPathname = pathname.startsWith("/hrms/")
    ? pathname.replace(/^\/hrms/, "")
    : pathname;
  const match = Object.keys(routeAccess)
    .sort((a, b) => b.length - a.length)
    .find((path) => normalizedPathname === path || normalizedPathname.startsWith(`${path}/`));

  if (match === "/company") return "hr.company_admin or Admin";
  if (match === "/approval-os") return "Approval OS";
  if (match === "/workflow-designer") return "hr.workflow_admin or Admin";
  if (match === "/custom-fields") return "hr.custom_field_admin or Admin";
  if (match === "/workflow/admin") return "Approval Administration";
  if (match === "/payroll") return "Payroll Operations";
  if (match === "/attendance") return "Attendance Register";
  if (match === "/attendance/shift-roster") return "Shift Roster Administration";
  if (match) return routeAccess[match].map((role) => role.toUpperCase()).join(", ");
  if (pathname.startsWith("/ai-agents")) return "AI Agents Access";
  if (pathname.startsWith("/srm")) return "SRM Access";
  return "Admin";
}

export function getSearchPlaceholder(role?: string | null, isSuperuser = false) {
  const key = getRoleKey(role, isSuperuser);
  if (key === "ceo") return "Search KPIs, payroll, reports...";
  if (key === "manager") return "Search team, leave, goals...";
  if (key === "employee") return "Search payslips, policies, tickets...";
  return "Search employees, documents, payroll...";
}

