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


@pytest.mark.parametrize('frequency',['daily','monthly','custom'])
def test_schedule_prepares_one_private_review_and_waits_for_approval(client,db,frequency):
    h,_,_,value,spec=draft(client,db,frequency=frequency,expires_at=(datetime.now(timezone.utc)+timedelta(days=90)).isoformat(),**({'interval':3,'interval_unit':'days'} if frequency=='custom' else {}))
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
    if frequency=='custom':
        from app.ai_operator.reminders import utc
        assert utc(job.run_at)==datetime.fromisoformat(spec['scheduled_at'])+timedelta(days=3)


def test_schedule_hash_revision_expiry_and_private_ownership(client,db):
    h,_,agent,value,spec=draft(client,db)
    assert client.post(ROOT+f'/{value["id"]}/activate',headers=h,json={'preview_hash':'0'*64}).status_code==409
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.post(ROOT+f'/{value["id"]}/cancel',headers=other).status_code==404
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=other).status_code==404
    assert client.post(ROOT+f'/{value["id"]}/resume',headers=other,json={'preview_hash':value['preview_hash']}).status_code==404
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).status_code==409
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


def test_pause_skips_missed_occurrences_and_resume_requires_exact_review(client,db,monkeypatch):
    from app.ai_operator import agent_schedules as schedules
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])
    r=client.post(ROOT+f'/{value["id"]}/pause',headers=h);assert r.status_code==200,r.text
    assert r.json()['status']=='paused' and r.json()['next_at'] is None
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).json()['controls']==r.json()['controls']
    later=first+timedelta(days=1,hours=2)
    assert asyncio.run(dispatch(db,client.app,later))['processed']==0
    monkeypatch.setattr(schedules,'now',lambda:later)
    assert client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':'0'*64}).status_code==409
    resumed=client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']})
    assert resumed.status_code==200,resumed.text
    assert resumed.json()['status']=='active' and datetime.fromisoformat(resumed.json()['next_at'])>later
    assert [i['action'] for i in resumed.json()['controls']]==['paused','resumed']
    assert db.query(SuiteRun).count()==0


def test_pause_waiting_preserves_review_and_recovers_same_occurrence(client,db,monkeypatch):
    from app.ai_operator import agent_schedules as schedules
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    asyncio.run(dispatch(db,client.app,first));db.expire_all();job=db.get(Job,value['id']);pending=job.payload_json['pending']
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).json()['status']=='paused'
    assert asyncio.run(dispatch(db,client.app,first+timedelta(minutes=2)))['processed']==0
    assert db.query(CRMTask).count()==0 and db.query(SuiteRun).count()==1
    monkeypatch.setattr(schedules,'now',lambda:first+timedelta(minutes=3))
    resumed=client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']})
    assert resumed.status_code==200 and resumed.json()['pending']['run_id']==pending['run_id']
    asyncio.run(dispatch(db,client.app,first+timedelta(minutes=4)))
    assert db.query(SuiteRun).count()==1 and db.query(CRMTask).count()==0
    db.refresh(job);assert job.status=='agent_waiting'


@pytest.mark.parametrize('resume_during_planning',[False,True])
def test_pause_during_planning_fences_late_result_and_resumes_without_duplicates(client,db,monkeypatch,resume_during_planning):
    from app.ai_operator import agent_schedules as schedules
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    original=schedules.prepare_agent
    async def pause_before_response(*args,**kwargs):
        result=await original(*args,**kwargs)
        assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).status_code==200
        if resume_during_planning:
            assert client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']}).status_code==200
        return result
    monkeypatch.setattr(schedules,'now',lambda:first)
    monkeypatch.setattr(schedules,'prepare_agent',pause_before_response)
    assert asyncio.run(dispatch(db,client.app,first))['processed']==0
    db.expire_all();job=db.get(Job,value['id'])
    assert job.status==('agent_preparing' if resume_during_planning else 'agent_paused')
    assert 'run_id' not in job.payload_json['pending'] and db.query(SuiteRun).count()==1
    if not resume_during_planning:
        assert client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']}).status_code==200
    monkeypatch.setattr(schedules,'prepare_agent',original)
    assert asyncio.run(dispatch(db,client.app,first+timedelta(seconds=1)))['processed']==1
    db.refresh(job);assert job.status=='agent_waiting' and job.payload_json['pending']['run_id']
    assert db.query(SuiteRun).count()==1 and db.query(CRMTask).count()==0


def test_planning_error_cannot_replace_a_concurrent_pause(client,db,monkeypatch):
    from app.ai_operator import agent_schedules as schedules
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    async def interrupted(*args,**kwargs):
        assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).status_code==200
        raise RuntimeError('Synthetic late network failure')
    monkeypatch.setattr(schedules,'prepare_agent',interrupted)
    asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)))
    db.expire_all();assert db.get(Job,value['id']).status=='agent_paused'


