import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ReactFlowProvider,
  Background,
  Controls,
  applyNodeChanges,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AutomationCanvas } from "../automations/builder/WorkflowPrimitives";
import { StudioNode, type CanvasNode } from "../automations/builder/StudioNode";
import "../automations/builder/studio.css";
import { studioApi } from "../automations/studioApi";
import type {
  NodeDefinition,
  WorkflowNode,
} from "../automations/builder/types";
import {
  ConditionBuilder,
  type ConditionGroup,
} from "../automations/builder/LogicEditors";
import { ApproverPicker } from "./ApprovalComponents";
import {
  approvalApi as api,
  errorMessage,
  type Policy,
  type Person,
  type Process,
  type Stage,
} from "./api";
export const starter = (): Process => ({
  stages: [
    {
      id: "review",
      name: "Independent review",
      mode: "all",
      selectors: [{ kind: "user", ids: [] }],
      quorum: 1,
      sla_seconds: 172800,
      remind_after_seconds: 86400,
      expire_after_seconds: 604800,
      require_reason: true,
      allow_delegation: false,
    },
  ],
  fields: [{ key: "details", label: "Details", kind: "text", required: true }],
  prohibit_self_approval: true,
  documents_required: false,
});
export function ApprovalPolicyEditor({
  stage,
  people,
  fields,
  onChange,
}: {
  stage: Stage;
  people: Person[];
  fields: Process["fields"];
  onChange: (s: Stage) => void;
}) {
  return (
    <>
      <label>
        Stage name
        <input
          value={stage.name}
          onChange={(e) => onChange({ ...stage, name: e.target.value })}
        />
      </label>
      <label>
        Voting rule
        <select
          value={stage.mode}
          onChange={(e) =>
            onChange({ ...stage, mode: e.target.value as Stage["mode"] })
          }
        >
          <option value="all">All must approve</option>
          <option value="any">Any one may approve</option>
          <option value="majority">Strict majority</option>
          <option value="quorum">Quorum</option>
        </select>
      </label>
      {stage.mode === "quorum" && (
        <label>
          Required approvals
          <input
            type="number"
            min={1}
            max={30}
            value={stage.quorum || 1}
            onChange={(e) =>
              onChange({ ...stage, quorum: Number(e.target.value) })
            }
          />
        </label>
      )}
      <label>
        Approver source
        <select
          value={stage.selectors[0].kind}
          onChange={(e) =>
            onChange({
              ...stage,
              selectors: [{ kind: e.target.value, ids: [] }],
            })
          }
        >
          {[
            "user",
            "group",
            "role",
            "reporting_manager",
            "department_manager",
            "department_head",
            "organization_owner",
            "record_user",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      {["user", "group", "record_user", "organization_owner"].includes(
        stage.selectors[0].kind,
      ) ? (
        <ApproverPicker
          people={people}
          value={stage.selectors[0].ids}
          onChange={(ids) =>
            onChange({ ...stage, selectors: [{ ...stage.selectors[0], ids }] })
          }
        />
      ) : stage.selectors[0].kind === "role" ? (
        <label>
          Authorized role IDs
          <input
            value={stage.selectors[0].ids.join(",")}
            onChange={(e) =>
              onChange({
                ...stage,
                selectors: [
                  {
                    kind: "role",
                    ids: e.target.value
                      .split(",")
                      .map(Number)
                      .filter((n) => n > 0),
                  },
                ],
              })
            }
          />
        </label>
      ) : (
        <p className="ap-muted">
          Uses existing company reporting relationships. Missing or unauthorized
          approvers require administrative resolution.
        </p>
      )}
      {stage.selectors[0].kind === "record_user" && (
        <label>
          Authorized form field
          <input
            value={stage.selectors[0].field || ""}
            onChange={(e) =>
              onChange({
                ...stage,
                selectors: [{ ...stage.selectors[0], field: e.target.value }],
              })
            }
          />
        </label>
      )}
      <label>
        SLA (hours)
        <input
          type="number"
          min={1}
          max={168}
          value={(stage.sla_seconds || 172800) / 3600}
          onChange={(e) =>
            onChange({ ...stage, sla_seconds: Number(e.target.value) * 3600 })
          }
        />
      </label>
      <label>
        Reminder after (hours)
        <input
          type="number"
          min={1}
          max={168}
          value={(stage.remind_after_seconds || 86400) / 3600}
          onChange={(e) =>
            onChange({
              ...stage,
              remind_after_seconds: Number(e.target.value) * 3600,
            })
          }
        />
      </label>
      <label className="ap-check">
        <input
          type="checkbox"
          checked={!!stage.allow_delegation}
          onChange={(e) =>
            onChange({ ...stage, allow_delegation: e.target.checked })
          }
        />
        Allow date-bound delegation
      </label>
      <label>
        Expire after (hours)
        <input
          type="number"
          min={1}
          max={168}
          value={(stage.expire_after_seconds || 604800) / 3600}
          onChange={(e) =>
            onChange({
              ...stage,
              expire_after_seconds: Number(e.target.value) * 3600,
            })
          }
        />
      </label>
      <label className="ap-check">
        <input
          type="checkbox"
          checked={stage.require_reason !== false}
          onChange={(e) =>
            onChange({ ...stage, require_reason: e.target.checked })
          }
        />
        Require a reason for rejection or changes
      </label>
      <ApproverPicker
        people={people}
        label="Escalation recipients"
        value={stage.escalation?.ids || []}
        onChange={(ids) =>
          onChange({
            ...stage,
            escalation: ids.length ? { kind: "user", ids } : null,
          })
        }
      />
      <label>
        Escalation action
        <select
          value={stage.escalation_action || "notify"}
          onChange={(e) =>
            onChange({
              ...stage,
              escalation_action: e.target.value as "notify" | "reassign",
            })
          }
        >
          <option value="notify">Notify recipients</option>
          <option value="reassign">
            Reassign pending seats to independent alternates
          </option>
        </select>
      </label>
      <label className="ap-check">
        <input
          type="checkbox"
          checked={!!stage.when}
          disabled={!fields.length}
          onChange={(e) =>
            onChange({
              ...stage,
              when: e.target.checked
                ? {
                    join: "and",
                    rules: [
                      {
                        left: `{{trigger.input.fields.${fields[0].key}}}`,
                        operator: "is_not_empty",
                        right: "",
                      },
                    ],
                  }
                : null,
            })
          }
        />
        Run this stage only when conditions match
      </label>
      {stage.when && (
        <ConditionBuilder
          value={stage.when as ConditionGroup}
          fieldOptions={fields.map((f) => ({
            label: f.label,
            value: `{{trigger.input.fields.${f.key}}}`,
          }))}
          onChange={(when) => onChange({ ...stage, when })}
        />
      )}
      <small>
        Unmatched stages are skipped. Conditions evaluate the submitted request
        fields.
      </small>
    </>
  );
}
const nodeTypes = { studio: StudioNode };
export function ApprovalDesigner({
  environment,
  policies,
  people,
  onSaved,
}: {
  environment: string;
  policies: Policy[];
  people: Person[];
  onSaved: () => void;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const policy = policies.find((p) => p.id === Number(id));
  const [name, setName] = useState("New approval process"),
    [process, setProcess] = useState<Process>(starter),
    [selected, setSelected] = useState(0),
    [error, setError] = useState(""),
    [nodes, setNodes] = useState<CanvasNode[]>([]),
    [definition, setDefinition] = useState<NodeDefinition | null>(null),
    [savedFingerprint, setSavedFingerprint] = useState("");
  useEffect(() => {
    studioApi
      .nodes()
      .then((rows) =>
        setDefinition(rows.find((n) => n.id === "approval_wait") || null),
      )
      .catch((e) => setError(errorMessage(e)));
  }, []);
  useEffect(() => {
    if (policy) {
      setName(policy.name);
      setProcess(policy.definition);
      setNodes([]);
      setSavedFingerprint(
        JSON.stringify({ name: policy.name, process: policy.definition }),
      );
    }
  }, [policy]);
  useEffect(() => {
    if (!definition) return;
    setNodes((old) =>
      process.stages.map((s, i) => {
        const position = old.find((n) => n.id === s.id)?.position ||
          process.layout?.[s.id] || {
            x: 310 * i,
            y: 90,
          };
        const node = {
          id: s.id,
          type: "approval_wait",
          label: s.name,
          position,
          description: "",
          config: { stage: s },
          credential_reference: null,
          mappings: {},
          disabled: false,
          advanced: {
            retry_attempts: 3,
            error_strategy: "stop",
            timeout_seconds: 60,
          },
        } as WorkflowNode;
        return {
          id: s.id,
          type: "studio",
          position,
          selected: i === selected,
          data: {
            node,
            definition,
            errors: 0,
            readOnly: false,
            onMenu: () => setSelected(i),
            onAdd: () => setSelected(i),
          },
        };
      }),
    );
  }, [process, selected, definition]);
  const dirty =
    JSON.stringify({ name, process }) !== savedFingerprint ||
    nodes.some((n) => {
      const saved = process.layout?.[n.id];
      return saved
        ? saved.x !== n.position.x || saved.y !== n.position.y
        : false;
    });
  const save = async () => {
    try {
      const value = {
        name,
        definition: {
          ...process,
          fields: process.fields,
          layout: Object.fromEntries(nodes.map((n) => [n.id, n.position])),
        },
        expected_version: policy?.version,
      };
      const saved = policy
        ? await api.put<Policy>(`/policies/${policy.id}`, environment, value)
        : await api.post<Policy>("/policies", environment, value);
      onSaved();
      navigate(
        `/power-apps/approvals/designer/${saved.id}?environment=${environment}`,
      );
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  return (
    <>
      <div className="ap-actions">
        <input
          className="ap-process-name"
          aria-label="Process name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          onClick={() => {
            setProcess({
              ...process,
              stages: [
                ...process.stages,
                {
                  ...starter().stages[0],
                  id:
                    "stage_" +
                    crypto.randomUUID().replace(/-/g, "").slice(0, 8),
                  name: `Review ${process.stages.length + 1}`,
                },
              ],
            });
            setSelected(process.stages.length);
          }}
        >
          Add approval stage
        </button>
        <button className="ap-primary" onClick={() => void save()}>
          Save version
        </button>
        {policy && (
          <button
            disabled={dirty}
            title={
              dirty
                ? "Save your changes before publishing"
                : "Activate the saved version"
            }
            onClick={async () => {
              try {
                await api.post(
                  `/policies/${policy.id}/activate`,
                  environment,
                  {},
                  { expected_version: policy.version },
                );
                onSaved();
              } catch (e) {
                setError(errorMessage(e));
              }
            }}
          >
            Publish & activate
          </button>
        )}
      </div>
      {error && (
        <p className="ap-error" role="alert">
          {error}
        </p>
      )}
      <div className="ap-designer">
        <div className="ap-canvas">
          <ReactFlowProvider>
            <AutomationCanvas
              nodes={nodes}
              nodeTypes={nodeTypes}
              edges={process.stages.slice(1).map((s, i) => ({
                id: "edge_" + s.id,
                source: process.stages[i].id,
                target: s.id,
              }))}
              onNodesChange={(changes) =>
                setNodes((n) =>
                  applyNodeChanges(changes as NodeChange<CanvasNode>[], n),
                )
              }
              onNodeClick={(_, n) =>
                setSelected(process.stages.findIndex((s) => s.id === n.id))
              }
              fitView
            >
              <Background gap={24} />
              <Controls />
            </AutomationCanvas>
          </ReactFlowProvider>
          <p className="ap-canvas-caption">
            Sequential stages · parallel voting within each stage · drag to
            arrange
          </p>
        </div>
        <aside>
          <ApprovalPolicyEditor
            stage={process.stages[selected] || process.stages[0]}
            people={people}
            fields={process.fields}
            onChange={(stage) =>
              setProcess({
                ...process,
                stages: process.stages.map((s, i) =>
                  i === selected ? stage : s,
                ),
              })
            }
          />
          <div className="ap-actions">
            <button
              disabled={!selected}
              onClick={() => {
                const stages = [...process.stages];
                [stages[selected - 1], stages[selected]] = [
                  stages[selected],
                  stages[selected - 1],
                ];
                setProcess({ ...process, stages });
                setSelected(selected - 1);
              }}
            >
              Move earlier
            </button>
            <button
              disabled={process.stages.length < 2}
              onClick={() => {
                setProcess({
                  ...process,
                  stages: process.stages.filter((_, i) => i !== selected),
                });
                setSelected(0);
              }}
            >
              Remove stage
            </button>
          </div>
        </aside>
      </div>
      <section className="ap-panel ap-form">
        <h3>Business calendar</h3>
        <label className="ap-check">
          <input
            type="checkbox"
            checked={!!process.business_calendar}
            onChange={(e) =>
              setProcess({
                ...process,
                business_calendar: e.target.checked
                  ? {
                      timezone: "UTC",
                      weekdays: [0, 1, 2, 3, 4],
                      opens_at: 9,
                      closes_at: 17,
                      holidays: [],
                    }
                  : null,
              })
            }
          />
          Count SLA time within configured business hours
        </label>
        {process.business_calendar && (
          <>
            <label>
              IANA timezone
              <input
                value={process.business_calendar.timezone}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    business_calendar: {
                      ...process.business_calendar!,
                      timezone: e.target.value,
                    },
                  })
                }
              />
            </label>
            <label>
              Weekdays (0 = Monday, 6 = Sunday)
              <select
                multiple
                value={process.business_calendar.weekdays.map(String)}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    business_calendar: {
                      ...process.business_calendar!,
                      weekdays: Array.from(e.target.selectedOptions).map((o) =>
                        Number(o.value),
                      ),
                    },
                  })
                }
              >
                {[
                  "Monday",
                  "Tuesday",
                  "Wednesday",
                  "Thursday",
                  "Friday",
                  "Saturday",
                  "Sunday",
                ].map((d, i) => (
                  <option value={i} key={i}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Opening hour
              <input
                type="number"
                min={0}
                max={23}
                value={process.business_calendar.opens_at}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    business_calendar: {
                      ...process.business_calendar!,
                      opens_at: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
            <label>
              Closing hour
              <input
                type="number"
                min={1}
                max={24}
                value={process.business_calendar.closes_at}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    business_calendar: {
                      ...process.business_calendar!,
                      closes_at: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
            <label>
              Holiday dates (comma-separated ISO dates)
              <input
                value={process.business_calendar.holidays.join(",")}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    business_calendar: {
                      ...process.business_calendar!,
                      holidays: e.target.value
                        .split(",")
                        .map((d) => d.trim())
                        .filter(Boolean),
                    },
                  })
                }
              />
            </label>
          </>
        )}
        <p className="ap-muted">
          The inherited execution limit is seven calendar days for the entire
          request. Choose stage deadlines within that limit.
        </p>
        <h3>Request form</h3>
        <p className="ap-muted">
          Define the information reviewers need. These fields also appear in
          stage conditions.
        </p>
        {process.fields.map((field, index) => (
          <fieldset key={index} className="ap-field-editor">
            <legend>Field {index + 1}</legend>
            <label>
              Label
              <input
                value={field.label}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    fields: process.fields.map((f, i) =>
                      i === index ? { ...f, label: e.target.value } : f,
                    ),
                  })
                }
              />
            </label>
            <label>
              Field key
              <input
                value={field.key}
                pattern="[A-Za-z][A-Za-z0-9_]*"
                onChange={(e) =>
                  setProcess({
                    ...process,
                    fields: process.fields.map((f, i) =>
                      i === index ? { ...f, key: e.target.value } : f,
                    ),
                  })
                }
              />
            </label>
            <label>
              Answer type
              <select
                value={field.kind}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    fields: process.fields.map((f, i) =>
                      i === index ? { ...f, kind: e.target.value } : f,
                    ),
                  })
                }
              >
                <option value="text">Text</option>
                <option value="number">Number</option>
                <option value="date">Date</option>
                <option value="select">Single choice</option>
              </select>
            </label>
            {field.kind === "select" && (
              <label>
                Choices (one per line)
                <textarea
                  value={(field.options || []).join("\n")}
                  onChange={(e) =>
                    setProcess({
                      ...process,
                      fields: process.fields.map((f, i) =>
                        i === index
                          ? { ...f, options: e.target.value.split("\n") }
                          : f,
                      ),
                    })
                  }
                />
              </label>
            )}
            <label className="ap-check">
              <input
                type="checkbox"
                checked={!!field.required}
                onChange={(e) =>
                  setProcess({
                    ...process,
                    fields: process.fields.map((f, i) =>
                      i === index ? { ...f, required: e.target.checked } : f,
                    ),
                  })
                }
              />
              Required answer
            </label>
            <button
              onClick={() =>
                setProcess({
                  ...process,
                  fields: process.fields.filter((_, i) => i !== index),
                })
              }
            >
              Remove field {index + 1}
            </button>
          </fieldset>
        ))}
        <button
          disabled={process.fields.length >= 30}
          onClick={() =>
            setProcess({
              ...process,
              fields: [
                ...process.fields,
                {
                  key: `field_${Date.now()}`,
                  label: "New field",
                  kind: "text",
                  required: false,
                },
              ],
            })
          }
        >
          Add request field
        </button>
        <label className="ap-check">
          <input
            type="checkbox"
            checked={process.documents_required}
            onChange={(e) =>
              setProcess({ ...process, documents_required: e.target.checked })
            }
          />
          Supporting documents required
        </label>
        <p>
          Requester and approver must be independent. Rejecting or requesting
          changes requires a reason by default.
        </p>
      </section>
    </>
  );
}
