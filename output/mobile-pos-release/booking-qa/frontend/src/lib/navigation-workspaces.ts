import { commonRouteContext } from "./common-routes";

type Link = { to: string; label: string; group?: string };
export type WorkspaceNavigation<T> = T & { pages?: T[] };

export function workspacePageHref(to: string, search: string, workspaceId?: number) {
  if (!to.startsWith("/pms") && !to.startsWith("/common/")) return to;
  const [path, query = ""] = to.split("?");
  const target = new URLSearchParams(query);
  // The directory must not inherit the board's selected workspace.
  if (path === "/pms/workspaces") return target.size ? `${path}?${target}` : path;
  const current = new URLSearchParams(search);
  for (const key of ["workspace", "project", "projectId"]) {
    const value = key === "workspace" && workspaceId ? String(workspaceId) : current.get(key);
    if (value && !target.has(key)) target.set(key, value);
  }
  return target.size ? `${path}?${target}` : path;
}

// Presentation only: callers supply links already filtered by route permissions.
const menuSubcategories: [string, string[]][] = [
  ["Account setup", ["/fam/chart-of-accounts", "/fam/ledger-groups", "/fam/ledgers", "/fam/opening-balances"]],
  ["Transactions & books", ["/fam/vouchers", "/fam/journal", "/fam/day-book", "/fam/ledger-entries", "/fam/bill-references", "/fam/bill-allocations"]],
  ["Customers & receivables", ["/fam/customers", "/fam/parties", "/fam/ar"]],
  ["Purchases & payables", ["/fam/purchase-bills", "/fam/purchases", "/fam/vendors", "/fam/ap", "/fam/expenses", "/fam/recurring-purchases", "/fam/purchase-register", "/fam/expense-register", "/fam/vendor-payments", "/fam/payables"]],
  ["Banking & reconciliation", ["/fam/banking", "/fam/bank-accounts", "/fam/payment-modes", "/fam/bank-statements", "/fam/bank-reconciliation", "/fam/bank-book", "/fam/cash-book", "/fam/contra", "/fam/bank-charges"]],
  ["Finance settings", ["/fam/settings", "/fam/financial-years", "/fam/cost-centers", "/fam/branches", "/fam/forms", "/fam/voucher-types", "/fam/transaction-locking", "/fam/bank-rules", "/fam/posting-rules", "/fam/gst/settings", "/fam/connectors", "/fam/import-data"]],
  ["Sales & inventory settings", ["/srm/settings", "/srm/forms", "/srm/sales-inventory/source", "/srm/inventory/source", "/srm/connectors", "/srm/import-data"]],
  ["HR settings", ["/hrms/settings", "/hrms/custom-fields", "/hrms/enterprise", "/hrms/workflow-designer", "/hrms/connectors", "/hrms/import-data"]],
  ["Project settings", ["/pms/settings", "/pms/custom-fields", "/pms/task-types", "/pms/tags", "/pms/workflow-schemes", "/pms/automation", "/pms/connectors", "/pms/import-data"]],
];

// SRM uses the same definitions for the menu and the working page tabs.
const srmWorkspaces: [string, string[]][] = [
  ["POS sessions & returns", ["/srm/pos/sessions", "/srm/pos/cashier-closing", "/srm/pos/returns"]],
  ["Customers & suppliers", ["/srm/customers", "/srm/vendors", "/srm/companies", "/srm/customer-360"]],
  ["Sales orders & contracts", ["/srm/sales-orders", "/srm/contracts", "/srm/engagements"]],
  ["Products & pricing", ["/srm/products-services", "/srm/inventory/price-lists", "/srm/inventory/batches", "/srm/inventory/stock-groups", "/srm/inventory/units"]],
  ["Stock & warehouses", ["/srm/inventory", "/srm/inventory/stock-summary", "/srm/inventory/warehouses", "/srm/inventory/reorder-alerts"]],
  ["Stock movements", ["/srm/inventory/stock-in", "/srm/inventory/stock-out", "/srm/inventory/stock-transfers", "/srm/inventory/stock-adjustments", "/srm/inventory/opening-stock", "/srm/inventory/delivery-notes"]],
  ["Purchasing", ["/srm/inventory/purchase-orders", "/srm/inventory/purchase-receipts", "/srm/inventory/gantt"]],
  ["Invoices & payments", ["/srm/invoices", "/srm/invoice-drafts", "/srm/billing-plans", "/srm/payment-requests", "/srm/collections"]],
  ["Sales reports", ["/srm/reports", "/srm/profitability", "/srm/revenue-recognition"]],
  ["Stock reports", ["/srm/inventory/reports/complete", "/srm/inventory/valuation", "/srm/inventory/gross-margin", "/srm/inventory/reconciliation", "/srm/inventory/audit"]],
];

