"""Server-owned execution capability registry, independent of editor claims."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from app.apps.power_apps.studio import local_node
from app.apps.power_apps.node_registry import NODES, ports
from app.apps.power_apps.authoring import bounded


@dataclass(frozen=True)
class Executor:
    node_type: str
    version: int = 1
    capabilities: tuple = ("pure_local",)
    permission: str = "power_apps_execute"
    timeout_seconds: int = 10
    retryable: bool = True
    idempotency: str = "transactional"

    @property
    def input_schema(self):
        return NODES[self.node_type]["fields"]

    @property
    def output_schema(self):
        return NODES[self.node_type]["output_schema"]

    def execute(self, node, config, payload, previous):
        if self.node_type == "error_handler":
            return {"value": config.get("message") or "Error handled"}, {"out"}
        if self.node_type == "scheduled_trigger":
            return {"scheduled_at": payload["scheduled_at"]}, {"out"}
        if self.node_type in {
            "webhook_trigger",
            "record_created",
            "record_updated",
            "status_changed",
        }:
            output = (
                {"body": payload}
                if self.node_type == "webhook_trigger"
                else {"record": payload.get("record", payload)}
            )
            return output, {"out"}
        if self.node_type == "merge":
            strategy = config.get("strategy", "all")
            return {
                "value": (
                    dict(zip(config.get("keys", []), previous))
                    if strategy == "keyed"
                    else (
                        previous[:1]
                        if strategy in {"first", "first_completed", "first_successful"}
                        else previous
                    )
                )
            }, {"out"}
        if self.node_type in {"delay", "wait_until"}:
            return {"value": "resumed"}, {"out"}
        output, active = local_node(node.type, config, payload, previous)
        return bounded(output), (
            active
            if active is not None
            else {
                p["id"]
                for p in ports(node, "outputs")
                if p["data_type"] == "flow" and p["id"] != "error"
            }
        )


PURE = {
    "error_handler",
    "manual_trigger",
    "if_else",
    "compare_values",
    "check_empty",
    "and_or",
    "filter",
    "switch",
    "route_by_priority",
    "parallel_branch",
    "merge",
    "stop_workflow",
    "set_variable",
    "transform_data",
    "map_fields",
    "evaluate_expression",
    "build_json",
    "parse_json",
    "format_date",
    "format_number",
    "aggregate_values",
    "log_event",
    "delay",
    "wait_until",
    "scheduled_trigger",
    "webhook_trigger",
    "record_created",
    "record_updated",
    "status_changed",
}
EXECUTORS = {
    kind: Executor(
        kind,
        capabilities=(
            ("durable_wait",)
            if kind in {"delay", "wait_until"}
            else ("durable_loop",) if kind in {"loop", "for_each"} else ("pure_local",)
        ),
    )
    for kind in PURE | {"loop", "for_each"}
}


EXECUTORS["approval_wait"] = Executor("approval_wait", capabilities=("durable_approval",), idempotency="transactional")

def capabilities():
    return [
        {
            "node_type": e.node_type,
            "version": e.version,
            "input_schema": e.input_schema,
            "output_schema": e.output_schema,
            "required_capabilities": e.capabilities,
            "permission": e.permission,
            "timeout_seconds": e.timeout_seconds,
            "retryable": e.retryable,
            "idempotency": e.idempotency,
        }
        for e in EXECUTORS.values()
    ]
