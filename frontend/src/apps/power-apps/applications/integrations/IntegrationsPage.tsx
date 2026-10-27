import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  Plug,
  Search,
  ShieldCheck,
  Webhook,
  X,
} from "lucide-react";
import { api } from "@/services/api";
import {
  integrationApi,
  message,
  type Connector,
  type Connection,
} from "./integrationApi";
import ActionFields from "./ActionFields";
import "./integrations.css";
type Log = {
  id: number;
  connector_id: string;
  action_id: string;
  status: string;
  duration_ms: number;
  error_category: string | null;
  correlation_id: string;
};
const secretKeys: Record<string, string[]> = {
  none: [],
  bearer: ["access_token"],
  api_key: ["api_key"],
  basic: ["username", "password"],
  signing: ["signing_secret"],
  database: ["username", "password"],
  service_account: ["service_account"],
  oauth2: [],
  gateway: [],
  platform_smtp: [],
};
export default function IntegrationsPage() {
  const dialogRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const environment = params.get("environment") || "development";
  const [catalog, setCatalog] = useState<Connector[]>([]),
    [connections, setConnections] = useState<Connection[]>([]),
    [logs, setLogs] = useState<Log[]>([]),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState(""),
    [selected, setSelected] = useState<Connector>(),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [name, setName] = useState(""),
    [auth, setAuth] = useState("bearer"),
    [secrets, setSecrets] = useState<Record<string, string>>({}),
    [hosts, setHosts] = useState(""),
    [writes, setWrites] = useState(false),
    [testing, setTesting] = useState<Connection>(),
    [actionId, setActionId] = useState(""),
    [input, setInput] = useState<Record<string, unknown>>({}),
    [requestKey, setRequestKey] = useState(() => crypto.randomUUID()),
    [confirmed, setConfirmed] = useState(false),
    [output, setOutput] = useState<unknown>();
  const load = useCallback(async () => {
    try {
      const [items, rows] = await Promise.all([
        integrationApi.catalog(),
        integrationApi.connections(environment),
      ]);
      setCatalog(items);
      setConnections(rows);
      setError("");
    } catch (e) {
      setError(message(e));
    }
  }, [environment]);
  const loadLogs = useCallback(
    () =>
      api
        .get<{ items: Log[] }>("/power-apps/integrations/monitor", {
          params: { environment },
        })
        .then((r) => setLogs(r.data.items))
        .catch(() => setLogs([])),
    [environment],
  );
  useEffect(() => {
    void load();
    void loadLogs();
  }, [load, loadLogs]);
  useEffect(() => {
    if (!selected && !testing) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.querySelector<HTMLElement>("button,input,select,textarea")?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        setSelected(undefined);
        setTesting(undefined);
        setSecrets({});
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
        ),
      );
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [selected, testing, busy]);
  const profile = catalog.find((c) => c.id === testing?.connector_id);
  const action = profile?.actions.find((a) => a.id === actionId);
  const visible = catalog.filter(
    (c) =>
      (!category || c.category === category) &&
      `${c.name} ${c.description}`.toLowerCase().includes(search.toLowerCase()),
  );
  async function create() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const config = hosts
        ? {
            hosts: hosts
              .split(",")
              .map((h) => h.trim())
              .filter(Boolean),
          }
        : {};
      const scopes = [
        ...new Set(
          selected.actions
            .filter((a) => writes || !a.mutates)
            .flatMap((a) => a.scopes),
        ),
      ];
      const response = await api.post<Connection>(
        "/power-apps/integrations/connections",
        {
          connector_id: selected.id,
          name,
          auth_type: auth,
          secrets,
          config,
          scopes,
          sharing: [],
          writes_enabled: writes,
        },
        { params: { environment } },
      );
      setSecrets({});
      setSelected(undefined);
      setNotice(
        "Connection saved. Run an authorized test action to verify provider access.",
      );
      await load();
      if (auth === "oauth2") {
        const r = await api.post<{ authorization_url: string }>(
          `/power-apps/integrations/connections/${response.data.id}/oauth`,
          { scopes },
          { params: { environment } },
        );
        window.location.assign(r.data.authorization_url);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  function openTest(c: Connection) {
    const p = catalog.find((p) => p.id === c.connector_id);
    setTesting(c);
    setActionId(
      p?.actions.find((a) => !a.mutates)?.id || p?.actions[0]?.id || "",
    );
    setInput({});
    setRequestKey(crypto.randomUUID());
    setConfirmed(false);
    setOutput(undefined);
    setError("");
  }
  return (
    <main className="integration-studio">
      <header className="ic-header">
        <div>
          <Link to="/power-apps">
            <ArrowLeft size={15} />
            Power Apps
          </Link>
          <p className="ic-eyebrow">CONNECTIONS, WITH CONTROL</p>
          <h1>Integration Studio</h1>
          <p>
            Connect your tools. Start with a webhook, then build the next
            action.
          </p>
        </div>
        <div>
          <span className="ic-env">{environment}</span>
          <button
            onClick={() => {
              void load();
              void loadLogs();
            }}
          >
            Refresh
          </button>
        </div>
      </header>
      {error && (
        <p role="alert" className="ic-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="ic-notice">
          <Check size={15} />
          {notice}
        </p>
      )}
      <section className="ic-start">
        <Webhook size={30} />
        <div>
          <h2>Start with webhooks</h2>
          <p>
            Add Webhook Trigger in the automation canvas, connect an action,
            then publish. Configure the signed incoming URL in the workflow
            runtime page.
          </p>
        </div>
        <Link to={`/power-apps/automations?environment=${environment}`}>
          Build a workflow
        </Link>
      </section>
      <div className="ic-quickstarts" aria-label="Webhook workflow starters">
        {[
          ["webhook-sheets-email", "Webhook > Sheets > Email"],
          ["webhook-groq-slack", "Webhook > Groq > Slack"],
          ["forms-responses-email", "Webhook > Google Forms > Gmail"],
        ].map(([id, label]) => (
          <button
            key={id}
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const response = await api.post<{ id: number }>(
                  `/power-apps/automations/templates/${id}/use`,
                  {},
                  { params: { environment } },
                );
                navigate(
                  `/power-apps/automations/${response.data.id}/edit?environment=${environment}`,
                );
              } catch (e) {
                setError(message(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="ic-section-title">
        <div>
          <h2>Explore integrations</h2>
          <span>{catalog.length} registered connectors</span>
        </div>
        <p>
          Accounts require your authorization. No live verification is claimed
          before a real provider request.
        </p>
      </div>
      <div className="ic-filters">
        <label>
          <Search size={17} />
          <input
            aria-label="Search integrations"
            value={search}
            placeholder="Google Sheets, email, Groq..."
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Integration category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {[...new Set(catalog.map((c) => c.category))].sort().map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>
      <div className="ic-grid">
        {visible.map((c) => (
          <article className="ic-card" key={c.id}>
            <div className="ic-card-mark">
              <Plug size={23} />
              <span>{c.category}</span>
            </div>
            <h3>{c.name}</h3>
            <p>
              {c.actions.length
                ? `${c.actions.length} supported actions`
                : "Uses the existing signed webhook trigger"}
            </p>
            <div className="ic-card-actions">
              {c.actions.slice(0, 3).map((a) => (
                <span key={a.id}>{a.name}</span>
              ))}
            </div>
            <button
              disabled={busy}
              onClick={async () => {
                if (c.id === "incoming_webhook") {
                  setBusy(true);
                  try {
                    const response = await api.post<{ id: number }>(
                      "/power-apps/automations/templates/webhook-receiver/use",
                      {},
                      { params: { environment } },
                    );
                    navigate(
                      `/power-apps/automations/${response.data.id}/edit?environment=${environment}`,
                    );
                  } catch (e) {
                    setError(message(e));
                  } finally {
                    setBusy(false);
                  }
                  return;
                }
                setSelected(c);
                setName(c.name + " account");
                setAuth(
                  c.authentication.find(
                    (a) => a !== "oauth2" || c.oauth_ready,
                  ) || c.authentication[0],
                );
                setSecrets({});
                setHosts("");
                setWrites(false);
                setError("");
              }}
            >
              {c.id === "incoming_webhook"
                ? "Configure webhook"
                : "Connect account"}
            </button>
            <a href={c.documentation_url} target="_blank" rel="noreferrer">
              Provider documentation
            </a>
          </article>
        ))}
      </div>
      {!visible.length && (
        <p className="ic-empty">
          No matching integration. Try another name or category.
        </p>
      )}
      <section className="ic-connections">
        <h2>Your connections</h2>
        <p>
          Credentials are encrypted on the server and never returned to the
          editor.
        </p>
        {!connections.length && (
          <p className="ic-empty">Connect an account above to start.</p>
        )}
        {connections.map((c) => (
          <article key={c.id}>
            <Plug size={20} />
            <div>
              <strong>{c.name}</strong>
              <small>
                {catalog.find((p) => p.id === c.connector_id)?.name} -{" "}
                {c.enabled ? c.health : "disabled"} - writes{" "}
                {c.writes_enabled ? "authorized" : "disabled"}
              </small>
            </div>
            <button
              onClick={async () => {
                try {
                  await api.put(
                    `/power-apps/integrations/connections/${c.id}`,
                    {
                      expected_revision: c.revision,
                      enabled: c.enabled,
                      writes_enabled: !c.writes_enabled,
                      sharing: [],
                    },
                    { params: { environment } },
                  );
                  await load();
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              {c.writes_enabled
                ? "Disable external writes"
                : "Allow external writes"}
            </button>
            <button disabled={!c.enabled} onClick={() => openTest(c)}>
              Test / run action
            </button>
            <button
              onClick={async () => {
                try {
                  await api.put(
                    `/power-apps/integrations/connections/${c.id}`,
                    {
                      expected_revision: c.revision,
                      enabled: !c.enabled,
                      writes_enabled: c.writes_enabled,
                      sharing: [],
                    },
                    { params: { environment } },
                  );
                  await load();
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              {c.enabled ? "Disable" : "Enable"}
            </button>
          </article>
        ))}
      </section>
      <section className="ic-monitor">
        <h2>Recent provider requests</h2>
        <p>
          Real action outcomes and correlation IDs. Accepted email requests do
          not confirm delivery.
        </p>
        {!logs.length && <p>No visible provider requests yet.</p>}
        {logs.map((l) => (
          <article key={l.id}>
            <strong>
              {l.connector_id} / {l.action_id}
            </strong>
            <span>
              {l.status} - {l.duration_ms} ms {l.error_category || ""}
            </span>
            <small>{l.correlation_id}</small>
          </article>
        ))}
      </section>
      {(selected || testing) && (
        <div className="ic-overlay">
          <section
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label={
              selected ? "Connect account" : "Test integration action"
            }
            className="ic-dialog"
          >
            <button
              className="ic-close"
              aria-label="Close integration dialog"
              onClick={() => {
                setSelected(undefined);
                setTesting(undefined);
                setSecrets({});
              }}
            >
              <X size={20} />
            </button>
            {selected ? (
              <>
                <p className="ic-eyebrow">{selected.category}</p>
                <h2>Connect {selected.name}</h2>
                <label className="ic-field">
                  Connection name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label className="ic-field">
                  Authentication
                  <select
                    value={auth}
                    onChange={(e) => {
                      setAuth(e.target.value);
                      setSecrets({});
                    }}
                  >
                    {selected.authentication.map((a) => (
                      <option
                        key={a}
                        disabled={a === "oauth2" && !selected.oauth_ready}
                      >
                        {a}
                        {a === "oauth2" && !selected.oauth_ready
                          ? " (administrator setup required)"
                          : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {(secretKeys[auth] || []).map((key) => (
                  <label className="ic-field" key={key}>
                    {key.replace(/_/g, " ")}
                    <input
                      type="password"
                      autoComplete="off"
                      value={secrets[key] || ""}
                      onChange={(e) =>
                        setSecrets({ ...secrets, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                {["http", "outgoing_webhook", "postgresql"].includes(
                  selected.id,
                ) && (
                  <label className="ic-field">
                    Exact allowed hostnames
                    <input
                      placeholder="api.example.com"
                      value={hosts}
                      onChange={(e) => setHosts(e.target.value)}
                    />
                  </label>
                )}
                {selected.id === "postgresql" && (
                  <p>
                    PostgreSQL requires database and table allowlists; configure
                    it through the typed connection API until the database setup
                    panel is available.
                  </p>
                )}
                <label className="ic-check">
                  <input
                    type="checkbox"
                    checked={writes}
                    onChange={(e) => setWrites(e.target.checked)}
                  />
                  Allow intentional external writes for this connection
                </label>
                <ul>
                  {selected.setup.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
                <p>
                  <ShieldCheck size={16} />
                  Secrets are write-only. Use a dedicated provider credential.
                </p>
                <button
                  className="ic-primary"
                  disabled={
                    busy || !name.trim() || selected.id === "postgresql"
                  }
                  onClick={() => void create()}
                >
                  {busy
                    ? "Connecting..."
                    : auth === "oauth2"
                      ? "Save and authorize account"
                      : "Save connection"}
                </button>
              </>
            ) : (
              testing &&
              profile && (
                <>
                  <h2>
                    {profile.name} - {testing.name}
                  </h2>
                  <label className="ic-field">
                    Action
                    <select
                      value={actionId}
                      onChange={(e) => {
                        setActionId(e.target.value);
                        setInput({});
                        setRequestKey(crypto.randomUUID());
                        setConfirmed(false);
                        setOutput(undefined);
                      }}
                    >
                      {profile.actions.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {action && (
                    <ActionFields
                      connector={profile.id}
                      action={action}
                      value={input}
                      onChange={(value) => {
                        setInput(value);
                        setRequestKey(crypto.randomUUID());
                      }}
                    />
                  )}
                  {action?.mutates && (
                    <label className="ic-check">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={(e) => setConfirmed(e.target.checked)}
                      />
                      Run this external write now. This can send a message,
                      create a record or consume provider credits.
                    </label>
                  )}
                  <button
                    className="ic-primary"
                    disabled={
                      busy ||
                      !action ||
                      (!!action.mutates &&
                        (!confirmed || !testing.writes_enabled))
                    }
                    onClick={async () => {
                      setBusy(true);
                      setError("");
                      try {
                        const r = await api.post(
                          "/power-apps/integrations/execute",
                          {
                            connection_id: testing.id,
                            action_id: actionId,
                            input,
                            confirm_side_effect: confirmed,
                            request_id: requestKey,
                          },
                          { params: { environment } },
                        );
                        setOutput(r.data.output);
                        await load();
                        await loadLogs();
                      } catch (e) {
                        setError(message(e));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {busy ? "Calling provider..." : "Run action"}
                  </button>
                  {output !== undefined && (
                    <pre>{JSON.stringify(output, null, 2)}</pre>
                  )}
                </>
              )
            )}
            {error && (
              <p role="alert" className="ic-error">
                {error}
              </p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
