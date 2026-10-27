import type { CSSProperties } from "react";
import type { Environment, Resource } from "../../../registry";
export type FieldKind =
  | "text"
  | "number"
  | "boolean"
  | "date"
  | "datetime"
  | "select"
  | "multi-select"
  | "json"
  | "dynamic"
  | "expression"
  | "credential"
  | "record"
  | "user"
  | "template";
export type ConfigField = {
  key: string;
  label: string;
  kind: FieldKind;
  required: boolean;
  allow_expression: boolean;
  default?: unknown;
  options?: string[];
  minimum?: number;
  maximum?: number;
  visible_when?: { field: string; equals: unknown };
};
export type PortDefinition = {
  id: string;
  label: string;
  data_type: string;
  max_connections: number;
};
export type NodeDefinition = {
  id: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  trigger: boolean;
  editor_ready: boolean;
  executable: boolean;
  preview_supported: boolean;
  requires_credential: boolean;
  fields: ConfigField[];
  inputs: PortDefinition[];
  outputs: PortDefinition[];
  output_schema: Record<string, string>;
  help: string;
};
export type Point = { x: number; y: number };
export type FieldMapping = {
  source: string | null;
  constant: unknown;
  operations: { op: string; argument: unknown }[];
  target_type:
    | "any"
    | "string"
    | "number"
    | "boolean"
    | "date"
    | "datetime"
    | "array"
    | "object";
  nullable: boolean;
};
export type BlockParameter = {
  name: string;
  node_id: string;
  field: string;
  data_type: string;
  default: unknown;
};
export type WorkflowNode = {
  mappings?: Record<string, FieldMapping>;
  disabled?: boolean;
  id: string;
  type: string;
  label: string;
  description: string;
  position: Point;
  config: Record<string, unknown>;
  credential_reference: string | null;
  advanced: {
    retry_attempts: number;
    error_strategy: "stop" | "continue" | "branch";
    timeout_seconds: number;
  };
};
export type WorkflowEdge = {
  style?: "bezier" | "orthogonal";
  id: string;
  source: string;
  target: string;
  source_port: string;
  target_port: string;
  label: string;
};
export type WorkflowGroup = {
  collapsed?: boolean;
  id: string;
  label: string;
  node_ids: string[];
  position: Point;
  width: number;
  height: number;
};
export type WorkflowAnnotation = {
  id: string;
  kind: "note" | "annotation";
  text: string;
  position: Point;
  width: number;
};
export type WorkflowSettings = {
  max_attempts: number;
  retry_backoff_seconds: number;
  idempotency: "event_id" | "request_id";
  execution_identity: "owner";
  timezone: string;
  retention_days: number;
};
export type WorkflowGraph = Record<string, unknown> & {
  schema_version: 2;
  catalog_version: 1;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  groups: WorkflowGroup[];
  block_contract?: {
    inputs: BlockParameter[];
    outputs: BlockParameter[];
  } | null;
  block_references?: {
    resource_id: number;
    version: number;
    node_ids: string[];
  }[];
  mapping_presets?: { name: string; mapping: FieldMapping }[];
  viewport: Point & { zoom: number };
  settings: WorkflowSettings;
  editor?: { snap_to_grid: boolean; connection_style: "bezier" | "orthogonal" };
  annotations?: WorkflowAnnotation[];
  tags?: string[];
  variables?: Record<string, string | number | boolean>;
};
export type Issue = {
  code: string;
  message: string;
  node_id?: string | null;
  field?: string | null;
  severity: "error" | "warning";
};
export type ValidationResult = {
  valid: boolean;
  executable: false;
  issues: Issue[];
  node_count: number;
  edge_count: number;
  catalog_version: number;
};
export type PreviewEntry = {
  node_id: string;
  label: string;
  status:
    | "synthetic"
    | "disabled"
    | "previewed"
    | "not_executable"
    | "not_reached"
    | "waiting_for_inputs"
    | "error";
  active_ports?: string[];
  variables?: Record<string, unknown>;
  input: unknown;
  output: unknown;
  error: string | null;
};
export type PreviewResult = {
  design_time_only: true;
  integration_execution: false;
  validation: ValidationResult;
  timeline: PreviewEntry[];
};
export type WorkflowDocument = {
  name: string;
  description: string;
  definition: WorkflowGraph;
};
export type VersionSnapshot = {
  id: number;
  version: number;
  created_at: string;
  created_by: number;
  snapshot: {
    name: string;
    description: string;
    definition: Record<string, unknown>;
    status: string;
    archived?: boolean;
  };
};
export type AutomationTemplate = {
  category?: string;
  id: string;
  name: string;
  description: string;
  version: number;
  requires_configuration: true;
  executable: false;
  required_adapters: string[];
  definition: WorkflowGraph;
};
export type BuilderPermissions = {
  create: boolean;
  edit: boolean;
  delete: boolean;
  publish: boolean;
  execute: boolean;
  manageCredentials: boolean;
};
export type ReferenceProvider = (
  query: string,
) => Promise<{ value: string; label: string }[]>;
export type AutomationBuilderProps = {
  authoring?: AuthoringServices;
  breadcrumbs?: { id: string; label: string; onNavigate?: () => void }[];
  workflowId?: number;
  environmentId: Environment;
  mode: "edit" | "read-only";
  initialDocument: WorkflowDocument;
  version: number;
  savedAt?: string;
  recoveryKey: string;
  nodeCatalog: NodeDefinition[];
  permissions: BuilderPermissions;
  onSave: (
    document: WorkflowDocument,
    expectedVersion: number,
  ) => Promise<Resource>;
  onValidate?: (definition: WorkflowGraph) => Promise<ValidationResult>;
  onPreview?: (
    definition: WorkflowGraph,
    input: Record<string, unknown>,
  ) => Promise<PreviewResult>;
  onOpenWorkflow?: (id: string) => Promise<void>;
  onBack: () => void;
  onRuntime?: () => void;
  onSaved?: (resource: Resource) => void;
  onDuplicate?: () => Promise<void>;
  onSaveCopy?: (document: WorkflowDocument) => Promise<void>;
  onVersionHistory?: () => void;
  onSettings?: () => void;
  externalPanel?: "versions" | "settings" | null;
  versions?: VersionSnapshot[];
  onRestoreVersion?: (version: number) => Promise<void>;
  referenceProviders?: Record<string, ReferenceProvider>;
  themeTokens?: CSSProperties;
  configurationPanel?: React.ComponentType<ConfigurationPanelProps>;
};
export type ConfigurationPanelProps = {
  recommendations?: React.ReactNode;
  logicEditor?: React.ReactNode;
  onOpenWorkflow?: (id: string) => void;
  environmentName?: string;
  referenceProviders?: Record<string, ReferenceProvider>;
  node: WorkflowNode;
  definition: NodeDefinition;
  graph: WorkflowGraph;
  catalog: NodeDefinition[];
  issues: Issue[];
  readOnly: boolean;
  onChange: (node: WorkflowNode) => void;
  onClose: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
};
export const categories = [
  "Triggers",
  "Actions",
  "Logic & Conditions",
  "Flow Control",
  "Data Transformation",
  "Scheduling",
  "Communication",
  "Approvals",
  "Connectors",
  "AI",
  "Utilities",
  "Error Handling",
];
export const categoryColors: Record<string, string> = {
  Triggers: "#8254d0",
  Actions: "#5089d6",
  "Logic & Conditions": "#d79c2f",
  "Flow Control": "#559f91",
  "Data Transformation": "#9b76ce",
  Scheduling: "#588fa8",
  Communication: "#c46494",
  Approvals: "#5b9d72",
  Connectors: "#6b88b7",
  AI: "#a064c6",
  Utilities: "#8b8a9e",
  "Error Handling": "#d66d72",
};

