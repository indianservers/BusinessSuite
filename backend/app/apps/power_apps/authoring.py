"""Restricted deterministic authoring interpreter; never invokes tools or connectors."""
import json
import math
import re
from copy import deepcopy
from datetime import datetime
from app.apps.power_apps.node_registry import expression_paths
from app.apps.power_apps.authoring_contracts import FieldMapping, Condition


def bounded(value):
    if len(json.dumps(value, allow_nan=False)) > 65536:
        raise ValueError("Data exceeds the 64 KB authoring limit")
    pending=[(value,0)]; count=0
    while pending:
        item,depth=pending.pop(); count+=1
        if depth>16 or count>5000: raise ValueError("Data exceeds depth/complexity limits")
        if isinstance(item,dict): pending.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list): pending.extend((v,depth+1) for v in item)
    expression_paths(value)
    return value


def path(value, selector):
    if not isinstance(selector,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+))*",selector):
        raise ValueError("Use a safe dotted JSON path")
    for part in selector.split("."):
        if part.startswith("__") or part in {"prototype","constructor"}: raise ValueError("Unsafe path")
        if isinstance(value,dict): value=value.get(part)
        elif isinstance(value,list) and part.isdigit(): value=value[int(part)] if int(part)<len(value) else None
        else: return None
    return value


def compare_rule(rule):
    left,right,op=rule.get("left"),rule.get("right"),rule.get("operator","equals")
    if op=="equals": return (type(left) is type(right) or (type(left) in (int,float) and type(right) in (int,float))) and left==right
    if op=="not_equals": return not compare_rule({"left":left,"right":right})
    if op in {"greater_than","less_than","greater_or_equal","less_or_equal"}:
        if type(left) not in (int,float) or type(right) not in (int,float): raise ValueError("Numeric comparisons require numbers; use explicit conversion")
        return {"greater_than":left>right,"less_than":left<right,"greater_or_equal":left>=right,"less_or_equal":left<=right}[op]
    if op in {"contains","starts_with","ends_with"}:
        if not isinstance(left,str) or not isinstance(right,str): raise ValueError("Text comparison requires strings")
        return right in left if op=="contains" else left.startswith(right) if op=="starts_with" else left.endswith(right)
    if op in {"is_empty","is_not_empty"}: return (left in (None,"",[],{})) == (op=="is_empty")
    if op in {"in_list","not_in_list"}:
        if not isinstance(right,list): raise ValueError("List comparison requires an array")
        return any(type(left) is type(v) and left==v for v in right) == (op=="in_list")
    if op in {"date_before","date_after"}:
        a,b=datetime.fromisoformat(str(left).replace("Z","+00:00")),datetime.fromisoformat(str(right).replace("Z","+00:00"))
        return a<b if op=="date_before" else a>b
    if op=="boolean_equals":
        if type(left) is not bool or type(right) is not bool: raise ValueError("Boolean comparison requires boolean values")
        return left==right
    raise ValueError("Unknown comparison")


def condition(value, depth=0):
    if depth>8: raise ValueError("Condition nesting exceeds 8 levels")
    if "rules" not in value: return compare_rule(value)
    if not value["rules"]: raise ValueError("A condition group needs at least one rule")
    results=[condition(rule,depth+1) for rule in value["rules"]]
    return all(results) if value.get("join","and")=="and" else any(results)


def convert(value, target):
    if target=="string":
        if isinstance(value,(dict,list)) or value is None: raise ValueError("String conversion requires a scalar")
        return str(value).lower() if isinstance(value,bool) else str(value)
    if target=="number":
        if isinstance(value,bool) or value is None or isinstance(value,(dict,list)): raise ValueError("Cannot convert to number")
        number=float(value)
        if not math.isfinite(number): raise ValueError("Number must be finite")
        return number
    if target=="boolean":
        if type(value) is bool:return value
        if value in ("true","false"):return value=="true"
        raise ValueError("Boolean conversion accepts only true/false")
    if target in {"object","array"}:
        parsed=json.loads(value) if isinstance(value,str) else value
        if not isinstance(parsed,dict if target=="object" else list):raise ValueError("JSON type mismatch")
        return parsed
    raise ValueError("Unsupported explicit conversion")


