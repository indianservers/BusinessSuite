import {
  BarChart3,
  Boxes,
  Download,
  Factory,
  FileText,
  GitCompareArrows,
  Layers3,
  Package,
  Receipt,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Store,
  Truck,
  Upload,
  type LucideIcon,
} from "lucide-react";

export const inventoryCanonicalPath = "C:\\Indian Servers\\AI Inventory Management Software";
export const inventoryClonedPath = "backend/app/apps/inventory/vyapara_erp";
export const inventorySourceBase = "http://127.0.0.1:5000";

export type InventorySourceFeature = {
  label: string;
  route: string;
  appPath?: string;
  icon: LucideIcon;
  owner: string;
};

export type InventorySourceGroup = {
  title: string;
  features: InventorySourceFeature[];
};

export const inventoryEntryPoints = [
  {
    label: "POS Terminal",
    description: "Open register session, scan/search products, hold bills, split tender, and complete retail sale.",
    to: "/srm/pos/terminal",
    icon: Store,
  },
  {
    label: "Sales Orders",
    description: "Source flow supports backorders, delivery bill creation, invoice conversion, and purchase order generation for shortages.",
    to: "/srm/sales-orders",
    icon: Receipt,
  },
  {
    label: "Inventory Dashboard",
    description: "Stock value, low-stock alerts, and inventory health.",
    to: "/srm/inventory/dashboard",
    icon: BarChart3,
  },
  {
    label: "Items & SKUs",
    description: "Maintain item masters, codes, units, and reorder controls.",
    to: "/srm/inventory/items",
    icon: Package,
  },
  {
    label: "Stock Summary",
    description: "Review warehouse stock, movement, and balances.",
    to: "/srm/inventory/stock-summary",
    icon: Boxes,
  },
  {
    label: "Reconciliation",
    description: "Compare physical stock with system balances.",
    to: "/srm/inventory/reconciliation",
    icon: GitCompareArrows,
  },
];

