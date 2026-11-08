import { lazyRoute } from "@/lib/lazy-route";
const OperationalWorkspaceDirectory = lazyRoute(() => import("@/shared/workspace/OperationalWorkspaceDirectory"));
import React from "react";
const WhatsAppCommunicationPage = lazyRoute(() => import("@/apps/communication/WhatsAppCommunicationPage"));
const ImportWorkspace = lazyRoute(() => import("@/shared/data-transfer/ImportWorkspace"));
import { Navigate } from "react-router-dom";
const FollowUpSummary = lazyRoute(() => import("@/shared/follow-ups/FollowUpSummary"));
const FollowUpsPage = lazyRoute(() => import("@/shared/follow-ups/FollowUpsPage"));
import CentralSettingsRedirect from "@/pages/settings/CentralSettingsRedirect";
const CommunicationWorkspace = lazyRoute(() => import("@/shared/communication/CommunicationWorkspace"));
const Record360Page = lazyRoute(() => import("@/shared/records/Record360Page"));
const PaymentRequestsPage = lazyRoute(() => import("@/shared/payments/PaymentRequestsPage"));
const ModuleGanttPage = lazyRoute(() => import("@/components/scheduling/ModuleGanttPage"));
import type { FrontendRoute } from "@/appRegistry";
import type { SRMViewKind } from "./types";
import type { FAMViewKind } from "@/apps/fam/types";
import { inventorySourceAppPaths } from "@/apps/inventory/sourceCatalog";

const MobileQuotesWorkspace = lazyRoute(() => import("@/components/mobile/MobileQuotesWorkspace"));
const CRMWorkspacePage = lazyRoute(() => import("@/apps/crm/CRMWorkspacePage"));
const SRMWorkspacePage = lazyRoute(() => import("./pages/SRMWorkspacePage"));
const SharedInvoicePage = lazyRoute(() => import("./pages/SharedInvoicePage"));
const SRMCommercialDetailPage = lazyRoute(() => import("./pages/SRMCommercialDetailPage"));
const SRMPOSPage = lazyRoute(() => import("./pages/SRMPOSPage"));
const FAMWorkspacePage = lazyRoute(() => import("@/apps/fam/FAMWorkspacePage"));
const InventoryBridgePage = lazyRoute(() => import("@/apps/inventory/InventoryBridgePage"));
const ModuleProfilePage = lazyRoute(() => import("@/pages/ModuleProfilePage"));
const CatalogPage = lazyRoute(() => import("@/shared/catalog/CatalogPage"));

const route = (path: string, kind: SRMViewKind): FrontendRoute => ({
  path,
  element: <>{kind === "dashboard" && <FollowUpSummary base="/srm/follow-ups"/>}<SRMWorkspacePage kind={kind} /></>,
});

const inventoryRoute = (path: string, kind: FAMViewKind): FrontendRoute => ({
  path,
  element: <FAMWorkspacePage kind={kind} />,
});

const inventorySourceRoute = (path: string): FrontendRoute => ({
  path,
  element: <InventoryBridgePage />,
});

