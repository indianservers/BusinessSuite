import { NativeSelect } from "@/components/ui/native-select";
import "./integrations.css";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { WorkflowNode } from "../automations/builder/types";
import ActionFields from "./ActionFields";
import ModuleConnectionSettings from "./ModuleConnectionSettings";
import {
  integrationApi,
  message,
  type Connector,
  type Connection,
} from "./integrationApi";
export default function ConnectorNodeEditor({
  node,
  onChange,
  environment,
  readOnly,
  settingsOnly = false,
  onOpenSettings,
}: {
  node: WorkflowNode;
  onChange: (n: WorkflowNode) => void;
  environment: string;
  readOnly: boolean;
  settingsOnly?: boolean;
  onOpenSettings?: () => void;
}) {
  const [connector, setConnector] = useState<Connector>();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState("");
  const [testBusy, setTestBusy] = useState(false);
  const [testConfirmed, setTestConfirmed] = useState(false);
  const [testStatus, setTestStatus] = useState("");
  const requestKey = useRef(crypto.randomUUID());
  useEffect(() => {
    requestKey.current = crypto.randomUUID();
    setTestConfirmed(false);
    setTestStatus("");
  }, [node.credential_reference, node.config.action, node.config.input]);
  useEffect(() => {
    let live = true;
    Promise.all([
      integrationApi.catalog(),
      integrationApi.connections(environment),
    ])
      .then(([catalog, rows]) => {
        if (live) {
          setConnector(catalog.find((c) => node.type === "connector_" + c.id));
          setConnections(rows);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(message(e));
      });
    return () => {
      live = false;
    };
  }, [node.type, environment, node.credential_reference]);
  const action =
    node.config.action ? connector?.actions.find((a) => a.id === node.config.action) : connector?.actions[0];
  const connection = connections.find((c) => String(c.id) === node.credential_reference && c.connector_id === connector?.id);
  const actionInput = Object.fromEntries(Object.entries((node.config.input || {}) as Record<string, unknown>).filter(([key]) => key in (action?.input_schema.properties || {})));
  const actionMutates = Boolean(action?.mutates || (connector?.id === "http" && !["GET", "HEAD"].includes(String(actionInput.method || "GET"))));
  if (settingsOnly) return <>
    {error && <p role="alert">{error}</p>}
    {connector ? <ModuleConnectionSettings key={`${node.id}-${connector.id}-${environment}`} connector={connector} connection={connection} environment={environment} readOnly={readOnly} onSaved={(saved) => {
      setConnections((rows) => [saved, ...rows.filter((row) => row.id !== saved.id)]);
      onChange({ ...node, credential_reference: String(saved.id) });
    }} /> : !error && <p role="status">Loading module settings...</p>}
    <Link target="_blank" rel="noreferrer" to={`/power-apps/connectors?environment=${environment}`}>Manage all module connections</Link>
  </>;
  return (
    <section aria-label="Integration configuration">
      <p>
        Choose your saved account, then map webhook data or earlier step outputs
        into the action.
      </p>
      {error && <p role="alert">{error}</p>}
      {onOpenSettings && <button type="button" className="ic-module-test" onClick={onOpenSettings}>Module settings / add connection</button>}
      <label className="as-basic-field">
        Connection
        <NativeSelect
          disabled={readOnly}
          aria-label="Integration connection"
          value={node.credential_reference || ""}
          onChange={(e) =>
            onChange({ ...node, credential_reference: e.target.value || null })
          }
        >
          <option value="">Choose a connection</option>
          {connections
            .filter((c) => c.connector_id === connector?.id && c.enabled)
            .map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name} - {c.health}
              </option>
            ))}
        </NativeSelect>
      </label>
      <Link
        target="_blank"
        rel="noreferrer"
        to={`/power-apps/connectors?environment=${environment}`}
      >
        Manage connections / add account
      </Link>
      <button
        type="button"
        onClick={() =>
          integrationApi
            .connections(environment)
            .then(setConnections)
            .catch((e) => setError(message(e)))
        }
      >
        Refresh connections
      </button>
      {connector && (
        <>
          <label className="as-basic-field">
            Action
            <NativeSelect
              disabled={readOnly}
              aria-label="Integration action"
              value={action?.id || ""}
              onChange={(e) =>
                onChange({
                  ...node,
                  config: {
                    action: e.target.value,
                    input: {},
                    confirm_write: false,
                  },
                })
              }
            >
              <option value="">Choose an action</option>
              {connector.actions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </NativeSelect>
          </label>
          {action && (
            <ActionFields
              connector={connector.id}
              action={action}
              value={actionInput}
              disabled={readOnly}
              onChange={(input) =>
                onChange({
                  ...node,
                  config: { ...node.config, action: action.id, input },
                })
              }
            />
          )}
          {connector.id === "telegram" && action?.id === "send_message" && <p className="as-config-note">Enter a numeric Chat ID (including the minus sign for groups) or @channelusername. Start a conversation with your bot first, or add it to your group/channel with permission to send messages.</p>}
          {action && actionMutates && (
            <label className="as-basic-field">
              <input
                type="checkbox"
                disabled={readOnly}
                checked={node.config.confirm_write === true}
                onChange={(e) =>
                  onChange({
                    ...node,
                    config: {
                      ...node.config,
                      action: action?.id || String(node.config.action || ""),
                      confirm_write: e.target.checked,
                    },
                  })
                }
              />
              Authorize this external write when the published workflow runs
            </label>
          )}
          {action && <div className="ic-module-action-test">
            {actionMutates && <label className="ic-module-toggle"><input type="checkbox" disabled={readOnly || testBusy || !connection?.writes_enabled} checked={testConfirmed} onChange={(e) => setTestConfirmed(e.target.checked)} />{connector.id === "telegram" ? "Send this test message to the specified chat now" : `Run ${action.name.toLowerCase()} against this account now`}</label>}
            {actionMutates && connection && !connection.writes_enabled && <p className="as-config-note">Enable the required write access in Module settings before testing this action.</p>}
            <button type="button" className="ic-module-test" disabled={readOnly || testBusy || !connection?.enabled || (actionMutates && (!testConfirmed || !connection.writes_enabled))} onClick={async () => {
              if (!connection) return;
              setTestBusy(true); setError(""); setTestStatus("");
              try {
                await integrationApi.execute(environment, {
                  connection_id: connection.id, action_id: action.id,
                  input: actionInput,
                  confirm_side_effect: testConfirmed, request_id: requestKey.current,
                });
                setTestStatus(connector.id === "telegram" ? (actionMutates ? "Test message sent successfully." : "Bot verified successfully.") : `${action.name} test completed.`);
              } catch (e) { setError(message(e)); } finally { setTestBusy(false); }
            }}>{testBusy ? "Testing..." : connector.id === "telegram" ? (actionMutates ? "Send test message" : "Verify bot token") : `Test: ${action.name}`}</button>
            {testStatus && <p role="status" className="ic-module-success">{testStatus}</p>}
          </div>}
          <p className="as-config-note">
            Secrets remain server-side. Verify your account in Module settings.
            Local workflow previews do not send requests; the explicit test
            buttons above call the provider directly.
          </p>
        </>
      )}
    </section>
  );
}