export type Analysis = {
  validation: ValidationResult;
  quality: { score: number; label: string; findings: Issue[] };
  documentation: string;
};
export type AIProposal = {
  summary: string;
  findings: string[];
  definition: WorkflowGraph | null;
  validation: ValidationResult | null;
  requires_approval: true;
};
export type AuthoringServices = {
  review: (
    definition: WorkflowGraph,
  ) => Promise<{ definition: WorkflowGraph; validation: ValidationResult }>;
  analyze: (document: WorkflowDocument, version: number) => Promise<Analysis>;
  propose: (
    prompt: string,
    mode: string,
    provider: string,
    definition: WorkflowGraph,
  ) => Promise<AIProposal>;
  mapping: (
    mapping: FieldMapping,
    context: Record<string, unknown>,
    node_type?: string,
    field?: string,
  ) => Promise<{ value: unknown }>;
  portable: (definition: WorkflowGraph) => Promise<{
    definition: WorkflowGraph;
    validation: ValidationResult;
    warnings: string[];
  }>;
  templates: () => Promise<AutomationTemplate[]>;
  blocks: () => Promise<Resource[]>;
  saveBlock: (
    document: WorkflowDocument,
    id?: number,
    version?: number,
  ) => Promise<Resource>;
  blockVersions: (id: number) => Promise<VersionSnapshot[]>;
  blockUsage: (
    id: number,
  ) => Promise<{ id: number; name: string; version: number }[]>;
  archiveBlock: (row: Resource) => Promise<Resource>;
  simulate: (
    definition: WorkflowGraph,
    input: Record<string, unknown>,
    synthetic: Record<string, unknown>,
    errors: string[],
  ) => Promise<PreviewResult>;
};
