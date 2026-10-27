import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  LayoutGrid,
  LogOut,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, authApi } from "@/services/api";
import { useAuthStore, type AuthUser } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { modules, features } from "@/lib/moduleCatalog";
import "./module-dashboard.css";

export default function ModuleDashboardPage() {
  const { user, isAuthenticated, isHydrated, setUser, logout } = useAuthStore();
  const [query, setQuery] = useState("");
  const [signingOut, setSigningOut] = useState(false);
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
  if (!isAuthenticated)
    return <Navigate to="/login" replace />;
  const allowed = user?.access
    ? modules.filter((m) =>
        canAccessRoute(m.homePath, user.role, user.is_superuser),
      )
    : [];
  const visible = allowed.filter((m) =>
    `${m.name} ${m.label} ${m.description} ${features[m.key].map(([, label]) => label).join(" ")}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  return (
    <div className="module-dashboard">
      <header className="md-header">
        <Link to="/dashboard" className="md-brand">
          <span>
            <LayoutGrid size={22} />
          </span>
          <div>
            Business Suite<small>APPLICATION DASHBOARD</small>
          </div>
        </Link>
        <div className="md-account">
          <span>{user?.email}</span>
          <button
            disabled={signingOut}
            onClick={async () => {
              setSigningOut(true);
              try {
                await authApi.logout();
              } catch {
                // Clear the local session even when the server is unreachable.
              } finally {
                logout();
              }
            }}
          >
            <LogOut size={16} />
            {signingOut ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </header>
      <main className="md-main">
        <section className="md-welcome">
          <div>
            <p className="md-eyebrow">
              <Building2 size={14} />
              {branding.data?.company_name || "YOUR BUSINESS WORKSPACE"}
            </p>
            <h1>Your work starts here.</h1>
            <p>
              Choose an application to get started. Move between your modules
              with one Business Suite account.
            </p>
          </div>
          <div className="md-access-note">
            <ShieldCheck size={23} />
            <span>
              Access tailored to you
              <small>
                Your company roles and permissions apply in every module.
              </small>
            </span>
          </div>
        </section>
        {!!user?.access && user.access.memberships.length > 1 && (
          <label className="md-company">
            Company
            <select
              aria-label="Current company"
              value={user.access.companyId}
              onChange={(e) => {
                sessionStorage.setItem("suite-organization", e.target.value);
                window.location.reload();
              }}
            >
              {user.access.memberships.map((id) => (
                <option key={id} value={id}>
                  Company {id}
                </option>
              ))}
            </select>
          </label>
        )}
        <section aria-labelledby="md-applications">
          <div className="md-section-head">
            <div>
              <h2 id="md-applications">Your applications</h2>
              <span>
                {allowed.length} available{" "}
                {allowed.length === 1 ? "module" : "modules"}
              </span>
            </div>
            <label className="md-search">
              <Search size={18} />
              <input
                aria-label="Search your modules"
                placeholder="Find a module..."
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
          {!user?.access || !access.data ? (
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
                <p>Loading your authorized applications...</p>
              )}
            </div>
          ) : (
            <div className="md-grid">
              {visible.map((m) => {
                const Icon = m.icon;
                return (
                  <Link
                    key={m.key}
                    to={m.homePath}
                    className={`md-card md-${m.key}`}
                    aria-label={`Open ${m.name}`}
                  >
                    <div className="md-card-top">
                      <span className="md-icon">
                        <Icon size={28} />
                      </span>
                      <ArrowRight className="md-arrow" size={21} />
                    </div>
                    <h3>{m.name}</h3>
                    <p className="md-category">{m.label}</p>
                    <p className="md-description">{m.description}</p>
                    <div className="md-features">
                      {features[m.key].map(([Feature, label]) => (
                        <span key={label}>
                          <Feature size={14} />
                          {label}
                        </span>
                      ))}
                    </div>
                    <div className="md-open">
                      Open application <ArrowRight size={16} />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
          {!!user?.access && !visible.length && (
            <div className="md-empty">
              <LayoutGrid size={30} />
              <h3>
                {query ? "No matching modules" : "No applications assigned yet"}
              </h3>
              <p>
                {query
                  ? "Try another name or clear your search."
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
