import { useState, useEffect } from "react";
import type { WorkflowNode, NodeDefinition } from "./types";
import { parseValue } from "./intelligenceTypes";
export type ConditionRule = { left: unknown; operator: string; right: unknown };
export type ConditionGroup = {
  join: "and" | "or";
  rules: (ConditionRule | ConditionGroup)[];
};
const operators = [
  "equals",
  "not_equals",
  "greater_than",
  "less_than",
  "greater_or_equal",
  "less_or_equal",
  "contains",
  "starts_with",
  "ends_with",
  "is_empty",
  "is_not_empty",
  "in_list",
  "not_in_list",
  "date_before",
  "date_after",
  "boolean_equals",
];
const freshRule = (): ConditionRule => ({
  left: "{{trigger.record.amount}}",
  operator: "greater_than",
  right: 50000,
});
export function ConditionBuilder({
  value,
  onChange,
  readOnly = false,
  depth = 0,
  fieldOptions,
}: {
  value: ConditionGroup;
  onChange: (value: ConditionGroup) => void;
  readOnly?: boolean;
  depth?: number;
  fieldOptions?: { label: string; value: string }[];
}) {
  return (
    <fieldset className="ai-condition" disabled={readOnly}>
      <legend>Condition group</legend>
      <label>
        Match
        <select
          aria-label={`Condition join level ${depth}`}
          value={value.join}
          onChange={(e) =>
            onChange({ ...value, join: e.target.value as "and" | "or" })
          }
        >
          <option value="and">All rules (AND)</option>
          <option value="or">Any rule (OR)</option>
        </select>
      </label>
      {value.rules.map((rule, i) => (
        <div key={i}>
          {"rules" in rule ? (
            <ConditionBuilder
              value={rule}
              readOnly={readOnly}
              depth={depth + 1}
              fieldOptions={fieldOptions}
              onChange={(next) =>
                onChange({
                  ...value,
                  rules: value.rules.map((r, index) =>
                    index === i ? next : r,
                  ),
                })
              }
            />
          ) : (
            <div className="ai-rule">
              {fieldOptions ? (
                <select
                  aria-label={`Rule ${i + 1} field`}
                  value={String(rule.left)}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      rules: value.rules.map((r, index) =>
                        index === i ? { ...rule, left: e.target.value } : r,
                      ),
                    })
                  }
                >
                  {!fieldOptions.some((f) => f.value === rule.left) && (
                    <option value={String(rule.left)}>
                      Select an available field
                    </option>
                  )}
                  {fieldOptions.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label={`Rule ${i + 1} left`}
                  value={
                    typeof rule.left === "string"
                      ? rule.left
                      : JSON.stringify(rule.left)
                  }
                  onChange={(e) =>
                    onChange({
                      ...value,
                      rules: value.rules.map((r, index) =>
                        index === i
                          ? { ...rule, left: parseValue(e.target.value) }
                          : r,
                      ),
                    })
                  }
                />
              )}
              <select
                aria-label={`Rule ${i + 1} operator`}
                value={rule.operator}
                onChange={(e) =>
                  onChange({
                    ...value,
                    rules: value.rules.map((r, index) =>
                      index === i ? { ...rule, operator: e.target.value } : r,
                    ),
                  })
                }
              >
                {operators.map((op) => (
                  <option key={op} value={op}>
                    {op.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <input
                aria-label={`Rule ${i + 1} right`}
                value={
                  typeof rule.right === "string"
                    ? rule.right
                    : JSON.stringify(rule.right)
                }
                onChange={(e) =>
                  onChange({
                    ...value,
                    rules: value.rules.map((r, index) =>
                      index === i
                        ? { ...rule, right: parseValue(e.target.value) }
                        : r,
                    ),
                  })
                }
              />
            </div>
          )}
          <button
            onClick={() =>
              onChange({
                ...value,
                rules: value.rules.filter((_, index) => index !== i),
              })
            }
          >
            Remove rule {i + 1}
          </button>
        </div>
      ))}
      <button
        disabled={value.rules.length >= 30}
        onClick={() =>
          onChange({
            ...value,
            rules: [
              ...value.rules,
              fieldOptions?.length
                ? {
                    left: fieldOptions[0].value,
                    operator: "is_not_empty",
                    right: "",
                  }
                : freshRule(),
            ],
          })
        }
      >
        Add rule
      </button>
      <button
        disabled={depth >= 7 || value.rules.length >= 30}
        onClick={() =>
          onChange({
            ...value,
            rules: [
              ...value.rules,
              {
                join: "or",
                rules: [
                  fieldOptions?.length
                    ? {
                        left: fieldOptions[0].value,
                        operator: "is_not_empty",
                        right: "",
                      }
                    : freshRule(),
                ],
              },
            ],
          })
        }
      >
        Add nested group
      </button>
      <p>
        Enter numbers, true/false, JSON arrays, or safe property references. No
        implicit type conversion.
      </p>
    </fieldset>
  );
}
export type LogicProps = {
  node: WorkflowNode;
  onChange: (node: WorkflowNode) => void;
  readOnly: boolean;
  usedPorts?: string[];
};
export function SwitchRouterEditor({
  node,
  onChange,
  readOnly,
  usedPorts = [],
}: LogicProps) {
  const routes = (node.config.routes || []) as {
    id: string;
    label: string;
    value: unknown;
  }[];
  return (
    <fieldset disabled={readOnly}>
      <legend>Named router branches</legend>
      <label>
        Routing value
        <input
          aria-label="Routing value"
          value={String(node.config.value || "")}
          onChange={(e) =>
            onChange({
              ...node,
              config: { ...node.config, value: e.target.value },
            })
          }
        />
      </label>
      {routes.map((route, i) => (
        <div className="ai-rule" key={route.id}>
          <input
            aria-label={`Branch ${i + 1} label`}
            value={route.label}
            onChange={(e) =>
              onChange({
                ...node,
                config: {
                  ...node.config,
                  routes: routes.map((r) =>
                    r.id === route.id ? { ...r, label: e.target.value } : r,
                  ),
                },
              })
            }
          />
          <input
            aria-label={`Branch ${i + 1} match`}
            value={
              typeof route.value === "string"
                ? route.value
                : JSON.stringify(route.value)
            }
            onChange={(e) =>
              onChange({
                ...node,
                config: {
                  ...node.config,
                  routes: routes.map((r) =>
                    r.id === route.id
                      ? { ...r, value: parseValue(e.target.value) }
                      : r,
                  ),
                },
              })
            }
          />
          <button
            disabled={usedPorts.includes(route.id)}
            title="Connected branches must be disconnected before removal"
            onClick={() =>
              onChange({
                ...node,
                config: {
                  ...node.config,
                  routes: routes.filter((r) => r.id !== route.id),
                },
              })
            }
          >
            Remove branch
          </button>
        </div>
      ))}
      <button
        disabled={
          routes.length >= 12 ||
          (!routes.length && usedPorts.some((p) => p.startsWith("route_")))
        }
        onClick={() =>
          onChange({
            ...node,
            config: {
              ...node.config,
              routes: [
                ...routes,
                {
                  id: "route_" + crypto.randomUUID().slice(0, 8),
                  label: "New branch",
                  value: "High",
                },
              ],
            },
          })
        }
      >
        Add named branch
      </button>
      <p>
        The default output remains available. Disconnect legacy routes before
        switching to named branches.
      </p>
    </fieldset>
  );
}
export function LoopConfigurationEditor({
  node,
  onChange,
  readOnly,
}: LogicProps) {
  return (
    <fieldset disabled={readOnly}>
      <legend>Bounded iteration design</legend>
      <label>
        Mode
        <select
          aria-label="Loop mode"
          value={String(node.config.mode || "sequential")}
          onChange={(e) =>
            onChange({
              ...node,
              config: { ...node.config, mode: e.target.value },
            })
          }
        >
          <option value="sequential">Sequential</option>
          <option value="bounded_parallel">Bounded parallel</option>
        </select>
      </label>
      {["max_iterations", "concurrency"].map((key) => (
        <label key={key}>
          {key.replace(/_/g, " ")}
          <input
            aria-label={key}
            type="number"
            min={1}
            max={key === "concurrency" ? 10 : 1000}
            value={Number(node.config[key] || 1)}
            onChange={(e) =>
              onChange({
                ...node,
                config: { ...node.config, [key]: Number(e.target.value) },
              })
            }
          />
        </label>
      ))}
      <label>
        Timeout seconds
        <input
          aria-label="Loop timeout"
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
      <ConditionBuilder
        value={
          (node.config.exit_condition || {
            join: "and",
            rules: [],
          }) as ConditionGroup
        }
        onChange={(exit_condition) =>
          onChange({ ...node, config: { ...node.config, exit_condition } })
        }
      />
      <p>
        Loop configuration only. Iteration/concurrency require Phase 3; implicit
        graph cycles remain forbidden.
      </p>
    </fieldset>
  );
}
export function MergeConfigurationEditor({
  node,
  onChange,
  readOnly,
}: LogicProps) {
  const [rawKeys, setRawKeys] = useState(
      JSON.stringify(node.config.keys || []),
    ),
    [keyError, setKeyError] = useState("");
  useEffect(() => {
    setRawKeys(JSON.stringify(node.config.keys || []));
    setKeyError("");
  }, [node.id, node.config.keys]);
  return (
    <fieldset disabled={readOnly}>
      <legend>Join semantics</legend>
      <label>
        Merge strategy
        <select
          aria-label="Merge strategy"
          value={String(node.config.strategy || "all")}
          onChange={(e) =>
            onChange({
              ...node,
              config: { ...node.config, strategy: e.target.value },
            })
          }
        >
          {["all", "first", "first_successful", "first_completed", "keyed"].map(
            (value) => (
              <option key={value} value={value}>
                {
                  (
                    {
                      all: "Wait for all branches",
                      first: "First available in deterministic order",
                      first_successful: "First successful branch",
                      first_completed: "First completed branch",
                      keyed: "Combine keyed outputs",
                    } as Record<string, string>
                  )[value]
                }
              </option>
            ),
          )}
        </select>
      </label>
      <label>
        Keys, in incoming connection order
        <input
          aria-label="Merge keys"
          value={rawKeys}
          aria-invalid={Boolean(keyError)}
          onChange={(e) => {
            setRawKeys(e.target.value);
            try {
              const keys = JSON.parse(e.target.value);
              if (
                !Array.isArray(keys) ||
                keys.some((key) => typeof key !== "string") ||
                new Set(keys).size !== keys.length
              )
                throw new Error("Use a JSON array of unique string keys");
              onChange({ ...node, config: { ...node.config, keys } });
              setKeyError("");
            } catch (error) {
              setKeyError((error as Error).message);
            }
          }}
        />
      </label>
      {keyError && <p role="alert">{keyError}</p>}
      <p>
        Concurrent completion order is not simulated. Keyed joins require one
        unique key per incoming branch.
      </p>
    </fieldset>
  );
}
export function LogicEditor({
  node,
  catalog,
  onChange,
  readOnly,
  usedPorts,
}: LogicProps & { catalog: NodeDefinition[] }) {
  if (["if_else", "filter", "compare_values"].includes(node.type))
    return (
      <ConditionBuilder
        readOnly={readOnly}
        value={
          (node.config.condition || {
            join: "and",
            rules: [],
          }) as ConditionGroup
        }
        onChange={(condition) =>
          onChange({ ...node, config: { ...node.config, condition } })
        }
      />
    );
  if (node.type === "switch")
    return <SwitchRouterEditor {...{ node, onChange, readOnly, usedPorts }} />;
  if (["loop", "for_each"].includes(node.type))
    return <LoopConfigurationEditor {...{ node, onChange, readOnly }} />;
  if (node.type === "merge")
    return <MergeConfigurationEditor {...{ node, onChange, readOnly }} />;
  return (
    <p>
      Select a condition, router, loop or merge node. {catalog.length}{" "}
      registered types available.
    </p>
  );
}
