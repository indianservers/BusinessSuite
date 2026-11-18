import { useMemo, useState } from "react";
import { Search } from "lucide-react";
export type VariableOption = {
  expression: string;
  label: string;
  type: string;
};
export function variableCompatible(type: string, expected: string) {
  return (
    [
      "dynamic",
      "expression",
      "text",
      "string",
      "record",
      "user",
      "template",
    ].includes(expected) ||
    type === "dynamic" ||
    type === "any" ||
    type === expected
  );
}
/** Safe property references only. Callers supply authorized, non-secret metadata. */
export function VariablePicker({
  options,
  expectedType = "dynamic",
  onInsert,
  onClose,
}: {
  options: VariableOption[];
  expectedType?: string;
  onInsert: (expression: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const matches = useMemo(
    () =>
      options.filter((v) =>
        `${v.label} ${v.expression} ${v.type}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [options, query],
  );
  return (
    <div
      className="as-variable-picker"
      role="dialog"
      aria-label="Variable picker"
    >
      <label>
        <Search size={13} />
        <input
          autoFocus
          aria-label="Search variables"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search upstream, workflow, environment..."
        />
      </label>
      <div>
        {matches.map((v) => (
          <button
            key={v.expression}
            disabled={!variableCompatible(v.type, expectedType)}
            title={
              variableCompatible(v.type, expectedType)
                ? v.expression
                : `Expected ${expectedType}, received ${v.type}`
            }
            onClick={() => onInsert(v.expression)}
          >
            <strong>
              {v.label}
              <small className="as-type-badge">{v.type}</small>
            </strong>
            <code>{v.expression}</code>
          </button>
        ))}
        {!matches.length && <p>No matching available variables.</p>}
      </div>
      <p className="as-config-note">
        Only safe references. Environment exposes its authorized name; secrets
        are never suggested.
      </p>
      <button onClick={onClose}>Close variables</button>
    </div>
  );
}
