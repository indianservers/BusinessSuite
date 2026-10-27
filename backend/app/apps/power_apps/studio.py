"""Deterministic design-time validation and pure preview. No network/DB writes."""
import json
import math
import re
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.apps.power_apps.node_registry import NODES, TOKEN, expression_paths, ports


def topology(graph):
    by_id = {node.id: node for node in graph.nodes}
    incoming = {key: [] for key in by_id}
    outgoing = {key: [] for key in by_id}
    for edge in graph.edges:
        incoming[edge.target].append(edge)
        outgoing[edge.source].append(edge)
    degree = {key: len(edges) for key, edges in incoming.items()}
    pending = deque(key for key in by_id if degree[key] == 0)
    order = []
    while pending:
        key = pending.popleft(); order.append(key)
        for edge in outgoing[key]:
            degree[edge.target] -= 1
            if degree[edge.target] == 0:
                pending.append(edge.target)
    ancestors = {}
    for key in order:
        ancestors[key] = set()
        for edge in incoming[key]:
            ancestors[key].add(edge.source)
            ancestors[key].update(ancestors.get(edge.source, set()))
    return by_id, incoming, outgoing, order, ancestors


def validate_graph(graph):
    by_id, incoming, outgoing, order, ancestors = topology(graph)
    issues = []
    def issue(code, message, node=None, field=None, severity="error"):
        issues.append({"code": code, "message": message, "node_id": node, "field": field, "severity": severity})
    try:
        ZoneInfo(graph.settings.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        issue("timezone", "Unknown workflow timezone", field="settings.timezone")
    triggers = [node for node in graph.nodes if NODES[node.type]["trigger"]]
    if len(triggers) != 1:
        issue("trigger_count", "A workflow must have exactly one trigger")
    root = triggers[0].id if len(triggers) == 1 else None
    for node in graph.nodes:
        definition = NODES[node.type]
        if node.disabled:
            issue("disabled", "Disabled node blocks this path during preview", node.id, severity="warning")
        if root and node.id != root and root not in ancestors[node.id]:
            issue("disconnected", "This node is not reachable from the trigger", node.id)
        for field in definition["fields"]:
            value = node.config.get(field["key"])
            if field["key"] in node.mappings: continue
            if node.config.get("condition") and field["key"] in {"left","right","operator"}: continue
            if field["required"] and (value is None or value == "" or value == []):
                issue("required", field["label"] + " is required", node.id, field["key"])
            if value and field["kind"] in {"date", "datetime"}:
                try:
                    datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except ValueError:
                    issue("date", "Use a valid ISO date or date/time", node.id, field["key"])
        if definition["requires_credential"] and not node.credential_reference:
            issue("credential", "A credential reference is required; no secret is sent to the editor", node.id, "credential_reference")
        if node.type == "scheduled_trigger":
            schedule = node.config.get("schedule", "")
            if schedule and (len(schedule.split()) != 5 or not re.fullmatch(r"[0-9*/?, -]+", schedule)):
                issue("schedule", "Use a five-field cron schedule", node.id, "schedule")
            try:
                ZoneInfo(node.config.get("timezone", "UTC"))
            except (ZoneInfoNotFoundError, ValueError):
                issue("timezone", "Unknown IANA timezone", node.id, "timezone")
        try:
            paths = expression_paths({"config":node.config,"mappings":{key:value.model_dump() for key,value in node.mappings.items()}})
        except ValueError as exc:
            issue("expression", str(exc), node.id); paths = []
        for path in paths:
            parts = path.split(".")
            if parts[0] == "steps":
                referenced = by_id.get(parts[1])
                if not referenced or parts[1] not in ancestors[node.id]:
                    issue("reference", "Variables must reference an upstream node: " + parts[1], node.id)
                elif len(parts) > 3 and parts[3] not in NODES[referenced.type]["output_schema"]:
                    issue("output_field", "Unknown output field: " + parts[3], node.id)
            elif parts[0] == "workflow":
                if parts[2] not in graph.variables and not any(by_id[key].type=="set_variable" and by_id[key].config.get("name")==parts[2] for key in ancestors[node.id]):
                    issue("reference", "Unknown workflow variable: " + parts[2], node.id)
            elif parts[0] == "env":
                pass  # Only the authorized environment name is supported.
            elif not root or root not in ancestors[node.id]:
                issue("reference", "Trigger variables are only available downstream of the trigger", node.id)
        required_ports = {"if_else": ["true", "false"], "filter": ["true", "false"], "compare_values": ["true", "false"], "and_or": ["true", "false"], "parallel_branch": ["route_1", "route_2"], "switch": ["route_1", "route_2", "default"], "loop": ["body", "done"], "for_each": ["body", "done"]}.get(node.type, [])
        if node.type == "switch" and node.config.get("routes"): required_ports=[route["id"] for route in node.config["routes"]]+["default"]
        if node.type == "merge" and node.config.get("strategy")=="keyed":
            keys=node.config.get("keys",[])
            if not isinstance(keys,list) or len(keys)!=len(incoming[node.id]) or len(set(map(str,keys)))!=len(keys):issue("merge_keys","Keyed merges need one unique key per incoming branch",node.id)
        connected = {edge.source_port for edge in outgoing[node.id]}
        for port in required_ports:
            if port not in connected:
                issue("branch", "Connect the " + port + " branch", node.id)
        if node.advanced.error_strategy == "branch" and "error" not in connected:
            issue("error_branch", "Connect an error handler or select a different error strategy", node.id)
        from app.apps.power_apps.runtime_executors import EXECUTORS
        if node.type not in EXECUTORS:
            issue("runtime_unavailable", "No production executor is registered for this node", node.id, severity="warning")
    return {"valid": not any(item["severity"] == "error" for item in issues), "executable": False,
        "issues": issues, "node_count": len(graph.nodes), "edge_count": len(graph.edges), "catalog_version": 1}


def resolve(value, context):
    if isinstance(value, dict):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, context) for item in value]
    if not isinstance(value, str):
        return value
    def lookup(path):
        current = context
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise ValueError("No test input for " + path)
            current = current[part]
        return current
    paths = expression_paths(value)
    if not paths:
        return value
    match = TOKEN.fullmatch(value.strip())
    if match:
        return lookup(match.group(1).strip())
    return TOKEN.sub(lambda m: str(lookup(m.group(1).strip())), value)


