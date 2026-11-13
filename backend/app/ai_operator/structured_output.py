"""Closed provider schemas without pretending arbitrary maps are strictly typed.

Open-map workflows retain explicit JSON mode and authoritative domain validation.
Optional fields become nullable on the wire; omitted defaults are restored before
Pydantic validation, preserving the difference between omitted and cleared fields.
"""
from copy import deepcopy


class OpenSchema(ValueError):pass


def _resolve(node,root):
    if '$ref' not in node:return node
    ref=node['$ref']
    if not ref.startswith('#/$defs/'):raise OpenSchema('External schema references are unsupported')
    return root['$defs'][ref.rsplit('/',1)[1]]


def _nullable(node,root):
    node=_resolve(node,root)
    return node.get('type')=='null' or 'null' in (node.get('type') if isinstance(node.get('type'),list) else []) or any(_nullable(n,root) for n in node.get('anyOf',[]))


def closed_schema(schema):
    root=deepcopy(schema)
    def visit(node,depth=0):
        if depth>25:raise OpenSchema('Recursive or oversized schema')
        node=_resolve(node,root)
        value={k:deepcopy(v) for k,v in node.items() if k not in {'$defs','default','title'}}
        if not any(k in value for k in ('type','anyOf','enum','const')):raise OpenSchema('Untyped schema')
        if value.get('type')=='object' or 'properties' in value:
            if 'properties' not in value:raise OpenSchema('Open map schema')
            required=set(value.get('required',[]));properties={}
            for key,item in value['properties'].items():
                child=visit(item,depth+1)
                if key not in required and not _nullable(item,root):child={'anyOf':[child,{'type':'null'}]}
                properties[key]=child
            value.update(properties=properties,required=list(properties),additionalProperties=False)
        if 'items' in value:value['items']=visit(value['items'],depth+1)
        if 'anyOf' in value:value['anyOf']=[visit(item,depth+1) for item in value['anyOf']]
        return value
    try:return visit(root)
    except (OpenSchema,KeyError,TypeError):return None


def restore_omitted_defaults(value,schema):
    def visit(value,node):
        node=_resolve(node,schema)
        if isinstance(value,dict) and 'properties' in node:
            required=set(node.get('required',[]));result={}
            for key,item in value.items():
                prop=node.get('properties',{}).get(key)
                if prop is None:result[key]=item;continue  # Never hide unknown arguments from validation.
                if item is None and key not in required and not _nullable(prop,schema):continue
                result[key]=visit(item,prop)
            return result
        if isinstance(value,list) and 'items' in node:return [visit(item,node['items']) for item in value]
        for branch in node.get('anyOf',[]):
            resolved=_resolve(branch,schema)
            if isinstance(value,dict) and resolved.get('type')=='object':return visit(value,branch)
            if isinstance(value,list) and resolved.get('type')=='array':return visit(value,branch)
        return value
    return visit(value,schema)
