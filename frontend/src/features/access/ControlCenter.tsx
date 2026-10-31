import AdminVerification, { administratorStepUp } from "./AdminVerification";
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Building2,
  LayoutDashboard,
  ShieldCheck,
  Boxes,
  History,
  Users,
  Plus,
  RefreshCw,
  ArrowUpRight,
} from "lucide-react";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import "./access.css";
import "./control.css";

const root = "/access/control";
const errorText = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : JSON.stringify(e?.response?.data?.detail || e.message);
const date = (value: any) =>
  value ? new Date(value).toLocaleString() : "Never";
const baseCompany = {
  name: "",
  legal_name: "",
  country: "India",
  registration_number: "",
  gstin: "",
  default_currency: "INR",
  default_timezone: "Asia/Kolkata",
  is_active: true,
};

export function ControlNav() {
  const path = useLocation().pathname;
  return (
    <nav aria-label="Master Suite" className="cc-nav">
      {[
        ["Dashboard", "/admin/control/dashboard"],
        ["Organizations", "/admin/control/organizations"],
        ["Users & Access", "/admin/access"],
        ["Roles & Permissions", "/admin/access?tab=Roles"],
        ["Module Management", "/admin/control/modules"],
        ["Security Center", "/admin/control/security"],
        ["Audit Logs", "/admin/control/audit"],
        ["Statistics Audit", "/admin/control/statistics"],
    ["Shared Services", "/admin/control/services/services"],
    ["Enterprise", "/admin/control/enterprise/overview"],
    ["AI Security", "/admin/control/ai-security"],
      ].map(([label, to]) => (
        <Link
          key={label}
          aria-current={path === to ? "page" : undefined}
          to={to}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}

function Bars({
  title,
  values,
}: {
  title: string;
  values: Record<string, number>;
}) {
  const max = Math.max(1, ...Object.values(values));
  return (
    <section className="cc-card">
      <h2>{title}</h2>
      {Object.keys(values).length ? (
        <div className="cc-bars">
          {Object.entries(values).map(([key, count]) => (
            <div className="cc-bar" key={key}>
              <span title={key}>{key}</span>
              <meter
                min={0}
                max={max}
                value={count}
                aria-label={`${key}: ${count}`}
              />
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="cc-empty">No records yet.</p>
      )}
    </section>
  );
}

function Events({ rows }: { rows: any[] }) {
  return (
    <div className="cc-scroll">
      <table>
        <thead>
          <tr>
            <th>When</th>
            <th>Action</th>
            <th>Actor</th>
            <th>Target</th>
            <th>Result</th>
            <th>Reason</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e: any) => (
            <tr key={e.id}>
              <td>{date(e.created_at)}</td>
              <td>{e.operation}</td>
              <td>#{e.actor_id}</td>
              <td>{e.target_id ? `#${e.target_id}` : "Organization"}</td>
              <td>{e.outcome}</td>
              <td>{e.reason}</td>
              <td>
                <details>
                  <summary>Inspect event</summary>
                  <p>
                    IP: {e.source_ip || "Unavailable"} · Session:{" "}
                    {e.session_id || "Unavailable"}
                  </p>
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      maxWidth: 440,
                      overflowWrap: "anywhere",
                    }}
                  >
                    {JSON.stringify(
                      { before: e.before_json, after: e.after_json },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <p className="cc-empty">No matching administrative events.</p>
      )}
    </div>
  );
}

export default function ControlCenter() {
  const actor = useAuthStore((s) => s.user);
  const section = useLocation().pathname.split("/").pop() || "dashboard";
  const [company, setCompany] = useState(
    Number(
      sessionStorage.getItem("suite-organization") ||
        actor?.access?.companyId ||
        1,
    ),
  );
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [data, setData] = useState<any>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [dialog, setDialog] = useState<any>();
  const [values, setValues] = useState<any>({});
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({
    action: "",
    result: "",
    userId: "",
    module: "",
    start: "",
    end: "",
  });
  const [page, setPage] = useState(1);
  const [moduleDetail, setModuleDetail] = useState<any>();
  const title =
    (
      {
        dashboard: "Dashboard",
        organizations: "Organizations",
        modules: "Module Management",
        security: "Security Center",
        audit: "Audit Logs",
      } as Record<string, string>
    )[section] || "Dashboard";
  useEffect(() => {
    if (!actor?.is_superuser && !actor?.access?.isAccessAdmin) return;
    let active = true;
    setLoading(true);
    setError("");
    setData(undefined);
    const params = {
      companyId: company,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
      page,
    };
    Promise.all([
      api.get(`${root}/organizations`),
      api.get(`${root}/${section}`, { params }),
    ])
      .then(([org, payload]) => {
        if (active) {
          setOrganizations(org.data);
          setData(payload.data);
        }
      })
      .catch((e) => active && setError(errorText(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [section, company, revision, filters, page, actor?.id]);
  if (!actor?.is_superuser && !actor?.access?.isAccessAdmin)
    return <p role="alert">Access administrator permission is required.</p>;
  const open = (config: any, initial: any = {}) => {
    setDialog(config);
    setValues(initial);
    setReason("");
    setPassword("");
    setError("");
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data: step } = await administratorStepUp(password);
      const body = dialog.body ? dialog.body(values) : values;
      await api.request({
        url: dialog.url,
        method: dialog.method || "post",
        data: { ...body, reason },
        headers: { "X-Access-Step-Up": step.token },
      });
      setDialog(undefined);
      setPassword("");
      setNotice("Saved. Authorization is enforced by the backend.");
      setRevision((r) => r + 1);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const field = (
    label: string,
    key: string,
    type = "text",
    required = false,
  ) => (
    <label className="cc-field" key={key}>
      {label}
      <input
        required={required}
        type={type}
        value={values[key] ?? ""}
        onChange={(e) =>
          setValues({
            ...values,
            [key]: type === "number" ? Number(e.target.value) : e.target.value,
          })
        }
      />
    </label>
  );
  const activeOrg = organizations.find((c) => c.id === company);
  const editOrg = (org?: any) =>
    open(
      {
        title: org ? "Edit company" : "Add company",
        type: "company",
        method: org ? "put" : "post",
        url: org ? `${root}/organizations/${org.id}` : `${root}/organizations`,
        body: (v: any) => ({
          ...Object.fromEntries(Object.keys(baseCompany).map((k) => [k, v[k]])),
          expectedUpdatedAt: org?.updated_at || null,
        }),
      },
      org || baseCompany,
    );
  const editUnit = (kind: string, unit?: any, branchId?: number) =>
    open(
      {
        title: `${unit ? "Edit" : "Add"} ${kind === "branches" ? "branch" : "department"}`,
        type: kind,
        url: `${root}/units/${kind}${unit ? `/${unit.id}` : ""}`,
        method: unit ? "put" : "post",
        body: (v: any) => ({
          companyId: company,
          name: v.name,
          code: v.code || null,
          is_active: v.is_active,
          country: v.country || "India",
          city: v.city || null,
          branch_id: kind === "departments" ? Number(v.branch_id) : null,
          head_employee_id: v.head_employee_id
            ? Number(v.head_employee_id)
            : null,
          manager_employee_id: v.manager_employee_id
            ? Number(v.manager_employee_id)
            : null,
          expectedUpdatedAt: unit?.updated_at || null,
        }),
      },
      unit || {
        name: "",
        code: "",
        is_active: true,
        branch_id: branchId,
        country: "India",
      },
    );
  const downloadAudit = async () => {
    try {
      const r = await api.get(`${root}/audit`, {
        params: {
          companyId: company,
          ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
          export: true,
        },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "access-audit.csv";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 500);
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <main className="ua-root cc-root">
      <div className="cc-heading">
        <div>
          <p className="cc-eyebrow">MASTER SUITE / SUPER ADMIN</p>
          <h1>
            <ShieldCheck size={22} />
            {title}
          </h1>
          <p>Central control for identity, organizations and access.</p>
        </div>
        <Button variant="outline" onClick={() => setRevision((r) => r + 1)}>
          <RefreshCw size={14} />
          Refresh
        </Button>
      </div>
      <ControlNav />
      {section !== "dashboard" && (
        <label className="cc-company">
          Company
          <select
            aria-label="Company"
            value={company}
            onChange={(e) => {
              sessionStorage.setItem("suite-organization", e.target.value);
              window.dispatchEvent(new Event("suite:organization-changed"));
              window.dispatchEvent(new Event("focus"));
              setCompany(Number(e.target.value));
              setPage(1);
            }}
          >
            {organizations.map((c) => (
              <option value={c.id} key={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && (
        <p role="alert" className="cc-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {loading && (
        <div aria-label="Loading control center" className="cc-skeleton" />
      )}
      {data && section === "dashboard" && (
        <>
          <p className="text-sm text-muted-foreground">Across all organizations you administer. Account totals count unique identities; organization charts count membership in each organization.</p>
          <div className="cc-stats">
            {Object.entries(data.summary).map(([label, value]) => (
              <section className="cc-card" key={({"Total users":"Provisioned accounts","Active users":"Login-enabled users","Suspended users":"Restricted org access"} as Record<string,string>)[label]||label}>
                <span>{({"Total users":"Provisioned accounts","Active users":"Login-enabled users","Suspended users":"Restricted org access"} as Record<string,string>)[label]||label}</span>
                <strong>{String(value)}</strong>
              </section>
            ))}
          </div>
          <section className="cc-card cc-actions">
            <Link to="/admin/access?action=add">
              <Plus size={14} />
              Add User
            </Link>
            <Link to="/admin/access?action=invite">Invite User</Link>
            {actor.is_superuser && (
              <Button variant="outline" onClick={() => editOrg()}>
                Add Company
              </Button>
            )}
            <Link to="/admin/access?tab=Roles">Manage Roles</Link>
            <Link to="/admin/access">Assign Modules</Link>
            <Link to="/admin/control/audit">View Audit Logs</Link>
          </section>
          <div className="cc-charts">
            {Object.entries(data.charts).map(([key, values]) => (
              <Bars
                key={key}
                title={key}
                values={values as Record<string, number>}
              />
            ))}
          </div>
          <section className="cc-card">
            <h2>Recent administrative activity</h2>
            <Events rows={data.activity} />
          </section>
        </>
      )}
      {data && section === "organizations" && (
        <>
          <div className="cc-actions">
            {actor.is_superuser && (
              <Button onClick={() => editOrg()}>Add Company</Button>
            )}
            <Button variant="outline" onClick={() => editUnit("branches")}>
              Add Branch
            </Button>
            <Link to="/admin/access">
              Assign company admins and memberships
              <ArrowUpRight size={14} />
            </Link>
          </div>
          {activeOrg ? (
            <section className="cc-card">
              <div className="cc-heading">
                <div>
                  <h2>
                    <Building2 size={18} />
                    {activeOrg.name}
                  </h2>
                  <p>
                    {activeOrg.legal_name || "Legal name not set"} ·{" "}
                    {activeOrg.country} · {activeOrg.default_currency} ·{" "}
                    {activeOrg.default_timezone}
                  </p>
                </div>
                <Button variant="outline" onClick={() => editOrg(activeOrg)}>
                  Edit Company
                </Button>
              </div>
              <div className="cc-meta">
                <span>{activeOrg.is_active ? "Active" : "Inactive"}</span>
                <span>{activeOrg.userCount} users</span>
                <span>{activeOrg.admins.length} assigned admins</span>
                <span>
                  Registration: {activeOrg.registration_number || "Not set"}
                </span>
                <span>Tax: {activeOrg.gstin || "Not set"}</span>
              </div>
              <p>
                Enabled modules: {activeOrg.enabledModules.join(", ") || "None"}
              </p>
              {activeOrg.branches.map((b: any) => (
                <section className="cc-branch" key={b.id}>
                  <div className="cc-heading">
                    <div>
                      <h3>
                        {b.name} {b.code && `(${b.code})`}
                      </h3>
                      <p>
                        {[b.city, b.country].filter(Boolean).join(", ")} ·{" "}
                        {b.is_active ? "Active" : "Inactive"}
                      </p>
                    </div>
                    <div className="cc-actions">
                      <Button
                        variant="outline"
                        onClick={() => editUnit("branches", b)}
                      >
                        Edit Branch
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => editUnit("departments", undefined, b.id)}
                      >
                        Add Department
                      </Button>
                    </div>
                  </div>
                  <div className="cc-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Department</th>
                          <th>Head</th>
                          <th>Employees</th>
                          <th>Status</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {b.departments.map((d: any) => (
                          <tr key={d.id}>
                            <td>{d.name}</td>
                            <td>
                              {activeOrg.employees.find(
                                (e: any) => e.id === d.head_employee_id,
                              )?.name || "Unassigned"}
                            </td>
                            <td>{d.employeeCount}</td>
                            <td>{d.is_active ? "Active" : "Inactive"}</td>
                            <td>
                              <Button
                                variant="ghost"
                                onClick={() => editUnit("departments", d)}
                              >
                                Edit
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!b.departments.length && (
                      <p className="cc-empty">
                        No departments. Add one to organize existing employees.
                      </p>
                    )}
                  </div>
                </section>
              ))}
              {!activeOrg.branches.length && (
                <p className="cc-empty">This company has no branches yet.</p>
              )}
              <h3>Reporting teams</h3>
              <p>Derived from existing HRMS reporting relationships.</p>
              {(activeOrg.reportingTeams || []).map((team: any) => (
                <details className="cc-branch" key={team.managerId}>
                  <summary>
                    {team.manager} · {team.users.length} team members
                  </summary>
                  {team.users.map((member: any) => (
                    <p key={member.employeeId}>
                      {member.name}{" "}
                      {member.userId && (
                        <Link to={`/admin/control/users/${member.userId}`}>
                          Account access
                        </Link>
                      )}
                    </p>
                  ))}
                </details>
              ))}
              {!activeOrg.reportingTeams?.length && (
                <p className="cc-empty">
                  No reporting teams are configured in HRMS for this company.
                </p>
              )}
            </section>
          ) : (
            <p>No authorized organization selected.</p>
          )}
        </>
      )}
      {data && section === "modules" && (
        <section className="cc-card">
          <p>
            Company entitlements are checked before individual grants. Disabling
            a module blocks its APIs for this company. Unconfigured companies
            preserve their installed-module defaults.
          </p>
          <div className="cc-scroll">
            <table>
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Company access</th>
                  <th>Authorized users</th>
                  <th>Companies enabled</th>
                  <th>Permissions</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.map((m: any) => (
                  <tr key={m.key}>
                    <td>
                      <Boxes size={16} />
                      <strong>{m.label}</strong>
                      <small>
                        {m.key} · {m.route}
                      </small>
                    </td>
                    <td>
                      <label>
                        <input
                          aria-label={`${m.label} enabled for company`}
                          type="checkbox"
                          checked={m.companyEnabled}
                          disabled={!actor.is_superuser || !m.installed}
                          onChange={() =>
                            open({
                              title: `${m.companyEnabled ? "Disable" : "Enable"} ${m.label}`,
                              type: "entitlement",
                              url: `${root}/modules/${m.key}`,
                              method: "put",
                              body: () => ({
                                companyId: company,
                                enabled: !m.companyEnabled,
                                version: m.entitlementVersion,
                              }),
                            })
                          }
                        />
                        {m.installed
                          ? m.companyEnabled
                            ? "Enabled"
                            : "Disabled"
                          : "Not installed"}
                      </label>
                    </td>
                    <td>{m.authorizedUsers}</td>
                    <td>{m.companiesUsing}</td>
                    <td>{m.permissions.length}</td>
                    <td>
                      <Button
                        variant="ghost"
                        onClick={() => setModuleDetail(m)}
                      >
                        Details
                      </Button>
                      <Link to={`/admin/access?module=${m.key}`}>
                        Assign users
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {data && section === "security" && (
        <>
          <div className="cc-stats">
            <section className="cc-card">
              <span>Active sessions shown</span>
              <strong>{data.sessions.length}</strong>
            </section>
            <section className="cc-card">
              <span>Recent login failures shown</span>
              <strong>{data.failures.length}</strong>
            </section>
            <section className="cc-card">
              <span>Privileged accounts</span>
              <strong>{data.privileged.length}</strong>
            </section>
          </div>
          <section className="cc-card">
            <h2>Privileged accounts</h2>
            {data.privileged.map((u: any) => (
              <p key={u.id}>
                {u.email} · MFA{" "}
                {u.mfaEnabled ? "enabled" : "not enrolled — review recommended"}{" "}
                <Link to={`/admin/control/users/${u.id}`}>Review account</Link>
              </p>
            ))}
          </section>
          <section className="cc-card">
            <h2>Active sessions</h2>
            <div className="cc-scroll">
              <table>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Device</th>
                    <th>IP</th>
                    <th>Last seen</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.sessions.map((s: any) => (
                    <tr key={s.id}>
                      <td>#{s.userId}</td>
                      <td>{s.device || "Browser"}</td>
                      <td>{s.ip || "Unavailable"}</td>
                      <td>{date(s.lastSeen)}</td>
                      <td>
                        <Button
                          variant="outline"
                          onClick={() =>
                            open({
                              title: `Revoke sessions for user #${s.userId}`,
                              type: "revoke",
                              url: `${root}/sessions/revoke`,
                              body: () => ({
                                companyId: company,
                                userId: s.userId,
                              }),
                            })
                          }
                        >
                          Revoke user sessions
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.sessions.length && (
                <p className="cc-empty">
                  No active sessions in this organization.
                </p>
              )}
            </div>
          </section>
          <section className="cc-card">
            <h2>Login failures</h2>
            {data.failures.map((f: any, index: number) => (
              <p key={index}>
                User #{f.userId} · {f.status} · {date(f.at)} ·{" "}
                {f.ip || "Unknown IP"}
              </p>
            ))}
            {!data.failures.length && (
              <p>No recorded failures for known accounts.</p>
            )}
          </section>
          <section className="cc-card">
            <h2>Password and MFA requirements</h2>
            <p>
              {data.policyScope}. MFA enrollment uses the existing
              authentication flow.
            </p>
            {actor.is_superuser && (
              <Button
                variant="outline"
                onClick={() => {
                  const policy = data.passwordPolicies
                    .filter((p: any) => p.is_active)
                    .sort((a: any, b: any) => b.id - a.id)[0];
                  open(
                    {
                      title: "Configure password policy",
                      type: "policy",
                      method: "put",
                      url: `${root}/password-policy`,
                      body: (v: any) => ({
                        name: v.name,
                        min_length: Number(v.min_length),
                        require_uppercase: v.require_uppercase,
                        require_lowercase: v.require_lowercase,
                        require_number: v.require_number,
                        require_special: v.require_special,
                        max_age_days: Number(v.max_age_days),
                        lockout_attempts: Number(v.lockout_attempts),
                        lockout_duration_minutes: Number(
                          v.lockout_duration_minutes,
                        ),
                        mfa_required: v.mfa_required,
                        expected: policy || {},
                      }),
                    },
                    policy || {
                      name: "Suite default",
                      min_length: 8,
                      max_age_days: 90,
                      lockout_attempts: 5,
                      lockout_duration_minutes: 30,
                      require_uppercase: true,
                      require_lowercase: true,
                      require_number: true,
                      require_special: false,
                      mfa_required: false,
                    },
                  );
                }}
              >
                Configure Policy
              </Button>
            )}
            <p>
              <Link to="/admin/access">
                Suspend or reactivate accounts in Users & Access
              </Link>
            </p>
          </section>
        </>
      )}
      {data && section === "audit" && (
        <section className="cc-card">
          <div className="cc-filter">
            {Object.entries(filters).map(([key, value]) => (
              <label key={key}>
                {key}
                <input
                  aria-label={`Filter ${key}`}
                  type={
                    key === "start" || key === "end" ? "datetime-local" : "text"
                  }
                  value={value}
                  onChange={(e) => {
                    setFilters({ ...filters, [key]: e.target.value });
                    setPage(1);
                  }}
                />
              </label>
            ))}
            {actor.is_superuser && (
              <Button variant="outline" onClick={downloadAudit}>
                Export Audit CSV
              </Button>
            )}
          </div>
          <Events rows={data.items} />
          <div className="cc-actions">
            <Button
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span>
              Page {page} · {data.total} events
              {data.capped ? " (10,000 event cap; narrow date filters)" : ""}
            </span>
            <Button
              variant="outline"
              disabled={page * 50 >= data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </section>
      )}
      <Dialog
        open={!!dialog}
        onOpenChange={(v) => {
          if (!v && !busy) {
            setDialog(undefined);
            setPassword("");
          }
        }}
      >
        <DialogContent className="ua-root cc-dialog">
          <DialogTitle>{dialog?.title || "Administrative change"}</DialogTitle>
          <form onSubmit={save}>
            {dialog?.type === "company" && (
              <div className="cc-form-grid">
                {Object.entries(baseCompany)
                  .filter(([k]) => k !== "is_active")
                  .map(([k]) =>
                    field(
                      k.replace(/_/g, " "),
                      k,
                      "text",
                      [
                        "name",
                        "country",
                        "default_currency",
                        "default_timezone",
                      ].includes(k),
                    ),
                  )}
              </div>
            )}
            {["branches", "departments"].includes(dialog?.type) && (
              <div className="cc-form-grid">
                {field("Name", "name", "text", true)}
                {field("Code", "code")}
                {dialog?.type === "branches" ? (
                  <>
                    {field("Country", "country")}
                    {field("City / Location", "city")}
                    <label>
                      Branch manager
                      <select
                        value={values.manager_employee_id || ""}
                        onChange={(e) =>
                          setValues({
                            ...values,
                            manager_employee_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Unassigned</option>
                        {activeOrg?.employees.map((e: any) => (
                          <option key={e.id} value={e.id}>
                            {e.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      Branch
                      <select
                        required
                        value={values.branch_id || ""}
                        onChange={(e) =>
                          setValues({ ...values, branch_id: e.target.value })
                        }
                      >
                        <option value="">Choose branch</option>
                        {activeOrg?.branches.map((b: any) => (
                          <option key={b.id} value={b.id}>
                            {b.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Department head
                      <select
                        value={values.head_employee_id || ""}
                        onChange={(e) =>
                          setValues({
                            ...values,
                            head_employee_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Unassigned</option>
                        {activeOrg?.employees.map((e: any) => (
                          <option key={e.id} value={e.id}>
                            {e.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                )}
              </div>
            )}
            {["company", "branches", "departments"].includes(dialog?.type) && (
              <label>
                <input
                  type="checkbox"
                  checked={!!values.is_active}
                  onChange={(e) =>
                    setValues({ ...values, is_active: e.target.checked })
                  }
                />
                Active
              </label>
            )}
            {dialog?.type === "policy" && (
              <div className="cc-form-grid">
                {field("Policy name", "name", "text", true)}
                {[
                  "min_length",
                  "max_age_days",
                  "lockout_attempts",
                  "lockout_duration_minutes",
                ].map((k) => field(k.replace(/_/g, " "), k, "number", true))}
                {[
                  "require_uppercase",
                  "require_lowercase",
                  "require_number",
                  "require_special",
                  "mfa_required",
                ].map((k) => (
                  <label key={k}>
                    <input
                      type="checkbox"
                      checked={!!values[k]}
                      onChange={(e) =>
                        setValues({ ...values, [k]: e.target.checked })
                      }
                    />
                    {k.replace(/_/g, " ")}
                  </label>
                ))}
              </div>
            )}
            {dialog?.type === "entitlement" && (
              <p>
                This changes company-wide access immediately, including existing
                user grants and background authorization. Review the selected
                company before saving.
              </p>
            )}
            {dialog?.type === "revoke" && (
              <p>
                All active sessions for this account will be revoked. The user
                must log in again.
              </p>
            )}
            <label className="cc-field">
              Reason
              <textarea
                minLength={3}
                maxLength={500}
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <AdminVerification value={password} onChange={setPassword} />
            {error && <p role="alert">{error}</p>}
            <Button disabled={busy} type="submit">
              {busy ? "Saving…" : "Verify & Save"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!moduleDetail}
        onOpenChange={(v) => !v && setModuleDetail(undefined)}
      >
        <DialogContent className="ua-root cc-dialog">
          <DialogTitle>{moduleDetail?.label || "Module details"}</DialogTitle>
          {moduleDetail && (
            <>
              <p>
                {moduleDetail.key} · {moduleDetail.route} ·{" "}
                {moduleDetail.routeCount} API operations
              </p>
              <p>{moduleDetail.integrationStatus}</p>
              <h3>Registered permissions</h3>
              {moduleDetail.permissions.map((p: any) => (
                <p key={p.name}>
                  <strong>{p.name}</strong> —{" "}
                  {p.description || "Native module permission"}
                </p>
              ))}
              <Link to="/admin/access?tab=Roles">Configure module roles</Link>
            </>
          )}
        </DialogContent>
      </Dialog>
    </main>
  );
}

export function UserAccess360() {
  const userId = useLocation().pathname.split("/").pop();
  const [data, setData] = useState<any>();
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const companyId = Number(
    sessionStorage.getItem("suite-organization") ||
      useAuthStore.getState().user?.access?.companyId ||
      1,
  );
  const load = () =>
    api
      .get(`${root}/users/${userId}/360`, { params: { companyId } })
      .then((r) => {
        setData(r.data);
        setName(r.data.overview.name);
        setEmail(r.data.overview.email);
      })
      .catch((e) => setError(errorText(e)));
  useEffect(() => {
    load();
  }, [userId, companyId]);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const step = await administratorStepUp(password);
      await api.put(
        `${root}/users/${userId}/identity`,
        {
          companyId,
          name,
          email,
          reason,
          expectedUpdatedAt: data.overview.updatedAt,
        },
        { headers: { "X-Access-Step-Up": step.data.token } },
      );
      setEditing(false);
      setPassword("");
      await load();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <main className="ua-root cc-root">
      <h1>
        <Users size={22} />
        User Access 360°
      </h1>
      <ControlNav />
      {error && <p role="alert">{error}</p>}
      {!data ? (
        <p>Loading identity and access…</p>
      ) : (
        <>
          <section className="cc-card">
            <h2>{data.overview.name}</h2>
            <p>
              {data.overview.email} · {data.overview.status} ·{" "}
              {data.overview.accountType}
            </p>
            <div className="cc-actions">
              {[
                "Overview",
                "Module Access",
                "Security",
                "Access History",
                "Linked Records",
              ].map((t) => (
                <Button
                  key={t}
                  variant={tab === t ? "default" : "outline"}
                  onClick={() => setTab(t)}
                >
                  {t}
                </Button>
              ))}
            </div>
          </section>
          <section className="cc-card">
            {tab === "Overview" && (
              <>
                <p>Company memberships: {data.memberships.join(", ")}</p>
                <p>
                  Department: {data.overview.department || "Unassigned"} ·
                  Branch: {data.overview.branch || "Unassigned"}
                </p>
                <p>Last login: {date(data.overview.lastLogin)}</p>
                <Button
                  variant="outline"
                  disabled={data.overview.isSuperuser}
                  onClick={() => setEditing(true)}
                >
                  Edit Identity
                </Button>
                <p>
                  <Link to="/admin/access">
                    Manage account status and access
                  </Link>
                </p>
              </>
            )}
            {tab === "Module Access" && (
              <div className="cc-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Module</th>
                      <th>Role</th>
                      <th>Scope</th>
                      <th>Effective native permissions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.overview.grants)
                      .filter(([, g]: any) => g.enabled)
                      .map(([key, g]: any) => (
                        <tr key={key}>
                          <td>{key}</td>
                          <td>{g.role}</td>
                          <td>{g.scope}</td>
                          <td>
                            {g.permissions.join(", ") ||
                              "No native permissions"}
                            <small>Actions: {g.actions.join(", ")}</small>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
            {tab === "Security" && (
              <>
                <p>
                  MFA: {data.security.mfaEnabled ? "Enabled" : "Not enrolled"} ·
                  Recent failures: {data.security.recentFailures}
                </p>
                <p>Account lock: {data.security.restricted ? "Restricted for this administrator" : data.security.lockout?.locked ? `Temporarily locked (${data.security.lockout.unlock_after_minutes} minute window)` : "Not locked"}</p>
                <h3>Sessions</h3>
                {data.security.sessions.map((s: any) => (
                  <p key={s.id}>
                    {s.device || "Browser"} · {s.status} ·{" "}
                    {s.ip || "Unavailable"} · {date(s.lastSeen)}
                  </p>
                ))}
                <h3>Login history</h3>
                {data.security.loginHistory.map((l: any) => (
                  <p key={l.id}>
                    {date(l.at)} · {l.status}
                  </p>
                ))}
                <Link to="/admin/control/security">
                  Manage sessions and requirements
                </Link>
              </>
            )}
            {tab === "Access History" && <Events rows={data.history} />}
            {tab === "Linked Records" && (
              <>
                <p>
                  Employee: {data.linked.employeeCode || "No linked employee"} ·
                  Intern: {data.linked.intern ? "Yes" : "No"}
                </p>
                <p>Department ID: {data.linked.departmentId || "Unassigned"}</p>
                <p>
                  HRMS payroll, documents and other sensitive employee data
                  remain governed by HRMS authorization.
                </p>
              </>
            )}
          </section>
        </>
      )}
      <Dialog
        open={editing}
        onOpenChange={(v) => {
          setEditing(v);
          if (!v) setPassword("");
        }}
      >
        <DialogContent className="ua-root cc-dialog">
          <DialogTitle>Edit identity</DialogTitle>
          <form onSubmit={save}>
            <label className="cc-field">
              Full name
              <input
                required
                maxLength={180}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="cc-field">
              Email
              <input
                type="email"
                required
                maxLength={150}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="cc-field">
              Reason
              <textarea
                required
                minLength={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <AdminVerification value={password} onChange={setPassword} />
            <p>
              Identity changes revoke active sessions. Employee records remain
              distinct.
            </p>
            {error && <p role="alert">{error}</p>}
            <Button type="submit">Verify & Save</Button>
          </form>
        </DialogContent>
      </Dialog>
    </main>
  );
}
