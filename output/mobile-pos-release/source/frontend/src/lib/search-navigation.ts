import { getRoleNav, canAccessRoute } from "./roles";
import { useAuthStore } from "@/store/authStore";
import { modules } from "./moduleCatalog";

/** Global search must enumerate each authorized module, not just the current sidebar. */
export function searchableNavigation(role: string | null | undefined, isSuperuser: boolean, pathname: string) {
  const access = useAuthStore.getState().user?.access;
  const contexts = new Set([pathname, ...modules.map(module => module.homePath)]);
  const results = new Map<string, { type: string; title: string; subtitle?: string; url: string }>();
  for (const context of contexts) {
    const module = modules.find(item => context === item.homePath || context.startsWith(item.homePath + "/"));
    if (module && access?.managed && !isSuperuser && !access.grants[module.productKey ?? module.key]?.enabled) continue;
    for (const page of getRoleNav(role, isSuperuser, context)) {
      const owner = modules.find(item => page.to === item.homePath || page.to.startsWith(item.homePath + "/"));
      if (owner && access?.managed && !isSuperuser && !access.grants[owner.productKey ?? owner.key]?.enabled) continue;
      if (canAccessRoute(page.to, role, isSuperuser) && !results.has(page.to)) {
        results.set(page.to, { type: "Page", title: page.label, subtitle: owner?.name ?? module?.name, url: page.to });
      }
    }
  }
  return [...results.values()];
}