const CompaniesPage = lazyRoute(()=>import("@/shared/master-data/CompaniesPage"));
export const srmRoutes: FrontendRoute[] = [
  { path: "srm/workspaces", element: <OperationalWorkspaceDirectory module="srm" /> },
  { path: "srm/whatsapp-communication", element: <WhatsAppCommunicationPage /> },
  {path:"srm/import-data",element:<ImportWorkspace module="srm"/>},
 {path:"srm/customers/:id/360",element:<Record360Page/>},
 {path:"srm/payment-requests",element:<PaymentRequestsPage/>},
 {path:"srm/customers",element:<CompaniesPage source="srm" role="Customer"/>},
 {path:"srm/vendors",element:<CompaniesPage source="srm" role="Vendor"/>},
 {path:"srm/suppliers",element:<Navigate to="/srm/vendors" replace/>},
 {path:"srm/companies",element:<CompaniesPage source="srm"/>},
 {path:"srm/quotes",element:<MobileQuotesWorkspace/>},
 {path:"srm/quotes/:id/builder",element:<CRMWorkspacePage kind="quoteBuilder"/>},
 {path:"srm/follow-ups/directory",element:<FollowUpsPage/>},
 {path:"srm/follow-ups/calendar",element:<FollowUpsPage/>},
 {path:"srm/follow-ups/:id",element:<FollowUpsPage/>},
 {path:"srm/follow-ups",element:<FollowUpsPage/>},
 { path: "srm/messages", element: <CommunicationWorkspace module="Sales" /> },
  { path: "srm/gantt", element: <ModuleGanttPage key="srm" module="srm" /> },
  { path: "srm/inventory/gantt", element: <ModuleGanttPage key="inventory" module="inventory" /> },
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
  { path: "srm/invoices/:id", element: <SharedInvoicePage /> },
  route("srm/collections", "collections"),
  route("srm/revenue-recognition", "revenueRecognition"),
  route("srm/profitability", "profitability"),
  route("srm/customer-360", "customer360"),
  { path: "srm/pos", element: <SRMPOSPage /> },
  ...["srm/products-services", "srm/products", "srm/services", "srm/pos/products"].map(path => ({ path, element: <CatalogPage source="srm" /> })),
  { path: "srm/pos/terminal", element: <SRMPOSPage /> },
  route("srm/pos/sessions", "posSessions"),
  route("srm/pos/cashier-closing", "cashierClosing"),
  route("srm/pos/returns", "posReturns"),
  inventoryRoute("srm/inventory", "inventory"),
  inventoryRoute("srm/inventory/dashboard", "inventoryDashboard"),
  { path: "srm/inventory/items", element: <CatalogPage source="srm" /> },
  inventoryRoute("srm/inventory/items/:id", "inventoryItemDetail"),
  inventoryRoute("srm/inventory/items/:id/ledger-mapping", "inventoryLedgerMapping"),
  { path: "srm/inventory/products", element: <CatalogPage source="srm" /> },
  { path: "srm/inventory/products/create", element: <CatalogPage source="srm" /> },
  { path: "srm/inventory/products/import", element: <CatalogPage source="srm" /> },
  { path: "srm/inventory/products/export", element: <CatalogPage source="srm" /> },
  { path: "srm/inventory/products/barcodes", element: <CatalogPage source="srm" /> },
  inventoryRoute("srm/inventory/price-lists", "inventoryPriceLists"),
  inventoryRoute("srm/inventory/stock-groups", "inventoryStockGroups"),
  inventoryRoute("srm/inventory/units", "inventoryUnits"),
  inventoryRoute("srm/inventory/warehouses", "inventoryWarehouses"),
  inventoryRoute("srm/inventory/opening-stock", "inventoryOpeningStock"),
  inventoryRoute("srm/inventory/stock-in", "inventoryStockIn"),
  inventoryRoute("srm/inventory/stock-out", "inventoryStockOut"),
  inventoryRoute("srm/inventory/stock-transfers", "inventoryStockTransfers"),
  inventoryRoute("srm/inventory/stock-adjustments", "inventoryStockAdjustments"),
  inventoryRoute("srm/inventory/purchase-receipts", "inventoryPurchaseReceipts"),
  inventoryRoute("srm/inventory/delivery-notes", "inventoryDeliveryNotes"),
  inventoryRoute("srm/inventory/stock-summary", "inventoryStockSummary"),
  inventoryRoute("srm/inventory/item-ledger/:id", "inventoryItemLedger"),
  inventoryRoute("srm/inventory/warehouse-stock", "inventoryWarehouseStock"),
  inventoryRoute("srm/inventory/stock-aging", "inventoryStockAging"),
  inventoryRoute("srm/inventory/reorder-report", "inventoryReorderReport"),
  inventoryRoute("srm/inventory/dead-stock", "inventoryDeadStock"),
  inventoryRoute("srm/inventory/fast-slow-moving", "inventoryFastSlowMoving"),
  inventoryRoute("srm/inventory/valuation", "inventoryValuation"),
  inventoryRoute("srm/inventory/gross-margin", "inventoryGrossMargin"),
  inventoryRoute("srm/inventory/cogs", "inventoryCogs"),
  inventoryRoute("srm/inventory/reconciliation", "inventoryReconciliation"),
  inventoryRoute("srm/inventory/reconciliation/gl", "inventoryReconciliationGl"),
  inventoryRoute("srm/inventory/reconciliation/grni", "inventoryReconciliationGrni"),
  inventoryRoute("srm/inventory/reconciliation/cogs", "inventoryReconciliationCogs"),
  inventoryRoute("srm/inventory/reconciliation/gst", "inventoryReconciliationGst"),
  inventoryRoute("srm/inventory/reports/cogs", "inventoryCogs"),
  inventoryRoute("srm/inventory/reports/gross-margin", "inventoryGrossMargin"),
  inventoryRoute("srm/inventory/reports/hsn-summary", "inventoryHsnSummary"),
  inventoryRoute("srm/inventory/reports/complete", "inventoryCompleteReports"),
  inventoryRoute("srm/inventory/batches", "inventoryBatches"),
  inventoryRoute("srm/inventory/serial-numbers", "inventoryBatches"),
  inventoryRoute("srm/inventory/purchase-orders", "inventoryPurchaseOrders"),
  inventoryRoute("srm/inventory/purchase-orders/create", "inventoryPurchaseOrders"),
  inventoryRoute("srm/inventory/grn", "inventoryPurchaseOrders"),
  inventoryRoute("srm/inventory/manufacturing", "inventoryManufacturing"),
  inventoryRoute("srm/inventory/manufacturing/bom", "inventoryManufacturing"),
  inventoryRoute("srm/inventory/manufacturing/bom/create", "inventoryManufacturing"),
  inventoryRoute("srm/inventory/manufacturing/orders", "inventoryManufacturing"),
  inventoryRoute("srm/inventory/manufacturing/orders/create", "inventoryManufacturing"),
  inventoryRoute("srm/inventory/audit", "inventoryAudit"),
  inventoryRoute("srm/inventory/reorder-alerts", "inventoryReorderAlerts"),
  inventoryRoute("srm/inventory/reports", "inventoryReports"),
  inventoryRoute("srm/inventory/ai", "inventoryAI"),
  inventorySourceRoute("srm/inventory/source"),
  inventorySourceRoute("srm/sales-inventory/source"),
  ...inventorySourceAppPaths.map((path) => inventorySourceRoute(path.replace(/^\//, ""))),
  route("srm/reports", "reports"),
  { path: "srm/settings", element: <CentralSettingsRedirect section="sales" /> },
];
