import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  MarkerType,
  SelectionMode,
  useReactFlow,
  type Connection,
  type Node,
  type NodeChange,
  type EdgeChange,
  ConnectionLineType,
  type NodeProps,
} from "@xyflow/react";
import {
  ArrowLeft,
  Braces,
  CircleAlert,
  Copy,
  Download,
  Expand,
  GitBranch,
  Grid2X2,
  Group,
  History,
  Layers3,
  LayoutDashboard,
  LayoutGrid,
  LockKeyhole,
  MoreHorizontal,
  MousePointer2,
  PanelRightClose,
  Play,
  Plus,
  Redo2,
  Save,
  Sparkles,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  Undo2,
  Ungroup,
  Workflow,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  AutomationCanvas,
  WorkflowMinimap,
  WorkflowToolbar,
  WorkflowBreadcrumbs,
} from "./WorkflowPrimitives";
import { IntelligentStudio } from "./IntelligencePanels";
import { NodeRecommendationPanel } from "./NodeRecommendationPanel";
import { LogicEditor } from "./LogicEditors";
import { WorkflowSearch } from "./WorkflowSearch";
import { NodeGroup, WorkflowAnnotation } from "./NodeGroup";
import { ConnectionEditor } from "./ConnectionEditor";
import { StudioNode, type CanvasNode } from "./StudioNode";
import { StudioEdge } from "./StudioEdge";
import { NodeLibrary } from "./NodeLibrary";
import { useDocument } from "./useDocument";
import { useDraftPersistence } from "./useDraftPersistence";
import {
  nodeDefinition,
  appendRecommendation,
  autoLayout,
  connectionError,
  copySubgraph,
  createNode,
  newId,
  pasteSubgraph,
  validateGraph,
} from "./graph";
import {
  PreviewPanel,
  SettingsPanel,
  ValidationPanel,
  VersionsPanel,
} from "./StudioPanels";
import {
  categoryColors,
  type AutomationBuilderProps,
  type NodeDefinition,
  type PreviewResult,
  type ValidationResult,
  type WorkflowEdge,
  type WorkflowGraph,
} from "./types";
import { errorMessage } from "../../../api";
import "@xyflow/react/dist/style.css";
import "./studio.css";
const validationSignature = (graph: WorkflowGraph) =>
  JSON.stringify({
    nodes: graph.nodes,
    edges: graph.edges,
    settings: graph.settings,
    variables: graph.variables,
  });
