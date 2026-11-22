import { LoadingState } from "@/components/ui/state";
import { useMobile } from "@/components/mobile/useMobile";
import { isSharedTaskWorkspace } from "@/lib/task-workspace";
import { Suspense, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Navigate, UNSAFE_LocationContext as LocationContext, useLocation, useNavigate } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { canAccessRoute, getRoleNav } from "@/lib/roles";
import { getOperationWorkspace, operationAliases, isStandaloneSrmOperation } from "@/lib/navigation-workspaces";
import { menuLabel } from "@/lib/navigation-menu";
import { commonNavigationHref, commonRouteContext } from "@/lib/common-routes";
import { useAuthStore } from "@/store/authStore";
import ErrorBoundary from "@/components/app/ErrorBoundary";
import { MobileOperationNavigationContext, OperationContentContext, OperationPanelContext, OperationWorkspaceContext } from "@/lib/operation-panel";

/** One page owns the related operations. Each panel renders the original working
 * component (including its API mutations), rather than linking to another page.
 * A scoped router location preserves pathname-dependent legacy behavior. */
export default function OperationsWorkspace({ route, routes }: { route: FrontendRoute; routes: FrontendRoute[] }) {
  const location = useLocation();
  const locationContext = useContext(LocationContext);
  const navigate = useNavigate();
  const user = useAuthStore(state => state.user);
  const pathname = `/${route.path}`;
  const compactNavigation = /^\/(crm|pms|srm)(\/|$)/.test(pathname);
  const workspace = getOperationWorkspace(pathname);
  const [mobileNavigationSlot, setMobileNavigationSlot] = useState<HTMLDivElement | null>(null);
  const nav = getRoleNav(user?.role, user?.is_superuser, pathname);
  const pages = (workspace?.paths || []).flatMap(path => {
    const entry = routes.find(item => `/${item.path}` === path);
    if (!entry || !canAccessRoute(path, user?.role, user?.is_superuser)) return [];
    if (operationAliases[path] && canAccessRoute(operationAliases[path], user?.role, user?.is_superuser)) return [];
    const originalLabel = nav.find(item => (commonRouteContext(item.to)?.nativePath || item.to) === path)?.label || path.split("/").pop()!.replace(/-/g, " ");
    const label = compactNavigation ? menuLabel({to:path,label:originalLabel}) : originalLabel;
    return [{ path, label, element: entry.element }];
  });
  const canonical = pages[0]?.path;
  const sharedContext = commonRouteContext(location.pathname, location.search);
  const canonicalHref = canonical && sharedContext?.module === "srm" ? commonNavigationHref(canonical, "srm") : canonical;
  const requestedPath = new URLSearchParams(location.search).get("operation");
  const requested = requestedPath && (operationAliases[requestedPath] || requestedPath);
  const legacy = operationAliases[pathname] || pathname;
  const selected = pages.find(page => page.path === requested)?.path || pages.find(page => page.path === legacy)?.path || canonical;
  // Retain drafts without broadcasting the active tab's create intent to hidden forms.
  const panelLocations = useRef<Record<string, typeof location>>({});
  if (selected) panelLocations.current[selected] = location;
  const [visited, setVisited] = useState<string[]>(selected ? [selected] : []);
  useEffect(() => { if (selected) setVisited(current => current.includes(selected) ? current : [...current, selected]); }, [selected]);
  const selectedLabel = pages.find(page => page.path === selected)?.label;
  const workspaceLabel = workspace?.label;
  const phone = useMobile(480);
  const operationTabs = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const list = operationTabs.current;
    const tab = list?.querySelector<HTMLElement>('[aria-selected="true"]');
    if (!phone || !list?.clientWidth || !tab) return;
    const bounds = list.getBoundingClientRect();
    const active = tab.getBoundingClientRect();
    if (active.right > bounds.right) list.scrollLeft += active.right - bounds.right;
    else if (active.left < bounds.left) list.scrollLeft -= bounds.left - active.left;
  }, [phone, selected]);
  useEffect(() => {
    if (workspaceLabel && selectedLabel) document.title = `${workspaceLabel} · ${selectedLabel} - Business Suite`;
  }, [workspaceLabel, selectedLabel]);
  if (!workspace || !canonical || !selected) return <>{route.element}</>;
  if(isStandaloneSrmOperation(selected)){
    if(pathname!==selected){
      const params=new URLSearchParams(location.search);params.delete('operation');
      return <Navigate replace to={`${selected}${params.size?`?${params}`:''}${location.hash}`}/>;
    }
    return <ErrorBoundary><Suspense fallback={<LoadingState label={`Loading ${selectedLabel}`} />}><OperationContentContext.Provider value={true}><OperationWorkspaceContext.Provider value={true}>{pages.find(page=>page.path===selected)!.element}</OperationWorkspaceContext.Provider></OperationContentContext.Provider></Suspense></ErrorBoundary>;
  }
  const searchFor = (path: string) => {
    const params = new URLSearchParams(location.search);
    params.delete("operation");
    if (pathname === "/srm/services") params.set("kind", "service");
    if (path !== canonical) params.set("operation", path);
    return params.size ? `?${params}` : "";
  };
  if (pathname !== canonical) return <Navigate replace to={`${canonicalHref!.split("?")[0]}${searchFor(selected)}${location.hash}`} />;
  // The shared task workspace supplies the complete PMS shell itself.
  if (isSharedTaskWorkspace(selected, location.search)) return <ErrorBoundary><Suspense fallback={<LoadingState label="Loading tasks" />}>
    <LocationContext.Provider value={{ ...locationContext, location: { ...location, pathname: selected } }}>
      {pages.find(page => page.path === selected)?.element}
    </LocationContext.Provider>
  </Suspense></ErrorBoundary>;
  const select = (path: string) => {
    setVisited(current => current.includes(path) ? current : [...current, path]);
    navigate({ pathname: canonicalHref!.split("?")[0], search: searchFor(path) });
  };
  const navigation = pages.length > 1 && workspace.label !== "Deals" && <div className={`suite-operation-navigation mb-5 border-b border-border pb-3 ${compactNavigation ? "ws-operation-navigation" : ""}`}>
      {compactNavigation ? <p className="mb-2 text-sm font-medium text-muted-foreground">{workspace.label}</p> : <h1 className="mb-3 text-xl font-semibold">{workspace.label}</h1>}
      <div ref={operationTabs} role="tablist" aria-label={`${workspace.label} operations`} className="flex flex-wrap gap-2">
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
    </div>;
  return <section aria-label={`${workspace.label} workspace`}>
    {mobileNavigationSlot ? createPortal(navigation, mobileNavigationSlot) : navigation}
    {pages.filter(page => visited.includes(page.path) || page.path === selected).map(page => {
      const panelLocation = panelLocations.current[page.path] || location;
      const panelSearch = new URLSearchParams(panelLocation.search);
      if (page.path !== selected) panelSearch.delete("new");
      return <div key={page.path}
      role="tabpanel" hidden={selected !== page.path} id={`operation-panel-${page.path}`} aria-label={workspace.label === "Deals" ? page.label : undefined} aria-labelledby={workspace.label === "Deals" ? undefined : `operation-tab-${page.path}`}>
      <ErrorBoundary><Suspense fallback={<LoadingState label={`Loading ${page.label}`} />}>
        <LocationContext.Provider value={{ ...locationContext, location: { ...panelLocation, pathname: page.path, search: panelSearch.size ? `?${panelSearch}` : "", hash: page.path === selected ? location.hash : "" } }}>
          <MobileOperationNavigationContext.Provider value={canonical === "/srm/inventory" && page.path === selected ? setMobileNavigationSlot : null}><OperationContentContext.Provider value={true}><OperationWorkspaceContext.Provider value={true}><OperationPanelContext.Provider value={!pathname.startsWith("/srm/") || page.path === selected}>{page.element}</OperationPanelContext.Provider></OperationWorkspaceContext.Provider></OperationContentContext.Provider></MobileOperationNavigationContext.Provider>
        </LocationContext.Provider>
      </Suspense></ErrorBoundary>
    </div>; })}
  </section>;
}
