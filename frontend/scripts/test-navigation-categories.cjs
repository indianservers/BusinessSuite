const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

function compile(source, resolveImport) {
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const compiled = { exports: {} };
  new Function("module", "exports", "require", output)(compiled, compiled.exports, resolveImport);
  return compiled.exports;
}
const categories = compile(fs.readFileSync(path.resolve(__dirname, "../src/lib/navigation-categories.ts"), "utf8"), require);
const common = compile(fs.readFileSync(path.resolve(__dirname, "../src/lib/common-routes.ts"), "utf8"), require);
let auth = {};
const source = fs.readFileSync(path.resolve(__dirname, "../src/lib/roles.ts"), "utf8")
  .replace("function getAvailableRoleNav(", "export function getAvailableRoleNav(");
const roles = compile(source, name => {
  if (name === "./common-routes") return common;
  if (name === "./navigation-categories") return categories;
  if (name === "@/store/authStore") return { useAuthStore: { getState: () => auth } };
  if (name === "@/appRegistry") return { getInstalledAppKeys: () => ["hrms", "crm", "project_management", "srm", "fam", "ai"], isFrontendModuleEnabled: () => true };
  if (name === "lucide-react") return new Proxy({}, { get: (_, key) => key });
  throw new Error("Unexpected import: " + name);
});

let count = 0;
const identity = items => items.map(({ group, ...item }) => JSON.stringify(item)).sort();
// Grouping must neither grant links nor hide an existing role-authorized link.
for (const role of ["admin", "hr", "hr_manager", "ceo", "manager", "employee", "crm_sales_executive", "crm_support_agent", "crm_viewer", "srm_sales_executive", "accountant", "fam_viewer"]) {
  for (const pathname of ["/hrms", "/crm", "/srm", "/fam", "/pms", "/ai-agents", "/ai/copilot"]) {
    const raw = roles.getAvailableRoleNav(role, false, pathname);
    const original = JSON.stringify(raw);
    const grouped = roles.getRoleNav(role, false, pathname);
    // The public catalog adds authorized import/connector destinations before
    // categorization. Test grouping separately from those existing additions.
    const categorized = categories.categorizeNavigation(raw, roles.getActiveModule(pathname));
    assert.deepEqual(identity(categorized), identity(raw), `${role} on ${pathname}: categorization changed available links`);
    const mapped = raw.map(item => ({...item,to: common.commonNavigationHref(item.to, pathname.slice(1))}));
    const originalLinks = grouped.filter(item => mapped.some(original => original.to === item.to));
    assert.deepEqual(identity(originalLinks), identity(mapped), `${role} on ${pathname}: lost an existing link`);
    const root = pathname.split('/')[1];
    for (const item of grouped.filter(item => !mapped.some(original => original.to === item.to))) {
      assert([`/${root}/import-data`, `/${root}/connectors`].includes(item.to) || common.commonRouteContext(item.to), 'Unexpected supplemental link: ' + item.to);
      assert(roles.canAccessRoute(item.to, role, false), 'Unauthorized supplemental link: ' + item.to);
    }
    assert.equal(JSON.stringify(raw), original, "Mutated shared navigation definitions");
    assert.deepEqual(originalLinks.filter(i => roles.canAccessRoute(i.to, role, false)).map(i => i.to).sort(), mapped.filter(i => roles.canAccessRoute(i.to, role, false)).map(i => i.to).sort());
    count++;
  }
}
for (const [pathname, to, group] of [
  ["/hrms", "/hrms/attendance/shift-roster", "Attendance & leave"],
  ["/hrms", "/hrms/forms", "Approvals & requests"],
  ["/hrms", "/hrms/leave/gantt", "Attendance & leave"],
  ["/hrms", "/hrms/payroll", "Payroll & benefits"],
  ["/hrms", "/admin/automation/workflows", "Settings & administration"],
  ["/crm", "/crm/contacts", "Customers & leads"],
  ["/crm", "/crm/products", "Sales & pipeline"],
  ["/crm", "/crm/calendar-integrations", "Activities & planning"],
  ["/crm", "/crm/campaigns", "Communication"],
  ["/pms", "/pms/workflow-schemes", "Settings & tools"],
  ["/pms", "/pms/transition-approvals", "Planning & workload"],
  ["/srm", "/srm/pos/returns", "Point of sale"],
  ["/srm", "/srm/inventory/stock-transfers", "Inventory & warehouses"],
  ["/srm", "/srm/inventory/purchase-orders", "Purchasing & manufacturing"],
  ["/fam", "/fam/bank-reconciliation", "Banking & reconciliation"],
  ["/fam", "/fam/gst/settings", "GST & tax compliance"],
]) {
  // Categorize legacy aliases too, even when a current role catalog exposes
  // only their canonical destination (for example Products & Services).
  assert.equal(categories.categorizeNavigation([{to}], roles.getActiveModule(pathname))[0]?.group, group, to);
  count++;
}
for (const module of ["hrms", "crm", "srm", "fam"]) {
  auth = { user: { access: { managed: true, modules: [{ key: module, route: `/${module}` }], grants: { [module]: { enabled: true } } } } };
  const nav = roles.getRoleNav("employee", false, `/${module}`);
  assert(nav.length > 0, module + ": managed grant lost its menu");
  assert(nav.every(i => !i.to.startsWith("/hrms/hrms/")), "Double-prefixed HRMS link");
  auth.user.access.grants[module].enabled = false;
  assert.deepEqual(roles.getRoleNav("employee", false, `/${module}`), [], "Disabled module has navigation");
  count++;
}
console.log(`${count} navigation checks passed (role visibility, managed grants, canonical links and categories).`);

for (const role of ["admin", "hr", "ceo", "manager", "employee"]) {
  assert(!roles.getRoleNav(role, false, "/hrms").some(item => item.to === "/analytics"), "Suite analytics leaked into HRMS");
}
assert.equal(roles.getActiveModule("/analytics"), "suite");
assert.equal(roles.getActiveModule("/analytics/collections"), "suite");
assert(roles.getRoleNav("admin", true, "/analytics").some(item => item.to === "/analytics"));

for (const managed of [false, true]) {
  auth = managed ? { user: { access: { managed: true, modules: [{key:"crm",route:"/crm"},{key:"project_management",route:"/pms"}], grants: {crm:{enabled:true},project_management:{enabled:true}} } } } : {};
  for (const [module, removed, retained] of [
    ["/crm", ["/analytics", "/ai-agents/config", "/crm/feature-checklist", "/crm/gantt", "/crm/tickets", "/crm/lead-to-cash"], ["/crm/campaigns", "/crm/quotations", "/crm/activities"]],
    ["/pms", ["/ai-agents", "/pms/org-chart", "/pms/people-work", "/pms/my-notices", "/pms/plans", "/pms/settings/ai/openai", "/pms/settings/ai/gemini", "/pms/settings/ai/claude"], ["/pms/tasks", "/pms/projects", "/pms/people", "/pms/settings", "/pms/operator"]],
  ]) {
    const nav = roles.getRoleNav("admin", !managed, module);
    for (const to of removed) assert(!nav.some(item => item.to === to), "Unrelated menu link: " + to);
    for (const to of retained) assert(nav.some(item => item.to === common.commonNavigationHref(to, module.slice(1))), "Lost core menu link: " + to);
  }
}
console.log("PMS and CRM menu scope checks passed for role-based and managed access.");
