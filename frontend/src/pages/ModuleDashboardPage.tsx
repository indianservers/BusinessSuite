import { SettingsHomeEntry } from "./SettingsHubPage";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Handshake,
  Building2,
  BarChart3,
  ClipboardList,
  Package,
  Sparkles,
  Star,
  Users,
  Zap,
  LayoutGrid,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, authApi } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { modules, features } from "@/lib/moduleCatalog";
import SuiteHeader from "@/components/suite/SuiteHeader";
import { useNotificationSummary } from "@/components/suite/notifications";
import {
  moduleFeaturePaths,
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
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const location = useLocation();
  const scope = suiteScope(user?.id, user?.access?.companyId);
  const preferences = useSuitePreferences(
    (state) => state.contexts[scope] || defaultSuitePreferences,
  );
  const updatePreferences = useSuitePreferences((state) => state.update);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const notifications = useNotificationSummary();
  const access = useQuery({
    queryKey: ["dashboard-access", user?.id],
    enabled: isHydrated && isAuthenticated && !!user,
    queryFn: () =>
      api
        .get<NonNullable<AuthUser["access"]>>("/access/me")
        .then((r) => r.data),
    retry: 1,
  });
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
  const role = (user?.primary_role || user?.role || "").toLowerCase();
  const recommended = user?.is_superuser
    ? null
    : /hr|employee/.test(role)
      ? "hrms"
      : /srm|inventory/.test(role)
        ? "srm"
        : /crm|sales_executive/.test(role)
          ? "crm"
          : /pms|project/.test(role)
            ? "pms"
            : /finance|accountant|fam/.test(role)
              ? "fam"
              : null;
  const visible = allowed
    .filter((m) => !favoritesOnly || preferences.favorites.includes(m.key))
    .filter((m) =>
      `${m.name} ${m.label} ${m.description} ${features[m.key].map(([, label]) => label).join(" ")}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
    )
    .sort(
      (a, b) =>
        Number(preferences.favorites.includes(b.key)) -
        Number(preferences.favorites.includes(a.key)),
    );
  return (
    <div
      className={`module-dashboard ${preferences.compact ? "suite-dashboard-compact" : ""}`}
    >
      <a className="suite-skip" href="#suite-main">
        Skip to applications
      </a>
      <SuiteHeader />
      <main className="md-main" id="suite-main" tabIndex={-1}>
        {location.state?.notice && (
          <p className="suite-dashboard-notice" role="status">
            {location.state.notice}
          </p>
        )}
        <SettingsHomeEntry />
        <section className="md-welcome">
          <div>
            <p className="md-eyebrow">
              <Building2 size={14} />
              {user?.access?.companyName ||
                branding.data?.company_name ||
                "YOUR BUSINESS WORKSPACE"}
            </p>
            <h1>
              Your work <span>starts here.</span>
            </h1>
            <p>
              Choose an application to get started. Move between your roles with
              one Business Suite account.
            </p>
            <div className="md-benefits">
              <div>
                <span>
                  <ShieldCheck />
                </span>
                <p>
                  <strong>Single account</strong>
                  <small>Access all modules</small>
                </p>
              </div>
              <div>
                <span>
                  <Users />
                </span>
                <p>
                  <strong>Role based access</strong>
                  <small>Secure and controlled</small>
                </p>
              </div>
              <div>
                <span>
                  <Zap />
                </span>
                <p>
                  <strong>Built for productivity</strong>
                  <small>All your tools in one place</small>
                </p>
              </div>
            </div>
          </div>
          <div className="md-hero-art" aria-hidden="true">
            <div className="md-orbit" />
            <span className="md-float md-float-chart">
              <BarChart3 />
            </span>
            <span className="md-float md-float-users">
              <Users />
            </span>
            <span className="md-float md-float-package">
              <Package />
            </span>
            <span className="md-float md-float-document">
              <ClipboardList />
            </span>
          </div>
          <div className="md-access-note">
            <div className="md-access-icon">
              <ShieldCheck size={30} />
            </div>
            <span>
              Access tailored to you
              <small>
                Your company roles and permissions apply in every module.
              </small>
              {canAccessRoute(
                "/admin/access",
                user?.role,
                user?.is_superuser,
              ) && (
                <Link className="md-manage" to="/admin/access?tab=Roles">
                  Manage permissions <ArrowRight size={16} />
                </Link>
              )}
            </span>
          </div>
        </section>
        {ready && recent.length > 0 && (
          <section className="suite-resume" aria-label="Continue working">
            <div>
              <p>Continue working</p>
              <strong>{suitePageLabel(recent[0])}</strong>
              {recent.length > 1 && (
                <details className="suite-recent-list">
                  <summary>Recent pages</summary>
                  {recent.slice(1).map((path) => (
                    <Link key={path} to={path}>
                      {suitePageLabel(path)}
                    </Link>
                  ))}
                </details>
              )}
            </div>
            <div className="suite-inline-actions">
              <Link className="suite-primary" to={recent[0]}>
                Resume <ArrowRight size={16} />
              </Link>
              <button
                className="suite-clear-recents"
                onClick={() => updatePreferences(scope, { recent: [] })}
              >
                Clear recent pages
              </button>
            </div>
          </section>
        )}
        <section aria-labelledby="md-applications">
          <div className="md-section-head">
            <div>
              <h2 id="md-applications">Your applications</h2>
              {ready && (
                <span>
                  {allowed.length} available{" "}
                  {allowed.length === 1 ? "module" : "modules"}
                </span>
              )}
            </div>
            <label className="md-search">
              <Search size={18} />
              <input
                ref={searchRef}
                aria-label="Search your modules"
                placeholder="Filter applications..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {query && (
                <button
                  aria-label="Clear module search"
                  onClick={() => setQuery("")}
                >
                  <X size={16} />
                </button>
              )}
            </label>
          </div>
          <div className="suite-dashboard-tools">
            <label>
              <input
                type="checkbox"
                checked={preferences.compact}
                onChange={(e) =>
                  updatePreferences(scope, { compact: e.target.checked })
                }
              />
              Compact view
            </label>
            <label>
              <input
                type="checkbox"
                checked={favoritesOnly}
                onChange={(e) => setFavoritesOnly(e.target.checked)}
              />
              Favorites only
            </label>
            <span>
              Pin an application using its star. Favorites appear first.
            </span>
          </div>
          {!ready ? (
            <div
              className="md-empty"
              role={access.isError ? "alert" : "status"}
            >
              {access.isError ? (
                <>
                  <h3>We couldn't load your applications.</h3>
                  <p>Try refreshing your access.</p>
                  <button onClick={() => void access.refetch()}>
                    Try again
                  </button>
                </>
              ) : (
                <>
                  <p role="status">Loading your authorized applications...</p>
                  <div className="md-grid" aria-hidden="true">
                    {Array.from({ length: 6 }, (_, index) => (
                      <div className="suite-dashboard-skeleton" key={index} />
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="md-grid">
              {visible.map((m) => {
                const Icon = m.key === "crm" ? Handshake : m.icon;
                return (
                  <article
                    key={m.key}
                    className={`md-card md-${m.key}`}
                    aria-label={m.name}
                  >
                    <button
                      className="suite-favorite"
                      aria-label={`${preferences.favorites.includes(m.key) ? "Unpin" : "Pin"} ${m.name}`}
                      aria-pressed={preferences.favorites.includes(m.key)}
                      onClick={() =>
                        updatePreferences(scope, {
                          favorites: preferences.favorites.includes(m.key)
                            ? preferences.favorites.filter(
                                (key) => key !== m.key,
                              )
                            : [...preferences.favorites, m.key],
                        })
                      }
                    >
                      <Star
                        size={18}
                        fill={
                          preferences.favorites.includes(m.key)
                            ? "currentColor"
                            : "none"
                        }
                      />
                    </button>
                    <div className="md-module-art" aria-hidden="true"><img src={`/module-art/${m.key}.webp`} alt="" width="160" height="160" decoding="async" /></div>
                    <div className="md-card-top">
                      <span className="md-icon">
                        <Icon size={36} />
                      </span>
                    </div>
                    <div className="suite-card-title">
                      <h3>
                        <Link to={m.homePath}>{m.name}</Link>
                      </h3>
                      {recommended === m.key && (
                        <span
                          className="md-featured"
                          title="Recommended for your role"
                        >
                          <Sparkles size={12} />
                          Recommended for your role
                        </span>
                      )}
                    </div>
                    <p className="md-category">{m.label}</p>
                    <p className="md-description">{m.description}</p>
                    <div className="md-features">
                      {features[m.key].map(([Feature, label]) =>
                        canAccessRoute(
                          moduleFeaturePaths[m.key][label],
                          user?.role,
                          user?.is_superuser,
                        ) ? (
                          <Link
                            key={label}
                            to={moduleFeaturePaths[m.key][label]}
                            aria-label={`${m.name}: ${label}`}
                          >
                            <Feature size={14} />
                            {label}
                          </Link>
                        ) : (
                          <span key={label}>
                            <Feature size={14} />
                            {label}
                          </span>
                        ),
                      )}
                    </div>
                    {!!notifications.byModule[m.key] && (
                      <Link
                        className="suite-module-alerts"
                        to={`/notifications?app=${m.key}&unread=1`}
                      >
                        {notifications.byModule[m.key]} unread{" "}
                        {notifications.byModule[m.key] === 1
                          ? "update"
                          : "updates"}{" "}
                        <ArrowRight size={13} />
                      </Link>
                    )}
                    <Link
                      className="md-open"
                      to={m.homePath}
                      aria-label={`Open ${m.name}`}
                    >
                      Open application <ArrowRight size={16} />
                    </Link>
                  </article>
                );
              })}
            </div>
          )}
          {ready && !visible.length && (
            <div className="md-empty">
              <LayoutGrid size={30} />
              <h3>
                {query
                  ? "No matching modules"
                  : favoritesOnly
                    ? "No favorite applications"
                    : "No applications assigned yet"}
              </h3>
              <p>
                {query
                  ? "Try another name or clear your search."
                  : favoritesOnly
                    ? "Turn off Favorites only, then pin an application using its star."
                    : "Contact your company administrator to request access."}
              </p>
              {query && (
                <button onClick={() => setQuery("")}>
                  Show my applications
                </button>
              )}
            </div>
          )}
        </section>
      </main>
      <footer className="md-footer">
        <span>Business Suite - One account. Your authorized workspace.</span>
        <Link to="/dashboard">Dashboard home</Link>
      </footer>
    </div>
  );
}
