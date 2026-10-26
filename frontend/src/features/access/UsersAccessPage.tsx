import SuperAdminManager from "./SuperAdminManager";
import React, { useEffect, useMemo, useState } from "react";
import {
  Check,
  Copy,
  Download,
  History,
  Plus,
  Search,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { api } from "@/services/api";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import "./access.css";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ControlNav } from "./ControlCenter";

type Grant = {
  enabled: boolean;
  role: string;
  roleId?: number | null;
  roleVersion?: number;
  permissions: string[];
  actions: string[];
  scope: string;
};
type Person = {
  id: number;
  name: string;
  email: string;
  employeeCode?: string;
  department?: string;
  departmentId?: number;
  branchId?: number;
  branch?: string;
  companyId: number;
  role?: string;
  status: string;
  accountType: string;
  isSuperuser: boolean;
  lastLogin?: string;
  version: number;
  managed: boolean;
  grants: Record<string, Grant>;
  moduleCount: number;
};
type Module = {
  key: string;
  label: string;
  installed: boolean;
  route: string;
  permissions: { name: string; description: string; group: string }[];
  routeCount: number;
  actions?: string[];
  scopes?: string[];
};
type Catalog = {
  modules: Module[];
  presets: Record<string, Record<string, Grant>>;
  roles: any[];
  legacyRoles: any[];
  scopes: string[];
  actions: string[];
  companies: { id: number; name: string }[];
};
type Change = {
  userId: number;
  version: number;
  grants: Record<string, Grant>;
  status?: string;
};
const err = (e: any) =>
  typeof e?.response?.data?.detail === "string"
    ? e.response.data.detail
    : JSON.stringify(
        e?.response?.data?.detail || e.message || "Request failed",
      );
const stamp = (s?: string) => (s ? new Date(s).toLocaleString() : "Never");
function download(data: Blob, name: string) {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}
const disabledGrant: Grant = {
  enabled: false,
  role: "viewer",
  permissions: [],
  actions: ["view"],
  scope: "own",
};

