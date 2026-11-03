import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import { fieldLabels, type Action } from "./integrationApi";
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
          ([, schema]) => schema.const === undefined,
        )
        .map(([key, property]) => {
          const schema = property.anyOf?.find((option) => option.type && option.type !== "null") || property;
          const label = fieldLabels[key] || schema.title || key.replace(/_/g, " ");
          const raw = value[key] ?? schema.default ?? (schema.type === "array" ? [] : schema.type === "object" || !schema.type ? {} : "");
          const edit = (v: unknown) => onChange({ ...value, [key]: v });
          return (
            <label className="ic-field" key={connector + action.id + key}>
              {label}
              {action.input_schema.required?.includes(key) ? " *" : ""}
              {schema.type === "object" || schema.type === "array" || (!schema.type && !schema.enum) ? (
                <JsonField
                  value={raw}
                  disabled={disabled}
                  label={label}
                  array={schema.type === "array"}
                  onChange={edit}
                />
              ) : schema.type === "boolean" ? (
                <input type="checkbox" aria-label={label} disabled={disabled} checked={raw === true} onChange={(e) => edit(e.target.checked)} />
              ) : schema.enum ? (
                <NativeSelect
                  disabled={disabled}
                  aria-label={label}
                  value={String(raw)}
                  onChange={(e) => edit(e.target.value)}
                >
                  {schema.enum.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </NativeSelect>
              ) : (
                <textarea
                  rows={key === "prompt" || key === "text" ? 4 : 1}
                  disabled={disabled}
                  aria-label={label}
                  maxLength={schema.maxLength}
                  value={String(raw)}
                  placeholder={
                    key === "model"
                      ? "Choose a model supported by your provider"
                      : "Value or {{trigger.input.field}}"
                  }
                  onChange={(e) =>
                    edit(
                      (schema.type === "number" || schema.type === "integer") && e.target.value.trim() && !e.target.value.includes("{{")
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
  array = false,
}: {
  value: unknown;
  onChange: (v: unknown) => void;
  disabled: boolean;
  label: string;
  array?: boolean;
}) {
  const empty = array ? [] : {};
  const [text, setText] = useState(typeof value === "string" ? value : JSON.stringify(value ?? empty, null, 2));
  const [error, setError] = useState("");
  useEffect(
    () =>
      setText(
        typeof value === "string"
          ? value
          : JSON.stringify(value ?? (array ? [] : {}), null, 2),
      ),
    [value, array],
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
