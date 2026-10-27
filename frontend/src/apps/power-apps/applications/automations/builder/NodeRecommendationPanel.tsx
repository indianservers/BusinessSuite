import { useState } from "react";
import { connectionError, createNode, nodeDefinition } from "./graph";
import type { WorkflowGraph, WorkflowNode, NodeDefinition } from "./types";
export function nodeRecommendations(
  graph: WorkflowGraph,
  node: WorkflowNode,
  catalog: NodeDefinition[],
) {
  const source = catalog.find((d) => d.id === node.type);
  if (!source) return [];
  return catalog
    .filter((d) => !d.trigger && d.id !== node.type)
    .map((d) => {
      const candidate = createNode(d, { x: 0, y: 0 });
      const possible = source.outputs
        .filter((p) => p.id !== "error")
        .some((p) =>
          d.inputs.some(
            (input) =>
              !connectionError(
                { ...graph, nodes: [...graph.nodes, candidate] },
                {
                  id: "suggestion",
                  source: node.id,
                  target: candidate.id,
                  source_port: p.id,
                  target_port: input.id,
                  label: "",
                },
                catalog,
              ),
          ),
        );
      return {
        definition: d,
        score:
          (d.id === "if_else" ? 8 : 0) +
          (Object.values(source.output_schema).includes("object") &&
          ["map_fields", "parse_json"].includes(d.id)
            ? 10
            : 0) +
          (d.requires_credential ? -5 : 3) +
          (d.preview_supported ? 3 : 0),
        possible,
      };
    })
    .filter((d) => d.possible)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
}
export function NodeRecommendationPanel({
  graph,
  node,
  catalog,
  readOnly,
  onAdd,
}: {
  graph: WorkflowGraph;
  node: WorkflowNode;
  catalog: NodeDefinition[];
  readOnly: boolean;
  onAdd: (definition: NodeDefinition, port?: string) => void;
}) {
  const source = nodeDefinition(node, catalog);
  const [port, setPort] = useState(
    source?.outputs.find((p) => p.id !== "error")?.id || "out",
  );
  const rows = nodeRecommendations(graph, node, catalog);
  return (
    <section className="ai-recommendations" aria-label="Recommended next nodes">
      <h3>Suggested next steps</h3>
      <label>
        Output
        <select
          aria-label="Recommendation output port"
          value={port}
          onChange={(e) => setPort(e.target.value)}
        >
          {source?.outputs
            .filter((p) => p.id !== "error")
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
        </select>
      </label>
      <p>
        Based on compatible ports, declared outputs and the allowed catalog.
        Connector-dependent nodes require configuration.
      </p>
      {rows.map(({ definition }) => (
        <button
          key={definition.id}
          disabled={readOnly}
          onClick={() => onAdd(definition, port)}
        >
          <strong>{definition.name}</strong>
          <small>
            {definition.requires_credential
              ? "Requires connection reference"
              : definition.preview_supported
                ? "Local preview available"
                : "Requires runtime executor"}
          </small>
        </button>
      ))}
    </section>
  );
}
