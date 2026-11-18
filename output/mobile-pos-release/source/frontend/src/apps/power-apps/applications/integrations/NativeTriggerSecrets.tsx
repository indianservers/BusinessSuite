import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { message } from "./integrationApi";

export default function NativeTriggerSecrets({
  workflowId,
  environment,
  value,
  onChange,
  disabled,
}: {
  workflowId: number;
  environment: string;
  value: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
  disabled: boolean;
}) {
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api
      .get<{ provider_secret_fields: Record<string, string> }>(
        `/power-apps/automations/${workflowId}/triggers/connector/options`,
        { params: { environment } },
      )
      .then(({ data }) => {
        if (live) {
          setFields(data.provider_secret_fields);
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(message(e));
      });
    return () => {
      live = false;
    };
  }, [workflowId, environment]);
  return (
    <>
      {error && <p role="alert">{error}</p>}
      {Object.entries(fields).map(([key, label]) => (
        <label key={key} className="ic-field">
          {label}
          {key === "cloud_service_account" ? (
            <textarea
              aria-label={label}
              autoComplete="off"
              spellCheck={false}
              rows={5}
              disabled={disabled}
              value={value[key] || ""}
              onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            />
          ) : (
            <input
              type="password"
              aria-label={label}
              autoComplete="new-password"
              disabled={disabled}
              value={value[key] || ""}
              onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            />
          )}
        </label>
      ))}
      {Object.keys(fields).length > 0 && (
        <p>
          Provide these credentials on the first setup. Leave blank to reuse the
          encrypted saved credentials. Values are never saved in workflow
          definitions.
        </p>
      )}
    </>
  );
}
