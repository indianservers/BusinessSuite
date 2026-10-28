import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useSuitePreferences, suiteScope } from "@/store/suitePreferences";
import { canAccessRoute } from "@/lib/roles";
import { modules } from "@/lib/moduleCatalog";

export default function SuiteNavigationTracker() {
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const visit = useSuitePreferences((s) => s.visit);
  useEffect(() => {
    if (
      !user?.access ||
      !modules.some(
        (m) =>
          location.pathname === m.homePath ||
          location.pathname.startsWith(m.homePath + "/"),
      )
    )
      return;
    if (canAccessRoute(location.pathname, user.role, user.is_superuser)) {
      // Store page paths only, excluding record filters, tokens and fragments.
      visit(suiteScope(user.id, user.access.companyId), location.pathname);
    }
  }, [location.pathname, user, visit]);
  return null;
}
