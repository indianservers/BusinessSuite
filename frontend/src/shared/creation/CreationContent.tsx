import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import type { CreationDefinition } from "./registry";
import type { CatalogSource } from "@/shared/catalog/api";
const Task = lazy(() => import("@/apps/project-management/pages/TaskStudioPage"));
const Project = lazy(() => import("@/apps/project-management/pages/CreateProjectPage"));
const Employee = lazy(() => import("@/apps/hrms/pages/employees/AddEmployeePage"));
const Catalog = lazy(() => import("@/shared/catalog/CatalogEditor"));
const Contact = lazy(() => import("@/apps/crm/CRMWorkspacePage").then(m => ({ default: m.CRMContactQuickCreate })));
const Deal = lazy(() => import("@/apps/crm/CRMWorkspacePage").then(m => ({ default: m.QuickDealDialog })));
const CRM = lazy(() => import("@/apps/crm/SalesActions").then(m => ({ default: m.CRMQuickCreate })));
const Company = lazy(() => import("@/shared/master-data/CompanyEditor").then(m => ({ default: m.CompanyQuickCreate })));
const Commercial = lazy(() => import("@/apps/srm/pages/SRMWorkspacePage").then(m => ({ default: m.CommercialCreateCard })));
const Invoice = lazy(() => import("@/apps/srm/pages/SRMWorkspacePage").then(m => ({ default: m.ManualInvoiceComposer })));

export function CreationContent({ definition, routes, close, complete, busy }: { definition: CreationDefinition; routes: FrontendRoute[]; close: () => void; complete: (record?: unknown, keepOpen?: boolean) => void; busy: (value: boolean) => void }) {
  const location = useLocation();
  const module = location.pathname.split('/')[1];
  const entity = definition.entity;
  const commercialKind = ({ salesOrder: "salesOrders", contract: "contracts", engagement: "engagements", billingPlan: "billingPlans" } as const)[entity as "salesOrder" | "contract" | "engagement" | "billingPlan"];
  let content;
  if (entity === "task") content = <Task draftScope={`smart-create:${location.pathname}${location.search}`} onBusyChange={busy} onClose={close} onCreated={async (task, keepOpen) => complete(task, keepOpen)} />;
  else if (entity === "project") content = <Project onCreated={complete} onCancel={close} />;
  else if (entity === "employee") content = <Employee onCreated={complete} />;
  else if (entity === "catalog") content = <Catalog source={module as CatalogSource} defaultKind={location.pathname.includes("services") && !location.pathname.includes("products-services") ? "service" : "product"} close={close} saved={complete} />;
  else if (["company", "customer", "vendor"].includes(entity) && module !== "fam") content = <Company source={module as "crm" | "srm"} recordLabel={entity} roles={[entity === "vendor" ? "Vendor" : entity === "customer" ? "Customer" : "Prospect"]} defaultEntityKind={entity === "customer" ? "Individual" : "Company"} onClose={close} onSaved={(record, keepOpen) => { if (!keepOpen) complete(record); }} />;
  else if (module === "crm" && entity === "contact") content = <Contact close={close} saved={complete} />;
  else if (module === "crm" && entity === "deal") content = <Deal close={close} saved={complete} />;
  else if (module === "crm" && entity === "lead") content = <CRM direct type={entity} close={close} saved={complete} />;
  else if (commercialKind) content = <Commercial kind={commercialKind} onSaved={complete} />;
  else if (entity === "invoice") content = <Invoice onCreated={complete} onBusyChange={busy} />;
  else content = <div className={definition.presentation === "dialog" ? "smart-create-existing-host" : "smart-create-route"}><Routes>{routes.map(route => <Route key={route.path} path={route.path} element={route.element} />)}</Routes></div>;
  return <Suspense fallback={<p role="status">Loading {entity} form…</p>}>{content}</Suspense>;
}
