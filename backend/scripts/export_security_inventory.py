"""Inventory actual registered and source-only routes without starting services."""
import os
import sys
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['ENVIRONMENT']='test'
from fastapi.routing import APIRoute, APIWebSocketRoute
from app.main import app


def dependencies(value):
    result=[]
    for child in value.dependencies:
        call=child.call
        result.append({'name':getattr(call,'__name__',type(call).__name__),
                       'permissions':sorted(getattr(call,'permissions',[]))})
        result.extend(dependencies(child))
    return result


registered=[]
def walk(routes,prefix=''):
    for route in routes:
        if hasattr(route,'original_router'):
            yield from walk(route.original_router.routes,prefix+route.include_context.prefix)
        else:
            yield prefix,route
for prefix,route in walk(app.routes):
    if isinstance(route,APIRoute):
        registered.append({'path':prefix+route.path,'protocol':'http','methods':sorted(route.methods),
                           'schema_visible':route.include_in_schema,
                           'handler':route.endpoint.__module__+'.'+route.endpoint.__name__,
                           'dependencies':dependencies(route.dependant)})
    elif isinstance(route,APIWebSocketRoute):
        registered.append({'path':prefix+route.path,'protocol':'websocket','methods':['WEBSOCKET'],'schema_visible':False,'handler':route.endpoint.__module__+'.'+route.endpoint.__name__,'dependencies':dependencies(route.dependant),'note':'Handshake and broadcast authorization are enforced in the handler and realtime manager.'})
source=[]
for path in (ROOT/'backend/app').rglob('*.py'):
    try:tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    except (SyntaxError,UnicodeError):continue
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        for decorator in node.decorator_list:
            if isinstance(decorator,ast.Call) and isinstance(decorator.func,ast.Attribute) and decorator.func.attr in {'get','post','put','patch','delete','websocket','route'}:
                segment=decorator.args[0].value if decorator.args and isinstance(decorator.args[0],ast.Constant) else None
                source.append({'file':path.relative_to(ROOT).as_posix(),'line':node.lineno,'method':decorator.func.attr.upper(),'local_path':segment,'handler':node.name})
target=ROOT/'docs/qa/shared-batch-workflow/security-route-inventory.json'
target.write_text(json.dumps({'registered':registered,'source_routes':source,'note':'Dependencies are evidence for manual review, not proof of object-level authorization. Source-only routes may be disabled or belong to embedded applications.'},indent=2),encoding='utf-8')
print(json.dumps({'registered':len(registered),'source_routes':len(source),'hidden_http':sum(not r['schema_visible'] for r in registered if r['protocol']=='http'),'websocket':sum(r['protocol']=='websocket' for r in registered)}))
