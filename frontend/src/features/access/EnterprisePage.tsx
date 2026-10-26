import { assetUrl } from "@/lib/utils";
import DashboardStudio from "./DashboardStudio";
import React, { useEffect, useState, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Building2,
  Flag,
  LifeBuoy,
  ShieldCheck,
  Database,
  Palette,
  RefreshCw,
  Plus,
  Save,
  Download,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ControlNav } from "./ControlCenter";
import "./control.css";
import "./enterprise.css";

const root = "/access/enterprise";
const sections = [
  ["overview", "Executive Overview"],
  ["analytics", "Business Insights"],
  ["actions", "Action Center"],
  ["licensing", "Subscriptions & Licensing"],
  ["flags", "Feature Management"],
  ["branding", "Branding"],
  ["health", "Health Monitor"],
  ["errors", "Error Center"],
  ["backups", "Backup & Recovery"],
  ["governance", "Data Governance"],
  ["support", "Support Center"],
  ["coverage", "Module Coverage"],
];
const sources = [
  ["crm_leads", "CRM leads"],
  ["crm_pipeline", "Sales pipeline"],
  ["projects", "PMS projects"],
  ["tasks", "PMS tasks"],
  ["invoices", "Invoices"],
  ["employees", "Employees"],
];
const text = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : JSON.stringify(e?.response?.data?.detail || e.message);
const stamp = (v: any) => (v ? new Date(v).toLocaleString() : "Not observed");
const defaults: any = {
  plans: {
    code: "",
    name: "",
    modules: ["crm", "project_management"],
    active: true,
    seats: 100,
    storageMb: 10240,
    aiRequests: 100,
    automationRuns: 1000,
    apiRequests: 100000,
    supportLevel: "standard",
    billingInterval: "monthly",
  },
  subscription: {
    planId: 0,
    status: "active",
    expiryPolicy: "allow",
    renewalAt: null,
    graceUntil: null,
    scheduledPlanId: null,
    effectiveAt: null,
  },
  flags: {
    module: "crm",
    key: "",
    name: "",
    description: "",
    ownerId: 0,
    enabled: false,
    environment: "production",
    percentage: 100,
    users: [],
    branches: [],
    roles: [],
    expiresAt: null,
  },
  branding: {
    appName: "Business Suite",
    logoPath: "",
    primary: "#6d28d9",
    surface: "#ffffff",
    background: "#f8fafc",
    text: "#171717",
    radius: 8,
  },
  governance: {
    module: "crm",
    entity: "lead",
    classification: "confidential",
    ownerId: 0,
    retentionDays: null,
    legalBasis: "",
    legalHold: false,
    allowedRoles: [],
  },
  support: {
    subject: "",
    description: "",
    module: "crm",
    priority: "Medium",
    kind: "support",
    assignedTo: null,
    relatedErrors: [],
  },
  dashboard: {
    name: "My enterprise dashboard",
    widgets: [
      { source: "crm_leads", type: "kpi", width: 1, title: "CRM leads" },
    ],
    sharedRoles: [],
  },
  recovery_request: {
    backupId: "",
    environment: "non-production",
    procedure: "",
    status: "requested",
  },
  support_access_request: {
    userId: 0,
    expiresAt: "",
    status: "requested",
    purpose: "",
  },
};

function Badge({ value }: { value: any }) {
  return (
    <span
      className={`ec-badge ec-${String(value)
        .replace(/[^a-z_]/gi, "")
        .toLowerCase()}`}
    >
      {value || "unknown"}
    </span>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return <p className="cc-empty">{children}</p>;
}
function Rows({ children }: { children: React.ReactNode }) {
  return (
    <div className="cc-scroll">
      <table>{children}</table>
    </div>
  );
}
function Field({
  name,
  value,
  onChange,
}: {
  name: string;
  value: any;
  onChange: (v: any) => void;
}) {
  const [draft, setDraft] = useState(
    typeof value === "object" ? JSON.stringify(value, null, 2) : "",
  );
  useEffect(() => {
    setDraft(typeof value === "object" ? JSON.stringify(value, null, 2) : "");
  }, [value]);
  const choices: Record<string, string[]> = {
    classification: ["public", "internal", "confidential", "restricted"],
    priority: ["Low", "Medium", "High", "Critical"],
    environment: [
      "development",
      "test",
      "staging",
      "production",
      "non-production",
    ],
    billingInterval: ["monthly", "yearly", "custom"],
    expiryPolicy: ["allow", "restrict"],
    kind: ["support", "incident"],
    status: [
      "active",
      "trial",
      "grace",
      "suspended",
      "Open",
      "In Progress",
      "Pending",
      "Resolved",
      "Closed",
      "open",
      "acknowledged",
      "resolved",
      "requested",
      "approved",
      "rejected",
      "revoked",
    ],
  };
  if (choices[name])
    return (
      <label>
        {name}
        <select
          aria-label={name}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {choices[name].map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </label>
    );
  return (
    <label>
      {name.replace(/([A-Z])/g, " $1").replace(/^./, (v) => v.toUpperCase())}
      {typeof value === "boolean" ? (
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
        />
      ) : typeof value === "object" ? (
        <textarea
          aria-label={name}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            try {
              onChange(JSON.parse(e.target.value));
            } catch {}
          }}
          onBlur={() => {
            try {
              onChange(JSON.parse(draft));
            } catch {
              setDraft(JSON.stringify(value, null, 2));
            }
          }}
        />
      ) : (
        <input
          aria-label={name}
          type={typeof value === "number" ? "number" : "text"}
          value={value ?? ""}
          onChange={(e) =>
            onChange(
              typeof value === "number"
                ? Number(e.target.value)
                : e.target.value,
            )
          }
        />
      )}
    </label>
  );
}

