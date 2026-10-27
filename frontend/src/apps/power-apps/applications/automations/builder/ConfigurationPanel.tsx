import { useEffect, useMemo, useRef, useState } from "react";
import {
  Braces,
  ChevronDown,
  Copy,
  KeyRound,
  ShieldCheck,
  Trash2,
  Variable,
  X,
} from "lucide-react";
import { NodeIcon } from "./NodeIcon";
import { VariablePicker } from "./VariablePicker";
import { ReferenceSelector } from "./ReferenceSelector";
import { upstreamVariables } from "./graph";
import {
  categoryColors,
  type ConfigField,
  type ConfigurationPanelProps,
} from "./types";
export default function ConfigurationPanel({
  recommendations,
  logicEditor,
  onOpenWorkflow,
  referenceProviders,
  node,
  definition,
  graph,
  catalog,
  issues,
  readOnly,
  onChange,
  onClose,
  onDelete,
  onDuplicate,
}: ConfigurationPanelProps) {
  const [variableField, setVariableField] = useState<string | null>(null);
  const [tab, setTab] = useState("Parameters");
  const variables = useMemo(
    () => upstreamVariables(graph, node.id, catalog),
    [graph.nodes, graph.edges, node.id, catalog],
  );
  const fields = useRef<
    Record<string, HTMLInputElement | HTMLTextAreaElement | null>
  >({});
  const update = (key: string, value: unknown) =>
    onChange({ ...node, config: { ...node.config, [key]: value } });
  const insert = (key: string, expression: string) => {
    const field = fields.current[key];
    const current = String(node.config[key] ?? "");
    let start = field?.selectionStart ?? current.length;
    const end = field?.selectionEnd ?? start;
    const opening = current.lastIndexOf("{{", start);
    if (opening >= 0 && !current.slice(opening, start).includes("}}"))
      start = opening;
    update(key, current.slice(0, start) + expression + current.slice(end));
    setVariableField(null);
    window.requestAnimationFrame(() => {
      fields.current[key]?.focus();
      fields.current[key]?.setSelectionRange(
        start + expression.length,
        start + expression.length,
      );
    });
  };
  const renderField = (field: ConfigField) => {
    const id = `config-${node.id}-${field.key}`,
      value = node.config[field.key],
      fieldErrors = issues.filter(
        (i) => i.field === field.key && i.severity === "error",
      );
    const shared = {
      id,
      "aria-label": field.label,
      disabled: readOnly,
      "aria-invalid": fieldErrors.length > 0,
      "aria-describedby": fieldErrors.length ? id + "-error" : undefined,
    };
    const isDynamic = typeof value === "string" && value.includes("{{");
    let control: React.ReactNode;
    if (field.kind === "boolean")
      control = (
        <label className="as-toggle">
          <input
            {...shared}
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => update(field.key, e.target.checked)}
          />
          <span>{value ? "Enabled" : "Disabled"}</span>
        </label>
      );
    else if (field.kind === "select")
      control = (
        <select
          {...shared}
          value={String(value ?? "")}
          onChange={(e) => update(field.key, e.target.value)}
        >
          <option value="">Choose an option</option>
          {field.options?.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      );
    else if (field.kind === "multi-select")
      control = (
        <select
          {...shared}
          multiple
          value={Array.isArray(value) ? value.map(String) : []}
          onChange={(e) =>
            update(
              field.key,
              Array.from(e.target.selectedOptions, (item) => item.value),
            )
          }
        >
          {field.options?.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      );
    else if (field.kind === "json")
      control = (
        <JsonField
          {...shared}
          value={value}
          onChange={(v) => update(field.key, v)}
        />
      );
    else if (["record", "user", "template", "credential"].includes(field.kind))
      control = (
        <ReferenceSelector
          {...shared}
          kind={field.kind}
          ref={(el) => {
            fields.current[field.key] = el;
          }}
          value={String(value ?? "")}
          onChange={(v) => update(field.key, v)}
          provider={
            referenceProviders?.[`${node.type}.${field.key}`] ||
            referenceProviders?.[field.kind]
          }
        />
      );
    else if (field.kind === "number" && !isDynamic)
      control = (
        <input
          {...shared}
          type="number"
          min={field.minimum}
          max={field.maximum}
          step="any"
          value={typeof value === "number" ? value : ""}
          onChange={(e) =>
            update(
              field.key,
              e.target.value === "" ? "" : e.target.valueAsNumber,
            )
          }
        />
      );
    else
      control = (
        <input
          {...shared}
          ref={(el) => {
            fields.current[field.key] = el;
          }}
          type={
            field.kind === "date"
              ? "date"
              : field.kind === "datetime"
                ? "datetime-local"
                : "text"
          }
          value={String(value ?? "")}
          maxLength={32768}
          placeholder={
            field.kind === "user"
              ? "User reference (no directory access)"
              : field.kind === "record"
                ? "Record ID or a dynamic variable"
                : field.kind === "template"
                  ? "Template reference"
                  : field.kind === "expression"
                    ? "{{trigger.record.id}}"
                    : "Enter a value"
          }
          onChange={(e) => {
            update(field.key, e.target.value);
            if (
              field.allow_expression &&
              e.target.value
                .slice(0, e.target.selectionStart ?? e.target.value.length)
                .endsWith("{{")
            )
              setVariableField(field.key);
          }}
        />
      );
    return (
      <div className="as-config-field" key={field.key}>
        <div>
          <label htmlFor={id}>
            {field.label}
            {field.required && <span aria-label="required"> *</span>}
          </label>
          <small className={isDynamic ? "dynamic" : ""}>
            {isDynamic
              ? "Dynamic"
              : field.kind === "expression"
                ? "Safe expression"
                : "Static value"}
          </small>
        </div>
        {control}
        {field.allow_expression && !readOnly && (
          <button
            className="as-insert-variable"
            onClick={() => {
              setVariableField(variableField === field.key ? null : field.key);
            }}
          >
            <Variable size={12} />
            Insert variable
          </button>
        )}
        {variableField === field.key && (
          <VariablePicker
            options={variables}
            expectedType={field.kind}
            onInsert={(expression) => insert(field.key, expression)}
            onClose={() => setVariableField(null)}
          />
        )}
        {fieldErrors.map((error, index) => (
          <p className="as-field-error" id={id + "-error"} key={index}>
            {error.message}
          </p>
        ))}
      </div>
    );
  };
  return (
    <aside className="as-config" aria-label="Node configuration">
      <header>
        <span
          className="as-config-icon"
          style={{
            color: categoryColors[definition.category],
            background: `${categoryColors[definition.category]}15`,
          }}
        >
          <NodeIcon name={definition.icon} size={22} />
        </span>
        <div>
          <small>{definition.category}</small>
          <h2>{definition.name}</h2>
        </div>
        <button aria-label="Close configuration" onClick={onClose}>
          <X size={18} />
        </button>
      </header>
      <div
        role="tablist"
        aria-label="Node editor tabs"
        className="as-config-tabs"
      >
        {["Parameters", "Input / Output", "Settings", "Documentation"].map(
          (name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ),
        )}
      </div>
      <div className="as-config-scroll">
        <p className="as-runtime-label">Not Executable Yet</p>
        {readOnly && <p className="as-readonly-note">Read-only inspection</p>}
        <section hidden={tab !== "Parameters"}>
          <label className="as-basic-field">
            Node name
            <input
              autoFocus={!readOnly}
              readOnly={readOnly}
              maxLength={180}
              value={node.label}
              onChange={(e) => onChange({ ...node, label: e.target.value })}
            />
          </label>
          <label className="as-basic-field">
            Node description
            <textarea
              aria-label="Node description"
              readOnly={readOnly}
              rows={2}
              maxLength={2000}
              value={node.description}
              onChange={(e) =>
                onChange({ ...node, description: e.target.value })
              }
            />
          </label>
          {definition.id === "sub_workflow" && onOpenWorkflow && (
            <button
              disabled={!/^\d+$/.test(String(node.config.workflow_id || ""))}
              onClick={() => onOpenWorkflow(String(node.config.workflow_id))}
            >
              Open referenced workflow
            </button>
          )}
          {logicEditor}
          <h3>INPUT PARAMETERS</h3>
          {definition.fields.length ? (
            definition.fields
              .filter(
                (field) =>
                  !(
                    node.config.condition &&
                    ["left", "right", "operator"].includes(field.key)
                  ),
              )
              .filter(
                (field) =>
                  !["condition", "routes", "exit_condition"].includes(
                    field.key,
                  ),
              )
              .filter(
                (field) =>
                  !field.visible_when ||
                  node.config[field.visible_when.field] ===
                    field.visible_when.equals,
              )
              .map(renderField)
          ) : (
            <p className="as-config-note">This node has no input parameters.</p>
          )}
          <details open={definition.requires_credential}>
            <summary>
              <KeyRound size={14} />
              Credentials / connections
              <ChevronDown size={13} />
            </summary>
            <label className="as-basic-field">
              Credential reference
              <input
                readOnly={readOnly}
                value={node.credential_reference || ""}
                maxLength={120}
                pattern="[a-zA-Z0-9_-]+"
                placeholder="Connection reference only"
                onChange={(e) =>
                  onChange({
                    ...node,
                    credential_reference: e.target.value || null,
                  })
                }
              />
            </label>
            <p className="as-config-note">
              References only. No credential secrets are loaded. Connection
              authorization will be verified by the Phase 3 worker.
            </p>
          </details>
          {recommendations}
        </section>
        <section hidden={tab !== "Input / Output"}>
          <h3>DECLARED INPUT PORTS</h3>
          <dl className="as-output-schema">
            {definition.inputs.map((port) => (
              <div key={port.id}>
                <dt>{port.label}</dt>
                <dd>{port.data_type}</dd>
              </div>
            ))}
          </dl>
          <details open>
            <summary>
              <Braces size={14} />
              Output schema
              <ChevronDown size={13} />
            </summary>
            <dl className="as-output-schema">
              {Object.entries(definition.output_schema).map(([key, type]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{type}</dd>
                </div>
              ))}
            </dl>
            <code className="as-output-ref">{`{{steps.${node.id}.output}}`}</code>
          </details>
        </section>
        <section hidden={tab !== "Settings"}>
          <label className="as-toggle">
            <input
              aria-label="Disable node"
              type="checkbox"
              disabled={readOnly}
              checked={Boolean(node.disabled)}
              onChange={(e) =>
                onChange({ ...node, disabled: e.target.checked })
              }
            />
            Disable this node (blocks preview path)
          </label>
          <details open>
            <summary>
              Advanced / error handling
              <ChevronDown size={13} />
            </summary>
            <label className="as-basic-field">
              Retry attempts
              <input
                readOnly={readOnly}
                type="number"
                min={1}
                max={10}
                value={node.advanced.retry_attempts}
                onChange={(e) =>
                  onChange({
                    ...node,
                    advanced: {
                      ...node.advanced,
                      retry_attempts: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
            <label className="as-basic-field">
              Timeout (seconds)
              <input
                readOnly={readOnly}
                type="number"
                min={1}
                max={86400}
                value={node.advanced.timeout_seconds}
                onChange={(e) =>
                  onChange({
                    ...node,
                    advanced: {
                      ...node.advanced,
                      timeout_seconds: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
            <label className="as-basic-field">
              On error
              <select
                disabled={readOnly}
                value={node.advanced.error_strategy}
                onChange={(e) =>
                  onChange({
                    ...node,
                    advanced: {
                      ...node.advanced,
                      error_strategy: e.target.value as
                        | "stop"
                        | "continue"
                        | "branch",
                    },
                  })
                }
              >
                <option value="stop">Stop this path</option>
                <option value="continue">Continue</option>
                <option value="branch">Use error branch</option>
              </select>
            </label>
          </details>
        </section>
        <details open={issues.some((i) => i.severity === "error")}>
          <summary>
            <ShieldCheck size={14} />
            Validation status
            <ChevronDown size={13} />
          </summary>
          {issues
            .filter((i) => i.severity === "error")
            .map((issue, i) => (
              <p className="as-field-error" key={i}>
                {issue.message}
              </p>
            ))}
          {!issues.some((i) => i.severity === "error") && (
            <p className="as-config-note">
              Configuration is structurally complete. Check the runtime page for
              publication readiness.
            </p>
          )}
        </details>
        <section hidden={tab !== "Documentation"}>
          <details open>
            <summary>
              Documentation / help
              <ChevronDown size={13} />
            </summary>
            <p className="as-config-note">{definition.help}</p>
            <p className="as-config-note">
              Expressions are property references, never executable JavaScript.
              Loop nodes are bounded; graph cycles are not allowed.
            </p>
          </details>
        </section>
      </div>
      <footer>
        <button disabled={readOnly} onClick={onDuplicate}>
          <Copy size={14} />
          Duplicate
        </button>
        <button disabled={readOnly} className="as-danger" onClick={onDelete}>
          <Trash2 size={14} />
          Delete node
        </button>
      </footer>
    </aside>
  );
}
function JsonField({
  id,
  disabled,
  value,
  onChange,
  ...rest
}: {
  id: string;
  disabled?: boolean;
  value: unknown;
  onChange: (value: unknown) => void;
  "aria-invalid"?: boolean;
}) {
  const [text, setText] = useState(JSON.stringify(value ?? {}, null, 2));
  const [invalid, setInvalid] = useState(false);
  const emitted = useRef(JSON.stringify(value));
  useEffect(() => {
    const next = JSON.stringify(value);
    if (next !== emitted.current) {
      emitted.current = next;
      setText(JSON.stringify(value ?? {}, null, 2));
      setInvalid(false);
    }
  }, [value]);
  return (
    <>
      <textarea
        {...rest}
        id={id}
        disabled={disabled}
        className="as-json-field"
        rows={6}
        spellCheck={false}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = JSON.parse(e.target.value);
            setInvalid(!parsed || typeof parsed !== "object");
            if (parsed && typeof parsed === "object") {
              emitted.current = JSON.stringify(parsed);
              onChange(parsed);
            }
          } catch {
            setInvalid(true);
          }
        }}
      />
      {invalid && (
        <p className="as-field-error" role="alert">
          Enter a valid JSON object or array. Invalid text has not replaced the
          saved value.
        </p>
      )}
    </>
  );
}
