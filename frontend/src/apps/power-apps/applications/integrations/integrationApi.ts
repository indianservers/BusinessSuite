import { api } from "@/services/api";
export type Schema = {
  type?: string;
  title?: string;
  default?: unknown;
  properties?: Record<string, Schema>;
  required?: string[];
  enum?: string[];
  maxLength?: number;
  const?: unknown;
  anyOf?: Schema[];
  items?: Schema;
  minimum?: number;
  maximum?: number;
  description?: string;
};
export type Action = {
  id: string;
  name: string;
  mutates: boolean;
  scopes: string[];
  input_schema: Schema;
};
export type Connector = {
  id: string;
  name: string;
  category: string;
  description: string;
  authentication: string[];
  oauth_ready?: boolean;
  actions: Action[];
  triggers?: {
    id: string;
    name: string;
    delivery:
      | "polling"
      | "native_webhook"
      | "native_polling"
      | "native_pubsub"
      | "native_stream";
    provider_secret_fields?: Record<string, string>;
    setup_schema: Schema;
  }[];
  setup: string[];
  documentation_url: string;
  availability: string;
  editor_options?: {
    credentials: Record<string, Record<string, string>>;
    config_schema: Schema;
    write_actions: string[];
    dynamic_writes: boolean;
  };
};
export type Connection = {
  id: number;
  connector_id: string;
  name: string;
  enabled: boolean;
  writes_enabled: boolean;
  health: string;
  revision: number;
  scopes: string[];
  sharing?: number[];
  config?: Record<string, unknown>;
};
export const integrationApi = {
  authorize: (environment: string, id: number, scopes: string[]) =>
    api
      .post<{ authorization_url: string }>(
        `/power-apps/integrations/connections/${id}/oauth`,
        { scopes },
        { params: { environment } },
      )
      .then((r) => r.data.authorization_url),
  updateConnection: (
    environment: string,
    connection: Connection,
    writesEnabled: boolean,
  ) =>
    api
      .put<Connection>(
        `/power-apps/integrations/connections/${connection.id}`,
        {
          expected_revision: connection.revision,
          enabled: connection.enabled,
          sharing: connection.sharing || [],
          writes_enabled: writesEnabled,
        },
        { params: { environment } },
      )
      .then((r) => r.data),
  createConnection: (
    environment: string,
    data: {
      connector_id: string;
      name: string;
      auth_type: string;
      secrets: Record<string, string>;
      config: Record<string, unknown>;
      scopes: string[];
      sharing: number[];
      writes_enabled: boolean;
    },
  ) =>
    api
      .post<Connection>("/power-apps/integrations/connections", data, {
        params: { environment },
      })
      .then((r) => r.data),
  execute: (
    environment: string,
    data: {
      connection_id: number;
      action_id: string;
      input: Record<string, unknown>;
      confirm_side_effect: boolean;
      request_id: string;
    },
  ) =>
    api
      .post<{ output: Record<string, unknown> }>(
        "/power-apps/integrations/execute",
        data,
        { params: { environment } },
      )
      .then((r) => r.data.output),
  catalog: () =>
    api
      .get<{ items: Connector[] }>("/power-apps/integrations/catalog")
      .then((r) => r.data.items),
  connections: (environment: string) =>
    api
      .get<{ items: Connection[] }>("/power-apps/integrations/connections", {
        params: { environment },
      })
      .then((r) => r.data.items),
};
export function message(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    .response?.data?.detail;
  return typeof detail === "string"
    ? detail
    : detail && typeof detail === "object" && "message" in detail
      ? String(detail.message)
      : "The request could not be completed. Check the action and connection settings.";
}
export const fieldLabels: Record<string, string> = {
  chat_id: "Chat ID",
  spreadsheet_id: "Spreadsheet ID",
  range: "Sheet range",
  values: "Rows (JSON array)",
  prompt: "Prompt",
  model: "Model ID",
  to: "Recipient email",
  recipient: "Recipient email",
  from_email: "Verified sender email",
  text: "Message",
  fields_json: "Record fields (JSON object)",
};
