import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { WorkspaceDirectory, type DirectoryEntry } from "./WorkspaceDirectory";
import { WorkspaceModuleLinks } from "./WorkspaceModuleLinks";
import { useWorkspaceOverview } from "./useWorkspaceOverview";
import { operationalWorkspaceDefinitions, type WorkspaceDomainModule as Module } from "./workspace-domains";

export default function OperationalWorkspaceDirectory({ module }: { module: Module }) {
  const user = useAuthStore(s => s.user);
  const definition = operationalWorkspaceDefinitions[module];
  const overview = useWorkspaceOverview(module);
  const allowed = (path: string) => canAccessRoute(path.split(/[?#]/)[0], user?.role, user?.is_superuser);
  const metricPaths: Record<Module, string[]> = { crm: ["/crm/leads", "/crm/deals", "/crm/follow-ups"], hrms: ["/hrms/employees", "/hrms/approval-os", "/hrms/attendance"], srm: ["/srm/sales-orders", "/srm/sales-orders", "/srm/invoices"], fam: ["/fam/journal", "/fam/journal", "/fam/chart-of-accounts"] };
  const factsFor = (path: string) => overview.metrics.flatMap(metric => {
    // Match by label: absent metrics must not slide onto another domain's card.
    const labels = { crm: ["Leads", "Open deals", "Overdue activities"], hrms: ["Employees in scope", "Pending approvals", "Open punches today"], srm: ["Sales orders · all time", "Pending approvals", "Approved invoices"], fam: ["Financial year", "Books status", "Base currency"] }[module];
    return metricPaths[module][labels.indexOf(metric.label)] === path ? [{ label: metric.label.toLowerCase(), value: metric.value }] : [];
  });
  const entries: DirectoryEntry[] = definition.domains.filter(domain => allowed(domain.path)).map(domain => ({ id: domain.path, name: domain.name, description: domain.description, href: domain.path, category: domain.category, icon: domain.icon, facts: factsFor(domain.path) }));
  const actions = definition.actions.filter(action => {
    if (!allowed(action.href)) return false;
    const grant = user?.access?.grants[module];
    const creates = /[?&]new=|\/new$/.test(action.href);
    return !creates || user?.is_superuser || !grant || grant.enabled && grant.actions.includes("create");
  });
  return <WorkspaceDirectory module={module} title={definition.title} description={definition.description} icon={definition.icon} entries={entries} actions={actions} notice={definition.notice} metrics={overview.metrics}>{overview.loading && <p role="status" className="mt-3 text-xs text-muted-foreground">Updating {module === "hrms" ? "people" : module === "srm" ? "sales" : module === "fam" ? "accounting" : "sales pipeline"} summary…</p>}{overview.error && <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground" role="status">Summary could not load for your current access.<Button variant="ghost" size="sm" onClick={overview.retry}>Retry summary</Button></div>}<WorkspaceModuleLinks current={module} /></WorkspaceDirectory>;
}