const ConfigurationPanel = lazy(() => import("./ConfigurationPanel"));
const nodeTypes = {
  studio: StudioNode,
  group: NodeGroup,
  annotation: WorkflowAnnotation,
};
const edgeTypes = { studio: StudioEdge };
/** Standalone editor: persistence, authorization, catalog and validation are injected. */
export function AutomationBuilder(props: AutomationBuilderProps) {
  return (
    <ReactFlowProvider>
      <BuilderCanvas {...props} />
    </ReactFlowProvider>
  );
}
function BuilderCanvas(props: AutomationBuilderProps) {
  const { document, update, undo, redo, checkpoint, canUndo, canRedo } =
    useDocument(props.initialDocument);
  const graph = document.definition;
  const readonly =
    props.mode === "read-only" ||
    !(props.workflowId ? props.permissions.edit : props.permissions.create);
  const flow = useReactFlow();
  const root = useRef<HTMLDivElement>(null);
  const reconnectingId = useRef<string | null>(null);
  const docRef = useRef(document);
  docRef.current = document;
  const [dragging, setDragging] = useState(false);
  const persistence = useDraftPersistence(document, {
    key: props.recoveryKey,
    version: props.version,
    savedAt: props.savedAt,
    exists: Boolean(props.workflowId),
    readOnly: readonly,
    paused: dragging,
    onSave: props.onSave,
    onSaved: props.onSaved,
  });
  const [libraryOpen, setLibraryOpen] = useState(
      () => window.innerWidth >= 1100,
    ),
    [picker, setPicker] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set()),
    [selectedEdges, setSelectedEdges] = useState<Set<string>>(new Set());
  const [inspectedId, setInspectedId] = useState<string | null>(null),
    [inspectorOpen, setInspectorOpen] = useState(
      () => window.innerWidth >= 900,
    );
  const [context, setContext] = useState<{
    id: string;
    x: number;
    y: number;
  } | null>(null);
  const [pendingSource, setPendingSource] = useState<{
    id: string;
    port: string;
  } | null>(null);
  const [authoringTab, setAuthoringTab] = useState<string | null>(null);
  const [simulation, setSimulation] = useState<PreviewResult>();
  const [searchOpen, setSearchOpen] = useState(false);
  const [pendingEdge, setPendingEdge] = useState<string | null>(null);
  const [viewExpandedGroups, setViewExpandedGroups] = useState<Set<string>>(
    new Set(),
  );
  const isCollapsed = useCallback(
    (group: WorkflowGraph["groups"][number]) =>
      Boolean(group.collapsed && !viewExpandedGroups.has(group.id)),
    [viewExpandedGroups],
  );
  const [guides, setGuides] = useState<{ x?: number; y?: number }>({});
  const [notice, setNotice] = useState("");
  const [showGrid, setShowGrid] = useState(true);
  const [zoom, setZoom] = useState(graph.viewport.zoom);
  const [panel, setPanel] = useState<
    "validation" | "versions" | "settings" | null
  >(props.externalPanel || null);
  const [remoteValidation, setRemoteValidation] =
      useState<ValidationResult | null>(null),
    [validating, setValidating] = useState(false);
  const [showTesting, setShowTesting] = useState(false),
    [testInput, setTestInput] = useState('{"record":{}}'),
    [preview, setPreview] = useState<PreviewResult>(),
    [previewBusy, setPreviewBusy] = useState(false),
    [previewError, setPreviewError] = useState("");
  const [panelWidth, setPanelWidth] = useState(326);
  const resizeAbort = useRef<AbortController>();
  const [shortcuts, setShortcuts] = useState(false);
  const [copying, setCopying] = useState(false);
  const clipboard = useRef<ReturnType<typeof copySubgraph> | null>(null);
  const [clipboardReady, setClipboardReady] = useState(false);
  const localValidation = useMemo(
    () => validateGraph(graph, props.nodeCatalog),
    [
      graph.nodes,
      graph.edges,
      graph.settings,
      graph.variables,
      props.nodeCatalog,
    ],
  );
  const validation = remoteValidation || localValidation;
  const errorCounts = useMemo(() => {
    const counts = new Map<string, number>();
    validation.issues
      .filter((i) => i.severity === "error" && i.node_id)
      .forEach((i) =>
        counts.set(i.node_id!, (counts.get(i.node_id!) || 0) + 1),
      );
    return counts;
  }, [validation]);
  const catalogMap = useMemo(
    () => new Map(props.nodeCatalog.map((n) => [n.id, n])),
    [props.nodeCatalog],
  );
  const inspected = graph.nodes.find((n) => n.id === inspectedId);
  useEffect(() => {
    setPanel(props.externalPanel || null);
  }, [props.externalPanel]);
  useEffect(() => {
    setRemoteValidation(null);
    setPreview(undefined);
    setSimulation(undefined);
  }, [graph.nodes, graph.edges, graph.settings, graph.variables]);
  useEffect(() => {
    const timer = window.setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => () => resizeAbort.current?.abort(), []);
  const changeGraph = useCallback(
    (recipe: (current: WorkflowGraph) => WorkflowGraph, history = true) => {
      if (readonly) return;
      update(
        (current) => ({ ...current, definition: recipe(current.definition) }),
        history,
      );
    },
    [readonly, update],
  );
  const inspect = useCallback((id: string) => {
    setInspectedId(id);
    setSelected(new Set([id]));
    setInspectorOpen(true);
    setPanel(null);
  }, []);
  const openMenu = useCallback((id: string, x: number, y: number) => {
    setContext({
      id,
      x: Math.min(x, window.innerWidth - 205),
      y: Math.min(y, window.innerHeight - 270),
    });
    setSelected((current) => (current.has(id) ? current : new Set([id])));
  }, []);
  const addAfter = useCallback((id: string, port: string) => {
    setPendingEdge(null);
    setPendingSource({ id, port });
    setPicker(true);
  }, []);
  const focusNode = useCallback(
    (id: string) => {
      const group = docRef.current.definition.groups.find((g) =>
        g.node_ids.includes(id),
      );
      if (group && isCollapsed(group) && readonly)
        setViewExpandedGroups((current) => new Set([...current, group.id]));
      if (group && isCollapsed(group) && !readonly)
        changeGraph((current) => ({
          ...current,
          groups: current.groups.map((g) =>
            g.id === group.id ? { ...g, collapsed: false } : g,
          ),
        }));
      inspect(id);
      const node = docRef.current.definition.nodes.find((n) => n.id === id);
      if (node)
        void flow.setCenter(node.position.x + 110, node.position.y + 80, {
          zoom: 1,
          duration: 250,
        });
    },
    [inspect, flow, changeGraph, isCollapsed, readonly],
  );
  const toggleGroup = useCallback(
    (id: string) => {
      if (readonly) {
        setViewExpandedGroups((current) => {
          const next = new Set(current);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        });
        return;
      }
      const group = docRef.current.definition.groups.find((g) => g.id === id);
      if (group && !group.collapsed)
        void flow.setCenter(group.position.x + 130, group.position.y + 32, {
          zoom: 1,
          duration: 0,
        });
      changeGraph((current) => ({
        ...current,
        groups: current.groups.map((g) =>
          g.id === id ? { ...g, collapsed: !g.collapsed } : g,
        ),
      }));
    },
    [changeGraph, readonly, flow],
  );
  const flowNodes = useMemo<Node[]>(() => {
    const groups = graph.groups.map((group) => ({
      id: group.id,
      type: "group",
      width: isCollapsed(group) ? 260 : group.width,
      height: isCollapsed(group) ? 64 : group.height,
      position: group.position,
      data: {
        label: group.label,
        collapsed: isCollapsed(group),
        count: group.node_ids.length,
        onToggle: () => toggleGroup(group.id),
      },
      style: {
        width: isCollapsed(group) ? 260 : group.width,
        height: isCollapsed(group) ? 64 : group.height,
      },
      selected: selected.has(group.id),
      draggable: !readonly,
      selectable: true,
    }));
    const children = graph.nodes
      .map((node) => {
        const definition = nodeDefinition(node, props.nodeCatalog);
        if (!definition) return null;
        const group = graph.groups.find((g) => g.node_ids.includes(node.id));
        return {
          id: node.id,
          type: "studio",
          width: 220,
          height: Math.max(
            160,
            definition.outputs.filter((p) => p.id !== "error").length * 28 + 48,
          ),
          position: group
            ? {
                x: node.position.x - group.position.x,
                y: node.position.y - group.position.y,
              }
            : node.position,
          ...(group ? { parentId: group.id } : {}),
          hidden: Boolean(group && isCollapsed(group)),
          selected: selected.has(node.id),
          draggable: !readonly,
          data: {
            node,
            definition,
            errors: errorCounts.get(node.id) || 0,
            readOnly: readonly,
            simulation: simulation?.timeline.find((e) => e.node_id === node.id)
              ?.status,
            onMenu: openMenu,
            onAdd: addAfter,
          },
          ariaLabel: `${node.label}, ${definition.name}, Not Executable Yet`,
        } as CanvasNode;
      })
      .filter(Boolean) as CanvasNode[];
    const notes = (graph.annotations || []).map((note) => ({
      id: note.id,
      type: "annotation",
      position: note.position,
      width: note.width,
      data: { text: note.text, kind: note.kind },
      style: { width: note.width },
      selected: selected.has(note.id),
      draggable: !readonly,
    }));
    return [...groups, ...children, ...notes];
  }, [
    graph.nodes,
    graph.groups,
    graph.annotations,
    simulation,
    props.nodeCatalog,
    toggleGroup,
    isCollapsed,
    selected,
    catalogMap,
    errorCounts,
    readonly,
    openMenu,
    addAfter,
  ]);
  const onSelectionChange = useCallback(
    ({ nodes, edges }: { nodes: Node[]; edges: { id: string }[] }) => {
      const ids = new Set(nodes.map((n) => n.id)),
        edgeIds = new Set(edges.map((e) => e.id));
      setSelected((previous) =>
        previous.size === ids.size && [...previous].every((id) => ids.has(id))
          ? previous
          : ids,
      );
      setSelectedEdges((previous) =>
        previous.size === edgeIds.size &&
        [...previous].every((id) => edgeIds.has(id))
          ? previous
          : edgeIds,
      );
    },
    [],
  );
  const flowEdges = useMemo(
    () =>
      graph.edges.map((edge) => {
        const source = graph.nodes.find((n) => n.id === edge.source);
        const definition = nodeDefinition(source, props.nodeCatalog);
        const color =
          edge.source_port === "error"
            ? "#d66d72"
            : categoryColors[definition?.category || "Triggers"];
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.source_port,
          targetHandle: edge.target_port,
          type: "studio",
          hidden: graph.groups.some(
            (g) =>
              isCollapsed(g) &&
              (g.node_ids.includes(edge.source) ||
                g.node_ids.includes(edge.target)),
          ),
          data: {
            routing: edge.style || "bezier",
            highlighted:
              selected.has(edge.source) ||
              selected.has(edge.target) ||
              Boolean(
                simulation?.timeline
                  .find((entry) => entry.node_id === edge.source)
                  ?.active_ports?.includes(edge.source_port),
              ),
            onInsert: () => {
              setPendingEdge(edge.id);
              setPendingSource(null);
              setPicker(true);
            },
            readOnly: readonly,
          },
          label:
            edge.label ||
            (edge.source_port === "out"
              ? ""
              : definition?.outputs.find((p) => p.id === edge.source_port)
                  ?.label || edge.source_port),
          selected: selectedEdges.has(edge.id),
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 15,
            height: 15,
            color,
          },
          style: { stroke: color },
          interactionWidth: 22,
        };
      }),
    [
      graph.nodes,
      graph.edges,
      graph.groups,
      graph.editor,
      simulation,
      isCollapsed,
      catalogMap,
      selectedEdges,
      selected,
      readonly,
    ],
  );
  const connect = useCallback(
    (connection: Connection) => {
      if (readonly) return;
      const edge: WorkflowEdge = {
        id: newId("edge"),
        style: docRef.current.definition.editor?.connection_style || "bezier",
        source: connection.source,
        target: connection.target,
        source_port: connection.sourceHandle || "out",
        target_port: connection.targetHandle || "in",
        label: "",
      };
      const reason = connectionError(
        docRef.current.definition,
        edge,
        props.nodeCatalog,
      );
      if (reason) {
        setNotice(reason);
        return;
      }
      changeGraph((current) => ({
        ...current,
        edges: [...current.edges, edge],
      }));
    },
    [readonly, props.nodeCatalog, changeGraph],
  );
  const addNode = useCallback(
    (definition: NodeDefinition, position?: { x: number; y: number }) => {
      if (readonly) return;
      if (docRef.current.definition.nodes.length >= 500) {
        setNotice("This editor supports up to 500 nodes per workflow");
        return;
      }
      const insertEdge =
        pendingEdge && picker && !position
          ? docRef.current.definition.edges.find((e) => e.id === pendingEdge)
          : undefined;
      if (insertEdge) {
        const current = docRef.current.definition;
        const from = current.nodes.find((n) => n.id === insertEdge.source)!,
          to = current.nodes.find((n) => n.id === insertEdge.target)!;
        const node = createNode(definition, {
          x: (from.position.x + to.position.x) / 2,
          y: (from.position.y + to.position.y) / 2 + 100,
        });
        const candidates: WorkflowEdge[][] = [];
        for (const input of definition.inputs)
          for (const output of definition.outputs.filter(
            (p) => p.id !== "error",
          )) {
            const first = {
              ...insertEdge,
              id: newId("edge"),
              target: node.id,
              target_port: input.id,
            };
            const second = {
              ...insertEdge,
              id: newId("edge"),
              source: node.id,
              source_port: output.id,
              label: "",
            };
            const next = {
              ...current,
              nodes: [...current.nodes, node],
              edges: current.edges.filter((e) => e.id !== insertEdge.id),
            };
            if (
              !connectionError(next, first, props.nodeCatalog) &&
              !connectionError(
                { ...next, edges: [...next.edges, first] },
                second,
                props.nodeCatalog,
              )
            )
              candidates.push([first, second]);
          }
        if (candidates.length !== 1) {
          setNotice(
            candidates.length
              ? "Ambiguous ports: add this node separately and connect explicit branches."
              : "No compatible insertion. The original connection is unchanged.",
          );
          return;
        }
        changeGraph((c) => ({
          ...c,
          nodes: [...c.nodes, node],
          edges: [
            ...c.edges.filter((e) => e.id !== insertEdge.id),
            ...candidates[0],
          ],
        }));
        setPendingEdge(null);
        setPicker(false);
        inspect(node.id);
        return;
      }
      const source =
        !position &&
        pendingSource &&
        docRef.current.definition.nodes.find((n) => n.id === pendingSource.id);
      const bounds = root.current
        ?.querySelector(".as-canvas")
        ?.getBoundingClientRect();
      const center =
        position ||
        (source
          ? {
              x: source.position.x + 340,
              y:
                source.position.y + (pendingSource?.port === "false" ? 210 : 0),
            }
          : flow.screenToFlowPosition({
              x: (bounds?.left || 0) + (bounds?.width || 800) / 2 - 110,
              y: (bounds?.top || 0) + (bounds?.height || 600) / 2 - 70,
            }));
      if (!position && !source) {
        let attempts = 0;
        while (
          docRef.current.definition.nodes.some(
            (n) =>
              Math.abs(n.position.x - center.x) < 250 &&
              Math.abs(n.position.y - center.y) < 185,
          ) &&
          attempts++ < 500
        )
          center.y += 200;
      }
      const node = createNode(definition, center);
      if (source && pendingSource) {
        const candidates = definition.inputs.filter(
          (input) =>
            !connectionError(
              {
                ...docRef.current.definition,
                nodes: [...docRef.current.definition.nodes, node],
              },
              {
                id: "pending",
                source: source.id,
                target: node.id,
                source_port: pendingSource.port,
                target_port: input.id,
                label: "",
              },
              props.nodeCatalog,
            ),
        );
        if (candidates.length !== 1) {
          setNotice(
            "No unambiguous compatible input. Choose another node or connect ports manually.",
          );
          return;
        }
      }
      changeGraph((current) => {
        let next = { ...current, nodes: [...current.nodes, node] };
        if (source && pendingSource && definition.inputs[0]) {
          const edge: WorkflowEdge = {
            id: newId("edge"),
            style: next.editor?.connection_style || "bezier",
            source: source.id,
            target: node.id,
            source_port: pendingSource.port,
            target_port: definition.inputs.find(
              (input) =>
                !connectionError(
                  next,
                  {
                    id: "pending",
                    source: source.id,
                    target: node.id,
                    source_port: pendingSource.port,
                    target_port: input.id,
                    label: "",
                  },
                  props.nodeCatalog,
                ),
            )!.id,
            label: "",
          };
          const reason = connectionError(next, edge, props.nodeCatalog);
          if (!reason) next = { ...next, edges: [...next.edges, edge] };
        }
        return next;
      });
      inspect(node.id);
      setPendingSource(null);
      setPicker(false);
    },
    [
      readonly,
      pendingSource,
      pendingEdge,
      picker,
      changeGraph,
      flow,
      inspect,
      props.nodeCatalog,
    ],
  );
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const positions = changes.filter(
        (change): change is Extract<NodeChange, { type: "position" }> =>
          change.type === "position" && Boolean(change.position),
      );
      if (!positions.length || readonly) return;
      changeGraph((current) => {
        const groups = current.groups.map((g) => {
          const change = positions.find((c) => c.id === g.id);
          return change?.position ? { ...g, position: change.position } : g;
        });
        const nodes = current.nodes.map((node) => {
          const change = positions.find((c) => c.id === node.id);
          const oldGroup = current.groups.find((g) =>
            g.node_ids.includes(node.id),
          );
          const group = oldGroup && groups.find((g) => g.id === oldGroup.id);
          if (change?.position)
            return {
              ...node,
              position: group
                ? {
                    x: change.position.x + group.position.x,
                    y: change.position.y + group.position.y,
                  }
                : change.position,
            };
          if (group && oldGroup && group !== oldGroup)
            return {
              ...node,
              position: {
                x: node.position.x + group.position.x - oldGroup.position.x,
                y: node.position.y + group.position.y - oldGroup.position.y,
              },
            };
          return node;
        });
        const annotations = (current.annotations || []).map((note) => {
          const change = positions.find((c) => c.id === note.id);
          return change?.position
            ? { ...note, position: change.position }
            : note;
        });
        return { ...current, nodes, groups, annotations };
      }, false);
    },
    [changeGraph, readonly],
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      if (readonly) return;
      const removed = new Set(
        changes.filter((c) => c.type === "remove").map((c) => c.id),
      );
      if (removed.size)
        changeGraph((current) => ({
          ...current,
          edges: current.edges.filter((e) => !removed.has(e.id)),
        }));
    },
    [changeGraph, readonly],
  );
  const deleteSelection = useCallback(
    (ids = selected) => {
      if (readonly) return;
      const expanded = new Set(ids);
      graph.groups
        .filter((g) => ids.has(g.id))
        .forEach((g) => g.node_ids.forEach((id) => expanded.add(id)));
      const count =
        graph.nodes.filter((n) => expanded.has(n.id)).length +
        (graph.annotations || []).filter((n) => expanded.has(n.id)).length;
      if (!count && !selectedEdges.size) return;
      if (
        !window.confirm(
          `Delete ${count ? `${count} selected node${count === 1 ? "" : "s"} and their connections` : "the selected connections"}?`,
        )
      )
        return;
      changeGraph((current) => ({
        ...current,
        annotations: (current.annotations || []).filter(
          (n) => !expanded.has(n.id),
        ),
        block_references: (current.block_references || [])
          .map((ref) => ({
            ...ref,
            node_ids: ref.node_ids.filter((id) => !expanded.has(id)),
          }))
          .filter((ref) => ref.node_ids.length),
        block_contract: current.block_contract
          ? {
              inputs: current.block_contract.inputs.filter(
                (p) => !expanded.has(p.node_id),
              ),
              outputs: current.block_contract.outputs.filter(
                (p) => !expanded.has(p.node_id),
              ),
            }
          : null,
        nodes: current.nodes.filter((n) => !expanded.has(n.id)),
        edges: current.edges.filter(
          (e) =>
            !expanded.has(e.source) &&
            !expanded.has(e.target) &&
            !selectedEdges.has(e.id),
        ),
        groups: current.groups
          .filter((g) => !ids.has(g.id))
          .map((g) => ({
            ...g,
            node_ids: g.node_ids.filter((id) => !expanded.has(id)),
          }))
          .filter((g) => g.node_ids.length),
      }));
      setSelected(new Set());
      setSelectedEdges(new Set());
      if (inspectedId && expanded.has(inspectedId)) setInspectedId(null);
      setContext(null);
    },
    [
      readonly,
      selected,
      selectedEdges,
      graph.groups,
      graph.nodes,
      graph.annotations,
      inspectedId,
      changeGraph,
    ],
  );
  const copyNodes = useCallback(
    (ids = selected) => {
      const copied = copySubgraph(docRef.current.definition, ids);
      if (!copied.nodes.length && !copied.annotations.length) return;
      clipboard.current = copied;
      setClipboardReady(true);
      setNotice(
        `Copied ${copied.nodes.length} nodes and ${copied.annotations.length} annotations inside this editor`,
      );
    },
    [selected],
  );
  const pasteNodes = useCallback(() => {
    if (
      readonly ||
      !clipboard.current ||
      (!clipboard.current.nodes.length && !clipboard.current.annotations.length)
    )
      return;
    if (
      graph.nodes.length + clipboard.current.nodes.length > 500 ||
      graph.groups.length + clipboard.current.groups.length > 100 ||
      (graph.annotations || []).length + clipboard.current.annotations.length >
        100 ||
      graph.edges.length + clipboard.current.edges.length > 1500
    ) {
      setNotice(
        "Pasting would exceed workflow size limits (500 nodes, 100 groups, 100 notes, 1500 connections)",
      );
      return;
    }
    const pasted = pasteSubgraph(docRef.current.definition, clipboard.current);
    changeGraph(() => pasted.graph);
    setSelected(pasted.selected);
  }, [
    readonly,
    graph.nodes.length,
    graph.groups.length,
    graph.annotations,
    graph.edges.length,
    changeGraph,
  ]);
  const duplicateNodes = useCallback(
    (ids = selected) => {
      if (readonly) return;
      const copied = copySubgraph(docRef.current.definition, ids);
      if (
        (!copied.nodes.length && !copied.annotations.length) ||
        graph.nodes.length + copied.nodes.length > 500 ||
        graph.groups.length + copied.groups.length > 100 ||
        (graph.annotations || []).length + copied.annotations.length > 100 ||
        graph.edges.length + copied.edges.length > 1500
      )
        return;
      const pasted = pasteSubgraph(docRef.current.definition, copied);
      changeGraph(() => pasted.graph);
      setSelected(pasted.selected);
      setContext(null);
    },
    [
      readonly,
      selected,
      graph.nodes.length,
      graph.groups.length,
      graph.annotations,
      graph.edges.length,
      changeGraph,
    ],
  );
  const groupSelection = useCallback(() => {
    if (readonly) return;
    const nodes = graph.nodes.filter((n) => selected.has(n.id));
    if (nodes.length < 2) {
      setNotice("Select at least two nodes to group them");
      return;
    }
    const x = Math.min(...nodes.map((n) => n.position.x)) - 30,
      y = Math.min(...nodes.map((n) => n.position.y)) - 48;
    const group = {
      id: newId("group"),
      label: "Group",
      node_ids: nodes.map((n) => n.id),
      position: { x, y },
      width: Math.max(...nodes.map((n) => n.position.x)) - x + 250,
      height: Math.max(...nodes.map((n) => n.position.y)) - y + 180,
    };
    changeGraph((current) => ({
      ...current,
      groups: [
        ...current.groups
          .map((g) => ({
            ...g,
            node_ids: g.node_ids.filter((id) => !selected.has(id)),
          }))
          .filter((g) => g.node_ids.length),
        group,
      ],
    }));
    setSelected(new Set([group.id]));
    setContext(null);
  }, [readonly, graph.nodes, selected, changeGraph]);
  const ungroup = useCallback(
    () =>
      changeGraph((current) => ({
        ...current,
        groups: current.groups.filter(
          (g) =>
            !selected.has(g.id) && !g.node_ids.some((id) => selected.has(id)),
        ),
      })),
    [selected, changeGraph],
  );
  const save = useCallback(() => {
    if (persistence.status === "conflict") {
      setNotice("Resolve the conflict by saving a separate copy or reloading");
      return;
    }
    void persistence.flush(persistence.status === "error");
  }, [persistence]);
  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPicker(false);
        setContext(null);
        setShortcuts(false);
        setSearchOpen(false);
        return;
      }
      if (
        (event.target as HTMLElement)?.closest(
          "input, textarea, select, [contenteditable=true]",
        )
      )
        return;
      const mod = event.ctrlKey || event.metaKey;
      if (mod && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (!readonly) save();
      } else if (mod && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (!readonly) event.shiftKey ? redo() : undo();
      } else if (mod && event.key.toLowerCase() === "y") {
        event.preventDefault();
        if (!readonly) redo();
      } else if (mod && event.key.toLowerCase() === "c") {
        event.preventDefault();
        copyNodes();
      } else if (mod && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setSearchOpen(true);
      } else if (mod && event.key.toLowerCase() === "x") {
        event.preventDefault();
        if (!readonly) {
          copyNodes();
          deleteSelection();
        }
      } else if (mod && event.key.toLowerCase() === "v") {
        event.preventDefault();
        pasteNodes();
      } else if (mod && event.key.toLowerCase() === "d") {
        event.preventDefault();
        duplicateNodes();
      } else if (mod && event.key.toLowerCase() === "g") {
        event.preventDefault();
        groupSelection();
      } else if (mod && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setSelected(
          new Set([
            ...graph.nodes.map((n) => n.id),
            ...graph.groups.map((g) => g.id),
            ...(graph.annotations || []).map((n) => n.id),
          ]),
        );
      } else if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (!readonly) {
          setPendingSource(null);
          setPicker(true);
        }
      } else if (["Delete", "Backspace"].includes(event.key)) {
        event.preventDefault();
        deleteSelection();
      }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [
    readonly,
    save,
    undo,
    redo,
    copyNodes,
    pasteNodes,
    duplicateNodes,
    groupSelection,
    deleteSelection,
    graph.nodes,
    graph.groups,
    graph.annotations,
  ]);
  const validate = async () => {
    setPanel("validation");
    setInspectorOpen(true);
    setValidating(true);
    const signature = validationSignature(graph);
    try {
      const result = props.onValidate
        ? await props.onValidate(graph)
        : localValidation;
      if (validationSignature(docRef.current.definition) === signature) {
        setRemoteValidation(result);
        setPanel("validation");
        setInspectorOpen(true);
      }
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setValidating(false);
    }
  };
  const runPreview = async () => {
    if (!props.onPreview) {
      setPreviewError("A local preview handler is not configured");
      return;
    }
    setPreviewBusy(true);
    setPreviewError("");
    try {
      const input = JSON.parse(testInput);
      if (!input || Array.isArray(input) || typeof input !== "object")
        throw new Error("Test input must be a JSON object");
      const signature = validationSignature(graph);
      const result = await props.onPreview(graph, input);
      if (signature === validationSignature(docRef.current.definition)) {
        setPreview(result);
        if (!result.validation.valid) {
          setRemoteValidation(result.validation);
          setPanel("validation");
          setInspectorOpen(true);
        }
      }
    } catch (error) {
      setPreviewError(
        error instanceof SyntaxError
          ? "Enter valid JSON test input"
          : (error as Error).message === "Test input must be a JSON object"
            ? (error as Error).message
            : errorMessage(error),
      );
    } finally {
      setPreviewBusy(false);
    }
  };
  const onResize = (event: React.PointerEvent) => {
    resizeAbort.current?.abort();
    const controller = new AbortController();
    resizeAbort.current = controller;
    const start = event.clientX,
      initial = panelWidth;
    const move = (e: PointerEvent) =>
      setPanelWidth(Math.max(280, Math.min(500, initial + start - e.clientX)));
    window.addEventListener("pointermove", move, { signal: controller.signal });
    window.addEventListener("pointerup", () => controller.abort(), {
      once: true,
      signal: controller.signal,
    });
  };
  const exportGraph = async () => {
    let exported = document;
    try {
      if (props.authoring)
        exported = {
          ...document,
          definition: (await props.authoring.portable(graph)).definition,
        };
    } catch (error) {
      setNotice(errorMessage(error));
      return;
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(exported, null, 2)], {
        type: "application/json",
      }),
    );
    const link = window.document.createElement("a");
    link.href = url;
    link.download =
      (document.name.replace(/[^a-zA-Z0-9_-]/g, "_") || "automation") + ".json";
    link.click();
    URL.revokeObjectURL(url);
  };
  const saveCopy = async () => {
    if (!props.onSaveCopy) return;
    setCopying(true);
    try {
      await props.onSaveCopy(document);
      try {
        sessionStorage.removeItem(props.recoveryKey);
      } catch {
        /* Optional recovery cache. */
      }
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setCopying(false);
    }
  };
  const addAnnotation = (kind: "note" | "annotation") => {
    if (readonly || (graph.annotations || []).length >= 100) return;
    const position = flow.screenToFlowPosition({
      x: window.innerWidth / 2,
      y: window.innerHeight / 2,
    });
    const occupied = [
      ...graph.nodes.map((n) => ({ ...n.position, width: 220, height: 160 })),
      ...(graph.annotations || []).map((n) => ({
        ...n.position,
        width: n.width,
        height: 150,
      })),
    ];
    let attempts = 0;
    while (
      occupied.some(
        (rect) =>
          position.x < rect.x + rect.width + 24 &&
          position.x + 300 > rect.x - 24 &&
          position.y < rect.y + rect.height + 24 &&
          position.y + 150 > rect.y - 24,
      ) &&
      attempts++ < 500
    )
      position.y += 180;
    const note = {
      id: newId(kind),
      kind,
      text: "",
      position,
      width: kind === "note" ? 240 : 300,
    };
    changeGraph((c) => ({
      ...c,
      annotations: [...(c.annotations || []), note],
    }));
    setSelected(new Set([note.id]));
    setInspectedId(null);
    setInspectorOpen(true);
  };
  const selectedEdge = graph.edges.find((e) => selectedEdges.has(e.id));
  const Config = props.configurationPanel || ConfigurationPanel;
  return (
    <div
      className="as-studio"
      ref={root}
      style={props.themeTokens}
      data-readonly={readonly}
    >
      <aside className="as-rail">
        <button
          className="as-rail-brand"
          aria-label="Back to automations"
          onClick={() => {
            if (
              !persistence.dirty ||
              readonly ||
              window.confirm(
                "Leave with unsaved changes? Your recovery draft remains in this tab.",
              )
            )
              props.onBack();
          }}
        >
          <Layers3 size={25} />
        </button>
        <button
          aria-label="Toggle node library"
          className={libraryOpen ? "active" : ""}
          onClick={() => setLibraryOpen((v) => !v)}
        >
          <LayoutGrid size={21} />
        </button>
        <button
          aria-label="Open workflow settings"
          onClick={() => {
            setPanel("settings");
            setInspectorOpen(true);
            props.onSettings?.();
          }}
        >
          <Settings2 size={21} />
        </button>
        <button
          aria-label="Open version history"
          disabled={!props.workflowId}
          onClick={() => {
            setPanel("versions");
            setInspectorOpen(true);
            props.onVersionHistory?.();
          }}
        >
          <History size={21} />
        </button>
        <span />
        <button
          aria-label="Keyboard shortcuts"
          onClick={() => setShortcuts(true)}
        >
          <Braces size={20} />
        </button>
        <div className="as-rail-avatar">
          <ShieldCheck size={19} />
        </div>
      </aside>
      <div className="as-workspace">
        <WorkflowToolbar>
          <div className="as-title">
            <button
              aria-label="Back to automation list"
              onClick={() => {
                if (
                  !persistence.dirty ||
                  readonly ||
                  window.confirm("Leave with unsaved changes?")
                )
                  props.onBack();
              }}
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <input
                aria-label="Automation name"
                readOnly={readonly}
                maxLength={180}
                value={document.name}
                onChange={(e) =>
                  update((current) => ({ ...current, name: e.target.value }))
                }
              />
              <p>
                <span className="as-draft-dot" />
                {readonly ? "Read-only draft" : "Draft"}
                <span className="as-toolbar-separator">/</span>
                {props.environmentId}
                <span className="as-toolbar-separator">/</span>
                <span
                  aria-live="polite"
                  className={`as-save-status ${persistence.status}`}
                >
                  {persistence.status === "saved"
                    ? `Saved ${persistence.savedAt ? new Date(persistence.savedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}`
                    : persistence.status === "saving"
                      ? "Saving..."
                      : persistence.status === "conflict"
                        ? "Save conflict"
                        : persistence.status === "error"
                          ? "Autosave paused"
                          : "Unsaved changes"}
                </span>
                {persistence.version > 0 && <span>v{persistence.version}</span>}
              </p>
            </div>
          </div>
          <div className="as-toolbar-actions">
            <div className="as-undo-controls">
              <button
                aria-label="Undo"
                title="Undo (Ctrl Z)"
                disabled={readonly || !canUndo}
                onClick={undo}
              >
                <Undo2 size={17} />
              </button>
              <button
                aria-label="Redo"
                title="Redo (Ctrl Shift Z)"
                disabled={readonly || !canRedo}
                onClick={redo}
              >
                <Redo2 size={17} />
              </button>
            </div>
            <button
              onClick={validate}
              disabled={validating}
              className="as-validate-button"
            >
              <ShieldCheck size={15} />
              {validating ? "Checking..." : "Validate"}
            </button>
            <button
              className="as-test-button"
              onClick={() => setShowTesting((v) => !v)}
            >
              <Play size={14} />
              Test workflow
            </button>
            <button
              className="as-button-primary"
              onClick={save}
              disabled={
                readonly ||
                persistence.status === "saving" ||
                persistence.status === "conflict"
              }
            >
              <Save size={14} />
              Save draft
            </button>
            <button
              disabled={!props.onRuntime}
              onClick={props.onRuntime}
              title="Review the saved draft, publication and execution policy"
              className="as-publish"
            >
              <LockKeyhole size={13} />
              Publish & runs
            </button>
            {props.authoring && (
              <>
                <button
                  aria-label="Create with AI"
                  title="Create with AI"
                  onClick={() => setAuthoringTab("AI designer")}
                >
                  <Sparkles size={15} />
                  <span className="ai-button-label">Create with AI</span>
                </button>
                <button
                  aria-label="Open authoring tools"
                  title="Mapping, blocks, templates, simulation and documentation"
                  onClick={() => setAuthoringTab("Data mapping")}
                >
                  <Braces size={16} />
                  <span className="ai-button-label">Authoring tools</span>
                </button>
              </>
            )}
            <details className="as-more-menu">
              <summary aria-label="More automation actions">
                <MoreHorizontal size={20} />
              </summary>
              <div>
                <button
                  disabled={
                    !props.permissions.create ||
                    !props.onDuplicate ||
                    !props.workflowId
                  }
                  onClick={() => {
                    void props
                      .onDuplicate?.()
                      .catch((error) => setNotice(errorMessage(error)));
                  }}
                >
                  <Copy size={14} />
                  Duplicate saved automation
                </button>
                <button
                  disabled={
                    !props.permissions.create || !props.onSaveCopy || copying
                  }
                  onClick={() => void saveCopy()}
                >
                  <Copy size={14} />
                  Save current work as a copy
                </button>
                <button onClick={exportGraph}>
                  <Download size={14} />
                  Export definition JSON
                </button>
                <button onClick={() => setShortcuts(true)}>
                  <Braces size={14} />
                  Keyboard shortcuts
                </button>
              </div>
            </details>
          </div>
        </WorkflowToolbar>
        {(persistence.error || persistence.status === "conflict") && (
          <div className="as-save-error" role="alert">
            <CircleAlert size={16} />
            <span>{persistence.error} Your local draft is preserved.</span>
            {props.permissions.create && (
              <button disabled={copying} onClick={() => void saveCopy()}>
                Save as separate copy
              </button>
            )}
            <button
              onClick={() => {
                if (
                  window.confirm(
                    "Reload the server draft? Your unsaved recovery copy remains available.",
                  )
                )
                  window.location.reload();
              }}
            >
              Reload latest
            </button>
          </div>
        )}
        {persistence.recovery && !readonly && (
          <div className="as-recovery">
            <History size={16} />
            <span>
              An unsaved draft from{" "}
              {new Date(persistence.recovery.timestamp).toLocaleString()} is
              available in this tab.
            </span>
            <button
              onClick={() => {
                const recovered = persistence.recover();
                if (recovered) update(recovered);
              }}
            >
              Recover changes
            </button>
            <button onClick={persistence.discardRecovery}>
              Discard recovery
            </button>
          </div>
        )}
        <div className="as-body">
          {libraryOpen && !readonly && (
            <NodeLibrary
              catalog={props.nodeCatalog}
              onAdd={(def) => addNode(def)}
              onClose={() => setLibraryOpen(false)}
            />
          )}
          <div className="as-center">
            <div
              className="as-canvas"
              onDragOver={(event) => {
                if (!readonly) {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "copy";
                }
              }}
              onDrop={(event) => {
                if (readonly) return;
                event.preventDefault();
                const definition = catalogMap.get(
                  event.dataTransfer.getData("application/power-apps-node"),
                );
                if (definition) {
                  setPendingSource(null);
                  addNode(
                    definition,
                    flow.screenToFlowPosition({
                      x: event.clientX,
                      y: event.clientY,
                    }),
                  );
                }
              }}
            >
              <AutomationCanvas
                nodes={flowNodes}
                edges={flowEdges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={connect}
                onNodeDragStart={() => {
                  if (!readonly) {
                    checkpoint();
                    setDragging(true);
                  }
                }}
                onNodeDrag={(_, node) => {
                  if (node.type !== "studio" || selected.size > 1) return;
                  const current = docRef.current.definition;
                  const moving = current.nodes.find((n) => n.id === node.id);
                  if (!moving) return;
                  const threshold = 8 / Math.max(zoom, 0.2);
                  const others = current.nodes.filter(
                    (n) => n.id !== node.id && !selected.has(n.id),
                  );
                  const x = others.find(
                    (n) =>
                      Math.abs(n.position.x - moving.position.x) < threshold,
                  )?.position.x;
                  const y = others.find(
                    (n) =>
                      Math.abs(n.position.y - moving.position.y) < threshold,
                  )?.position.y;
                  setGuides({ x, y });
                }}
                onNodeDragStop={(_, node) => {
                  setDragging(false);
                  setGuides({});
                  if (
                    node.type === "studio" &&
                    (guides.x !== undefined || guides.y !== undefined)
                  )
                    changeGraph(
                      (c) => ({
                        ...c,
                        nodes: c.nodes.map((n) =>
                          n.id === node.id
                            ? {
                                ...n,
                                position: {
                                  x: guides.x ?? n.position.x,
                                  y: guides.y ?? n.position.y,
                                },
                              }
                            : n,
                        ),
                      }),
                      false,
                    );
                }}
                onEdgeClick={(_, edge) => {
                  setInspectedId(null);
                  setSelectedEdges(new Set([edge.id]));
                  setInspectorOpen(true);
                  setPanel(null);
                }}
                onReconnectStart={(_, edge) => {
                  reconnectingId.current = edge.id;
                }}
                onReconnectEnd={() => {
                  reconnectingId.current = null;
                }}
                onReconnect={(old, connection) => {
                  if (readonly) return;
                  const edge: WorkflowEdge = {
                    ...graph.edges.find((e) => e.id === old.id)!,
                    source: connection.source,
                    target: connection.target,
                    source_port: connection.sourceHandle || "out",
                    target_port: connection.targetHandle || "in",
                  };
                  const reason = connectionError(
                    {
                      ...graph,
                      edges: graph.edges.filter((e) => e.id !== old.id),
                    },
                    edge,
                    props.nodeCatalog,
                  );
                  if (reason) {
                    setNotice(reason);
                    return;
                  }
                  changeGraph((c) => ({
                    ...c,
                    edges: c.edges.map((e) => (e.id === old.id ? edge : e)),
                  }));
                }}
                onSelectionChange={onSelectionChange}
                onNodeClick={(_, node) => {
                  if (node.type !== "studio") {
                    setInspectedId(null);
                    setInspectorOpen(true);
                    setPanel(null);
                  }
                  if (node.type === "studio") {
                    setInspectedId(node.id);
                    setInspectorOpen(true);
                    setPanel(null);
                  }
                }}
                onNodeDoubleClick={(_, node) => inspect(node.id)}
                onNodeContextMenu={(event, node) => {
                  event.preventDefault();
                  openMenu(node.id, event.clientX, event.clientY);
                }}
                onPaneClick={() => {
                  setContext(null);
                }}
                isValidConnection={(connection) =>
                  !readonly &&
                  !connectionError(
                    reconnectingId.current
                      ? {
                          ...graph,
                          edges: graph.edges.filter(
                            (e) => e.id !== reconnectingId.current,
                          ),
                        }
                      : graph,
                    {
                      id: "pending",
                      source: connection.source,
                      target: connection.target,
                      source_port: connection.sourceHandle || "out",
                      target_port: connection.targetHandle || "in",
                      label: "",
                    },
                    props.nodeCatalog,
                  )
                }
                nodesDraggable={!readonly}
                nodesConnectable={!readonly}
                edgesReconnectable={!readonly}
                elementsSelectable
                snapToGrid={graph.editor?.snap_to_grid ?? true}
                snapGrid={[20, 20]}
                minZoom={0.01}
                maxZoom={2}
                defaultViewport={props.initialDocument.definition.viewport}
                connectionLineType={
                  graph.editor?.connection_style === "orthogonal"
                    ? ConnectionLineType.SmoothStep
                    : ConnectionLineType.Bezier
                }
                zoomOnScroll
                zoomOnPinch
                panOnDrag
                selectionKeyCode="Shift"
                multiSelectionKeyCode={["Meta", "Control"]}
                selectionMode={SelectionMode.Partial}
                deleteKeyCode={null}
                onlyRenderVisibleElements
                onMoveEnd={(_, viewport) => {
                  setZoom(viewport.zoom);
                  if (!readonly)
                    changeGraph((current) => ({ ...current, viewport }), false);
                }}
                proOptions={{ hideAttribution: false }}
              >
                {showGrid && (
                  <Background
                    variant={BackgroundVariant.Dots}
                    gap={24}
                    size={1}
                    color="#d9d4e3"
                  />
                )}
                <WorkflowMinimap
                  pannable
                  zoomable
                  nodeColor={(node) =>
                    node.type === "group"
                      ? "#eee7fa"
                      : categoryColors[
                          (node.data as { definition?: NodeDefinition })
                            .definition?.category || "Triggers"
                        ]
                  }
                  maskColor="rgba(247,245,251,.7)"
                  position="bottom-right"
                  style={{ width: 145, height: 90 }}
                />
              </AutomationCanvas>
              {guides.x !== undefined && (
                <div
                  className="as-alignment-guide vertical"
                  style={{ left: guides.x * zoom + flow.getViewport().x }}
                />
              )}
              {guides.y !== undefined && (
                <div
                  className="as-alignment-guide horizontal"
                  style={{ top: guides.y * zoom + flow.getViewport().y }}
                />
              )}
              {searchOpen && (
                <WorkflowSearch
                  graph={graph}
                  onSelect={(id) => {
                    focusNode(id);
                    setSearchOpen(false);
                  }}
                  onClose={() => setSearchOpen(false)}
                />
              )}
              <WorkflowBreadcrumbs
                items={[
                  {
                    id: "list",
                    label: "Automations",
                    onNavigate: () => {
                      if (
                        !persistence.dirty ||
                        window.confirm("Leave with unsaved changes?")
                      )
                        props.onBack();
                    },
                  },
                  ...(props.breadcrumbs || []).map((item) => ({
                    ...item,
                    onNavigate: item.onNavigate
                      ? () => {
                          if (
                            !persistence.dirty ||
                            window.confirm("Leave with unsaved changes?")
                          )
                            item.onNavigate?.();
                        }
                      : undefined,
                  })),
                  {
                    id: String(props.workflowId || "draft"),
                    label: document.name,
                  },
                ]}
              />

              {!graph.nodes.length && (
                <div className="as-canvas-empty">
                  <span>
                    <Workflow size={38} strokeWidth={1.4} />
                  </span>
                  <p>EVERY GREAT WORKFLOW STARTS WITH ONE STEP</p>
                  <h1>What starts your automation?</h1>
                  <p>
                    Choose a trigger, then connect the steps that follow.
                    <br />
                    Your ideas have room to grow here.
                  </p>
                  <button
                    className="as-button-primary"
                    disabled={readonly}
                    onClick={() => {
                      setPendingSource(null);
                      setPicker(true);
                    }}
                  >
                    <Plus size={16} />
                    Add your first node
                  </button>
                </div>
              )}
              <details className="as-canvas-options">
                <summary aria-label="Canvas options">Canvas options</summary>
                <div>
                  <button onClick={() => setSearchOpen(true)}>
                    Find / jump to node <kbd>Ctrl F</kbd>
                  </button>
                  <button
                    onClick={() =>
                      void flow.setViewport(
                        { x: 0, y: 0, zoom: 1 },
                        { duration: 200 },
                      )
                    }
                  >
                    Reset view to 100%
                  </button>
                  <label>
                    <input
                      type="checkbox"
                      disabled={readonly}
                      checked={graph.editor?.snap_to_grid ?? true}
                      onChange={(e) =>
                        changeGraph((c) => ({
                          ...c,
                          editor: {
                            connection_style:
                              c.editor?.connection_style || "bezier",
                            snap_to_grid: e.target.checked,
                          },
                        }))
                      }
                    />
                    Snap to grid
                  </label>
                  <label>
                    Default connections
                    <select
                      aria-label="Default connection style"
                      disabled={readonly}
                      value={graph.editor?.connection_style || "bezier"}
                      onChange={(e) =>
                        changeGraph((c) => ({
                          ...c,
                          editor: {
                            snap_to_grid: c.editor?.snap_to_grid ?? true,
                            connection_style: e.target.value as
                              | "bezier"
                              | "orthogonal",
                          },
                        }))
                      }
                    >
                      <option value="bezier">Bezier</option>
                      <option value="orthogonal">Orthogonal</option>
                    </select>
                  </label>
                  <button
                    disabled={
                      readonly || (graph.annotations || []).length >= 100
                    }
                    onClick={() => addAnnotation("note")}
                  >
                    Add sticky note
                  </button>
                  <button
                    disabled={
                      readonly || (graph.annotations || []).length >= 100
                    }
                    onClick={() => addAnnotation("annotation")}
                  >
                    Add annotation block
                  </button>
                </div>
              </details>
              <div className="as-canvas-tools">
                <button
                  aria-label="Zoom out"
                  onClick={() => void flow.zoomOut({ duration: 180 })}
                >
                  <ZoomOut size={17} />
                </button>
                <span>{Math.round(zoom * 100)}%</span>
                <button
                  aria-label="Zoom in"
                  onClick={() => void flow.zoomIn({ duration: 180 })}
                >
                  <ZoomIn size={17} />
                </button>
                <i />
                <button
                  aria-label="Fit to screen"
                  title="Fit to screen"
                  onClick={() =>
                    void flow.fitView({
                      padding: 0.24,
                      duration: 250,
                      minZoom: 0.01,
                      maxZoom: 1.2,
                    })
                  }
                >
                  <Expand size={17} />
                </button>
                <button
                  aria-label="Auto layout"
                  disabled={readonly || !graph.nodes.length}
                  onClick={() => {
                    if (
                      graph.groups.length &&
                      !window.confirm(
                        "Auto-layout will reposition nodes and remove visual groups. Continue?",
                      )
                    )
                      return;
                    changeGraph(autoLayout);
                    window.setTimeout(
                      () =>
                        void flow.fitView({
                          padding: 0.22,
                          duration: 200,
                          minZoom: 0.01,
                          maxZoom: 1.2,
                        }),
                      50,
                    );
                  }}
                >
                  <LayoutDashboard size={17} />
                </button>
                <button
                  aria-label="Toggle background grid"
                  aria-pressed={showGrid}
                  onClick={() => setShowGrid((v) => !v)}
                >
                  <Grid2X2 size={16} />
                </button>
                <i />
                <button
                  aria-label="Add node"
                  disabled={readonly}
                  onClick={() => {
                    setPendingSource(null);
                    setPicker(true);
                  }}
                >
                  <Plus size={18} />
                </button>
                <button
                  aria-label="Copy selected nodes"
                  disabled={!selected.size}
                  onClick={() => copyNodes()}
                >
                  <Copy size={16} />
                </button>
                <button
                  aria-label="Paste nodes"
                  disabled={readonly || !clipboardReady}
                  onClick={pasteNodes}
                >
                  <Braces size={16} />
                </button>
                <button
                  aria-label="Group selection"
                  disabled={readonly || selected.size < 2}
                  onClick={groupSelection}
                >
                  <Group size={16} />
                </button>
                <button
                  aria-label="Ungroup selection"
                  disabled={
                    readonly ||
                    !graph.groups.some(
                      (g) =>
                        selected.has(g.id) ||
                        g.node_ids.some((id) => selected.has(id)),
                    )
                  }
                  onClick={ungroup}
                >
                  <Ungroup size={16} />
                </button>
                <button
                  aria-label="Delete selected"
                  disabled={readonly || (!selected.size && !selectedEdges.size)}
                  onClick={() => deleteSelection()}
                >
                  <Trash2 size={16} />
                </button>
              </div>
              <div className="as-canvas-status">
                <span className="as-draft-dot" />
                <span>{readonly ? "Read-only" : "Draft workspace"}</span>
                <span data-testid="graph-count">
                  {graph.nodes.length} nodes / {graph.edges.length} connections
                </span>
              </div>
              <button
                className="as-inspector-toggle"
                aria-label="Toggle inspector"
                onClick={() => setInspectorOpen((v) => !v)}
              >
                <PanelRightClose size={17} />
              </button>
              {notice && (
                <div role="status" className="as-notice">
                  {notice}
                  <button
                    aria-label="Dismiss message"
                    onClick={() => setNotice("")}
                  >
                    <X size={13} />
                  </button>
                </div>
              )}
            </div>
            {showTesting && (
              <PreviewPanel
                result={preview}
                input={testInput}
                setInput={(value) => {
                  setTestInput(value);
                  setPreview(undefined);
                }}
                busy={previewBusy}
                error={previewError}
                onRun={() => void runPreview()}
                onClose={() => setShowTesting(false)}
                onInspect={inspect}
              />
            )}
          </div>
          {inspectorOpen && (
            <div className="as-panel-host" style={{ width: panelWidth }}>
              <div
                role="separator"
                aria-label="Resize configuration panel"
                aria-orientation="vertical"
                aria-valuenow={panelWidth}
                aria-valuemin={280}
                aria-valuemax={500}
                tabIndex={0}
                className="as-panel-resizer"
                onPointerDown={onResize}
                onKeyDown={(event) => {
                  if (event.key === "ArrowLeft")
                    setPanelWidth((v) => Math.min(500, v + 20));
                  if (event.key === "ArrowRight")
                    setPanelWidth((v) => Math.max(280, v - 20));
                }}
              />
              {panel === "validation" ? (
                <ValidationPanel
                  result={validation}
                  onClose={() => setPanel(null)}
                  onSelect={focusNode}
                />
              ) : panel === "versions" ? (
                <VersionsPanel
                  key={props.versions?.length}
                  versions={props.versions || []}
                  current={document}
                  readOnly={!props.permissions.create}
                  onRestore={props.onRestoreVersion}
                  onClose={() => setPanel(null)}
                />
              ) : panel === "settings" ? (
                <SettingsPanel
                  settings={graph.settings}
                  metadata={
                    <WorkflowMetadata
                      graph={graph}
                      readOnly={readonly}
                      onChange={changeGraph}
                    />
                  }
                  description={document.description}
                  readOnly={readonly}
                  onChange={(settings) =>
                    changeGraph((current) => ({ ...current, settings }))
                  }
                  onDescription={(description) => {
                    if (!readonly)
                      update((current) => ({ ...current, description }));
                  }}
                  onClose={() => setPanel(null)}
                />
              ) : inspected && catalogMap.has(inspected.type) ? (
                <Suspense
                  fallback={
                    <div className="as-panel-loading" role="status">
                      Loading configuration...
                    </div>
                  }
                >
                  <Config
                    logicEditor={
                      props.authoring ? (
                        <details>
                          <summary>Visual logic builder</summary>
                          <LogicEditor
                            node={inspected}
                            catalog={props.nodeCatalog}
                            readOnly={readonly}
                            usedPorts={graph.edges
                              .filter((e) => e.source === inspected.id)
                              .map((e) => e.source_port)}
                            onChange={(node) =>
                              changeGraph((c) => ({
                                ...c,
                                nodes: c.nodes.map((n) =>
                                  n.id === node.id ? node : n,
                                ),
                              }))
                            }
                          />
                        </details>
                      ) : undefined
                    }
                    recommendations={
                      <details>
                        <summary>Recommended next steps</summary>
                        <NodeRecommendationPanel
                          key={inspected.id}
                          graph={graph}
                          node={inspected}
                          catalog={props.nodeCatalog}
                          readOnly={readonly}
                          onAdd={(definition, port) => {
                            try {
                              const result = appendRecommendation(
                                graph,
                                inspected,
                                definition,
                                props.nodeCatalog,
                                port,
                              );
                              changeGraph(() => result.graph);
                              inspect(result.node.id);
                            } catch (e) {
                              setNotice((e as Error).message);
                            }
                          }}
                        />
                      </details>
                    }
                    environmentName={props.environmentId}
                    onOpenWorkflow={
                      props.onOpenWorkflow
                        ? (id) => {
                            if (
                              !persistence.dirty ||
                              window.confirm(
                                "Open the sub-workflow with unsaved changes? Your recovery draft remains available.",
                              )
                            )
                              void props
                                .onOpenWorkflow?.(id)
                                .catch((error) =>
                                  setNotice(errorMessage(error)),
                                );
                          }
                        : undefined
                    }
                    referenceProviders={props.referenceProviders}
                    key={inspected.id}
                    node={inspected}
                    definition={nodeDefinition(inspected, props.nodeCatalog)!}
                    graph={graph}
                    catalog={props.nodeCatalog}
                    issues={validation.issues.filter(
                      (i) => i.node_id === inspected.id,
                    )}
                    readOnly={readonly}
                    onChange={(node) =>
                      changeGraph((current) => ({
                        ...current,
                        nodes: current.nodes.map((n) =>
                          n.id === node.id ? node : n,
                        ),
                      }))
                    }
                    onClose={() => setInspectedId(null)}
                    onDelete={() => deleteSelection(new Set([inspected.id]))}
                    onDuplicate={() => duplicateNodes(new Set([inspected.id]))}
                  />
                </Suspense>
              ) : graph.groups.some((g) => selected.has(g.id)) ? (
                <aside className="as-aux-panel">
                  <header>
                    <h2>Node group</h2>
                  </header>
                  <div className="as-aux-scroll">
                    {graph.groups
                      .filter((g) => selected.has(g.id))
                      .map((g) => (
                        <div key={g.id}>
                          <label className="as-basic-field">
                            Group label
                            <input
                              aria-label="Group label"
                              readOnly={readonly}
                              maxLength={120}
                              value={g.label}
                              onChange={(e) =>
                                changeGraph((c) => ({
                                  ...c,
                                  groups: c.groups.map((item) =>
                                    item.id === g.id
                                      ? { ...item, label: e.target.value }
                                      : item,
                                  ),
                                }))
                              }
                            />
                          </label>
                          <button onClick={() => toggleGroup(g.id)}>
                            {g.collapsed ? "Expand group" : "Collapse group"}
                          </button>
                          <button disabled={readonly} onClick={ungroup}>
                            Dissolve group
                          </button>
                        </div>
                      ))}
                  </div>
                </aside>
              ) : (graph.annotations || []).some((n) => selected.has(n.id)) ? (
                <aside className="as-aux-panel">
                  <header>
                    <h2>Annotation</h2>
                  </header>
                  <div className="as-aux-scroll">
                    {(graph.annotations || [])
                      .filter((n) => selected.has(n.id))
                      .map((n) => (
                        <label className="as-basic-field" key={n.id}>
                          Note text
                          <textarea
                            aria-label="Note text"
                            readOnly={readonly}
                            maxLength={4000}
                            value={n.text}
                            onChange={(e) =>
                              changeGraph((c) => ({
                                ...c,
                                annotations: (c.annotations || []).map(
                                  (note) =>
                                    note.id === n.id
                                      ? { ...note, text: e.target.value }
                                      : note,
                                ),
                              }))
                            }
                          />
                        </label>
                      ))}
                    <button
                      disabled={readonly}
                      onClick={() => deleteSelection()}
                    >
                      Delete annotation
                    </button>
                  </div>
                </aside>
              ) : selectedEdge ? (
                <aside className="as-aux-panel">
                  <header>
                    <h2>Connection</h2>
                    <button
                      aria-label="Close connection editor"
                      onClick={() => setSelectedEdges(new Set())}
                    >
                      <X size={16} />
                    </button>
                  </header>
                  <div className="as-aux-scroll">
                    <ConnectionEditor
                      key={selectedEdge.id}
                      edge={selectedEdge}
                      graph={graph}
                      catalog={props.nodeCatalog}
                      readOnly={readonly}
                      onChange={(edge) =>
                        changeGraph((c) => ({
                          ...c,
                          edges: c.edges.map((e) =>
                            e.id === edge.id ? edge : e,
                          ),
                        }))
                      }
                      onInsert={() => {
                        setPendingEdge(selectedEdge.id);
                        setPendingSource(null);
                        setPicker(true);
                      }}
                      onDelete={() => deleteSelection(new Set())}
                    />
                  </div>
                </aside>
              ) : (
                <CanvasInspector
                  graph={graph}
                  catalog={props.nodeCatalog}
                  readOnly={readonly}
                  onClose={() => setInspectorOpen(false)}
                  onConnect={connect}
                  onLabel={() => {}}
                  onInspect={focusNode}
                  errorCount={
                    validation.issues.filter((i) => i.severity === "error")
                      .length
                  }
                />
              )}
            </div>
          )}
        </div>
      </div>
      {authoringTab && props.authoring && (
        <IntelligentStudio
          key={authoringTab}
          initialTab={authoringTab}
          document={document}
          version={persistence.version}
          catalog={props.nodeCatalog}
          selected={selected}
          node={inspected}
          readOnly={readonly}
          services={props.authoring}
          onApply={(definition) => changeGraph(() => definition)}
          onNode={(node) =>
            changeGraph((c) => ({
              ...c,
              nodes: c.nodes.map((n) => (n.id === node.id ? node : n)),
            }))
          }
          onFocus={focusNode}
          onSimulation={setSimulation}
          onClose={() => setAuthoringTab(null)}
        />
      )}
      {picker && !readonly && (
        <div
          className="as-picker-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Choose a workflow node"
          onClick={() => setPicker(false)}
          onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const focusable = Array.from(
              event.currentTarget.querySelectorAll<HTMLElement>(
                "button:not([disabled]),input,select",
              ),
            );
            const first = focusable[0],
              last = focusable[focusable.length - 1];
            if (event.shiftKey && window.document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (
              !event.shiftKey &&
              window.document.activeElement === last
            ) {
              event.preventDefault();
              first?.focus();
            }
          }}
        >
          <div onClick={(event) => event.stopPropagation()}>
            <NodeLibrary
              catalog={props.nodeCatalog}
              picker
              onAdd={(def) => addNode(def)}
              onClose={() => setPicker(false)}
            />
          </div>
        </div>
      )}
      {context && (
        <div
          className="as-context-menu"
          role="menu"
          style={{ left: context.x, top: context.y }}
        >
          <button
            role="menuitem"
            onClick={() => {
              inspect(context.id);
              setContext(null);
            }}
          >
            Configure node
          </button>
          <button
            role="menuitem"
            disabled={readonly || !graph.nodes.some((n) => n.id === context.id)}
            onClick={() => {
              changeGraph((c) => ({
                ...c,
                nodes: c.nodes.map((n) =>
                  n.id === context.id ? { ...n, disabled: !n.disabled } : n,
                ),
              }));
              setContext(null);
            }}
          >
            {graph.nodes.find((n) => n.id === context.id)?.disabled
              ? "Enable node"
              : "Disable node"}
          </button>
          <button
            role="menuitem"
            onClick={() => {
              copyNodes(selected);
              setContext(null);
            }}
          >
            Copy selection
          </button>
          <button
            role="menuitem"
            disabled={readonly}
            onClick={() => duplicateNodes(selected)}
          >
            Duplicate selection
          </button>
          <button
            role="menuitem"
            disabled={readonly || selected.size < 2}
            onClick={groupSelection}
          >
            Group selection
          </button>
          <button
            role="menuitem"
            disabled={readonly}
            onClick={() => deleteSelection(selected)}
            className="as-danger"
          >
            Delete selection
          </button>
          <button role="menuitem" onClick={() => setContext(null)}>
            Close menu
          </button>
        </div>
      )}
      {shortcuts && (
        <div
          className="as-shortcuts"
          role="dialog"
          aria-modal="true"
          aria-label="Keyboard shortcuts"
        >
          <button
            autoFocus
            aria-label="Close shortcuts"
            onClick={() => setShortcuts(false)}
          >
            <X size={18} />
          </button>
          <h2>Make it your flow</h2>
          <p>Ctrl / Command + S: save draft</p>
          <p>Ctrl / Command + Z: undo</p>
          <p>Ctrl / Command + Shift + Z: redo</p>
          <p>Ctrl / Command + C / X / V: copy / cut / paste selection</p>
          <p>Ctrl / Command + D: duplicate nodes</p>
          <p>Ctrl / Command + G: group selection</p>
          <p>Ctrl / Command + K: add a node</p>
          <p>Ctrl / Command + F: find and jump to a node</p>
          <p>Shift + drag: select multiple nodes</p>
          <p>Delete / Backspace: delete selected nodes or edges</p>
          <p>Mouse wheel / pinch: zoom. Drag the background to pan.</p>
          <p>Escape: close picker, menu or shortcuts</p>
        </div>
      )}
    </div>
  );
}
function CanvasInspector({
  graph,
  catalog,
  readOnly,
  selectedEdge,
  onClose,
  onConnect,
  onLabel,
  onInspect,
  errorCount,
}: {
  graph: WorkflowGraph;
  catalog: NodeDefinition[];
  readOnly: boolean;
  selectedEdge?: WorkflowEdge;
  onClose: () => void;
  onConnect: (connection: Connection) => void;
  onLabel: (label: string) => void;
  onInspect: (id: string) => void;
  errorCount: number;
}) {
  const [source, setSource] = useState(""),
    [target, setTarget] = useState(""),
    [sourcePort, setSourcePort] = useState("out");
  const sourceDefinition = nodeDefinition(
    graph.nodes.find((n) => n.id === source),
    catalog,
  );
  return (
    <aside
      className="as-aux-panel as-canvas-inspector"
      aria-label="Canvas inspector"
    >
      <header>
        <GitBranch size={18} />
        <h2>Workflow overview</h2>
        <button aria-label="Close inspector" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="as-aux-scroll">
        <p className="as-info-banner">
          {readOnly
            ? "You can inspect this workflow. Editing requires a draft-edit permission."
            : "A private space to shape your next idea. No integrations will run while you design."}
        </p>
        <div className="as-inspector-stats">
          <span>
            <strong>{graph.nodes.length}</strong>Nodes
          </span>
          <span>
            <strong>{graph.edges.length}</strong>Connections
          </span>
          <span>
            <strong>{errorCount}</strong>Issues
          </span>
        </div>
        {selectedEdge && (
          <label className="as-basic-field">
            Connection label
            <input
              readOnly={readOnly}
              maxLength={120}
              value={selectedEdge.label}
              onChange={(e) => onLabel(e.target.value)}
            />
          </label>
        )}
        <h3>CONNECT NODES</h3>
        <p className="as-config-note">
          Drag between connection ports, or use the accessible connection form
          below.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (source && target)
              onConnect({
                source,
                target,
                sourceHandle: sourcePort,
                targetHandle:
                  catalog.find(
                    (d) =>
                      d.id === graph.nodes.find((n) => n.id === target)?.type,
                  )?.inputs[0]?.id || "in",
              });
          }}
        >
          <label className="as-basic-field">
            From node
            <select
              aria-label="From node"
              disabled={readOnly}
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setSourcePort(
                  nodeDefinition(
                    graph.nodes.find((n) => n.id === e.target.value),
                    catalog,
                  )?.outputs[0]?.id || "out",
                );
              }}
            >
              <option value="">Choose source</option>
              {graph.nodes
                .filter(
                  (n) => catalog.find((d) => d.id === n.type)?.outputs.length,
                )
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
            </select>
          </label>
          <label className="as-basic-field">
            Output port
            <select
              aria-label="Output port"
              disabled={readOnly}
              value={sourcePort}
              onChange={(e) => setSourcePort(e.target.value)}
            >
              {sourceDefinition?.outputs.map((port) => (
                <option key={port.id} value={port.id}>
                  {port.label}
                </option>
              ))}
            </select>
          </label>
          <label className="as-basic-field">
            To node
            <select
              aria-label="To node"
              disabled={readOnly}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Choose target</option>
              {graph.nodes
                .filter(
                  (n) => catalog.find((d) => d.id === n.type)?.inputs.length,
                )
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
            </select>
          </label>
          <button
            className="as-button-outline"
            disabled={readOnly || !source || !target}
          >
            <GitBranch size={14} />
            Connect nodes
          </button>
        </form>
        <h3>WORKFLOW STEPS</h3>
        <div className="as-overview-nodes">
          {graph.nodes.map((node) => (
            <button key={node.id} onClick={() => onInspect(node.id)}>
              <span
                style={{
                  background:
                    categoryColors[
                      catalog.find((d) => d.id === node.type)?.category ||
                        "Triggers"
                    ],
                }}
              />
              <strong>{node.label}</strong>
              <Search size={12} />
            </button>
          ))}
        </div>
        <div className="as-inspector-help">
          <MousePointer2 size={20} />
          <p>
            Click a node to configure it.
            <br />
            Shift-click to select a few.
            <br />
            Use the plus button to keep building.
          </p>
        </div>
      </div>
    </aside>
  );
}

