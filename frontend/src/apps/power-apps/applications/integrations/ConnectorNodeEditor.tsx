import "./integrations.css";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { WorkflowNode } from "../automations/builder/types";
import ActionFields from "./ActionFields";
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
}: {
  node: WorkflowNode;
  onChange: (n: WorkflowNode) => void;
  environment: string;
  readOnly: boolean;
}) {
  const [connector, setConnector] = useState<Connector>();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState("");
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
  }, [node.type, environment]);
  const action =
    connector?.actions.find((a) => a.id === node.config.action) ||
    connector?.actions[0];
  return (
    <section aria-label="Integration configuration">
      <p>
        Choose your saved account, then map webhook data or earlier step outputs
        into the action.
      </p>
      {error && <p role="alert">{error}</p>}
      <label className="as-basic-field">
        Connection
        <select
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
        </select>
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
            <select
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
              {connector.actions.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          {action && (
            <ActionFields
              connector={connector.id}
              action={action}
              value={(node.config.input || {}) as Record<string, unknown>}
              disabled={readOnly}
              onChange={(input) =>
                onChange({
                  ...node,
                  config: { ...node.config, action: action.id, input },
                })
              }
            />
          )}
          {action?.mutates && (
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
                      action: action.id,
                      confirm_write: e.target.checked,
                    },
                  })
                }
              />
              Authorize this external write when the published workflow runs
            </label>
          )}
          <p className="as-config-note">
            Secrets remain server-side. Test this connection in Integration
            Studio. Publish and run through the existing execution worker; local
            preview does not send requests.
          </p>
        </>
      )}
    </section>
  );
}