export const inventorySourceGroups: InventorySourceGroup[] = [
  {
    title: "POS & Counter Sales",
    features: [
      { label: "POS terminal", route: "/pos/terminal", appPath: "/srm/pos/terminal", icon: Store, owner: "POS" },
      { label: "Open register session", route: "/pos/", appPath: "/srm/pos", icon: Store, owner: "POS" },
      { label: "Held bills", route: "/pos/held", appPath: "/srm/pos/held-bills", icon: ShoppingCart, owner: "POS" },
      { label: "POS sessions", route: "/pos/sessions", appPath: "/srm/pos/sessions", icon: FileText, owner: "POS" },
      { label: "Cashier closing report", route: "/reports/cashier-closing", appPath: "/srm/pos/cashier-closing", icon: BarChart3, owner: "Reports" },
      { label: "POS registers", route: "/settings/registers", appPath: "/srm/pos/registers", icon: Settings, owner: "Admin" },
    ],
  },
  {
    title: "Sales Documents",
    features: [
      { label: "Sales invoices", route: "/sales/", appPath: "/srm/sales-inventory/invoices", icon: Receipt, owner: "Sales" },
      { label: "Create sales invoice", route: "/sales/create", appPath: "/srm/sales-inventory/invoices/create", icon: Receipt, owner: "Sales" },
      { label: "Sales orders", route: "/sales/orders", appPath: "/srm/sales-inventory/orders", icon: Receipt, owner: "Sales" },
      { label: "Create sales order", route: "/sales/orders/create", appPath: "/srm/sales-inventory/orders/create", icon: Receipt, owner: "Sales" },
      { label: "Delivery bills", route: "/sales/delivery-bills", appPath: "/srm/sales-inventory/delivery-bills", icon: Truck, owner: "Delivery" },
      { label: "Picklists", route: "/sales/picklists", appPath: "/srm/sales-inventory/picklists", icon: Package, owner: "Fulfilment" },
      { label: "Packages", route: "/sales/packages", appPath: "/srm/sales-inventory/packages", icon: Package, owner: "Fulfilment" },
      { label: "Sales returns", route: "/sales/returns", appPath: "/srm/sales-inventory/returns", icon: Receipt, owner: "Sales" },
      { label: "Quotations", route: "/sales/quotations", appPath: "/srm/sales-inventory/quotations", icon: FileText, owner: "Sales" },
      { label: "Proforma invoices", route: "/sales/proforma", appPath: "/srm/sales-inventory/proforma", icon: FileText, owner: "Sales" },
      { label: "Delivery challans", route: "/sales/challans", appPath: "/srm/sales-inventory/challans", icon: Truck, owner: "Delivery" },
      { label: "Refunds", route: "/sales/refunds", appPath: "/srm/sales-inventory/refunds", icon: Receipt, owner: "Sales" },
    ],
  },
  {
    title: "Product Master",
    features: [
      { label: "Products", route: "/products/", appPath: "/srm/inventory/products", icon: Package, owner: "Inventory" },
      { label: "Create product", route: "/products/create", appPath: "/srm/inventory/products/create", icon: Package, owner: "Inventory" },
      { label: "Import products", route: "/products/import", appPath: "/srm/inventory/products/import", icon: Upload, owner: "Inventory" },
      { label: "Export products", route: "/products/export", appPath: "/srm/inventory/products/export", icon: Download, owner: "Inventory" },
      { label: "Barcode labels", route: "/products/barcode-labels", appPath: "/srm/inventory/products/barcodes", icon: FileText, owner: "Inventory" },
      { label: "Price lists", route: "/price-lists/", appPath: "/srm/inventory/price-lists", icon: Receipt, owner: "Pricing" },
      { label: "Warehouses", route: "/settings/warehouses", appPath: "/srm/inventory/warehouses", icon: Boxes, owner: "Admin" },
      { label: "Branches", route: "/settings/branches", appPath: "/srm/inventory/branches", icon: Layers3, owner: "Admin" },
    ],
  },
  {
    title: "Stock Operations",
    features: [
      { label: "Current stock", route: "/stock/current", appPath: "/srm/inventory/warehouse-stock", icon: Boxes, owner: "Inventory" },
      { label: "Stock ledger", route: "/stock/ledger", appPath: "/srm/inventory/stock-summary", icon: FileText, owner: "Inventory" },
      { label: "Opening stock", route: "/stock/opening-stock", appPath: "/srm/inventory/opening-stock", icon: Upload, owner: "Inventory" },
      { label: "Stock adjustments", route: "/stock/adjustments", appPath: "/srm/inventory/stock-adjustments", icon: GitCompareArrows, owner: "Inventory" },
      { label: "Stock transfers", route: "/stock/transfers", appPath: "/srm/inventory/stock-transfers", icon: GitCompareArrows, owner: "Inventory" },
      { label: "Create stock transfer", route: "/stock/transfers/create", appPath: "/srm/inventory/stock-transfers/create", icon: Truck, owner: "Inventory" },
      { label: "Reorder suggestions", route: "/stock/reorder-suggestions", appPath: "/srm/inventory/reorder-alerts", icon: Boxes, owner: "Inventory" },
      { label: "Batches & expiry", route: "/stock/batches", appPath: "/srm/inventory/batches", icon: ShieldCheck, owner: "Inventory" },
      { label: "Serial numbers", route: "/stock/serial-numbers", appPath: "/srm/inventory/serial-numbers", icon: ShieldCheck, owner: "Inventory" },
      { label: "Composite items", route: "/stock/composite-items", appPath: "/srm/inventory/composite-items", icon: Layers3, owner: "Inventory" },
      { label: "Item repacking", route: "/stock/repacking", appPath: "/srm/inventory/repacking", icon: Package, owner: "Inventory" },
    ],
  },
  {
    title: "Procurement & Manufacturing",
    features: [
      { label: "Purchase orders", route: "/purchase-orders/", appPath: "/srm/inventory/purchase-orders", icon: Receipt, owner: "Procurement" },
      { label: "Create purchase order", route: "/purchase-orders/create", appPath: "/srm/inventory/purchase-orders/create", icon: Receipt, owner: "Procurement" },
      { label: "Create GRN", route: "/grn/create", appPath: "/srm/inventory/grn", icon: Truck, owner: "Procurement" },
      { label: "BOM", route: "/manufacturing/bom/", appPath: "/srm/inventory/manufacturing/bom", icon: Factory, owner: "Manufacturing" },
      { label: "Create BOM", route: "/manufacturing/bom/create", appPath: "/srm/inventory/manufacturing/bom/create", icon: Factory, owner: "Manufacturing" },
      { label: "Manufacturing orders", route: "/manufacturing/orders/", appPath: "/srm/inventory/manufacturing/orders", icon: Factory, owner: "Manufacturing" },
      { label: "Create manufacturing order", route: "/manufacturing/orders/create", appPath: "/srm/inventory/manufacturing/orders/create", icon: Factory, owner: "Manufacturing" },
    ],
  },
  {
    title: "Inventory Reports",
    features: [
      { label: "Reports index", route: "/reports/", appPath: "/srm/inventory/reports/complete", icon: BarChart3, owner: "Reports" },
      { label: "Stock report", route: "/reports/stock", appPath: "/srm/inventory/reports/stock", icon: BarChart3, owner: "Reports" },
      { label: "Low stock", route: "/reports/low-stock", appPath: "/srm/inventory/reports/low-stock", icon: BarChart3, owner: "Reports" },
      { label: "Reorder report", route: "/reports/reorder", appPath: "/srm/inventory/reports/reorder", icon: BarChart3, owner: "Reports" },
      { label: "Valuation", route: "/reports/valuation", appPath: "/srm/inventory/reports/valuation", icon: BarChart3, owner: "Reports" },
      { label: "Expiry report", route: "/reports/expiry", appPath: "/srm/inventory/reports/expiry", icon: ShieldCheck, owner: "Reports" },
      { label: "Inventory ledger", route: "/reports/inventory-ledger", appPath: "/srm/inventory/reports/inventory-ledger", icon: FileText, owner: "Reports" },
      { label: "ABC analysis", route: "/reports/abc-analysis", appPath: "/srm/inventory/reports/abc-analysis", icon: BarChart3, owner: "Reports" },
      { label: "Dead stock", route: "/reports/dead-stock", appPath: "/srm/inventory/reports/dead-stock-source", icon: BarChart3, owner: "Reports" },
      { label: "Stock health", route: "/reports/stock-health", appPath: "/srm/inventory/reports/stock-health", icon: BarChart3, owner: "Reports" },
      { label: "Sales velocity", route: "/reports/sales-velocity", appPath: "/srm/inventory/reports/sales-velocity", icon: BarChart3, owner: "Reports" },
      { label: "Stock summary", route: "/reports/stock-summary", appPath: "/srm/inventory/reports/stock-summary-source", icon: BarChart3, owner: "Reports" },
      { label: "Stock movement", route: "/reports/stock-movement", appPath: "/srm/inventory/reports/stock-movement", icon: BarChart3, owner: "Reports" },
      { label: "Serial number report", route: "/reports/serial-numbers", appPath: "/srm/inventory/reports/serial-numbers", icon: ShieldCheck, owner: "Reports" },
    ],
  },
];

export const inventorySourceFeatures = inventorySourceGroups.flatMap((group) =>
  group.features.map((feature) => ({ ...feature, group: group.title })),
);

export const inventorySourceFeatureCount = inventorySourceFeatures.length;
export const mappedInventorySourceFeatureCount = inventorySourceFeatures.filter((feature) => feature.appPath).length;
export const inventorySourceAppPaths = inventorySourceFeatures
  .map((feature) => feature.appPath)
  .filter((path): path is string => Boolean(path));

export function findInventorySourceFeature(pathname: string) {
  const normalizedPath = pathname.replace(/\/+$/, "") || "/srm/inventory/source";
  return inventorySourceFeatures.find((feature) => feature.appPath === normalizedPath);
}
