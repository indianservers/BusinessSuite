import { ApprovalAnalytics } from "./ApprovalAnalytics";
export { ApprovalAnalytics } from "./ApprovalAnalytics";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BadgeCheck,
  ArrowLeft,
  Plus,
  RefreshCw,
  ChevronRight,
  ArrowUpRight,
  Inbox,
  FileText,
  GitBranch,
  Layers3,
  ShieldCheck,
  Users,
  BarChart3,
  History as HistoryIcon,
  Settings,
} from "lucide-react";
import {
  ApprovalInbox,
  ApprovalDetailsDrawer,
  ApprovalForm,
  ApproverPicker,
} from "./ApprovalComponents";
import { ApprovalDesigner } from "./ApprovalDesigner";
import {
  approvalApi as api,
  errorMessage,
  formatDate,
  duration,
  root,
  type Policy,
  type Person,
  type Analytics,
  type Process,
} from "./api";
import "./approvals.css";
export * from "./ApprovalComponents";
export * from "./ApprovalDesigner";
const sections = [
  ["", "Overview", BadgeCheck],
  ["inbox", "Approval inbox", Inbox],
  ["requests", "My requests", FileText],
  ["designer", "Process designer", GitBranch],
  ["templates", "Templates", Layers3],
  ["policies", "Policies", ShieldCheck],
  ["delegations", "Delegations", Users],
  ["analytics", "Analytics", BarChart3],
  ["audit", "Audit trail", HistoryIcon],
  ["settings", "Settings", Settings],
] as const;
type Delegation = {
  id: number;
  owner_user_id: number;
  alternate_user_id: number;
  starts_at: string;
  ends_at: string;
  reason: string;
  enabled: boolean;
};
export function DelegationManager({
  environment,
  people,
}: {
  environment: string;
  people: Person[];
}) {
  const [rows, setRows] = useState<Delegation[]>([]),
    [alternate, setAlternate] = useState<number[]>([]),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [reason, setReason] = useState(""),
    [error, setError] = useState("");
  const load = useCallback(
    () =>
      api
        .get<{ items: Delegation[] }>("/delegations", environment)
        .then((r) => setRows(r.items))
        .catch((e) => setError(errorMessage(e))),
    [environment],
  );
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <section className="ap-panel ap-form">
      <h2>Temporary delegation</h2>
      <p>
        Delegate only within an explicit date range. Each workflow must permit
        delegation. Chains and overlapping periods are prohibited.
      </p>
      {error && (
        <p className="ap-error" role="alert">
          {error}
        </p>
      )}
      <ApproverPicker
        people={people}
        value={alternate}
        onChange={(ids) => setAlternate(ids.slice(-1))}
      />
      <label>
        Starts
        <input
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
      </label>
      <label>
        Ends
        <input
          type="datetime-local"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </label>
      <label>
        Reason
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <button
        className="ap-primary"
        disabled={!alternate.length || !start || !end || !reason}
        onClick={async () => {
          try {
            await api.post("/delegations", environment, {
              alternate_user_id: alternate[0],
              starts_at: new Date(start).toISOString(),
              ends_at: new Date(end).toISOString(),
              reason,
            });
            await load();
          } catch (e) {
            setError(errorMessage(e));
          }
        }}
      >
        Create delegation
      </button>
      {rows.map((d) => (
        <div className="ap-assignment" key={d.id}>
          <span>
            #{d.owner_user_id} → #{d.alternate_user_id}
            <small>
              {formatDate(d.starts_at)} – {formatDate(d.ends_at)} ·{" "}
              {d.enabled ? "Enabled" : "Revoked"}
            </small>
          </span>
          {d.enabled && (
            <button
              onClick={async () => {
                try {
                  const { api } = await import("@/services/api");
                  await api.delete(`${root}/delegations/${d.id}`, {
                    params: { environment },
                  });
                  await load();
                } catch (e) {
                  setError(errorMessage(e));
                }
              }}
            >
              Revoke
            </button>
          )}
        </div>
      ))}
    </section>
  );
}
export default function ApprovalsPage() {
  const location = useLocation(),
    navigate = useNavigate();
  const environment =
      new URLSearchParams(location.search).get("environment") || "development",
    section = location.pathname.split("/")[3] || "";
  const [policies, setPolicies] = useState<Policy[]>([]),
    [people, setPeople] = useState<Person[]>([]),
    [data, setData] = useState<Analytics | null>(null),
    [templates, setTemplates] = useState<
      { id: string; name: string; definition: Process }[]
    >([]),
    [permissions, setPermissions] = useState<string[]>([]),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<number | null>(
      Number(new URLSearchParams(location.search).get("request")) || null,
    );
  const path = (s: string) =>
    `/power-apps/approvals${s ? "/" + s : ""}?environment=${environment}`;
  const load = useCallback(() => {
    Promise.all([
      api.get<{ items: Policy[] }>("/policies", environment),
      api.get<Analytics>("/analytics", environment),
      api.get<{ items: Person[] }>("/people", environment),
      api.get<{ items: { id: string; name: string; definition: Process }[] }>(
        "/templates",
        environment,
      ),
      api.get<{ permissions: string[] }>("/capabilities", environment),
    ])
      .then(([p, a, u, t, c]) => {
        setPolicies(p.items);
        setData(a);
        setPeople(u.items);
        setTemplates(t.items);
        setPermissions(c.permissions);
        setError("");
      })
      .catch((e) => setError(errorMessage(e)));
  }, [environment]);
  useEffect(load, [load]);
  const manage = permissions.includes("power_apps_approval_manage"),
    canSubmit = permissions.includes("power_apps_approval_submit");
  return (
    <main className="ap-app">
      <aside className="ap-sidebar">
        <Link to="/power-apps" className="ap-suite-link">
          <ArrowLeft size={15} />
          Power Apps
        </Link>
        <div className="ap-brand">
          <span>
            <BadgeCheck size={23} />
          </span>
          <div>
            Approvals<small>DECISIONS, WITH CLARITY</small>
          </div>
        </div>
        <nav>
          {sections.map(([key, label, Icon]) => (
            <Link
              key={key}
              to={path(key)}
              className={section === key ? "active" : ""}
            >
              <Icon size={17} />
              {label}
              {key === "inbox" && !!data?.counts.awaiting_me && (
                <b>{data.counts.awaiting_me}</b>
              )}
            </Link>
          ))}
        </nav>
        <div className="ap-side-note">
          <ShieldCheck size={19} />
          <strong>Every decision, accountable.</strong>
          <p>
            Independent approvals with versioned policies and verifiable
            evidence.
          </p>
        </div>
      </aside>
      <div className="ap-main">
        <header className="ap-header">
          <span>
            WORKSPACE <ChevronRight size={12} /> APPROVALS
          </span>
          <select
            aria-label="Approval environment"
            value={environment}
            onChange={(e) =>
              navigate(`${location.pathname}?environment=${e.target.value}`)
            }
          >
            {["development", "testing", "production"].map((e) => (
              <option key={e}>{e}</option>
            ))}
          </select>
        </header>
        <div className="ap-content">
          <div className="ap-page-title">
            <div>
              <small className="ap-eyebrow">BUSINESS SUITE · POWER APPS</small>
              <h1>
                {section === "new"
                  ? "New request"
                  : sections.find(([key]) => key === section)?.[1] ||
                    "Approvals"}
              </h1>
              <p>Clear ownership. Thoughtful decisions. A complete trail.</p>
            </div>
            <div className="ap-actions">
              <button aria-label="Refresh approvals" onClick={load}>
                <RefreshCw size={16} />
              </button>
              {canSubmit && (
                <Link className="ap-primary" to={path("new")}>
                  <Plus size={16} />
                  New request
                </Link>
              )}
            </div>
          </div>
          {error && (
            <p className="ap-error" role="alert">
              {error}
            </p>
          )}
          {!section && (
            <>
              <div className="ap-welcome">
                <div>
                  <span className="ap-badge">YOUR DECISION CENTER</span>
                  <h2>Keep good work moving.</h2>
                  <p>
                    Review requests, remove bottlenecks, and give every decision
                    the context it deserves.
                  </p>
                  <Link to={path("inbox")}>
                    Open your approval inbox <ArrowUpRight size={15} />
                  </Link>
                </div>
                <BadgeCheck size={115} strokeWidth={1} />
              </div>
              <div className="ap-metrics">
                {[
                  ["awaiting_me", "Awaiting my approval"],
                  ["submitted_by_me", "Submitted by me"],
                  ["pending", "Pending requests"],
                  ["overdue", "Overdue requests"],
                  ["approved", "Approved"],
                  ["rejected", "Rejected"],
                  ["average_seconds", "Average approval time"],
                  ["escalated", "Escalated requests"],
                ].map(([key, label]) => (
                  <div className="ap-metric" key={key}>
                    <small>{label}</small>
                    <strong>
                      {key === "average_seconds"
                        ? duration(data?.counts[key])
                        : (data?.counts[key] ?? "—")}
                    </strong>
                    <span>
                      {key === "awaiting_me"
                        ? "Your active assignments"
                        : "Current authorized scope"}
                    </span>
                  </div>
                ))}
              </div>
              <ApprovalInbox environment={environment} onOpen={setSelected} />
            </>
          )}
          {["inbox", "requests"].includes(section) && (
            <ApprovalInbox
              key={section + selected}
              environment={environment}
              scope={section === "requests" ? "submitted" : "assigned"}
              onOpen={setSelected}
            />
          )}{" "}
          {section === "new" && (
            <ApprovalForm
              environment={environment}
              policies={policies}
              onSubmitted={(id) => {
                navigate(path("requests"));
                setSelected(id);
                load();
              }}
            />
          )}
          {section === "designer" && (
            <ApprovalDesigner
              environment={environment}
              policies={policies}
              people={people}
              onSaved={load}
            />
          )}{" "}
          {section === "policies" && (
            <section className="ap-panel">
              <div className="ap-section-title">
                <h2>Approval processes</h2>
                {manage && (
                  <Link to={path("designer")}>
                    <Plus size={15} />
                    Design process
                  </Link>
                )}
              </div>
              {policies.length ? (
                policies.map((p) => (
                  <div className="ap-assignment" key={p.id}>
                    <span>
                      <strong>{p.name}</strong>
                      <small>
                        Version {p.version} · {p.definition.stages.length}{" "}
                        stages · {p.enabled ? "Activated" : "Disabled"}
                      </small>
                    </span>
                    <Link to={path(`designer/${p.id}`)}>Open designer ↗</Link>
                  </div>
                ))
              ) : (
                <p className="ap-empty">
                  No processes yet. Start from a configurable template.
                </p>
              )}
            </section>
          )}
          {section === "templates" && (
            <div className="ap-template-grid">
              {templates.map((t) => (
                <article className="ap-panel" key={t.id}>
                  <span className="ap-template-icon">
                    <Layers3 size={21} />
                  </span>
                  <h3>{t.name}</h3>
                  <p>
                    Choose approvers, request fields, and deadlines before
                    activation.
                  </p>
                  <span className="ap-badge">Disabled template</span>
                  {manage && (
                    <button
                      onClick={async () => {
                        try {
                          const p = await api.post<Policy>(
                            "/policies",
                            environment,
                            { name: t.name, definition: t.definition },
                          );
                          load();
                          navigate(path(`designer/${p.id}`));
                        } catch (e) {
                          setError(errorMessage(e));
                        }
                      }}
                    >
                      Configure template <ChevronRight size={14} />
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
          {section === "delegations" && (
            <DelegationManager environment={environment} people={people} />
          )}{" "}
          {section === "analytics" && (
            <ApprovalAnalytics
              data={data}
              environment={environment}
              policies={policies}
            />
          )}{" "}
          {section === "audit" && (
            <section className="ap-panel">
              <h2>Recent approval evidence</h2>
              <p className="ap-muted">
                Full evidence is verified in each request's decision history.
              </p>
              {data?.recent.length ? (
                data.recent.map((h) => (
                  <div className="ap-assignment" key={h.id}>
                    <span>
                      {h.event_type.replace(/_/g, " ")}
                      <small>
                        {formatDate(h.created_at)} ·{" "}
                        {h.actor_user_id
                          ? `User #${h.actor_user_id}`
                          : "Workflow worker"}
                      </small>
                    </span>
                    <span>{h.reason}</span>
                  </div>
                ))
              ) : (
                <p className="ap-empty">No approval activity yet.</p>
              )}
            </section>
          )}
          {section === "settings" && (
            <section className="ap-panel ap-form">
              <h2>Approval governance</h2>
              <p>
                Decisions require explicit permission and a current assignment.
                Authorship alone grants no decision authority.
              </p>
              <dl className="ap-fields">
                <div>
                  <dt>Execution engine</dt>
                  <dd>Phase 3 durable worker</dd>
                </div>
                <div>
                  <dt>Segregation of duties</dt>
                  <dd>Independent decisions required</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>Signed audit chain, not a qualified digital signature</dd>
                </div>
                <div>
                  <dt>Documents</dt>
                  <dd>Private storage · verified hashes · 2 MB each</dd>
                </div>
                <div>
                  <dt>Activation</dt>
                  <dd>Explicit publication and activation required</dd>
                </div>
                <div>
                  <dt>Scheduler</dt>
                  <dd>Elapsed UTC deadlines; no automatic approval</dd>
                </div>
              </dl>
            </section>
          )}
        </div>
      </div>
      {selected && (
        <ApprovalDetailsDrawer
          key={selected}
          id={selected}
          environment={environment}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      )}
    </main>
  );
}