export default function EnterprisePage() {
  const actor = useAuthStore((s) => s.user);
  const visibleSections = sections.filter(
    ([id]) => id !== "backups" || actor?.is_superuser,
  );
  const section = useLocation().pathname.split("/").pop() || "overview";
  const [company, setCompany] = useState(
    Number(
      sessionStorage.getItem("suite-organization") ||
        actor?.access?.companyId ||
        1,
    ),
  );
  const [companies, setCompanies] = useState<any[]>([]),
    [catalog, setCatalog] = useState<any[]>([]);
  const [source, setSource] = useState("crm_leads"),
    [start, setStart] = useState(""),
    [end, setEnd] = useState("");
  const [branch, setBranch] = useState(""),
    [department, setDepartment] = useState("");
  const [result, setResult] = useState<{ key: string; value: any } | null>(
      null,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<any>(null),
    [values, setValues] = useState<any>({}),
    [reason, setReason] = useState("");
  const [password, setPassword] = useState(""),
    [step, setStep] = useState(false),
    [pending, setPending] = useState<null | (() => Promise<void>)>(null);
  const key = JSON.stringify([
    section,
    company,
    source,
    start,
    end,
    branch,
    department,
  ]);
  const data = result?.key === key ? result.value : null;
  useEffect(() => {
    api.get("/access/control/organizations").then((r) => setCompanies(r.data));
    api
      .get(root + "/catalog")
      .then((r) => setCatalog(r.data.modules))
      .catch((e) => setError(text(e)));
  }, []);
  useEffect(() => {
    setEditor(null);
    setNotice("");
    load();
  }, [key]);
  const loadVersion = useRef(0);
  async function load() {
    const version = ++loadVersion.current;
    setBusy(true);
    setError("");
    try {
      let value: any;
      const params: any = { companyId: company };
      if (section === "analytics") {
        Object.assign(params, {
          source,
          start: start ? new Date(start).toISOString() : undefined,
          end: end ? new Date(end).toISOString() : undefined,
          branchId: branch || undefined,
          departmentId: department || undefined,
        });
        value = (await api.get(root + "/analytics", { params })).data;
      } else if (section === "licensing") {
        const r = await Promise.all([
          api.get(root + "/plans"),
          api.get(root + "/subscription", { params }),
        ]);
        value = { plans: r[0].data, ...r[1].data };
      } else if (section === "branding" || section === "governance") {
        value = (
          await api.get(root + "/policies", {
            params: { ...params, kind: section },
          })
        ).data;
      } else if (section === "overview") {
        const r = await Promise.all([
          api.get(root + "/health", { params }),
          api.get(root + "/actions", { params }),
        ]);
        value = { health: r[0].data, actions: r[1].data.items };
      } else if (section === "coverage") {
        value = (await api.get(root + "/catalog")).data;
      } else {
        const route = section === "support" ? "tickets" : section;
        value = (await api.get(root + "/" + route, { params })).data;
      }
      if (version === loadVersion.current) setResult({ key, value });
    } catch (e) {
      if (version === loadVersion.current) setError(text(e));
    } finally {
      if (version === loadVersion.current) setBusy(false);
    }
  }
  async function mutate(action: () => Promise<any>) {
    setError("");
    setNotice("");
    try {
      await action();
      setNotice("Saved and audited.");
      if (section === "branding") window.dispatchEvent(new Event("suite-branding-updated"));
      await load();
    } catch (e: any) {
      if (
        String(e.response?.data?.detail).includes("Reauthenticate") ||
        e.response?.status === 428 ||
        (e.response?.status === 401 &&
          String(e.response?.data?.detail).includes("tep"))
      ) {
        setPending(() => async () => {
          await action();
          setNotice("Saved and audited.");
          if (section === "branding") window.dispatchEvent(new Event("suite-branding-updated"));
          await load();
        });
        setStep(true);
      } else setError(text(e));
    }
  }
  function edit(kind: string, row?: any) {
    setReason("");
    let value = { ...defaults[kind] };
    let version = row?.version || 0;
    let id = row?.id;
    let policyKey =
      kind === "dashboard"
        ? `user:${actor?.id}`
        : kind === "branding"
          ? "theme"
          : kind;
    if (row) {
      if (kind === "plans") {
        const c = row.config_json || {};
        value = {
          code: row.code,
          name: row.name,
          active: row.active,
          modules: c.modules || [],
          seats: c.seats || 100,
          storageMb: c.storage_mb || 10240,
          aiRequests: c.ai_requests || 100,
          automationRuns: c.automation_runs || 1000,
          apiRequests: c.api_requests || 100000,
          supportLevel: c.support_level || "standard",
          billingInterval: c.billing_interval || "monthly",
        };
      } else if (kind === "flags") {
        const c = row.value_json || {};
        value = {
          module: row.module_key,
          key: row.flag_key,
          name: c.name || row.flag_key,
          description: c.description || "",
          ownerId: c.ownerId || actor?.id,
          enabled: row.enabled,
          environment: c.environment || "production",
          percentage: c.percentage ?? 100,
          users: c.users || [],
          branches: c.branches || [],
          roles: c.roles || [],
          expiresAt: c.expires_at || null,
        };
        version = c.version || 0;
      } else if (kind === "subscription") {
        const sub = row.subscription;
        value = {
          ...value,
          planId: sub?.planId || data?.plans?.[0]?.id || 0,
          status: sub?.status || "active",
          renewalAt: sub?.values?.renewal_at || null,
          graceUntil: sub?.values?.grace_until || null,
          expiryPolicy: sub?.values?.expiry_policy || "allow",
          scheduledPlanId: sub?.values?.scheduled_change?.plan_id || null,
          effectiveAt: sub?.values?.scheduled_change?.effective_at || null,
        };
        version = sub?.version || 0;
      } else if (row.values_json) {
        value = { ...defaults[kind], ...row.values_json };
        policyKey = row.scope_key.split(`:${kind}:`)[1] || policyKey;
      }
    }
    if (kind === "flags" && !value.ownerId) value.ownerId = actor?.id;
    setValues(value);
    setEditor({ kind, version, id, key: policyKey });
  }
  async function save() {
    if (reason.trim().length < 3) {
      setError("Provide a reason of at least three characters.");
      return;
    }
    const current = editor;
    const body: any = {
      companyId: company,
      version: current.version,
      reason,
      ...values,
    };
    await mutate(async () => {
      if (current.kind === "plans") await api.post(root + "/plans", body);
      else if (current.kind === "flags") await api.put(root + "/flags", body);
      else if (current.kind === "subscription")
        await api.put(root + "/subscription", body);
      else if (current.kind === "support")
        await api.post(root + "/tickets", body);
      else
        await api.put(root + "/policies", {
          companyId: company,
          version: current.version,
          reason,
          kind: current.kind,
          key: current.key,
          values,
        });
      setEditor(null);
    });
  }
  async function download(path: string, name: string) {
    try {
      const response = await api.get(root + path, {
        params: {
          companyId: company,
          source,
          ...(path.startsWith("/analytics")
            ? {
                start: start ? new Date(start).toISOString() : undefined,
                end: end ? new Date(end).toISOString() : undefined,
                branchId: branch || undefined,
                departmentId: department || undefined,
              }
            : {}),
        },
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(text(e));
    }
  }
  const tree = companies.find((c) => c.id === company);
  const branches = tree?.branches || [];
  const departments = branches.flatMap((b: any) => b.departments || []);
  return (
    <main className="cc-root ec-root" aria-busy={busy || !data}>
      <header className="cc-heading">
        <div>
          <span className="cc-eyebrow">MASTER SUITE · ENTERPRISE CONTROL</span>
          <h1>{sections.find((s) => s[0] === section)?.[1] || "Enterprise"}</h1>
          <p>
            Central governance, authorized business insights and observed
            operations.
          </p>
        </div>
        <div className="ec-toolbar">
          <select
            aria-label="Company"
            value={company}
            onChange={(e) => setCompany(Number(e.target.value))}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" onClick={load} disabled={busy}>
            <RefreshCw size={14} />
            Refresh
          </Button>
        </div>
      </header>
      <ControlNav />
      <nav className="cc-nav ec-sections" aria-label="Enterprise sections">
        {visibleSections.map(([id, label]) => (
          <Link
            key={id}
            to={`/admin/control/enterprise/${id}`}
            aria-current={id === section ? "page" : undefined}
          >
            {label}
          </Link>
        ))}
      </nav>
      {error && (
        <div className="cc-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="ec-notice" role="status">
          {notice}
        </div>
      )}
      {busy && <p role="status">Loading authorized data…</p>}
      {section === "overview" && data && (
        <>
          <div className="ec-kpis">
            {[
              [
                "Companies in scope",
                companies.length,
                "/admin/control/organizations",
              ],
              [
                "Installed modules",
                catalog.filter((m) => m.installed).length,
                "/admin/control/modules",
              ],
              [
                "Open actions",
                data.actions.length,
                "/admin/control/enterprise/actions",
              ],
              [
                "API requests · 24h",
                data.health.api.requests,
                "/admin/control/enterprise/health",
              ],
            ].map(([label, count, path]) => (
              <Link className="cc-card ec-kpi" to={String(path)} key={label}>
                <span>{label}</span>
                <strong>{count}</strong>
                <ArrowUpRight size={14} />
              </Link>
            ))}
          </div>
          <div className="ec-grid">
            <section className="cc-card">
              <h2>Operational signals</h2>
              <p>
                Database <Badge value={data.health.database.status} />
              </p>
              <p>
                API <Badge value={data.health.api.status} />
              </p>
              <p>
                Frontend availability{" "}
                <Badge value={data.health.frontend.status} />
              </p>
              <small>{data.health.frontend.reason}</small>
            </section>
            <section className="cc-card">
              <h2>Business insights</h2>
              <p>
                Each source applies your company and record permissions.
                Financial totals remain separated by currency.
              </p>
              <div className="ec-shortcuts">
                {sources.map(([id, label]) => (
                  <Link
                    key={id}
                    to="/admin/control/enterprise/analytics"
                    onClick={() => setSource(id)}
                  >
                    {label}
                    <ArrowUpRight size={13} />
                  </Link>
                ))}
              </div>
            </section>
            <section className="cc-card">
              <h2>Platform management</h2>
              <div className="ec-shortcuts">
                {visibleSections.slice(3).map(([id, label]) => (
                  <Link key={id} to={`/admin/control/enterprise/${id}`}>
                    {label}
                    <ArrowUpRight size={13} />
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
      {section === "analytics" && (
        <>
          <div className="ec-filter">
            <label>
              Source
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
              >
                {sources.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              From
              <input
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Until
              <input
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <label>
              Branch
              <select
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
              >
                <option value="">All authorized branches</option>
                {branches.map((b: any) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Department
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="">All authorized departments</option>
                {departments.map((d: any) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="outline"
              onClick={() =>
                download("/analytics/export", "enterprise-report.csv")
              }
            >
              <Download size={14} />
              Export
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                document
                  .querySelector(".ec-studio")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              <Save size={14} />
              Dashboard studio
            </Button>
          </div>
          {data && (
            <section className="cc-card">
              <div className="cc-heading">
                <div>
                  <h2>{sources.find((s) => s[0] === source)?.[1]}</h2>
                  <p>{data.scope}</p>
                </div>
                <Link to={data.path}>
                  Open records <ArrowUpRight size={13} />
                </Link>
              </div>
              <div className="ec-total">
                {data.count.toLocaleString()} <small>authorized records</small>
              </div>
              {data.amounts.map((a: any) => (
                <p key={a.currency}>
                  {a.currency}: {a.amount}
                </p>
              ))}
              <div className="cc-bars">
                {data.groups.map((g: any) => (
                  <div className="cc-bar" key={g.label}>
                    <span>{g.label}</span>
                    <meter
                      min={0}
                      max={Math.max(1, data.count)}
                      value={g.count}
                      aria-label={`${g.label}: ${g.count}`}
                    />
                    <strong>{g.count}</strong>
                  </div>
                ))}
              </div>
              {!data.groups.length && (
                <Empty>No grouped status data in this source.</Empty>
              )}
            </section>
          )}
        </>
      )}
      {section === "licensing" && data && (
        <>
          <div className="ec-toolbar">
            <Button
              disabled={!actor?.is_superuser}
              title={
                actor?.is_superuser
                  ? "Create plan"
                  : "Global Super Admin required"
              }
              onClick={() => edit("plans")}
            >
              <Plus size={14} />
              Create plan
            </Button>
            <Button
              variant="outline"
              disabled={!actor?.is_superuser}
              title={
                actor?.is_superuser
                  ? "Change plan"
                  : "Global Super Admin required"
              }
              onClick={() => edit("subscription", data)}
            >
              Assign / change company plan
            </Button>
          </div>
          <section className="cc-card">
            <h2>Company license</h2>
            <p>
              {data.subscription?.plan || "No managed plan assigned"} ·{" "}
              <Badge value={data.subscription?.status || "legacy"} />
            </p>
            <p>
              Active seats: {data.activeSeats} · Licensed seats:{" "}
              {data.subscription?.values?.seats ?? "Unspecified"}
            </p>
            <p>
              Renewal: {stamp(data.subscription?.values?.renewal_at)} · Billing:{" "}
              {data.billing}
            </p>
            <p>
              Shared usage ({data.usage?.period} UTC):{" "}
              {(Number(data.usage?.storageBytes || 0) / 1048576).toFixed(2)} MB
              documents /{" "}
              {data.subscription?.values?.storage_mb ?? "Unspecified"} MB;{" "}
              {data.usage?.aiRequests || 0} AI requests;{" "}
              {data.usage?.automationRuns || 0} workflow runs;{" "}
              {data.usage?.apiRequests || 0} business API attempts.
            </p>
            <small>
              Module entitlement is enforced by the backend. Unconfigured
              billing cannot automatically suspend access.
            </small>
          </section>
          <Rows>
            <thead>
              <tr>
                <th>Plan</th>
                <th>Included modules</th>
                <th>Seats</th>
                <th>Storage MB</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.plans.map((p: any) => (
                <tr key={p.id}>
                  <td>
                    {p.name}
                    <small>
                      {p.code} · v{p.version}
                    </small>
                  </td>
                  <td>{p.config_json?.modules?.join(", ") || "Legacy plan"}</td>
                  <td>{p.config_json?.seats ?? "—"}</td>
                  <td>{p.config_json?.storage_mb ?? "—"}</td>
                  <td>
                    <Badge value={p.active ? "active" : "inactive"} />
                  </td>
                  <td>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!actor?.is_superuser}
                      onClick={() => edit("plans", p)}
                    >
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
        </>
      )}
      {section === "flags" && (
        <>
          <Button onClick={() => edit("flags")}>
            <Flag size={14} />
            New feature flag
          </Button>
          <Rows>
            <thead>
              <tr>
                <th>Feature</th>
                <th>Module</th>
                <th>Environment</th>
                <th>Rollout</th>
                <th>Status</th>
                <th>Review / expiry</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(data || []).map((f: any) => (
                <tr key={f.id}>
                  <td>
                    {f.value_json?.name || f.flag_key}
                    <small>{f.flag_key}</small>
                  </td>
                  <td>{f.module_key}</td>
                  <td>{f.value_json?.environment || "production"}</td>
                  <td>{f.value_json?.percentage ?? 100}%</td>
                  <td>
                    <Badge value={f.enabled ? "enabled" : "disabled"} />
                  </td>
                  <td>{stamp(f.value_json?.expires_at)}</td>
                  <td>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => edit("flags", f)}
                    >
                      Edit / disable
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={
                        !Object.keys(f.value_json?.previous?.config || {})
                          .length
                      }
                      onClick={() =>
                        mutate(async () => {
                          await api.post(root + `/flags/${f.id}/rollback`, {
                            companyId: company,
                            version: f.value_json?.version || 0,
                            reason:
                              "Rollback selected flag to its prior configuration",
                          });
                        })
                      }
                    >
                      Rollback
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
          {data?.length === 0 && (
            <Empty>
              No company feature flags configured. Optional features default
              off.
            </Empty>
          )}
        </>
      )}
      {section === "branding" && (
        <section className="cc-card">
          <div className="cc-heading">
            <h2>Company name & logo across all modules</h2>
            <Button onClick={() => edit("branding", data?.[0])}>
              <Palette size={14} />
              Edit branding
            </Button>
          </div>
          <div
            className="ec-brand-preview"
            style={{
              background: data?.[0]?.values_json?.surface || "#fff",
              color: data?.[0]?.values_json?.text || "#171717",
              borderRadius: data?.[0]?.values_json?.radius || 8,
            }}
          >
            {data?.[0]?.values_json?.logoPath && <img src={assetUrl(data[0].values_json.logoPath)} alt="Company logo" className="mb-3 h-16 w-16 object-contain" />}
            <strong>
              {data?.[0]?.values_json?.appName || "Business Suite"}
            </strong>
            <p>Company workspace</p>
            <span
              style={{
                background: data?.[0]?.values_json?.primary || "#6d28d9",
                color: "white",
                padding: "8px 16px",
                borderRadius: 6,
              }}
            >
              Brand accent preview
            </span>
          </div>
          <p>
            Text contrast is checked by the backend. Domains remain unverified
            until an authorized infrastructure operation.
          </p>
        </section>
      )}
      {section === "health" && data && (
        <>
          <div className="ec-kpis">
            {[
              ["API · 24 hours", data.api.status],
              ["Database", data.database.status],
              ["Worker heartbeat", data.worker.status],
              ["Frontend probe", data.frontend.status],
            ].map(([label, value]) => (
              <section className="cc-card" key={label}>
                <h2>{label}</h2>
                <Badge value={value} />
              </section>
            ))}
          </div>
          <div className="ec-grid">
            <section className="cc-card">
              <h2>Requests & latency</h2>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  mutate(async () => {
                    const result = await api.post(root + "/alerts/evaluate", {
                      companyId: company,
                      reason: "Evaluate current operational alert signals",
                    });
                    setNotice(
                      `${result.data.created} inbox alerts created; duplicate alerts have a 15-minute cooldown.`,
                    );
                  })
                }
              >
                Evaluate operational alerts
              </Button>
              <p>
                {data.api.requests} requests · {data.api.errors} server errors
              </p>
              <p>
                P50: {data.api.latencyMs.p50 ?? "—"} ms · P95:{" "}
                {data.api.latencyMs.p95 ?? "—"} ms · P99:{" "}
                {data.api.latencyMs.p99 ?? "—"} ms
              </p>
              <small>
                Latest {data.api.sampleCount} latency samples; limit{" "}
                {data.api.sampleLimit}. Observed {stamp(data.observedAt)}.
              </small>
            </section>
            <section className="cc-card">
              <h2>Queues</h2>
              <h3>Workflows</h3>
              {data.workflowQueue.map((q: any) => (
                <p key={q.status}>
                  {q.status}: {q.count}
                </p>
              ))}
              <h3>Email</h3>
              {data.emailQueue.map((q: any) => (
                <p key={q.status}>
                  {q.status}: {q.count}
                </p>
              ))}
              <Link to="/admin/control/services/executions">
                Inspect executions
              </Link>
            </section>
            <section className="cc-card">
              <h2>Storage & infrastructure</h2>
              <p>
                Managed documents: {data.documentBytes.toLocaleString()} bytes
              </p>
              <p>
                Database pool size: {data.pool.size ?? "Unavailable"} · checked
                out: {data.pool.checkedOut ?? "Unavailable"}
              </p>
              <p>{data.infrastructure.reason}</p>
              <Button
                variant="outline"
                onClick={() => download("/diagnostics", "diagnostics.json")}
              >
                Download sanitized diagnostics
              </Button>
            </section>
          </div>
        </>
      )}
      {section === "errors" && (
        <>
          <Rows>
            <thead>
              <tr>
                <th>Error group</th>
                <th>Module / endpoint</th>
                <th>Occurrences</th>
                <th>Latest</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data?.items?.map((e: any) => (
                <tr key={e.key}>
                  <td>
                    {e.type || "HTTP 500"}
                    <small>{e.key}</small>
                  </td>
                  <td>
                    {e.module}
                    <small>{e.endpoint}</small>
                  </td>
                  <td>{e.frequency}</td>
                  <td>{stamp(e.latest)}</td>
                  <td>
                    <Badge value={e.status} />
                  </td>
                  <td>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setValues({ status: "acknowledged", notes: "" });
                        setReason("");
                        setEditor({
                          kind: "error_resolution",
                          key: e.key,
                          version: e.version || 0,
                        });
                      }}
                    >
                      Review
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
          {data?.total === 0 && (
            <Empty>No recorded server errors for this company.</Empty>
          )}
          <p>
            Exception messages and request payloads are excluded from this view.
          </p>
        </>
      )}
      {section === "backups" && data && (
        <>
          <div className="ec-toolbar">
            <Button
              onClick={() => {
                setValues({});
                setReason("");
                setEditor({ kind: "backup" });
              }}
            >
              <Database size={14} />
              Create backup
            </Button>
            <Button variant="outline" onClick={() => edit("recovery_request")}>
              Request non-production recovery
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setValues({
                  enabled: data.policy?.enabled || false,
                  intervalHours: data.policy?.interval_hours || 24,
                  retainAutomatic: data.policy?.retain_automatic || 14,
                });
                setReason("");
                setEditor({ kind: "backup_policy" });
              }}
            >
              Backup policy
            </Button>
          </div>
          <p>{data.restore_mode}</p>
          <Rows>
            <thead>
              <tr>
                <th>Backup</th>
                <th>Created</th>
                <th>Size</th>
                <th>Status</th>
                <th>Verification</th>
              </tr>
            </thead>
            <tbody>
              {data.archives?.map((b: any) => (
                <tr key={b.id}>
                  <td>{b.id}</td>
                  <td>{stamp(b.created_at)}</td>
                  <td>{b.bytes.toLocaleString()} bytes</td>
                  <td>
                    <Badge value={b.state} />
                  </td>
                  <td>
                    {b.verification?.databaseRestore || "Verification required"}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        mutate(async () => {
                          await api.post(root + `/backups/${b.id}/verify`, {
                            companyId: company,
                            reason:
                              "Verify selected backup in isolated recovery context",
                          });
                        })
                      }
                    >
                      Verify archive
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
          {!data.archives?.length && (
            <Empty>
              No available archives in the configured backup destination.
            </Empty>
          )}
          <p>
            Scheduled backups: {data.scheduler_enabled ? "enabled" : "disabled"}
            . Production restoration requires the privileged offline procedure.
          </p>
        </>
      )}
      {section === "governance" && (
        <>
          <Button onClick={() => edit("governance")}>
            <ShieldCheck size={14} />
            Configure entity governance
          </Button>
          <Rows>
            <thead>
              <tr>
                <th>Entity</th>
                <th>Classification</th>
                <th>Retention</th>
                <th>Hold</th>
                <th>Policy reference</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(data || []).map((p: any) => (
                <tr key={p.id}>
                  <td>
                    {p.values_json.module} / {p.values_json.entity}
                  </td>
                  <td>
                    <Badge value={p.values_json.classification} />
                  </td>
                  <td>
                    {p.values_json.retentionDays
                      ? `${p.values_json.retentionDays} days`
                      : "Not configured"}
                  </td>
                  <td>{p.values_json.legalHold ? "Active hold" : "No hold"}</td>
                  <td>{p.values_json.legalBasis || "—"}</td>
                  <td>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => edit("governance", p)}
                    >
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
          <p>
            Restricted classification is enforced on shared access, analytics
            and native module routes. Native routes use a conservative
            module-wide restriction until finer entity adapters are verified.
            Generic retention does not delete business, employment or statutory
            records.
          </p>
        </>
      )}
      {section === "support" && (
        <>
          <div className="ec-toolbar">
            <Button onClick={() => edit("support")}>
              <LifeBuoy size={14} />
              New ticket / incident
            </Button>
            <Button
              variant="outline"
              disabled={!actor?.is_superuser}
              title={
                actor?.is_superuser
                  ? "Request access review"
                  : "Global Super Admin required"
              }
              onClick={() => edit("support_access_request")}
            >
              Request support access
            </Button>
          </div>
          <Rows>
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Module</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Owner</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data?.items?.map((t: any) => (
                <tr key={t.id}>
                  <td>
                    {t.subject}
                    <small>
                      {t.ticket_number} · {t.detail_json?.kind || "support"}
                    </small>
                  </td>
                  <td>{t.module_key}</td>
                  <td>
                    <Badge value={t.priority} />
                  </td>
                  <td>
                    <Badge value={t.status} />
                  </td>
                  <td>{t.assigned_to || "Unassigned"}</td>
                  <td>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setValues({
                          status: t.status,
                          assignedTo: t.assigned_to,
                          comment: "",
                        });
                        setReason("");
                        setEditor({
                          kind: "ticket_change",
                          id: t.id,
                          version: t.version,
                        });
                      }}
                    >
                      Manage
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Rows>
          {data?.total === 0 && <Empty>No company support tickets.</Empty>}
          <p>
            Support requests grant no hidden impersonation. Access continues to
            require explicit company memberships and module permissions.
          </p>
        </>
      )}
      {section === "actions" && (
        <div className="ec-grid">
          {data?.items?.map((a: any) => (
            <Link className="cc-card ec-action" key={a.id} to={a.path}>
              <Badge value={a.priority} />
              <h2>{a.title}</h2>
              <span>
                Review {a.type}
                <ArrowUpRight size={14} />
              </span>
            </Link>
          ))}
          {data?.items?.length === 0 && (
            <Empty>No open recorded operational actions.</Empty>
          )}
          <Link className="cc-card" to="/hrms/approvals">
            Approval inbox <ArrowUpRight size={14} />
          </Link>
          <Link className="cc-card" to="/admin/control/security">
            Security reviews <ArrowUpRight size={14} />
          </Link>
        </div>
      )}
      {section === "coverage" && data && (
        <Rows>
          <thead>
            <tr>
              <th>Discovered module</th>
              <th>Installed</th>
              <th>Authentication / entitlement</th>
              <th>Record adapters</th>
              <th>Analytics</th>
            </tr>
          </thead>
          <tbody>
            {data.modules.map((m: any) => (
              <tr key={m.key}>
                <td>
                  {m.label}
                  <small>{m.key}</small>
                </td>
                <td>{m.installed ? "Yes" : "No"}</td>
                <td>
                  {m.authentication}
                  <small>{m.entitlements}</small>
                </td>
                <td>
                  {m.recordAdapters.join(", ") || "Domain adapter pending"}
                </td>
                <td>{m.analytics.join(", ") || "Not registered"}</td>
              </tr>
            ))}
          </tbody>
        </Rows>
      )}
      {section === "analytics" && (
        <DashboardStudio company={company} mutate={mutate} />
      )}
      <Dialog
        open={!!editor}
        onOpenChange={(open) => {
          if (!open) setEditor(null);
        }}
      >
        <DialogContent className="ec-dialog">
          <DialogTitle>{editor?.kind?.replace(/_/g, " ")}</DialogTitle>
          <div className="ec-editor">
            {editor?.kind === "branding" && actor?.is_superuser && <label>Upload company logo (PNG, JPEG or WebP, up to 2 MB)
              <input type="file" accept="image/png,image/jpeg,image/webp" onChange={async event => {
                const file = event.target.files?.[0]; if (!file) return;
                if (file.size > 2 * 1024 * 1024) { setError("Logo must be 2 MB or smaller"); return; }
                const body = new FormData(); body.append("file", file);
                try { const response = await api.post(`${root}/branding/logo`, body, {params:{companyId:company}}); setValues((old:any) => ({...old,logoPath:response.data.url})); }
                catch(e) { setError(text(e)); }
                event.target.value = "";
              }} />
              {values.logoPath && <img src={assetUrl(values.logoPath)} alt="Logo preview" className="h-16 w-16 object-contain" />}
            </label>}
            {Object.entries(values).map(([name, value]) => (
              <Field
                key={name}
                name={name}
                value={value}
                onChange={(v) =>
                  setValues((old: any) => ({ ...old, [name]: v }))
                }
              />
            ))}
            <label>
              Reason
              <input
                aria-label="Reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="cc-error">
                {error}
              </p>
            )}
          </div>
          <Button
            onClick={() => {
              if (editor.kind === "backup_policy")
                mutate(async () => {
                  await api.put(root + "/backups/policy", {
                    companyId: company,
                    reason,
                    ...values,
                  });
                  setEditor(null);
                });
              else if (editor.kind === "backup")
                mutate(async () => {
                  await api.post(root + "/backups", {
                    companyId: company,
                    reason,
                  });
                  setEditor(null);
                });
              else if (editor.kind === "ticket_change")
                mutate(async () => {
                  await api.put(root + `/tickets/${editor.id}`, {
                    companyId: company,
                    version: editor.version,
                    reason,
                    ...values,
                  });
                  setEditor(null);
                });
              else save();
            }}
          >
            <Save size={14} />
            Save
          </Button>
        </DialogContent>
      </Dialog>
      <Dialog open={step} onOpenChange={setStep}>
        <DialogContent>
          <DialogTitle>Confirm your administrator session</DialogTitle>
          <p>Administrative changes require the existing password step-up.</p>
          <input
            aria-label="Administrator password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            onClick={async () => {
              try {
                const token = (await api.post("/access/step-up", { password }))
                  .data.token;
                api.defaults.headers.common["X-Access-Step-Up"] = token;
                setPassword("");
                setStep(false);
                try {
                  if (pending) await pending();
                } finally {
                  delete api.defaults.headers.common["X-Access-Step-Up"];
                }
                setPending(null);
              } catch (e) {
                setError(text(e));
              }
            }}
          >
            Verify and save
          </Button>
        </DialogContent>
      </Dialog>
    </main>
  );
}
