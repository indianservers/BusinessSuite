import { Link, useLocation } from "react-router-dom";
import { Package, ShieldCheck, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  findInventorySourceFeature,
  inventoryCanonicalPath,
  inventoryClonedPath,
  inventoryEntryPoints,
  inventorySourceBase,
  inventorySourceFeatureCount,
  inventorySourceGroups,
  mappedInventorySourceFeatureCount,
} from "./sourceCatalog";

export default function InventoryBridgePage() {
  const location = useLocation();
  const selectedFeature = findInventorySourceFeature(location.pathname);
  const SelectedIcon = selectedFeature?.icon;

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Package className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sales & Inventory Source</h1>
            <p className="text-sm text-muted-foreground">Vyapara ERP inventory and POS are folded into Sales & Inventory as the source implementation.</p>
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
            Sales inventory and POS are reused from the existing Flask/MySQL Vyapara ERP source. Business Suite keeps one Sales & Inventory module and maps the source capabilities into SRM instead of duplicating features.
          </p>
          <p className="text-xs text-muted-foreground">
            {inventorySourceFeatureCount} source-backed inventory, sales, POS, procurement, manufacturing, and reporting entry points are available from this catalogue; {mappedInventorySourceFeatureCount} are mapped to Business Suite routes.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border p-3">
              <p className="text-xs font-medium uppercase text-muted-foreground">Canonical source</p>
              <p className="mt-1 break-all font-mono text-xs">{inventoryCanonicalPath}</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs font-medium uppercase text-muted-foreground">Business Suite clone</p>
              <p className="mt-1 break-all font-mono text-xs">{inventoryClonedPath}</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {inventoryEntryPoints.map((entry) => {
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
            <Link to="/srm/inventory/dashboard">Open stock dashboard</Link>
          </Button>
        </CardContent>
      </Card>

      {selectedFeature && SelectedIcon ? (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <SelectedIcon className="h-4 w-4" />
              {selectedFeature.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border bg-background p-3">
                <p className="text-xs font-medium uppercase text-muted-foreground">Business Suite route</p>
                <p className="mt-1 break-all font-mono text-xs">{selectedFeature.appPath}</p>
              </div>
              <div className="rounded-lg border bg-background p-3">
                <p className="text-xs font-medium uppercase text-muted-foreground">Source route</p>
                <p className="mt-1 break-all font-mono text-xs">{selectedFeature.route}</p>
              </div>
              <div className="rounded-lg border bg-background p-3">
                <p className="text-xs font-medium uppercase text-muted-foreground">Area</p>
                <p className="mt-1 text-sm font-medium">{selectedFeature.group} / {selectedFeature.owner}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <a href={`${inventorySourceBase}${selectedFeature.route}`} target="_blank" rel="noreferrer">
                  Open source function
                </a>
              </Button>
              <Button asChild variant="outline">
                <Link to="/srm/inventory/source">View complete source map</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Store className="h-4 w-4" />
            Complete Source Sales, Inventory & POS Map
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {inventorySourceGroups.map((group) => (
            <div key={group.title} className="space-y-3">
              <h2 className="text-sm font-semibold">{group.title}</h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {group.features.map((feature) => {
                  const Icon = feature.icon;
                  const content = (
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span>
                        <span className="block font-medium text-foreground">{feature.label}</span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {feature.appPath ? "Business Suite mapped route" : `${feature.owner} source route`}
                        </span>
                        <span className="mt-1 block break-all font-mono text-[10px] text-muted-foreground">{feature.appPath ?? feature.route}</span>
                      </span>
                    </div>
                  );
                  return feature.appPath ? (
                    <Link
                      key={`${group.title}-${feature.route}`}
                      to={feature.appPath}
                      className="rounded-lg border p-3 transition-colors hover:border-primary/50 hover:bg-muted/60"
                    >
                      {content}
                    </Link>
                  ) : (
                    <a
                      key={`${group.title}-${feature.route}`}
                      href={`${inventorySourceBase}${feature.route}`}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border p-3 transition-colors hover:border-primary/50 hover:bg-muted/60"
                    >
                      {content}
                    </a>
                  );
                })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}
