from datetime import date, timedelta
from uuid import uuid4
import pytest
from tests.test_ai_operator import setup_operator, plan_for, isolate_generic_http_audit
from app.ai_operator.workbench import tick_rules
from app.ai_operator.jobs import process_batch
from app.ai_operator.models import OperatorRun
from app.ai_operator.workbench_models import AssistantArtifact
from app.apps.project_management.models import PMSTask, PMSChecklistItem, PMSTaskDependency
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/workbench'


def item(client,headers,project,kind,payload,title='Test item'):
    r=client.post(ROOT+'/items',headers=headers,json={'project_id':project,'kind':kind,'title':title,'payload':payload})
    assert r.status_code==200,r.text
    return r.json()


def test_memory_scope_revision_forget_and_brain_context(client,db):
    h,_,p,_=setup_operator(client,db)
    row=item(client,h,p,'memory',{'text':'Orion means mobile release','category':'terminology'})
    session=client.post('/api/v1/ai-operator/brain/sessions',headers=h,json={'project_id':p}).json()
    packet=client.get(f'/api/v1/ai-operator/brain/sessions/{session["id"]}/context',headers=h).json()
    assert packet['context']['project_memory'][0]['text']=='Orion means mobile release'
    other,_=auth_headers(client,db,email=f'other-{uuid4()}@example.com',permissions=['ai_assistant','pms_manage_projects','pms_manage_tasks'])
    assert client.delete(f'{ROOT}/items/{row["id"]}',headers=other).status_code==404
    data={'project_id':p,'kind':'memory','title':'Corrected','payload':{'text':'Orion is the launch'},'revision':99}
    assert client.put(f'{ROOT}/items/{row["id"]}',headers=h,json=data).status_code==409
    data['revision']=1
    assert client.put(f'{ROOT}/items/{row["id"]}',headers=h,json=data).json()['revision']==2
    assert client.delete(f'{ROOT}/items/{row["id"]}',headers=h).status_code==200
    assert not client.get(f'/api/v1/ai-operator/brain/sessions/{session["id"]}/context',headers=h).json()['context']['project_memory']


def test_edited_plan_impact_execution_recovery_and_stale_guard(client,db):
    h,_,p,t=setup_operator(client,db)
    original=db.get(PMSTask,t).priority
    data={'project_id':p,'plan':plan_for(t),'request_key':str(uuid4()),'mode':'atomic'}
    impact=client.post(ROOT+'/impact',headers=h,json=data)
    assert impact.status_code==200,impact.text
    assert impact.json()['changes'][0]['changes'][0]['before']==original
    run=client.post(ROOT+'/plans/preview',headers=h,json=data).json()
    assert run['status']=='awaiting_approval' and db.get(PMSTask,t).priority==original
    assert client.post(f'/api/v1/ai-operator/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']}).status_code==200
    process_batch(db)
    assert db.get(PMSTask,t).priority=='High'
    undo=client.post(f'{ROOT}/runs/{run["id"]}/undo-preview',headers=h)
    assert undo.status_code==200,undo.text
    child=undo.json()['run']
    assert child['status']=='awaiting_approval'
    client.post(f'/api/v1/ai-operator/runs/{child["id"]}/approve',headers=h,json={'plan_hash':child['plan_hash']})
    process_batch(db)
    assert db.get(PMSTask,t).priority==original
    assert db.query(PMSChecklistItem).filter_by(task_id=t).count()==0


def test_schedule_respects_holidays_dependencies_and_capacity(client,db):
    h,u,p,t=setup_operator(client,db)
    task=db.get(PMSTask,t);task.estimated_hours=16
    second=client.post(f'/api/v1/project-management/projects/{p}/tasks',headers=h,json={'title':'QA','task_key':'OP-2'}).json()['id']
    db.add(PMSTaskDependency(task_id=second,depends_on_task_id=t,dependency_type='Finish To Start',lag_days=0));db.commit()
    item(client,h,p,'policy',{'holidays':['2026-10-26'],'skills':{str(u.id):['QA']},'away_user_ids':[u.id]})
    response=client.post(ROOT+'/schedule',headers=h,json={'project_id':p,'task_ids':[second,t],'start_date':'2026-10-24'})
    assert response.status_code==200,response.text
    steps=response.json()['plan']['steps']
    assert steps[0]['task_id']==t and steps[0]['start_date']=='2026-10-27' and steps[0]['due_date']=='2026-10-28'
    assert steps[1]['start_date']=='2026-10-29'
    insights=client.get(ROOT+'/insights',headers=h,params={'project_id':p}).json()
    person=next(row for row in insights['workload'] if row['user_id']==u.id)
    assert person['away'] and person['available_hours']==0 and person['skills']==['QA']


