from pathlib import Path
import json,re,runpy
root=Path('.')
p=root/'docs/ui-v2/route-coverage.json'; report=json.loads(p.read_text(encoding='utf-8'))
smoke={r['path']:r for r in json.loads((root/'docs/ui-v2/route-smoke.json').read_text(encoding='utf-8'))}
for route in report['routes']:
    result=smoke.get(route['path'])
    route['implementation']='Shared theme, typography, shell and component foundations applied; page-specific behavior retained.'
    route['testing']=('Route smoke: '+result['outcome']+'; this does not certify every workflow.') if result else 'Not included in recorded route smoke.'
    route['issues']=['Dynamic-record setup or workflow review still required.'] if not result or result['outcome']!='rendered' else []
    if route['path']=='/pms/projects/:projectId':
        route['issues']=[]
        route['testing']='Original missing-record crash repaired; regression test verifies recoverable 403 state. Accessible project workflow tested separately.'
    if route['path']=='/pms/dashboards':
        route['implementation']='Persistent dashboard builder, permissions, revisions, widget data engine and responsive UI implemented.'
        route['testing']='API and real-browser creation/edit/drag/resize/save/conflict/history/export/mobile tests passed; see dashboard report.'
    # Resolve imports to report actual API dependencies and explicitly labelled actions.
    source=root/route['source']; component=route.get('component','')
    if source.exists():
        text=source.read_text(encoding='utf-8-sig',errors='replace')
        match=re.search(r'import\s+'+re.escape(component)+r'\s+from\s+[\"\x27]([^\"\x27]+)',text)
        target=(source.parent/match.group(1)) if match else source.parent/component
        candidates=[target.with_suffix('.tsx'),target.with_suffix('.ts'),target/'index.tsx']
        actual=next((candidate for candidate in candidates if candidate.exists()),None)
        if actual:
            text=actual.read_text(encoding='utf-8-sig',errors='replace');route['componentSource']=actual.as_posix()
            route['actions']=sorted(set(re.findall(r'<(?:Button|button)\b[^>]*>\s*([A-Za-z][A-Za-z &/…-]{2,65})\s*<',text)))
            route['dataDependencies']=sorted(set(re.findall(r'\b(?:api|\w+Api)\.(?:get|post|put|patch|delete)\(\s*[\"\x27`]([^\"\x27`]+)',text))) or route.get('dataDependencies',[])
        route['inventoryNote']='Static declarations and visible labels only; runtime actions may be permission-dependent.'
report['verificationScope']='Recorded route smoke plus representative end-to-end workflows, not exhaustive workflow certification.'
p.write_text(json.dumps(report,indent=2),encoding='utf-8')
module=runpy.run_path('backend/app/apps/project_management/dashboard_config.py')
widgets=list(module['WIDGETS'].values())
(root/'docs/ui-v2/widget-catalog.json').write_text(json.dumps({'supported':sum(not w['requirement'] for w in widgets),'unavailable':sum(bool(w['requirement']) for w in widgets),'widgets':widgets},indent=2),encoding='utf-8')