def test_paused_schedule_expires_without_starting_any_conversation(client,db):
    h,_,_,value,spec=draft(client,db);enable(client,h,value)
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).status_code==200
    assert asyncio.run(dispatch(db,client.app,datetime.fromisoformat(spec['expires_at'])))['processed']==0
    db.expire_all();assert db.get(Job,value['id']).status=='agent_expired'
    assert db.query(SuiteRun).count()==0


@pytest.mark.parametrize('mutation',['expiry','revision','session','once'])
def test_resume_checks_expiry_revision_session_and_missed_one_time_run(client,db,monkeypatch,mutation):
    from app.ai_operator import agent_schedules as schedules
    from app.models.user import UserSession
    h,_,agent,value,spec=draft(client,db,frequency='once' if mutation=='once' else 'daily');enable(client,h,value)
    assert client.post(ROOT+f'/{value["id"]}/pause',headers=h).status_code==200
    instant=datetime.fromisoformat(spec['scheduled_at'])+timedelta(minutes=1)
    if mutation=='expiry':instant=datetime.fromisoformat(spec['expires_at'])
    elif mutation=='revision':
        from app.ai_operator.assistant_models import AssistantConversation
        row=db.get(AssistantConversation,agent['id']);row.references={**row.references,'revision':2};db.commit()
    elif mutation=='session':
        row=db.get(Job,value['id']);db.get(UserSession,row.payload_json['security_context']['session_id']).status='Revoked';db.commit()
    monkeypatch.setattr(schedules,'now',lambda:instant)
    result=client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']})
    if mutation in ('expiry','once'):
        assert result.status_code==200,result.text
        assert result.json()['status']==('expired' if mutation=='expiry' else 'complete') and result.json()['next_at'] is None
    else:assert result.status_code in (401,403,409),result.text
    assert db.query(SuiteRun).count()==0



@pytest.mark.parametrize('stop',['emergency','quota'])
@pytest.mark.parametrize('stage',['preview','active','waiting'])
def test_owner_schedule_controls_remain_available_during_company_stop(client,db,stop,stage):
    from app.ai_agents.models import AiSecuritySetting,AiUsageLimit,AiUsageEvent
    h,user,agent,value,spec=draft(client,db)
    if stage!='preview':enable(client,h,value)
    first=datetime.fromisoformat(spec['scheduled_at'])+timedelta(seconds=1)
    child_id=None
    if stage=='waiting':
        assert asyncio.run(dispatch(db,client.app,first))['processed']==1
        db.expire_all();child_id=db.get(Job,value['id']).payload_json['pending']['run_id']
    existing_runs=db.query(SuiteRun).count()
    if stop=='emergency':db.add(AiSecuritySetting(company_id=1,ai_enabled=False))
    else:
        db.add(AiUsageLimit(company_id=1,limit_type='per_company',period='daily',max_requests=1,is_active=True))
        db.add(AiUsageEvent(company_id=1,user_id=user.id,event_type='synthetic_stop',module='CROSS'))
    db.commit();blocked=403 if stop=='emergency' else 429
    for suffix in ['',f'/{value["id"]}']:
        response=client.get(ROOT+suffix,headers=h)
        assert response.status_code==200,response.text
    response=client.post(ROOT+'/preview',headers=h,json={**spec,'request_key':str(uuid4())})
    assert response.status_code==blocked,response.text
    response=client.post(ROOT+f'/{value["id"]}/activate',headers=h,json={'preview_hash':value['preview_hash']})
    assert response.status_code==blocked,response.text
    if stage!='preview':
        response=client.post(ROOT+f'/{value["id"]}/pause',headers=h)
        assert response.status_code==200 and response.json()['status']=='paused'
        response=client.post(ROOT+f'/{value["id"]}/resume',headers=h,json={'preview_hash':value['preview_hash']})
        assert response.status_code==blocked,response.text
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    response=client.post(ROOT+f'/{value["id"]}/cancel',headers=other)
    assert response.status_code==404,response.text
    response=client.post(ROOT+f'/{value["id"]}/cancel',headers=h)
    assert response.status_code==200 and response.json()['status']=='cancelled'
    controls=response.json()['controls']
    response=client.post(ROOT+f'/{value["id"]}/cancel',headers=h)
    assert response.status_code==200 and response.json()['controls']==controls
    assert asyncio.run(dispatch(db,client.app,first+timedelta(hours=2)))['processed']==0
    assert db.query(SuiteRun).count()==existing_runs and db.query(CRMTask).count()==0
    if child_id:
        # A schedule controls future occurrences; each prepared action keeps its
        # own explicit approval and cancellation boundary.
        response=client.get('/api/v1/ai-operator/suite/runs/'+str(child_id),headers=h)
        assert response.status_code==200 and response.json()['status']=='awaiting_approval'
        response=client.post('/api/v1/ai-operator/suite/runs/'+str(child_id)+'/cancel',headers=h)
        assert response.status_code==200 and response.json()['status']=='cancelled'
    assert tick(client,db)==0
