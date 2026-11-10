import { consolidateNavigation, operationAliases, type WorkspaceNavigation } from "./navigation-workspaces";

type MenuItem = { to: string; label: string; group?: string };

// Keep the business flow short; configuration always lives inside its module.
export function moduleMenuNavigation<T extends MenuItem>(items: readonly T[], module: string): T[] {
  const flow: Record<string, Record<string, string[]>> = {
    hrms: {
      "People": ["Overview", "People & organization", "Recruitment & employee lifecycle", "Performance & learning"],
      "Time & pay": ["Attendance & leave", "Payroll & benefits"],
      "Employee services": ["Approvals & requests", "Documents, assets & support", "Collaboration"],
      "Reports & compliance": ["Reports & analytics", "Compliance & verification"],
    },
    crm: {
      "Customers & leads": ["Dashboard", "Customer growth", "Customers & leads"],
      "Sales": ["Sales & pipeline"],
      "Activities & communication": ["Activities & planning", "Communication", "Collaboration", "Support & files"],
      "Reports": ["Reports & forecasts"],
    },
    pms: {
      "Projects & tasks": ["Overview", "Tasks & projects"],
      "Planning & delivery": ["Planning & workload"],
      "Team & collaboration": ["People & teams", "Collaboration"],
      "Reports & finances": ["Reports & finances"],
    },
    srm: {
      "Customers & sales": ["Overview", "Business relationships", "Sales & contracts", "Point of sale"],
      "Products & inventory": ["Products & pricing", "Inventory & warehouses", "Purchasing & manufacturing"],
      "Billing & collections": ["Billing & collections"],
      "Reports": ["Reports & revenue"],
    },
    fam: {
      "Accounts & transactions": ["Overview", "Accounts & opening balances", "Transactions & books"],
      "Receivables & payables": ["Customers & receivables", "Purchases & payables"],
      "Banking": ["Banking & reconciliation"],
      "Reports & tax": ["GST & tax compliance"],
      "Integrations": ["Integrations & posting"],
    },
  };
  if (!flow[module]) return [...items];
  const settings = "Settings & administration";
  const seen = new Set<string>();
  const result = items.flatMap(item => {
    const path = item.to.split(/[?#]/)[0].replace(/\/+$/, "");
    const canonical = operationAliases[path] || path;
    const identity = canonical + (item.to.includes("?") ? "?" + item.to.split("?")[1] : "");
    if (seen.has(identity)) return [];
    seen.add(identity);
    const configuration = /setting|administration|settings & tools|data management/i.test(item.group || "")
      || /\/(settings|connectors|import-data|custom-fields|task-types|tags|workflow-designer|record-metadata|pipeline-settings|approval-settings|calendar-integrations|posting-rules|bank-rules|voucher-types|transaction-locking)(\/|$)/.test(path);
    const group = configuration ? settings : Object.entries(flow[module]).find(([, groups]) => groups.includes(item.group || ""))?.[0] || item.group || "Other tools";
    return [{ ...item, group }];
  });
  const order = [...Object.keys(flow[module]), "AI tools", "Other tools", settings];
  const rank = (group?: string) => { const index = order.indexOf(group || ""); return index < 0 ? order.length - 2 : index; };
  return result.sort((a, b) => rank(a.group) - rank(b.group));
}

// Only promote links already present in the caller's authorized navigation.
// Root and /dashboard are aliases for a module's landing page, not submenus.
export function moduleLandingNavigation<T extends MenuItem>(items: readonly T[], moduleKey: string) {
  const root = `/${moduleKey}`;
  const pathname = (item: T) => item.to.split(/[?#]/)[0].replace(/\/$/, "");
  const primaryPaths = [root, `${root}/dashboard`];
  const primary = items.find(item => primaryPaths.includes(pathname(item)));
  const direct = primary ? [primary] : [];
  // The PMS dashboard library is a separate destination from its workspace board.
  const library = items.find(item => pathname(item) === `${root}/dashboards`);
  if (library) direct.push(library);
  // ESS is the authorized HR landing page for employee roles.
  if (!primary && moduleKey === "hrms") {
    const personal = items.find(item => pathname(item) === "/hrms/ess");
    if (personal) direct.unshift(personal);
  }
  return {
    direct,
    grouped: items.filter(item => !primaryPaths.includes(pathname(item)) && !direct.includes(item)),
  };
}
const labels: Record<string, string> = {
  "/pms": "Workspace board", "/pms/tasks": "All tasks", "/pms/my-work": "My work",
  "/pms/work-hub": "Work pipeline", "/pms/live": "Live work board",
  "/pms/command-center": "Workspace overview", "/pms/enterprise-engine": "Project blueprints",
  "/pms/members": "Members & invitations", "/pms/people": "People directory",
  "/pms/time-tracking": "Time & timesheets", "/pms/operator": "AI assistant",
  "/pms/gantt": "Project timeline", "/pms/timeline-plus": "Dependency timeline",
  "/pms/settings": "Workspace settings", "/pms/admin": "Workspace administration",
  "/pms/templates": "Templates & workflows", "/pms/goals": "Goals",
  "/pms/backlog": "Backlog & sprints", "/pms/notes": "Notes",
  "/crm/companies": "Companies", "/crm/accounts": "Companies", "/crm/contacts": "Contacts", "/crm/customer-360": "Customer overview",
  "/crm/lead-to-cash": "Sales to payment", "/crm/gantt": "Activity timeline",
  "/crm/quotes": "Quote builder", "/crm/quotations": "Quotes", "/crm/duplicates": "Duplicate records",
  "/crm/settings": "CRM settings", "/crm/feature-checklist": "Feature availability",
  "/hrms/approval-os": "Approvals", "/hrms/workflow": "Request inbox",
  "/hrms/fnf-settlements": "Final settlements", "/hrms/lms": "Learning & courses",
  "/hrms/background-verification": "Background checks", "/hrms/ess": "My dashboard",
  "/hrms/letters-certificates": "Letters & certificates",
  "/hrms/settings": "HR settings", "/srm/settings": "Sales & inventory settings", "/fam/settings": "Finance settings",
  "/fam/ar": "Customer balances", "/fam/ap": "Supplier balances",
};
export const menuLabel = (item: MenuItem) => labels[item.to.split("?")[0]] || item.label;

// Consolidate only within a category; a page must not disappear into an unrelated section.
export function menuItems<T extends MenuItem>(items: readonly T[]): WorkspaceNavigation<T>[] {
  return [...new Set(items.map(item => item.group))].flatMap(group => {
    const grouped = items.filter(item => item.group === group);
    const internPages = grouped.filter(item => item.to === "/hrms/interns" || item.to.startsWith("/hrms/interns/"));
    const hasInternHub = internPages.some(item => item.to === "/hrms/interns");
    return consolidateNavigation(grouped).filter(item => !hasInternHub || !item.to.startsWith("/hrms/interns/"))
      .map(item => hasInternHub && item.to === "/hrms/interns" ? { ...item, pages: internPages } : item).map(item => item.pages?.length === 1 ? { ...item, label: item.pages[0].label } : item).sort((a, b) => {
      const priority = ["/hrms/settings", "/crm/settings", "/pms/settings", "/srm/settings", "/fam/settings", "/pms/my-work", "/pms/tasks", "/pms/projects", "/pms/workspaces"];
      const rank = (to: string) => priority.includes(to) ? priority.indexOf(to) : priority.length;
      return rank(a.to) - rank(b.to);
    });
  });
}
export function menuPages<T extends MenuItem>(item: WorkspaceNavigation<T>): T[] {
  const seen = new Set<string>();
  return (item.pages || [item]).filter(page => {
    const canonical = operationAliases[page.to] || page.to;
    if (seen.has(canonical)) return false;
    seen.add(canonical); return true;
  });
}
export function menuMatches(item: MenuItem, query: string) {
  return `${item.label} ${menuLabel(item)} ${item.group || ""} ${item.to}`.toLowerCase().includes(query.trim().toLowerCase());
}
