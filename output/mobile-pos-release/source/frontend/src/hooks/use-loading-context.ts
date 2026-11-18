import { useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { getRoleNav } from "@/lib/roles";
import { menuLabel } from "@/lib/navigation-menu";

/** Reuse permission-aware navigation labels rather than exposing URL/API segments. */
export function useLoadingContext() {
  const { pathname } = useLocation();
  const user = useAuthStore((s) => s.user);
  const navigation = getRoleNav(user?.role, user?.is_superuser, pathname);
  const match = navigation
    .filter((item) => {
      const path = item.to.split("?")[0];
      return (
        pathname === path || (path !== "/" && pathname.startsWith(path + "/"))
      );
    })
    .sort((a, b) => b.to.length - a.to.length)[0];
  const resource = match ? menuLabel(match) : "Workspace";
  const singular = resource.replace(/ies$/i, "y").replace(/s$/i, "");
  const detail = match && pathname !== match.to.split("?")[0];
  const creating = /\/new\/?$/.test(pathname),
    editing = /\/edit\/?$/.test(pathname);
  return {
    title: creating
      ? `Preparing New ${singular}`
      : editing
        ? `Loading ${singular} Details`
        : detail
          ? `Loading ${singular} Details`
          : `Loading ${resource}`,
    resource,
    module: navigation[0]?.group || "",
    pathname,
  };
}