@pytest.mark.parametrize('relationship,expected',[('Finish To Start','2026-10-30'),('Start To Start','2026-10-28'),('Finish To Finish','2026-10-29'),('Start To Finish','2026-10-28')])
def test_schedule_supports_each_dependency_relationship(client,db,relationship,expected):
    h,_,p,t=setup_operator(client,db);db.get(PMSTask,t).estimated_hours=16
    second=client.post(f'/api/v1/project-management/projects/{p}/tasks',headers=h,json={'title':'QA','task_key':'OP-2'}).json()['id']
    db.add(PMSTaskDependency(task_id=second,depends_on_task_id=t,dependency_type=relationship,lag_days=2));db.commit()
    response=client.post(ROOT+'/schedule',headers=h,json={'project_id':p,'task_ids':[second,t],'start_date':'2026-10-26'})
    assert response.status_code==200,response.text
    assert response.json()['plan']['steps'][1]['start_date']==expected


def test_playbook_rules_deduplicate_and_autonomy_is_bounded(client,db):
    h,_,p,t=setup_operator(client,db)
    task=db.get(PMSTask,t);task.status='Blocked';db.commit()
    book=item(client,h,p,'playbook',{'plan':plan_for(t)})
    rule=item(client,h,p,'rule',{'playbook_id':book['id'],'trigger':'blocked','enabled':True,'autonomous':True})
    assert tick_rules(db)['created']==1
    row=db.get(AssistantArtifact,rule['id']);run=db.get(OperatorRun,row.payload['last_run_id'])
    assert run.status=='awaiting_approval' # No standing policy yet.
    assert tick_rules(db)['created']==0
    policy=item(client,h,p,'policy',{'auto_enabled':True,'allowed_tools':['update_task']})
    # Checklist actions are not automatically authorized, even with standing consent.
    row.payload={**row.payload,'fingerprint':'different','next_check_at':None};db.commit()
    tick_rules(db)
    run=db.get(OperatorRun,db.get(AssistantArtifact,rule['id']).payload['last_run_id'])
    assert run.status=='awaiting_approval'


def test_opted_in_small_priority_rule_executes_through_approval_queue(client,db):
    h,_,p,t=setup_operator(client,db)
    task=db.get(PMSTask,t);task.status='Blocked';db.commit()
    plan={'summary':'Escalate blocked priority','steps':[{'tool':'update_task','task_id':t,'changes':{'priority':'Urgent'}}]}
    book=item(client,h,p,'playbook',{'plan':plan})
    item(client,h,p,'policy',{'auto_enabled':True,'allowed_tools':['update_task'],'max_steps':1})
    rule=item(client,h,p,'rule',{'playbook_id':book['id'],'trigger':'blocked','enabled':True,'autonomous':True})
    assert tick_rules(db)['created']==1
    ident=db.get(AssistantArtifact,rule['id']).payload['last_run_id']
    assert db.get(OperatorRun,ident).status=='queued'
    process_batch(db)
    assert db.get(OperatorRun,ident).status=='succeeded' and db.get(PMSTask,t).priority=='Urgent'
    assert tick_rules(db)['created']==0


def test_standing_consent_revocation_stops_queued_automatic_work(client,db):
    h,_,p,t=setup_operator(client,db)
    task=db.get(PMSTask,t);task.status='Blocked';before=task.priority;db.commit()
    plan={'summary':'Escalate blocked priority','steps':[{'tool':'update_task','task_id':t,'changes':{'priority':'Urgent'}}]}
    book=item(client,h,p,'playbook',{'plan':plan})
    policy=item(client,h,p,'policy',{'auto_enabled':True,'allowed_tools':['update_task']})
    rule=item(client,h,p,'rule',{'playbook_id':book['id'],'trigger':'blocked','enabled':True,'autonomous':True})
    tick_rules(db);ident=db.get(AssistantArtifact,rule['id']).payload['last_run_id']
    assert db.get(OperatorRun,ident).status=='queued'
    response=client.put(f'{ROOT}/items/{policy["id"]}',headers=h,json={'project_id':p,'kind':'policy','title':'Revoked','revision':1,'payload':{'auto_enabled':False}})
    assert response.status_code==200,response.text
    process_batch(db)
    assert db.get(PMSTask,t).priority==before
    assert db.get(OperatorRun,ident).status=='paused' and db.get(OperatorRun,ident).error_code=='AUTO_POLICY_REVOKED'


