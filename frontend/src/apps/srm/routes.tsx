import React from "react";
import type { FrontendRoute } from "@/appRegistry";
import type { SRMViewKind } from "./types";

const SRMWorkspacePage = React.lazy(() => import("./pages/SRMWorkspacePage"));
const SRMCommercialDetailPage = React.lazy(() => import("./pages/SRMCommercialDetailPage"));
const ModuleProfilePage = React.lazy(() => import("@/pages/ModuleProfilePage"));

const route = (path: string, kind: SRMViewKind): FrontendRoute => ({
  path,
  element: <SRMWorkspacePage kind={kind} />,
});

export const srmRoutes: FrontendRoute[] = [
  route("srm", "dashboard"),
  route("srm/dashboard", "dashboard"),
  { path: "srm/profile", element: <ModuleProfilePage /> },
  route("srm/sales-orders", "salesOrders"),
  { path: "srm/sales-orders/:id", element: <SRMCommercialDetailPage kind="salesOrder" /> },
  route("srm/contracts", "contracts"),
  { path: "srm/contracts/:id", element: <SRMCommercialDetailPage kind="contract" /> },
  route("srm/engagements", "engagements"),
  { path: "srm/engagements/:id", element: <SRMCommercialDetailPage kind="engagement" /> },
  route("srm/billing-plans", "billingPlans"),
  { path: "srm/billing-plans/:id", element: <SRMCommercialDetailPage kind="billingPlan" /> },
  route("srm/invoice-drafts", "invoiceDrafts"),
  route("srm/invoices", "invoices"),
  route("srm/collections", "collections"),
  route("srm/revenue-recognition", "revenueRecognition"),
  route("srm/profitability", "profitability"),
  route("srm/customer-360", "customer360"),
  route("srm/reports", "reports"),
  route("srm/settings", "settings"),
];
