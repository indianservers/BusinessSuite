import type {
  NodeDefinition,
  WorkflowGraph,
  WorkflowNode,
  WorkflowEdge,
  ValidationResult,
  Issue,
  Point,
} from "./types";
export const emptyGraph = (): WorkflowGraph => ({
  schema_version: 2,
  catalog_version: 1,
  nodes: [],
  edges: [],
  groups: [],
  viewport: { x: 0, y: 0, zoom: 1 },
  settings: {
    max_attempts: 3,
    retry_backoff_seconds: 60,
    idempotency: "request_id",
    execution_identity: "owner",
    timezone: "Asia/Kolkata",
    retention_days: 30,
  },
});
export const newId = (prefix = "node") =>
  `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
export function createNode(
  definition: NodeDefinition,
  position: Point,
): WorkflowNode {
  return {
    id: newId(definition.id),
    type: definition.id,
    label: definition.name,
    description: "",
    position: {
      x: Math.round(position.x / 20) * 20,
      y: Math.round(position.y / 20) * 20,
    },
    config: Object.fromEntries(
      definition.fields
        .filter((f) => f.default !== undefined)
        .map((f) => [f.key, structuredClone(f.default)]),
    ),
    credential_reference: null,
    advanced: {
      retry_attempts: 3,
      error_strategy: "stop",
      timeout_seconds: 60,
    },
  };
}
export function asVisualGraph(
  value: Record<string, unknown>,
  catalog: NodeDefinition[],
): WorkflowGraph {
  if (value.schema_version === 2)
    return structuredClone(value) as WorkflowGraph;
  const result = emptyGraph();
  const old = (value.nodes || []) as {
    id: string;
    type: string;
    component?: string;
    next?: string[];
    credential_reference?: string;
    delay_seconds?: number;
  }[];
  const triggerConfig = (value.trigger || {}) as {
    type?: string;
    event_name?: string;
    schedule?: string;
  };
  const def = catalog.find(
    (n) =>
      n.id ===
      ({
        event: "record_created",
        scheduled: "scheduled_trigger",
        webhook: "webhook_trigger",
      }[triggerConfig.type || ""] || "manual_trigger"),
  );
  if (!def) return result;
  const trigger = createNode(def, { x: 80, y: 220 });
  trigger.id = "trigger_legacy";
  while (old.some((n) => n.id === trigger.id)) trigger.id += "_1";
  if (triggerConfig.schedule) trigger.config.schedule = triggerConfig.schedule;
  if (triggerConfig.event_name) {
    trigger.description = `Imported event: ${triggerConfig.event_name}. Review the future adapter binding.`;
    if (def.id === "webhook_trigger")
      trigger.config.event_name = triggerConfig.event_name;
  }
  result.nodes.push(trigger);
  const used = new Set([trigger.id]),
    ids = new Map<string, string>();
  old.forEach((node) => {
    let id = /^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(node.id)
      ? node.id
      : `legacy_${node.id}`;
    id = id.slice(0, 80);
    const base = id.slice(0, 74);
    let suffix = 1;
    while (used.has(id)) id = `${base}_${suffix++}`;
    used.add(id);
    ids.set(node.id, id);
  });
  old.forEach((node, index) => {
    const type =
      catalog.find((n) => n.id === node.component) ||
      catalog.find(
        (n) =>
          n.id ===
          ({
            condition: "if_else",
            branch: "parallel_branch",
            delay: "delay",
            approval: "create_approval",
            webhook: "http_request",
          }[node.type] || "internal_service"),
      );
    if (!type) return;
    const mapped = createNode(type, { x: 420 + index * 320, y: 220 });
    mapped.id = ids.get(node.id)!;
    mapped.label = node.component || type.name;
    mapped.description =
      "Imported from schema v1. Review configuration and routes before saving.";
    mapped.credential_reference = node.credential_reference || null;
    if (type.id === "internal_service")
      mapped.config.service = node.component || "legacy.action";
    if (type.id === "delay" && node.delay_seconds !== undefined)
      mapped.config.seconds = node.delay_seconds;
    result.nodes.push(mapped);
    (node.next || []).forEach((target, i) => {
      const ports = type.outputs.filter((p) => p.id !== "error");
      const port = ports[Math.min(i, ports.length - 1)]?.id || "out";
      result.edges.push({
        id: newId("edge"),
        source: mapped.id,
        target: ids.get(target) || target,
        source_port: port,
        target_port: "in",
        label: "",
      });
    });
  });
  const entry = (value.entry as string | undefined) || old[0]?.id;
  if (entry)
    result.edges.unshift({
      id: newId("edge"),
      source: trigger.id,
      target: ids.get(entry) || entry,
      source_port: "out",
      target_port: "in",
      label: "",
    });
  result.settings.max_attempts =
    typeof value.max_attempts === "number"
      ? value.max_attempts
      : result.settings.max_attempts;
  result.settings.retry_backoff_seconds =
    typeof value.retry_backoff_seconds === "number"
      ? value.retry_backoff_seconds
      : result.settings.retry_backoff_seconds;
  result.settings.idempotency =
    value.idempotency === "event_id" ? "event_id" : "request_id";
  return result;
}
const token = /\{\{\s*([^{}]+?)\s*\}\}/g;
const pathPattern =
  /^(?:workflow\.variables\.[A-Za-z_][A-Za-z0-9_]*|env\.name|trigger\.(?:record|input)(?:\.[A-Za-z_][A-Za-z0-9_]*)*|steps\.[A-Za-z_][A-Za-z0-9_-]*\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$/;
export function expressionPaths(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(expressionPaths);
  if (value && typeof value === "object")
    return Object.entries(value).flatMap(([key, item]) => {
      const normalized = key.trim().toLowerCase().replace(/[- ]/g, "_");
      if (
        [
          "api_key",
          "apikey",
          "secret",
          "client_secret",
          "password",
          "access_token",
          "refresh_token",
          "authorization",
          "private_key",
          "token",
          "__proto__",
          "constructor",
          "prototype",
        ].includes(normalized) ||
        /_(?:api_key|secret|password|access_token)$/.test(normalized)
      )
        throw new Error(
          "Use credential references, not inline secrets or unsafe keys",
        );
      return expressionPaths(item);
    });
  if (typeof value !== "string") return [];
  const paths = [...value.matchAll(token)].map((m) => m[1].trim());
  if (
    paths.some(
      (p) =>
        !pathPattern.test(p) ||
        p
          .split(".")
          .some(
            (part) =>
              part.startsWith("__") ||
              ["constructor", "prototype"].includes(part),
          ),
    ) ||
    /\{\{|\}\}/.test(value.replace(token, ""))
  )
    throw new Error(
      "Use safe {{trigger.record.field}} or {{steps.node_id.output.field}} references",
    );
  return paths;
}
export function graphTopology(graph: WorkflowGraph) {
  const incoming = new Map(
    graph.nodes.map((n) => [n.id, [] as WorkflowEdge[]]),
  );
  const outgoing = new Map(
    graph.nodes.map((n) => [n.id, [] as WorkflowEdge[]]),
  );
  graph.edges.forEach((e) => {
    incoming.get(e.target)?.push(e);
    outgoing.get(e.source)?.push(e);
  });
  const degree = new Map(
    graph.nodes.map((n) => [n.id, incoming.get(n.id)!.length]),
  );
  const pending = graph.nodes.filter((n) => !degree.get(n.id)).map((n) => n.id);
  const order: string[] = [];
  for (let i = 0; i < pending.length; i++) {
    const id = pending[i];
    order.push(id);
    for (const edge of outgoing.get(id) || []) {
      degree.set(edge.target, degree.get(edge.target)! - 1);
      if (!degree.get(edge.target)) pending.push(edge.target);
    }
  }
  const ancestors = new Map<string, Set<string>>();
  order.forEach((id) => {
    const seen = new Set<string>();
    for (const edge of incoming.get(id) || []) {
      seen.add(edge.source);
      ancestors.get(edge.source)?.forEach((p) => seen.add(p));
    }
    ancestors.set(id, seen);
  });
  return { incoming, outgoing, order, ancestors };
}
export function connectionError(
  graph: WorkflowGraph,
  edge: WorkflowEdge,
  catalog: NodeDefinition[],
): string | null {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const source = nodeDefinition(nodes.get(edge.source), catalog),
    target = nodeDefinition(nodes.get(edge.target), catalog);
  const output = source?.outputs.find((p) => p.id === edge.source_port),
    input = target?.inputs.find((p) => p.id === edge.target_port);
  if (!output || !input || output.data_type !== input.data_type)
    return "These ports are incompatible";
  if (edge.source === edge.target)
    return "Use a bounded Loop node instead of a graph cycle";
  if (
    graph.edges.some(
      (e) =>
        e.source === edge.source &&
        e.target === edge.target &&
        e.source_port === edge.source_port &&
        e.target_port === edge.target_port,
    )
  )
    return "This connection already exists";
  if (
    graph.edges.filter(
      (e) => e.source === edge.source && e.source_port === edge.source_port,
    ).length >= output.max_connections ||
    graph.edges.filter(
      (e) => e.target === edge.target && e.target_port === edge.target_port,
    ).length >= input.max_connections
  )
    return "This port has reached its connection limit";
  if (
    graphTopology({ ...graph, edges: [...graph.edges, edge] }).order.length !==
    graph.nodes.length
  )
    return "Arbitrary cycles are not allowed. Use a bounded Loop node";
  return null;
}
export function validateGraph(
  graph: WorkflowGraph,
  catalog: NodeDefinition[],
): ValidationResult {
  const issues: Issue[] = [];
  const defs = new Map(catalog.map((d) => [d.id, d]));
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const { order, ancestors, outgoing } = graphTopology(graph);
  const add = (
    code: string,
    message: string,
    node_id?: string,
    field?: string,
    severity: "error" | "warning" = "error",
  ) => issues.push({ code, message, node_id, field, severity });
  const triggers = graph.nodes.filter((n) => defs.get(n.type)?.trigger);
  if (triggers.length !== 1)
    add("trigger_count", "Add exactly one trigger to this workflow");
  if (order.length !== graph.nodes.length)
    add("cycle", "Graph cycles are forbidden; use a bounded Loop node");
  if (nodes.size !== graph.nodes.length)
    add("duplicate", "Node IDs must be unique");
  graph.nodes.forEach((node) => {
    const def = defs.get(node.type);
    if (!def) {
      add("unsupported", "Unsupported node type", node.id);
      return;
    }
    if (
      triggers.length === 1 &&
      node.id !== triggers[0].id &&
      !ancestors.get(node.id)?.has(triggers[0].id)
    )
      add("disconnected", "Connect this node to the trigger", node.id);
    def.fields.forEach((field) => {
      if (
        node.mappings?.[field.key] ||
        (node.config.condition &&
          ["left", "right", "operator"].includes(field.key))
      )
        return;
      const value = node.config[field.key];
      if (
        field.required &&
        (value === undefined ||
          value === null ||
          value === "" ||
          (Array.isArray(value) && !value.length))
      )
        add("required", `${field.label} is required`, node.id, field.key);
      if (value === undefined || value === "" || value === null) return;
      if (
        field.allow_expression &&
        typeof value === "string" &&
        value.includes("{{")
      )
        return;
      if (
        field.kind === "number" &&
        (typeof value !== "number" ||
          !Number.isFinite(value) ||
          value < (field.minimum ?? -1e9) ||
          value > (field.maximum ?? 1e9))
      )
        add(
          "field",
          `Enter a valid ${field.label.toLowerCase()}`,
          node.id,
          field.key,
        );
      if (field.kind === "boolean" && typeof value !== "boolean")
        add(
          "field",
          `${field.label} must be true or false`,
          node.id,
          field.key,
        );
      if (
        field.kind === "json" &&
        (typeof value !== "object" || value === null)
      )
        add(
          "field",
          `${field.label} must be a JSON object or array`,
          node.id,
          field.key,
        );
      if (field.kind === "select" && !field.options?.includes(String(value)))
        add(
          "field",
          `Choose a valid ${field.label.toLowerCase()}`,
          node.id,
          field.key,
        );
      if (
        ["date", "datetime"].includes(field.kind) &&
        Number.isNaN(Date.parse(String(value)))
      )
        add("date", "Enter a valid date", node.id, field.key);
    });
    if (
      Object.keys(node.config).some(
        (key) => !def.fields.some((f) => f.key === key),
      )
    )
      add("field", "Unknown configuration field", node.id);
    if (def.requires_credential && !node.credential_reference)
      add(
        "credential",
        "A credential reference is required",
        node.id,
        "credential_reference",
      );
    try {
      expressionPaths({
        config: node.config,
        mappings: node.mappings || {},
      }).forEach((path) => {
        const parts = path.split(".");
        if (parts[0] === "steps") {
          if (!ancestors.get(node.id)?.has(parts[1]))
            add(
              "reference",
              "Variables must reference an upstream node",
              node.id,
            );
          else if (
            parts.length > 3 &&
            !defs.get(nodes.get(parts[1])!.type)?.output_schema[parts[3]]
          )
            add("output_field", `Unknown output field ${parts[3]}`, node.id);
        } else if (parts[0] === "workflow") {
          if (
            !Object.prototype.hasOwnProperty.call(
              graph.variables || {},
              parts[2],
            )
          )
            add("reference", "Unknown workflow variable", node.id);
        } else if (parts[0] === "env") {
          /* Only authorized environment name is available. */
        } else if (
          !triggers.length ||
          !ancestors.get(node.id)?.has(triggers[0].id)
        )
          add(
            "reference",
            "Trigger variables are only available downstream",
            node.id,
          );
      });
    } catch (error) {
      add("expression", (error as Error).message, node.id);
    }
    const required = ["if_else", "compare_values", "filter", "and_or"].includes(
      node.type,
    )
      ? ["true", "false"]
      : ["parallel_branch"].includes(node.type)
        ? ["route_1", "route_2"]
        : node.type === "switch"
          ? Array.isArray(node.config.routes) && node.config.routes.length
            ? [
                ...(node.config.routes as { id: string }[]).map((r) => r.id),
                "default",
              ]
            : ["route_1", "route_2", "default"]
          : ["loop", "for_each"].includes(node.type)
            ? ["body", "done"]
            : [];
    required.forEach((port) => {
      if (!outgoing.get(node.id)?.some((e) => e.source_port === port))
        add("branch", `Connect the ${port} branch`, node.id);
    });
    if (
      node.advanced.error_strategy === "branch" &&
      !outgoing.get(node.id)?.some((e) => e.source_port === "error")
    )
      add("error_branch", "Connect an error handler", node.id);
    if (!def.executable)
      add(
        "runtime_unavailable",
        "Not Executable Yet",
        node.id,
        undefined,
        "warning",
      );
  });
  const portCounts = new Map<string, number>();
  const seenEdges = new Set<string>();
  graph.edges.forEach((edge) => {
    const source = nodeDefinition(nodes.get(edge.source), catalog),
      target = nodeDefinition(nodes.get(edge.target), catalog);
    const out = source?.outputs.find((p) => p.id === edge.source_port),
      input = target?.inputs.find((p) => p.id === edge.target_port);
    if (!out || !input || out.data_type !== input.data_type) {
      add("connection", "Incompatible connection ports", edge.target);
      return;
    }
    const key = `${edge.source}:${edge.source_port}:${edge.target}:${edge.target_port}`;
    if (seenEdges.has(key))
      add("connection", "Duplicate connection", edge.target);
    seenEdges.add(key);
    [
      [`${edge.source}:out:${edge.source_port}`, out],
      [`${edge.target}:in:${edge.target_port}`, input],
    ].forEach(([id, port]) => {
      const k = id as string,
        p = port as typeof out;
      portCounts.set(k, (portCounts.get(k) || 0) + 1);
      if (portCounts.get(k)! > p!.max_connections)
        add("connection", "Port connection limit exceeded", edge.target);
    });
  });
  return {
    valid: !issues.some((i) => i.severity === "error"),
    executable: false,
    issues,
    node_count: graph.nodes.length,
    edge_count: graph.edges.length,
    catalog_version: 1,
  };
}
export function upstreamVariables(
  graph: WorkflowGraph,
  nodeId: string,
  catalog: NodeDefinition[],
): { expression: string; label: string; type: string }[] {
  const { ancestors } = graphTopology(graph);
  const upstream = ancestors.get(nodeId) || new Set<string>();
  const vars: { expression: string; label: string; type: string }[] = [
    { expression: "{{env.name}}", label: "Environment / name", type: "string" },
    ...Object.entries(graph.variables || {}).map(([name, value]) => ({
      expression: `{{workflow.variables.${name}}}`,
      label: `Workflow / ${name}`,
      type: typeof value,
    })),
  ];
  if (
    graph.nodes.some(
      (n) =>
        upstream.has(n.id) && catalog.find((d) => d.id === n.type)?.trigger,
    )
  )
    vars.push(
      ...["id", "status", "title", "name", "priority"].map((field) => ({
        expression: `{{trigger.record.${field}}}`,
        label: `Trigger record / ${field}`,
        type: "dynamic",
      })),
    );
  graph.nodes
    .filter(
      (n) =>
        upstream.has(n.id) && !catalog.find((d) => d.id === n.type)?.trigger,
    )
    .forEach((node) => {
      const def = catalog.find((d) => d.id === node.type);
      Object.entries(def?.output_schema || {}).forEach(([field, type]) =>
        vars.push({
          expression: `{{steps.${node.id}.output.${field}}}`,
          label: `${node.label} / ${field}`,
          type,
        }),
      );
    });
  return vars;
}
export function autoLayout(graph: WorkflowGraph): WorkflowGraph {
  const { order, incoming } = graphTopology(graph);
  const level = new Map<string, number>();
  const row = new Map<number, number>();
  const positions = new Map<string, Point>();
  order.forEach((id) => {
    const depth = Math.max(
      0,
      ...(incoming.get(id) || []).map((e) => (level.get(e.source) || 0) + 1),
    );
    level.set(id, depth);
    const r = row.get(depth) || 0;
    row.set(depth, r + 1);
    positions.set(id, { x: 100 + depth * 340, y: 160 + r * 210 });
  });
  return {
    ...graph,
    nodes: graph.nodes.map((n) => ({
      ...n,
      position: positions.get(n.id) || n.position,
    })),
    groups: [],
  };
}
export function copySubgraph(graph: WorkflowGraph, selected: Set<string>) {
  const expanded = new Set(selected);
  graph.groups
    .filter((g) => selected.has(g.id))
    .forEach((g) => g.node_ids.forEach((id) => expanded.add(id)));
  return {
    block_references: structuredClone(
      (graph.block_references || []).filter((ref) =>
        ref.node_ids.every((id) => expanded.has(id)),
      ),
    ),
    groups: structuredClone(graph.groups.filter((g) => selected.has(g.id))),
    annotations: structuredClone(
      (graph.annotations || []).filter((n) => selected.has(n.id)),
    ),
    nodes: structuredClone(graph.nodes.filter((n) => expanded.has(n.id))),
    edges: structuredClone(
      graph.edges.filter(
        (e) => expanded.has(e.source) && expanded.has(e.target),
      ),
    ),
  };
}
export function pasteSubgraph(
  graph: WorkflowGraph,
  clipboard: ReturnType<typeof copySubgraph>,
) {
  const ids = new Map(clipboard.nodes.map((n) => [n.id, newId(n.type)]));
  const remap = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(remap);
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value).map(([k, v]) => [k, remap(v)]),
      );
    if (typeof value === "string")
      return value.replace(
        /\{\{(\s*)steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output([^{}]*?)\}\}/g,
        (whole, space, id, suffix) =>
          ids.has(id)
            ? `{{${space}steps.${ids.get(id)}.output${suffix}}}`
            : whole,
      );
    return value;
  };
  const nodes = clipboard.nodes.map((n) => ({
    ...structuredClone(n),
    id: ids.get(n.id)!,
    position: { x: n.position.x + 60, y: n.position.y + 60 },
    config: remap(n.config) as Record<string, unknown>,
    mappings: remap(n.mappings || {}) as WorkflowNode["mappings"],
  }));
  const groups = (clipboard.groups || []).map((g) => ({
    ...g,
    id: newId("group"),
    node_ids: g.node_ids.map((id) => ids.get(id)!),
    position: { x: g.position.x + 60, y: g.position.y + 60 },
  }));
  const annotations = (clipboard.annotations || []).map((n) => ({
    ...n,
    id: newId("note"),
    position: { x: n.position.x + 60, y: n.position.y + 60 },
  }));
  const edges = clipboard.edges.map((e) => ({
    ...e,
    id: newId("edge"),
    source: ids.get(e.source)!,
    target: ids.get(e.target)!,
  }));
  return {
    graph: {
      ...graph,
      nodes: [...graph.nodes, ...nodes],
      block_references: [
        ...(graph.block_references || []),
        ...(clipboard.block_references || []).map((ref) => ({
          ...ref,
          node_ids: ref.node_ids.map((id) => ids.get(id)!),
        })),
      ],
      groups: [...graph.groups, ...groups],
      annotations: [...(graph.annotations || []), ...annotations],
      edges: [...graph.edges, ...edges],
    },
    selected: new Set([
      ...nodes.map((n) => n.id),
      ...groups.map((g) => g.id),
      ...annotations.map((n) => n.id),
    ]),
  };
}
export function compareVersions(
  left: {
    definition: Record<string, unknown>;
    name: string;
    description: string;
  },
  right: {
    definition: Record<string, unknown>;
    name: string;
    description: string;
  },
) {
  const a = new Map(
    ((left.definition.nodes || []) as WorkflowNode[]).map((n) => [n.id, n]),
  );
  const b = new Map(
    ((right.definition.nodes || []) as WorkflowNode[]).map((n) => [n.id, n]),
  );
  return {
    added: [...b.values()]
      .filter((n) => !a.has(n.id))
      .map((n) => n.label || n.id),
    removed: [...a.values()]
      .filter((n) => !b.has(n.id))
      .map((n) => n.label || n.id),
    changed: [...b.values()]
      .filter(
        (n) => a.has(n.id) && JSON.stringify(a.get(n.id)) !== JSON.stringify(n),
      )
      .map((n) => n.label || n.id),
    connectionsChanged:
      JSON.stringify(left.definition.edges || []) !==
      JSON.stringify(right.definition.edges || []),
    organizationChanged: [
      "groups",
      "annotations",
      "tags",
      "variables",
      "editor",
    ].some(
      (key) =>
        JSON.stringify(left.definition[key]) !==
        JSON.stringify(right.definition[key]),
    ),
    nameChanged: left.name !== right.name,
    descriptionChanged: left.description !== right.description,
    settingsChanged:
      JSON.stringify(left.definition.settings) !==
      JSON.stringify(right.definition.settings),
  };
}

export function nodeDefinition(
  node: WorkflowNode | undefined,
  catalog: NodeDefinition[],
): NodeDefinition | undefined {
  const base = catalog.find((d) => d.id === node?.type);
  if (!base || !node) return base;
  if (
    node.type === "switch" &&
    Array.isArray(node.config.routes) &&
    node.config.routes.length
  )
    return {
      ...base,
      outputs: [
        ...(node.config.routes as { id: string; label: string }[]).map((r) => ({
          id: r.id,
          label: r.label,
          data_type: "flow",
          max_connections: 20,
        })),
        ...base.outputs.filter((p) => ["default", "error"].includes(p.id)),
      ],
    };
  return base;
}

export function appendRecommendation(
  graph: WorkflowGraph,
  source: WorkflowNode,
  definition: NodeDefinition,
  catalog: NodeDefinition[],
  port?: string,
) {
  if (graph.nodes.length >= 500) throw new Error("Workflow node limit reached");
  const node = createNode(definition, {
    x: source.position.x + 340,
    y: source.position.y + 200,
  });
  const sourcePort =
    port ||
    nodeDefinition(source, catalog)?.outputs.find((p) => p.id !== "error")
      ?.id ||
    "out";
  const next = { ...graph, nodes: [...graph.nodes, node] };
  const edges = definition.inputs
    .map((input) => ({
      id: newId("edge"),
      source: source.id,
      target: node.id,
      source_port: sourcePort,
      target_port: input.id,
      label: "",
      style: graph.editor?.connection_style || ("bezier" as const),
    }))
    .filter((edge) => !connectionError(next, edge, catalog));
  if (edges.length !== 1)
    throw new Error(
      "Choose an available compatible output and an unambiguous destination",
    );
  return { graph: { ...next, edges: [...graph.edges, edges[0]] }, node };
}

/** Only functional graph content determines whether a simulation response is stale. */
export function executionSignature(graph: WorkflowGraph) {
  return JSON.stringify({
    nodes: graph.nodes.map((node) => ({ ...node, position: undefined })),
    edges: graph.edges.map((edge) => ({
      ...edge,
      style: undefined,
      label: undefined,
    })),
    settings: graph.settings,
    variables: graph.variables,
  });
}
