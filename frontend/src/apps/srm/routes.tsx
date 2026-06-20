import React from "react";
import type { FrontendRoute } from "@/appRegistry";
import type { SRMViewKind } from "./types";
import type { FAMViewKind } from "@/apps/fam/types";
import { inventorySourceAppPaths } from "@/apps/inventory/sourceCatalog";

const SRMWorkspacePage = React.lazy(() => import("./pages/SRMWorkspacePage"));
const SRMCommercialDetailPage = React.lazy(() => import("./pages/SRMCommercialDetailPage"));
const SRMPOSPage = React.lazy(() => import("./pages/SRMPOSPage"));
const FAMWorkspacePage = React.lazy(() => import("@/apps/fam/FAMWorkspacePage"));
const InventoryBridgePage = React.lazy(() => import("@/apps/inventory/InventoryBridgePage"));
const ModuleProfilePage = React.lazy(() => import("@/pages/ModuleProfilePage"));

const route = (path: string, kind: SRMViewKind): FrontendRoute => ({
  path,
  element: <SRMWorkspacePage kind={kind} />,
});

const inventoryRoute = (path: string, kind: FAMViewKind): FrontendRoute => ({
  path,
  element: <FAMWorkspacePage kind={kind} />,
});

const inventorySourceRoute = (path: string): FrontendRoute => ({
  path,
  element: <InventoryBridgePage />,
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
  { path: "srm/pos", element: <SRMPOSPage /> },
  { path: "srm/pos/terminal", element: <SRMPOSPage /> },
  route("srm/pos/sessions", "posSessions"),
  route("srm/pos/cashier-closing", "cashierClosing"),
  route("srm/pos/returns", "posReturns"),
  inventoryRoute("srm/inventory", "inventory"),
  inventoryRoute("srm/inventory/dashboard", "inventoryDashboard"),
  inventoryRoute("srm/inventory/items", "inventoryItems"),
  inventoryRoute("srm/inventory/items/:id", "inventoryItemDetail"),
  inventoryRoute("srm/inventory/items/:id/ledger-mapping", "inventoryLedgerMapping"),
  inventoryRoute("srm/inventory/products", "inventoryProducts"),
  inventoryRoute("srm/inventory/products/create", "inventoryProducts"),
  inventoryRoute("srm/inventory/products/import", "inventoryProducts"),
  inventoryRoute("srm/inventory/products/export", "inventoryProducts"),
  inventoryRoute("srm/inventory/products/barcodes", "inventoryProducts"),
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
  route("srm/settings", "settings"),
];
