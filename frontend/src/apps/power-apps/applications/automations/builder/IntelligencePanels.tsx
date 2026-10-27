import { useEffect, useRef, useState, useId } from "react";
import { X, Sparkles, Pause, Play, Download } from "lucide-react";
import type { AuthoringPanelProps } from "./intelligenceTypes";
import { download } from "./intelligenceTypes";
import type {
  AIProposal,
  Analysis,
  AutomationTemplate,
  FieldMapping,
  WorkflowGraph,
  PreviewResult,
  VersionSnapshot,
} from "./types";
import {
  upstreamVariables,
  copySubgraph,
  pasteSubgraph,
  compareVersions,
  executionSignature,
  emptyGraph,
  asVisualGraph,
  nodeDefinition,
  appendRecommendation,
} from "./graph";
import { NodeRecommendationPanel } from "./NodeRecommendationPanel";
import { LogicEditor } from "./LogicEditors";
import type { Resource } from "../../../registry";
import { errorMessage } from "../../../api";

type Props = AuthoringPanelProps;
const message = (error: unknown) =>
  error instanceof SyntaxError ? "Enter valid JSON" : errorMessage(error);
const text = (value: unknown) => JSON.stringify(value, null, 2);
function JSONEditor({
  label,
  value,
  onChange,
  readOnly = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}) {
  return (
    <label className="ai-field">
      {label}
      <textarea
        aria-label={label}
        spellCheck={false}
        rows={5}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
function TransformationArgument({
  value,
  onChange,
  onValidity,
  label,
}: {
  value: unknown;
  onChange: (value: unknown) => void;
  onValidity: (valid: boolean) => void;
  label: string;
}) {
  const [raw, setRaw] = useState(text(value));
  const emitted = useRef(text(value));
  useEffect(() => {
    const next = text(value);
    if (next !== emitted.current) {
      setRaw(next);
      emitted.current = next;
      onValidity(true);
    }
  }, [value]);
  return (
    <input
      aria-label={label}
      value={raw}
      onChange={(e) => {
        setRaw(e.target.value);
        try {
          const parsed = JSON.parse(e.target.value);
          emitted.current = text(parsed);
          onChange(parsed);
          onValidity(true);
        } catch {
          onValidity(false);
        }
      }}
    />
  );
}
export function GraphProposalPreview({ graph }: { graph: WorkflowGraph }) {
  const arrowId = useId().replace(/:/g, "");
  const positions = graph.nodes.map((n) => n.position),
    minX = Math.min(0, ...positions.map((p) => p.x)),
    minY = Math.min(0, ...positions.map((p) => p.y)),
    width = Math.max(800, ...positions.map((p) => p.x + 240)) - minX,
    height = Math.max(240, ...positions.map((p) => p.y + 100)) - minY;
  return (
    <svg
      role="img"
      aria-label="Proposed workflow graph"
      className="ai-graph-preview"
      viewBox={`${minX - 20} ${minY - 20} ${width + 40} ${height + 40}`}
    >
      <defs>
        <marker
          id={arrowId}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto"
        >
          <path d="M0 0L10 5L0 10" fill="#9564cf" />
        </marker>
      </defs>
      {graph.edges.map((e) => {
        const a = graph.nodes.find((n) => n.id === e.source),
          b = graph.nodes.find((n) => n.id === e.target);
        return a && b ? (
          <g key={e.id}>
            <path
              d={`M${a.position.x + 200},${a.position.y + 35}L${b.position.x},${b.position.y + 35}`}
              stroke="#b299d1"
              fill="none"
              markerEnd={`url(#${arrowId})`}
            />
            <text
              x={(a.position.x + 200 + b.position.x) / 2}
              y={(a.position.y + b.position.y) / 2 + 25}
              fontSize="10"
              fill="#84619f"
            >
              {e.label || e.source_port}
            </text>
          </g>
        ) : null;
      })}
      {graph.nodes.map((n) => (
        <g key={n.id} transform={`translate(${n.position.x},${n.position.y})`}>
          <rect width="200" height="70" rx="9" fill="white" stroke="#d8c6ec" />
          <text x="12" y="28" fontSize="12" fill="#583684">
            {n.label.slice(0, 26)}
          </text>
          <text x="12" y="49" fontSize="10" fill="#9d89b4">
            {n.type}
          </text>
        </g>
      ))}
    </svg>
  );
}
export function AIWorkflowDesigner(props: Props) {
  const [prompt, setPrompt] = useState(""),
    [mode, setMode] = useState("design"),
    [provider, setProvider] = useState("gemini"),
    [result, setResult] = useState<AIProposal>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [proposalJSON, setProposalJSON] = useState("");
  const base = useRef("");
  return (
    <section aria-label="AI workflow designer">
      <h3>Create with AI</h3>
      <p>
        Only the authorized company gateway is used. The provider receives this
        draft's design metadata, with credential references stripped and
        sensitive text redacted. Suggestions never execute actions.
      </p>
      <label>
        Task
        <select
          aria-label="AI task"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
        >
          {[
            "design",
            "explain",
            "improve",
            "conditions",
            "mappings",
            "errors",
          ].map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
      </label>
      <label>
        Configured provider
        <select
          aria-label="AI provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {["gemini", "openai", "claude"].map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </label>
      <JSONEditor
        label="Describe your workflow"
        value={prompt}
        onChange={setPrompt}
      />
      <button
        disabled={props.readOnly || busy || !prompt.trim()}
        onClick={async () => {
          setBusy(true);
          setError("");
          setResult(undefined);
          setProposalJSON("");
          base.current = text({ ...props.document.definition, viewport: null });
          try {
            setResult(
              await props.services.propose(
                prompt,
                mode,
                provider,
                props.document.definition,
              ),
            );
          } catch (e) {
            setError(message(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Sparkles size={14} />
        {busy ? "Designing…" : "Generate proposal"}
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <h4>{result.summary}</h4>
          {result.findings.map((f, i) => (
            <p key={i}>{f}</p>
          ))}
          {result.definition && (
            <>
              <GraphProposalPreview graph={result.definition} />
              <details>
                <summary>Review or complete proposed configuration</summary>
                <p>
                  Edit the structured proposal if required parameters are
                  missing. Revalidate before approval. This never edits the
                  current draft.
                </p>
                <JSONEditor
                  label="AI proposal configuration JSON"
                  value={proposalJSON || text(result.definition)}
                  onChange={(value) => {
                    setProposalJSON(value);
                    setResult((current) =>
                      current ? { ...current, validation: null } : current,
                    );
                  }}
                />
                <button
                  onClick={async () => {
                    try {
                      const reviewed = await props.services.review(
                        JSON.parse(proposalJSON || text(result.definition)),
                      );
                      setResult({ ...result, ...reviewed });
                      setProposalJSON(text(reviewed.definition));
                      setError("");
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  Validate reviewed proposal
                </button>
              </details>

              <p>
                Before: {props.document.definition.nodes.length} nodes,{" "}
                {props.document.definition.edges.length} connections. After:{" "}
                {result.definition.nodes.length} nodes,{" "}
                {result.definition.edges.length} connections. This replaces the
                current graph as a draft; undo remains available.
              </p>
              <details open>
                <summary>Before-and-after changes</summary>
                {Object.entries(
                  compareVersions(props.document, {
                    ...props.document,
                    definition: result.definition,
                  }),
                ).map(([key, value]) => (
                  <p key={key}>
                    {key}:{" "}
                    {Array.isArray(value)
                      ? value.join(", ") || "None"
                      : value
                        ? "Changed"
                        : "Unchanged"}
                  </p>
                ))}
                <pre>{text(result.definition)}</pre>
              </details>
              {result.validation?.issues
                .filter((i) => i.severity === "error")
                .map((i, index) => (
                  <p key={index}>{i.message}</p>
                ))}
              <button
                disabled={props.readOnly || !result.validation?.valid}
                onClick={() => {
                  if (
                    base.current !==
                    text({ ...props.document.definition, viewport: null })
                  ) {
                    setError(
                      "The draft changed while the proposal was pending. Generate a new proposal.",
                    );
                    return;
                  }
                  if (
                    window.confirm(
                      "Apply this reviewed AI proposal to the draft?",
                    )
                  ) {
                    props.onApply(result.definition!);
                    setResult(undefined);
                  }
                }}
              >
                Approve and apply proposal
              </button>
            </>
          )}
        </>
      )}
    </section>
  );
}
const mappingTargetType = (kind: string): FieldMapping["target_type"] =>
  (
    ({
      number: "number",
      boolean: "boolean",
      json: "object",
      "multi-select": "array",
      date: "date",
      datetime: "datetime",
      text: "string",
      select: "string",
      record: "string",
      user: "string",
      template: "string",
      credential: "string",
    }) as Record<string, FieldMapping["target_type"]>
  )[kind] || "any";
export function DataMappingStudio(props: Props) {
  const node = props.node;
  const definition = node && nodeDefinition(node, props.catalog);
  const [destination, setDestination] = useState(""),
    [mapping, setMapping] = useState<FieldMapping>({
      source: null,
      constant: null,
      operations: [],
      target_type: "any",
      nullable: false,
    }),
    [constant, setConstant] = useState("null"),
    [sample, setSample] = useState(
      '{"trigger":{"record":{"id":42,"amount":75000,"name":"Synthetic sample"}},"steps":{},"workflow":{"variables":{}}}',
    ),
    [result, setResult] = useState<unknown>(),
    [error, setError] = useState(""),
    [preset, setPreset] = useState(""),
    [checked, setChecked] = useState(false);
  const [invalidArguments, setInvalidArguments] = useState<
    Record<number, boolean>
  >({});
  const [argumentRevision, setArgumentRevision] = useState(0);
  const mappingCurrent = useRef("");
  mappingCurrent.current = text({
    mapping,
    sample,
    node: node?.id,
    destination,
  });
  const variables = node
    ? upstreamVariables(props.document.definition, node.id, props.catalog)
    : [];
  useEffect(() => {
    setDestination("");
    setChecked(false);
    setResult(undefined);
  }, [node?.id]);
  const change = (next: FieldMapping) => {
    setMapping(next);
    setChecked(false);
    setResult(undefined);
  };
  if (!node || !definition)
    return (
      <p>Select a destination node on the canvas before mapping its fields.</p>
    );
  return (
    <section aria-label="Data mapping studio">
      <h3>Visual data mapping · {node.label}</h3>
      <p>
        Drag an available field onto a destination or choose it by keyboard.
        Previews use only the JSON supplied below.
      </p>
      <div className="ai-mapping-grid">
        <div>
          <h4>Available Data</h4>
          {variables.map((v) => (
            <button
              key={v.expression}
              draggable
              onDragStart={(e) =>
                e.dataTransfer.setData(
                  "application/power-mapping",
                  v.expression,
                )
              }
              onClick={() => change({ ...mapping, source: v.expression })}
            >
              <strong>{v.label}</strong>
              <small>
                {v.type} · {v.expression}
              </small>
            </button>
          ))}
          <button onClick={() => change({ ...mapping, source: null })}>
            Constant value
          </button>
        </div>
        <div>
          <h4>Mapping Connections</h4>
          <label>
            Source binding
            <input
              aria-label="Mapping source"
              value={mapping.source || ""}
              placeholder="Constant, or {{trigger.record.id}}"
              onChange={(e) =>
                change({ ...mapping, source: e.target.value || null })
              }
            />
          </label>
          {!mapping.source && (
            <JSONEditor
              label="Mapping constant JSON"
              value={constant}
              onChange={(v) => {
                setConstant(v);
                try {
                  change({ ...mapping, constant: JSON.parse(v) });
                } catch {
                  setChecked(false);
                }
              }}
            />
          )}
          <label>
            Target type
            <select
              aria-label="Mapping target type"
              value={mapping.target_type}
              onChange={(e) =>
                change({
                  ...mapping,
                  target_type: e.target.value as FieldMapping["target_type"],
                })
              }
            >
              {[
                "any",
                "string",
                "number",
                "boolean",
                "date",
                "datetime",
                "array",
                "object",
              ].map((type) => (
                <option key={type}>{type}</option>
              ))}
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={mapping.nullable}
              onChange={(e) =>
                change({ ...mapping, nullable: e.target.checked })
              }
            />
            Allow null
          </label>
          {mapping.operations.map((op, i) => (
            <div className="ai-operation" key={i}>
              <select
                aria-label={`Transformation ${i + 1}`}
                value={op.op}
                onChange={(e) =>
                  change({
                    ...mapping,
                    operations: mapping.operations.map((o, j) =>
                      j === i ? { ...o, op: e.target.value } : o,
                    ),
                  })
                }
              >
                {[
                  "default",
                  "convert",
                  "concat",
                  "format_date",
                  "format_number",
                  "filter",
                  "map",
                  "rename",
                  "conditional",
                  "lookup",
                  "path",
                ].map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
              <TransformationArgument
                label={`Transformation ${i + 1} argument JSON`}
                key={`${argumentRevision}-${i}`}
                value={op.argument}
                onChange={(argument) =>
                  change({
                    ...mapping,
                    operations: mapping.operations.map((item, index) =>
                      index === i ? { ...item, argument } : item,
                    ),
                  })
                }
                onValidity={(valid) =>
                  setInvalidArguments((current) => ({
                    ...current,
                    [i]: !valid,
                  }))
                }
              />

              <button
                onClick={() =>
                  change({
                    ...mapping,
                    operations: mapping.operations.filter((_, j) => j !== i),
                  })
                }
              >
                Remove transformation
              </button>
            </div>
          ))}
          <button
            disabled={mapping.operations.length >= 12}
            onClick={() =>
              change({
                ...mapping,
                operations: [
                  ...mapping.operations,
                  { op: "default", argument: "" },
                ],
              })
            }
          >
            Add transformation
          </button>
          <details>
            <summary>Operator examples</summary>
            <pre>
              {text({
                convert: "number",
                concat: [" suffix"],
                format_date: "date",
                format_number: 2,
                filter: { operator: "greater_than", right: 10 },
                map: [{ op: "path", argument: "name" }],
                rename: { old_name: "name" },
                conditional: {
                  condition: { operator: "is_empty" },
                  then: "Missing",
                  else: "Present",
                },
                lookup: { High: 1, Low: 0 },
                path: "record.items.0.name",
              })}
            </pre>
          </details>
        </div>
        <div>
          <h4>Destination Fields</h4>
          {definition.fields.map((f) => (
            <button
              key={f.key}
              aria-pressed={destination === f.key}
              disabled={["max_iterations", "concurrency", "routes"].includes(
                f.key,
              )}
              title={
                ["max_iterations", "concurrency", "routes"].includes(f.key)
                  ? "Bounds and topology must be literal design-time values"
                  : f.label
              }
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setDestination(f.key);
                change({
                  ...mapping,
                  source: e.dataTransfer.getData("application/power-mapping"),
                  target_type: mappingTargetType(f.kind),
                });
              }}
              onClick={() => {
                setDestination(f.key);
                change({ ...mapping, target_type: mappingTargetType(f.kind) });
                if (node.mappings?.[f.key]) {
                  setArgumentRevision((v) => v + 1);
                  setInvalidArguments({});
                  change(node.mappings[f.key]);
                  setConstant(text(node.mappings[f.key].constant));
                }
              }}
            >
              <strong>
                {f.label} {f.required ? "*" : ""}
              </strong>
              <small>
                {f.kind} {f.minimum !== undefined ? `min ${f.minimum}` : ""}{" "}
                {f.maximum !== undefined ? `max ${f.maximum}` : ""}
              </small>
              {node.mappings?.[f.key] && <small>Bound</small>}
            </button>
          ))}
        </div>
      </div>
      <JSONEditor
        label="Mapping sample context JSON"
        value={sample}
        onChange={(v) => {
          setSample(v);
          setChecked(false);
        }}
      />
      <button
        onClick={async () => {
          try {
            if (Object.values(invalidArguments).some(Boolean))
              throw new Error(
                "Correct invalid transformation JSON before previewing",
              );
            const signature = mappingCurrent.current;
            if (!mapping.source) JSON.parse(constant);
            const context = JSON.parse(sample);
            context.workflow = {
              variables: props.document.definition.variables || {},
            };
            const response = await props.services.mapping(
              mapping,
              context,
              destination ? node.type : undefined,
              destination || undefined,
            );
            if (signature !== mappingCurrent.current)
              throw new Error("Mapping changed during preview; preview again");
            setResult(response.value);
            setError("");
            setChecked(true);
          } catch (e) {
            setError(message(e));
            setChecked(false);
          }
        }}
      >
        Preview mapping
      </button>
      <button
        disabled={props.readOnly || !destination || !checked}
        onClick={() => {
          props.onNode({
            ...node,
            mappings: { ...node.mappings, [destination]: mapping },
          });
          setChecked(false);
        }}
      >
        Apply validated mapping
      </button>
      {destination && node.mappings?.[destination] && (
        <button
          disabled={props.readOnly}
          onClick={() => {
            const mappings = { ...node.mappings };
            delete mappings[destination];
            props.onNode({ ...node, mappings });
          }}
        >
          Remove field binding
        </button>
      )}
      {error && <p role="alert">{error}</p>}
      {checked && <pre aria-label="Mapping preview result">{text(result)}</pre>}
      <label>
        Mapping preset name
        <input
          aria-label="Mapping preset name"
          value={preset}
          onChange={(e) => setPreset(e.target.value)}
          maxLength={80}
        />
      </label>
      <button
        disabled={
          props.readOnly ||
          !checked ||
          !preset ||
          (props.document.definition.mapping_presets || []).length >= 30
        }
        onClick={() =>
          props.onApply({
            ...props.document.definition,
            mapping_presets: [
              ...(props.document.definition.mapping_presets || []),
              { name: preset, mapping },
            ],
          })
        }
      >
        Save mapping preset
      </button>
      {(props.document.definition.mapping_presets || []).map((p, i) => (
        <button
          key={i}
          onClick={() => {
            change(p.mapping);
            setConstant(text(p.mapping.constant));
          }}
        >
          Use preset: {p.name}
        </button>
      ))}
    </section>
  );
}
export function TemplateMarketplace(props: Props) {
  const [items, setItems] = useState<AutomationTemplate[]>([]),
    [query, setQuery] = useState(""),
    [category, setCategory] = useState("All"),
    [selected, setSelected] = useState<AutomationTemplate>(),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    props.services
      .templates()
      .then((items) => {
        if (live) setItems(items);
      })
      .catch((e) => {
        if (live) setError(message(e));
      });
    return () => {
      live = false;
    };
  }, []);
  return (
    <section aria-label="Template marketplace">
      <h3>Template marketplace</h3>
      <p>Standalone designs. No module events or connectors are activated.</p>
      <input
        aria-label="Search marketplace"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search workflow ideas"
      />
      <select
        aria-label="Marketplace category"
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      >
        <option>All</option>
        {[...new Set(items.map((i) => i.category || "Productivity"))].map(
          (c) => (
            <option key={c}>{c}</option>
          ),
        )}
      </select>
      {error && <p role="alert">{error}</p>}
      <div className="ai-template-grid">
        {items
          .filter(
            (i) =>
              (category === "All" || i.category === category) &&
              `${i.name} ${i.description}`
                .toLowerCase()
                .includes(query.toLowerCase()),
          )
          .map((i) => (
            <button key={i.id} onClick={() => setSelected(i)}>
              <strong>{i.name}</strong>
              <small>
                {i.category} · v{i.version}
              </small>
            </button>
          ))}
      </div>
      {selected && (
        <article>
          <h4>{selected.name}</h4>
          <p>{selected.description}</p>
          <GraphProposalPreview graph={selected.definition} />
          <p>
            Prerequisites:{" "}
            {selected.required_adapters.join(", ") ||
              "Configure input parameters"}
          </p>
          <button
            disabled={props.readOnly}
            onClick={() => {
              if (
                window.confirm(
                  "Replace the draft graph with this reviewed template?",
                )
              )
                props.onApply(selected.definition);
            }}
          >
            Use reviewed template
          </button>
        </article>
      )}
    </section>
  );
}
export function WorkflowImportExport(props: Props) {
  const [raw, setRaw] = useState(""),
    [preview, setPreview] = useState<{
      definition: WorkflowGraph;
      warnings: string[];
    }>(),
    [error, setError] = useState("");
  return (
    <section aria-label="Workflow import export">
      <h3>Portable workflow JSON</h3>
      <p>
        Imported graphs remain drafts. Credential references and tenant-bound
        links are stripped; node IDs and internal references are remapped.
        Review missing configuration before use.
      </p>
      <button
        onClick={async () => {
          try {
            const portable = await props.services.portable(
              props.document.definition,
            );
            download(
              "workflow.json",
              text({ ...props.document, definition: portable.definition }),
            );
          } catch (e) {
            setError(message(e));
          }
        }}
      >
        Export portable workflow
      </button>
      <label>
        Choose workflow JSON
        <input
          aria-label="Import workflow file"
          type="file"
          accept=".json,application/json"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 1000000) {
              setError("Import limit is 1 MB");
              return;
            }
            setRaw(await file.text());
            setPreview(undefined);
          }}
        />
      </label>
      <JSONEditor
        label="Import workflow JSON"
        value={raw}
        onChange={(v) => {
          setRaw(v);
          setPreview(undefined);
        }}
      />
      <button
        disabled={!raw}
        onClick={async () => {
          try {
            const value = JSON.parse(raw);
            const imported = value.definition || value;
            const result = await props.services.portable(
              imported.schema_version === 1
                ? asVisualGraph(imported, props.catalog)
                : imported,
            );
            setPreview(result);
            setError("");
          } catch (e) {
            setError(message(e));
            setPreview(undefined);
          }
        }}
      >
        Validate import preview
      </button>
      {error && <p role="alert">{error}</p>}
      {preview && (
        <>
          <GraphProposalPreview graph={preview.definition} />
          {preview.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          <button
            disabled={props.readOnly}
            onClick={() => {
              if (
                window.confirm("Replace this draft with the reviewed import?")
              ) {
                props.onApply(preview.definition);
                setPreview(undefined);
              }
            }}
          >
            Apply reviewed import
          </button>
        </>
      )}
    </section>
  );
}
export function WorkflowQualityPanel({
  analysis,
  onFocus,
}: {
  analysis: Analysis;
  onFocus: (id: string) => void;
}) {
  return (
    <section aria-label="Workflow quality">
      <h3>Design quality · {analysis.quality.score}/100</h3>
      <p>{analysis.quality.label}</p>
      {analysis.quality.findings.map((f, i) => (
        <button
          key={i}
          disabled={!f.node_id}
          onClick={() => f.node_id && onFocus(f.node_id)}
        >
          <strong>
            {f.severity}: {f.message}
          </strong>
          <small>{f.node_id || "Workflow"}</small>
        </button>
      ))}
    </section>
  );
}
export function WorkflowDocumentation({ analysis }: { analysis: Analysis }) {
  return (
    <section aria-label="Workflow documentation">
      <h3>Workflow documentation</h3>
      <p>
        Generated from the definition; operational behavior is not verified.
      </p>
      <button
        onClick={() =>
          download(
            "workflow-documentation.md",
            analysis.documentation,
            "text/markdown",
          )
        }
      >
        Export documentation
      </button>
      <pre>{analysis.documentation}</pre>
    </section>
  );
}
export function WorkflowDebugger({
  result,
  visible,
  onFocus,
  mode = "simulation",
  focusedNodeId,
  allowExport = true,
  onExport,
}: {
  mode?: "simulation" | "runtime";
  focusedNodeId?: string;
  allowExport?: boolean;
  onExport?: () => void;
  result: {
    validation: { issues: PreviewResult["validation"]["issues"] };
    timeline: (Omit<PreviewResult["timeline"][number], "status"> & {
      status: string;
      attempt?: number;
      started_at?: string | null;
      finished_at?: string | null;
    })[];
  };
  visible: number;
  onFocus: (id: string) => void;
}) {
  const [selected, setSelected] = useState(0);
  useEffect(() => {
    if (!focusedNodeId) return;
    const index = result.timeline.findIndex((e) => e.node_id === focusedNodeId);
    if (index >= 0) setSelected(index);
  }, [focusedNodeId, result.timeline]);
  const entries = result.timeline.slice(0, visible);
  const entry = entries[Math.min(selected, entries.length - 1)];
  return (
    <section aria-label="Workflow debugger">
      <h3>
        {mode === "runtime" ? "Execution timeline" : "Simulation timeline"}
      </h3>
      {result.validation.issues
        .filter((i) => i.severity === "error")
        .map((i, index) => (
          <button key={index} onClick={() => i.node_id && onFocus(i.node_id)}>
            {i.message}
          </button>
        ))}
      <div className="ai-debug-grid">
        <div>
          {entries.map((e, i) => (
            <button
              key={e.node_id}
              aria-pressed={i === selected}
              onClick={() => {
                setSelected(i);
                onFocus(e.node_id);
              }}
            >
              <strong>
                {i + 1}. {e.label}
              </strong>
              <small>
                {e.status === "not_executable"
                  ? "Skipped — External Action / Requires Production Executor"
                  : e.status === "synthetic"
                    ? "Explicit synthetic output"
                    : e.status}
              </small>
            </button>
          ))}
        </div>
        {entry && (
          <div>
            <h4>{entry.label}</h4>
            <p>{entry.error}</p>
            <pre>
              {text({
                input: entry.input,
                output: entry.output,
                condition_evaluation: entry.output,
                active_ports: entry.active_ports,
                variable_state: entry.variables,
                attempt: entry.attempt,
                started_at: entry.started_at,
                finished_at: entry.finished_at,
              })}
            </pre>
          </div>
        )}
      </div>
      <button
        disabled={!allowExport}
        onClick={() =>
          onExport
            ? onExport()
            : download(
                mode === "runtime"
                  ? "execution-debug.json"
                  : "simulation-debug.json",
                text(result),
              )
        }
      >
        <Download size={13} />
        Export debug report
      </button>
      <p>
        {mode === "runtime"
          ? "Read-only persisted steps from the version used by this run."
          : "Simulation is not proof that integrations work. No estimated integration timings are fabricated."}
      </p>
    </section>
  );
}
export function WorkflowSimulator(props: Props) {
  const latest = useRef(props.document.definition);
  latest.current = props.document.definition;
  const [input, setInput] = useState('{"record":{}}'),
    [synthetic, setSynthetic] = useState("{}"),
    [injected, setInjected] = useState(""),
    [result, setResult] = useState<PreviewResult>(),
    [visible, setVisible] = useState(0),
    [playing, setPlaying] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!playing || !result) return;
    if (visible >= result.timeline.length) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setVisible((v) => v + 1), 650);
    return () => clearTimeout(timer);
  }, [playing, visible, result]);
  useEffect(() => {
    if (result)
      props.onSimulation({
        ...result,
        timeline: result.timeline.slice(0, visible),
      });
  }, [result, visible]);
  useEffect(() => {
    setResult(undefined);
    setPlaying(false);
    props.onSimulation(undefined);
  }, [executionSignature(props.document.definition)]);
  return (
    <section aria-label="Safe simulation studio">
      <h3>Design-time simulation</h3>
      <p>
        Only deterministic local nodes run. External actions are blocked. Supply
        explicit synthetic outputs to inspect downstream logic.
      </p>
      <button
        onClick={() =>
          setInput(
            text({
              record: {
                id: 42,
                name: "Synthetic fixture",
                amount: 75000,
                severity: "Critical",
                email: "fixture@example.invalid",
                items: [
                  { name: "One", amount: 12 },
                  { name: "Two", amount: 25 },
                ],
              },
            }),
          )
        }
      >
        Generate labeled synthetic payload
      </button>
      <JSONEditor
        label="Simulation input JSON"
        value={input}
        onChange={setInput}
      />
      <JSONEditor
        label="Explicit synthetic node outputs JSON"
        value={synthetic}
        onChange={setSynthetic}
      />
      <label>
        Inject errors in node IDs (comma separated)
        <input
          aria-label="Injected error node IDs"
          value={injected}
          onChange={(e) => setInjected(e.target.value)}
        />
      </label>
      <button
        onClick={async () => {
          try {
            const signature = executionSignature(latest.current);
            const response = await props.services.simulate(
              props.document.definition,
              JSON.parse(input),
              JSON.parse(synthetic),
              injected
                .split(",")
                .map((i) => i.trim())
                .filter(Boolean),
            );
            if (signature !== executionSignature(latest.current))
              throw new Error(
                "Draft changed during simulation; prepare it again",
              );
            setResult(response);
            setVisible(0);
            setPlaying(false);

            setError("");
          } catch (e) {
            setError(message(e));
          }
        }}
      >
        Prepare safe simulation
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p>
            {result.validation.valid
              ? "Structurally valid · local simulation prepared"
              : "Failed validation"}
          </p>
          <button
            disabled={visible >= result.timeline.length}
            onClick={() => setVisible((v) => v + 1)}
          >
            Step through
          </button>
          <button
            disabled={!result.timeline.length}
            onClick={() => setPlaying((p) => !p)}
          >
            {playing ? <Pause size={13} /> : <Play size={13} />}{" "}
            {playing ? "Pause inspection" : "Play inspection"}
          </button>
          <button
            onClick={() => {
              setVisible(result.timeline.length);
              setPlaying(false);
            }}
          >
            Inspect all
          </button>
          <WorkflowDebugger
            result={result}
            visible={visible}
            onFocus={props.onFocus}
          />
        </>
      )}
    </section>
  );
}

