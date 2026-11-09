import { useFavoriteSync } from "@/hooks/use-favorite-sync";
import { accessQueryOptions } from "@/features/access/access-query";
import PremiumLauncher from "@/components/suite/PremiumLauncher";
import CompanySampleData from "@/shared/data-transfer/CompanySampleData";
import { useEffect } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, authApi } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { modules } from "@/lib/moduleCatalog";
import { useNotificationSummary } from "@/components/suite/notifications";
import {
  safeSuiteDestination,
  suitePageLabel,
} from "@/lib/suiteNavigation";
import {
  defaultSuitePreferences,
  suiteScope,
  useSuitePreferences,
} from "@/store/suitePreferences";
import "./module-dashboard.css";

export default function ModuleDashboardPage() {
  const { user, isAuthenticated, isHydrated, setUser } = useAuthStore();
  const location = useLocation();
  const access = useQuery({
    ...accessQueryOptions(),
    enabled: isHydrated && isAuthenticated && !!user,
  });
  const scope = suiteScope(user?.id, access.data?.companyId ?? user?.access?.companyId);
  const preferences = useSuitePreferences(
    (state) => state.contexts[scope] || defaultSuitePreferences,
  );
  const updatePreferences = useSuitePreferences((state) => state.update);
  const notifications = useNotificationSummary();
  const favoriteSync = useFavoriteSync(scope, !!(isAuthenticated && access.isSuccess && user?.access));
  const branding = useQuery({
    queryKey: ["login-branding"],
    queryFn: () =>
      authApi.branding().then((r) => r.data as { company_name: string | null }),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });
  useEffect(() => {
    const currentUser = useAuthStore.getState().user;
    if (access.data && currentUser)
      setUser({ ...currentUser, access: access.data });
  }, [access.data, setUser]);
  if (!isHydrated)
    return (
      <main className="module-dashboard md-state" aria-busy="true">
        Loading your workspace...
      </main>
    );
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const allowed = user?.access
    ? modules.filter((m) =>
        canAccessRoute(m.homePath, user.role, user.is_superuser),
      )
    : [];
  const ready = access.isSuccess && !!user?.access;
  const recent = preferences.recent.filter(
    (path) =>
      safeSuiteDestination(path) &&
      canAccessRoute(path, user?.role, user?.is_superuser),
  );
  return <PremiumLauncher applications={ready ? allowed : []} authenticated
    company={user?.access?.companyName || branding.data?.company_name || "Your workspace"}
    favorites={preferences.favorites} unread={notifications.byModule}
    loading={!ready && !access.isError}
    workspaceCount={new Set(user?.access?.organizations?.map(org => org.id) || user?.access?.memberships || []).size}
    query={preferences.applicationSearch || ""} onQuery={applicationSearch => updatePreferences(scope, { applicationSearch })}
    favoritesOnly={preferences.favoritesOnly || false} onFavoritesOnly={favoritesOnly => updatePreferences(scope, { favoritesOnly })}
    onReorder={favorites => updatePreferences(scope, { favorites, favoritesDirty: true })}
    compact={preferences.compact} onCompact={value => updatePreferences(scope, { compact: value })}
    onFavorite={key => updatePreferences(scope, { favoritesDirty: true, favorites: preferences.favorites.includes(key)
      ? preferences.favorites.filter(value => value !== key) : [...preferences.favorites, key] })}>
    {favoriteSync.error && <p className="launcher-notice" role="status">Favorites are saved on this browser. Sync is unavailable. <button onClick={favoriteSync.retry}>Retry sync</button></p>}
    {location.state?.notice && <p className="launcher-notice" role="status">{location.state.notice}</p>}
    {!ready && <div className="launcher-notice" role={access.isError ? "alert" : "status"}>
      {access.isError ? <><p>We couldn't load your applications.</p><button onClick={() => void access.refetch()}>Try again</button></> : "Loading your authorized applications…"}
    </div>}
    {ready && !allowed.length && <p className="launcher-notice">No applications assigned yet. Contact your company administrator to request access.</p>}
    {ready && recent.length > 0 && <section className="launcher-recents" aria-label="Continue working"><h2>Continue working</h2><div>
      {recent.map(path => <Link key={path} to={path}>{suitePageLabel(path)}{preferences.recentVisitedAt?.[path] && <time dateTime={preferences.recentVisitedAt[path]}>{new Date(preferences.recentVisitedAt[path]).toLocaleString()}</time>}</Link>)}
      <button onClick={() => updatePreferences(scope, { recent: [], recentVisitedAt: {} })}>Clear recent pages</button>
    </div></section>}
  <CompanySampleData/>
  </PremiumLauncher>;
}
