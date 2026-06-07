import { ExternalLink, Package, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const canonicalPath = "C:\\Indian Servers\\AI Inventory Management Software";
const clonedPath = "backend/app/apps/inventory/vyapara_erp";

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
          <Button asChild variant="outline">
            <a href="/inventory/dashboard">
              <ExternalLink className="h-4 w-4" />
              Inventory bridge
            </a>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