export function ReusableBlockLibrary(props: Props) {
  const [items, setItems] = useState<Resource[]>([]),
    [error, setError] = useState(""),
    [name, setName] = useState("New reusable block"),
    [description, setDescription] = useState(""),
    [contract, setContract] = useState('{"inputs":[],"outputs":[]}'),
    [parameters, setParameters] = useState("{}"),
    [editing, setEditing] = useState<Resource>(),
    [raw, setRaw] = useState(""),
    [versions, setVersions] = useState<VersionSnapshot[]>([]),
    [selectedVersion, setSelectedVersion] = useState<number>(),
    [selected, setSelected] = useState<Resource>(),
    [usage, setUsage] = useState<
      { id: number; name: string; version: number }[]
    >([]);
  const refresh = () =>
    props.services
      .blocks()
      .then(setItems)
      .catch((e) => setError(message(e)));
  useEffect(() => {
    void refresh();
  }, []);
  const save = async (copy = false) => {
    try {
      let graph: WorkflowGraph;
      if (editing) {
        graph = JSON.parse(raw);
      } else {
        const part = copySubgraph(props.document.definition, props.selected);
        graph = {
          ...emptyGraph(),
          nodes: part.nodes,
          edges: part.edges,
          groups: part.groups,
          annotations: part.annotations,
        };
      }
      graph.block_contract = JSON.parse(contract);
      await props.services.saveBlock(
        { name, description, definition: graph },
        copy ? undefined : editing?.id,
        editing?.version,
      );
      setError("");
      setEditing(undefined);
      await refresh();
    } catch (e) {
      setError(message(e));
    }
  };
  return (
    <section aria-label="Reusable blocks library">
      <h3>Reusable Blocks</h3>
      <p>
        Save a selection without a trigger. Versions are immutable snapshots;
        inserted copies pin their source version and never change when a block
        is edited.
      </p>
      <label>
        Block name
        <input
          aria-label="Block name"
          value={name}
          maxLength={180}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label>
        Description
        <input
          aria-label="Block description"
          value={description}
          maxLength={2000}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      <JSONEditor
        label="Block input output contract JSON"
        value={contract}
        onChange={setContract}
      />
      <details>
        <summary>Contract example</summary>
        <pre>
          {text({
            inputs: [
              {
                name: "approval_title",
                node_id: "selected_node_id",
                field: "title",
                data_type: "string",
                default: "Review request",
              },
            ],
            outputs: [
              {
                name: "result",
                node_id: "selected_node_id",
                field: "value",
                data_type: "any",
                default: null,
              },
            ],
          })}
        </pre>
      </details>
      {editing && (
        <JSONEditor
          label="Block draft definition JSON"
          value={raw}
          onChange={setRaw}
        />
      )}
      <button disabled={props.readOnly} onClick={() => void save()}>
        {editing ? "Save block draft version" : "Save selection as block"}
      </button>
      {editing && (
        <button disabled={props.readOnly} onClick={() => void save(true)}>
          Duplicate block
        </button>
      )}
      {error && <p role="alert">{error}</p>}
      <div className="ai-template-grid">
        {items.map((row) => (
          <button
            key={row.id}
            onClick={async () => {
              try {
                setSelected(row);
                setVersions(await props.services.blockVersions(row.id));
                setSelectedVersion(row.version);
                setUsage(await props.services.blockUsage(row.id));
                setParameters(
                  text(
                    Object.fromEntries(
                      (
                        (row.definition as WorkflowGraph).block_contract
                          ?.inputs || []
                      ).map((p) => [p.name, p.default]),
                    ),
                  ),
                );
                setError("");
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            <strong>{row.name}</strong>
            <small>Draft v{row.version}</small>
          </button>
        ))}
      </div>
      {selected && (
        <article>
          <h4>{selected.name}</h4>
          <label>
            Immutable version
            <select
              aria-label="Block version"
              value={selectedVersion}
              onChange={(e) => setSelectedVersion(Number(e.target.value))}
            >
              {versions.map((v) => (
                <option key={v.id} value={v.version}>
                  Version {v.version}
                </option>
              ))}
            </select>
          </label>
          <GraphProposalPreview
            graph={
              (versions.find((v) => v.version === selectedVersion)?.snapshot
                .definition || selected.definition) as WorkflowGraph
            }
          />
          <JSONEditor
            label="Block parameter values JSON"
            value={parameters}
            onChange={setParameters}
          />
          <button
            disabled={props.readOnly}
            onClick={() => {
              try {
                const graph = structuredClone(
                  (versions.find((v) => v.version === selectedVersion)?.snapshot
                    .definition || selected.definition) as WorkflowGraph,
                );
                const values = JSON.parse(parameters);
                for (const p of graph.block_contract?.inputs || []) {
                  const node = graph.nodes.find((n) => n.id === p.node_id);
                  if (node) {
                    node.config[p.field] = values[p.name] ?? p.default;
                    if (node.mappings) delete node.mappings[p.field];
                  }
                }
                const pasted = pasteSubgraph(props.document.definition, {
                  nodes: graph.nodes,
                  edges: graph.edges,
                  groups: graph.groups,
                  annotations: graph.annotations || [],
                  block_references: graph.block_references || [],
                });
                props.onApply({
                  ...pasted.graph,
                  block_references: [
                    ...(pasted.graph.block_references || []),
                    {
                      resource_id: selected.id,
                      version: selectedVersion || selected.version,
                      node_ids: pasted.graph.nodes
                        .filter((n) => pasted.selected.has(n.id))
                        .map((n) => n.id),
                    },
                  ],
                });
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            Insert pinned block version
          </button>
          <button
            disabled={props.readOnly}
            onClick={() => {
              setEditing(selected);
              setName(selected.name);
              setDescription(selected.description);
              setContract(
                text(
                  (selected.definition as WorkflowGraph).block_contract || {
                    inputs: [],
                    outputs: [],
                  },
                ),
              );
              setRaw(text(selected.definition));
            }}
          >
            Edit block draft
          </button>
          <button
            disabled={props.readOnly}
            onClick={async () => {
              try {
                await props.services.saveBlock({
                  name: selected.name + " (copy)",
                  description: selected.description,
                  definition: selected.definition as WorkflowGraph,
                });
                await refresh();
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            Duplicate selected block
          </button>
          <button
            disabled={props.readOnly || usage.length > 0}
            onClick={async () => {
              if (window.confirm("Archive this unused block?")) {
                try {
                  await props.services.archiveBlock(selected);
                  setSelected(undefined);
                  await refresh();
                } catch (e) {
                  setError(message(e));
                }
              }
            }}
          >
            Archive unused block
          </button>
          <h4>Usage in your authorized scope</h4>
          {usage.length ? (
            usage.map((row) => (
              <p key={row.id}>
                {row.name} · v{row.version}
              </p>
            ))
          ) : (
            <p>
              No references visible in this scope. Server checks all tenant
              references before archival.
            </p>
          )}
        </article>
      )}
    </section>
  );
}
const toolTabs = [
  "AI designer",
  "Recommendations",
  "Data mapping",
  "Logic",
  "Reusable blocks",
  "Templates",
  "Simulation",
  "Documentation",
  "Quality",
  "Import / export",
];
export function IntelligentStudio(props: Props) {
  const [tab, setTab] = useState(props.initialTab || "AI designer"),
    [analysis, setAnalysis] = useState<Analysis>(),
    [error, setError] = useState("");
  useEffect(() => {
    if (!["Quality", "Documentation"].includes(tab)) return;
    let active = true;
    setAnalysis(undefined);
    props.services
      .analyze(props.document, props.version)
      .then((result) => {
        if (active) setAnalysis(result);
      })
      .catch((e) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [tab, props.document, props.version]);
  return (
    <div
      className="ai-workbench"
      role="dialog"
      aria-label="Intelligent automation studio"
    >
      <header>
        <Sparkles size={17} />
        <strong>Authoring studio</strong>
        <span>DESIGN TIME ONLY</span>
        <button aria-label="Close authoring studio" onClick={props.onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="ai-workbench-body">
        <nav aria-label="Authoring tools">
          {toolTabs.map((name) => (
            <button
              key={name}
              aria-pressed={tab === name}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </nav>
        <div className="ai-workbench-content">
          {error && <p role="alert">{error}</p>}
          {tab === "AI designer" && <AIWorkflowDesigner {...props} />}{" "}
          {tab === "Recommendations" &&
            (props.node ? (
              <NodeRecommendationPanel
                graph={props.document.definition}
                node={props.node}
                catalog={props.catalog}
                readOnly={props.readOnly}
                onAdd={(definition, port) => {
                  try {
                    const result = appendRecommendation(
                      props.document.definition,
                      props.node!,
                      definition,
                      props.catalog,
                      port,
                    );
                    props.onApply(result.graph);
                    props.onFocus(result.node.id);
                  } catch (e) {
                    setError(message(e));
                  }
                }}
              />
            ) : (
              <p>Select a node to get schema-based recommendations.</p>
            ))}
          {tab === "Data mapping" && <DataMappingStudio {...props} />}{" "}
          {tab === "Logic" &&
            (props.node ? (
              <LogicEditor
                node={props.node}
                catalog={props.catalog}
                readOnly={props.readOnly}
                usedPorts={props.document.definition.edges
                  .filter((e) => e.source === props.node!.id)
                  .map((e) => e.source_port)}
                onChange={props.onNode}
              />
            ) : (
              <p>Select a logic node.</p>
            ))}{" "}
          {tab === "Reusable blocks" && <ReusableBlockLibrary {...props} />}{" "}
          {tab === "Templates" && <TemplateMarketplace {...props} />}{" "}
          {tab === "Simulation" && <WorkflowSimulator {...props} />}{" "}
          {tab === "Import / export" && <WorkflowImportExport {...props} />}{" "}
          {tab === "Documentation" &&
            (analysis ? (
              <WorkflowDocumentation analysis={analysis} />
            ) : (
              <p>Analyzing definition…</p>
            ))}{" "}
          {tab === "Quality" &&
            (analysis ? (
              <WorkflowQualityPanel
                analysis={analysis}
                onFocus={props.onFocus}
              />
            ) : (
              <p>Analyzing definition…</p>
            ))}
        </div>
      </div>
    </div>
  );
}
