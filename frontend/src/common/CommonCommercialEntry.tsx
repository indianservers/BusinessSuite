import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { commonNavigationHref, commonRouteContext, isCommercialEntity } from "@/lib/common-routes";

/** Old document links enter the same shared manager as the module menus. */
export default function CommonCommercialEntry({ children }: { children: ReactNode }) {
  const { pathname, search, hash } = useLocation();
  const module = pathname.split("/")[1];
  if (module !== "crm" && module !== "srm") return <>{children}</>;
  const target = commonNavigationHref(pathname + search + hash, module);
  const context = commonRouteContext(target.split("#")[0]);
  return context && isCommercialEntity(context.entity) ? <Navigate replace to={target} /> : <>{children}</>;
}
