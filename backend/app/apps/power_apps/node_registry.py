"""Editor contracts are independent of executors; no node is executable in Phase 2."""
import json
import math
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

CATALOG_VERSION = 1
NODES = {item["id"]: item for item in json.loads(Path(__file__).with_name("node_catalog.json").read_text(encoding="utf-8"))["nodes"]}
SECRET_KEYS = {"api_key", "apikey", "secret", "client_secret", "password", "access_token", "refresh_token", "authorization", "private_key", "token"}
PATH = re.compile(r"^(?:workflow\.variables\.[A-Za-z_][A-Za-z0-9_]*|env\.name|trigger\.(?:record|input)(?:\.[A-Za-z_][A-Za-z0-9_]*)*|steps\.[A-Za-z_][A-Za-z0-9_-]*\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$")
TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

def expression_paths(value, _depth=0, _count=None):
    """Parse interpolations as property paths, never Python/JS source code."""
    _count = _count if _count is not None else [0]
    _count[0] += 1
    if _depth > 16 or _count[0] > 5000:
        raise ValueError("Configuration exceeds depth/complexity limits")
    paths = []
    if isinstance(value, str):
        if len(value) > 32768:
            raise ValueError("A configuration value is too long")
        for match in TOKEN.finditer(value):
            path = match.group(1).strip()
            if not PATH.fullmatch(path) or any(part.startswith("__") or part in {"constructor", "prototype"} for part in path.split(".")):
                raise ValueError("Expressions only support safe trigger/step output paths")
            paths.append(path)
        remainder = TOKEN.sub("", value)
        if "{{" in remainder or "}}" in remainder:
            raise ValueError("Malformed workflow expression")
    elif isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalized in SECRET_KEYS or normalized.endswith(("_api_key", "_secret", "_password", "_access_token")) or str(key) in {"__proto__", "constructor", "prototype"}:
                raise ValueError("Inline secrets and unsafe property names are forbidden; use a credential reference")
            paths.extend(expression_paths(item, _depth + 1, _count))
    elif isinstance(value, list):
        for item in value:
            paths.extend(expression_paths(item, _depth + 1, _count))
    return paths

def configuration_errors(type_id, config):
    definition = NODES.get(type_id)
    if definition is None:
        return ["Unsupported node type"]
    if type_id=='approval_wait' and config.get('stage'):
        try:
            from app.apps.power_apps.approvals.contracts import Stage
            Stage.model_validate(config['stage'])
            if expression_paths({k:v for k,v in config['stage'].items() if k!='when'}):return ['Approval stages must use literal published policy configuration']
        except (ValueError,TypeError):return ['Invalid approval stage contract']
    fields = {field["key"]: field for field in definition["fields"]}
    errors = []
    if set(config) - fields.keys():
        errors.append("Unknown configuration fields: " + ", ".join(sorted(set(config) - fields.keys())))
    try:
        expression_paths(config)
    except ValueError as exc:
        errors.append(str(exc))
    for key, value in config.items():
        field = fields.get(key)
        if not field or value is None or value == "":
            continue  # Missing values are draft-valid; validation reports them.
        if field.get("allow_expression") and isinstance(value, str) and TOKEN.search(value):
            continue
        kind = field["kind"]
        valid = True
        if kind == "number":
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and field.get("minimum", -1e9) <= value <= field.get("maximum", 1e9)
        elif kind == "boolean":
            valid = isinstance(value, bool)
        elif kind == "multi-select":
            valid = isinstance(value, list) and len(value) <= 50 and all(item in field.get("options", []) for item in value)
        elif kind == "select":
            valid = value in field.get("options", [])
        elif kind in {"dynamic", "expression"}:
            valid = isinstance(value, (str, int, float, bool, dict, list)) and (not isinstance(value, str) or len(value) <= 32768)
        elif kind == "json":
            valid = isinstance(value, (dict, list))
        else:
            valid = isinstance(value, str) and len(value) <= 32768
        if not valid:
            errors.append(field["label"] + " has an invalid type or value")
        if key == "url" and isinstance(value, str) and "{{" not in value:
            try:
                url = urlsplit(value)
                if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                    errors.append("Use an HTTPS URL without inline credentials, query secrets or fragments")
            except ValueError:
                errors.append("Invalid HTTPS URL")
    try:
        if config.get("condition"):
            from app.apps.power_apps.authoring_contracts import Condition
            Condition.model_validate(config["condition"])
        if config.get("exit_condition"):
            from app.apps.power_apps.authoring_contracts import Condition
            Condition.model_validate(config["exit_condition"])
        routes = config.get("routes")
        if routes:
            if not isinstance(routes,list) or not 1 <= len(routes) <= 12: raise ValueError("Provide 1–12 named branches")
            ids=set()
            for route in routes:
                if not isinstance(route,dict) or set(route)-{"id","label","value"} or not re.fullmatch(r"route_[A-Za-z0-9_]{1,40}",str(route.get("id",""))) or not isinstance(route.get("label"),str) or not 1<=len(route["label"])<=80 or route["id"] in ids:raise ValueError("Named branch identifiers must be safe and unique")
                ids.add(route["id"])
    except (ValueError, TypeError) as exc:
        errors.append(str(exc)[:400])
    return errors

def register_node(definition):
    """Deployment-owned extensions must be installed on the server as well."""
    if definition["id"] in NODES or definition.get("executable"):
        raise ValueError("Duplicate or executable editor registration")
    NODES[definition["id"]] = deepcopy(definition)


def ports(node, direction):
    base = NODES[node.type][direction]
    if node.type == "switch" and direction == "outputs" and node.config.get("routes"):
        return [{"id": route["id"], "label": route["label"], "data_type": "flow", "max_connections": 20} for route in node.config["routes"]] + [port for port in base if port["id"] in {"default", "error"}]
    return base
