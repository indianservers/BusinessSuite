import type {
  AuthoringServices,
  NodeDefinition,
  WorkflowDocument,
  WorkflowGraph,
  WorkflowNode,
  PreviewResult,
} from "./types";
export type AuthoringPanelProps = {
  document: WorkflowDocument;
  version: number;
  catalog: NodeDefinition[];
  selected: Set<string>;
  node?: WorkflowNode;
  readOnly: boolean;
  services: AuthoringServices;
  onApply: (graph: WorkflowGraph) => void;
  onNode: (node: WorkflowNode) => void;
  onFocus: (id: string) => void;
  onSimulation: (result: PreviewResult | undefined) => void;
  onClose: () => void;
  initialTab?: string;
};
export const parseValue = (text: string): unknown => {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};
export function download(
  name: string,
  value: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([value], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
