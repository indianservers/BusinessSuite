import { Link } from "react-router-dom";
import { BarChart3, Boxes, GitCompareArrows, Package, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const canonicalPath = "C:\\Indian Servers\\AI Inventory Management Software";
const clonedPath = "backend/app/apps/inventory/vyapara_erp";

const entryPoints = [
  {
    label: "Inventory Dashboard",
    description: "Stock value, low-stock alerts, and inventory health.",
    to: "/fam/inventory/dashboard",
    icon: BarChart3,
  },
  {
    label: "Items & SKUs",
    description: "Maintain item masters, codes, units, and reorder controls.",
    to: "/fam/inventory/items",
    icon: Package,
  },
  {
    label: "Stock Summary",
    description: "Review warehouse stock, movement, and balances.",
    to: "/fam/inventory/stock-summary",
    icon: Boxes,
  },
  {
    label: "Reconciliation",
    description: "Compare physical stock with system balances.",
    to: "/fam/inventory/reconciliation",
    icon: GitCompareArrows,
  },
];

export default function InventoryBridgePage() {
  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Package className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
            <p className="text-sm text-muted-foreground">Vyapara ERP inventory is cloned here and kept as the source implementation.</p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4" />
            Cloned Inventory Source
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p>
            Inventory is not recreated in React/FastAPI. The existing Flask/MySQL Vyapara ERP source has been cloned into Business Suite for controlled integration.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border p-3">
              <p className="text-xs font-medium uppercase text-muted-foreground">Canonical source</p>
              <p className="mt-1 break-all font-mono text-xs">{canonicalPath}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs font-medium uppercase text-muted-foreground">Business Suite clone</p>
              <p className="mt-1 break-all font-mono text-xs">{clonedPath}</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {entryPoints.map((entry) => {
              const Icon = entry.icon;
              return (
                <Link
                  key={entry.to}
                  to={entry.to}
                  className="rounded-lg border p-3 transition-colors hover:border-primary/50 hover:bg-muted/60"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>
                      <span className="block font-medium text-foreground">{entry.label}</span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">{entry.description}</span>
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
          <Button asChild variant="outline">
            <Link to="/fam/inventory/dashboard">Open stock dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
