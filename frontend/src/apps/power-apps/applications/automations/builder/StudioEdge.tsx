import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
export const StudioEdge = memo(function StudioEdge(props: EdgeProps) {
  const [path, x, y] =
    props.data?.routing === "orthogonal"
      ? getSmoothStepPath({ ...props, borderRadius: 12 })
      : getBezierPath({ ...props, curvature: 0.3 });
  const label = String(props.label || "");
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={props.markerEnd}
        style={{
          ...props.style,
          strokeWidth: props.selected || props.data?.highlighted ? 2.8 : 1.8,
        }}
      />
      {(label || props.selected) && (
        <EdgeLabelRenderer>
          <div
            className="as-edge-label"
            style={{
              transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
            }}
          >
            {label}
            {props.selected && !props.data?.readOnly && (
              <button
                className="nodrag nopan"
                aria-label="Insert node on connection"
                onClick={() => (props.data?.onInsert as () => void)()}
              >
                +
              </button>
            )}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});