def compare(config):
    left, right = config.get("left"), config.get("right")
    op = config.get("operator", "equals")
    if op == "equals": return left == right
    if op == "not_equals": return left != right
    if op == "greater_than": return float(left) > float(right)
    if op == "less_than": return float(left) < float(right)
    if op == "contains": return str(right) in str(left)
    if op == "starts_with": return str(left).startswith(str(right))
    from app.apps.power_apps.authoring import compare_rule
    return compare_rule(config)


def local_node(node_type, config, test_input, incoming_outputs):
    """An explicit allowlist of pure transformations, never integration adapters."""
    routes = None
    if node_type == "manual_trigger":
        output = {"input": test_input, "record": test_input.get("record", {})}
    elif node_type in {"if_else", "filter", "compare_values", "check_empty", "and_or"}:
        if config.get("condition"):
            from app.apps.power_apps.authoring import condition
            result=condition(config["condition"])
        elif node_type == "check_empty": result = config.get("value") in (None, "", [], {})
        elif node_type == "and_or":
            values = config.get("values", [])
            if not isinstance(values, list) or any(not isinstance(v, bool) for v in values):
                raise ValueError("AND / OR expects boolean values")
            result = all(values) if config.get("operator") == "and" else any(values)
        else: result = compare(config)
        output, routes = {"result": result}, {"true" if result else "false"}
    elif node_type == "switch" and config.get("routes"):
        route=next((row["id"] for row in config["routes"] if type(row.get("value")) is type(config.get("value")) and row.get("value")==config.get("value")),"default")
        output,routes={"route":route},{route}
    elif node_type == "switch":
        route = next((key for key, item in config.get("cases", {}).items() if item == config.get("value") and key in {"route_1", "route_2"}), "default")
        output, routes = {"route": route}, {route}
    elif node_type == "route_by_priority":
        route = "route_1" if str(config.get("value")).lower() in {"critical", "high", "urgent"} else "route_2"
        output, routes = {"value": config.get("value")}, {route}
    elif node_type == "parallel_branch": output, routes = {"value": incoming_outputs}, {"route_1", "route_2"}
    elif node_type == "merge":
        strategy=config.get("strategy","all")
        if strategy in {"first_successful","first_completed"}:raise ValueError("Concurrent join timing requires the production executor")
        output={"value":dict(zip(config.get("keys",[]),incoming_outputs)) if strategy=="keyed" else incoming_outputs[:1] if strategy=="first" else incoming_outputs}
    elif node_type == "stop_workflow": output, routes = {"value": config.get("reason", "Stopped")}, set()
    elif node_type == "set_variable": output = {"value": config.get("value")}
    elif node_type in {"transform_data", "map_fields"}: output = {"value": config.get("mapping", {})}
    elif node_type == "evaluate_expression": output = {"value": config.get("expression")}
    elif node_type == "build_json": output = {"value": config.get("value", {})}
    elif node_type == "parse_json":
        raw = config.get("value", "")
        if not isinstance(raw, str) or len(raw) > 32768: raise ValueError("JSON text must be a bounded string")
        output = {"value": json.loads(raw)}
        pending = [(output, 0)]; visited = 0
        while pending:
            item, depth = pending.pop(); visited += 1
            if depth > 16 or visited > 5000: raise ValueError("Parsed JSON is too deeply nested or complex")
            if isinstance(item, dict): pending.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list): pending.extend((v, depth + 1) for v in item)
            elif isinstance(item, float) and not math.isfinite(item): raise ValueError("JSON numbers must be finite")
        expression_paths(output)
    elif node_type == "format_date":
        value = datetime.fromisoformat(str(config.get("value")).replace("Z", "+00:00"))
        fmt = config.get("format")
        output = {"value": value.isoformat() if fmt == "iso" else value.strftime("%Y-%m" if fmt == "year-month" else "%Y-%m-%d")}
    elif node_type == "format_number":
        number = float(config.get("value"))
        if not math.isfinite(number): raise ValueError("Number must be finite")
        output = {"value": format(number, "." + str(int(config.get("digits", 2))) + "f")}
    elif node_type == "aggregate_values":
        values = config.get("values", [])
        if not isinstance(values, list) or not values or len(values) > 1000 or any(not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v) for v in values):
            raise ValueError("Provide between 1 and 1000 finite numbers")
        op = config.get("operation")
        output = {"value": len(values) if op == "count" else min(values) if op == "min" else max(values) if op == "max" else sum(values) / len(values) if op == "average" else sum(values)}
    elif node_type == "log_event": output = {"value": config.get("message", "")}
    else: raise ValueError("No local preview is available for this node")
    return output, routes


