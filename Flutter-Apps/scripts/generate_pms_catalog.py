"""Generate mobile form contracts; reads documentation, writes only Flutter-Apps."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / 'docs/mobile-api-reference'
source = json.loads((DOCS / 'openapi.json').read_text())
unavailable = {(x['method'].lower(), x['path']) for x in json.loads((DOCS / 'deployment-check.json').read_text())['local_only_operations']}
schemas = source['components']['schemas']

def resolve(schema, depth=0):
    if depth > 24:
        return {'type': 'object', 'properties': {}}
    if '$ref' in schema:
        return resolve(schemas[schema['$ref'].split('/')[-1]], depth+1)
    schema = dict(schema)
    if 'anyOf' in schema:
        alternatives = schema.pop('anyOf')
        options = [x for x in alternatives if x.get('type') != 'null']
        decimal_string = len(options)==2 and {'number','string'}=={x.get('type') for x in options}
        preferred = next((x for x in options if x.get('type') in {'object', 'array', 'integer', 'number'} or '$ref' in x), options[0] if options else {})
        schema = {**resolve(preferred, depth+1), **schema}
        if decimal_string: schema['decimalString'] = True
        if any(x.get('type')=='null' for x in alternatives): schema['nullable']=True
        if len(options)>1 and not decimal_string:
            schema['variants']=[resolve(x,depth+1) for x in options]
    if 'allOf' in schema:
        for item in schema.pop('allOf'):
            schema.update(resolve(item, depth+1))
    if 'properties' in schema:
        schema['properties'] = {k: resolve(v, depth+1) for k,v in schema['properties'].items()}
    if 'items' in schema:
        schema['items'] = resolve(schema['items'], depth+1)
    if isinstance(schema.get('additionalProperties'),dict):
        schema['additionalProperties']=resolve(schema['additionalProperties'],depth+1)
    return schema

def area(path):
    if '/business/' in path or '/billing' in path or '/commercial' in path or '/invoices' in path or '/clients' in path: return 'Clients & commercial'
    if any(x in path for x in ['/chat', '/direct-conversations', '/messaging']): return 'Messages'
    if any(x in path for x in ['/reports/', '/analytics', '/portfolio', '/dashboard', '/workload', '/velocity']): return 'Insights'
    if any(x in path for x in ['/time-', '/timesheets', '/timer']): return 'Time tracking'
    if any(x in path for x in ['/sprint', '/backlog', '/epic', '/release', '/milestone', '/roadmap', '/gantt', '/planner', '/risks', '/components']): return 'Planning'
    if any(x in path for x in ['/recovery', '/trash', '/data-backups', '/admin/']): return 'Recovery & administration'
    if any(x in path for x in ['/automation', '/forms', '/tools', '/custom-fields', '/task-types', '/tag-manager', '/dev-integrations', '/workflow']): return 'Configuration'
    if any(x in path for x in ['/docs', '/notes', '/files', '/attachments']): return 'Documents & files'
    if any(x in path for x in ['/members', '/invitations', '/teams', '/org-chart']): return 'People & teams'
    return 'Work & activity'

operations=[]
for path, methods in source['paths'].items():
    if not path.startswith('/api/v1/project-management/'):
        continue
    for method, item in methods.items():
        if method not in {'get','post','put','patch','delete'}: continue
        content = item.get('requestBody',{}).get('content',{})
        mime = next(iter(content), 'application/json')
        response_types = {m for r in item.get('responses',{}).values() for m in r.get('content',{})}
        internal = '/webhook/' in path or '/realtime' in path or path.endswith('/module-info')
        # Global disaster-recovery/reset handlers are deliberately not general-user actions.
        restricted = '/admin/workspaces' in path or '/data-backups' in path
        operations.append({'id':item['operationId'],'method':method.upper(),
          'path':path.removeprefix('/api/v1'),'title':item.get('summary','Open').replace('Pms ','').replace('Task Checklist Entry','Checklist item'),
          'area':area(path), 'description':item.get('description',''),
          'parameters':[{**p,'schema':resolve(p.get('schema',{}))} for p in item.get('parameters',[])],
          'body':resolve(content.get(mime,{}).get('schema',{})), 'mime':mime,
          'download': any(m not in {'application/json','text/event-stream'} for m in response_types) or any(x in path for x in ['/download','/export']),
          'available':(method,path) not in unavailable,'internal':internal,'restricted':restricted})
assets=ROOT/'assets';assets.mkdir(exist_ok=True)
(assets/'pms_catalog.json').write_text(json.dumps({'operations':operations},separators=(',',':')),encoding='utf-8')
coverage={'source':'docs/mobile-api-reference/openapi.json','total':len(operations),
 'deployed':sum(o['available'] for o in operations),
 'internal': [o for o in operations if o['internal']],
 'restricted': [o for o in operations if o['restricted']],
 'undeployed': [o for o in operations if not o['available']],
 'mobile_form_operations':sum(o['available'] and not o['internal'] and not o['restricted'] for o in operations)}
(ROOT/'qa/pms-coverage.json').write_text(json.dumps(coverage,indent=2),encoding='utf-8')
print({k:v for k,v in coverage.items() if isinstance(v,(int,str))})