def test_workbench_migrations_are_idempotent_and_preserve_evidence():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    backend=Path(__file__).resolve().parents[1]
    for folder,name in [('alembic','20261024_010_assistant_workbench.py'),('alembic_postgresql','pg_20261024_010_assistant_workbench.py')]:
        engine=sa.create_engine('sqlite://')
        with engine.begin() as connection:
            for table in ['users','pms_projects']:connection.execute(sa.text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)'))
            path=backend/folder/'versions'/name
            spec=importlib.util.spec_from_file_location(name,path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
            connection.execute(sa.text("INSERT INTO pms_assistant_artifacts (id,user_id,project_id,scope_key,kind,key,title,payload,revision) VALUES (42,1,1,'user:1','memory','keep','Retain me','{}',1)"))
            with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
            assert connection.execute(sa.text('SELECT title FROM pms_assistant_artifacts WHERE id=42')).scalar()=='Retain me'
        engine.dispose()


def test_new_task_agent_baselines_and_ignores_deletion(client,db):
    h,_,p,t=setup_operator(client,db)
    book=item(client,h,p,'playbook',{'plan':plan_for(t)})
    rule=item(client,h,p,'rule',{'playbook_id':book['id'],'trigger':'task_created','enabled':True})
    assert tick_rules(db)['created']==0
    second=client.post(f'/api/v1/project-management/projects/{p}/tasks',headers=h,json={'title':'New task','task_key':'OP-2'}).json()['id']
    row=db.get(AssistantArtifact,rule['id']);row.payload={**row.payload,'next_check_at':None};db.commit()
    assert tick_rules(db)['created']==1
    from datetime import datetime,timezone
    db.get(PMSTask,second).deleted_at=datetime.now(timezone.utc)
    row=db.get(AssistantArtifact,rule['id']);row.payload={**row.payload,'next_check_at':None};db.commit()
    assert tick_rules(db)['created']==0


def test_project_administrator_reviews_member_teaching_examples(client,db):
    admin,_,p,t=setup_operator(client,db)
    member,_=auth_headers(client,db,email=f'teacher-{uuid4()}@example.com',permissions=['ai_assistant','pms_manage_projects','pms_manage_tasks'])
    row=item(client,member,p,'teaching',{'command':'Raise priority and add QA','plan':plan_for(t)})
    assert client.get(ROOT+'/teaching/review',headers=member,params={'project_id':p}).status_code==403
    review=client.get(ROOT+'/teaching/review',headers=admin,params={'project_id':p})
    assert review.status_code==200,review.text
    assert row['id'] in [r['id'] for r in review.json()['items']]
    assert client.post(f'{ROOT}/items/{row["id"]}/approve-teaching',headers=admin).status_code==200
    assert len(client.get(ROOT+'/teaching/export',headers=admin,params={'project_id':p}).json()['examples'])==1
    changed={'project_id':p,'kind':'teaching','title':'Corrected','revision':2,'payload':{'command':'New wording','plan':plan_for(t)}}
    assert client.put(f'{ROOT}/items/{row["id"]}',headers=member,json=changed).status_code==200
    assert not client.get(ROOT+'/teaching/export',headers=admin,params={'project_id':p}).json()['examples']


def test_recovery_refuses_changed_records_and_policy_requires_admin(client,db):
    h,_,p,t=setup_operator(client,db)
    data={'project_id':p,'plan':plan_for(t),'request_key':str(uuid4())}
    run=client.post(ROOT+'/plans/preview',headers=h,json=data).json()
    client.post(f'/api/v1/ai-operator/runs/{run["id"]}/approve',headers=h,json={'plan_hash':run['plan_hash']})
    process_batch(db)
    db.get(PMSTask,t).title='Edited by another workflow';db.commit()
    response=client.post(f'{ROOT}/runs/{run["id"]}/undo-preview',headers=h)
    assert response.status_code==409,response.text
    regular,_=auth_headers(client,db,email=f'regular-{uuid4()}@example.com',permissions=['ai_assistant','pms_manage_projects','pms_manage_tasks'])
    response=client.post(ROOT+'/items',headers=regular,json={'project_id':p,'kind':'policy','title':'Unsafe','payload':{'auto_enabled':True}})
    assert response.status_code==403,response.text


def test_teaching_review_export_quality_metrics_and_invalid_payload(client,db):
    h,_,p,t=setup_operator(client,db)
    row=item(client,h,p,'teaching',{'command':'Make it important','plan':plan_for(t)})
    assert not client.get(ROOT+'/teaching/export',headers=h,params={'project_id':p}).json()['examples']
    assert client.post(f'{ROOT}/items/{row["id"]}/approve-teaching',headers=h).status_code==200
    assert len(client.get(ROOT+'/teaching/export',headers=h,params={'project_id':p}).json()['examples'])==1
    case=item(client,h,p,'evaluation',{'command':'Raise priority','expected_kind':'task_plan','expected_tools':['update_task','add_checklist']})
    key=str(uuid4());payload={'actual_kind':'task_plan','actual_plan':plan_for(t),'duration_ms':120,'request_key':key}
    endpoint=f'{ROOT}/items/{case["id"]}/evaluate'
    assert client.post(endpoint,headers=h,json=payload).json()['passed']
    assert client.post(endpoint,headers=h,json=payload).json()['passed']
    metrics=client.get(ROOT+'/metrics',headers=h,params={'project_id':p}).json()
    assert len(metrics['evaluations'])==1 and metrics['evaluation_passes']==1
    bad=client.post(ROOT+'/items',headers=h,json={'project_id':p,'kind':'policy','title':'bad','payload':{'weekdays':[9]}})
    assert bad.status_code==422,bad.text
    issue={'project_id':p,'category':'incorrect_plan','request_key':str(uuid4())}
    assert client.post(ROOT+'/feedback',headers=h,json=issue).status_code==200
    assert client.post(ROOT+'/feedback',headers=h,json=issue).status_code==200
    assert client.get(ROOT+'/metrics',headers=h,params={'project_id':p}).json()['feedback_counts']=={'incorrect_plan':1}
