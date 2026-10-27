import { useState } from "react";
import type { NodeDefinition, WorkflowEdge, WorkflowGraph } from "./types";
import { connectionError, nodeDefinition } from "./graph";
export function ConnectionEditor({
  edge,
  graph,
  catalog,
  readOnly,
  onChange,
  onDelete,
  onInsert,
}: {
  edge: WorkflowEdge;
  graph: WorkflowGraph;
  catalog: NodeDefinition[];
  readOnly: boolean;
  onChange: (edge: WorkflowEdge) => void;
  onDelete: () => void;
  onInsert: () => void;
}) {
  const [draft, setDraft] = useState(edge),
    [error, setError] = useState("");
  const ports = (id: string, kind: "inputs" | "outputs") =>
    nodeDefinition(
      graph.nodes.find((n) => n.id === id),
      catalog,
    )?.[kind] || [];
  return (
    <section className="as-connection-editor" aria-label="Connection editor">
      <h3>CONNECTION</h3>
      <label className="as-basic-field">
        Connection label
        <input
          aria-label="Connection label"
          disabled={readOnly}
          maxLength={120}
          value={draft.label}
          onChange={(e) => setDraft({ ...draft, label: e.target.value })}
        />
      </label>
      {(["source", "target"] as const).map((side) => (
        <div key={side}>
          <label className="as-basic-field">
            {side === "source" ? "Connection source" : "Connection target"}
            <select
              aria-label={`Connection ${side}`}
              disabled={readOnly}
              value={draft[side]}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  [side]: e.target.value,
                  [side + "_port"]:
                    ports(
                      e.target.value,
                      side === "source" ? "outputs" : "inputs",
                    )[0]?.id || "",
                })
              }
            >
              {graph.nodes
                .filter(
                  (n) =>
                    ports(n.id, side === "source" ? "outputs" : "inputs")
                      .length,
                )
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
            </select>
          </label>
          <label className="as-basic-field">
            {side} port
            <select
              aria-label={`Connection ${side} port`}
              disabled={readOnly}
              value={draft[`${side}_port`]}
              onChange={(e) =>
                setDraft({ ...draft, [`${side}_port`]: e.target.value })
              }
            >
              {ports(draft[side], side === "source" ? "outputs" : "inputs").map(
                (p) => (
                  <option key={p.id} value={p.id}>
                    {p.label} ({p.data_type})
                  </option>
                ),
              )}
            </select>
          </label>
        </div>
      ))}
      <label className="as-basic-field">
        Connection style
        <select
          aria-label="Connection style"
          disabled={readOnly}
          value={draft.style || "bezier"}
          onChange={(e) =>
            setDraft({
              ...draft,
              style: e.target.value as WorkflowEdge["style"],
            })
          }
        >
          <option value="bezier">Smooth Bezier</option>
          <option value="orthogonal">Orthogonal</option>
        </select>
      </label>
      {error && (
        <p role="alert" className="as-field-error">
          {error}
        </p>
      )}
      <button
        disabled={readOnly}
        onClick={() => {
          const reason = connectionError(
            { ...graph, edges: graph.edges.filter((e) => e.id !== edge.id) },
            draft,
            catalog,
          );
          setError(reason || "");
          if (!reason) onChange(draft);
        }}
      >
        Apply connection
      </button>
      <button disabled={readOnly} onClick={onInsert}>
        Insert node between
      </button>
      <button disabled={readOnly} className="as-danger" onClick={onDelete}>
        Delete connection
      </button>
    </section>
  );
}
