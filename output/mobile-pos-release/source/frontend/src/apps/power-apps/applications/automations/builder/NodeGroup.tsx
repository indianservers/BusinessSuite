import { memo } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { NodeProps } from "@xyflow/react";
export const NodeGroup = memo(function NodeGroup({ data }: NodeProps) {
  return (
    <div className="as-group-label">
      <button
        className="nodrag nopan"
        aria-label={`${data.collapsed ? "Expand" : "Collapse"} group ${data.label}`}
        onClick={() => (data.onToggle as () => void)()}
      >
        {data.collapsed ? (
          <ChevronRight size={15} />
        ) : (
          <ChevronDown size={15} />
        )}
      </button>
      <span>{String(data.label)}</span>
      <small>{String(data.count)} steps</small>
    </div>
  );
});
export const WorkflowAnnotation = memo(function WorkflowAnnotation({
  data,
}: NodeProps) {
  return (
    <div
      className={`as-annotation ${data.kind === "annotation" ? "as-annotation-block" : ""}`}
    >
      <small>{data.kind === "annotation" ? "ANNOTATION" : "STICKY NOTE"}</small>
      <p>{String(data.text || "Select this note to add context")}</p>
    </div>
  );
});