function ModuleEditor({
  modules,
  catalog,
  grants,
  patch,
  disabled,
}: {
  modules: Module[];
  catalog: Catalog;
  grants: Record<string, Grant>;
  patch: (key: string, grant: Grant) => void;
  disabled?: boolean;
}) {
  const setRole = (key: string, value: string) => {
    if (value.startsWith("custom:")) {
      const role = catalog.roles.find((r) => r.id === Number(value.slice(7)));
      if (role)
        patch(key, {
          enabled: true,
          role: role.name,
          roleId: role.id,
          roleVersion: role.version,
          permissions: role.permissions,
          actions: role.actions,
          scope: role.scope,
        });
    } else if (value.startsWith("legacy:")) {
      const role = catalog.legacyRoles.find(
        (r) => r.id === Number(value.slice(7)),
      );
      const allowed = new Set(
        modules.find((m) => m.key === key)?.permissions.map((p) => p.name),
      );
      patch(key, {
        enabled: true,
        role: role.name,
        roleId: null,
        permissions: role.permissions.filter((p: string) => allowed.has(p)),
        actions: ["view", "create", "edit"],
        scope: "own",
      });
    } else patch(key, { ...catalog.presets[key][value], roleId: null });
  };
  return (
    <div className="ua-module-editor">
      {modules.map((m) => {
        const grant = grants[m.key] || disabledGrant;
        const roleValue = grant.roleId
          ? `custom:${grant.roleId}`
          : catalog.presets[m.key]?.[grant.role]
            ? grant.role
            : "current";
        return (
          <details key={m.key} className="ua-module-row">
            <summary>
              <label onClick={(e) => e.stopPropagation()}>
                <input
                  aria-label={`Enable ${m.label}`}
                  type="checkbox"
                  checked={grant.enabled}
                  disabled={disabled || !m.installed}
                  onChange={(e) =>
                    patch(m.key, {
                      ...(grant.permissions.length || grant.roleId
                        ? grant
                        : catalog.presets[m.key].viewer),
                      enabled: e.target.checked,
                    })
                  }
                />
                {m.label}
              </label>
              <span>
                {grant.scope} · {grant.permissions.length} permissions
              </span>
            </summary>
            <fieldset disabled={disabled || !grant.enabled}>
              <label>
                Module role
                <select
                  aria-label={`Role for ${m.label}`}
                  value={roleValue}
                  onChange={(e) => setRole(m.key, e.target.value)}
                >
                  <option value="current">{grant.role || "Custom"}</option>
                  {Object.keys(catalog.presets[m.key] || {}).map((t) => (
                    <option value={t} key={t}>
                      {t === "admin" ? "Module Admin" : t}
                    </option>
                  ))}
                  {catalog.roles
                    .filter((r) => r.module_key === m.key)
                    .map((r) => (
                      <option key={r.id} value={`custom:${r.id}`}>
                        {r.name}
                      </option>
                    ))}
                  <optgroup label="Existing suite roles (module permissions only)">
                    {catalog.legacyRoles.map((r) => (
                      <option key={r.id} value={`legacy:${r.id}`}>
                        {r.name}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </label>
              <label>
                Data scope
                <select
                  aria-label={`Scope for ${m.label}`}
                  value={grant.scope}
                  onChange={(e) =>
                    patch(m.key, { ...grant, scope: e.target.value })
                  }
                >
                  {catalog.scopes.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
              <h4>Actions</h4>
              <div className="ua-check-grid">
                {(m.actions || catalog.actions).map((a) => (
                  <label key={a}>
                    <input
                      type="checkbox"
                      checked={grant.actions.includes(a)}
                      onChange={(e) =>
                        patch(m.key, {
                          ...grant,
                          roleId: null,
                          role: "Custom",
                          actions: e.target.checked
                            ? [...grant.actions, a]
                            : grant.actions.filter((v) => v !== a),
                        })
                      }
                    />
                    {a.replace(/_/g, " ")}
                  </label>
                ))}
              </div>
              <h4>Backend permissions</h4>
              <div className="ua-permission-list">
                {m.permissions.map((p) => (
                  <label key={p.name} title={p.description}>
                    <input
                      type="checkbox"
                      checked={grant.permissions.includes(p.name)}
                      onChange={(e) =>
                        patch(m.key, {
                          ...grant,
                          roleId: null,
                          role: "Custom",
                          permissions: e.target.checked
                            ? [...grant.permissions, p.name]
                            : grant.permissions.filter((n) => n !== p.name),
                        })
                      }
                    />
                    <span>
                      {p.name}
                      <small>{p.description}</small>
                    </span>
                  </label>
                ))}
              </div>
              {!m.permissions.length && (
                <p className="ua-hint">
                  This module uses existing membership checks. Action and
                  data-scope restrictions still apply.
                </p>
              )}
            </fieldset>
          </details>
        );
      })}
    </div>
  );
}

export default function UsersAccessPage() {
  const actor = useAuthStore((s) => s.user);
  const [company, setCompany] = useState(
    Number(
      sessionStorage.getItem("suite-organization") ||
        actor?.access?.companyId ||
        1,
    ),
  );
  const [catalog, setCatalog] = useState<Catalog>();
  const [data, setData] = useState<any>();
  const [templates, setTemplates] = useState<any[]>([]);
  const location = useLocation();
  const navigate = useNavigate();
  const [tab, setTab] = useState("Matrix");
  const [filters, setFilters] = useState({
    search: "",
    sort: "name",
    descending: "",
    role: "",
    status: "",
    branch: "",
    department: "",
    module: "",
  });
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(100);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<Record<number, Person>>({});
  const [drafts, setDrafts] = useState<Record<number, Change>>({});
  const [opened, setOpened] = useState<Person>();
  const [review, setReview] = useState<any>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] =
    useState<(token: string) => Promise<void>>();
  const [password, setPassword] = useState("");
  const [bulkModule, setBulkModule] = useState("");
  const [bulkRole, setBulkRole] = useState("viewer");
  const [bulkScope, setBulkScope] = useState("own");
  const [bulkAction, setBulkAction] = useState("grant");
  const [templateId, setTemplateId] = useState("");
  const [templateMode, setTemplateMode] = useState("merge");
  const [templateMeta, setTemplateMeta] = useState<any>();
  const [createMode, setCreateMode] = useState<"add" | "invite">();
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requested = params.get("tab");
    if (requested && ["Matrix", "User listing", "Roles", "Templates", "Audit", "Insights"].includes(requested)) setTab(requested);
    if (params.get("action") === "add" || params.get("action") === "invite") {
      setCreateMode(params.get("action") as "add" | "invite");
      params.delete("action");
      navigate({pathname: location.pathname, search: params.toString()}, {replace: true});
    }
    if (params.get("module")) setFilters(f => ({...f, module: params.get("module") || ""}));
  }, [location.search]);

  const [newUser, setNewUser] = useState({ name: "", email: "", password: "" });
  const [invitation, setInvitation] = useState("");
  const [cloneFrom, setCloneFrom] = useState("");
  const [roleEdit, setRoleEdit] = useState<any>();
  const [templateEdit, setTemplateEdit] = useState<any>();
  const [audit, setAudit] = useState<any>();
  const [auditTarget, setAuditTarget] = useState("");
  const [auditSearch, setAuditSearch] = useState("");
  const [auditPage, setAuditPage] = useState(1);
  const [scrollTop, setScrollTop] = useState(0);
  const [membership, setMembership] = useState<any>();
  const dirty = Object.keys(drafts).length > 0;
  const refresh = () => setRevision((v) => v + 1);
  const report = (e: any) => setError(err(e));
  useEffect(() => {
    if (!dirty) return;
    const protect = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [dirty]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    Promise.all([
      api.get("/access/catalog", {
        params: { companyId: company },
        signal: controller.signal,
      }),
      api.get("/access/users", {
        params: {
          companyId: company,
          ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
          page,
          perPage,
        },
        signal: controller.signal,
      }),
      api.get("/access/templates", {
        params: { companyId: company },
        signal: controller.signal,
      }),
    ])
      .then(([c, u, t]) => {
        setCatalog(c.data);
        setData(u.data);
        setTemplates(t.data.items);
      })
      .catch((e) => {
        if (!controller.signal.aborted) report(e);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [company, filters, page, perPage, revision]);
  useEffect(() => {
    if (tab !== "Audit") return;
    const controller = new AbortController();
    api
      .get("/access/audit", {
        params: {
          companyId: company,
          target: auditTarget || undefined,
          search: auditSearch,
          page: auditPage,
        },
        signal: controller.signal,
      })
      .then((r) => setAudit(r.data))
      .catch((e) => {
        if (!controller.signal.aborted) report(e);
      });
    return () => controller.abort();
  }, [tab, company, auditTarget, auditSearch, auditPage, revision]);
  const users: Person[] = data?.items || [];
  const modules = catalog?.modules || [];
  const visibleModules = filters.module
    ? modules.filter((m) => m.key === filters.module)
    : modules;
  const grantsFor = (u: Person) => ({
    ...u.grants,
    ...(drafts[u.id]?.grants || {}),
  });
  const patch = (u: Person, key: string, grant: Grant) => {
    if (u.isSuperuser) return;
    setDrafts((current) => ({
      ...current,
      [u.id]: {
        ...(current[u.id] || { userId: u.id, version: u.version, grants: {} }),
        grants: { ...current[u.id]?.grants, [key]: grant },
      },
    }));
  };
  const stageStatus = (u: Person, status: string) =>
    setDrafts((current) => ({
      ...current,
      [u.id]: {
        ...(current[u.id] || { userId: u.id, version: u.version, grants: {} }),
        status,
      },
    }));
  const changeFilter = (key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
    setScrollTop(0);
  };
  const preview = async () => {
    if (!reason.trim()) {
      setError("Enter a reason before reviewing changes.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const payload = {
        companyId: company,
        changes: Object.values(drafts),
        reason,
        ...templateMeta,
      };
      const r = await api.post("/access/changes/preview", payload);
      setReview({ ...r.data, payload });
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  };
  const refreshVersions = async () => {
    if (
      !window.confirm(
        "Load the latest access versions and keep your staged proposals? Review every change again before applying.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      const responses = await Promise.all(
        Object.keys(drafts).map((id) =>
          api.get<Person>(`/access/users/${id}`, {
            params: { companyId: company },
          }),
        ),
      );
      const current = new Map(responses.map((r) => [r.data.id, r.data]));
      setDrafts((old) =>
        Object.fromEntries(
          Object.entries(old).map(([id, change]) => [
            id,
            {
              ...change,
              version: current.get(Number(id))?.version ?? change.version,
            },
          ]),
        ),
      );
      setReview(undefined);
      setOpened((old) => (old ? current.get(old.id) || old : old));
      refresh();
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  };
  const secure = (action: (token: string) => Promise<void>) => {
    setPassword("");
    setError("");
    setOperation(() => action);
  };
  const exportReport = async () => {
    try {
      const r = await api.get("/access/report", {
        params: { companyId: company, ids: Object.keys(selected).join(",") },
        responseType: "blob",
      });
      download(r.data, "user-access.csv");
    } catch (e) {
      report(e);
    }
  };
  const stageBulk = () => {
    const targets = Object.values(selected).filter((u) => !u.isSuperuser);
    if (!targets.length) {
      setError("Select at least one editable user.");
      return;
    }
    if (["suspend", "reactivate"].includes(bulkAction)) {
      targets.forEach((u) =>
        stageStatus(u, bulkAction === "suspend" ? "suspended" : "active"),
      );
      return;
    }
    if (bulkAction === "template") {
      const t = templates.find((t) => t.id === Number(templateId));
      if (!t) return;
      targets.forEach((u) => {
        if (templateMode === "replace")
          modules.forEach((m) =>
            patch(u, m.key, {
              ...(grantsFor(u)[m.key] || disabledGrant),
              enabled: false,
            }),
          );
        Object.entries(t.grants).forEach(([key, grant]) =>
          patch(u, key, grant as Grant),
        );
      });
      setTemplateMeta({ templateId: t.id, templateVersion: t.version });
      return;
    }
    if (!bulkModule || !catalog) return;
    targets.forEach((u) => {
      const current =
        grantsFor(u)[bulkModule] || catalog.presets[bulkModule].viewer;
      const custom = bulkRole.startsWith("custom:")
        ? catalog.roles.find(
            (r) =>
              r.id === Number(bulkRole.slice(7)) && r.module_key === bulkModule,
          )
        : undefined;
      patch(
        u,
        bulkModule,
        bulkAction === "revoke"
          ? { ...current, enabled: false }
          : bulkAction === "scope"
            ? { ...current, scope: bulkScope }
            : custom
              ? {
                  enabled: true,
                  role: custom.name,
                  roleId: custom.id,
                  roleVersion: custom.version,
                  permissions: custom.permissions,
                  actions: custom.actions,
                  scope: bulkScope,
                }
              : { ...catalog.presets[bulkModule][bulkRole], scope: bulkScope },
      );
    });
  };
  const first = Math.max(0, Math.floor(scrollTop / 64) - 4);
  const virtualUsers = users.slice(first, first + 24);
  return (
    <div className="ua-root">
      <ControlNav />
      <header className="ua-header">
        <div>
          <span className="ua-eyebrow">MASTER SUITE / SUPER ADMIN</span>
          <h1>
            <ShieldCheck size={23} /> Users & Access
          </h1>
          <p>
            One place to manage module access, roles and organization
            boundaries.
          </p>
        </div>
        <span className="ua-admin-badge">
          {actor?.is_superuser ? "Global Super Admin" : "Organization Admin"}
        </span>
      </header>
      <div className="ua-toolbar">
        {actor?.is_superuser && <SuperAdminManager companyId={company} />}
        <label>
          Company
          <select
            aria-label="Company"
            value={company}
            onChange={(e) => {
              if (
                dirty &&
                !window.confirm(
                  "Discard unsaved changes before changing company?",
                )
              )
                return;
              setCompany(Number(e.target.value));
              setDrafts({});
              setSelected({});
              setOpened(undefined);
              setTemplateMeta(undefined);
              setPage(1);
            }}
          >
            {catalog?.companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            )) || <option value={company}>Company {company}</option>}
          </select>
        </label>
        <Button variant="outline" onClick={() => setCreateMode("add")}>
          <Plus size={15} />
          Add User
        </Button>
        <Button variant="outline" onClick={() => setCreateMode("invite")}>
          Invite User
        </Button>
        <Button variant="outline" onClick={() => setTab("Roles")}>
          Manage Roles
        </Button>
        <Button variant="outline" onClick={() => setTab("Templates")}>
          Permission Templates
        </Button>
        <Button variant="outline" onClick={exportReport}>
          <Download size={14} />
          Export Access Report
        </Button>
        {actor?.is_superuser && (
          <Button
            variant="outline"
            onClick={() =>
              setMembership({
                userId: "",
                companyId: company,
                active: true,
                isAdmin: false,
                reason: "",
              })
            }
          >
            Organization membership
          </Button>
        )}
      </div>
      {error && (
        <div className="ua-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label="Dismiss error">
            <X size={15} />
          </button>
        </div>
      )}
      {message && (
        <p role="status" className="ua-success">
          {message}
        </p>
      )}
      <div className="ua-summary">
        {[
          ["Total users", "total"],
          ["Active users", "active"],
          ["Pending invitations", "invited"],
          ["Suspended users", "suspended"],
          ["Active modules", "modules"],
          ["Users with admin access", "admins"],
        ].map(([label, key]) => (
          <div key={key}>
            <strong>{data?.summary?.[key] ?? "—"}</strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
      <nav className="ua-tabs" aria-label="Access management views">
        {[
          "Matrix",
          "User listing",
          "Roles",
          "Templates",
          "Audit",
          "Insights",
        ].map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>
      {["Matrix", "User listing"].includes(tab) && (
        <>
          <div className="ua-filters"><select aria-label="Sort users" value={filters.sort} onChange={e => changeFilter("sort", e.target.value)}>{["name", "email", "role", "status", "lastLogin"].map(k => <option key={k} value={k}>Sort: {k}</option>)}</select><select aria-label="Sort direction" value={filters.descending} onChange={e => changeFilter("descending", e.target.value)}><option value="">Ascending</option><option value="true">Descending</option></select>
            <label className="ua-search">
              <Search size={16} />
              <input
                aria-label="Search users"
                placeholder="Name, email, employee ID or department"
                value={filters.search}
                onChange={(e) => changeFilter("search", e.target.value)}
              />
            </label>
            <select
              aria-label="Filter module"
              value={filters.module}
              onChange={(e) => changeFilter("module", e.target.value)}
            >
              <option value="">All modules</option>
              {modules.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter role"
              value={filters.role}
              onChange={(e) => changeFilter("role", e.target.value)}
            >
              <option value="">All roles</option>
              {catalog?.roles.map((r) => (
                <option key={`custom-${r.id}`}>{r.name}</option>
              ))}
              {catalog?.legacyRoles.map((r) => (
                <option key={r.id}>{r.name}</option>
              ))}
            </select>
            <select
              aria-label="Filter account status"
              value={filters.status}
              onChange={(e) => changeFilter("status", e.target.value)}
            >
              <option value="">All statuses</option>
              {["active", "invited", "suspended", "deactivated"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <input
              aria-label="Filter branch ID"
              type="number"
              min={1}
              placeholder="Branch ID"
              value={filters.branch}
              onChange={(e) => changeFilter("branch", e.target.value)}
            />
            <input
              aria-label="Filter department ID"
              type="number"
              min={1}
              placeholder="Department ID"
              value={filters.department}
              onChange={(e) => changeFilter("department", e.target.value)}
            />
          </div>
          <div className="ua-bulk">
            <strong>{Object.keys(selected).length} selected</strong>
            <select
              aria-label="Bulk operation"
              value={bulkAction}
              onChange={(e) => setBulkAction(e.target.value)}
            >
              {[
                "grant",
                "revoke",
                "scope",
                "template",
                "suspend",
                "reactivate",
              ].map((a) => (
                <option key={a}>{a}</option>
              ))}
            </select>
            {["grant", "revoke", "scope"].includes(bulkAction) && (
              <select
                aria-label="Bulk module"
                value={bulkModule}
                onChange={(e) => setBulkModule(e.target.value)}
              >
                <option value="">Choose module</option>
                {modules.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </select>
            )}
            {bulkAction === "grant" && (
              <select
                aria-label="Bulk role"
                value={bulkRole}
                onChange={(e) => setBulkRole(e.target.value)}
              >
                {["viewer", "contributor", "editor", "manager", "admin"].map(
                  (r) => (
                    <option key={r}>{r}</option>
                  ),
                )}
                {catalog?.roles
                  .filter((r) => r.module_key === bulkModule)
                  .map((r) => (
                    <option key={r.id} value={`custom:${r.id}`}>
                      {r.name}
                    </option>
                  ))}
              </select>
            )}
            {["grant", "scope"].includes(bulkAction) && (
              <select
                aria-label="Bulk scope"
                value={bulkScope}
                onChange={(e) => setBulkScope(e.target.value)}
              >
                {catalog?.scopes.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            )}
            {bulkAction === "template" && (
              <>
                <select
                  aria-label="Apply template"
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                >
                  <option value="">Choose template</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} · v{t.version}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Template application mode"
                  value={templateMode}
                  onChange={(e) => setTemplateMode(e.target.value)}
                >
                  <option value="merge">Merge selected grants</option>
                  <option value="replace">Replace all module grants</option>
                </select>
              </>
            )}
            <Button variant="outline" disabled={busy} onClick={stageBulk}>
              Stage bulk changes
            </Button>
            <button onClick={() => setSelected({})}>Clear selection</button>
          </div>
          {loading && <p role="status">Loading authorized users…</p>}
          <div
            className="ua-table-wrap"
            onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
          >
            <table className="ua-table">
              <thead>
                <tr>
                  <th className="ua-sticky">
                    <label>
                      <input
                        type="checkbox"
                        aria-label="Select all users on this page"
                        checked={
                          users.filter((u) => !u.isSuperuser).length > 0 &&
                          users
                            .filter((u) => !u.isSuperuser)
                            .every((u) => selected[u.id])
                        }
                        onChange={(e) =>
                          setSelected((current) => {
                            const next = { ...current };
                            users
                              .filter((u) => !u.isSuperuser)
                              .forEach((u) => {
                                if (e.target.checked) next[u.id] = u;
                                else delete next[u.id];
                              });
                            return next;
                          })
                        }
                      />
                      User
                    </label>
                  </th>
                  {tab === "Matrix"
                    ? visibleModules.map((m) => (
                        <th
                          key={m.key}
                          title={`${m.label} · ${m.routeCount} registered API routes`}
                        >
                          {m.label}
                        </th>
                      ))
                    : [
                        "Email",
                        "Employee ID",
                        "Department",
                        "Branch",
                        "Company",
                        "Account type",
                        "Modules",
                        "Primary role",
                        "Status",
                        "Last login",
                        "Actions",
                      ].map((c) => <th key={c}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {first > 0 && (
                  <tr aria-hidden="true" style={{ height: first * 64 }}>
                    <td
                      colSpan={
                        tab === "Matrix" ? visibleModules.length + 1 : 11
                      }
                    />
                  </tr>
                )}
                {virtualUsers.map((u) => (
                  <tr key={u.id} className={drafts[u.id] ? "ua-row-dirty" : ""}>
                    <td className="ua-sticky">
                      <div className="ua-user-cell">
                        <input
                          type="checkbox"
                          aria-label={`Select ${u.name}`}
                          disabled={u.isSuperuser}
                          checked={Boolean(selected[u.id])}
                          onChange={(e) =>
                            setSelected((current) => {
                              const next = { ...current };
                              if (e.target.checked) next[u.id] = u;
                              else delete next[u.id];
                              return next;
                            })
                          }
                        />
                        <span className="ua-avatar">
                          {u.name.slice(0, 2).toUpperCase()}
                        </span>
                        <button
                          className="ua-user-name"
                          onClick={() => setOpened(u)}
                        >
                          <strong>{u.name}</strong>
                          <small>{u.department || u.email}</small>
                        </button>
                        <Link aria-label={`Access profile for ${u.name}`} to={`/admin/control/users/${u.id}`}>360</Link>
                        {u.isSuperuser && (
                          <ShieldCheck
                            size={14}
                            aria-label="Protected Super Admin"
                          />
                        )}
                      </div>
                    </td>
                    {tab === "Matrix" ? (
                      visibleModules.map((m) => {
                        const grant = grantsFor(u)[m.key] || disabledGrant;
                        return (
                          <td key={m.key} className="ua-matrix-cell">
                            <input
                              type="checkbox"
                              aria-label={`${u.name}: ${m.label}`}
                              title={
                                u.isSuperuser
                                  ? "Super Admin access is protected"
                                  : `${grant.role} · ${grant.scope}`
                              }
                              checked={grant.enabled}
                              disabled={u.isSuperuser || !m.installed}
                              onChange={(e) =>
                                patch(
                                  u,
                                  m.key,
                                  grant.permissions.length
                                    ? { ...grant, enabled: e.target.checked }
                                    : {
                                        ...catalog!.presets[m.key].viewer,
                                        enabled: e.target.checked,
                                      },
                                )
                              }
                            />
                            <button
                              className="ua-role-link"
                              disabled={u.isSuperuser || !grant.enabled}
                              onClick={() => setOpened(u)}
                            >
                              {grant.enabled ? grant.role : "No access"}
                            </button>
                          </td>
                        );
                      })
                    ) : (
                      <>
                        <td>{u.email}<Link className="ml-2 text-primary" to={`/admin/control/users/${u.id}`}>Access 360�</Link></td>
                        <td>{u.employeeCode || "—"}</td>
                        <td>{u.department || "—"}</td>
                        <td>
                          {
                            catalog?.companies.find((c) => c.id === company)
                              ?.name
                          }
                        </td>
                        <td>{u.accountType}</td>
                        <td>
                          {
                            Object.values(grantsFor(u)).filter((g) => g.enabled)
                              .length
                          }
                        </td>
                        <td>{u.role || "Custom module roles"}</td>
                        <td>
                          <span
                            className={`ua-status ua-${drafts[u.id]?.status || u.status}`}
                          >
                            {drafts[u.id]?.status || u.status}
                          </span>
                        </td>
                        <td>{stamp(u.lastLogin)}</td>
                        <td>
                          <button onClick={() => setOpened(u)}>
                            Edit access
                          </button>{" "}
                          ·{" "}
                          <button
                            disabled={u.isSuperuser}
                            onClick={() => stageStatus(u, "suspended")}
                          >
                            Suspend
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
                {users.length > first + 24 && (
                  <tr
                    aria-hidden="true"
                    style={{ height: (users.length - first - 24) * 64 }}
                  >
                    <td
                      colSpan={
                        tab === "Matrix" ? visibleModules.length + 1 : 11
                      }
                    />
                  </tr>
                )}
              </tbody>
            </table>
            {!loading && !users.length && (
              <p className="ua-empty">No users match these filters.</p>
            )}
          </div>
          <div className="ua-pagination">
            <span>
              {data?.total || 0} authorized users · page {page}
            </span>
            <select
              aria-label="Users per page"
              value={perPage}
              onChange={(e) => {
                setPerPage(Number(e.target.value));
                setPage(1);
                setScrollTop(0);
              }}
            >
              {[50, 100, 200].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
            <Button
              variant="outline"
              disabled={page === 1}
              onClick={() => {
                setPage((p) => p - 1);
                setScrollTop(0);
              }}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              disabled={page * perPage >= (data?.total || 0)}
              onClick={() => {
                setPage((p) => p + 1);
                setScrollTop(0);
              }}
            >
              Next
            </Button>
          </div>
        </>
      )}
      {tab === "Roles" && (
        <section className="ua-panel">
          <header>
            <h2>Module roles</h2>
            <Button
              onClick={() =>
                setRoleEdit({
                  module: modules[0]?.key,
                  name: "",
                  description: "",
                  permissions: [],
                  actions: ["view"],
                  scope: "own",
                  active: true,
                  affectedUsers: [],
                })
              }
            >
              Create custom role
            </Button>
          </header>
          {catalog?.roles.map((r) => (
            <article key={r.id} className="ua-resource">
              <div>
                <strong>{r.name}</strong>
                <p>
                  {r.module_key} · {r.scope} · {r.permissions.length}{" "}
                  permissions · v{r.version}
                </p>
              </div>
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    const response = await api.get(
                      `/access/roles/${r.id}/users`,
                      { params: { companyId: company } },
                    );
                    setRoleEdit({
                      ...r,
                      module: r.module_key,
                      affectedUsers: response.data.items,
                    });
                  } catch (e) {
                    report(e);
                  }
                }}
              >
                Edit / assigned users
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  setRoleEdit({
                    ...r,
                    id: undefined,
                    version: 0,
                    name: r.name + " copy",
                    module: r.module_key,
                    affectedUsers: [],
                  })
                }
              >
                Duplicate
              </Button>
            </article>
          ))}
        </section>
      )}
      {tab === "Templates" && (
        <section className="ua-panel">
          <header>
            <h2>Versioned permission templates</h2>
            <Button
              onClick={() =>
                setTemplateEdit({
                  name: "",
                  description: "",
                  grants: {},
                  active: true,
                })
              }
            >
              Create template
            </Button>
          </header>
          <p className="ua-hint">
            Apply templates from bulk assignment. Merge updates selected
            modules; replace explicitly revokes modules outside the template.
          </p>
          {templates.map((t) => (
            <article className="ua-resource" key={t.id}>
              <div>
                <strong>{t.name}</strong>
                <p>
                  {t.description} · v{t.version} ·{" "}
                  {
                    Object.values(t.grants as Record<string, Grant>).filter(
                      (g) => g.enabled,
                    ).length
                  }{" "}
                  modules
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() =>
                  setTemplateEdit({ ...t, grants: structuredClone(t.grants) })
                }
              >
                Edit / preview
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  setTemplateEdit({
                    ...t,
                    id: undefined,
                    version: 0,
                    name: t.name + " copy",
                    grants: structuredClone(t.grants),
                  })
                }
              >
                Duplicate
              </Button>
            </article>
          ))}
        </section>
      )}
      {tab === "Audit" && (
        <section className="ua-panel">
          <header>
            <h2>Access history</h2>
            <input
              aria-label="Filter audit user ID"
              placeholder="User ID"
              value={auditTarget}
              onChange={(e) => {
                setAuditTarget(e.target.value);
                setAuditPage(1);
              }}
            />
            <input
              aria-label="Search audit history"
              placeholder="Name, email, operation or reason"
              value={auditSearch}
              onChange={(e) => {
                setAuditSearch(e.target.value);
                setAuditPage(1);
              }}
            />
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const r = await api.get("/access/audit", {
                    params: {
                      companyId: company,
                      target: auditTarget || undefined,
                      search: auditSearch,
                      export: true,
                    },
                    responseType: "blob",
                  });
                  download(r.data, "access-audit.csv");
                } catch (e) {
                  report(e);
                }
              }}
            >
              Export audit
            </Button>
          </header>
          {audit?.items.map((a: any) => (
            <details className="ua-resource" key={a.id}>
              <summary>
                {stamp(a.created_at)} · {a.operation} ·{" "}
                {a.actorName || `Admin ${a.actor_id}`} →
                {a.targetName || `User ${a.target_id || "—"}`} · {a.outcome}
              </summary>
              <p>
                {a.reason} · IP {a.source_ip || "—"}
              </p>
              <pre>
                {JSON.stringify(
                  { before: a.before_json, after: a.after_json },
                  null,
                  2,
                )}
              </pre>
            </details>
          ))}
          <Button
            variant="outline"
            disabled={auditPage === 1}
            onClick={() => setAuditPage((p) => p - 1)}
          >
            Previous events
          </Button>
          <Button
            variant="outline"
            disabled={auditPage * 50 >= (audit?.total || 0)}
            onClick={() => setAuditPage((p) => p + 1)}
          >
            Next events
          </Button>
        </section>
      )}
      {tab === "Insights" && (
        <section className="ua-panel">
          <h2>Access distribution</h2>
          <div className="ua-insights">
            {["byModule", "byRole", "byDepartment"].map((key) => (
              <div key={key}>
                <h3>{key.replace("by", "Users by ")}</h3>
                {Object.entries(data?.analytics?.[key] || {}).map(
                  ([name, value]) => (
                    <div className="ua-bar" key={name}>
                      <span>{name}</span>
                      <progress
                        value={Number(value)}
                        max={Math.max(1, data?.summary?.total || 0)}
                      />
                      <strong>{String(value)}</strong>
                    </div>
                  ),
                )}
              </div>
            ))}
          </div>
          <p>
            {data?.analytics?.dormant.length || 0} accounts have never logged in
            or have been dormant for 90 days.
          </p>
        </section>
      )}
      {dirty && (
        <footer className="ua-savebar">
          <strong>
            {Object.keys(drafts).length} users have unsaved access changes
          </strong>
          <input
            aria-label="Reason for access changes"
            placeholder="Reason for these changes"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Discard all staged access changes?")) {
                setDrafts({});
                setTemplateMeta(undefined);
              }
            }}
          >
            Discard
          </Button>
          <Button variant="outline" disabled={busy} onClick={refreshVersions}>
            Refresh versions, keep proposals
          </Button>
          <Button disabled={busy || reason.trim().length < 3} onClick={preview}>
            Review changes
          </Button>
        </footer>
      )}
      {opened && catalog && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setOpened(undefined);
          }}
        >
          <DialogContent className="ua-root ua-drawer">
            <DialogTitle>{opened.name} · Access</DialogTitle>
            <p>
              {opened.email} · {opened.department || "No department"} ·{" "}
              {opened.status}
            </p>
            <p className="ua-hint">
              Last login {stamp(opened.lastLogin)} ·{" "}
              {Object.values(grantsFor(opened)).filter((g) => g.enabled).length}{" "}
              enabled modules
              {!opened.managed
                ? " · Existing role access; saving creates an explicit policy."
                : ""}
            </p>
            <div className="ua-toolbar">
        {actor?.is_superuser && <SuperAdminManager companyId={company} />}
              <Button
                variant="outline"
                disabled={opened.isSuperuser}
                onClick={() => {
                  if (
                    window.confirm(
                      "Enable all installed modules with Viewer permissions? Review before applying.",
                    )
                  )
                    modules
                      .filter((m) => m.installed)
                      .forEach((m) =>
                        patch(opened, m.key, catalog.presets[m.key].viewer),
                      );
                }}
              >
                Select all
              </Button>
              <Button
                variant="outline"
                disabled={opened.isSuperuser}
                onClick={() => {
                  if (
                    window.confirm(
                      "Revoke all modules for this user? Review before applying.",
                    )
                  )
                    modules.forEach((m) =>
                      patch(opened, m.key, {
                        ...(grantsFor(opened)[m.key] || disabledGrant),
                        enabled: false,
                      }),
                    );
                }}
              >
                Clear all
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setAuditTarget(String(opened.id));
                  setTab("Audit");
                  setOpened(undefined);
                }}
              >
                <History size={14} />
                History
              </Button>
            </div>
            <div className="ua-toolbar">
        {actor?.is_superuser && <SuperAdminManager companyId={company} />}
              <select
                aria-label="Copy access from user"
                value={cloneFrom}
                onChange={(e) => setCloneFrom(e.target.value)}
              >
                <option value="">Copy access from…</option>
                {users
                  .filter((u) => u.id !== opened.id && !u.isSuperuser)
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
              </select>
              <Button
                variant="outline"
                disabled={!cloneFrom || opened.isSuperuser}
                onClick={() => {
                  const source = users.find((u) => u.id === Number(cloneFrom));
                  if (source)
                    Object.entries(grantsFor(source)).forEach(([key, g]) =>
                      patch(opened, key, structuredClone(g)),
                    );
                }}
              >
                <Copy size={14} />
                Stage copy
              </Button>
              <Button
                variant="outline"
                disabled={opened.isSuperuser}
                onClick={() => {
                  Object.entries(grantsFor(opened)).forEach(([key, g]) => {
                    const defaults = catalog.presets[key]?.[g.role];
                    const role = catalog.roles.find((r) => r.id === g.roleId);
                    if (role && g.enabled)
                      patch(opened, key, {
                        enabled: true,
                        role: role.name,
                        roleId: role.id,
                        roleVersion: role.version,
                        permissions: role.permissions,
                        actions: role.actions,
                        scope: role.scope,
                      });
                    else if (defaults && g.enabled)
                      patch(opened, key, structuredClone(defaults));
                  });
                }}
              >
                Reset assigned roles
              </Button>
            </div>
            <ModuleEditor
              modules={modules}
              catalog={catalog}
              grants={grantsFor(opened)}
              disabled={opened.isSuperuser}
              patch={(key, g) => patch(opened, key, g)}
            />
            {!opened.isSuperuser && (
              <label>
                Reason for this user's changes
                <input
                  aria-label="Reason for this user's changes"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
            )}
            <div className="ua-toolbar">
        {actor?.is_superuser && <SuperAdminManager companyId={company} />}
              <Button
                disabled={
                  !drafts[opened.id] || reason.trim().length < 3 || busy
                }
                onClick={async () => {
                  await preview();
                  setOpened(undefined);
                }}
              >
                Review & save
              </Button>
              <Button onClick={() => setOpened(undefined)}>
                Keep staged changes
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setDrafts((current) => {
                    const next = { ...current };
                    delete next[opened.id];
                    return next;
                  });
                  setOpened(undefined);
                }}
              >
                Cancel user changes
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
      {review && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open && !busy) setReview(undefined);
          }}
        >
          <DialogContent className="ua-root ua-review">
            <DialogTitle>Review {review.count} user access changes</DialogTitle>
            <p>{review.payload.reason}</p>
            <p className="ua-warning">
              Affected users will be signed out of existing sessions. Super
              Admin accounts remain protected.
            </p>
            {review.items.map((item: any) => (
              <details key={item.userId} open>
                <summary>
                  <strong>{item.name}</strong> · {item.oldStatus} →{" "}
                  {item.newStatus}
                </summary>
                {Object.keys(item.after)
                  .filter(
                    (key) =>
                      JSON.stringify(item.before[key]) !==
                      JSON.stringify(item.after[key]),
                  )
                  .map((key) => (
                    <div className="ua-diff" key={key}>
                      <strong>
                        {modules.find((m) => m.key === key)?.label || key}
                      </strong>
                      <span>
                        {item.before[key]?.enabled
                          ? item.before[key].role
                          : "No access"}{" "}
                        →{" "}
                        {item.after[key]?.enabled
                          ? item.after[key].role
                          : "No access"}
                      </span>
                      <small>
                        Scope: {item.before[key]?.scope || "—"} →{" "}
                        {item.after[key].scope}
                      </small>
                      <small>
                        Permissions removed:{" "}
                        {(item.before[key]?.permissions || [])
                          .filter(
                            (p: string) =>
                              !item.after[key].permissions.includes(p),
                          )
                          .join(", ") || "None"}
                      </small>
                      <small>
                        Permissions added:{" "}
                        {item.after[key].permissions
                          .filter(
                            (p: string) =>
                              !(item.before[key]?.permissions || []).includes(
                                p,
                              ),
                          )
                          .join(", ") || "None"}
                      </small>
                    </div>
                  ))}
              </details>
            ))}
            <Button
              disabled={busy}
              onClick={() =>
                secure(async (token) => {
                  const r = await api.post(
                    "/access/changes/apply",
                    review.payload,
                    { headers: { "X-Access-Step-Up": token } },
                  );
                  setMessage(
                    `${r.data.updated} users updated. Existing sessions were revoked.`,
                  );
                  setDrafts({});
                  setSelected({});
                  setTemplateMeta(undefined);
                  setReview(undefined);
                  setOpened(undefined);
                  refresh();
                })
              }
            >
              Reauthenticate & apply
            </Button>
          </DialogContent>
        </Dialog>
      )}
      {operation && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open && !busy) setOperation(undefined);
          }}
        >
          <DialogContent className="ua-root ua-step">
            <DialogTitle>Verify your administrator identity</DialogTitle>
            <p>
              Re-enter your current password to apply this administrative
              change.
            </p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                setError("");
                try {
                  const r = await api.post("/access/step-up", { password });
                  await operation(r.data.token);
                  setOperation(undefined);
                  setPassword("");
                } catch (e) {
                  report(e);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Current password
                <input
                  aria-label="Current administrator password"
                  autoComplete="current-password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {error && (
                <p role="alert" className="ua-error">
                  {error}
                </p>
              )}
              <Button disabled={busy || !password}>Verify & continue</Button>
            </form>
          </DialogContent>
        </Dialog>
      )}
      {createMode && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setCreateMode(undefined);
          }}
        >
          <DialogContent className="ua-root ua-step">
            <DialogTitle>
              {createMode === "invite" ? "Invite User" : "Add User"}
            </DialogTitle>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                secure(async (token) => {
                  const r = await api.post(
                    "/access/users",
                    {
                      companyId: company,
                      ...newUser,
                      password:
                        createMode === "invite" ? undefined : newUser.password,
                      invite: createMode === "invite",
                      reason: reason || "Create managed suite account",
                    },
                    { headers: { "X-Access-Step-Up": token } },
                  );
                  if (r.data.invitationToken)
                    setInvitation(
                      `${window.location.origin}/invite-access?token=${encodeURIComponent(r.data.invitationToken)}`,
                    );
                  setMessage(r.data.message);
                  setCreateMode(undefined);
                  setNewUser({ name: "", email: "", password: "" });
                  refresh();
                });
              }}
            >
              <label>
                Full name
                <input
                  required
                  value={newUser.name}
                  onChange={(e) =>
                    setNewUser((v) => ({ ...v, name: e.target.value }))
                  }
                />
              </label>
              <label>
                Email
                <input
                  required
                  type="email"
                  value={newUser.email}
                  onChange={(e) =>
                    setNewUser((v) => ({ ...v, email: e.target.value }))
                  }
                />
              </label>
              {createMode === "add" && (
                <label>
                  Initial password
                  <input
                    required
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                    value={newUser.password}
                    onChange={(e) =>
                      setNewUser((v) => ({ ...v, password: e.target.value }))
                    }
                  />
                </label>
              )}
              <p className="ua-hint">
                New accounts start with no module access. Invitations use the
                existing password setup flow; email delivery is currently
                manual.
              </p>
              <Button>Continue</Button>
            </form>
          </DialogContent>
        </Dialog>
      )}
      {invitation && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setInvitation("");
          }}
        >
          <DialogContent className="ua-root ua-step">
            <DialogTitle>Secure invitation · valid 48 hours</DialogTitle>
            <p>
              Email delivery is not configured. Share this private link with the
              intended recipient.
            </p>
            <input
              aria-label="Invitation link"
              readOnly
              value={invitation}
              onFocus={(e) => e.target.select()}
            />
            <Button onClick={() => navigator.clipboard.writeText(invitation)}>
              Copy invitation link
            </Button>
          </DialogContent>
        </Dialog>
      )}
      {roleEdit && catalog && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setRoleEdit(undefined);
          }}
        >
          <DialogContent className="ua-root ua-review">
            <DialogTitle>
              {roleEdit.id ? "Edit" : "Create"} module role
            </DialogTitle>
            <label>
              Name
              <input
                value={roleEdit.name}
                onChange={(e) =>
                  setRoleEdit((r: any) => ({ ...r, name: e.target.value }))
                }
              />
            </label>
            <label>
              Description
              <input
                value={roleEdit.description}
                onChange={(e) =>
                  setRoleEdit((r: any) => ({
                    ...r,
                    description: e.target.value,
                  }))
                }
              />
            </label>
            <label>
              Module
              <select
                disabled={!!roleEdit.id}
                value={roleEdit.module}
                onChange={(e) =>
                  setRoleEdit((r: any) => ({
                    ...r,
                    module: e.target.value,
                    permissions: [],
                    actions: ["view"],
                  }))
                }
              >
                {modules.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <ModuleEditor
              modules={modules.filter((m) => m.key === roleEdit.module)}
              catalog={catalog}
              grants={{
                [roleEdit.module]: {
                  enabled: true,
                  role: "Custom",
                  permissions: roleEdit.permissions,
                  actions: roleEdit.actions,
                  scope: roleEdit.scope,
                },
              }}
              patch={(_, g) =>
                setRoleEdit((r: any) => ({
                  ...r,
                  permissions: g.permissions,
                  actions: g.actions,
                  scope: g.scope,
                }))
              }
            />
            <p className="ua-warning">
              Updating this role affects {roleEdit.affectedUsers?.length || 0}{" "}
              assigned users and revokes their sessions.
            </p>
            {roleEdit.affectedUsers?.map((u: Person) => (
              <p key={u.id}>
                {u.name} · {u.email}<Link className="ml-2 text-primary" to={`/admin/control/users/${u.id}`}>Access 360�</Link>
              </p>
            ))}
            <label>
              Reason
              <input
                value={roleEdit.reason || ""}
                onChange={(e) =>
                  setRoleEdit((r: any) => ({ ...r, reason: e.target.value }))
                }
              />
            </label>
            <Button
              disabled={
                roleEdit.name.trim().length < 2 ||
                (roleEdit.reason || "").length < 3
              }
              onClick={() =>
                secure(async (token) => {
                  const payload = {
                    companyId: company,
                    module: roleEdit.module,
                    name: roleEdit.name,
                    description: roleEdit.description || "",
                    permissions: roleEdit.permissions,
                    actions: roleEdit.actions,
                    scope: roleEdit.scope,
                    version: roleEdit.version || 0,
                    active: roleEdit.active,
                    reason: roleEdit.reason,
                    expectedUserIds: (roleEdit.affectedUsers || []).map(
                      (u: Person) => u.id,
                    ),
                  };
                  await api.request({
                    url: roleEdit.id
                      ? `/access/roles/${roleEdit.id}`
                      : "/access/roles",
                    method: roleEdit.id ? "PUT" : "POST",
                    data: payload,
                    headers: { "X-Access-Step-Up": token },
                  });
                  setRoleEdit(undefined);
                  refresh();
                  setMessage("Module role saved.");
                })
              }
            >
              Reviewed affected users · save role
            </Button>
            {roleEdit.id && (
              <Button
                variant="outline"
                disabled={!!roleEdit.affectedUsers?.length}
                onClick={() =>
                  setRoleEdit((r: any) => ({
                    ...r,
                    active: false,
                    reason: r.reason || "Retire unused role",
                  }))
                }
              >
                {roleEdit.active
                  ? "Mark unused role for retirement"
                  : "Retirement staged; save to apply"}
              </Button>
            )}
          </DialogContent>
        </Dialog>
      )}
      {templateEdit && catalog && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setTemplateEdit(undefined);
          }}
        >
          <DialogContent className="ua-root ua-review">
            <DialogTitle>
              Permission template{" "}
              {templateEdit.version ? `v${templateEdit.version}` : ""}
            </DialogTitle>
            <label>
              Name
              <input
                value={templateEdit.name}
                onChange={(e) =>
                  setTemplateEdit((t: any) => ({ ...t, name: e.target.value }))
                }
              />
            </label>
            <label>
              Description
              <input
                value={templateEdit.description}
                onChange={(e) =>
                  setTemplateEdit((t: any) => ({
                    ...t,
                    description: e.target.value,
                  }))
                }
              />
            </label>
            <ModuleEditor
              modules={modules}
              catalog={catalog}
              grants={templateEdit.grants}
              patch={(key, g) =>
                setTemplateEdit((t: any) => ({
                  ...t,
                  grants: { ...t.grants, [key]: g },
                }))
              }
            />
            <label>
              Reason
              <input
                value={templateEdit.reason || ""}
                onChange={(e) =>
                  setTemplateEdit((t: any) => ({
                    ...t,
                    reason: e.target.value,
                  }))
                }
              />
            </label>
            <Button
              disabled={
                templateEdit.name.trim().length < 2 ||
                (templateEdit.reason || "").length < 3
              }
              onClick={() =>
                secure(async (token) => {
                  await api.request({
                    url: templateEdit.id
                      ? `/access/templates/${templateEdit.id}`
                      : "/access/templates",
                    method: templateEdit.id ? "PUT" : "POST",
                    data: {
                      companyId: company,
                      name: templateEdit.name,
                      description: templateEdit.description || "",
                      grants: templateEdit.grants,
                      version: templateEdit.version || 0,
                      active: templateEdit.active,
                      reason: templateEdit.reason,
                    },
                    headers: { "X-Access-Step-Up": token },
                  });
                  setTemplateEdit(undefined);
                  refresh();
                  setMessage("Versioned template saved.");
                })
              }
            >
              Save template
            </Button>
          </DialogContent>
        </Dialog>
      )}
      {membership && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setMembership(undefined);
          }}
        >
          <DialogContent className="ua-root ua-step">
            <DialogTitle>Authorize organization membership</DialogTitle>
            <p className="ua-warning">
              This explicitly changes which companies an existing account can
              enter. Module grants remain separate.
            </p>
            <label>
              Existing user ID
              <input
                type="number"
                min={1}
                value={membership.userId}
                onChange={(e) =>
                  setMembership((v: any) => ({ ...v, userId: e.target.value }))
                }
              />
            </label>
            <label>
              Company
              <select
                value={membership.companyId}
                onChange={(e) =>
                  setMembership((v: any) => ({
                    ...v,
                    companyId: Number(e.target.value),
                  }))
                }
              >
                {catalog?.companies.map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={membership.active}
                onChange={(e) =>
                  setMembership((v: any) => ({
                    ...v,
                    active: e.target.checked,
                  }))
                }
              />
              Membership active
            </label>
            <label>
              <input
                type="checkbox"
                checked={membership.isAdmin}
                onChange={(e) =>
                  setMembership((v: any) => ({
                    ...v,
                    isAdmin: e.target.checked,
                  }))
                }
              />
              Delegate access administration within their own permission ceiling
            </label>
            <label>
              Reason
              <input
                value={membership.reason}
                onChange={(e) =>
                  setMembership((v: any) => ({ ...v, reason: e.target.value }))
                }
              />
            </label>
            <Button
              disabled={!membership.userId || membership.reason.length < 3}
              onClick={() =>
                secure(async (token) => {
                  await api.post(
                    "/access/memberships",
                    { ...membership, userId: Number(membership.userId) },
                    { headers: { "X-Access-Step-Up": token } },
                  );
                  setMembership(undefined);
                  refresh();
                  setMessage("Organization membership updated.");
                })
              }
            >
              Reauthenticate & authorize
            </Button>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

export function AccessInvitationPage() {
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);
  return (
    <main className="ua-root ua-invitation">
      <ShieldCheck size={32} />
      <h1>Welcome to Business Suite</h1>
      <p>Choose your password to accept your invitation.</p>
      {!done && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const token = new URLSearchParams(window.location.search).get(
                "token",
              );
              await api.post("/auth/reset-password", {
                token,
                new_password: password,
              });
              setDone(true);
              setMessage("Your account is ready. Sign in to Business Suite.");
            } catch (e) {
              setMessage(err(e));
            }
          }}
        >
          <label>
            New password
            <input
              aria-label="New password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <Button>Accept invitation</Button>
        </form>
      )}
      {message && <p role="status">{message}</p>}
      {done && <a href="/login">Go to sign in</a>}
    </main>
  );
}
