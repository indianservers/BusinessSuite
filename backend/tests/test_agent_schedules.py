import asyncio
import pytest
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_saved_agents import profile
from app.ai_operator.agent_schedules import dispatch
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite/agents/schedules'


@pytest.mark.parametrize('anchor,current,expected',[
    ('2028-01-31T09:00:00+05:30','2028-01-31T04:00:00+00:00','2028-02-29T03:30:00+00:00'),
    ('2028-01-31T09:00:00+05:30','2028-02-29T04:00:00+00:00','2028-03-31T03:30:00+00:00'),
    ('2027-01-31T09:00:00+05:30','2027-01-31T04:00:00+00:00','2027-02-28T03:30:00+00:00'),
    ('2027-01-31T09:00:00+05:30','2027-12-31T04:00:00+00:00','2028-01-31T03:30:00+00:00'),
])
def test_monthly_recurrence_clamps_short_months_without_anchor_drift(anchor,current,expected):
    from app.ai_operator.agent_schedules import next_agent_occurrence
    spec={'frequency':'monthly','scheduled_at':anchor,'timezone':'Asia/Kolkata'}
    assert next_agent_occurrence(spec,datetime.fromisoformat(current))==datetime.fromisoformat(expected)


def test_monthly_schedule_uses_existing_preview_and_activation(client,db):
    h,_,_,value,spec=draft(client,db,frequency='monthly')
    assert value['spec']['frequency']=='monthly'
    enable(client,h,value)
    assert client.get(ROOT,headers=h).json()['items'][0]['status']=='active'


def draft(client,db,**extra):
    h,user,_,_=setup_suite(client,db);agent=profile(client,h)
    first=datetime.now(timezone.utc)+timedelta(hours=1)
    spec={'request_key':str(uuid4()),'agent_id':agent['id'],'prompt':'Create CRM task called Scheduled delivery review',
        'scheduled_at':first.isoformat(),'expires_at':(first+timedelta(days=3)).isoformat(),'frequency':'daily',**extra}
    r=client.post(ROOT+'/preview',headers=h,json=spec);assert r.status_code==200,r.text
    return h,user,agent,r.json(),spec


def enable(client,h,value):
    r=client.post(ROOT+f'/{value["id"]}/activate',headers=h,json={'preview_hash':value['preview_hash']});assert r.status_code==200,r.text


@pytest.mark.parametrize('frequency',['daily','monthly'])
def test_schedule_prepares_one_private_review_and_waits_for_approval(client,db,frequency):
    h,_,_,value,spec=draft(client,db,frequency=frequency,expires_at=(datetime.now(timezone.utc)+timedelta(days=90)).isoformat())
    assert client.post(ROOT+'/preview',headers=h,json=spec).json()['id']==value['id']
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    assert asyncio.run(dispatch(db,client.app,first))['processed']==0
    enable(client,h,value)
    assert asyncio.run(dispatch(db,client.app,first))['processed']==1
    db.expire_all();job=db.get(Job,value['id']);assert job.status=='agent_waiting',job.last_error
    run=db.get(SuiteRun,job.payload_json['pending']['run_id'])
    assert run.status=='awaiting_approval' and run.approval_id and not run.receipts
    assert db.query(CRMTask).count()==0
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=2)))['processed']==0
    assert db.query(SuiteRun).count()==1
    result=client.get('/api/v1/ai-operator/suite/runs/'+str(run.id),headers=h).json()
    approve(client,h,result);tick(client,db)
    assert db.query(CRMTask).count()==1
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=4)))['processed']==1
    db.refresh(job);assert job.status=='agent_active' and len(job.payload_json['occurrences'])==1
    assert job.payload_json['pending'] is None
    if frequency=='monthly':
        from app.ai_operator.agent_schedules import next_agent_occurrence
        from app.ai_operator.reminders import utc
        assert utc(job.run_at)==next_agent_occurrence(value['spec'],first+timedelta(minutes=4))


def test_schedule_hash_revision_expiry_and_private_ownership(client,db):
    h,_,agent,value,spec=draft(client,db)
    assert client.post(ROOT+f'/{value["id"]}/activate',headers=h,json={'preview_hash':'0'*64}).status_code==409
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.post(ROOT+f'/{value["id"]}/cancel',headers=other).status_code==404
    enable(client,h,value)
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','environment','mcp_ids')}
    body.update(revision=1,instructions='A changed profile must be reviewed again.')
    assert client.put('/api/v1/ai-operator/suite/agents/'+str(agent['id']),headers=h,json=body).status_code==200
    asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)))
    db.expire_all();assert db.get(Job,value['id']).status=='agent_blocked'
    assert db.query(SuiteRun).count()==0


