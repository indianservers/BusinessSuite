import { createPath, type To } from "react-router-dom";

export type CreationDefinition = { entity: string; title: string; presentation: "page" | "dialog"; size: "compact" | "standard" | "large"; };
const pages: Record<string, CreationDefinition> = {
  "/pms/tasks/new": { entity: "task", title: "Create task", presentation: "page", size: "large" },
  "/pms/projects/new": { entity: "project", title: "Create project", presentation: "page", size: "large" },
  "/hrms/employees/new": { entity: "employee", title: "Create employee", presentation: "page", size: "large" },
  "/fam/vouchers/new": { entity: "voucher", title: "Create voucher", presentation: "page", size: "large" },
  "/fam/purchase-bills/new": { entity: "purchase", title: "Create purchase bill", presentation: "page", size: "large" },
  "/fam/expenses/new": { entity: "expense", title: "Create expense", presentation: "page", size: "standard" },
  "/srm/inventory/products/create": { entity: "catalog", title: "Create product", presentation: "dialog", size: "large" },
  "/srm/inventory/purchase-orders/create": { entity: "purchaseOrder", title: "Create purchase order", presentation: "page", size: "large" },
  "/srm/inventory/manufacturing/bom/create": { entity: "billOfMaterials", title: "Create bill of materials", presentation: "page", size: "large" },
  "/srm/inventory/manufacturing/orders/create": { entity: "productionOrder", title: "Create production order", presentation: "page", size: "large" },
  "/power-apps/automations/new": { entity: "automation", title: "Create automation", presentation: "page", size: "large" },
};
const intents: Record<string, string> = {
  "/crm/leads": "lead", "/crm/potential-clients": "lead", "/crm/leads/workbench": "lead",
  "/crm/contacts": "contact", "/crm/companies": "company", "/crm/accounts": "customer", "/crm/customers": "customer", "/crm/vendors": "vendor",
  "/crm/deals": "deal", "/crm/tasks": "task", "/crm/activities": "activity", "/crm/tickets": "ticket",
  "/crm/quotes": "quote", "/crm/quotations": "quotation", "/crm/price-books": "priceBook",
  "/crm/products": "catalog", "/crm/services": "catalog", "/crm/products-services": "catalog",
  "/pms/products": "catalog", "/pms/products-services": "catalog",
  "/srm/products": "catalog", "/srm/services": "catalog", "/srm/products-services": "catalog", "/srm/inventory/products": "catalog", "/srm/inventory/items": "catalog",
  "/srm/customers": "customer", "/srm/vendors": "vendor", "/hrms/helpdesk": "ticket", "/hrms/leave": "leave",
  "/pms/workspaces": "workspace",
  "/crm/workspaces": "workspace", "/hrms/workspaces": "workspace", "/srm/workspaces": "workspace", "/fam/workspaces": "workspace",
  "/pms/notes": "note",
  "/crm/campaigns": "campaign",
  "/analytics/scheduled-reports": "reportSchedule",
  "/analytics/report-builder": "report",
  "/hrms/letters-certificates": "letter",
  "/crm/emails": "email",
  "/admin/customization/fields": "customField",
  "/admin/customization/modules": "customModule",
  "/admin/customization/buttons": "recordAction",
  "/admin/customization/validation-rules": "validationRule",
  "/admin/customization/related-lists": "relatedList",
  "/admin/customization/layouts": "layout",
  "/admin/customization/views": "savedView",
  "/admin/customization/kanban": "kanbanBoard",
  "/admin/customization/picklists": "picklist",
};
const commercial: Record<string, string> = {
  "/srm/sales-orders": "salesOrder", "/srm/contracts": "contract", "/srm/engagements": "engagement", "/srm/billing-plans": "billingPlan",
  "/srm/invoice-drafts": "invoice", "/srm/invoices": "invoice", "/hrms/assets": "asset", "/fam/customers": "customer", "/fam/vendors": "vendor",
};

/** Only explicitly supported creation intents are intercepted. Edit/view/designer URLs are untouched. */
export function creationDefinition(destination: string): CreationDefinition | undefined {
  const url = new URL(destination, "http://suite.local");
  if (pages[url.pathname]) return pages[url.pathname];
  if (/^\/(pms|crm|hrms|srm|fam)\/forms\/new$/.test(url.pathname)) return { entity: "form", title: "Create form", presentation: "page", size: "large" };
  let entity = url.searchParams.has("new") ? intents[url.pathname] : url.hash === "#new-record" ? commercial[url.pathname] : undefined;
  if (url.pathname === "/pms/workspaces") entity = ({ task: "task", story: "task", bug: "task", project: "project", workspace: "workspace", user: "invitation" } as Record<string, string>)[url.searchParams.get("new") || ""];
  if (!entity) return;
  const hasExistingDialog = (["catalog", "lead", "contact", "company", "customer", "vendor", "deal", "activity", "quote", "quotation", "priceBook", "invitation", "campaign", "reportSchedule", "customField", "customModule", "recordAction", "validationRule", "relatedList", "layout", "savedView", "kanbanBoard", "picklist", "ticket", "leave"].includes(entity)) && !url.pathname.startsWith("/fam");
  return { entity, title: `Create ${entity.replace(/([A-Z])/g, " $1").toLowerCase()}`, presentation: hasExistingDialog ? "dialog" : "page", size: "large" };
}

export function destinationPath(to: To): string { return typeof to === "string" ? to : createPath(to); }

/** Carry only known scope, never arbitrary filters or an unrelated relationship. Explicit target defaults win. */
export function contextualDestination(destination: string, origin: { pathname: string; search: string }): string {
  const target = new URL(destination, "http://suite.local");
  const source = new URLSearchParams(origin.search);
  if (target.pathname === "/pms/workspaces" && ["task", "story", "bug"].includes(target.searchParams.get("new") || "")) {
    const kind = target.searchParams.get("new")!;
    target.pathname = "/pms/tasks/new";
    if (!target.searchParams.has("workType")) target.searchParams.set("workType", kind === "bug" ? "Bug" : kind === "story" ? "Story" : "Task");
    if (target.searchParams.has("project") && !target.searchParams.has("projectId")) target.searchParams.set("projectId", target.searchParams.get("project")!);
    target.searchParams.delete("new"); target.searchParams.delete("project");
  }
  if (target.pathname === "/pms/workspaces" && target.searchParams.get("new") === "project") { target.pathname = "/pms/projects/new"; if (target.searchParams.has("workspace")) target.searchParams.set("workspace_id", target.searchParams.get("workspace")!); target.searchParams.delete("new"); }
  if (target.pathname === "/pms/tasks/new") {
    const project = origin.pathname.match(/^\/pms\/projects\/(\d+)(?:\/|$)/)?.[1] || source.get("projectId") || source.get("project");
    if (project && !target.searchParams.has("projectId")) target.searchParams.set("projectId", project);
    const workspace = source.get("workspace") || source.get("workspace_id");
    if (workspace && !target.searchParams.has("workspace")) target.searchParams.set("workspace", workspace);
  }
  if (target.pathname === "/pms/projects/new") {
    const workspace = source.get("workspace") || source.get("workspace_id");
    if (workspace && !target.searchParams.has("workspace_id")) target.searchParams.set("workspace_id", workspace);
  }
  return target.pathname + target.search + target.hash;
}
