import { Link, useLocation } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { commonRouteContext } from "@/lib/common-routes";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";

/** Mount the registered page itself: no secondary persistence or module-specific copies. */
export default function CommonEntityPage({ routes }: { routes: FrontendRoute[] }) {
  const location = useLocation();
  const user = useAuthStore(state => state.user);
  const context = commonRouteContext(location.pathname, location.search);
  if (!context || !canAccessRoute(location.pathname + location.search, user?.role, user?.is_superuser)) {
    return <p role="alert" className="p-6">This shared page is unavailable or you do not have access.</p>;
  }
  const route = routes.find(item => `/${item.path}` === context.nativePath);
  if (!route) return <p role="alert" className="p-6">The module providing this shared page is not installed.</p>;
  return <>
    <nav aria-label="Shared page breadcrumbs" className="flex items-center gap-2 border-b px-4 py-2 text-sm">
      <Link className="text-primary" to={context.contextPath}>{context.module === "srm" ? "Sales & POS" : context.module.toUpperCase()}</Link>
      <span aria-hidden="true">/</span><span aria-current="page">{context.definition.label}</span>
    </nav>
    {route.element}
  </>;
}