def test_cancelled_or_expired_schedule_does_not_plan(client,db):
    h,_,_,value,spec=draft(client,db)
    enable(client,h,value)
    asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['expires_at'])))
    db.expire_all();assert db.get(Job,value['id']).status=='agent_expired'
    assert client.post(ROOT+f'/{value["id"]}/cancel',headers=h).status_code==200
    assert asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['expires_at'])+timedelta(days=1)))['processed']==0
    assert db.query(SuiteRun).count()==0


def test_crash_after_planning_recovers_same_conversation_without_duplicate_run(client,db):
    from app.models.notification import Notification
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    assert asyncio.run(dispatch(db,client.app,first))['processed']==1
    db.expire_all();job=db.get(Job,value['id']);pending=job.payload_json['pending']
    # Recover the durable claim as if the HTTP response arrived but the worker
    # had not yet persisted its result. The canonical command owns deduplication.
    job.status='agent_preparing';job.run_at=first+timedelta(minutes=5)
    job.payload_json={**job.payload_json,'pending':{k:v for k,v in pending.items() if k!='run_id'}};db.commit()
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=4)))['processed']==0
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=6)))['processed']==1
    db.refresh(job);assert job.status=='agent_waiting'
    assert job.payload_json['pending']['run_id']==pending['run_id']
    assert db.query(SuiteRun).count()==1 and db.query(CRMTask).count()==0
    assert db.query(Notification).filter_by(event_type='ai.agent_schedule').count()==1


@pytest.mark.parametrize('mutation',['prompt','session'])
def test_schedule_payload_tampering_or_revoked_session_blocks_planning(client,db,mutation):
    from app.models.user import UserSession
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    job=db.get(Job,value['id'])
    if mutation=='prompt':job.payload_json={**job.payload_json,'spec':{**job.payload_json['spec'],'prompt':'Send messages to all leads'}}
    else:db.get(UserSession,job.payload_json['security_context']['session_id']).status='Revoked'
    db.commit()
    asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)))
    db.refresh(job);assert job.status=='agent_blocked'
    assert db.query(SuiteRun).count()==0


def test_scheduler_migration_creates_unique_request_index_on_native_database(client,db):
    import importlib.util
    from pathlib import Path
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    from sqlalchemy.exc import IntegrityError
    h,user,_,_=setup_suite(client,db)
    pg=db.bind.dialect.name=='postgresql'
    relative='alembic_postgresql/versions/pg_20261111_097_agent_schedules.py' if pg else 'alembic/versions/20261111_080_agent_schedules.py'
    spec=importlib.util.spec_from_file_location('schedule_native_migration',Path(__file__).resolve().parents[1]/relative)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(db.connection())):
        migration.downgrade();migration.upgrade();migration.upgrade()
    value={'organization_id':1,'created_by':user.id,'job_type':'ai_agent_schedule','module_name':'ai','payload_json':{'ai_request_key':'migration-check'}}
    db.execute(Job.__table__.insert(),value)
    with pytest.raises(IntegrityError):
        with db.begin_nested():db.execute(Job.__table__.insert(),value)


def test_schedule_waits_for_corrected_followup_and_tracks_its_receipt(client,db):
    h,_,agent,value,spec=draft(client,db);enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    asyncio.run(dispatch(db,client.app,first));db.expire_all();job=db.get(Job,value['id']);pending=job.payload_json['pending']
    response=client.post('/api/v1/ai-operator/suite/commands',headers=h,json={'request_key':str(uuid4()),'agent_id':agent['id'],'provider':'preferred','conversation_id':pending['conversation_id'],'parent_run_id':pending['run_id'],'text':'Make it high priority'})
    assert response.status_code==200,response.text
    corrected=response.json();assert corrected['status']=='awaiting_approval',corrected
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=2)))['processed']==0
    db.refresh(job);assert job.status=='agent_waiting'
    assert job.payload_json['pending']['run_id']==corrected['id']
    approve(client,h,corrected);tick(client,db)
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=4)))['processed']==1
    db.refresh(job);assert job.payload_json['occurrences'][-1]['run_id']==corrected['id']
    assert job.payload_json['occurrences'][-1]['status']=='succeeded'
    assert db.query(CRMTask).one().priority=='High'
