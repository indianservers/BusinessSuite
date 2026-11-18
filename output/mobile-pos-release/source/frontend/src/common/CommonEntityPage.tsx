import { Link, Navigate, useLocation } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { commonNavigationHref, commonRouteContext, isCommercialEntity } from "@/lib/common-routes";
import CommonCommercialPage from "./CommonCommercialPage";
import CommercialDocumentTools from "./CommercialDocumentTools";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { getOperationWorkspace } from "@/lib/navigation-workspaces";
import OperationsWorkspace from "@/components/layout/OperationsWorkspace";

/** Mount the registered page itself: no secondary persistence or module-specific copies. */
export default function CommonEntityPage({ routes }: { routes: FrontendRoute[] }) {
  const location = useLocation();
  const user = useAuthStore(state => state.user);
  const context = commonRouteContext(location.pathname, location.search);
  if (!context || !canAccessRoute(location.pathname + location.search, user?.role, user?.is_superuser)) {
    return <p role="alert" className="p-6">This shared page is unavailable or you do not have access.</p>;
  }
  const commercial = isCommercialEntity(context.entity);
  // Old grouped-menu links select an operation in the query string. Resolve
  // those to the shared manager itself, so both modules open the same page.
  const operation = new URLSearchParams(location.search).get('operation');
  if (commercial && operation && getOperationWorkspace(context.nativePath)?.paths.includes(operation)) {
    const target = commonNavigationHref(operation, context.module);
    if (commonRouteContext(target)) {
      const params = new URLSearchParams(location.search);
      params.delete('operation');
      params.set('module', context.module);
      return <Navigate replace to={`${target.split('?')[0]}?${params}${location.hash}`}/>;
    }
  }
  const route = routes.find(item => `/${item.path}` === (commercial ? context.definition.owner : context.nativePath));
  if (!route) return <p role="alert" className="p-6">The module providing this shared page is not installed.</p>;
  // Commercial managers must render the identical registered page in both
  // modules. A Sales-only OperationsWorkspace changes routes and hides archives.
  return <>
    <nav aria-label="Shared page breadcrumbs" className="flex items-center gap-2 border-b px-4 py-2 text-sm">
      <Link className="text-primary" to={context.contextPath}>{context.module === "srm" ? "Sales & POS" : context.module.toUpperCase()}</Link>
      <span aria-hidden="true">/</span><span aria-current="page">{context.definition.label}</span>
    </nav>
    {commercial ? <CommercialDocumentTools context={context}><CommonCommercialPage routes={routes} nativePath={context.nativePath} module={context.module} /></CommercialDocumentTools> : context.module === "srm" && getOperationWorkspace(context.nativePath)
      ? <OperationsWorkspace key={context.nativePath} route={route} routes={routes} />
      : route.element}
  </>;
}
