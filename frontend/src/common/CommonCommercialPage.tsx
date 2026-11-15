import { useContext, useMemo } from "react";
import { Route, Routes, UNSAFE_NavigationContext as NavigationContext, UNSAFE_RouteContext as RouteContext, useLocation, createPath, type To } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { commonNavigationHref, type CommonModule } from "@/lib/common-routes";
import { OperationContentContext, OperationWorkspaceContext } from "@/lib/operation-panel";

/** Render the registered manager and its detail routes under a shared URL.
 * Links and imperative navigation retain the originating module throughout the lifecycle. */
export default function CommonCommercialPage({ routes, nativePath, module }: { routes: FrontendRoute[]; nativePath: string; module: CommonModule }) {
  const location = useLocation();
  const navigation = useContext(NavigationContext);
  const scopedNavigation = useMemo(() => {
    const destination = (to: To) => {
      const href = typeof to === "string" ? to : createPath(to);
      return commonNavigationHref(href, module);
    };
    return { ...navigation, navigator: {
      ...navigation.navigator,
      createHref: (to: To) => navigation.navigator.createHref(destination(to)),
      push: (to: To, state?: unknown, options?: { preventScrollReset?: boolean }) => navigation.navigator.push(destination(to), state, options),
      replace: (to: To, state?: unknown, options?: { preventScrollReset?: boolean }) => navigation.navigator.replace(destination(to), state, options),
    } };
  }, [navigation, module]);
  // The inner route match supplies the original manager's params and pathname.
  // The outer app shell keeps the shared URL and selected module.
  // This host already selects the manager; native grouped operation routing
  // must not replace it with another commercial page.
  return <NavigationContext.Provider value={scopedNavigation}>
    <RouteContext.Provider value={{ outlet: null, matches: [], isDataRoute: false }}>
      <OperationWorkspaceContext.Provider value={true}><OperationContentContext.Provider value={true}><Routes key={nativePath} location={{ ...location, pathname: nativePath }}>
        {routes.map(route => <Route key={route.path} path={route.path} element={route.element} />)}
        <Route path="*" element={<p role="alert">This commercial page is unavailable.</p>} />
      </Routes></OperationContentContext.Provider></OperationWorkspaceContext.Provider>
    </RouteContext.Provider>
  </NavigationContext.Provider>;
}