const workspaces: [string, string[]][] = [
  ...srmWorkspaces,
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
  ["Activities & Planning", ["/crm/follow-ups", "/crm/activities", "/crm/tasks", "/crm/calendar", "/crm/gantt", "/crm/calendar-integrations"]],
  ["Communication", ["/crm/communication-hub", "/crm/send-reminders", "/crm/birthdays", "/crm/email-templates", "/crm/emails", "/crm/forms", "/crm/webforms", "/crm/campaigns", "/crm/consents", "/crm/whatsapp", "/crm/whatsapp/inbox", "/crm/whatsapp/sent", "/crm/whatsapp/templates", "/crm/whatsapp/profile", "/crm/auto-responses", "/crm/delivery-logs", "/crm/communication-timeline"]],
  ["Catalog", ["/crm/products-services", "/crm/products", "/crm/services", "/crm/price-books"]],
  ["Quoting", ["/crm/quotes", "/crm/cpq", "/crm/guided-selling", "/crm/quote-approvals"]],
  ["Sales Insights", ["/crm/reports", "/crm/forecasting", "/crm/targets", "/crm/sales-performance", "/crm/funnel", "/crm/lost-analysis"]],
  ["CRM Administration", ["/crm/settings", "/crm/pipeline-settings", "/crm/approval-settings", "/crm/webhooks", "/crm/import-export", "/crm/automation", "/crm/admin", "/crm/feature-checklist"]],
];

export function getOperationWorkspace(pathname: string) {
  const definition = workspaces.find(([, paths]) => paths.includes(navigationOperationPath(pathname)));
  // Communication already renders its operations inside a single hub.
  if (!definition || definition[1].includes("/crm/communication-hub")) return undefined;
  return { label: definition[0], paths: definition[1] };
}

// These aliases render exactly the same operation; retain their URLs without
// presenting extra copies of the same form/table in the combined page.
export const operationAliases: Record<string, string> = {
  "/srm/suppliers": "/srm/vendors",
  "/srm/sales-inventory/source": "/srm/inventory/source",
  "/srm/pos": "/srm/pos/terminal",
  "/srm/pos/products": "/srm/products-services",
  "/srm/inventory/dashboard": "/srm/inventory",
  "/srm/inventory/items": "/srm/products-services",
  "/srm/inventory/products": "/srm/products-services",
  "/srm/products": "/srm/products-services",
  "/srm/services": "/srm/products-services",
  "/srm/inventory/reports": "/srm/inventory/reports/complete",
  "/pms/navigator": "/pms/tasks", "/pms/issue-navigator-pro": "/pms/tasks",
  "/pms/issues": "/pms/software", "/pms/releases": "/pms/software",
  "/pms/backlog-grooming": "/pms/backlog", "/pms/sprint-lifecycle": "/pms/backlog",
  "/pms/planner": "/pms/calendar", "/pms/dependency-timeline": "/pms/timeline-plus",
  "/pms/dependencies": "/pms/roadmap", "/pms/capacity": "/pms/workload",
  "/pms/resource-utilization": "/pms/workload", "/pms/teams-live": "/pms/live",
  "/pms/workspace-tools": "/pms/command-center",
  "/pms/components": "/pms/command-center", "/pms/workflows": "/pms/command-center",
  "/pms/security": "/pms/command-center", "/pms/apps": "/pms/command-center",
  "/pms/blueprints": "/pms/enterprise-engine",
  "/pms/ai-planner": "/pms/operator",
};

/** Resolve shared SRM pages before grouping, without changing their public URLs. */
export function navigationOperationPath(href: string) {
  const context = commonRouteContext(href);
  const path = (context?.module === "srm" ? context.nativePath : href.split(/[?#]/)[0]).replace(/\/+$/, "");
  return operationAliases[path] || path;
}

export function consolidateNavigation<T extends Link>(items: readonly T[]): WorkspaceNavigation<T>[] {
  const seen = new Set<string>();
  const result: WorkspaceNavigation<T>[] = [];
  for (const item of items) {
    const workspace = [...menuSubcategories, ...workspaces].find(([, paths]) => paths.includes(navigationOperationPath(item.to)));
    if (!workspace) { result.push(item); continue; }
    const [label, paths] = workspace;
    const key = paths[0];
    if (seen.has(key)) continue;
    seen.add(key);
    const pages = paths.flatMap(path => items.filter(candidate => navigationOperationPath(candidate.to) === path));
    const primary = pages[0];
    result.push({ ...primary, label, group: item.group, pages });
  }
  return result;
}

export function activeWorkspace<T extends Link>(items: readonly WorkspaceNavigation<T>[], pathname: string, search = "") {
  const workspace = getOperationWorkspace(pathname + search);
  const requested = new URLSearchParams(search).get("operation");
  const selected = requested && workspace?.paths.includes(requested) ? requested : navigationOperationPath(pathname + search);
  const matches = (to: string) => { const path = navigationOperationPath(to); return selected === path || selected.startsWith(path + "/"); };
  const rank = (item: WorkspaceNavigation<T>) => Math.max(...(item.pages || []).filter(page => matches(page.to)).map(page => navigationOperationPath(page.to).length));
  return items.filter(item => item.pages?.some(page => matches(page.to))).sort((a, b) => rank(b) - rank(a))[0];
}
