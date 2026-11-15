/** Code-owned destinations. Module context is presentation, never an access grant. */
export const commonModules = ["crm", "pms", "hrms", "srm", "fam"] as const;
export type CommonModule = typeof commonModules[number];
export const commercialEntities = ["quotations", "contracts", "purchase-orders", "sales-orders", "invoices", "invoice-drafts", "billing-plans", "collections", "engagements", "payment-requests"] as const;
export const isCommercialEntity = (entity: string) => (commercialEntities as readonly string[]).includes(entity);
export const commonEntities = {
  quotations: { label: "Quotations", owner: "/crm/quotations", module: "crm", aliases: ["/crm/quotations", "/crm/quotes", "/srm/quotes", "/srm/quotations"] },
  contracts: { label: "Contracts", owner: "/srm/contracts", module: "srm", aliases: ["/srm/contracts", "/crm/contracts"] },
  "purchase-orders": { label: "Purchase orders", owner: "/srm/inventory/purchase-orders", module: "srm", aliases: ["/srm/inventory/purchase-orders", "/crm/purchase-orders"] },
  "sales-orders": { label: "Sales orders", owner: "/srm/sales-orders", module: "srm", aliases: ["/srm/sales-orders", "/crm/sales-orders"] },
  invoices: { label: "Invoices", owner: "/srm/invoices", module: "srm", aliases: ["/srm/invoices", "/crm/invoices"] },
  "invoice-drafts": { label: "Invoice drafts", owner: "/srm/invoice-drafts", module: "srm", aliases: ["/srm/invoice-drafts", "/crm/invoice-drafts"] },
  "billing-plans": { label: "Billing plans", owner: "/srm/billing-plans", module: "srm", aliases: ["/srm/billing-plans", "/crm/billing-plans"] },
  collections: { label: "Collections", owner: "/srm/collections", module: "srm", aliases: ["/srm/collections", "/crm/collections"] },
  engagements: { label: "Engagements", owner: "/srm/engagements", module: "srm", aliases: ["/srm/engagements", "/crm/engagements"] },
  "payment-requests": { label: "Payment requests", owner: "/srm/payment-requests", module: "srm", aliases: ["/srm/payment-requests", "/crm/payment-requests"] },
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
  quotations: ["crm", "srm"], contracts: ["crm", "srm"], "purchase-orders": ["crm", "srm"],
  "sales-orders": ["crm", "srm"], invoices: ["crm", "srm"], "invoice-drafts": ["crm", "srm"],
  "billing-plans": ["crm", "srm"], collections: ["crm", "srm"], engagements: ["crm", "srm"], "payment-requests": ["crm", "srm"],
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
  const match = /^\/common\/([^/]+)(\/.*)?$/.exec(pathname);
  if (!match || !Object.prototype.hasOwnProperty.call(commonEntities, match[1])) return null;
  const entity = match[1] as CommonEntity;
  const definition = commonEntities[entity];
  const suffix = (match[2] || "").replace(/\/$/, "");
  if (suffix && (!isCommercialEntity(entity) || !validCommercialSuffix(entity, suffix))) return null;
  const params = new URLSearchParams(search ?? query ?? currentSearch(pathname));
  const requested = params.get("module") || definition.module;
  if (!commonModules.includes(requested as CommonModule)) return null;
  const module = requested as CommonModule;
  // Reuse source-aware adapters where they already exist, without copying records.
  let nativePath: string = definition.owner;
  if (isCommercialEntity(entity)) {
    nativePath = entity === "quotations" && /\/builder$/.test(suffix) ? `/crm/quotes${suffix}` : definition.owner + suffix;
  }
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
  const [address, hash] = href.split("#");
  const [path, query = ""] = address.split("?");
  const entry = Object.entries(commonEntities).find(([entity, value]) => value.aliases.some(alias => path === alias || (isCommercialEntity(entity) && path.startsWith(alias + "/") && validCommercialSuffix(entity, path.slice(alias.length)))));
  if (!entry) return href;
  const params = new URLSearchParams(query);
  if (path === "/srm/services") params.set("kind", "service");
  const alias = entry[1].aliases.find(alias => path === alias || path.startsWith(alias + "/"))!;
  const suffix = path.slice(alias.length);
  const target = commonPagePath(entry[0] as CommonEntity, module, params.toString()).replace("?", `${suffix}?`);
  return target + (hash ? `#${hash}` : "");
}

function validCommercialSuffix(entity: string, suffix: string) {
  if (!suffix || suffix === "/") return true;
  if (entity === "quotations") return /^\/\d+(\/builder)?$/.test(suffix);
  if (entity === "purchase-orders") return suffix === "/create" || /^\/\d+$/.test(suffix);
  return ["contracts", "sales-orders", "invoices", "billing-plans", "engagements"].includes(entity) && /^\/\d+$/.test(suffix);
}

export function moduleContextPath(pathname: string, search?: string) {
  return commonRouteContext(pathname, search)?.contextPath || pathname;
}