function WorkflowMetadata({
  graph,
  readOnly,
  onChange,
}: {
  graph: WorkflowGraph;
  readOnly: boolean;
  onChange: (recipe: (graph: WorkflowGraph) => WorkflowGraph) => void;
}) {
  const [variables, setVariables] = useState(
      JSON.stringify(graph.variables || {}, null, 2),
    ),
    [error, setError] = useState("");
  return (
    <section>
      <label className="as-basic-field">
        Workflow tags (comma separated)
        <input
          aria-label="Workflow tags"
          readOnly={readOnly}
          maxLength={1200}
          defaultValue={(graph.tags || []).join(", ")}
          onBlur={(e) =>
            onChange((c) => ({
              ...c,
              tags: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
                .slice(0, 20)
                .map((s) => s.slice(0, 60)),
            }))
          }
        />
      </label>
      <label className="as-basic-field">
        Workflow variables (non-secret JSON)
        <textarea
          aria-label="Workflow variables"
          readOnly={readOnly}
          rows={5}
          value={variables}
          onChange={(e) => setVariables(e.target.value)}
        />
      </label>
      <button
        disabled={readOnly}
        onClick={() => {
          try {
            const value = JSON.parse(variables);
            if (
              !value ||
              Array.isArray(value) ||
              typeof value !== "object" ||
              Object.keys(value).length > 50 ||
              Object.entries(value).some(
                ([key, v]) =>
                  !/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) ||
                  !["string", "number", "boolean"].includes(typeof v) ||
                  /(secret|password|token|api.?key|authorization|constructor|prototype)/i.test(
                    key,
                  ) ||
                  String(v).includes("{{"),
              )
            )
              throw new Error(
                "Use up to 50 literal, non-secret variables with safe names.",
              );
            onChange((c) => ({ ...c, variables: value }));
            setError("");
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        Apply workflow variables
      </button>
      {error && (
        <p role="alert" className="as-field-error">
          {error}
        </p>
      )}
    </section>
  );
}
