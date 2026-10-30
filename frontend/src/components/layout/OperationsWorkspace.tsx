import { Suspense, useContext, useEffect, useState } from "react";
import { Navigate, UNSAFE_LocationContext as LocationContext, useLocation, useNavigate } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { canAccessRoute, getRoleNav } from "@/lib/roles";
import { getOperationWorkspace, operationAliases } from "@/lib/navigation-workspaces";
import { useAuthStore } from "@/store/authStore";
import ErrorBoundary from "@/components/app/ErrorBoundary";

/** One page owns the related operations. Each panel renders the original working
 * component (including its API mutations), rather than linking to another page.
 * A scoped router location preserves pathname-dependent legacy behavior. */
export default function OperationsWorkspace({ route, routes }: { route: FrontendRoute; routes: FrontendRoute[] }) {
  const location = useLocation();
  const locationContext = useContext(LocationContext);
  const navigate = useNavigate();
  const user = useAuthStore(state => state.user);
  const pathname = `/${route.path}`;
  const workspace = getOperationWorkspace(pathname);
  const nav = getRoleNav(user?.role, user?.is_superuser, pathname);
  const pages = (workspace?.paths || []).flatMap(path => {
    const entry = routes.find(item => `/${item.path}` === path);
    if (!entry || !canAccessRoute(path, user?.role, user?.is_superuser)) return [];
    if (operationAliases[path] && canAccessRoute(operationAliases[path], user?.role, user?.is_superuser)) return [];
    const label = nav.find(item => item.to === path)?.label || path.split("/").pop()!.replace(/-/g, " ");
    return [{ path, label, element: entry.element }];
  });
  const canonical = pages[0]?.path;
  const requested = new URLSearchParams(location.search).get("operation");
  const legacy = operationAliases[pathname] || pathname;
  const selected = pages.find(page => page.path === requested)?.path || pages.find(page => page.path === legacy)?.path || canonical;
  const [visited, setVisited] = useState<string[]>(selected ? [selected] : []);
  useEffect(() => { if (selected) setVisited(current => current.includes(selected) ? current : [...current, selected]); }, [selected]);
  const selectedLabel = pages.find(page => page.path === selected)?.label;
  const workspaceLabel = workspace?.label;
  useEffect(() => {
    if (workspaceLabel && selectedLabel) document.title = `${workspaceLabel} · ${selectedLabel} - Business Suite`;
  }, [workspaceLabel, selectedLabel]);
  if (!workspace || !canonical || !selected) return <>{route.element}</>;
  const searchFor = (path: string) => {
    const params = new URLSearchParams(location.search);
    params.delete("operation");
    if (path !== canonical) params.set("operation", path);
    return params.size ? `?${params}` : "";
  };
  if (pathname !== canonical) return <Navigate replace to={`${canonical}${searchFor(selected)}`} />;
  const select = (path: string) => {
    setVisited(current => current.includes(path) ? current : [...current, path]);
    navigate({ pathname: canonical, search: searchFor(path) });
  };
  return <section aria-label={`${workspace.label} workspace`}>
    {pages.length > 1 && <div className="mb-5 border-b border-border pb-3">
      <h1 className="mb-3 text-xl font-semibold">{workspace.label}</h1>
      <div role="tablist" aria-label={`${workspace.label} operations`} className="flex flex-wrap gap-2">
        {pages.map(page => <button key={page.path} id={`operation-tab-${page.path}`} type="button" role="tab"
          aria-selected={selected === page.path} aria-controls={`operation-panel-${page.path}`}
          tabIndex={selected === page.path ? 0 : -1}
          onKeyDown={event => {
            const index = pages.findIndex(item => item.path === page.path);
            const next = event.key === "ArrowRight" ? (index + 1) % pages.length : event.key === "ArrowLeft" ? (index + pages.length - 1) % pages.length : event.key === "Home" ? 0 : event.key === "End" ? pages.length - 1 : -1;
            if (next < 0) return;
            event.preventDefault(); select(pages[next].path);
            document.getElementById(`operation-tab-${pages[next].path}`)?.focus();
          }} onClick={() => select(page.path)}
          className={`rounded-md px-3 py-2 text-sm capitalize focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${selected === page.path ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}
        >{page.label}</button>)}
      </div>
    </div>}
    {pages.filter(page => visited.includes(page.path) || page.path === selected).map(page => <div key={page.path}
      role="tabpanel" hidden={selected !== page.path} id={`operation-panel-${page.path}`} aria-labelledby={`operation-tab-${page.path}`}>
      <ErrorBoundary><Suspense fallback={<p role="status">Loading {page.label}…</p>}>
        <LocationContext.Provider value={{ ...locationContext, location: { ...location, pathname: page.path } }}>
          {page.element}
        </LocationContext.Provider>
      </Suspense></ErrorBoundary>
    </div>)}
  </section>;
}
