type Link = { to: string; label: string; group?: string };
export type WorkspaceNavigation<T> = T & { pages?: T[] };

export function workspacePageHref(to: string, search: string, workspaceId?: number) {
  if (!to.startsWith("/pms")) return to;
  const [path, query = ""] = to.split("?");
  const target = new URLSearchParams(query);
  const current = new URLSearchParams(search);
  for (const key of ["workspace", "project", "projectId"]) {
    const value = key === "workspace" && workspaceId ? String(workspaceId) : current.get(key);
    if (value && !target.has(key)) target.set(key, value);
  }
  return target.size ? `${path}?${target}` : path;
}

// Presentation only: callers supply links already filtered by route permissions.
const workspaces: [string, string[]][] = [
  ["Tasks", ["/pms/tasks", "/pms/navigator", "/pms/issue-navigator-pro"]],
  ["Software Delivery", ["/pms/software", "/pms/issues", "/pms/releases"]],
  ["Agile Planning", ["/pms/backlog", "/pms/backlog-grooming", "/pms/sprint-lifecycle", "/pms/sprints", "/pms/agile-execution"]],
  ["Calendar", ["/pms/calendar", "/pms/planner"]],
  ["Timeline & Dependencies", ["/pms/gantt", "/pms/timeline-plus", "/pms/dependency-timeline", "/pms/dependency-management"]],
  ["Roadmap", ["/pms/roadmap", "/pms/dependencies"]],
  ["Resources & Workload", ["/pms/workload", "/pms/capacity", "/pms/resource-utilization", "/pms/resource-planning"]],
  ["Live Work", ["/pms/live", "/pms/teams-live"]],
  ["Time", ["/pms/time-tracking", "/pms/timesheets"]],
  ["Insights", ["/pms/reports", "/pms/analytics/team", "/pms/analytics/projects", "/pms/dashboards"]],
  ["Recovery", ["/pms/recovery", "/pms/trash"]],
  ["Workspace Administration", ["/pms/command-center", "/pms/workspace-tools", "/pms/goals", "/pms/templates", "/pms/components", "/pms/workflows", "/pms/security", "/pms/apps"]],
  ["Enterprise Engine", ["/pms/enterprise-engine", "/pms/blueprints"]],
  ["AI Operator", ["/pms/operator", "/pms/ai-planner"]],
  ["People", ["/hrms/employees", "/hrms/employee-directory", "/hrms/org-chart"]],
  ["Attendance & Scheduling", ["/hrms/attendance", "/hrms/my-attendance", "/hrms/attendance/shift-roster", "/hrms/my-roster"]],
  ["Approvals", ["/hrms/approval-os", "/hrms/workflow"]],
  ["Employee Lifecycle", ["/hrms/onboarding", "/hrms/probation", "/hrms/exit"]],
  ["Documents", ["/hrms/documents", "/hrms/letters-certificates"]],
  ["Payroll", ["/hrms/payroll", "/hrms/my-payslips", "/hrms/investment-declaration", "/hrms/fnf-settlements"]],
  ["Insights", ["/hrms/reports", "/hrms/advanced-analytics"]],
  ["Intern Management", ["/hrms/interns", "/hrms/interns/applications", "/hrms/interns/batches", "/hrms/interns/tasks", "/hrms/interns/reviews", "/hrms/interns/performance"]],
  ["Deals", ["/crm/deals", "/crm/pipeline", "/crm/templates"]],
  ["Activities & Planning", ["/crm/activities", "/crm/tasks", "/crm/calendar", "/crm/gantt", "/crm/calendar-integrations"]],
  ["Communication & Campaigns", ["/crm/communication-hub", "/crm/email-templates", "/crm/emails", "/crm/webforms", "/crm/campaigns", "/crm/consents", "/crm/whatsapp", "/crm/auto-responses", "/crm/delivery-logs", "/crm/communication-timeline"]],
  ["Catalog", ["/crm/products", "/crm/services", "/crm/price-books"]],
  ["Quoting", ["/crm/quotes", "/crm/cpq", "/crm/guided-selling", "/crm/quote-approvals"]],
  ["Sales Insights", ["/crm/reports", "/crm/forecasting", "/crm/targets", "/crm/sales-performance", "/crm/funnel", "/crm/lost-analysis"]],
  ["CRM Administration", ["/crm/settings", "/crm/pipeline-settings", "/crm/approval-settings", "/crm/webhooks", "/crm/import-export", "/crm/automation", "/crm/admin", "/crm/feature-checklist"]],
];

export function getOperationWorkspace(pathname: string) {
  const definition = workspaces.find(([, paths]) => paths.includes(pathname));
  // Communication already renders its operations inside a single hub.
  if (!definition || definition[1].includes("/crm/communication-hub")) return undefined;
  return { label: definition[0], paths: definition[1] };
}

// These aliases render exactly the same operation; retain their URLs without
// presenting extra copies of the same form/table in the combined page.
export const operationAliases: Record<string, string> = {
  "/pms/navigator": "/pms/tasks", "/pms/issue-navigator-pro": "/pms/tasks",
  "/pms/issues": "/pms/software", "/pms/releases": "/pms/software",
  "/pms/backlog-grooming": "/pms/backlog", "/pms/sprint-lifecycle": "/pms/backlog",
  "/pms/planner": "/pms/calendar", "/pms/dependency-timeline": "/pms/timeline-plus",
  "/pms/dependencies": "/pms/roadmap", "/pms/capacity": "/pms/workload",
  "/pms/resource-utilization": "/pms/workload", "/pms/teams-live": "/pms/live",
  "/pms/workspace-tools": "/pms/command-center", "/pms/blueprints": "/pms/enterprise-engine",
  "/pms/ai-planner": "/pms/operator",
};

export function consolidateNavigation<T extends Link>(items: readonly T[]): WorkspaceNavigation<T>[] {
  const seen = new Set<string>();
  const result: WorkspaceNavigation<T>[] = [];
  for (const item of items) {
    const workspace = workspaces.find(([, paths]) => paths.includes(item.to));
    if (!workspace) { result.push(item); continue; }
    const [label, paths] = workspace;
    const key = paths[0];
    if (seen.has(key)) continue;
    seen.add(key);
    const pages = paths.flatMap(path => items.filter(candidate => candidate.to === path));
    const primary = pages[0];
    result.push({ ...primary, label, group: item.group, pages });
  }
  return result;
}

export function activeWorkspace<T extends Link>(items: readonly WorkspaceNavigation<T>[], pathname: string) {
  return items.filter(item => item.pages?.some(page => pathname === page.to || pathname.startsWith(page.to + "/")))
    .sort((a, b) => Math.max(...b.pages!.filter(p => pathname === p.to || pathname.startsWith(p.to + "/")).map(p => p.to.length)) - Math.max(...a.pages!.filter(p => pathname === p.to || pathname.startsWith(p.to + "/")).map(p => p.to.length)))[0];
}
