import { memo, useEffect } from "react";
import {
  useUpdateNodeInternals,
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Check, CircleAlert, MoreHorizontal, Plus } from "lucide-react";
import { NodeIcon } from "./NodeIcon";
import {
  categoryColors,
  type WorkflowNode,
  type NodeDefinition,
} from "./types";
export type StudioNodeData = Record<string, unknown> & {
  node: WorkflowNode;
  definition: NodeDefinition;
  errors: number;
  simulation?: string;
  readOnly: boolean;
  onMenu: (id: string, x: number, y: number) => void;
  onAdd: (id: string, port: string) => void;
};
export type CanvasNode = Node<StudioNodeData, "studio">;
function NodeCard({ data, selected }: NodeProps<CanvasNode>) {
  const { node, definition, errors, readOnly, onMenu, onAdd } = data;
  const updateInternals = useUpdateNodeInternals();
  const portSignature = definition.outputs.map((p) => p.id).join("|");
  useEffect(() => {
    updateInternals(node.id);
  }, [node.id, portSignature, updateInternals]);
  const color = categoryColors[definition.category] || "#8254d0";
  return (
    <div
      className={`as-node ${selected ? "selected" : ""} ${errors ? "invalid" : ""} ${node.disabled ? "disabled" : ""}`}
      style={
        {
          "--node-color": color,
          height: Math.max(
            160,
            definition.outputs.filter((p) => p.id !== "error").length * 28 + 48,
          ),
        } as React.CSSProperties
      }
      data-testid={`node-${node.id}`}
    >
      <div className="as-node-heading">
        <span className="as-node-icon">
          <NodeIcon name={definition.icon} size={22} />
        </span>
        <span className="as-node-category">{definition.category}</span>
        <button
          className="nodrag nopan as-node-menu"
          aria-label={`Actions for ${node.label}`}
          onClick={(e) => {
            e.stopPropagation();
            onMenu(node.id, e.clientX, e.clientY);
          }}
        >
          <MoreHorizontal size={17} />
        </button>
      </div>
      {data.simulation && (
        <small className={`ai-node-state ${data.simulation}`}>
          {data.simulation === "synthetic"
            ? "Synthetic fixture"
            : data.simulation === "previewed"
              ? "Simulated locally"
              : data.simulation}
        </small>
      )}
      <strong title={node.label}>{node.label}</strong>
      <p>{node.description || definition.description}</p>
      <div className="as-node-foot">
        <span className={errors ? "as-node-error" : "as-node-ready"}>
          {errors ? <CircleAlert size={10} /> : <Check size={10} />}{" "}
          {node.disabled
            ? "Disabled"
            : errors
              ? `${errors} to configure`
              : "Configured"}
        </span>
        <span
          title={
            definition.executable
              ? "Server executor registered; publication requires runtime validation"
              : "No runtime executor is registered"
          }
        >
          {definition.executable ? "Executor available" : "Not Executable Yet"}
        </span>
      </div>
      {definition.inputs.map((port, index) => (
        <Handle
          key={port.id}
          type="target"
          id={port.id}
          position={Position.Left}
          isConnectable={!readOnly}
          style={{
            top: `${50 + index * 15}%`,
            background: port.data_type === "error" ? "#d66d72" : color,
          }}
          aria-label={`${node.label}: ${port.label} input`}
        />
      ))}
      {definition.outputs.map((port, index) => (
        <Handle
          key={port.id}
          type="source"
          id={port.id}
          position={port.id === "error" ? Position.Bottom : Position.Right}
          isConnectable={!readOnly}
          style={
            port.id === "error"
              ? { left: "70%", background: "#d66d72" }
              : {
                  top: `${definition.outputs.filter((p) => p.id !== "error").length === 1 ? 50 : ((index + 1) * 100) / (definition.outputs.filter((p) => p.id !== "error").length + 1)}%`,
                  background: color,
                }
          }
          aria-label={`${node.label}: ${port.label} output`}
        >
          <span className="as-port-label">
            {port.id === "out" ? "" : port.label}
          </span>
        </Handle>
      ))}
      {!readOnly &&
        definition.outputs.map((port, index) => (
          <button
            key={port.id}
            className="nodrag nopan as-node-add"
            style={
              port.id === "error"
                ? { top: "100%", right: "27%" }
                : {
                    top: `${definition.outputs.filter((p) => p.id !== "error").length === 1 ? 50 : ((index + 1) * 100) / (definition.outputs.filter((p) => p.id !== "error").length + 1)}%`,
                  }
            }
            aria-label={
              index === 0
                ? `Add after ${node.label}`
                : `Add after ${node.label} via ${port.label}`
            }
            title={`Add to ${port.label} output`}
            onClick={(e) => {
              e.stopPropagation();
              onAdd(node.id, port.id);
            }}
          >
            <Plus size={12} />
          </button>
        ))}
    </div>
  );
}
export const StudioNode = memo(
  NodeCard,
  (a, b) =>
    a.selected === b.selected &&
    a.data.node === b.data.node &&
    a.data.definition === b.data.definition &&
    a.data.errors === b.data.errors &&
    a.data.simulation === b.data.simulation &&
    a.data.readOnly === b.data.readOnly,
);
