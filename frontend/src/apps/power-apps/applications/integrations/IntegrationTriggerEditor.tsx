import { useEffect, useState } from "react";
import { NativeSelect } from "@/components/ui/native-select";
import type { WorkflowNode } from "../automations/builder/types";
import ActionFields from "./ActionFields";
import ConnectorNodeEditor from "./ConnectorNodeEditor";
import {
  integrationApi,
  message,
  type Connector,
  type Connection,
} from "./integrationApi";

export default function IntegrationTriggerEditor({
  node,
  onChange,
  environment,
  readOnly,
}: {
  node: WorkflowNode;
  onChange: (node: WorkflowNode) => void;
  environment: string;
  readOnly: boolean;
}) {
  const [connector, setConnector] = useState<Connector>();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState(false);
  const [revision, setRevision] = useState(0);
  const id = node.type.replace("integration_trigger_", "");
  const setup = (node.config.setup || {}) as Record<string, unknown>;
  useEffect(() => {
    let live = true;
    Promise.all([
      integrationApi.catalog(),
      integrationApi.connections(environment),
    ])
      .then(([catalog, rows]) => {
        if (live) {
          setConnector(catalog.find((c) => c.id === id));
          setConnections(rows.filter((c) => c.connector_id === id));
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(message(e));
      });
    return () => {
      live = false;
    };
  }, [id, environment, revision]);
  const trigger =
    connector?.triggers?.find((t) => t.id === setup.event) ||
    connector?.triggers?.[0];
  const change = (value: Record<string, unknown>) =>
    onChange({
      ...node,
      config: {
        ...node.config,
        setup: Object.fromEntries(
          Object.entries({ event: trigger?.id, ...value }).filter(
            ([, item]) =>
              item !== "" &&
              item !== undefined &&
              (!Array.isArray(item) || item.length > 0),
          ),
        ),
      },
    });
  return (
    <section aria-label="Connector trigger setup">
      {error && <p role="alert">{error}</p>}
      <label className="ic-field">
        Connection *
        <NativeSelect
          aria-label="Trigger connection"
          disabled={readOnly}
          value={String(setup.connection_id || "")}
          onChange={(e) =>
            change({ ...setup, connection_id: Number(e.target.value) })
          }
        >
          <option value="">Choose a connection</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {!c.enabled ? " (disabled)" : ""}
            </option>
          ))}
        </NativeSelect>
      </label>
      <button
        type="button"
        onClick={() => {
          setSettings(!settings);
          setRevision((n) => n + 1);
        }}
      >
        {settings ? "Close connection settings" : "Connection settings"}
      </button>
      {settings && (
        <ConnectorNodeEditor
          settingsOnly
          node={{
            ...node,
            type: "connector_" + id,
            credential_reference: String(setup.connection_id || ""),
            config: {},
          }}
          environment={environment}
          readOnly={readOnly}
          onChange={(updated) => {
            change({
              ...setup,
              connection_id: Number(updated.credential_reference),
            });
            setRevision((n) => n + 1);
          }}
        />
      )}
      {trigger && (
        <ActionFields
          connector={id}
          action={{
            id: trigger.id,
            name: trigger.name,
            mutates: false,
            scopes: [],
            input_schema: {
              ...trigger.setup_schema,
              properties: Object.fromEntries(
                Object.entries(trigger.setup_schema.properties || {}).filter(
                  ([key]) => key !== "connection_id",
                ),
              ),
            },
          }}
          value={setup}
          onChange={change}
          disabled={readOnly}
        />
      )}
      <p className="as-config-note">
        {trigger?.delivery === "polling"
          ? "The automation worker polls this resource. Publish this setup, then enable Connector events in Runtime."
          : trigger?.delivery === "native_polling"
            ? "Power Apps reads provider changes directly. Publish this setup, then enable Connector events in Runtime. No relay is required."
            : "Publish this setup, then enable Connector events in Runtime. Power Apps registers and maintains the native provider subscription automatically. Provider setup credentials are entered in Runtime."}
      </p>
      {(id === "google_sheets" || id === "excel_online") && (
        <p className="as-config-note">
          Use a stable, unique key column. Google Sheets ranges must include
          headers; Excel watches a table. Changes are detected at the polling
          interval. Watch at most 1,000 rows and 64 KB. Existing rows are a
          baseline unless Emit initial is enabled.
        </p>
      )}
      {id === "telegram" && (
        <p className="as-config-note">
          Receives bot updates including media, captions, channel posts and
          callback queries. Only one polling listener may use a bot. Group
          privacy and administrator permissions control which updates Telegram
          sends.
        </p>
      )}
    </section>
  );
}
