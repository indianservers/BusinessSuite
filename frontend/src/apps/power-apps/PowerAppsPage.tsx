import { AutomationList } from "./applications/automations/AutomationList";
import {
  environmentFromSearch,
  studioPath,
} from "./applications/automations/studioApi";
import { Empty } from "./shared/EmptyState";
import { ActivityList } from "./shared/ActivityList";
import { PlannedApplication } from "./shared/PlannedApplication";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  ChevronDown,
  Layers3,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useSignOut } from "@/hooks/use-sign-out";
import { powerApi, errorMessage } from "./api";
import {
  applicationIcons,
  type Activity,
  type Catalog,
  type Environment,
  type Overview,
  type Resource,
} from "./registry";
import "./power-apps.css";

const metrics = [
  ["total_apps", "Total apps"],
  ["active_automations", "Active automations"],
  ["pending_approvals", "Pending approvals"],
  ["form_submissions", "Form submissions"],
  ["workflow_executions", "Workflow executions"],
  ["failed_runs", "Failed runs"],
];
export default function PowerAppsPage() {
  const user = useAuthStore((s) => s.user);
  const signOut = useSignOut("/login");
  const location = useLocation();
  const navigate = useNavigate();
  const section = location.pathname.split("/")[2];
  const [catalog, setCatalog] = useState<Catalog>();
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [environment, setEnvironment] = useState<Environment>(() =>
    environmentFromSearch(location.search),
  );
  const [overview, setOverview] = useState<Overview>();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [saving, setSaving] = useState(false);
  const can = (permission: string) =>
    catalog?.permissions.includes(`power_apps_${permission}`) ?? false;
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    setOverview(undefined);
    setActivities([]);
    (async () => {
      const [cat, envs] = await Promise.all([
        powerApi.catalog(),
        powerApi.environments(),
      ]);
      if (!active) return;
      setCatalog(cat);
      const enabled = envs.filter((e) => e.enabled).map((e) => e.key);
      setEnvironments(enabled);
      if (!enabled.length) {
        setBusy(false);
        return;
      }
      if (!enabled.includes(environment)) {
        setEnvironment(enabled[0]);
        return;
      }
      const [data, activity] = await Promise.all([
        powerApi.overview(environment),
        cat.permissions.includes("power_apps_activity_view")
          ? powerApi.activity(environment)
          : Promise.resolve([]),
      ]);
      if (!active) return;
      setOverview(data);
      setActivities(activity);
      setBusy(false);
    })().catch((e) => {
      if (active) {
        setError(errorMessage(e));
        setBusy(false);
      }
    });
    return () => {
      active = false;
    };
  }, [environment, section, location.pathname, refresh]);
  const move = (route: string) =>
    navigate(
      route.startsWith("/power-apps") ? studioPath(route, environment) : route,
    );
  const selected = catalog?.applications.find((a) => a.id === section);
  const available =
    catalog?.applications.filter((a) =>
      `${a.name} ${a.description}`.toLowerCase().includes(query.toLowerCase()),
    ) || [];
  return (
    <div className="pa-shell">
      <aside className="pa-sidebar">
        <Link className="pa-logo" to="/power-apps">
          <span>
            <Layers3 />
          </span>
          <strong>
            Power Apps<small>BUSINESS SUITE</small>
          </strong>
        </Link>
        <Link className="pa-suite-link" to="/dashboard">
          <ArrowLeft size={15} />
          Master Suite
        </Link>
        <nav aria-label="Power Apps">
          <button
            className={!section ? "active" : ""}
            onClick={() => move("/power-apps")}
          >
            <Layers3 size={18} />
            Overview
          </button>
          <p>YOUR TOOLKIT</p>
          {catalog?.applications.map((app) => {
            const Icon = applicationIcons[app.icon];
            return (
              <button
                className={section === app.id ? "active" : ""}
                key={app.id}
                onClick={() => move(app.route)}
              >
                <Icon size={18} />
                {app.name}
                {app.status === "planned" && <span className="pa-dot" />}
              </button>
            );
          })}
        </nav>
        <div className="pa-sidebar-note">
          <ShieldCheck size={20} />
          <strong>A space to build safely</strong>
          <p>
            Isolated environments.
            <br />
            Governed from the start.
          </p>
        </div>
      </aside>
      <div className="pa-main">
        <header className="pa-header">
          <label className="pa-global-search">
            <Search size={18} />
            <input
              aria-label="Search Power Apps applications"
              placeholder="Find an application..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (section) move("/power-apps");
              }}
            />
          </label>
          <label className="pa-environment">
            <span className="pa-dot" />
            <select
              aria-label="Power Apps environment"
              value={environments.includes(environment) ? environment : ""}
              disabled={busy || !environments.length}
              onChange={(e) => {
                setEnvironment(e.target.value as Environment);
                navigate(
                  studioPath("/power-apps", e.target.value as Environment),
                );
              }}
            >
              {!environments.length && <option value="">No environment</option>}
              {environments.map((env) => (
                <option key={env} value={env}>
                  {env[0].toUpperCase() + env.slice(1)}
                </option>
              ))}
            </select>
          </label>
          {can("create") && environments.length > 0 && (
            <details className="pa-create-menu">
              <summary>
                <Plus size={16} />
                Create new
                <ChevronDown size={14} />
              </summary>
              <button onClick={() => move("/power-apps/automations/new")}>
                <Workflow size={17} />
                Automation draft
              </button>
            </details>
          )}
          {can("activity_view") && (
            <button
              className="pa-bell"
              aria-label="View recent changes"
              onClick={() => move("/power-apps/activity")}
            >
              <Bell size={19} />
              {activities.length > 0 && <i />}
            </button>
          )}
          <details className="pa-user-menu">
            <summary aria-label="User menu">
              {(user?.name || user?.email || "U").slice(0, 1).toUpperCase()}
            </summary>
            <div>
              <strong>{user?.name || user?.email}</strong>
              <span>Organization {user?.access?.companyId || "context"}</span>
              <button onClick={() => signOut()}>Sign out</button>
            </div>
          </details>
        </header>
        <main className="pa-content">
          <div className="pa-page-heading">
            <div>
              <p className="pa-eyebrow">YOUR IDEAS. CONNECTED.</p>
              <h1>
                {selected?.name ||
                  (section
                    ? "Application unavailable"
                    : "Your business, with superpowers.")}
              </h1>
              <p>
                {selected?.description ||
                  "Build smarter tools. Connect your work. Make room for what matters."}
              </p>
            </div>
            {!section && (
              <span className="pa-phase">
                <Sparkles size={14} />
                Automation Studio - Phase 2
              </span>
            )}
          </div>
          {error && (
            <div role="alert" className="pa-error">
              {error}
              <button onClick={() => setRefresh((v) => v + 1)}>
                Retry / reload
              </button>
            </div>
          )}
          {busy ? (
            <p role="status" className="pa-loading">
              Loading your environment...
            </p>
          ) : !catalog ? null : !environments.length ? (
            <section className="pa-panel">
              <Empty title="Set up your first environment">
                An environment administrator must enable a workspace for this
                organization.
              </Empty>
              {can("manage_environment") && (
                <button
                  className="pa-primary"
                  onClick={async () => {
                    try {
                      await powerApi.configure("development", true);
                      setRefresh((v) => v + 1);
                    } catch (e) {
                      setError(errorMessage(e));
                    }
                  }}
                >
                  Enable Development
                </button>
              )}
            </section>
          ) : (
            <>
              {!section && (
                <>
                  <section
                    className="pa-metrics"
                    aria-label="Environment statistics"
                  >
                    {metrics.map(([key, title]) => (
                      <article key={key}>
                        <p>{title}</p>
                        <strong>
                          {overview ? (overview.counts[key] ?? 0) : "-"}
                        </strong>
                        <small>
                          {overview?.unsupported_metrics.includes(key)
                            ? "Available in a future phase"
                            : "In this environment"}
                        </small>
                      </article>
                    ))}
                  </section>
                  <section>
                    <div className="pa-section-title">
                      <div>
                        <h2>Everything you need to build</h2>
                        <p>One platform. A world of possibilities.</p>
                      </div>
                      <span>{available.length} applications</span>
                    </div>
                    <div className="pa-catalog">
                      {available.map((app) => {
                        const Icon = applicationIcons[app.icon];
                        return (
                          <article key={app.id}>
                            <div className={`pa-app-icon pa-icon-${app.id}`}>
                              <Icon size={25} />
                            </div>
                            <span className={`pa-status ${app.status}`}>
                              {app.status === "drafts"
                                ? "Draft workspace"
                                : app.status === "available"
                                  ? "Available"
                                  : "Coming next"}
                            </span>
                            <h3>{app.name}</h3>
                            <p>{app.description}</p>
                            <button onClick={() => move(app.route)}>
                              Open application
                              <ArrowRight size={16} />
                            </button>
                          </article>
                        );
                      })}
                    </div>
                    {!available.length && (
                      <Empty title="No applications found">
                        Try another application name.
                      </Empty>
                    )}
                  </section>
                  <div className="pa-bottom-grid">
                    <section className="pa-panel">
                      <div className="pa-section-title">
                        <h2>Recent work</h2>
                        <span>This environment</span>
                      </div>
                      {overview?.recent.length ? (
                        overview.recent.map((row) => (
                          <button
                            className="pa-resource"
                            key={row.id}
                            onClick={() =>
                              move(`/power-apps/automations/${row.id}/edit`)
                            }
                          >
                            <Workflow size={18} />
                            <span>
                              <strong>{row.name}</strong>
                              <small>
                                Draft - v{row.version} -{" "}
                                {new Date(row.updated_at).toLocaleDateString()}
                              </small>
                            </span>
                            <ArrowRight size={16} />
                          </button>
                        ))
                      ) : (
                        <Empty title="Your next idea starts here">
                          Create an automation draft and it will appear here.
                        </Empty>
                      )}
                    </section>
                    <section className="pa-panel pa-template-panel">
                      <span className="pa-template-icon">
                        <Sparkles size={24} />
                      </span>
                      <h2>A head start for every idea</h2>
                      <p>
                        A shared home for automation, approval, form, and
                        application templates.
                      </p>
                      {catalog.templates.length ? (
                        catalog.templates
                          .slice(0, 3)
                          .map((t) => <p key={t.id}>{t.name || t.id}</p>)
                      ) : (
                        <p className="pa-muted">No templates registered yet.</p>
                      )}
                      <span className="pa-phase">
                        <button
                          onClick={() =>
                            move("/power-apps/automations?view=templates")
                          }
                        >
                          Explore automation templates <ArrowRight size={12} />
                        </button>
                      </span>
                    </section>
                  </div>
                  {can("activity_view") && (
                    <section className="pa-panel">
                      <h2>Recent activity</h2>
                      <ActivityList activities={activities.slice(0, 5)} />
                    </section>
                  )}
                </>
              )}
              {section === "automations" && (
                <AutomationList environment={environment} can={can} />
              )}
              {section === "activity" &&
                (can("activity_view") ? (
                  <section className="pa-panel">
                    <h2>Environment activity</h2>
                    <ActivityList activities={activities} />
                  </section>
                ) : (
                  <Empty title="Activity permission required">
                    Ask your administrator for permission to view activity logs.
                  </Empty>
                ))}
              {section &&
                section !== "automations" &&
                section !== "activity" && (
                  <PlannedApplication
                    section={section}
                    name={selected?.name}
                    onBack={() => move("/power-apps")}
                  />
                )}
            </>
          )}
          {can("manage_environment") && !busy && (
            <details className="pa-admin">
              <summary>Environment administration</summary>
              <p>
                Enablement is separate from workflow creation. Resources remain
                isolated in each environment.
              </p>
              {(["development", "testing", "production"] as Environment[]).map(
                (env) => (
                  <button
                    key={env}
                    disabled={saving}
                    onClick={async () => {
                      setSaving(true);
                      try {
                        await powerApi.configure(
                          env,
                          !environments.includes(env),
                        );
                        setRefresh((v) => v + 1);
                      } catch (e) {
                        setError(errorMessage(e));
                      } finally {
                        setSaving(false);
                      }
                    }}
                  >
                    {environments.includes(env) ? "Disable" : "Enable"} {env}
                  </button>
                ),
              )}
            </details>
          )}
          <footer className="pa-footer">
            <Layers3 size={14} />
            Power Apps<span>Built on Business Suite - {environment}</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
