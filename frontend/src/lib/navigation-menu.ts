import { consolidateNavigation, operationAliases, type WorkspaceNavigation } from "./navigation-workspaces";

type MenuItem = { to: string; label: string; group?: string };

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
  "/crm/settings": "Fields & preferences", "/crm/feature-checklist": "Feature availability",
  "/hrms/approval-os": "Approvals", "/hrms/workflow": "Request inbox",
  "/hrms/fnf-settlements": "Final settlements", "/hrms/lms": "Learning & courses",
  "/hrms/background-verification": "Background checks", "/hrms/ess": "My dashboard",
  "/hrms/letters-certificates": "Letters & certificates",
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
      const priority = ["/pms/my-work", "/pms/tasks", "/pms/projects", "/pms/workspaces"];
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
