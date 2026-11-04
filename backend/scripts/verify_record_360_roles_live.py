"""Inspect existing local QA memberships; no user or permission mutations."""
from app.db.session import engine
from sqlalchemy import text
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from app.db.init_db import DEMO_USERS

root='http://127.0.0.1:1534/api/v1'
def http(path, token=None, method='GET', body=None, branch=None):
    headers={'Content-Type':'application/json','X-Suite-Organization':'1'}
    if branch: headers['X-Suite-Branch']=branch
    if token: headers['Authorization']='Bearer '+token
    try:
        with urlopen(Request(root+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method),timeout=90) as r:
            return r.status,json.load(r)
    except HTTPError as e:
        return e.code,json.load(e)

with engine.connect() as c:
    print('memberships', [dict(r._mapping) for r in c.execute(text("""
        select m.project_id,m.user_id,m.role,u.is_active
        from pms_project_members m join users u on u.id=m.user_id
        where m.role in ('Viewer','Member','Contributor') and u.is_active
        order by m.role,m.project_id limit 20
    """))])
    print('workspace roles', [tuple(r) for r in c.execute(text('select workspace_id,user_id,role from pms_workspace_members limit 12'))])
    print('test accounts', [tuple(r) for r in c.execute(text("select u.id,r.name from users u join roles r on r.id=u.role_id where u.is_active and not u.is_superuser order by u.id limit 12"))])

output=Path('../docs/qa/record-360/live/roles.json')
policies_only='--policies-only' in sys.argv
checks=[r for r in json.loads(output.read_text()) if 'role' in r] if policies_only else []
for role in ([] if policies_only else ['pms_org_admin','pms_project_manager','pms_team_member','pms_client','crm_sales_executive','employee']):
    actor=next(x for x in DEMO_USERS if x['role']==role)
    status,login=http('/auth/login',method='POST',body={'email':actor['email'],'password':actor['password']})
    assert status==200,(role,'existing demo login',status)
    token=login['access_token']
    status,queue=http('/record-360/work/queue/items?view=all&source_filter=pms_task&cursor_mode=true&per_page=5',token)
    checks.append({'role':role,'queue_status':status,'items':len(queue.get('items',[])),'reason':queue.get('detail')})
    assert status in (200,403),(role,status)
    if status==200:
        for item in queue['items']:
            task=item['source_id']
            status,links=http(f'/project-management/task-workspace/tasks/{task}/crm-links',token)
            assert status==200,(role,'queue-visible task unreadable',task,status)
            if not links['can_manage']:
                denied,_=http(f'/project-management/task-workspace/tasks/{task}/crm-links',token,'POST',{'kind':'contact','record_id':883})
                assert denied==403,(role,'readonly mutation',denied)
    # Unrelated new QA project must not be writable by unrelated roles.
    if role in ('pms_client','employee'):
        status,_=http('/project-management/task-workspace/tasks/2438/crm-links',token,'POST',{'kind':'contact','record_id':883})
        assert status in (403,404),(role,'unrelated task mutation',status)
        checks[-1]['unrelated_link_status']=status
    print('PASS',checks[-1])
output.write_text(json.dumps(checks,indent=2))

# Exercise current persisted employee/intern policies without changing accounts,
# passwords, memberships or grants. Tokens expire after five minutes and stay in memory.
from app.core.security import create_access_token
from datetime import timedelta
for actor_id in [33,35,401,557]:
    token=create_access_token(actor_id,expires_delta=timedelta(minutes=5))
    context_status,branch_context=http('/branches/context',token)
    if actor_id==557:
        status,denied=http('/record-360/work/queue/items?view=all&cursor_mode=true',token)
        assert status==403 and 'Intern' in denied.get('detail','')
        checks.append({'actor_id':actor_id,'queue_status':status,'reason':denied['detail']});print('PASS restricted intern',checks[-1]);continue
    assert context_status==200,(actor_id,context_status,branch_context.get('detail'))
    branch=str(branch_context['selected'])
    status,queue=http('/record-360/work/queue/items?view=all&source_filter=pms_task&cursor_mode=true&per_page=5',token,branch=branch)
    assert status==200,(actor_id,status,queue.get('detail'))
    for option in branch_context['branches']:
        if queue['items']: break
        branch=str(option['id'])
        status,queue=http('/record-360/work/queue/items?view=all&source_filter=pms_task&cursor_mode=true&per_page=5',token,branch=branch)
        assert status==200,(actor_id,branch,status)
    result={'actor_id':actor_id,'queue_status':status,'items':len(queue['items']),'task_checks':[]}
    if actor_id==401: assert queue['items'],(actor_id,'assigned policy returned no work')
    for item in queue['items'][:2]:
        tid=item['source_id'];status,summary=http(f'/record-360/task/{tid}?source=project_management',token,branch=branch)
        assert status==200,(actor_id,tid,status,summary.get('detail'))
        status,links=http(f'/project-management/task-workspace/tasks/{tid}/crm-links',token,branch=branch)
        assert status==200,(actor_id,tid,status)
        result['task_checks'].append({'task_id':tid,'can_manage':links['can_manage']})
        if actor_id in (33,34,35,36):
            assert not links['can_manage']
            denied,_=http(f'/project-management/task-workspace/tasks/{tid}/crm-links',token,'POST',{'kind':'contact','record_id':883},branch=branch)
            assert denied==403,(actor_id,'viewer mutation',denied)
            denied,_=http(f'/project-management/task-workspace/tasks/{tid}/crm-link-options?kind=contact',token,branch=branch)
            assert denied==403,(actor_id,'viewer picker',denied)
            denied,_=http(f'/project-management/task-workspace/tasks/{tid}/crm-links/1',token,'DELETE',branch=branch)
            assert denied==403,(actor_id,'viewer unlink',denied)
    status,denied=http('/record-360/task/2438?source=project_management',token,branch='6')
    result['unassigned_qa_task_status']=status
    assert status in (403,404),(actor_id,'unassigned QA task visible',status)
    checks.append(result);print('PASS assigned policy',result)
output.write_text(json.dumps(checks,indent=2))
