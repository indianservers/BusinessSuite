import { useEffect, useState } from "react";
import { fieldLabels, providerFields, type Action } from "./integrationApi";
export default function ActionFields({
  connector,
  action,
  value,
  onChange,
  disabled = false,
}: {
  connector: string;
  action: Action;
  value: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  return (
    <>
      {Object.entries(action.input_schema.properties || {})
        .filter(
          ([key]) =>
            !providerFields[connector] ||
            providerFields[connector].includes(key),
        )
        .map(([key, schema]) => {
          const label = fieldLabels[key] || key.replace(/_/g, " ");
          const raw = value[key] ?? schema.default ?? "";
          const edit = (v: unknown) => onChange({ ...value, [key]: v });
          return (
            <label className="ic-field" key={action.id + key}>
              {label}
              {action.input_schema.required?.includes(key) ? " *" : ""}
              {schema.type === "object" || schema.type === "array" ? (
                <JsonField
                  value={raw}
                  disabled={disabled}
                  label={label}
                  onChange={edit}
                />
              ) : schema.enum ? (
                <select
                  disabled={disabled}
                  value={String(raw)}
                  onChange={(e) => edit(e.target.value)}
                >
                  {schema.enum.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              ) : (
                <textarea
                  rows={key === "prompt" || key === "text" ? 4 : 1}
                  disabled={disabled}
                  aria-label={label}
                  value={String(raw)}
                  placeholder={
                    key === "model"
                      ? "Choose a model supported by your provider"
                      : "Value or {{trigger.input.field}}"
                  }
                  onChange={(e) =>
                    edit(
                      schema.type === "number" || schema.type === "integer"
                        ? Number(e.target.value)
                        : e.target.value,
                    )
                  }
                />
              )}
            </label>
          );
        })}
    </>
  );
}
function JsonField({
  value,
  onChange,
  disabled,
  label,
}: {
  value: unknown;
  onChange: (v: unknown) => void;
  disabled: boolean;
  label: string;
}) {
  const [text, setText] = useState(JSON.stringify(value || {}, null, 2));
  const [error, setError] = useState("");
  useEffect(
    () =>
      setText(
        typeof value === "string"
          ? value
          : JSON.stringify(value || {}, null, 2),
      ),
    [value],
  );
  return (
    <>
      <textarea
        rows={5}
        aria-label={label}
        disabled={disabled}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value));
            setError("");
          } catch {
            onChange(e.target.value);
            setError(
              e.target.value.trim().startsWith("{{") &&
                e.target.value.trim().endsWith("}}")
                ? ""
                : "Enter valid JSON before saving this field.",
            );
          }
        }}
      />
      {error && <small role="alert">{error}</small>}
    </>
  );
}
