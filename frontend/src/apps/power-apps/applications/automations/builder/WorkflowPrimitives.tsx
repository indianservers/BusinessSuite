import type { ComponentProps, ReactNode } from "react";
import { ReactFlow, MiniMap } from "@xyflow/react";
export function AutomationCanvas(props: ComponentProps<typeof ReactFlow>) {
  return <ReactFlow {...props} />;
}
export function WorkflowMinimap(props: ComponentProps<typeof MiniMap>) {
  return <MiniMap {...props} />;
}
export function WorkflowToolbar({ children }: { children: ReactNode }) {
  return <header className="as-toolbar">{children}</header>;
}
export type WorkflowCrumb = {
  id: string;
  label: string;
  onNavigate?: () => void;
};
export function WorkflowBreadcrumbs({ items }: { items: WorkflowCrumb[] }) {
  return (
    <nav className="as-canvas-breadcrumb" aria-label="Workflow breadcrumbs">
      {items.map((item, i) => (
        <span key={item.id}>
          {i > 0 && <span aria-hidden="true"> / </span>}
          {item.onNavigate ? (
            <button onClick={item.onNavigate}>{item.label}</button>
          ) : (
            <strong aria-current={i === items.length - 1 ? "page" : undefined}>
              {item.label}
            </strong>
          )}
        </span>
      ))}
    </nav>
  );
}
