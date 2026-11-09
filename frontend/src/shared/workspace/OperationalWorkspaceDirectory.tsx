import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { useWorkspaceOverview } from "./useWorkspaceOverview";
import { operationalWorkspaceDefinitions, workspaceDomainViewIds as viewIds, type WorkspaceDomainModule } from "./workspace-domains";
import ManagedWorkspaceDirectory from "./ManagedWorkspaceDirectory";
export default function OperationalWorkspaceDirectory({ module }: { module: WorkspaceDomainModule }) {
  const user = useAuthStore(state => state.user);
  const definition = operationalWorkspaceDefinitions[module];
  const overview = useWorkspaceOverview(module);
  const allowed = (path: string) => canAccessRoute(path.split(/[?#]/)[0], user?.role, user?.is_superuser);
  const grant = user?.access?.grants[module];
  const actions = definition.actions.filter(action => allowed(action.href) && (!/[?&]new=|\/new$/.test(action.href) || user?.is_superuser || !grant || grant.enabled && grant.actions.includes("create")));
  const views = definition.domains.map((domain, index) => ({ id: viewIds[module][index], label: domain.name, href: domain.path, icon: domain.icon, description: domain.description })).filter(view => allowed(view.href));
  return <ManagedWorkspaceDirectory module={module} title={definition.title} description={definition.description} icon={definition.icon} views={views} actions={actions} metrics={overview.metrics}>{overview.loading && <p role="status" className="wd-notice">Updating {module.toUpperCase()} summary…</p>}{overview.error && <p role="status" className="wd-notice">Branch summary could not load.<Button variant="ghost" size="sm" onClick={overview.retry}>Retry summary</Button></p>}</ManagedWorkspaceDirectory>;
}
