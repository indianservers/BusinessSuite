/** Code-owned destinations. Module context is presentation, never an access grant. */
export const commonModules = ["crm", "pms", "hrms", "srm", "fam"] as const;
export type CommonModule = typeof commonModules[number];
export const commonEntities = {
  employees: { label: "Employees", owner: "/hrms/employees", module: "hrms", aliases: ["/hrms/employees"] },
  teams: { label: "Teams", owner: "/pms/teams", module: "pms", aliases: ["/pms/teams"] },
  vendors: { label: "Vendors", owner: "/crm/vendors", module: "crm", aliases: ["/crm/vendors", "/srm/vendors", "/srm/suppliers"] },
  tasks: { label: "Tasks", owner: "/pms/tasks", module: "pms", aliases: ["/pms/tasks", "/crm/tasks"] },
  notes: { label: "Notes", owner: "/pms/notes", module: "pms", aliases: ["/pms/notes"] },
  contacts: { label: "Contacts", owner: "/crm/contacts", module: "crm", aliases: ["/crm/contacts"] },
  customers: { label: "Customers", owner: "/crm/customers", module: "crm", aliases: ["/crm/customers", "/srm/customers"] },
  leads: { label: "Leads", owner: "/crm/leads", module: "crm", aliases: ["/crm/leads"] },
  calendar: { label: "Calendar", owner: "/pms/calendar", module: "pms", aliases: ["/pms/calendar"] },
  "follow-ups": { label: "Follow-ups", owner: "/crm/follow-ups", module: "crm", aliases: ["/crm/follow-ups", "/pms/follow-ups", "/srm/follow-ups"] },
  catalog: { label: "Products & services", owner: "/srm/products-services", module: "srm", aliases: ["/crm/products-services", "/pms/products-services", "/srm/products-services", "/srm/products", "/srm/services", "/srm/pos/products", "/srm/inventory/items", "/srm/inventory/products"] },
} as const;
export type CommonEntity = keyof typeof commonEntities;
export const commonEntityModules: Record<CommonEntity, readonly CommonModule[]> = {
  employees: ["hrms", "pms", "crm", "srm"], teams: ["hrms", "pms", "crm", "srm"],
  vendors: ["srm", "crm", "fam", "pms"], tasks: commonModules, notes: commonModules,
  contacts: commonModules, customers: ["crm", "srm", "pms", "fam"], leads: ["crm", "srm"],
  calendar: commonModules, "follow-ups": ["crm", "srm", "pms"], catalog: ["crm", "srm", "pms", "fam"],
};

function currentSearch(pathname: string) {
  return typeof window !== "undefined" && window.location.pathname === pathname ? window.location.search : "";
}

export function commonRouteContext(href: string, search?: string) {
  const [pathname, query] = href.split("?");
  const match = /^\/common\/([^/]+)\/?$/.exec(pathname);
  if (!match || !Object.prototype.hasOwnProperty.call(commonEntities, match[1])) return null;
  const entity = match[1] as CommonEntity;
  const definition = commonEntities[entity];
  const params = new URLSearchParams(search ?? query ?? currentSearch(pathname));
  const requested = params.get("module") || definition.module;
  if (!commonModules.includes(requested as CommonModule)) return null;
  const module = requested as CommonModule;
  // Reuse source-aware adapters where they already exist, without copying records.
  let nativePath: string = definition.owner;
  if ((entity === "customers" || entity === "vendors") && module === "srm") nativePath = `/srm/${entity}`;
  if (entity === "catalog" && ["crm", "pms", "srm"].includes(module)) nativePath = `/${module}/products-services`;
  if (entity === "follow-ups" && ["crm", "pms", "srm"].includes(module)) nativePath = `/${module}/follow-ups`;
  if (entity === "tasks" && module === "crm") nativePath = "/crm/tasks";
  return { entity, definition, module, nativePath, contextPath: `/${module}` };
}

export function commonPagePath(entity: CommonEntity, module: CommonModule, query = "") {
  const params = new URLSearchParams(query);
  params.set("module", module);
  return `/common/${entity}?${params}`;
}

export function commonNavigationHref(href: string, module: CommonModule) {
  const [path, query = ""] = href.split("?");
  const entry = Object.entries(commonEntities).find(([, value]) => (value.aliases as readonly string[]).includes(path));
  if (!entry) return href;
  const params = new URLSearchParams(query);
  if (path === "/srm/services") params.set("kind", "service");
  return commonPagePath(entry[0] as CommonEntity, module, params.toString());
}

export function moduleContextPath(pathname: string, search?: string) {
  return commonRouteContext(pathname, search)?.contextPath || pathname;
}
