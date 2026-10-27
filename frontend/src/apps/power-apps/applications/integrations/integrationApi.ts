import { api } from "@/services/api";
export type Schema = {
  type?: string;
  title?: string;
  default?: unknown;
  properties?: Record<string, Schema>;
  required?: string[];
  enum?: string[];
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
  setup: string[];
  documentation_url: string;
  availability: string;
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
};
export const integrationApi = {
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
export const providerFields: Record<string, string[]> = {
  google_sheets: ["spreadsheet_id", "range", "values", "limit"],
  google_drive: ["file_id", "name", "content", "parent_id", "limit"],
  github: ["owner", "repository", "title", "text", "limit"],
  outlook: ["recipient", "subject", "text", "limit"],
  smtp: ["recipient", "subject", "text"],
  http: ["url", "method", "body", "query", "timeout_seconds"],
  outgoing_webhook: ["url", "method", "body", "timeout_seconds"],
};
