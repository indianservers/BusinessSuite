import json,re
from pathlib import Path
root=Path('frontend/src')
entries={}
for p in list(root.rglob('routes.tsx'))+[root/'App.tsx']:
 s=p.read_text(encoding='utf-8',errors='replace')
 patterns=[(m.group(1),m.start()) for m in re.finditer(r'path\s*[:=]\s*["\']([^"\']+)["\']',s)]+[(m.group(1),m.start()) for m in re.finditer(r'\broute\(["\']([^"\']+)["\']',s)]
 for path,pos in patterns:
  if path=='/*':continue
  path='/'+path.lstrip('/')
  module=path.split('/')[1] or 'suite'
  snippet=s[pos:pos+250]
  component=(re.search(r'element:\s*<([\w]+)',snippet) or re.search(r'element=\{<([\w]+)',snippet))
  component=component.group(1) if component else ('FAMWorkspacePage' if 'fam'==module else 'route factory / redirect')
  files=[f for f in root.rglob(component+'.tsx')]
  code=files[0].read_text(encoding='utf-8',errors='replace') if files else ''
  entries[path]={'path':path,'module':module,'submodule':'/'.join(path.split('/')[2:3]) or 'overview','pageType':'create' if path.endswith('/new') else 'detail' if ':' in path else 'workspace/list','layout':'workspace' if path in ['/pms','/pms/workspaces'] else 'AppLayout' if 'login' not in path and path!='/' else 'public','component':component,'source':str(p).replace('\\','/'),'dynamic':':' in path or '*' in path,'dataDependencies':sorted(set(re.findall(r'\b(\w+(?:API|Api))\.',code))),'actions':sorted(set(re.findall(r'\.(create|update|delete|list|export|upload|restore)\(',code))),'permissions':'canAccessRoute + server authorization; record membership enforced by API','issues':['legacy palette / typography / shared controls require consolidation'],'implementation':'audited; shared foundations pending','testing':'not yet verified'}
Path('docs/ui-v2/route-coverage.json').write_text(json.dumps({'routes':list(entries.values()),'counts':{'routes':len(entries),'routeNamespaces':len(set(x['module'] for x in entries.values()))}},indent=2),encoding='utf-8')
print(json.dumps({'routes':len(entries),'namespaces':sorted(set(x['module'] for x in entries.values()))}))

