import { NativeSelect } from "@/components/ui/native-select";
import { useState } from "react";
import { KeyRound, ShieldCheck, Loader2 } from "lucide-react";
import ActionFields from "./ActionFields";
import { integrationApi, message, type Connection, type Connector } from "./integrationApi";

import { authFields, authLabels, supportsWrites, providerScopes } from "./moduleOptions";

function verificationInput(connector: Connector, config: Record<string, unknown> = {}) {
  const action = connector.actions.find((a) => a.id === "test" && !a.mutates);
  if (!action) return null;
  const input: Record<string, unknown> = {};
  for (const field of action.input_schema.required || []) {
    const value = config[field];
    if (value === undefined || value === "" || value === null) return null;
    input[field] = value;
  }
  return { action, input };
}
export default function ModuleConnectionSettings({ connector, connection, environment, readOnly, onSaved }: {
  connector: Connector; connection?: Connection; environment: string; readOnly: boolean;
  onSaved: (connection: Connection) => void;
}) {
  const telegram = connector.id === "telegram";
  const [name, setName] = useState(`${connector.name} connection`);
  const [auth, setAuth] = useState(() => connector.authentication.find((a) => a !== "oauth2" || connector.oauth_ready) || connector.authentication[0]);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [writes, setWrites] = useState(false);
  const [pendingWrites, setPendingWrites] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [authorizationUrl, setAuthorizationUrl] = useState("");
  const fields = connector.editor_options?.credentials[auth] || (telegram ? { access_token: "Bot token" } : authFields[auth]) || {};
  const writesAvailable = supportsWrites(connector);
  const writeActions = connector.actions.filter((a) => a.mutates);
  const writeLabel = telegram ? "send Telegram messages" : writeActions.length ? writeActions.map((a) => a.name.toLowerCase()).join(", ") : "use POST, PUT, PATCH or DELETE requests";
  const schema = connector.editor_options?.config_schema || { type: "object", properties: {} };
  const configSchema = { ...schema, properties: Object.fromEntries(Object.entries(schema.properties || {}).filter(([key]) => key !== "header_name" || auth === "api_key")) };
  const canSave = !readOnly && !busy && Boolean(name.trim()) && Boolean(auth) && (auth !== "oauth2" || Boolean(connector.oauth_ready)) &&
    Object.keys(fields).every((key) => Boolean(secrets[key]?.trim())) &&
    (schema.required || []).every((key) => config[key] !== undefined && config[key] !== "" && (!Array.isArray(config[key]) || (config[key] as unknown[]).length > 0));
  const verifyAction = connector.actions.find((a) => a.id === "test" && !a.mutates);
  const newVerification = verificationInput(connector, config);
  const savedVerification = connection && verificationInput(connector, connection.config);
  const missingWriteScopes = connection && writeActions.some((a) => a.scopes.some((scope) => !connection.scopes.includes(scope)));
  const verify = async (saved: Connection) => {
    const probe = verificationInput(connector, saved.config);
    if (!probe) return;
    const output = await integrationApi.execute(environment, { connection_id: saved.id, action_id: probe.action.id, input: probe.input, confirm_side_effect: false, request_id: crypto.randomUUID() });
    const data = output.data as { result?: { username?: string } } | undefined;
    const username = data?.result?.username;
    setStatus(telegram ? `Bot verified${username ? `: @${username}` : " successfully"}.` : "Connection check completed.");
    onSaved({ ...saved, health: "healthy" });
  };
  return (
    <section className="ic-module-settings" aria-label={`${connector.name} module settings`}>
      <header><span><KeyRound size={18} /></span><div><h3>{connector.name} settings</h3><p>Connection options for this module</p></div></header>
      {telegram && <p>Create a bot with <a href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a>, then paste its token below. Verification checks the bot identity without sending a message.</p>}
      {connector.setup.length > 0 && !telegram && <details><summary>Set up {connector.name}</summary><ul>{connector.setup.map((step) => <li key={step}>{step}</li>)}</ul></details>}
      {connection && <div className="ic-module-connected"><ShieldCheck size={16} /><span>{connection.name}<small>{connection.health}{writesAvailable ? ` · ${connection.writes_enabled ? "Writes enabled" : "Read access only"}` : ""}</small></span></div>}
      {connection && writesAvailable && <>
        <label className="ic-module-toggle"><input type="checkbox" aria-label="Enable writes for saved module connection" checked={pendingWrites ?? connection.writes_enabled} disabled={busy || readOnly || (!connection.writes_enabled && Boolean(missingWriteScopes))} onChange={async (event) => {
          const enabled = event.target.checked;
          setPendingWrites(enabled); setBusy(true); setError(""); setStatus("");
          try {
            const updated = await integrationApi.updateConnection(environment, connection, enabled);
            onSaved(updated);
            setStatus(telegram ? `Sending ${enabled ? "enabled" : "disabled"} for this connection.` : `Write access ${enabled ? "enabled" : "disabled"} for this connection.`);
          } catch (e) { setError(message(e)); } finally { setBusy(false); setPendingWrites(null); }
        }} />Allow this connection to {writeLabel}</label>
        {missingWriteScopes && !connection.writes_enabled && <p>Create a connection with the required write scopes to enable these actions.</p>}
      </>}
      {!readOnly && <>
        <label className="as-basic-field">Connection name<input aria-label="Module connection name" maxLength={180} value={name} disabled={busy} onChange={(e) => setName(e.target.value)} /></label>
        {connector.authentication.length > 1 ? <label className="as-basic-field">Authentication
          <NativeSelect aria-label="Module authentication" value={auth} disabled={busy} onChange={(e) => { setAuth(e.target.value); setSecrets({}); setAuthorizationUrl(""); }}>
            {connector.authentication.map((method) => <option key={method} value={method} disabled={method === "oauth2" && !connector.oauth_ready}>{authLabels[method] || method}{method === "oauth2" && !connector.oauth_ready ? " — administrator setup required" : ""}</option>)}
          </NativeSelect>
        </label> : <p>{authLabels[auth] || auth}</p>}
        {Object.entries(fields).map(([key, label]) => <label className="as-basic-field" key={auth + key}>{label}
          {key === "service_account" ? <textarea aria-label={label} autoComplete="off" spellCheck={false} rows={4} value={secrets[key] || ""} disabled={busy} onChange={(e) => setSecrets({ ...secrets, [key]: e.target.value })} /> :
            <input aria-label={telegram ? "Telegram bot token" : label} type="password" autoComplete="new-password" spellCheck={false} value={secrets[key] || ""} disabled={busy} placeholder={`Enter ${label.toLowerCase()}`} onChange={(e) => setSecrets({ ...secrets, [key]: e.target.value })} />}
        </label>)}
        <ActionFields connector={connector.id} action={{ id: "connection_settings", name: "Connection settings", mutates: false, scopes: [], input_schema: configSchema }} value={config} disabled={busy} onChange={setConfig} />
        {writesAvailable && <label className="ic-module-toggle"><input type="checkbox" checked={writes} disabled={busy} onChange={(e) => setWrites(e.target.checked)} />{telegram ? "Allow this connection to send Telegram messages" : `Allow this connection to ${writeLabel}`}</label>}
        <button type="button" className="as-button-primary" disabled={!canSave} onClick={async () => {
          setBusy(true); setError(""); setStatus(""); setAuthorizationUrl("");
          try {
            const scopes = [...new Set([...providerScopes(connector, auth, writes), ...connector.actions.filter((a) => writes || !a.mutates).flatMap((a) => a.scopes)])];
            if (auth === "oauth2" && ["outlook", "excel_online", "onedrive", "sharepoint", "microsoft_calendar", "microsoft_teams"].includes(connector.id)) scopes.push("offline_access");
            const effectiveConfig = { ...Object.fromEntries(Object.entries(configSchema.properties || {}).filter(([, field]) => field.default !== undefined).map(([key, field]) => [key, field.default])), ...config };
            if (auth !== "api_key") delete effectiveConfig.header_name;
            const saved = await integrationApi.createConnection(environment, { connector_id: connector.id, name: name.trim(), auth_type: auth, secrets: Object.fromEntries(Object.keys(fields).map((key) => [key, secrets[key].trim()])), config: effectiveConfig, sharing: [], writes_enabled: Boolean(writesAvailable && writes), scopes });
            setSecrets({}); onSaved(saved); setStatus("Connection saved securely.");
            if (auth === "oauth2") setAuthorizationUrl(await integrationApi.authorize(environment, saved.id, scopes));
            else await verify(saved);
          } catch (e) { setError(message(e)); } finally { setBusy(false); }
        }}>{busy ? <Loader2 size={14} className="ic-module-spinner" /> : <ShieldCheck size={14} />}{auth === "oauth2" ? "Save and authorize account" : newVerification ? "Save & verify connection" : "Save connection"}</button>
      </>}
      {authorizationUrl && <a href={authorizationUrl} target="_blank" rel="noreferrer">Authorize {connector.name} account</a>}
      {connection && savedVerification && <button type="button" className="ic-module-test" disabled={busy || readOnly} onClick={async () => {
        setBusy(true); setError(""); setStatus("");
        try { await verify(connection); } catch (e) { setError(message(e)); } finally { setBusy(false); }
      }}>{telegram ? "Verify saved bot" : verifyAction?.name || "Check connection"}</button>}
      {verifyAction && !newVerification && !savedVerification && <p>Use “{verifyAction.name}” in Parameters and provide its required fields to test this module.</p>}
      {Object.keys(fields).length > 0 && <p className="as-config-note">Credentials are encrypted in the connection vault. Only the connection reference is saved in your workflow.</p>}
      {status && <p role="status" className="ic-module-success">{status}</p>}
      {error && <p role="alert" className="ic-error">{error}</p>}
    </section>
  );
}
