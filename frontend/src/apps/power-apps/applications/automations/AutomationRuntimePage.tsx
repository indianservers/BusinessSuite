import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Download,
  Pause,
  Play,
  RefreshCw,
  ShieldCheck,
  Workflow,
  XCircle,
} from "lucide-react";
import {
  Background,
  Controls,
  ReactFlow,
  Position,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { powerApi } from "../../api";
import type { Resource } from "../../registry";
import { environmentFromSearch, studioPath } from "./studioApi";
import { WorkflowDebugger } from "./builder/IntelligencePanels";
import { GraphProposalPreview } from "./builder/IntelligencePanels";
import { asVisualGraph } from "./builder/graph";
import {
  runtimeApi,
  runtimeError,
  type RuntimeHistory,
  type Deployment,
  type RuntimePolicy,
  type ExecutionList,
  type Health,
  type RuntimeTrigger,
} from "./runtimeApi";
import "./runtime.css";
const defaults: RuntimePolicy = {
  concurrency: 4,
  overflow: "queue",
  max_queued: 1000,
  max_duration_seconds: 86400,
  identity: "initiator",
  delegated_owner: false,
};
const statuses = [
  "queued",
  "running",
  "waiting",
  "retry_scheduled",
  "completed",
  "failed",
  "cancelled",
];
const when = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : "—";
const json = (value: unknown) => JSON.stringify(value, null, 2);
const saveReport = (report: RuntimeHistory) => {
  const url = URL.createObjectURL(
    new Blob([json(report)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `execution-${report.execution.id}.json`;
  a.click();
  URL.revokeObjectURL(url);
};
const colors: Record<string, string> = {
  completed: "#268f64",
  failed: "#cf4265",
  running: "#7751c9",
  queued: "#ad8fca",
  waiting: "#c38b23",
  retry_scheduled: "#b57d20",
  cancelled: "#8d8897",
  skipped: "#aaa4b4",
};
export function RunGraph({
  report,
  focus,
  onFocus,
}: {
  report: RuntimeHistory;
  focus: string;
  onFocus: (id: string) => void;
}) {
  const nodes: Node[] = report.definition.nodes.map((n) => {
    const steps = report.steps.filter((s) => s.original_node_id === n.id);
    const step =
      steps.find((s) => s.status === "failed") ||
      steps.find((s) =>
        ["running", "queued", "waiting", "retry_scheduled"].includes(s.status),
      ) ||
      steps[steps.length - 1];
    const status = step?.status || "pending";
    return {
      id: n.id,
      position: n.position,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: {
        label: (
          <div>
            <small>{n.type.replace(/_/g, " ")}</small>
            <strong>{n.label}</strong>
            <span>
              {status.replace(/_/g, " ")}{" "}
              {steps.length > 1 ? `· ${steps.length} instances` : ""}
            </span>
          </div>
        ),
      },
      style: {
        border: `2px solid ${colors[status] || "#d7cce8"}`,
        boxShadow: focus === n.id ? "0 0 0 5px #dfd2fc" : "none",
        background: "#fff",
        width: 210,
        borderRadius: 16,
        padding: 14,
      },
    };
  });
  const edges: Edge[] = report.definition.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label || e.source_port,
    animated: report.steps.some(
      (s) => s.original_node_id === e.source && s.status === "running",
    ),
    style: {
      stroke: report.steps.some(
        (s) =>
          s.original_node_id === e.source &&
          s.active_ports.includes(e.source_port),
      )
        ? "#8d62c9"
        : "#ddd5e8",
      strokeWidth: 2,
    },
  }));
  return (
    <div className="rt-graph" aria-label="Persisted execution graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, n) => onFocus(n.id)}
        minZoom={0.15}
        maxZoom={1.5}
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
export default function AutomationRuntimePage() {
  const params = useParams(),
    location = useLocation(),
    navigate = useNavigate();
  const environment = environmentFromSearch(location.search),
    client = useMemo(() => runtimeApi(environment), [environment]);
  const workflowId = params.resourceId ? Number(params.resourceId) : undefined,
    runId = params.runId ? Number(params.runId) : undefined;
  const [permissions, setPermissions] = useState<string[]>([]),
    [list, setList] = useState<ExecutionList>(),
    [report, setReport] = useState<RuntimeHistory>(),
    [draft, setDraft] = useState<Resource>(),
    [deployment, setDeployment] = useState<Deployment>(),
    [health, setHealth] = useState<Health>(),
    [triggers, setTriggers] = useState<RuntimeTrigger[]>([]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [refresh, setRefresh] = useState(0),
    [auto, setAuto] = useState(true),
    [focus, setFocus] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({
      status: "",
      workflow: "",
      identity: "",
      initiator: "",
      error_type: "",
      start: "",
      end: "",
    }),
    [offset, setOffset] = useState(0);
  const [policy, setPolicy] = useState<RuntimePolicy>(defaults),
    [input, setInput] = useState("{}"),
    [confirm, setConfirm] = useState<
      "publish" | "activate" | "rerun" | "cancel" | null
    >(null),
    [triggerKind, setTriggerKind] = useState("scheduled"),
    [triggerEnabled, setTriggerEnabled] = useState(false),
    [triggerJSON, setTriggerJSON] = useState(
      json({ mode: "daily", timezone: "Asia/Kolkata", hour: 9, minute: 0 }),
    ),
    [secret, setSecret] = useState(""),
    [endpoint, setEndpoint] = useState("");
  const [resumeKey, setResumeKey] = useState("");
  const [focusedStep, setFocusedStep] = useState("");
  useEffect(() => {
    setConfirm(null);
    setFocus("");
    setFocusedStep("");
    setSecret("");
    setNotice("");
    setError("");
  }, [environment, workflowId, runId]);
  const requestKey = useRef(crypto.randomUUID());
  const can = (name: string) => permissions.includes(`power_apps_${name}`);
  useEffect(() => {
    let live = true;
    powerApi
      .catalog()
      .then((c) => {
        if (live) setPermissions(c.permissions);
      })
      .catch((e) => {
        if (live) setError(runtimeError(e));
      });
    return () => {
      live = false;
    };
  }, [environment]);
  useEffect(() => {
    if (!auto) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) setRefresh((v) => v + 1);
    }, 5000);
    return () => clearInterval(timer);
  }, [auto]);
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        if (runId) {
          const data = await client.history(runId);
          if (live) setReport(data);
        } else if (workflowId) {
          const [row, state, t] = await Promise.all([
            powerApi.read(environment, workflowId),
            client.deployment(workflowId),
            client.triggers(workflowId),
          ]);
          if (live) {
            setDraft(row);
            setDeployment(state);
            setTriggers(t);
          }
        } else {
          const data = await client.list({
            ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
            offset,
          });
          if (live) setList(data);
        }
      } catch (e) {
        if (live) setError(runtimeError(e));
      }
    };
    void load();
    return () => {
      live = false;
    };
  }, [client, environment, workflowId, runId, filters, offset, refresh]);
  useEffect(() => {
    if (deployment) setPolicy({ ...defaults, ...deployment.policy });
  }, [deployment?.revision]);
  useEffect(() => {
    if (!permissions.includes("power_apps_manage_environment")) return;
    let live = true;
    client
      .health()
      .then((h) => {
        if (live) setHealth(h);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [client, permissions, refresh]);
  const action = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(runtimeError(e));
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };
  const parseInput = () => {
    const v = JSON.parse(input);
    if (!v || typeof v !== "object" || Array.isArray(v))
      throw new Error("Input must be a JSON object");
    return v;
  };
  const changeFilter = (key: string, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setOffset(0);
  };
  const title = runId
    ? `Execution #${runId}`
    : workflowId
      ? draft?.name || "Workflow runtime"
      : "Executions";
  return (
    <main className="rt-page">
      <header className="rt-header">
        <Link
          className="rt-back"
          to={studioPath("/power-apps/automations", environment)}
        >
          <ArrowLeft size={17} /> Automations
        </Link>
        <div className="rt-heading">
          <span className="rt-symbol">
            <Activity size={27} />
          </span>
          <div>
            <p>POWER APPS · {environment.toUpperCase()}</p>
            <h1>{title}</h1>
            <span>
              {runId
                ? "Persisted history from an immutable workflow version"
                : workflowId
                  ? "Review, publish and explicitly activate your workflow"
                  : "Monitor durable runs, queue activity and outcomes"}
            </span>
          </div>
        </div>
        <div className="rt-tools">
          <label>
            <input
              type="checkbox"
              checked={auto}
              onChange={(e) => setAuto(e.target.checked)}
            />{" "}
            Live refresh
          </label>
          <button onClick={() => setRefresh((v) => v + 1)}>
            <RefreshCw size={15} /> Refresh
          </button>
          <Link
            to={studioPath("/power-apps/automations/executions", environment)}
          >
            All executions <ArrowUpRight size={14} />
          </Link>
        </div>
      </header>
      {error && (
        <div role="alert" className="rt-alert">
          {error}
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      {notice && (
        <p role="status" className="rt-notice">
          {notice}
        </p>
      )}
      {!workflowId && !runId && (
        <>
          <section className="rt-metrics" aria-label="Execution metrics">
            {[
              ["total", "Total executions", Activity],
              ["running", "Running", Play],
              ["waiting", "Waiting", Clock3],
              ["completed", "Completed", CheckCircle2],
              ["failed", "Failed", XCircle],
              ["cancelled", "Cancelled", Pause],
            ].map(([key, label, Icon]) => {
              const MetricIcon = Icon as typeof Activity;
              return (
                <article key={String(key)}>
                  <MetricIcon size={18} />
                  <strong>{list?.metrics[String(key)] ?? "—"}</strong>
                  <span>{String(label)}</span>
                </article>
              );
            })}
          </section>
          <section className="rt-panel">
            <div className="rt-panel-heading">
              <h2>Execution history</h2>
              <p>
                Queue depth <b>{list?.metrics.queue_depth ?? "—"}</b> · Average{" "}
                {list?.metrics.average_duration_seconds == null
                  ? "—"
                  : `${Number(list.metrics.average_duration_seconds).toFixed(2)}s`}{" "}
                · Failure rate{" "}
                {list
                  ? `${(Number(list.metrics.failure_rate) * 100).toFixed(1)}%`
                  : "—"}
              </p>
            </div>
            <div className="rt-filters">
              <label>
                Status
                <select
                  value={filters.status}
                  onChange={(e) => changeFilter("status", e.target.value)}
                >
                  <option value="">All statuses</option>
                  {statuses.map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </label>
              {[
                ["workflow", "Workflow ID"],
                ["identity", "Execution identity"],
                ["initiator", "Initiating identity"],
                ["error_type", "Error type"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    value={filters[key]}
                    onChange={(e) => changeFilter(key, e.target.value)}
                  />
                </label>
              ))}
              {[
                ["start", "From"],
                ["end", "Until"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    type="date"
                    value={filters[key].slice(0, 10)}
                    onChange={(e) =>
                      changeFilter(
                        key,
                        e.target.value
                          ? `${e.target.value}T${key === "end" ? "23:59:59" : "00:00:00"}Z`
                          : "",
                      )
                    }
                  />
                </label>
              ))}
              <label>
                Environment
                <select
                  value={environment}
                  onChange={(e) =>
                    navigate(
                      `${location.pathname}?environment=${e.target.value}`,
                    )
                  }
                >
                  {["development", "testing", "production"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="rt-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Execution</th>
                    <th>Workflow / version</th>
                    <th>Status</th>
                    <th>Identity</th>
                    <th>Created</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {list?.items.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <Link
                          to={studioPath(
                            `/power-apps/automations/executions/${row.id}`,
                            environment,
                          )}
                        >
                          #{row.id} <ArrowUpRight size={12} />
                        </Link>
                      </td>
                      <td>
                        <Link
                          to={studioPath(
                            `/power-apps/automations/${row.resource_id}/runtime`,
                            environment,
                          )}
                        >
                          Workflow {row.resource_id}
                        </Link>
                        <small>Version {row.workflow_version}</small>
                      </td>
                      <td>
                        <span className={`rt-status rt-${row.status}`}>
                          {row.status.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td>#{row.effective_user_id}</td>
                      <td>{when(row.created_at)}</td>
                      <td>{row.error_type || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {list && !list.items.length && (
              <div className="rt-empty">
                <Workflow size={32} />
                <h3>No executions yet</h3>
                <p>
                  Publish and activate a supported workflow, then start an
                  authorized run.
                </p>
              </div>
            )}
            <footer className="rt-pagination">
              <span>{list?.total ?? 0} executions</span>
              <button
                disabled={!offset}
                onClick={() => setOffset((v) => Math.max(0, v - 30))}
              >
                Previous
              </button>
              <button
                disabled={!list || offset + 30 >= list.total}
                onClick={() => setOffset((v) => v + 30)}
              >
                Next
              </button>
            </footer>
          </section>
        </>
      )}
      {workflowId &&
        draft &&
        draft.id === workflowId &&
        draft.environment === environment &&
        deployment && (
          <div className="rt-workflow-grid">
            <section className="rt-panel">
              <div className="rt-panel-heading">
                <h2>Publication</h2>
                <span className={`rt-status rt-${deployment.status}`}>
                  {deployment.status}
                </span>
              </div>
              <p>
                Saved draft V{draft.version} · Validated V
                {deployment.validated_version ?? "—"} · Publication snapshot #
                {deployment.version_id ?? "—"}
              </p>
              <p>
                Changing this draft does not change a running execution.
                Publication and activation are separate authorized actions.
              </p>
              <Link
                to={studioPath(
                  `/power-apps/automations/${workflowId}/edit`,
                  environment,
                )}
              >
                Open visual editor <ArrowUpRight size={13} />
              </Link>
              <GraphProposalPreview
                graph={asVisualGraph(draft.definition, [])}
              />
              <div className="rt-policy">
                <h3>Execution policy</h3>
                <label>
                  Concurrent runs
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={policy.concurrency}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        concurrency: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  When capacity is full
                  <select
                    value={policy.overflow}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        overflow: e.target.value as RuntimePolicy["overflow"],
                      })
                    }
                  >
                    <option value="queue">Queue additional runs</option>
                    <option value="reject">Reject additional runs</option>
                    <option value="ignore">
                      Ignore duplicate events; reject overflow
                    </option>
                  </select>
                </label>
                <label>
                  Maximum queued
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    value={policy.max_queued}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        max_queued: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  Maximum duration (seconds)
                  <input
                    type="number"
                    min={1}
                    max={604800}
                    value={policy.max_duration_seconds}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        max_duration_seconds: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  Execution identity
                  <select
                    value={policy.identity}
                    onChange={(e) =>
                      setPolicy({
                        ...policy,
                        identity: e.target.value as RuntimePolicy["identity"],
                        delegated_owner: false,
                        service_user_id: null,
                      })
                    }
                  >
                    <option value="initiator">Initiating user</option>
                    <option value="owner">Delegated workflow owner</option>
                    {can("manage_environment") && (
                      <option value="service">Managed service identity</option>
                    )}
                  </select>
                </label>
                {policy.identity === "service" && (
                  <label>
                    Managed service user ID
                    <input
                      type="number"
                      min={1}
                      value={policy.service_user_id || ""}
                      onChange={(e) =>
                        setPolicy({
                          ...policy,
                          service_user_id: Number(e.target.value) || null,
                        })
                      }
                    />
                    <small>
                      Requires an active, centrally managed non-admin identity
                      with scoped Power Apps execution access.
                    </small>
                  </label>
                )}
                {policy.identity === "owner" && (
                  <label className="rt-check">
                    <input
                      type="checkbox"
                      checked={policy.delegated_owner}
                      onChange={(e) =>
                        setPolicy({
                          ...policy,
                          delegated_owner: e.target.checked,
                        })
                      }
                    />{" "}
                    I explicitly delegate this workflow to my current scoped
                    authority. Future actions recheck access.
                  </label>
                )}
              </div>
              {can("manage_environment") && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await client.limits(workflowId, draft.version, policy);
                      setNotice(
                        "Concurrency limits updated without changing the execution identity.",
                      );
                    })
                  }
                >
                  Update runtime capacity
                </button>
              )}
              {can("publish") && (
                <div className="rt-actions">
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await client.transition(
                          workflowId,
                          "validate",
                          draft.version,
                          policy,
                        );
                        setNotice("The saved draft passed runtime validation.");
                      })
                    }
                  >
                    <ShieldCheck size={15} /> Validate saved draft
                  </button>
                  <button
                    disabled={
                      busy ||
                      deployment.validated_version !== draft.version ||
                      deployment.status === "active"
                    }
                    onClick={() => setConfirm("publish")}
                  >
                    Publish V{draft.version}
                  </button>
                  {["published", "paused"].includes(deployment.status) && (
                    <button
                      className="rt-primary"
                      disabled={busy}
                      onClick={() => setConfirm("activate")}
                    >
                      <Play size={14} /> Activate
                    </button>
                  )}
                  {deployment.status === "active" && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          client.transition(
                            workflowId,
                            "pause",
                            draft.version,
                            policy,
                          ),
                        )
                      }
                    >
                      <Pause size={14} /> Pause new triggers
                    </button>
                  )}
                  {deployment.status !== "active" &&
                    deployment.status !== "archived" && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(() =>
                            client.transition(
                              workflowId,
                              "archive",
                              draft.version,
                              policy,
                            ),
                          )
                        }
                      >
                        Archive runtime
                      </button>
                    )}
                </div>
              )}
            </section>
            <div>
              <section className="rt-panel">
                <h2>Start a manual run</h2>
                <p>
                  Uses the immutable active publication. The server rejects
                  incompatible trigger types.
                </p>
                <label>
                  Execution input JSON
                  <textarea
                    rows={7}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                  />
                </label>
                <button
                  className="rt-primary"
                  disabled={
                    busy || !can("execute") || deployment.status !== "active"
                  }
                  onClick={() =>
                    void action(async () => {
                      const result = await client.execute(
                        workflowId,
                        parseInput(),
                        requestKey.current,
                      );
                      requestKey.current = crypto.randomUUID();
                      navigate(
                        studioPath(
                          `/power-apps/automations/executions/${result.id}`,
                          environment,
                        ),
                      );
                    })
                  }
                >
                  <Play size={15} /> Start execution
                </button>
              </section>
              <section className="rt-panel">
                <h2>Configured triggers</h2>
                {triggers.map((t) => (
                  <article className="rt-trigger" key={t.id}>
                    <strong>{t.kind}</strong>
                    <span>{t.enabled ? "Enabled" : "Disabled"}</span>
                    <small>Next: {when(t.next_at)}</small>
                    <button
                      disabled={!can("publish") || busy}
                      onClick={() =>
                        void action(() =>
                          client.configure(
                            workflowId,
                            t.kind,
                            !t.enabled,
                            t.config,
                          ),
                        )
                      }
                    >
                      {t.enabled ? "Disable" : "Enable"}
                    </button>
                  </article>
                ))}
                <label>
                  Trigger type
                  <select
                    value={triggerKind}
                    onChange={(e) => {
                      setTriggerKind(e.target.value);
                      setSecret("");
                      setEndpoint("");
                      setTriggerJSON(
                        json(
                          e.target.value === "scheduled"
                            ? {
                                mode: "daily",
                                timezone: "Asia/Kolkata",
                                hour: 9,
                                minute: 0,
                              }
                            : e.target.value === "webhook"
                              ? {
                                  schema: {
                                    type: "object",
                                    properties: { message: { type: "string" } },
                                    required: ["message"],
                                    additionalProperties: false,
                                  },
                                  max_per_minute: 30,
                                  ip_allowlist: [],
                                }
                              : {
                                  provider: "",
                                  event: "",
                                  schema: { type: "object", properties: {} },
                                },
                        ),
                      );
                    }}
                  >
                    <option value="scheduled">Schedule</option>
                    <option value="webhook">Signed webhook</option>
                    <option value="internal">Registered internal event</option>
                  </select>
                </label>
                <p>
                  {triggerKind === "scheduled"
                    ? "Modes: once, minutes, hourly, daily, weekly, monthly, cron. Use an IANA timezone. DST gaps are skipped and the first repeated time is used."
                    : triggerKind === "webhook"
                      ? "HMAC-SHA256 over timestamp.nonce.raw-body. Headers: X-Power-Timestamp, X-Power-Nonce, X-Power-Signature. Secrets are shown once."
                      : "Only explicitly registered and authorized server providers can subscribe."}
                </p>
                <label>
                  Trigger policy JSON
                  <textarea
                    rows={9}
                    value={triggerJSON}
                    onChange={(e) => setTriggerJSON(e.target.value)}
                  />
                </label>
                <label className="rt-check">
                  <input
                    type="checkbox"
                    checked={triggerEnabled}
                    onChange={(e) => setTriggerEnabled(e.target.checked)}
                  />{" "}
                  Enable this configured trigger
                </label>
                <div className="rt-actions">
                  <button
                    disabled={busy || !can("publish")}
                    onClick={() =>
                      void action(async () => {
                        const result = await client.configure(
                          workflowId,
                          triggerKind,
                          triggerEnabled,
                          JSON.parse(triggerJSON),
                        );
                        setSecret(result.secret || "");
                        setEndpoint(result.endpoint || "");
                        setNotice("Trigger policy saved.");
                      })
                    }
                  >
                    Save trigger policy
                  </button>
                  {triggerKind === "webhook" && (
                    <button
                      disabled={busy || !can("publish")}
                      onClick={() =>
                        void action(async () => {
                          const result = await client.rotate(workflowId);
                          setSecret(result.secret);
                        })
                      }
                    >
                      Rotate secret
                    </button>
                  )}
                </div>
                {endpoint && (
                  <label>
                    Webhook endpoint
                    <input readOnly value={endpoint} />
                  </label>
                )}
                {secret && (
                  <div className="rt-secret">
                    <strong>Copy this secret now</strong>
                    <input
                      aria-label="New webhook secret"
                      readOnly
                      value={secret}
                    />
                    <button onClick={() => setSecret("")}>Hide secret</button>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      {runId &&
        report &&
        report.execution.id === runId &&
        report.execution.environment === environment && (
          <>
            <section className="rt-panel rt-run-meta">
              <div>
                <span className={`rt-status rt-${report.execution.status}`}>
                  {report.execution.status.replace(/_/g, " ")}
                </span>
                <h2>
                  Workflow {report.execution.resource_id} · Version{" "}
                  {report.execution.workflow_version}
                </h2>
                <p>
                  Correlation <code>{report.run.correlation_id}</code>
                </p>
                <p>
                  Identity #{report.run.effective_user_id} · Started{" "}
                  {when(report.execution.started_at)} · Finished{" "}
                  {when(report.execution.finished_at)}
                </p>
                <p>Deadline {when(report.run.deadline)}</p>
                {report.run.error && (
                  <p className="rt-error">{report.run.error}</p>
                )}
              </div>
              <div className="rt-actions">
                <button
                  disabled={!report.can_export || busy}
                  onClick={() =>
                    void action(async () => {
                      saveReport(await client.report(runId));
                    })
                  }
                >
                  <Download size={14} /> Export sanitized report
                </button>
                {can("execute") && (
                  <>
                    <button
                      disabled={
                        busy ||
                        ![
                          "queued",
                          "running",
                          "waiting",
                          "retry_scheduled",
                        ].includes(report.execution.status)
                      }
                      onClick={() => setConfirm("cancel")}
                    >
                      Cancel run
                    </button>
                    <button
                      disabled={busy || report.execution.status !== "failed"}
                      onClick={() =>
                        void action(() => client.action(runId, "retry"))
                      }
                    >
                      Retry failed step safely
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => {
                        setInput(json(report.run.input_payload));
                        setConfirm("rerun");
                      }}
                    >
                      Re-run with confirmation
                    </button>
                  </>
                )}
              </div>
            </section>
            <RunGraph
              report={report}
              focus={focus}
              onFocus={(id) => {
                setFocus(id);
                setFocusedStep(
                  report.steps.find((s) => s.original_node_id === id)
                    ?.node_id || "",
                );
              }}
            />
            <section className="rt-panel rt-debug">
              <WorkflowDebugger
                mode="runtime"
                allowExport={report.can_export}
                onExport={() =>
                  void action(async () => {
                    saveReport(await client.report(runId));
                  })
                }
                focusedNodeId={focusedStep}
                result={{
                  validation: { issues: [] },
                  timeline: report.steps.map((s) => ({
                    node_id: s.node_id,
                    label:
                      report.definition.nodes.find(
                        (n) => n.id === s.original_node_id,
                      )?.label || s.node_id,
                    status: s.status,
                    input: s.input_payload,
                    output: s.output,
                    error: s.error,
                    active_ports: s.active_ports,
                    attempt: s.attempt,
                    started_at: s.started_at,
                    finished_at: s.finished_at,
                  })),
                }}
                visible={report.steps.length}
                onFocus={(id) => {
                  setFocusedStep(id);
                  setFocus(
                    report.steps.find((s) => s.node_id === id)
                      ?.original_node_id || id,
                  );
                }}
              />
            </section>
            <section className="rt-panel">
              {can("execute") && report.execution.status === "waiting" && (
                <div>
                  <h3>Resume an authorized event wait</h3>
                  <label>
                    Resume event key
                    <input
                      value={resumeKey}
                      onChange={(e) => setResumeKey(e.target.value)}
                    />
                  </label>
                  <button
                    disabled={busy || resumeKey.length < 8}
                    onClick={() =>
                      void action(() => client.resume(runId, resumeKey))
                    }
                  >
                    Request resume
                  </button>
                </div>
              )}
              <h2>Execution audit timeline</h2>
              <div className="rt-events">
                {report.events.map((e) => (
                  <article key={e.id}>
                    <time>{when(e.created_at)}</time>
                    <strong>{e.kind.replace(/_/g, " ")}</strong>
                    <code>{json(e.details)}</code>
                  </article>
                ))}
              </div>
            </section>
          </>
        )}
      {health && (
        <details className="rt-panel">
          <summary>
            Operational health · {health.workers_alive} workers alive
          </summary>
          <div className="rt-health">
            <span>Scheduler {when(health.scheduler_last_at)}</span>
            <span>{health.queue_depth} queued jobs</span>
            <span>{health.leased} leased jobs</span>
            <span>Oldest due {health.oldest_due_seconds.toFixed(1)}s</span>
          </div>
          <h3>Unresolved dead letters</h3>
          {health.dead_letters.length ? (
            health.dead_letters.map((d) => (
              <p key={d.id}>
                <Link
                  to={studioPath(
                    `/power-apps/automations/executions/${d.run_id}`,
                    environment,
                  )}
                >
                  Execution #{d.run_id}
                </Link>{" "}
                · {d.reason} · {when(d.created_at)}
              </p>
            ))
          ) : (
            <p>No unresolved dead letters in this scope.</p>
          )}
        </details>
      )}
      {confirm && (
        <div className="rt-modal-backdrop">
          <section
            className="rt-modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Confirm ${confirm}`}
          >
            <h2>
              {confirm === "publish"
                ? `Publish saved draft V${draft?.version}`
                : confirm === "activate"
                  ? "Activate this publication"
                  : confirm === "rerun"
                    ? "Start a new execution"
                    : "Cancel this execution"}
            </h2>
            <p>
              {confirm === "publish"
                ? "This pins an immutable saved version and its execution policy. Existing runs keep their version."
                : confirm === "activate"
                  ? "Configured triggers may enqueue work when the worker is running. No unsupported action can be activated."
                  : confirm === "rerun"
                    ? "This creates a new run using the current active publication, which may differ from this history."
                    : "Committed steps remain in history. Remaining jobs and waits will be cancelled."}
            </p>
            {confirm === "rerun" && (
              <label>
                Input JSON
                <textarea
                  rows={8}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                />
              </label>
            )}
            <div className="rt-actions">
              <button onClick={() => setConfirm(null)}>Go back</button>
              <button
                className="rt-primary"
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    if (confirm === "publish" || confirm === "activate") {
                      await client.transition(
                        workflowId!,
                        confirm,
                        draft!.version,
                        policy,
                      );
                      setNotice(
                        confirm === "publish"
                          ? "Immutable version published. Activate it explicitly when ready."
                          : "Publication activated.",
                      );
                    } else if (confirm === "cancel")
                      await client.action(runId!, "cancel");
                    else {
                      const result = await client.rerun(
                        runId!,
                        parseInput(),
                        requestKey.current,
                      );
                      requestKey.current = crypto.randomUUID();
                      navigate(
                        studioPath(
                          `/power-apps/automations/executions/${result.id}`,
                          environment,
                        ),
                      );
                    }
                  })
                }
              >
                {busy ? "Working…" : `Confirm ${confirm}`}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
