import type { Connector } from "./integrationApi";

export const authLabels: Record<string, string> = {
  none: "No authentication", bearer: "API token", api_key: "API key",
  basic: "Username and password", database: "Database credentials",
  signing: "Signing secret", service_account: "Service account",
  oauth2: "Authorize account (OAuth)", gateway: "Company AI gateway",
  platform_smtp: "Configured company email transport",
};
export const authFields: Record<string, Record<string, string>> = {
  bearer: { access_token: "Access token" }, api_key: { api_key: "API key" },
  basic: { username: "Username", password: "Password" },
  database: { username: "Database username", password: "Database password" },
  signing: { signing_secret: "Signing secret" }, service_account: { service_account: "Service account JSON" },
};
export function supportsWrites(connector: Connector) {
  return connector.editor_options?.dynamic_writes || connector.id === "http" || connector.actions.some((a) => a.mutates);
}
export function providerScopes(connector: Connector, auth: string, writes: boolean) {
  return auth === 'oauth2' ? [...(connector.oauth_scopes || []), ...(writes ? connector.oauth_write_scopes || [] : [])] : [];
}