def preview_graph(graph, test_input, environment="development", synthetic_outputs=None, injected_errors=None):
    if len(json.dumps(test_input)) > 32768 or len(graph.nodes) > 250:
        raise ValueError("Local preview supports up to 250 nodes and 32 KB of test input")
    from app.apps.power_apps.authoring import bounded, map_value, redact_debug
    bounded(test_input); bounded(synthetic_outputs or {})
    if "record" in test_input and not isinstance(test_input["record"],dict):raise ValueError("Trigger record input must be an object")
    synthetic_outputs=synthetic_outputs or {}; injected_errors=set(injected_errors or [])
    known={n.id for n in graph.nodes}
    if (set(synthetic_outputs)|injected_errors)-known:raise ValueError("Simulation fixtures must reference existing nodes")
    validation = validate_graph(graph)
    if not validation["valid"]:
        return {"design_time_only": True, "integration_execution": False, "validation": validation, "timeline": []}
    by_id, incoming, outgoing, order, ancestors = topology(graph)
    context = {"trigger": {"record": test_input.get("record", {}), "input": test_input}, "steps": {}, "workflow": {"variables": graph.variables}, "env": {"name": environment}}
    def inputs_for(node):
        config=resolve(node.config,context)
        for field,mapping in node.mappings.items():config[field]=map_value(mapping.model_dump(),context)
        return bounded(config)
    routes = {}
    timeline = []
    blocked = set()
    for key in order:
        node = by_id[key]; definition = NODES[node.type]
        entry = {"node_id": key, "label": node.label, "status": "not_reached", "input": None, "output": None, "error": None}
        if node.disabled:
            entry["status"] = "disabled"; blocked.add(key); timeline.append(entry); continue
        candidates = [e for e in incoming[key] if e.source not in blocked and (routes.get(e.source) is None or e.source_port in routes.get(e.source, set()))]
        if not definition["trigger"] and not candidates:
            blocked.add(key); timeline.append(entry); continue
        if node.type == "merge" and node.config.get("strategy", "all") == "all" and len(candidates) != len(incoming[key]):
            entry["status"] = "waiting_for_inputs"; blocked.add(key); timeline.append(entry); continue
        if key in synthetic_outputs:
            if definition["preview_supported"] or len([port for port in ports(node,"outputs") if port["data_type"]=="flow"])>1:raise ValueError("Supply inputs for deterministic/branching nodes; fixtures may only replace external scalar-flow actions")
            output=synthetic_outputs[key]
            if not isinstance(output,dict) or set(output)-definition["output_schema"].keys():raise ValueError("Synthetic output must match the declared output keys")
            expected={"number":(int,float),"string":str,"boolean":bool,"array":list,"object":dict}
            for field,value in output.items():
                kind=definition["output_schema"][field]
                if kind in expected and (not isinstance(value,expected[kind]) or (kind=="number" and isinstance(value,bool))):raise ValueError("Synthetic output type does not match its declared schema")
            entry.update(status="synthetic",output=output,error="User-supplied synthetic output. No action executed.")
            context["steps"][key]={"output":output}
            if definition["trigger"]:context["trigger"]={"record":output.get("record",output.get("body",test_input.get("record",{}))),"input":output.get("input",output.get("body",test_input))}
            routes[key]={port["id"] for port in ports(node,"outputs") if port["data_type"]=="flow"}
            entry["active_ports"]=sorted(routes[key]);entry["variables"]={"workflow":graph.variables,"steps":list(context["steps"])}
            timeline.append(entry);continue
        if node.type=="merge" and node.config.get("strategy") in {"first_successful","first_completed"}:
            entry.update(status="not_executable",error="Requires Production Executor: concurrent completion ordering is not simulated")
            blocked.add(key);timeline.append(entry);continue
        if key not in injected_errors and not definition["preview_supported"]:
            entry["status"] = "not_executable"; entry["error"] = "Not Executable Yet. No integration was invoked."
            try:entry["input"]=inputs_for(node)
            except (ValueError,TypeError,KeyError):entry["input"]={"declared_parameters":node.config}
            blocked.add(key); timeline.append(entry); continue
        try:
            if key in injected_errors:raise ValueError("User-injected simulation error")
            config = inputs_for(node)
            if len(json.dumps(config)) > 65536: raise ValueError("Resolved input exceeds the preview limit")
            entry["input"] = config
            previous = [context["steps"][e.source]["output"] for e in candidates if e.source in context["steps"]]
            output, active = local_node(node.type, config, test_input, previous)
            if len(json.dumps(output)) > 65536: raise ValueError("Preview output exceeds the size limit")
            entry["output"], entry["status"] = output, "previewed"
            context["steps"][key] = {"output": output}; routes[key] = active if active is not None else {port["id"] for port in ports(node,"outputs") if port["data_type"]=="flow"}
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
            entry["status"], entry["error"] = "error", str(exc)[:400]
            if node.advanced.error_strategy=="branch" and any(e.source_port=="error" for e in outgoing[key]):
                routes[key]={"error"};context["steps"][key]={"output":{"error":entry["error"]}}
            else:blocked.add(key)
        entry["active_ports"]=sorted(routes.get(key) or [])
        entry["variables"]={"workflow":graph.variables,"steps":list(context["steps"])}
        timeline.append(entry)
    report={"design_time_only": True, "integration_execution": False, "validation": validation, "timeline": timeline}
    if len(json.dumps(report))>2097152:raise ValueError("Simulation report exceeds 2 MB; reduce fixture size or node count")
    return redact_debug(report)