def operations(value, items, depth=0):
    if depth>4 or len(items)>12:raise ValueError("Transformation limits exceeded")
    for item in items:
        op,arg=item["op"],item.get("argument")
        if op=="default": value=arg if value is None else value
        elif op=="convert":value=convert(value,arg)
        elif op=="concat":
            if not isinstance(value,str) or not isinstance(arg,list) or any(not isinstance(v,str) for v in arg):raise ValueError("Concatenation requires strings")
            value=value+"".join(arg)
        elif op=="path":value=path(value,arg)
        elif op=="format_date":
            formats={"iso":None,"date":"%Y-%m-%d","year-month":"%Y-%m"}
            if arg not in formats:raise ValueError("Unsupported date format")
            date=datetime.fromisoformat(str(value).replace("Z","+00:00"));value=date.isoformat() if arg=="iso" else date.strftime(formats[arg])
        elif op=="format_number":
            if type(value) not in (int,float) or type(arg) is not int or not 0<=arg<=8:raise ValueError("Provide a number and 0–8 decimal digits")
            value=f"{value:.{arg}f}"
        elif op in {"filter","map"}:
            if not isinstance(value,list) or len(value)>1000:raise ValueError("Array operation requires up to 1000 items")
            if op=="map":value=[operations(v,arg,depth+1) for v in value]
            else:
                if not isinstance(arg,dict):raise ValueError("Array filter requires a condition")
                value=[v for v in value if compare_rule({**arg,"left":path(v,arg["path"]) if arg.get("path") else v})]
        elif op=="rename":
            if not isinstance(value,dict) or not isinstance(arg,dict) or any(not isinstance(v,str) for v in arg.values()):raise ValueError("Key renaming requires an object and string names")
            keys=[arg.get(k,k) for k in value]
            if len(set(keys))!=len(keys):raise ValueError("Renaming would overwrite a key")
            value={arg.get(k,k):v for k,v in value.items()}
        elif op=="lookup":
            if not isinstance(arg,dict) or isinstance(value,(dict,list)):raise ValueError("Lookup requires a scalar and an object")
            value=arg.get(str(value))
        elif op=="conditional":
            if not isinstance(arg,dict):raise ValueError("Conditional mapping requires condition/then/else")
            value=arg.get("then") if condition({**arg["condition"],"left":value}) else arg.get("else")
        else:raise ValueError("Unknown transformation operator")
        bounded(value)
    return value


def map_value(mapping, context):
    from app.apps.power_apps.studio import resolve
    item=FieldMapping.model_validate(mapping)
    try:value=resolve(item.source,context) if item.source else deepcopy(item.constant)
    except ValueError as exc:
        if not str(exc).startswith("No test input for "):raise
        value=None
    value=operations(value,resolve([op.model_dump() for op in item.operations],context))
    if value is None:
        if not item.nullable:raise ValueError("Null requires explicit nullable or a default")
        return None
    types={"string":str,"number":(int,float),"boolean":bool,"array":list,"object":dict,"date":str,"datetime":str}
    if item.target_type!="any" and (not isinstance(value,types[item.target_type]) or (item.target_type=="number" and isinstance(value,bool))):raise ValueError("Mapped value is incompatible with the target type; add an explicit conversion")
    if item.target_type in {"date","datetime"}:datetime.fromisoformat(value.replace("Z","+00:00"))
    return bounded(value)


def redact_debug(value):
    """Redact recognizable secret text from reports, never from interpreter state."""
    from app.ai_agents.services.advanced_security import AiDataRedactionService
    if isinstance(value,str):return AiDataRedactionService().redact_text(value)
    if isinstance(value,dict):return {key:redact_debug(item) for key,item in value.items()}
    if isinstance(value,list):return [redact_debug(item) for item in value]
    return value
