"""Persistable schema v2; invalid/incomplete configurations remain distinguishable."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.apps.power_apps.node_registry import NODES, configuration_errors, ports

def safe_identifier(value):
    if value.startswith("__") or value in {"constructor", "prototype"}:raise ValueError("Unsafe graph identifier")
    return value

class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

class Position(GraphModel):
    x: float = Field(ge=-1000000, le=1000000)
    y: float = Field(ge=-1000000, le=1000000)

class Viewport(Position):
    zoom: float = Field(default=1, ge=0.01, le=2)

class Advanced(GraphModel):
    retry_attempts: int = Field(default=3, ge=1, le=10)
    error_strategy: Literal["stop", "continue", "branch"] = "stop"
    timeout_seconds: int = Field(default=60, ge=1, le=86400)

from app.apps.power_apps.authoring_contracts import FieldMapping, BlockContract, BlockReference, MappingPreset

class VisualNode(GraphModel):
    _safe_id = field_validator("id")(safe_identifier)
    mappings: dict[str, FieldMapping] = Field(default_factory=dict, max_length=50)
    disabled: bool = False
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
    type: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    position: Position
    config: dict[str, Any] = Field(default_factory=dict, max_length=50)
    credential_reference: str | None = Field(default=None, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    advanced: Advanced = Field(default_factory=Advanced)

    @field_validator("label", "description")
    @classmethod
    def safe_labels(cls, value):
        # Labels are plain text and are also escaped by React on rendering.
        import re
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)

    @model_validator(mode="after")
    def valid_contract(self):
        errors = configuration_errors(self.type, self.config)
        fields = {field["key"] for field in NODES.get(self.type, {}).get("fields", [])}
        if set(self.mappings) - fields:
            errors.append("Mapping targets must be registered fields")
        expected={"number":{"number"},"boolean":{"boolean"},"json":{"array","object"},"multi-select":{"array"},"date":{"date"},"datetime":{"datetime"},"text":{"string"},"select":{"string"},"record":{"string"},"user":{"string"},"template":{"string"},"credential":{"string"}}
        for field in NODES.get(self.type,{}).get("fields",[]):
            binding=self.mappings.get(field["key"])
            if not binding:continue
            if field["key"] in {"max_iterations","concurrency","routes"}:errors.append("Loop bounds and router topology must be literal design-time values")
            if field["kind"] in expected and binding.target_type not in expected[field["kind"]]:errors.append(field["label"]+" mapping must declare a compatible target type")
        if errors:
            raise ValueError("; ".join(errors))
        return self

class VisualEdge(GraphModel):
    _safe_id = field_validator("id")(safe_identifier)
    style: Literal["bezier", "orthogonal"] = "bezier"
    id: str = Field(min_length=1, max_length=180, pattern=r"^[a-zA-Z0-9_-]+$")
    source: str = Field(max_length=80)
    target: str = Field(max_length=80)
    source_port: str = Field(default="out", max_length=60)
    target_port: str = Field(default="in", max_length=60)
    label: str = Field(default="", max_length=120)

class VisualGroup(GraphModel):
    _safe_id = field_validator("id")(safe_identifier)
    collapsed: bool = False
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
    label: str = Field(min_length=1, max_length=120)
    node_ids: list[str] = Field(min_length=1, max_length=500)
    position: Position
    width: float = Field(ge=100, le=100000)
    height: float = Field(ge=100, le=100000)

class WorkflowSettings(GraphModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_backoff_seconds: int = Field(default=60, ge=1, le=86400)
    idempotency: Literal["event_id", "request_id"] = "request_id"
    execution_identity: Literal["owner"] = "owner"
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    retention_days: int = Field(default=30, ge=1, le=365)

class Annotation(GraphModel):
    _safe_id = field_validator("id")(safe_identifier)
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
    kind: Literal["note", "annotation"] = "note"
    text: str = Field(default="", max_length=4000)
    position: Position
    width: float = Field(default=240, ge=160, le=1000)

class EditorSettings(GraphModel):
    snap_to_grid: bool = True
    connection_style: Literal["bezier", "orthogonal"] = "bezier"

class VisualWorkflowDefinition(GraphModel):
    schema_version: Literal[2] = 2
    catalog_version: Literal[1] = 1
    nodes: list[VisualNode] = Field(default_factory=list, max_length=500)
    edges: list[VisualEdge] = Field(default_factory=list, max_length=1500)
    groups: list[VisualGroup] = Field(default_factory=list, max_length=100)
    viewport: Viewport = Field(default_factory=lambda: Viewport(x=0, y=0, zoom=1))
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    editor: EditorSettings = Field(default_factory=EditorSettings)
    annotations: list[Annotation] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    block_contract: BlockContract | None = None
    block_references: list[BlockReference] = Field(default_factory=list, max_length=100)
    mapping_presets: list[MappingPreset] = Field(default_factory=list, max_length=30)
    variables: dict[str, str | float | bool] = Field(default_factory=dict, max_length=50)

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, tags):
        if any(not tag.strip() or len(tag) > 60 for tag in tags):
            raise ValueError("Tags must contain 1–60 characters")
        return list(dict.fromkeys(tags))

    @field_validator("variables")
    @classmethod
    def valid_variables(cls, values):
        import re
        from app.apps.power_apps.node_registry import expression_paths
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in values):
            raise ValueError("Variable names must be safe property identifiers")
        expression_paths(values)
        if any(isinstance(value, str) and "{{" in value for value in values.values()):
            raise ValueError("Workflow variables must be literal non-secret values")
        return values

    @model_validator(mode="after")
    def shape_is_safe(self):
        by_id = {node.id: node for node in self.nodes}
        if len(by_id) != len(self.nodes) or len({e.id for e in self.edges}) != len(self.edges):
            raise ValueError("Node and edge IDs must be unique")
        edges_seen = set()
        port_counts = {}
        adjacent = {key: [] for key in by_id}
        indegree = dict.fromkeys(by_id, 0)
        for edge in self.edges:
            if edge.source not in by_id or edge.target not in by_id:
                raise ValueError("Edges must reference existing nodes")
            source = NODES[by_id[edge.source].type]
            target = NODES[by_id[edge.target].type]
            output = next((p for p in ports(by_id[edge.source], "outputs") if p["id"] == edge.source_port), None)
            input_port = next((p for p in ports(by_id[edge.target], "inputs") if p["id"] == edge.target_port), None)
            if not output or not input_port or output["data_type"] != input_port["data_type"]:
                raise ValueError("Incompatible connection ports")
            key = (edge.source, edge.source_port, edge.target, edge.target_port)
            if key in edges_seen:
                raise ValueError("Duplicate connections are forbidden")
            edges_seen.add(key)
            for node_id, port, direction in [(edge.source, output, "out"), (edge.target, input_port, "in")]:
                count_key = (node_id, port["id"], direction)
                port_counts[count_key] = port_counts.get(count_key, 0) + 1
                if port_counts[count_key] > port.get("max_connections", 1):
                    raise ValueError("Port connection limit exceeded")
            adjacent[edge.source].append(edge.target)
            indegree[edge.target] += 1
        pending = [key for key, degree in indegree.items() if degree == 0]
        visited = 0
        while pending:
            key = pending.pop(); visited += 1
            for child in adjacent[key]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    pending.append(child)
        if visited != len(by_id):
            raise ValueError("Arbitrary graph cycles are forbidden; use a bounded Loop node")
        grouped = set()
        group_ids = set()
        for group in self.groups:
            if group.id in by_id or group.id in group_ids:
                raise ValueError("Group IDs must be unique and distinct from node IDs")
            group_ids.add(group.id)
            for node_id in group.node_ids:
                if node_id not in by_id or node_id in grouped:
                    raise ValueError("A node can belong to only one valid group")
                grouped.add(node_id)
        annotation_ids = [item.id for item in self.annotations]
        if len(set(annotation_ids)) != len(annotation_ids) or set(annotation_ids) & (set(by_id) | group_ids):
            raise ValueError("Annotation IDs must be unique and distinct")
        for reference in self.block_references:
            if any(key not in by_id for key in reference.node_ids): raise ValueError("Block instances must reference existing nodes")
        if self.block_contract:
            names = set()
            for parameter in self.block_contract.inputs + self.block_contract.outputs:
                if parameter.node_id not in by_id:raise ValueError("Block contracts must reference member nodes")
                if parameter in self.block_contract.inputs and parameter.field not in {f["key"] for f in NODES[by_id[parameter.node_id].type]["fields"]}:raise ValueError("Unknown block input field")
                if parameter in self.block_contract.outputs and parameter.field not in NODES[by_id[parameter.node_id].type]["output_schema"]:raise ValueError("Unknown block output field")
                name=("input" if parameter in self.block_contract.inputs else "output",parameter.name)
                if name in names:raise ValueError("Block parameter names must be unique")
                names.add(name)
        return self
